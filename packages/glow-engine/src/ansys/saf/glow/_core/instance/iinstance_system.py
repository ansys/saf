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

from abc import ABC
from collections.abc import Callable
import os
from pathlib import PurePath
import time
from types import ModuleType
from typing import Protocol

from ansys.saf.glow._config.const import (
    GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM,
    GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY,
)
from ansys.saf.glow._config.directories import find_product_instance_configs_dir
from ansys.saf.glow._utilities.path_parser import parse_platform_specific_absolute_path
from ansys.saf.product_configuration.manager.configurations_manager import ProductInstanceConfigurationsManager


class IProductInstanceVersionDefinition(Protocol):
    """The definition of a "type" of instance."""

    @property
    def name(self) -> str: ...

    @property
    def product_version(self) -> str: ...


class IProductInstanceService(Protocol):
    """Connection information for a service provided by an instance."""

    @property
    def host(self) -> str:
        """The host on which the service is exposed."""
        ...

    @property
    def port(self) -> int:
        """The port on which the service is exposed."""
        ...

    @property
    def uds_id(self) -> str | None:
        """The identifier of the Unix Domain Socket created for this service, if any.
        (This is only relevant for services that are exposed over UDS)"""
        return None

    @property
    def uds_dir(self) -> str | None:
        """The directory in which the instance has created a Unix Domain Socket for this service, if any.
        (This is only relevant for services that are exposed over UDS)"""
        return None

    @property
    def secure_flags(self) -> str | None:
        """The secure flags (if any) with which the product instance was launched."""
        return None

    @property
    def project_files_directory(self) -> PurePath | None:
        project_files_directory = os.getenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY)
        product_platform = os.getenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM)
        if project_files_directory and product_platform:
            return parse_platform_specific_absolute_path(project_files_directory, product_platform)
        return None


class IHealthClient(Protocol):
    def is_healthy(self) -> bool: ...

    def close(self) -> None: ...


class IHealthClientFactory(Protocol):
    def create_client(self, service: IProductInstanceService) -> IHealthClient: ...


class IProductInstance(Protocol):
    """Information about and operations on a given instance"""

    def wait_for_ready(self) -> None: ...

    def is_healthy(self) -> bool: ...

    @property
    def name(self) -> str: ...

    @property
    def definition_name(self) -> str: ...

    @property
    def services(self) -> dict[str, IProductInstanceService]: ...

    def delete(self, missing_ok: bool = False) -> None: ...

    @property
    def version(self) -> str: ...


class GenericProductInstance(ABC, IProductInstance):
    # TODO - support a product instance serviceing more than one service using different protocols
    #        its not a glow requirement (yet) but PIM supports it.

    def __init__(
        self,
        health_client_factory: IHealthClientFactory,
        service_name: str,
        wait_attempts: int = 100,
    ) -> None:
        self._health_client_factory = health_client_factory
        self._service_name = service_name
        self._wait_attempts = wait_attempts

    def _wait(self, is_done: Callable[[], bool], when_done: Callable[[], None], timeout_message: str) -> None:
        attempts = 0
        while not (done := is_done()) and attempts != self._wait_attempts:
            time.sleep(0.5)
            attempts += 1

        when_done()

        if not done:
            raise TimeoutError(timeout_message)

    def _get_health_client(self) -> IHealthClient | None:
        if self._service_name in self.services:
            service = self.services[self._service_name]
            return self._health_client_factory.create_client(service)
        return None

    def is_healthy(self) -> bool:
        client = self._get_health_client()
        if client:
            return client.is_healthy()
        return False

    def _wait_for_healthy(self) -> None:
        client = self._get_health_client()
        if not client:
            raise RuntimeError(
                f"Service {self._service_name} not found in instance's services. Instance may not be ready yet.",
            )

        self._wait(
            lambda: client.is_healthy(),
            lambda: client.close(),
            f"Timed out waiting for instance {self.name} to become healthy",
        )

    def _wait_for_removal(self) -> None:
        client = self._get_health_client()

        if not client:
            return

        self._wait(
            lambda: not client.is_healthy(),
            lambda: client.close(),
            f"Product instance {self.name} is still running. Failed to delete",
        )


class IProductInstanceSystem(Protocol):
    """Interface to a service that manages stateful instances that provide services (HPS or PIM)."""

    _configurations_manager = ProductInstanceConfigurationsManager()

    def load_configurations_from_solution(self, solution_module: ModuleType):
        """Load the product instance configurations found within the solution.

        This will search recursively the solution directories for a folder named ``product_instance_configs``.

        Parameters
        ----------
        solution_module : str
            The module containing the solution definition.
        """
        product_instance_configs = find_product_instance_configs_dir(solution_module)
        self._configurations_manager.load_configurations(product_instance_configs)

    def list_definitions(self, product_name: str) -> list[IProductInstanceVersionDefinition]:
        """"""
        ...

    def create_instance(
        self,
        product_name: str,
        max_execution_time: int,
        product_version: str | None = None,
    ) -> IProductInstance: ...

    def get_instance(self, instance_name: str) -> IProductInstance | None: ...

    def close(self) -> None: ...


class IProductInstanceSystemFactory(Protocol):
    """Generate an interface to a a service that manages stateful instances that provide services"""

    def create_system(self, uri: str) -> IProductInstanceSystem:
        """Generate an interface to a a service that manages stateful instances that provide services.
        Assume that this method consumes scarce connection resources. Under normal conditions a
        process will only need to call this method once.
        """
        ...
