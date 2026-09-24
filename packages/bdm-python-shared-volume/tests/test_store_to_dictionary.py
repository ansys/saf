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
    IAsyncStorageScope,
    IStorageScope,
    NotFoundInLocalStorageRootError,
    RecursiveDictionaryOfEntityHandles,
)
from tests.content import CONTENT


def test_store_to_dictionary_outside_storage_root(scope: IStorageScope, tmp_path: Path):
    """Test that storing a single file with glob pattern raises an exception."""
    file_path = tmp_path / "test_file.txt"
    file_path.write_text(CONTENT)

    with pytest.raises(NotFoundInLocalStorageRootError, match="root path is not within the storage root."):
        scope.store_to_dictionary(file_path, glob="*.txt")


async def test_store_to_dictionary_outside_storage_root_async(async_scope: IAsyncStorageScope, tmp_path: Path):
    """Test that storing a single file with glob pattern raises an exception."""
    file_path = tmp_path / "test_file.txt"
    file_path.write_text(CONTENT)

    with pytest.raises(NotFoundInLocalStorageRootError, match="root path is not within the storage root."):
        await async_scope.store_to_dictionary(file_path, glob="*.txt")


def test_store_to_dictionary_inexistent_path(scope: IStorageScope):
    """Test that storing a single file with glob pattern raises an exception."""
    inexistent_path = scope.get_storage_root() / "inexistent_file.txt"

    with pytest.raises(FileNotFoundError, match="root path does not exist"):
        scope.store_to_dictionary(inexistent_path, glob="*.txt")


async def test_store_to_dictionary_inexistent_path_async(async_scope: IAsyncStorageScope):
    """Test that storing a single file with glob pattern raises an exception."""
    inexistent_path = await async_scope.get_storage_root() / "inexistent_file.txt"

    with pytest.raises(FileNotFoundError, match="root path does not exist"):
        await async_scope.store_to_dictionary(inexistent_path, glob="*.txt")


def test_store_to_dictionary_with_single_file_raises_exception(scope: IStorageScope):
    """Test storing a single file to dictionary raises an exception."""
    file_path = scope.get_storage_root() / "test_file.txt"
    file_path.write_text(CONTENT)

    with pytest.raises(NotADirectoryError, match="root path is a file"):
        scope.store_to_dictionary(file_path)


async def test_store_to_dictionary_with_single_file_raises_exception_async(async_scope: IAsyncStorageScope):
    """Test storing a single file to dictionary raises an exception."""
    file_path = await async_scope.get_storage_root() / "test_file.txt"
    file_path.write_text(CONTENT)

    with pytest.raises(NotADirectoryError, match="root path is a file"):
        await async_scope.store_to_dictionary(file_path)


def _verify_dictionary(recursive_dict: RecursiveDictionaryOfEntityHandles, txt_only: bool = False):
    if txt_only:
        assert sorted(recursive_dict.keys()) == sorted([".hidden_file.txt", "single_file.txt", "level1"])
    else:
        assert sorted(recursive_dict.keys()) == sorted(
            [".hidden_file.txt", "single_file.txt", "level1", "empty_dir_root", "src", "file.multiple.dots.json"],
        )
        assert isinstance(recursive_dict["file.multiple.dots.json"], EntityHandle)
        empty_dir_root_dict = recursive_dict["empty_dir_root"]
        assert isinstance(empty_dir_root_dict, dict)
        assert len(empty_dir_root_dict) == 0
        src_dict = recursive_dict["src"]
        assert isinstance(src_dict, dict)
        assert list(src_dict.keys()) == ["main.py"]
        assert isinstance(src_dict["main.py"], EntityHandle)

    assert isinstance(recursive_dict[".hidden_file.txt"], EntityHandle)
    assert isinstance(recursive_dict["single_file.txt"], EntityHandle)

    level1_dict = recursive_dict["level1"]
    assert isinstance(level1_dict, dict)
    if txt_only:
        assert sorted(level1_dict.keys()) == sorted(["level2"])
    else:
        assert sorted(level1_dict.keys()) == sorted(["level2", "empty_dir_nested"])
        empty_dir_nested_dict = level1_dict["empty_dir_nested"]
        assert isinstance(empty_dir_nested_dict, dict)
        assert len(empty_dir_nested_dict) == 0
    assert "level2" in level1_dict
    level2_dict = level1_dict["level2"]
    assert isinstance(level2_dict, dict)
    assert list(level2_dict.keys()) == ["deep_file.txt"]
    assert isinstance(level2_dict["deep_file.txt"], EntityHandle)


def test_store_to_dictionary_with_directory_no_glob(scope: IStorageScope, test_root: Path):
    """Test storing a directory to dictionary without glob pattern - all files and dirs included."""
    result = scope.store_to_dictionary(test_root)

    _verify_dictionary(result)


async def test_store_to_dictionary_with_directory_no_glob_async(async_scope: IAsyncStorageScope, async_test_root: Path):
    """Test storing a directory to dictionary without glob pattern - all files and dirs included."""
    result = await async_scope.store_to_dictionary(async_test_root)

    _verify_dictionary(result)


def test_store_to_dictionary_with_directory_with_glob_single_file(scope: IStorageScope, test_root: Path):
    """Test storing a directory to dictionary with glob pattern - only matching file included."""
    result = scope.store_to_dictionary(test_root, glob="file.multiple.dots.json")

    assert list(result.keys()) == ["file.multiple.dots.json"]
    file_with_dots = result["file.multiple.dots.json"]
    assert isinstance(file_with_dots, EntityHandle)
    assert scope.get_text(file_with_dots) == '{"key": "value"}'


async def test_store_to_dictionary_with_directory_with_glob_single_file_async(
    async_scope: IAsyncStorageScope,
    async_test_root: Path,
):
    """Test storing a directory to dictionary with glob pattern - only matching file included."""
    result = await async_scope.store_to_dictionary(async_test_root, glob="file.multiple.dots.json")

    assert list(result.keys()) == ["file.multiple.dots.json"]
    file_with_dots = result["file.multiple.dots.json"]
    assert isinstance(file_with_dots, EntityHandle)
    assert await async_scope.get_text(file_with_dots) == '{"key": "value"}'


def test_store_to_dictionary_with_directory_with_glob_single_directory(scope: IStorageScope, test_root: Path):
    """Test storing a directory to dictionary with glob pattern - only matching directory included
    without its contents."""
    result = scope.store_to_dictionary(test_root, glob="src/")

    assert list(result.keys()) == ["src"]
    src_dict = result["src"]
    assert isinstance(src_dict, dict)
    assert len(src_dict) == 0  # no contents included, missing "*" in glob


async def test_store_to_dictionary_with_directory_with_glob_single_directory_async(
    async_scope: IAsyncStorageScope,
    async_test_root: Path,
):
    """Test storing a directory to dictionary with glob pattern - only matching directory included,
    without its contents."""
    result = await async_scope.store_to_dictionary(async_test_root, glob="src/")

    assert list(result.keys()) == ["src"]
    src_dict = result["src"]
    assert isinstance(src_dict, dict)
    assert len(src_dict) == 0  # no contents included, missing "*" in glob


def test_store_to_dictionary_with_directory_with_glob_matching_files_in_root_and_subdirs(
    scope: IStorageScope,
    test_root: Path,
):
    """Test storing a directory to dictionary with glob pattern with wildcards - only matching files included."""
    result = scope.store_to_dictionary(test_root, glob="**/*.txt")

    _verify_dictionary(result, txt_only=True)


async def test_store_to_dictionary_with_directory_with_glob_matching_files_in_root_and_subdirs_async(
    async_scope: IAsyncStorageScope,
    async_test_root: Path,
):
    """Test storing a directory to dictionary with glob pattern - only matching files included."""
    result = await async_scope.store_to_dictionary(async_test_root, glob="**/*.txt")

    _verify_dictionary(result, txt_only=True)


def test_store_to_dictionary_with_directory_matching_glob(scope: IStorageScope, test_root: Path):
    """Test that a directory matching glob includes all its contents."""
    result = scope.store_to_dictionary(test_root, glob="src/*")

    assert list(result.keys()) == ["src"]
    src_dict = result["src"]
    assert isinstance(src_dict, dict)
    assert list(src_dict.keys()) == ["main.py"]
    main_file = src_dict["main.py"]
    assert isinstance(main_file, EntityHandle)
    assert scope.get_text(main_file) == "main source"


async def test_store_to_dictionary_with_directory_matching_glob_async(
    async_scope: IAsyncStorageScope,
    async_test_root: Path,
):
    """Test that a directory matching glob includes all its contents."""
    result = await async_scope.store_to_dictionary(async_test_root, glob="src/*")

    assert list(result.keys()) == ["src"]
    src_dict = result["src"]
    assert isinstance(src_dict, dict)
    assert list(src_dict.keys()) == ["main.py"]
    main_file = src_dict["main.py"]
    assert isinstance(main_file, EntityHandle)
    assert await async_scope.get_text(main_file) == "main source"


def test_store_to_dictionary_with_glob_empty_directory_matched(scope: IStorageScope, test_root: Path):
    """Test storing directory with glob that matches empty directories at different levels."""
    result = scope.store_to_dictionary(test_root, glob="empty_dir*")

    assert result == {"empty_dir_root": {}, "level1": {"empty_dir_nested": {}}}


async def test_store_to_dictionary_with_glob_empty_directory_matched_async(
    async_scope: IAsyncStorageScope,
    async_test_root: Path,
):
    """Test storing directory with glob that matches empty directories at different levels."""
    result = await async_scope.store_to_dictionary(async_test_root, glob="empty_dir*")

    assert result == {"empty_dir_root": {}, "level1": {"empty_dir_nested": {}}}


def test_store_to_dictionary_with_glob_no_matches(scope: IStorageScope, test_root: Path):
    """Test storing directory with glob that matches nothing returns empty dict."""
    result = scope.store_to_dictionary(test_root, glob="**/*.aedt")

    assert result == {}


async def test_store_to_dictionary_with_glob_no_matches_async(async_scope: IAsyncStorageScope, async_test_root: Path):
    """Test storing directory with glob that matches nothing returns empty dict."""
    result = await async_scope.store_to_dictionary(async_test_root, glob="**/*.aedt")

    assert result == {}
