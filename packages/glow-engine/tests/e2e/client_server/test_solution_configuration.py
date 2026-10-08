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

from collections.abc import Callable, Generator
from pathlib import Path

import httpx2
import pytest

from ansys.saf.glow._crud.solution_configuration_models import GLOW_SCHEMA_VERSION
from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import SolutionConfiguration
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.mocks.solutions.extended_solution_configuration_not_defined import NotDefinedSolutionConfigurationSolution
from tests.mocks.solutions.extended_solution_configuration_not_used import NotUsedSolutionConfigurationSolution
from tests.mocks.solutions.solution_configuration import SolutionConfigurationSolution

pytestmark = pytest.mark.parametrize("solution_type", [SolutionConfigurationSolution], indirect=True)


@pytest.fixture
def set_default_solution_configuration(
    session_glow: GlowBaseProcess[SolutionConfigurationSolution],
) -> Generator[None, None, None]:
    httpx2.put(
        f"{session_glow.base_api_url}/solution-configuration",
        json=SolutionConfiguration().model_dump(),
    ).raise_for_status()
    yield
    httpx2.put(
        f"{session_glow.base_api_url}/solution-configuration",
        json=SolutionConfiguration().model_dump(),
    ).raise_for_status()


class TestSolutionConfiguration:
    @pytest.mark.usefixtures("set_default_solution_configuration")
    def test_solution_config_read_using_rest_api(
        self,
        session_glow: GlowBaseProcess[SolutionConfigurationSolution],
    ):
        """Test that the solution configuration can be read using REST API."""
        response = httpx2.get(f"{session_glow.base_api_url}/solution-configuration")
        response.raise_for_status()
        assert response.json() == SolutionConfiguration().model_dump()

    @pytest.mark.usefixtures("set_default_solution_configuration")
    @pytest.mark.parametrize("long_running", [False, True])
    def test_read_solution_config_from_within_transaction(
        self,
        function_project: ProjectFixture[SolutionConfigurationSolution],
        long_running: bool,
    ):
        """Test that the solution configuration can be accessed within a transaction when the feature is enabled
        (i.e., the environment variable is set). The returned solution configuration is properly typed.
        """
        step = function_project.project.steps.solution_configuration_step

        if long_running:
            transaction_output = step.read_solution_configuration_lr().wait()
        else:
            transaction_output = step.read_solution_configuration()
        assert transaction_output == "SolutionConfiguration"

    @pytest.mark.usefixtures("set_default_solution_configuration")
    def test_read_solution_config_from_client(
        self,
        function_project: ProjectFixture[SolutionConfigurationSolution],
    ):
        """Test that the solution configuration can be accessed from the client when the feature is enabled
        (i.e., the environment variable is set). The returned solution configuration is properly typed.
        """
        assert function_project.project.solution_configuration.__class__.__name__ == "SolutionConfiguration"
        assert function_project.project.solution_configuration == SolutionConfiguration()
        # just to check that type hints are correct
        assert function_project.project.solution_configuration.glow_schema_version == GLOW_SCHEMA_VERSION

    @pytest.mark.usefixtures("set_default_solution_configuration")
    def test_solution_config_schema_read(
        self,
        session_glow: GlowBaseProcess[SolutionConfigurationSolution],
    ):
        """Test that the solution configuration schema can be retrieved using the REST API."""
        expected_schema = SolutionConfiguration.model_json_schema()
        response = httpx2.get(f"{session_glow.base_api_url}/solution-configuration/schema")
        response.raise_for_status()
        assert response.json() == expected_schema


class TestNoSolutionConfiguration:
    def test_solution_config_routes_without_defining_field(
        self,
        run_glow: Callable[
            [type[NotUsedSolutionConfigurationSolution], Path],
            GlowBaseProcess[NotUsedSolutionConfigurationSolution],
        ],
        tmp_solutions_dir: dict[type[NotUsedSolutionConfigurationSolution], Path],
    ):
        """Test that the solution configuration REST API routes are not accessible when the feature is not enabled."""
        glow_proc = run_glow(
            NotUsedSolutionConfigurationSolution,
            tmp_solutions_dir[NotUsedSolutionConfigurationSolution],
        )
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            httpx2.get(f"{glow_proc.base_api_url}/solution-configuration").raise_for_status()
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            httpx2.put(f"{glow_proc.base_api_url}/solution-configuration").raise_for_status()
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            httpx2.get(f"{glow_proc.base_api_url}/solution-configuration/schema").raise_for_status()

    def test_read_solution_config_from_within_transaction_without_defining_field(
        self,
        run_glow: Callable[
            [type[NotDefinedSolutionConfigurationSolution], Path],
            GlowBaseProcess[NotDefinedSolutionConfigurationSolution],
        ],
        tmp_solutions_dir: dict[type[NotDefinedSolutionConfigurationSolution], Path],
    ):
        """Test that trying to launch a Solution that reads the solution configuration within a transaction when the
        feature is not enabled raises an exception with the expected error message.
        """
        glow_proc = run_glow(
            NotDefinedSolutionConfigurationSolution,
            tmp_solutions_dir[NotDefinedSolutionConfigurationSolution],
        )
        assert not glow_proc.healthy
        error_msg = (
            "The solution configuration type used in the transactions is not the one defined in the Solution's "
            "solution_configuration field."
        )
        assert glow_proc.text_in_output(error_msg, "api")

    def test_read_solution_config_from_client_without_defining_field(
        self,
        run_glow: Callable[
            [type[NotUsedSolutionConfigurationSolution], Path],
            GlowBaseProcess[NotUsedSolutionConfigurationSolution],
        ],
        get_glow_client: Callable[
            [GlowBaseProcess[NotUsedSolutionConfigurationSolution]],
            Client[NotUsedSolutionConfigurationSolution],
        ],
        tmp_solutions_dir: dict[type[NotUsedSolutionConfigurationSolution], Path],
    ):
        """Test that trying to read the solution configuration in the Client API when the feature is not enabled
        raises an exception with the expected error message.
        """
        glow_proc = run_glow(
            NotUsedSolutionConfigurationSolution,
            tmp_solutions_dir[NotUsedSolutionConfigurationSolution],
        )
        glow_client = get_glow_client(glow_proc)
        project = glow_client.create_project("test project")
        with pytest.raises(RuntimeError, match="The solution does not have solution_configuration field defined."):
            project.solution_configuration  # type: ignore  # noqa: B018
