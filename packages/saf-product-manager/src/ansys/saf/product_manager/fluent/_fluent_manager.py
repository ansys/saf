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
from typing import TYPE_CHECKING, Any, TypeVar

from ansys.fluent.core import connect_to_fluent  # pyright: ignore[reportMissingTypeStubs]
from ansys.fluent.core.session_meshing import Meshing  # pyright: ignore[reportMissingTypeStubs]
from ansys.fluent.core.session_pure_meshing import PureMeshing  # pyright: ignore[reportMissingTypeStubs]
from ansys.fluent.core.session_solver import Solver  # pyright: ignore[reportMissingTypeStubs]
from ansys.fluent.core.session_solver_icing import SolverIcing  # pyright: ignore[reportMissingTypeStubs]
import httpx2

from ansys.saf.glow.solution import InstanceManager, ProductInstanceManager, RecoveryStateInfo
from ansys.saf.product_manager._utilities.const import ANSYS_GRPC_CERTIFICATES, INSECURE_GRPC_MSG

if TYPE_CHECKING:
    from pathlib import Path

T = TypeVar("T", Meshing, PureMeshing, Solver, SolverIcing)

logger = logging.getLogger(__name__)


class FluentStateInfo(RecoveryStateInfo):
    pass


class AbstractFluentInternalManager(InstanceManager[T, FluentStateInfo]):
    """Private class to manage a generic Fluent instance using secure gRPC connections.

    Fluent uses the current working directory of the process as the project directory,
    where all files are uploaded to/generated/downloaded from. This directory is set
    by the wrapper in saf-product-configuration and we configure it to be GLOW's product space
    so we don't need to synchronize files between both directories and all files are automatically
    preserved between reinitializations.
    """

    SERVICE_NAME = "http"

    def initialize(self, version: str | None = None):
        """Initialize and start the Fluent server."""
        try:
            self.initialize_service(self.SERVICE_NAME, version)
        except Exception:
            logger.exception("")
            raise

        self.recovery_state_info = FluentStateInfo()
        self._launch_fluent_instance()

    def _launch_fluent_instance(self) -> None:
        service = self._get_service()
        try:
            httpx2.post(
                f"http://{service.host}:{service.port}/start",
                json={"working_dir": self.state_directory.as_posix()},
                timeout=300,
            ).raise_for_status()
        except Exception as e:
            logger.error(str(e))
            raise

    def get_client_object_implement(self, hostname: str, port: int) -> T:
        """Connect to the Fluent app and provides an API to control it."""
        # We need to launch here the instance because when the instance is re-initialized,
        # this is executed before load_state_implement is called. It shouldn't be an issue
        # because the wrapper supports calling the launch multiple times, and this method
        # is cached within a transaction method.
        self._launch_fluent_instance()

        # sifile contains all the required information (host, port, socket path, password) to connect to the
        # Fluent instance. No need to ask the wrapper for the info.
        state_directory_on_solution = (
            self._project_directory_path_on_solution / self.recovery_state_info.product_instance_state_dirname
        )
        sifile_path: Path | None = None
        for file in sorted(state_directory_on_solution.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
            # Pick latest one created, there can be multiple sifile-*.txt files, because we reuse the same state dir
            # for every re-initialization of the instance.
            if file.name.startswith("sifile-") and file.suffix == ".txt":
                sifile_path = file
                break
        if not sifile_path:
            raise RuntimeError("Fluent server info file not found in the state directory.")

        fluent_info = sifile_path.read_text().splitlines()
        fluent_address = fluent_info[0]  # can be ip:port or unix:/socket/path.sock
        fluent_password = fluent_info[1]

        # For None, mtls or unknown, we cannot pass the server_info_file_name because the host within is the
        # binding host (or socket path). Except for UDS/WNUA scenarios, binding host can be different than product host.
        service = self._get_service()
        if service.secure_flags is None:
            logger.warning(INSECURE_GRPC_MSG)
            fluent_port = int(fluent_address.split(":")[1])
            return connect_to_fluent(  # pyright: ignore[reportReturnType]
                ip=hostname,
                port=fluent_port,
                password=fluent_password,
                cleanup_on_exit=False,
                allow_remote_host=True,
                insecure_mode=True,
            )
        elif "mtls" in service.secure_flags.lower():
            certs_dir = os.getenv(ANSYS_GRPC_CERTIFICATES, None)
            if certs_dir is None:
                raise RuntimeError(
                    "MTLS transport mode requires certificates directory to be set in environment variable ANSYS_GRPC_CERTIFICATES.",  # noqa: E501
                )
            logger.info("MTLS secure flags found, creating MTLS channel with certificates from %s", certs_dir)
            fluent_port = int(fluent_address.split(":")[1])
            return connect_to_fluent(  # pyright: ignore[reportReturnType]
                ip=hostname,
                port=fluent_port,
                password=fluent_password,
                cleanup_on_exit=False,
                allow_remote_host=True,
                certificates_folder=certs_dir,
            )
        elif "uds" in service.secure_flags.lower():
            logger.info("UDS secure flags found, creating UDS channel with socket_path=%s", fluent_address)
            return connect_to_fluent(  # pyright: ignore[reportReturnType]
                server_info_file_name=sifile_path.as_posix(),
                cleanup_on_exit=False,
            )
        elif "wnua" in service.secure_flags.lower():
            logger.info("WNUA secure flag found, creating secure channel.")
            return connect_to_fluent(  # pyright: ignore[reportReturnType]
                server_info_file_name=sifile_path.as_posix(),
                cleanup_on_exit=False,
            )
        else:
            logger.warning(INSECURE_GRPC_MSG)
            fluent_port = int(fluent_address.split(":")[1])
            return connect_to_fluent(  # pyright: ignore[reportReturnType]
                ip=hostname,
                port=fluent_port,
                password=fluent_password,
                cleanup_on_exit=False,
                allow_remote_host=True,
                insecure_mode=True,
            )

    def close_client_object_implement(self) -> None:
        """Close Fluent client."""
        self.instance.exit()  # type: ignore

    def save_state_implement(self) -> None:
        """Save the state of Fluent instance to the given directory."""
        # TODO: Save/load state of the fluent session

    def load_state_implement(self) -> None:
        """Load the state of Fluent instance from the given directory."""

    def shutdown_implement(self) -> None:
        """Shutdown the Fluent instance and all of its associated processes."""
        service = self._get_service()
        httpx2.post(f"http://{service.host}:{service.port}/shutdown", timeout=100).raise_for_status()


class Fluent3DDPSolverInternalManager(AbstractFluentInternalManager[Solver]):
    """Private class to manage a Fluent Solver 3DDP instance using secure gRPC connections."""

    PRODUCT_NAME = "fluent-3ddp-solver-secure"

    @classmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of Fluent Solver 3DDP in the PIM environment."""
        return cls.PRODUCT_NAME


class Fluent3DDPSolverManager(
    ProductInstanceManager[Solver, FluentStateInfo],
    instance_manager_impl_type=Fluent3DDPSolverInternalManager,
):
    """A manager of a `Fluent <https://www.ansys.com/en-gb/products/fluids/ansys-fluent>`_ product instance
    in 3D Solver mode with double precision using secure gRPC connections."""

    def __init__(self, **kwargs: Any):
        """Initialize and start a Fluent Solver 3DDP product instance.

        Parameters
        ----------
        version : str, optional
            The version of the Fluent product instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None):
        """Initialize and start a Fluent Solver 3DDP product instance.

        Parameters
        ----------
        version : str, optional
            The version of the Fluent product instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().start(version=version)


class Fluent2DDPSolverInternalManager(AbstractFluentInternalManager[Solver]):
    """Private class to manage a Fluent Solver 2DDP instance using secure gRPC connections."""

    PRODUCT_NAME = "fluent-2ddp-solver-secure"

    @classmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of Fluent Solver 2DDP in the PIM environment."""
        return cls.PRODUCT_NAME


class Fluent2DDPSolverManager(
    ProductInstanceManager[Solver, FluentStateInfo],
    instance_manager_impl_type=Fluent2DDPSolverInternalManager,
):
    """A manager of a `Fluent <https://www.ansys.com/en-gb/products/fluids/ansys-fluent>`_ product instance
    in 2D Solver mode with double precision using secure gRPC connections."""

    def __init__(self, **kwargs: Any):
        """Initialize and start a Fluent Solver 2DDP product instance.

        Parameters
        ----------
        version : str, optional
            The version of the Fluent product instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None):
        """Initialize and start a Fluent Solver 2DDP product instance.

        Parameters
        ----------
        version : str, optional
            The version of the Fluent product instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().start(version=version)


class Fluent3DDPMeshingInternalManager(AbstractFluentInternalManager[Meshing]):
    """Private class to manage a Fluent Meshing 3DDP instance using secure gRPC connections."""

    PRODUCT_NAME = "fluent-3ddp-meshing-secure"

    @classmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of Fluent Meshing 3DDP in the PIM environment."""
        return cls.PRODUCT_NAME


class Fluent3DDPMeshingManager(
    ProductInstanceManager[Meshing, FluentStateInfo],
    instance_manager_impl_type=Fluent3DDPMeshingInternalManager,
):
    """A manager of a `Fluent <https://www.ansys.com/en-gb/products/fluids/ansys-fluent>`_ product instance
    in 3D Meshing mode with double precision using secure gRPC connections."""

    def __init__(self, **kwargs: Any):
        """Initialize and start a Fluent Meshing 3DDP product instance.

        Parameters
        ----------
        version : str, optional
            The version of the Fluent product instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None):
        """Initialize and start a Fluent Meshing 3DDP product instance.

        Parameters
        ----------
        version : str, optional
            The version of the Fluent product instance that must be used. The format is 3 decimal digits where
            the first two digits indicate the year of release in the 21st century and the third digit indicates
            the release within that year.
        """
        super().start(version=version)
