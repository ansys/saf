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
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
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


@dataclass
class PackageUpdate:
    """Represents a package version change."""

    package: str
    version_before: str | None
    version_after: str | None
    error: str | None = None

    @property
    def status(self) -> str:
        """Return the status of the update."""
        if self.error:
            return "error"
        if self.version_before is None:
            return "not found"
        if self.version_before == self.version_after:
            return "unchanged"
        return "updated"


@dataclass
class LockFileUpdate:
    """Represents updates to a single lock file."""

    lock_file: Path
    package_updates: list[PackageUpdate] = field(default_factory=list)
    error: str | None = None


def parse_packages(packages: str) -> list[str]:
    """Parse a comma-separated package list."""
    parsed_packages = [
        package.strip() for package in packages.split(",") if package.strip()
    ]
    if not parsed_packages:
        msg = "At least one package must be provided."
        raise ValueError(msg)

    return parsed_packages


def get_poetry_versions(lock_file: Path, packages: Sequence[str]) -> dict[str, str | None]:
    """Extract package versions from a poetry.lock file."""
    versions: dict[str, str | None] = {pkg: None for pkg in packages}
    if not lock_file.exists():
        return versions

    content = lock_file.read_text(encoding="utf-8")
    # Poetry lock format: [[package]]\nname = "pkg"\nversion = "1.0.0"
    package_pattern = re.compile(
        r'\[\[package\]\]\s*\nname\s*=\s*"([^"]+)"\s*\nversion\s*=\s*"([^"]+)"',
        re.MULTILINE,
    )
    for match in package_pattern.finditer(content):
        name, version = match.groups()
        # Normalize package name (replace - with _ for comparison)
        normalized_name = name.lower().replace("-", "_")
        for pkg in packages:
            if pkg.lower().replace("-", "_") == normalized_name:
                versions[pkg] = version
                break

    return versions


def get_uv_versions(lock_file: Path, packages: Sequence[str]) -> dict[str, str | None]:
    """Extract package versions from a uv.lock file."""
    versions: dict[str, str | None] = {pkg: None for pkg in packages}
    if not lock_file.exists():
        return versions

    content = lock_file.read_text(encoding="utf-8")
    # uv.lock format: [[package]]\nname = "pkg"\nversion = "1.0.0"
    package_pattern = re.compile(
        r'\[\[package\]\]\s*\nname\s*=\s*"([^"]+)"\s*\nversion\s*=\s*"([^"]+)"',
        re.MULTILINE,
    )
    for match in package_pattern.finditer(content):
        name, version = match.groups()
        normalized_name = name.lower().replace("-", "_")
        for pkg in packages:
            if pkg.lower().replace("-", "_") == normalized_name:
                versions[pkg] = version
                break

    return versions


def get_npm_versions(lock_file: Path, packages: Sequence[str]) -> dict[str, str | None]:
    """Extract package versions from a package-lock.json file."""
    versions: dict[str, str | None] = {pkg: None for pkg in packages}
    if not lock_file.exists():
        return versions

    try:
        content = json.loads(lock_file.read_text(encoding="utf-8"))
        # npm v2+ lockfile format
        pkgs = content.get("packages", {})
        for pkg in packages:
            # Check node_modules path
            pkg_path = f"node_modules/{pkg}"
            if pkg_path in pkgs:
                versions[pkg] = pkgs[pkg_path].get("version")
            # Also check dependencies (npm v1 format)
            elif "dependencies" in content and pkg in content["dependencies"]:
                versions[pkg] = content["dependencies"][pkg].get("version")
    except (json.JSONDecodeError, KeyError):
        pass

    return versions


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


def find_npm_project_dirs(root_dir: Path) -> list[Path]:
    """Find directories that contain package-lock.json files below a root directory."""
    npm_lock_files: list[Path] = []

    for current_dir_name, dir_names, file_names in os.walk(root_dir):
        dir_names[:] = [
            dir_name for dir_name in dir_names if dir_name not in EXCLUDED_DIR_NAMES
        ]
        if "package-lock.json" in file_names:
            npm_lock_files.append(Path(current_dir_name) / "package-lock.json")

    return sorted({npm_lock_file.parent for npm_lock_file in npm_lock_files})


def update_poetry_locks(
    project_dirs: Sequence[Path],
    packages: Sequence[str],
    *,
    one_by_one: bool = False,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[LockFileUpdate]:
    """Run Poetry's lock-only package update in each project directory."""
    results: list[LockFileUpdate] = []
    base_command = ["uvx", "--with", "poetry==2.5.1", "poetry", "update"]

    for project_dir in project_dirs:
        lock_file = project_dir / "poetry.lock"
        print(f"Updating {lock_file}")

        versions_before = get_poetry_versions(lock_file, packages)
        update_result = LockFileUpdate(lock_file=lock_file)

        if one_by_one:
            for package in packages:
                command = [*base_command, package, "--lock"]
                error = None
                try:
                    run(command, cwd=project_dir, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as err:
                    error = err.stderr.strip() if err.stderr else "Unknown error"
                    print(f"  Warning: failed to update {package}")
                    if err.stderr:
                        for line in err.stderr.strip().splitlines():
                            print(f"    {line}")

                versions_after = get_poetry_versions(lock_file, [package])
                update_result.package_updates.append(
                    PackageUpdate(
                        package=package,
                        version_before=versions_before[package],
                        version_after=versions_after[package],
                        error=error,
                    )
                )
        else:
            command = [*base_command, *packages, "--lock"]
            error = None
            try:
                run(command, cwd=project_dir, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as err:
                error = err.stderr.strip() if err.stderr else "Unknown error"
                print(f"  Warning: failed to update {lock_file}")
                if err.stderr:
                    for line in err.stderr.strip().splitlines():
                        print(f"    {line}")
                update_result.error = error

            versions_after = get_poetry_versions(lock_file, packages)
            for package in packages:
                update_result.package_updates.append(
                    PackageUpdate(
                        package=package,
                        version_before=versions_before[package],
                        version_after=versions_after[package],
                        error=error if error else None,
                    )
                )

        results.append(update_result)

    return results


def update_uv_locks(
    project_dirs: Sequence[Path],
    packages: Sequence[str],
    *,
    one_by_one: bool = False,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[LockFileUpdate]:
    """Run uv's lock-only package update in each project directory."""
    results: list[LockFileUpdate] = []

    for project_dir in project_dirs:
        lock_file = project_dir / "uv.lock"
        print(f"Updating {lock_file}")

        versions_before = get_uv_versions(lock_file, packages)
        update_result = LockFileUpdate(lock_file=lock_file)

        if one_by_one:
            for package in packages:
                command = ["uv", "lock", "--upgrade-package", package]
                error = None
                try:
                    run(command, cwd=project_dir, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as err:
                    error = err.stderr.strip() if err.stderr else "Unknown error"
                    print(f"  Warning: failed to update {package}")
                    if err.stderr:
                        for line in err.stderr.strip().splitlines():
                            print(f"    {line}")

                versions_after = get_uv_versions(lock_file, [package])
                update_result.package_updates.append(
                    PackageUpdate(
                        package=package,
                        version_before=versions_before[package],
                        version_after=versions_after[package],
                        error=error,
                    )
                )
        else:
            command = ["uv", "lock"]
            for package in packages:
                command += ["--upgrade-package", package]
            error = None
            try:
                run(command, cwd=project_dir, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as err:
                error = err.stderr.strip() if err.stderr else "Unknown error"
                print(f"  Warning: failed to update {lock_file}")
                if err.stderr:
                    for line in err.stderr.strip().splitlines():
                        print(f"    {line}")
                update_result.error = error

            versions_after = get_uv_versions(lock_file, packages)
            for package in packages:
                update_result.package_updates.append(
                    PackageUpdate(
                        package=package,
                        version_before=versions_before[package],
                        version_after=versions_after[package],
                        error=error if error else None,
                    )
                )

        results.append(update_result)

    return results


def update_npm_locks(
    project_dirs: Sequence[Path],
    packages: Sequence[str],
    *,
    one_by_one: bool = False,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[LockFileUpdate]:
    """Run npm update for packages in each project directory."""
    results: list[LockFileUpdate] = []

    for project_dir in project_dirs:
        lock_file = project_dir / "package-lock.json"
        print(f"Updating {lock_file}")

        versions_before = get_npm_versions(lock_file, packages)
        update_result = LockFileUpdate(lock_file=lock_file)

        if one_by_one:
            for package in packages:
                command = ["npm", "update", package]
                error = None
                try:
                    run(command, cwd=project_dir, check=True, capture_output=True, text=True, shell=True)
                except subprocess.CalledProcessError as err:
                    error = err.stderr.strip() if err.stderr else "Unknown error"
                    print(f"  Warning: failed to update {package}")
                    if err.stderr:
                        for line in err.stderr.strip().splitlines():
                            print(f"    {line}")

                versions_after = get_npm_versions(lock_file, [package])
                update_result.package_updates.append(
                    PackageUpdate(
                        package=package,
                        version_before=versions_before[package],
                        version_after=versions_after[package],
                        error=error,
                    )
                )
        else:
            command = ["npm", "update", *packages]
            error = None
            try:
                run(command, cwd=project_dir, check=True, capture_output=True, text=True, shell=True)
            except subprocess.CalledProcessError as err:
                error = err.stderr.strip() if err.stderr else "Unknown error"
                print(f"  Warning: failed to update {lock_file}")
                if err.stderr:
                    for line in err.stderr.strip().splitlines():
                        print(f"    {line}")
                update_result.error = error

            versions_after = get_npm_versions(lock_file, packages)
            for package in packages:
                update_result.package_updates.append(
                    PackageUpdate(
                        package=package,
                        version_before=versions_before[package],
                        version_after=versions_after[package],
                        error=error if error else None,
                    )
                )

        results.append(update_result)

    return results


def generate_report(
    results: list[LockFileUpdate],
    packages: Sequence[str],
    root_dir: Path,
) -> str:
    """Generate a markdown report of the update results."""
    lines: list[str] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines.append("# Lock File Update Report")
    lines.append("")
    lines.append(f"**Generated:** {timestamp}")
    lines.append(f"**Packages:** {', '.join(packages)}")
    lines.append("")

    # Summary counts
    total_updated = 0
    total_unchanged = 0
    total_not_found = 0
    total_errors = 0

    for result in results:
        for pkg_update in result.package_updates:
            status = pkg_update.status
            if status == "updated":
                total_updated += 1
            elif status == "unchanged":
                total_unchanged += 1
            elif status == "not found":
                total_not_found += 1
            elif status == "error":
                total_errors += 1

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Updated:** {total_updated}")
    lines.append(f"- **Unchanged:** {total_unchanged}")
    lines.append(f"- **Not found:** {total_not_found}")
    lines.append(f"- **Errors:** {total_errors}")
    lines.append("")

    lines.append("## Details")
    lines.append("")

    for result in results:
        try:
            relative_path = result.lock_file.relative_to(root_dir)
        except ValueError:
            relative_path = result.lock_file

        lines.append(f"### {relative_path}")
        lines.append("")

        if result.error:
            lines.append(f"**Error:** {result.error}")
            lines.append("")

        lines.append("| Package | Before | After | Status |")
        lines.append("|---------|--------|-------|--------|")

        for pkg_update in result.package_updates:
            before = pkg_update.version_before or "-"
            after = pkg_update.version_after or "-"
            status = pkg_update.status

            # Add emoji for status
            status_display = {
                "updated": "updated",
                "unchanged": "unchanged",
                "not found": "not found",
                "error": "error",
            }.get(status, status)

            lines.append(f"| {pkg_update.package} | {before} | {after} | {status_display} |")

        lines.append("")

    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update package lock files (poetry.lock, uv.lock, package-lock.json) across a repository.",
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
    parser.add_argument(
        "--one-by-one",
        action="store_true",
        help="Update packages one at a time instead of all at once.",
    )
    parser.add_argument(
        "--npm",
        action="store_true",
        help="Update npm package-lock.json files instead of Python lock files.",
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

    results: list[LockFileUpdate] = []

    if args.npm:
        npm_project_dirs = find_npm_project_dirs(args.root_dir)
        if not npm_project_dirs:
            print(f"No package-lock.json files found below {args.root_dir}.")
            return 0
        results = update_npm_locks(npm_project_dirs, packages, one_by_one=args.one_by_one)
    else:
        poetry_project_dirs = find_poetry_project_dirs(args.root_dir)
        uv_project_dirs = find_uv_project_dirs(args.root_dir)
        if not poetry_project_dirs and not uv_project_dirs:
            print(f"No poetry.lock or uv.lock files found below {args.root_dir}.")
            return 0
        results.extend(
            update_poetry_locks(poetry_project_dirs, packages, one_by_one=args.one_by_one)
        )
        results.extend(
            update_uv_locks(uv_project_dirs, packages, one_by_one=args.one_by_one)
        )

    # Generate and write report
    report = generate_report(results, packages, args.root_dir)
    dist_dir = args.root_dir / "dist"
    dist_dir.mkdir(exist_ok=True)
    report_file = dist_dir / "lock_update_report.md"
    report_file.write_text(report, encoding="utf-8")
    print(f"\nReport written to {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
