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

import sys
from unittest.mock import ANY, MagicMock

from fastapi import status
import pytest
import pytest_mock

from ansys.iam.oidc import OidcClient, UserInfo
from ansys.saf.glow._bdm.datarepo import DataRepositoryType
from ansys.saf.glow._config.const import GLOW_DATA_REPOSITORY_TYPE
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._server.exceptions import INTERNAL_ERROR_MESSAGE
import tests.mocks.solutions.data_repository as data_repository_solution
from tests.unit.routes.conftest import ProjectFixture

solution = data_repository_solution

pytestmark = pytest.mark.parametrize(
    "mock_module_settings",
    [{"glow_data_repository_type": DataRepositoryType.Minerva}],
    ids=["Minerva"],
    indirect=True,
)


@pytest.fixture
def mock_minerva_client(mocker: pytest_mock.MockerFixture):
    mock_module = MagicMock()
    minerva_client = MagicMock()
    mock_module.client.MinervaClient = minerva_client
    mocker.patch.dict(
        sys.modules,
        {
            "ansys.minerva_python_client": mock_module,
            "ansys.minerva_python_client.client": mock_module.client,
        },
    )
    return minerva_client


@pytest.fixture(autouse=True)
def data_repo_type(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_DATA_REPOSITORY_TYPE, DataRepositoryType.Minerva.value)


@pytest.fixture(autouse=True)
def oidc_client(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(OidcClient, "get_user_info", return_value=UserInfo(preferred_username="test"))


@pytest.fixture
def step_url(project_fixture: ProjectFixture) -> str:
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/data-repository-step"
    return step_url


def test_impersonation_used_when_request_contains_auth_header(
    project_fixture: ProjectFixture,
    step_url: str,
    mock_minerva_client: MagicMock,
):
    project_fixture.client.post(f"{step_url}:upload-blob-to-data-repo", headers={"Authorization": "Bearer fake_jwt"})
    mock_minerva_client.assert_called_with(impersonated_user="test", working_dir=ANY)


def test_impersonation_not_used_when_request_contains_no_auth_header(
    project_fixture: ProjectFixture,
    step_url: str,
    mock_minerva_client: MagicMock,
):
    project_fixture.client.post(f"{step_url}:upload-blob-to-data-repo")
    mock_minerva_client.assert_called_with(impersonated_user=None, working_dir=ANY)


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_using_minerva_as_data_repo_without_minerva_python_client_installed_raises_error(
    project_fixture: ProjectFixture,
    step_url: str,
    settings: Settings,
):
    response = project_fixture.client.post(f"{step_url}:upload-blob-to-data-repo")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    error_message = (
        "ImportError: The ansys-minerva-python-client package is required to use Minerva as a data repository."
        if settings.glow_debug
        else INTERNAL_ERROR_MESSAGE
    )
    assert error_message in response.json()["detail"]
