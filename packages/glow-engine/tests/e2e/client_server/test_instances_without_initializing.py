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

import httpx2
import pytest

from ansys.saf.glow.client import BadRequestException
from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solutions.method_step_using_instance_without_initializing import (
    InstanceMethodWithoutInitializationSolution,
)

pytestmark = pytest.mark.parametrize("solution_type", [InstanceMethodWithoutInitializationSolution], indirect=True)

expected_error_message = (
    "The method has been called out of sequence. "
    "A shared product instance that this method uses has not been initialized."
)


@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
class TestInstancesWithoutInit:
    def test_instance_method_without_initializing(
        self,
        function_project: ProjectFixture[InstanceMethodWithoutInitializationSolution],
    ):
        step = function_project.project.steps.my_step

        with pytest.raises(
            BadRequestException,
            match=expected_error_message,
        ):
            step.use_instance()

    def test_invoking_instance_method_without_initializing_returns_400_code(
        self,
        function_project: ProjectFixture[InstanceMethodWithoutInitializationSolution],
    ):
        method_url = f"{function_project.project.url}/steps/my-step:use-instance"
        response = httpx2.post(method_url, timeout=10)
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert isinstance(detail, str)
        assert detail.startswith(expected_error_message)

    def test_long_running_instance_method_without_initializing(
        self,
        function_project: ProjectFixture[InstanceMethodWithoutInitializationSolution],
    ):
        step = function_project.project.steps.my_step
        long_running = step.use_instance_with_long_running()
        with pytest.raises(BadRequestException, match=expected_error_message):
            long_running.wait()
        state = step.get_long_running_method_state("use_instance_with_long_running")
        assert state.status == MethodStatus.Failed
        assert expected_error_message in state.exception_message  # type: ignore
