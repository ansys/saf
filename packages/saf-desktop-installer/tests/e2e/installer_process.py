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

from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.testing.process import Process


@retry(stop=stop_after_attempt(240), wait=wait_fixed(1))
def find_final_installer_startup_message(p: Process):
    if not p.find_msg_in_output("Serving Flask app 'Solution Installer'"):
        raise TryAgain


class SolutionInstallerProcess(Process):
    def __init__(self, cmd: list[str]):
        super().__init__(
            cmd=cmd,
            bg=True,
            health_check=find_final_installer_startup_message,
        )

    @property
    def installer_ui_url(self) -> str:
        url_log_line = self.find_msg_in_output(r"Dash is running on http://127\.0\.0\.1:\d+/", regex=True)
        assert url_log_line
        return url_log_line.split("Dash is running on ")[1]
