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
from typing import TypeVar

import pytest

from ansys.saf.glow.solution import Solution
from ansys.saf.testing.solution.end_to_end import (
    EnvVarDebugLogLevel,
    GlowBaseProcess,
    ProjectFixture,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    ),
]

T = TypeVar("T", bound=Solution)


@pytest.fixture(scope="class")
def set_logging_level_to_debug(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    session_glow.change_configuration(EnvVarDebugLogLevel)
    yield
    session_glow.configure_default_execution()


@pytest.mark.usefixtures("set_logging_level_to_debug")
class TestTransactionEventLoggingWithoutUI:
    def test_triggering_event_log_indicates_event_row_removal(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """
        Test that when trigger an event the logs show that there are no events in the repository
        before the project is deleted which indicates that the event handling is properly
        removing events from the repository
        """

        # WHEN: when publishing an event from a transaction method without any clients connected
        function_project.project.steps.transaction_verification_step.trigger_event()

        # THEN: check there are no events in repository
        assert session_glow.text_in_output("Event row count reduced to 0")
