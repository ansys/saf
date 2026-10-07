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

from abc import ABC
import inspect
from io import BytesIO, RawIOBase
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any, NamedTuple
import uuid

from anyio import create_memory_object_stream
from anyio.streams.buffered import BufferedByteReceiveStream

from ansys.bdm.api import (
    EntityHandle,
    EntityNotFoundInBlobStorageError,
    IAsyncReadStorageScope,
    InvalidContextError,
    IReadStorageScope,
    IReadStorageScopeFactory,
)
from ansys.bdm.base.encoder import encode_text
from ansys.saf.glow._bdm.storage_contexts import METHOD_CONTEXT, PRODUCT_CONTEXT
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, ROOT, SHORTID
from ansys.saf.glow._server.hidden_project_directories import bdm_asset_cache_dir_name
from ansys.saf.glow._utilities.decrypt_file import decrypt_file

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Buffer
    from types import TracebackType
    from typing import Self

    from anyio.abc import ByteReceiveStream

    from ansys.saf.glow._core.solution import Solution


class SubsidiarySystemStorageScope(ABC, IReadStorageScope):
    def __enter__(self) -> IReadStorageScope: ...

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,  # noqa: PYI063
        __exc_value: BaseException | None,
        __traceback: TracebackType | None,
    ) -> None: ...

    def get_stream(self, entity: EntityHandle) -> RawIOBase:
        path = self.get_cached(entity)
        if path.is_dir():
            raise ValueError("Cannot create stream for directory")
        return path.open("rb", buffering=0)

    def get_bytes(self, entity: EntityHandle) -> bytes:
        return self.get_stream(entity).readall()

    def get_text(self, entity: EntityHandle, encoding: str | None = None) -> str:
        return encode_text(self.get_bytes(entity), entity, encoding)


class AssetSubsidiarySystemStorageScope(SubsidiarySystemStorageScope):
    class _ParsedHandle(NamedTuple):
        filepath: Path
        step_name: str
        asset_path: str
        is_encrypted: bool

    class InMemoryRawIO(RawIOBase):
        """BDM uses RawIOBase to stream data.
        However RawIOBase is only subclassed by FileIO which does not allow in memory streaming.
        This class is therefore a custom implementation of RawIOBase using BytesIO to allow
        in memory streaming, so that encrypted asset files can be streamed without decryption on disk."""

        def __init__(self, initial_bytes: bytes = b""):
            self._bytes_io = BytesIO(initial_bytes)

        def read(self, size: int = -1):
            return self._bytes_io.read(size)

        def readall(self) -> bytes:
            return self._bytes_io.getvalue()

        def readinto(self, b: Buffer) -> int:
            return self._bytes_io.readinto(b)

        def write(self, b: Buffer) -> int:
            return self._bytes_io.write(b)

        def __getattr__(self, name: str) -> Any:
            """Defer all calls to other RawIOBase methods to the BytesIO impl."""
            return getattr(self._bytes_io, name)

    def __init__(self, solution_type: type[Solution], cache_dir: Path):
        self._solution_type = solution_type
        self._cache_dir = cache_dir

    def __enter__(self) -> Self:
        # .cache_dir creation deferred until get_cached is called
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir)

    def get_entity_handle(self, step_name: str, asset_path: str) -> EntityHandle:
        asset_dir = self._get_asset_dir(step_name)
        entity_path = asset_dir / asset_path
        is_encrypted = False
        if not entity_path.exists():
            entity_path = entity_path.with_suffix(entity_path.suffix + ".encrypted")
            if not entity_path.exists():
                raise EntityNotFoundInBlobStorageError(f"'{asset_path}' asset file not found.")
            is_encrypted = True
        return EntityHandle(
            is_blob=entity_path.is_file(),
            original_name=entity_path.name.removesuffix(".encrypted"),
            entity_id=uuid.uuid4(),
            opaque_identifier=f"{step_name}/{asset_path}" + (".encrypted" if is_encrypted else ""),
            mime_type=None,
            encoding=None,
            size=entity_path.stat().st_size,
        )

    def get_stream(self, entity: EntityHandle) -> RawIOBase:
        parsed_handle = self._parse_handle(entity)
        if parsed_handle.is_encrypted:
            content = self.get_bytes(entity)
            return self.InMemoryRawIO(content)
        return super().get_stream(entity)

    def get_bytes(self, entity: EntityHandle) -> bytes:
        filepath, _, _, is_encrypted = self._parse_handle(entity)
        if filepath.is_dir():
            raise ValueError("Cannot create bytes for directory.")
        if is_encrypted:
            decrypted_string = decrypt_file(filepath)
            return decrypted_string.encode()
        return filepath.read_bytes()

    def get_cached(self, entity: EntityHandle) -> Path:
        filepath, step_name, asset_path, is_encrypted = self._parse_handle(entity)
        if filepath.is_file():
            return filepath if not is_encrypted else self._decrypt_to_cache(filepath, step_name, asset_path)

        # directory
        all_asset_files = sorted(filepath.rglob("*"))
        is_encrypted = any(file.suffix == ".encrypted" for file in all_asset_files)
        if is_encrypted:
            # at least one file is encrypted: let's copy all files to the cache folder
            for asset_file in all_asset_files:
                child_asset_path = f"{asset_path}/{asset_file.relative_to(filepath)}"
                if asset_file.suffix == ".encrypted":
                    self._decrypt_to_cache(asset_file, step_name, child_asset_path.removesuffix(".encrypted"))
                else:
                    self._write_to_cache(asset_file.read_text(), step_name, child_asset_path)

        return filepath if not is_encrypted else self._cache_dir / step_name / asset_path

    def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        parsed_handle = self._parse_handle(entity)
        if parsed_handle.filepath.is_file():
            destination.parent.mkdir(exist_ok=True, parents=True)
            if parsed_handle.is_encrypted:
                decrypted_string = decrypt_file(parsed_handle.filepath)
                destination.write_text(decrypted_string)
            else:
                shutil.copy(parsed_handle.filepath, destination)
        else:  # directory
            all_asset_files = sorted(parsed_handle.filepath.rglob("*"))
            for asset_file in all_asset_files:
                subpath = asset_file.relative_to(parsed_handle.filepath).as_posix().removesuffix(".encrypted")
                child_asset_path = f"{parsed_handle.asset_path}/{subpath}"
                entity_handle = self.get_entity_handle(step_name=parsed_handle.step_name, asset_path=child_asset_path)
                self.get_copy(entity_handle, destination / subpath)

    def get_children(self, entity: EntityHandle) -> list[EntityHandle]:
        filepath, step_name, asset_path, _ = self._parse_handle(entity)
        return [
            self.get_entity_handle(step_name, f"{asset_path}/{child_asset_path.relative_to(filepath)}")
            for child_asset_path in filepath.iterdir()
        ]

    def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        parsed_handle = self._parse_handle(entity)
        return self.get_entity_handle(parsed_handle.step_name, f"{parsed_handle.asset_path}/{child_name}")

    def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        parsed_handle = self._parse_handle(entity)
        parent_asset_path = parsed_handle.asset_path.rsplit("/", 1)[0]
        if parsed_handle.asset_path == parent_asset_path:
            return None
        return self.get_entity_handle(parsed_handle.step_name, parent_asset_path)

    def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        raise RuntimeError("Operation not allowed in the context of the asset storage scope.")

    def _get_asset_dir(self, step_name: str) -> Path:
        step_type = self._solution_type.get_steps_fields()[step_name]
        source_file = inspect.getsourcefile(step_type)
        if source_file is None:
            raise ValueError(f"Cannot find source file named {source_file} for step type {step_type}")
        parents = Path(source_file).parents
        for parent in parents:
            asset_dir = parent / "method_assets"
            if asset_dir.is_dir():
                return asset_dir
        raise ValueError(f"Cannot find method_assets directory for step type {step_type}")

    def _decrypt_to_cache(self, encrypted_filepath: Path, step_name: str, asset_path: str) -> Path:
        decrypted_string = decrypt_file(encrypted_filepath)
        return self._write_to_cache(decrypted_string, step_name, asset_path)

    def _write_to_cache(self, content: str, step_name: str, asset_path: str) -> Path:
        cache_path = self._cache_dir / step_name / asset_path
        cache_path.parent.mkdir(exist_ok=True, parents=True)
        if not cache_path.exists():
            cache_path.write_text(content)
        return cache_path

    def _parse_handle(self, entity: EntityHandle) -> _ParsedHandle:
        step_name, asset_path = entity.opaque_identifier.split("/", 1)
        entity_path = self._get_asset_dir(step_name) / asset_path
        if not entity_path.exists():
            raise EntityNotFoundInBlobStorageError(
                f"The entity handle '{entity.original_name}' is referring to a non-existent path.",
            )
        return self._ParsedHandle(
            filepath=entity_path,
            step_name=step_name,
            asset_path=asset_path.removesuffix(".encrypted"),
            is_encrypted=asset_path.endswith(".encrypted"),
        )

    @property
    def asynchronous(self) -> IAsyncReadStorageScope:
        return AsyncProxySubsidiarySystemStorageScope(self)


class AssetSubsidiarySystemStorageScopeFactory(IReadStorageScopeFactory):
    def __init__(self, solution_type: type[Solution]):
        self._solution_type = solution_type

    def create_storage_scope(self, context: str, template_vars: dict[str, str]) -> IReadStorageScope:
        if context not in [METHOD_CONTEXT, PRODUCT_CONTEXT]:
            # Asset storage scope can only be accessed from within a transaction method,
            # not from the rest api, to avoid leaking sensitive information.
            return ProhibitedSubsidiarySystemStorageScope()
        project_files_dir = template_vars[ROOT]
        project_id = template_vars[PROJECT_ID]
        cache_dir = Path(project_files_dir) / project_id / bdm_asset_cache_dir_name / template_vars[SHORTID]
        return AssetSubsidiarySystemStorageScope(solution_type=self._solution_type, cache_dir=cache_dir)

    async def create_async_storage_scope(
        self,
        context: str,
        template_vars: dict[str, str],
    ) -> IAsyncReadStorageScope:
        sync_storage_scope = self.create_storage_scope(context=context, template_vars=template_vars)
        return sync_storage_scope.asynchronous


class ProhibitedSubsidiarySystemStorageScope(IReadStorageScope):
    def _raise_error(self, entity: EntityHandle):
        raise InvalidContextError(f"The entity handle '{entity.original_name}' cannot be resolved from this context.")

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None: ...

    def get_cached(self, entity: EntityHandle) -> Path:
        self._raise_error(entity)

    def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        self._raise_error(entity)

    def get_stream(self, entity: EntityHandle) -> RawIOBase:
        self._raise_error(entity)

    def get_bytes(self, entity: EntityHandle) -> bytes:
        self._raise_error(entity)

    def get_text(self, entity: EntityHandle, encoding: str | None = None) -> str:
        self._raise_error(entity)

    def get_children(self, entity: EntityHandle) -> list[EntityHandle]:
        self._raise_error(entity)

    def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        self._raise_error(entity)

    def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        self._raise_error(entity)

    def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        raise NotImplementedError()

    @property
    def asynchronous(self) -> IAsyncReadStorageScope:
        return AsyncProxySubsidiarySystemStorageScope(self)


class ProhibitedSubsidiarySystemStorageScopeFactory:
    def create_storage_scope(self, context: str, template_vars: dict[str, str]) -> IReadStorageScope:
        return ProhibitedSubsidiarySystemStorageScope()

    async def create_async_storage_scope(
        self,
        context: str,
        template_vars: dict[str, str],
    ) -> IAsyncReadStorageScope:
        sync_storage_scope = self.create_storage_scope(
            context=context,
            template_vars=template_vars,
        )
        return sync_storage_scope.asynchronous


class AsyncProxySubsidiarySystemStorageScope(IAsyncReadStorageScope):
    """Wrap a synchronous subsidiary storage scope and make it compatible with an async interface.

    Due to performance issue, this must only be used when there is no alternative, for example
    when the underlying system is synchronous and we don't have control over it (e.g. HPS or minerva client)
    """

    def __init__(
        self,
        sync_substorage_scope: IReadStorageScope,
    ):
        self._sync_substorage_scope = sync_substorage_scope

    async def __aenter__(self) -> IAsyncReadStorageScope:
        self._sync_substorage_scope.__enter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._sync_substorage_scope.__exit__(exc_type, exc_value, traceback)

    async def get_stream(self, entity: EntityHandle) -> ByteReceiveStream:
        stream = self._sync_substorage_scope.get_stream(entity)
        # we need to convert from RawIOBase to ByteReceiveStream..
        # not sure this is the best way but at least it works.
        send_stream, receive_stream = create_memory_object_stream(16)  # type: ignore
        content = stream.readall()
        with send_stream:
            await send_stream.send(content)  # type: ignore
        buffered_stream = BufferedByteReceiveStream(receive_stream)  # type: ignore
        return buffered_stream

    async def get_bytes(self, entity: EntityHandle) -> bytes:
        return self._sync_substorage_scope.get_bytes(entity)

    async def get_text(self, entity: EntityHandle, encoding: str | None = None) -> str:
        return self._sync_substorage_scope.get_text(entity, encoding)

    async def get_cached(self, entity: EntityHandle) -> Path:
        return self._sync_substorage_scope.get_cached(entity)

    async def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        return self._sync_substorage_scope.get_copy(entity=entity, destination=destination)

    async def get_children(self, entity: EntityHandle) -> AsyncIterator[EntityHandle]:
        for child in self._sync_substorage_scope.get_children(entity=entity):
            yield child

    async def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        return self._sync_substorage_scope.get_child(entity=entity, child_name=child_name)

    async def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        return self._sync_substorage_scope.get_parent(entity=entity)

    async def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        return self._sync_substorage_scope.get_unreferenced_entities(context=context, live_handles=live_handles)

    async def get_synchronous(self) -> IReadStorageScope:
        return self._sync_substorage_scope
