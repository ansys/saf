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

from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.usefixtures("configure_aedt_installation_dir"),
]

SOLUTIONS_PER_PRODUCT: dict[str, list[tuple[str, str]]] = {
    # Examples of solution types for each product
    "icepak": [("SteadyStateTemperatureAndFlow", "SteadyState")],
    "hfss": [("Terminal", "Terminal")],
}


@pytest.mark.use_aedt
@pytest.mark.parametrize("aedt_product", ["hfss", "icepak"])
@pytest.mark.parametrize(
    "instance_system_type",
    [
        pytest.param("PIM", marks=pytest.mark.use_pim),
        pytest.param("HPS", marks=pytest.mark.use_hps),
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    [
        "Desktop",
        pytest.param(
            "DockerCompose",
            marks=pytest.mark.xfail(reason="pyaedt rpyc not working with docker"),
        ),
    ],
    indirect=True,
)
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True)
def test_aedt_solution_type(aedt_product: str, function_project: ProjectFixture[EndToEndSolution], ansys_release: str):
    """
    Test that AEDT instances accept solution types as inputs.
    """
    step = function_project.project.steps.aedt_solution_types_verification_step
    for solution_type_input, solution_type_retrieved in SOLUTIONS_PER_PRODUCT[aedt_product]:
        # GIVEN: AEDT solution_type configured
        step.target_solution_type = solution_type_input
        # WHEN: Launching AEDT
        step.aedt_version = ansys_release
        getattr(step, f"initialize_{aedt_product}_instance_with_solution_type")().wait(timeout=180)
        # THEN: solution type was correctly set and retrieved
        assert step.retrieved_solution_type == solution_type_retrieved
        # THEN: launched AEDT version is correct
        getattr(step, f"upload_{aedt_product}_aedt_version_from_aedt")().wait()
        assert step.aedt_version == f"ANSYSEM_ROOT{ansys_release}"

    getattr(step, f"exit_{aedt_product}_instance")()
