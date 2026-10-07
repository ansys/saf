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
from typing import Any

import pytest

from ansys.bdm.api import NO_ENTITY, EntityHandle, IStorageScope
from ansys.bdm.shared_volume.entity_tracker import EntityTracker
from ansys.bdm.shared_volume.storage_configuration import (
    SharedFilesystemConfiguration,
    SharedFilesystemContextConfiguration,
)
from ansys.bdm.shared_volume.storage_scope import StorageScope
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.migrations import MigrationContext
from ansys.saf.glow._server.project_files_manager import ProjectFilesManager
from tests.unit.contruct_migration_context import create_failing_storage_scope


def _create_storage_scope(root: Path) -> StorageScope:
    return StorageScope(
        EntityTracker(
            "CONTEXT",
            SharedFilesystemConfiguration(
                shared_filesystem_root=root,
                contexts={
                    "CONTEXT": SharedFilesystemContextConfiguration(relative_path=Path("inner_root")),
                },
            ),
        ),
    )


def _create_context(
    solution: dict[str, Any] | None = None,
    project_storage_scope: IStorageScope | None = None,
    file_manager: ProjectFilesManager | None = None,
    project_id: str | None = None,
    settings: Settings | None = None,
):
    return MigrationContext(
        solution=solution or {},
        project_storage_scope=project_storage_scope or create_failing_storage_scope(),
        file_manager=file_manager or ProjectFilesManager(Path()),
        project_id=project_id or "",
        settings=settings or Settings(glow_solution_definition="", glow_ui_module=""),
    )


def test_project_directory():
    project = "test_project"
    projects = Path("projects")
    ctx = _create_context(file_manager=ProjectFilesManager(projects), project_id=project)

    assert ctx.project_directory == projects / project


def test_solution():
    solution = {"key": "value"}
    ctx = _create_context(solution)

    assert ctx.solution == solution


def test_steps():
    solution = {"steps": {"step1": "value1", "step2": "value2"}}
    ctx = _create_context(solution)

    assert ctx.steps == solution["steps"]


def test_get_path_from_entity_handle(tmp_path: Path):
    with _create_storage_scope(tmp_path) as storage_scope:
        file = storage_scope.get_storage_root() / "test_file.txt"
        file.write_text("test content")
        entity_handle = storage_scope.store(file)

        ctx = _create_context(project_storage_scope=storage_scope)
        assert ctx.get_path_from_entity_handle(entity_handle.model_dump()) == file


def test_get_path_from_no_entity_entity_handle():
    ctx = _create_context()

    assert ctx.get_path_from_entity_handle(NO_ENTITY.model_dump()) is None


def test_create_entity_handle(tmp_path: Path):
    content = "test content"
    file = tmp_path / "test_file.txt"
    file.write_text(content)

    with _create_storage_scope(tmp_path / "bdm") as storage_scope:
        ctx = _create_context(project_storage_scope=storage_scope)

        entity_handle = ctx.create_entity_handle(file)

        file.unlink()

        handle = EntityHandle.model_validate(entity_handle)
        assert storage_scope.get_text(handle) == content


def test_create_entity_handle_file_exists_raises_helpful_exception_if_target_already_exists(tmp_path: Path):
    """Test that creating an entity handle raises a helpful exception if the target already exists."""

    file = tmp_path / "test_file.txt"
    file.write_text("test content")

    with _create_storage_scope(tmp_path / "bdm") as storage_scope:
        ctx = _create_context(project_storage_scope=storage_scope)

        ctx.create_entity_handle(file)

        with pytest.raises(
            FileExistsError,
            match="An entity already exists at the requested target path: test_file.txt.",
        ):
            ctx.create_entity_handle(file)


def test_create_entity_handle_nested_target_path(tmp_path: Path):
    content = "test content"
    file = tmp_path / "test_file.txt"
    file.write_text(content)

    with _create_storage_scope(tmp_path / "bdm") as storage_scope:
        ctx = _create_context(project_storage_scope=storage_scope)

        entity_handle = ctx.create_entity_handle(file, Path("a/b.txt"))

        file.unlink()

        handle = EntityHandle.model_validate(entity_handle)
        assert storage_scope.get_text(handle) == content
        file_copy = storage_scope.get_cached(handle)
        assert file_copy.name == "b.txt"
        assert file_copy.parent.name == "a"


def test_create_entity_handle_file_exists_raises_helpful_exception_if_source_does_not_exist(tmp_path: Path):
    with _create_storage_scope(tmp_path) as storage_scope:
        ctx = _create_context(project_storage_scope=storage_scope)

        with pytest.raises(FileNotFoundError, match="Entity JUNK does not exist."):
            ctx.create_entity_handle(Path("JUNK"))


def test_create_entity_handle_with_directory_source(tmp_path: Path):
    content = "test content"
    sub_dir = tmp_path / "test_dir"
    sub_dir.mkdir()
    file = sub_dir / "test_file.txt"
    file.write_text(content)

    with _create_storage_scope(tmp_path / "bdm") as storage_scope:
        ctx = _create_context(project_storage_scope=storage_scope)

        entity_handle = ctx.create_entity_handle(sub_dir)

        file.unlink()

        handle = EntityHandle.model_validate(entity_handle)
        dir_copy = storage_scope.get_cached(handle)
        assert dir_copy.is_dir()
        assert (dir_copy / "test_file.txt").read_text() == content
