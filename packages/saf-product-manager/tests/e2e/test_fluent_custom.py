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
from typing import TYPE_CHECKING

import pytest

from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.testing.hps import GetHpsJobIdsType
from ansys.saf.testing.solution.const import TestProductInstanceSystemType
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

if TYPE_CHECKING:
    from ansys.saf.testing.pim.process import PimProcess

pytestmark = [pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)]
PRODUCT_CONFIGS_DIR = Path("tests") / "mocks" / "solution_end_to_end" / "product_instance_configs"


@pytest.mark.use_fluent
@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
@pytest.mark.parametrize("deployment_type", ["Desktop", "DockerCompose"], indirect=True)
@pytest.mark.parametrize("product_configs_dir", [PRODUCT_CONFIGS_DIR], indirect=True)
class TestCustomFluent:
    def test_fluent_custom_args(
        self,
        request: pytest.FixtureRequest,
        function_project: ProjectFixture[EndToEndSolution],
        instance_system_type: TestProductInstanceSystemType,
        get_hps_job_ids: GetHpsJobIdsType,
        get_hps_job_output: Callable[[str], list[str]],
    ) -> None:
        """
        Test that a solution can use a shared product instance that derives from a built-in product configuration,
        but overriding it (e.g., changing the command arguments).
        """
        old_job_ids = []
        job_name = "custom-fluent-2ddp-solver-252-GLOW-Instance"
        if instance_system_type == TestProductInstanceSystemType.HPS:
            old_job_ids = get_hps_job_ids(job_name, "all", [])

        step = function_project.project.steps.fluent_custom_step
        with pytest.raises(InternalSolutionException):
            step.launch_instance()

        if instance_system_type == TestProductInstanceSystemType.PIM:
            pim_proc: PimProcess = request.getfixturevalue("session_pim")
            assert pim_proc.find_msg_in_output("Try 'python -m ansys.saf.product_configuration.wrappers.fluent --help'")
            assert pim_proc.find_msg_in_output("Error: No such option '--my-custom-arg'.")
        else:
            job_ids = get_hps_job_ids(job_name, "all", old_job_ids)
            assert len(job_ids) == 1
            job_output = get_hps_job_output(job_ids[0])
            assert any(
                "Try 'python -m ansys.saf.product_configuration.wrappers.fluent --help'" in line for line in job_output
            )
            assert any("Error: No such option '--my-custom-arg'." in line for line in job_output)
