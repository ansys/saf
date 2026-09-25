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

from ansys.bdm.api import EntityHandle, IAsyncStorageScope, IStorageScope, RecursiveDictionaryOfEntityHandles


def test_copy_from_dictionary_with_file_destination(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying to a file path raises NotADirectoryError."""
    dest_dir = tmp_path / "my_file.txt"
    dest_dir.touch()
    with pytest.raises(NotADirectoryError, match="destination path must be a directory"):
        scope.get_copy_from_dictionary(dest_dir, source_dict)


async def test_copy_from_dictionary_with_file_destination_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying to a file path raises NotADirectoryError."""
    dest_dir = tmp_path / "my_file.txt"
    dest_dir.touch()
    with pytest.raises(NotADirectoryError, match="destination path must be a directory"):
        await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict)


def _verify_copied_directory(dest_dir: Path, txt_only: bool = False) -> None:
    assert (dest_dir / ".hidden_file.txt").read_text() == "hidden content"
    assert (dest_dir / "single_file.txt").read_text() == "single content"
    assert (dest_dir / "level1" / "level2" / "deep_file.txt").read_text() == "deep content"

    if txt_only:
        assert not (dest_dir / "file.multiple.dots.json").exists()
        assert not (dest_dir / "empty_dir_root").exists()
        assert not (dest_dir / "src" / "main.py").exists()
        assert not (dest_dir / "level1" / "empty_dir_nested").exists()
    else:
        assert (dest_dir / "file.multiple.dots.json").read_text() == '{"key": "value"}'
        assert (dest_dir / "empty_dir_root").is_dir()
        assert (dest_dir / "src" / "main.py").read_text() == "main source"
        assert (dest_dir / "level1" / "empty_dir_nested").is_dir()


def test_copy_from_dictionary_no_glob(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary of entities to filesystem without glob - all files copied."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    scope.get_copy_from_dictionary(dest_dir, source_dict)

    _verify_copied_directory(dest_dir)


async def test_copy_from_dictionary_no_glob_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary of entities to filesystem without glob - all files copied."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict)

    _verify_copied_directory(dest_dir)


def test_copy_from_dictionary_with_glob_single_file(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary of entities with glob pattern - only matching file copied."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    scope.get_copy_from_dictionary(dest_dir, source_dict, glob="single_file.txt")

    assert list(dest_dir.iterdir()) == [dest_dir / "single_file.txt"]


async def test_copy_from_dictionary_with_glob_single_file_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary of entities with glob pattern - only matching file copied."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict, glob="single_file.txt")

    assert list(dest_dir.iterdir()) == [dest_dir / "single_file.txt"]


def test_copy_from_dictionary_with_glob_single_dir(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary of entities with glob pattern - only matching dir copied."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    scope.get_copy_from_dictionary(dest_dir, source_dict, glob="src/")

    assert list(dest_dir.iterdir()) == [dest_dir / "src"]  # no contents included, missing "*" in glob


async def test_copy_from_dictionary_with_glob_single_dir_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary of entities with glob pattern - only matching dir copied."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict, glob="src/")

    assert list(dest_dir.iterdir()) == [dest_dir / "src"]  # no contents included, missing "*" in glob


def test_copy_from_dictionary_with_glob(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary of entities with glob pattern - only matching files copied."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    scope.get_copy_from_dictionary(dest_dir, source_dict, glob="**/*.txt")

    _verify_copied_directory(dest_dir, txt_only=True)


async def test_copy_from_dictionary_with_glob_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary of entities with glob pattern - only matching files copied."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict, glob="**/*.txt")

    _verify_copied_directory(dest_dir, txt_only=True)


def test_copy_from_dictionary_uses_dictionary_keys_not_original_names(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test that copy_from_dictionary uses dictionary keys, not EntityHandle original_name."""
    source_dict["renamed_file.txt"] = source_dict.pop("single_file.txt")
    source_dict["renamed_subdir"] = source_dict.pop("level1")

    file = source_dict["renamed_file.txt"]
    assert isinstance(file, EntityHandle)
    assert file.original_name == "single_file.txt"

    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    scope.get_copy_from_dictionary(dest_dir, source_dict, glob="**/*.txt")

    actual = [path.relative_to(dest_dir) for path in dest_dir.rglob("*") if path.is_file()]
    expected = [
        Path(".hidden_file.txt"),
        Path("renamed_file.txt"),
        Path("renamed_subdir/level2/deep_file.txt"),
    ]
    assert sorted(actual) == sorted(expected)


async def test_copy_from_dictionary_uses_dictionary_keys_not_original_names_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test that copy_from_dictionary uses dictionary keys, not EntityHandle original_name."""
    async_source_dict["renamed_file.txt"] = async_source_dict.pop("single_file.txt")
    async_source_dict["renamed_subdir"] = async_source_dict.pop("level1")

    file = async_source_dict["renamed_file.txt"]
    assert isinstance(file, EntityHandle)
    assert file.original_name == "single_file.txt"

    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict, glob="*.txt")

    actual = [path.relative_to(dest_dir) for path in dest_dir.rglob("*") if path.is_file()]
    expected = [
        Path(".hidden_file.txt"),
        Path("renamed_file.txt"),
        Path("renamed_subdir/level2/deep_file.txt"),
    ]
    assert sorted(actual) == sorted(expected)


def test_copy_from_dictionary_with_glob_matching_directory(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test that when a directory matches glob, all its contents are copied."""
    dest_dir = tmp_path / "output"
    assert not dest_dir.exists()
    scope.get_copy_from_dictionary(dest_dir, source_dict, glob="src/*")

    assert [path.relative_to(dest_dir) for path in dest_dir.rglob("*")] == [Path("src"), Path("src/main.py")]


async def test_copy_from_dictionary_with_glob_matching_directory_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test that when a directory matches glob, all its contents are copied."""
    dest_dir = tmp_path / "output"
    assert not dest_dir.exists()
    await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict, glob="src/*")

    assert [path.relative_to(dest_dir) for path in dest_dir.rglob("*")] == [Path("src"), Path("src/main.py")]


@pytest.fixture
def existing_directory_with_content(tmp_path: Path) -> Path:
    dest_dir = tmp_path / "output"
    dest_dir.mkdir(parents=True)
    (dest_dir / "single_file.txt").write_text("old content 1")
    (dest_dir / "extra_file_not_in_new_directory.txt").write_text("old content 2")
    return dest_dir


def test_copy_from_dictionary_replaces_existing_directory(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    existing_directory_with_content: Path,
):
    """Test that copy_from_dictionary replaces (not merges) existing directories."""
    scope.get_copy_from_dictionary(existing_directory_with_content, source_dict)

    assert not (existing_directory_with_content / "extra_file_not_in_new_directory.txt").exists()
    _verify_copied_directory(existing_directory_with_content)


async def test_copy_from_dictionary_replaces_existing_directory_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    existing_directory_with_content: Path,
):
    """Test that copy_from_dictionary replaces (not merges) existing directories."""
    await async_scope.get_copy_from_dictionary(existing_directory_with_content, async_source_dict)

    assert not (existing_directory_with_content / "extra_file_not_in_new_directory.txt").exists()
    _verify_copied_directory(existing_directory_with_content)


def test_copy_from_dictionary_subset(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a subset of a dictionary of entities to filesystem works due to the recursive nature of
    RecursiveDictionaryOfEntityHandles."""
    dest_dir = tmp_path / "output"

    subsource_dict = source_dict["src"]
    assert isinstance(subsource_dict, dict)
    scope.get_copy_from_dictionary(dest_dir, subsource_dict)

    assert list(dest_dir.iterdir()) == [dest_dir / "main.py"]


async def test_copy_from_dictionary_subset_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a subset of a dictionary of entities to filesystem works due to the recursive nature of
    RecursiveDictionaryOfEntityHandles."""
    dest_dir = tmp_path / "output"

    subsource_dict = async_source_dict["src"]
    assert isinstance(subsource_dict, dict)
    await async_scope.get_copy_from_dictionary(dest_dir, subsource_dict)

    assert list(dest_dir.iterdir()) == [dest_dir / "main.py"]


INVALID_DICT_KEYS = [
    ("", "Path component cannot be empty"),
    (".", "Path component cannot be '.'"),
    ("my_file/with\\manyslashes", "contains invalid characters"),
    ("another<wrong*?key>.txt", "contains invalid characters"),
    ("file_with_trailing_space ", "cannot end with a dot or space"),
]


@pytest.mark.parametrize(("invalid_key", "expected_message"), INVALID_DICT_KEYS)
def test_copy_from_dictionary_invalid_keys(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
    invalid_key: str,
    expected_message: str,
):
    """Test that invalid keys in the dictionary raise ValueError when trying to get a copy."""
    dest_dir = tmp_path / "output"
    source_dict[invalid_key] = source_dict.pop("single_file.txt")

    with pytest.raises(ValueError, match=expected_message):
        scope.get_copy_from_dictionary(dest_dir, source_dict)


@pytest.mark.parametrize(("invalid_key", "expected_message"), INVALID_DICT_KEYS)
async def test_copy_from_dictionary_invalid_keys_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
    invalid_key: str,
    expected_message: str,
):
    """Test that invalid keys in the dictionary raise ValueError when trying to get a copy."""
    dest_dir = tmp_path / "output"
    async_source_dict[invalid_key] = async_source_dict.pop("single_file.txt")

    with pytest.raises(ValueError, match=expected_message):
        await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict)


@pytest.mark.parametrize("manually_create_dictionary_simple_syntax", ["simple_syntax"], indirect=True)
def test_copy_manually_created_dictionary_with_simple_syntax(
    scope: IStorageScope,
    source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary created manually with simple dict-based syntax ignoring pyright issues."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    scope.get_copy_from_dictionary(dest_dir, source_dict)

    _verify_copied_directory(dest_dir)


@pytest.mark.parametrize("manually_create_dictionary_simple_syntax", ["simple_syntax"], indirect=True)
async def test_copy_manually_created_dictionary_with_simple_syntax_async(
    async_scope: IAsyncStorageScope,
    async_source_dict: RecursiveDictionaryOfEntityHandles,
    tmp_path: Path,
):
    """Test copying a dictionary created manually with simple dict-based syntax ignoring pyright issues."""
    dest_dir = tmp_path / "dest_dir"
    assert not dest_dir.exists()
    await async_scope.get_copy_from_dictionary(dest_dir, async_source_dict)

    _verify_copied_directory(dest_dir)
