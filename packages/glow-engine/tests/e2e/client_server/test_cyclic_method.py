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
from tests.mocks.solutions.one_method_cyclic_dependency import OneMethodCyclicDependencySolution

pytestmark = pytest.mark.parametrize("solution_type", [OneMethodCyclicDependencySolution], indirect=True)


def test_method_transaction_can_increment_field(
    function_project: ProjectFixture[OneMethodCyclicDependencySolution],
):
    step = function_project.project.steps.one_method_cyclic_dependency_step
    assert step.x == 99
    returned_value = step.increment_and_return()
    assert step.x == returned_value == 100
