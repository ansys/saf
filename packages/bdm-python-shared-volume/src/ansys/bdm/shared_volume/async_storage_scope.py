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

from collections.abc import AsyncIterator
import itertools
import os
from pathlib import Path
from types import TracebackType
import uuid

import aioshutil
import anyio
from anyio.abc import ByteReceiveStream, ByteSendStream
from anyio.streams.file import FileReadStream, FileWriteStream

from ansys.bdm.api import (
    NO_ENTITY,
    CannotGenerateStreamForDirectoryError,
    EntityHandle,
    EntityNotFoundInBlobStorageError,
    IAsyncEntityWriter,
    IAsyncStorageScope,
    IStorageScope,
    NotFoundInLocalStorageRootError,
)
from ansys.bdm.base.base_async_storage_scope import AsyncStorageScopeBase
from ansys.bdm.shared_volume.async_entity_writer import AsyncEntityWriter
from ansys.bdm.shared_volume.entity_tracker import EntityTracker
from ansys.bdm.shared_volume.identifier_parser import IdentifierParser


class AsyncStorageScope(AsyncStorageScopeBase):
    """A storage scope based on a shared folder globally available."""

    def __init__(self, entity_tracker: EntityTracker):
        self._entity_tracker = entity_tracker

    async def __aenter__(self) -> "IAsyncStorageScope":
        """track the set of files that are stored centrally"""
        return self

    async def __aexit__(
        self,
        __exc_type: type[BaseException] | None,  # noqa: PYI063
        __exc_value: BaseException | None,
        __traceback: TracebackType | None,
    ) -> None:
        """remove all files from local storage that are not stored centrally"""

        required_files = self._entity_tracker.required_files

        if not required_files:
            await aioshutil.rmtree(self._entity_tracker.get_storage_root())
            return

        # TODO - substitute an async equivalent of os.walk and delete in parallel
        for _, dirs, files in os.walk(self._entity_tracker.get_storage_root()):
            for filename in itertools.chain(files, dirs):
                file_path = anyio.Path(self._entity_tracker.get_storage_root() / filename)
                if await file_path.exists() and not any(
                    required_file
                    for required_file in required_files
                    if required_file == Path(file_path) or file_path in required_file.parents
                ):
                    if await file_path.is_file():
                        await file_path.unlink()
                    else:
                        await aioshutil.rmtree(file_path)

    async def get_cached(self, entity: EntityHandle) -> Path:
        """returns a Path to the entity referenced by the entity handle.
        The caller MUST NOT modify the returned Path.
        """

        handle_path = self._entity_tracker.get_handle_path(entity)

        if not await anyio.Path(handle_path).exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")
        return handle_path

    async def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        """Creates a copy of the EntityHandle contents at the given Path.
        The caller is free to modify the written file. The caller is responsible
        for deleting the generated file.
        """
        handle_path = anyio.Path(self._entity_tracker.get_handle_path(entity))

        if not await handle_path.exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")

        if await handle_path.is_file():
            await aioshutil.copy(handle_path, destination)
        else:
            await aioshutil.copytree(handle_path, destination)

    async def store(
        self,
        from_: "os.PathLike[str]",
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        """returns a handle for the entity at the Path location"""
        f = await anyio.Path(from_).resolve()
        if not await f.exists():
            raise NotFoundInLocalStorageRootError(f"from_ path does not exist. {from_=}")
        # TODO: We can relax this to anything in the shared folder possibly?
        if self._entity_tracker.get_storage_root() not in f.parents:
            raise NotFoundInLocalStorageRootError(
                "from_ path is not within the storage root.  "
                f"storage_root={self._entity_tracker.get_storage_root()}, path to store={from_}",
            )
        result = self._entity_tracker.create_handle(
            self._entity_tracker.get_storage_root(),
            Path(from_),
            mime_type,
            encoding,
        )
        self._entity_tracker.add_stored_entity(result)
        return result

    async def get_storage_root(self) -> Path:
        """The local filesystem location where the content of new entities is staged"""

        return self._entity_tracker.get_storage_root()

    async def get_stored_entities(self) -> AsyncIterator[EntityHandle]:
        """The set of entities that have been stored via this scope"""

        for entity in self._entity_tracker.stored_entities:
            yield entity

    async def destroy(self, *entities: EntityHandle) -> None:
        """Delete the entity referenced by the handle"""
        # TODO: With anyio.create_task_group() we could parallel-ize this, but
        # it mangles the return exception type.
        for entity in entities:
            p = self._entity_tracker.get_handle_path(entity)
            entity_path = anyio.Path(p)
            if not await entity_path.exists():
                raise EntityNotFoundInBlobStorageError("entity not found")

            if await entity_path.is_file():
                await entity_path.unlink()
            else:
                await aioshutil.rmtree(p)

    # this signature is identical to the base signature but for some reason a typing error is reported ?!
    async def get_children(self, entity: EntityHandle) -> AsyncIterator[EntityHandle]:
        """Return the entities contained in this entity"""
        entity_path = anyio.Path(self._entity_tracker.get_handle_path(entity))
        if not await entity_path.exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")

        original_storage_root = self._entity_tracker.get_original_storage_root(entity)
        if await entity_path.is_file():
            raise NotADirectoryError()

        async for child in entity_path.iterdir():
            yield self._entity_tracker.create_handle(original_storage_root, Path(str(child)))

    async def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        """Return the entity contained in this entity with a given name.  Raises an exception if not present."""
        async for child in self.get_children(entity):
            if child.original_name == child_name:
                return child
        raise EntityNotFoundInBlobStorageError(f"{child_name} not found")

    async def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        """Return the entity containing in this entity.
        Raises an exception if the original stored entity was located immediately within storage scope."""
        if entity == NO_ENTITY or not self._entity_tracker.get_handle_path(entity).exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")
        relative_path = IdentifierParser(entity).relative_path_within_original_storage_root
        if len(relative_path.parts) == 1:
            return None
        parent = relative_path.parent
        original_storage_root = self._entity_tracker.get_original_storage_root(entity)
        return self._entity_tracker.create_handle(original_storage_root, original_storage_root / parent)

    async def get_stream(self, entity: EntityHandle) -> ByteReceiveStream:
        """Opens the EntityHandle contents for reading as a stream."""
        if entity == NO_ENTITY:
            raise EntityNotFoundInBlobStorageError("entity does not exist")

        path = self._entity_tracker.get_handle_path(entity)
        if not await anyio.Path(path).exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")
        if await anyio.Path(path).is_dir():
            raise CannotGenerateStreamForDirectoryError("cannot create stream for directory")
        return await FileReadStream.from_path(path)

    async def _send_stream_to_stream(self, from_: ByteReceiveStream, to_: ByteSendStream) -> None:
        """
        Read a stream and write the contents to another stream.

        Parameters
        ----------

        from_: ByteReceiveStream
            The stream to read from
        to_: ByteSendStream
            The stream to write to
        """
        try:
            while True:
                buf = await from_.receive()
                await to_.send(buf)
        except anyio.EndOfStream:
            pass

    async def store_stream(
        self,
        from_: ByteReceiveStream | bytes,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        """returns a handle for the content in the given stream.

        Parameters
        ----------

        from_ : AsyncStream
            the stream from which the new entity will be created
        relative_location : Optional[Path]
            the nominal relative path of the entity. The path is relative to the storage_root of
            the scope.  No data is expected at this location.
            Use this parameter to indicate the original name of the entity.
            If this parameter is not set then the implementation will generate a unique location.
        """
        path = await self._resolve_relative_path_for_write(relative_location)

        if isinstance(from_, bytes):
            await path.write_bytes(from_)
        else:
            async with await FileWriteStream.from_path(path) as to_write:
                await self._send_stream_to_stream(from_, to_write)
        return await self.store(path, mime_type, encoding)

    async def _resolve_relative_path_for_write(self, relative_location: Path | None) -> anyio.Path:
        if relative_location is None:
            relative_location = Path(str(uuid.uuid4()))

        path = await anyio.Path(await self.get_storage_root() / relative_location).resolve()

        try:
            path.relative_to(await self.get_storage_root())
        except ValueError as e:
            raise NotFoundInLocalStorageRootError(f"path '{relative_location}' is outside storage root") from e

        await path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def begin_store(
        self,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> IAsyncEntityWriter:
        path = await self._resolve_relative_path_for_write(relative_location)
        return AsyncEntityWriter(self, path, mime_type, encoding)

    async def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        return self._entity_tracker.get_unreferenced_entities(context, live_handles)

    async def get_synchronous(self) -> IStorageScope:
        """returns a object with a synchronous interface to the same scope"""
        # avoid circular import
        from ansys.bdm.shared_volume.storage_scope import StorageScope

        return StorageScope(self._entity_tracker)
