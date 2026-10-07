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

import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.parametric_studies_step import ParametricStudiesStep

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
]


@retry(
    stop=stop_after_attempt(150),
    wait=wait_fixed(1),
)
def wait_for_hps_parametric_study_to_finish(parametric_step: ParametricStudiesStep) -> None:
    parametric_step.query_parametric_study()
    if parametric_step.number_left != 0:
        raise TryAgain


@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestHpsParametricStudy:
    def test_simple_parametric_study(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        get_available_application_on_hps: Callable[[str], str],
    ):
        """
        Test that GLOW's HPS API can be used to submit jobs involving a python product scripts.
        Also test that GLOW's HPS API design point selection capabilities are working.
        (here we explicitly use `Software(Python)` instead of the sugar API with the `python_version` arg
        because we want to mimic the case where another product is installed and is required by the script.)
        """
        step = function_class_project.project.steps.parametric_studies_step
        python_version = get_available_application_on_hps("Python")
        step.start_parametric_study(python_version=python_version)
        wait_for_hps_parametric_study_to_finish(step)
        assert step.result == ["8.0", "10.0", "12.0", "14.0", "16.0", "18.0"]
        assert [str(value) for value in step.fetch_result_values()] == step.result
