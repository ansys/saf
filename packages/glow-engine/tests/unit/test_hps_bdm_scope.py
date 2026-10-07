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
from unittest.mock import MagicMock
import uuid

from ansys.hps.client.jms import (  # pyright: ignore[reportMissingTypeStubs]
    File,
)
import pytest
from pytest_mock.plugin import MockerFixture

from ansys.bdm.api import EntityHandle, IReadStorageScope
from ansys.saf.glow._bdm.hps_scope import (
    HpsOpaqueIdentifier,
    HpsSubsidiarySystemStorageScope,
    HpsSubsidiarySystemStorageScopeFactory,
)
from ansys.saf.glow._bdm.storage_contexts import METHOD_CONTEXT
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, ROOT, SHORTID
from ansys.saf.glow._hps_auth.hps_authenticator import NullHpsAuthenticator

HPS_PROJECT_IDENTIFIER = "bdm_project_id"
FILE_ID = "mock_file_id"
HPS_SERVER_URL = "http://mock_server_url:1234"
CLIENT_ID = "mock_client_id"
LEGACY_DELIMITER = "_?"


@pytest.fixture
def hps_storage_scope(tmp_path: Path) -> Generator[IReadStorageScope, None, None]:
    root_dir = tmp_path / ".hps_cache"
    storage_factory = HpsSubsidiarySystemStorageScopeFactory(NullHpsAuthenticator(), HPS_SERVER_URL)
    with storage_factory.create_storage_scope(
        METHOD_CONTEXT,
        {
            ROOT: str(root_dir),
            PROJECT_ID: "bdm_project_id",
            SHORTID: "bdm_shortid",
        },
    ) as scope:
        yield scope


@pytest.fixture
def mock_get_project_file(mocker: MockerFixture, request: pytest.FixtureRequest) -> MagicMock:
    mock_get_project_file = mocker.patch(
        "ansys.saf.glow._hps_parametric_studies.project_wrapper.HpsProjectWrapper.get_project_file",
    )
    file = None
    if request.param:
        file = File(
            id=FILE_ID,
            evaluation_path="eval_path",
            size=123,
        )
    else:
        file = File(
            id=FILE_ID,
            name="mock_file_name",
            size=123,
        )
    mock_get_project_file.return_value = file
    return mock_get_project_file


@pytest.fixture
def expected_opaque_identifier() -> str:
    return HpsOpaqueIdentifier(
        version="2.0",
        hps_project_identifier=HPS_PROJECT_IDENTIFIER,
        file_id=FILE_ID,
        hps_server_url=HPS_SERVER_URL,
        client_id=CLIENT_ID,
    ).serialize()


@pytest.fixture
def legacy_opaque_identifier_v1() -> str:
    # Legacy identifiers had two additional configurable fields separated by the old delimiter.
    return (
        f"{HPS_PROJECT_IDENTIFIER}{LEGACY_DELIMITER}"
        f"{FILE_ID}{LEGACY_DELIMITER}"
        f"{HPS_SERVER_URL}{LEGACY_DELIMITER}"
        f"{CLIENT_ID}{LEGACY_DELIMITER}"
        f"my_kc_realm{LEGACY_DELIMITER}"
        "my_kc_relative_path"
    )


@pytest.fixture
def legacy_opaque_identifier_v2() -> str:
    # Legacy identifiers had two additional hardcoded fields separated by the old delimiter.
    return (
        f"{HPS_PROJECT_IDENTIFIER}{LEGACY_DELIMITER}"
        f"{FILE_ID}{LEGACY_DELIMITER}"
        f"{HPS_SERVER_URL}{LEGACY_DELIMITER}"
        f"{CLIENT_ID}{LEGACY_DELIMITER}"
        f"deprecated_kc_realm{LEGACY_DELIMITER}"
        "deprecated_kc_relative_path"
    )


def copy_file(file_id: str, destination_dir: Path) -> Path:
    file = destination_dir / "file.txt"
    file.write_text("hello world!")
    return file


@pytest.fixture
def mock_copy_file(mocker: MockerFixture) -> MagicMock:
    mock_copy_file = mocker.patch("ansys.saf.glow._hps_parametric_studies.project_wrapper.HpsProjectWrapper.copy_file")
    mock_copy_file.side_effect = copy_file
    return mock_copy_file


@pytest.fixture
def entity_handle(
    expected_opaque_identifier: str,
    legacy_opaque_identifier_v1: str,
    legacy_opaque_identifier_v2: str,
    request: pytest.FixtureRequest,
) -> EntityHandle:
    opaque_identifier_version = getattr(request, "param", "2.0")
    if opaque_identifier_version == "legacy_v1":
        opaque_identifier = legacy_opaque_identifier_v1
    elif opaque_identifier_version == "legacy_v2":
        opaque_identifier = legacy_opaque_identifier_v2
    else:
        opaque_identifier = expected_opaque_identifier
    return EntityHandle(
        is_blob=True,
        original_name="mock_file_name",
        entity_id=uuid.uuid4(),
        opaque_identifier=opaque_identifier,
        mime_type="application/json",
        encoding=None,
        size=123,
    )


def test_cache_dir_created_and_removed(
    tmp_path: Path,
    mock_copy_file: MagicMock,
    entity_handle: EntityHandle,
):
    root_dir = tmp_path / ".hps_cache"
    storage_factory = HpsSubsidiarySystemStorageScopeFactory(NullHpsAuthenticator(), HPS_SERVER_URL)
    expected_cache_dir = root_dir / "bdm_project_id" / ".hps_cache" / "bdm_shortid"

    # WHEN: the storage scope is accessed
    with storage_factory.create_storage_scope(
        METHOD_CONTEXT,
        {
            ROOT: str(root_dir),
            PROJECT_ID: "bdm_project_id",
            SHORTID: "bdm_shortid",
        },
    ) as storage_scope:
        # THEN: the cache directory is not created until _copy_file is called
        assert not expected_cache_dir.is_dir()
        storage_scope.get_cached(entity_handle)
        mock_copy_file.assert_called_once()
        assert expected_cache_dir.is_dir()
        cache_file = expected_cache_dir / "cache_file.txt"
        cache_file.touch()

    assert not expected_cache_dir.exists()
    assert not cache_file.exists()


@pytest.mark.parametrize("mock_get_project_file", [True, False], indirect=True)
def test_get_entity_handle(
    hps_storage_scope: HpsSubsidiarySystemStorageScope,
    mock_get_project_file: MagicMock,
    expected_opaque_identifier: str,
):
    handle = hps_storage_scope.get_entity_handle(
        hps_project_identifier=HPS_PROJECT_IDENTIFIER,
        file_id=FILE_ID,
        hps_server_url=HPS_SERVER_URL,
        client_id=CLIENT_ID,
    )
    assert handle.is_blob
    if mock_get_project_file.return_value.evaluation_path:
        assert handle.original_name == "eval_path"
    else:
        assert handle.original_name == "mock_file_name"
    assert handle.opaque_identifier == expected_opaque_identifier
    deserialized_opaque_identifier = HpsOpaqueIdentifier.deserialize(handle.opaque_identifier)
    assert deserialized_opaque_identifier.version == "2.0"
    assert deserialized_opaque_identifier.hps_project_identifier == HPS_PROJECT_IDENTIFIER
    assert deserialized_opaque_identifier.file_id == FILE_ID
    assert deserialized_opaque_identifier.hps_server_url == HPS_SERVER_URL
    assert deserialized_opaque_identifier.client_id == CLIENT_ID
    assert handle.size == 123
    mock_get_project_file.assert_called_once_with(FILE_ID)


@pytest.mark.parametrize("entity_handle", ["2.0", "legacy_v1", "legacy_v2"], indirect=True)
def test_get_cached(
    hps_storage_scope: HpsSubsidiarySystemStorageScope,
    mock_copy_file: MagicMock,
    entity_handle: EntityHandle,
):
    handle_path = hps_storage_scope.get_cached(entity_handle)
    expected_handle_path = (
        Path(hps_storage_scope._cache_dir)  # pyright: ignore[reportPrivateUsage]
        / str(hash(HPS_PROJECT_IDENTIFIER))
        / FILE_ID
        / "file.txt"
    )
    assert handle_path.exists()
    assert handle_path == expected_handle_path
    mock_copy_file.assert_called_once_with(FILE_ID, expected_handle_path.parent)


@pytest.mark.usefixtures("mock_copy_file")
def test_get_copy(
    hps_storage_scope: HpsSubsidiarySystemStorageScope,
    entity_handle: EntityHandle,
    tmp_path: Path,
):
    dst = tmp_path / "destination_dir" / "another.txt"
    existing_file = tmp_path / "destination_dir" / "file.txt"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_text("existing")

    hps_storage_scope.get_copy(entity_handle, dst)
    assert dst.read_text() == "hello world!"
    assert existing_file.read_text() == "existing"


def test_get_children(
    hps_storage_scope: HpsSubsidiarySystemStorageScope,
    entity_handle: EntityHandle,
):
    assert hps_storage_scope.get_children(entity_handle) == []


def test_get_child(
    hps_storage_scope: HpsSubsidiarySystemStorageScope,
    entity_handle: EntityHandle,
):
    with pytest.raises(ValueError, match="child_name not found."):
        hps_storage_scope.get_child(entity_handle, "child_name")


def test_get_parent(
    hps_storage_scope: HpsSubsidiarySystemStorageScope,
    entity_handle: EntityHandle,
):
    assert not hps_storage_scope.get_parent(entity_handle)


def test_get_unreferenced_entities(
    hps_storage_scope: HpsSubsidiarySystemStorageScope,
    entity_handle: EntityHandle,
):
    with pytest.raises(RuntimeError, match="Operation not allowed in the context of the HPS storage scope."):
        hps_storage_scope.get_unreferenced_entities("context", [entity_handle])
