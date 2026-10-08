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

import importlib.metadata

import httpx2
import pytest

from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess
from tests.e2e.conftest import SetExternalApiUrlConfiguration
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    ),
]


def test_root_route_returns_server_info(
    session_glow: GlowBaseProcess[EndToEndSolution],
    deployment_type: TestDeployment,
):
    """Test that the root route returns basic server info, including external_api_url."""
    response = httpx2.get(f"{session_glow.base_api_url}/")
    assert response.status_code == 200
    server_info = response.json()
    assert server_info["solution"]["name"] == "EndToEndSolution"
    assert server_info["solution"]["display_name"] == "End-to-end solution"
    assert server_info["solution"]["schema_version"] == 1
    assert server_info["glow_version"] == importlib.metadata.version("ansys-saf-glow-engine")
    assert server_info["external_api_url"] == (  # when unconfigured, defaults to glow_api_host+glow_api_port
        session_glow.base_api_url if deployment_type == TestDeployment.Desktop else "http://0.0.0.0:50000"
    )


@pytest.fixture
def configure_external_api_url(session_glow: GlowBaseProcess[EndToEndSolution]) -> YieldFixture[None]:
    session_glow.change_configuration(SetExternalApiUrlConfiguration, external_api_url="https://my.external.url:1234")
    yield
    session_glow.configure_default_execution()


@pytest.mark.usefixtures("configure_external_api_url")
def test_root_route_exposes_external_api_url_derived_from_settings(session_glow: GlowBaseProcess[EndToEndSolution]):
    """Test that the root route reports an external_api_url matching the configured value in the env var."""
    response = httpx2.get(f"{session_glow.base_api_url}/")
    assert response.status_code == 200
    server_info = response.json()
    assert server_info["external_api_url"] == "https://my.external.url:1234"
