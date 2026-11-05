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

from pathlib import Path
import shutil
import tempfile
from typing import Self

import click

from ansys.saf.cli._utilities.conversion import namespace_to_path


class BackupManager:
    """
    Handles snapshot, backup, restore and cleanup operations for a solution add-step workflow.
    Implements context manager protocol for automatic rollback on exceptions.

    When used as a context manager, ``__enter__`` snapshots the solution module directory
    and backs up all provided files upfront (non-existent files are silently skipped).
    On exception, ``__exit__`` removes newly created files and restores all backed-up files;
    the backup directory is always removed on exit.

    Attributes:
        solution_root_dir: The root directory of the solution.
        solution_package_name: The name of the solution package module.
        files_to_backup: List of (file_path, base_dir) tuples to back up.
    """

    def __init__(
        self,
        solution_root_dir: Path,
        solution_package_name: str,
        namespace_root: str,
        files_to_backup: list[tuple[Path, Path]] | None = None,
    ):
        """Initialize BackupManager.

        Args:
            solution_root_dir: Root directory of the solution.
            solution_package_name: Name of the solution package (used to compute base_solution_dir).
            namespace_root: Root namespace of the solution.
            files_to_backup: List of (file_path, base_dir) tuples to back up. If None, uses default files
                           (page.py, definition.py, pyproject.toml, poetry.lock, uv.lock).
        """
        self._solution_root_dir = solution_root_dir
        # Compute base_solution_dir from solution_root_dir and solution_package_name
        self._base_solution_dir = solution_root_dir / "src" / namespace_to_path(namespace_root) / solution_package_name

        # If files_to_backup is not provided, use default files
        if files_to_backup is None:
            files_to_backup = [
                # even if some of these files are not modified explicitly by the saf-cli,
                # they can be modified by the post-gen hooks in the step templates themselves
                (self._base_solution_dir / "ui" / "pages" / "page.py", self._base_solution_dir),
                (self._base_solution_dir / "solution" / "definition.py", self._base_solution_dir),
                (solution_root_dir / "pyproject.toml", solution_root_dir),
                (solution_root_dir / "poetry.lock", solution_root_dir),
                (solution_root_dir / "uv.lock", solution_root_dir),
            ]

        self._files_to_backup = files_to_backup
        self._backup_dir = Path(tempfile.mkdtemp())
        self._preexisting_paths: set[str] = set()
        self._backup_mapping: dict[Path, Path] = {}
        self._missing_files_to_remove_on_restore: set[Path] = set()
        self._snapshot_taken = False

    def _snapshot_directory_paths(self) -> set[str]:
        """Return relative paths of all files and directories under the solution module directory."""
        if not self._base_solution_dir.exists():
            return set()
        return {str(p.relative_to(self._base_solution_dir)) for p in self._base_solution_dir.rglob("*")}

    def _rollback_newly_created_files_and_empty_dirs(self) -> None:
        """Remove newly created files and empty directories."""
        if not self._snapshot_taken:
            raise RuntimeError("Cannot rollback before taking a snapshot.")

        post_paths = self._snapshot_directory_paths()
        created_paths = post_paths - self._preexisting_paths

        for rel in sorted(created_paths, reverse=True):
            target = self._base_solution_dir / rel
            try:
                if target.is_file() or target.is_symlink():
                    target.unlink()
                elif target.is_dir() and not any(target.iterdir()):
                    target.rmdir()
            except OSError as e:
                click.secho(
                    f"Warning: Failed cleanup: {target} ({e})",
                    fg="yellow",
                )

        for target in sorted(self._missing_files_to_remove_on_restore, reverse=True):
            if not target.exists():
                continue

            try:
                if target.is_file() or target.is_symlink():
                    target.unlink()
            except OSError as e:
                click.secho(
                    f"Warning: Failed cleanup: {target} ({e})",
                    fg="yellow",
                )

    def _backup_files(self) -> None:
        """Backup files preserving relative structure."""
        for src in (file for file, _ in self._files_to_backup):
            if not src.is_file():
                continue

            # Find the base_dir for this file from _files_to_backup
            base_dir = next((bd for f, bd in self._files_to_backup if f == src), self._base_solution_dir)
            relative_path = src.relative_to(base_dir) if src.is_relative_to(base_dir) else Path(src.name)
            backup_file = self._backup_dir / relative_path

            try:
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, backup_file)
                self._backup_mapping[src] = backup_file
            except OSError as e:
                click.secho(
                    f"Warning: Failed to backup '{src}' -> '{backup_file}' ({e})",
                    fg="yellow",
                )

    def _restore_files(self) -> None:
        """Restore files from backup."""
        for original, backup in self._backup_mapping.items():
            try:
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, original)
            except OSError as e:
                click.secho(
                    f"Restore failed: {original} ({e})",
                    fg="yellow",
                )

    def __enter__(self) -> Self:
        """Enter context manager.

        Snapshots ``base_solution_dir`` and backs up every file supplied via ``files_to_backup``.
        Files that do not yet exist (e.g. an optional ``poetry.lock``) are silently skipped.
        """
        # Take snapshot of the solution module directory
        self._preexisting_paths = self._snapshot_directory_paths()
        self._missing_files_to_remove_on_restore = {
            file_path for file_path, _ in self._files_to_backup if not file_path.exists()
        }
        self._snapshot_taken = True

        # Back up specified files
        self._backup_files()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:  # type: ignore
        """Exit context manager: restore state if exception occurred, always cleanup."""
        try:
            if exc_type is not None:
                # Remove newly created files and empty directories
                self._rollback_newly_created_files_and_empty_dirs()
                # Restore all backed-up files
                self._restore_files()
        finally:
            # Always cleanup backup directory
            shutil.rmtree(self._backup_dir, ignore_errors=True)
        return False
