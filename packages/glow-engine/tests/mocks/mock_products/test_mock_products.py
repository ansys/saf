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
from pathlib import Path

from fastapi import HTTPException
import pytest

from ansys.saf.testing.platform_specific import xfail_for_ci_on_linux
from tests.mocks.mock_products.client import (
    MockGrpcProductClient,
    MockHttpProductClient,
    MockTcpProductClient,
)
from tests.mocks.mock_products.conftest import ProductServerInfo
from tests.mocks.mock_products.http_server import restore_given_absolute_path, store_given_absolute_path


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


@pytest.mark.parametrize("endpoint", [store_given_absolute_path, restore_given_absolute_path])
def test_http_product_rejects_paths_outside_allowed_roots(
    endpoint: Callable[[dict[str, str]], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed_root = tmp_path / "allowed"
    outside_path = tmp_path / "allowed-sibling" / "outside"
    monkeypatch.setenv("GLOW_PROJECT_FILES_DIRECTORY", str(allowed_root))

    with pytest.raises(HTTPException, match="outside the allowed filesystem roots"):
        endpoint({"value": str(outside_path)})


@pytest.mark.parametrize("endpoint", [store_given_absolute_path, restore_given_absolute_path])
def test_http_product_rejects_path_traversal(
    endpoint: Callable[[dict[str, str]], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    monkeypatch.setenv("GLOW_PROJECT_FILES_DIRECTORY", str(allowed_root))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    with pytest.raises(HTTPException, match="outside the allowed filesystem roots"):
        endpoint({"value": str(allowed_root / ".." / "outside")})


@pytest.mark.parametrize("endpoint", [store_given_absolute_path, restore_given_absolute_path])
def test_http_product_rejects_symlink_outside_allowed_roots(
    endpoint: Callable[[dict[str, str]], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (allowed_root / "link").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Cannot create symlink: {exc}")
    monkeypatch.setenv("GLOW_PROJECT_FILES_DIRECTORY", str(allowed_root))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    with pytest.raises(HTTPException, match="outside the allowed filesystem roots"):
        endpoint({"value": str(allowed_root / "link" / "file")})
