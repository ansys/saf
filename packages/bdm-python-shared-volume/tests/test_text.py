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

import codecs
from pathlib import Path
import shutil

import pytest

from ansys.bdm.api.entity_handle import EntityHandle
from ansys.bdm.api.storage_exceptions import CannotGenerateStreamForDirectoryError
from ansys.bdm.base.encoder import decode_bom
from tests.conftest import SimpleAsyncStorageScopeFactory, SimpleStorageScopeFactory
from tests.content import CONTENT

TEST_FILE_NAME_PARTS = ["8", "16", "16BE", "32", "32BE"]
TEST_FILE_CONTENT = "私は短くて太くて少しエンコードしています\n"


def _assert_strings_are_equal_ignoring_line_breaks(expected: str, actual: str):
    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()
    assert len(expected_lines) == len(actual_lines)
    for expected_line, actual_line in zip(expected_lines, actual_lines, strict=False):
        assert expected_line == actual_line


# this is sanity check for the tests in this module
def test_using_utf_16_le_encoding_creates_bytes_without_bom():
    content_bytes = TEST_FILE_CONTENT.encode("utf-16-le")
    (encoding, length) = decode_bom(content_bytes)
    assert encoding is None
    assert length == 0


def test_read_text_returns_basic_content_as_expected_by_default(
    file_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope:
        assert scope.get_text(file_entity) == CONTENT


async def test_read_text_returns_basic_content_as_expected_by_default_async(
    file_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        content = await scope.get_text(file_entity)
        assert content == CONTENT


def test_cannot_read_text_from_directory(
    directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    with storage_scope_factory() as scope, pytest.raises(CannotGenerateStreamForDirectoryError):
        scope.get_text(directory_entity)


async def test_cannot_read_text_from_directory_async(
    directory_entity: EntityHandle,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    async with await async_storage_scope_factory() as scope:
        with pytest.raises(CannotGenerateStreamForDirectoryError):
            await scope.get_text(directory_entity)


def test_read_text_returns_utf_8_by_default(storage_scope_factory: SimpleStorageScopeFactory):
    content_bytes = TEST_FILE_CONTENT.encode("utf-8")
    with storage_scope_factory() as scope:
        handle = scope.store_stream(content_bytes)

    with storage_scope_factory() as scope:
        assert scope.get_text(handle) == TEST_FILE_CONTENT


async def test_read_text_returns_utf_8_by_default_async(async_storage_scope_factory: SimpleAsyncStorageScopeFactory):
    content_bytes = TEST_FILE_CONTENT.encode("utf-8")
    async with await async_storage_scope_factory() as scope:
        handle = await scope.store_stream(content_bytes)

    async with await async_storage_scope_factory() as scope:
        text = await scope.get_text(handle)
        assert text == TEST_FILE_CONTENT


def test_read_text_returns_string_in_requested_encoding(storage_scope_factory: SimpleStorageScopeFactory):
    content_bytes = TEST_FILE_CONTENT.encode("utf-16-le")
    with storage_scope_factory() as scope:
        handle = scope.store_stream(content_bytes)

    with storage_scope_factory() as scope:
        assert scope.get_text(handle, encoding="utf-16") == TEST_FILE_CONTENT


async def test_read_text_returns_string_in_requested_encoding_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    content_bytes = TEST_FILE_CONTENT.encode("utf-16-le")
    async with await async_storage_scope_factory() as scope:
        handle = await scope.store_stream(content_bytes)

    async with await async_storage_scope_factory() as scope:
        text = await scope.get_text(handle, "utf-16")
        assert text == TEST_FILE_CONTENT


def test_read_text_returns_string_in_bom_encoding_when_present(storage_scope_factory: SimpleStorageScopeFactory):
    original_encoded = TEST_FILE_CONTENT.encode("utf-16-le")
    data_bytes = codecs.BOM_UTF16_LE + original_encoded
    with storage_scope_factory() as scope:
        handle = scope.store_stream(data_bytes)

    with storage_scope_factory() as scope:
        assert scope.get_text(handle) == TEST_FILE_CONTENT


async def test_read_text_returns_string_in_bom_encoding_when_present_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    original_encoded = TEST_FILE_CONTENT.encode("utf-16-le")
    data_bytes = codecs.BOM_UTF16_LE + original_encoded
    async with await async_storage_scope_factory() as scope:
        handle = await scope.store_stream(data_bytes)

    async with await async_storage_scope_factory() as scope:
        text = await scope.get_text(handle)
        assert text == TEST_FILE_CONTENT


@pytest.mark.parametrize("test_file_name_part", TEST_FILE_NAME_PARTS)
def test_can_recover_text_from_files_with_bom_prefix(
    test_file_name_part: str,
    storage_scope_factory: SimpleStorageScopeFactory,
):
    source_file = Path(__file__).parent / "test_data" / f"BOM-utf-{test_file_name_part}.txt"
    assert source_file.is_file()

    with storage_scope_factory() as scope:
        stored_file = scope.get_storage_root() / "x.txt"
        shutil.copy(source_file, stored_file)
        handle = scope.store(stored_file)

    with storage_scope_factory() as scope:
        _assert_strings_are_equal_ignoring_line_breaks(TEST_FILE_CONTENT, scope.get_text(handle))


@pytest.mark.parametrize("test_file_name_part", TEST_FILE_NAME_PARTS)
async def test_can_recover_text_from_files_with_bom_prefix_async(
    test_file_name_part: str,
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    source_file = Path(__file__).parent / "test_data" / f"BOM-utf-{test_file_name_part}.txt"
    assert source_file.is_file()

    async with await async_storage_scope_factory() as scope:
        stored_file = await scope.get_storage_root() / "x.txt"
        shutil.copy(source_file, stored_file)
        handle = await scope.store(stored_file)

    async with await async_storage_scope_factory() as scope:
        content = await scope.get_text(handle)
        _assert_strings_are_equal_ignoring_line_breaks(TEST_FILE_CONTENT, content)


def test_get_text_uses_the_entity_handle_encoding_when_it_is_present(storage_scope_factory: SimpleStorageScopeFactory):
    content_bytes = TEST_FILE_CONTENT.encode("utf-16-le")
    with storage_scope_factory() as scope:
        handle = scope.store_stream(content_bytes, encoding="utf-16")

    with storage_scope_factory() as scope:
        assert scope.get_text(handle) == TEST_FILE_CONTENT


async def test_get_text_uses_the_entity_handle_encoding_when_it_is_present_async(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
):
    content_bytes = TEST_FILE_CONTENT.encode("utf-16-le")
    async with await async_storage_scope_factory() as scope:
        handle = await scope.store_stream(content_bytes, encoding="utf-16")

    async with await async_storage_scope_factory() as scope:
        text = await scope.get_text(handle)
        assert text == TEST_FILE_CONTENT
