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


class MockHttpInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
    def __init__(self, version: str) -> None:
        self._version = version

    @property
    def service_name(self) -> str:
        return "http"

    @property
    def execution_command(self) -> str:
        return f"${{EXECUTABLE}} -m tests.mocks.http_mock_product.server ${{PORT}} --version {self._version}"

    @property
    def exe_path_for_pim(self) -> str:
        return sys.executable

    @property
    def environment(self) -> dict[str, str]:
        return {"my_env_var_name": "my_env_var_value"}

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
        return ServiceType.HTTP


class MockHttpInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-http-product"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockHttpInstanceVersionConfiguration(version)


class MockHttpOldInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "old-custom-http-product"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockHttpInstanceVersionConfiguration(version)


class MockHttpNoInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-http-no-instance-product"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockHttpInstanceVersionConfiguration(version)


class MockGrpcInstanceVersionConfiguration(MockHttpInstanceVersionConfiguration):
    @property
    def service_type(self) -> ServiceType:
        return ServiceType.GRPC


class MockGrpcInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-http-product-wrong-service-type"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockGrpcInstanceVersionConfiguration(version)


class MockHttpCustomRouteInstanceVersionConfiguration(MockHttpInstanceVersionConfiguration):
    @property
    def health_route(self) -> str:
        return "/my_custom_health_route"


class MockHttpCustomRouteInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-http-product-custom-route"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockHttpCustomRouteInstanceVersionConfiguration(version)


class MockHttpFakeRouteInstanceVersionConfiguration(MockHttpInstanceVersionConfiguration):
    @property
    def health_route(self) -> str:
        return "/my_fake_health_route"


class MockHttpFakeRouteInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-http-product-wrong-route"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockHttpFakeRouteInstanceVersionConfiguration(version)


# duplicate product_name with MockHttpFakeRouteInstanceConfiguration and in the same file
class MockHttpFakeRouteInstanceConfiguration2(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-http-product-wrong-route"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockHttpFakeRouteInstanceVersionConfiguration(version)


class MockHttpFakePortInstanceVersionConfiguration(MockHttpInstanceVersionConfiguration):
    @property
    def execution_command(self) -> str:
        return f"${{EXECUTABLE}} -m tests.mocks.http_mock_product.server 8888 --version {self._version}"


class MockHttpFakePortInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "wrong-port-http-product"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockHttpFakePortInstanceVersionConfiguration(version)
