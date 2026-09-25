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
import re
import sys

from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
    ISoftware,
    ServiceType,
    Software,
)
from ansys.saf.product_configuration.wrappers.versions import FLUENT_WRAPPER_VERSION

SERVICE_NAME = "http"

# Same supported configurations as PIM-K8s: solver-3ddp, solver-2ddp, meshing-3ddp


class AbstractFluentInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
    """Configuration class for a specific version of Ansys Fluent."""

    def __init__(self, version: str) -> None:
        """
        Initialize the configuration class for Fluent with the specified version.

        Parameters
        ----------
        version : str
            The version of the Fluent instance.
        """
        self._version = version

    @property
    def service_name(self) -> str:
        """The name of the service associated with the Fluent instance."""
        return SERVICE_NAME

    @property
    def execution_command(self) -> str:
        """The command to launch Fluent."""
        raise NotImplementedError

    @property
    def environment(self) -> dict[str, str]:
        """Environment variables for the Fluent instance."""
        return {}

    @property
    def software_requirements(self) -> list[ISoftware]:
        """Required software to run Fluent in HPS."""
        return [
            Software(
                name="Ansys SAF Product Wrapper [Fluent]",
                version=FLUENT_WRAPPER_VERSION,
            ),
            Software(
                name="Ansys Fluent",
                version=f"20{self._version[0:2]} R{self._version[2:]}",
            ),
        ]

    @property
    def exe_path_for_pim(self) -> str:
        """Path to the Fluent executable."""
        for varname, _ in os.environ.copy().items():
            varname_match = re.fullmatch(r"AWP_ROOT([0-9]{3})", varname)
            if varname_match and varname_match.group(1) == self._version:
                return sys.executable
        raise ValueError(f"Ansys Fluent version {self._version} cannot be found")

    @property
    def service_type(self) -> ServiceType:
        """Service type use for the health check."""
        return ServiceType.HTTP

    @property
    def enable_secure_flags(self) -> bool:
        return True

    @property
    def linux_local_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure local communication on
        Linux."""
        return "--transport-mode=UDS"

    @property
    def windows_local_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure local communication on
        Windows."""
        return "--transport-mode=WNUA"

    @property
    def remote_secure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for secure remote communication."""
        return "--transport-mode=MTLS --certs-dir=${CERTS_DIR}"

    @property
    def insecure_flags(self) -> str:
        """The command line arguments needed to configure the product instance for insecure communication."""
        return "--transport-mode=insecure"


class Fluent3DDPSolverInstanceVersionConfiguration(AbstractFluentInstanceVersionConfiguration):
    """Configuration class for a specific version of Ansys Fluent
    in solver mode with 3D geometry in double precision and secure gRPC connection."""

    @property
    def execution_command(self) -> str:
        """The command to launch Fluent in solver mode with 3D geometry in double precision."""
        return (
            "${EXECUTABLE} -m ansys.saf.product_configuration.wrappers.fluent --port ${PORT} --host ${HOST} "
            f"--version {self._version} --mode solver --geometry 3d --precision double"
        )


class Fluent3DDPSolverInstanceConfiguration(IProductInstanceConfiguration):
    """Configuration class for Ansys Fluent in solver mode with 3D geometry in double precision and
    secure gRPC connection."""

    @property
    def product_name(self) -> str:
        """Name used to identify Fluent in the product instance management system."""
        return "fluent-3ddp-solver-secure"

    @property
    def versions(self) -> list[str]:
        """Supported Fluent versions."""
        return ["251", "252"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        """Get configuration class for a particular version of Fluent."""
        return Fluent3DDPSolverInstanceVersionConfiguration(version)


class Fluent2DDPSolverInstanceVersionConfiguration(AbstractFluentInstanceVersionConfiguration):
    """Configuration class for a specific version of Ansys Fluent
    in solver mode with 2D geometry in double precision and secure gRPC connection."""

    @property
    def execution_command(self) -> str:
        """The command to launch Fluent in solver mode with 2D geometry in double precision."""
        return (
            "${EXECUTABLE} -m ansys.saf.product_configuration.wrappers.fluent --port ${PORT} --host ${HOST} "
            f"--version {self._version} --mode solver --geometry 2d --precision double"
        )


class Fluent2DDPSolverInstanceConfiguration(IProductInstanceConfiguration):
    """Configuration class for Ansys Fluent in solver mode with 2D geometry in double precision and
    secure gRPC connection."""

    @property
    def product_name(self) -> str:
        """Name used to identify Fluent in the product instance management system."""
        return "fluent-2ddp-solver-secure"

    @property
    def versions(self) -> list[str]:
        """Supported Fluent versions."""
        return ["251", "252"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        """Get configuration class for a particular version of Fluent."""
        return Fluent2DDPSolverInstanceVersionConfiguration(version)


class Fluent3DDPMeshingInstanceVersionConfiguration(AbstractFluentInstanceVersionConfiguration):
    """Configuration class for a specific version of Ansys Fluent
    in meshing mode with 3D geometry in double precision and secure gRPC connection."""

    @property
    def execution_command(self) -> str:
        """The command to launch Fluent in meshing mode with 3D geometry in double precision."""
        return (
            "${EXECUTABLE} -m ansys.saf.product_configuration.wrappers.fluent --port ${PORT} --host ${HOST} "
            f"--version {self._version} --mode meshing --geometry 3d --precision double"
        )


class Fluent3DDPMeshingInstanceConfiguration(IProductInstanceConfiguration):
    """Configuration class for Ansys Fluent in meshing mode with 3D geometry in double precision and
    secure gRPC connection."""

    @property
    def product_name(self) -> str:
        """Name used to identify Fluent in the product instance management system."""
        return "fluent-3ddp-meshing-secure"

    @property
    def versions(self) -> list[str]:
        """Supported Fluent versions."""
        return ["251", "252"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        """Get configuration class for a particular version of Fluent."""
        return Fluent3DDPMeshingInstanceVersionConfiguration(version)
