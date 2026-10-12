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
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    CustomTypeABC,
    CustomTypeXYZ,
)

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestCustomTypes:
    def test_custom_type_download(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that a Step field typed as a custom data type can be downloaded and uploaded from transactions.
        """

        step = function_project.project.steps.transaction_verification_step

        assert step.custom_object2 == CustomTypeXYZ(x=1, y=0, z=0)
        assert step.custom_object2_x == 0

        step.ct2_x_parse()

        assert step.custom_object2_x == 1

    def test_custom_type_init_upload(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that a Step field typed as a custom data type can be constructed and uploaded from a transactions.
        """
        step = function_project.project.steps.transaction_verification_step

        assert step.custom_object is None
        step.ct_init()
        assert step.custom_object == CustomTypeXYZ(x=1, y=2, z=3)

    def test_compound_custom_type_download(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that a Step field can handle compound custom data types.
        """
        step = function_project.project.steps.transaction_verification_step

        assert step.compound_custom_object == CustomTypeABC(a=0, b=CustomTypeXYZ(x=0, y=0, z=0), c=0)
        step.comp_obj()
        assert step.compound_custom_object == CustomTypeABC(a=1, b=CustomTypeXYZ(x=1, y=0, z=0), c=3)

    def test_compound_custom_type_init_upload(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that a Step field typed as a compound custom data type can be constructed and uploaded from a transactions.
        """
        step = function_project.project.steps.transaction_verification_step

        assert step.optional_compound_custom_object is None
        step.comp_obj_with_init()
        assert step.optional_compound_custom_object == CustomTypeABC(a=1, b=CustomTypeXYZ(x=1, y=0, z=0), c=3)

    def test_switch_custom_type(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that a Step field typed as a Union between multiple custom data types.
        """
        step = function_project.project.steps.transaction_verification_step

        compound_custom_object = CustomTypeABC(a=0, b=CustomTypeXYZ(x=0, y=0, z=0), c=0)

        assert step.multiple_types_attribute == CustomTypeXYZ(x=1, y=0, z=0)  # type: ignore
        assert step.compound_custom_object == compound_custom_object
        step.switch_type()
        assert step.multiple_types_attribute == compound_custom_object  # type: ignore
