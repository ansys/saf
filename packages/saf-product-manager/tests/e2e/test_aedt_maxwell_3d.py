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

TOLERANCE = 1e-3

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.usefixtures("configure_aedt_installation_dir"),
]


@pytest.fixture(scope="class")
def launch_maxwell3d(class_project: ProjectFixture[EndToEndSolution], ansys_release: str):
    step = class_project.project.steps.maxwell_3d_verification_step
    # Launch AEDT
    step.aedt_version = ansys_release
    step.initialize_maxwell_3d_instance().wait()
    yield

    step.exit_aedt()


@pytest.mark.use_aedt
@pytest.mark.usefixtures("launch_maxwell3d")
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
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.xfail(reason="pyaedt rpyc not working with docker"))],
    indirect=True,
)
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True)
class TestMaxwell3D:
    def test_maxwell_3d_workflow(self, function_class_project: ProjectFixture[EndToEndSolution], ansys_release: str):
        """Run a basic workflow with Maxwell3D product instance manager."""

        # GIVEN: Maxwell3D instance launched
        step = function_class_project.project.steps.maxwell_3d_verification_step
        step.refresh_availability()
        assert step.m3d_available

        # We verify the version of AEDT is correct.
        step.upload_aedt_version_from_aedt().wait()
        assert step.aedt_version == f"ANSYSEM_ROOT{ansys_release}"

        # We add a box in the design, with specific origin, dimension and name.
        box_name = "box_A"
        box_dimension = [5.0, 5.0, 5.0]
        step.origin = [0, 0, 0]
        step.dimension = box_dimension
        step.box_name = box_name
        step.add_box()

        # We verify the dimension of the box.
        step.dimension = [0, 0, 0]
        step.upload_object_dimension_from_aedt().wait()
        for actual, expected in zip(step.dimension, box_dimension, strict=False):
            assert pytest.approx(float(actual), TOLERANCE) == pytest.approx(expected, TOLERANCE)  # type: ignore
