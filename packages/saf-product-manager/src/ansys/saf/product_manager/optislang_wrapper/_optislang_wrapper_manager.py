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

from collections.abc import Iterator
from contextlib import contextmanager
import logging
from pathlib import PurePath
from typing import Any

from ansys.optislang.core import Optislang  # pyright: ignore[reportMissingTypeStubs]
from ansys.optislang.core.communication_channels import (  # pyright: ignore[reportMissingTypeStubs]
    CommunicationChannel,
)
import httpx2

from ansys.saf.glow.solution import InstanceManager, ProductInstanceManager, RecoveryStateInfo
from ansys.saf.product_manager._utilities.const import DEFAULT_SAF_OPTISLANG_TIMEOUT, LOCALHOSTS, SAF_OPTISLANG_TIMEOUT
from ansys.saf.product_manager._utilities.timeout_utilities import get_timeout_from_environment

CONNECTION_MODE_LOCAL_DOMAIN = "LOCAL_DOMAIN"
CONNECTION_MODE_TCP = "TCP"

logger = logging.getLogger(__name__)


class OslClient:
    def __init__(
        self,
        host: str,
        port: int,
        connection_mode: str = CONNECTION_MODE_LOCAL_DOMAIN,
        timeout: int = DEFAULT_SAF_OPTISLANG_TIMEOUT,
    ):
        """Creating a new OptislangWrapperClient instance with the given host and port."""
        self._host = host
        self._port = port
        self._connection_mode = connection_mode
        self._timeout = timeout

    @contextmanager
    def optislang_client(self, loglevel: str = "INFO") -> Iterator[Optislang]:
        response = httpx2.get(f"http://{self._host}:{self._port}/connection", timeout=self._timeout)
        response.raise_for_status()
        connection_info = response.json()
        if connection_info["connection_mode"] == CONNECTION_MODE_TCP:
            osl = Optislang(
                host=self._host,
                port=connection_info["port"],
                communication_channel=CommunicationChannel.TCP,
                loglevel=loglevel,
            )
        else:
            osl = Optislang(
                local_server_id=connection_info["local_server_id"],
                communication_channel=CommunicationChannel.LOCAL_DOMAIN,
                loglevel=loglevel,
            )
        with osl:
            yield osl

    def start(
        self,
        project_path: PurePath,
        project_properties_file: PurePath,
        input_files: list[PurePath],
        osl_version: str,
        loglevel: str,
        connection_mode: str | None = None,
    ):
        """Initialize and start an optiSLang product instance.

        Parameters
        ----------
        project_path : PurePath
            Optislang .opf file
        project_properties_file : PurePath
            Optislang placeholders file, typically called working_properties_file.json
        input_files : list[PurePath]
            List of input files required by Optislang. If no input files are required, pass an empty list.
        osl_version : str
            The custom product version of the optiSLang instance. The format is 3 digits string. Example: "241"
        loglevel : str
            oSL Logging level. Example: INFO
        connection_mode : str
            Connection mode used by the wrapper to launch the optiSLang server. Example: LOCAL_DOMAIN
        """
        httpx2.post(
            f"http://{self._host}:{self._port}/start",
            json={
                "project_path": project_path.as_posix(),
                "project_properties_file": project_properties_file.as_posix(),
                "input_files": [input_file.as_posix() for input_file in input_files],
                "osl_version": int(osl_version),
                "loglevel": loglevel,
                "connection_mode": connection_mode or self._connection_mode,
            },
            timeout=self._timeout,
        ).raise_for_status()

    def get_logs(self) -> str | None:
        response = httpx2.get(f"http://{self._host}:{self._port}/logs", timeout=self._timeout)
        response.raise_for_status()
        logs = response.content.decode()
        return logs

    def shutdown(self) -> None:
        httpx2.post(f"http://{self._host}:{self._port}/shutdown", timeout=self._timeout).raise_for_status()

    def close_optislang(self) -> None:
        httpx2.post(f"http://{self._host}:{self._port}/close-optislang", timeout=self._timeout).raise_for_status()


class OptislangStateInfo(RecoveryStateInfo):
    pass


class InternalOptislangManagerImpl(InstanceManager[OslClient, OptislangStateInfo]):
    """A manager of a secure `optiSLang <https://www.ansys.com/en-gb/products/connect/ansys-optislang>`_
    product instance, accessed through the optiSLang wrapper service.
    """

    PRODUCT_NAME = "optislang-wrapper-secure"
    SERVICE_NAME = "http"

    def initialize(
        self,
        version: str | None = None,
    ):
        """Initialize secure optiSLang wrapper service without deprecation warning."""

        self.initialize_service(self.SERVICE_NAME, product_version=version)

        service = self._get_service()

        self.recovery_state_info = OptislangStateInfo()

        if not service:
            raise RuntimeError("Service not initialized.")

    @staticmethod
    def get_connection_mode_for_secure_flags(secure_flags: str | None, hostname: str | None = None) -> str:
        if secure_flags is None:
            logger.warning("No secure flags found for optiSLang wrapper. Falling back to insecure TCP.")
            return CONNECTION_MODE_TCP

        secure_flags_lower = secure_flags.lower()
        if "uds" in secure_flags_lower or "wnua" in secure_flags_lower:
            return CONNECTION_MODE_LOCAL_DOMAIN
        if "mtls" in secure_flags_lower:
            logger.warning(
                "MTLS secure flag found for optiSLang wrapper but MTLS is not supported yet. "
                "Falling back to insecure TCP.",
            )
            return CONNECTION_MODE_TCP
        if "insecure" in secure_flags_lower:
            # PIM currently reports insecure flags for secure products because it cannot
            # distinguish between local secure modes (WNUA/UDS) and insecure transport.
            # When service host is local, we should still use LOCAL_DOMAIN for optiSLang.
            # This is going to launch optiSLang in secure local mode. In comparison with
            # other products, this does not only affect the client, as there is a wrapper.
            if hostname in LOCALHOSTS:
                return CONNECTION_MODE_LOCAL_DOMAIN
            logger.warning("Insecure flag found for optiSLang wrapper. Using TCP connection mode.")
            return CONNECTION_MODE_TCP

        logger.warning(
            "Unknown secure flags '%s' for optiSLang wrapper. Falling back to insecure TCP.",
            secure_flags,
        )
        return CONNECTION_MODE_TCP

    def get_client_object_implement(self, hostname: str, port: int) -> OslClient:
        """Return an instance of the custom product's client given the host and port of the shared product instance."""
        service = self._get_service()
        connection_mode = self.get_connection_mode_for_secure_flags(
            service.secure_flags if service else None,
            hostname,
        )
        return OslClient(
            hostname,
            port,
            connection_mode,
            timeout=get_timeout_from_environment(SAF_OPTISLANG_TIMEOUT, DEFAULT_SAF_OPTISLANG_TIMEOUT),
        )

    @classmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of the product in the PIM environment."""
        return cls.PRODUCT_NAME

    def save_state_implement(self) -> None:
        """Save the state of the product instance to the given directory."""

    def load_state_implement(self) -> None:
        """Loads the state of the product instance from the given directory."""

    def shutdown_implement(self) -> None:
        """Gracefully terminates the product instance process."""
        self.instance.shutdown()


class OslManager(
    ProductInstanceManager[OslClient, OptislangStateInfo],
    instance_manager_impl_type=InternalOptislangManagerImpl,
):
    """A manager of an `OptiSLang <https://www.ansys.com/en-gb/products/connect/ansys-optislang>`_ product instance."""

    def __init__(self, **kwargs: Any):
        """Initialize an optiSLang product instance. OptiSLang is not started here.
        To start it, call the start method on the instance after initialization."""
        # Mandatory call to the base class!
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None):
        """Initialize an optiSLang product instance. OptiSLang is not started here.
        To start it, call the start method on the instance after initialization."""
        super().start(version=version)
