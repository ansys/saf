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

import os
from pathlib import Path
import platform
import shutil

import httpx2
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.testing.process import Process
from tests.utils import get_appdata_directory


@retry(stop=stop_after_attempt(240), wait=wait_fixed(1))
def find_final_orchestrator_startup_message(p: Process):
    if not p.find_msg_in_output("Additional services:"):
        raise TryAgain


class SolutionShortcutProcess(Process):
    def __init__(self, solution_class_name: str, shortcut_path: Path, use_pythonw: bool = False):
        self._solution_files_dir = Path(get_appdata_directory()) / "ansys" / "glow" / solution_class_name
        if self._solution_files_dir.is_dir():
            # FIXME: remove once we have dedicated tmp appdata for every test. In the meantime, we need to clean it up
            # to isolate tests.
            shutil.rmtree(self._solution_files_dir)
        if platform.system() == "Windows":
            cmd = ["cmd", "/c", shortcut_path.as_posix()]
        elif use_pythonw:
            raise ValueError("Pythonw not available for Linux")
        else:
            cmd = ["xvfb-run", "gtk-launch", shortcut_path.name.replace(".desktop", "")]

        super().__init__(
            cmd=cmd,
            bg=True,
            health_check=find_final_orchestrator_startup_message if not use_pythonw else None,
        )

    def orchestrator_logs(self) -> list[str]:
        orchestrator_log_file = self._solution_files_dir / "orchestrator.log"
        return orchestrator_log_file.read_text().splitlines() if orchestrator_log_file.is_file() else []

    def api_logs(self) -> list[str]:
        api_logs_dir = self._solution_files_dir / "logs" / "api_server"
        api_log_files = sorted(api_logs_dir.glob("log_*.log"), key=os.path.getmtime)
        return api_log_files[-1].read_text().splitlines() if api_log_files else []

    def ui_logs(self) -> list[str]:
        ui_logs_dir = self._solution_files_dir / "logs" / "ui_server"
        ui_log_files = sorted(ui_logs_dir.glob("log_*.log"), key=os.path.getmtime)
        return ui_log_files[-1].read_text().splitlines() if ui_log_files else []

    def _api_started(self) -> bool:
        api_started = self.find_msg_in_output("Solution API: not launched")
        return not api_started

    def _ui_started(self) -> bool:
        ui_started = self.find_msg_in_output("Solution UI: not launched")
        return not ui_started

    def _portal_started(self) -> bool:
        portal_started = self.find_msg_in_output("SAF Portal: not launched")
        return not portal_started

    def _otel_started(self) -> bool:
        otel_started = self.find_msg_in_output("OTEL Dashboard: not launched")
        return not otel_started

    def _get_project_name(self) -> str:
        project_name_log_line = self.find_msg_in_output(r"- name: projects/[0-9a-f]+", regex=True)
        return project_name_log_line.removeprefix("- name: ") if project_name_log_line else ""

    def _get_api_docs_url(self) -> str:
        project_api_log_line = self.find_msg_in_output(r"Solution API: http://127\.0\.0\.1:\d+/docs", regex=True)
        assert project_api_log_line
        return project_api_log_line.removeprefix("INFO - Solution API: ")

    def _get_project_api_url(self) -> str:
        project_name = self._get_project_name()
        return self._get_api_docs_url().replace("docs", project_name) if project_name else ""

    def get_solution_ui_url(self) -> str:
        project_ui_log_line = self.find_msg_in_output(
            r"Solution UI: http://127\.0\.0\.1:\d+",
            regex=True,
        )
        assert project_ui_log_line
        return project_ui_log_line.removeprefix("INFO - Solution UI: ")

    def api_running(self) -> bool:
        if self._api_started():
            api_url = self._get_api_docs_url()
            try:
                return httpx2.get(api_url).status_code == 200
            except Exception:
                pass
        return False

    def ui_running(self) -> bool:
        if self._ui_started():
            ui_url = self.get_solution_ui_url()
            try:
                return httpx2.get(ui_url).status_code == 200
            except Exception:
                pass
        return False

    def project_running(self) -> bool:
        if self._api_started():
            project_api_url = self._get_project_api_url()
            try:
                return httpx2.get(project_api_url).status_code == 200
            except Exception:
                return False
        return False

    def portal_running(self) -> bool:
        if self._portal_started():
            portal_log_line = self.find_msg_in_output(r"SAF Portal: http://127\.0\.0\.1:\d+", regex=True)
            assert portal_log_line
            portal_url = portal_log_line.removeprefix("INFO - SAF Portal: ")
            try:
                return httpx2.get(portal_url).status_code == 200
            except Exception:
                pass
        return False

    def otel_running(self) -> bool:
        if self._otel_started():
            otel_log_line = self.find_msg_in_output(r"OTEL Dashboard: http://127\.0\.0\.1:\d+", regex=True)
            assert otel_log_line
            otel_url = otel_log_line.removeprefix("INFO - OTEL Dashboard: ")
            try:
                return httpx2.get(otel_url, follow_redirects=True).status_code == 200
            except Exception:
                pass
        return False
