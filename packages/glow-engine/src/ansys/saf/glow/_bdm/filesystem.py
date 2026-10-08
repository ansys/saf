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

import contextlib
from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from ansys.bdm.api import (
    NO_ENTITY,
    EntityHandle,
    IAsyncReadStorageScope,
    IReadStorageScope,
    IReadStorageScopeFactory,
)
from ansys.saf.glow._bdm.datarepo import (
    DataRepository,
    IClient,
    IItemProperties,
    ItemResult,
)
from ansys.saf.glow._bdm.minerva import MinervaSubsidiarySystemStorageScope
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, PROJECT_NAME, ROOT
from ansys.saf.glow._bdm.subsystem_names import DATA_REPOSITORY_BDM_SYSTEM_NAME
from ansys.saf.glow._bdm.subsystem_scope import AsyncProxySubsidiarySystemStorageScope
from ansys.saf.glow._server.hidden_project_directories import bdm_minerva_working_dir_name

if TYPE_CHECKING:
    from ansys.iam.oidc import OidcClient
    from ansys.saf.glow._bdm.multiplexor import BdmMultiplexor

Param = ParamSpec("Param")
RetType = TypeVar("RetType")

logger = logging.getLogger(__name__)


@dataclass
class FileSystemItemProperties(IItemProperties):
    is_directory: bool
    name: str
    modified_on: str
    locator: str
    revision: str
    branch: str
    size: int | None
    path: str
    url: str
    is_latest: bool
    state: str
    mime_type: str | None = None
    checksum: str | None = None


class FileSystemMinervaMockClient(IClient):
    """Mock client to minerva for interacting with files and folders from the file system."""

    def __init__(self, data_repo_path: Path, working_dir: Path):
        self._data_repo_path = data_repo_path
        self._working_dir = working_dir

    def list_files_by_id(self, remote_id: str) -> list[dict[str, Any]]:
        # in filesystem, id = <remote_path> + ?version=<version>
        if "?version=" not in remote_id:
            raise ValueError("A remote id must be a string of the form '<remote_path>?version=<version>'")
        remote_directory, _ = remote_id.split("?version=")
        return self.list_files_by_remote_path(remote_directory)

    def list_files_by_remote_path(self, remote_directory: str) -> list[dict[str, Any]]:
        parent_path = self._data_repo_path / remote_directory.removeprefix("/")
        children = [
            self.get_item_by_remote_path("/" + child.relative_to(self._data_repo_path).as_posix())
            for child in parent_path.iterdir()
        ]
        return children

    def get_item_by_id(self, remote_id: str, item_type: str = "Ans_Data") -> dict[str, Any]:
        # in filesystem, id = <remote_path> + ?version=<version>
        if "?version=" not in remote_id:
            raise ValueError("A remote id must be a string of the form '<remote_path>?version=<version>'")
        remote_path, version = remote_id.split("?version=")
        return self.get_item_by_remote_path(remote_path, version)

    def get_item_by_remote_path(self, remote_path: str, version: str | None = None) -> dict[str, Any]:
        item_path = self._data_repo_path / remote_path.removeprefix("/")
        resolved_path = item_path
        if version is None:
            version = "001"
        if (item_path / "001_default").is_file():
            # item is a file
            resolved_path = item_path / "001_default" if version == "001" else item_path / f"{version}"
        elif item_path.is_dir() and version != "001":
            # item is a directory with unsupported version or item_path does not exist
            raise ValueError("Directory versioning is not supported yet: directory version must be 001.")
        if (
            not resolved_path.exists()
            or resolved_path == self._data_repo_path
            or resolved_path == self._data_repo_path / "Data"
        ):
            # Minerva doesn't allow to get properties of / nor /Data.
            raise ValueError(f"No item could be found: {remote_path}")
        return {
            "classification": "Folder" if resolved_path.is_dir() else "File",
            "name": item_path.name,
            "modified_on": str(resolved_path.stat().st_mtime),
            "id": f"{remote_path}?version={version}",
            "path": remote_path.removesuffix("/").removesuffix(item_path.name),
            "is_latest": True,
            "state": "In Work",
            "major_rev": version,
            "branch": "Default",
            "url": "is-local",
            "file_size": resolved_path.stat().st_size if not resolved_path.is_dir() else None,
        }

    def get_metadata_by_id(self, remote_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def list_versions(self, remote_id: str) -> list[str]:
        raise NotImplementedError

    def _convert_item_result_to_properties(self, item_result: dict[str, Any]) -> FileSystemItemProperties:
        # Minerva CLI returns different Item objects that Minerva HTTP-based searches. We mimic that behaviour by
        # converting the item result from get_item_* to a new item properties that is returned by "CLI"-based
        # methods such as upload, download, etc.
        modified_item_result = item_result.copy()
        modified_item_result["is_directory"] = item_result["classification"] == "Folder"
        modified_item_result["revision"] = item_result["major_rev"]
        modified_item_result["path"] = f"{item_result['path']}{item_result['name']}"
        modified_item_result["locator"] = item_result["id"]
        modified_item_result["size"] = item_result["file_size"]
        del modified_item_result["classification"]
        del modified_item_result["major_rev"]
        del modified_item_result["id"]
        del modified_item_result["file_size"]
        return FileSystemItemProperties(**modified_item_result)

    def _compare_files(self, filepath1: Path, filepath2: Path) -> bool:
        def file_hash(filepath: Path) -> str:
            hasher = hashlib.md5(usedforsecurity=False)
            with filepath.open("rb") as f:
                for buffer in iter(lambda: f.read(4096), b""):
                    hasher.update(buffer)
            return hasher.hexdigest()

        if not filepath1.exists() or not filepath2.exists():
            return False
        return file_hash(filepath1) == file_hash(filepath2)

    def _create_or_update_default_file_version(self, filepath: Path, target_filepath: Path) -> tuple[Path, Path]:
        # convert my/path/test.txt to my/path/test.txt/001_default
        destination = target_filepath / "001_default"
        destination.unlink(missing_ok=True)
        logger.debug(f"Moving {filepath} to {destination}")
        shutil.move(filepath, destination)
        # metadata management
        metadata_filepath = filepath.with_suffix(".metadata")
        metadata_destination = destination.with_suffix(".metadata")
        if metadata_filepath.exists():
            # if there is metadata copy my/path/test.metadata to my/path/test.txt/001_default.metadata
            logger.debug(f"Moving metadata {metadata_filepath} to {metadata_destination}")
            shutil.move(metadata_filepath, metadata_destination)
        elif metadata_destination.exists():
            # if a file previously uploaded with metadata is now uploaded without metadata, we need to
            # remove 001_default.metadata so that 001_default keeps corresponding to the last upload.
            metadata_destination.unlink()

        return destination, metadata_destination

    def _create_new_file_version(self, destination: Path, metadata_destination: Path, target_filepath: Path) -> str:
        versions = [str(f.name) for f in target_filepath.glob("001.*") if f.is_file() and f.suffix != ".metadata"]
        last_version = max([version.split(".")[-1] for version in versions]) if versions else "000"
        last_version_destination = target_filepath / f"001.{last_version}"
        if self._compare_files(destination, last_version_destination):
            # In Minerva, when uploading a file that is equal to its last version (path and content) the version is
            # not updated, but the metadata is overwritten.
            if metadata_destination.exists():
                # overwrite metadata version:
                # copy 001_default.metadata to 001.00x.metadata
                shutil.copy(
                    metadata_destination,
                    target_filepath / f"001.{last_version}.metadata",
                )
            return f"001.{last_version}"
        else:
            new_version = str(int(last_version) + 1).zfill(3)
            # update version:
            # copy 001_default to 001.00x
            shutil.copy(destination, target_filepath / f"001.{new_version}")
            if metadata_destination.exists():
                # update metadata version:
                # copy 001_default.metadata to 001.00x.metadata
                shutil.copy(
                    metadata_destination,
                    target_filepath / f"001.{new_version}.metadata",
                )
            return f"001.{new_version}"

    def upload(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        remote_root: str = "/Data",
    ) -> list[FileSystemItemProperties]:
        item_properties: list[FileSystemItemProperties] = []
        root_dir = self._working_dir / remote_root.removeprefix("/")
        for filepath in sorted(root_dir.rglob("*")):
            if filepath.suffix == ".metadata":
                continue
            relative_filepath = filepath.relative_to(root_dir)
            target_filepath = self._data_repo_path / remote_root.removeprefix("/") / relative_filepath
            if filepath.is_file():
                if not target_filepath.exists():
                    target_filepath.mkdir(exist_ok=True, parents=True)
                destination, metadata_destination = self._create_or_update_default_file_version(
                    filepath,
                    target_filepath,
                )
                version = self._create_new_file_version(destination, metadata_destination, target_filepath)
            else:
                destination = target_filepath
                destination.mkdir(parents=True, exist_ok=True)
                version = None
            relative_remote_path = destination.relative_to(self._data_repo_path)
            # convert back /my/path/test.txt/001_default to /my/path/test.txt
            remote_path = relative_remote_path if filepath.is_dir() else relative_remote_path.parent
            item_property = self._convert_item_result_to_properties(
                self.get_item_by_remote_path("/" + remote_path.as_posix(), version),
            )
            item_properties.append(item_property)

        with contextlib.suppress(ValueError):
            parent_item_properties = self._convert_item_result_to_properties(self.get_item_by_remote_path(remote_root))
            item_properties.append(parent_item_properties)

        return item_properties

    def download(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        remote_path: str,
        version: str | None = None,
    ) -> list[FileSystemItemProperties]:
        path = self._data_repo_path / remote_path.removeprefix("/")
        item_properties: list[FileSystemItemProperties] = []
        if version is None or version == "001":
            version = "001_default"
        for filepath in sorted(path.rglob("*")):
            relative_path = filepath.relative_to(self._data_repo_path)
            if filepath.is_dir() and not (filepath / "001_default").is_file():
                destination = self._working_dir / relative_path
                logger.debug(f"Copying {filepath} into {destination}")
                destination.mkdir(exist_ok=True, parents=True)
            elif filepath.name == version:
                relative_path = relative_path.parent
                destination = self._working_dir / relative_path
                destination.parent.mkdir(exist_ok=True, parents=True)
                logger.debug(f"Copying {filepath} into {destination}")
                shutil.copyfile(filepath, destination)
            else:
                # a non versioned file or a different version of the file
                continue
            item_property = self._convert_item_result_to_properties(
                self.get_item_by_remote_path(
                    remote_path=f"/{relative_path.as_posix()}",
                    version=version.removesuffix("_default"),
                ),
            )
            item_properties.append(item_property)
        return item_properties

    def search_items_using_aml(self, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class FileSystemMinervaMockSubsidiarySystemStorageScope(MinervaSubsidiarySystemStorageScope):
    def __init__(
        self,
        minerva_local_working_dir: Path,
        project_id: str,
        project_name: str,
        upload_root: str,
        data_repo_path: Path,
        filesystem_client: FileSystemMinervaMockClient,
        oidc_client: OidcClient,
        access_token: str = "",
        filesystem_data_repository_query_map: dict[str, list[tuple[str, str]]] | None = None,
    ):
        super().__init__(
            local_working_dir=minerva_local_working_dir,
            project_id=project_id,
            project_name=project_name,
            upload_root=upload_root,
            oidc_client=oidc_client,
            access_token=access_token,
        )
        self._filesystem_client = filesystem_client
        self._data_repo_path = data_repo_path
        self._filesystem_data_repository_query_map = filesystem_data_repository_query_map

    @property
    def client(self) -> IClient:
        return self._filesystem_client

    def upload(self, source_path: Path, target_path: str | None = None, metadata: str | None = None) -> EntityHandle:
        # wipe out existing content to avoid uploading existing downloaded items
        if self._local_working_dir.exists():
            shutil.rmtree(self._local_working_dir)
        return super().upload(source_path, target_path, metadata)

    def _create_item_result_from_filesystem_target_path(self, target_path: str, version: str) -> ItemResult:
        if not target_path.startswith("/"):
            target_path = (self._upload_root / self._project_name / target_path).as_posix()
        abs_path = self._data_repo_path / target_path.removeprefix("/")
        identifier = target_path + f"?version={version}"
        if not abs_path.exists():
            raise FileNotFoundError(f"Could not create ItemResult. File does not exist: {abs_path}")
        is_blob = abs_path.is_file()
        size: int | None = None
        if is_blob:
            size = abs_path.stat().st_size
        return ItemResult(
            branch="no_branch",
            major_rev=version,
            classification="File/Other/Other" if is_blob else "Folder",
            file_size=size,
            id=identifier,
            name=abs_path.name,
        )

    def query(self, value: str) -> list[EntityHandle]:
        if self._filesystem_data_repository_query_map is None:
            raise AttributeError("Solution configuration must include a 'filesystem_data_repository_query_map' field")
        mock_results = self._filesystem_data_repository_query_map.get(value, [])
        items = [self._create_item_result_from_filesystem_target_path(path, version) for path, version in mock_results]
        return [self._create_handle_from_minerva_item_result(item) for item in items]

    @property
    def asynchronous(self) -> IAsyncReadStorageScope:
        return AsyncProxySubsidiarySystemStorageScope(self)


class FileSystemMinervaMockDataRepository(DataRepository):
    def __init__(self, multiplexor: BdmMultiplexor):
        data_repo_scope = multiplexor.subsidiary_storage_scopes.get(DATA_REPOSITORY_BDM_SYSTEM_NAME)
        if data_repo_scope is None or not isinstance(
            data_repo_scope,
            FileSystemMinervaMockSubsidiarySystemStorageScope,
        ):
            raise ValueError("The file system subsidiary storage scope cannot be found in the bdm multiplexor.")
        self._data_repo_scope = data_repo_scope
        self._multiplexor = multiplexor

    def upload(
        self,
        entity_handle: EntityHandle,
        target_path: str | None = None,
        metadata: str | None = None,
    ) -> EntityHandle:
        if entity_handle == NO_ENTITY:
            raise ValueError("NO_ENTITY handle cannot be uploaded.")
        filepath = self._multiplexor.get_cached(entity_handle)
        data_repo_handle = self._data_repo_scope.upload(filepath, target_path, metadata)
        return self._multiplexor.wrap_handle(DATA_REPOSITORY_BDM_SYSTEM_NAME, data_repo_handle)

    def get_entity_handle(self, target_path: str, version: str | None = None) -> EntityHandle:
        data_repo_handle = self._data_repo_scope.get_entity_handle(target_path, version)
        return (
            self._multiplexor.wrap_handle(DATA_REPOSITORY_BDM_SYSTEM_NAME, data_repo_handle)
            if data_repo_handle != NO_ENTITY
            else NO_ENTITY
        )

    def query(self, value: str) -> list[EntityHandle]:
        return [
            self._multiplexor.wrap_handle(DATA_REPOSITORY_BDM_SYSTEM_NAME, data_repo_handle)
            for data_repo_handle in self._data_repo_scope.query(value)
        ]


class FileSystemMinervaMockSubsidiarySystemStorageScopeFactory(IReadStorageScopeFactory):
    def __init__(
        self,
        data_repo_upload_root: str,
        oidc_client: OidcClient,
        filesystem_data_repository_query_map: dict[str, list[tuple[str, str]]] | None,
    ):
        self._data_repo_upload_root = data_repo_upload_root
        self._oidc_client = oidc_client
        self._filesystem_data_repository_query_map = filesystem_data_repository_query_map

    def create_storage_scope(
        self,
        context: str,
        template_vars: dict[str, str],
    ) -> IReadStorageScope:
        project_files_dir = template_vars[ROOT]
        project_id = template_vars[PROJECT_ID]
        project_name = template_vars[PROJECT_NAME]
        data_repo_path = Path(project_files_dir) / "filesystem"
        minerva_working_dir = Path(project_files_dir) / project_id / bdm_minerva_working_dir_name

        client = FileSystemMinervaMockClient(data_repo_path=data_repo_path, working_dir=minerva_working_dir)
        return FileSystemMinervaMockSubsidiarySystemStorageScope(
            minerva_local_working_dir=minerva_working_dir,
            project_id=project_id,
            project_name=project_name,
            upload_root=self._data_repo_upload_root,
            data_repo_path=data_repo_path,
            filesystem_client=client,
            oidc_client=self._oidc_client,
            filesystem_data_repository_query_map=self._filesystem_data_repository_query_map,
        )

    async def create_async_storage_scope(
        self,
        context: str,
        template_vars: dict[str, str],
    ) -> IAsyncReadStorageScope:
        return self.create_storage_scope(context=context, template_vars=template_vars).asynchronous
