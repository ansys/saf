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

import contextlib
from pathlib import Path

import pytest

from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.usefixtures("configure_aedt_installation_dir"),
]


@pytest.mark.use_aedt
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
def test_aedt_design_names(function_project: ProjectFixture[EndToEndSolution], ansys_release: str):
    """
    Test that AEDT instances accept design names as inputs.
    """

    aedt_version_input = ansys_release
    input_project = Path(__file__).parent / "inputs" / "maxwell_3d_2_designs.aedt"
    active_design_name = "M3D_A"
    initial_object_count_in_design = 5
    input_design_names = ["M3D_A", "M3D_B"]
    expected_project_list = ["project"]

    def verify_design_name(expected_design_names: list[str], active_design_name: str) -> list[str]:
        # We verify the design names in the project and the active design name.
        step = function_project.project.steps.design_name_verification_step

        # We reset the field in which info from aedt is uploaded
        step.design_names = []

        # We invoke the method that uploads the design names.
        step.upload_design_names_from_maxwell_3d_instance().wait()

        # We verify the actual design names are the expected ones.
        actual_design_names = step.design_names
        assert sorted(actual_design_names) == sorted(expected_design_names)

        # We set the fields in which info from pyaedt is uploaded to non expected values.
        step.design_name = "dummy_name"

        # We retrieve the active design name and verify it is the new active design.
        step.get_active_design_for_maxwell_3d_instance()
        assert step.design_name == active_design_name

        return actual_design_names

    def verify_objects_in_design(
        expected_object_count: int,
        object_names_to_verify: list[str] | None = None,
    ) -> list[str]:
        """Verify the object count and the presence of named objects in the design.

        Args:
            expected_object_count (int): expected object count
            object_names_to_verify (list[str]): object names to verify the presence in the design.

        Returns:
            list[str]: the complete list of objects in the design.
        """
        step = function_project.project.steps.design_name_verification_step
        step.object_names = []  # reset the field in which info from aedt is uploaded
        step.upload_object_names_from_maxwell_3d_instance().wait()
        object_names = step.object_names

        assert object_names
        assert len(object_names) == expected_object_count

        if object_names_to_verify:
            for object_name_to_verify in object_names_to_verify:
                assert object_name_to_verify in object_names

        return object_names

    def verify_project_list() -> None:
        step = function_project.project.steps.design_name_verification_step
        step.get_project_list_from_maxwell_3d_instance().wait()
        project_list = step.project_list
        assert project_list
        assert sorted(project_list) == sorted(expected_project_list)

    def verify_transaction_method_with_close_project() -> None:
        # We call a transaction method closing the active project with pyaedt.
        # We verify that the save_state_implement does not try to save the project as it is closed.
        step = function_project.project.steps.design_name_verification_step

        # We set the fields in which info from pyaedt is uploaded to non expected values.
        step.project_closed = False
        step.project_list = ["dummy_name"]

        # We close the project and verify that the info from pyaedt is correctly uploaded.
        step.close_project_for_maxwell_3d_instance()
        assert step.project_closed
        assert step.project_list == []

    def verify_change_of_active_design() -> None:
        # We call a transaction method changing the active design with pyaedt.
        # We verify the next transaction method has the correct active design name.
        step = function_project.project.steps.design_name_verification_step

        # We select the name of a design which is not active and we patch the step property with this name.
        new_active_design = [design for design in input_design_names if design != active_design_name][0]
        step.design_name = new_active_design
        # We call the transaction method to active the design.
        step.set_active_design_for_maxwell_3d_instance()

        # We set the fields in which info from pyaedt is uploaded to non expected values.
        step.design_name = "dummy_name"

        # We retrieve the active design name and verify it is the new active design.
        step.get_active_design_for_maxwell_3d_instance()
        assert step.design_name == new_active_design

    # Launch AEDT with a project that contains multiple designs and a particular active design with some objects already
    step = function_project.project.steps.design_name_verification_step
    project_file = function_project.project.storage_scope.get_storage_root() / "project.aedt"
    _ = project_file.write_bytes(input_project.read_bytes())
    step.project_input = function_project.project.storage_scope.store(project_file)
    step.aedt_version = aedt_version_input
    step.design_name = active_design_name
    step.initialize_maxwell_3d_instance().wait(timeout=180)

    verify_project_list()
    initial_design_name = verify_design_name(input_design_names, active_design_name)
    verify_objects_in_design(expected_object_count=initial_object_count_in_design)

    step.upload_aedt_version_from_aedt().wait()
    assert step.aedt_version == f"ANSYSEM_ROOT{ansys_release}"

    # Create some objects
    step.add_object_to_maxwell_3d_instance().wait()
    object_names = verify_objects_in_design(expected_object_count=initial_object_count_in_design + 1)

    # Close AEDT and try to add more objects, so forces its reinitialization and automatically restore the state
    with contextlib.suppress(InternalSolutionException):
        # Since we are closing mechanical from the pim/hps and not the manager itself,
        # the dispose of the client in the end of the transaction is raising an exception
        step.kill_aedt_from_instance_system()
    step.add_object_to_maxwell_3d_instance().wait()
    verify_project_list()
    verify_design_name(initial_design_name, active_design_name)
    verify_objects_in_design(
        expected_object_count=initial_object_count_in_design + 2,
        object_names_to_verify=object_names,
    )

    # Test if changing the active design works OK
    verify_change_of_active_design()

    # Close the project and exit AEDT
    verify_transaction_method_with_close_project()
    step.exit_maxwell_3d_instance()
