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
import socket

import grpc
from grpc_health.v1 import (
    health_pb2,
    health_pb2_grpc,
)

from ansys.saf.glow._core.instance.iinstance_system import IHealthClient, IHealthClientFactory, IProductInstanceService
from ansys.saf.glow._utilities.ip_utilities import try_response
from ansys.saf.product_configuration.interfaces import IProductInstanceVersionConfiguration, ServiceType

logger = logging.getLogger(__name__)


class GrpcHealthClient(IHealthClient):
    def __init__(
        self,
        host: str,
        port: int,
        health_route: str,
        uds_dir: str | None = None,
        uds_id: str | None = None,
        secure_flags: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._health_route = health_route
        self._uds_dir = uds_dir
        self._uds_id = uds_id
        self._secure_flags = secure_flags.lower() if secure_flags else None
        self._channel: grpc.Channel | None = None
        self._health_stub: health_pb2_grpc.HealthStub | None = None

    def _create_channel(self, host: str, port: int, health_route: str) -> grpc.Channel:
        if self._secure_flags is None:
            logger.warning(
                f"Health check: creating insecure grpc channel with uri={host}:{port}{health_route} "
                + "and localhost as default authority",
            )
            options = (("grpc.default_authority", "localhost"),)
            return grpc.insecure_channel(f"{host}:{port}{health_route}", options=options)

        if "mtls" in self._secure_flags:
            if certs_dir := os.getenv("ANSYS_GRPC_CERTIFICATES"):
                certificates_dir = Path(certs_dir)
                creds = grpc.ssl_channel_credentials(
                    root_certificates=(certificates_dir / "ca.crt").read_bytes(),
                    private_key=(certificates_dir / "client.key").read_bytes(),
                    certificate_chain=(certificates_dir / "client.crt").read_bytes(),
                )
                logger.info(
                    f"Health check: creating secure grpc channel with uri={host}:{port}{health_route}"
                    + f" and certificates={certificates_dir}",
                )
                return grpc.secure_channel(f"{host}:{port}{health_route}", creds)
            else:
                # fallback to insecure
                logger.warning(
                    f"Health check: creating insecure grpc channel with uri={host}:{port}{health_route}"
                    + " without certificates",
                )
                return grpc.insecure_channel(f"{host}:{port}{health_route}")
        elif "uds" in self._secure_flags and self._uds_dir and self._uds_id:
            # (host is localhost, so we assume that the product instance is running on the same host as glow)
            socket_paths = list(
                Path(self._uds_dir).glob(f"*{self._uds_id}*.sock"),
            )
            if len(socket_paths) != 1:
                raise RuntimeError("Unable to find unique socket file for UDS health check.")
            target = f"unix:{socket_paths[0]}"
            options = (("grpc.default_authority", "localhost"),)
            logger.info(
                f"Health check: creating secure grpc channel with uri={target}",
            )
            return grpc.insecure_channel(target=target, options=options)
        elif "wnua" in self._secure_flags:
            options = (("grpc.default_authority", "localhost"),)
            target = f"{host}:{port}{health_route}"
            logger.info(
                f"Health check: creating wnua secure grpc channel with uri={target}",
            )
            return grpc.insecure_channel(f"{target}", options=options)
        else:
            logger.warning(
                f"Health check: creating insecure grpc channel with uri={host}:{port}{health_route} "
                + "and localhost as default authority",
            )
            options = (("grpc.default_authority", "localhost"),)
            return grpc.insecure_channel(f"{host}:{port}{health_route}", options=options)

    def _get_or_create_health_stub(self) -> health_pb2_grpc.HealthStub:
        """Lazily creates the gRPC channel and health stub on first use and caches it.

        For UDS connections the socket file may not exist in the first health check. If creation fails,
        no channel is cached and the next call will retry, allowing UDS to eventually succeed once the socket appears.
        For non-UDS connections the channel is created the first time and reused.
        """
        if self._channel is None:
            self._channel = self._create_channel(self._host, self._port, self._health_route)
        if self._health_stub is None:
            self._health_stub = health_pb2_grpc.HealthStub(self._channel)
        return self._health_stub

    def is_healthy(self) -> bool:
        try:
            health_stub = self._get_or_create_health_stub()
            request = health_pb2.HealthCheckRequest(service="")
            resp = health_stub.Check(request)  # type: ignore
        except Exception:
            return False
        return resp.status == health_pb2.HealthCheckResponse.SERVING  # type: ignore

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
        if self._health_stub is not None:
            self._health_stub = None


class HttpHealthClient(IHealthClient):
    def __init__(self, host: str, port: int, health_route: str) -> None:
        self._health_url = f"http://{host}:{port}{health_route}"

    def is_healthy(self) -> bool:
        return try_response(self._health_url)

    def close(self) -> None: ...


class TcpHealthClient(IHealthClient):
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def is_healthy(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.connect((self._host, self._port))
                return True
            except Exception:
                return False

    def close(self) -> None: ...


class GrpcHealthClientFactory(IHealthClientFactory):
    def __init__(self, health_route: str | None = None) -> None:
        self._health_route = health_route if health_route is not None else ""

    def create_client(self, service: IProductInstanceService) -> IHealthClient:
        return GrpcHealthClient(
            host=service.host,
            port=service.port,
            health_route=self._health_route,
            uds_dir=service.uds_dir,
            uds_id=service.uds_id,
            secure_flags=service.secure_flags,
        )


class HttpHealthClientFactory(IHealthClientFactory):
    def __init__(self, health_route: str | None = None) -> None:
        self._health_route = health_route if health_route is not None else "/health"

    def create_client(self, service: IProductInstanceService) -> IHealthClient:
        return HttpHealthClient(service.host, service.port, self._health_route)


class TcpHealthClientFactory(IHealthClientFactory):
    def create_client(self, service: IProductInstanceService) -> IHealthClient:
        return TcpHealthClient(service.host, service.port)


def create_health_client_factory(config: IProductInstanceVersionConfiguration) -> IHealthClientFactory:
    """Returns a client that can run a health check on
    the service exposed by the process started by ``execution_command``"""
    if config.service_type == ServiceType.HTTP:
        return HttpHealthClientFactory(config.health_route)
    elif config.service_type == ServiceType.GRPC:
        return GrpcHealthClientFactory(config.health_route)
    elif config.service_type == ServiceType.TCP:
        return TcpHealthClientFactory()
    raise RuntimeError(f"Unsupported service type {config.service_type} for instance management.")
