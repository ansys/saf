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

from collections.abc import Generator
from copy import deepcopy
import importlib
import logging
from pathlib import Path
import socket
from typing import Any
from unittest import mock
import warnings

import httpx2
import pytest
import pytest_mock

from ansys.saf.glow._config.directories import find_product_instance_configs_dir
from ansys.saf.glow._core.instance.healthcheck import create_health_client_factory
from ansys.saf.glow._core.instance.hps_system import HpsProductInstanceService, HpsSystem
from ansys.saf.product_configuration.manager.configurations_manager import ProductInstanceConfigurationsManager
from ansys.saf.testing.platform_specific import xfail_for_ci
from tests.conftest import MOCKS_DIR


@pytest.fixture
def clean_hps_system() -> Generator[None, None, None]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        original_configs = deepcopy(HpsSystem._configurations_manager)  # type: ignore
    yield
    HpsSystem._configurations_manager = original_configs  # type: ignore


def get_instance_configurations(hps_system: Any, product_type: str) -> list[Any]:
    return [
        configuration
        for configuration in hps_system._configurations_manager._configurations  # type: ignore
        if type(configuration).__name__ == product_type
    ]


@xfail_for_ci(reason="recent flakiness")
@pytest.mark.usefixtures("clean_hps_system")
def test_load_hps_configurations():
    # GIVEN: A clean HpsSystem, without mechanical instance configurations
    assert not get_instance_configurations(HpsSystem, "MyProductInstanceConfiguration")

    # WHEN: Loading instance configurations from python files inside a directory
    configs_dir = (
        Path(__file__).parent.parent.parent
        / "mocks"
        / "solution_with_instance_configurations"
        / "product_instance_configs"
    )
    HpsSystem._configurations_manager.load_configurations(configs_dir)  # pyright: ignore[reportPrivateUsage]

    # THEN: HpsSystem contains mechanical instance configurations
    assert len(get_instance_configurations(HpsSystem, "MyProductInstanceConfiguration")) == 1

    # WHEN: Loading instance configurations twice
    HpsSystem._configurations_manager.load_configurations(configs_dir)  # pyright: ignore[reportPrivateUsage]

    # THEN: HpsSystem doesn't add duplicated instance configurations
    assert len(get_instance_configurations(HpsSystem, "MyProductInstanceConfiguration")) == 1


def test_product_instance_configs_found_from_solution_module():
    solution_module = importlib.import_module("tests.mocks.solution_with_instance_configurations.solution.definition")
    config_path = find_product_instance_configs_dir(solution_module)
    assert config_path
    assert config_path.exists()
    assert config_path == MOCKS_DIR / "solution_with_instance_configurations" / "product_instance_configs"


@pytest.fixture
def extended_mgr():
    mgr = ProductInstanceConfigurationsManager()
    product_instance_configs_dir = Path(__file__).parent.parent.parent / "mocks" / "product_instance_configs"
    assert product_instance_configs_dir.is_dir()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        mgr.load_configurations(product_instance_configs_dir)
    return mgr


@pytest.mark.parametrize("product_name", ["custom-grpc-product", "custom-grpc-product-custom-route"])
def test_mock_grpc_product_health_route(
    extended_mgr: ProductInstanceConfigurationsManager,
    product_name: str,
    mocker: pytest_mock.MockerFixture,
):
    """Test that insecure channel is created when secure_flags does not contain anything."""
    _, configuration = extended_mgr.get_version_configuration(product_name, "222")
    config = HpsProductInstanceService(
        {"host": "127.0.0.1", "port": "50000", "uds_dir": "", "uds_id": "", "secure_flags": ""},
    )
    if product_name == "custom-grpc-product":
        assert configuration.health_route is None
    elif product_name == "custom-grpc-product-custom-route":
        assert configuration.health_route

    health_route = configuration.health_route if configuration.health_route is not None else ""
    expected_health_uri = f"{config.host}:{config.port}{health_route}"

    mock_logger_warn = mocker.patch.object(logging.Logger, "warning")
    grpc_channel = mocker.patch("grpc.insecure_channel")

    client = create_health_client_factory(configuration).create_client(config)
    client.is_healthy()
    options = (("grpc.default_authority", "localhost"),)
    grpc_channel.assert_called_with(expected_health_uri, options=options)
    mock_logger_warn.assert_called_once_with(
        f"Health check: creating insecure grpc channel with uri={expected_health_uri} and localhost "
        "as default authority",
    )


def test_grpc_channel_creation_insecure(
    extended_mgr: ProductInstanceConfigurationsManager,
    mocker: pytest_mock.MockerFixture,
):
    """Test that insecure channel is created when secure_flags contains 'insecure'."""
    _, configuration = extended_mgr.get_version_configuration("custom-grpc-product-secure", "222")
    config = HpsProductInstanceService(
        {
            "host": "127.0.0.1",
            "port": "50000",
            "uds_dir": "",
            "uds_id": "",
            "secure_flags": "--transport-mode=insecure",
        },
    )

    mock_logger_warn = mocker.patch.object(logging.Logger, "warning")
    grpc_channel = mocker.patch("grpc.insecure_channel")

    client = create_health_client_factory(configuration).create_client(config)
    client.is_healthy()
    options = (("grpc.default_authority", "localhost"),)
    grpc_channel.assert_called_with("127.0.0.1:50000", options=options)
    mock_logger_warn.assert_called_once_with(
        "Health check: creating insecure grpc channel with uri=127.0.0.1:50000 and localhost as default authority",
    )


def test_grpc_channel_creation_mtls_with_certs(
    extended_mgr: ProductInstanceConfigurationsManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
):
    """Test that mTLS secure channel is created when secure_flags contains 'mtls' and certificates are available."""
    _, configuration = extended_mgr.get_version_configuration("custom-grpc-product-secure", "222")

    # Create mock certificate files
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    (certs_dir / "ca.crt").write_text("mock ca certificate")
    (certs_dir / "client.key").write_text("mock private key")
    (certs_dir / "client.crt").write_text("mock client certificate")

    monkeypatch.setenv("ANSYS_GRPC_CERTIFICATES", str(certs_dir))

    config = HpsProductInstanceService(
        {
            "host": "127.0.0.1",
            "port": "50000",
            "uds_dir": "",
            "uds_id": "",
            "secure_flags": "--transport-mode=MTLS",
        },
    )

    mock_logger_info = mocker.patch.object(logging.Logger, "info")
    grpc_channel = mocker.patch("grpc.secure_channel")
    ssl_creds = mocker.patch("grpc.ssl_channel_credentials")

    client = create_health_client_factory(configuration).create_client(config)
    client.is_healthy()
    ssl_creds.assert_called_once()
    grpc_channel.assert_called_once()
    assert grpc_channel.call_args[0][0] == "127.0.0.1:50000"
    mock_logger_info.assert_called_once_with(
        f"Health check: creating secure grpc channel with uri=127.0.0.1:50000 and certificates={certs_dir}",
    )


def test_grpc_channel_creation_mtls_fallback_to_insecure(
    extended_mgr: ProductInstanceConfigurationsManager,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
):
    """Test that channel falls back to insecure when secure_flags contains 'mtls' but certificates are not available."""
    _, configuration = extended_mgr.get_version_configuration("custom-grpc-product-secure", "222")

    # Ensure ANSYS_GRPC_CERTIFICATES is not set
    monkeypatch.delenv("ANSYS_GRPC_CERTIFICATES", raising=False)

    config = HpsProductInstanceService(
        {
            "host": "127.0.0.1",
            "port": "50000",
            "uds_dir": "",
            "uds_id": "",
            "secure_flags": "--transport-mode=MTLS",
        },
    )

    mock_logger_warn = mocker.patch.object(logging.Logger, "warning")
    grpc_channel = mocker.patch("grpc.insecure_channel")

    client = create_health_client_factory(configuration).create_client(config)
    client.is_healthy()
    grpc_channel.assert_called_with("127.0.0.1:50000")
    mock_logger_warn.assert_called_once_with(
        "Health check: creating insecure grpc channel with uri=127.0.0.1:50000 without certificates",
    )


def test_grpc_channel_creation_uds(
    extended_mgr: ProductInstanceConfigurationsManager,
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
):
    """Test that UDS channel is created when secure_flags contains 'uds' and uds_dir/uds_id are provided."""
    _, configuration = extended_mgr.get_version_configuration("custom-grpc-product-secure", "222")

    # Create mock UDS socket file
    uds_dir = tmp_path / "sockets"
    uds_dir.mkdir()
    socket_file = uds_dir / "mockproduct-test-id.sock"
    socket_file.touch()

    config = HpsProductInstanceService(
        {
            "host": "127.0.0.1",
            "port": "50000",
            "uds_dir": str(uds_dir),
            "uds_id": "test-id",
            "secure_flags": "--transport-mode=UDS",
        },
    )

    mock_logger_info = mocker.patch.object(logging.Logger, "info")
    grpc_channel = mocker.patch("grpc.insecure_channel")

    client = create_health_client_factory(configuration).create_client(config)
    client.is_healthy()
    options = (("grpc.default_authority", "localhost"),)
    expected_target = f"unix:{socket_file}"
    grpc_channel.assert_called_with(target=expected_target, options=options)
    mock_logger_info.assert_called_once_with(f"Health check: creating secure grpc channel with uri={expected_target}")


def test_grpc_channel_creation_uds_without_uds_dir_or_id_fallback_to_insecure(
    extended_mgr: ProductInstanceConfigurationsManager,
    mocker: pytest_mock.MockerFixture,
):
    """Test that channel falls back to insecure when secure_flags contains 'uds' but uds_dir or uds_id are not
    provided."""
    _, configuration = extended_mgr.get_version_configuration("custom-grpc-product-secure", "222")

    config = HpsProductInstanceService(
        {
            "host": "127.0.0.1",
            "port": "50000",
            "uds_dir": "",
            "uds_id": "",
            "secure_flags": "--transport-mode=UDS",
        },
    )

    mock_logger_warn = mocker.patch.object(logging.Logger, "warning")
    grpc_channel = mocker.patch("grpc.insecure_channel")

    client = create_health_client_factory(configuration).create_client(config)
    client.is_healthy()
    options = (("grpc.default_authority", "localhost"),)
    grpc_channel.assert_called_with("127.0.0.1:50000", options=options)
    mock_logger_warn.assert_called_once_with(
        "Health check: creating insecure grpc channel with uri=127.0.0.1:50000 and localhost as default authority",
    )


def test_grpc_channel_creation_uds_without_socket_path_returns_false(
    extended_mgr: ProductInstanceConfigurationsManager,
):
    """Test that is_healthy returns False when secure_flags contains 'uds' and uds_dir/uds_id are provided but no
    socket file is found."""
    _, configuration = extended_mgr.get_version_configuration("custom-grpc-product-secure", "222")

    config = HpsProductInstanceService(
        {
            "host": "127.0.0.1",
            "port": "50000",
            "uds_dir": "/non/existent/dir",
            "uds_id": "test-id",
            "secure_flags": "--transport-mode=UDS",
        },
    )

    client = create_health_client_factory(configuration).create_client(config)
    assert client.is_healthy() is False


def test_grpc_channel_creation_wnua(
    extended_mgr: ProductInstanceConfigurationsManager,
    mocker: pytest_mock.MockerFixture,
):
    """Test that WNUA channel is created when secure_flags contains 'wnua'."""
    _, configuration = extended_mgr.get_version_configuration("custom-grpc-product-secure", "222")

    config = HpsProductInstanceService(
        {
            "host": "127.0.0.1",
            "port": "50000",
            "uds_dir": "",
            "uds_id": "",
            "secure_flags": "--transport-mode=WNUA",
        },
    )

    mock_logger_info = mocker.patch.object(logging.Logger, "info")
    grpc_channel = mocker.patch("grpc.insecure_channel")

    client = create_health_client_factory(configuration).create_client(config)
    client.is_healthy()
    options = (("grpc.default_authority", "localhost"),)
    grpc_channel.assert_called_with("127.0.0.1:50000", options=options)
    mock_logger_info.assert_called_once_with("Health check: creating wnua secure grpc channel with uri=127.0.0.1:50000")


@pytest.mark.parametrize("product_name", ["custom-tcp-product"])
def test_mock_tcp_product_health_route(extended_mgr: ProductInstanceConfigurationsManager, product_name: str):
    _, configuration = extended_mgr.get_version_configuration(product_name, "222")
    config = HpsProductInstanceService(
        {"host": "127.0.0.1", "port": "50000", "uds_dir": "", "uds_id": "", "secure_flags": ""},
    )
    assert configuration.health_route is None

    with mock.patch.object(socket.socket, "connect") as mock_sock:
        client = create_health_client_factory(configuration).create_client(config)
        client.is_healthy()
        assert mock_sock.call_args_list[0][0][0] == ("127.0.0.1", 50000)


@pytest.mark.parametrize("product_name", ["custom-http-product", "custom-http-product-custom-route"])
def test_mock_http_product_health_route(extended_mgr: ProductInstanceConfigurationsManager, product_name: str):
    _, configuration = extended_mgr.get_version_configuration(product_name, "222")
    config = HpsProductInstanceService(
        {"host": "127.0.0.1", "port": "50000", "uds_dir": "", "uds_id": "", "secure_flags": ""},
    )
    if product_name == "custom-http-product":
        assert configuration.health_route is None
    elif product_name == "custom-http-product-custom-route":
        assert configuration.health_route

    health_route = configuration.health_route if configuration.health_route is not None else "/health"
    expected_health_url = f"http://{config.host}:{config.port}{health_route}"

    with mock.patch.object(httpx2.Client, "get") as http_get:
        client = create_health_client_factory(configuration).create_client(config)
        client.is_healthy()
        http_get.assert_called_with(expected_health_url)
