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

from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.testing.common import find_exec_in_venv
from ansys.saf.testing.process import Process


@retry(stop=stop_after_attempt(200), wait=wait_fixed(0.5))
def _find_final_orchestrator_startup_message(p: Process) -> None:
    if not p.find_msg_in_output("Additional services: "):
        raise TryAgain


class SolutionAppStarter(Process):
    def __init__(self, solution_root_dir: Path, archived_solution: Path) -> None:
        starter_exec = find_exec_in_venv(solution_root_dir, "solution-app-starter")
        super().__init__(
            cmd=[starter_exec.as_posix(), archived_solution.as_posix()],
            bg=True,
            health_check=_find_final_orchestrator_startup_message,
        )
