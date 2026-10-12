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

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._bdm.subsystem_scope import SubsidiarySystemStorageScope

DATA_REPO_NO_ENTITY_ERROR_MSG = "entity does not exist"  # same as BDM uses
# To initialize the subsidiary system
DEFAULT_GLOW_DATA_REPOSITORY_UPLOAD_ROOT = "/Data"


class DataRepositoryType(Enum):
    FileSystem = "FileSystem"
    Minerva = "Minerva"


class DataRepository(ABC):
    @abstractmethod
    def upload(
        self,
        entity_handle: EntityHandle,
        target_path: str | None = None,
        metadata: str | None = None,
    ) -> EntityHandle:
        """Stores a blob or directory referenced by an entity handle in the data repository. Returns a handle to the
        copy in the data repository. Optional target_path argument which indicates the location for the file in the data
        repository.

        If a blob exists at the target location:
        - and the supplied handle refers to a blob, then a new version of the blob is created in the data repository
        and the method returns a handle referring to the new version.
        - and the supplied handle refers to a directory, then an exception is thrown.

        If a directory exists at the target location:
        - and the supplied handle refers to a blob, then an exception is thrown.
        - and the supplied handle refers to a directory, behaviour depends on the specifics of the backend used.

        The entity handle can refer to an entity already in the data repository in which case another copy of the
        referenced entity is created in the data repository at the target path. If the entity handle refers to the
        latest version at the target path, then no copy takes place and upload simply returns the supplied entity
        handle.
        """
        ...

    @abstractmethod
    def get_entity_handle(self, target_path: str, version: str | None = None) -> EntityHandle:
        """Returns handle to the data stored at target path. Optional version identifier. If the version identifier
        is not supplied, then the latest version is returned. Returns an entity handle if the requested
        blob / directory exists or NO_ENTITY otherwise.
        """
        ...

    @abstractmethod
    def query(self, value: str) -> list[EntityHandle]:
        """Queries items at the data repository based on the input value string and returns a list of handles
        pointing to the entities that fulfill such query.
        """
        ...


class DataRepoSystemStorageScope(SubsidiarySystemStorageScope):
    @abstractmethod
    def upload(
        self,
        source_path: Path,
        target_path: str | None = None,
        metadata: str | None = None,
    ) -> EntityHandle: ...

    @abstractmethod
    def get_entity_handle(self, target_path: str, version: str | None = None) -> EntityHandle: ...

    @abstractmethod
    def query(self, value: str) -> list[EntityHandle]: ...


class IItemProperties(Protocol):
    """Interface to define the properties of an item stored at the data repository."""

    is_directory: bool
    name: str
    modified_on: str
    locator: str
    revision: str
    branch: str
    mime_type: str | None
    size: int | None
    checksum: str | None
    path: str
    url: str
    is_latest: bool
    state: str


class ItemResult(BaseModel):
    """Define the result fields from Minerva required for building entity handle."""

    branch: str
    major_rev: str
    classification: str
    file_size: int | None = None  # default for directories
    id: str
    name: str


class IClient(Protocol):
    def list_files_by_id(self, remote_id: str) -> list[dict[str, Any]]: ...

    def list_files_by_remote_path(self, remote_directory: str) -> list[dict[str, Any]]: ...

    def get_item_by_id(self, remote_id: str, item_type: str = "Ans_Data") -> dict[str, Any]: ...

    def get_item_by_remote_path(self, remote_path: str, version: str | None = None) -> dict[str, Any]: ...

    def upload(self, remote_root: str = "/Data") -> list[IItemProperties]: ...

    def download(self, remote_path: str, version: str | None = None) -> list[IItemProperties]: ...

    def search_items_using_aml(self, query: str) -> list[dict[str, Any]]: ...

    def get_metadata_by_id(self, remote_id: str) -> dict[str, Any]: ...

    def list_versions(self, remote_id: str) -> list[str]: ...
