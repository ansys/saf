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

# pyright: reportPrivateUsage=false

from pathlib import Path

import pytest

from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._solutions.backend_detection import parse_solution_backend
from ansys.saf.cli._utilities.backup import BackupManager
from ansys.saf.cli._utilities.conversion import namespace_to_path


def _create_file(path: Path, content: str = "data"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src", "cleanup_solution_pyproject")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_backup_manager_context_manager_preserves_changes_on_success(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
):
    """Verify that changes are NOT reverted on successful context exit."""
    solution_root = session_solution.root_dir
    solution_package_name = session_solution.name
    base_dir = solution_root / "src" / namespace_to_path(session_solution_namespace) / solution_package_name
    definition_path = base_dir / "solution" / "definition.py"

    with BackupManager(solution_root, solution_package_name, session_solution_namespace):
        definition_path.write_text("MODIFIED_DEFINITION")

    # After successful context exit, modifications should persist
    assert definition_path.read_text() == "MODIFIED_DEFINITION"


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src", "cleanup_solution_pyproject")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_backup_manager_context_manager_rolls_back_and_reraises_on_exception(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
):
    """Verify rollback restores state, cleans artifacts, and re-raises on exception."""
    solution_root = session_solution.root_dir
    solution_package_name = session_solution.name
    base_dir = solution_root / "src" / namespace_to_path(session_solution_namespace) / solution_package_name
    definition_path = base_dir / "solution" / "definition.py"
    page_path = base_dir / "ui" / "pages" / "page.py"
    original_definition = definition_path.read_text()
    original_page = page_path.read_text()
    manager = BackupManager(solution_root, solution_package_name, session_solution_namespace)
    backup_dir = manager._backup_dir
    assert backup_dir.exists()

    def _perform_failing_workflow() -> None:
        with manager:
            definition_path.write_text("CORRUPTED_DEFINITION")
            page_path.write_text("CORRUPTED_PAGE")

            new_step_path = base_dir / "solution" / "new_step.py"
            _create_file(new_step_path, "NEW_STEP_CODE")
            new_page_path = base_dir / "ui" / "pages" / "new_page.py"
            _create_file(new_page_path, "NEW_PAGE_CODE")

            nested_dir = base_dir / "solution" / "nested" / "deep"
            nested_dir.mkdir(parents=True)
            _create_file(nested_dir / "file.py")

            raise RuntimeError("simulated failure")

    with pytest.raises(RuntimeError, match="simulated failure"):
        _perform_failing_workflow()

    # Verify restoration of modified files
    assert definition_path.read_text() == original_definition
    assert page_path.read_text() == original_page

    # Verify newly created files were removed
    assert not (base_dir / "solution" / "new_step.py").exists()
    assert not (base_dir / "ui" / "pages" / "new_page.py").exists()

    # Verify newly created nested structure was removed
    assert not (base_dir / "solution" / "nested").exists()

    # Verify backup directory is always cleaned on exception path
    assert not backup_dir.exists()


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src", "cleanup_solution_pyproject")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_backup_manager_context_manager_cleans_backup_on_success(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
):
    """Verify backup directory is cleaned up on successful exit."""
    solution_root = session_solution.root_dir
    solution_package_name = session_solution.name
    manager = BackupManager(solution_root, solution_package_name, session_solution_namespace)
    backup_dir = manager._backup_dir

    with manager:
        assert backup_dir.exists()

    # Verify cleanup happened
    assert not backup_dir.exists()


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src", "cleanup_solution_pyproject", "cleanup_solution_lock")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_backup_manager_context_manager_restores_dependency_files(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
):
    """Verify rollback preserves the solution's own dependency lockfile."""
    solution_root = session_solution.root_dir
    solution_package_name = session_solution.name
    pyproject_path = solution_root / "pyproject.toml"
    lock_path = parse_solution_backend(solution_root).lockfile_path
    original_pyproject = pyproject_path.read_bytes()
    original_lock = lock_path.read_bytes()

    try:
        with BackupManager(solution_root, solution_package_name, session_solution_namespace):
            pyproject_path.write_bytes(b"UPDATED_PYPROJECT")
            lock_path.write_bytes(b"UPDATED_LOCK")
            raise RuntimeError("simulated dependency update failure")
    except RuntimeError:
        pass

    # Verify restoration
    assert pyproject_path.read_bytes() == original_pyproject
    assert lock_path.read_bytes() == original_lock


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src", "cleanup_solution_pyproject")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_backup_manager_context_manager_skips_nonexistent_files(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
):
    """Verify context manager skips nonexistent files gracefully."""
    solution_root = session_solution.root_dir
    solution_package_name = session_solution.name
    base_dir = solution_root / "src" / namespace_to_path(session_solution_namespace) / solution_package_name
    missing_path = base_dir / "solution" / "does_not_exist.py"
    definition_path = base_dir / "solution" / "definition.py"
    original_definition = definition_path.read_text()
    custom_files = [
        (missing_path, base_dir),
        (definition_path, base_dir),
    ]

    try:
        with BackupManager(
            solution_root,
            solution_package_name,
            session_solution_namespace,
            files_to_backup=custom_files,
        ):
            definition_path.write_text("MODIFIED")
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass

    # Verify that existing file was restored despite nonexistent file in list
    assert definition_path.read_text() == original_definition
