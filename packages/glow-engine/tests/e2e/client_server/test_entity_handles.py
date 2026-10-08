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

from pathlib import Path

import pytest

from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.mocks.solutions.entity_handle_solution import EntityHandleSolution

pytestmark = pytest.mark.parametrize("solution_type", [EntityHandleSolution], indirect=True)


def test_store_and_retrieval_of_entity_using_the_same_project_proxy(
    function_project: ProjectFixture[EntityHandleSolution],
    tmp_path: Path,
):
    # GIVEN - a file to upload
    content = "hello worldly world"
    file = tmp_path / "abc.txt"
    file.write_text(content)

    # AND GIVEN - a client for a specific project
    project = function_project.project

    # WHEN - uploading the file straight into the project storage scope
    with file.open(mode="rb") as binary_fileobj:  # this simulates a Dash upload
        project.steps.entity_handle_step.my_entity = project.storage_scope.store_stream(binary_fileobj, Path("xxx.txt"))

    # THEN - downloading the file straight from the project storage scope
    #        results in data with the correct content
    with project.storage_scope.get_stream(project.steps.entity_handle_step.my_entity) as stream:
        assert str(stream.readall(), "UTF-8") == content


def test_get_storage_scope_returns_the_same_value(
    function_project_without_context_mgr: ProjectFixture[EntityHandleSolution],
):
    project = function_project_without_context_mgr.project
    with project.get_storage_scope() as scope, project.get_storage_scope() as scope2:
        assert scope != scope2


def test_store_and_retrieval_of_entity_on_different_sessions(
    function_project: ProjectFixture[EntityHandleSolution],
    tmp_path: Path,
    session_glow: GlowBaseProcess[EntityHandleSolution],
):
    # GIVEN - a file to upload
    content = "hello worldly world"
    file = tmp_path / "abc.txt"
    file.write_text(content)

    # WHEN - uploading the file straight into the project storage scope
    project = function_project.project
    with file.open(mode="rb") as binary_fileobj:  # this simulates a Dash upload
        project.steps.entity_handle_step.my_entity = project.storage_scope.store_stream(binary_fileobj, Path("xxx.txt"))

    # THEN - downloading the file straight from the project storage scope
    #        results in data with the correct content
    session_glow.restart()
    project = function_project.project
    with project.storage_scope.get_stream(project.steps.entity_handle_step.my_entity) as stream:
        assert str(stream.readall(), "UTF-8") == content
