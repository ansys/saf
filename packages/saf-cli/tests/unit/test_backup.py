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

from ansys.saf.cli._utilities.backup import BackupManager
from ansys.saf.cli._utilities.conversion import namespace_to_path


def _create_file(file_path: Path, content: str = "sample_data"):
    """Helper to create a file with given content."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


@pytest.mark.parametrize("create_base_dir", [False, True], ids=["missing_base_dir", "empty_base_dir"])
@pytest.mark.parametrize("solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
def test_snapshot_returns_empty_set_when_no_content(tmp_path: Path, create_base_dir: bool, solution_namespace: str):
    """snapshot_directory_paths should return empty set for missing or empty base directory."""
    manager = BackupManager(tmp_path, "test_solution", solution_namespace)
    if create_base_dir:
        base_dir = tmp_path / "src" / namespace_to_path(solution_namespace) / "test_solution"
        base_dir.mkdir(parents=True, exist_ok=True)

    snapshot = manager._snapshot_directory_paths()

    assert snapshot == set()


@pytest.mark.parametrize("solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
def test_snapshot_captures_files_and_directories(tmp_path: Path, solution_namespace: str):
    """snapshot_directory_paths should capture files and nested directory hierarchy."""
    manager = BackupManager(tmp_path, "test_solution", solution_namespace)
    base_dir = tmp_path / "src" / namespace_to_path(solution_namespace) / "test_solution"
    _create_file(base_dir / "file.txt")
    (base_dir / "subdir").mkdir(parents=True, exist_ok=True)
    _create_file(base_dir / "subdir" / "nested.txt")
    _create_file(base_dir / "a" / "b" / "c" / "file.txt")
    snapshot = manager._snapshot_directory_paths()

    assert "file.txt" in snapshot
    assert "subdir" in snapshot
    assert str(Path("subdir") / "nested.txt") in snapshot
    assert "a" in snapshot
    assert str(Path("a") / "b") in snapshot
    assert str(Path("a") / "b" / "c") in snapshot
    assert str(Path("a") / "b" / "c" / "file.txt") in snapshot


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
@pytest.mark.parametrize(
    ("root_solution_dir_with_pyproject_and_lock", "lockfile_name"),
    [
        pytest.param({}, "poetry.lock", id="poetry"),
        pytest.param({"backend": "uv"}, "uv.lock", id="uv"),
    ],
    indirect=["root_solution_dir_with_pyproject_and_lock"],
)
def test_manager_initialization_and_enter_flow(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
    lockfile_name: str,
):
    """Initialization and __enter__ should set base paths, take snapshot, and populate backup mapping."""
    manager = BackupManager(root_solution_dir_with_pyproject_and_lock, solution_name, solution_namespace)
    expected_base = (
        root_solution_dir_with_pyproject_and_lock / "src" / namespace_to_path(solution_namespace) / solution_name
    )

    assert manager._solution_root_dir == root_solution_dir_with_pyproject_and_lock
    assert manager._base_solution_dir == expected_base
    assert manager._backup_dir.exists()
    assert manager._backup_dir.is_dir()
    assert len(manager._preexisting_paths) == 0
    lockfile_path = root_solution_dir_with_pyproject_and_lock / lockfile_name
    assert lockfile_path.is_file()
    other_lockfile_name = "poetry.lock" if lockfile_name == "uv.lock" else "uv.lock"
    assert not (root_solution_dir_with_pyproject_and_lock / other_lockfile_name).exists()

    with manager as entered:
        assert isinstance(entered, BackupManager)
        assert entered._backup_dir.exists()
        assert len(entered._preexisting_paths) > 0
        assert len(entered._backup_mapping) == 4
        assert lockfile_path in entered._backup_mapping

        for original, backup_copy in entered._backup_mapping.items():
            assert isinstance(original, Path)
            assert isinstance(backup_copy, Path)
            assert backup_copy.exists()

        definition_backup = entered._backup_mapping.get(expected_base / "solution" / "definition.py")
        assert definition_backup is not None, "definition.py was not backed up"
        assert definition_backup.parent.name == "solution"
        assert definition_backup.name == "definition.py"


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
def test_initialization_with_custom_files_to_backup(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
):
    """BackupManager should only back up the explicitly provided files."""
    custom_files = [
        (root_solution_dir_with_pyproject_and_lock / "pyproject.toml", root_solution_dir_with_pyproject_and_lock),
    ]
    with BackupManager(
        root_solution_dir_with_pyproject_and_lock,
        solution_name,
        solution_namespace,
        files_to_backup=custom_files,
    ) as manager:
        # Only pyproject.toml was specified, so only one file should be backed up
        assert len(manager._backup_mapping) == 1
        assert root_solution_dir_with_pyproject_and_lock / "pyproject.toml" in manager._backup_mapping


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
def test_initialization_computes_base_solution_dir(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
):
    """BackupManager should compute base_solution_dir from solution_package_name."""
    manager = BackupManager(root_solution_dir_with_pyproject_and_lock, "my_solution", solution_namespace)

    expected = root_solution_dir_with_pyproject_and_lock / "src" / namespace_to_path(solution_namespace) / "my_solution"
    assert manager._base_solution_dir == expected


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
@pytest.mark.parametrize(
    ("exception_type", "error_message"),
    [
        (None, None),
        (RuntimeError, "simulated runtime failure"),
        (ValueError, "test exception"),
    ],
    ids=["success_exit", "runtime_exception_exit", "value_error_reraised"],
)
def test_context_manager_cleanup_on_exit(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
    exception_type: type[Exception] | None,
    error_message: str | None,
):
    """__exit__ should always cleanup and must re-raise exceptions."""
    manager = BackupManager(root_solution_dir_with_pyproject_and_lock, solution_name, solution_namespace)
    backup_dir = manager._backup_dir
    assert backup_dir.exists()

    def _raise_inside_manager() -> None:
        assert exception_type is not None
        with manager:
            raise exception_type(error_message)

    if exception_type is not None:
        with pytest.raises(exception_type, match=error_message):
            _raise_inside_manager()
    else:
        with manager:
            assert backup_dir.exists()

    assert not backup_dir.exists()


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
def test_backup_files_skips_nonexistent_files(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
):
    """Backup should skip files that don't exist; only present files appear in backup_mapping."""
    custom_files = [
        (root_solution_dir_with_pyproject_and_lock / "nonexistent.txt", root_solution_dir_with_pyproject_and_lock),
        (root_solution_dir_with_pyproject_and_lock / "pyproject.toml", root_solution_dir_with_pyproject_and_lock),
    ]
    with BackupManager(
        root_solution_dir_with_pyproject_and_lock,
        solution_name,
        solution_namespace,
        files_to_backup=custom_files,
    ) as manager:
        assert root_solution_dir_with_pyproject_and_lock / "nonexistent.txt" not in manager._backup_mapping
        assert root_solution_dir_with_pyproject_and_lock / "pyproject.toml" in manager._backup_mapping


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
def test_backup_files_handles_empty_files_list(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
):
    """Backup should produce an empty backup_mapping when files_to_backup is empty."""
    with BackupManager(
        root_solution_dir_with_pyproject_and_lock,
        solution_name,
        solution_namespace,
        files_to_backup=[],
    ) as manager:
        assert len(manager._backup_mapping) == 0


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
@pytest.mark.parametrize(
    ("root_solution_dir_with_pyproject_and_lock", "files_to_modify"),
    [
        pytest.param({}, ["pyproject.toml"], id="single_file"),
        pytest.param(
            {},
            [
                "src/saf/solutions/{solution_name}/ui/pages/page.py",
                "src/saf/solutions/{solution_name}/solution/definition.py",
                "pyproject.toml",
                "poetry.lock",
            ],
            id="poetry_multiple_files",
        ),
        pytest.param(
            {"backend": "uv"},
            [
                "src/saf/solutions/{solution_name}/ui/pages/page.py",
                "src/saf/solutions/{solution_name}/solution/definition.py",
                "pyproject.toml",
                "uv.lock",
            ],
            id="uv_multiple_files",
        ),
    ],
    indirect=["root_solution_dir_with_pyproject_and_lock"],
)
def test_restore_existing_files_on_exception(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
    files_to_modify: list[str],
):
    """Modified existing files should be restored when an exception happens in the context."""
    targets = [
        root_solution_dir_with_pyproject_and_lock / rel.format(solution_name=solution_name) for rel in files_to_modify
    ]
    original_content = {target: target.read_text() for target in targets}

    def _modify_targets_and_fail() -> None:
        with BackupManager(root_solution_dir_with_pyproject_and_lock, solution_name, solution_namespace):
            for target in targets:
                target.write_text("MODIFIED_CONTENT")
            raise RuntimeError("simulated failure")

    with pytest.raises(RuntimeError, match="simulated failure"):
        _modify_targets_and_fail()

    for target in targets:
        assert target.read_text() == original_content[target]


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
def test_restore_only_backed_up_files(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
):
    """Only files in files_to_backup should be restored on exception; other files remain as-is."""
    custom_file = root_solution_dir_with_pyproject_and_lock / "custom.txt"
    _create_file(custom_file, "custom")

    # Only back up pyproject.toml
    custom_files = [
        (root_solution_dir_with_pyproject_and_lock / "pyproject.toml", root_solution_dir_with_pyproject_and_lock),
    ]

    manager = BackupManager(
        root_solution_dir_with_pyproject_and_lock,
        solution_name,
        solution_namespace,
        files_to_backup=custom_files,
    )
    original_pyproject = (root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_text()

    try:
        with manager:
            (root_solution_dir_with_pyproject_and_lock / "pyproject.toml").write_text("MODIFIED")
            custom_file.write_text("MODIFIED_CUSTOM")
            raise RuntimeError("test")
    except RuntimeError:
        pass

    # pyproject.toml should be restored, custom_file should not
    assert (root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_text() == original_pyproject
    assert custom_file.read_text() == "MODIFIED_CUSTOM"


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
@pytest.mark.parametrize(
    ("root_solution_dir_with_pyproject_and_lock", "lockfile_name"),
    [
        pytest.param({}, "poetry.lock", id="poetry"),
        pytest.param({"backend": "uv"}, "uv.lock", id="uv"),
    ],
    indirect=["root_solution_dir_with_pyproject_and_lock"],
)
def test_rollback_removes_new_artifacts_and_restores_existing_files(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
    lockfile_name: str,
):
    """Rollback should remove newly created artifacts and restore pre-existing file content."""
    base_dir = root_solution_dir_with_pyproject_and_lock / "src" / namespace_to_path(solution_namespace) / solution_name
    new_file = base_dir / "new_step.py"
    new_dir = base_dir / "new_step"
    lockfile_path = root_solution_dir_with_pyproject_and_lock / lockfile_name
    existing_file = base_dir / "solution" / "definition.py"
    original_content = existing_file.read_text()
    lockfile_path.unlink(missing_ok=True)

    def _create_artifacts_and_fail() -> None:
        with BackupManager(root_solution_dir_with_pyproject_and_lock, solution_name, solution_namespace):
            _create_file(new_file, "new content")
            new_dir.mkdir(parents=True)
            _create_file(new_dir / "file.py")
            lockfile_path.write_text("NEW_LOCK")
            existing_file.write_text("MODIFIED")
            raise RuntimeError("simulated failure")

    with pytest.raises(RuntimeError, match="simulated failure"):
        _create_artifacts_and_fail()

    assert not new_file.exists()
    assert not new_dir.exists()
    assert not lockfile_path.exists()
    assert existing_file.read_text() == original_content


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
@pytest.mark.parametrize(
    ("root_solution_dir_with_pyproject_and_lock", "lockfile_name", "preexisting_lock"),
    [
        pytest.param({}, None, True, id="new_file_only"),
        pytest.param({"backend": "uv"}, "uv.lock", False, id="uv_new_lock"),
        pytest.param({"backend": "uv"}, "uv.lock", True, id="uv_existing_lock"),
    ],
    indirect=["root_solution_dir_with_pyproject_and_lock"],
)
def test_rollback_only_on_exception(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
    lockfile_name: str | None,
    preexisting_lock: bool,
):
    """Rollback should only happen when exception occurs."""
    base_dir = root_solution_dir_with_pyproject_and_lock / "src" / namespace_to_path(solution_namespace) / solution_name
    new_file = base_dir / "new_step.py"
    lockfile_path = root_solution_dir_with_pyproject_and_lock / lockfile_name if lockfile_name is not None else None
    if lockfile_path is not None and not preexisting_lock:
        lockfile_path.unlink()

    with BackupManager(root_solution_dir_with_pyproject_and_lock, solution_name, solution_namespace):
        _create_file(new_file, "new content")
        if lockfile_path is not None:
            lockfile_path.write_text("UPDATED_LOCK")
        # No exception raised

    # New file should NOT be removed on successful completion
    assert new_file.exists()
    if lockfile_path is not None:
        assert lockfile_path.read_text() == "UPDATED_LOCK"


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
def test_rollback_requires_snapshot(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    solution_namespace: str,
):
    """Rollback should fail fast when the context snapshot was never taken."""
    manager = BackupManager(root_solution_dir_with_pyproject_and_lock, solution_name, solution_namespace)

    with pytest.raises(RuntimeError, match="Cannot rollback before taking a snapshot"):
        manager._rollback_newly_created_files_and_empty_dirs()
