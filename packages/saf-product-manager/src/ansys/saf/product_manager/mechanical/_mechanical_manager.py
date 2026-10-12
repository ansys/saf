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

import logging
import os
from pathlib import Path
from typing import Any

from ansys.mechanical.core import Mechanical  # pyright: ignore[reportMissingTypeStubs]

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._server.exceptions import MalformedSolutionError
from ansys.saf.glow.solution import (
    InstanceManager,
    ProductInstanceManager,
    RecoveryStateInfo,
)
from ansys.saf.product_manager._utilities.const import (
    ANSYS_GRPC_CERTIFICATES,
    INSECURE_GRPC_MSG,
)

logger = logging.getLogger(__name__)


class MechanicalStateInfo(RecoveryStateInfo):
    project_files: list[EntityHandle] = []  # retained for backwards compatibility
    downloaded_files: list[str] = []


class InternalMechanicalManager(InstanceManager[Mechanical, MechanicalStateInfo]):
    """A private class to manage a Mechanical instance with secure gRPC connections.

    Mechanical implements its own project directory, where all files are uploaded to/generated/downloaded from.
    It is not configurable. Thus, this manager:
    - stores a copy of it in GLOW's product space when saving the instance state
    - loads a copy of it from GLOW's product space when restoring the instance state
    The user must use pymechanical's upload()/download() to move files to the product working directory.
    Using this manager's upload()/download() will only move them to the product space.
    """

    PRODUCT_NAME = "mechanical-secure"
    SERVICE_NAME = "grpc"

    def initialize(self, version: str | None = None):
        """Initialize and start the Mechanical server."""
        self.initialize_service(self.SERVICE_NAME, version)
        self.recovery_state_info = MechanicalStateInfo()

    @classmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of Mechanical in the PIM environment."""
        return cls.PRODUCT_NAME

    def get_client_object_implement(self, hostname: str, port: int) -> Mechanical:
        """Return an instance of Mechanical's client given the host and port of the shared product instance."""
        service = self._get_service()

        if service.secure_flags is None:
            logger.warning(INSECURE_GRPC_MSG)
            return Mechanical(
                ip=hostname,
                port=port,
                transport_mode="insecure",
            )
        elif "mtls" in service.secure_flags.lower():
            certs_dir = os.getenv(ANSYS_GRPC_CERTIFICATES, None)
            if certs_dir is None:
                raise RuntimeError(
                    "MTLS transport mode requires certificates directory to be set in environment variable ANSYS_GRPC_CERTIFICATES.",  # noqa: E501
                )
            logger.info(
                "MTLS secure flags found, creating MTLS channel with certificates from %s",
                certs_dir,
            )
            return Mechanical(
                ip=hostname,
                port=port,
                transport_mode="mtls",
                certs_dir=certs_dir,
            )
        elif "wnua" in service.secure_flags.lower():
            logger.info("WNUA secure flag found, creating secure channel.")
            return Mechanical(
                ip=hostname,
                port=port,
                transport_mode="wnua",
            )
        else:
            logger.warning(INSECURE_GRPC_MSG)
            return Mechanical(
                ip=hostname,
                port=port,
                transport_mode="insecure",
            )

    def save_state_implement(self) -> None:
        """Save the state of Mechanical instance to the given directory."""
        self.recovery_state_info.downloaded_files = self.instance.download_project(target_dir=str(self.state_directory))  # type: ignore
        logger.debug(
            f"Downloaded files from Mechanical instance: {self.recovery_state_info.downloaded_files}",
        )
        # TODO: Save/load state of the mechanical session

    def load_state_implement(self) -> None:
        """Loads the state of Mechanical instance from the given directory."""

        if self.recovery_state_info.project_files:
            # load from old schema
            for handle in self.recovery_state_info.project_files:
                if handle.original_name is None:
                    raise MalformedSolutionError(
                        "Original name of project file is None.",
                    )
                self.copy_to_state_directory(handle, Path(handle.original_name))
                self.instance.upload(str(self.state_directory / handle.original_name))  # type: ignore
        else:
            # load from new schema
            for file in self.recovery_state_info.downloaded_files:
                self.instance.upload(file)  # type: ignore
        logger.debug(
            f"Uploaded files to Mechanical instance: {self.instance.list_files()}",
        )

    def shutdown_implement(self) -> None:
        """Gracefully terminates Mechanical instance process."""
        self.instance.exit()


class MechanicalManager(
    ProductInstanceManager[Mechanical, MechanicalStateInfo],
    instance_manager_impl_type=InternalMechanicalManager,
):
    """A manager of a `Mechanical <https://www.ansys.com/en-gb/products/structures/ansys-mechanical>`_
    product instance with secure gRPC connections."""

    def __init__(self, **kwargs: Any):
        """Initialize and start a Mechanical instance with secure gRPC connections.

        Parameters
        ----------
        version : str, optional
            The version of the Mechanical instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None):
        """Initialize and start a Mechanical instance with secure gRPC connections.

        Parameters
        ----------
        version : str, optional
            The version of the Mechanical instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        # Mandatory call to the base implementation of ``start``, passing the values of the arguments of this method.
        super().start(version=version)
