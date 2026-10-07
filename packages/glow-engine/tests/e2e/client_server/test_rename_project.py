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

from collections.abc import Callable
import re

from fastapi import status
import httpx2
import pytest

from ansys.saf.glow.client import BadRequestException, Client
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import TEXT_FILE_DUMMY_STRING

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


def project_list_diff(
    projects_before: list[dict[str, str]],
    projects_after: list[dict[str, str]],
    target_display_name: str,
) -> list[dict[str, str]]:
    """
    Finds the elements in projects_after that are not present in projects_before.
    Asserts that any project other than the target_display_name is left unchanged
    """
    for project in projects_before:
        if project["display_name"] != target_display_name:
            assert project in projects_after

    return [project for project in projects_after if project not in projects_before]


@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestRenameProjects:
    def test_rename_project_proper(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
        random_project_name: Callable[[], str],
    ):
        """
        Test that src project is properly renamed to dst. Other existing project remains unchanged.
        """
        dst_project_name = random_project_name()

        with (
            ProjectFixture(session_glow, function_client) as src_project,
            ProjectFixture(
                session_glow,
                function_client,
            ),
        ):
            project_list_before = function_client.list_projects()["projects"]
            old_project_name = src_project.display_name
            src_project.project.modify_info(display_name=dst_project_name)
            project_list_after = function_client.list_projects()["projects"]
            project = project_list_diff(project_list_before, project_list_after, old_project_name)
            assert len(project) == 1
            assert len(project_list_before) == len(project_list_after)
            assert project[0]["name"] == src_project.project_name
            assert project[0]["display_name"] == dst_project_name

    def test_rename_project_to_used_name(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
    ):
        """
        Test that it works because display_name is not unique in GLOW.
        """
        with (
            ProjectFixture(session_glow, function_client) as src_project,
            ProjectFixture(
                session_glow,
                function_client,
            ) as dst_project,
        ):
            project_list_before = function_client.list_projects()["projects"]
            old_project_name = src_project.display_name
            src_project.project.modify_info(display_name=dst_project.display_name)
            project_list_after = function_client.list_projects()["projects"]
            project = project_list_diff(project_list_before, project_list_after, old_project_name)
            assert len(project) == 1
            assert len(project_list_before) == len(project_list_after)
            assert project[0]["name"] == src_project.project_name
            assert project[0]["display_name"] == dst_project.display_name

    @pytest.mark.parametrize("check_target_unchanged", [False, True])
    def test_rename_project_that_does_not_exist(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
        random_project_id: Callable[[], str],
        random_project_name: Callable[[], str],
        check_target_unchanged: bool,
    ):
        """
        Test that status code 404: Not Found is returned after trying to rename a project that does not exist.
        Repeat checking that existing project with target name is not modified in the process.
        Other existing project remains unchanged.
        """
        src_project_name = random_project_name()
        existing_project_name = random_project_name()
        src_project_id = random_project_id()

        existing_project: ProjectFixture[EndToEndSolution] | None = None
        if check_target_unchanged:
            existing_project = ProjectFixture(session_glow, function_client, display_name=src_project_name)
        with ProjectFixture(session_glow, function_client, display_name=existing_project_name):
            project_request = {"display_name": src_project_name}

            project_list_before = function_client.list_projects()["projects"]
            response = httpx2.patch(f"{session_glow.base_api_url}/projects/{src_project_id}", json=project_request)
            project_list_after = function_client.list_projects()["projects"]

            assert response.status_code == status.HTTP_404_NOT_FOUND

            project = project_list_diff(project_list_before, project_list_after, src_project_name)

            assert len(project_list_before) == len(project_list_after)
            assert len(project) == 0

            assert session_glow.text_in_output("not found", "api")

        if existing_project:
            existing_project.project.delete()

    def test_rename_project_special_character(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
    ):
        """
        Test that src project cannot be renamed to name with special characters.
        Other project remains unchanged.
        """
        dst_project_name = "invalid-project-n:me"

        with (
            ProjectFixture(session_glow, function_client) as src_project,
            ProjectFixture(
                session_glow,
                function_client,
            ),
        ):
            project_list_before = function_client.list_projects()["projects"]
            with pytest.raises(
                BadRequestException,
                match="Display name cannot contain any of the following characters:",
            ):
                src_project.project.modify_info(display_name=dst_project_name)
            project_list_after = function_client.list_projects()["projects"]
            project = project_list_diff(project_list_before, project_list_after, src_project.display_name)

            assert len(project_list_before) == len(project_list_after)
            assert len(project) == 0

            assert session_glow.text_in_output(
                "Value error, Display name cannot contain any of the following characters:",
                "api",
            )

    def test_rename_project_in_use(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        random_project_name: Callable[[], str],
    ):
        """
        Check that project cannot be modified during long running methods.
        Long running method is not altered by the ill-fated rename attempt.
        """
        dst_project_name = random_project_name()
        waiting_seconds = 2
        field_1 = 1
        field_2 = 3
        expected_result = 4

        step = function_project.project.steps.transaction_verification_step

        step.create_text_file()
        assert step.result != expected_result

        # patch values for method
        step.field_1 = field_1
        step.field_2 = field_2
        step.sleepy_seconds = waiting_seconds

        # start long running
        method = step.long_running_dummy()

        # rename attempt
        error_msg = (
            "Unable to perform this action because the following methods are still running: '['long_running_dummy']'."
        )
        with pytest.raises(BadRequestException, match=re.escape(error_msg)):
            function_project.project.modify_info(display_name=dst_project_name)

        # wait for method to finish and check final result is ok
        method.wait()
        assert step.result == expected_result

    def test_rename_project_with_files(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        random_project_name: Callable[[], str],
    ):
        """
        Test that a project can be renamed without affecting its project files.
        """
        dst_project_name = random_project_name()
        file_content = TEXT_FILE_DUMMY_STRING
        function_project.project.steps.transaction_verification_step.create_text_file()
        function_project.project.modify_info(display_name=dst_project_name)
        file_path = next(function_project.project_files_dir.rglob("projectFiles/file.txt"))
        assert file_path.read_text() == file_content
