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

from io import BufferedIOBase, RawIOBase
import itertools
import os
from pathlib import Path
import shutil
from types import TracebackType
import uuid

from ansys.bdm.api import (
    NO_ENTITY,
    CannotGenerateStreamForDirectoryError,
    EntityHandle,
    EntityNotFoundInBlobStorageError,
    IAsyncStorageScope,
    NotFoundInLocalStorageRootError,
)
from ansys.bdm.base.base_storage_scope import StorageScopeBase
from ansys.bdm.shared_volume.entity_tracker import EntityTracker
from ansys.bdm.shared_volume.entity_writer import EntityWriter
from ansys.bdm.shared_volume.identifier_parser import IdentifierParser


class StorageScope(StorageScopeBase):
    """A storage scope based on a shared folder globally available."""

    def __init__(self, entity_tracker: EntityTracker):
        self._entity_tracker = entity_tracker

    def __enter__(self) -> "StorageScope":
        return self

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,  # noqa: PYI063
        __exc_value: BaseException | None,
        __traceback: TracebackType | None,
    ) -> None:
        required_files = self._entity_tracker.required_files

        if not required_files:
            shutil.rmtree(self._entity_tracker.get_storage_root())
            return

        for _, dirs, files in os.walk(self._entity_tracker.get_storage_root()):
            for filename in itertools.chain(files, dirs):
                file_path = self._entity_tracker.get_storage_root() / filename
                if file_path.exists() and not any(
                    required_file
                    for required_file in required_files
                    if required_file == file_path or file_path in required_file.parents
                ):
                    if file_path.is_file():
                        file_path.unlink()
                    else:
                        shutil.rmtree(file_path)

    def get_cached(self, entity: EntityHandle) -> Path:
        handle_path = self._entity_tracker.get_handle_path(entity)

        if not handle_path.exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")
        return handle_path

    def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        handle_path = self._entity_tracker.get_handle_path(entity)

        if not handle_path.exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")

        if handle_path.is_file():
            shutil.copy(handle_path, destination)
        else:
            shutil.copytree(handle_path, destination)

    def get_stream(self, entity: EntityHandle) -> RawIOBase:
        path = self.get_cached(entity)

        if path.is_dir():
            raise CannotGenerateStreamForDirectoryError("cannot create stream for directory")
        return path.open("rb", buffering=0)

    def store(
        self,
        from_: "os.PathLike[str]",
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        from_ = Path(from_).resolve()
        if not from_.exists():
            raise NotFoundInLocalStorageRootError(f"from_ path does not exist. {from_=}")
        # TODO: We can relax this to anything in the shared folder possibly?
        if self._entity_tracker.get_storage_root() not in from_.parents:
            raise NotFoundInLocalStorageRootError(
                "from_ path is not within the storage root.  "
                f"storage_root={self._entity_tracker.get_storage_root()}, path to store={from_}",
            )
        result = self._entity_tracker.create_handle(self._entity_tracker.get_storage_root(), from_, mime_type, encoding)
        self._entity_tracker.add_stored_entity(result)
        return result

    # TODO: There has to be a utility for this
    def _send_stream_to_stream(self, from_: RawIOBase | BufferedIOBase, to_: BufferedIOBase) -> None:
        """
        Read a stream and write the contents to another stream.

        Parameters
        ----------

        from_: ByteReceiveStream
            The stream to read from
        to_: ByteSendStream
            The stream to write to
        """
        buf: bytearray = bytearray(4096)
        done = False
        while not done:
            # TODO: Not sure this is really right in all cases
            nread = from_.readinto1(buf) if isinstance(from_, BufferedIOBase) else from_.readinto(buf)
            if (nread is None) or (nread == 0):
                done = True
            else:
                to_.write(buf[0:nread])

    def store_stream(
        self,
        from_: RawIOBase | BufferedIOBase | bytes,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        path = self._resolve_relative_path_for_write(relative_location)
        if isinstance(from_, bytes):
            path.write_bytes(from_)
        else:
            with path.open("wb") as to_write:
                self._send_stream_to_stream(from_, to_write)
        return self.store(path, mime_type, encoding)

    def _resolve_relative_path_for_write(self, relative_location: Path | None = None) -> Path:
        if relative_location is None:
            relative_location = Path(str(uuid.uuid4()))

        path = (self.get_storage_root() / relative_location).resolve()

        try:
            path.relative_to(self.get_storage_root())
        except ValueError as e:
            raise NotFoundInLocalStorageRootError(
                f"path '{relative_location}' references file outside storage root",
            ) from e

        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def begin_store(
        self,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityWriter:
        path = self._resolve_relative_path_for_write(relative_location)
        return EntityWriter(self, path, mime_type, encoding)

    def get_storage_root(self) -> Path:
        return self._entity_tracker.get_storage_root()

    @property
    def stored_entities(self) -> list[EntityHandle]:
        return self._entity_tracker.stored_entities

    def destroy(self, *entities: EntityHandle) -> None:
        for entity in entities:
            entity_path = self._entity_tracker.get_handle_path(entity)
            if not entity_path.exists():
                raise EntityNotFoundInBlobStorageError("entity not found")

            if entity_path.is_file():
                entity_path.unlink()
            else:
                shutil.rmtree(entity_path)

    def get_children(self, entity: EntityHandle) -> list[EntityHandle]:
        """Return the entities contained in this entity"""
        entity_path = self._entity_tracker.get_handle_path(entity)
        if not entity_path.exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")

        original_storage_root = self._entity_tracker.get_original_storage_root(entity)
        if entity_path.is_file():
            raise NotADirectoryError()
        return [self._entity_tracker.create_handle(original_storage_root, child) for child in entity_path.iterdir()]

    def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        children = [child for child in self.get_children(entity) if child.original_name == child_name]

        if not children:
            raise EntityNotFoundInBlobStorageError(f"{child_name} not found")
        return children[0]

    def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        if entity == NO_ENTITY or not self._entity_tracker.get_handle_path(entity).exists():
            raise EntityNotFoundInBlobStorageError("entity does not exist")
        relative_path = IdentifierParser(entity).relative_path_within_original_storage_root
        if len(relative_path.parts) == 1:
            return None
        parent = relative_path.parent
        original_storage_root = self._entity_tracker.get_original_storage_root(entity)
        return self._entity_tracker.create_handle(original_storage_root, original_storage_root / parent)

    def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        return self._entity_tracker.get_unreferenced_entities(context, live_handles)

    @property
    def asynchronous(self) -> IAsyncStorageScope:
        """returns a object with a synchronous interface to the same scope"""
        # avoid circular import
        from ansys.bdm.shared_volume.async_storage_scope import AsyncStorageScope

        return AsyncStorageScope(self._entity_tracker)
