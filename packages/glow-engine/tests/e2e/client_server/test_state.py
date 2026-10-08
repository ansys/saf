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

from ansys.saf.glow.solution import FieldState
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solutions.state_dependency import StateDependencySolution

pytestmark = pytest.mark.parametrize("solution_type", [StateDependencySolution], indirect=True)


def test_initial_states(
    function_project: ProjectFixture[StateDependencySolution],
):
    expected_a_state = {
        "a1": FieldState.UPTODATE,
        "a2": FieldState.UPTODATE,
        "a3": FieldState.OUTOFDATE,
        "a_file": FieldState.OUTOFDATE,
    }
    expected_b_state = {
        "b1": FieldState.UPTODATE,
        "b2": FieldState.UPTODATE,
        "b3": FieldState.OUTOFDATE,
        "b4": FieldState.OUTOFDATE,
    }
    expected_c_state = {"c1": FieldState.OUTOFDATE, "c2": FieldState.UPTODATE, "c_file_group": FieldState.UPTODATE}
    assert function_project.project.steps.a_step.state == expected_a_state
    assert function_project.project.steps.b_step.state == expected_b_state
    assert function_project.project.steps.c_step.state == expected_c_state


def test_update_all_fields_makes_them_uptodate(
    function_project: ProjectFixture[StateDependencySolution],
):
    expected_a_state = {
        "a1": FieldState.UPTODATE,
        "a2": FieldState.UPTODATE,
        "a3": FieldState.UPTODATE,
        "a_file": FieldState.OUTOFDATE,
    }
    expected_b_state = {
        "b1": FieldState.UPTODATE,
        "b2": FieldState.UPTODATE,
        "b3": FieldState.OUTOFDATE,
        "b4": FieldState.OUTOFDATE,
    }
    expected_c_state = {"c1": FieldState.OUTOFDATE, "c2": FieldState.UPTODATE, "c_file_group": FieldState.UPTODATE}
    # TODO: use with transaction() to update all fields at once.
    project = function_project.project
    project.steps.a_step.a1 = 90
    project.steps.a_step.a2 = 2
    project.steps.a_step.a3 = "hi"
    assert project.steps.a_step.state == expected_a_state
    assert project.steps.b_step.state == expected_b_state
    assert project.steps.c_step.state == expected_c_state


def test_update_downstream_field_makes_it_uptodate(
    function_project: ProjectFixture[StateDependencySolution],
):
    project = function_project.project
    project.steps.b_step.b4 = "uptodate"
    expected_b_state = {
        "b1": FieldState.UPTODATE,
        "b2": FieldState.UPTODATE,
        "b3": FieldState.OUTOFDATE,
        "b4": FieldState.UPTODATE,
    }
    assert project.steps.b_step.state == expected_b_state


def test_update_upstream_field_invalidates_downstream(
    function_project: ProjectFixture[StateDependencySolution],
):
    project = function_project.project
    # make downstream c1 valid
    project.steps.c_step.c1 = "valid"
    assert project.steps.c_step.state["c1"] == FieldState.UPTODATE
    # change a3 value to invalidate c1
    project.steps.a_step.a3 = "updated_value"
    expected_a_state = {
        "a1": FieldState.UPTODATE,
        "a2": FieldState.UPTODATE,
        "a3": FieldState.UPTODATE,
        "a_file": FieldState.OUTOFDATE,
    }
    expected_b_state = {
        "b1": FieldState.UPTODATE,
        "b2": FieldState.UPTODATE,
        "b3": FieldState.OUTOFDATE,
        "b4": FieldState.OUTOFDATE,
    }
    expected_c_state = {"c1": FieldState.OUTOFDATE, "c2": FieldState.UPTODATE, "c_file_group": FieldState.UPTODATE}
    assert project.steps.a_step.state == expected_a_state
    assert project.steps.b_step.state == expected_b_state
    assert project.steps.c_step.state == expected_c_state


def test_execute_method_validates_downstream_fields(
    function_project: ProjectFixture[StateDependencySolution],
):
    project = function_project.project
    project.steps.a_step.a_method()
    expected_a_state = {
        "a1": FieldState.UPTODATE,
        "a2": FieldState.UPTODATE,
        "a3": FieldState.UPTODATE,
        "a_file": FieldState.OUTOFDATE,
    }
    assert project.steps.a_step.state == expected_a_state
