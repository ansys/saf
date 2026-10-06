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
import random
import uuid

from fastapi import status
import pytest

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow._bdm.datarepo import DataRepositoryType
from ansys.saf.glow._config.const import GLOW_DATA_REPOSITORY_TYPE
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._server.exceptions import INTERNAL_ERROR_MESSAGE
import tests.mocks.solutions.data_repository as data_repository_solution
from tests.unit.routes.conftest import ProjectFixture

solution = data_repository_solution

pytestmark = pytest.mark.parametrize(
    "mock_module_settings",
    [{"glow_data_repository_type": DataRepositoryType.FileSystem}],
    ids=["FileSystem"],
    indirect=True,
)


@pytest.fixture(autouse=True)
def data_repo_type(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_DATA_REPOSITORY_TYPE, DataRepositoryType.FileSystem.value)


@pytest.fixture
def minerva_path(project_fixture: ProjectFixture) -> Path:
    return project_fixture.project_files_dir / "minerva"


@pytest.fixture
def data_repository_path(project_fixture: ProjectFixture) -> Path:
    return project_fixture.project_files_path / "filesystem"


@pytest.fixture
def temp_upload_root() -> str:
    return f"/Data/SAF/glow_tests_{str(uuid.uuid4())}"


@pytest.fixture
def step_url(project_fixture: ProjectFixture) -> str:
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/data-repository-step"
    return step_url


@pytest.fixture
def data_project_directory_name(project_fixture: ProjectFixture) -> str:
    data_project_dir_name = f"{project_fixture.project_display_name} ({project_fixture.project_id})"
    return data_project_dir_name


def test_upload_entity_handle_to_data_repo_using_default_target_path(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
    data_project_directory_name: str,
):
    data_repo_file = data_repository_path / "Data" / data_project_directory_name / "data.txt" / "001_default"
    assert not data_repo_file.exists()
    response = project_fixture.client.post(f"{step_url}:upload-blob-to-data-repo")
    assert response.status_code == status.HTTP_200_OK
    assert data_repo_file.exists()
    assert data_repo_file.read_text() == "hello world!"


def test_upload_entity_handle_to_data_repo_using_relative_target_path(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
    data_project_directory_name: str,
):
    data_repo_file = data_repository_path / "Data" / data_project_directory_name / "data.txt" / "001_default"
    assert not data_repo_file.exists()
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"target_path": "data.txt"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert data_repo_file.exists()
    assert data_repo_file.read_text() == "hello world!"


def test_upload_entity_handle_to_data_repo_using_absolute_target_path(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    file_name = f"data_{random.randint(0, 1000)}.txt"
    data_repo_file = data_repository_path / "Data" / file_name / "001_default"
    assert not data_repo_file.exists()
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"target_path": f"/Data/{file_name}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert data_repo_file.exists()
    assert data_repo_file.read_text() == "hello world!"


def test_upload_entity_handle_multiple_times_to_data_repo_creates_several_versions(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
    data_project_directory_name: str,
):
    response = project_fixture.client.post(f"{step_url}:upload-blob-multiple-times-to-data-repo")
    assert response.status_code == status.HTTP_200_OK
    for i in range(1, 4):
        data_repo_file = data_repository_path / "Data" / data_project_directory_name / "data.txt" / f"001.00{i}"
        assert data_repo_file.exists()
        assert data_repo_file.read_text() == f"hello world! v{i}"
    data_repo_file = data_repository_path / "Data" / data_project_directory_name / "data.txt" / "001_default"
    assert data_repo_file.exists()
    assert data_repo_file.read_text() == "hello world! v3"


def test_upload_entity_handle_directory_to_data_repo_creates_versioned_files(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
    data_project_directory_name: str,
):
    v1 = "001_default"
    data_repo_file_1 = data_repository_path / "Data" / data_project_directory_name / "folder" / "my_file1.txt" / v1
    data_repo_file_2 = data_repository_path / "Data" / data_project_directory_name / "folder" / "my_file2.txt" / v1
    data_repo_file_3 = (
        data_repository_path / "Data" / data_project_directory_name / "folder" / "subdir" / "my_file3.txt" / v1
    )
    assert not data_repo_file_1.exists()
    assert not data_repo_file_2.exists()
    assert not data_repo_file_3.exists()
    response = project_fixture.client.post(f"{step_url}:upload-directory-to-data-repo")
    assert response.status_code == status.HTTP_200_OK
    response.raise_for_status()
    assert data_repo_file_1.read_text() == "file1"
    assert data_repo_file_2.read_text() == "file2"
    assert data_repo_file_3.read_text() == "file3"


def test_upload_entity_handle_directory_to_data_repo_using_relative_target_path(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
    data_project_directory_name: str,
):
    v1 = "001_default"
    data_repo_file_1 = data_repository_path / "Data" / data_project_directory_name / "directory" / "my_file1.txt" / v1
    data_repo_file_2 = data_repository_path / "Data" / data_project_directory_name / "directory" / "my_file2.txt" / v1
    data_repo_file_3 = (
        data_repository_path / "Data" / data_project_directory_name / "directory" / "subdir" / "my_file3.txt" / v1
    )
    assert not data_repo_file_1.exists()
    assert not data_repo_file_2.exists()
    assert not data_repo_file_3.exists()
    response = project_fixture.client.post(
        f"{step_url}:upload-directory-to-data-repo",
        json={"target_path": "directory"},
    )
    assert response.status_code == status.HTTP_200_OK
    response.raise_for_status()
    assert data_repo_file_1.read_text() == "file1"
    assert data_repo_file_2.read_text() == "file2"
    assert data_repo_file_3.read_text() == "file3"


def test_upload_entity_handle_directory_to_data_repo_asbolute_path_creates_versioned_files(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    v1 = "001_default"
    dir_name = f"my_dir_{random.randint(0, 1000)}"
    data_repo_file_1 = data_repository_path / "Data" / dir_name / "my_file1.txt" / v1
    data_repo_file_2 = data_repository_path / "Data" / dir_name / "my_file2.txt" / v1
    data_repo_file_3 = data_repository_path / "Data" / dir_name / "subdir" / "my_file3.txt" / v1
    assert not data_repo_file_1.exists()
    assert not data_repo_file_2.exists()
    assert not data_repo_file_3.exists()
    response = project_fixture.client.post(
        f"{step_url}:upload-directory-to-data-repo",
        json={"target_path": f"/Data/{dir_name}"},
    )
    assert response.status_code == status.HTTP_200_OK
    response.raise_for_status()
    assert data_repo_file_1.read_text() == "file1"
    assert data_repo_file_2.read_text() == "file2"
    assert data_repo_file_3.read_text() == "file3"


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_upload_entity_handle_existing_directory_at_target_location_raise_error(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    settings: Settings,
    step_url: str,
    data_project_directory_name: str,
):
    data_repo_existing_dir = data_repository_path / "Data" / data_project_directory_name / "data.txt" / "v1"
    data_repo_existing_dir.mkdir(parents=True, exist_ok=True)
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"target_path": "data.txt"},
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    if settings.glow_debug:
        message = f"Directory already exists at /Data/{data_project_directory_name}/data.txt"
    else:
        message = "The solution encountered an internal error and was unable to complete the request"
    assert message in response.json()["detail"]


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_upload_directory_but_blob_exists_at_target_location_raise_error(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    settings: Settings,
    step_url: str,
    data_project_directory_name: str,
):
    data_repo_existing_blob = data_repository_path / "Data" / data_project_directory_name / "folder"
    data_repo_existing_blob.parent.mkdir(parents=True, exist_ok=True)
    data_repo_existing_blob.write_text("hello world!")
    response = project_fixture.client.post(f"{step_url}:upload-small-directory-to-data-repo")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    if settings.glow_debug:
        message = f"File exists at /Data/{data_project_directory_name}/folder"
    else:
        message = "The solution encountered an internal error and was unable to complete the request"
    assert message in response.json()["detail"]


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_upload_no_entity_raise_error(
    project_fixture: ProjectFixture,
    settings: Settings,
    step_url: str,
):
    response = project_fixture.client.post(f"{step_url}:upload-no-entity-to-data-repo")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    if settings.glow_debug:
        message = "NO_ENTITY handle cannot be uploaded."
    else:
        message = "The solution encountered an internal error and was unable to complete the request"
    assert message in response.json()["detail"]


def test_fetch_blob_content_from_data_repo(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
    data_project_directory_name: str,
):
    data_txt_dir = data_repository_path / "Data" / data_project_directory_name / "data.txt"
    data_txt_dir.mkdir(exist_ok=True, parents=True)
    (data_txt_dir / "001_default").write_text("hello world!")
    (data_txt_dir / "001.001_default").write_text("hello world!")
    (data_txt_dir / "001_default.metadata").touch()
    (data_txt_dir / "001.001_default.metadata").touch()
    response = project_fixture.client.post(f"{step_url}:fetch-blob-content-from-data-repo")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "hello world!"


def test_fetch_blob_content_from_data_repo_using_relative_path(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
    data_project_directory_name: str,
):
    data_txt_dir = data_repository_path / "Data" / data_project_directory_name / "folder" / "data.txt"
    data_txt_dir.mkdir(exist_ok=True, parents=True)
    (data_txt_dir / "001_default").write_text("hello world!")
    (data_txt_dir / "001.001_default").write_text("hello world!")
    (data_txt_dir / "001_default.metadata").touch()
    (data_txt_dir / "001.001_default.metadata").touch()
    response = project_fixture.client.post(
        f"{step_url}:fetch-blob-content-from-data-repo",
        json={"minerva_path": "folder/data.txt"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "hello world!"


def test_fetch_blob_content_from_data_repo_using_absolute_path(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    file_name = f"data_{random.randint(0, 1000)}.txt"
    data_txt_dir = data_repository_path / "Data" / file_name
    data_txt_dir.mkdir(exist_ok=True, parents=True)
    (data_txt_dir / "001_default").write_text("hello world!")
    (data_txt_dir / "001.001_default").write_text("hello world!")
    (data_txt_dir / "001_default.metadata").touch()
    (data_txt_dir / "001.001_default.metadata").touch()
    response = project_fixture.client.post(
        f"{step_url}:fetch-blob-content-from-data-repo",
        json={"minerva_path": f"/Data/{file_name}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "hello world!"


@pytest.fixture
def create_3_versions(data_repository_path: Path, project_fixture: ProjectFixture, data_project_directory_name: str):
    versioned_dir = data_repository_path / "Data" / data_project_directory_name / "data.txt"
    versioned_dir.mkdir(exist_ok=True, parents=True)
    v1 = versioned_dir / "001.001"
    v1.write_text("v1")
    v2 = versioned_dir / "001.002"
    v2.write_text("v2")
    v3 = versioned_dir / "001.003"
    v3.write_text("v3")
    m3 = versioned_dir / "001.003.metadata"
    m3.touch()
    v3_ = versioned_dir / "001_default"
    v3_.write_text("v3")
    m3_ = versioned_dir / "001_default.metadata"
    m3_.touch()


@pytest.mark.usefixtures("create_3_versions")
def test_fetch_blob_content_without_version_from_data_repo_use_latest_version(
    project_fixture: ProjectFixture,
    step_url: str,
):
    response = project_fixture.client.post(f"{step_url}:fetch-blob-content-from-data-repo")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "v3"


@pytest.mark.usefixtures("create_3_versions")
@pytest.mark.parametrize("version", ["001.001", "001.002"])
def test_fetch_blob_content_non_default_versions_from_data_repo(
    project_fixture: ProjectFixture,
    step_url: str,
    version: str,
):
    response = project_fixture.client.post(f"{step_url}:fetch-blob-content-from-data-repo", json={"version": version})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == f"v{version[-1]}"


@pytest.fixture
def upload_directory_to_data_repo(project_fixture: ProjectFixture, step_url: str):
    response = project_fixture.client.post(f"{step_url}:upload-directory-to-data-repo")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize("abs_path", [False, True])
@pytest.mark.parametrize("ending_slash", [False, True])
@pytest.mark.usefixtures("upload_directory_to_data_repo")
def test_fetch_children_from_data_repo_directory(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
    data_project_directory_name: str,
    abs_path: bool,
    ending_slash: bool,
):
    remote_path = f"/Data/{data_project_directory_name}/folder" if abs_path else "folder"
    if ending_slash:
        remote_path += "/"

    response = project_fixture.client.post(
        f"{step_url}:fetch-children-from-data-repo-directory",
        json={"minerva_path": remote_path},
    )
    assert response.status_code == status.HTTP_200_OK
    assert sorted([child["original_name"] for child in response.json()]) == sorted(
        ["empty_subdir", "my_file1.txt", "my_file2.txt", "nested_empty_subdir", "nested_subdir_same_name", "subdir"],
    )


@pytest.mark.usefixtures("upload_directory_to_data_repo")
def test_fetch_child_from_data_repo_directory(project_fixture: ProjectFixture, step_url: str):
    response = project_fixture.client.post(f"{step_url}:fetch-child-from-data-repo-handle")
    assert response.json()["original_name"] == "my_file1.txt"


@pytest.mark.usefixtures("upload_directory_to_data_repo")
def test_fetch_parent_from_data_repo_directory(project_fixture: ProjectFixture, step_url: str):
    response = project_fixture.client.post(f"{step_url}:fetch-parent-from-data-repo-directory")
    assert response.json()["original_name"] == "folder"


@pytest.fixture
def upload_blob_to_data_repo(project_fixture: ProjectFixture, step_url: str):
    response = project_fixture.client.post(f"{step_url}:upload-blob-to-data-repo")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.usefixtures("upload_blob_to_data_repo")
def test_fetch_cached_from_data_repo(
    project_fixture: ProjectFixture,
    step_url: str,
    minerva_path: Path,
    data_project_directory_name: str,
):
    response = project_fixture.client.post(f"{step_url}:fetch-cached-from-data-repo-handle")
    assert response.status_code == status.HTTP_200_OK
    assert Path(response.json()) == minerva_path / "Data" / data_project_directory_name / "data.txt"


@pytest.mark.usefixtures("upload_blob_to_data_repo")
def test_fetch_text_from_data_repo(project_fixture: ProjectFixture, step_url: str):
    response = project_fixture.client.post(f"{step_url}:fetch-text-from-data-repo-handle")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "hello world!"


@pytest.mark.usefixtures("upload_blob_to_data_repo")
def test_fetch_bytes_from_data_repo(project_fixture: ProjectFixture, step_url: str):
    response = project_fixture.client.post(f"{step_url}:fetch-bytes-from-data-repo-handle")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "hello world!"


@pytest.mark.usefixtures("upload_blob_to_data_repo")
def test_fetch_stream_from_data_repo(project_fixture: ProjectFixture, step_url: str):
    response = project_fixture.client.post(f"{step_url}:fetch-stream-from-data-repo-handle")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "hello world!"


def test_fetch_nonexisting_item_from_data_repo_returns_no_entity(
    project_fixture: ProjectFixture,
    step_url: str,
):
    response = project_fixture.client.post(f"{step_url}:fetch-nonexisting-item-from-data-repo")
    assert response.status_code == status.HTTP_200_OK
    assert EntityHandle.model_validate(response.json()) == NO_ENTITY


def test_upload_entity_handle_return_same_handle_as_get_entity_handle(
    project_fixture: ProjectFixture,
    step_url: str,
):
    upload_handle_response = project_fixture.client.post(f"{step_url}:upload-blob-to-data-repo").json()
    get_entity_response = project_fixture.client.post(f"{step_url}:return-get-entity-handle").json()
    # only entity_id field is different since it is generated each time
    assert {k for k, _ in upload_handle_response.items() ^ get_entity_response.items()} == {
        "entity_id",
        "opaque_identifier",
    }


def test_upload_handle_is_not_method_handle(
    project_fixture: ProjectFixture,
    step_url: str,
):
    response = project_fixture.client.post(f"{step_url}:upload-blob-to-data-repo")
    assert response.status_code == status.HTTP_200_OK
    step = project_fixture.client.get(f"{step_url}").json()
    assert step["data_repo_handle"] != step["method_handle"]


@pytest.mark.usefixtures("upload_directory_to_data_repo")
def test_query_files(
    project_fixture: ProjectFixture,
    step_url: str,
):
    query_str = "folder_files_query_placeholder"
    response = project_fixture.client.post(
        f"{step_url}:get-entities-based-on-query",
        json={"value": query_str},
    )
    assert response.status_code == status.HTTP_200_OK
    entities = response.json()
    for file_path in [
        "folder/my_file1.txt",
        "folder/my_file2.txt",
        "folder/subdir/my_file3.txt",
        "folder/nested_subdir_same_name/folder/my_file4.txt",
        "folder/nested_subdir_same_name/folder/my_file5.txt",
    ]:
        response = project_fixture.client.post(
            f"{step_url}:get-data-repository-entity-handle",
            json={"minerva_path": file_path},
        )
        assert response.status_code == status.HTTP_200_OK
        expected_entity = response.json()
        assert expected_entity["opaque_identifier"] in [entity["opaque_identifier"] for entity in entities]


@pytest.mark.usefixtures("upload_directory_to_data_repo")
def test_query_dir(
    project_fixture: ProjectFixture,
    step_url: str,
):
    query_str = "folder_dir_query_placeholder"
    response = project_fixture.client.post(
        f"{step_url}:get-entities-based-on-query",
        json={"value": query_str},
    )
    assert response.status_code == status.HTTP_200_OK
    entities = response.json()
    file_path = "folder/nested_empty_subdir/empty_subdir_2"
    response = project_fixture.client.post(
        f"{step_url}:get-data-repository-entity-handle",
        json={"minerva_path": file_path},
    )
    assert response.status_code == status.HTTP_200_OK
    expected_entity = response.json()
    assert expected_entity["opaque_identifier"] in [entity["opaque_identifier"] for entity in entities]


def test_invalid_query(
    project_fixture: ProjectFixture,
    step_url: str,
):
    query_str = "gibberish"
    response = project_fixture.client.post(
        f"{step_url}:get-entities-based-on-query",
        json={"value": query_str},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


@pytest.mark.usefixtures("upload_directory_to_data_repo")
def test_query_without_filesystem_query_map(
    project_fixture: ProjectFixture,
    step_url: str,
):
    query_str = "files_query_placeholder"
    response = project_fixture.client.post(
        f"{step_url}:get-entities-based-on-query-without-query-map",
        json={"value": query_str},
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == INTERNAL_ERROR_MESSAGE


@pytest.mark.usefixtures("upload_directory_to_data_repo")
def test_query_file_not_found(
    project_fixture: ProjectFixture,
    step_url: str,
):
    query_str = "file_not_found_query_placeholder"
    response = project_fixture.client.post(
        f"{step_url}:get-entities-based-on-query",
        json={"value": query_str},
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == INTERNAL_ERROR_MESSAGE


def check_entity_version(opaque_identifier: str, expected_version: str):
    version = opaque_identifier.split("?version=")[-1]
    assert version == expected_version


def check_blob_content(project_fixture: ProjectFixture, step_url: str, target_path: str, content: str, version: str):
    response = project_fixture.client.post(
        f"{step_url}:fetch-blob-content-from-data-repo",
        json={"minerva_path": target_path, "version": version},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == content


def validate_filesystem_metadata(
    data_repository_path: Path,
    opaque_identifier: str,
    version: str,
    property_name: str | None = None,
) -> bool:
    remote_path = opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
    version_str = f"{version}_default" if version == "001" else version
    metadata_path = data_repository_path / remote_path / f"{version_str}.metadata"
    if not metadata_path.is_file():
        return False
    if property_name:
        return property_name in metadata_path.read_text()
    return True


def test_upload_file_with_associated_metadata_and_relative_path(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    file_name = "my_data.txt"
    content = str(uuid.uuid4())
    metadata = "test_metadata"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content, "target_path": file_name, "metadata": metadata},
    )
    assert response.status_code == status.HTTP_200_OK
    uploaded_entity = response.json()
    check_entity_version(uploaded_entity["opaque_identifier"], "001.001")
    check_blob_content(project_fixture, step_url, file_name, content, "001")
    check_blob_content(project_fixture, step_url, file_name, content, "001.001")
    assert validate_filesystem_metadata(data_repository_path, uploaded_entity["opaque_identifier"], "001", metadata)
    assert validate_filesystem_metadata(data_repository_path, uploaded_entity["opaque_identifier"], "001.001", metadata)


def test_upload_file_with_associated_metadata_and_absolute_path(
    project_fixture: ProjectFixture,
    temp_upload_root: str,
    data_repository_path: Path,
    step_url: str,
):
    target_path = f"{temp_upload_root}/my_data.txt"
    content = str(uuid.uuid4())
    metadata = "test_metadata"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content, "target_path": target_path, "metadata": metadata},
    )
    assert response.status_code == status.HTTP_200_OK
    uploaded_entity = response.json()
    check_entity_version(uploaded_entity["opaque_identifier"], "001.001")
    check_blob_content(project_fixture, step_url, target_path, content, "001")
    check_blob_content(project_fixture, step_url, target_path, content, "001.001")
    assert validate_filesystem_metadata(data_repository_path, uploaded_entity["opaque_identifier"], "001", metadata)
    assert validate_filesystem_metadata(data_repository_path, uploaded_entity["opaque_identifier"], "001.001", metadata)


def test_upload_different_file_after_upload_with_metadata(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    file_name = "my_data.txt"
    content = str(uuid.uuid4())
    metadata = "test_metadata"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content, "target_path": file_name, "metadata": metadata},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.001")

    other_file_name = "my_data_2.txt"
    other_content = str(uuid.uuid4())
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": other_content, "target_path": other_file_name},
    )
    assert response.status_code == status.HTTP_200_OK
    other_entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.001")

    check_blob_content(project_fixture, step_url, file_name, content, "001")
    check_blob_content(project_fixture, step_url, file_name, content, "001.001")
    check_blob_content(project_fixture, step_url, other_file_name, other_content, "001")
    check_blob_content(project_fixture, step_url, other_file_name, other_content, "001.001")
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001", metadata)
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.001", metadata)
    assert not validate_filesystem_metadata(data_repository_path, other_entity["opaque_identifier"], "001")
    assert not validate_filesystem_metadata(data_repository_path, other_entity["opaque_identifier"], "001.001")


def test_reupload_same_file_with_new_content_and_without_metadata(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    file_name = "my_data.txt"
    content = str(uuid.uuid4())
    metadata = "test_metadata"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content, "target_path": file_name, "metadata": metadata},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.001")

    content_v2 = str(uuid.uuid4())
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content_v2, "target_path": file_name},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.002")

    check_blob_content(project_fixture, step_url, file_name, content_v2, "001")
    check_blob_content(project_fixture, step_url, file_name, content, "001.001")
    check_blob_content(project_fixture, step_url, file_name, content_v2, "001.002")
    assert not validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001")
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.001", metadata)
    assert not validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.002")


def test_reupload_same_file_with_new_content_and_same_metadata(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    file_name = "my_data.txt"
    content = str(uuid.uuid4())
    metadata = "test_metadata"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content, "target_path": file_name, "metadata": metadata},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.001")

    content_v2 = str(uuid.uuid4())
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content_v2, "target_path": file_name, "metadata": metadata},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.002")

    check_blob_content(project_fixture, step_url, file_name, content_v2, "001")
    check_blob_content(project_fixture, step_url, file_name, content, "001.001")
    check_blob_content(project_fixture, step_url, file_name, content_v2, "001.002")
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001", metadata)
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.001", metadata)
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.002", metadata)


def test_reupload_same_file_with_new_content_and_new_metadata(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    file_name = "my_data.txt"
    content = str(uuid.uuid4())
    metadata = "test_metadata"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content, "target_path": file_name, "metadata": metadata},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.001")

    content_v2 = str(uuid.uuid4())
    metadata_v2 = "metadata_test"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content_v2, "target_path": file_name, "metadata": metadata_v2},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.002")

    check_blob_content(project_fixture, step_url, file_name, content_v2, "001")
    check_blob_content(project_fixture, step_url, file_name, content, "001.001")
    check_blob_content(project_fixture, step_url, file_name, content_v2, "001.002")
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001", metadata_v2)
    assert not validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001", metadata)
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.001", metadata)
    assert not validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.001", metadata_v2)
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.002", metadata_v2)
    assert not validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.002", metadata)


def test_reupload_same_file_with_same_content_and_new_metadata(
    project_fixture: ProjectFixture,
    data_repository_path: Path,
    step_url: str,
):
    # When uploading the same file with new metadata, Minerva links the new metadata to version 001 and
    # generates a new identical version 001.001 with the same new metadata. The previous metadata is not
    # linked to any version. A version 001.002 is not generated.

    file_name = "my_data.txt"
    content = str(uuid.uuid4())
    metadata = "test_metadata"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content, "target_path": file_name, "metadata": metadata},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.001")

    metadata_v2 = "metadata_test"
    response = project_fixture.client.post(
        f"{step_url}:upload-blob-to-data-repo",
        json={"content": content, "target_path": file_name, "metadata": metadata_v2},
    )
    assert response.status_code == status.HTTP_200_OK
    entity = response.json()
    check_entity_version(entity["opaque_identifier"], "001.001")

    check_blob_content(project_fixture, step_url, file_name, content, "001")
    check_blob_content(project_fixture, step_url, file_name, content, "001.001")
    response = project_fixture.client.post(
        f"{step_url}:get-data-repository-entity-handle",
        json={"minerva_path": file_name, "version": "001.002"},
    )
    assert response.status_code == status.HTTP_200_OK
    no_entity = response.json()
    assert EntityHandle.model_validate(no_entity) == NO_ENTITY

    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001", metadata_v2)
    assert not validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001", metadata)
    assert validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.001", metadata_v2)
    assert not validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.001", metadata)
    assert not validate_filesystem_metadata(data_repository_path, entity["opaque_identifier"], "001.002")


def test_access_entity_handle_from_data_repo_using_blobs_endpoint(
    project_fixture: ProjectFixture,
    step_url: str,
):
    project_fixture.client.post(f"{step_url}:upload-blob-to-data-repo")
    response = project_fixture.client.get(f"{step_url}/blobs/data-repo-handle")
    assert response.text == "hello world!"
