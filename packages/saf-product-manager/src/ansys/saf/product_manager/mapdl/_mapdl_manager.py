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

from ansys.mapdl.core import Mapdl  # pyright: ignore[reportMissingTypeStubs]
from ansys.mapdl.core.errors import MapdlVersionError  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.glow.solution import InstanceManager, ProductInstanceManager, RecoveryStateInfo
from ansys.saf.product_manager._utilities.const import ANSYS_GRPC_CERTIFICATES, INSECURE_GRPC_MSG

logger = logging.getLogger(__name__)


class MapdlStateInfo(RecoveryStateInfo):
    pass


class InternalMapdlManager(InstanceManager[Mapdl, MapdlStateInfo]):
    """A private class to manage a Mapdl instance with secure gRPC connection.

    Mapdl implements its own project directory, and we configure it to be GLOW's product space
    so we don't need to synchronize files between both directories and all files are automatically
    preserved between reinitializations.
    """

    PRODUCT_NAME = "mapdl-secure"
    SERVICE_NAME = "grpc"
    _STATE_DB_FILE_NAME = "mapdl_model.db"

    def initialize(self, version: str | None = None):
        """Initialize and start the Mapdl server."""
        self.initialize_service(self.SERVICE_NAME, version)
        self.recovery_state_info = MapdlStateInfo()
        self.instance.directory = self.state_directory  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of Mapdl in the PIM environment."""
        return cls.PRODUCT_NAME

    def get_client_object_implement(self, hostname: str, port: int) -> Mapdl:
        """Return an instance of Mapdl's client given the host and port of the shared product instance."""
        service = self._get_service()
        if service.secure_flags is None:
            logger.warning(INSECURE_GRPC_MSG)
            return Mapdl(ip=hostname, port=port, transport_mode="insecure")
        elif "mtls" in service.secure_flags.lower():
            certs_dir = os.getenv(ANSYS_GRPC_CERTIFICATES, None)
            if certs_dir is None:
                raise RuntimeError(
                    "MTLS transport mode requires certificates directory to be set in environment variable ANSYS_GRPC_CERTIFICATES.",  # noqa: E501
                )
            logger.info("MTLS secure flags found, creating MTLS channel with certificates from %s", certs_dir)
            return Mapdl(ip=hostname, port=port, transport_mode="mtls", certs_dir=certs_dir)
        elif "uds" in service.secure_flags.lower():
            if not service.uds_dir or not service.uds_id:
                raise RuntimeError("UDS transport mode requires uds_dir and uds_id.")
            logger.info(
                "UDS secure flags found, creating UDS channel with uds_dir=%s and uds_id=%s",
                service.uds_dir,
                service.uds_id,
            )
            # it's expected that port == uds_id, and pymapdl will use it to find the file in uds_dir.
            return Mapdl(
                ip=hostname,
                port=port,
                transport_mode="uds",
                uds_dir=service.uds_dir,
            )
        elif "wnua" in service.secure_flags.lower():
            logger.info("WNUA secure flag found, creating secure channel.")
            return Mapdl(ip=hostname, port=port, transport_mode="wnua")
        else:
            logger.warning(INSECURE_GRPC_MSG)
            return Mapdl(ip=hostname, port=port, transport_mode="insecure")

    def save_state_implement(self) -> None:
        # In pymapdl 0.68.0, MAPDL 24R1 was compatible with the database module. Then, in pymapdl 0.68.1,
        # they added 24R1 to the list of incompatible versions, which includes 24R2 too.
        # However, even if we don't explicitly save it, it seems that MAPDL automatically saves/loads
        # the db from a file named "file.db"
        try:
            self.instance.save(self._STATE_DB_FILE_NAME)  # type: ignore
        except MapdlVersionError:
            logger.warning("Could not save MAPDL DB. This MAPDL version is not compatible with the Database module.")

    def load_state_implement(self) -> None:
        self.instance.directory = self.state_directory  # pyright: ignore[reportAttributeAccessIssue]
        try:
            self.instance.resume(self._STATE_DB_FILE_NAME)  # pyright: ignore[reportUnknownMemberType]
        except MapdlVersionError:
            logger.warning("Could not load MAPDL DB. This MAPDL version is not compatible with the Database module.")

    def shutdown_implement(self) -> None:
        """Gracefully terminates Mapdl instance process."""
        self.instance.exit(force=True)  # pyright: ignore[reportUnknownMemberType]


class MapdlManager(
    ProductInstanceManager[Mapdl, MapdlStateInfo],
    instance_manager_impl_type=InternalMapdlManager,
):
    """A manager of a MAPDL product instance."""

    def __init__(self, **kwargs: Any):
        """Initialize and start a Mapdl instance.

        Parameters
        ----------
        version : str, optional
            The version of the Mapdl instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None):
        """Initialize and start a Mapdl instance.

        Parameters
        ----------
        version : str, optional
            The version of the Mapdl instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        # Mandatory call to the base implementation of ``start``, passing the values of the arguments of this method.
        super().start(version=version)
