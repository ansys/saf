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

from __future__ import annotations

from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ansys.bdm.api import NO_ENTITY, EntityHandle, IStorageScope

if TYPE_CHECKING:
    from ansys.saf.glow._config.settings import Settings
    from ansys.saf.glow._server.project_files_manager import ProjectFilesManager


class MigrationContext:
    """This class defines the API to perform the migration of a solution and stores the solution to be migrated."""

    def __init__(
        self,
        solution: dict[str, Any],
        project_storage_scope: IStorageScope,
        file_manager: ProjectFilesManager,
        project_id: str,
        settings: Settings,
    ):
        self._solution = solution
        self._project_storage_scope = project_storage_scope
        self._file_manager = file_manager
        self._project_id = project_id
        self._settings = settings

    @property
    def project_directory(self) -> Path:
        """Return the root of the project directory."""
        return self._file_manager.get_project_files_dir(self._project_id)

    @property
    def solution(self) -> dict[str, Any]:
        """Returns the solution model in its JSON structure form,
        as it will be loaded into the database during migration.

        At the beginning of the migration process, this structure represents
        either the data loaded from the GLOW database during an upgrade,
        or the data parsed from a `.safx` file during an import.

        The migration transformation is expected to modify this structure
        so that it conforms to the target solution schema."""
        return self._solution

    @property
    def steps(self) -> dict[str, Any]:
        """Returns the solution steps model in its JSON structure form,
        as it will be loaded into the database during migration.

        At the beginning of the migration process, this structure represents
        either the data loaded from the GLOW database during an upgrade,
        or the data parsed from a `.safx` file during an import.

        The migration transformation is expected to modify this structure
        so that it conforms to the target solution schema."""
        return self._solution["steps"]

    def get_path_from_entity_handle(self, entity_handle: dict[str, Any]) -> Path | None:
        """Attempt to interpret the ``entity_handle`` argument as a ``EntityHandle``
        object, in its JSON structure form, and return the path to a
        copy of the entity or None if the handle is ``NO_ENTITY``.
        The entity should not be modified or deleted.

        Parameters
        ----------
        entity_handle : dict[str, Any]
            The entity handle in its JSON structure form.

        Returns
        -------
        Path | None
            The path to a copy of the entity if it exists, or None if the handle is NO_ENTITY.
            The entity should not be modified or deleted.
        """
        handle = EntityHandle(**entity_handle)
        if handle == NO_ENTITY:
            return None
        return self._project_storage_scope.get_cached(handle)

    def create_entity_handle(
        self,
        path_to_existing_entity: Path,
        target_relative_path: Path | None = None,
    ) -> dict[str, Any]:
        """Return an ``EntityHandle`` object, in its JSON structure form,
        pointing at a new copy of the referenced file or directory.
        This method performs a copy from a file anywhere accessible to the GLOW API server, into the BDM system.

        Parameters
        ----------
        path_to_existing_entity : Path
            The path to the existing file or directory that should be copied.
        target_relative_path : Path | None, optional
            The relative path where the new entity should be stored relative to the BDM storage scope root.
            If not provided, the name of the existing entity will be used as the target path.

        Returns
        -------
        dict[str, Any]
            The entity handle in its JSON structure form, pointing to the newly created entity.
        """
        target_relative_path = target_relative_path or Path(path_to_existing_entity.name)
        assert isinstance(path_to_existing_entity, Path), "The entity must be a Path object."  # noqa: S101  #nosec
        root = self._project_storage_scope.get_storage_root()
        target_path = root / target_relative_path
        if target_path.exists():
            raise FileExistsError(
                f"An entity already exists at the requested target path: {target_relative_path}.",
            )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        assert root.exists(), f"Project storage root {root} does not exist."  # noqa: S101  #nosec
        if not path_to_existing_entity.exists():
            raise FileNotFoundError(f"Entity {path_to_existing_entity} does not exist.")
        if path_to_existing_entity.is_file():
            shutil.copy(path_to_existing_entity, target_path)
        else:
            shutil.copytree(path_to_existing_entity, target_path)
        handle = self._project_storage_scope.store(target_path)
        result = handle.model_dump()
        return result


class MigrationTransformation(BaseModel):
    """This class defines a specific migration of the solution stored in the MigrationContext object."""

    def migrate(self, ctx: MigrationContext) -> None:
        """Modify the solution stored in a MigrationContext to achieve a certain migration."""
        raise NotImplementedError("Classes inheriting from MigrationTransformation must implement the migrate method.")


class Migration(BaseModel):
    """This class links a specific solution migration with the solution version to which this migration should be
    applied.
    """

    version: int
    migration_transformation: MigrationTransformation
