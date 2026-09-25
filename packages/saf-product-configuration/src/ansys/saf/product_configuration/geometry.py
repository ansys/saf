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
import shutil

from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
    ISoftware,
    ServiceType,
    Software,
)

PRODUCT_NAME_SECURE = "geometry-secure"
SERVICE_NAME = "grpc"

DEFAULT_DOTNET_ROOT = (
    Path("~/.dotnet/").expanduser() if platform.system() == "Linux" else Path("C:/Program Files/dotnet/")
)


class BaseGeometryInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
    """Base configuration class for Ansys Geometry service."""

    def __init__(self, version: str) -> None:
        """
        Initialize the configuration class for Geometry with the specified version.

        Parameters
        ----------
        version : str
            The version of the Geometry service instance.
        """
        self._version = version
        self._geometry_path = self._get_geometry_path()
        # In non-desktop deployments or when using HPS, GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM is used to specify the
        # platform of the system where the product is running. For example, in this way, GLOW API can create the
        # correct HPS task/job for the expected platform and not the one where the GLOW API is running.
        # We default to platform.system(), which should be fine for desktop deployments.
        self._geometry_platform = os.getenv("GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM", platform.system())

    @property
    def service_name(self) -> str:
        """The name of the service associated with the Geometry service instance."""
        return SERVICE_NAME

    @property
    def execution_command(self) -> str:
        """The command to launch Geometry."""
        raise NotImplementedError

    @property
    def environment(self) -> dict[str, str]:
        """Environment variables for the Geometry service instance."""
        raise NotImplementedError

    @property
    def software_requirements(self) -> list[ISoftware]:
        """Required software to run Geometry in HPS."""
        return [
            Software(
                name="Ansys Geometry",
                version=f"20{self._version[0:2]} R{self._version[2:]}",
            ),
        ]

    @property
    def exe_path_for_pim(self) -> str:
        """Path to the Geometry executable."""
        raise NotImplementedError

    @property
    def service_type(self) -> ServiceType:
        """Service type use for the health check."""
        return ServiceType.GRPC

    def _get_geometry_path(self) -> Path:
        # FIXME: We shouldn't check for this env var outside of exe_path_for_pim. Otherwise, we are assuming that
        # the Solution API proc knows the path of the Geometry binaries in the HPS Scaler environment and is
        # configured with it.
        for varname, value in os.environ.copy().items():
            varname_match = re.fullmatch(r"GEOMETRY_ROOT([0-9]{3})", varname)
            if varname_match and varname_match.group(1) == self._version:
                return Path(value)
        raise ValueError(f"Ansys Geometry version {self._version} cannot be found")

    def _get_dotnet_path(self) -> Path:
        dotnet_path = Path(os.getenv("DOTNET_ROOT", DEFAULT_DOTNET_ROOT)) / (
            "dotnet" if platform.system() == "Linux" else "dotnet.exe"
        )
        if not dotnet_path.is_file() and (dotnet := shutil.which("dotnet")):
            dotnet_path = Path(dotnet)
        return dotnet_path

    @property
    def enable_secure_flags(self) -> bool:
        """Enable secure communication with the Geometry service."""
        return True


class Geometry251InstanceVersionConfiguration(BaseGeometryInstanceVersionConfiguration):
    """Configuration class for a 251 version of Ansys Geometry service with secure gRPC connections."""

    def __init__(self, version: str) -> None:
        super().__init__(version=version)
        if self._geometry_platform == "Linux":
            raise ValueError("Only Windows platform is supported for Geometry version 251.")

    @property
    def execution_command(self) -> str:
        """The command to launch Geometry."""
        return "${EXECUTABLE}"

    @property
    def exe_path_for_pim(self) -> str:
        """Path to the Geometry executable."""
        return (self._geometry_path / "Presentation.ApiServerDMS.exe").as_posix()

    @property
    def environment(self) -> dict[str, str]:
        """Environment variables for the Geometry service instance."""
        return {
            "API_ADDRESS": "${HOST}",
            "API_PORT": "${PORT}",
            "LOG_LEVEL": "2",
        }


class GeometryInstanceVersionConfiguration(BaseGeometryInstanceVersionConfiguration):
    """Configuration class for 252 or higher version of Ansys Geometry service with secure gRPC connections."""

    @property
    def execution_command(self) -> str:
        """The command to launch Geometry."""
        if self._geometry_platform == "Linux":
            # self-contained executable for Linux will be added in 26R1
            # Due to how PIM configurations work, we must follow the "$exec [$args]" structure,
            # and thus dotnet is the right executable for 25R2 on Linux.
            return f"${{EXECUTABLE}} {(self._geometry_path / 'Presentation.ApiServerCoreService.dll').as_posix()}"
        else:
            return "${EXECUTABLE}"

    @property
    def exe_path_for_pim(self) -> str:
        """Path to the Geometry executable."""
        if self._geometry_platform == "Windows":
            return (self._geometry_path / "Presentation.ApiServerCoreService.exe").as_posix()
        else:
            return self._get_dotnet_path().as_posix()

    @property
    def environment(self) -> dict[str, str]:
        """Environment variables for the Geometry service instance."""
        env_vars = {
            "ANS_DSCO_REMOTE_PORT": "${PORT}",
            "ANS_DSCO_REMOTE_IP": "${HOST}",
            "LOG_LEVEL": "2",
            "ANSYS_CI_INSTALL": (self._geometry_path / "CADIntegration").as_posix(),
            "P_SCHEMA": (self._geometry_path / "Schema").as_posix(),
        }
        if self._geometry_platform == "Linux":
            library_paths_str = (
                f"{self._geometry_path.as_posix()}:"
                f"{(self._geometry_path / 'CADIntegration' / 'bin').as_posix()}:"
                f"{(self._geometry_path / 'Native' / 'Linux').as_posix()}"
            )
            env_vars["LD_LIBRARY_PATH"] = library_paths_str
            env_vars[f"ANSYSCL{self._version}_DIR"] = (self._geometry_path / "licensingclient").as_posix()
        else:
            library_paths_str = (
                f"{self._geometry_path.as_posix()};"
                f"{(self._geometry_path / 'CADIntegration' / 'bin').as_posix()};"
                f"{(self._geometry_path / 'Native' / 'Windows').as_posix()}"
            )
            env_vars["PATH"] = library_paths_str

        return env_vars


class GeometryInstanceConfiguration(IProductInstanceConfiguration):
    """Configuration class for Ansys Geometry service with secure gRPC connections."""

    @property
    def product_name(self) -> str:
        """Name used to identify Geometry in the product instance management system."""
        return PRODUCT_NAME_SECURE

    @property
    def versions(self) -> list[str]:
        """Supported Geometry versions."""
        return ["251", "252", "261"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        """Get configuration class for a particular version of Geometry."""
        if version == "251":
            return Geometry251InstanceVersionConfiguration(version)
        return GeometryInstanceVersionConfiguration(version)
