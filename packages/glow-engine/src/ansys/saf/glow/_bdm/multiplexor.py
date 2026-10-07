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

import logging
from typing import TYPE_CHECKING, Generic, TypeVar

from ansys.bdm.api import (
    NO_ENTITY,
    EntityHandle,
    IAsyncEntityWriter,
    IAsyncReadStorageScope,
    IAsyncStorageScope,
    IEntityWriter,
    IReadStorageScope,
    IReadStorageScopeFactory,
    IStorageScope,
    IStorageScopeFactory,
)
from ansys.iam.oidc import OidcClient
from ansys.saf.glow._bdm.datarepo import DataRepositoryType
from ansys.saf.glow._bdm.filesystem import FileSystemMinervaMockSubsidiarySystemStorageScopeFactory
from ansys.saf.glow._bdm.hps_scope import HpsSubsidiarySystemStorageScopeFactory
from ansys.saf.glow._bdm.minerva import MinervaSubsidiarySystemStorageScopeFactory
from ansys.saf.glow._bdm.storage_factory import create_shared_storage_factory, random_shortid
from ansys.saf.glow._bdm.storage_variable_names import ACCESS_TOKEN, PROJECT_ID, PROJECT_NAME, ROOT, SHORTID
from ansys.saf.glow._bdm.subsystem_names import (
    ALL_SUBSYSTEMS,
    DATA_REPOSITORY_BDM_SYSTEM_NAME,
    HPS_BDM_SYSTEM_NAME,
    METHOD_ASSET_BDM_SYSTEM_NAME,
    PRIMARY_BDM_SYSTEM_NAME,
)
from ansys.saf.glow._bdm.subsystem_scope import (
    AssetSubsidiarySystemStorageScopeFactory,
    ProhibitedSubsidiarySystemStorageScopeFactory,
)
from ansys.saf.glow._hps_auth.hps_authenticator import (
    create_hps_authenticator,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from io import BufferedIOBase, RawIOBase
    from os import PathLike
    from pathlib import Path
    from types import TracebackType

    from anyio.abc import ByteReceiveStream, ByteSendStream

    from ansys.bdm.shared_volume.storage_factory import StorageScopeFactory
    from ansys.saf.glow._config.settings import Settings
    from ansys.saf.glow._core.solution import Solution


TStorageScope = TypeVar("TStorageScope", IStorageScope, IAsyncStorageScope)
TReadStorageScope = TypeVar("TReadStorageScope", IReadStorageScope, IAsyncReadStorageScope)

logger = logging.getLogger(__name__)


class BdmMultiplexorBase(Generic[TStorageScope, TReadStorageScope]):
    def __init__(self, primary_system_scope: TStorageScope, subsystem_scopes: dict[str, TReadStorageScope]):
        """The multiplexor provides a storage scope interface that is consumed by the application.
        It delegates operations to a set of subsidiary BDM systems that provide storage scope factories.
        The multiplexor adds and removes metadata to/ from the opaque identifier of an entity handle
        as the entity handles pass through the multiplexor interface.
        The metadata encodes which subsidiary BDM system contains the referenced blob
        to ensure that current and future get operations function as expected.

        Note that the multiplexor does not attempt to duplicate copies of blobs across the subsidiary systems.
        A handle only refers to one copy of the data in one specific subsidiary.

        Parameters:
        -----------
        primary_system_scope: IStorageScope | IAsyncStorageScope
            The bdm system used for storing files via the storage scope interface.

        subsystem_scopes: dict[str, IReadStorageScope | IAsyncReadStorageScope]
            A dictionary mapping the subsidiaries systems used as data sources with a given name.
        """
        self._primary_system_scope = primary_system_scope
        self._subsystem_scopes = subsystem_scopes
        self._bdm_system_names = [PRIMARY_BDM_SYSTEM_NAME, *self._subsystem_scopes]
        if any(name for name in self._bdm_system_names if "/" in name):
            raise ValueError("Subsystem names cannot contain the following character: '/'")

    def wrap_handle(self, bdm_system_name: str, entity_handle: EntityHandle) -> EntityHandle:
        """Convert a handle from a given bdm system into a handle supported by the multiplexor.

        Parameters:
        -----------
        bdm_system_name: str
            A string which identifies the bdm system that can realize the handle)
        entity_handle: EntityHandle
            An entity handle supported by the given scope factory.
        """
        if bdm_system_name not in self._bdm_system_names:
            raise ValueError(f"The BDM system '{bdm_system_name}' cannot be found.")
        return entity_handle.model_copy(
            update={"opaque_identifier": f"{bdm_system_name}/{entity_handle.opaque_identifier}"},
        )

    @property
    def subsidiary_storage_scopes(self) -> dict[str, TReadStorageScope]:
        return self._subsystem_scopes

    def _unwrap_handle(self, entity_handle: EntityHandle) -> tuple[EntityHandle, str]:
        if entity_handle == NO_ENTITY:
            # Let the primary system take responsibility for raising the right error messages
            return entity_handle, PRIMARY_BDM_SYSTEM_NAME
        bdm_system_name = entity_handle.opaque_identifier.split("/")[0]
        unwrapped_entity = entity_handle.model_copy(
            update={"opaque_identifier": entity_handle.opaque_identifier.removeprefix(f"{bdm_system_name}/")},
        )
        return unwrapped_entity, bdm_system_name

    def _get_system_scope(self, bdm_system_name: str) -> TReadStorageScope | TStorageScope:
        return (
            self._primary_system_scope
            if bdm_system_name == PRIMARY_BDM_SYSTEM_NAME
            else self._subsystem_scopes[bdm_system_name]
        )

    def _get_relative_path(self, entity_handle: EntityHandle) -> str | None:
        if entity_handle.opaque_identifier.startswith(PRIMARY_BDM_SYSTEM_NAME):
            relative_path = entity_handle.opaque_identifier.split(":_DELIMITER")[-1]
            return relative_path


class BdmMultiplexor(BdmMultiplexorBase[IStorageScope, IReadStorageScope], IStorageScope):
    def __init__(self, primary_system_scope: IStorageScope, subsystem_scopes: dict[str, IReadStorageScope]):
        super().__init__(primary_system_scope=primary_system_scope, subsystem_scopes=subsystem_scopes)

    def __enter__(self) -> IStorageScope:
        self._primary_system_scope.__enter__()
        for subsystem_scope in self._subsystem_scopes.values():
            subsystem_scope.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._primary_system_scope.__exit__(exc_type, exc_value, traceback)
        for subsystem_scope in self._subsystem_scopes.values():
            subsystem_scope.__exit__(exc_type, exc_value, traceback)

    def get_storage_root(self) -> Path:
        return self._primary_system_scope.get_storage_root()

    def get_cached(self, entity: EntityHandle) -> Path:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return self._get_system_scope(system_name).get_cached(unwrapped_entity)

    def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        self._get_system_scope(system_name).get_copy(entity=unwrapped_entity, destination=destination)

    def get_stream(self, entity: EntityHandle) -> RawIOBase:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return self._get_system_scope(system_name).get_stream(entity=unwrapped_entity)

    def get_bytes(self, entity: EntityHandle) -> bytes:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return self._get_system_scope(system_name).get_bytes(entity=unwrapped_entity)

    def get_text(self, entity: EntityHandle, encoding: str | None = None) -> str:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return self._get_system_scope(system_name).get_text(entity=unwrapped_entity, encoding=encoding)

    def store(self, from_: PathLike[str], mime_type: str | None = None, encoding: str | None = None) -> EntityHandle:
        entity_handle = self._primary_system_scope.store(from_=from_, mime_type=mime_type, encoding=encoding)
        return self.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, entity_handle)

    def store_stream(
        self,
        from_: RawIOBase | BufferedIOBase | bytes,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        entity_handle = self._primary_system_scope.store_stream(
            from_=from_,
            relative_location=relative_location,
            mime_type=mime_type,
            encoding=encoding,
        )
        return self.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, entity_handle)

    def begin_store(
        self,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> IEntityWriter:
        entity_writer = self._primary_system_scope.begin_store(
            relative_location=relative_location,
            mime_type=mime_type,
            encoding=encoding,
        )
        return self._PrimaryBdmEntityWriterWrapper(primary_bdm_entity_writer=entity_writer)

    @property
    def stored_entities(self) -> list[EntityHandle]:
        unwrapped_stored_entities = self._primary_system_scope.stored_entities
        return [self.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, entity_handle) for entity_handle in unwrapped_stored_entities]

    def destroy(self, *entities: EntityHandle) -> None:
        unwrapped_entities = [self._unwrap_handle(entity)[0] for entity in entities]
        self._primary_system_scope.destroy(*unwrapped_entities)

    def get_children(self, entity: EntityHandle) -> list[EntityHandle]:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return [
            self.wrap_handle(system_name, child)
            for child in self._get_system_scope(system_name).get_children(entity=unwrapped_entity)
        ]

    def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        unwrapped_child = self._get_system_scope(system_name).get_child(entity=unwrapped_entity, child_name=child_name)
        return self.wrap_handle(system_name, unwrapped_child)

    def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        unwrapped_parent = self._get_system_scope(system_name).get_parent(entity=unwrapped_entity)
        return self.wrap_handle(system_name, unwrapped_parent) if unwrapped_parent else None

    def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        primary_live_handles: list[EntityHandle] = []
        for live_handle in live_handles:
            unwrapped_handle, system_name = self._unwrap_handle(live_handle)
            if system_name == PRIMARY_BDM_SYSTEM_NAME:
                primary_live_handles.append(unwrapped_handle)
        unwrapped_unreferenced_entities = self._primary_system_scope.get_unreferenced_entities(
            context=context,
            live_handles=primary_live_handles,
        )
        return [
            self.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, unreferenced_entity)
            for unreferenced_entity in unwrapped_unreferenced_entities
        ]

    @property
    def asynchronous(self) -> IAsyncStorageScope:
        return AsyncBdmMultiplexor(
            self._primary_system_scope.asynchronous,  # pyright: ignore[reportArgumentType]
            {k: v.asynchronous for k, v in self._subsystem_scopes.items()},  # type: ignore
        )

    class _PrimaryBdmEntityWriterWrapper(IEntityWriter):
        def __init__(self, primary_bdm_entity_writer: IEntityWriter):
            self._primary_bdm_entity_writer = primary_bdm_entity_writer

        def __enter__(self) -> IEntityWriter:
            self._primary_bdm_entity_writer.__enter__()
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            self._primary_bdm_entity_writer.__exit__(exc_type, exc_value, traceback)

        @property
        def stream(self) -> RawIOBase:
            return self._primary_bdm_entity_writer.stream

        @property
        def handle(self) -> EntityHandle:
            entity_handle = self._primary_bdm_entity_writer.handle
            return entity_handle.model_copy(
                update={"opaque_identifier": f"{PRIMARY_BDM_SYSTEM_NAME}/{entity_handle.opaque_identifier}"},
            )


class AsyncBdmMultiplexor(BdmMultiplexorBase[IAsyncStorageScope, IAsyncReadStorageScope], IAsyncStorageScope):
    def __init__(self, primary_system_scope: IAsyncStorageScope, subsystem_scopes: dict[str, IAsyncReadStorageScope]):
        super().__init__(primary_system_scope=primary_system_scope, subsystem_scopes=subsystem_scopes)

    async def __aenter__(self) -> IAsyncStorageScope:
        await self._primary_system_scope.__aenter__()
        for subsystem_scope in self._subsystem_scopes.values():
            await subsystem_scope.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._primary_system_scope.__aexit__(exc_type, exc_value, traceback)
        for subsystem_scope in self._subsystem_scopes.values():
            await subsystem_scope.__aexit__(exc_type, exc_value, traceback)

    async def get_storage_root(self) -> Path:
        return await self._primary_system_scope.get_storage_root()

    async def get_cached(self, entity: EntityHandle) -> Path:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return await self._get_system_scope(system_name).get_cached(unwrapped_entity)

    async def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        await self._get_system_scope(system_name).get_copy(entity=unwrapped_entity, destination=destination)

    async def get_stream(self, entity: EntityHandle) -> ByteReceiveStream:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return await self._get_system_scope(system_name).get_stream(entity=unwrapped_entity)

    async def get_bytes(self, entity: EntityHandle) -> bytes:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return await self._get_system_scope(system_name).get_bytes(entity=unwrapped_entity)

    async def get_text(self, entity: EntityHandle, encoding: str | None = None) -> str:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        return await self._get_system_scope(system_name).get_text(entity=unwrapped_entity, encoding=encoding)

    async def store(
        self,
        from_: PathLike[str],
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        entity_handle = await self._primary_system_scope.store(from_=from_, mime_type=mime_type, encoding=encoding)
        return self.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, entity_handle)

    async def store_stream(
        self,
        from_: ByteReceiveStream | bytes,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        entity_handle = await self._primary_system_scope.store_stream(
            from_=from_,
            relative_location=relative_location,
            mime_type=mime_type,
            encoding=encoding,
        )
        return self.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, entity_handle)

    async def begin_store(
        self,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> IAsyncEntityWriter:
        entity_writer = await self._primary_system_scope.begin_store(
            relative_location=relative_location,
            mime_type=mime_type,
            encoding=encoding,
        )
        return self._AsyncPrimaryBdmEntityWriterWrapper(primary_bdm_entity_writer=entity_writer)

    async def get_stored_entities(self) -> AsyncIterator[EntityHandle]:
        async for unwrapped_entity in self._primary_system_scope.get_stored_entities():
            yield self.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, unwrapped_entity)

    async def destroy(self, *entities: EntityHandle) -> None:
        unwrapped_entities = [self._unwrap_handle(entity)[0] for entity in entities]
        await self._primary_system_scope.destroy(*unwrapped_entities)

    async def get_children(self, entity: EntityHandle) -> AsyncIterator[EntityHandle]:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        async for child in self._get_system_scope(system_name).get_children(entity=unwrapped_entity):
            yield self.wrap_handle(system_name, child)

    async def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        unwrapped_child = await self._get_system_scope(system_name).get_child(
            entity=unwrapped_entity,
            child_name=child_name,
        )
        return self.wrap_handle(system_name, unwrapped_child)

    async def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        unwrapped_entity, system_name = self._unwrap_handle(entity)
        unwrapped_parent = await self._get_system_scope(system_name).get_parent(entity=unwrapped_entity)
        return self.wrap_handle(system_name, unwrapped_parent) if unwrapped_parent else None

    async def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        primary_live_handles: list[EntityHandle] = []
        for live_handle in live_handles:
            unwrapped_handle, system_name = self._unwrap_handle(live_handle)
            if system_name == PRIMARY_BDM_SYSTEM_NAME:
                primary_live_handles.append(unwrapped_handle)
        unwrapped_unreferenced_entities = await self._primary_system_scope.get_unreferenced_entities(
            context=context,
            live_handles=primary_live_handles,
        )
        return [
            self.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, unreferenced_entity)
            for unreferenced_entity in unwrapped_unreferenced_entities
        ]

    async def get_synchronous(self) -> IStorageScope:
        return BdmMultiplexor(
            await self._primary_system_scope.get_synchronous(),  # pyright: ignore[reportArgumentType]
            {k: await v.get_synchronous() for k, v in self._subsystem_scopes.items()},  # type: ignore
        )

    class _AsyncPrimaryBdmEntityWriterWrapper(IAsyncEntityWriter):
        def __init__(self, primary_bdm_entity_writer: IAsyncEntityWriter):
            self._primary_bdm_entity_writer = primary_bdm_entity_writer

        async def __aenter__(self) -> IAsyncEntityWriter:
            await self._primary_bdm_entity_writer.__aenter__()
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            await self._primary_bdm_entity_writer.__aexit__(exc_type, exc_value, traceback)

        @property
        def stream(self) -> ByteSendStream:
            return self._primary_bdm_entity_writer.stream

        @property
        def handle(self) -> EntityHandle:
            entity_handle = self._primary_bdm_entity_writer.handle
            return entity_handle.model_copy(
                update={"opaque_identifier": f"{PRIMARY_BDM_SYSTEM_NAME}/{entity_handle.opaque_identifier}"},
            )


class MultiplexorStorageScopeFactory(IStorageScopeFactory):
    def __init__(
        self,
        primary_system_scope_factory: IStorageScopeFactory,
        subsystem_scope_factories: dict[str, IReadStorageScopeFactory],
    ):
        """
        A factory pattern for creating multiplexor instances of IStorageScope and IAsyncStorageScope.

        Parameters:
        -----------
        primary_system_scope_factory: IStorageScopeFactory | IAsyncStorageScopeFactory
            The bdm system scope factory used for creating the primary storage scopes.

        subsystem_scope_factories: dict[str, IReadStorageScopeFactory | IAsyncReadStorageScopeFactory]
            A dictionary mapping the subsidiaries system factories used as data sources with a given name.
        """
        self._primary_system_scope_factory = primary_system_scope_factory
        self._subsystem_scope_factories = subsystem_scope_factories

    def create_storage_scope(self, context: str, template_vars: dict[str, str]) -> BdmMultiplexor:
        primary_system = self._primary_system_scope_factory.create_storage_scope(context, template_vars)
        subsystems = {
            key: scope_factory.create_storage_scope(context, template_vars)
            for key, scope_factory in self._subsystem_scope_factories.items()
        }
        return BdmMultiplexor(primary_system, subsystems)

    async def create_async_storage_scope(self, context: str, template_vars: dict[str, str]) -> AsyncBdmMultiplexor:
        primary_system = await self._primary_system_scope_factory.create_async_storage_scope(context, template_vars)
        subsystems = {
            key: await scope_factory.create_async_storage_scope(context, template_vars)
            for key, scope_factory in self._subsystem_scope_factories.items()
        }
        return AsyncBdmMultiplexor(primary_system, subsystems)


class SafMultiplexorStorageScopeFactory:
    def __init__(
        self,
        project_files_dir: str,
        project_id: str,
        settings: Settings,
        short_id: str | None = None,
    ):
        self._template_vars = {
            ROOT: project_files_dir,
            PROJECT_ID: project_id,
            SHORTID: short_id or random_shortid(),
        }
        self._settings = settings
        self._primary_system_scope_factory: StorageScopeFactory = create_shared_storage_factory()
        self._subsystem_scope_factories: dict[str, IReadStorageScopeFactory] = {}
        for subsystem in ALL_SUBSYSTEMS:
            # Let's first assign all possible subsystems with a prohibited subsystem which raises
            # a proper error if used.
            self._subsystem_scope_factories[subsystem] = ProhibitedSubsidiarySystemStorageScopeFactory()

    def with_datarepo_storage_scope(
        self,
        project_display_name: str,
        access_token: str,
        filesystem_data_repository_query_map: dict[str, list[tuple[str, str]]] | None = None,
    ):
        self._template_vars[PROJECT_NAME] = project_display_name
        self._template_vars[ACCESS_TOKEN] = access_token
        oidc_client = OidcClient(
            issuer=self._settings.glow_auth_issuer_url,
            audience=self._settings.glow_auth_client_id,
        )
        match self._settings.glow_data_repository_type:
            case DataRepositoryType.FileSystem:
                logger.debug("Adding file system data repository subsystem storage scope")
                self._subsystem_scope_factories[DATA_REPOSITORY_BDM_SYSTEM_NAME] = (
                    FileSystemMinervaMockSubsidiarySystemStorageScopeFactory(
                        data_repo_upload_root=self._settings.glow_data_repository_upload_root,
                        oidc_client=oidc_client,
                        filesystem_data_repository_query_map=filesystem_data_repository_query_map,
                    )
                )
            case DataRepositoryType.Minerva:
                logger.debug("Adding minerva data repository subsystem storage scope")
                self._subsystem_scope_factories[DATA_REPOSITORY_BDM_SYSTEM_NAME] = (
                    MinervaSubsidiarySystemStorageScopeFactory(
                        data_repo_upload_root=self._settings.glow_data_repository_upload_root,
                        oidc_client=oidc_client,
                    )
                )
            case _:
                pass

    def with_asset_storage_scope(self, solution_type: type[Solution]):
        self._subsystem_scope_factories[METHOD_ASSET_BDM_SYSTEM_NAME] = AssetSubsidiarySystemStorageScopeFactory(
            solution_type=solution_type,
        )

    def with_hps_storage_scope(
        self,
        access_token: str | None = None,
    ):
        logger.debug("Adding hps subsystem storage scope")
        hps_authenticator = create_hps_authenticator(self._settings, access_token)
        self._subsystem_scope_factories[HPS_BDM_SYSTEM_NAME] = HpsSubsidiarySystemStorageScopeFactory(
            hps_authenticator=hps_authenticator,
            hps_server_url=self._settings.computed_glow_hps_url,  # type: ignore
        )

    def create_storage_scope(self, context: str):
        multiplexor = MultiplexorStorageScopeFactory(
            self._primary_system_scope_factory,
            self._subsystem_scope_factories,
        )
        return multiplexor.create_storage_scope(context, self._template_vars)

    async def create_async_storage_scope(self, context: str):
        multiplexor = MultiplexorStorageScopeFactory(
            self._primary_system_scope_factory,
            self._subsystem_scope_factories,
        )
        return await multiplexor.create_async_storage_scope(context, self._template_vars)
