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
import re
import shutil
from uuid import UUID

import pytest

from ansys.bdm.api.entity_handle import NO_ENTITY, EntityHandle
from ansys.bdm.api.storage_exceptions import EntityNotFoundInBlobStorageError
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory
from tests.content import CONTENT


def test_unreferenced_entities_empty_live_handles_return_all_stored_handles(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        for i in range(10):
            x = scope.get_storage_root() / f"{i}.txt"
            x.write_text(CONTENT)
            scope.store(x)
        unreferenced_entities = scope.get_unreferenced_entities("PROJECT_BOUNDARY", [])
        assert len(unreferenced_entities) == 10
        for entity in unreferenced_entities:
            assert scope.get_cached(entity).exists()


async def test_async_unreferenced_entities_empty_live_handles_return_all_stored_handles(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        for i in range(10):
            x = await scope.get_storage_root() / f"{i}.txt"
            x.write_text(CONTENT)
            await scope.store(x)
        unreferenced_entities = await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [])
        assert len(unreferenced_entities) == 10
        for entity in unreferenced_entities:
            path = await scope.get_cached(entity)
            assert path.exists()


def test_unreferenced_entities_all_live_handles_return_empty(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        live_handles: list[EntityHandle] = []
        for i in range(10):
            x = scope.get_storage_root() / f"{i}.txt"
            x.write_text(CONTENT)
            handle = scope.store(x)
            live_handles.append(handle)
        unreferenced_entities = scope.get_unreferenced_entities("PROJECT_BOUNDARY", live_handles)
        assert len(unreferenced_entities) == 0


async def test_async_unreferenced_entities_all_live_handles_return_empty(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        live_handles: list[EntityHandle] = []
        for i in range(10):
            x = await scope.get_storage_root() / f"{i}.txt"
            x.write_text(CONTENT)
            handle = await scope.store(x)
            live_handles.append(handle)
        unreferenced_entities = await scope.get_unreferenced_entities("PROJECT_BOUNDARY", live_handles)
        assert len(unreferenced_entities) == 0


def test_unreferenced_entities_half_live_handles_return_other_half(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        live_handles: list[EntityHandle] = []
        x = scope.get_storage_root() / "x.txt"
        x.write_text("x")
        x_handle = scope.store(x)
        y = scope.get_storage_root() / "y.txt"
        y.write_text("y")
        y_handle = scope.store(y)
        live_handles.append(y_handle)
        unreferenced_entities = scope.get_unreferenced_entities("PROJECT_BOUNDARY", live_handles)
        assert len(unreferenced_entities) == 1
        assert scope.get_cached(unreferenced_entities[0]) == scope.get_cached(x_handle)


async def test_async_unreferenced_entities_half_live_handles_return_other_half(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        live_handles: list[EntityHandle] = []
        x = await scope.get_storage_root() / "x.txt"
        x.write_text("x")
        x_handle = await scope.store(x)
        y = await scope.get_storage_root() / "y.txt"
        y.write_text("y")
        y_handle = await scope.store(y)
        live_handles.append(y_handle)
        unreferenced_entities = await scope.get_unreferenced_entities("PROJECT_BOUNDARY", live_handles)
        assert len(unreferenced_entities) == 1
        assert await scope.get_cached(unreferenced_entities[0]) == await scope.get_cached(x_handle)


def test_unreferenced_entities_no_entity_live_handles_return_all_stored_handles(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        live_handles = [NO_ENTITY]
        x = scope.get_storage_root() / "x.txt"
        x.write_text("x")
        scope.store(x)
        unreferenced_entities = scope.get_unreferenced_entities("PROJECT_BOUNDARY", live_handles)
        assert len(unreferenced_entities) == 1


async def test_async_unreferenced_entities_no_entity_live_handles_return_all_stored_handles(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        live_handles = [NO_ENTITY]
        x = await scope.get_storage_root() / "x.txt"
        x.write_text("x")
        await scope.store(x)
        unreferenced_entities = await scope.get_unreferenced_entities("PROJECT_BOUNDARY", live_handles)
        assert len(unreferenced_entities) == 1


def test_unreferenced_entities_live_handle_no_subdirectory_of_context_raise_error(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        live_handles = [
            EntityHandle(
                is_blob=True,
                original_name="fake_name",
                entity_id=UUID("00000000-0000-0000-0000-000000000000"),
                opaque_identifier="WRONG_PROJECT_BOUNDARY/UUID:_DELIMITERmy_entity",
                mime_type=None,
                encoding=None,
                size=None,
            ),
        ]

        with pytest.raises(
            ValueError,
            match=re.escape(
                "The storage scope has been misconfigured: the scope directory "
                "'WRONG_PROJECT_BOUNDARY/UUID' is not a subdirectory of the "
                "'PROJECT_BOUNDARY' context",
            ),
        ):
            scope.get_unreferenced_entities("PROJECT_BOUNDARY", live_handles)


async def test_async_unreferenced_entities_live_handle_no_subdirectory_of_context_raise_error(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        live_handles = [
            EntityHandle(
                is_blob=True,
                original_name="fake_name",
                entity_id=UUID("00000000-0000-0000-0000-000000000000"),
                opaque_identifier="WRONG_PROJECT_BOUNDARY/UUID:_DELIMITERmy_entity",
                mime_type=None,
                encoding=None,
                size=None,
            ),
        ]

        with pytest.raises(
            ValueError,
            match=re.escape(
                "The storage scope has been misconfigured: the scope directory "
                "'WRONG_PROJECT_BOUNDARY/UUID' is not a subdirectory of the "
                "'PROJECT_BOUNDARY' context",
            ),
        ):
            await scope.get_unreferenced_entities("PROJECT_BOUNDARY", live_handles)


def test_entity_not_stored_is_destroyed_or_is_unreferenced_entities(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        assert len(scope.get_unreferenced_entities("PROJECT_BOUNDARY", [])) == 0
        x = scope.get_storage_root() / "x.txt"
        x.write_text("x")
        # intentionally not stored.
    # either the file is destroyed on scope exit or the file is detected by the unreference entities method
    assert not x.exists() or len(scope.get_unreferenced_entities("PROJECT_BOUNDARY", [])) == 1


async def test_async_entity_not_stored_is_destroyed_or_is_unreferenced_entities(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        assert len(await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [])) == 0
        x = await scope.get_storage_root() / "x.txt"
        x.write_text("x")
        # intentionally not stored.
    # either the file is destroyed on scope exit or the file is detected by the unreference entities method
    assert not x.exists() or len(await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [])) == 1


def test_unreferenced_file_in_subdirectory_is_destroyed(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x" / "x.txt"
        x.parent.mkdir()
        x.write_text("x")
        live_handle = scope.store(x)
        y = scope.get_storage_root() / "x" / "y.txt"
        y.write_text("y")
        dead_handle = scope.store(y)

    unreferenced = scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle])
    assert len(unreferenced) == 1
    assert unreferenced[0].original_name == dead_handle.original_name


async def test_async_unreferenced_file_in_subdirectory_is_destroyed(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x" / "x.txt"
        x.parent.mkdir()
        x.write_text("x")
        live_handle = await scope.store(x)
        y = await scope.get_storage_root() / "x" / "y.txt"
        y.write_text("y")
        dead_handle = await scope.store(y)

    unreferenced = await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle])
    assert len(unreferenced) == 1
    assert unreferenced[0].original_name == dead_handle.original_name


def test_referenced_files_in_subdirectory_are_not_destroyed(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x" / "x.txt"
        x.parent.mkdir()
        x.write_text("x")
        live_handle1 = scope.store(x)
        y = scope.get_storage_root() / "x" / "y.txt"
        y.write_text("y")
        live_handle2 = scope.store(y)

    unreferenced = scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle1, live_handle2])
    assert len(unreferenced) == 0


async def test_async_referenced_files_in_subdirectory_are_not_destroyed(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x" / "x.txt"
        x.parent.mkdir()
        x.write_text("x")
        live_handle1 = await scope.store(x)
        y = await scope.get_storage_root() / "x" / "y.txt"
        y.write_text("y")
        live_handle2 = await scope.store(y)

    unreferenced = await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle1, live_handle2])
    assert len(unreferenced) == 0


def test_unreferenced_file_in_referenced_subdirectory_is_not_destroyed(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x"
        x.mkdir()
        y = x / "y.txt"
        y.write_text("y")
        live_handle = scope.store(x)

    unreferenced = scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle])
    assert len(unreferenced) == 0


async def test_async_unreferenced_file_in_referenced_subdirectory_is_not_destroyed(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x"
        x.mkdir()
        y = x / "y.txt"
        y.write_text("y")
        live_handle = await scope.store(x)

    unreferenced = await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle])
    assert len(unreferenced) == 0


def test_referenced_file_in_referenced_subdirectory_is_not_destroyed(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x"
        x.mkdir()
        y = x / "y.txt"
        y.write_text("y")
        live_handle1 = scope.store(x)
        live_handle2 = scope.store(y)

    unreferenced = scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle1, live_handle2])
    assert len(unreferenced) == 0


async def test_async_referenced_file_in_referenced_subdirectory_is_not_destroyed(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        x = await scope.get_storage_root() / "x"
        x.mkdir()
        y = x / "y.txt"
        y.write_text("y")
        live_handle1 = await scope.store(x)
        live_handle2 = await scope.store(y)

    unreferenced = await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle1, live_handle2])
    assert len(unreferenced) == 0


def test_get_unreferenced_entities_is_robust_to_a_storage_scope_root_being_replaced_with_a_file(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    # GIVEN - storage root and a handle referring to a file inside it
    with storage_scope_factory() as scope:
        storage_root = scope.get_storage_root()
        x = storage_root / "x.txt"
        x.write_text("x")
        live_handle = scope.store(x)

    # WHEN - the storage root is replaced with a file (a violation of the contract)
    shutil.rmtree(storage_root)
    storage_root.write_text("JUNK")

    # THEN - the get_unreferenced_entities method should either
    # - not raise an exception (the result is undefined) or
    # - raise EntityNotFoundInBlobStorageError
    with contextlib.suppress(EntityNotFoundInBlobStorageError):
        scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle])


async def test_async_get_unreferenced_entities_is_robust_to_a_storage_scope_root_being_replaced_with_a_file(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    # GIVEN - storage root and a handle referring to a file inside it
    async with await async_storage_scope_factory() as scope:
        storage_root = await scope.get_storage_root()
        x = storage_root / "x.txt"
        x.write_text("x")
        live_handle = await scope.store(x)

    # WHEN - the storage root is replaced with a file (a violation of the contract)
    shutil.rmtree(storage_root)
    storage_root.write_text("JUNK")

    # THEN - the get_unreferenced_entities method should either
    # - not raise an exception (the result is undefined) or
    # - raise EntityNotFoundInBlobStorageError
    with contextlib.suppress(EntityNotFoundInBlobStorageError):
        await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle])


def test_get_unreferenced_entities_directory_containing_a_referenced_file_being_replaced_with_a_file(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    # GIVEN - storage root and a handle referring to a file inside a directory inside the storage root
    with storage_scope_factory() as scope:
        test_dir = scope.get_storage_root() / "to_be_replaced"
        test_dir.mkdir()
        x = test_dir / "x.txt"
        x.write_text("x")
        live_handle = scope.store(x)

    # WHEN - the directory is replaced with a file (a violation of the contract)
    shutil.rmtree(test_dir)
    test_dir.write_text("JUNK")

    # THEN - the get_unreferenced_entities method should either
    # - not raise an exception (the result is undefined) or
    # - raise EntityNotFoundInBlobStorageError
    with contextlib.suppress(EntityNotFoundInBlobStorageError):
        scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle])


async def test_async_get_unreferenced_entities_directory_containing_a_referenced_file_being_replaced_with_a_file(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    # GIVEN - storage root and a handle referring to a file inside a directory inside the storage root
    async with await async_storage_scope_factory() as scope:
        test_dir = await scope.get_storage_root() / "to_be_replaced"
        test_dir.mkdir()
        x = test_dir / "x.txt"
        x.write_text("x")
        live_handle = await scope.store(x)

    # WHEN - the directory is replaced with a file (a violation of the contract)
    shutil.rmtree(test_dir)
    test_dir.write_text("JUNK")

    # THEN - the get_unreferenced_entities method should either
    # - not raise an exception (the result is undefined) or
    # - raise EntityNotFoundInBlobStorageError
    with contextlib.suppress(EntityNotFoundInBlobStorageError):
        await scope.get_unreferenced_entities("PROJECT_BOUNDARY", [live_handle])
