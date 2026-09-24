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

from ansys.bdm.api import (
    EntityHandle,
    EntityNotFoundInBlobStorageError,
    NotFoundInLocalStorageRootError,
)
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory
from tests.content import (
    CONTENT,
    assert_directory_content,
    assert_subdirectory_content,
    create_directory_content,
)


def test_directory_check_is_consistent(tmp_path: Path):
    assert_directory_content(create_directory_content(tmp_path))


def test_get_children_file_entity_raises(file_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(NotADirectoryError):
        scope.get_children(file_entity)


async def test_get_children_file_entity_raises_async(
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(NotADirectoryError):
            async for _ in scope.get_children(file_entity):
                pass


def test_directory_entity_default_metadata(directory_entity: EntityHandle):
    assert directory_entity.size is None
    assert directory_entity.mime_type is None
    assert directory_entity.encoding is None


def test_getting_child_of_file_entity_raises_exception(
    file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(NotADirectoryError):
        scope.get_child(file_entity, "x.txt")


async def test_getting_child_of_file_entity_raises_exception_async(
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(NotADirectoryError):
            await scope.get_child(file_entity, "x.txt")


def test_can_get_children_of_directory(
    directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        top_children = scope.get_children(directory_entity)
        assert {"subtop", "empty"} == {child.original_name for child in top_children}


async def test_can_get_children_of_directory_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        top_children = scope.get_children(directory_entity)
        assert {"subtop", "empty"} == {child.original_name async for child in top_children}


def test_can_get_child_of_directory(directory_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        subtop = scope.get_child(directory_entity, "subtop")
        assert subtop.original_name == "subtop"


async def test_can_get_child_of_directory_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        subtop = await scope.get_child(directory_entity, "subtop")
        assert subtop.original_name == "subtop"


def test_get_inexistent_child_of_directory_raises_error(
    directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:  # noqa: SIM117
        with pytest.raises(EntityNotFoundInBlobStorageError, match="not_subtop not found"):
            scope.get_child(directory_entity, "not_subtop")


async def test_get_inexistent_child_of_directory_raises_error_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(EntityNotFoundInBlobStorageError, match="not_subtop not found"):
            await scope.get_child(directory_entity, "not_subtop")


def test_can_get_children_of_nested_directory(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        create_directory_content(scope.get_storage_root())
        subtop = scope.store(scope.get_storage_root() / "top" / "subtop")
    with storage_scope_factory() as scope:
        subtop_children = scope.get_children(subtop)
        assert [child.original_name for child in subtop_children] == ["leaf.txt"]


async def test_can_get_children_of_nested_directory_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        create_directory_content(await scope.get_storage_root())
        subtop = await scope.store(await scope.get_storage_root() / "top" / "subtop")
    async with await async_storage_scope_factory() as scope:
        subtop_children = scope.get_children(subtop)
        assert [child.original_name async for child in subtop_children] == ["leaf.txt"]


def test_can_get_child_of_nested_directory(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        create_directory_content(scope.get_storage_root())
        subtop = scope.store(scope.get_storage_root() / "top" / "subtop")
    with storage_scope_factory() as scope:
        assert scope.get_child(subtop, "leaf.txt").original_name == "leaf.txt"


async def test_can_get_child_of_nested_directory_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        create_directory_content(await scope.get_storage_root())
        subtop = await scope.store(await scope.get_storage_root() / "top" / "subtop")
    async with await async_storage_scope_factory() as scope:
        assert (await scope.get_child(subtop, "leaf.txt")).original_name == "leaf.txt"


def test_can_get_cached_directory(directory_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        assert_directory_content(scope.get_cached(directory_entity))


async def test_can_get_cached_directory_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        assert_directory_content(await scope.get_cached(directory_entity))


def test_can_get_copy_of_directory(directory_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory):
    alt_name = "top_copy"
    with storage_scope_factory() as scope:
        top_copy = scope.get_storage_root() / alt_name
        scope.get_copy(directory_entity, top_copy)
    assert not top_copy.exists()


async def test_can_get_copy_of_directory_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    alt_name = "top_copy"
    async with await async_storage_scope_factory() as scope:
        top_copy = await scope.get_storage_root() / alt_name
        await scope.get_copy(directory_entity, top_copy)
    assert not top_copy.exists()


def test_can_get_file_stored_in_directory(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        create_directory_content(scope.get_storage_root())
        leaf = scope.get_storage_root() / "top" / "subtop" / "leaf.txt"
        assert leaf.is_file()  # just checking
        leaf_handle = scope.store(leaf)
    with storage_scope_factory() as scope:
        leaf = scope.get_cached(leaf_handle)
        assert leaf.read_text() == CONTENT


async def test_can_get_file_stored_in_directory_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        create_directory_content(await scope.get_storage_root())
        leaf = await scope.get_storage_root() / "top" / "subtop" / "leaf.txt"
        assert leaf.is_file()  # just checking
        leaf_handle = await scope.store(leaf)
    async with await async_storage_scope_factory() as scope:
        leaf = await scope.get_cached(leaf_handle)
        assert leaf.read_text() == CONTENT


def test_can_get_subdirectory_stored_in_directory(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        create_directory_content(scope.get_storage_root())
        subtop = scope.get_storage_root() / "top" / "subtop"
        assert subtop.is_dir()  # just checking
        subtop_handle = scope.store(subtop)
    with storage_scope_factory() as scope:
        subtop = scope.get_cached(subtop_handle)
        assert_subdirectory_content(subtop)


async def test_can_get_subdirectory_stored_in_directory_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        create_directory_content(await scope.get_storage_root())
        subtop = await scope.get_storage_root() / "top" / "subtop"
        assert subtop.is_dir()  # just checking
        subtop_handle = await scope.store(subtop)
    async with await async_storage_scope_factory() as scope:
        subtop = await scope.get_cached(subtop_handle)
        assert_subdirectory_content(subtop)


def test_can_get_file_stored_in_directory_preserving_relative_paths_to_other_handles(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        top = create_directory_content(scope.get_storage_root())
        leaf = scope.get_storage_root() / "top" / "subtop" / "leaf.txt"
        top_handle = scope.store(top)
        leaf_handle = scope.store(leaf)
    with storage_scope_factory() as scope:
        top = scope.get_cached(top_handle)
        leaf = scope.get_cached(leaf_handle)
        assert leaf == top / "subtop" / "leaf.txt"


async def test_can_get_file_stored_in_directory_preserving_relative_paths_to_other_handles_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        top = create_directory_content(await scope.get_storage_root())
        leaf = await scope.get_storage_root() / "top" / "subtop" / "leaf.txt"
        top_handle = await scope.store(top)
        leaf_handle = await scope.store(leaf)
    async with await async_storage_scope_factory() as scope:
        top = await scope.get_cached(top_handle)
        leaf = await scope.get_cached(leaf_handle)
        assert leaf == top / "subtop" / "leaf.txt"


def test_can_get_subdirectory_stored_in_directory_preserving_relative_paths_to_other_handles(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        top = create_directory_content(scope.get_storage_root())
        subtop = scope.get_storage_root() / "top" / "subtop"
        top_handle = scope.store(top)
        subtop_handle = scope.store(subtop)
    with storage_scope_factory() as scope:
        top = scope.get_cached(top_handle)
        subtop = scope.get_cached(subtop_handle)
        assert subtop == top / "subtop"


async def test_can_get_subdirectory_stored_in_directory_preserving_relative_paths_to_other_handles_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        top = create_directory_content(await scope.get_storage_root())
        subtop = await scope.get_storage_root() / "top" / "subtop"
        top_handle = await scope.store(top)
        subtop_handle = await scope.store(subtop)
    async with await async_storage_scope_factory() as scope:
        top = await scope.get_cached(top_handle)
        subtop = await scope.get_cached(subtop_handle)
        assert subtop == top / "subtop"


def test_can_get_file_stored_in_directory_preserving_relative_paths_to_other_handles_reverse_order(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        top = create_directory_content(scope.get_storage_root())
        leaf = scope.get_storage_root() / "top" / "subtop" / "leaf.txt"
        leaf_handle = scope.store(leaf)
        top_handle = scope.store(top)
    with storage_scope_factory() as scope:
        leaf = scope.get_cached(leaf_handle)
        top = scope.get_cached(top_handle)
        assert leaf == top / "subtop" / "leaf.txt"


async def test_can_get_file_stored_in_directory_preserving_relative_paths_to_other_handles_reverse_order_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        top = create_directory_content(await scope.get_storage_root())
        leaf = await scope.get_storage_root() / "top" / "subtop" / "leaf.txt"
        leaf_handle = await scope.store(leaf)
        top_handle = await scope.store(top)
    async with await async_storage_scope_factory() as scope:
        leaf = await scope.get_cached(leaf_handle)
        top = await scope.get_cached(top_handle)
        assert leaf == top / "subtop" / "leaf.txt"


def test_can_get_subdirectory_stored_in_directory_preserving_relative_paths_to_other_handles_reverse_order(
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        top = create_directory_content(scope.get_storage_root())
        subtop = scope.get_storage_root() / "top" / "subtop"
        subtop_handle = scope.store(subtop)
        top_handle = scope.store(top)
    with storage_scope_factory() as scope:
        subtop = scope.get_cached(subtop_handle)
        top = scope.get_cached(top_handle)
        assert subtop == top / "subtop"


async def test_can_get_subdirectory_stored_in_directory_preserving_relative_paths_to_other_handles_reverse_order_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        top = create_directory_content(await scope.get_storage_root())
        subtop = await scope.get_storage_root() / "top" / "subtop"
        subtop_handle = await scope.store(subtop)
        top_handle = await scope.store(top)
    async with await async_storage_scope_factory() as scope:
        subtop = await scope.get_cached(subtop_handle)
        top = await scope.get_cached(top_handle)
        assert subtop == top / "subtop"


def test_get_parent_of_top_level_file_returns_none(
    file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        assert scope.get_parent(file_entity) is None


async def test_get_parent_of_top_level_file_returns_none_async(
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        assert await scope.get_parent(file_entity) is None


def test_get_parent_of_top_level_directory_returns_none(
    directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        assert scope.get_parent(directory_entity) is None


async def test_get_parent_of_top_level_directory_returns_none_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        assert await scope.get_parent(directory_entity) is None


def test_can_get_parents_of_nested_file(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        create_directory_content(scope.get_storage_root())
        leaf_handle = scope.store(scope.get_storage_root() / "top" / "subtop" / "leaf.txt")
    with storage_scope_factory() as scope:
        subtop_handle = scope.get_parent(leaf_handle)
        assert subtop_handle is not None
        top_handle = scope.get_parent(subtop_handle)
        assert top_handle is not None
        assert subtop_handle.original_name == "subtop"
        assert top_handle.original_name == "top"


async def test_can_get_parents_of_nested_file_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        create_directory_content(await scope.get_storage_root())
        leaf_handle = await scope.store(await scope.get_storage_root() / "top" / "subtop" / "leaf.txt")
    async with await async_storage_scope_factory() as scope:
        subtop_handle = await scope.get_parent(leaf_handle)
        assert subtop_handle is not None
        top_handle = await scope.get_parent(subtop_handle)
        assert top_handle is not None
        assert subtop_handle.original_name == "subtop"
        assert top_handle.original_name == "top"


def test_parents_of_nested_file_are_consistent(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        create_directory_content(scope.get_storage_root())
        leaf_handle = scope.store(scope.get_storage_root() / "top" / "subtop" / "leaf.txt")
        subtop_handle = scope.store(scope.get_storage_root() / "top" / "subtop")
        top_handle = scope.store(scope.get_storage_root() / "top")
    with storage_scope_factory() as scope:
        derived_subtop_handle = scope.get_parent(leaf_handle)
        assert derived_subtop_handle is not None
        derived_top_handle = scope.get_parent(derived_subtop_handle)
        assert subtop_handle == derived_subtop_handle
        assert top_handle == derived_top_handle


async def test_parents_of_nested_file_are_consistent_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        create_directory_content(await scope.get_storage_root())
        leaf_handle = await scope.store(await scope.get_storage_root() / "top" / "subtop" / "leaf.txt")
        subtop_handle = await scope.store(await scope.get_storage_root() / "top" / "subtop")
        top_handle = await scope.store(await scope.get_storage_root() / "top")
    async with await async_storage_scope_factory() as scope:
        derived_subtop_handle = await scope.get_parent(leaf_handle)
        assert derived_subtop_handle is not None
        derived_top_handle = await scope.get_parent(derived_subtop_handle)
        assert subtop_handle == derived_subtop_handle
        assert top_handle == derived_top_handle


def test_can_get_parents_of_nested_directory(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        create_directory_content(scope.get_storage_root())
        subtop_handle = scope.store(scope.get_storage_root() / "top" / "subtop")
    with storage_scope_factory() as scope:
        top_handle = scope.get_parent(subtop_handle)
        assert top_handle is not None
        assert top_handle.original_name == "top"


async def test_can_get_parents_of_nested_directory_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        create_directory_content(await scope.get_storage_root())
        subtop_handle = await scope.store(await scope.get_storage_root() / "top" / "subtop")
    async with await async_storage_scope_factory() as scope:
        top_handle = await scope.get_parent(subtop_handle)
        assert top_handle is not None
        assert top_handle.original_name == "top"


def test_storing_the_storage_root_raises_exception(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope, pytest.raises(NotFoundInLocalStorageRootError):
        scope.store(scope.get_storage_root())


async def test_storing_the_storage_root_raises_exception_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(NotFoundInLocalStorageRootError):
            await scope.store(await scope.get_storage_root())


def test_is_blob_returns_true_for_a_file(file_entity: EntityHandle):
    assert file_entity.is_blob


def test_is_blob_returns_false_for_a_directory(directory_entity: EntityHandle):
    assert not directory_entity.is_blob


def test_is_blob_returns_true_for_a_deleted_file(destroyed_file_entity: EntityHandle):
    assert destroyed_file_entity.is_blob


def test_is_blob_returns_false_for_a_deleted_directory(destroyed_directory_entity: EntityHandle):
    assert not destroyed_directory_entity.is_blob
