# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from saf.solutions.solution03e2bfd.solution.definition import Solution03E2BfdSolution


def test_set_and_retrieve_basic_step_fields(client_project: Solution03E2BfdSolution):
    first_step = client_project.steps.first_step
    # retrieve step field
    assert first_step.first_arg == 0
    # set step field
    first_step.first_arg = 1.0
    # retrieve updated value
    assert first_step.first_arg == 1.0
    # set multiple fields
    first_step.set_fields({"first_arg": 2.0, "second_arg": 3.0})
    # retrieve updated values
    assert first_step.first_arg == 2.0
    assert first_step.second_arg == 3.0


def test_calculate(client_project: Solution03E2BfdSolution):
    first_step = client_project.steps.first_step
    first_step.first_arg = 10.0
    first_step.second_arg = 20.0
    first_step.calculate()
    assert first_step.result == 30.0


def test_save_result(client_project: Solution03E2BfdSolution):
    first_step = client_project.steps.first_step
    first_step.result = 7.0
    first_step.save_result()
    assert client_project.storage_scope.get_text(first_step.result_file) == "7.0"


def test_load_result(client_project: Solution03E2BfdSolution):
    result_file = client_project.storage_scope.get_storage_root() / "result_file.txt"
    result_file.write_text("29.5")
    first_step = client_project.steps.first_step
    first_step.result_file = client_project.storage_scope.store(result_file)
    result = first_step.load_result()
    assert result == 29.5
