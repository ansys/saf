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
import logging
import mimetypes
from pathlib import Path
import shutil
from typing import TYPE_CHECKING
import uuid

from ansys.bdm.api import (
    NO_ENTITY,
    EntityHandle,
    IAsyncReadStorageScope,
    IReadStorageScope,
    IReadStorageScopeFactory,
)
from ansys.saf.glow._bdm.datarepo import (
    DATA_REPO_NO_ENTITY_ERROR_MSG,
    DataRepository,
    DataRepoSystemStorageScope,
    IClient,
    IItemProperties,
    ItemResult,
)
from ansys.saf.glow._bdm.storage_variable_names import ACCESS_TOKEN, PROJECT_ID, PROJECT_NAME, ROOT
from ansys.saf.glow._bdm.subsystem_names import DATA_REPOSITORY_BDM_SYSTEM_NAME
from ansys.saf.glow._bdm.subsystem_scope import AsyncProxySubsidiarySystemStorageScope
from ansys.saf.glow._server.hidden_project_directories import bdm_minerva_working_dir_name

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ansys.iam.oidc import OidcClient
    from ansys.saf.glow._bdm.multiplexor import BdmMultiplexor

logger = logging.getLogger(__name__)


class MinervaSubsidiarySystemStorageScope(DataRepoSystemStorageScope):
    def __init__(
        self,
        local_working_dir: Path,
        project_id: str,
        project_name: str,
        upload_root: str,
        oidc_client: OidcClient,
        access_token: str = "",
    ):
        self._local_working_dir = local_working_dir
        self._project_id = project_id
        self._project_name = f"{project_name} ({project_id})"
        self._upload_root = Path(upload_root)
        self._oidc_client = oidc_client
        self._access_token = access_token
        self._client = None

    @property
    def client(self) -> IClient:
        # deliberate import here because minerva_python_client is an optional dependency
        try:
            from ansys.minerva_python_client.client import (  # pyright: ignore[reportMissingImports]
                MinervaClient,  # pyright: ignore[reportUnknownVariableType]
            )
        except ImportError as ex:
            raise ImportError(
                "The ansys-minerva-python-client package is required to use Minerva as a data repository.",
            ) from ex

        if self._client is None:  # pyright: ignore[reportUnknownMemberType]
            if not self._access_token:
                username = None
            else:
                userinfo = self._oidc_client.get_user_info(self._access_token)
                username = userinfo.preferred_username if userinfo else None
            if username:
                logger.info(f"Logging to minerva by impersonating user: {username}.")
            self._client = MinervaClient(  # pyright: ignore[reportUnknownMemberType]
                working_dir=self._local_working_dir,
                impersonated_user=username,
            )
        return self._client  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    def _create_handle_from_minerva_item_properties(self, item_properties: IItemProperties):
        return EntityHandle(
            is_blob=not item_properties.is_directory,
            original_name=item_properties.name,
            entity_id=uuid.uuid4(),
            opaque_identifier=item_properties.locator.removesuffix("/local_file"),
            mime_type=item_properties.mime_type,
            size=item_properties.size,
        )

    def _create_handle_from_minerva_item_result(self, item_result: ItemResult):
        locator = f"Ans_Data/{item_result.id}" if type(self.client).__name__ == "MinervaClient" else item_result.id
        return EntityHandle(
            is_blob=item_result.classification != "Folder",
            original_name=item_result.name,
            entity_id=uuid.uuid4(),
            opaque_identifier=locator,
            size=item_result.file_size,
        )

    def _create_handle_from_local_path(
        self,
        file_system_root: Path,
        path: Path,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        identifier = str(path.relative_to(file_system_root).as_posix())
        is_blob = path.is_file()
        size: int | None = None
        if is_blob:
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(path, False)
            size = path.stat().st_size
        return EntityHandle(
            is_blob=is_blob,
            original_name=path.name,
            entity_id=uuid.uuid4(),
            opaque_identifier=identifier,
            mime_type=mime_type,
            size=size,
            encoding=encoding,
        )

    def upload(  # noqa: C901
        self,
        source_path: Path,
        target_path: str | None = None,
        metadata: str | None = None,
    ) -> EntityHandle:
        if target_path is None:
            target_path = source_path.name

        if not target_path.startswith("/"):
            # relative path: put files in project_files/<project_id>/minerva/<upload_root>/<project_name>/<target_path>
            target_path = (self._upload_root / f"{self._project_name}/{target_path}").as_posix()
        local_destination = self._local_working_dir / target_path.removeprefix("/")

        # Check if an item with such target_path already exists in Minerva or locally, and if it's compatible
        item_result: ItemResult | None = None
        with contextlib.suppress(ValueError):
            item_result = ItemResult.model_validate(self.client.get_item_by_remote_path(target_path))
        if source_path.is_file() and (
            (item_result and item_result.classification == "Folder") or local_destination.is_dir()
        ):
            raise ValueError(f"Directory already exists at {target_path}.")
        elif source_path.is_dir() and (
            (item_result and item_result.classification != "Folder") or local_destination.is_file()
        ):
            raise ValueError(f"File exists at {target_path}.")

        # Copy first source_path to local data repository path
        local_destination.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Copying {source_path} to {local_destination}")
        if source_path.is_file():
            shutil.copy2(source_path, local_destination)
        else:
            shutil.copytree(source_path, local_destination)

        local_metadata = local_destination.with_suffix(".metadata")
        if metadata:
            if local_destination.is_dir():
                # Confirmed by Minerva team that this is a file-only feature.
                raise ValueError("Can't upload metadata for a directory.")
            local_metadata.write_text(metadata)
        elif local_metadata.is_file():
            # in the case of re-uploads where posterior uploads don't have metadata.
            local_metadata.unlink()

        # upload contains a list of item properties for each directory, subdirectory and file created...
        # so let's find the proper entity handle to return
        target_root_dir = f"{target_path.removeprefix('/').split('/')[0]}"
        local_path = self._local_working_dir / target_root_dir
        logger.info(f"Uploading {local_path} to minerva")
        item_properties_list = self.client.upload(
            remote_root=f"/{target_root_dir}",
        )
        uploaded_item_properties = next(
            (item_properties for item_properties in item_properties_list if item_properties.path == target_path),
            None,
        )
        if uploaded_item_properties:
            return self._create_handle_from_minerva_item_properties(uploaded_item_properties)
        if source_path.is_dir():
            # In case a modified folder is re-uploaded, the return value of the upload
            # contains only the files within the folder (because the folder is not re-uploaded)
            uploaded_item_result = self.client.get_item_by_remote_path(target_path)
            return self._create_handle_from_minerva_item_result(ItemResult.model_validate(uploaded_item_result))
        raise ValueError(f"Something went wrong when uploading files in {target_path}")

    def get_entity_handle(self, target_path: str, version: str | None = None) -> EntityHandle:
        if not target_path.startswith("/"):
            # insert upload root and project name if relative path
            target_path = (self._upload_root / f"{self._project_name}/{target_path}").as_posix()
        try:
            item_result = self.client.get_item_by_remote_path(target_path, version=version)
        except ValueError as ex:
            if "No item could be found" in str(ex):
                return NO_ENTITY
            else:
                raise
        return self._create_handle_from_minerva_item_result(ItemResult.model_validate(item_result))

    def query(self, value: str) -> list[EntityHandle]:
        results = self.client.search_items_using_aml(value)
        return [self._create_handle_from_minerva_item_result(ItemResult.model_validate(result)) for result in results]

    def get_cached(self, entity: EntityHandle) -> Path:
        minerva_id = entity.opaque_identifier.removeprefix("Ans_Data/")
        if entity.original_name is None:
            raise ValueError("Entity handle must have an original name.")
        item_result = self.client.get_item_by_id(minerva_id)
        remote_path = f"{item_result['path']}{item_result['name']}"
        self.client.download(
            remote_path=remote_path,
            version=item_result["major_rev"],
        )
        relative_path = remote_path.removeprefix("/")
        return Path(self._local_working_dir) / relative_path

    def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        handle_path = self.get_cached(entity)
        if not handle_path.exists():
            raise ValueError(DATA_REPO_NO_ENTITY_ERROR_MSG)

        if handle_path.is_file():
            shutil.copy(handle_path, destination)
        else:
            shutil.copytree(handle_path, destination)

    def get_children(self, entity: EntityHandle) -> list[EntityHandle]:
        if entity.original_name is None:
            raise ValueError("Entity handle must have an original name.")

        minerva_id = entity.opaque_identifier.removeprefix("Ans_Data/")
        children = self.client.list_files_by_id(minerva_id)
        return [self._create_handle_from_minerva_item_result(ItemResult.model_validate(child)) for child in children]

    def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        children = [child for child in self.get_children(entity) if child.original_name == child_name]

        if not children:
            raise ValueError(f"{child_name} not found")
        return children[0]

    def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        entity_path = self.get_cached(entity)
        if entity == NO_ENTITY or not entity_path.exists():
            raise ValueError(DATA_REPO_NO_ENTITY_ERROR_MSG)
        relative_path = entity_path.relative_to(self._local_working_dir)
        if len(relative_path.parts) == 1:
            return None
        return self._create_handle_from_local_path(self._local_working_dir, entity_path.parent)

    def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        raise RuntimeError("Operation not allowed in the context of the Minerva storage scope.")

    @property
    def asynchronous(self) -> IAsyncReadStorageScope:
        return AsyncMinervaSubsidiarySystemStorageScope(self)


class MinervaDataRepository(DataRepository):
    def __init__(self, multiplexor: BdmMultiplexor):
        data_repo_scope = multiplexor.subsidiary_storage_scopes.get(DATA_REPOSITORY_BDM_SYSTEM_NAME)
        if data_repo_scope is None or not isinstance(data_repo_scope, MinervaSubsidiarySystemStorageScope):
            raise ValueError("The minerva subsidiary storage scope cannot be found in the bdm multiplexor.")
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
        if target_path is None:
            target_path = self._multiplexor._get_relative_path(entity_handle)  # pyright: ignore[reportPrivateUsage]
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


class AsyncMinervaSubsidiarySystemStorageScope(AsyncProxySubsidiarySystemStorageScope):
    def __init__(self, sync_substorage_scope: MinervaSubsidiarySystemStorageScope):
        # For now, let's simply use the sync sub storage scope until we have an async minerva client
        super().__init__(sync_substorage_scope)
        self._sync_minerva_storage_scope = sync_substorage_scope

    async def upload(
        self,
        source_path: Path,
        target_path: str | None = None,
        metadata: str | None = None,
    ) -> EntityHandle:
        return self._sync_minerva_storage_scope.upload(
            source_path=source_path,
            target_path=target_path,
            metadata=metadata,
        )

    async def get_entity_handle(self, target_path: str, version: str | None = None) -> EntityHandle:
        return self._sync_minerva_storage_scope.get_entity_handle(target_path=target_path, version=version)

    async def query(self, value: str) -> AsyncIterator[EntityHandle]:
        for q in self._sync_minerva_storage_scope.query(value):
            yield q


class MinervaSubsidiarySystemStorageScopeFactory(IReadStorageScopeFactory):
    def __init__(self, data_repo_upload_root: str, oidc_client: OidcClient):
        self._data_repo_upload_root = data_repo_upload_root
        self._oidc_client = oidc_client

    def create_storage_scope(
        self,
        context: str,
        template_vars: dict[str, str],
    ) -> IReadStorageScope:
        project_files_dir = template_vars[ROOT]
        project_id = template_vars[PROJECT_ID]
        project_name = template_vars[PROJECT_NAME]
        access_token = template_vars[ACCESS_TOKEN]
        local_working_dir = Path(project_files_dir) / project_id / bdm_minerva_working_dir_name
        return MinervaSubsidiarySystemStorageScope(
            local_working_dir=local_working_dir,
            project_id=project_id,
            project_name=project_name,
            upload_root=self._data_repo_upload_root,
            oidc_client=self._oidc_client,
            access_token=access_token,
        )

    async def create_async_storage_scope(
        self,
        context: str,
        template_vars: dict[str, str],
    ) -> IAsyncReadStorageScope:
        sync_storage_scope = self.create_storage_scope(context=context, template_vars=template_vars)
        return sync_storage_scope.asynchronous
