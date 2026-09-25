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

from collections.abc import Callable
import os
from pathlib import Path
import platform
import re
import sys

import pytest
import pytest_mock
from pytest_mock import MockerFixture

from ansys.saf.product_configuration.aedt import AedtInstanceConfiguration
from ansys.saf.product_configuration.fluent import (
    Fluent2DDPSolverInstanceConfiguration,
    Fluent3DDPMeshingInstanceConfiguration,
    Fluent3DDPSolverInstanceConfiguration,
)
from ansys.saf.product_configuration.geometry import (
    BaseGeometryInstanceVersionConfiguration,
    GeometryInstanceConfiguration,
)
from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    ServiceType,
)
from ansys.saf.product_configuration.mapdl import MapdlInstanceConfiguration
from ansys.saf.product_configuration.mechanical import MechanicalInstanceConfiguration
from ansys.saf.product_configuration.optislang_wrapper import (
    OptislangWrapperInstanceConfiguration,
)
from ansys.saf.product_configuration.pim.config_writer import (
    DEFAULT_GLOW_PRODUCT_BINDING_HOST,
    DEFAULT_GLOW_PRODUCT_BINDING_SECURE_HOST,
    LOCALHOSTS,
    PimLightConfigWriter,
)
from ansys.saf.product_configuration.visor import VisorInstanceConfiguration
from tests.mocks.product_instance_configs.mock_grpc_instance_configuration import (
    MockGrpcInstanceConfiguration,
    MockSecureGrpcCustomRouteInstanceConfiguration,
)
from tests.mocks.product_instance_configs.mock_http_instance_configuration import (
    MockHttpInstanceConfiguration,
    MockHttpInstanceVersionConfiguration,
)
from tests.mocks.product_instance_configs.mock_tcp_instance_configuration import (
    MockNoArgumentsInstanceConfiguration,
    MockTcpInstanceConfiguration,
)


@pytest.fixture
def mock_mkdtemp(mocker: MockerFixture) -> None:
    mocker.patch("tempfile.mkdtemp", return_value="my_fake_temp_dir")


@pytest.fixture
def pim_configurations_dir(tmp_path: Path) -> Path:
    pim_configurations = tmp_path / "Configurations"
    pim_configurations.mkdir(exist_ok=True)
    return pim_configurations


@pytest.fixture(autouse=True)
def clean_local_ansys_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ.keys()):
        if key.startswith(("ANSYSEM_ROOT", "AWP_ROOT", "GEOMETRY_ROOT")):
            monkeypatch.delenv(key)


@pytest.mark.parametrize(
    ("service_type", "product_config"),
    [
        (ServiceType.HTTP.value, MockHttpInstanceConfiguration()),
        (ServiceType.GRPC.value, MockGrpcInstanceConfiguration()),
        (ServiceType.TCP.value, MockTcpInstanceConfiguration()),
        (ServiceType.TCP.value, MockNoArgumentsInstanceConfiguration()),
    ],
)
def test_pim_light_config_writer_dump_config(
    service_type: str,
    product_config: IProductInstanceConfiguration,
    tmp_path: Path,
):
    PimLightConfigWriter.write_config(tmp_path, product_config)
    product_yaml = tmp_path / f"{product_config.product_name}{product_config.versions[0]}.yaml"
    command = sys.executable.replace("\\", "\\\\")
    assert product_yaml.exists()

    expected_name = (
        f"custom-{service_type}-product1"
        if not isinstance(product_config, MockNoArgumentsInstanceConfiguration)
        else "no-arguments-product1"
    )
    expected_product_name = (
        f"custom-{service_type}-product"
        if not isinstance(product_config, MockNoArgumentsInstanceConfiguration)
        else "no-arguments-product"
    )
    expected_args = (
        '\n            - "-m"\n'
        + f'            - "tests.mocks.{service_type}_mock_product.server"\n'
        + f'            - "${{AENEID_PORT_{service_type.upper()}}}"\n'
    )
    if service_type == ServiceType.GRPC.value:
        expected_args += '            - "--host"\n'
        expected_args += '            - "0.0.0.0"\n'
    expected_args += '            - "--version"\n'
    expected_args += '            - "1"'

    if isinstance(product_config, MockNoArgumentsInstanceConfiguration):
        expected_args = '\n            - ""'

    expected_yaml = rf"""configVersion: 1.0
name: {expected_name}
productName: {expected_product_name}
productVersion: 1
stateful: true
startupTimeout: 30
ports:
  - name: {service_type}
    value: 0
services:
  - name: {service_type}
    nameBeta2: {service_type}
    type: {service_type}
    port: {service_type}
    basePath: ""
recipes:
  exec:
    os:
      - platform: {platform.system().lower()}
        config:
          command: "{command}"
          args:{expected_args}
env:
  my_env_var_name: my_env_var_value
"""
    if service_type == ServiceType.GRPC.value:
        expected_yaml += "  host_env: 0.0.0.0\n"
        expected_yaml += "  port_env: ${AENEID_PORT_GRPC}\n"
    assert product_yaml.read_text() == expected_yaml


@pytest.mark.parametrize(
    ("glow_product_binding_host"),
    ["localhost", "127.0.0.1", "172.1.252.0", None],
)
def test_pim_light_secure_flags(
    tmp_path: Path,
    glow_product_binding_host: str | None,
    monkeypatch: pytest.MonkeyPatch,
):
    if glow_product_binding_host is None:
        monkeypatch.delenv("GLOW_PRODUCT_BINDING_HOST", raising=False)
    else:
        monkeypatch.setenv("GLOW_PRODUCT_BINDING_HOST", glow_product_binding_host)

    product_config = MockSecureGrpcCustomRouteInstanceConfiguration()
    PimLightConfigWriter.write_config(tmp_path, product_config)
    product_yaml = tmp_path / f"{product_config.product_name}{product_config.versions[0]}.yaml"
    command = sys.executable.replace("\\", "\\\\")
    assert product_yaml.exists()

    expected_args = (
        '\n            - "-m"\n'
        + '            - "tests.mocks.grpc_mock_product.server"\n'
        + '            - "${AENEID_PORT_GRPC}"\n'
    )
    expected_args += '            - "--host"\n'
    expected_args += f'            - "{glow_product_binding_host or DEFAULT_GLOW_PRODUCT_BINDING_SECURE_HOST}"\n'
    expected_args += '            - "--version"\n'
    expected_args += '            - "1"\n'
    if (
        not glow_product_binding_host or glow_product_binding_host in LOCALHOSTS
    ) and platform.system().lower() == "windows":
        expected_args += '            - "--transport-mode=WNUA"'
    else:
        expected_args += '            - "--transport-mode=insecure"'

    expected_yaml = rf"""configVersion: 1.0
name: custom-secure-grpc-product1
productName: custom-secure-grpc-product
productVersion: 1
stateful: true
startupTimeout: 30
ports:
  - name: grpc
    value: 0
services:
  - name: grpc
    nameBeta2: grpc
    type: grpc
    port: grpc
    basePath: ""
recipes:
  exec:
    os:
      - platform: {platform.system().lower()}
        config:
          command: "{command}"
          args:{expected_args}
env:
  my_env_var_name: my_env_var_value
  host_env: {glow_product_binding_host or DEFAULT_GLOW_PRODUCT_BINDING_SECURE_HOST}
  port_env: ${{AENEID_PORT_GRPC}}
"""

    assert product_yaml.read_text() == expected_yaml


@pytest.mark.parametrize(
    ("glow_product_binding_host"),
    ["localhost", "127.0.0.1", "172.1.252.0", None],
)
def test_pim_light_config_glow_product_binding_host_injection_in_insecure_config(
    glow_product_binding_host: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    if glow_product_binding_host is None:
        monkeypatch.delenv("GLOW_PRODUCT_BINDING_HOST", raising=False)
    else:
        monkeypatch.setenv("GLOW_PRODUCT_BINDING_HOST", glow_product_binding_host)
    PimLightConfigWriter.write_config(tmp_path, MockGrpcInstanceConfiguration())
    product_yaml = tmp_path / "custom-grpc-product1.yaml"
    expected_args = '            - "--host"\n'
    expected_args += f'            - "{glow_product_binding_host or DEFAULT_GLOW_PRODUCT_BINDING_HOST}"\n'
    assert expected_args in product_yaml.read_text()


@pytest.mark.parametrize(
    "product",
    [
        MockHttpInstanceConfiguration,
    ],
)
def test_custom_product_pim_configurations_no_product_installed(
    mocker: MockerFixture,
    pim_configurations_dir: Path,
    product: type[IProductInstanceConfiguration],
    caplog: pytest.LogCaptureFixture,
):
    class NoExeInstanceVersionConfiguration(MockHttpInstanceVersionConfiguration):
        @property
        def exe_path_for_pim(self) -> None:  # type: ignore
            raise ValueError(f"MockHttpProduct version {self._version} cannot be found")

    # GIVEN: Custom product is not installed
    # WHEN: Collecting PIM configurations
    mocker.patch.object(
        MockHttpInstanceConfiguration,
        "get_version_configuration",
        return_value=NoExeInstanceVersionConfiguration("1"),
    )
    config = product()
    PimLightConfigWriter.write_config(pim_configurations_dir, config)

    # THEN: No configurations found, logs an ERROR
    assert list(pim_configurations_dir.iterdir()) == []
    pattern = r"(ERROR) .* The configuration for .* is not valid: .* cannot be found"
    matches = re.findall(pattern, caplog.text)
    assert matches


@pytest.mark.parametrize(
    ("product", "versions"),
    [
        (AedtInstanceConfiguration, ["251", "252", "261"]),
        (MechanicalInstanceConfiguration, ["251", "252"]),
        (MapdlInstanceConfiguration, ["251", "252"]),
        (GeometryInstanceConfiguration, ["251", "252", "261"]),
        (Fluent3DDPSolverInstanceConfiguration, ["251", "252"]),
        (Fluent2DDPSolverInstanceConfiguration, ["251", "252"]),
        (Fluent3DDPMeshingInstanceConfiguration, ["251", "252"]),
        (OptislangWrapperInstanceConfiguration, ["241", "242", "251", "252", "261"]),
        (VisorInstanceConfiguration, ["0"]),
    ],
)
def test_builtin_product_available_versions(product: type[IProductInstanceConfiguration], versions: list[str]):
    # GIVEN: No env vars pointing to local installations
    # WHEN: Loading product configurations
    config = product()

    # THEN: Expected available versions are available
    assert config.versions == versions


@pytest.mark.parametrize(
    "product",
    [
        AedtInstanceConfiguration,
        MechanicalInstanceConfiguration,
        MapdlInstanceConfiguration,
        Fluent3DDPSolverInstanceConfiguration,
        Fluent2DDPSolverInstanceConfiguration,
        Fluent3DDPMeshingInstanceConfiguration,
        GeometryInstanceConfiguration,
        OptislangWrapperInstanceConfiguration,
    ],
)
def test_builtin_product_pim_configurations_no_product_installed(
    pim_configurations_dir: Path,
    product: type[IProductInstanceConfiguration],
    caplog: pytest.LogCaptureFixture,
):
    # GIVEN: No env vars pointing to local product installation
    # WHEN: Collecting PIM configurations
    config = product()
    PimLightConfigWriter.write_config(pim_configurations_dir, config)

    # THEN: No configurations found, logs a WARNING
    assert list(pim_configurations_dir.iterdir()) == []
    pattern = r"(WARNING) .* The configuration for .* is not valid: .* cannot be found"
    matches = re.findall(pattern, caplog.text)
    assert matches


@pytest.mark.parametrize(
    ("product", "version"),
    [
        (AedtInstanceConfiguration, "242"),
        (MapdlInstanceConfiguration, "242"),
        (MechanicalInstanceConfiguration, "242"),
        (Fluent3DDPSolverInstanceConfiguration, "242"),
        (Fluent2DDPSolverInstanceConfiguration, "242"),
        (Fluent3DDPMeshingInstanceConfiguration, "242"),
        (GeometryInstanceConfiguration, "242"),
    ],
)
def test_builtin_product_pim_configurations_lower_version_available(
    pim_configurations_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    product: type[IProductInstanceConfiguration],
    version: str,
):
    # GIVEN: Env vars pointing to non-supported older product installation
    monkeypatch.setenv(f"ANSYSEM_ROOT{version}", "test")
    monkeypatch.setenv(f"AWP_ROOT{version}", "test")

    # WHEN: Collecting PIM configurations
    config = product()
    PimLightConfigWriter.write_config(pim_configurations_dir, config)

    # THEN: No configurations found
    assert list(pim_configurations_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("product", "version"),
    [
        (AedtInstanceConfiguration, "262"),
        (MapdlInstanceConfiguration, "261"),
        (MechanicalInstanceConfiguration, "261"),
        (Fluent3DDPSolverInstanceConfiguration, "261"),
        (Fluent2DDPSolverInstanceConfiguration, "261"),
        (Fluent3DDPMeshingInstanceConfiguration, "261"),
        (OptislangWrapperInstanceConfiguration, "262"),
        (GeometryInstanceConfiguration, "262"),
    ],
)
def test_builtin_product_pim_configurations_higher_version_available(
    pim_configurations_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    product: type[IProductInstanceConfiguration],
    version: str,
):
    # GIVEN: Env vars pointing to non-supported future product installation
    monkeypatch.setenv(f"ANSYSEM_ROOT{version}", "test")
    monkeypatch.setenv(f"AWP_ROOT{version}", "test")

    # WHEN: Collecting PIM configurations
    config = product()
    PimLightConfigWriter.write_config(pim_configurations_dir, config)

    # THEN: No configurations found
    assert list(pim_configurations_dir.iterdir()) == []


def test_geometry_251_only_works_in_windows(
    pim_configurations_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    # GIVEN: Env vars pointing to local Geometry installation
    monkeypatch.setenv("GEOMETRY_ROOT251", "test")

    # WHEN: Collecting PIM configurations
    config = GeometryInstanceConfiguration()
    PimLightConfigWriter.write_config(pim_configurations_dir, config)

    if platform.system() == "Linux":
        # THEN: No configurations found, logs a WARNING
        assert list(pim_configurations_dir.iterdir()) == []
        expected_log_level = "WARNING"
        expected_message = "Only Windows platform is supported for Geometry version 251."
        assert expected_log_level in caplog.text
        assert expected_message in caplog.text
    else:
        # THEN: Configuration is generated
        assert (pim_configurations_dir / f"{config.product_name}251.yaml").is_file()


def test_autogenerate_built_in_product_config_list():
    expected_product_conf_list = [
        "AedtInstanceConfiguration",
        "MapdlInstanceConfiguration",
        "MechanicalInstanceConfiguration",
        "OptislangWrapperInstanceConfiguration",
        "Fluent2DDPSolverInstanceConfiguration",
        "Fluent3DDPMeshingInstanceConfiguration",
        "Fluent3DDPSolverInstanceConfiguration",
        "GeometryInstanceConfiguration",
        "VisorInstanceConfiguration",
    ]
    product_conf_list = PimLightConfigWriter._list_built_in_product_configs()  # pyright: ignore[reportPrivateUsage]
    assert set(product_conf_list) == set(expected_product_conf_list)


@pytest.fixture
def expected_command() -> Callable[[type[IProductInstanceConfiguration], str], str | None]:
    def _get_expected_command(
        product_config: type[IProductInstanceConfiguration],
        version: str,
    ) -> str | None:
        mock_ansys_dir = "fake_ansys_install_dir"
        if product_config == MechanicalInstanceConfiguration:
            exe_path = (
                str(Path(mock_ansys_dir) / "aisol" / "bin" / "winx64" / "AnsysWBU.exe")
                if platform.system() == "Windows"
                else str(Path(mock_ansys_dir) / "aisol" / ".workbench")
            )
        elif product_config == MapdlInstanceConfiguration:
            exe_path = (
                str(Path(mock_ansys_dir) / "ansys" / "bin" / "winx64" / f"ANSYS{version}.exe")
                if platform.system() == "Windows"
                else str(Path(mock_ansys_dir) / "ansys" / "bin" / f"ansys{version}")
            )
        elif product_config in [
            AedtInstanceConfiguration,
            Fluent3DDPSolverInstanceConfiguration,
            Fluent2DDPSolverInstanceConfiguration,
            Fluent3DDPMeshingInstanceConfiguration,
            OptislangWrapperInstanceConfiguration,
            VisorInstanceConfiguration,
        ]:
            exe_path = sys.executable
        elif product_config == GeometryInstanceConfiguration and version == "251" and platform.system() == "Windows":
            return (Path(mock_ansys_dir) / "Presentation.ApiServerDMS.exe").as_posix()
        elif product_config == GeometryInstanceConfiguration and version != "251" and platform.system() == "Windows":
            return (Path(mock_ansys_dir) / "Presentation.ApiServerCoreService.exe").as_posix()
        elif product_config == GeometryInstanceConfiguration and version != "251" and platform.system() == "Linux":
            return (Path(mock_ansys_dir) / "dotnet").as_posix()
        else:
            raise ValueError(f"Unrecognized product: {product_config}.")

        return exe_path.replace("\\", "\\\\") if platform.system() == "Windows" and exe_path else exe_path

    return _get_expected_command


@pytest.fixture
def expected_args() -> Callable[[type[IProductInstanceConfiguration], str, str | None], str]:  # noqa: C901

    def _get_expected_args(  # noqa: C901
        product_config: type[IProductInstanceConfiguration],
        version: str,
        binding_host: str | None,
    ) -> str:
        secure_bind_host = binding_host or DEFAULT_GLOW_PRODUCT_BINDING_SECURE_HOST

        product_expected_args: dict[type[IProductInstanceConfiguration], str] = {}
        product_expected_args[MechanicalInstanceConfiguration] = (
            f"""
            - "-DSAPPLET"
            - "-B"
            - "-GRPC"
            - "${{AENEID_PORT_TCP}}"
            - "--GRPC-HOST"
            - "{secure_bind_host}"
          """
        ).strip()
        if platform.system() == "Windows" and secure_bind_host in LOCALHOSTS:
            product_expected_args[MechanicalInstanceConfiguration] += (
                '\n            - "--transport-mode"\n            - "WNUA"'
            )
        else:
            product_expected_args[MechanicalInstanceConfiguration] += (
                '\n            - "--transport-mode"\n            - "insecure"'
            )
        product_expected_args[MapdlInstanceConfiguration] = (
            """
            - "-grpc"
            - "-port"
            - "${AENEID_PORT_GRPC}"
            - "-dir"
            - "my_fake_temp_dir"
        """
        ).strip()
        if platform.system() == "Windows" and secure_bind_host in LOCALHOSTS:
            product_expected_args[MapdlInstanceConfiguration] += '\n            - "-transport"\n            - "wnua"'
        else:
            product_expected_args[MapdlInstanceConfiguration] += (
                '\n            - "-transport"\n            - "insecure"'
                '\n            - "-allowremote"\n            - "true"'
            )
        bind_host_osl = binding_host or DEFAULT_GLOW_PRODUCT_BINDING_SECURE_HOST
        wrapper_args = (
            f"""
            - "-m"
            - "ansys.saf.product_configuration.wrappers.optislang"
            - "--port"
            - "${{AENEID_PORT_HTTP}}"
            - "--host"
            - "{bind_host_osl}"
            """
        ).strip()
        if platform.system() == "Windows" and bind_host_osl in LOCALHOSTS:
            wrapper_args += '\n            - "--transport-mode=WNUA"'
        else:
            wrapper_args += '\n            - "--transport-mode=insecure"'
        product_expected_args[OptislangWrapperInstanceConfiguration] = wrapper_args
        product_expected_args[AedtInstanceConfiguration] = (
            f"""
            - "-m"
            - "ansys.saf.product_configuration.wrappers.aedt"
            - "--port"
            - "${{AENEID_PORT_HTTP}}"
            - "--host"
            - "{secure_bind_host}"
            - "--version"
            - "{version}"
          """
        ).strip()
        if platform.system() == "Windows" and secure_bind_host in LOCALHOSTS:
            product_expected_args[AedtInstanceConfiguration] += '\n            - "--transport-mode=WNUA"'
        else:
            product_expected_args[AedtInstanceConfiguration] += '\n            - "--transport-mode=insecure"'
        product_expected_args[Fluent3DDPSolverInstanceConfiguration] = (
            f"""
            - "-m"
            - "ansys.saf.product_configuration.wrappers.fluent"
            - "--port"
            - "${{AENEID_PORT_HTTP}}"
            - "--host"
            - "{secure_bind_host}"
            - "--version"
            - "{version}"
            - "--mode"
            - "solver"
            - "--geometry"
            - "3d"
            - "--precision"
            - "double"
          """
        ).strip()
        if platform.system() == "Windows" and secure_bind_host in LOCALHOSTS:
            product_expected_args[Fluent3DDPSolverInstanceConfiguration] += '\n            - "--transport-mode=WNUA"'
        else:
            product_expected_args[Fluent3DDPSolverInstanceConfiguration] += (
                '\n            - "--transport-mode=insecure"'
            )
        product_expected_args[Fluent2DDPSolverInstanceConfiguration] = (
            f"""
            - "-m"
            - "ansys.saf.product_configuration.wrappers.fluent"
            - "--port"
            - "${{AENEID_PORT_HTTP}}"
            - "--host"
            - "{secure_bind_host}"
            - "--version"
            - "{version}"
            - "--mode"
            - "solver"
            - "--geometry"
            - "2d"
            - "--precision"
            - "double"
          """
        ).strip()
        if platform.system() == "Windows" and secure_bind_host in LOCALHOSTS:
            product_expected_args[Fluent2DDPSolverInstanceConfiguration] += '\n            - "--transport-mode=WNUA"'
        else:
            product_expected_args[Fluent2DDPSolverInstanceConfiguration] += (
                '\n            - "--transport-mode=insecure"'
            )
        product_expected_args[Fluent3DDPMeshingInstanceConfiguration] = (
            f"""
            - "-m"
            - "ansys.saf.product_configuration.wrappers.fluent"
            - "--port"
            - "${{AENEID_PORT_HTTP}}"
            - "--host"
            - "{secure_bind_host}"
            - "--version"
            - "{version}"
            - "--mode"
            - "meshing"
            - "--geometry"
            - "3d"
            - "--precision"
            - "double"
            """
        ).strip()
        if platform.system() == "Windows" and secure_bind_host in LOCALHOSTS:
            product_expected_args[Fluent3DDPMeshingInstanceConfiguration] += '\n            - "--transport-mode=WNUA"'
        else:
            product_expected_args[Fluent3DDPMeshingInstanceConfiguration] += (
                '\n            - "--transport-mode=insecure"'
            )
        if platform.system() == "Windows":
            transport_mode = "insecure"
            if secure_bind_host in LOCALHOSTS:
                transport_mode = "WNUA"
            product_expected_args[GeometryInstanceConfiguration] = f'- "--transport-mode={transport_mode}"'
        else:
            product_expected_args[GeometryInstanceConfiguration] = (
                """
            - "fake_ansys_install_dir/Presentation.ApiServerCoreService.dll"
            - "--transport-mode=insecure"
            """
            ).strip()
        product_expected_args[VisorInstanceConfiguration] = (
            """
            - "-m"
            - "ansys.visor.viewer.cli.visor_cli"
            - "--api-host"
            - "0.0.0.0"
            - "--api-port"
            - "${AENEID_PORT_HTTP}"
            - "server"
            - "start"
            """
        ).strip()
        if product_config in product_expected_args:
            return product_expected_args[product_config]
        else:
            raise ValueError(f"Unrecognized product: {product_config}.")

    return _get_expected_args


@pytest.fixture
def expected_env_vars() -> Callable[[type[IProductInstanceConfiguration], str, str | None], str]:
    def _get_expected_env_vars(
        product_config: type[IProductInstanceConfiguration],
        version: str,
        binding_host: str | None,
    ) -> str:
        secure_bind_host = binding_host or DEFAULT_GLOW_PRODUCT_BINDING_SECURE_HOST

        if product_config == MechanicalInstanceConfiguration:
            return ""
        elif product_config == MapdlInstanceConfiguration:
            return "env:\n  ANSYS_LOCK: OFF\n  ANSYS_MAPDL_UDS_PATH: ${UDS_DIR}\n"
        elif product_config in (
            OptislangWrapperInstanceConfiguration,
            AedtInstanceConfiguration,
            Fluent3DDPSolverInstanceConfiguration,
            Fluent2DDPSolverInstanceConfiguration,
            Fluent3DDPMeshingInstanceConfiguration,
            VisorInstanceConfiguration,
        ):
            return ""
        elif product_config == GeometryInstanceConfiguration and version == "251" and platform.system() == "Windows":
            return f"""env:
  API_ADDRESS: {secure_bind_host}
  API_PORT: ${{AENEID_PORT_GRPC}}
  LOG_LEVEL: 2\n"""
        elif product_config == GeometryInstanceConfiguration and version != "251" and platform.system() == "Windows":
            return f"""env:
  ANS_DSCO_REMOTE_PORT: ${{AENEID_PORT_GRPC}}
  ANS_DSCO_REMOTE_IP: {secure_bind_host}
  LOG_LEVEL: 2
  ANSYS_CI_INSTALL: fake_ansys_install_dir/CADIntegration
  P_SCHEMA: fake_ansys_install_dir/Schema
  PATH: fake_ansys_install_dir;fake_ansys_install_dir/CADIntegration/bin;fake_ansys_install_dir/Native/Windows\n"""
        elif product_config == GeometryInstanceConfiguration and version != "251" and platform.system() == "Linux":
            return f"""env:
  ANS_DSCO_REMOTE_PORT: ${{AENEID_PORT_GRPC}}
  ANS_DSCO_REMOTE_IP: {secure_bind_host}
  LOG_LEVEL: 2
  ANSYS_CI_INSTALL: fake_ansys_install_dir/CADIntegration
  P_SCHEMA: fake_ansys_install_dir/Schema
  LD_LIBRARY_PATH: fake_ansys_install_dir:fake_ansys_install_dir/CADIntegration/bin:fake_ansys_install_dir/Native/Linux
  ANSYSCL{version}_DIR: fake_ansys_install_dir/licensingclient\n"""
        else:
            raise ValueError(f"Unrecognized product: {product_config}.")

    return _get_expected_env_vars


@pytest.mark.usefixtures("mock_mkdtemp")
@pytest.mark.parametrize(
    ("service_type", "healthcheck_type", "product_config", "version"),
    [
        (
            ServiceType.GRPC.value,
            ServiceType.TCP.value,
            MechanicalInstanceConfiguration,
            "252",
        ),
        (
            ServiceType.GRPC.value,
            ServiceType.GRPC.value,
            MapdlInstanceConfiguration,
            "252",
        ),
        (
            ServiceType.HTTP.value,
            ServiceType.HTTP.value,
            OptislangWrapperInstanceConfiguration,
            "241",
        ),
        (
            ServiceType.HTTP.value,
            ServiceType.HTTP.value,
            AedtInstanceConfiguration,
            "252",
        ),
        (
            ServiceType.HTTP.value,
            ServiceType.HTTP.value,
            Fluent3DDPSolverInstanceConfiguration,
            "252",
        ),
        (
            ServiceType.HTTP.value,
            ServiceType.HTTP.value,
            Fluent2DDPSolverInstanceConfiguration,
            "252",
        ),
        (
            ServiceType.HTTP.value,
            ServiceType.HTTP.value,
            Fluent3DDPMeshingInstanceConfiguration,
            "252",
        ),
        (
            ServiceType.GRPC.value,
            ServiceType.GRPC.value,
            GeometryInstanceConfiguration,  # Two appearances of GeometryInstanceConfiguration because there are two
            "251",  # different IProductInstanceVersionConfiguration, depending on the version.
        ),
        (
            ServiceType.GRPC.value,
            ServiceType.GRPC.value,
            GeometryInstanceConfiguration,
            "261",
        ),
        (
            ServiceType.HTTP.value,
            ServiceType.HTTP.value,
            VisorInstanceConfiguration,
            "0",
        ),
    ],
)
@pytest.mark.parametrize("binding_host", ["localhost", "127.0.0.1", "172.1.252.0", None])
def test_pim_dump_config_for_builtin_products(
    monkeypatch: pytest.MonkeyPatch,
    service_type: str,
    healthcheck_type: str,
    expected_command: Callable[[type[IProductInstanceConfiguration], str], str],
    expected_args: Callable[[type[IProductInstanceConfiguration], str, str | None], str],
    expected_env_vars: Callable[[type[IProductInstanceConfiguration], str, str | None], str],
    version: str,
    product_config: type[IProductInstanceConfiguration],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    mocker: pytest_mock.MockerFixture,
    binding_host: str | None,
):
    # GIVEN: Env vars pointing to supported Ansys installations
    mock_ansys_dir = "fake_ansys_install_dir"
    monkeypatch.setenv(f"AWP_ROOT{version}", mock_ansys_dir)
    monkeypatch.setenv(f"ANSYSEM_ROOT{version}", mock_ansys_dir)
    monkeypatch.setenv(f"GEOMETRY_ROOT{version}", mock_ansys_dir)

    mocker.patch.object(
        BaseGeometryInstanceVersionConfiguration,
        "_get_dotnet_path",
        return_value=Path(mock_ansys_dir) / "dotnet",
    )

    if binding_host:
        monkeypatch.setenv("GLOW_PRODUCT_BINDING_HOST", binding_host)
    else:
        monkeypatch.delenv("GLOW_PRODUCT_BINDING_HOST", raising=False)

    # WHEN: Collecting PIM configurations
    config = product_config()
    product_yaml = tmp_path / f"{config.product_name}{version}.yaml"
    assert not product_yaml.exists()
    PimLightConfigWriter.write_config(tmp_path, config)

    # THEN: Geometry not supported on Linux for 251
    if product_config == GeometryInstanceConfiguration and platform.system() == "Linux" and version == "251":
        pattern = r"(WARNING) .* Only Windows platform is supported for Geometry version 251\."
        matches = re.findall(pattern, caplog.text)
        assert matches
        assert not product_yaml.exists()
        return

    # THEN: Configurations found
    assert product_yaml.exists()
    pim_config = product_yaml.read_text()
    assert pim_config == (
        rf"""configVersion: 1.0
name: {config.product_name}{version}
productName: {config.product_name}
productVersion: {version}
stateful: true
startupTimeout: 30
ports:
  - name: {healthcheck_type}
    value: 0
services:
  - name: {service_type}
    nameBeta2: {service_type}
    type: {healthcheck_type}
    port: {healthcheck_type}
    basePath: ""
recipes:
  exec:
    os:
      - platform: {platform.system().lower()}
        config:
          command: "{expected_command(product_config, version)}"
          args:
            {expected_args(product_config, version, binding_host)}
{expected_env_vars(product_config, version, binding_host)}"""
    )
