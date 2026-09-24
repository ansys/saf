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

from io import BytesIO
import locale
from pathlib import Path

import pytest

from ansys.bdm.api import (
    EntityHandle,
    NotFoundInLocalStorageRootError,
)
from tests.bytes_receive_stream import BytesReceiveStream
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory
from tests.content import CONTENT


def test_file_entity_default_metadata(file_entity: EntityHandle):
    assert file_entity.size == len(CONTENT.encode(locale.getpreferredencoding(False)))
    assert file_entity.mime_type == "text/plain"
    assert file_entity.encoding is None


def test_mime_type_detection(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        entity: EntityHandle = scope.store_stream(BytesIO(b""), Path("dummy.jpg"))
        assert entity.mime_type == "image/jpeg"


async def test_mime_type_detection_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        entity: EntityHandle = await scope.store_stream(BytesReceiveStream(b""), Path("dummy.jpg"))
        assert entity.mime_type == "image/jpeg"


def test_mime_type_override(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        entity: EntityHandle = scope.store_stream(BytesIO(b""), mime_type="application/bogus")
        assert entity.mime_type == "application/bogus"


async def test_mime_type_override_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        entity: EntityHandle = await scope.store_stream(BytesReceiveStream(b""), mime_type="application/bogus")
        assert entity.mime_type == "application/bogus"


def test_can_store_and_get_cached_data(file_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        y = scope.get_cached(file_entity)
        assert y.read_text() == CONTENT


async def test_can_store_and_get_cached_data_async(
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        y = await scope.get_cached(file_entity)
        assert y.read_text() == CONTENT


async def test_can_store_async_and_get_cached_data_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x.txt"
        x.write_text(CONTENT)
        file_entity = await scope.store(x)
    async with await async_storage_scope_factory() as scope:
        y = await scope.get_cached(file_entity)
        assert y.read_text() == CONTENT


async def test_can_store_using_get_synchronous_and_get_cached_data_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x.txt"
        x.write_text(CONTENT)
        synchronous = await scope.get_synchronous()
        file_entity = synchronous.store(x)
    async with await async_storage_scope_factory() as scope:
        y = await scope.get_cached(file_entity)
        assert y.read_text() == CONTENT


async def test_can_store_using_asynchronous_and_get_cached_data_async(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x.txt"
        x.write_text(CONTENT)
        asynchronous = scope.asynchronous
        file_entity = await asynchronous.store(x)
    with storage_scope_factory() as scope:
        y = scope.get_cached(file_entity)
        assert y.read_text() == CONTENT


def test_scope_exit_deletes_file_created_in_scope(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x.txt"
        x.write_text(CONTENT)
    assert not x.exists()


async def test_scope_exit_deletes_file_created_in_scope_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x.txt"
        x.write_text(CONTENT)
    assert not x.exists()


def test_scope_exit_deletes_file_created_in_scope_when_entity_stored_too(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x.txt"
        x.write_text(CONTENT)
        y = scope.get_storage_root() / "y.txt"
        y.write_text(CONTENT)
        scope.store(y)
    assert not x.exists()


async def test_scope_exit_deletes_file_created_in_scope_when_entity_stored_too_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x.txt"
        x.write_text(CONTENT)
        y = await scope.get_storage_root() / "y.txt"
        y.write_text(CONTENT)
        await scope.store(y)
    assert not x.exists()


def test_scope_exit_deletes_directory_created_in_scope_when_entity_stored_too(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x"
        x.mkdir()
        y = scope.get_storage_root() / "y.txt"
        y.write_text(CONTENT)
        scope.store(y)
    assert not x.exists()


async def test_scope_exit_deletes_directory_created_in_scope_when_entity_stored_too_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x"
        x.mkdir()
        y = await scope.get_storage_root() / "y.txt"
        y.write_text(CONTENT)
        await scope.store(y)
    assert not x.exists()


def test_can_store_and_get_copy_of_data(file_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        y = scope.get_storage_root() / "y.txt"
        scope.get_copy(file_entity, y)
        assert y.read_text() == CONTENT
    assert not y.exists()


async def test_can_store_and_get_copy_of_data_async(
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        y = await scope.get_storage_root() / "y.txt"
        await scope.get_copy(file_entity, y)
        assert y.read_text() == CONTENT
    assert not y.exists()


def test_can_store_and_get_copy_of_data_outside_storage_root(
    tmp_path: Path,
    file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        y = tmp_path / "y.txt"
        scope.get_copy(file_entity, y)
        assert y.read_text() == CONTENT
    assert y.exists()


async def test_can_store_and_get_copy_of_data_outside_storage_root_async(
    tmp_path: Path,
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        y = tmp_path / "y.txt"
        await scope.get_copy(file_entity, y)
        assert y.read_text() == CONTENT
    assert y.exists()


def test_stored_entities_is_empty_as_scope_entry(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        assert len(scope.stored_entities) == 0


async def test_stored_entities_is_empty_as_scope_entry_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        assert len([x async for x in scope.get_stored_entities()]) == 0


def test_stored_entities_has_entry_after_store(storage_scope_factory: SimpleStorageScopeFactory):
    content = "hello world"
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x.txt"
        x.write_text(content)
        handle = scope.store(x)
        assert scope.stored_entities == [handle]


async def test_stored_entities_has_entry_after_store_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    content = "hello world"
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x.txt"
        x.write_text(content)
        handle = await scope.store(x)
        assert [x async for x in scope.get_stored_entities()] == [handle]


def test_storing_file_from_outside_storage_root_raises_exception(
    tmp_path: Path,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    y = tmp_path / "y.txt"
    y.write_text(CONTENT)
    with storage_scope_factory() as scope, pytest.raises(NotFoundInLocalStorageRootError):
        scope.store(y)


async def test_storing_file_from_outside_storage_root_raises_exception_async(
    tmp_path: Path,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    y = tmp_path / "y.txt"
    y.write_text(CONTENT)
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(NotFoundInLocalStorageRootError):
            await scope.store(y)


def test_storing_file_from_outside_storage_root_using_dot_dot_raises_exception(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        y = scope.get_storage_root() / ".." / "y.txt"
        y.write_text(CONTENT)
        with pytest.raises(NotFoundInLocalStorageRootError):
            scope.store(y)


async def test_storing_file_from_outside_storage_root_using_dot_dot_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        y = await scope.get_storage_root() / ".." / "y.txt"
        y.write_text(CONTENT)
        with pytest.raises(NotFoundInLocalStorageRootError):
            await scope.store(y)
