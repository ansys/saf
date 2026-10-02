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
import signal
import subprocess
import sys

import httpx2
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.desktop.installer.solution_desktop_deployment import get_random_port


class InstallerUIProcess:
    def __init__(
        self,
        solution_metadata_path: Path,
        installation_directory: Path | None = None,
        cwd: Path | None = None,
    ):
        self._solution_metadata_path = solution_metadata_path
        self._process = None
        self._port = get_random_port()
        self._installation_directory = installation_directory
        self._cwd = cwd

    def start(self):
        args = [
            sys.executable,
            "-m",
            "ansys.saf.desktop.installer.solution_desktop_deployment",
            "-m",
            str(self._solution_metadata_path),
            "-P",
            str(self.port),
        ]
        args += ["-i", str(self._installation_directory)] if self._installation_directory else []
        # BROWSER=true makes webbrowser.open a no-op on Linux.
        env = {**os.environ, "BROWSER": "true"}
        # Own session/group so stop() can kill the Dash child too; no inherited pipes to keep CI waiting.
        self._process = subprocess.Popen(
            args,
            cwd=self._cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=sys.platform != "win32",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        self._wait_for_healthy()
        return self

    @retry(stop=stop_after_attempt(10), wait=wait_fixed(0.5))
    def _wait_for_healthy(self):
        url = f"http://localhost:{self.port}"
        try:
            response = httpx2.get(url, timeout=1.0)
            if response.status_code in (200, 404):
                return
        except (httpx2.ConnectError, httpx2.TimeoutException):
            raise TryAgain from None

        raise TimeoutError("Installation UI did not successfully start")

    def stop(self):
        if not self._process:
            return
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                capture_output=True,
                check=False,
            )
        else:
            try:  # noqa: SIM105
                os.killpg(self._process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if sys.platform != "win32":
                os.killpg(self._process.pid, signal.SIGKILL)
            self._process.kill()
            self._process.wait()

    @property
    def port(self) -> int:
        return self._port
