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

from dash.testing import ignore_register_page
import pytest

from saf.solutions.solution03e2bfd.solution.definition import Solution03E2BfdSolution

with ignore_register_page():
    from saf.solutions.solution03e2bfd.ui.pages.first_page import calculate, load_result, save_result

pytestmark = [pytest.mark.usefixtures("init_dashclient")]


def test_calculate_callback(project_name: str):
    assert calculate(1, 1, 2, project_name) == (3.0, True)


def test_save_result_callback(client_project: Solution03E2BfdSolution, project_name: str):
    first_step = client_project.steps.first_step
    first_step.result = 7.0
    assert save_result(1, project_name) == True
    assert client_project.storage_scope.get_text(first_step.result_file) == "7.0"


def test_load_result_callback(client_project: Solution03E2BfdSolution, project_name: str):
    result_file = client_project.storage_scope.get_storage_root() / "result_file.txt"
    result_file.write_text("29.5")
    first_step = client_project.steps.first_step
    first_step.result_file = client_project.storage_scope.store(result_file)
    assert load_result(1, project_name) == (29.5, True)
