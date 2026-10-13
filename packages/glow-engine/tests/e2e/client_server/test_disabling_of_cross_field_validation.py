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
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.check_message import check_message
from tests.mocks.solutions.cross_field_validation_solution import CrossFieldValidationSolution

pytestmark = pytest.mark.parametrize("solution_type", [CrossFieldValidationSolution], indirect=True)


def test_set_step_multiple_fields_validation_is_not_supported_and_will_not_raise_exception_as_might_be_expected(
    function_project: ProjectFixture[CrossFieldValidationSolution],
):
    """Tests that setting property from the step proxy with a value that is validated using values from other fields
    is not supported.

    When fields are validated before being set, all validation is executed but fields except the modified one have
    the default value. In this case we're checking a scenario where the expected validation does not occur as expected
    because the validation is against defaults."""
    cross_field_validation_step = function_project.project.steps.cross_field_validation_step
    cross_field_validation_step.set_fields({"flag_a": True, "flag_b": True})


def test_set_step_multiple_fields_validation_is_not_supported_and_will_not_report_failures_as_might_be_expected(
    function_project: ProjectFixture[CrossFieldValidationSolution],
):
    """Tests that setting property from the step proxy with a value that is validated using values from other fields
    is not supported.

    When fields are validated before being set, all validation is executed but fields except the modified one have
    the default value. In this case we're checking a scenario where the expected validation does not occur as expected
    because the validation is against defaults.  Here we trigger a validation message via other fields (flag_c) and
    check that the cross field validation (flag_a and flag_b) is not reported."""
    cross_field_validation_step = function_project.project.steps.cross_field_validation_step
    with pytest.raises(BadRequestException) as e:
        cross_field_validation_step.set_fields({"flag_c": True, "flag_a": True, "flag_b": True})
    check_message(
        [
            "1 validation error for CrossFieldValidationStep",
            "Value error, flag_c is set [type=value_error, input_value={'flag_c': True}, input_type=dict]",
        ],
        e.value.args[0],
    )
