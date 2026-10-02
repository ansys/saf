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
from pathlib import Path

from ansys.saf.testing.common import find_exec_in_venv
from ansys.saf.testing.process import Process


class SAFProcess(Process):
    def __init__(
        self,
        cmd: list[str],
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        bg: bool = False,
        input_str: str = "",
        health_check: Callable[["Process"], None] | None = None,
        expected_return_code: int | None = None,
    ) -> None:
        starter_exec = find_exec_in_venv(Path.cwd(), "saf")
        super().__init__(
            cmd=[starter_exec.as_posix()] + cmd,
            env=env,
            cwd=cwd,
            bg=bg,
            input_str=input_str,
            health_check=health_check,
            expected_return_code=expected_return_code,
        )

    def get_project_display_name(self) -> str:
        project_display_name = self.find_msg_in_output(r"- display name: my-project-[0-9a-f]{5}", regex=True)
        assert project_display_name
        return project_display_name.removeprefix("- display name: ")

    def get_project_name(self) -> str:
        project_name = self.find_msg_in_output(r"- name: projects/[0-9a-f]+", regex=True)
        assert project_name
        return project_name.removeprefix("- name: ")

    def get_api_docs_url(self) -> str:
        project_api_url = self.find_msg_in_output(r"Solution API: http://127\.0\.0\.1:\d+/docs", regex=True)
        assert project_api_url
        return project_api_url.removeprefix("INFO - Solution API: ")

    def get_project_api_url(self) -> str:
        return self.get_api_docs_url().replace("docs", self.get_project_name())

    def get_solution_ui_url(self, no_project: bool = False) -> str:
        solution_ui_url_pattern = r"Solution UI: http://127\.0\.0\.1:\d+"
        if not no_project:
            solution_ui_url_pattern += r"/projects/[0-9a-f]+"
        solution_ui_url = self.find_msg_in_output(solution_ui_url_pattern, regex=True)
        assert solution_ui_url
        return solution_ui_url.removeprefix("INFO - Solution UI: ")

    def get_portal_url(self) -> str:
        project_ui_url = self.find_msg_in_output(r"SAF Portal: http://127\.0\.0\.1:\d+", regex=True)
        assert project_ui_url
        return project_ui_url.removeprefix("INFO - SAF Portal: ")

    def get_projects_dashboard_url(self) -> str | None:
        """Return the URL of the projects dashboard, or None if the solution does not use it."""
        projects_dashboard_url = self.find_msg_in_output(r"Projects Dashboard: http://127\.0\.0\.1:\d+/\S*", regex=True)
        if not projects_dashboard_url:
            return None
        return projects_dashboard_url.removeprefix("INFO - Projects Dashboard: ")

    def get_otel_dashboard_url(self) -> str:
        otel_url = self.find_msg_in_output(r"OTEL Dashboard: http://127\.0\.0\.1:\d+", regex=True)
        assert otel_url
        return otel_url.removeprefix("INFO - OTEL Dashboard: ")
