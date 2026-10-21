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
import dataclasses
from typing import Any

from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
import pytest

from ansys.saf.glow._access.principal import ON_BEHALF_OF_HEADER, Principal
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._server.dependencies import PrincipalDep, get_settings
from tests.mocks.solutions import minimal_solution
from tests.unit.access.conftest import encode_jwt

solution = minimal_solution

API_KEY = "configured-api-key"


def _build_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/principal")
    async def get_current_principal(principal: PrincipalDep) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return dataclasses.asdict(principal)

    return app


def _client(app: FastAPI, peer: str = "127.0.0.1") -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, client=(peer, 123)), base_url="http://localhost")


async def test_principal_from_token(access_settings: Settings, make_token: Callable[..., str]):
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers={"Authorization": f"Bearer {make_token('alice')}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": "alice", "is_super_admin": False, "is_internal": False}


async def test_principal_super_admin(access_settings: Settings, make_token: Callable[..., str]):
    token = make_token("alice", ["saf_super_admin"])
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers={"Authorization": f"Bearer {token}"})
    assert response.json() == {"user_id": "alice", "is_super_admin": True, "is_internal": False}


async def test_principal_super_admin_requires_configured_role(
    access_settings: Settings,
    make_token: Callable[..., str],
):
    access_settings.glow_auth_super_admin_roles = ""
    token = make_token("alice", ["saf_super_admin"])
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["is_super_admin"] is False


async def test_on_behalf_of_ignored_without_api_key(access_settings: Settings, make_token: Callable[..., str]):
    headers = {"Authorization": f"Bearer {make_token('alice')}", ON_BEHALF_OF_HEADER: "bob"}
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers=headers)
    assert response.json() == {"user_id": "alice", "is_super_admin": False, "is_internal": False}


async def test_on_behalf_of_with_api_key(access_settings: Settings):
    access_settings.glow_api_key = API_KEY
    headers = {"x-api-key": API_KEY, ON_BEHALF_OF_HEADER: "bob"}
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers=headers)
    assert response.json() == dataclasses.asdict(Principal("bob", False, True))


async def test_api_key_without_on_behalf_of_has_no_user(access_settings: Settings):
    access_settings.glow_api_key = API_KEY
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers={"x-api-key": API_KEY})
    assert response.json() == dataclasses.asdict(Principal(None, False, True))


async def test_on_behalf_of_ignored_for_api_key_from_remote_host(
    access_settings: Settings,
    make_token: Callable[..., str],
):
    # The API key is only honoured from localhost: a remote caller falls back to its token.
    access_settings.glow_api_key = API_KEY
    headers = {
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {make_token('alice')}",
        ON_BEHALF_OF_HEADER: "bob",
    }
    async with _client(_build_app(access_settings), peer="10.0.0.5") as client:
        response = await client.get("/principal", headers=headers)
    assert response.json() == {"user_id": "alice", "is_super_admin": False, "is_internal": False}


async def test_token_without_sub_is_rejected(access_settings: Settings, make_token: Callable[..., str]):
    token = make_token(None, ["saf_super_admin"])
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers={"Authorization": f"Bearer {token}"})
    assert response.json() == {"user_id": None, "is_super_admin": False, "is_internal": False}


async def test_non_jwt_token_has_no_user(access_settings: Settings):
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.json() == {"user_id": None, "is_super_admin": False, "is_internal": False}


async def test_principal_when_auth_is_disabled(settings: Settings):
    # No ``access_settings``: the token scheme does not enforce auth and yields no token.
    async with _client(_build_app(settings)) as client:
        response = await client.get("/principal", headers={ON_BEHALF_OF_HEADER: "bob"})
    assert response.json() == {"user_id": None, "is_super_admin": False, "is_internal": False}


@pytest.mark.parametrize("sub", ["", 42])
async def test_token_with_invalid_sub_has_no_user(access_settings: Settings, sub: Any):
    token = encode_jwt({"sub": sub})
    async with _client(_build_app(access_settings)) as client:
        response = await client.get("/principal", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["user_id"] is None
