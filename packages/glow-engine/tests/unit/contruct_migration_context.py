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

from ansys.bdm.shared_volume.entity_tracker import EntityTracker
from ansys.bdm.shared_volume.storage_configuration import (
    SharedFilesystemConfiguration,
    SharedFilesystemContextConfiguration,
)
from ansys.bdm.shared_volume.storage_scope import StorageScope
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.migrations import MigrationContext
from ansys.saf.glow._server.project_files_manager import ProjectFilesManager


def create_failing_storage_scope() -> StorageScope:
    return StorageScope(
        EntityTracker(
            "JUNK_CONTEXT",
            SharedFilesystemConfiguration(
                shared_filesystem_root=Path("JUNK_ROOT"),
                contexts={
                    "JUNK_CONTEXT": SharedFilesystemContextConfiguration(relative_path=Path("JUNK_RELATIVE_PATH")),
                },
            ),
        ),
    )


def get_construct_migration_context(project_files_dir: Path):
    """Returns a function that constructs a MigrationContext with the given project files directory."""

    def construct_migration_context(
        solution: dict[str, Any],
        project_directory: Path = project_files_dir,
    ) -> MigrationContext:
        return MigrationContext(
            solution=solution,
            project_storage_scope=create_failing_storage_scope(),
            file_manager=ProjectFilesManager(project_directory.parent),
            project_id=project_directory.name,
            settings=Settings(glow_solution_definition="", glow_ui_module=""),
        )

    return construct_migration_context
