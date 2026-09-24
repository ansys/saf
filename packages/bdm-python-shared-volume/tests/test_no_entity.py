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

import pytest

from ansys.bdm.api import (
    NO_ENTITY,
    EntityNotFoundInBlobStorageError,
)
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory


def test_getting_cached_using_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_cached(NO_ENTITY)


async def test_getting_cached_using_no_entity_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_cached(NO_ENTITY)


def test_getting_copy_using_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_copy(NO_ENTITY, scope.get_storage_root() / "x.txt")


async def test_getting_copy_using_no_entity_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_copy(NO_ENTITY, await scope.get_storage_root() / "x.txt")


def test_getting_stream_using_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_stream(NO_ENTITY)


async def test_getting_stream_using_no_entity_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_stream(NO_ENTITY)


def test_destroy_of_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.destroy(NO_ENTITY)


async def test_destroy_of_no_entity_raises_exception_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.destroy(NO_ENTITY)


def test_getting_children_of_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_children(NO_ENTITY)


async def test_getting_children_of_no_entity_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        itr = scope.get_children(NO_ENTITY)
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await itr.__anext__()


def test_getting_child_of_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_child(NO_ENTITY, "x.txt")


async def test_getting_child_of_no_entity_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_child(NO_ENTITY, "x.txt")


def test_getting_parent_of_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_parent(NO_ENTITY)


async def test_getting_parent_of_no_entity_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_parent(NO_ENTITY)


def test_getting_bytes_of_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_bytes(NO_ENTITY)


async def test_getting_bytes_of_no_entity_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_bytes(NO_ENTITY)


def test_getting_text_of_no_entity_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(EntityNotFoundInBlobStorageError):
        scope.get_text(NO_ENTITY)


async def test_getting_text_of_no_entity_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError):
            await scope.get_text(NO_ENTITY)
