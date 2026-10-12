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

from collections.abc import Iterator
from dataclasses import dataclass
import sys
from time import sleep

import pytest

from ansys.saf.glow._utilities.ip_utilities import get_random_free_port
from ansys.saf.testing.process import Process
from tests.mocks.mock_products.client import (
    IMockProductClient,
)


class MockProductProcess(Process):
    def __init__(self, args: list[str]) -> None:
        self._port = get_random_free_port()
        super().__init__(args + [str(self._port)], bg=True)

    @property
    def port(self) -> int:
        return self._port


@dataclass
class ProductServerInfo:
    port: int
    client: type[IMockProductClient]

    def create_client(self) -> IMockProductClient:
        return self.client(self.port)  # pyright: ignore[reportCallIssue]


@pytest.fixture(scope="package")
def product_server_info(request: pytest.FixtureRequest) -> Iterator[ProductServerInfo]:
    service_type, product_client_type = request.param
    process = MockProductProcess([sys.executable, "-m", f"tests.mocks.mock_products.{service_type}_server"])
    process.start()

    tries = 0
    product_server_info = ProductServerInfo(port=process.port, client=product_client_type)
    client = product_server_info.create_client()
    healthy = False
    while not healthy and tries < 10:
        healthy = client.healthy()
        if healthy:
            break
        tries += 1
        sleep(0.25)
    assert healthy

    yield ProductServerInfo(port=process.port, client=product_client_type)

    process.stop()
