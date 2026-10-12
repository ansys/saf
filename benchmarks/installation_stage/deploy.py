"""Install and exercise one prepared SAF benchmark payload.

This module intentionally uses only the Python standard library.  The
benchmark orchestrator calls it in a fresh process so that the timed section
matches the installer phase while preparation and report generation stay
outside that measurement.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import tomllib
from typing import Any


VIRTUAL_ENVIRONMENT_NAME = ".venv"
VERSION_FILE = "version.txt"
PORTAL_PACKAGE_NAMES = {"ansys-saf-desktop-portal", "ansys-saf-portal"}


def command_text(command: list[str | Path]) -> str:
    """Return a readable command line for logs."""
    return subprocess.list2cmdline([str(argument) for argument in command])


def remove_path(path: Path) -> None:
    """Remove a disposable file or directory when it exists."""
    if not path.exists() and not path.is_symlink():
        return
    for attempt in range(1, 21):
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            return
        except PermissionError:
            if attempt == 20:
                raise
            time.sleep(0.5)


def run_process(
    command: list[str | Path],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command, print its output, and raise with useful context on failure."""
    normalized_command = [str(argument) for argument in command]
    print(f"Executing: {command_text(normalized_command)}", flush=True)
    completed = subprocess.run(
        normalized_command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.stdout:
        print(
            completed.stdout,
            end="" if completed.stdout.endswith("\n") else "\n",
            flush=True,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: "
            f"{command_text(normalized_command)}\n{completed.stdout[-4000:]}",
        )
    return completed


def get_embedded_python(python_directory: Path) -> Path:
    """Find the Python interpreter bundled in an installer payload."""
    if platform.system() == "Windows":
        candidates = (python_directory / "python.exe", python_directory / "tools" / "python.exe")
    elif platform.system() == "Linux":
        candidates = (python_directory / "bin" / "python3",)
    else:
        raise RuntimeError(f"Unsupported operating system: {platform.system()}")

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(f"Could not find the embedded Python interpreter in {python_directory}.")


def get_venv_python(venv_directory: Path) -> Path:
    """Find the Python interpreter in a solution virtual environment."""
    if platform.system() == "Windows":
        candidate = venv_directory / "Scripts" / "python.exe"
    else:
        candidate = venv_directory / "bin" / "python"
    if not candidate.is_file():
        raise RuntimeError(f"Unable to find a Python interpreter in {venv_directory}.")
    return candidate


def get_payload_uv(solution_directory: Path) -> Path:
    """Find the UV executable bundled into a prepared solution payload."""
    tool_name = "uv.exe" if platform.system() == "Windows" else "uv"
    candidate = solution_directory / "tools" / tool_name
    if not candidate.is_file():
        raise RuntimeError(f"Unable to find UV executable in {solution_directory / 'tools'}.")
    return candidate


def get_solution_directory(payload: Path, metadata: dict[str, Any]) -> Path:
    """Return the solution project directory inside a prepared payload."""
    solution_directory = payload / "definitions" / str(metadata["solution-module-name"])
    if not solution_directory.is_dir():
        raise RuntimeError(f"Missing solution directory: {solution_directory}")
    return solution_directory


def get_solution_wheel(solution_directory: Path, package_name: str) -> Path:
    """Return the one solution wheel retained at the project root."""
    normalized_name = package_name.replace("-", "_")
    wheels = list(solution_directory.glob(f"{normalized_name}-*.whl"))
    if not wheels:
        raise RuntimeError(f"No solution wheel matching {package_name} in {solution_directory}.")
    if len(wheels) != 1:
        raise RuntimeError(f"Expected one solution wheel matching {package_name}, found {len(wheels)}.")
    return wheels[0]


def validate_payload(
    payload: Path,
    metadata: dict[str, Any],
    backend: str,
    source_variant: str,
) -> Path:
    """Validate the files needed by the selected deployment backend."""
    if not payload.is_dir():
        raise FileNotFoundError(f"Prepared payload not found: {payload}")

    version_file = payload / VERSION_FILE
    if not version_file.is_file():
        raise RuntimeError(f"Missing version file: {version_file}")

    solution_directory = get_solution_directory(payload, metadata)
    project_file = solution_directory / "pyproject.toml"
    if not project_file.is_file():
        raise RuntimeError(f"Missing project file: {project_file}")

    lock_file_name = "poetry.lock" if backend == "poetry" else "uv.lock"
    lock_file = solution_directory / lock_file_name
    if not lock_file.is_file():
        raise RuntimeError(f"Missing {backend} lock file: {lock_file}")

    get_solution_wheel(solution_directory, str(metadata["solution-package-name"]))

    tools_directory = solution_directory / "tools"
    if not tools_directory.is_dir():
        raise RuntimeError(f"Missing installer tools directory: {tools_directory}")
    if backend == "poetry" and not (tools_directory / "poetry_requirements.txt").is_file():
        raise RuntimeError(f"Missing Poetry requirements file: {tools_directory / 'poetry_requirements.txt'}")
    if backend == "uv":
        get_payload_uv(solution_directory)

    if source_variant in {"wheelhouse", "server"}:
        wheelhouse = solution_directory / "wheelhouse"
        if not wheelhouse.is_dir() or not any(wheelhouse.glob("*.whl")):
            raise RuntimeError(f"Missing or empty wheelhouse: {wheelhouse}")
    if source_variant == "server":
        simple_index = solution_directory / "simple" / "index.html"
        if not simple_index.is_file():
            raise RuntimeError(f"Missing Poetry package server index: {simple_index}")

    return solution_directory


def has_portal_dependency(lock_file: Path) -> bool:
    """Check whether a Poetry or UV lock contains a SAF Portal package."""
    lock_data = tomllib.loads(lock_file.read_text(encoding="utf-8"))
    return any(package.get("name") in PORTAL_PACKAGE_NAMES for package in lock_data.get("package", []))


def install_tool(
    tool: str,
    tools_directory: Path,
    tools_python: Path,
    pip_cache: Path,
    environment: dict[str, str],
) -> None:
    """Install one tool required by the Poetry deployment."""
    requirements = tools_directory / f"{tool}_requirements.txt"
    if not requirements.is_file():
        raise RuntimeError(f"Missing tool requirements file: {requirements}")

    tool_environment = environment.copy()
    tool_environment["PIP_CACHE_DIR"] = str(pip_cache)
    run_process(
        [
            tools_python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            requirements,
            *([] if tool != "pip" else ["--force-reinstall"]),
        ],
        cwd=tools_directory,
        environment=tool_environment,
    )


def install_poetry(
    payload: Path,
    solution_directory: Path,
    source_variant: str,
) -> bool:
    """Install dependencies with Poetry and return whether Portal is present."""
    embedded_python = get_embedded_python(payload / "python")
    tools_directory = solution_directory / "tools"
    temporary_tools_environment = payload / "install_tools_venv"
    pip_cache = payload / "pip_cache"
    poetry_cache = payload / "poetry_cache"

    remove_path(solution_directory / VIRTUAL_ENVIRONMENT_NAME)
    remove_path(temporary_tools_environment)
    run_process([embedded_python, "-m", "venv", temporary_tools_environment], cwd=payload)
    tools_python = get_venv_python(temporary_tools_environment)

    base_environment = os.environ.copy()
    base_environment["PATH"] = str(embedded_python.resolve().parent) + os.pathsep + base_environment.get("PATH", "")
    if source_variant in {"wheelhouse", "server"}:
        base_environment["PIP_NO_INDEX"] = "1"
    install_tool("pip", tools_directory, tools_python, pip_cache, base_environment)
    install_tool("poetry", tools_directory, tools_python, pip_cache, base_environment)

    poetry_environment = base_environment.copy()
    poetry_command = [tools_python, "-m", "poetry"]
    for arguments in (
        ["config", "--local", "virtualenvs.create", "true"],
        ["config", "--local", "virtualenvs.in-project", "true"],
        ["config", "--local", "cache-dir", poetry_cache],
        ["env", "use", embedded_python.resolve()],
    ):
        run_process([*poetry_command, *arguments], cwd=solution_directory, environment=poetry_environment)

    install_command = [*poetry_command, "install", "--no-root"]
    attempts = 5
    last_output = ""
    for attempt in range(1, attempts + 1):
        completed = subprocess.run(
            [str(argument) for argument in install_command],
            cwd=solution_directory,
            env=poetry_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        last_output = completed.stdout
        if completed.stdout:
            print(
                completed.stdout,
                end="" if completed.stdout.endswith("\n") else "\n",
                flush=True,
            )
        if completed.returncode == 0:
            break
    else:
        raise RuntimeError(f"Poetry installation failed after {attempts} attempts.\n{last_output[-4000:]}")
    portal_present = has_portal_dependency(solution_directory / "poetry.lock")
    for path in (
        temporary_tools_environment,
        pip_cache,
        poetry_cache,
        solution_directory / "poetry.lock",
        solution_directory / "pyproject.toml",
        solution_directory / "poetry.toml",
        solution_directory / "requirements.txt",
        solution_directory / ".poetry",
        tools_directory,
    ):
        remove_path(path)
    for wheel in solution_directory.glob("*.whl"):
        remove_path(wheel)
    return portal_present


def install_uv(
    payload: Path,
    solution_directory: Path,
    metadata: dict[str, Any],
    use_wheelhouse: bool,
) -> bool:
    """Install dependencies with UV and return whether Portal is present."""
    embedded_python = get_embedded_python(payload / "python")
    uv_executable = get_payload_uv(solution_directory)
    uv_cache = payload / "uv_cache"
    environment = os.environ.copy()
    environment["UV_CACHE_DIR"] = str(uv_cache)
    command: list[str | Path] = [
        uv_executable,
        "sync",
        "--locked",
        "--no-install-project",
        "--python",
        embedded_python.resolve(),
    ]
    if str(metadata.get("offline-package", "False")).lower() == "true":
        command.append("--offline")
        if use_wheelhouse:
            command.extend(["--no-index", "--find-links", solution_directory / "wheelhouse"])

    run_process(command, cwd=solution_directory, environment=environment)
    portal_present = has_portal_dependency(solution_directory / "uv.lock")

    for wheel in solution_directory.glob("*.whl"):
        remove_path(wheel)
    if use_wheelhouse:
        remove_path(solution_directory / "wheelhouse")
    for path in (
        uv_cache,
        solution_directory / "pyproject.toml",
        solution_directory / "uv.lock",
        solution_directory / "tools",
    ):
        remove_path(path)
    return portal_present


def compute_solution_command(
    solution_directory: Path,
    metadata: dict[str, Any],
    portal_present: bool,
) -> tuple[Path, list[str]]:
    """Build the application command used for preload."""
    if platform.system() == "Windows":
        python_directory = solution_directory / VIRTUAL_ENVIRONMENT_NAME / "Scripts"
        python_executable = (
            python_directory / "python.exe"
            if str(metadata["display-console-window"]) == "True"
            else python_directory / "pythonw.exe"
        )
    else:
        python_executable = solution_directory / VIRTUAL_ENVIRONMENT_NAME / "bin" / "python"

    if not python_executable.is_file():
        raise RuntimeError(f"Unable to find the solution Python interpreter at {python_executable}.")

    environment_file = solution_directory / ".env"
    if not environment_file.is_file():
        raise RuntimeError(f"Unable to find the solution environment file at {environment_file}.")

    if str(metadata["use-glow"]) == "True":
        arguments = [
            "-m",
            str(metadata["glow-entry-point-module"]),
            "--solution-main-module-name",
            str(metadata["solution-main-module"]),
        ]
        if portal_present:
            arguments.append("--portal")
        arguments.extend(["--env-file", f'"{environment_file.as_posix()}"'])
    else:
        arguments = ["-m", str(metadata["solution-entry-point"])]
    return python_executable, arguments


def escape_powershell_string(value: str) -> str:
    """Escape a value enclosed in a PowerShell single-quoted string."""
    return value.replace("'", "''")


def create_shortcut(
    shortcut_root: Path,
    python_executable: Path,
    icon_path: Path,
    arguments: list[str],
    metadata: dict[str, Any],
) -> None:
    """Create the benchmark shortcut in an isolated writable directory."""
    shortcut_root.mkdir(parents=True, exist_ok=True)
    display_name = str(metadata["solution-display-name"])
    arguments_string = " ".join(arguments)
    if platform.system() == "Windows":
        shortcut_path = shortcut_root / f"{display_name}.lnk"
        shell_command = "$WshShell = New-Object -ComObject WScript.Shell; "
        shell_command += f"$Shortcut = $WshShell.CreateShortcut('{escape_powershell_string(str(shortcut_path))}'); "
        shell_command += f"$Shortcut.TargetPath = '{escape_powershell_string(str(python_executable))}'; "
        shell_command += f"$Shortcut.Arguments = '{escape_powershell_string(arguments_string)}'; "
        shell_command += (
            f"$Shortcut.Description = '{escape_powershell_string(display_name)} Application'; "
        )
        shell_command += f"$Shortcut.IconLocation = '{escape_powershell_string(str(icon_path))}'; "
        shell_command += "$Shortcut.Save()"
        powershell = shutil.which("powershell.exe") or "powershell.exe"
        run_process([powershell, "-NoProfile", "-Command", shell_command], cwd=shortcut_root)
        return

    shortcut_path = shortcut_root / f"{display_name}.desktop"
    terminal = "true" if str(metadata["display-console-window"]) == "True" else "false"
    shortcut_path.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                f"Name={display_name}",
                f'Exec="{python_executable}" {arguments_string}',
                "Type=Application",
                f"Terminal={terminal}",
                "Categories=Development;",
                f"Icon={icon_path}",
            ],
        )
        + "\n",
        encoding="utf-8",
    )
    shortcut_path.chmod(0o755)


def run_benchmark(
    payload: Path,
    metadata_file: Path,
    backend: str,
    shortcut_root: Path,
    source_variant: str,
) -> dict[str, float]:
    """Run installation, preload, and shortcut creation for one payload."""
    started = time.perf_counter()
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    solution_directory = validate_payload(payload, metadata, backend, source_variant)
    backend_started = time.perf_counter()
    print(f"Installing dependencies with {backend}.", flush=True)
    if backend == "poetry":
        portal_present = install_poetry(payload, solution_directory, source_variant)
    else:
        portal_present = install_uv(payload, solution_directory, metadata, source_variant == "wheelhouse")
    backend_seconds = time.perf_counter() - backend_started

    solution_python, arguments = compute_solution_command(solution_directory, metadata, portal_present)
    preload_python = solution_python
    if preload_python.name.lower() == "pythonw.exe":
        preload_python = preload_python.with_name("python.exe")
    preload_started = time.perf_counter()
    print("Preloading the application.", flush=True)
    run_process([preload_python, *arguments, "--pre-load"], cwd=solution_directory)
    preload_seconds = time.perf_counter() - preload_started

    icon_suffix = ".ico" if platform.system() == "Windows" else ".png"
    shortcut_started = time.perf_counter()
    print("Creating the shortcut.", flush=True)
    create_shortcut(
        shortcut_root,
        solution_python,
        payload / "assets" / f"shortcut{icon_suffix}",
        arguments,
        metadata,
    )
    shortcut_seconds = time.perf_counter() - shortcut_started
    total_seconds = time.perf_counter() - started
    return {
        "backend_seconds": backend_seconds,
        "preload_seconds": preload_seconds,
        "shortcut_seconds": shortcut_seconds,
        "total_seconds": total_seconds,
    }


def parse_arguments() -> argparse.Namespace:
    """Parse deployment-runner arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("poetry", "uv"), required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--metadata-file", type=Path, required=True)
    parser.add_argument("--shortcut-root", type=Path, required=True)
    parser.add_argument("--uv-wheelhouse", action="store_true")
    poetry_source = parser.add_mutually_exclusive_group()
    poetry_source.add_argument("--poetry-wheelhouse", action="store_true")
    poetry_source.add_argument("--poetry-server", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run one benchmark payload and emit a machine-readable timing marker."""
    arguments = parse_arguments()
    if arguments.backend != "uv" and arguments.uv_wheelhouse:
        raise ValueError("--uv-wheelhouse is only valid for the UV backend.")
    if arguments.backend != "poetry" and (arguments.poetry_wheelhouse or arguments.poetry_server):
        raise ValueError("Poetry source variants are only valid for the Poetry backend.")
    source_variant = "standard"
    if arguments.uv_wheelhouse or arguments.poetry_wheelhouse:
        source_variant = "wheelhouse"
    elif arguments.poetry_server:
        source_variant = "server"
    metadata = json.loads(arguments.metadata_file.read_text(encoding="utf-8"))
    if source_variant != "standard" and str(metadata.get("offline-package", "False")).lower() != "true":
        raise ValueError("Offline source variants require an offline-package payload.")
    timings = run_benchmark(
        arguments.payload.resolve(),
        arguments.metadata_file.resolve(),
        arguments.backend,
        arguments.shortcut_root.resolve(),
        source_variant,
    )
    print(f"BENCHMARK_RESULT={json.dumps(timings, sort_keys=True)}")


if __name__ == "__main__":
    main()
