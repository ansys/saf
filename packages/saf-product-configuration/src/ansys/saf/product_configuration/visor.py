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

import sys

from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
    ISoftware,
    ServiceType,
    Software,
)

PRODUCT_NAME = "visor"
SERVICE_NAME = "http"


class VisorInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
    """Configuration class for a specific version of Visor."""

    def __init__(self, version: str) -> None:
        """
        Initialize the configuration class for Visor with the specified version.

        Parameters
        ----------
        version : str
            The version of the Visor instance.
        """
        self._version = version

    @property
    def service_name(self) -> str:
        """The name of the service associated with the Visor instance."""
        return SERVICE_NAME

    @property
    def execution_command(self) -> str:
        """The command to launch Visor."""
        return "${EXECUTABLE} -m ansys.visor.viewer.cli.visor_cli --api-host 0.0.0.0 --api-port ${PORT} server start"

    @property
    def exe_path_for_pim(self) -> str:
        """Path to the Visor executable for PIM light server."""
        return sys.executable

    @property
    def environment(self) -> dict[str, str]:
        """Environment variables for the Visor instance."""
        return {}

    @property
    def software_requirements(self) -> list[ISoftware]:
        """Required software to run Visor in HPS."""
        return [
            Software(
                name="Visor Viewer",
                version=self._version,
            ),
        ]

    @property
    def service_type(self) -> ServiceType:
        """Service type use for the health check."""
        return ServiceType.HTTP


class VisorInstanceConfiguration(IProductInstanceConfiguration):
    """Configuration class for Visor."""

    @property
    def product_name(self) -> str:
        """Name used to identify Visor in the product instance management system."""
        return PRODUCT_NAME

    @property
    def versions(self) -> list[str]:
        """Supported Visor versions."""
        return ["0"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        """Get configuration class for a particular version of Visor."""
        return VisorInstanceVersionConfiguration(version)
