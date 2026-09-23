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

import asyncio
from collections.abc import Generator
import io
from pathlib import Path
import random
import tempfile
import time
from typing import Any
from unittest import mock
from unittest.mock import patch
import zipfile

from ansys.iam.oidc import OidcDependency
from fastapi import Request, status
from fastapi.testclient import TestClient
import httpx2
from httpx2 import AsyncClient, Response
import pytest
from pytest_mock.plugin import MockerFixture
from starlette.datastructures import URL

from ansys.saf.glow._config.const import DatabaseType, Deployment, ProductInstanceSystemType
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.exceptions import SolutionLoadException
from ansys.saf.glow._executor.transaction import VALID_URL_CHARACTERS, Transaction
from ansys.saf.glow._hps_auth.hps_authenticator import NullHpsAuthenticator
from ansys.saf.glow._hps_parametric_studies.api import HpsParametricStudyProject, HpsSimpleProject
from ansys.saf.glow._hps_parametric_studies.base import (
    DynamicHpsParametricStudyProject,
    DynamicHpsProject,
    DynamicHpsSimpleProject,
)
from ansys.saf.glow._server.dependencies import get_method_url, oidc_scheme
from ansys.saf.glow._server.exceptions import INTERNAL_ERROR_MESSAGE
from ansys.saf.glow._server.server import create_app
from tests.check_message import MATCH_ANYTHING, check_message
import tests.mocks.solutions.transactions as transactions
from tests.unit.routes.conftest import ProjectFixture

pytestmark = pytest.mark.parametrize(
    "mock_module_settings",
    [{"glow_database_type": DatabaseType.Sqlite}, {"glow_database_type": DatabaseType.PostgreSql}],
    ids=["sqlite", "postgres"],
    indirect=True,
)
solution = transactions


@pytest.fixture
def method_tmpdir(tmp_path: Path) -> Generator[Path, None, None]:
    # We are assuming that the patched function is used exclusively
    # in the transaction logic as the method temp directory.
    with patch.object(tempfile, "mkdtemp") as mock:
        method_dir = tmp_path / "method_dir"
        method_dir.mkdir()
        mock.return_value = str(method_dir)
        yield method_dir


@pytest.fixture
def project_file(project_fixture: ProjectFixture) -> Generator[Path, None, None]:
    project_file = project_fixture.project_files_dir / "dir" / "file.txt"
    project_file.parent.mkdir(exist_ok=True, parents=True)
    project_file.write_text("hello world")
    yield project_file
    project_file.unlink(missing_ok=True)


def mock_additional_telemetry_variables(*args: Any, **kwargs: Any):
    return {
        "step_name": "not relevant",
        "method_name": "not relevant",
        "project_directory": "not relevant",
    }


def run_method(client: TestClient, url: str):
    response = client.post(url)
    assert response.status_code == status.HTTP_200_OK


def test_method_transaction_increment_get_and_set_step_field(project_fixture: ProjectFixture):
    """Test that a transaction can get and set a step field."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:increment"
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 99
    # Act
    run_method(project_fixture.client, url)
    # Assert
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 100


@pytest.mark.usefixtures("project_file")
def test_method_transaction_return_multiple_fields(project_fixture: ProjectFixture):
    """Test that a transaction can get and set all fields."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:return-x-and-y"
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 99
    # Act
    run_method(project_fixture.client, url)
    # Assert
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 12
    assert response.json()["y"] == 1234


def test_method_transaction_download_x_upload_y(project_fixture: ProjectFixture):
    """Test that a transaction can selectively download a field and upload another."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:download-x-upload-y"
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 99
    assert response.json()["y"] == 1
    # Act
    run_method(project_fixture.client, url)
    # Assert
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 99
    assert response.json()["y"] == 99


def test_method_transaction_download_updated_x_upload_y(project_fixture: ProjectFixture):
    """Test that a transaction can selectively download an updated field and upload another."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:download-x-upload-y"
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 99
    assert response.json()["y"] == 1
    response = project_fixture.client.patch(step_url, json={"x": 56})
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 56
    assert response.json()["y"] == 1
    # Act
    run_method(project_fixture.client, url)
    # Assert
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == 56
    assert response.json()["y"] == 56


def test_hps_project_collections_are_persisted_and_rehydrated(
    mocker: MockerFixture,
    project_fixture: ProjectFixture,
    hps_blob_manager: Any,
):
    simple_identifiers = [
        "simple-list-1",
        "simple-list-2",
        "simple-dict-1",
        "simple-dict-2",
    ]
    study_identifiers = ["study-list-1", "study-list-2", "study-dict-1", "study-dict-2"]
    authenticator = NullHpsAuthenticator()
    simple_projects = [
        DynamicHpsSimpleProject(
            HpsSimpleProject(hps_project_identifier=identifier),
            hps_blob_manager,
            authenticator,
        )
        for identifier in simple_identifiers
    ]
    study_projects = [
        DynamicHpsParametricStudyProject(
            HpsParametricStudyProject(hps_project_identifier=identifier),
            hps_blob_manager,
            authenticator,
        )
        for identifier in study_identifiers
    ]
    mocker.patch.object(HpsSimpleProject, "start_hps_job", side_effect=simple_projects)
    mocker.patch.object(HpsParametricStudyProject, "start_hps_parametric_study", side_effect=study_projects)

    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.post(f"{step_url}:append-hps-project-collections")

    assert response.status_code == status.HTTP_200_OK, response.content
    persisted_step = project_fixture.client.get(step_url).json()
    assert [project["hps_project_identifier"] for project in persisted_step["simple_projects"]] == simple_identifiers[
        :2
    ]
    assert [project["hps_project_identifier"] for project in persisted_step["study_projects"]] == study_identifiers[:2]
    assert {
        key: project["hps_project_identifier"] for key, project in persisted_step["simple_projects_by_name"].items()
    } == {"first": simple_identifiers[2], "second": simple_identifiers[3]}
    assert {
        key: project["hps_project_identifier"] for key, project in persisted_step["study_projects_by_name"].items()
    } == {"first": study_identifiers[2], "second": study_identifiers[3]}
    assert {
        key: [project["hps_project_identifier"] for project in projects]
        for key, projects in persisted_step["nested_simple_projects"].items()
    } == {"group_1": simple_identifiers[:2]}

    hps_project = mocker.MagicMock()
    hps_project.ui_url = "https://hps.example/projects/test"
    hps_project.finished = True
    hps_project.exists = True
    hps_project.get_status_of_design_points.return_value = [mocker.MagicMock()]
    hps_project.fetch_values_of_parameters.return_value = [[42]]
    mocker.patch.object(DynamicHpsProject, "_get_project", return_value=hps_project)

    response = project_fixture.client.post(f"{step_url}:inspect-hps-project-collections")

    assert response.status_code == status.HTTP_200_OK, response.content
    assert response.json() == {
        "all_simple_projects_are_dynamic": True,
        "all_study_projects_are_dynamic": True,
        "identifiers": [
            *simple_identifiers[:2],
            *simple_identifiers[2:],
            *simple_identifiers[:2],
            *study_identifiers[:2],
            *study_identifiers[2:],
        ],
        "dictionary_keys": ["first", "second", "first", "second"],
        "nested_dictionary_keys": ["group_1"],
        "ui_urls": ["https://hps.example/projects/test"] * 10,
        "finished": [True] * 10,
        "exists": [True] * 10,
        "status_counts": [1] * 4,
        "parameter_values": [[[42]]] * 4,
    }


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}], indirect=True)
def test_hps_project_collections_reject_raw_projects(project_fixture: ProjectFixture):
    project_name = project_fixture.properties["name"]

    response = project_fixture.client.post(
        f"{project_name}/steps/transaction-step:append-raw-hps-project-to-collection",
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "simple_projects" in response.json()["detail"]
    assert "HPS project handle" in response.json()["detail"]
    assert "start_hps_job" in response.json()["detail"]


def test_method_transaction_increment_other_step_field(project_fixture: ProjectFixture):
    """Test that a transaction can get another step field."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:increment-from-other-step"
    other_step_url = f"{project_name}/steps/other-step"
    response = project_fixture.client.get(other_step_url)
    other_step_x = response.json()["x"]
    # Act
    run_method(project_fixture.client, url)
    # Assert
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url)
    assert response.json()["x"] == other_step_x + 1


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_method_accessing_field_not_defined_in_the_transaction_results_in_an_exception(
    project_fixture: ProjectFixture,
    settings: Settings,
):
    """Test that one cannot access a field that is not defined in the transaction."""
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:access-field-that-is-not-declared-in-transaction"
    error_message = (
        (
            "The solution definition is invalid: "
            "invalid attribute 'x' in TransactionStep.access_field_that_is_not_declared_in_transaction. "
            "Please make sure that the field is declared in the step and in the transaction decorating the method."
        )
        if settings.glow_debug
        else INTERNAL_ERROR_MESSAGE
    )
    response = project_fixture.client.post(url)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert error_message in response.json()["detail"]


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
@pytest.mark.parametrize(
    ("transaction_name", "expected_error"),
    [
        (
            "assign-int-to-string-field",
            [
                "The solution definition is invalid: Uploading during the execution of assign_int_to_string_field:",
                "1 validation error for TransactionStep",
                "str_field",
                "Input should be a valid string [type=string_type, input_value=99, input_type=int]",
            ],
        ),
        (
            "assign-string-to-int-field",
            [
                "The solution definition is invalid: Uploading during the execution of assign_string_to_int_field:",
                "1 validation error for TransactionStep",
                "x",
                "Input should be a valid integer, unable to parse string as an integer [type=int_parsing, "
                "input_value='foo', input_type=str]",
            ],
        ),
        (
            "assign-custom-model-to-entity-handle",
            [
                "The solution definition is invalid: Uploading during the execution of "
                "assign_custom_model_to_entity_handle:",
                "1 validation error for TransactionStep",
                "stored_entity",
                "Input should be a valid dictionary or instance of EntityHandle "
                "[type=model_type, input_value=CustomField(x=1, y=2, z=3), "
                "input_type=CustomField]",
            ],
        ),
        (
            "assign-multiple-fields-wrong-types",
            [
                "The solution definition is invalid: Uploading during the execution of "
                "assign_multiple_fields_wrong_types:",
                "1 validation error for TransactionStep",
                "x",
                "Input should be a valid integer, unable to parse string as an integer [type=int_parsing, "
                "input_value='foo', input_type=str]",
                MATCH_ANYTHING,
                "1 validation error for TransactionStep",
                "str_field",
                "Input should be a valid string [type=string_type, input_value=99, input_type=int]",
                MATCH_ANYTHING,
                "1 validation error for TransactionStep",
                "stored_entity",
                "Input should be a valid dictionary or instance of EntityHandle [type=model_type, "
                "input_value=CustomField(x=1, y=2, z=3), input_type=CustomField]",
            ],
        ),
    ],
)
def test_method_assigning_the_wrong_type_to_a_field_results_in_a_helpful_exception(
    project_fixture: ProjectFixture,
    settings: Settings,
    transaction_name: str,
    expected_error: list[str],
):
    """Test that in debug mode a helpful error message is
    raised when assigning the wrong type to a field in a transaction."""
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:{transaction_name}"
    response = project_fixture.client.post(url)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.content

    detail = response.json()["detail"]
    if settings.glow_debug:
        check_message(expected_error, detail)
    else:
        assert detail == INTERNAL_ERROR_MESSAGE


@pytest.mark.parametrize(
    "settings",
    [
        {"glow_deployment": Deployment.DockerCompose},
        {"glow_deployment": Deployment.Desktop},
        {"glow_deployment": Deployment.Unknown},
    ],
    ids=["non_desktop", "desktop", "unknown"],
    indirect=True,
)
def test_method_transaction_call_internal_method_modify_field(project_fixture: ProjectFixture):
    """Test that a transaction can call internal method not marked as transaction."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:call-internal-method"
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url).json()
    x = response["x"]
    y = response["y"]
    assert x != y
    # Act
    run_method(project_fixture.client, url)
    # Assert
    response = project_fixture.client.get(step_url).json()
    x = response["x"]
    y = response["y"]
    assert x == y


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_method_transaction_call_internal_method_wrong_field_throw_exception(
    project_fixture: ProjectFixture,
    settings: Settings,
):
    """Test that a transaction calling an internal method cannot access fields outside
    of the enclosing transaction."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:call-internal-method-wrong-field"
    # Act
    error_message = (
        ("The solution definition is invalid: invalid attribute 'x'") if settings.glow_debug else INTERNAL_ERROR_MESSAGE
    )
    response = project_fixture.client.post(url)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert error_message in response.json()["detail"]


def test_method_transaction_wrong_parameter_order_works(
    project_fixture: ProjectFixture,
):
    """Test that a transaction method with parameters in the wrong order works."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:method-parameter-wrong-order"
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url).json()
    assert response["x"] == 99
    # Act
    run_method(project_fixture.client, url)
    # Assert
    response = project_fixture.client.get(step_url).json()
    assert response["x"] == 89


def test_method_upload_custom_field(
    project_fixture: ProjectFixture,
):
    """Test that a transaction method with a custom field type."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:upload-custom-field"
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url).json()
    assert response["custom_field"]["x"] == 1
    assert response["custom_field"]["y"] == 2
    assert response["custom_field"]["z"] == 3
    # Act
    run_method(project_fixture.client, url)
    # Assert
    response = project_fixture.client.get(step_url).json()
    assert response["custom_field"]["x"] == 4
    assert response["custom_field"]["y"] == 5
    assert response["custom_field"]["z"] == 6


async def test_already_running_exception_not_thrown_for_sync_methods(
    mocker: MockerFixture,
    project_fixture: ProjectFixture,
    async_client: AsyncClient,
):
    start_time = time.time()
    run_method_called_times: list[float] = []
    method_elapsed_time = 0.5

    def run_method_mock(solution_configuration: tuple[str, Any], input_params: dict[str, Any]):
        run_method_called_times.append(time.time() - start_time)
        time.sleep(method_elapsed_time)

    m = mocker.patch("ansys.saf.glow._executor.method_runner.ThreadMethodRunner.run_method")
    m.side_effect = run_method_mock

    async def launch_transaction(url: str) -> Response:
        response = await async_client.post(url=url)
        return response

    async def wait_running(url: str) -> Response:
        attempt = 0
        response = await async_client.get(url=url)
        status = response.json()["status"]
        while status != "run-required" and attempt < 10:
            status = response.json()["status"]
            await asyncio.sleep(0.1)
            attempt += 1
        return response

    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:one-second-sync"
    call_task1 = asyncio.create_task(launch_transaction(url))
    # wait a bit to be sure that the first call to the method is running
    await wait_running(url)
    call_task2 = asyncio.create_task(launch_transaction(url))
    await call_task1
    response = await call_task2
    assert response.status_code == status.HTTP_200_OK
    # Verify that the second call to MethodRunner.run_method has been called after the first one has been completed.
    assert run_method_called_times[1] - run_method_called_times[0] >= method_elapsed_time


@pytest.mark.parametrize(
    "request_url",
    [
        "my_app.my_host",  # solution accessible via subdomain using reverse proxy
        "my_host:5432",  # different host and port externally
        "my_host:5432/my_application",  # externally, solution available at sub-path
    ],
)
async def test_method_runner_initialized_with_internal_netloc(request_url: str):
    class MockRequest:
        @property
        def url(self) -> URL:
            return URL(f"http://{request_url}/projects/fake_project_id/steps/transaction-step:download-x-upload-y")

    internal_api_port = random.randint(10000, 20000)
    expected_url = (
        f"http://localhost:{internal_api_port}/projects/fake_project_id/steps/transaction-step:download-x-upload-y"
    )
    assert str(MockRequest().url) != expected_url

    method_url = await get_method_url(
        "fake_project_id",
        MockRequest(),  # type: ignore
        Settings(glow_solution_definition="tests.mocks.solutions.transactions", glow_api_port=internal_api_port),
    )
    assert method_url.url == expected_url


def test_method_upload_fields_not_working_with_strict(
    project_fixture: ProjectFixture,
):
    """Test that step fields not working with strict mode are properly working."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:upload-fields-not-working-with-strict"
    step_url = f"{project_name}/steps/transaction-step"
    response = project_fixture.client.get(step_url).json()
    assert response["dict_int_int"] == {}
    assert response["my_list_of_tuple"] == [["a", "b"], ["c", "d"]]
    assert response["my_enum"] == "a"
    assert response["my_tuple"] == ["a", "b"]
    # Act
    run_method(project_fixture.client, url)
    # Assert
    response = project_fixture.client.get(step_url).json()
    assert response["dict_int_int"] == {"0": 0}
    assert response["my_list_of_tuple"] == [["e", "f"]]
    assert response["my_enum"] == "b"
    assert response["my_tuple"] == ["c", "d"]


@pytest.mark.parametrize(
    ("method_name", "stream_name", "expected_str"),
    [
        ("raise-event", None, "hello1"),
        ("raise-event-long-running", None, "hello4"),
        ("raise-event-custom-stream-name", "my-stream", "hello2"),
    ],
)
def test_raise_event(
    method_name: str,
    stream_name: str | None,
    expected_str: str,
    project_fixture: ProjectFixture,
    mocker: MockerFixture,
):
    class MockHttpClient:
        def post(self, *args: Any, **kwargs: dict[str, Any]) -> None:
            expected_url = (
                f"http://localhost:5432/events/projects/{project_fixture.project_id}/"
                f"steps/transaction-step/streams/{expected_stream_name}"
            )
            assert args[0] == expected_url
            assert kwargs["json"] == {"message": expected_str}

    class MockTransaction(Transaction):
        def __init__(self, *args: Any, **kwargs: dict[str, Any]):
            super().__init__(*args, **kwargs)
            self._http_client = MockHttpClient()

    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:{method_name}"
    expected_stream_name = stream_name or method_name
    mocker.patch("ansys.saf.glow._executor.transaction.Transaction", MockTransaction)
    run_method(project_fixture.client, url)


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_raise_event_invalid_stream_name(project_fixture: ProjectFixture, settings: Settings):
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:raise-event-invalid-custom-stream-name"
    response = project_fixture.client.post(url)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    error_message = (
        (f"RuntimeError: Invalid stream_name='my_stream'. Valid characters: {','.join(VALID_URL_CHARACTERS)}.")
        if settings.glow_debug
        else INTERNAL_ERROR_MESSAGE
    )
    assert error_message in response.json()["detail"]


def test_raise_event_invalid_message(project_fixture: ProjectFixture):
    project_name = project_fixture.properties["name"]
    ws_url = f"/events/{project_name}/steps/transaction-step/streams/test-stream"
    response = project_fixture.client.post(ws_url, json=None)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid JSON" in response.text


@pytest.mark.parametrize(
    "request_url",
    [
        "my_app.my_host",  # solution accessible via subdomain using reverse proxy
        "my_host:5432",  # different host and port externally
        "my_host:5432/my_application",  # externally, solution available at sub-path
    ],
)
def test_raise_event_with_internal_netloc(request_url: str, project_fixture: ProjectFixture, mocker: MockerFixture):
    project_name = project_fixture.properties["name"]
    transaction_name = "raise-event"
    url = f"{project_name}/steps/transaction-step:{transaction_name}"

    class MockHttpClient:
        def post(self, *args: Any, **kwargs: dict[str, Any]) -> None:
            expected_url = (
                f"http://localhost:5432/events/projects/{project_fixture.project_id}/"
                f"steps/transaction-step/streams/raise-event"
            )
            assert args[0] == expected_url
            assert kwargs["json"] == {"message": "hello1"}

    class MockTransaction(Transaction):
        def __init__(self, *args: Any, **kwargs: dict[str, Any]):
            super().__init__(*args, **kwargs)
            self._http_client = MockHttpClient()

    mocker.patch.object(
        Request,
        "url",
        new_callable=mock.PropertyMock,
        return_value=URL(f"http://{request_url}/{project_name}/steps/transaction-step:{transaction_name}"),
    )
    mocker.patch("ansys.saf.glow._executor.transaction.Transaction", MockTransaction)

    run_method(project_fixture.client, url)


@pytest.mark.parametrize(
    ("method_name", "expected_final_status"),
    [
        ("download-x-upload-y", "completed"),
        ("long-running-download-x-upload-y", "completed"),
        ("raise-bad-request-error", "failed"),
        ("raise-bad-request-error-lr", "failed"),
    ],
)
def test_method_status_set_properly(method_name: str, expected_final_status: str, project_fixture: ProjectFixture):
    """Test that a transaction sets the method status correctly."""
    # Arrange
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:{method_name}"
    # Act
    project_fixture.client.post(url)
    status = project_fixture.client.get(url).json()["status"]
    tries = 0
    while status != expected_final_status and tries < 10:
        time.sleep(0.1)
        tries += 1
        status = project_fixture.client.get(url).json()["status"]

    # Assert
    assert project_fixture.client.get(url).json()["status"] == expected_final_status


@pytest.mark.parametrize(
    ("method_name", "inputs", "expected_result"),
    [
        ("input-str-or-none", {"my_input": "hello"}, "hello"),
        ("input-str-or-none", None, "None"),
        ("input-dict", {"my_input": {"a": "b", "c": {"d": "e"}}}, '{"a": "b", "c": {"d": "e"}}'),
        ("multiple-inputs", {"int_input": 1, "str_input": "string"}, '{"int_input": 1, "str_input": "string"}'),
        ("input-custom-model", {"my_input": {"x": 1, "y": 2, "z": 3}}, '{"x":1,"y":2,"z":3}'),
        ("input-str-with-default", {"my_input": "new_value"}, "new_value"),
        ("input-str-with-default", None, "default_value"),
    ],
)
def test_transaction_inputs(
    project_fixture: ProjectFixture,
    method_name: str,
    inputs: dict[str, Any],
    expected_result: Any,
):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:{method_name}"
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == ""
    # Act
    response = project_fixture.client.post(method_url, json=inputs)
    assert response.status_code == status.HTTP_200_OK
    # Assert
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == expected_result


def test_transaction_simple_input_wrong_type(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:input-str-or-none"
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == ""
    # Act
    response = project_fixture.client.post(method_url, json={"my_input": 1})
    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "Input should be a valid string" in response.json()["detail"][0]["msg"]


def test_transaction_dict_input_none_raise_error(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:input-dict"
    # Act
    response = project_fixture.client.post(method_url)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "The transaction method requires argument(s) but none was provided." in response.json()["detail"]


def test_transaction_wrong_input_raise_error(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:input-dict"
    # Act
    response = project_fixture.client.post(method_url, json={"random": "value"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    error_message = response.json()["detail"][0]
    assert error_message["type"] == "missing"
    assert error_message["msg"] == "Field required"
    assert error_message["loc"] == ["body", "my_input"]


def test_transaction_extra_wrong_input_raise_error(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:input-dict"
    # Act
    response = project_fixture.client.post(method_url, json={"my_input": {"hi": "hello"}, "random": "value"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    error_message = response.json()["detail"][0]
    assert error_message["type"] == "extra_forbidden"
    assert error_message["msg"] == "Extra inputs are not permitted"
    assert error_message["loc"] == ["body", "random"]


def test_transaction_field_input_with_field_max_length(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:input-str-with-field"
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == ""
    # Act
    response = project_fixture.client.post(method_url, json={"my_input": "hi"})
    # Assert
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == "hi"


def test_transaction_field_input_with_field_wrong_max_length(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:input-str-with-field"
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == ""
    # Act
    response = project_fixture.client.post(method_url, json={"my_input": "wrong_lenght"})
    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "String should have at most 5 characters" in response.json()["detail"][0]["msg"]


def test_transaction_unjsonable_input_raise_error():
    settings = Settings(glow_solution_definition="tests.mocks.solutions.method_param_wrong_type")

    with pytest.raises(
        SolutionLoadException,
        match="Invalid parameter types for the @transaction 'param_unjsonable'!"
        " Check that the parameters are valid pydantic field types.",
    ):
        create_app(settings)


def test_transaction_unjsonable_return_raise_error():
    settings = Settings(glow_solution_definition="tests.mocks.solutions.method_return_wrong_type")

    with pytest.raises(
        SolutionLoadException,
        match="Invalid return type for the @transaction 'return_unjsonable'!"
        " Check that the return type is a valid pydantic field types.",
    ):
        create_app(settings)


def test_transaction_input_long_running(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:input-str-long-running"
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == ""
    # Act
    response = project_fixture.client.post(method_url, json={"my_input": "hello"})
    assert response.status_code == status.HTTP_200_OK
    # Assert
    trial = 20
    while True:
        response = project_fixture.client.get(method_url)
        if trial == 0 or response.json()["status"] not in ["running", "run-required"]:
            break
        trial -= 1
        time.sleep(0.1)
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == "hello"


def test_transaction_input_with_other_step(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    other_step_url = f"{project_name}/steps/other-step"
    method_url = f"{step_url}:input-int-with-other-step"
    response = project_fixture.client.get(other_step_url)
    assert response.json()["x"] == 88
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == ""
    # Act
    response = project_fixture.client.post(method_url, json={"my_input": 10})
    response.raise_for_status()
    # Assert
    response = project_fixture.client.get(step_url)
    assert response.json()["inputs_as_json"] == "98"


@pytest.mark.parametrize(
    ("method_name", "expected_result"),
    [
        ("return-int", 10),
        ("return-dict", {"hello": "world"}),
        ("return-custom-model", {"x": 1, "y": 2, "z": 3}),
    ],
)
def test_transaction_return(project_fixture: ProjectFixture, method_name: str, expected_result: Any):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:{method_name}"
    # Act
    response = project_fixture.client.post(method_url)
    # Assert
    assert response.json() == expected_result


def test_transaction_return_input(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:return-input-str"
    # When: using string as input
    response = project_fixture.client.post(method_url, json={"my_input": "hello"})
    # then: the string is returned
    assert response.json() == "hello"

    # When: using None as input
    response = project_fixture.client.post(method_url)
    # None is returned
    assert response.json() is None


def test_transaction_return_long_running(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:return-long-running-int"
    # Act
    response = project_fixture.client.post(method_url)
    # Assert
    trial = 20
    while True:
        response = project_fixture.client.get(method_url)
        if trial == 0 or response.json()["status"] not in ["running", "run-required"]:
            break
        trial -= 1
        time.sleep(0.1)
    assert response.json()["result"] == 10


def test_transaction_return_input_long_running(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:return-input-str-long-running"
    # Act
    response = project_fixture.client.post(method_url, json={"my_input": "hello"})
    # Assert
    trial = 20
    while True:
        response = project_fixture.client.get(method_url)
        if trial == 0 or response.json()["status"] not in ["running", "run-required"]:
            break
        trial -= 1
        time.sleep(0.1)
    assert response.json()["result"] == "hello"


def test_transaction_input_parameters_not_saved_in_step(project_fixture: ProjectFixture):
    # Arrange
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:return-input-str"
    # given: the input parameter not part of the step fields
    response = project_fixture.client.get(step_url)
    assert "my_input" not in response.json()
    # when: executing the transaction with the input parameter
    response = project_fixture.client.post(method_url, json={"my_input": "hello"})
    # then: the input parameter is still not part of the step fields
    assert "my_input" not in response.json()


def test_transaction_input_parameters_not_saved_in_exported_project(project_fixture: ProjectFixture, tmp_path: Path):
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/transaction-step"
    method_url = f"{step_url}:return-input-str"
    # when: executing the transaction with the input parameter
    response = project_fixture.client.post(method_url, json={"my_input": "hello"})
    response = project_fixture.client.get(f"{project_name}:export")
    target = tmp_path / "archive"
    assert not target.exists()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(target)

    # then: the input parameter is not part of the exported data
    sap_file = target / "project.sap"
    assert "my_input" not in sap_file.read_text()


HPS_ONPREM_ERROR_MSG = "On-prem HPS authentication requires either token or username and password authentication."


class TestOnPremBearerToken:
    @pytest.fixture(autouse=True)
    def override_oidc_scheme(self, project_fixture: ProjectFixture):
        """Override oidc_scheme dependencies to avoid querying the oidc metadata server."""
        project_fixture.client.app.dependency_overrides[oidc_scheme] = OidcDependency("", "", auto_error=False)  # type: ignore
        yield
        # reset the overrides
        project_fixture.client.app.dependency_overrides = {}  # type: ignore

    @pytest.mark.parametrize(
        "settings",
        [
            {
                "glow_deployment": Deployment.DockerCompose,
                "glow_product_instance_system": ProductInstanceSystemType.HPS,
                "glow_product_instance_system_host": "localhost",
                "glow_product_instance_system_port": 8888,
                "glow_debug": "True",
                "glow_auth_disabled": "True",
                "glow_hps_client_id": "some_client_id",
                "glow_auth_issuer_url": "some_issuer_url",
            },
        ],
        indirect=["settings"],
    )
    def test_transaction_bearer_token_lk(self, mocker: MockerFixture, project_fixture: ProjectFixture):
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/transaction-step:create-hps-client"
        # WHEN: http request are sent by default without headers
        mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_username_from_access_token",
        )
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._request_action_token_url",
            return_value="https://fake_auth_url",
        )
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_access_and_refresh_tokens",
            return_value={"access_token": "fake_access_token", "refresh_token": "fake_refresh_token"},
        )
        response = project_fixture.client.post(url)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert HPS_ONPREM_ERROR_MSG in response.json()["detail"]
        mocked_hps_client.assert_not_called()
        # WHEN: http request are sent with Authorization headers
        response = project_fixture.client.post(url, headers={"Authorization": "Bearer faketoken"})
        # THEN: the hps client has been called with access_token
        assert response.json() == "ok"
        mocked_hps_client.assert_called_once_with(
            url="https://localhost:8888/hps",
            access_token="fake_access_token",
            refresh_token="fake_refresh_token",
        )

    @pytest.mark.parametrize(
        "settings",
        [
            {
                "glow_deployment": Deployment.DockerCompose,
                "glow_debug": "True",
                "glow_hps_client_id": "some_client_id",
                "glow_auth_issuer_url": "some_issuer_url",
            },
        ],
        indirect=["settings"],
    )
    def test_transaction_bearer_token_custom_hps_url(self, mocker: MockerFixture, project_fixture: ProjectFixture):
        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/transaction-step:create-hps-client-with-custom-hps-url"
        # WHEN: http request are sent by default without headers
        mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_username_from_access_token",
        )
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._request_action_token_url",
            return_value="https://fake_auth_url",
        )
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_access_and_refresh_tokens",
            return_value={"access_token": "fake_access_token", "refresh_token": "fake_refresh_token"},
        )
        response = project_fixture.client.post(url)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert HPS_ONPREM_ERROR_MSG in response.json()["detail"]
        mocked_hps_client.assert_not_called()
        # WHEN: http request are sent with Authorization headers
        response = project_fixture.client.post(url, headers={"Authorization": "Bearer faketoken"})
        # THEN: the hps client has been called with access_token and custom url
        assert response.json() == "ok"
        mocked_hps_client.assert_called_once_with(
            url="https://custom_url:1234/hps",
            access_token="fake_access_token",
            refresh_token="fake_refresh_token",
        )

    @pytest.mark.parametrize(
        "settings",
        [
            {
                "glow_deployment": Deployment.DockerCompose,
                "glow_debug": "True",
            },
        ],
        indirect=["settings"],
    )
    def test_transaction_bearer_token_raise_event(self, mocker: MockerFixture, project_fixture: ProjectFixture):
        captured_auth_headers: list[str | None] = []

        class MockHttpClient:
            def __init__(self, http_client: httpx2.Client):
                self._http_client = http_client

            def post(self, *args: Any, **kwargs: dict[str, Any]) -> None:
                captured_auth_headers.append(self._http_client.headers.get("Authorization", None))

        class MockTransaction(Transaction):
            def __init__(self, *args: Any, **kwargs: dict[str, Any]):
                super().__init__(*args, **kwargs)
                self._http_client = MockHttpClient(self._http_client)  # type: ignore

        project_name = project_fixture.properties["name"]
        url = f"{project_name}/steps/transaction-step:raise-event"

        mocker.patch("ansys.saf.glow._executor.transaction.Transaction", MockTransaction)

        # WHEN: transaction http request is sent without headers
        response = project_fixture.client.post(url)
        assert response.status_code == status.HTTP_200_OK
        # THEN: the request to the store_event route is done with a http client that has no Authorization header
        assert len(captured_auth_headers) == 1
        assert captured_auth_headers[0] is None

        # WHEN: transaction http request is sent with authorization header
        response = project_fixture.client.post(url, headers={"Authorization": "Bearer faketoken"})
        assert response.status_code == status.HTTP_200_OK
        # THEN: the Authorization header is propagated and used by the client that does the request to the store_event
        assert len(captured_auth_headers) == 2
        assert captured_auth_headers[1] == "Bearer faketoken"


def test_transaction_custom_hps_params(
    mocker: MockerFixture,
    project_fixture: ProjectFixture,
):
    project_name = project_fixture.properties["name"]
    url = f"{project_name}/steps/transaction-step:create-hps-client-with-custom-params"
    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    mocker.patch(
        "ansys.saf.glow._server.routers.desktop.HpsInteractiveAuthenticator.check_token_validity",
        return_value=False,
    )
    mocked_interactive_auth = mocker.patch(
        "ansys.saf.glow._server.routers.desktop.HpsInteractiveAuthenticator.acquire_token",
        return_value=("fake_access", "fake_refresh"),
    )
    # WHEN: creating an HPS client with all custom HPS auth params
    response = project_fixture.client.post(url)
    assert response.status_code == status.HTTP_200_OK
    # THEN: the HPS Client is called with the right params
    mocked_hps_client.assert_called_once_with(
        url="https://custom_host:1234/hps",
        client_id="custom_client",
        refresh_token="fake_refresh",
    )
    # THEN: the HPS interactive authenticator is called with the right params
    mocked_interactive_auth.assert_called_once_with(
        hps_server_url="https://custom_host:1234/hps",
        client_id="custom_client",
    )
