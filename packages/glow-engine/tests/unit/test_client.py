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

import os
import re
import sys
from typing import Any
from unittest import mock

import httpx2
import pytest
from pytest_mock.plugin import MockerFixture

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution.hps import HpsParametricStudyProject, HpsSimpleProject
from tests.mocks.solutions.minimal_solution import MinimalSolution
from tests.mocks.solutions.transactions import TransactionsSolution

VALID_API_URLS = [
    "http://127.0.0.1:5432",
    "http://127.0.0.1:5432/my_application",
    "http://127.0.0.1:5432/my_application/",
    "https://127.0.0.1:5432",
]
VALID_WS_ENDPOINT_ADDRS = [
    "ws://127.0.0.1:5432",
    "ws://127.0.0.1:5432/my_application",
    "ws://127.0.0.1:5432/my_application/",
    "wss://127.0.0.1:5432",
]


@pytest.fixture(autouse=True)
def clean_env():
    # Tests here instantiate the GLOW Dash/Client, which internally modifies the sys.path/sys.modules and
    # sets environment variables such as GLOW_DEPLOYMENT, _API_URL... Clean it up between tests
    old_paths = sys.path.copy()
    with mock.patch.dict(os.environ, os.environ.copy()):
        yield
    sys.path = old_paths


def test_get_field(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture):
    client = Client(MinimalSolution, "http://127.0.0.1:5432")
    project = client.get_project("projects/my_project_id")
    step = project.steps.minimal_step
    expected_result = 101
    mocked_get_request = mocker.patch.object(
        httpx2.Client,
        "get",
        return_value=httpx2.Response(
            200,
            json={"x": expected_result},
        ),
    )

    # WHEN - a field value is requested from a step via the client
    returned_value = step.x

    # THEN - the client should make a get request to the correct url with a field filter
    mocked_get_request.assert_called_once_with(
        "http://127.0.0.1:5432/projects/my_project_id/steps/minimal-step",
        params={"fields": "x"},
    )

    # AND - the returned value should be the expected result
    assert returned_value == expected_result


@pytest.mark.parametrize(
    ("field_name", "server_value", "collection_key", "project_type"),
    [
        (
            "simple_projects",
            [{"hps_project_identifier": "simple-project"}],
            0,
            HpsSimpleProject,
        ),
        (
            "study_projects",
            [{"hps_project_identifier": "study-project"}],
            0,
            HpsParametricStudyProject,
        ),
        (
            "simple_projects_by_name",
            {"project_1": {"hps_project_identifier": "simple-project"}},
            "project_1",
            HpsSimpleProject,
        ),
        (
            "study_projects_by_name",
            {"project_1": {"hps_project_identifier": "study-project"}},
            "project_1",
            HpsParametricStudyProject,
        ),
    ],
)
def test_get_hps_project_collection_field(
    mocker: MockerFixture,
    field_name: str,
    server_value: list[dict[str, str]] | dict[str, dict[str, str]],
    collection_key: int | str,
    project_type: type[HpsSimpleProject] | type[HpsParametricStudyProject],
):
    client = Client(TransactionsSolution, "http://127.0.0.1:5432")
    step = client.get_project("projects/my_project_id").steps.transaction_step
    mocker.patch.object(
        httpx2.Client,
        "get",
        return_value=httpx2.Response(200, json={field_name: server_value}),
    )

    collection = getattr(step, field_name)
    project = collection[collection_key]

    assert isinstance(project, project_type)
    assert project.hps_project_identifier in ("simple-project", "study-project")


@pytest.mark.parametrize(
    ("field_name", "server_value", "collection_key", "project_type"),
    [
        (
            "simple_projects",
            [{"hps_project_identifier": "simple-project"}],
            0,
            HpsSimpleProject,
        ),
        (
            "study_projects",
            [{"hps_project_identifier": "study-project"}],
            0,
            HpsParametricStudyProject,
        ),
        (
            "simple_projects_by_name",
            {"project_1": {"hps_project_identifier": "simple-project"}},
            "project_1",
            HpsSimpleProject,
        ),
        (
            "study_projects_by_name",
            {"project_1": {"hps_project_identifier": "study-project"}},
            "project_1",
            HpsParametricStudyProject,
        ),
    ],
)
def test_get_fields_returns_hps_project_collections(
    mocker: MockerFixture,
    field_name: str,
    server_value: list[dict[str, str]] | dict[str, dict[str, str]],
    collection_key: int | str,
    project_type: type[HpsSimpleProject] | type[HpsParametricStudyProject],
):
    client = Client(TransactionsSolution, "http://127.0.0.1:5432")
    step = client.get_project("projects/my_project_id").steps.transaction_step
    mocker.patch.object(
        httpx2.Client,
        "get",
        return_value=httpx2.Response(200, json={field_name: server_value}),
    )

    collection = step.get_fields([field_name])[field_name]
    project = collection[collection_key]

    assert isinstance(project, project_type)
    assert project.hps_project_identifier in ("simple-project", "study-project")


@pytest.mark.parametrize(
    ("fields"),
    ([["x", "name", "users", "my_list_of_tuple"], [], None]),
)
def test_get_fields(mocker: MockerFixture, fields: list[str]):
    client = Client(MinimalSolution, "http://127.0.0.1:5432")
    project = client.get_project("projects/my_project_id")
    step = project.steps.minimal_step
    p = mocker.patch("ansys.saf.glow._client.project_proxy.StepProxy.to_dict")
    step.get_fields(fields)
    p.assert_called_once_with(fields)


@pytest.mark.parametrize(("fields"), ([["wrong_field"], ["dont_change_x"]]))
def test_get_wrong_field(fields: list[str]):
    client = Client(MinimalSolution, "http://127.0.0.1:5432")
    project = client.get_project("projects/my_project_id")
    step = project.steps.minimal_step
    error_msg = f"At least one of the provided field names is not a '{step}' step field.\nAvailable fields are: "
    with pytest.raises(AttributeError, match=error_msg):
        step.get_fields(fields)


@pytest.mark.parametrize(("fields"), ([{"x": 1, "name": "new name", "value": 3}, {"value": 3}, {}]))
def test_set_fields(mocker: MockerFixture, fields: dict[str, Any]):
    client = Client(MinimalSolution, "http://127.0.0.1:5432")
    project = client.get_project("projects/my_project_id")
    step = project.steps.minimal_step
    p = mocker.patch("ansys.saf.glow._client.project_proxy.StepProxy.from_dict")
    step.set_fields(fields)
    p.assert_called_once_with(fields)


def test_set_wrong_field():
    client = Client(MinimalSolution, "http://127.0.0.1:5432")
    project = client.get_project("projects/my_project_id")
    step = project.steps.minimal_step
    with pytest.raises(
        AttributeError,
        match=re.escape(f"'{step}' has no field(s) 'wrong_field, another_wrong_field'."),
    ):
        step.set_fields({"wrong_field": 1, "another_wrong_field": 2})
    with pytest.raises(AttributeError, match=re.escape(f"'{step}' has no field(s) 'wrong_field'.")):
        step.wrong_field = 1  # pyright: ignore[reportAttributeAccessIssue]


def test_set_multiple_fields_with_invalid_attribute():
    client = Client(MinimalSolution, "http://127.0.0.1:5432")
    project = client.get_project("projects/my_project_id")
    step = project.steps.minimal_step
    with pytest.raises(AttributeError, match=re.escape(f"'{step}' has no field(s) 'wrong_field'.")):
        step.set_fields({"x": 1, "wrong_field": 2})


@pytest.mark.parametrize("external_url", [None, "http://api.my_solution"])
def test_get_entity_url_uses_external_url(external_url: str | None):
    expected_external_url = external_url if external_url is not None else "http://127.0.0.1:5432"
    client = Client(MinimalSolution, "http://127.0.0.1:5432", external_url=external_url)
    project = client.get_project("projects/my_project_id")
    step = project.steps.minimal_step
    expected_entity_url = f"{expected_external_url}/projects/my_project_id/steps/minimal-step/blobs/file-entity"
    assert step.get_entity_url("file_entity") == expected_entity_url


@pytest.mark.parametrize("deployment", [None, "Desktop", "DockerCompose"])
def test_hps_authentication_calls_endpoint_only_in_desktop(
    deployment: str | None,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    if not deployment:
        monkeypatch.delenv("GLOW_DEPLOYMENT", raising=False)
    else:
        monkeypatch.setenv("GLOW_DEPLOYMENT", deployment)
    client = Client(MinimalSolution, "http://127.0.0.1:5432")
    project = client.get_project("projects/my_project_id")
    mocked_auth_get_request = mocker.patch.object(
        httpx2.Client,
        "get",
        return_value=httpx2.Response(
            200,
            json={"access_token": "test_access", "refresh_token": "test_refresh"},
            request=httpx2.Request("GET", "/"),
        ),
    )
    project.authenticate_hps()
    if deployment == "DockerCompose":
        mocked_auth_get_request.assert_not_called()
    else:
        mocked_auth_get_request.assert_called_once_with(
            "http://127.0.0.1:5432/desktop:hps-auth-info",
            params={},
        )


def test_hps_authentication_calls_endpoint_with_custom_hps_params_header(
    mocker: MockerFixture,
):
    client = Client(MinimalSolution, "http://127.0.0.1:5432")
    project = client.get_project("projects/my_project_id")
    mocked_auth_get_request = mocker.patch.object(
        httpx2.Client,
        "get",
        return_value=httpx2.Response(
            200,
            request=httpx2.Request("GET", "/"),
        ),
    )
    project.authenticate_hps(
        hps_server_url="test_url",
        client_id="test_client",
    )
    mocked_auth_get_request.assert_called_once_with(
        "http://127.0.0.1:5432/desktop:hps-auth-info",
        params={
            "hps_server_url": "test_url",
            "client_id": "test_client",
        },
    )
