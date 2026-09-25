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

import random
import string

import pytest

from ansys.bdm.api.entity_handle import EntityHandle
from ansys.bdm.api.storage_exceptions import CannotGenerateStreamForDirectoryError
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory
from tests.content import CONTENT


def test_can_read_bytes(file_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        content_bytes = scope.get_bytes(file_entity)
        assert str(content_bytes, encoding="utf-8") == CONTENT


async def test_can_read_bytes_async(
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        content_bytes = await scope.get_bytes(file_entity)
        assert str(content_bytes, encoding="utf-8") == CONTENT


def test_cannot_read_bytes_from_directory(
    directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(CannotGenerateStreamForDirectoryError):
        scope.get_bytes(directory_entity)


async def test_cannot_read_bytes_from_directory_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(CannotGenerateStreamForDirectoryError):
            await scope.get_bytes(directory_entity)


def test_can_write_bytes(storage_scope_factory: SimpleStorageScopeFactory):
    # GIVEN - file content in bytes
    content_bytes = CONTENT.encode("utf-8")

    # WHEN - storing the bytes and generating a handle for the data
    with storage_scope_factory() as scope:
        handle = scope.store_stream(content_bytes)

    # THEN - the retrieved content, using the handle, is the original stored data
    with storage_scope_factory() as scope:
        file_path = scope.get_cached(handle)
        assert file_path.read_text() == CONTENT


async def test_can_write_bytes_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    # GIVEN - file content in bytes
    content_bytes = CONTENT.encode("utf-8")

    # WHEN - storing the bytes and generating a handle for the data
    async with await async_storage_scope_factory() as scope:
        handle = await scope.store_stream(content_bytes)

    # THEN - the retrieved content, using the handle, is the original stored data
    async with await async_storage_scope_factory() as scope:
        file_path = await scope.get_cached(handle)
        assert file_path.read_text() == CONTENT


def test_can_read_and_write_long_bytes(storage_scope_factory: SimpleStorageScopeFactory):
    # GIVEN - file content in bytes
    letters = string.ascii_lowercase
    content = "".join(random.choice(letters) for _ in range(1500000))
    content_bytes = content.encode("utf-8")

    # WHEN - storing the bytes and generating a handle for the data
    with storage_scope_factory() as scope:
        handle = scope.store_stream(content_bytes)

    # THEN - the retrieved content, using the handle, is the original stored data
    with storage_scope_factory() as scope:
        assert scope.get_bytes(handle) == content_bytes


async def test_can_read_and_write_long_bytes_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    # GIVEN - file content in bytes
    letters = string.ascii_lowercase
    content = "".join(random.choice(letters) for _ in range(1500000))
    content_bytes = content.encode("utf-8")

    # WHEN - storing the bytes and generating a handle for the data
    async with await async_storage_scope_factory() as scope:
        handle = await scope.store_stream(content_bytes)

    # THEN - the retrieved content, using the handle, is the original stored data
    async with await async_storage_scope_factory() as scope:
        data = await scope.get_bytes(handle)
        assert data == content_bytes
