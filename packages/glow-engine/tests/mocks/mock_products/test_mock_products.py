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

from pathlib import Path

import pytest

from ansys.saf.testing.platform_specific import xfail_for_ci_on_linux
from tests.mocks.mock_products.client import (
    MockGrpcProductClient,
    MockHttpProductClient,
    MockTcpProductClient,
)
from tests.mocks.mock_products.conftest import ProductServerInfo


@xfail_for_ci_on_linux(reason="Fails with 3.12 consistently in github-hosted linux runners. OK locally.")
@pytest.mark.parametrize(
    "product_server_info",
    [
        ("http", MockHttpProductClient),
        ("grpc", MockGrpcProductClient),
        ("tcp", MockTcpProductClient),
    ],
    ids=["http", "grpc", "tcp"],
    indirect=True,
)
class TestMockProductClient:
    def test_mock_http_product(self, product_server_info: ProductServerInfo):
        client = product_server_info.create_client()
        assert client.the_property == "blue"

    def test_state_can_be_restored_in_mock_product(self, tmp_path: Path, product_server_info: ProductServerInfo):
        store = str(tmp_path / "store")
        client = product_server_info.create_client()
        assert client.the_property != "red"
        client.the_property = "red"
        client.store_given_absolute_path(store)
        client = product_server_info.create_client()
        client.restore_given_absolute_path(store)
        assert client.the_property == "red"
