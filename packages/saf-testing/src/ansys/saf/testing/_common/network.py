# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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

from enum import Enum
from pathlib import Path
import platform
import socket
import subprocess

import pytest

from ansys.saf.testing._common.grpc_certificates import (
    create_ca_certificate,
    create_client_certificate,
    generate_private_key,
    generate_server_certificates,
    save_certificate,
    save_private_key,
)


def get_random_free_port() -> int:
    """Return a free socket port. Handled by the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("", 0))
            return sock.getsockname()[1]
        except OSError as err:
            raise OSError("no free ports") from err


def get_local_ip() -> str:
    """Return the unique ipv4 address of this node."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def get_docker_gateway_ip() -> str:
    p = subprocess.run("ip route | awk '/docker0/ {print $9}'", capture_output=True, text=True, shell=True)
    if p.returncode != 0:
        raise Exception("Can't get default docker gateway IP")
    return p.stdout.strip()


@pytest.fixture(scope="session")
def docker_gateway_ip(deployment_type: Enum) -> str:
    from ansys.saf.glow.client import Deployment  # pyright: ignore[reportMissingImports]

    if deployment_type == Deployment.MultiContainer and platform.system() == "Linux":
        return get_docker_gateway_ip()
    else:
        return "127.0.0.1"


@pytest.fixture(scope="session")
def local_ip() -> str:
    return get_local_ip()


@pytest.fixture(scope="session")
def certificates_directory(
    tmp_path_factory: pytest.TempPathFactory,
    local_ip: str,
    docker_gateway_ip: str,
    hps_host: str,
) -> Path:
    """Create localhost server and client certificates signed by a local CA. The validity is one day."""

    output_dir = tmp_path_factory.mktemp("certs-")

    servers = [
        f"localhost,127.0.0.1,{local_ip}",
    ]
    if docker_gateway_ip not in servers[0]:
        servers[0] += f",{docker_gateway_ip},host.docker.internal"
    if hps_host not in servers[0]:
        servers[0] += f",{hps_host}"

    days = 1
    client_common_name = "client"

    output_dir.mkdir(exist_ok=True)

    # Generate CA key and certificate for self-signing
    ca_key = generate_private_key()
    ca_cert = create_ca_certificate(ca_key, days)

    save_private_key(ca_key, output_dir / "ca.key")
    save_certificate(ca_cert, output_dir / "ca.crt")

    # Generate server certificates
    generate_server_certificates(ca_cert, ca_key, servers, days, output_dir.as_posix())

    # Generate client key and certificate
    client_key = generate_private_key()
    client_cert = create_client_certificate(client_key, ca_cert, ca_key, client_common_name, days)

    save_private_key(client_key, output_dir / "client.key")
    save_certificate(client_cert, output_dir / "client.crt")

    return output_dir
