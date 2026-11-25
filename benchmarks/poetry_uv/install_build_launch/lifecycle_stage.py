"""Run and time one benchmark stage (install, build, or launch) for one case.

This worker uses only the Python standard library so that the same file can be
executed natively on Windows and inside a WSL Linux distribution. The
orchestrator (``run_benchmarks.py``) starts it once per benchmark run.

Stages
------
``install``  Timed ``saf install`` on a fresh copy of the fixture solution.
``build``    Un-timed ``saf install``, then timed ``saf build`` (online or
             ``--offline-package``).
``launch``   Un-timed install and build (or a reused installer), then the timed
             unattended run of the generated installer executable
             (``--no-ui --installation-directory``).

Every run writes ``stage.log`` (full command output), ``preparation.log``
(un-timed commands), and ``result.json`` into its run directory. The timing
result is also printed as a ``BENCHMARK_RESULT=`` marker.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import tomllib
from typing import Any, TextIO

STAGES = ("install", "build", "launch")
NETWORKS = ("online", "offline")
BACKENDS = ("poetry", "uv")
SIZES = ("small", "medium", "large")
INSTALLER_GLOB = "*-installer*"
# Windows installers end in .exe; Linux installers have no suffix.
INSTALLER_SUFFIXES = {".exe", ""}

# Copy exclusions keep generated and machine-specific files out of each workspace.
COPY_EXCLUSIONS = {
    ".git",
    ".mypy_cache",
    ".poetry",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "dist",
    "poetry.toml",
}

# The frozen installer buffers its stdout when it is not attached to a console,
# so line arrival times are useless. Instead, use the durations it prints itself:
#   "preload time: <seconds>"
#   "Installation completed in <minutes> minutes."  (full precision)
#   "Execution time: <minutes> minutes."           (one decimal, fallback)
PRELOAD_PATTERN = re.compile(r"^preload time:\s*(?P<value>[0-9.]+)")
INSTALLER_TOTAL_PATTERNS = (
    re.compile(r"^Installation completed in\s*(?P<value>[0-9.]+)\s*minutes"),
    re.compile(r"^Execution time:\s*(?P<value>[0-9.]+)\s*minutes"),
)
SHORTCUT_PATTERN = re.compile(r"^Shortcut created at (?P<path>.+?)\s*$")
# Transient failures that justify a retry on a fresh workspace:
# - dropped TLS sessions / resets (pip, git, uv, requests);
# - SAF's PyPI access check, which reports any request failure as a missing SSL
#   certificate and then aborts because no one answers the prompt;
# - Windows file locks (antivirus/indexer) when deleting temporary folders.
NETWORK_ERROR_PATTERN = re.compile(
    r"SSLEOFError|UNEXPECTED_EOF_WHILE_READING|ConnectionResetError|RemoteDisconnected|"
    r"Connection aborted|Connection was reset|Connection reset|ConnectTimeout|ReadTimeout|Read timed out|"
    r"The read operation timed out|"
    r"Max retries exceeded|Temporary failure in name resolution|getaddrinfo failed|error sending request|"
    r"connection closed before message completed|operation timed out|"
    r"All attempts to connect to [\w.-]+ failed|client error \(Connect\)|Failed to fetch: https?://|"
    r"Install will fail without a valid SSL certificate|"
    r"WinError 32\]|being used by another process",
)


class StageError(RuntimeError):
    """A benchmark stage command failed."""


def utc_now() -> str:
    """Return the current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def command_text(command: list[str | Path]) -> str:
    """Return a readable command line for logs."""
    return subprocess.list2cmdline([str(argument) for argument in command])


def remove_tree(path: Path) -> None:
    """Remove a directory tree, retrying for transient Windows file locks."""
    if not path.exists():
        return

    def make_writable(function: Any, failed_path: str, _excinfo: Any) -> None:
        os.chmod(failed_path, stat.S_IWRITE)
        function(failed_path)

    for attempt in range(1, 11):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(path, onexc=make_writable)
            else:
                shutil.rmtree(path, onerror=make_writable)
            return
        except OSError:
            if attempt == 10:
                raise
            time.sleep(1.0)


def copy_ignore(_directory: str, names: list[str]) -> set[str]:
    """Exclude generated files when copying a fixture."""
    return {name for name in names if name in COPY_EXCLUSIONS or name.endswith(".egg-info")}


def sandbox_environment(run_root: Path, isolate_caches: bool, share_profile: bool) -> dict[str, str]:
    """Return an environment whose caches and temporary files stay under ``run_root``.

    ``isolate_caches`` gives every run a cold Poetry, UV, and pip cache so the
    backends are compared fairly. The SAF CLI solution database lives in the
    user profile; it is only redirected when ``share_profile`` is false.
    """
    environment = os.environ.copy()
    sandbox = run_root / "environment"
    locations: dict[str, Path] = {
        "TEMP": sandbox / "temp",
        "TMP": sandbox / "temp",
        "TMPDIR": sandbox / "temp",
    }
    if isolate_caches:
        locations.update(
            {
                "PIP_CACHE_DIR": sandbox / "cache" / "pip",
                "POETRY_CACHE_DIR": sandbox / "cache" / "poetry",
                "UV_CACHE_DIR": sandbox / "cache" / "uv",
                "XDG_CACHE_HOME": sandbox / "cache" / "xdg",
            },
        )
    if not share_profile:
        locations.update(
            {
                "APPDATA": sandbox / "appdata",
                "LOCALAPPDATA": sandbox / "localappdata",
                "XDG_DATA_HOME": sandbox / "share",
                "XDG_CONFIG_HOME": sandbox / "config",
            },
        )
    for variable, location in locations.items():
        location.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(location)
    # Keep tool output plain and non-interactive in the logs.
    environment.setdefault("NO_COLOR", "1")
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


class Recorder:
    """Run commands, stream their output into a log, and time them."""

    def __init__(self, log_file: Path, echo: bool) -> None:
        self.log_file = log_file
        self.echo = echo
        log_file.parent.mkdir(parents=True, exist_ok=True)
        self._stream: TextIO = log_file.open("a", encoding="utf-8", errors="replace")

    def close(self) -> None:
        """Close the log file."""
        self._stream.close()

    def note(self, message: str) -> None:
        """Write a line to the log and optionally to the console."""
        self._stream.write(message + "\n")
        self._stream.flush()
        if self.echo:
            print(message, flush=True)

    def run(
        self,
        command: list[str | Path],
        *,
        cwd: Path,
        environment: dict[str, str],
        timeout: float | None,
    ) -> tuple[float, list[tuple[float, str]]]:
        """Run ``command`` and return its wall time and time-stamped output lines."""
        normalized = [str(argument) for argument in command]
        self.note(f"\n[{utc_now()}] $ {command_text(normalized)}")
        self.note(f"    cwd: {cwd}")
        started = time.perf_counter()
        process = subprocess.Popen(
            normalized,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if process.stdout is None:
            raise StageError("The command did not provide an output stream.")
        lines: list[tuple[float, str]] = []
        try:
            for line in process.stdout:
                offset = time.perf_counter() - started
                text = line.rstrip("\r\n")
                lines.append((offset, text))
                self._stream.write(f"[{offset:9.3f}s] {text}\n")
            self._stream.flush()
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait()
            raise StageError(f"Command timed out after {timeout} s: {command_text(normalized)}") from error
        elapsed = time.perf_counter() - started
        self.note(f"[{utc_now()}] exit code {returncode} after {elapsed:.3f} s")
        if returncode != 0:
            tail = "\n".join(text for _, text in lines[-80:])
            cause = next((text.strip() for _, text in reversed(lines) if text.strip()), "no output")
            raise StageError(
                f"{Path(normalized[0]).name} {' '.join(normalized[1:])} exited with {returncode}: {cause}\n{tail}",
            )
        return elapsed, lines


def saf_build_command(saf: str, network: str) -> list[str | Path]:
    """Return the SAF build command for the requested network mode."""
    command: list[str | Path] = [saf, "build"]
    if network == "offline":
        command.append("--offline-package")
    return command


def find_installer(solution: Path) -> Path:
    """Return the installer executable produced by ``saf build``."""
    dist = solution / "dist"
    candidates = [
        path
        for path in dist.glob(INSTALLER_GLOB)
        if path.is_file() and path.suffix.lower() in INSTALLER_SUFFIXES
    ]
    if not candidates:
        raise StageError(f"No installer executable matching {INSTALLER_GLOB} found in {dist}.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def launch_phases(lines: list[tuple[float, str]], total: float) -> dict[str, float]:
    """Split the launch time using the durations printed by the installer.

    * ``startup``: executable start until the installer logic runs (PyInstaller
      unpacking, third-party extraction, prerequisite checks).
    * ``setup``: file deployment and dependency installation.
    * ``preload``: first start of the installed solution.
    """
    preload: float | None = None
    installer_total: float | None = None
    for _offset, text in lines:
        stripped = text.strip()
        match = PRELOAD_PATTERN.search(stripped)
        if match and preload is None:
            preload = float(match.group("value"))
        for pattern in INSTALLER_TOTAL_PATTERNS:
            match = pattern.search(stripped)
            if match and installer_total is None:
                installer_total = float(match.group("value")) * 60.0
    phases: dict[str, float] = {}
    if installer_total is not None:
        installer_total = min(installer_total, total)
        phases["startup_seconds"] = max(0.0, total - installer_total)
        if preload is not None:
            phases["preload_seconds"] = min(preload, installer_total)
            phases["setup_seconds"] = max(0.0, installer_total - preload)
    elif preload is not None:
        phases["preload_seconds"] = preload
    return phases


def created_shortcuts(lines: list[tuple[float, str]]) -> list[Path]:
    """Return shortcut paths reported by the installer."""
    paths: list[Path] = []
    for _, text in lines:
        match = SHORTCUT_PATTERN.search(text.strip())
        if match:
            paths.append(Path(match.group("path")))
    return paths


def directory_size(path: Path) -> int:
    """Return the total size of files below ``path`` in bytes."""
    total = 0
    for root, _directories, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def tool_versions(saf: str, environment: dict[str, str]) -> dict[str, str]:
    """Collect tool versions for the report header."""
    versions: dict[str, str] = {"python": platform.python_version(), "platform": platform.platform()}
    for name, command in {"saf": [saf, "--version"], "uv": ["uv", "--version"]}.items():
        try:
            completed = subprocess.run(
                command,
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            versions[name] = (completed.stdout or completed.stderr).strip().splitlines()[0]
        except (OSError, IndexError, subprocess.SubprocessError):
            versions[name] = "unavailable"
    return versions


def copy_poetry_credentials_to_uv(solution: Path, environment: dict[str, str]) -> list[str]:
    """Map ``POETRY_HTTP_BASIC_<INDEX>_*`` to ``UV_INDEX_<INDEX>_*`` for UV private indexes.

    ``saf install`` performs this mapping internally, but the desktop installer
    used by ``saf build --offline-package`` (and the online build of private
    wheels) reads only ``UV_INDEX_*``. Without it pip prompts for a password and
    fails. Only variable names are returned; values are never logged.
    """
    project_file = solution / "pyproject.toml"
    try:
        project = tomllib.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    indexes = project.get("tool", {}).get("uv", {}).get("index", [])
    if not isinstance(indexes, list):
        return []
    copied: list[str] = []
    for index in indexes:
        if not isinstance(index, dict) or not isinstance(index.get("name"), str):
            continue
        slug = re.sub(r"[^A-Za-z0-9]", "_", index["name"]).upper()
        for credential in ("USERNAME", "PASSWORD"):
            uv_variable = f"UV_INDEX_{slug}_{credential}"
            poetry_variable = f"POETRY_HTTP_BASIC_{slug}_{credential}"
            if not environment.get(uv_variable) and environment.get(poetry_variable):
                environment[uv_variable] = environment[poetry_variable]
                copied.append(uv_variable)
    return copied


def prepare_workspace(fixture: Path, workspace: Path) -> Path:
    """Copy the fixture into a fresh workspace and return the solution root.

    Call this before :func:`sandbox_environment`, which creates directories
    inside the workspace.
    """
    if workspace.exists():
        remove_tree(workspace)
    solution = workspace / "solution"
    shutil.copytree(fixture, solution, ignore=copy_ignore)
    return solution


def reuse_or_build_installer(
    arguments: argparse.Namespace,
    solution: Path,
    preparation: Recorder,
    environment: dict[str, str],
) -> tuple[Path, bool]:
    """Return an installer for the launch stage, building it when no cache exists."""
    cache = Path(arguments.installer_cache) if arguments.installer_cache else None
    if cache is not None and cache.is_dir():
        cached = [path for path in cache.glob(INSTALLER_GLOB) if path.is_file()]
        if cached:
            preparation.note(f"Reusing cached installer {cached[0]}")
            return cached[0], True

    preparation.run([arguments.saf, "install"], cwd=solution, environment=environment, timeout=arguments.timeout)
    preparation.run(
        saf_build_command(arguments.saf, arguments.network),
        cwd=solution,
        environment=environment,
        timeout=arguments.timeout,
    )
    installer = find_installer(solution)
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        cached_installer = cache / installer.name
        shutil.copy2(installer, cached_installer)
        if os.name != "nt":
            cached_installer.chmod(cached_installer.stat().st_mode | stat.S_IXUSR)
        preparation.note(f"Cached installer at {cached_installer}")
        return cached_installer, False
    return installer, False


def run_stage(arguments: argparse.Namespace) -> dict[str, Any]:
    """Run the requested stage and return the result record."""
    run_directory = Path(arguments.run_directory).expanduser().resolve()
    workspace = Path(arguments.workspace).expanduser().resolve()
    fixture = Path(arguments.fixture).expanduser().resolve()
    if arguments.installer_cache:
        arguments.installer_cache = str(Path(arguments.installer_cache).expanduser())
    if arguments.saf.startswith("~"):
        arguments.saf = str(Path(arguments.saf).expanduser())
    run_directory.mkdir(parents=True, exist_ok=True)

    stage_log = Recorder(run_directory / "stage.log", echo=False)
    preparation_log = Recorder(run_directory / "preparation.log", echo=False)
    result: dict[str, Any] = {
        "stage": arguments.stage,
        "network": arguments.network,
        "backend": arguments.backend,
        "size": arguments.size,
        "os": platform.system(),
        "status": "failed",
        "started": utc_now(),
        "finished": None,
        "preparation_seconds": None,
        "stage_seconds": None,
        "installer_reused": None,
        "installer_bytes": None,
        "venv_bytes": None,
        "workspace": str(workspace),
        "error": None,
    }
    environment = os.environ.copy()
    shortcuts: list[Path] = []
    try:
        print("Preparing workspace.", flush=True)
        preparation_started = time.perf_counter()
        solution = prepare_workspace(fixture, workspace)
        environment = sandbox_environment(workspace, arguments.isolate_caches, arguments.share_profile)
        copied = copy_poetry_credentials_to_uv(solution, environment)
        if copied:
            preparation_log.note(f"Mapped Poetry credentials to UV variables: {', '.join(copied)}")
        probe_started = time.perf_counter()
        result["tools"] = tool_versions(arguments.saf, environment)
        result["tools"]["saf_path"] = arguments.saf
        # Exclude the version probe from the reported preparation time.
        preparation_started += time.perf_counter() - probe_started

        if arguments.stage == "install":
            result["preparation_seconds"] = time.perf_counter() - preparation_started
            print("Running: saf install", flush=True)
            elapsed, _ = stage_log.run(
                [arguments.saf, "install"],
                cwd=solution,
                environment=environment,
                timeout=arguments.timeout,
            )
            result["stage_seconds"] = elapsed
            venv = solution / ".venv"
            result["venv_bytes"] = directory_size(venv) if venv.is_dir() else None

        elif arguments.stage == "build":
            print("Preparing: saf install (not timed)", flush=True)
            preparation_log.run(
                [arguments.saf, "install"],
                cwd=solution,
                environment=environment,
                timeout=arguments.timeout,
            )
            result["preparation_seconds"] = time.perf_counter() - preparation_started
            print(f"Running: saf build ({arguments.network})", flush=True)
            elapsed, _ = stage_log.run(
                saf_build_command(arguments.saf, arguments.network),
                cwd=solution,
                environment=environment,
                timeout=arguments.timeout,
            )
            result["stage_seconds"] = elapsed
            installer = find_installer(solution)
            result["installer_bytes"] = installer.stat().st_size
            if arguments.installer_cache:
                cache = Path(arguments.installer_cache)
                cache.mkdir(parents=True, exist_ok=True)
                shutil.copy2(installer, cache / installer.name)

        else:  # launch
            print("Preparing: installer (not timed)", flush=True)
            installer, reused = reuse_or_build_installer(arguments, solution, preparation_log, environment)
            result["installer_reused"] = reused
            result["installer_bytes"] = installer.stat().st_size
            install_target = workspace / "installed"
            install_target.mkdir(parents=True, exist_ok=True)
            result["preparation_seconds"] = time.perf_counter() - preparation_started
            print("Running: installer --no-ui", flush=True)
            elapsed, lines = stage_log.run(
                [installer, "--no-ui", "--installation-directory", install_target],
                cwd=workspace,
                environment=environment,
                timeout=arguments.timeout,
            )
            result["stage_seconds"] = elapsed
            result.update(launch_phases(lines, elapsed))
            shortcuts = created_shortcuts(lines)
            result["venv_bytes"] = directory_size(install_target)

        result["status"] = "passed"
    except (OSError, StageError, subprocess.SubprocessError) as error:
        result["error"] = str(error).splitlines()[0] if str(error) else type(error).__name__
        result["network_error"] = bool(NETWORK_ERROR_PATTERN.search(str(error)))
        stage_log.note(f"\nFAILED: {error}")
    finally:
        for shortcut in shortcuts:
            try:
                shortcut.unlink(missing_ok=True)
                stage_log.note(f"Removed benchmark shortcut {shortcut}")
            except OSError as error:
                stage_log.note(f"Could not remove shortcut {shortcut}: {error}")
        if not arguments.keep_workspace:
            try:
                remove_tree(workspace)
            except OSError as error:
                stage_log.note(f"Could not remove workspace {workspace}: {error}")
        result["finished"] = utc_now()
        stage_log.close()
        preparation_log.close()
        (run_directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse worker arguments supplied by the orchestrator."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--network", choices=NETWORKS, default="online")
    parser.add_argument("--backend", choices=BACKENDS, required=True)
    parser.add_argument("--size", choices=SIZES, required=True)
    parser.add_argument("--fixture", required=True, help="Fixture solution directory to copy.")
    parser.add_argument("--workspace", required=True, help="Scratch directory for this run.")
    parser.add_argument("--run-directory", required=True, help="Directory that receives logs and result.json.")
    parser.add_argument("--saf", default="saf", help="SAF CLI executable.")
    parser.add_argument("--installer-cache", default="", help="Directory used to share built installers.")
    parser.add_argument("--timeout", type=float, default=None, help="Per-command timeout in seconds.")
    parser.add_argument("--keep-workspace", action="store_true", help="Keep the scratch workspace.")
    parser.add_argument(
        "--no-isolate-caches",
        dest="isolate_caches",
        action="store_false",
        help="Use the user's Poetry/UV/pip caches (warm-cache measurement).",
    )
    parser.add_argument(
        "--isolate-profile",
        dest="share_profile",
        action="store_false",
        help="Also redirect APPDATA/LOCALAPPDATA (isolates the SAF CLI solution database).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run one stage and print the result marker."""
    arguments = parse_arguments(argv)
    result = run_stage(arguments)
    print("BENCHMARK_RESULT=" + json.dumps(result), flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
