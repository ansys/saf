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

import sys

from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
    ISoftware,
    ServiceType,
    Software,
)


class MockGrpcInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
    def __init__(self, version: str) -> None:
        self._version = version

    @property
    def service_name(self) -> str:
        return "grpc"

    @property
    def execution_command(self) -> str:
        return f"${{EXECUTABLE}} -m tests.mocks.grpc_mock_product.server ${{PORT}} --host ${{HOST}} --version {self._version}"  # noqa: E501

    @property
    def exe_path_for_pim(self) -> str:
        return sys.executable

    @property
    def environment(self) -> dict[str, str]:
        return {
            "my_env_var_name": "my_env_var_value",
            "host_env": "${HOST}",
            "port_env": "${PORT}",
        }

    @property
    def software_requirements(self) -> list[ISoftware]:
        return [
            Software(
                name="Python",
                version=f"{sys.version_info.major}.{sys.version_info.minor}",
            ),
        ]

    @property
    def service_type(self) -> ServiceType:
        return ServiceType.GRPC


class MockGrpcInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-grpc-product"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockGrpcInstanceVersionConfiguration(version)


class MockGrpcCustomRouteInstanceVersionConfiguration(MockGrpcInstanceVersionConfiguration):
    @property
    def health_route(self) -> str:
        return "my_custom_health_route"


class MockGrpcCustomRouteInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-grpc-product-custom-route"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockGrpcCustomRouteInstanceVersionConfiguration(version)


class MockSecureGrpcCustomRouteInstanceVersionConfiguration(MockGrpcInstanceVersionConfiguration):
    @property
    def enable_secure_flags(self) -> bool:
        return True


class MockSecureGrpcCustomRouteInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-secure-grpc-product"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockSecureGrpcCustomRouteInstanceVersionConfiguration(version)
