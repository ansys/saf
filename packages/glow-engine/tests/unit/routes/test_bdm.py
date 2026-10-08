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

from fastapi import status
import pytest

from ansys.bdm.api import NO_ENTITY
from ansys.bdm.api.entity_handle import EntityHandle
from ansys.saf.glow._config.const import DatabaseType
from tests.conftest import SOLUTIONS_MOCKS_DIR
import tests.mocks.solutions.bdm_solution as bdm_solution
from tests.unit.routes.conftest import ProjectFixture

pytestmark = pytest.mark.parametrize(
    "mock_module_settings",
    [{"glow_database_type": DatabaseType.Sqlite}, {"glow_database_type": DatabaseType.PostgreSql}],
    ids=["sqlite", "postgres"],
    indirect=True,
)
solution = bdm_solution

BDM_NO_ENTITY_ERROR_MSG = "entity does not exist"


class TestBlobRoutes:
    def test_get_blob_response_openapi_spec(self, project_fixture: ProjectFixture):
        # Verify that the OpenAPI spec declares the GET blob endpoint as returning application/octet-stream,
        # not application/json, so that API clients and code generators treat the response as a binary download.
        openapi_response = project_fixture.client.get("openapi.json")
        openapi_response.raise_for_status()
        openapi_spec = openapi_response.json()
        blob_get_path = "/projects/{project_id}/steps/bdm-step/blobs/{datapath}"
        spec_get_operation = openapi_spec["paths"][blob_get_path]["get"]
        spec_200_content = spec_get_operation["responses"]["200"]["content"]
        assert spec_200_content == {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}

    def test_can_upload_and_download_file(self, tmp_path: Path, project_fixture: ProjectFixture):
        # GIVEN - a file with known content and name
        content = "hello world"
        file_name = "x.txt"
        source_file = tmp_path / file_name
        source_file.write_text(content)

        # AND GIVEN - a project with an entity handle and the url pointing to the content of the entity handle
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step/blobs/my-entity"

        # WHEN - uploading the file to the URL
        with source_file.open("rb") as file_stream:
            response = project_fixture.client.put(url, files={"upload_file": (file_name, file_stream)})
        response.raise_for_status()

        # THEN - the returned result contains a serialized EntityHandle containing a reference to a file with
        # the correct name
        handle_json = response.json()
        handle = EntityHandle.model_validate(handle_json)
        assert handle.original_name == file_name
        assert handle.is_blob

        # AND THEN - a GET on the same URL returns the content of the original file
        response = project_fixture.client.get(url)
        response.raise_for_status()
        assert response.text == content

    def test_uploading_a_file_does_not_wipeout_other_field_values_on_step(
        self,
        tmp_path: Path,
        project_fixture: ProjectFixture,
    ):
        # GIVEN - a file with known content and name
        content = "hello world"
        file_name = "x.txt"
        source_file = tmp_path / file_name
        source_file.write_text(content)

        # AND GIVEN - a project with an entity handle and the url pointing to the content of the entity handle
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step/blobs/my-entity"

        # AND GIVEN - a field with a non-default value on the same step as the entity handle
        patch_url = f"{project_name}/steps/bdm-step"
        payload = {"other": 23}
        response = project_fixture.client.patch(patch_url, json=payload)
        response.raise_for_status()

        # WHEN - uploading the file to the URL
        with source_file.open("rb") as file_stream:
            response = project_fixture.client.put(url, files={"upload_file": (file_name, file_stream)})
        response.raise_for_status()

        # THEN - the modified field retains it's value
        response = project_fixture.client.get(patch_url)
        assert response.status_code == 200
        assert response.json()["other"] == 23

    def test_trying_to_download_a_file_referenced_by_a_no_entity_value_results_in_a_404_response(
        self,
        project_fixture: ProjectFixture,
    ):
        # GIVEN - a project with an entity handle and the url pointing to the content of the entity handle
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step/blobs/my-entity"

        # WHEN - executing a GET on the same URL
        response = project_fixture.client.get(url)

        # THEN - the response is a 404 error
        assert response.status_code == 404
        assert response.json()["detail"] == BDM_NO_ENTITY_ERROR_MSG

    def test_stream_entity_handle_from_blobs_endpoint(
        self,
        project_fixture: ProjectFixture,
    ):
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step/blobs/result"
        store_stream_url = f"{project_name}/steps/bdm-step:store-stream"
        project_fixture.client.post(store_stream_url)
        response = project_fixture.client.get(url)
        assert response.text == "hello world!"

    @pytest.mark.parametrize(
        ("filename", "allowed_content_types"),
        [
            ("text.txt", ["text/plain; charset=utf-8"]),
            ("document.pdf", ["application/pdf"]),
            ("img.png", ["image/png"]),
            (
                "word.docx",
                [
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "text/plain; charset=utf-8",
                    "application/octet-stream",
                ],
            ),
            ("script.py", ["text/x-python; charset=utf-8"]),
            ("archive.zip", ["application/x-zip-compressed", "application/zip"]),
            ("geometry.scdoc", ["text/plain; charset=utf-8", "application/octet-stream"]),
        ],
    )
    def test_bdm_download_file(
        self,
        project_fixture: ProjectFixture,
        filename: str,
        allowed_content_types: list[str],
    ) -> None:
        # The OpenAPI spec advertises application/octet-stream as the response content type, but the actual
        # Content-Type header in the response is resolved at runtime by Starlette via mimetypes.guess_type().
        # For unknown files, it falls back to application/octet-stream.
        project_name = project_fixture.properties["name"]
        step_url = f"{project_name}/steps/bdm-step"
        filepath = SOLUTIONS_MOCKS_DIR / "assets" / filename
        payload = {"filename": filepath.as_posix()}
        _ = project_fixture.client.post(f"{step_url}:store-file", json=payload)
        entity_url = f"{project_name}/steps/bdm-step/blobs/result"
        response = project_fixture.client.get(entity_url)
        assert response.headers.get("content-disposition") == f'attachment; filename="{filename}"'
        assert response.headers.get("content-type") in allowed_content_types
        assert response.text


class TestBdmPatchStepField:
    def test_bdm_upload_list_handles(self, project_fixture: ProjectFixture):
        project_name = project_fixture.properties["name"]
        step_url = f"{project_name}/steps/bdm-step"
        response = project_fixture.client.get(step_url)
        assert response.json()["list_handles"] == []

        payload = {
            "list_handles": [
                {
                    "is_blob": True,
                    "original_name": "test",
                    "entity_id": "82420cb0-4061-441d-bd3f-b5c234842153",
                    "opaque_identifier": "test",
                },
            ],
        }
        response = project_fixture.client.patch(step_url, json=payload)
        assert response.status_code == status.HTTP_200_OK
        response = project_fixture.client.get(step_url)
        assert response.json()["list_handles"][0] == payload["list_handles"][0]

    def test_bdm_upload_dict_handles(self, project_fixture: ProjectFixture):
        project_name = project_fixture.properties["name"]
        step_url = f"{project_name}/steps/bdm-step"
        response = project_fixture.client.get(step_url)
        assert response.json()["dict_handles"] == {}

        payload = {
            "dict_handles": {
                "handle": {
                    "is_blob": True,
                    "original_name": "test",
                    "entity_id": "82420cb0-4061-441d-bd3f-b5c234842153",
                    "opaque_identifier": "test",
                },
            },
        }
        response = project_fixture.client.patch(step_url, json=payload)
        assert response.status_code == status.HTTP_200_OK
        response = project_fixture.client.get(step_url)
        assert response.json()["dict_handles"]["handle"] == payload["dict_handles"]["handle"]

    def test_bdm_upload_sub_handles(self, project_fixture: ProjectFixture):
        project_name = project_fixture.properties["name"]
        step_url = f"{project_name}/steps/bdm-step"
        payload = {
            "sub": {
                "sub_handle": {
                    "is_blob": True,
                    "original_name": "sub",
                    "entity_id": "11111111-0000-0000-0000-000000000000",
                    "opaque_identifier": "sub_opaque",
                },
                "inner_sub": {
                    "inner_sub_handle": {
                        "is_blob": True,
                        "original_name": "inner",
                        "entity_id": "22222222-0000-0000-0000-000000000000",
                        "opaque_identifier": "inner_opaque",
                    },
                },
            },
        }
        response = project_fixture.client.patch(step_url, json=payload)
        assert response.status_code == status.HTTP_200_OK
        response = project_fixture.client.get(step_url)
        assert response.json()["sub"]["sub_handle"] == payload["sub"]["sub_handle"]
        assert (
            response.json()["sub"]["inner_sub"]["inner_sub_handle"] == payload["sub"]["inner_sub"]["inner_sub_handle"]
        )


class TestBdmDataRoutes:
    @pytest.mark.parametrize(
        ("datapath", "method", "filename"),
        [
            ("result", "store-result", "result.txt"),
            ("list_handles/0", "store-list-handles", "list_handles.txt"),
            ("dict_handles/dict_handle", "store-dict-handles", "dict_handles.txt"),
            ("directory/subtop/leaf.txt", "store-directory-in-entity-handle", "leaf.txt"),
            ("directory/empty", "store-directory-in-entity-handle", "empty"),
            ("sub/sub_handle", "store-sub-model", "sub.txt"),
            ("sub/inner_sub/inner_sub_handle", "store-sub-model", "inner_sub.txt"),
            ("my_entities/root_file.txt", "manually-create-entities-dict", "root_file.txt"),
            ("my_entities/subdir1/level1_file.json", "manually-create-entities-dict", "level1_file.json"),
        ],
    )
    def test_get_data(self, project_fixture: ProjectFixture, datapath: str, method: str, filename: str):
        project_name = project_fixture.properties["name"]
        method_url = f"{project_name}/steps/bdm-step:{method}"
        project_fixture.client.post(method_url).raise_for_status()
        url = f"{project_name}/steps/bdm-step/data/{datapath}"
        response = project_fixture.client.get(url)
        entity_handle = EntityHandle.model_validate(response.json())
        assert entity_handle != NO_ENTITY
        assert entity_handle.original_name == filename

    @pytest.mark.parametrize(
        ("datapath", "method"),
        [
            ("sub/sub_handle/extra", "store-sub-model"),
            ("sub/wrong_handle", "store-sub-model"),
            ("directory/empty/wrong", "store-directory-in-entity-handle"),
            ("no_entity/wrong", "store-result"),
            ("my_entities/wrong", "manually-create-entities-dict"),
        ],
    )
    def test_get_data_raise_not_found_wrong_entity_handle(
        self,
        project_fixture: ProjectFixture,
        datapath: str,
        method: str,
    ):
        project_name = project_fixture.properties["name"]
        method_url = f"{project_name}/steps/bdm-step:{method}"
        project_fixture.client.post(method_url).raise_for_status()
        url = f"{project_name}/steps/bdm-step/data/{datapath}"
        response = project_fixture.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "The object referenced by the datapath cannot be found" in response.json()["detail"]
