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

from collections.abc import Callable
from pathlib import Path

import pytest

from ansys.saf.glow.client import Client, PermissionException, UnauthorizedException
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    EnableAuthValidationConfiguration,
    GlowBaseProcess,
)
from tests.e2e.conftest import GlowApiKeyConfiguration, SetGlowApiKeyConfiguration, SetGlowApiKeyFileConfiguration
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    ),
]


@pytest.fixture(scope="module", autouse=True)
def authenticated_solution(
    session_glow: GlowBaseProcess[EndToEndSolution],
    session_idp_mock_server: str,
    deployment_type: TestDeployment,
) -> YieldFixture[None]:
    idp_server_url = session_idp_mock_server
    if deployment_type == TestDeployment.DockerCompose:
        idp_server_url = idp_server_url.replace("localhost", "host.docker.internal")
    session_glow.change_configuration(EnableAuthValidationConfiguration, idp_server=idp_server_url)
    yield
    session_glow.configure_default_execution()


@pytest.mark.parametrize("from_file", [False, True], ids=["api_key_from_env_var", "api_key_from_file_env_var"])
def test_glow_client_using_api_key(
    deployment_type: TestDeployment,
    session_glow: GlowBaseProcess[EndToEndSolution],
    get_glow_client: Callable[[GlowBaseProcess[EndToEndSolution], str | None], Client[EndToEndSolution]],
    existing_project: EndToEndSolution,
    from_file: bool,
    tmp_path: Path,
):
    """Test that authentication at API server can be bypassed using an API key only for local requests.

    API key can be provided either directly as an environment variable or through a file whose path is set
    in an environment variable."""

    if "api_key" in session_glow.applied_configurations:
        # cleanup between parametrization of the same test. since API key is configured in the middle,
        # we need to reset the configuration to avoid it being applied for the first part of the test
        # in the next iteration.
        session_glow.change_configuration(GlowApiKeyConfiguration)

    api_key = "my-mock-api-key"

    with get_glow_client(session_glow, None) as unauthenticated_client:  # noqa: SIM117
        with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
            _ = unauthenticated_client.get_project(existing_project.project_name).project_display_name
    with (
        Client(
            session_glow.solution_type,
            session_glow.base_api_url,
            api_key=api_key,
        ) as client_with_api_key,
        pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"),
    ):
        _ = client_with_api_key.get_project(existing_project.project_name).project_display_name

    if from_file:
        api_key_file = tmp_path / "api_key_file.txt"
        api_key_file.write_text(api_key)
        session_glow.change_configuration(SetGlowApiKeyFileConfiguration, api_key_file=api_key_file)
    else:
        session_glow.change_configuration(SetGlowApiKeyConfiguration, api_key=api_key)

    with get_glow_client(session_glow, None) as unauthenticated_client:  # noqa: SIM117
        with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
            _ = unauthenticated_client.get_project(existing_project.project_name).project_display_name

    with Client(session_glow.solution_type, session_glow.base_api_url, api_key=api_key) as client_with_api_key:
        if deployment_type == TestDeployment.DockerCompose:
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                _ = client_with_api_key.get_project(existing_project.project_name).project_display_name
        else:
            assert (
                client_with_api_key.get_project(existing_project.project_name).project_display_name
                == existing_project.project_display_name
            )
