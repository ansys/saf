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

from datetime import datetime
from io import BufferedIOBase, RawIOBase
import logging
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Self

import httpx2
from pydantic import FutureDate, TypeAdapter, ValidationError

from ansys.bdm.api import (
    EntityHandle,
    IAsyncStorageScope,
    IEntityWriter,
    IStorageScope,
)
from ansys.saf.glow._bdm.multiplexor import SafMultiplexorStorageScopeFactory
from ansys.saf.glow._bdm.storage_contexts import CLIENT_CONTEXT
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.client_exceptions import check

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from os import PathLike

future_date_validator: TypeAdapter[FutureDate] = TypeAdapter(FutureDate)


class ClientStorageScope(IStorageScope):
    def __init__(
        self,
        root_directory: str,
        http_client: httpx2.Client,
        project_url: str,
        project_display_name: str,
        settings: Settings,
        access_token: str | None = None,
        filesystem_data_repository_query_map: dict[str, list[tuple[str, str]]] | None = None,
    ):
        self._project_id = project_url.split("/")[-1]
        self._root_directory = root_directory
        self._bdm_locks_url = f"{project_url}/bdm-locks"
        self._http_client = http_client
        self._lock_id: str
        self._storage_scope: IStorageScope
        self._disposed: bool = False
        self._disabled_gc = settings.glow_bdm_gc_disabled
        self._settings = settings
        self._access_token = access_token
        self._project_display_name = project_display_name
        self._fs_datarepo_query_map = filesystem_data_repository_query_map

    def __enter__(self) -> Self:
        if not self._disabled_gc:
            response = self._http_client.post(f"{self._bdm_locks_url}")
            check(response)
            lock_model = response.json()
            self._lock_id = lock_model["id"]
            self._lock_exp = datetime.fromisoformat(lock_model["expiration_date"].replace("Z", "+00:00"))

        multiplexor_scope_factory = SafMultiplexorStorageScopeFactory(
            project_files_dir=str(self._root_directory),
            project_id=self._project_id,
            settings=self._settings,
        )

        multiplexor_scope_factory.with_datarepo_storage_scope(
            project_display_name=self._project_display_name,
            access_token=self._access_token or "",
            filesystem_data_repository_query_map=self._fs_datarepo_query_map,
        )
        multiplexor_scope_factory.with_hps_storage_scope(
            access_token=self._access_token,
        )

        self._storage_scope = multiplexor_scope_factory.create_storage_scope(
            CLIENT_CONTEXT,
        )
        self._storage_scope.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Remove all files from local storage that are not stored centrally."""
        self._storage_scope.__exit__(None, None, None)
        if not self._disabled_gc:
            response = self._http_client.delete(f"{self._bdm_locks_url}/{self._lock_id}")
            if not response.is_success:
                logger.error(
                    "An error occurred while removing the bdm lock for the client storage scope. "
                    "Garbage collection may be deferred until expiration of the lock.",
                )
        self._disposed = True

    def _check_bdm_locks(self) -> None:
        if not hasattr(self, "_storage_scope"):
            raise ValueError("The storage scope must be used with the 'with' statement.")
        if self._disposed:
            raise ValueError("The storage scope has been closed.")
        if not self._disabled_gc:
            try:
                future_date_validator.validate_python(self._lock_exp.date())
            except ValidationError as ex:
                raise ValueError(f"The storage scope client has expired. {ex}") from None

    def get_storage_root(self) -> Path:
        self._check_bdm_locks()
        return self._storage_scope.get_storage_root()

    def get_cached(self, entity: EntityHandle) -> Path:
        self._check_bdm_locks()
        return self._storage_scope.get_cached(entity)

    def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        self._check_bdm_locks()
        return self._storage_scope.get_copy(entity, destination)

    def get_stream(self, entity: EntityHandle) -> RawIOBase:
        self._check_bdm_locks()
        return self._storage_scope.get_stream(entity)

    def get_bytes(self, entity: EntityHandle) -> bytes:
        self._check_bdm_locks()
        return self._storage_scope.get_bytes(entity)

    def get_text(self, entity: EntityHandle, encoding: str | None = None) -> str:
        self._check_bdm_locks()
        return self._storage_scope.get_text(entity, encoding)

    def store(self, from_: "PathLike[str]", mime_type: str | None = None, encoding: str | None = None) -> EntityHandle:
        self._check_bdm_locks()
        return self._storage_scope.store(from_, mime_type, encoding)

    def store_stream(
        self,
        from_: RawIOBase | BufferedIOBase | bytes,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        self._check_bdm_locks()
        return self._storage_scope.store_stream(from_, relative_location, mime_type, encoding)

    def begin_store(
        self,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> IEntityWriter:
        self._check_bdm_locks()
        return self._storage_scope.begin_store(relative_location, mime_type, encoding)

    @property
    def stored_entities(self) -> list[EntityHandle]:
        self._check_bdm_locks()
        return self._storage_scope.stored_entities

    def destroy(self, *entity: EntityHandle) -> None:
        self._check_bdm_locks()
        return self._storage_scope.destroy(*entity)

    def get_children(self, entity: EntityHandle) -> list[EntityHandle]:
        self._check_bdm_locks()
        return self._storage_scope.get_children(entity)

    def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        self._check_bdm_locks()
        return self._storage_scope.get_child(entity, child_name)

    def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        self._check_bdm_locks()
        return self._storage_scope.get_parent(entity)

    def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        raise RuntimeError("Operation not allowed in the context of the client storage scope.")

    @property
    def asynchronous(self) -> IAsyncStorageScope:
        """
        Returns a object with an asynchronous interface to the same scope
        """
        raise RuntimeError("Operation not allowed in the context of the client storage scope.")
