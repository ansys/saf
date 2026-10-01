# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
from collections.abc import Callable, Sequence
import os
from pathlib import Path
import subprocess
import sys


EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
    "{{cookiecutter.__solution_name}}",
}


def parse_packages(packages: str) -> list[str]:
    """Parse a comma-separated package list."""
    parsed_packages = [
        package.strip() for package in packages.split(",") if package.strip()
    ]
    if not parsed_packages:
        msg = "At least one package must be provided."
        raise ValueError(msg)

    return parsed_packages


def find_poetry_project_dirs(root_dir: Path) -> list[Path]:
    """Find directories that contain poetry.lock files below a root directory."""
    poetry_lock_files: list[Path] = []

    for current_dir_name, dir_names, file_names in os.walk(root_dir):
        dir_names[:] = [
            dir_name for dir_name in dir_names if dir_name not in EXCLUDED_DIR_NAMES
        ]
        if "poetry.lock" in file_names:
            poetry_lock_files.append(Path(current_dir_name) / "poetry.lock")

    return sorted({poetry_lock_file.parent for poetry_lock_file in poetry_lock_files})


def find_uv_project_dirs(root_dir: Path) -> list[Path]:
    """Find directories that contain uv.lock files below a root directory."""
    uv_lock_files: list[Path] = []

    for current_dir_name, dir_names, file_names in os.walk(root_dir):
        dir_names[:] = [
            dir_name for dir_name in dir_names if dir_name not in EXCLUDED_DIR_NAMES
        ]
        if "uv.lock" in file_names:
            uv_lock_files.append(Path(current_dir_name) / "uv.lock")

    return sorted({uv_lock_file.parent for uv_lock_file in uv_lock_files})


def update_poetry_locks(
    project_dirs: Sequence[Path],
    packages: Sequence[str],
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """Run Poetry's lock-only package update in each project directory."""
    command = ["poetry", "update", *packages, "--lock"]
    for project_dir in project_dirs:
        print(f"Updating {project_dir / 'poetry.lock'}")
        run(command, cwd=project_dir, check=True)


def update_uv_locks(
    project_dirs: Sequence[Path],
    packages: Sequence[str],
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """Run uv's lock-only package update in each project directory."""
    command = ["uv", "lock"]
    for package in packages:
        command += ["--upgrade-package", package]
    for project_dir in project_dirs:
        print(f"Updating {project_dir / 'uv.lock'}")
        run(command, cwd=project_dir, check=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run 'poetry update <packages> --lock' for every poetry.lock file below a directory.",
    )
    parser.add_argument(
        "packages",
        help="Comma-separated package list to update, for example 'ansys-saf-glow,ansys-saf-cli'.",
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Root directory to search. Defaults to this repository root.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the lock updater command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        packages = parse_packages(args.packages)
    except ValueError as error:
        parser.error(str(error))

    poetry_project_dirs = find_poetry_project_dirs(args.root_dir)
    uv_project_dirs = find_uv_project_dirs(args.root_dir)
    if not poetry_project_dirs and not uv_project_dirs:
        print(f"No poetry.lock or uv.lock files found below {args.root_dir}.")
        return 0

    try:
        update_poetry_locks(poetry_project_dirs, packages)
        update_uv_locks(uv_project_dirs, packages)
    except subprocess.CalledProcessError as error:
        return error.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
