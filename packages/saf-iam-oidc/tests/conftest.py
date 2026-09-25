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

from collections.abc import Generator
import datetime
import logging
import time
from typing import Annotated, Any

from fastapi import Depends, FastAPI, WebSocket
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import OctKey
import pytest

from ansys.iam.oidc._fastapi import OidcDependency, OidcWebSocketDependency
from ansys.iam.oidc._utilities import encode_base64_token

######################################################## TOKENS ########################################################


IDP_URL = "http://test_issuer_url"
TEST_SECRET_KEY = "this_is_a_very_secure_test_key"
TEST_WRONG_SECRET_KEY = "this_is_a_different_secure_test_key"


@pytest.fixture
def secret_key() -> OctKey:
    key = OctKey.import_key(TEST_SECRET_KEY)
    key.ensure_kid()
    return key


@pytest.fixture
def wrong_secret_key() -> OctKey:
    key = OctKey.import_key(TEST_WRONG_SECRET_KEY)
    key.ensure_kid()
    return key


@pytest.fixture
def claims() -> dict[str, Any]:
    return {
        "iss": IDP_URL,
        "sid": "fake_session_id",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()) - 3600 * 5,
        "preferred_username": "admin",
        "email": "admin@glow.com",
        "email_verified": False,
        "roles": ["admin"],
        "groups": ["admin"],
        "aud": ["audience1", "audience2"],
    }


@pytest.fixture
def incomplete_claims(claims: dict[str, Any]) -> dict[str, Any]:
    claims.pop("preferred_username", None)
    return claims


@pytest.fixture
def encode_token(request: pytest.FixtureRequest) -> bool:
    return getattr(request, "param", False)


@pytest.fixture
def dummy_jwt_token(claims: dict[str, Any], encode_token: bool) -> str:
    key = OctKey.import_key(TEST_SECRET_KEY)
    key.ensure_kid()
    header = {"alg": "HS256", "kid": key.kid}
    token = jwt.encode(header, claims, key)
    return token if not encode_token else encode_base64_token(token)


@pytest.fixture
def incomplete_dummy_jwt_token(incomplete_claims: dict[str, Any], encode_token: bool) -> str:
    key = OctKey.import_key(TEST_SECRET_KEY)
    key.ensure_kid()
    header = {"alg": "HS256", "kid": key.kid}
    token = jwt.encode(header, incomplete_claims, key)
    return token if not encode_token else encode_base64_token(token)


@pytest.fixture
def expired_jwt_token(secret_key: OctKey, claims: dict[str, Any], encode_token: bool) -> str:
    header = {"alg": "HS256", "kid": secret_key.kid}
    claims["exp"] = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=10)
    token = jwt.encode(header, claims, secret_key)
    return token if not encode_token else encode_base64_token(token)


@pytest.fixture
def jwt_token_wrong_iss(secret_key: OctKey, claims: dict[str, Any], encode_token: bool) -> str:
    header = {"alg": "HS256", "kid": secret_key.kid}
    claims["iss"] = "http://wrong_url"
    token = jwt.encode(header, claims, secret_key)
    return token if not encode_token else encode_base64_token(token)


@pytest.fixture
def jwt_token_wrong_aud(secret_key: OctKey, claims: dict[str, Any], encode_token: bool) -> str:
    header = {"alg": "HS256", "kid": secret_key.kid}
    claims["aud"] = ["wrong_audience"]
    token = jwt.encode(header, claims, secret_key)
    return token if not encode_token else encode_base64_token(token)


@pytest.fixture
def jwt_token_wrong_nbf(secret_key: OctKey, claims: dict[str, Any], encode_token: bool) -> str:
    header = {"alg": "HS256", "kid": secret_key.kid}
    claims["nbf"] = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(hours=10)
    token = jwt.encode(header, claims, secret_key)
    return token if not encode_token else encode_base64_token(token)


@pytest.fixture
def invalid_token(request: pytest.FixtureRequest) -> str:
    token_type = getattr(request, "param", None)

    match token_type:
        case "expired":
            return request.getfixturevalue("expired_jwt_token")
        case "wrong_iss":
            return request.getfixturevalue("jwt_token_wrong_iss")
        case "wrong_aud":
            return request.getfixturevalue("jwt_token_wrong_aud")
        case "wrong_nbf":
            return request.getfixturevalue("jwt_token_wrong_nbf")
        case _:
            msg = f"Invalid token type: {token_type}. Expected 'expired', 'wrong_iss', 'wrong_aud', or 'wrong_nbf'."
            raise ValueError(
                msg,
            )


####################################################### LOGGING #######################################################


@pytest.fixture
def caplog(caplog: pytest.LogCaptureFixture, request: pytest.FixtureRequest) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.DEBUG, logger=request.param)
    return caplog


##################################################### FASTAPI APP #####################################################


def get_mock_fastapi_app() -> FastAPI:
    app = FastAPI()

    oidc_scheme = OidcDependency("http://test_issuer_url", "audience1")
    oidc_scheme_optional = OidcDependency("http://test_issuer_url", "audience1", auto_error=False)
    oidc_scheme_without_issuer = OidcDependency(auto_error=False)
    ws_oidc_scheme = OidcWebSocketDependency("http://test_issuer_url", "audience1")
    ws_oidc_scheme_custom_prefix = OidcWebSocketDependency(
        "http://test_issuer_url",
        "audience1",
        subprotocol_prefix="my.mock.prefix.",
    )
    ws_oidc_scheme_optional = OidcWebSocketDependency("http://test_issuer_url", "audience1", auto_error=False)
    ws_oidc_scheme_without_issuer = OidcWebSocketDependency(auto_error=False)

    @app.get("/token")
    async def read_token(token: Annotated[str, Depends(oidc_scheme)]) -> str:  # pyright: ignore[reportUnusedFunction]
        return token

    @app.get("/token_optional_auth")
    async def read_token_optional_auth(  # pyright: ignore[reportUnusedFunction]
        token: Annotated[str | None, Depends(oidc_scheme_optional)],
    ) -> str | None:
        return token

    @app.get("/token_without_issuer_auth")
    async def read_token_without_issuer_auth(  # pyright: ignore[reportUnusedFunction]
        token: Annotated[str | None, Depends(oidc_scheme_without_issuer)],
    ) -> str | None:
        return token

    @app.websocket("/token")
    async def read_ws_token(  # pyright: ignore[reportUnusedFunction]
        websocket: WebSocket,
        token: Annotated[str, Depends(ws_oidc_scheme)],
    ) -> None:
        await websocket.accept()
        await websocket.send_text(token)

    @app.websocket("/token_custom_prefix")
    async def read_ws_token_custom_prefix(  # pyright: ignore[reportUnusedFunction]
        websocket: WebSocket,
        token: Annotated[str, Depends(ws_oidc_scheme_custom_prefix)],
    ) -> None:
        await websocket.accept()
        await websocket.send_text(token)

    @app.websocket("/token_optional_auth")
    async def read_ws_token_optional_auth(  # pyright: ignore[reportUnusedFunction]
        websocket: WebSocket,
        token: Annotated[str | None, Depends(ws_oidc_scheme_optional)],
    ) -> None:
        await websocket.accept()
        await websocket.send_text(token or "no_token")

    @app.websocket("/token_without_issuer_auth")
    async def read_ws_token_without_issuer_auth(  # pyright: ignore[reportUnusedFunction]
        websocket: WebSocket,
        token: Annotated[str | None, Depends(ws_oidc_scheme_without_issuer)],
    ) -> None:
        await websocket.accept()
        await websocket.send_text(token or "no_token")

    return app


@pytest.fixture(scope="session")
def mock_app() -> FastAPI:
    return get_mock_fastapi_app()


@pytest.fixture(scope="session")
def client(mock_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(mock_app) as client:
        yield client
