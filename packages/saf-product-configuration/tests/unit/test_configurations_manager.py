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
import logging
from pathlib import Path
import py_compile
import shutil

import pytest
import pytest_mock

from ansys.saf.product_configuration.manager.configurations_manager import (
    ProductInstanceConfigurationsManager,
)


@pytest.fixture
def mgr():
    mgr = ProductInstanceConfigurationsManager()
    return mgr


@pytest.fixture
def product_instance_configs_dir() -> Path:
    configs_dir = Path(__file__).parent.parent / "mocks" / "product_instance_configs"
    assert configs_dir.is_dir()
    return configs_dir


@pytest.fixture
def compiled_product_instance_configs_dir(
    product_instance_configs_dir: Path,
    tmp_path: Path,
) -> Generator[Path, None, None]:
    mock_compiled_instance_configurations_dir = tmp_path / "product_instance_configs_compiled"
    mock_compiled_instance_configurations_dir.mkdir()

    for py_file in product_instance_configs_dir.iterdir():
        if py_file.suffix != ".py":
            continue
        dest_file = mock_compiled_instance_configurations_dir / f"{py_file.stem}.pyc"
        py_compile.compile(str(py_file), str(dest_file))

    yield mock_compiled_instance_configurations_dir

    shutil.rmtree(mock_compiled_instance_configurations_dir)


@pytest.fixture
def extended_mgr(
    mgr: ProductInstanceConfigurationsManager,
    product_instance_configs_dir: Path,
    compiled_product_instance_configs_dir: Path,
    request: pytest.FixtureRequest,
    mocker: pytest_mock.MockerFixture,
):
    file_type = request.param if hasattr(request, "param") else "default"
    if file_type == "compiled":
        mock_instance_configurations_dir = compiled_product_instance_configs_dir
    else:
        mock_instance_configurations_dir = product_instance_configs_dir

    logger_mock = mocker.patch.object(logging.Logger, "info")
    mgr.load_configurations(mock_instance_configurations_dir)
    duplicated_configs_warnings = [
        call.args[0] for call in logger_mock.call_args_list if "already loaded" in call.args[0]
    ]
    assert sorted(duplicated_configs_warnings) == sorted(
        [
            "Instance configuration Fluent2DDPSolverInstanceConfiguration already loaded, skipping.",
            "Instance configuration MockGrpcCustomRouteInstanceConfiguration already loaded, skipping.",
            "Instance configuration MockGrpcInstanceConfiguration already loaded, skipping.",
            "Instance configuration MockHttpFakeRouteInstanceConfiguration2 already loaded, skipping.",
        ],
    )

    return mgr


def test_manager_has_expected_products(mgr: ProductInstanceConfigurationsManager):
    assert sorted(mgr.get_products()) == sorted(
        [
            "aedt",
            "optislang-wrapper-secure",
            "mechanical-secure",
            "mapdl-secure",
            "fluent-3ddp-solver-secure",
            "fluent-2ddp-solver-secure",
            "fluent-3ddp-meshing-secure",
            "geometry-secure",
            "visor",
        ],
    )


def test_aedt_has_expected_versions(mgr: ProductInstanceConfigurationsManager):
    assert mgr.list_versions("aedt") == ["251", "252", "261"]


def test_mechanical_has_expected_versions(mgr: ProductInstanceConfigurationsManager):
    assert mgr.list_versions("mechanical-secure") == ["251", "252"]


def test_osl_wrapper_has_expected_versions(mgr: ProductInstanceConfigurationsManager):
    assert mgr.list_versions("optislang-wrapper-secure") == ["241", "242", "251", "252", "261"]


def test_mapdl_has_expected_versions(mgr: ProductInstanceConfigurationsManager):
    assert mgr.list_versions("mapdl-secure") == ["251", "252"]


def test_geometry_has_expected_versions(mgr: ProductInstanceConfigurationsManager):
    assert mgr.list_versions("geometry-secure") == ["251", "252", "261"]


def test_fluent_has_expected_versions(mgr: ProductInstanceConfigurationsManager):
    assert mgr.list_versions("fluent-3ddp-solver-secure") == ["251", "252"]
    assert mgr.list_versions("fluent-2ddp-solver-secure") == ["251", "252"]
    assert mgr.list_versions("fluent-3ddp-meshing-secure") == ["251", "252"]


@pytest.mark.parametrize("extended_mgr", ["default", "compiled"], indirect=True)
def test_extended_manager_has_expected_products(
    extended_mgr: ProductInstanceConfigurationsManager,
):
    assert sorted(extended_mgr.get_products()) == sorted(
        [
            "aedt",
            "optislang-wrapper-secure",
            "mechanical-secure",
            "mapdl-secure",
            "fluent-3ddp-solver-secure",
            "fluent-2ddp-solver-secure",
            "fluent-3ddp-meshing-secure",
            "geometry-secure",
            "custom-grpc-product-custom-route",
            "custom-http-product",
            "custom-http-no-instance-product",
            "custom-http-product-custom-route",
            "custom-grpc-product",
            "custom-secure-grpc-product",
            "custom-http-product-wrong-route",
            "custom-http-product-wrong-service-type",
            "custom-tcp-product",
            "wrong-port-http-product",
            "old-custom-http-product",
            "custom-fluent-2ddp-solver",
            "visor",
            "no-arguments-product",
        ],
    )


def test_mock_product_has_expected_versions(
    extended_mgr: ProductInstanceConfigurationsManager,
):
    assert extended_mgr.list_versions("custom-grpc-product") == ["1", "2", "222"]


def test_mock_product_has_expected_last_version(
    extended_mgr: ProductInstanceConfigurationsManager,
):
    version, configuration = extended_mgr.get_version_configuration("custom-grpc-product")
    assert version == "222"
    assert configuration.execution_command.endswith(
        " -m tests.mocks.grpc_mock_product.server ${PORT} --host ${HOST} --version 222",
    )


def test_mock_product_222_has_expected_command_line(
    extended_mgr: ProductInstanceConfigurationsManager,
):
    version, configuration = extended_mgr.get_version_configuration("custom-grpc-product", "222")
    assert version == "222"
    assert configuration.execution_command.endswith(
        " -m tests.mocks.grpc_mock_product.server ${PORT} --host ${HOST} --version 222",
    )


def test_mock_http_product_222_has_expected_command_line(
    extended_mgr: ProductInstanceConfigurationsManager,
):
    version, configuration = extended_mgr.get_version_configuration("custom-http-product", "222")
    assert version == "222"
    assert configuration.execution_command.endswith(" -m tests.mocks.http_mock_product.server ${PORT} --version 222")
