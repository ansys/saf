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
import subprocess

import httpx2

from ansys.saf.testing.process import Process


class SolutionShortcutPythonwProcess(Process):
    def __init__(self, shortcut_path: Path):
        if platform.system() == "Windows":
            cmd = ["cmd", "/c", str(shortcut_path.absolute())]
        else:
            # For Linux we need to copy the shortcut to ~/.local/share/applications so that it can be launched
            # using gtk-launch.
            applications_dir = Path(os.environ.get("HOME", "")) / ".local" / "share" / "applications"
            applications_dir.mkdir(parents=True, exist_ok=True)
            copy_cmd = ["cp", shortcut_path.as_posix(), applications_dir.as_posix()]
            subprocess.check_output(copy_cmd)
            # Using new_solution fixture changes the value of XDG_DATA_HOME. The following command requires
            # the default value of this environment variable.
            # Use -a so xvfb-run to pick a free display automatically and avoid Xvfb collision on :99
            cmd = [
                "xvfb-run",
                "-a",
                "env",
                f"XDG_DATA_HOME={applications_dir.parent}",
                "gtk-launch",
                shortcut_path.name.replace(".desktop", ""),
            ]
        super().__init__(cmd=cmd, bg=True)

    def _api_started(self) -> bool:
        api_started = self.find_msg_in_output("Solution API: not launched")
        return not api_started

    def _ui_started(self) -> bool:
        ui_started = self.find_msg_in_output("Solution UI: not launched")
        return not ui_started

    def _portal_started(self) -> bool:
        portal_started = self.find_msg_in_output("SAF Portal: not launched")
        return not portal_started

    def get_api_docs_url(self) -> str:
        project_api_url = self.find_msg_in_output(r"Solution API: http://127\.0\.0\.1:\d+/docs", regex=True)
        assert project_api_url
        return project_api_url.removeprefix("INFO - Solution API: ")

    def get_project_ui_url(self) -> str:
        project_ui_url = self.find_msg_in_output(r"Solution UI: http://127\.0\.0\.1:\d+/projects/[0-9a-f]+", regex=True)
        assert project_ui_url
        return project_ui_url.removeprefix("INFO - Solution UI: ")

    def api_running(self) -> bool:
        if self._api_started():
            api_url = self.get_api_docs_url()
            try:
                return httpx2.get(api_url).status_code == 200
            except Exception:
                pass
        return False

    def ui_running(self) -> bool:
        if self._ui_started():
            ui_url = self.get_project_ui_url()
            try:
                return httpx2.get(ui_url).status_code == 200
            except Exception:
                pass
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
