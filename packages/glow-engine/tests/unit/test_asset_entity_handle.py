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

from collections.abc import Generator
from pathlib import Path
import platform
import re
import uuid

import pytest

from ansys.bdm.api import EntityHandle, EntityNotFoundInBlobStorageError, IReadStorageScope
from ansys.saf.glow._bdm.storage_contexts import METHOD_CONTEXT
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, ROOT, SHORTID
from ansys.saf.glow._bdm.subsystem_scope import (
    AssetSubsidiarySystemStorageScope,
    AssetSubsidiarySystemStorageScopeFactory,
)
from tests.conftest import MOCKS_DIR
from tests.mocks.solution_with_method_assets.bdm_method_assets import SolutionBdmAssets

uuid_regex = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
uuid_pattern = re.compile(uuid_regex)


class TestInMemoryRawIOBase:
    def test_read_in_memory_raw_io(self):
        text = b"hello"
        b = AssetSubsidiarySystemStorageScope.InMemoryRawIO(text)
        assert b.read() == text

    def test_readall_in_memory_raw_io(self):
        text = b"hello"
        b = AssetSubsidiarySystemStorageScope.InMemoryRawIO(text)
        assert b.readall() == text

    def test_write_in_memory_raw_io(self):
        text = b"hello"
        b = AssetSubsidiarySystemStorageScope.InMemoryRawIO()
        b.write(text)
        assert b.readall() == text

    def test_readinto_in_memory_raw_io(self):
        text = b"hello"
        buffer = bytearray(5)
        b = AssetSubsidiarySystemStorageScope.InMemoryRawIO(text)
        b.readinto(buffer)
        assert buffer == text

    def test_io_base_method_in_memory_raw_io(self):
        text = b"hello"
        b = AssetSubsidiarySystemStorageScope.InMemoryRawIO(text)
        assert not b.seekable()


@pytest.fixture
def root_dir(tmp_path: Path):
    return tmp_path / "root_dir"


@pytest.fixture
def asset_storage_scope(tmp_path: Path) -> Generator[IReadStorageScope, None, None]:
    root_dir = tmp_path / "root_dir"
    storage_factory = AssetSubsidiarySystemStorageScopeFactory(solution_type=SolutionBdmAssets)
    with storage_factory.create_storage_scope(
        METHOD_CONTEXT,
        {
            ROOT: str(root_dir),
            PROJECT_ID: "project_id",
            SHORTID: "shortid",
        },
    ) as scope:
        yield scope


decrypted_handle: EntityHandle = EntityHandle(
    is_blob=True,
    original_name="asset_always_decrypted.txt",
    entity_id=uuid.uuid4(),
    opaque_identifier="step_with_assets/asset_always_decrypted.txt",
    size=16,
)
decrypted_dir_handle: EntityHandle = EntityHandle(
    is_blob=False,
    original_name="decrypted_dir",
    entity_id=uuid.uuid4(),
    opaque_identifier="step_with_assets/decrypted_dir",
    size=0,
)
dir_decrypted_handle: EntityHandle = EntityHandle(
    is_blob=True,
    original_name="asset_decrypted.txt",
    entity_id=uuid.uuid4(),
    opaque_identifier="step_with_assets/dir/asset_decrypted.txt",
    size=16,
)
decrypted_dir_decrypted_handle: EntityHandle = EntityHandle(
    is_blob=True,
    original_name="decrypted_asset.txt",
    entity_id=uuid.uuid4(),
    opaque_identifier="step_with_assets/decrypted_dir/decrypted_asset.txt",
    size=19,
)
encrypted_handle: EntityHandle = EntityHandle(
    is_blob=True,
    original_name="asset_encrypted.txt",
    entity_id=uuid.uuid4(),
    opaque_identifier="step_with_assets/asset_encrypted.txt.encrypted",
    size=120,
)
dir_handle: EntityHandle = EntityHandle(
    is_blob=False,
    original_name="dir",
    entity_id=uuid.uuid4(),
    opaque_identifier="step_with_assets/dir",
    size=0,
)
dir_encrypted_handle: EntityHandle = EntityHandle(
    is_blob=True,
    original_name="asset_encrypted.txt",
    entity_id=uuid.uuid4(),
    opaque_identifier="step_with_assets/dir/asset_encrypted.txt.encrypted",
    size=120,
)


@pytest.mark.parametrize(
    ("asset_path", "expected_handle"),
    [
        ("asset_always_decrypted.txt", decrypted_handle),
        ("dir/asset_decrypted.txt", dir_decrypted_handle),
        ("decrypted_dir", decrypted_dir_handle),
        ("decrypted_dir/decrypted_asset.txt", decrypted_dir_decrypted_handle),
    ],
)
def test_get_entity_handle(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    asset_path: str,
    expected_handle: EntityHandle,
):
    handle = asset_storage_scope.get_entity_handle(
        step_name="step_with_assets",
        asset_path=asset_path,
    )
    assert handle.is_blob == expected_handle.is_blob
    assert handle.original_name == expected_handle.original_name
    assert uuid_pattern.match(str(handle.entity_id))
    assert handle.opaque_identifier == expected_handle.opaque_identifier
    assert handle.mime_type == expected_handle.mime_type
    assert handle.encoding == expected_handle.encoding
    if platform.system() == "Windows":
        # size is different on linux and windows
        assert expected_handle.size is not None
        assert handle.size is not None
        assert (handle.size - expected_handle.size) < 2


def test_get_entity_handle_non_existent_file(asset_storage_scope: AssetSubsidiarySystemStorageScope):
    with pytest.raises(EntityNotFoundInBlobStorageError, match="'non_existent' asset file not found."):
        asset_storage_scope.get_entity_handle(
            step_name="step_with_assets",
            asset_path="non_existent",
        )


@pytest.mark.parametrize(
    ("asset_path", "handle", "is_cached"),
    [
        ("asset_always_decrypted.txt", decrypted_handle, False),
        ("dir/asset_decrypted.txt", dir_decrypted_handle, False),
        ("decrypted_dir", decrypted_dir_handle, False),
        ("decrypted_dir/decrypted_asset.txt", decrypted_dir_decrypted_handle, False),
    ],
)
def test_get_cached(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    asset_path: str,
    handle: EntityHandle,
    is_cached: bool,
    root_dir: Path,
):
    handle_path = asset_storage_scope.get_cached(handle)
    assert handle_path.exists()
    if is_cached:
        assert handle_path == root_dir / "project_id" / ".asset_cache" / "shortid" / "step_with_assets" / asset_path
    else:
        expected_path = MOCKS_DIR / "solution_with_method_assets" / "method_assets" / asset_path
        assert handle_path == expected_path


@pytest.mark.parametrize(
    ("expected_content", "handle"),
    [
        ("always decrypted", decrypted_handle),
        ("always decrypted", dir_decrypted_handle),
        ("Cannot create bytes for directory.", decrypted_dir_handle),
        ("decrypted content", decrypted_dir_decrypted_handle),
    ],
)
def test_get_text(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    expected_content: str,
    handle: EntityHandle,
):
    if not handle.is_blob:
        with pytest.raises(ValueError, match=expected_content):
            asset_storage_scope.get_text(handle)
    else:
        assert expected_content == asset_storage_scope.get_text(handle).rstrip()


@pytest.mark.parametrize(
    ("expected_content", "handle"),
    [
        (b"always decrypted", decrypted_handle),
        (b"always decrypted", dir_decrypted_handle),
        ("Cannot create bytes for directory.", decrypted_dir_handle),
        (b"decrypted content", decrypted_dir_decrypted_handle),
    ],
)
def test_get_bytes(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    expected_content: str,
    handle: EntityHandle,
):
    if not handle.is_blob:
        with pytest.raises(ValueError, match=expected_content):
            asset_storage_scope.get_bytes(handle)
    else:
        assert expected_content == asset_storage_scope.get_bytes(handle).rstrip()


@pytest.mark.parametrize(
    ("expected_content", "handle"),
    [
        (b"always decrypted", decrypted_handle),
        (b"always decrypted", dir_decrypted_handle),
        ("Cannot create stream for directory", decrypted_dir_handle),
        (b"decrypted content", decrypted_dir_decrypted_handle),
    ],
)
def test_get_stream(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    expected_content: str,
    handle: EntityHandle,
):
    if not handle.is_blob:
        with pytest.raises(ValueError, match=expected_content):
            asset_storage_scope.get_stream(handle)
    else:
        assert expected_content == asset_storage_scope.get_stream(handle).readall().rstrip()


@pytest.mark.parametrize(
    ("handle", "content"),
    [
        (decrypted_handle, "always decrypted"),
        (dir_decrypted_handle, "always decrypted"),
        (decrypted_dir_decrypted_handle, "decrypted content"),
    ],
)
def test_get_copy_file(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    handle: EntityHandle,
    content: str,
    tmp_path: Path,
):
    destination = tmp_path / "dest"
    assert not destination.exists()
    asset_storage_scope.get_copy(handle, destination)
    assert destination.exists()
    assert destination.is_file()
    assert destination.read_text().rstrip() == content


@pytest.mark.parametrize(
    ("handle", "content"),
    [
        (decrypted_dir_handle, ["decrypted_asset.txt"]),
    ],
)
def test_get_copy_dir(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    handle: EntityHandle,
    content: list[str],
    tmp_path: Path,
):
    destination = tmp_path / "dest"
    assert not destination.exists()
    asset_storage_scope.get_copy(handle, destination)
    assert destination.exists()
    assert destination.is_dir()
    assert sorted([file.name for file in destination.rglob("*")]) == sorted(content)


def test_get_children(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
):
    assert set(asset_storage_scope.get_children(dir_handle)) == {dir_decrypted_handle, dir_encrypted_handle}


def test_get_children_on_file(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
):
    with pytest.raises(NotADirectoryError):
        assert asset_storage_scope.get_children(encrypted_handle)


def test_get_child(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
):
    assert asset_storage_scope.get_child(dir_handle, "asset_encrypted.txt") == dir_encrypted_handle


def test_get_child_not_found(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
):
    with pytest.raises(EntityNotFoundInBlobStorageError, match="'dir/non_existent.txt' asset file not found"):
        asset_storage_scope.get_child(dir_handle, "non_existent.txt")


@pytest.mark.parametrize(
    ("parent_handle", "handle"),
    [
        (dir_handle, dir_decrypted_handle),
        (dir_handle, dir_encrypted_handle),
        (decrypted_dir_handle, decrypted_dir_decrypted_handle),
    ],
)
def test_get_parent(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    parent_handle: EntityHandle,
    handle: EntityHandle,
):
    assert asset_storage_scope.get_parent(handle) == parent_handle


@pytest.mark.parametrize(
    ("handle"),
    [
        (decrypted_handle),
        (encrypted_handle),
        (dir_handle),
        (decrypted_dir_handle),
    ],
)
def test_get_parent_no_parent_returns_none(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
    handle: EntityHandle,
):
    assert asset_storage_scope.get_parent(handle) is None


def test_get_unreferenced_entities(
    asset_storage_scope: AssetSubsidiarySystemStorageScope,
):
    with pytest.raises(RuntimeError, match="Operation not allowed in the context of the asset storage scope."):
        asset_storage_scope.get_unreferenced_entities("test", [])
