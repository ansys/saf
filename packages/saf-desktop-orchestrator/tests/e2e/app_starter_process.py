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
import re

import httpx2
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.testing.common import find_exec_in_venv
from ansys.saf.testing.process import Process


@retry(stop=stop_after_attempt(200), wait=wait_fixed(0.5))
def _find_final_orchestrator_startup_message(p: Process) -> None:
    if not p.find_msg_in_output("Additional services: "):
        raise TryAgain


class SolutionAppStarter(Process):
    def __init__(
        self,
        archived_solution: Path,
        log_to_files: bool = False,
        env: dict[str, str] | None = None,
    ) -> None:
        starter_exec = find_exec_in_venv(Path.cwd().parent.parent, "solution-app-starter")
        cmd = [starter_exec.as_posix(), archived_solution.as_posix()]
        if log_to_files:
            cmd.append("--log-to-files")

        super().__init__(
            cmd=cmd,
            bg=True,
            health_check=_find_final_orchestrator_startup_message,
            env=env,
        )

    def get_project_ui_url(self) -> str:
        url_line = self.find_msg_in_output(r"Solution UI: http://127\.0\.0\.1:\d+\b", regex=True)
        assert url_line
        solution_ui_url = url_line.split("Solution UI: ")[1].strip()
        return f"{solution_ui_url}/projects/{self.get_project_id()}"

    def get_project_display_name(self) -> str:
        project_line = self.find_msg_in_output("Starting project with display_name ")
        assert project_line
        return project_line.split("display_name ")[1].split("...")[0]

    def get_project_id(self) -> str:
        project_line = self.find_msg_in_output("- name: projects/")
        assert project_line
        return project_line.split("name: ")[1].split("\n")[0]

    def get_solution_appdata(self) -> Path:
        appdata_line = self.find_msg_in_output("APPDATA set to ")
        assert appdata_line
        return Path(appdata_line.split("APPDATA set to ")[1].strip().rstrip("."))

    def otel_running(self) -> bool:
        otel_line = self.find_msg_in_output(r"OTEL Dashboard: http://127\.0\.0\.1:\d+", regex=True)
        if otel_line is None:
            return False
        otel_url = otel_line.removeprefix("INFO - OTEL Dashboard: ")
        try:
            response = httpx2.get(otel_url)
            # homepage redirect to /structuredLog
            return response.status_code == 302
        except Exception:
            pass
        return False

    def get_log_file_path(self) -> Path:
        log_file_line = self.find_msg_in_output("Extended logging available at ")
        assert log_file_line
        log_file_path_str = log_file_line.removeprefix("INFO - Extended logging available at ")
        log_file_path = Path(log_file_path_str)
        assert log_file_path.is_file()
        return log_file_path

    def find_msg_in_log_file(self, msg: str, regex: bool = False) -> str | None:
        for line in self.get_log_file_path().read_text().splitlines():
            if not regex:
                if msg in line:
                    return line
            else:
                if re.search(msg, line):
                    return line
