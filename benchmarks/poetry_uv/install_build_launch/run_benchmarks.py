"""Benchmark SAF install, build, and installer launch with Poetry and UV.

The harness builds one solution per backend from the shared fixture and
times three stages for both backends:

* ``dev`` mode:  ``install`` (``saf install``) and ``build`` (``saf build``,
  online or ``--offline-package``).
* ``prod`` mode: ``launch`` (unattended run of the generated installer).

Without options, the harness runs the default matrix on the current operating
system: both modes, all sizes, both backends, both network modes, three runs
each. Linux cases can be run from Windows through WSL.

Results are written to ``results/<timestamp>/`` using the same tree as the
manual benchmark (``<mode>/<stage>/<OS>/<size>/[<network>/]<Backend>/runN``)
and summarized in ``report.md``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shlex
import shutil
import subprocess
import sys
import time
from typing import Any

from fixture_builder import LOCK_FILES
from report import collect_records, write_reports

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
WORKER_SCRIPT = SCRIPT_DIRECTORY / "lifecycle_stage.py"
DEFAULT_CONFIG_NAMES = ("config.local.json", "config.json")

MODES = ("dev", "prod")
MODE_STAGES = {"dev": ("install", "build"), "prod": ("launch",)}
STAGES = ("install", "build", "launch")
OPERATING_SYSTEMS = ("Windows", "Linux")
SIZES = ("small",)
NETWORKS = ("online", "offline")
BACKENDS = ("poetry", "uv")
BACKEND_LABELS = {"poetry": "Poetry", "uv": "UV"}
DEFAULT_RUN_COUNT = 3

# Variables forwarded into WSL so private indexes and GitHub dependencies work.
FORWARDED_PREFIXES = ("POETRY_HTTP_BASIC_", "POETRY_CERTIFICATES_", "UV_INDEX_", "UV_DEFAULT_INDEX")
FORWARDED_NAMES = ("ANSYS_GITHUB_PAT", "GITHUB_TOKEN", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")
PROGRESS_PREFIXES = ("Preparing", "Running")


@dataclass(frozen=True)
class PlannedRun:
    """One benchmark run in the matrix."""

    mode: str
    stage: str
    os_name: str
    size: str
    network: str | None
    backend: str
    repetition: int

    @property
    def case_parts(self) -> tuple[str, ...]:
        """Return the directory parts identifying the case (without the run number)."""
        parts = [self.mode, self.stage, self.os_name, self.size]
        if self.network is not None:
            parts.append(self.network)
        parts.append(BACKEND_LABELS[self.backend])
        return tuple(parts)

    @property
    def relative_directory(self) -> PurePosixPath:
        """Return the run directory relative to the result root."""
        return PurePosixPath(*self.case_parts, f"run{self.repetition}")

    @property
    def label(self) -> str:
        """Return a readable label."""
        return str(self.relative_directory)


@dataclass
class WslSettings:
    """Settings used to run Linux cases through WSL."""

    distribution: str | None = None
    python: str = "python3"
    saf_executable: str = "saf"
    work_root: str = "~/.cache/saf-lifecycle-benchmark"


@dataclass
class HarnessConfig:
    """Harness configuration loaded from JSON or defaults."""

    saf_executable: str | None = None
    fixture_directory: Path = SCRIPT_DIRECTORY / "fixture"
    work_root: Path = SCRIPT_DIRECTORY / ".work"
    timeout_seconds: float | None = 3600.0
    isolate_caches: bool = True
    forward_environment: list[str] = field(default_factory=list)
    wsl: WslSettings = field(default_factory=WslSettings)

    @classmethod
    def from_file(cls, path: Path) -> HarnessConfig:
        """Load a configuration file, resolving relative paths beside it."""
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Configuration must be a JSON object: {path}")
        config = cls()
        base = path.parent
        if data.get("saf_executable"):
            config.saf_executable = str(data["saf_executable"])
        if data.get("fixtures_directory"):
            raise ValueError("'fixtures_directory' was replaced by 'fixture_directory' (the shared fixture folder).")
        if data.get("fixture_directory"):
            config.fixture_directory = (base / str(data["fixture_directory"])).resolve()
        if data.get("work_root"):
            config.work_root = (base / str(data["work_root"])).resolve()
        if "timeout_seconds" in data:
            timeout = data["timeout_seconds"]
            config.timeout_seconds = None if timeout in (None, 0) else float(timeout)
        if "isolate_caches" in data:
            config.isolate_caches = bool(data["isolate_caches"])
        config.forward_environment = [str(name) for name in data.get("forward_environment", [])]
        wsl = data.get("wsl") or {}
        if not isinstance(wsl, dict):
            raise ValueError("The 'wsl' configuration entry must be an object.")
        config.wsl = WslSettings(
            distribution=wsl.get("distribution") or None,
            python=str(wsl.get("python") or "python3"),
            saf_executable=str(wsl.get("saf_executable") or "saf"),
            work_root=str(wsl.get("work_root") or WslSettings.work_root),
        )
        return config


def positive_integer(value: str) -> int:
    """Parse a positive run count."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("run count must be at least 1")
    return parsed


def case_insensitive(choices: tuple[str, ...]) -> Any:
    """Return an argparse type that maps a value onto ``choices`` ignoring case."""
    lookup = {choice.lower(): choice for choice in choices}

    def parse(value: str) -> str:
        try:
            return lookup[value.lower()]
        except KeyError as error:
            raise argparse.ArgumentTypeError(
                f"invalid choice: {value!r} (choose from {', '.join(choices)})",
            ) from error

    return parse


def current_os() -> str:
    """Return the current operating system label."""
    system = platform.system()
    if system not in OPERATING_SYSTEMS:
        raise RuntimeError(f"Unsupported operating system: {system}")
    return system


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse benchmark selection and output options."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    selection = parser.add_argument_group("matrix selection (each option accepts one or more values)")
    selection.add_argument(
        "--mode",
        nargs="+",
        type=case_insensitive(MODES),
        metavar="MODE",
        help="dev (install + build) and/or prod (launch). Default: dev prod.",
    )
    selection.add_argument(
        "--stage",
        nargs="+",
        type=case_insensitive(STAGES),
        metavar="STAGE",
        help="Narrow the stages: install, build, launch. Default: all stages of the selected modes.",
    )
    selection.add_argument(
        "--os",
        dest="os_names",
        nargs="+",
        type=case_insensitive(OPERATING_SYSTEMS),
        metavar="OS",
        help="Windows and/or Linux. Linux runs through WSL on Windows. Default: current OS.",
    )
    selection.add_argument(
        "--size",
        nargs="+",
        type=case_insensitive(SIZES),
        metavar="SIZE",
        help="Solution size: small. Default: all available sizes.",
    )
    selection.add_argument(
        "--backend",
        nargs="+",
        type=case_insensitive(BACKENDS),
        metavar="BACKEND",
        help="poetry and/or uv. Default: both.",
    )
    selection.add_argument(
        "--network",
        nargs="+",
        type=case_insensitive(NETWORKS),
        metavar="NETWORK",
        help="online and/or offline package for build and launch. Default: both.",
    )
    selection.add_argument(
        "--run",
        dest="run_count",
        type=positive_integer,
        default=DEFAULT_RUN_COUNT,
        metavar="N",
        help=f"Number of runs for every selected case (default: {DEFAULT_RUN_COUNT}).",
    )

    control = parser.add_argument_group("execution control")
    control.add_argument("-c", "--config", type=Path, help="JSON configuration file.")
    control.add_argument(
        "--output-dir",
        type=Path,
        help="Result directory inside this benchmark folder. Default: results/<timestamp>.",
    )
    control.add_argument("--dry-run", action="store_true", help="Print the selected runs without running them.")
    control.add_argument("--fail-fast", action="store_true", help="Stop after the first failed run.")
    control.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep each run's scratch workspace (.venv, dist, installed files). Uses a lot of disk.",
    )
    control.add_argument(
        "--warm-cache",
        action="store_true",
        help="Use the user's Poetry/UV/pip caches instead of a cold cache per run.",
    )
    control.add_argument(
        "--retries",
        type=int,
        default=2,
        metavar="N",
        help="Re-run a failed run up to N times on a fresh workspace when it failed with a transient error "
        "(dropped TLS connection or reset, SAF's PyPI check failing, Windows temp-file lock). "
        "Retries are listed in the report. Default: 2.",
    )
    control.add_argument(
        "--retry-delay",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Wait before a retry, multiplied by the attempt number (60 s, then 120 s, ...). Default: 60.",
    )
    control.add_argument(
        "--rerun-failed",
        action="store_true",
        help="Re-run only the runs of the selection that did not pass in --output-dir (an existing result "
        "directory). Previous logs are kept in previousN/, and report.md is rebuilt from all runs.",
    )
    return parser.parse_args(argv)


def build_plan(arguments: argparse.Namespace) -> list[PlannedRun]:
    """Build the ordered run matrix.

    Runs of the same case alternate between backends so that slow drifts of the
    machine or network affect Poetry and UV equally. ``dev`` runs first so that
    ``prod`` can reuse the installers built during the ``build`` stage.
    """
    modes = [mode for mode in MODES if mode in (arguments.mode or MODES)]
    requested_stages = set(arguments.stage or STAGES)
    if arguments.stage and not arguments.mode:
        modes = [mode for mode in MODES if requested_stages & set(MODE_STAGES[mode])]
    os_names = [name for name in OPERATING_SYSTEMS if name in (arguments.os_names or (current_os(),))]
    sizes = [size for size in SIZES if size in (arguments.size or SIZES)]
    networks = [network for network in NETWORKS if network in (arguments.network or NETWORKS)]
    backends = [backend for backend in BACKENDS if backend in (arguments.backend or BACKENDS)]

    plan: list[PlannedRun] = []
    for mode in modes:
        stages = [stage for stage in MODE_STAGES[mode] if stage in requested_stages]
        if not stages:
            raise ValueError(f"No selected stage belongs to mode '{mode}'.")
        for stage in stages:
            stage_networks: list[str | None] = [None] if stage == "install" else list(networks)
            for os_name in os_names:
                for size in sizes:
                    for network in stage_networks:
                        for repetition in range(1, arguments.run_count + 1):
                            for backend in backends:
                                plan.append(
                                    PlannedRun(mode, stage, os_name, size, network, backend, repetition),
                                )
    return plan


def find_default_config() -> Path | None:
    """Find a local configuration beside this script."""
    for name in DEFAULT_CONFIG_NAMES:
        candidate = SCRIPT_DIRECTORY / name
        if candidate.is_file():
            return candidate
    return None


def default_output_directory() -> Path:
    """Return a timestamped result directory."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return SCRIPT_DIRECTORY / "results" / timestamp


def resolve_output_directory(value: Path | None) -> Path:
    """Resolve the output directory and keep it inside this benchmark folder."""
    candidate = SCRIPT_DIRECTORY / value if value is not None and not value.is_absolute() else value
    output_root = (candidate or default_output_directory()).resolve()
    try:
        output_root.relative_to(SCRIPT_DIRECTORY)
    except ValueError as error:
        raise ValueError(f"Output directory must be inside {SCRIPT_DIRECTORY}.") from error
    return output_root


def to_wsl_path(path: Path) -> str:
    """Convert a Windows drive path to its ``/mnt/<drive>`` WSL equivalent."""
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive or len(drive) != 1:
        raise ValueError(f"Cannot map {resolved} into WSL; use a path on a drive letter.")
    remainder = resolved.as_posix()[len(resolved.drive):]
    return f"/mnt/{drive}{remainder}"


def find_wsl() -> str:
    """Return the WSL launcher executable."""
    for name in ("wsl.exe", "wsl"):
        found = shutil.which(name)
        if found:
            return found
    # PATH may be unusable (for example Python started from MSYS/Git Bash); WSL lives in System32.
    system_wsl = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "wsl.exe"
    if system_wsl.is_file():
        return str(system_wsl)
    raise FileNotFoundError("WSL is required to run Linux cases on Windows, but wsl.exe was not found.")


def resolve_windows_saf(config: HarnessConfig) -> str:
    """Return the SAF CLI used for native runs."""
    if config.saf_executable:
        return config.saf_executable
    found = shutil.which("saf")
    if found:
        return found
    # Fall back to the SAF CLI installed next to the running interpreter (active virtual environment).
    scripts = Path(sys.executable).parent
    for candidate in (scripts / "saf.exe", scripts / "Scripts" / "saf.exe", scripts / "saf"):
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(
        "SAF CLI not found on PATH. Activate an environment with 'saf' or set 'saf_executable' in the config.",
    )


def validate(config: HarnessConfig, plan: list[PlannedRun]) -> None:
    """Fail early when fixtures or execution targets are missing."""
    if not plan:
        raise ValueError("The selection does not contain any run.")
    fixture = config.fixture_directory
    required = [fixture / "solution", fixture / "dependencies.toml"]
    required += [fixture / LOCK_FILES[backend] for backend in sorted({item.backend for item in plan})]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Fixture incomplete, missing: {', '.join(missing)}")
    host = current_os()
    for os_name in sorted({item.os_name for item in plan}):
        if os_name == host:
            continue
        if host == "Windows" and os_name == "Linux":
            continue
        raise ValueError(f"{os_name} cases cannot run on {host}.")


def worker_arguments(
    item: PlannedRun,
    *,
    fixture: str,
    workspace: str,
    run_directory: str,
    saf: str,
    installer_cache: str,
    timeout: float | None,
    keep_workspace: bool,
    isolate_caches: bool,
) -> list[str]:
    """Return the worker command-line arguments for one run."""
    arguments = [
        "--stage",
        item.stage,
        "--network",
        item.network or "online",
        "--backend",
        item.backend,
        "--size",
        item.size,
        "--fixture",
        fixture,
        "--workspace",
        workspace,
        "--run-directory",
        run_directory,
        "--saf",
        saf,
        "--installer-cache",
        installer_cache,
    ]
    if timeout:
        arguments.extend(["--timeout", str(timeout)])
    if keep_workspace:
        arguments.append("--keep-workspace")
    if not isolate_caches:
        arguments.append("--no-isolate-caches")
    return arguments


def forwarded_variables(config: HarnessConfig) -> list[str]:
    """Return environment variable names to forward into WSL."""
    names = {
        name
        for name in os.environ
        if name.startswith(FORWARDED_PREFIXES) or name in FORWARDED_NAMES
    }
    names.update(name for name in config.forward_environment if name in os.environ)
    return sorted(names)


def build_command(
    item: PlannedRun,
    workspace_name: str,
    config: HarnessConfig,
    session: str,
    run_directory: Path,
    arguments: argparse.Namespace,
) -> tuple[list[str], dict[str, str]]:
    """Return the worker command and environment for native or WSL execution."""
    isolate = config.isolate_caches and not arguments.warm_cache
    case_key = "/".join(part for part in (item.os_name, item.size, item.network or "online", item.backend))
    if item.os_name == current_os():
        work_root = config.work_root / session
        worker = worker_arguments(
            item,
            fixture=str(config.fixture_directory),
            workspace=str(work_root / workspace_name),
            run_directory=str(run_directory),
            saf=resolve_windows_saf(config) if item.os_name == "Windows" else (config.saf_executable or "saf"),
            installer_cache=str(work_root / "installers" / case_key),
            timeout=config.timeout_seconds,
            keep_workspace=arguments.keep_workspace,
            isolate_caches=isolate,
        )
        return [sys.executable, "-u", str(WORKER_SCRIPT), *worker], os.environ.copy()

    # Linux case from Windows: run the same worker inside WSL. Workspaces stay on
    # the Linux file system for realistic I/O; logs are written back to /mnt/<drive>.
    work_root = f"{config.wsl.work_root.rstrip('/')}/{session}"
    worker = worker_arguments(
        item,
        fixture=to_wsl_path(config.fixture_directory),
        workspace=f"{work_root}/{workspace_name}",
        run_directory=to_wsl_path(run_directory),
        saf=config.wsl.saf_executable,
        installer_cache=f"{work_root}/installers/{case_key}",
        timeout=config.timeout_seconds,
        keep_workspace=arguments.keep_workspace,
        isolate_caches=isolate,
    )
    # Every argument is quoted; the worker expands "~" itself with Linux's HOME.
    script = " ".join(
        shlex.quote(part)
        for part in (config.wsl.python, "-u", to_wsl_path(WORKER_SCRIPT), *worker)
    )
    command = [find_wsl()]
    if config.wsl.distribution:
        command.extend(["-d", config.wsl.distribution])
    command.extend(["--", "bash", "-lc", script])
    environment = os.environ.copy()
    forwarded = forwarded_variables(config)
    if forwarded:
        existing = environment.get("WSLENV", "")
        environment["WSLENV"] = ":".join(filter(None, [existing, *forwarded]))
    return command, environment


def extract_result(output: str) -> dict[str, Any] | None:
    """Read the worker's result marker."""
    for line in reversed(output.splitlines()):
        if line.startswith("BENCHMARK_RESULT="):
            try:
                result = json.loads(line.removeprefix("BENCHMARK_RESULT="))
            except json.JSONDecodeError:
                return None
            return result if isinstance(result, dict) else None
    return None


def run_attempt(
    item: PlannedRun,
    workspace_name: str,
    config: HarnessConfig,
    session: str,
    run_directory: Path,
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], str | None]:
    """Run the worker once; return its result (or None) and an error message."""
    worker_log = run_directory / "worker.log"
    try:
        command, environment = build_command(item, workspace_name, config, session, run_directory, arguments)
        process = subprocess.Popen(
            command,
            cwd=SCRIPT_DIRECTORY,
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
            raise RuntimeError("The worker did not provide an output stream.")
        lines: list[str] = []
        for line in process.stdout:
            lines.append(line)
            if line.startswith(PROGRESS_PREFIXES):
                print(f"  {line.rstrip()}", flush=True)
        process.wait()
        output = "".join(lines)
        worker_log.write_text(f"$ {subprocess.list2cmdline(command)}\n\n{output}", encoding="utf-8")
        result = extract_result(output)
        if result is None:
            raise RuntimeError(f"The worker exited with code {process.returncode} without a result. See {worker_log}.")
        return result, None
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        return {}, str(error)


def archive_attempt(run_directory: Path, attempt: int) -> None:
    """Move a failed attempt's logs into ``attempt<N>/`` so the retry starts clean."""
    archive = run_directory / f"attempt{attempt}"
    archive.mkdir(parents=True, exist_ok=True)
    for path in list(run_directory.iterdir()):
        if path.is_file():
            path.replace(archive / path.name)


def run_one(
    item: PlannedRun,
    index: int,
    config: HarnessConfig,
    session: str,
    output_root: Path,
    arguments: argparse.Namespace,
) -> dict[str, Any]:
    """Run one planned benchmark, retrying transient network failures, and return its record."""
    run_directory = output_root.joinpath(*item.relative_directory.parts)
    if run_directory.exists() and any(run_directory.iterdir()):
        raise FileExistsError(f"Run directory is not empty: {run_directory}")
    run_directory.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "label": item.label,
        "mode": item.mode,
        "stage": item.stage,
        "os": item.os_name,
        "size": item.size,
        "network": item.network,
        "backend": item.backend,
        "repetition": item.repetition,
        "run_directory": item.label,
        "status": "failed",
        "error": None,
        "attempts": 0,
        "retried_errors": [],
    }
    started = time.perf_counter()
    for attempt in range(1, arguments.retries + 2):
        record["attempts"] = attempt
        workspace_name = f"r{index:03d}" if attempt == 1 else f"r{index:03d}a{attempt}"
        result, error = run_attempt(item, workspace_name, config, session, run_directory, arguments)
        # The planned identity (os, network, ...) stays authoritative; the worker adds measurements.
        identity = {"os", "network", "stage", "backend", "size"}
        record.update({key: value for key, value in result.items() if key not in identity})
        record["host_os"] = result.get("os", record.get("host_os"))
        record["error"] = error or result.get("error")
        if result.get("status") == "passed" or not result.get("network_error") or attempt > arguments.retries:
            break
        print(f"  Network failure, retrying on a fresh workspace: {record['error']}", flush=True)
        record["retried_errors"].append(record["error"])
        archive_attempt(run_directory, attempt)
        # Back off so a short outage does not consume every attempt within seconds.
        delay = arguments.retry_delay * attempt
        if delay > 0:
            print(f"  Waiting {delay} s before attempt {attempt + 1}.", flush=True)
            time.sleep(delay)
    record["wall_seconds"] = time.perf_counter() - started
    (run_directory / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def load_config(arguments: argparse.Namespace) -> tuple[HarnessConfig, Path | None]:
    """Load the explicit, local, or default configuration."""
    config_file = arguments.config or find_default_config()
    if config_file is None:
        return HarnessConfig(), None
    config_file = config_file.resolve()
    if not config_file.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    return HarnessConfig.from_file(config_file), config_file


def run_passed(run_directory: Path) -> bool:
    """Return whether a run directory holds a passed result."""
    result_file = run_directory / "result.json"
    if not result_file.is_file():
        return False
    try:
        return json.loads(result_file.read_text(encoding="utf-8")).get("status") == "passed"
    except (OSError, json.JSONDecodeError):
        return False


def archive_previous_run(run_directory: Path) -> None:
    """Move a previous (failed) run's files into ``previousN/`` before re-running it."""
    if not run_directory.is_dir() or not any(run_directory.iterdir()):
        return
    number = 1
    while (run_directory / f"previous{number}").exists():
        number += 1
    archive = run_directory / f"previous{number}"
    archive.mkdir()
    for path in list(run_directory.iterdir()):
        if path != archive and not path.name.startswith("previous"):
            path.replace(archive / path.name)


def main(argv: list[str] | None = None) -> int:
    """Select, execute, and report the requested benchmark matrix."""
    arguments = parse_arguments(argv)
    config, config_file = load_config(arguments)
    plan = build_plan(arguments)
    validate(config, plan)
    output_root = resolve_output_directory(arguments.output_dir)

    if arguments.rerun_failed:
        if arguments.output_dir is None or not output_root.is_dir():
            raise ValueError("--rerun-failed requires --output-dir pointing to an existing result directory.")
        plan = [
            item for item in plan if not run_passed(output_root.joinpath(*item.relative_directory.parts))
        ]

    print(f"Selected {len(plan)} benchmark runs:", flush=True)
    for item in plan:
        print(f"  - {item.label}", flush=True)
    print(f"Results: {output_root}", flush=True)
    if arguments.dry_run:
        return 0

    if arguments.rerun_failed:
        for item in plan:
            archive_previous_run(output_root.joinpath(*item.relative_directory.parts))
        session = f"{output_root.name}-rerun"
    else:
        if output_root.exists() and any(output_root.iterdir()):
            raise FileExistsError(f"Output directory is not empty: {output_root}")
        output_root.mkdir(parents=True, exist_ok=True)
        session = output_root.name
    settings = {
        "command": subprocess.list2cmdline([Path(sys.argv[0]).name, *(argv or sys.argv[1:])]),
        "config": str(config_file) if config_file else "defaults",
        "runs_per_case": arguments.run_count,
        "cold_cache": config.isolate_caches and not arguments.warm_cache,
        "host": platform.node(),
        "host_os": platform.platform(),
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    records: list[dict[str, Any]] = []
    try:
        for index, item in enumerate(plan, start=1):
            print(f"\n----- [{index}/{len(plan)}] {item.label} -----", flush=True)
            record = run_one(item, index, config, session, output_root, arguments)
            records.append(record)
            if record["status"] == "passed":
                print(f"Passed: {float(record['stage_seconds']):.1f} s", flush=True)
            else:
                print(f"Failed: {record['error']}", flush=True)
                if arguments.fail_fast:
                    break
    except KeyboardInterrupt:
        print("\nInterrupted; writing a report for the completed runs.", flush=True)
    finally:
        settings["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if arguments.rerun_failed:
            # Rebuild the report from every run in the directory, keeping the original session settings.
            previous = output_root / "results.json"
            if previous.is_file():
                original = json.loads(previous.read_text(encoding="utf-8"))
                settings = {**original.get("settings", {}), "rerun": settings["command"],
                            "rerun_finished": settings["finished"]}
                planned = int(original.get("planned", len(plan)))
            else:
                planned = len(plan)
            report_file = write_reports(output_root, collect_records(output_root), planned, settings)
        else:
            report_file = write_reports(output_root, records, len(plan), settings)
        print(f"\nReport: {report_file}", flush=True)
        if not arguments.keep_workspace:
            shutil.rmtree(config.work_root / session, ignore_errors=True)
            if any(item.os_name != current_os() for item in plan):
                cleanup_wsl_session(config, session)
    return 1 if len(records) < len(plan) or any(record["status"] != "passed" for record in records) else 0


def cleanup_wsl_session(config: HarnessConfig, session: str) -> None:
    """Remove the session's Linux-side workspaces and cached installers."""
    command = [find_wsl()]
    if config.wsl.distribution:
        command.extend(["-d", config.wsl.distribution])
    target = f"{config.wsl.work_root.rstrip('/')}/{session}"
    if target.startswith("~/"):
        script = f'rm -rf -- "$HOME"/{shlex.quote(target[2:])}'
    else:
        script = f"rm -rf -- {shlex.quote(target)}"
    command.extend(["--", "bash", "-lc", script])
    subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=600)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
