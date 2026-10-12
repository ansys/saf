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

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import InstanceManager, ProductInstanceManager, RecoveryStateInfo
from ansys.saf.product_manager._utilities.const import DEFAULT_SAF_VISOR_TIMEOUT, SAF_VISOR_TIMEOUT
from ansys.saf.product_manager._utilities.timeout_utilities import get_timeout_from_environment

if TYPE_CHECKING:
    from ansys.visor.viewer import Metadata  # pyright: ignore[reportMissingTypeStubs]

logger = logging.getLogger(__name__)


class VisorSafClient:
    """Visor SAF Client"""

    def __init__(self, host: str, port: int, timeout: int = DEFAULT_SAF_VISOR_TIMEOUT):
        """Creating a new Visor Client instance with the given host and port."""
        self._service_host = host
        self._service_port = port
        self._timeout = timeout
        response = (
            httpx2.get(
                f"http://{self._service_host}:{self._service_port}/info",
                timeout=self._timeout,
            )
            .raise_for_status()
            .json()
        )
        self._port = response["port"]
        self._host = response["host"]

    def update(self, file_path: str, metadata: Metadata) -> None:
        """Update the Visor instance."""
        update_payload = {
            "file_path": file_path,
            "metadata": metadata.model_dump(),
        }
        logger.debug(f"Updating Visor with payload: {update_payload}")
        httpx2.post(
            f"http://{self._service_host}:{self._service_port}/update",
            json=update_payload,
            timeout=self._timeout,
        ).raise_for_status()
        logger.info("Visor service updated.")

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port


class VisorRecoveryStateInfo(RecoveryStateInfo):
    pass


class InternalVisorManager(InstanceManager[VisorSafClient, VisorRecoveryStateInfo]):
    """Private class for Visor Manager"""

    PRODUCT_NAME = "visor"
    SERVICE_NAME = "http"

    def _get_metadata_obj(self, metadata_file: EntityHandle) -> dict[str, Any]:
        if metadata_file == NO_ENTITY:
            raise ValueError("Metadata file must be provided.")
        metadata_path = self.manager_storage_scope.get_cached(metadata_file)
        with Path(metadata_path).open("r") as f:
            metadata = json.load(f)
        return metadata

    def initialize(
        self,
        version: str | None = None,
        input_file: EntityHandle = NO_ENTITY,
        metadata_file: EntityHandle = NO_ENTITY,
    ):
        """Initialize and start the custom product server."""
        self.initialize_service(self.SERVICE_NAME, version)
        service = self._get_service()
        self._initialize_visor(
            hostname=service.host,
            port=service.port,
            input_file=input_file,
            metadata_file=metadata_file,
            timeout=get_timeout_from_environment(SAF_VISOR_TIMEOUT, DEFAULT_SAF_VISOR_TIMEOUT),
        )
        self.recovery_state_info = VisorRecoveryStateInfo()

    def _initialize_visor(
        self,
        hostname: str,
        port: int,
        input_file: EntityHandle = NO_ENTITY,
        metadata_file: EntityHandle = NO_ENTITY,
        timeout: int = DEFAULT_SAF_VISOR_TIMEOUT,
    ) -> None:
        init_payload = {
            "host": hostname,
            "standalone": False,
        }
        logger.debug(f"Initializing Visor with payload: {init_payload}")
        httpx2.post(f"http://{hostname}:{port}/initialize", json=init_payload, timeout=timeout).raise_for_status()
        logger.debug("Visor service initialized.")

        start_payload = {
            "file_path": self.product_storage_scope.get_cached(input_file).as_posix()
            if input_file != NO_ENTITY
            else None,
            "metadata": self._get_metadata_obj(metadata_file) if metadata_file != NO_ENTITY else None,
            "timeout": timeout,
        }
        logger.debug(f"Starting Visor with payload: {start_payload}")
        httpx2.post(f"http://{hostname}:{port}/start", json=start_payload, timeout=timeout).raise_for_status()
        logger.debug("Visor service started.")

    @classmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of the product in the product instance system (PIM or HPS) environment."""
        return cls.PRODUCT_NAME

    def save_state_implement(self) -> None:
        """Save changes to the project data and settings."""

    def load_state_implement(self) -> None:
        """Open the latest Visor project saved within ``protected_state_directory_path``."""
        service = self._get_service()
        self._initialize_visor(
            hostname=service.host,
            port=service.port,
            timeout=get_timeout_from_environment(SAF_VISOR_TIMEOUT, DEFAULT_SAF_VISOR_TIMEOUT),
        )

    def get_client_object_implement(self, hostname: str, port: int) -> VisorSafClient:
        """Return an instance of the custom product's client given the host and port of the product instance."""
        return VisorSafClient(
            hostname,
            port,
            timeout=get_timeout_from_environment(SAF_VISOR_TIMEOUT, DEFAULT_SAF_VISOR_TIMEOUT),
        )

    def close_client_object_implement(self) -> None:
        """Close the Visor object."""

    def shutdown_implement(self) -> None:
        """Gracefully terminates the product instance process."""
        service = self._get_service()
        httpx2.post(
            f"http://{service.host}:{service.port}/stop",
            timeout=get_timeout_from_environment(SAF_VISOR_TIMEOUT, DEFAULT_SAF_VISOR_TIMEOUT),
        ).raise_for_status()


class VisorManager(
    ProductInstanceManager[VisorSafClient, VisorRecoveryStateInfo],
    instance_manager_impl_type=InternalVisorManager,
):
    """A manager of a Visor product instance."""

    def __init__(self, **kwargs: Any):
        """Initialize and start the Visor product instance.

        Parameters
        ----------
        version : str, optional
            The version of the Visor product instance that must be used.
        input_file : EntityHandle, optional
            The input file to open on start.
        metadata_file : EntityHandle, optional
            The input metadata to use on start if a file is provided.
        """
        super().__init__(**kwargs)

    def initialize(
        self,
        version: str | None = None,
        input_file: EntityHandle = NO_ENTITY,
        metadata_file: EntityHandle = NO_ENTITY,
    ):
        """Initialize and start the Visor product instance.

        Parameters
        ----------
        version : str, optional
            The version of the custom product instance that must be used.
        input_file : EntityHandle, optional
            The input file to open on start.
        metadata_file : EntityHandle, optional
            The input metadata to use on start if a file is provided.
        """
        super().start(version=version, input_file=input_file, metadata_file=metadata_file)
