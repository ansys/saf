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

import contextlib
import datetime
import re
import time
from typing import Any

from joserfc import jwt
from joserfc.jwk import OctKey
import pytest
from pytest_httpx2 import HTTPXMock

from ansys.iam.oidc import AsyncOidcClient, NoIssuerError, NoIssuerOrAudienceError, OidcClient
from tests.conftest import IDP_URL  # pyright: ignore

pytestmark = pytest.mark.httpx_mock(assert_all_responses_were_requested=False)


OPENID_CONFIG_URL = f"{IDP_URL}/.well-known/openid-configuration"


@pytest.fixture
def header(secret_key: OctKey) -> dict[str, Any]:
    return {"alg": "HS256", "kid": secret_key.kid}


class TestAsyncOidcClient:
    @pytest.fixture
    def async_oidc_client(self, httpx_mock: HTTPXMock, secret_key: OctKey) -> AsyncOidcClient:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(
            url="http://jwks_uri",
            json=keys,
        )
        return AsyncOidcClient(issuer=IDP_URL, audience="audience1")

    def test_metadata_server_without_issuer(self) -> None:
        client = AsyncOidcClient(issuer=None)
        with pytest.raises(
            NoIssuerError,
            match=re.escape("Cannot build OpenID configuration URL because issuer URL is not set."),
        ):
            _ = client.metadata_server

    @pytest.mark.parametrize(
        ("issuer", "audience"),
        [("http://test-issuer", None), (None, "test-audience"), (None, None)],
    )
    async def test_validate_access_token_without_issuer_or_audience(
        self,
        issuer: str | None,
        audience: str | None,
        dummy_jwt_token: str,
    ) -> None:
        client = AsyncOidcClient(issuer=issuer, audience=audience)
        with pytest.raises(
            NoIssuerOrAudienceError,
            match=re.escape("Cannot validate access token because issuer URL or audience is not set."),
        ):
            await client.validate_access_token(dummy_jwt_token)

    @pytest.mark.httpx_mock(assert_all_responses_were_requested=True)
    async def test_validate_token_call_server_metadata_and_jwks(
        self,
        async_oidc_client: AsyncOidcClient,
        dummy_jwt_token: str,
    ) -> None:
        with contextlib.suppress(Exception):
            await async_oidc_client.validate_access_token(dummy_jwt_token)

    async def test_validate_token_wrong_key(
        self,
        httpx_mock: HTTPXMock,
        dummy_jwt_token: str,
        wrong_secret_key: OctKey,
    ) -> None:
        keys = {"keys": [wrong_secret_key.as_dict()]}
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri"},
        )
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        async_oidc_client = AsyncOidcClient(issuer=IDP_URL, audience="audience1")
        with pytest.raises(ValueError, match="No key for kid"):
            await async_oidc_client.validate_access_token(dummy_jwt_token)

    async def test_validate_expired_token(
        self,
        async_oidc_client: AsyncOidcClient,
        secret_key: OctKey,
        claims: dict[str, Any],
    ) -> None:
        header = {"alg": "HS256", "kid": secret_key.kid}
        claims["exp"] = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=10)
        expired_token = jwt.encode(header, claims, secret_key)
        with pytest.raises(ValueError, match="The token is invalid: The token is expired"):
            await async_oidc_client.validate_access_token(expired_token)

    async def test_validate_token_wrong_iss(
        self,
        async_oidc_client: AsyncOidcClient,
        secret_key: OctKey,
        claims: dict[str, Any],
    ) -> None:
        header = {"alg": "HS256", "kid": secret_key.kid}
        claims["iss"] = "http://wrong_url"
        token = jwt.encode(header, claims, secret_key)
        with pytest.raises(ValueError, match="The token is invalid: Invalid claim: 'iss'"):
            await async_oidc_client.validate_access_token(token)

    async def test_validate_token_wrong_aud(
        self,
        async_oidc_client: AsyncOidcClient,
        secret_key: OctKey,
        claims: dict[str, Any],
    ) -> None:
        header = {"alg": "HS256", "kid": secret_key.kid}
        claims["aud"] = ["wrong_audience"]
        token = jwt.encode(header, claims, secret_key)
        with pytest.raises(ValueError, match="The token is invalid: Invalid claim: 'aud'"):
            await async_oidc_client.validate_access_token(token)

    async def test_validate_token_wrong_nbf(
        self,
        async_oidc_client: AsyncOidcClient,
        secret_key: OctKey,
        claims: dict[str, Any],
    ) -> None:
        header = {"alg": "HS256", "kid": secret_key.kid}
        claims["nbf"] = int(time.time()) + 3600 * 10
        token = jwt.encode(header, claims, secret_key)
        with pytest.raises(ValueError, match="The token is invalid: The token is not yet valid"):
            await async_oidc_client.validate_access_token(token)


class TestOidcClient:
    @pytest.fixture
    def oidc_client(self, httpx_mock: HTTPXMock, secret_key: OctKey) -> OidcClient:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(
            url="http://jwks_uri",
            json=keys,
        )
        return OidcClient(issuer=IDP_URL, audience="audience1")

    def test_metadata_server_without_issuer(self) -> None:
        client = OidcClient(issuer=None)
        with pytest.raises(
            NoIssuerError,
            match=re.escape("Cannot build OpenID configuration URL because issuer URL is not set."),
        ):
            _ = client.metadata_server

    @pytest.mark.parametrize(
        ("issuer", "audience"),
        [("http://test-issuer", None), (None, "test-audience"), (None, None)],
    )
    def test_validate_access_token_without_issuer_or_audience(
        self,
        issuer: str | None,
        audience: str | None,
        dummy_jwt_token: str,
    ) -> None:
        client = OidcClient(issuer=issuer, audience=audience)
        with pytest.raises(
            NoIssuerOrAudienceError,
            match=re.escape("Cannot validate access token because issuer URL or audience is not set."),
        ):
            client.validate_access_token(dummy_jwt_token)

    @pytest.mark.httpx_mock(assert_all_responses_were_requested=True)
    def test_validate_token_call_server_metadata_and_jwks(self, oidc_client: OidcClient, dummy_jwt_token: str) -> None:
        with contextlib.suppress(Exception):
            oidc_client.validate_access_token(dummy_jwt_token)

    def test_validate_token_wrong_key(
        self,
        httpx_mock: HTTPXMock,
        dummy_jwt_token: str,
        wrong_secret_key: OctKey,
    ) -> None:
        keys = {"keys": [wrong_secret_key.as_dict()]}
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri"},
        )
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        oidc_client = OidcClient(issuer=IDP_URL, audience="audience1")
        with pytest.raises(ValueError, match="No key for kid"):
            oidc_client.validate_access_token(dummy_jwt_token)

    def test_validate_expired_token(self, oidc_client: OidcClient, secret_key: OctKey, claims: dict[str, Any]) -> None:
        header = {"alg": "HS256", "kid": secret_key.kid}
        claims["exp"] = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=10)
        expired_token = jwt.encode(header, claims, secret_key)
        with pytest.raises(ValueError, match="The token is invalid: The token is expired"):
            oidc_client.validate_access_token(expired_token)

    def test_validate_token_wrong_iss(
        self,
        oidc_client: OidcClient,
        secret_key: OctKey,
        claims: dict[str, Any],
    ) -> None:
        header = {"alg": "HS256", "kid": secret_key.kid}
        claims["iss"] = "http://wrong_url"
        token = jwt.encode(header, claims, secret_key)
        with pytest.raises(ValueError, match="The token is invalid: Invalid claim: 'iss'"):
            oidc_client.validate_access_token(token)

    def test_validate_token_wrong_aud(
        self,
        oidc_client: OidcClient,
        secret_key: OctKey,
        claims: dict[str, Any],
    ) -> None:
        header = {"alg": "HS256", "kid": secret_key.kid}
        claims["aud"] = ["wrong_audience"]
        token = jwt.encode(header, claims, secret_key)
        with pytest.raises(ValueError, match="The token is invalid: Invalid claim: 'aud'"):
            oidc_client.validate_access_token(token)

    def test_validate_token_wrong_nbf(
        self,
        oidc_client: OidcClient,
        secret_key: OctKey,
        claims: dict[str, Any],
    ) -> None:
        header = {"alg": "HS256", "kid": secret_key.kid}
        claims["nbf"] = int(time.time()) + 3600 * 10
        token = jwt.encode(header, claims, secret_key)
        with pytest.raises(ValueError, match="The token is invalid: The token is not yet valid"):
            oidc_client.validate_access_token(token)
