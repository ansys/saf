# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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

import logging
from enum import Enum
from pathlib import Path
import subprocess

from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.testing._hps.scripts.hps_installer import (
    HPS_DEPLOYMENTS_DIRECTORY,
    configuring_hps_deployment,
    get_hps_external_name,
)
from ansys.saf.testing._pytest.platform_specific import is_ci_run

logger = logging.getLogger(__name__)


class HpsDeploymentProcess:
    compose_file: Path = HPS_DEPLOYMENTS_DIRECTORY / "docker-compose.yaml"

    @classmethod
    def run(cls, deployment_type: Enum) -> None:
        configuring_hps_deployment(get_hps_external_name(deployment_type.name))
        cmd = ["docker", "compose", "-f", cls.compose_file.as_posix(), "up", "-d", "--wait-timeout", "200"]
        if is_ci_run():
            cmd.append("--pull=never")
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError as err:
            logger.exception(err.output)
            raise
        cls._wait_for_healthy()

    @classmethod
    @retry(stop=stop_after_attempt(300), wait=wait_fixed(1))
    def _wait_for_healthy(cls) -> None:
        cmd = ["docker", "compose", "-f", cls.compose_file.as_posix(), "logs", "jms"]
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        if "Worker is running, reporting ready" not in result:
            raise TryAgain

    @classmethod
    def stop(cls) -> None:
        cmd = ["docker", "compose", "-f", cls.compose_file.as_posix(), "down", "-v"]
        try:
            with Path("hps_deployment_logs.txt").open("w") as f:
                cmd_logs = ["docker", "compose", "-f", cls.compose_file.as_posix(), "logs"]
                subprocess.run(cmd_logs, stdout=f, stderr=subprocess.STDOUT, text=True)
            subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError as err:
            logger.exception(err.output)
            raise

    @classmethod
    def restart(cls, deployment_type: Enum) -> None:
        cls.stop()
        cls.run(deployment_type)
