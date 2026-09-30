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

from enum import Enum, auto
import logging
import os
from pathlib import Path
import platform
import re
import shutil
from tempfile import mkdtemp
import typing
import uuid

from ansys.saf.desktop.orchestrator._config.schema import DEFAULT_SAF_DESKTOP_HEALTH_CHECK_TIMEOUT, PIM_LOCALHOSTS
from ansys.saf.desktop.orchestrator._orchestration.process import ServiceProcess
from ansys.saf.desktop.orchestrator._utilities.ip_utilities import get_random_free_port
from ansys.saf.product_configuration.interfaces import IProductInstanceConfiguration
from ansys.saf.product_configuration.pim.config_writer import PimLightConfigWriter

logger = logging.getLogger(__name__)


class TransportMode(Enum):
    """The different modes of connection of PIM Light Server."""

    UNKNOWN = auto()
    INSECURE = auto()
    UDS = auto()
    MTLS = auto()
    WNUA = auto()


class PimProcess(ServiceProcess):
    _PIM_DEFINITIONS_CONFIG_PATH_ENV = "AENEID_ROOT"

    def __init__(
        self,
        products: list[IProductInstanceConfiguration],
        port: int | None = None,
        ip: str = "127.0.0.1",
        health_check_timeout: int = DEFAULT_SAF_DESKTOP_HEALTH_CHECK_TIMEOUT,
        log_file: Path | None = None,
    ) -> None:
        logger.debug("Starting pim process...")
        if log_file:
            logger.info(f"PIM Light Server logging to {log_file}")
        self._is_windows = platform.system() == "Windows"
        self._is_local_ip = ip in PIM_LOCALHOSTS
        self._http_scheme = "http" if self._is_local_ip else "https"
        if not self._is_windows and self._is_local_ip and port is not None:
            raise RuntimeError("PIM on Linux with a localhost IP can only be run with UDS, port must be None.")
        self._certs_dir = None
        if certs_dir := os.getenv("ANSYS_GRPC_CERTIFICATES"):
            if self._is_local_ip:
                logger.warning("PIM is running on a localhost IP with gRPC certificates. They will not be used.")
            else:
                self._certs_dir = Path(certs_dir)
        if not self._is_local_ip and not self._certs_dir:
            raise RuntimeError(
                "PIM is running on a non-localhost IP without gRPC certificates. "
                "Set ANSYS_GRPC_CERTIFICATES environment variable with the path to the certificates directory.",
            )

        if (self._is_windows or not self._is_local_ip) and port is None:
            port = get_random_free_port()

        self._products = products
        self._socket_path: Path | None = None
        self._definitions_dir = mkdtemp()

        self._write_configurations()

        args = self._build_cmd_args(ip, port)
        logger.debug(f"pim command line: {args}")

        super().__init__(
            args,
            port=port,
            ip=ip,
            health_route="",
            health_check_timeout=health_check_timeout,
            log_file=log_file,
        )

    @classmethod
    def find_unified_pim_installation(cls) -> Path | None:
        # Look for Ansys installations in the environment variables, preferring the latest version
        # that actually contains the PIM Light executable.
        if platform.system() == "Linux":
            # PIM server is currently only included in the unified installation for Windows,
            # so we skip this search on Linux.
            return None

        ansys_installations = sorted(
            (
                (int(awp_root_match.group(1)), env_value)
                for env_name, env_value in os.environ.items()
                if (awp_root_match := re.fullmatch(r"AWP_ROOT([0-9]{3})", env_name))
            ),
            key=lambda x: x[0],
            reverse=True,
        )
        if not ansys_installations:
            return None
        for _, ansys_path in ansys_installations:
            pim_exe = (
                Path(ansys_path)
                / "pim"
                / "ansys"
                / "instancemanagement"
                / "light"
                / "Ansys.InstanceManagement.Light.exe"
            )
            if pim_exe.is_file():
                return pim_exe

        return None

    def _build_cmd_args(self, ip: str, port: int | None) -> list[str]:
        # PIM Light Server is not a mandatory service defined as dependency in the orchestrator.
        try:
            from ansys.saf.pim_light_server.locate import (  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
                get_pim_light_exe_and_args,  # pyright: ignore[reportUnknownVariableType]
            )

            args: list[str] = typing.cast("list[str]", get_pim_light_exe_and_args())  # pyright: ignore[reportUnnecessaryCast]
        except ModuleNotFoundError:
            # pim light server not found in the environment, try to find it in a unified Ansys installation.
            pim_exe = self.find_unified_pim_installation()
            if pim_exe is None:
                raise ModuleNotFoundError(
                    "The package 'ansys-saf-pim-light-server' is not installed or could not be found.",
                ) from None
            args = [pim_exe.as_posix()]

        if self._is_windows and self._is_local_ip:
            self._transport_mode = TransportMode.WNUA
            args.append(f"--transport-mode={self._transport_mode.name}")
            args.append(f"--urls={self._http_scheme}://{ip}:{port}")
        elif not self._is_local_ip:
            self._transport_mode = TransportMode.MTLS
            args.append(f"--transport-mode={self._transport_mode.name}")
            args.append(f"--urls={self._http_scheme}://{ip}:{port}")
            args.append(f"--certs-dir={self._certs_dir.as_posix()}")  # pyright: ignore[reportOptionalMemberAccess]  # already checked at init
        else:
            self._transport_mode = TransportMode.UDS
            args.append(f"--transport-mode={self._transport_mode.name}")
            uds_dir = mkdtemp()
            args.append(f"--uds-dir={uds_dir}")
            shortid = uuid.uuid4().hex[:8]
            # we need an id to be able to launch multiple servers on the same host
            args.append(f"--uds-id={shortid}")
            self._socket_path = Path(uds_dir) / f"pim-{shortid}.sock"

        logger.info(f"Using PIM light command args: {' '.join(args)}")
        return args

    def _write_configurations(self):
        configurations_dir = Path(self._definitions_dir) / "Configurations"
        configurations_dir.mkdir()
        logger.debug(f"Pim product configurations directory: {configurations_dir}")
        for product_config in self._products:
            PimLightConfigWriter().write_config(configurations_dir, product_config)
        os.environ[self._PIM_DEFINITIONS_CONFIG_PATH_ENV] = self._definitions_dir

    @property
    def args(self) -> list[str]:
        return self._args

    @property
    def url(self) -> str:
        if self._socket_path:
            return f"unix:{self._socket_path}"
        else:
            return f"{self._http_scheme}://{self._ip}:{self._port}"

    @property
    def socket_path(self) -> Path | None:
        return self._socket_path

    def wait_for_healthy(self):
        if not self._grpc_health_check("PIM", self._socket_path, self._certs_dir):
            raise RuntimeError("unable to connect to healthy PIM server after PIM startup")

    def stop(self):
        if self._PIM_DEFINITIONS_CONFIG_PATH_ENV in os.environ:
            del os.environ[self._PIM_DEFINITIONS_CONFIG_PATH_ENV]
        shutil.rmtree(self._definitions_dir)
        super().stop()
