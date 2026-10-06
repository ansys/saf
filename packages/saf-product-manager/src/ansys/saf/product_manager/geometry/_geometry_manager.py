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
from typing import Any

from ansys.geometry.core.modeler import Modeler

from ansys.saf.glow.solution import InstanceManager, ProductInstanceManager, RecoveryStateInfo
from ansys.saf.product_manager._utilities.const import ANSYS_GRPC_CERTIFICATES, INSECURE_GRPC_MSG

logger = logging.getLogger(__name__)


class GeometryStateInfo(RecoveryStateInfo):
    project_file_saved: bool = False


class InternalGeometryManager(InstanceManager[Modeler, GeometryStateInfo]):
    """A private class to manage a Geometry instance with secure gRPC connections."""

    PRODUCT_NAME = "geometry-secure"
    SERVICE_NAME = "grpc"
    _INSTANCE_STATE_PROJECT_FILE_NAME = "project.scdocx"

    def initialize(self, version: str | None = None):
        """Initialize and start the Geometry server."""
        self.initialize_service(self.SERVICE_NAME, version)
        self.recovery_state_info = GeometryStateInfo()

    @classmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of Geometry in the PIM environment."""
        return cls.PRODUCT_NAME

    def get_client_object_implement(self, hostname: str, port: int) -> Modeler:
        """Connect to the Geometry instance and provides an API to control it."""
        service = self._get_service()

        if service.secure_flags is None:
            logger.warning(INSECURE_GRPC_MSG)
            return Modeler(host=hostname, port=port, transport_mode="insecure")
        elif "mtls" in service.secure_flags.lower():
            certs_dir = os.getenv(ANSYS_GRPC_CERTIFICATES, None)
            if certs_dir is None:
                raise RuntimeError(
                    "MTLS transport mode requires certificates directory to be set in environment variable ANSYS_GRPC_CERTIFICATES.",  # noqa: E501
                )
            logger.info("MTLS secure flags found, creating MTLS channel with certificates from %s", certs_dir)
            return Modeler(host=hostname, port=port, transport_mode="mtls", certs_dir=certs_dir)
        elif "uds" in service.secure_flags.lower():
            if not service.uds_dir or not service.uds_id:
                raise RuntimeError("UDS transport mode requires uds_dir and uds_id.")
            logger.info(
                "UDS secure flags found, creating UDS channel with uds_dir=%s and uds_id=%s",
                service.uds_dir,
                service.uds_id,
            )
            return Modeler(
                host=hostname,
                port=port,
                transport_mode="uds",
                uds_dir=service.uds_dir,
                uds_id=service.uds_id,
            )
        elif "wnua" in service.secure_flags.lower():
            logger.info("WNUA secure flag found, creating secure channel.")
            return Modeler(host=hostname, port=port, transport_mode="wnua")
        else:
            logger.warning(INSECURE_GRPC_MSG)
            return Modeler(host=hostname, port=port, transport_mode="insecure")

    def close_client_object_implement(self) -> None:
        """Close the Modeler client."""
        self.instance.close(close_design=False)

    def save_state_implement(self) -> None:
        """Save changes to the project data and settings."""
        design = self.instance.get_active_design()
        if design:
            design.download(self.project_file_path_for_product)
            self.recovery_state_info.project_file_saved = True
            logger.debug("Saved Geometry project file.")

    @property
    def project_file_path_for_product(self) -> str:
        return str(self.state_directory / self._INSTANCE_STATE_PROJECT_FILE_NAME)

    def load_state_implement(self) -> None:
        if self.recovery_state_info.project_file_saved:
            self.instance.open_file(self.project_file_path_for_product)
            logger.debug("Uploaded design file to Geometry instance.")

    def shutdown_implement(self) -> None:
        """Let GLOW shutdown the instance."""


class GeometryManager(
    ProductInstanceManager[Modeler, GeometryStateInfo],
    instance_manager_impl_type=InternalGeometryManager,
):
    """A manager of a Geometry service instance with secure gRPC connections."""

    def __init__(self, **kwargs: Any):
        """Initialize and start a Geometry service instance with secure gRPC connections.

        Parameters
        ----------
        version : str, optional
            The version of the Geometry service instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None):
        """Initialize and start a Geometry service instance with secure gRPC connections.

        Parameters
        ----------
        version : str, optional
            The version of the Geometry service instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().start(version=version)
