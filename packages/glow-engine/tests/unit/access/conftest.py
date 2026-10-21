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

"""Fixtures shared by the project access control unit tests."""

import base64
from collections.abc import Callable, Sequence
import json
from typing import Any

import pytest
from pytest_mock import MockerFixture

from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._server import dependencies
from ansys.saf.glow._server.dependencies import oidc_scheme, oidc_scheme_ws

TEST_CLIENT_ID = "my-client-id"
SUPER_ADMIN_ROLE = "saf_super_admin"


def encode_jwt(claims: dict[str, Any]) -> str:
    """Build an unsigned JWT-shaped token. Tests using it mock the signature validation (see ``access_settings``)."""

    def encode(part: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(part).encode()).decode().rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode(claims)}.signature"


@pytest.fixture
def make_token() -> Callable[..., str]:
    """Return a factory ``make_token(sub, roles=())`` building a token. ``sub=None`` omits the claim."""

    def _make_token(sub: str | None, roles: Sequence[str] = ()) -> str:
        claims: dict[str, Any] = {"resource_access": {TEST_CLIENT_ID: {"roles": list(roles)}}}
        if sub is not None:
            claims["sub"] = sub
        return encode_jwt(claims)

    return _make_token


@pytest.fixture
def access_settings(settings: Settings, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> Settings:
    """Settings with authentication and project access control enabled, and token validation mocked."""
    settings.glow_project_access_control_enabled = True
    settings.glow_auth_disabled = False
    settings.glow_auth_super_admin_roles = SUPER_ADMIN_ROLE
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    monkeypatch.setattr(oidc_scheme_ws, "auto_error", True)
    monkeypatch.setattr(dependencies, "audience", TEST_CLIENT_ID)
    mocker.patch.object(oidc_scheme._oidc_client, "validate_access_token")  # pyright: ignore[reportPrivateUsage]
    mocker.patch.object(oidc_scheme_ws._oidc_client, "validate_access_token")  # pyright: ignore[reportPrivateUsage]
    return settings


@pytest.fixture
def as_user(make_token: Callable[..., str]) -> Callable[..., dict[str, str]]:
    """Return a function giving the request headers that authenticate as user ``sub``.

    The ``client`` argument is accepted for readability only: the returned headers are passed to each request.
    """

    def _as_user(client: object, sub: str | None, roles: Sequence[str] = ()) -> dict[str, str]:
        del client
        return {"Authorization": f"Bearer {make_token(sub, roles)}"}

    return _as_user
