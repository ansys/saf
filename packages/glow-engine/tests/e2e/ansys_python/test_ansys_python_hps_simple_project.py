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
import time

import pytest

from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_ansys_python,
]


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestHpsSimpleProject:
    def test_hps_job_using_ansys_python(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        get_available_application_on_hps: Callable[[str], str],
    ):
        """
        Test that HPS is able to run jobs using Ansys Python and a BDM script.
        """
        ansys_python_version = get_available_application_on_hps("Ansys Python")

        step = function_project.project.steps.hps_simple_project_step
        step.start_job_using_ansys_python_and_bdm(ansys_python_version=ansys_python_version)
        step.query_hps()
        attempts = 1

        while step.python_name is None and attempts < 28:
            time.sleep(2.5)
            step.query_hps()
            attempts += 1

        assert step.python_name == "Ansys Python"
        assert step.python_version
        assert step.python_version.replace("_", ".") == ansys_python_version
