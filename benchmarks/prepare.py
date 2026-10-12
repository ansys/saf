"""Prepare source workspaces and backend-specific benchmark payloads."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable


DEFAULT_TARGET_ENVIRONMENT = (
    "sys_platform == 'win32' and os_name == 'nt' and "
    "platform_python_implementation == 'CPython'"
)


@dataclass(frozen=True)
class ModeSpec:
    """Prepared source payload and metadata for one installation mode."""

    name: str
    payload: Path
    metadata: Path


@dataclass(frozen=True)
class BenchmarkConfig:
    """Repository and tool settings needed by the harness."""

    saf_repo: Path
    saf_executable: Path | None
    uv_executable: Path
    modes: dict[str, ModeSpec]
    target_environment: str

    @classmethod
    def from_file(cls, config_file: Path) -> "BenchmarkConfig":
        """Load and resolve a JSON configuration file."""
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        config_directory = config_file.parent.resolve()
        default_repository = config_directory.parent
        if not (
            (default_repository / "examples").is_dir()
            and (default_repository / "packages").is_dir()
        ):
            default_repository /= "saf"
        saf_repo = default_repository.resolve()
        saf_executable = resolve_optional_config_path(raw.get("saf_executable"), config_directory)
        uv_value = raw.get("uv_executable")
        if uv_value is None:
            uv_executable = find_executable("uv")
        else:
            uv_executable = resolve_config_path(uv_value, config_directory, "uv_executable")

        return cls(
            saf_repo=saf_repo,
            saf_executable=saf_executable,
            uv_executable=uv_executable,
            modes={},
            target_environment=str(raw.get("target_environment", DEFAULT_TARGET_ENVIRONMENT)),
        )

    @classmethod
    def defaults(cls, saf_repo: Path) -> "BenchmarkConfig":
        """Create configuration without requiring a local JSON file."""
        return cls(
            saf_repo=saf_repo.resolve(),
            saf_executable=None,
            uv_executable=find_executable("uv"),
            modes={},
            target_environment=DEFAULT_TARGET_ENVIRONMENT,
        )


def resolve_config_path(value: Any, base_directory: Path, field_name: str) -> Path:
    """Resolve a required path from configuration."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"Configuration field '{field_name}' must be a non-empty path.")
    path = Path(value)
    return (path if path.is_absolute() else base_directory / path).resolve()


def resolve_optional_config_path(value: Any, base_directory: Path) -> Path | None:
    """Resolve an optional path from configuration."""
    if value is None:
        return None
    return resolve_config_path(value, base_directory, "optional path")


def find_executable(name: str) -> Path:
    """Resolve an executable from PATH or raise a useful error."""
    executable = shutil.which(name)
    if executable is None:
        raise FileNotFoundError(f"Command executable not found on PATH: {name}")
    return Path(executable).resolve()


def validate_configuration(config: BenchmarkConfig, plan: Iterable[Any]) -> None:
    """Validate repository and tools before preparing the selected matrix."""
    if not config.saf_repo.is_dir():
        raise FileNotFoundError(f"SAF repository not found: {config.saf_repo}")
    examples = config.saf_repo / "examples"
    if not examples.is_dir():
        raise FileNotFoundError(f"SAF Examples solution not found: {examples}")
    if not config.uv_executable.is_file():
        raise FileNotFoundError(f"UV executable not found: {config.uv_executable}")
    if config.saf_executable is not None and not config.saf_executable.is_file():
        raise FileNotFoundError(f"SAF executable not found: {config.saf_executable}")

    if not plan:
        raise ValueError("The benchmark plan is empty.")


def validate_prepared_configuration(config: BenchmarkConfig, plan: Iterable[Any]) -> None:
    """Validate only the prepared payloads selected by the plan."""
    selected = {(item.mode, item.backend, item.variant) for item in plan}
    for mode, backend, _variant in selected:
        mode_spec = config.modes[mode]
        if not mode_spec.payload.is_dir():
            raise FileNotFoundError(f"Payload directory not found: {mode_spec.payload}")
        if not mode_spec.metadata.is_file():
            raise FileNotFoundError(f"Metadata file not found: {mode_spec.metadata}")
        if backend == "uv" and not config.uv_executable.is_file():
            raise FileNotFoundError(f"UV executable not found: {config.uv_executable}")


def command_text(command: list[str | Path]) -> str:
    """Return a readable command line for logs and reports."""
    return subprocess.list2cmdline([str(argument) for argument in command])


def run_preparation_command(
    command: list[str | Path],
    cwd: Path,
    output: list[str],
    environment: dict[str, str] | None = None,
    attempts: int = 1,
) -> None:
    """Run one un-timed preparation command and capture its output."""
    normalized = [str(argument) for argument in command]
    if attempts < 1:
        raise ValueError("Preparation command attempts must be at least 1.")
    last_output = ""
    for attempt in range(1, attempts + 1):
        output.append(f"$ {command_text(normalized)}")
        completed = subprocess.run(
            normalized,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env=environment,
        )
        last_output = completed.stdout
        if completed.stdout:
            output.append(completed.stdout)
        if completed.returncode == 0:
            return
        if attempt < attempts:
            output.append(f"Preparation attempt {attempt}/{attempts} failed; retrying.")
    raise RuntimeError(
        f"Preparation command failed after {attempts} attempt(s) with exit code "
        f"{completed.returncode}: {command_text(normalized)}\n{last_output[-4000:]}",
    )


def sandbox_environment(root: Path) -> dict[str, str]:
    """Keep subprocess profiles, temporary files, and caches under one root."""
    environment = os.environ.copy()
    sandbox_root = root / "environment"
    locations = {
        "APPDATA": sandbox_root / "appdata",
        "LOCALAPPDATA": sandbox_root / "localappdata",
        "TEMP": sandbox_root / "temp",
        "TMP": sandbox_root / "temp",
        "TMPDIR": sandbox_root / "temp",
        "HOME": sandbox_root / "home",
        "USERPROFILE": sandbox_root / "profile",
        "PIP_CACHE_DIR": sandbox_root / "cache" / "pip",
        "POETRY_CACHE_DIR": sandbox_root / "cache" / "poetry",
        "UV_CACHE_DIR": sandbox_root / "cache" / "uv",
        "XDG_CACHE_HOME": sandbox_root / "cache" / "xdg",
    }
    for variable, location in locations.items():
        location.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(location)
    return environment


def preparation_environment(preparation_root: Path) -> dict[str, str]:
    """Keep SAF CLI state and package caches inside the benchmark directory."""
    return sandbox_environment(preparation_root)


def source_copy_ignore(_directory: str, names: list[str]) -> set[str]:
    """Exclude generated and machine-specific files from a source copy."""
    excluded = {
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
    return {name for name in names if name in excluded}


def copy_solution_workspace(saf_repo: Path, workspace: Path) -> Path:
    """Copy Examples and the path dependency needed by its lock file."""
    examples_source = saf_repo / "examples"
    examples_target = workspace / "examples"
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(examples_source, examples_target, ignore=source_copy_ignore)
    project_file = examples_target / "pyproject.toml"
    project_text = project_file.read_text(encoding="utf-8")
    if "[tool.poetry.group.doc]" not in project_text:
        project_file.write_text(
            project_text.rstrip()
            + "\n\n[tool.poetry.group.doc]\noptional = true\n",
            encoding="utf-8",
        )

    cli_source = saf_repo / "packages" / "saf-cli"
    if not cli_source.is_dir():
        raise FileNotFoundError(f"SAF CLI package not found: {cli_source}")
    shutil.copytree(
        cli_source,
        workspace / "packages" / "saf-cli",
        ignore=source_copy_ignore,
    )
    return examples_target


def platform_is_windows() -> bool:
    """Return whether the benchmark is running on Windows."""
    return sys.platform.startswith("win")


def get_venv_python_path(venv_directory: Path) -> Path:
    """Return the interpreter path for a virtual environment."""
    return (
        venv_directory / "Scripts" / "python.exe"
        if platform_is_windows()
        else venv_directory / "bin" / "python"
    )


def resolve_saf_executable(
    config: BenchmarkConfig,
    preparation_root: Path,
    environment: dict[str, str],
    output: list[str],
) -> Path:
    """Find the repository CLI or build a private CLI environment locally."""
    candidates: list[Path] = []
    if config.saf_executable is not None:
        candidates.append(config.saf_executable)
    if platform_is_windows():
        candidates.extend(
            [
                config.saf_repo / "examples" / ".venv" / "Scripts" / "saf.exe",
                config.saf_repo / ".venv" / "Scripts" / "saf.exe",
            ],
        )
    else:
        candidates.extend(
            [
                config.saf_repo / "examples" / ".venv" / "bin" / "saf",
                config.saf_repo / ".venv" / "bin" / "saf",
            ],
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    cli_environment = preparation_root / "tools" / "saf-cli-venv"
    cli_environment.parent.mkdir(parents=True, exist_ok=True)
    cli_python = get_venv_python_path(cli_environment)
    run_preparation_command(
        [config.uv_executable, "venv", cli_environment],
        cwd=preparation_root,
        output=output,
        environment=environment,
    )
    install_sources = [config.saf_repo / "packages" / "saf-cli"]
    templates_source = config.saf_repo / "packages" / "saf-templates"
    if templates_source.is_dir():
        install_sources.append(templates_source)
    run_preparation_command(
        [
            config.uv_executable,
            "pip",
            "install",
            "--python",
            cli_python,
            *install_sources,
        ],
        cwd=preparation_root,
        output=output,
        environment=environment,
    )
    saf_executable = (
        cli_environment / "Scripts" / "saf.exe"
        if platform_is_windows()
        else cli_environment / "bin" / "saf"
    )
    if not saf_executable.is_file():
        raise RuntimeError(f"SAF CLI installation did not create {saf_executable}")
    return saf_executable


def remove_directory_with_retries(directory: Path, attempts: int = 20) -> None:
    """Remove a generated directory while allowing transient Windows locks to clear."""
    for attempt in range(1, attempts + 1):
        try:
            shutil.rmtree(directory)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(0.5)


def has_embedded_python(directory: Path) -> bool:
    """Return whether a copied payload contains an embedded Python interpreter."""
    candidates = (
        directory / "python.exe",
        directory / "tools" / "python.exe",
        directory / "bin" / "python3",
    )
    return any(candidate.is_file() for candidate in candidates)


def normalize_build_payload(build_output: Path, destination: Path) -> str | None:
    """Copy a SAF build output into the payload shape used by deploy.py."""
    if not build_output.is_dir():
        raise FileNotFoundError(f"SAF build did not create {build_output}")
    shutil.copytree(build_output, destination)
    bundled_python = destination / "third_party" / "python"
    payload_python = destination / "python"
    if bundled_python.is_dir():
        if payload_python.exists():
            if payload_python.is_dir():
                remove_directory_with_retries(payload_python)
            else:
                payload_python.unlink()
        try:
            shutil.move(str(bundled_python), str(payload_python))
            return None
        except PermissionError:
            # shutil.move may have completed the copy and only failed while
            # removing the source directory because Windows still held a file.
            if not payload_python.is_dir() or not has_embedded_python(payload_python):
                raise
            try:
                remove_directory_with_retries(bundled_python)
            except PermissionError:
                return (
                    f"Retained the locked source directory {bundled_python} after "
                    "copying the embedded Python to the payload."
                )
            return None
    return None


def copy_uv_to_preparation(config: BenchmarkConfig, preparation_root: Path) -> Path:
    """Copy UV into the benchmark workspace so later runs use a local tool."""
    local_name = "uv.exe" if platform_is_windows() else "uv"
    local_uv = preparation_root / "tools" / local_name
    local_uv.parent.mkdir(parents=True, exist_ok=True)
    if config.uv_executable.resolve() != local_uv.resolve():
        shutil.copy2(config.uv_executable, local_uv)
    return local_uv


def prepare_source_payload(
    mode: str,
    config: BenchmarkConfig,
    preparation_root: Path,
    saf_executable: Path,
    environment: dict[str, str],
) -> tuple[ModeSpec, dict[str, Any]]:
    """Build one online or offline payload from a fresh Examples copy."""
    started = time.perf_counter()
    mode_root = preparation_root / "workspaces" / mode
    examples_directory = copy_solution_workspace(config.saf_repo, mode_root)
    log_lines: list[str] = [
        f"SAF repository: {config.saf_repo}",
        f"Examples workspace: {examples_directory}",
    ]
    try:
        run_preparation_command(
            [saf_executable, "install", examples_directory, "-F"],
            cwd=examples_directory,
            output=log_lines,
            environment=environment,
            attempts=2,
        )
        build_command: list[str | Path] = [
            saf_executable,
            "build",
            examples_directory,
            "--no-executable",
        ]
        if mode == "offline":
            build_command.append("--offline-package")
        run_preparation_command(
            build_command,
            cwd=examples_directory,
            output=log_lines,
            environment=environment,
        )

        payload = preparation_root / "payloads" / mode
        normalization_note = normalize_build_payload(examples_directory / "dist" / "solution", payload)
        if normalization_note is not None:
            log_lines.append(f"Payload normalization note: {normalization_note}")
        metadata = payload / "solution-metadata.json"
        if not metadata.is_file():
            raise RuntimeError(f"SAF build did not create {metadata}")
        preparation_log = preparation_root / f"{mode}.log"
        preparation_log.write_text("\n\n".join(log_lines) + "\n", encoding="utf-8")
        return (
            ModeSpec(name=mode, payload=payload, metadata=metadata),
            {
                "mode": mode,
                "status": "passed",
                "seconds": time.perf_counter() - started,
                "saf_repository": str(config.saf_repo),
                "workspace": str(examples_directory),
                "payload": str(payload),
                "log": str(preparation_log),
                "error": None,
            },
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        preparation_log = preparation_root / f"{mode}.log"
        log_lines.append(f"Preparation failed: {error}")
        preparation_log.write_text("\n\n".join(log_lines) + "\n", encoding="utf-8")
        raise


def prepare_benchmark_assets(
    config: BenchmarkConfig,
    modes: Iterable[str],
    preparation_root: Path,
) -> tuple[BenchmarkConfig, list[dict[str, Any]]]:
    """Create all selected source payloads under the benchmark output."""
    preparation_root.mkdir(parents=True, exist_ok=True)
    environment = preparation_environment(preparation_root)
    output: list[str] = []
    local_uv = copy_uv_to_preparation(config, preparation_root)
    config = replace(config, uv_executable=local_uv)
    saf_executable = resolve_saf_executable(config, preparation_root, environment, output)
    if output:
        (preparation_root / "saf-cli-setup.log").write_text("\n\n".join(output) + "\n", encoding="utf-8")

    prepared_modes: dict[str, ModeSpec] = {}
    preparation_records: list[dict[str, Any]] = []
    for mode in modes:
        mode_spec, record = prepare_source_payload(
            mode,
            config,
            preparation_root,
            saf_executable,
            environment,
        )
        prepared_modes[mode] = mode_spec
        preparation_records.append(record)
    return replace(config, saf_executable=saf_executable, modes=prepared_modes), preparation_records
