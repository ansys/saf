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

from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
    ISoftware,
    ServiceType,
    Software,
)

PRODUCT_NAME_SECURE = "mechanical-secure"
SERVICE_NAME = "grpc"


class MechanicalInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
    """Configuration class for a specific version of Ansys Mechanical with secure gRPC connections."""

    # Notes:
    # - Careful! Using equal sign in options does not work:
    # (--transport-mode=insecure launches mechanical, but you cannot connect to it with insecure channel...)

    def __init__(self, version: str) -> None:
        """
        Initialize the configuration class for Mechanical with the specified version.

        Parameters
        ----------
        version : str
            The version of the Mechanical instance.
        """
        self._version = version

    @property
    def service_name(self) -> str:
        """The name of the service associated with the Mechanical instance."""
        return SERVICE_NAME

    @property
    def execution_command(self) -> str:
        """The command to launch Mechanical."""
        return "${EXECUTABLE} -DSAPPLET -B -GRPC ${PORT} --GRPC-HOST ${HOST}"

    @property
    def environment(self) -> dict[str, str]:
        """Environment variables for the Mechanical instance."""
        return {}

    @property
    def software_requirements(self) -> list[ISoftware]:
        """Required software to run Mechanical in HPS."""
        return [
            Software(
                name="Ansys Mechanical",
                version=f"20{self._version[0:2]} R{self._version[2:]}",
            ),
        ]

    @property
    def exe_path_for_pim(self) -> str:
        """Path to the Mechanical executable."""
        for varname, value in os.environ.copy().items():
            varname_match = re.fullmatch(r"AWP_ROOT([0-9]{3})", varname)
            if varname_match and varname_match.group(1) == self._version:
                if platform.system() == "Windows":
                    return str(Path(value) / "aisol" / "bin" / "winx64" / "AnsysWBU.exe")
                else:
                    return str(Path(value) / "aisol" / ".workbench")
        raise ValueError(f"Ansys Mechanical version {self._version} cannot be found")

    @property
    def service_type(self) -> ServiceType:
        """Service type use for the health check."""
        return ServiceType.TCP

    @property
    def enable_secure_flags(self) -> bool:
        """Enable secure communication with the Mechanical service."""
        return True

    # Explicitly defining the secure flags because service type is TCP so the default won't apply
    @property
    def linux_local_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure local communication on
        Linux."""
        # mechanical doesn't support uds
        return "--transport-mode MTLS --certs-dir ${CERTS_DIR}"

    @property
    def windows_local_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure local communication on
        Windows."""
        return "--transport-mode WNUA"

    @property
    def remote_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure remote communication."""
        return "--transport-mode MTLS --certs-dir ${CERTS_DIR}"

    @property
    def insecure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for insecure communication."""
        return "--transport-mode insecure"


class MechanicalInstanceConfiguration(IProductInstanceConfiguration):
    """Configuration class for Ansys Mechanical with secure gRPC connections."""

    @property
    def product_name(self) -> str:
        """Name used to identify Mechanical in the product instance management system."""
        return PRODUCT_NAME_SECURE

    @property
    def versions(self) -> list[str]:
        """Supported Mechanical versions."""
        return ["251", "252"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        """Get configuration class for a particular version of Mechanical."""
        return MechanicalInstanceVersionConfiguration(version)
