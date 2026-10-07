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
from fastapi.encoders import jsonable_encoder
import pytest
import pytest_mock

from ansys.bdm.api import NO_ENTITY
from ansys.saf.glow._config.const import DatabaseType
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._crud.crud import Crud
import tests.mocks.solutions.bdm_solution as bdm_solution
from tests.unit.routes.conftest import ProjectFixture, wait_for_method_completion

pytestmark = pytest.mark.parametrize(
    "mock_module_settings",
    [{"glow_database_type": DatabaseType.Sqlite}, {"glow_database_type": DatabaseType.PostgreSql}],
    ids=["sqlite", "postgres"],
    indirect=True,
)
solution = bdm_solution


class TestGarbageCollection:
    def test_bdm_gc_store_file_but_no_upload(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-file-but-no-upload"
        assert len(project_fixture.project_files()) == 0
        # WHEN - executing the transaction
        project_fixture.client.post(url)
        # THEN - the file has been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 0

    def test_bdm_gc_add_bdm_lock_keep_files_after_method(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-file-but-no-upload"
        assert len(project_fixture.project_files()) == 0
        # WHEN - adding a bdm transaction
        project_fixture.client.post(f"{project_name}/bdm-locks")
        # AND - executing the transaction while a bdm transaction has been added
        project_fixture.client.post(url)
        # THEN - the file has not been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 1

    def test_bdm_gc_add_bdm_lock_while_storing_twice_keep_all_files(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        assert len(project_fixture.project_files()) == 0
        # WHEN - adding a bdm transaction
        project_fixture.client.post(f"{project_name}/bdm-locks")
        # AND - executing the method storing entity handles twice
        project_fixture.client.post(url)
        project_fixture.client.post(url)
        # THEN - the files have not been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 2

    def test_bdm_gc_store_entity_handle_list_keep_files(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-list-handles"
        assert len(project_fixture.project_files()) == 0
        # AND - executing the method storing entity handles in submodel
        project_fixture.client.post(url)
        # THEN - the files have not been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 1

    def test_bdm_gc_remove_entity_handle_list_remove_files(self, project_fixture: ProjectFixture):
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-list-handles"
        project_fixture.client.post(url)
        project_files = project_fixture.project_files()
        assert len(project_files) == 1
        url = f"{project_name}/steps/bdm-step:remove-list-handles"
        project_fixture.client.post(url)
        project_files = project_fixture.project_files()
        assert len(project_files) == 0

    def test_bdm_gc_pop_entity_handle_from_list_remove_file(self, project_fixture: ProjectFixture):
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-list-handles"
        project_fixture.client.post(url)
        project_files = project_fixture.project_files()
        assert len(project_files) == 1
        url = f"{project_name}/steps/bdm-step:pop-list-handles"
        project_fixture.client.post(url)
        project_files = project_fixture.project_files()
        assert len(project_files) == 0

    def test_bdm_gc_store_entity_handle_in_dict_keep_files(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-dict-handles"
        assert len(project_fixture.project_files()) == 0
        # AND - executing the method storing entity handles in submodel
        project_fixture.client.post(url)
        # THEN - the files have not been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 1

    def test_bdm_gc_store_entity_handle_in_submodel_keep_files(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-sub-model"
        assert len(project_fixture.project_files()) == 0
        # AND - executing the method storing entity handles in submodel
        project_fixture.client.post(url)
        # THEN - the files have not been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 2

    def test_bdm_gc_add_bdm_lock_keep_files_after_field_no_entity(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        assert len(project_fixture.project_files()) == 0
        project_fixture.client.post(f"{project_name}/steps/bdm-step:store-result")
        # WHEN - adding a bdm transaction
        project_fixture.client.post(f"{project_name}/bdm-locks")
        # AND - setting the result handle to NO_ENTITY
        payload = {"result": jsonable_encoder(NO_ENTITY.model_dump())}
        project_fixture.client.patch(f"{project_name}/steps/bdm-step", json=payload)
        # THEN - the result file has not been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 1

    def test_bdm_gc_overwrite_entity_handle_from_transaction_remove_previous_file(
        self,
        project_fixture: ProjectFixture,
    ):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        assert len(project_fixture.project_files()) == 0
        # WHEN - executing the transaction
        project_fixture.client.post(url)
        # THEN - the file has been created and has the right content
        assert len(project_fixture.project_files()) == 1
        result_txt = next(project_fixture.project_files_dir.rglob("result.txt"))
        assert result_txt.read_text() == "hello world!"
        # WHEN - overwriting the entity handle
        url = f"{project_name}/steps/bdm-step:overwrite-result"
        project_fixture.client.post(url)
        # THEN - the previous file has been removed
        assert not result_txt.exists()
        assert len(project_fixture.project_files()) == 1
        # AND - the new file has the right content
        result_txt = next(project_fixture.project_files_dir.rglob("result.txt"))
        assert result_txt.read_text() == "another hello world!"

    def test_bdm_gc_upload_overwrite_entity_handle_remove_previous_file(
        self,
        project_fixture: ProjectFixture,
        tmp_path: Path,
    ):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        assert len(project_fixture.project_files()) == 0
        # WHEN - executing the transaction
        project_fixture.client.post(url)
        result_txt = next(project_fixture.project_files_dir.rglob("result.txt"))
        assert result_txt.read_text() == "hello world!"
        # WHEN - uploading the file to the existing entity handle
        overwrite_txt = tmp_path / "result.txt"
        overwrite_txt.write_text("overwrite")
        url = f"{project_name}/steps/bdm-step/blobs/result"
        with overwrite_txt.open("rb") as file_stream:
            project_fixture.client.put(url, files={"upload_file": ("result.txt", file_stream)})
        # THEN - the previous file has been removed
        assert not result_txt.exists()
        assert len(project_fixture.project_files()) == 1
        # AND - the new file has the right content
        result_txt = next(project_fixture.project_files_dir.rglob("result.txt"))
        assert result_txt.read_text() == "overwrite"

    def test_bdm_gc_patch_step_remove_previous_file(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        assert len(project_fixture.project_files()) == 0
        # WHEN - executing the transaction
        project_fixture.client.post(url)
        # THEN - the file has been created and has the right content
        result_txt = next(project_fixture.project_files_dir.rglob("result.txt"))
        assert result_txt.read_text() == "hello world!"
        # WHEN - updating step with a no_entity to the existing entity handle
        url = f"{project_name}/steps/bdm-step"
        payload = {"result": jsonable_encoder(NO_ENTITY.model_dump())}
        project_fixture.client.patch(url, json=payload)
        # THEN - the previous file has been removed
        assert not result_txt.exists()
        assert len(project_fixture.project_files()) == 0

    def test_bdm_gc_update_blob_use_bdm_lock(
        self,
        mocker: pytest_mock.MockerFixture,
        tmp_path: Path,
        project_fixture: ProjectFixture,
    ):
        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

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
            project_fixture.client.put(url, files={"upload_file": (file_name, file_stream)})
        # THEN - the bdm transaction has been used
        add_bdm_lock.assert_called_once()
        remove_bdm_lock.assert_called_once()

    def test_bdm_gc_patch_step_with_entity_handle_use_bdm_lock(
        self,
        mocker: pytest_mock.MockerFixture,
        project_fixture: ProjectFixture,
    ):
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step"

        project_fixture.client.post(f"{url}:store-result").raise_for_status()
        entity_handle_json = project_fixture.client.get(f"{url}/data/result").json()

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")
        project_fixture.client.patch(url, json={"result": entity_handle_json})
        add_bdm_lock.assert_called_once()
        remove_bdm_lock.assert_called_once()

    def test_bdm_gc_patch_step_without_entity_handle_dont_use_bdm_lock(
        self,
        mocker: pytest_mock.MockerFixture,
        project_fixture: ProjectFixture,
    ):
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step"

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")
        project_fixture.client.patch(url, json={"other": "3"})
        add_bdm_lock.assert_not_called()
        remove_bdm_lock.assert_not_called()

    def test_bdm_gc_post_method_with_entity_handle_use_bdm_lock(
        self,
        mocker: pytest_mock.MockerFixture,
        project_fixture: ProjectFixture,
    ):
        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        project_fixture.client.post(url)
        assert add_bdm_lock.call_count == 2  # (2 locks, one for the transaction and one for the upload)
        assert remove_bdm_lock.call_count == 2


class TestGarbageCollectionDisabled:
    @pytest.fixture(autouse=True)
    def gc_disabled(self, settings: Settings):
        settings.glow_bdm_gc_disabled = True

    def test_bdm_gc_store_file_but_no_upload_keeps_file(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-file-but-no-upload"
        assert len(project_fixture.project_files()) == 0
        # WHEN - executing the transaction
        project_fixture.client.post(url)
        # THEN - the file has NOT been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 1

    def test_bdm_gc_no_entity_not_removed(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        assert len(project_fixture.project_files()) == 0
        project_fixture.client.post(f"{project_name}/steps/bdm-step:store-result")
        # AND - setting the result handle to NO_ENTITY
        payload = {"result": jsonable_encoder(NO_ENTITY.model_dump())}
        project_fixture.client.patch(f"{project_name}/steps/bdm-step", json=payload)
        # THEN - the result file has not been removed
        project_files = project_fixture.project_files()
        assert len(project_files) == 1

    def test_bdm_gc_overwrite_entity_handle_from_transaction_remove_previous_file(
        self,
        project_fixture: ProjectFixture,
    ):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        assert len(project_fixture.project_files()) == 0
        # WHEN - executing the transaction
        project_fixture.client.post(url)
        # THEN - the file has been created and has the right content
        assert len(project_fixture.project_files()) == 1
        result_txt = next(project_fixture.project_files_dir.rglob("result.txt"))
        # WHEN - overwriting the entity handle
        url = f"{project_name}/steps/bdm-step:overwrite-result"
        project_fixture.client.post(url)
        # THEN - the previous file has NOT been removed
        assert result_txt.exists()
        assert len(project_fixture.project_files()) == 2

    def test_bdm_gc_overwrite_entity_handle_from_http_keep_previous_file(
        self,
        project_fixture: ProjectFixture,
        tmp_path: Path,
    ):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        assert len(project_fixture.project_files()) == 0
        # WHEN - executing the transaction
        project_fixture.client.post(url)
        result_txt = next(project_fixture.project_files_dir.rglob("result.txt"))
        # WHEN - uploading the file to the existing entity handle
        overwrite_txt = tmp_path / "result.txt"
        overwrite_txt.write_text("overwrite")
        url = f"{project_name}/steps/bdm-step/blobs/result"
        with overwrite_txt.open("rb") as file_stream:
            project_fixture.client.put(url, files={"upload_file": ("result.txt", file_stream)})
        # THEN - the previous file has been removed
        assert result_txt.exists()
        assert len(project_fixture.project_files()) == 2

    def test_bdm_gc_upload_no_entity_keep_previous_file(self, project_fixture: ProjectFixture):
        # GIVEN - a transaction storing a file using bdm
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        assert len(project_fixture.project_files()) == 0
        # WHEN - executing the transaction
        project_fixture.client.post(url)
        # THEN - the file has been created and has the right content
        result_txt = next(project_fixture.project_files_dir.rglob("result.txt"))
        # WHEN - uploading no_entity to the existing entity handle
        url = f"{project_name}/steps/bdm-step"
        payload = {"result": jsonable_encoder(NO_ENTITY.model_dump())}
        project_fixture.client.patch(url, json=payload)
        # THEN - the previous file has not been removed
        assert result_txt.exists()
        assert len(project_fixture.project_files()) == 1

    def test_bdm_gc_update_blob_dont_use_bdm_lock(
        self,
        mocker: pytest_mock.MockerFixture,
        tmp_path: Path,
        project_fixture: ProjectFixture,
    ):
        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

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
            project_fixture.client.put(url, files={"upload_file": (file_name, file_stream)})
        # THEN - the bdm lock has not been used
        add_bdm_lock.assert_not_called()
        remove_bdm_lock.assert_not_called()

    def test_bdm_gc_patch_step_with_entity_handle_dont_use_bdm_lock(
        self,
        mocker: pytest_mock.MockerFixture,
        project_fixture: ProjectFixture,
    ):
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step"

        project_fixture.client.post(f"{url}:store-result").raise_for_status()
        entity_handle_json = project_fixture.client.get(f"{url}/data/result").json()

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")
        project_fixture.client.patch(url, json={"result": entity_handle_json})
        add_bdm_lock.assert_not_called()
        remove_bdm_lock.assert_not_called()

    def test_bdm_gc_post_method_with_entity_handle_dont_use_bdm_lock(
        self,
        mocker: pytest_mock.MockerFixture,
        project_fixture: ProjectFixture,
    ):
        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/bdm-step:store-result"
        project_fixture.client.post(url)
        add_bdm_lock.assert_not_called()
        remove_bdm_lock.assert_not_called()

    def test_post_bdm_lock_gc_disabled_raise_error(self, project_fixture: ProjectFixture):
        project = project_fixture.properties
        response = project_fixture.client.post(f"{project['name']}/bdm-locks")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Garbage collection is disabled" in response.json()["detail"]

    def test_get_bdm_lock_gc_disabled_raise_error(self, project_fixture: ProjectFixture):
        project = project_fixture.properties
        response = project_fixture.client.get(f"{project['name']}/bdm-locks/fake_id")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Garbage collection is disabled" in response.json()["detail"]

    def test_delete_bdm_lock_gc_disabled_raise_error(self, project_fixture: ProjectFixture):
        project = project_fixture.properties
        response = project_fixture.client.delete(f"{project['name']}/bdm-locks/fake_id")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Garbage collection is disabled" in response.json()["detail"]


class TestBdmGarbageCollectorLocks:
    def test_transaction_with_entity_handle_in_return_value(
        self,
        project_fixture: ProjectFixture,
        mocker: pytest_mock.MockerFixture,
    ):
        project_name = project_fixture.properties["name"]

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

        # WHEN - executing the transaction returning entity handles
        project_fixture.client.post(f"{project_name}/steps/bdm-step:store-file-but-no-upload").raise_for_status()
        # THEN - the bdm locks have been used (no upload, so only one lock for the transaction)
        assert add_bdm_lock.call_count == 1
        assert remove_bdm_lock.call_count == 1

    def test_transaction_with_entity_handle_in_input_param(
        self,
        project_fixture: ProjectFixture,
        mocker: pytest_mock.MockerFixture,
    ):
        project_name = project_fixture.properties["name"]
        project_fixture.client.post(f"{project_name}/steps/bdm-step:store-result").raise_for_status()
        entity_handle_json = project_fixture.client.get(f"{project_name}/steps/bdm-step/data/result").json()

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

        # WHEN - executing the transaction that has an entity handle as input
        project_fixture.client.post(
            f"{project_name}/steps/bdm-step:get-text-from-input-handle-no-download",
            json={"handle": entity_handle_json},
        ).raise_for_status()
        # THEN - the bdm locks have been used (no upload, so only one lock for the transaction)
        assert add_bdm_lock.call_count == 1
        assert remove_bdm_lock.call_count == 1

    @pytest.mark.parametrize(
        ("transaction_upload_name", "transaction_download_name"),
        [
            ("store_result", "get_text_result"),
            ("store_list_handles", "get_text_first_item_list_handles"),
            ("store_dict_handles", "get_text_handle_item_dict_handles"),
            ("store_sub_model", "get_text_sub_handle"),
            ("store_directory_in_entity_handle", "get_directory_children"),
            ("upload_directory_to_recursive_dict", "download_directory_from_recursive_dict"),
        ],
    )
    def test_transaction_with_entity_handles_in_step_spec_upload_or_download(
        self,
        project_fixture: ProjectFixture,
        mocker: pytest_mock.MockerFixture,
        transaction_upload_name: str,
        transaction_download_name: str,
    ):
        project_name = project_fixture.properties["name"]

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

        # WHEN - executing the transaction uploading entity handles
        project_fixture.client.post(
            f"{project_name}/steps/bdm-step:{transaction_upload_name.replace('_', '-')}",
        ).raise_for_status()
        # THEN - the bdm locks have been used (2 locks, one for the transaction and one for the upload)
        assert add_bdm_lock.call_count == 2
        assert remove_bdm_lock.call_count == 2

        add_bdm_lock.reset_mock()
        remove_bdm_lock.reset_mock()

        # WHEN - executing the transaction downloading entity handles
        project_fixture.client.post(
            f"{project_name}/steps/bdm-step:{transaction_download_name.replace('_', '-')}",
        ).raise_for_status()
        # THEN - the bdm locks have been used (no upload, so only one lock for the transaction)
        assert add_bdm_lock.call_count == 1
        assert remove_bdm_lock.call_count == 1

    def test_long_running_transaction_with_entity_handles_in_step_spec_upload_or_download(
        self,
        project_fixture: ProjectFixture,
        mocker: pytest_mock.MockerFixture,
    ):
        project_name = project_fixture.properties["name"]

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

        # WHEN - executing the long running transaction uploading entity handles
        upload_method_url = f"{project_name}/steps/bdm-step:store-result-long-running"
        project_fixture.client.post(upload_method_url).raise_for_status()
        wait_for_method_completion(project_fixture.client, upload_method_url)
        # THEN - the bdm locks have been used (2 locks, one for the transaction and one for the upload)
        assert add_bdm_lock.call_count == 2
        assert remove_bdm_lock.call_count == 2

        add_bdm_lock.reset_mock()
        remove_bdm_lock.reset_mock()

        # WHEN - executing the long running transaction downloading entity handles
        download_method_url = f"{project_name}/steps/bdm-step:get-cached-result-long-running"
        project_fixture.client.post(download_method_url).raise_for_status()
        wait_for_method_completion(project_fixture.client, download_method_url)
        # THEN - the bdm locks have been used (no upload, so only one lock for the transaction)
        assert add_bdm_lock.call_count == 1
        assert remove_bdm_lock.call_count == 1

    def test_transaction_with_entity_handles_in_others_step_spec_upload_or_download(
        self,
        project_fixture: ProjectFixture,
        mocker: pytest_mock.MockerFixture,
    ):
        project_name = project_fixture.properties["name"]

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

        # WHEN - executing the transaction uploading entity handle
        project_fixture.client.post(f"{project_name}/steps/bdm-step:store-file-in-entity-handle").raise_for_status()
        # THEN - the bdm locks have been used (2 locks, one for the transaction and one for the upload)
        assert add_bdm_lock.call_count == 2
        assert remove_bdm_lock.call_count == 2

        add_bdm_lock.reset_mock()
        remove_bdm_lock.reset_mock()

        # WHEN - executing the transaction downloading entity handles from another step
        project_fixture.client.post(
            f"{project_name}/steps/other-bdm-step:get-text-from-handle-from-other-step",
        ).raise_for_status()
        # THEN - the bdm locks have been used (no upload, so only one lock for the transaction)
        assert add_bdm_lock.call_count == 1
        assert remove_bdm_lock.call_count == 1

    def test_transaction_no_entity_handles_in_step_spec(
        self,
        project_fixture: ProjectFixture,
        mocker: pytest_mock.MockerFixture,
    ):
        project_name = project_fixture.properties["name"]

        add_bdm_lock = mocker.spy(Crud, "add_bdm_lock")
        remove_bdm_lock = mocker.spy(Crud, "remove_bdm_lock")

        # WHEN - executing the transaction not using entity handles, downloading int
        project_fixture.client.post(f"{project_name}/steps/bdm-step:duplicate-other").raise_for_status()
        # THEN - the bdm locks have NOT been used
        add_bdm_lock.assert_not_called()
        remove_bdm_lock.assert_not_called()

        # WHEN - executing the transaction not using entity handles, uploading int
        project_fixture.client.post(f"{project_name}/steps/bdm-step:upload-other", json={"other": 4}).raise_for_status()
        # THEN - the bdm locks have NOT been used
        add_bdm_lock.assert_not_called()
        remove_bdm_lock.assert_not_called()
