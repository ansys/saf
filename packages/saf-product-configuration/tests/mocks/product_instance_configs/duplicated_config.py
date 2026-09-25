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

from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
)
from tests.mocks.product_instance_configs.mock_grpc_instance_configuration import (
    MockGrpcCustomRouteInstanceVersionConfiguration,
    MockGrpcInstanceConfiguration,  # pyright: ignore[reportUnusedImport]  # noqa: F401 # for testing duplicates via imports
)


# duplicate of
# tests.mocks.product_instance_configs.mock_grpc_instance_configuration.MockGrpcCustomRouteInstanceConfiguration
class MockGrpcCustomRouteInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-grpc-product-custom-route"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockGrpcCustomRouteInstanceVersionConfiguration(version)
