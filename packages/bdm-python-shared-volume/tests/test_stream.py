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

import contextlib
from io import BytesIO, FileIO
from pathlib import Path

from anyio import EndOfStream
from anyio.abc import ByteReceiveStream
from anyio.streams.file import FileReadStream
import pytest

from ansys.bdm.api import (
    CannotGenerateStreamForDirectoryError,
    EntityHandle,
    EntityNotFoundInBlobStorageError,
    EntityWriterHasNotCompletedWritingDataError,
    EntityWriterHasWrittenDataError,
    EntityWriterIsNotWritingDataError,
    NotFoundInLocalStorageRootError,
)
from tests.bytes_receive_stream import BytesReceiveStream
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory
from tests.content import CONTENT


async def async_read_all(stream: ByteReceiveStream) -> bytes:
    """
    Reads an entire async stream into memory.
    (Depends on the stream not being more than 65536 bytes long)

    Parameters
    ----------

    stream: ByteReceiveStream
        The stream to read

    Returns
    -------

    bytes
        The bytes read from the stream
    """
    result = bytearray()
    with contextlib.suppress(EndOfStream):
        # the default number of bytes read is 65536
        # we're assuming the stream isn't longer than that
        result.extend(await stream.receive())
    return bytes(result)


def test_can_store_and_get_streamed_data(file_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        stream_bytes = scope.get_stream(file_entity).readall()
        assert str(stream_bytes, "UTF-8") == CONTENT


async def test_can_store_and_get_streamed_data_async(
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        stream = await scope.get_stream(file_entity)
        stream_bytes = await async_read_all(stream)
        assert str(stream_bytes, "UTF-8") == CONTENT


def test_cannot_get_stream_of_directory(
    directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(CannotGenerateStreamForDirectoryError):
        scope.get_stream(directory_entity)


async def test_cannot_get_stream_of_directory_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(CannotGenerateStreamForDirectoryError):
            await scope.get_stream(directory_entity)


def test_cannot_get_stream_of_destroyed_file(
    destroyed_file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_stream(destroyed_file_entity)


async def test_cannot_get_stream_of_destroyed_file_async(
    destroyed_file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_stream(destroyed_file_entity)


def test_can_store_stream_and_retrieve_the_content(tmp_path: Path, storage_scope_factory: SimpleStorageScopeFactory):
    y = tmp_path / "y.txt"
    y.write_text(CONTENT)
    with storage_scope_factory() as scope:
        handle = scope.store_stream(FileIO(y, "rb"))
    with storage_scope_factory() as scope:
        assert scope.get_cached(handle).read_text() == CONTENT


async def test_can_store_stream_and_retrieve_the_content_async(
    tmp_path: Path,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    y = tmp_path / "y.txt"
    y.write_text(CONTENT)
    async with await async_storage_scope_factory() as scope:
        handle = await scope.store_stream(await FileReadStream.from_path(y))
    async with await async_storage_scope_factory() as scope:
        f = await scope.get_cached(handle)
        assert f.read_text() == CONTENT


def test_can_use_begin_store_and_retrieve_the_content(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        with scope.begin_store() as writer:
            writer.stream.write(CONTENT.encode())
        handle = writer.handle
    with storage_scope_factory() as scope:
        assert scope.get_cached(handle).read_text() == CONTENT


async def test_can_use_begin_store_and_retrieve_the_content_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        async with await scope.begin_store() as writer:
            await writer.stream.send(CONTENT.encode())
        handle = writer.handle
    async with await async_storage_scope_factory() as scope:
        assert (await scope.get_cached(handle)).read_text() == CONTENT


def test_reusing_entity_writer_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        writer = scope.begin_store()
        with writer:
            pass
        with pytest.raises(EntityWriterHasWrittenDataError), writer:
            pass


async def test_reusing_entity_writer_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        writer = await scope.begin_store()
        async with writer:
            pass
        with pytest.raises(EntityWriterHasWrittenDataError):
            async with writer:
                pass


def test_accessing_writer_stream_before_entering_write_raises_exception(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        writer = scope.begin_store()
        with pytest.raises(EntityWriterIsNotWritingDataError):
            writer.stream  # noqa: B018


async def test_accessing_writer_stream_before_entering_write_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        writer = await scope.begin_store()
        with pytest.raises(EntityWriterIsNotWritingDataError):
            writer.stream  # noqa: B018


def test_accessing_writer_stream_after_write_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        with scope.begin_store() as writer:
            pass
        with pytest.raises(EntityWriterIsNotWritingDataError):
            writer.stream  # noqa: B018


async def test_accessing_writer_stream_after_write_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        async with await scope.begin_store() as writer:
            pass
        with pytest.raises(EntityWriterIsNotWritingDataError):
            writer.stream  # noqa: B018


def test_accessing_writer_handle_during_write_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, scope.begin_store() as writer:  # noqa: SIM117
        with pytest.raises(EntityWriterHasNotCompletedWritingDataError):
            writer.handle  # noqa: B018


async def test_accessing_writer_handle_during_write_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope, await scope.begin_store() as writer:
        with pytest.raises(EntityWriterHasNotCompletedWritingDataError):
            writer.handle  # noqa: B018


def test_can_store_stream_at_nested_location_and_retrieve_the_content(
    tmp_path: Path,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    y = tmp_path / "y.txt"
    y.write_text(CONTENT)
    with storage_scope_factory() as scope:
        handle = scope.store_stream(FileIO(y, "rb"), Path("top") / "subtop" / "leaf.txt")
    with storage_scope_factory() as scope:
        assert handle.original_name == "leaf.txt"
        assert scope.get_cached(handle).read_text() == CONTENT
        subtop = scope.get_parent(handle)
        assert subtop is not None
        assert subtop.original_name == "subtop"
        top = scope.get_parent(subtop)
        assert top is not None
        assert top.original_name == "top"


async def test_can_store_stream_at_nested_location_and_retrieve_the_content_async(
    tmp_path: Path,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    y = tmp_path / "y.txt"
    y.write_text(CONTENT)
    async with await async_storage_scope_factory() as scope:
        handle = await scope.store_stream(await FileReadStream.from_path(y), Path("top") / "subtop" / "leaf.txt")
    async with await async_storage_scope_factory() as scope:
        assert handle.original_name == "leaf.txt"
        f = await scope.get_cached(handle)
        assert f.read_text() == CONTENT
        subtop = await scope.get_parent(handle)
        assert subtop is not None
        assert subtop.original_name == "subtop"
        top = await scope.get_parent(subtop)
        assert top is not None
        assert top.original_name == "top"


def test_cannot_store_stream_outside_storage_root(tmp_path: Path, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(NotFoundInLocalStorageRootError):
        scope.store_stream(BytesIO(b""), Path("..") / "x.txt")


async def test_cannot_store_stream_outside_storage_root_async(
    tmp_path: Path,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(NotFoundInLocalStorageRootError):
            await scope.store_stream(BytesReceiveStream(b""), Path("..") / "x.txt")
