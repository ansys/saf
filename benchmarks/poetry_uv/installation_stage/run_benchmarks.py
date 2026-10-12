"""Run repeated Poetry and UV SAF installation benchmarks.

The harness prepares fresh payloads from the unmodified SAF repository before
the timed deployment starts. Preparation is reported separately and is not
included in the installer timing.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Thread
import time
from typing import Any

from prepare import (
    BenchmarkConfig,
    command_text,
    find_saf_repository,
    prepare_benchmark_assets,
    sandbox_environment,
    validate_configuration,
    validate_prepared_configuration,
)
from report import write_reports
from uv_prepare import prepare_poetry_payload, prepare_uv_payload


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
DEPLOY_SCRIPT = SCRIPT_DIRECTORY / "deploy.py"
DEFAULT_CONFIG_NAMES = ("config.local.json", "config.json")
DEPLOYMENT_PROGRESS_MESSAGES = {
    "Installing dependencies with poetry.",
    "Installing dependencies with uv.",
    "Preloading the application.",
    "Creating the shortcut.",
}


def start_package_server(root: Path) -> tuple[ThreadingHTTPServer, Thread, str]:
    """Start a local static package server for a Poetry benchmark."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/simple/"


@dataclass(frozen=True)
class PlannedRun:
    """One backend/mode/repetition combination."""

    mode: str
    backend: str
    variant: str
    repetition: int

    @property
    def label(self) -> str:
        """Return a stable human-readable run label."""
        return f"{self.mode}-{self.backend}-{self.variant}-run{self.repetition}"


def default_saf_repository() -> Path:
    """Return the repository containing this benchmarks directory."""
    return find_saf_repository(SCRIPT_DIRECTORY)


def find_default_config() -> Path | None:
    """Find a local configuration beside this script."""
    for name in DEFAULT_CONFIG_NAMES:
        candidate = SCRIPT_DIRECTORY / name
        if candidate.is_file():
            return candidate
    return None


def positive_integer(value: str) -> int:
    """Parse a positive repetition count."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("run count must be at least 1")
    return parsed


def parse_arguments() -> argparse.Namespace:
    """Parse benchmark selection and output options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Optional JSON configuration file. Defaults to the repository containing benchmarks.",
    )
    parser.add_argument("--online", action="store_true", help="Run online cases.")
    parser.add_argument("--offline", action="store_true", help="Run offline-package cases.")
    parser.add_argument(
        "--run",
        dest="run_count",
        type=positive_integer,
        default=3,
        metavar="N",
        help="Number of repetitions for every selected case (default: 3).",
    )
    parser.add_argument(
        "--uv-wheelhouse",
        action="store_true",
        help="Use the wheelhouse UV variant for offline UV cases instead of individual local paths.",
    )
    poetry_source = parser.add_mutually_exclusive_group()
    poetry_source.add_argument(
        "--poetry-wheelhouse",
        action="store_true",
        help="Use local wheel paths for offline Poetry cases.",
    )
    poetry_source.add_argument(
        "--poetry-server",
        action="store_true",
        help="Use a local package server for offline Poetry cases.",
    )
    parser.add_argument("--poetry-only", action="store_true", help="Run Poetry cases only.")
    parser.add_argument("--uv-only", action="store_true", help="Run UV cases only.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected cases without running them.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory for run payloads and reports. Defaults to "
            "benchmarks/poetry_uv/installation_stage/results/<timestamp>."
        ),
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed case.",
    )
    return parser.parse_args()


def selected_modes(arguments: argparse.Namespace) -> list[str]:
    """Resolve mode flags, defaulting to both modes."""
    offline_variant_requested = (
        arguments.uv_wheelhouse
        or arguments.poetry_wheelhouse
        or arguments.poetry_server
    )
    if arguments.online and arguments.offline:
        return ["online", "offline"]
    if arguments.online:
        if offline_variant_requested:
            raise ValueError("Offline source variants require an offline case.")
        return ["online"]
    if arguments.offline:
        return ["offline"]
    return ["online", "offline"]


def selected_backends(arguments: argparse.Namespace) -> list[str]:
    """Resolve backend flags, defaulting to both backends."""
    if arguments.poetry_only and arguments.uv_only:
        raise ValueError("--poetry-only and --uv-only cannot be combined.")
    if arguments.poetry_only:
        return ["poetry"]
    if arguments.uv_only:
        return ["uv"]
    return ["poetry", "uv"]


def build_plan(arguments: argparse.Namespace) -> list[PlannedRun]:
    """Build the ordered matrix of runs requested by the user."""
    modes = selected_modes(arguments)
    backends = selected_backends(arguments)
    if (arguments.poetry_wheelhouse or arguments.poetry_server) and "poetry" not in backends:
        raise ValueError("Poetry source variants require Poetry cases.")
    plan: list[PlannedRun] = []
    for mode in modes:
        for backend in backends:
            variant = "standard"
            if backend == "uv":
                variant = "wheelhouse" if mode == "offline" and arguments.uv_wheelhouse else "direct-path"
            elif mode == "offline":
                if arguments.poetry_wheelhouse:
                    variant = "wheelhouse"
                elif arguments.poetry_server:
                    variant = "server"
            for repetition in range(1, arguments.run_count + 1):
                plan.append(PlannedRun(mode, backend, variant, repetition))
    return plan


def copy_payload(source: Path, destination: Path) -> None:
    """Copy one prepared payload into an isolated run directory."""
    if destination.exists():
        raise FileExistsError(f"Run directory already exists: {destination}")
    shutil.copytree(source, destination)


def extract_result(output: str) -> dict[str, float]:
    """Read the deployment runner's timing marker."""
    for line in reversed(output.splitlines()):
        if line.startswith("BENCHMARK_RESULT="):
            result = json.loads(line.removeprefix("BENCHMARK_RESULT="))
            if not isinstance(result, dict):
                break
            return {key: float(value) for key, value in result.items()}
    raise RuntimeError("Deployment completed without a BENCHMARK_RESULT marker.")


def run_one(
    item: PlannedRun,
    config: BenchmarkConfig,
    output_root: Path,
) -> dict[str, Any]:
    """Prepare and run one benchmark case."""
    mode_spec = config.modes[item.mode]
    source_payload = mode_spec.payload

    run_directory = output_root / item.label
    preparation_log = run_directory / "preparation.log"
    runner_log = run_directory / "runner.log"
    record: dict[str, Any] = {
        "label": item.label,
        "mode": item.mode,
        "backend": item.backend,
        "variant": item.variant,
        "repetition": item.repetition,
        "status": "failed",
        "run_directory": str(run_directory),
        "preparation_seconds": None,
        "runner_seconds": None,
        "backend_seconds": None,
        "preload_seconds": None,
        "shortcut_seconds": None,
        "total_seconds": None,
        "error": None,
    }
    preparation_started = time.perf_counter()
    local_server: ThreadingHTTPServer | None = None
    server_thread: Thread | None = None
    try:
        print("Preparing payload.", flush=True)
        copy_payload(source_payload, run_directory)
        run_metadata = run_directory / "solution-metadata.json"
        if item.backend == "uv":
            prepare_uv_payload(
                run_directory,
                run_metadata,
                item.mode,
                item.variant,
                config,
                preparation_log,
            )
        elif item.variant in {"wheelhouse", "server"}:
            source_url = None
            if item.variant == "server":
                metadata = json.loads(run_metadata.read_text(encoding="utf-8"))
                solution_directory = run_directory / "definitions" / str(
                    metadata["solution-module-name"],
                )
                local_server, server_thread, source_url = start_package_server(solution_directory)
            preparation_note = prepare_poetry_payload(
                run_directory,
                run_metadata,
                item.variant,
                source_url,
            )
            preparation_log.write_text(preparation_note + "\n", encoding="utf-8")
        else:
            preparation_log.write_text("Poetry payload copied without UV preparation.\n", encoding="utf-8")
        record["preparation_seconds"] = time.perf_counter() - preparation_started
        print("Running deployment.", flush=True)

        shortcut_root = run_directory / "shortcut"
        command: list[str | Path] = [
            sys.executable,
            "-u",
            DEPLOY_SCRIPT,
            "--backend",
            item.backend,
            "--payload",
            run_directory,
            "--metadata-file",
            run_metadata,
            "--shortcut-root",
            shortcut_root,
        ]
        if item.backend == "uv" and item.variant == "wheelhouse":
            command.append("--uv-wheelhouse")
        elif item.backend == "poetry" and item.variant == "wheelhouse":
            command.append("--poetry-wheelhouse")
        elif item.backend == "poetry" and item.variant == "server":
            command.append("--poetry-server")
        runner_environment = sandbox_environment(run_directory)
        if item.variant == "server":
            runner_environment.update(
                {
                    "NO_PROXY": "127.0.0.1,localhost",
                    "no_proxy": "127.0.0.1,localhost",
                },
            )
        runner_started = time.perf_counter()
        process = subprocess.Popen(
            [str(argument) for argument in command],
            cwd=SCRIPT_DIRECTORY,
            env=runner_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if process.stdout is None:
            raise RuntimeError("Deployment process did not provide a standard output stream.")
        output_lines: list[str] = []
        for line in process.stdout:
            output_lines.append(line)
            if line.strip() in DEPLOYMENT_PROGRESS_MESSAGES:
                print(line, end="", flush=True)
        completed_output = "".join(output_lines)
        returncode = process.wait()
        record["runner_seconds"] = time.perf_counter() - runner_started
        runner_log.write_text(
            f"$ {command_text(command)}\n\n{completed_output}",
            encoding="utf-8",
        )
        if returncode != 0:
            raise RuntimeError(
                f"Deployment failed with exit code {returncode}. "
                f"See {runner_log} for details.",
            )
        result = extract_result(completed_output)
        record.update(result)
        record["status"] = "passed"
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        record["error"] = str(error)
        if not preparation_log.exists():
            preparation_log.parent.mkdir(parents=True, exist_ok=True)
            preparation_log.write_text(f"Preparation failed: {error}\n", encoding="utf-8")
    finally:
        if local_server is not None:
            local_server.shutdown()
            local_server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=5)
    return record


def default_output_directory() -> Path:
    """Return a timestamped result directory."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return SCRIPT_DIRECTORY / "results" / timestamp


def resolve_output_directory(value: Path | None) -> Path:
    """Resolve an output directory and keep it inside the benchmarks directory."""
    candidate = SCRIPT_DIRECTORY / value if value is not None and not value.is_absolute() else value
    output_root = (candidate or default_output_directory()).resolve()
    try:
        output_root.relative_to(SCRIPT_DIRECTORY)
    except ValueError as error:
        raise ValueError(
            f"Output directory must be inside the benchmarks directory: {SCRIPT_DIRECTORY}",
        ) from error
    return output_root


def main() -> int:
    """Select, execute, and report the requested benchmark matrix."""
    arguments = parse_arguments()
    config_file = arguments.config or find_default_config()
    if config_file is not None:
        config_file = config_file.resolve()
        if not config_file.is_file():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        config = BenchmarkConfig.from_file(config_file)
    else:
        config = BenchmarkConfig.defaults(default_saf_repository())
    plan = build_plan(arguments)
    validate_configuration(config, plan)
    print(f"Selected {len(plan)} benchmark runs:", flush=True)
    for item in plan:
        print(f"  - {item.label}", flush=True)
    output_root = resolve_output_directory(arguments.output_dir)
    if arguments.dry_run:
        return 0

    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    print("\n----- Creating assets -----", flush=True)
    config, preparation_records = prepare_benchmark_assets(
        config,
        sorted({item.mode for item in plan}),
        output_root / "preparation",
    )
    validate_prepared_configuration(config, plan)
    print("Assets created.", flush=True)

    records: list[dict[str, Any]] = []
    for item in plan:
        print(f"\n----- {item.label} -----", flush=True)
        record = run_one(item, config, output_root)
        records.append(record)
        if record["status"] == "passed":
            print(
                f"Passed {item.label}: "
                f"backend={float(record['backend_seconds']):.3f}s, "
                f"total={float(record['total_seconds']):.3f}s",
                flush=True,
            )
        else:
            print(f"Failed {item.label}: {record['error']}", flush=True)
            if arguments.fail_fast:
                break

    markdown_file = write_reports(
        output_root,
        records,
        plan,
        config_file,
        preparation_records,
    )
    print("\nBenchmark reports:", flush=True)
    print(f"  Markdown: {markdown_file}", flush=True)
    return 1 if any(record["status"] == "failed" for record in records) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, FileExistsError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
