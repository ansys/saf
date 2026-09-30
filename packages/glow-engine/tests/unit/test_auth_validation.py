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

import base64
from collections.abc import Callable
import json
import logging
from typing import TYPE_CHECKING
from unittest.mock import call

from ansys.iam.oidc import DEFAULT_SUBPROTOCOL_PREFIX, OidcClient, encode_base64_token
from asgi_lifespan import LifespanManager
from fastapi import WebSocketDisconnect, status
from fastapi.routing import APIWebSocketRoute, _IncludedRouter  # pyright: ignore[reportPrivateUsage]
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient, Response
import pytest
import pytest_mock
from pytest_mock import MockerFixture
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.testclient import WebSocketDenialResponse

from ansys.saf.glow._config.const import Deployment
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._server import dependencies
from ansys.saf.glow._server.dependencies import oidc_scheme, oidc_scheme_ws
from tests.mocks.solutions import instances
from tests.unit.conftest import MOCK_APP_STARTUP_TIMEOUT, build_mock_app, build_mock_dash_app

if TYPE_CHECKING:
    from flask import Flask

# should have both transaction types and instances.
solution = instances

ROUTES_WITHOUT_AUTH = [
    "/health",
    "/schema",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    # TODO: should we allow to enable auth on the desktop routes? since env vars are not deployment-locked anymore
    "/desktop:exit",
    "/desktop:hps-auth-info",
]

EXPECTED_ROUTES = {
    "get /openapi.json",
    "head /openapi.json",
    "get /docs",
    "head /docs",
    "get /docs/oauth2-redirect",
    "head /docs/oauth2-redirect",
    "get /redoc",
    "head /redoc",
    "get /projects/{project_id}/steps/instance-step",
    "patch /projects/{project_id}/steps/instance-step",
    "get /projects/{project_id}/steps/instance-step/data/{datapath:path}",
    "get /projects/{project_id}/steps/other-step",
    "patch /projects/{project_id}/steps/other-step",
    "get /projects/{project_id}/steps/other-step/data/{datapath:path}",
    "post /projects/{project_id}/steps/instance-step:be-healthy-http",
    "get /projects/{project_id}/steps/instance-step:be-healthy-http",
    "patch /projects/{project_id}/steps/instance-step:be-healthy-http",
    "post /projects/{project_id}/steps/instance-step:be-unhealthy-http",
    "get /projects/{project_id}/steps/instance-step:be-unhealthy-http",
    "patch /projects/{project_id}/steps/instance-step:be-unhealthy-http",
    "post /projects/{project_id}/steps/instance-step:check-instance-health",
    "get /projects/{project_id}/steps/instance-step:check-instance-health",
    "patch /projects/{project_id}/steps/instance-step:check-instance-health",
    "post /projects/{project_id}/steps/instance-step:check-pim-config-env-var-is-not-set",
    "get /projects/{project_id}/steps/instance-step:check-pim-config-env-var-is-not-set",
    "patch /projects/{project_id}/steps/instance-step:check-pim-config-env-var-is-not-set",
    "post /projects/{project_id}/steps/instance-step:create",
    "get /projects/{project_id}/steps/instance-step:create",
    "patch /projects/{project_id}/steps/instance-step:create",
    "post /projects/{project_id}/steps/instance-step:create-http",
    "get /projects/{project_id}/steps/instance-step:create-http",
    "patch /projects/{project_id}/steps/instance-step:create-http",
    "post /projects/{project_id}/steps/instance-step:create-http-no-save",
    "get /projects/{project_id}/steps/instance-step:create-http-no-save",
    "patch /projects/{project_id}/steps/instance-step:create-http-no-save",
    "post /projects/{project_id}/steps/instance-step:create-no-type",
    "get /projects/{project_id}/steps/instance-step:create-no-type",
    "patch /projects/{project_id}/steps/instance-step:create-no-type",
    "post /projects/{project_id}/steps/instance-step:create-tcp",
    "get /projects/{project_id}/steps/instance-step:create-tcp",
    "patch /projects/{project_id}/steps/instance-step:create-tcp",
    "post /projects/{project_id}/steps/instance-step:create-with-project",
    "get /projects/{project_id}/steps/instance-step:create-with-project",
    "patch /projects/{project_id}/steps/instance-step:create-with-project",
    "post /projects/{project_id}/steps/instance-step:fetch-the-property",
    "get /projects/{project_id}/steps/instance-step:fetch-the-property",
    "patch /projects/{project_id}/steps/instance-step:fetch-the-property",
    "post /projects/{project_id}/steps/instance-step:get-http-instance-color-and-kill-instance",
    "get /projects/{project_id}/steps/instance-step:get-http-instance-color-and-kill-instance",
    "patch /projects/{project_id}/steps/instance-step:get-http-instance-color-and-kill-instance",
    "post /projects/{project_id}/steps/instance-step:get-http-process-pid",
    "get /projects/{project_id}/steps/instance-step:get-http-process-pid",
    "patch /projects/{project_id}/steps/instance-step:get-http-process-pid",
    "post /projects/{project_id}/steps/instance-step:get-instance-to-entity-handle",
    "get /projects/{project_id}/steps/instance-step:get-instance-to-entity-handle",
    "patch /projects/{project_id}/steps/instance-step:get-instance-to-entity-handle",
    "post /projects/{project_id}/steps/instance-step:get-pim-name",
    "get /projects/{project_id}/steps/instance-step:get-pim-name",
    "patch /projects/{project_id}/steps/instance-step:get-pim-name",
    "post /projects/{project_id}/steps/instance-step:harakiri",
    "get /projects/{project_id}/steps/instance-step:harakiri",
    "patch /projects/{project_id}/steps/instance-step:harakiri",
    "post /projects/{project_id}/steps/instance-step:http-no-save-get-color-harakiri",
    "get /projects/{project_id}/steps/instance-step:http-no-save-get-color-harakiri",
    "patch /projects/{project_id}/steps/instance-step:http-no-save-get-color-harakiri",
    "post /projects/{project_id}/steps/instance-step:kill-product-directly-from-instance-system",
    "get /projects/{project_id}/steps/instance-step:kill-product-directly-from-instance-system",
    "patch /projects/{project_id}/steps/instance-step:kill-product-directly-from-instance-system",
    "post /projects/{project_id}/steps/instance-step:long-running-before-create-instance",
    "get /projects/{project_id}/steps/instance-step:long-running-before-create-instance",
    "patch /projects/{project_id}/steps/instance-step:long-running-before-create-instance",
    "post /projects/{project_id}/steps/instance-step:long-running-before-instance",
    "get /projects/{project_id}/steps/instance-step:long-running-before-instance",
    "patch /projects/{project_id}/steps/instance-step:long-running-before-instance",
    "post /projects/{project_id}/steps/instance-step:set-http-instance-red",
    "get /projects/{project_id}/steps/instance-step:set-http-instance-red",
    "patch /projects/{project_id}/steps/instance-step:set-http-instance-red",
    "post /projects/{project_id}/steps/instance-step:set-http-no-save-red",
    "get /projects/{project_id}/steps/instance-step:set-http-no-save-red",
    "patch /projects/{project_id}/steps/instance-step:set-http-no-save-red",
    "post /projects/{project_id}/steps/instance-step:set-instance-from-entity-handle",
    "get /projects/{project_id}/steps/instance-step:set-instance-from-entity-handle",
    "patch /projects/{project_id}/steps/instance-step:set-instance-from-entity-handle",
    "post /projects/{project_id}/steps/instance-step:set-instance-red",
    "get /projects/{project_id}/steps/instance-step:set-instance-red",
    "patch /projects/{project_id}/steps/instance-step:set-instance-red",
    "post /projects/{project_id}/steps/instance-step:set-is-blue",
    "get /projects/{project_id}/steps/instance-step:set-is-blue",
    "patch /projects/{project_id}/steps/instance-step:set-is-blue",
    "post /projects/{project_id}/steps/instance-step:set-is-blue-from-entity-handle",
    "get /projects/{project_id}/steps/instance-step:set-is-blue-from-entity-handle",
    "patch /projects/{project_id}/steps/instance-step:set-is-blue-from-entity-handle",
    "post /projects/{project_id}/steps/instance-step:set-is-blue-no-type",
    "get /projects/{project_id}/steps/instance-step:set-is-blue-no-type",
    "patch /projects/{project_id}/steps/instance-step:set-is-blue-no-type",
    "post /projects/{project_id}/steps/instance-step:set-is-blue-tcp",
    "get /projects/{project_id}/steps/instance-step:set-is-blue-tcp",
    "patch /projects/{project_id}/steps/instance-step:set-is-blue-tcp",
    "post /projects/{project_id}/steps/instance-step:shutdown",
    "get /projects/{project_id}/steps/instance-step:shutdown",
    "patch /projects/{project_id}/steps/instance-step:shutdown",
    "post /projects/{project_id}/steps/instance-step:shutdown-http",
    "get /projects/{project_id}/steps/instance-step:shutdown-http",
    "patch /projects/{project_id}/steps/instance-step:shutdown-http",
    "post /projects/{project_id}/steps/instance-step:shutdown-tcp",
    "get /projects/{project_id}/steps/instance-step:shutdown-tcp",
    "patch /projects/{project_id}/steps/instance-step:shutdown-tcp",
    "post /projects/{project_id}/steps/instance-step:store-red-in-entity-handle",
    "get /projects/{project_id}/steps/instance-step:store-red-in-entity-handle",
    "patch /projects/{project_id}/steps/instance-step:store-red-in-entity-handle",
    "post /projects/{project_id}/steps/instance-step:unshared-bdm-product-instance",
    "get /projects/{project_id}/steps/instance-step:unshared-bdm-product-instance",
    "patch /projects/{project_id}/steps/instance-step:unshared-bdm-product-instance",
    "post /projects/{project_id}/steps/instance-step:unshared-product-instance",
    "get /projects/{project_id}/steps/instance-step:unshared-product-instance",
    "patch /projects/{project_id}/steps/instance-step:unshared-product-instance",
    "post /projects/{project_id}/steps/other-step:set-is-blue",
    "get /projects/{project_id}/steps/other-step:set-is-blue",
    "patch /projects/{project_id}/steps/other-step:set-is-blue",
    "post /projects/{project_id}/steps/instance-step/instances/x-y",
    "get /projects/{project_id}/steps/instance-step/instances/x-y",
    "patch /projects/{project_id}/steps/instance-step/instances/x-y",
    "delete /projects/{project_id}/steps/instance-step/instances/x-y",
    "post /projects/{project_id}/steps/instance-step/instances/http",
    "get /projects/{project_id}/steps/instance-step/instances/http",
    "patch /projects/{project_id}/steps/instance-step/instances/http",
    "delete /projects/{project_id}/steps/instance-step/instances/http",
    "post /projects/{project_id}/steps/instance-step/instances/http-no-save",
    "get /projects/{project_id}/steps/instance-step/instances/http-no-save",
    "patch /projects/{project_id}/steps/instance-step/instances/http-no-save",
    "delete /projects/{project_id}/steps/instance-step/instances/http-no-save",
    "post /projects/{project_id}/steps/instance-step/instances/tcp",
    "get /projects/{project_id}/steps/instance-step/instances/tcp",
    "patch /projects/{project_id}/steps/instance-step/instances/tcp",
    "delete /projects/{project_id}/steps/instance-step/instances/tcp",
    "put /projects/{project_id}/steps/instance-step/blobs/transfer-entity-handle",
    "put /projects/{project_id}/steps/instance-step/blobs/project",
    "get /projects/{project_id}/steps/instance-step/blobs/{datapath:path}",
    "get /projects/{project_id}/steps/other-step/blobs/{datapath:path}",
    "options /graphql",
    "get /graphql",
    "post /graphql",
    "post /desktop:exit",
    "get /desktop:hps-auth-info",
    "post /projects",
    "post /projects:import",
    "get /projects",
    "get /projects/{project_id}:export",
    "get /projects/{project_id}",
    "patch /projects/{project_id}",
    "post /projects/{project_id}:upgrade",
    "delete /projects/{project_id}",
    "post /projects/{project_id}/bdm-locks",
    "get /projects/{project_id}/bdm-locks/{lock_id}",
    "delete /projects/{project_id}/bdm-locks/{lock_id}",
    "post /events/projects/{project_id}/steps/{step_id}/streams/{stream_name}",
    "get /health",
    "get /schema",
    "get /",
}


async def _verify_http_routes(
    settings: Settings,
    assert_response: Callable[[str, Response], None],
    bearer_token: str = "",
    api_key: str = "",
    base_url: str = "http://localhost",
    peer_client: tuple[str, int] = ("127.0.0.1", 123),
) -> None:
    app = build_mock_app(settings, solution)
    tested_routes: set[str] = set()
    async with (
        LifespanManager(app, startup_timeout=MOCK_APP_STARTUP_TIMEOUT) as manager,
        AsyncClient(
            transport=ASGITransport(app=manager.app, client=peer_client),
            base_url=base_url,
        ) as async_client,
    ):
        for route in app.routes:
            routes = route.original_router.routes if isinstance(route, _IncludedRouter) else [route]
            for sub_route in routes:
                if isinstance(sub_route, APIWebSocketRoute):
                    continue
                for method in sub_route.methods:  # type: ignore
                    http_verb = method.lower()  # type: ignore
                    request_client = getattr(async_client, http_verb)  # pyright: ignore[reportUnknownArgumentType]
                    endpoint = str(sub_route.path)  # type: ignore
                    tested_routes.add(f"{http_verb} {endpoint}")
                    headers: dict[str, str] = {}
                    if api_key:
                        headers["x-api-key"] = api_key
                    elif bearer_token:
                        headers["Authorization"] = f"Bearer {bearer_token}"
                    response = await request_client(endpoint, headers=headers)
                    assert_response(endpoint, response)
    assert tested_routes == EXPECTED_ROUTES


def _assert_authenticated_response(endpoint: str, response: Response) -> None:
    # In most cases, this status_code is actually 404: project not found, because we are not replacing the
    # {project_id} or {step_id} in the endpoint. However, that's on purpose, since otherwise we would trigger
    # real backend operations. It's already enough to test that we passed the authentication.
    assert response.status_code not in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


def _assert_missing_token(endpoint: str, response: Response) -> None:
    if endpoint not in ROUTES_WITHOUT_AUTH:
        # fastapi < 0.122 returns 403. the behaviour changed afterwards, returning 401 instead.
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        assert response.json() == {"detail": "Not authenticated"}
    else:
        assert response.status_code not in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


def _assert_invalid_token(endpoint: str, response: Response) -> None:
    if endpoint not in ROUTES_WITHOUT_AUTH:
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"detail": "Invalid token"}
    else:
        assert response.status_code not in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


async def test_http_routes_require_valid_token(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    mocker.patch.object(
        oidc_scheme._oidc_client,  # pyright: ignore[reportPrivateUsage]
        "validate_access_token",
    )
    await _verify_http_routes(settings, _assert_authenticated_response, bearer_token="my_valid_token")


async def test_http_routes_without_token_return_40x(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    await _verify_http_routes(settings, _assert_missing_token)


async def test_http_routes_without_valid_token_return_401(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    mocker.patch.object(
        oidc_scheme._oidc_client,  # pyright: ignore[reportPrivateUsage]
        "validate_access_token",
        side_effect=ValueError("Invalid token"),
    )
    await _verify_http_routes(settings, _assert_invalid_token, bearer_token="invalid_token")


def _make_token(claims: dict[str, object]) -> str:
    """Build an unsigned JWT-shaped token. Tests using it mock the signature validation."""

    def encode(part: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(part).encode()).decode().rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode(claims)}.signature"


TOKEN_WITH_ROLE = _make_token({"resource_access": {"my-client-id": {"roles": ["portal_user", "app-role"]}}})
TOKEN_BYPASS_ROLE = _make_token({"resource_access": {"my-client-id": {"roles": ["portal_admin"]}}})
TOKEN_WITHOUT_ROLE = _make_token({"resource_access": {"my-client-id": {"roles": ["portal_user"]}}})
TOKEN_WITH_ONLY_APP_ROLE = _make_token({"resource_access": {"my-client-id": {"roles": ["app-role"]}}})
TOKEN_WITH_ROLE_OF_OTHER_CLIENT = _make_token(
    {"resource_access": {"other-client": {"roles": ["portal_user", "app-role"]}}},
)


def _assert_missing_role(endpoint: str, response: Response) -> None:
    if endpoint not in ROUTES_WITHOUT_AUTH:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {"detail": "Forbidden"}
    else:
        assert response.status_code not in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.fixture
def require_app_role(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    monkeypatch.setattr(oidc_scheme_ws, "auto_error", True)
    monkeypatch.setattr(dependencies, "audience", "my-client-id")
    monkeypatch.setattr(dependencies, "required_roles", frozenset({"portal_user", "app-role"}))
    monkeypatch.setattr(dependencies, "bypass_roles", frozenset({"portal_admin"}))
    mocker.patch.object(oidc_scheme._oidc_client, "validate_access_token")  # pyright: ignore[reportPrivateUsage]
    mocker.patch.object(oidc_scheme_ws._oidc_client, "validate_access_token")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.usefixtures("require_app_role")
@pytest.mark.parametrize("token", [TOKEN_WITH_ROLE, TOKEN_BYPASS_ROLE])
async def test_http_routes_accept_token_with_required_or_bypass_role(settings: Settings, token: str):
    await _verify_http_routes(settings, _assert_authenticated_response, bearer_token=token)


@pytest.mark.usefixtures("require_app_role")
@pytest.mark.parametrize(
    "token",
    [TOKEN_WITHOUT_ROLE, TOKEN_WITH_ONLY_APP_ROLE, TOKEN_WITH_ROLE_OF_OTHER_CLIENT, "not-a-jwt"],
)
async def test_http_routes_without_required_role_return_403(settings: Settings, token: str):
    await _verify_http_routes(settings, _assert_missing_role, bearer_token=token)


@pytest.mark.usefixtures("require_app_role")
def test_websocket_routes_without_required_role_raise_1008(settings: Settings):
    app = build_mock_app(settings, solution)
    with TestClient(app) as client:
        for route in app.routes:
            if not isinstance(route, APIWebSocketRoute):
                continue
            for token, forbidden in [(TOKEN_WITHOUT_ROLE, True), (TOKEN_WITH_ROLE, False)]:
                subprotocols = [f"{DEFAULT_SUBPROTOCOL_PREFIX}{encode_base64_token(token)}"]
                if forbidden:
                    with pytest.raises(WebSocketDisconnect) as e, client.websocket_connect(route.path, subprotocols):
                        ...
                    assert e.value.code == WS_1008_POLICY_VIOLATION
                    assert e.value.reason == "Forbidden"
                else:
                    with (
                        pytest.raises(WebSocketDenialResponse) as denial,
                        client.websocket_connect(route.path, subprotocols),
                    ):
                        ...
                    # Using placeholder project_id and getting a 404 is fine. We only want to see if auth is passed.
                    assert "404 Not Found" in str(denial)


def test_websocket_routes_require_valid_token(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    app = build_mock_app(settings, solution)
    monkeypatch.setattr(oidc_scheme_ws, "auto_error", True)
    mocker.patch.object(
        oidc_scheme_ws._oidc_client,  # pyright: ignore[reportPrivateUsage]
        "validate_access_token",
    )
    with TestClient(app) as client:
        for route in app.routes:
            if not isinstance(route, APIWebSocketRoute):
                continue
            valid_token = encode_base64_token("my_valid_token")
            with (
                pytest.raises(WebSocketDenialResponse) as e,
                client.websocket_connect(
                    route.path,
                    subprotocols=[f"{DEFAULT_SUBPROTOCOL_PREFIX}{valid_token}"],
                ),
            ):
                ...
            # Using placeholder project_id and getting a 404 is fine. We only want to see if auth is passed.
            assert "404 Not Found" in str(e)


def test_websocket_routes_without_token_raise_1008(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    app = build_mock_app(settings, solution)
    monkeypatch.setattr(oidc_scheme_ws, "auto_error", True)
    with TestClient(app) as client:
        for route in app.routes:
            if not isinstance(route, APIWebSocketRoute):
                continue
            with pytest.raises(WebSocketDisconnect) as e, client.websocket_connect(route.path):
                ...
            assert e.value.code == WS_1008_POLICY_VIOLATION
            assert e.value.reason == "Not authenticated"


def test_websocket_routes_without_valid_token_raise_1008(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    app = build_mock_app(settings, solution)
    monkeypatch.setattr(oidc_scheme_ws, "auto_error", True)
    mocker.patch.object(
        oidc_scheme_ws._oidc_client,  # pyright: ignore[reportPrivateUsage]
        "validate_access_token",
        side_effect=ValueError("Invalid token"),
    )
    with TestClient(app) as client:
        for route in app.routes:
            if not isinstance(route, APIWebSocketRoute):
                continue
            invalid_token = encode_base64_token("invalid_token")
            with (
                pytest.raises(WebSocketDisconnect) as e,
                client.websocket_connect(
                    route.path,
                    subprotocols=[f"{DEFAULT_SUBPROTOCOL_PREFIX}{invalid_token}"],
                ),
            ):
                ...
            assert e.value.code == WS_1008_POLICY_VIOLATION
            assert e.value.reason == "Invalid token"


async def test_all_routes_ignore_auth_in_desktop_by_default(settings: Settings):
    app = build_mock_app(settings, solution)
    assert settings.glow_deployment == Deployment.Desktop
    assert not oidc_scheme.auto_error
    assert not oidc_scheme_ws.auto_error
    async with (
        LifespanManager(app, startup_timeout=MOCK_APP_STARTUP_TIMEOUT) as manager,
        AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as async_client,
    ):
        # route that uses oidc_scheme
        response = await async_client.get("/projects")
        assert response.status_code == status.HTTP_200_OK
    with TestClient(app) as client:
        # route that uses oidc_scheme_ws
        with (
            pytest.raises(WebSocketDenialResponse) as e,
            client.websocket_connect(
                "/events/projects/{project_id}/steps/{step_id}/streams/{stream_name}",
            ),
        ):
            ...
        # Using placeholder project_id and getting a 404 is fine. We only want to see if auth is passed.
        assert "404 Not Found" in str(e)


DASH_ROUTES_WITHOUT_AUTH = [
    "/health",
    "/favicon.ico",
]
DASH_TESTING_ROUTES = [
    ("get", "/projects/my_project"),
    ("get", "/any_get_route"),
    ("post", "/any_post_route"),
    ("put", "/any_put_route"),
    ("patch", "/any_patch_route"),
    ("delete", "/any_delete_route"),
]


def test_dash_app_requires_valid_token(monkeypatch: pytest.MonkeyPatch, mocker: pytest_mock.MockerFixture):
    mocker.patch.object(OidcClient, "validate_access_token", return_value=None)
    monkeypatch.setenv("GLOW_AUTH_ISSUER_URL", "https://my-issuer-url")
    monkeypatch.setenv("GLOW_AUTH_CLIENT_ID", "my-client-id")
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "False")

    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore
    with flask_app.test_client() as client:
        for route in DASH_ROUTES_WITHOUT_AUTH:
            assert client.get(route).status_code == 200
        assert client.options("/").status_code == 200
        for method, route in DASH_TESTING_ROUTES:
            assert getattr(client, method)(
                route,
                headers={"Authorization": "Bearer my_valid_token"},
            ).status_code not in [403, 401]


def test_dash_app_without_token_returns_403(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_AUTH_ISSUER_URL", "https://my-issuer-url")
    monkeypatch.setenv("GLOW_AUTH_CLIENT_ID", "my-client-id")
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "False")

    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore
    with flask_app.test_client() as client:
        for route in DASH_ROUTES_WITHOUT_AUTH:
            assert client.get(route).status_code == 200
        assert client.options("/").status_code == 200
        for method, route in DASH_TESTING_ROUTES:
            r = getattr(client, method)(route)
            assert (
                "<title>403 Forbidden</title>\n"
                "<h1>Forbidden</h1>\n"
                "<p>You don&#39;t have the permission to access the requested resource."
            ) in r.text
            assert r.status_code == 403


def test_dash_app_without_valid_token_returns_401(monkeypatch: pytest.MonkeyPatch, mocker: pytest_mock.MockerFixture):
    mocker.patch.object(OidcClient, "validate_access_token", side_effect=ValueError("Invalid token"))
    log_error_mock = mocker.patch.object(logging.Logger, "error")
    monkeypatch.setenv("GLOW_AUTH_ISSUER_URL", "https://my-issuer-url")
    monkeypatch.setenv("GLOW_AUTH_CLIENT_ID", "my-client-id")
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "False")

    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore
    with flask_app.test_client() as client:
        for route in DASH_ROUTES_WITHOUT_AUTH:
            assert client.get(route).status_code == 200
        assert client.options("/").status_code == 200
        for method, route in DASH_TESTING_ROUTES:
            r = getattr(client, method)(route, headers={"Authorization": "Bearer invalid_token"})
            assert (
                "<title>401 Unauthorized</title>\n"
                "<h1>Unauthorized</h1>\n"
                "<p>The server could not verify that you are authorized to access the URL requested."
            ) in r.text
            assert r.status_code == 401
    # real error message is logged and not returned to the user.
    assert log_error_mock.call_args_list == [call("Invalid access token: %s", "Invalid token")] * len(
        DASH_TESTING_ROUTES,
    )


@pytest.mark.parametrize(
    ("roles", "expected_status"),
    [
        (["portal_user", "app-role"], 200),
        (["portal_admin"], 200),
        (["portal_user"], 403),
        (["app-role"], 403),
        ([], 403),
    ],
)
def test_dash_app_enforces_required_roles(
    roles: list[str],
    expected_status: int,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
):
    claims = {"resource_access": {"my-client-id": {"roles": roles}}}
    mocker.patch.object(OidcClient, "validate_access_token", return_value=mocker.Mock(claims=claims))
    monkeypatch.setenv("GLOW_AUTH_ISSUER_URL", "https://my-issuer-url")
    monkeypatch.setenv("GLOW_AUTH_CLIENT_ID", "my-client-id")
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "False")
    monkeypatch.setenv("GLOW_AUTH_REQUIRED_ROLES", "portal_user, app-role")
    monkeypatch.setenv("GLOW_AUTH_BYPASS_ROLES", "portal_admin")

    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore
    with flask_app.test_client() as client:
        for route in DASH_ROUTES_WITHOUT_AUTH:
            assert client.get(route).status_code == 200
        for method, route in DASH_TESTING_ROUTES:
            r = getattr(client, method)(route, headers={"Authorization": "Bearer my_valid_token"})
            if expected_status == 403:
                assert r.status_code == 403
            else:
                assert r.status_code not in [403, 401]


def test_dash_app_ignores_required_roles_when_auth_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "True")
    monkeypatch.setenv("GLOW_AUTH_REQUIRED_ROLES", "app-role")

    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore
    with flask_app.test_client() as client:
        for method, route in DASH_TESTING_ROUTES:
            assert getattr(client, method)(route).status_code not in [403, 401]


@pytest.mark.parametrize(
    ("issuer_url", "client_id"),
    [(None, "my-client-id"), ("https://my-issuer-url", None), (None, None)],
)
def test_dash_app_with_validation_requires_auth_env_vars(
    monkeypatch: pytest.MonkeyPatch,
    issuer_url: str | None,
    client_id: str | None,
):
    if issuer_url is not None:
        monkeypatch.setenv("GLOW_AUTH_ISSUER_URL", issuer_url)
    else:
        monkeypatch.delenv("GLOW_AUTH_ISSUER_URL", raising=False)
    if client_id is not None:
        monkeypatch.setenv("GLOW_AUTH_CLIENT_ID", client_id)
    else:
        monkeypatch.delenv("GLOW_AUTH_CLIENT_ID", raising=False)
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "False")

    error_msg = (
        "Authentication cannot be enforced without setting environment variables GLOW_AUTH_ISSUER_URL and "
        "GLOW_AUTH_CLIENT_ID."
    )
    with pytest.raises(RuntimeError, match=error_msg):
        _ = build_mock_dash_app(monkeypatch)


def test_dash_app_ignores_auth_on_desktop_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_DEPLOYMENT", "Desktop")

    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore
    with flask_app.test_client() as client:
        for route in DASH_ROUTES_WITHOUT_AUTH:
            assert client.get(route).status_code == 200
        assert client.options("/").status_code == 200
        for method, route in DASH_TESTING_ROUTES:
            assert getattr(client, method)(route).status_code not in [403, 401]


@pytest.mark.parametrize("dash_version", ["invalid_version", "2.18.1"])
def test_dash_app_with_old_dash_version_and_token_logs_warning(
    dash_version: str,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
):
    mocker.patch.object(OidcClient, "validate_access_token", return_value=None)
    mocker.patch("dash.__version__", dash_version)
    monkeypatch.setenv("GLOW_AUTH_ISSUER_URL", "https://my-issuer-url")
    monkeypatch.setenv("GLOW_AUTH_CLIENT_ID", "my-client-id")
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "False")
    log_warning_mock = mocker.patch.object(logging.Logger, "warning")

    expected_warning_msgs: list[str] = []
    if dash_version == "invalid_version":
        expected_warning_msgs.append("Dash version could not be parsed. Assuming lower than 2.18.2.")
    expected_warning_msgs.append(
        "Dash version is invalid or lower than 2.18.2. Authorization token is present but cannot be "
        "propagated unless Dash is upgraded to 2.18.2 or higher.",
    )

    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore
    with flask_app.test_client() as client:
        r = client.get("/projects/my_project", headers={"Authorization": "Bearer my_valid_token"})
        assert r.status_code == 200
    assert log_warning_mock.call_args_list == [call(msg) for msg in expected_warning_msgs]
    log_warning_mock.reset_mock()

    # Assert that warning doesn't depend on auth being enforced, just on the presence of the token
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "True")

    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore
    with flask_app.test_client() as client:
        r = client.get("/projects/my_project", headers={"Authorization": "Bearer my_valid_token"})
        assert r.status_code == 200
        assert log_warning_mock.call_args_list == [call(msg) for msg in expected_warning_msgs]
        log_warning_mock.reset_mock()
        r = client.get("/projects/my_project")
        assert r.status_code == 200
        log_warning_mock.assert_not_called()


@pytest.mark.parametrize(
    "settings",
    [{"glow_api_key": "my-secret-api-key"}],
    ids=["with_api_key"],
    indirect=["settings"],
)
async def test_localhost_with_valid_api_key_bypasses_oidc_http(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
):
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    oidc_scheme_call = mocker.patch.object(dependencies.oidc_scheme, "__call__")
    await _verify_http_routes(settings, _assert_authenticated_response, api_key="my-secret-api-key")
    oidc_scheme_call.assert_not_called()


@pytest.mark.parametrize(
    "settings",
    [{"glow_api_key": "my-secret-api-key"}],
    ids=["with_api_key"],
    indirect=["settings"],
)
async def test_localhost_without_api_key_falls_through_to_oidc_http(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    await _verify_http_routes(settings, _assert_missing_token)


@pytest.mark.parametrize(
    "settings",
    [{"glow_api_key": "my-secret-api-key"}],
    ids=["with_api_key"],
    indirect=["settings"],
)
async def test_localhost_with_wrong_api_key_falls_through_to_oidc_http(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
):
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    mocker.patch.object(
        oidc_scheme._oidc_client,  # pyright: ignore[reportPrivateUsage]
        "validate_access_token",
        side_effect=ValueError("Invalid token"),
    )
    await _verify_http_routes(settings, _assert_missing_token, api_key="wrong-key")


@pytest.mark.parametrize(
    "settings",
    [{"glow_api_key": "my-secret-api-key"}],
    ids=["with_api_key"],
    indirect=["settings"],
)
async def test_non_localhost_with_valid_api_key_falls_through_to_oidc_http(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
):
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    mocker.patch.object(
        oidc_scheme._oidc_client,  # pyright: ignore[reportPrivateUsage]
        "validate_access_token",
        side_effect=ValueError("Invalid token"),
    )
    await _verify_http_routes(
        settings,
        _assert_missing_token,
        api_key="my-secret-api-key",
        base_url="http://external-host",
        peer_client=("192.168.1.100", 12345),
    )


@pytest.mark.parametrize(
    "settings",
    [{"glow_api_key": "my-secret-api-key"}],
    ids=["with_api_key"],
    indirect=["settings"],
)
async def test_spoofed_host_header_with_valid_api_key_cannot_bypass_oidc_http(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
):
    monkeypatch.setattr(oidc_scheme, "auto_error", True)
    mocker.patch.object(
        oidc_scheme._oidc_client,  # pyright: ignore[reportPrivateUsage]
        "validate_access_token",
        side_effect=ValueError("Invalid token"),
    )
    # Peer is a remote IP, but Host header is "localhost" (spoofed).
    await _verify_http_routes(
        settings,
        _assert_missing_token,
        api_key="my-secret-api-key",
        base_url="http://localhost",
        peer_client=("192.168.1.100", 12345),
    )
