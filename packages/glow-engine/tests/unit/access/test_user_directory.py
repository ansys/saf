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

"""Unit tests for the pluggable user directory of the UI server."""

from collections.abc import Sequence

from flask import Flask
from pydantic import SecretStr
import pytest
from pytest_httpx2 import HTTPXMock

from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._ui import user_directory
from ansys.saf.glow._ui.user_directory import (
    KeycloakUserDirectory,
    MsGraphUserDirectory,
    NoUserDirectory,
    ScimUserDirectory,
    create_user_directory,
    get_user_directory,
    set_user_directory,
)
from tests.mocks.solutions import minimal_solution
from tests.unit.conftest import build_mock_dash_app

solution = minimal_solution

BASE_URL = "http://keycloak.test"
REALM = "myrealm"
TOKEN_URL = f"{BASE_URL}/realms/{REALM}/protocol/openid-connect/token"
USERS_URL = f"{BASE_URL}/admin/realms/{REALM}/users"


@pytest.fixture
def directory() -> KeycloakUserDirectory:
    return KeycloakUserDirectory(BASE_URL, REALM, "my-client", "my-secret")


def _add_token(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=TOKEN_URL,
        json={"access_token": "tok", "expires_in": 300},
        is_optional=True,
    )


def test_keycloak_resolve_by_email(httpx_mock: HTTPXMock, directory: KeycloakUserDirectory):
    _add_token(httpx_mock)
    httpx_mock.add_response(url=f"{USERS_URL}?email=a%40b.com&exact=true", json=[{"id": "u1", "username": "a"}])

    assert directory.resolve("a@b.com") == "u1"

    token_request = next(r for r in httpx_mock.get_requests() if r.url.path.endswith("/token"))
    body = token_request.content.decode()
    assert "grant_type=client_credentials" in body
    assert "client_id=my-client" in body
    assert "client_secret=my-secret" in body
    users_request = next(r for r in httpx_mock.get_requests() if r.url.path.endswith("/users"))
    assert users_request.headers["Authorization"] == "Bearer tok"


def test_keycloak_resolve_falls_back_to_username(httpx_mock: HTTPXMock, directory: KeycloakUserDirectory):
    _add_token(httpx_mock)
    httpx_mock.add_response(url=f"{USERS_URL}?email=alice&exact=true", json=[])
    httpx_mock.add_response(url=f"{USERS_URL}?username=alice&exact=true", json=[{"id": "u2", "username": "alice"}])

    assert directory.resolve("alice") == "u2"


def test_keycloak_resolve_ambiguous_returns_none(httpx_mock: HTTPXMock, directory: KeycloakUserDirectory):
    _add_token(httpx_mock)
    httpx_mock.add_response(url=f"{USERS_URL}?email=alice&exact=true", json=[{"id": "u1"}, {"id": "u2"}])
    httpx_mock.add_response(url=f"{USERS_URL}?username=alice&exact=true", json=[{"id": "u1"}], is_optional=True)

    assert directory.resolve("alice") is None


def test_keycloak_resolve_no_match_returns_none(httpx_mock: HTTPXMock, directory: KeycloakUserDirectory):
    _add_token(httpx_mock)
    httpx_mock.add_response(url=f"{USERS_URL}?email=ghost&exact=true", json=[])
    httpx_mock.add_response(url=f"{USERS_URL}?username=ghost&exact=true", json=[])

    assert directory.resolve("ghost") is None


def test_keycloak_display_names_cached(httpx_mock: HTTPXMock, directory: KeycloakUserDirectory):
    _add_token(httpx_mock)
    httpx_mock.add_response(url=f"{USERS_URL}/u1", json={"id": "u1", "firstName": "Ada", "lastName": "Lovelace"})
    httpx_mock.add_response(url=f"{USERS_URL}/u2", json={"id": "u2", "username": "bob"})

    first = directory.display_names(["u1", "u2"])
    requests_after_first = len(httpx_mock.get_requests())
    second = directory.display_names(["u1", "u2"])

    assert first == {"u1": "Ada Lovelace", "u2": "bob"}
    assert second == first
    assert len(httpx_mock.get_requests()) == requests_after_first


def test_keycloak_cache_expires(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch):
    now = [1000.0]
    monkeypatch.setattr(user_directory.time, "monotonic", lambda: now[0])
    directory = KeycloakUserDirectory(BASE_URL, REALM, "my-client", "my-secret", cache_ttl_seconds=10)
    httpx_mock.add_response(method="POST", url=TOKEN_URL, json={"access_token": "tok", "expires_in": 3600})
    httpx_mock.add_response(url=f"{USERS_URL}/u1", json={"id": "u1", "username": "ada"})
    httpx_mock.add_response(url=f"{USERS_URL}/u1", json={"id": "u1", "username": "ada"})

    assert directory.display_names(["u1"]) == {"u1": "ada"}
    now[0] += 11
    assert directory.display_names(["u1"]) == {"u1": "ada"}
    assert len([r for r in httpx_mock.get_requests() if r.url.path.endswith("/users/u1")]) == 2


def test_keycloak_unknown_id_omitted(httpx_mock: HTTPXMock, directory: KeycloakUserDirectory):
    _add_token(httpx_mock)
    httpx_mock.add_response(url=f"{USERS_URL}/known", json={"id": "known", "username": "carol"})
    httpx_mock.add_response(url=f"{USERS_URL}/unknown", status_code=404, json={"error": "User not found"})

    assert directory.display_names(["known", "unknown"]) == {"known": "carol"}


def test_no_directory_resolve_rules():
    directory = NoUserDirectory()

    assert directory.resolve("  user-1 ") == "user-1"
    assert directory.resolve("a@b.com") is None
    assert directory.resolve("two words") is None
    assert directory.resolve("   ") is None
    assert directory.resolve("") is None
    assert directory.display_names(["x", "y"]) == {"x": "x", "y": "y"}


def test_placeholders_raise_not_implemented(settings: Settings):
    with pytest.raises(NotImplementedError, match="SCIM user directory is not implemented yet"):
        ScimUserDirectory()
    with pytest.raises(NotImplementedError, match="Microsoft Graph user directory is not implemented yet"):
        MsGraphUserDirectory()

    with pytest.raises(NotImplementedError, match="SCIM"):
        create_user_directory(settings.model_copy(update={"glow_ui_user_directory": "scim"}))
    with pytest.raises(NotImplementedError, match="Microsoft Graph"):
        create_user_directory(settings.model_copy(update={"glow_ui_user_directory": "msgraph"}))


def test_missing_keycloak_settings_raise(settings: Settings):
    settings = settings.model_copy(update={"glow_ui_user_directory": "keycloak", "glow_ui_keycloak_url": BASE_URL})

    with pytest.raises(ValueError, match="GLOW_UI_USER_DIRECTORY=keycloak") as exc_info:
        create_user_directory(settings)
    message = str(exc_info.value)
    for name in ("GLOW_UI_KEYCLOAK_REALM", "GLOW_UI_KEYCLOAK_CLIENT_ID", "GLOW_UI_KEYCLOAK_CLIENT_SECRET"):
        assert name in message
    assert "GLOW_UI_KEYCLOAK_URL" not in message


def test_create_user_directory_selection(settings: Settings):
    assert isinstance(create_user_directory(settings), NoUserDirectory)

    settings = settings.model_copy(
        update={
            "glow_ui_user_directory": "keycloak",
            "glow_ui_keycloak_url": BASE_URL,
            "glow_ui_keycloak_realm": REALM,
            "glow_ui_keycloak_client_id": "my-client",
            "glow_ui_keycloak_client_secret": SecretStr("my-secret"),
        },
    )
    assert isinstance(create_user_directory(settings), KeycloakUserDirectory)


class _FakeDirectory:
    def resolve(self, identifier: str) -> str | None:
        return {"alice@x.com": "uid-alice"}.get(identifier)

    def display_names(self, user_ids: Sequence[str]) -> dict[str, str]:
        return {u: f"Name of {u}" for u in user_ids if u != "gone"}


@pytest.fixture
def flask_app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    monkeypatch.setenv("GLOW_AUTH_DISABLED", "True")
    monkeypatch.setattr(user_directory, "_user_directory", NoUserDirectory())
    ui_app = build_mock_dash_app(monkeypatch)
    return ui_app.server  # type: ignore


def test_flask_routes_resolve_and_names(flask_app: Flask):
    assert isinstance(get_user_directory(), NoUserDirectory)
    set_user_directory(_FakeDirectory())
    with flask_app.test_client() as client:
        response = client.get("/_saf/users/resolve", query_string={"q": "alice@x.com"})
        assert response.status_code == 200
        assert response.get_json() == {"user_id": "uid-alice"}
        assert response.headers["Cache-Control"] == "no-store"

        response = client.get("/_saf/users/resolve", query_string={"q": "nobody"})
        assert response.status_code == 404
        assert response.headers["Cache-Control"] == "no-store"

        response = client.get("/_saf/users/resolve")
        assert response.status_code == 404

        response = client.post("/_saf/users/names", json={"user_ids": ["u1", "gone"]})
        assert response.status_code == 200
        assert response.get_json() == {"names": {"u1": "Name of u1"}}
        assert response.headers["Cache-Control"] == "no-store"


def test_flask_routes_use_directory_built_from_settings(flask_app: Flask):
    # create_app builds the directory from settings: "none" resolves bare ids only.
    with flask_app.test_client() as client:
        assert client.get("/_saf/users/resolve", query_string={"q": "user-1"}).get_json() == {"user_id": "user-1"}
        assert client.get("/_saf/users/resolve", query_string={"q": "a@b.com"}).status_code == 404
        assert client.post("/_saf/users/names", json={"user_ids": ["user-1"]}).get_json() == {
            "names": {"user-1": "user-1"},
        }


def test_names_limit_400(flask_app: Flask):
    with flask_app.test_client() as client:
        ok = client.post("/_saf/users/names", json={"user_ids": [f"u{i}" for i in range(200)]})
        assert ok.status_code == 200
        too_many = client.post("/_saf/users/names", json={"user_ids": [f"u{i}" for i in range(201)]})
        assert too_many.status_code == 400
        assert too_many.headers["Cache-Control"] == "no-store"
        for bad in ({}, {"user_ids": "u1"}, {"user_ids": [1, 2]}):
            response = client.post("/_saf/users/names", json=bad)
            assert response.status_code == 400


def test_routes_directory_failure_returns_502(flask_app: Flask):
    class _Failing:
        def resolve(self, identifier: str) -> str | None:
            raise RuntimeError("boom")

        def display_names(self, user_ids: Sequence[str]) -> dict[str, str]:
            raise RuntimeError("boom")

    set_user_directory(_Failing())
    with flask_app.test_client() as client:
        assert client.get("/_saf/users/resolve", query_string={"q": "x"}).status_code == 502
        assert client.post("/_saf/users/names", json={"user_ids": ["x"]}).status_code == 502
