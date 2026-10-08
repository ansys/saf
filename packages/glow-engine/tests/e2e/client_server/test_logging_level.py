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

from collections.abc import Generator

import pytest

from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DefaultLogLevel,
    EnvVarDebugLogLevel,
    EnvVarErrorLogLevelWithDebugMode,
    GlowBaseProcess,
    LogLevelConfiguration,
    ProjectFixture,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    LOGGING_DEBUG_TESTING_STRING,
)

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


@pytest.fixture(scope="class", autouse=True)
def log_level(
    session_glow: GlowBaseProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param)


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    "Need to return session_glow back to the default state."
    yield
    session_glow.configure_default_execution()


@pytest.mark.parametrize(
    "log_level",
    [
        DefaultLogLevel,
        EnvVarDebugLogLevel,
        EnvVarErrorLogLevelWithDebugMode,
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestLogLevel:
    def test_method_log_message(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
        log_level: LogLevelConfiguration,
    ):
        """
        Test that the method log level can be set below INFO.
        """

        function_project.project.steps.transaction_verification_step.log_some_debug()

        if log_level.log_level == "DEBUG" or log_level.debug:
            assert session_glow.text_in_output(LOGGING_DEBUG_TESTING_STRING)
        else:
            assert not session_glow.text_in_output(LOGGING_DEBUG_TESTING_STRING)

    def test_api_log_message(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        log_level: LogLevelConfiguration,
    ):
        """
        Test that normal DEBUG log level content is found in the API logs.
        """
        # do something that we know it triggers a debug message
        function_project.project.steps.transaction_verification_step.field_1 = 3
        normal_debug_content = "Invalidating descendant fields..."

        if log_level.log_level == "DEBUG" or log_level.debug:
            assert session_glow.text_in_output(normal_debug_content)
        else:
            assert not session_glow.text_in_output(normal_debug_content)
