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

import base64
import logging
from pathlib import Path
import shutil
from types import TracebackType
from typing import Self
import uuid
import zipfile

from pydantic import BaseModel

from ansys.bdm.api import (
    EntityHandle,
    IAsyncReadStorageScope,
    IReadStorageScope,
    IReadStorageScopeFactory,
)
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, ROOT, SHORTID
from ansys.saf.glow._bdm.subsystem_scope import (
    AsyncProxySubsidiarySystemStorageScope,
    SubsidiarySystemStorageScope,
)
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator
from ansys.saf.glow._server.hidden_project_directories import bdm_hps_cache_dir_name

logger = logging.getLogger(__name__)
_DEPRECATED_DELIMITER = "_?"


class HpsOpaqueIdentifier(BaseModel):
    version: str
    hps_project_identifier: str
    file_id: str
    hps_server_url: str | None
    client_id: str | None

    @classmethod
    def deserialize(cls, serialized_str: str) -> Self:
        # not sure why we would expect this prefix to reach here, in theory it's removed by the multiplexor...
        serialized_str = serialized_str.removeprefix("hps/")
        if _DEPRECATED_DELIMITER in serialized_str:
            # legacy format:
            # - "{hps_project_identifier}_?{file_id}_?{hps_server_url}_?{client_id}_?{kc_realm}_?{kc_relative_path}"
            # which then changed to
            # - "{hps_project_identifier}_?{file_id}_?{hps_server_url}_?{client_id}_?deprecated_kc_realm_?deprecated_kc_relative_path"  # noqa: E501
            hps_project_identifier, file_id, hps_server_url, client_id, _, _ = tuple(
                None if part == "None" else part for part in serialized_str.split(_DEPRECATED_DELIMITER)
            )
            return cls(
                version="2.0",
                hps_project_identifier=hps_project_identifier,  # type: ignore
                file_id=file_id,  # type: ignore
                hps_server_url=hps_server_url,
                client_id=client_id,
            )
        else:
            json_str = base64.b64decode(serialized_str.encode("utf-8")).decode("utf-8")
            return cls.model_validate_json(json_str)

    def serialize(self) -> str:
        base64_bytes = base64.b64encode(self.model_dump_json().encode("utf-8"))
        return base64_bytes.decode("utf-8")


class HpsSubsidiarySystemStorageScope(SubsidiarySystemStorageScope):
    def __init__(
        self,
        cache_dir: Path,
        hps_authenticator: IHpsAuthenticator,
        hps_server_url: str,
    ):
        self._cache_dir = cache_dir
        self._hps_authenticator = hps_authenticator
        self._hps_server_url = hps_server_url

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ):
        # InstanceManagerBase calls __exit__ twice,
        # on dispose() and on _set_product_storage_scopes(),
        # so the cache directory is already removed on the second call.
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir)

    def get_entity_handle(
        self,
        hps_project_identifier: str = "UNKNOWN",
        file_id: str = "",
        hps_server_url: str | None = None,
        client_id: str | None = None,
        is_an_output_dir: bool = False,
    ) -> EntityHandle:
        # we dynamically import so that the GLOW API doesn't force a HPS dependency
        from ansys.saf.glow._hps_parametric_studies.project_wrapper import HpsProject, HpsProjectWrapper

        project = HpsProjectWrapper(
            persisted_project=HpsProject(
                hps_project_identifier=hps_project_identifier,
                hps_server_url=hps_server_url or self._hps_server_url,
                client_id=client_id,
            ),
            hps_authenticator=self._hps_authenticator,
        )

        file = project.get_project_file(file_id)

        opaque_identifier = HpsOpaqueIdentifier(
            version="2.0",
            hps_project_identifier=hps_project_identifier,
            file_id=file_id,
            hps_server_url=hps_server_url,
            client_id=client_id,
        )

        is_blob = True
        original_name = Path(file.evaluation_path).name if file.evaluation_path else file.name
        size = file.size
        if is_an_output_dir:
            is_blob = False
            original_name = original_name.rstrip(".zip")
            size = None

        return EntityHandle(
            is_blob=is_blob,
            original_name=original_name,
            entity_id=uuid.uuid4(),
            opaque_identifier=opaque_identifier.serialize(),
            mime_type=None,
            encoding=None,
            size=size,
        )

    def _copy_project_entity(self, entity: EntityHandle, destination_dir: Path | None = None) -> Path:
        if entity.original_name is None:
            raise ValueError("Entity handle must have an original name.")

        # we dynamically import so that the GLOW API doesn't force a HPS dependency
        from ansys.saf.glow._hps_parametric_studies.project_wrapper import HpsProject, HpsProjectWrapper

        identifier_to_deserialize = entity.opaque_identifier
        is_dir = not entity.is_blob

        opaque_identifier = HpsOpaqueIdentifier.deserialize(identifier_to_deserialize)
        hps_project_identifier = opaque_identifier.hps_project_identifier
        file_id = opaque_identifier.file_id
        hps_server_url = opaque_identifier.hps_server_url
        client_id = opaque_identifier.client_id

        project = HpsProjectWrapper(
            persisted_project=HpsProject(
                hps_project_identifier=hps_project_identifier,  # pyright: ignore[reportArgumentType]
                hps_server_url=hps_server_url or self._hps_server_url,
                client_id=client_id,
            ),
            hps_authenticator=self._hps_authenticator,
        )

        if is_dir:
            if destination_dir is None:
                unique_dir_name = str(uuid.uuid4())
                extract_path = self._cache_dir / unique_dir_name
                extract_path.mkdir(parents=True, exist_ok=True)
            else:
                extract_path = destination_dir

            zip_path = project.copy_file(file_id, extract_path)  # pyright: ignore[reportArgumentType]
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_path)
            zip_path.unlink(missing_ok=True)
            return extract_path
        else:
            if destination_dir is None:
                destination_dir = (  # pyright: ignore[reportOperatorIssue, reportUnknownVariableType]
                    self._cache_dir / str(hash(hps_project_identifier)) / file_id
                )
                destination_dir.mkdir(parents=True, exist_ok=True)  # pyright: ignore[reportUnknownMemberType]

            return project.copy_file(
                file_id,  # pyright: ignore[reportArgumentType]
                destination_dir,  # pyright: ignore[reportUnknownArgumentType]
            )

    def get_cached(self, entity: EntityHandle) -> Path:
        return self._copy_project_entity(entity)

    def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        tmp_destination_dir = destination.parent / str(uuid.uuid4())
        tmp_destination_dir.mkdir(parents=True, exist_ok=True)

        file_copy = self._copy_project_entity(entity, tmp_destination_dir)

        shutil.move(file_copy, destination)
        tmp_destination_dir.rmdir()

    def get_children(self, entity: EntityHandle) -> list[EntityHandle]:
        return []

    def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        raise ValueError(f"{child_name} not found.")

    def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        return None

    def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        raise RuntimeError("Operation not allowed in the context of the HPS storage scope.")

    @property
    def asynchronous(self) -> IAsyncReadStorageScope:
        return AsyncHpsSubsidiarySystemStorageScope(self)


class AsyncHpsSubsidiarySystemStorageScope(AsyncProxySubsidiarySystemStorageScope):
    def __init__(self, sync_substorage_scope: HpsSubsidiarySystemStorageScope):
        # For now, let's simply use the sync sub storage scope until we have an async hps client
        super().__init__(sync_substorage_scope)
        self._sync_hps_storage_scope = sync_substorage_scope

    async def get_entity_handle(
        self,
        hps_project_identifier: str = "UNKNOWN",
        file_id: str = "",
        hps_server_url: str | None = None,
        client_id: str | None = None,
        is_an_output_dir: bool = False,
    ) -> EntityHandle:
        return self._sync_hps_storage_scope.get_entity_handle(
            hps_project_identifier=hps_project_identifier,
            file_id=file_id,
            hps_server_url=hps_server_url,
            client_id=client_id,
            is_an_output_dir=is_an_output_dir,
        )


class HpsSubsidiarySystemStorageScopeFactory(IReadStorageScopeFactory):
    def __init__(self, hps_authenticator: IHpsAuthenticator, hps_server_url: str):
        self._hps_authenticator = hps_authenticator
        self._hps_server_url = hps_server_url

    def create_storage_scope(self, context: str, template_vars: dict[str, str]) -> IReadStorageScope:
        project_files_dir = template_vars[ROOT]
        project_id = template_vars[PROJECT_ID]
        cache_dir = Path(project_files_dir) / project_id / bdm_hps_cache_dir_name / template_vars[SHORTID]
        return HpsSubsidiarySystemStorageScope(
            cache_dir=cache_dir,
            hps_authenticator=self._hps_authenticator,
            hps_server_url=self._hps_server_url,
        )

    async def create_async_storage_scope(
        self,
        context: str,
        template_vars: dict[str, str],
    ) -> IAsyncReadStorageScope:
        return self.create_storage_scope(context=context, template_vars=template_vars).asynchronous
