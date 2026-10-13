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

from typing import TypeVar

import pytest

from ansys.saf.glow.solution import Solution
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DefaultLoggingConfig,
    EnvVarLoggingConfig,
    GlowBaseProcess,
    LoggingConfiguration,
)
from tests.e2e.conftest import STEPS_WITH_LOGGING_METHODS
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    LOGGING_ERROR_TESTING_STRING,
    LOGGING_INFO_TESTING_STRING,
)

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_ui,
    pytest.mark.parametrize("ui_enabled", [True], indirect=True),
    pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    ),
]

T = TypeVar("T", bound=Solution)


@pytest.fixture(scope="class", autouse=True)
def logging_configuration(
    session_glow: GlowBaseProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    """Sets up the logging configuration. Needs to be indirectly parametrized"""
    return session_glow.change_configuration(request.param)


@pytest.fixture(autouse=True, scope="module")
def module_setup_and_cleanup(session_glow: GlowBaseProcess[EndToEndSolution]):
    """Reset the logging configuration to default."""
    yield None
    session_glow.configure_default_execution()


@pytest.fixture
def normal_content(logging_configuration: LoggingConfiguration) -> dict[str, str]:
    normal_content = {
        DefaultLoggingConfig: {
            "api": "Using default logging config for GLOW API",
            "ui": "Using default logging config for GLOW UI",
        },
        EnvVarLoggingConfig: {
            "api": "Applied user logging configuration for GLOW API",
            "ui": "Applied user logging configuration for GLOW UI",
        },
    }

    return normal_content[type(logging_configuration)]  # type: ignore


@pytest.mark.parametrize("logging_configuration", [DefaultLoggingConfig, EnvVarLoggingConfig], indirect=True)
class TestLoggingConfigurations:
    def test_container_normal_content(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        normal_content: dict[str, str],
        logging_configuration: LoggingConfiguration,
    ):
        """
        Test that expected INFO messages show up on each log service on startup.
        """
        session_glow.restart()
        for service, content in normal_content.items():
            assert session_glow.text_in_output([content], service=service)

    @pytest.mark.usefixtures("log_something")
    def test_log_content(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        logging_configuration: LoggingConfiguration,
    ):
        """
        Logging INFO/ERROR messages show up on the log appropriately. Each Step logger writes to one file.
        """

        for step in STEPS_WITH_LOGGING_METHODS.values():
            assert session_glow.text_in_output([step, logging_configuration.tag, LOGGING_ERROR_TESTING_STRING])
            assert session_glow.text_in_output([step, logging_configuration.tag, LOGGING_INFO_TESTING_STRING])
