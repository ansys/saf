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

from pathlib import Path

import pytest

from ansys.bdm.api import EntityHandle, EntityNotFoundInBlobStorageError
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory
from tests.content import create_directory_content


def test_destroyed_entities_cannot_be_got_from_cache(
    destroyed_file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_cached(destroyed_file_entity)


async def test_destroyed_entities_cannot_be_got_from_cache_async(
    destroyed_file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_cached(destroyed_file_entity)


def test_destroyed_entities_cannot_be_copied(
    destroyed_file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        y = Path(scope.get_storage_root()) / "y.txt"
        with pytest.raises(EntityNotFoundInBlobStorageError):
            scope.get_copy(destroyed_file_entity, y)


async def test_destroyed_entities_cannot_be_copied_async(
    destroyed_file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        y = Path(await scope.get_storage_root()) / "y.txt"
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_copy(destroyed_file_entity, y)


def test_destroyed_entities_cannot_be_streamed(
    destroyed_file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_stream(destroyed_file_entity)


def test_cannot_get_copy_of_destroyed_directory(
    destroyed_directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_copy(destroyed_directory_entity, scope.get_storage_root() / "x")


async def test_cannot_get_copy_of_destroyed_directory_async(
    destroyed_directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_copy(destroyed_directory_entity, await scope.get_storage_root() / "x")


def test_cannot_get_cache_of_destroyed_directory(
    destroyed_directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_cached(destroyed_directory_entity)


async def test_cannot_get_cache_of_destroyed_directory_async(
    destroyed_directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_cached(destroyed_directory_entity)


def test_cannot_destroy_destroyed_file(
    destroyed_file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.destroy(destroyed_file_entity)


async def test_cannot_destroy_destroyed_file_sync(
    destroyed_file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.destroy(destroyed_file_entity)


def test_cannot_destroy_destroyed_directory(
    destroyed_directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.destroy(destroyed_directory_entity)


async def test_cannot_destroy_destroyed_directory_async(
    destroyed_directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.destroy(destroyed_directory_entity)


def test_cannot_get_children_of_destroyed_directory(
    destroyed_directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_children(destroyed_directory_entity)


async def test_cannot_get_children_of_destroyed_directory_async(
    destroyed_directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        itr = scope.get_children(destroyed_directory_entity)
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await itr.__anext__()


def test_cannot_get_child_of_destroyed_directory(
    destroyed_directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_child(destroyed_directory_entity, "subtop")


async def test_cannot_get_child_of_destroyed_directory_async(
    destroyed_directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_child(destroyed_directory_entity, "subtop")


def test_cannot_get_parent_of_destroyed_file(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        top = create_directory_content(scope.get_storage_root())
        file_handle = scope.store(top / "subtop" / "leaf.txt")
    with storage_scope_factory() as scope:
        scope.destroy(file_handle)
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_parent(file_handle)


async def test_cannot_get_parent_of_destroyed_file_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        top = create_directory_content(await scope.get_storage_root())
        file_handle = await scope.store(top / "subtop" / "leaf.txt")
    async with await async_storage_scope_factory() as scope:
        await scope.destroy(file_handle)
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_parent(file_handle)


def test_cannot_get_parent_of_file_within_destroyed_directory(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        top = create_directory_content(scope.get_storage_root())
        subtop = scope.store(top / "subtop")
        file_handle = scope.store(top / "subtop" / "leaf.txt")
    with storage_scope_factory() as scope:
        scope.destroy(subtop)
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_parent(file_handle)


async def test_cannot_get_parent_of_file_within_destroyed_directory_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        top = create_directory_content(await scope.get_storage_root())
        subtop = await scope.store(top / "subtop")
        file_handle = await scope.store(top / "subtop" / "leaf.txt")
    async with await async_storage_scope_factory() as scope:
        await scope.destroy(subtop)
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_parent(file_handle)


def test_multi_destroy(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        file1 = scope.get_storage_root() / "file1.txt"
        file2 = scope.get_storage_root() / "file2.txt"
        file1.write_text("Yadda yadda")
        file2.write_text("Bogus Smogus")
        eh1 = scope.store(file1)
        eh2 = scope.store(file2)
    with storage_scope_factory() as scope:
        scope.destroy(eh1, eh2)
    with storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            scope.get_cached(eh1)
        with pytest.raises(EntityNotFoundInBlobStorageError):
            scope.get_cached(eh2)


async def test_multi_destroy_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        file1 = await scope.get_storage_root() / "file1.txt"
        file2 = await scope.get_storage_root() / "file2.txt"
        file1.write_text("Yadda yadda")
        file2.write_text("Bogus Smogus")
        eh1 = await scope.store(file1)
        eh2 = await scope.store(file2)
    async with await async_storage_scope_factory() as scope:
        await scope.destroy(eh1, eh2)
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            _ = await scope.get_cached(eh1)
        with pytest.raises(EntityNotFoundInBlobStorageError):
            _ = await scope.get_cached(eh2)
