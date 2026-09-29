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
import re

import httpx2

from ansys.saf.testing.common import find_exec_in_venv
from ansys.saf.testing.process import Process


class OrchestratorProcess(Process):
    def __init__(
        self,
        args: list[str],
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        health_check: Callable[["Process"], None] | None = None,
        use_pythonw: bool = False,
        bg: bool = True,
    ):
        python_exec = find_exec_in_venv(Path.cwd(), "python" if not use_pythonw else "pythonw")
        super().__init__([python_exec.as_posix()] + args, env=env, cwd=cwd, health_check=health_check, bg=bg)

    def _portal_started(self) -> bool:
        portal_started = self.find_msg_in_output("SAF Portal: not launched")
        return not portal_started

    def _api_started(self) -> bool:
        api_started = self.find_msg_in_output("Solution API: not launched")
        return not api_started

    def _ui_started(self) -> bool:
        ui_started = self.find_msg_in_output("Solution UI: not launched")
        return not ui_started

    def _pim_started(self) -> bool:
        pim_started = self.find_msg_in_output("PIM Light Server: not launched")
        return not pim_started

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

    def get_api_docs_url(self) -> str:
        project_api_log_line = self.find_msg_in_output(r"Solution API: http://127\.0\.0\.1:\d+/docs", regex=True)
        assert project_api_log_line
        return project_api_log_line.removeprefix("INFO - Solution API: ")

    def get_project_api_url(self) -> str:
        project_name = self.get_project_name()
        return self.get_api_docs_url().replace("docs", project_name) if project_name else ""

    def get_solution_ui_url(self, no_project: bool = False) -> str:
        solution_ui_url_pattern = r"Solution UI: http://127\.0\.0\.1:\d+"
        if not no_project:
            solution_ui_url_pattern += r"/projects/[0-9a-f]+"
        solution_ui_log_line = self.find_msg_in_output(
            solution_ui_url_pattern,
            regex=True,
        )
        assert solution_ui_log_line
        return solution_ui_log_line.removeprefix("INFO - Solution UI: ")

    def get_portal_ui_url(self) -> str:
        portal_log_line = self.find_msg_in_output(r"SAF Portal: http://127\.0\.0\.1:\d+", regex=True)
        assert portal_log_line
        return portal_log_line.removeprefix("INFO - SAF Portal: ")

    def get_otel_url(self) -> str:
        otel_log_line = self.find_msg_in_output(r"OTEL Dashboard: http://127\.0\.0\.1:\d+", regex=True)
        assert otel_log_line
        return otel_log_line.removeprefix("INFO - OTEL Dashboard: ")

    @staticmethod
    def _check_url_status(url: str, expected_status_code: int) -> bool:
        try:
            with httpx2.Client(trust_env=False) as client:
                return client.get(url).status_code == expected_status_code
        except Exception:
            return False

    def api_running(self) -> bool:
        if self._api_started():
            api_url = self.get_api_docs_url()
            return self._check_url_status(api_url, 200)
        return False

    def ui_running(self, no_project: bool = False) -> bool:
        if self._ui_started():
            ui_url = self.get_solution_ui_url(no_project)
            return self._check_url_status(ui_url, 200)
        return False

    def assert_started_and_shutting_down(self):
        assert self._api_started()
        assert self._ui_started()
        assert self.find_msg_in_output("Shutting down services...")

    def get_project_display_name(self) -> str:
        project_display_name_log_line = self.find_msg_in_output(r"- display name: .+", regex=True)
        return project_display_name_log_line.removeprefix("- display name: ") if project_display_name_log_line else ""

    def get_project_name(self) -> str:
        project_name_log_line = self.find_msg_in_output(r"- name: projects/[0-9a-f]+", regex=True)
        return project_name_log_line.removeprefix("- name: ") if project_name_log_line else ""

    def project_running(self) -> bool:
        if self._api_started():
            project_api_url = self.get_project_api_url()
            return self._check_url_status(project_api_url, 200)
        return False

    def portal_running(self) -> bool:
        if self._portal_started():
            portal_url = self.get_portal_ui_url()
            return self._check_url_status(portal_url, 200)
        return False

    def pim_running(self) -> str | None:
        if self._pim_started():
            pim_log_line = self.find_msg_in_output("PIM Light Server: ")
            assert pim_log_line
            return pim_log_line.removeprefix("INFO - PIM Light Server: ")
        return None

    def get_pim_url(self) -> str:
        pim_url = self.pim_running()
        assert pim_url
        return pim_url

    def pim_logging(self) -> Path | None:
        pim_log_line = self.find_msg_in_output("PIM Light Server logging to ")
        if pim_log_line is None:
            return None
        pim_log_path_str = pim_log_line.removeprefix("INFO - PIM Light Server logging to ")
        pim_log_path = Path(pim_log_path_str)
        if pim_log_path.is_file():
            return pim_log_path
        return None

    def pim_args(self) -> str | None:
        if self._pim_started():
            pim_log_line = self.find_msg_in_output("Using PIM light command args: ")
            assert pim_log_line
            return pim_log_line.removeprefix("INFO - Using PIM light command args: ")
        return None

    def otel_running(self) -> bool:
        otel_line = self.find_msg_in_output(r"OTEL Dashboard: http://127\.0\.0\.1:\d+", regex=True)
        if otel_line is None:
            return False
        otel_url = otel_line.removeprefix("INFO - OTEL Dashboard: ")
        # homepage redirect to /structuredLog
        return self._check_url_status(otel_url, 302)

    def additional_services_running(self, yaml_file: Path | None = None) -> bool:
        if yaml_file is None:
            return False

        additional_services: list[str] = []

        with Path.open(yaml_file) as file:
            for line in file:
                if "- name: " in line:
                    service_name = line.removeprefix("- name: ")
                    refactor_service_name = service_name.replace('"', "").replace("\n", "").upper()
                    additional_services.append(refactor_service_name)

        for line in self.output:
            match_service = re.search(r"- (\w+_SERVICE): http://localhost:\d+", line)
            if match_service:
                service_line = match_service.group(0)
                service_name = service_line.split(": http://")[0].removeprefix("- ")
                additional_services.remove(service_name)

        return len(additional_services) == 0

    def get_additional_services_urls(self, yaml_file: Path | None = None) -> dict[str, str]:
        services_urls: dict[str, str] = {}
        if yaml_file is None:
            return services_urls

        with Path.open(yaml_file) as file:
            for line in file:
                if "- name: " in line:
                    service_name = line.removeprefix("- name: ")
                    refactor_service_name = service_name.replace('"', "").replace("\n", "").upper()

                    service_log_line = self.find_msg_in_output(
                        rf"- {refactor_service_name}: http://localhost:\d+",
                        regex=True,
                    )
                    assert service_log_line
                    service_url = service_log_line.split(": http://")[1]
                    services_urls[refactor_service_name] = f"http://{service_url}"

        return services_urls
