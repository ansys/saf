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

import pytest

from ansys.saf.glow.client import BadRequestException
from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.solution.end_to_end import GlowDesktopProcess, ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


def test_instance_not_initialized(
    session_glow: GlowDesktopProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
):
    """
    Test that GLOW raises the appropriate exception when a instance-decorated method is run before its corresponding
    create_instance-decorated method.
    """
    with pytest.raises(BadRequestException, match="The method has been called out of sequence."):
        function_project.project.steps.custom_http_shared_instance_step.retrieve_value_custom_http_product_instance()

    assert session_glow.text_in_output("The method has been called out of sequence.", "api")


def test_instance_not_initialized_long_running(
    session_glow: GlowDesktopProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
):
    """
    Test that GLOW raises the appropriate exception when a instance-decorated long_running method is run before its
    corresponding create_instance-decorated method.
    """
    lr_method = (
        function_project.project.steps.custom_http_shared_instance_step.retrieve_http_product_value_and_kill_instance()
    )
    with pytest.raises(BadRequestException, match="The method has been called out of sequence."):
        lr_method.wait()
    assert lr_method.get_state().status == MethodStatus.Failed  # type: ignore

    assert session_glow.text_in_output("ERROR [ansys.saf.glow._executor.method_runner]")

    expected_exception = (
        "The method has been called out of sequence. "
        "A shared product instance that this method uses has not been initialized."
    )
    assert session_glow.text_in_output(expected_exception)
