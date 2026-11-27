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

import os
from enum import Enum
from pathlib import Path
import platform

from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.testing._hps.scripts.hps_installer import (
    HPS_SCALING_EXECUTABLE_PATH,
    configuring_scalar,
    get_hps_external_name,
)
from ansys.saf.testing._system.process import Process


@retry(stop=stop_after_attempt(200), wait=wait_fixed(0.2))
def _find_final_scaler_startup_message(p: Process) -> None:
    if not p.find_msg_in_output("================== Waiting For Work =================="):
        raise TryAgain


class HpsScalerProcess(Process):
    """Process for managing HPS Scaler instances.

    This class handles the lifecycle of HPS Scaler processes, including starting,
    stopping, and configuring the scaler with appropriate environment settings.
    """

    def __init__(
        self,
        deployment_type: Enum,
        python_in_saf_product_environment: None | Path = None,
        saf_product_environment: None | Path = None,
        product_host: str | None = None,
        product_binding_host: str | None = None,
        certificates_directory: Path | None = None,
        enable_insecure_product: bool = False,
    ):
        # Examples:
        # - Solution running in WSL (Desktop or containerized) + HPS Scaler running in Windows:
        #   Use IP Address of Windows host (e.g., 172.23.80.1). Find it with `ipconfig` in Windows.
        # - Solution running in Linux/WSL Desktop + HPS Scaler running in same environment: localhost
        # - Solution running in Linux/WSL containerized + HPS Scaler running in Linux/WSL host: host.docker.internal
        from ansys.saf.glow.client import Deployment  # pyright: ignore[reportMissingImports]

        self.product_host = product_host or (
            "localhost"
            if deployment_type == Deployment.Desktop or platform.system() == "Windows"
            else "host.docker.internal"
        )
        self.product_binding_host = product_binding_host
        self.certificates_dir = certificates_directory
        self.enable_insecure_product = enable_insecure_product

        cmd = [HPS_SCALING_EXECUTABLE_PATH.as_posix(), "-v4", "run"]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path.cwd())
        env["GLOW_PRODUCT_HOST"] = self.product_host
        if self.product_binding_host:  # allow for None to test GLOW defaults
            env["GLOW_PRODUCT_BINDING_HOST"] = self.product_binding_host
        if self.certificates_dir and not self.enable_insecure_product:
            env["ANSYS_GRPC_CERTIFICATES"] = self.certificates_dir.as_posix()

        super().__init__(cmd=cmd, env=env, bg=True, health_check=_find_final_scaler_startup_message)

        self._python_in_saf_product_environment = python_in_saf_product_environment
        self._saf_product_environment = saf_product_environment
        self._hps_external_name = get_hps_external_name(deployment_type.name)

    def start(
        self,
        configure_scalar: bool = True,
        with_saf_product_environment_variable_set: bool = True,
        set_python_path: bool = True,
    ) -> None:
        """Start the HPS Scaler process.

        Parameters
        ----------
        configure_scalar : bool, default: True
            Whether to configure the scalar before starting.
        with_saf_product_environment_variable_set : bool, default: True
            Whether to set the SAF_PRODUCT_ENVIRONMENT variable.
        set_python_path : bool, default: True
            Whether to set the PYTHONPATH environment variable.
        """
        if configure_scalar:
            configuring_scalar(self._python_in_saf_product_environment, self._hps_external_name)
        if with_saf_product_environment_variable_set and self._saf_product_environment is not None:
            self._env["SAF_PRODUCT_ENVIRONMENT"] = str(self._saf_product_environment)
        if set_python_path:
            self._env["PYTHONPATH"] = str(Path.cwd())
        elif "PYTHONPATH" in self._env:
            del self._env["PYTHONPATH"]

        super().start()

    def restart(
        self,
        clear_output: bool = False,
        with_saf_product_environment_variable_set: bool = True,
        set_python_path: bool = True,
    ) -> None:
        self.stop()
        self.start(
            configure_scalar=False,
            with_saf_product_environment_variable_set=with_saf_product_environment_variable_set,
            set_python_path=set_python_path,
        )
