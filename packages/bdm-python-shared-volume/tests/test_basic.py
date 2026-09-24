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
    InvalidContextError,
    IStorageScopeFactory,
    NotFoundInLocalStorageRootError,
)
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory


# TODO: Should we assume that all possible BDM implementations have the same rules on contexts?
def test_passing_junk_context_to_factory_results_in_exception(
    storage_scope_factory_under_test: IStorageScopeFactory,
):
    with pytest.raises(InvalidContextError):
        storage_scope_factory_under_test.create_storage_scope("JUNK", {"TEMP_DIR": "", "UUID": "", "PROJECT_ID": ""})


async def test_passing_junk_context_to_factory_results_in_exception_async(
    storage_scope_factory_under_test: IStorageScopeFactory,
):
    with pytest.raises(InvalidContextError):
        await storage_scope_factory_under_test.create_async_storage_scope(
            "JUNK",
            {"TEMP_DIR": "", "UUID": "", "PROJECT_ID": ""},
        )


def test_cannot_store_non_existent_path(storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        path = scope.get_storage_root() / "JUNK"
        with pytest.raises(NotFoundInLocalStorageRootError):
            scope.store(path)


async def test_cannot_store_non_existent_path_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    async with await async_storage_scope_factory() as scope:
        path = await scope.get_storage_root() / "JUNK"
        with pytest.raises(NotFoundInLocalStorageRootError):
            await scope.store(path)


# TODO: where is tmp_path defined, and is it true of all generic BDM implementations that this holds?
def test_storage_root_is_inside_temp_dir(tmp_path: Path, storage_scope_factory: SimpleStorageScopeFactory):
    with storage_scope_factory() as scope:
        scope.get_storage_root().relative_to(tmp_path)


async def test_storage_root_is_inside_temp_dir_async(
    tmp_path: Path,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        (await scope.get_storage_root()).relative_to(tmp_path)


def test_storage_root_is_not_created_by_scope_factory(tmp_path: Path, storage_scope_factory: SimpleStorageScopeFactory):
    storage_scope_factory()
    assert not any(x for x in tmp_path.iterdir())


async def test_storage_root_is_not_created_by_scope_factory_async(
    tmp_path: Path,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    await async_storage_scope_factory()
    assert not any(x for x in tmp_path.iterdir())  # noqa: ASYNC240
