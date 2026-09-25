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
import re
import tempfile

from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
    ISoftware,
    ServiceType,
    Software,
)

SERVICE_NAME = "grpc"


class MapdlInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
    """Configuration class for a specific version of Ansys Mechanical APDL (MAPDL) using secure gRPC connections."""

    # Notes:
    # - gRPC certificates must be passed through environment variable ANSYS_GRPC_CERTIFICATES.
    # - binding host cannot be configured. It's either localhost or 0.0.0.0, depending on the -allowremote flag.
    # - uds_dir can be configured through environment variable ANSYS_MAPDL_UDS_PATH
    # - uds_id is always $PORT. Hence, the resulting socket file is: "mapdl-$PORT.sock"

    def __init__(self, version: str) -> None:
        """
        Initialize the configuration class for MAPDL with the specified version.

        Parameters
        ----------
        version : str
            The version of the MAPDL instance.
        """
        self._version = version

    @property
    def service_name(self) -> str:
        """The name of the service associated with the MAPDL instance."""
        return SERVICE_NAME

    @property
    def execution_command(self) -> str:
        """The command to launch MAPDL."""
        # Use a custom temp dir for launching MAPDL, otherwise it uses the current
        # working directory and fills it with initial files.
        # For HPS, this temp dir is unique for every launch, but
        # for PIM it is the same one since it's computed when generating the YAML config.
        # In any case, this directory will be changed to the proper value by the manager.
        mapdl_temp_dir = Path(tempfile.mkdtemp(prefix="mapdl-")).as_posix()
        return f"${{EXECUTABLE}} -grpc -port ${{PORT}} -dir {mapdl_temp_dir}"

    @property
    def environment(self) -> dict[str, str]:
        """Environment variables for the MAPDL instance."""
        return {
            "ANSYS_LOCK": "OFF",  # Force startup, even if previous launches have left .lock files in the temp dir
            "ANSYS_MAPDL_UDS_PATH": "${UDS_DIR}",
        }

    @property
    def software_requirements(self) -> list[ISoftware]:
        """Required software to run MAPDL in HPS."""
        return [
            Software(
                name="Ansys Mechanical APDL",
                version=f"20{self._version[0:2]} R{self._version[2:]}",
            ),
        ]

    @property
    def exe_path_for_pim(self) -> str:
        """Path to the MAPDL executable."""
        for varname, value in os.environ.copy().items():
            varname_match = re.fullmatch(r"AWP_ROOT([0-9]{3})", varname)
            if varname_match and varname_match.group(1) == self._version:
                if platform.system() == "Windows":
                    mapdl_path = Path(value) / "ansys" / "bin" / "winx64" / f"ANSYS{self._version}.exe"
                else:
                    mapdl_path = Path(value) / "ansys" / "bin" / f"ansys{self._version}"
                return str(mapdl_path)
        raise ValueError(f"Ansys Mechanical APDL version {self._version} cannot be found")

    @property
    def service_type(self) -> ServiceType:
        """Service type use for the health check."""
        return ServiceType.GRPC

    @property
    def enable_secure_flags(self) -> bool:
        """Enable secure communication flags for MAPDL."""
        return True

    @property
    def linux_local_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure local communication on
        Linux."""
        return "-transport uds"

    @property
    def linux_uds_id(self) -> str:
        """Template for the uds_id, which is used to identify the socket file for UDS communication."""
        return "${PORT}"

    @property
    def windows_local_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure local communication on
        Windows."""
        return "-transport wnua"

    @property
    def remote_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure remote communication."""
        return "-transport mtls -allowremote true"

    @property
    def insecure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for insecure communication."""
        return "-transport insecure -allowremote true"


class MapdlInstanceConfiguration(IProductInstanceConfiguration):
    """Configuration class for Ansys Mechanical APDL (MAPDL) using secure gRPC connections."""

    @property
    def product_name(self) -> str:
        """Name used to identify MAPDL in the product instance management system."""
        return "mapdl-secure"

    @property
    def versions(self) -> list[str]:
        """Supported MAPDL versions."""
        return ["251", "252"]

    def get_version_configuration(self, version: str) -> MapdlInstanceVersionConfiguration:
        """Get configuration class for a particular version of MAPDL."""
        return MapdlInstanceVersionConfiguration(version)
