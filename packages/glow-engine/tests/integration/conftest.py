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

import os
from pathlib import Path
import platform
from unittest import mock

import grpc
import httpx2
import pytest

from ansys.saf.glow._config.const import LOCALHOST_HOSTS
from ansys.saf.glow._core.instance.hps_system import HpsSystemFactory
from ansys.saf.glow._core.instance.iinstance_system import (
    IProductInstance,
    IProductInstanceSystem,
    IProductInstanceSystemFactory,
)
from ansys.saf.glow._core.instance.mock_system import MockProductInstance, MockSystemFactory
from ansys.saf.glow._core.instance.null_system import NullSystemFactory
from ansys.saf.glow._core.instance.pim_system import ExternalPimSystemFactory, LocalPimSystemFactory
from ansys.saf.glow._hps_auth.hps_authenticator import DesktopHpsAuthenticator
from ansys.saf.glow._utilities.ip_utilities import get_random_free_port, wait_for_response
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.process import Process
from ansys.saf.testing.solution.const import TestProductInstanceSystemType
from tests.mocks.mock_products.client import (
    IMockProductClient,
    MockGrpcProductClient,
    MockHttpProductClient,
    MockSystemProductClient,
    MockTcpProductClient,
)

LATEST_PRODUCT_VERSION = "222"


class BasicGlowProcess(Process):
    """Thin wrapper around :class:`Process` that picks a free port and exposes a health-check helper."""

    def __init__(self, args: list[str], cwd: Path, env: dict[str, str]) -> None:
        self._port = get_random_free_port()
        args.extend(["--port", str(self._port)])
        super().__init__(args, env=env, cwd=cwd, bg=True)

    @property
    def port(self) -> int:
        return self._port

    def wait_for_healthy(self) -> None:
        tries = 20 if platform.system() == "Windows" else 30
        wait_for_response(f"http://localhost:{self._port}/health", tries=tries, interval=0.25)


@pytest.fixture(scope="module", autouse=True)
def mock_appdata(tmp_path_factory: pytest.TempPathFactory) -> YieldFixture[Path]:
    """Redirect APPDATA / XDG_DATA_HOME to a temporary directory so each test
    module works in isolation and concurrent runs do not collide."""
    tmp_appdata = tmp_path_factory.getbasetemp() / "appdata"
    with mock.patch.dict(os.environ, {"APPDATA": str(tmp_appdata), "XDG_DATA_HOME": str(tmp_appdata)}):
        yield tmp_appdata


def get_instance_client(instance: IProductInstance, product_name: str) -> IMockProductClient:
    if isinstance(instance, MockProductInstance):
        client = MockSystemProductClient(instance._instance_file_path)  # pyright: ignore[reportPrivateUsage]
    elif product_name == "custom-grpc-product":
        service = instance.services["grpc"]
        client = MockGrpcProductClient(service.port)
    elif product_name == "custom-http-product":
        service = instance.services["http"]
        client = MockHttpProductClient(service.port)
    else:
        service = instance.services["tcp"]
        client = MockTcpProductClient(service.port)
    return client


def assert_instance(instance: IProductInstance, product_name: str, product_version: str | None = None) -> None:
    assert instance.is_healthy()
    client = get_instance_client(instance, product_name)
    assert client.the_property == "blue"
    # instance system defaults to launching latest product version if not specified
    assert client.server_version == product_version or LATEST_PRODUCT_VERSION


def assert_instance_deleted(instance: IProductInstance, product_name: str) -> None:
    client = get_instance_client(instance, product_name)
    with pytest.raises((grpc.RpcError, httpx2.ConnectError, ConnectionRefusedError, FileNotFoundError)):
        _ = client.the_property


@pytest.fixture
def product_instance_system_factory(
    instance_system_type: TestProductInstanceSystemType | None,
    certificates_directory: Path,
    pim_host: str,
) -> IProductInstanceSystemFactory:
    match instance_system_type:
        case TestProductInstanceSystemType.HPS:
            # TODO: should depend on deployment type
            hps_authenticator = DesktopHpsAuthenticator(
                glow_api_url="",
                client_id="rep-jms-web",
                glow_hps_username="repadmin",
                glow_hps_password="repadmin",
            )
            return HpsSystemFactory(hps_authenticator)
        case TestProductInstanceSystemType.PIM:
            if pim_host in LOCALHOST_HOSTS:
                return LocalPimSystemFactory()
            else:
                return ExternalPimSystemFactory(certificates_directory)
        case TestProductInstanceSystemType._MOCK:  # pyright: ignore[reportPrivateUsage]
            return MockSystemFactory()
        case _:
            return NullSystemFactory()


@pytest.fixture
def product_instance_system_uri(
    product_instance_system_factory: IProductInstanceSystemFactory,
    pim_uri: str | None,
    hps_port: int | None,
) -> str:
    if isinstance(product_instance_system_factory, LocalPimSystemFactory | ExternalPimSystemFactory):
        return pim_uri  # type: ignore
    elif isinstance(product_instance_system_factory, HpsSystemFactory):
        return f"https://localhost:{hps_port}/hps"
    else:
        return ""  # not needed for Mock or Null systems


def create_product_instance_system(
    product_instance_system_factory: IProductInstanceSystemFactory,
    product_instance_system_uri: str,
) -> IProductInstanceSystem:
    # keeping outside of a fixture to be able to call it in the tests and capture the logs generated.

    # Load mock instance configurations into Product System
    mock_instance_configs_dir = Path(__file__).parent.parent / "mocks" / "product_instance_configs"
    assert mock_instance_configs_dir.is_dir()
    product_instance_system = product_instance_system_factory.create_system(product_instance_system_uri)
    product_instance_system._configurations_manager.load_configurations(  # pyright: ignore[reportPrivateUsage]
        mock_instance_configs_dir,
    )
    return product_instance_system


@pytest.fixture
def product_instance_system(
    product_instance_system_factory: IProductInstanceSystemFactory,
    product_instance_system_uri: str,
) -> IProductInstanceSystem:
    return create_product_instance_system(product_instance_system_factory, product_instance_system_uri)
