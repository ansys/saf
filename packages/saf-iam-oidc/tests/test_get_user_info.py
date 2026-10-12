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

import re
from typing import Any

from joserfc.jwk import OctKey
import pytest
from pytest_httpx2 import HTTPXMock

from ansys.iam.oidc import AsyncOidcClient, NoIssuerError, OidcClient
from tests.conftest import IDP_URL  # pyright: ignore

pytestmark = pytest.mark.httpx_mock(assert_all_responses_were_requested=False)


OPENID_CONFIG_URL = f"{IDP_URL}/.well-known/openid-configuration"


@pytest.fixture
def header(secret_key: OctKey) -> dict[str, Any]:
    return {"alg": "HS256", "kid": secret_key.kid}


class TestGetUserInfoSync:
    def test_get_userinfo_on_complete_token(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        userinfo = oidc_client.get_user_info(dummy_jwt_token, fields=["preferred_username", "email_verified"])
        assert userinfo.preferred_username == "admin"
        assert not userinfo.email_verified
        requested_urls = {str(r.url) for r in httpx_mock.get_requests()}
        assert "http://userinfo_uri" not in requested_urls

    def test_get_userinfo_on_incomplete_token_and_complete_response(
        self,
        incomplete_dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "preferred_username": "j.doe",
                "email": "janedoe@example.com",
                "email_verified": False,
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        # Requesting a field that is not present in the token
        userinfo = oidc_client.get_user_info(
            incomplete_dummy_jwt_token,
            fields=["preferred_username", "email_verified"],
        )
        # The user info is retrieved from the userinfo endpoint
        assert userinfo.sub == "248289761001"
        assert userinfo.name == "Jane Doe"
        assert userinfo.preferred_username == "j.doe"
        assert not userinfo.email_verified

    def test_get_userinfo_on_incomplete_token_and_incomplete_response(
        self,
        incomplete_dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        # Requesting a field that is not present in the token nor in the userinfo response
        with pytest.raises(
            ValueError,
            match=re.escape("The userinfo response does not include all required fields: ['preferred_username']."),
        ):
            oidc_client.get_user_info(incomplete_dummy_jwt_token, fields=["preferred_username"])

    def test_get_userinfo_with_non_existent_field(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        with pytest.raises(
            ValueError,
            match=re.escape("Invalid field(s) requested: ['non_existent_field']. Valid fields are:"),
        ):
            oidc_client.get_user_info(dummy_jwt_token, fields=["non_existent_field"])

    def test_get_userinfo_with_no_fields(self, dummy_jwt_token: str, httpx_mock: HTTPXMock, secret_key: OctKey) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        userinfo = oidc_client.get_user_info(dummy_jwt_token)
        assert userinfo.preferred_username == "admin"
        requested_urls = {str(r.url) for r in httpx_mock.get_requests()}
        assert "http://userinfo_uri" not in requested_urls

    def test_get_userinfo_on_complete_token_without_issuer(self, dummy_jwt_token: str) -> None:
        oidc_client = OidcClient(issuer=None, audience=None)
        userinfo = oidc_client.get_user_info(dummy_jwt_token, fields=["preferred_username", "email_verified"])
        assert userinfo.preferred_username == "admin"
        assert userinfo.email_verified is False

    def test_get_userinfo_on_incomplete_token_without_issuer(self, incomplete_dummy_jwt_token: str) -> None:
        oidc_client = OidcClient(issuer=None, audience=None)
        msg = (
            "Requested fields are not present locally at the token and they cannot be retrieved from the identity "
            "provider because issuer URL is not set."
        )
        with pytest.raises(NoIssuerError, match=msg):
            oidc_client.get_user_info(incomplete_dummy_jwt_token, fields=["preferred_username"])

    def test_get_userinfo_on_token_with_wrong_keyset(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        wrong_secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [wrong_secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        with pytest.raises(ValueError, match="No key for kid:"):
            oidc_client.get_user_info(dummy_jwt_token, fields=["preferred_username"])

    @pytest.mark.parametrize("invalid_token", ["expired", "wrong_iss", "wrong_aud", "wrong_nbf"], indirect=True)
    def test_get_userinfo_on_invalid_token_with_issuer(
        self,
        invalid_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        oidc_client.get_user_info(invalid_token, fields=["preferred_username"])

    @pytest.mark.parametrize("invalid_token", ["expired", "wrong_iss", "wrong_aud", "wrong_nbf"], indirect=True)
    def test_get_userinfo_on_invalid_token_without_issuer(self, invalid_token: str) -> None:
        oidc_client = OidcClient(issuer=None, audience=None)
        userinfo = oidc_client.get_user_info(invalid_token, fields=["preferred_username"])
        assert userinfo.preferred_username == "admin"

    def test_get_userinfo_with_from_issuer(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        user_info = oidc_client.get_user_info(dummy_jwt_token, from_issuer=True)
        assert user_info.name == "Jane Doe"

    @pytest.mark.parametrize("invalid_token", ["expired", "wrong_iss", "wrong_aud", "wrong_nbf"], indirect=True)
    def test_get_userinfo_with_from_issuer_and_invalid_token(
        self,
        invalid_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        user_info = oidc_client.get_user_info(invalid_token, from_issuer=True)
        assert user_info.name == "Jane Doe"

    def test_get_userinfo_with_from_issuer_and_field_present_in_issuer_and_token(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        user_info = oidc_client.get_user_info(dummy_jwt_token, fields=["name"], from_issuer=True)
        assert user_info.name == "Jane Doe"

    def test_get_userinfo_with_from_issuer_and_field_missing_in_issuer_present_in_token(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = OidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        with pytest.raises(
            ValueError,
            match=re.escape("The userinfo response does not include all required fields: ['preferred_username']."),
        ):
            oidc_client.get_user_info(dummy_jwt_token, fields=["preferred_username"], from_issuer=True)


class TestGetUserInfoASync:
    async def test_get_userinfo_on_complete_token(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        async_oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        userinfo = await async_oidc_client.get_user_info(
            dummy_jwt_token,
            fields=["preferred_username", "email_verified"],
        )
        assert userinfo.preferred_username == "admin"
        assert not userinfo.email_verified
        requested_urls = {str(r.url) for r in httpx_mock.get_requests()}
        assert "http://userinfo_uri" not in requested_urls

    async def test_get_userinfo_on_incomplete_token_and_complete_response(
        self,
        incomplete_dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        async_oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "preferred_username": "j.doe",
                "email": "janedoe@example.com",
                "email_verified": False,
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        userinfo = await async_oidc_client.get_user_info(
            incomplete_dummy_jwt_token,
            fields=["preferred_username", "email_verified"],
        )
        assert userinfo.sub == "248289761001"
        assert userinfo.name == "Jane Doe"
        assert userinfo.preferred_username == "j.doe"
        assert not userinfo.email_verified

    async def test_get_userinfo_on_incomplete_token_and_incomplete_response(
        self,
        incomplete_dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        async_oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        with pytest.raises(
            ValueError,
            match=re.escape("The userinfo response does not include all required fields: ['preferred_username']."),
        ):
            await async_oidc_client.get_user_info(incomplete_dummy_jwt_token, fields=["preferred_username"])

    async def test_get_userinfo_with_non_existent_field(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        async_oidc_client = AsyncOidcClient(issuer=IDP_URL)
        with pytest.raises(
            ValueError,
            match=re.escape("Invalid field(s) requested: ['non_existent_field']. Valid fields are:"),
        ):
            await async_oidc_client.get_user_info(dummy_jwt_token, fields=["non_existent_field"])

    async def test_get_userinfo_with_no_fields(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        async_oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        userinfo = await async_oidc_client.get_user_info(dummy_jwt_token)
        assert userinfo.preferred_username == "admin"
        requested_urls = {str(r.url) for r in httpx_mock.get_requests()}
        assert "http://userinfo_uri" not in requested_urls

    async def test_get_userinfo_on_complete_token_without_issuer(self, dummy_jwt_token: str) -> None:
        oidc_client = AsyncOidcClient()
        userinfo = await oidc_client.get_user_info(dummy_jwt_token, fields=["preferred_username", "email_verified"])
        assert userinfo.preferred_username == "admin"
        assert not userinfo.email_verified

    async def test_get_userinfo_on_incomplete_token_without_issuer(self, incomplete_dummy_jwt_token: str) -> None:
        oidc_client = AsyncOidcClient()
        msg = (
            "Requested fields are not present locally at the token and they cannot be retrieved from the identity "
            "provider because issuer URL is not set."
        )
        with pytest.raises(NoIssuerError, match=msg):
            await oidc_client.get_user_info(incomplete_dummy_jwt_token, fields=["preferred_username"])

    async def test_get_userinfo_on_token_with_wrong_keyset(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        wrong_secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [wrong_secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        with pytest.raises(ValueError, match="No key for kid:"):
            await oidc_client.get_user_info(dummy_jwt_token, fields=["preferred_username"])

    @pytest.mark.parametrize("invalid_token", ["expired", "wrong_iss", "wrong_aud", "wrong_nbf"], indirect=True)
    async def test_get_userinfo_on_invalid_token_with_issuer(
        self,
        invalid_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        await oidc_client.get_user_info(invalid_token, fields=["preferred_username"])

    @pytest.mark.parametrize("invalid_token", ["expired", "wrong_iss", "wrong_aud", "wrong_nbf"], indirect=True)
    async def test_get_userinfo_on_invalid_token_without_issuer(self, invalid_token: str) -> None:
        oidc_client = AsyncOidcClient()
        userinfo = await oidc_client.get_user_info(invalid_token, fields=["preferred_username"])
        assert userinfo.preferred_username == "admin"

    async def test_get_userinfo_with_from_issuer(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        user_info = await oidc_client.get_user_info(dummy_jwt_token, from_issuer=True)
        assert user_info.name == "Jane Doe"

    @pytest.mark.parametrize("invalid_token", ["expired", "wrong_iss", "wrong_aud", "wrong_nbf"], indirect=True)
    async def test_get_userinfo_with_from_issuer_and_invalid_token(
        self,
        invalid_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        user_info = await oidc_client.get_user_info(invalid_token, from_issuer=True)
        assert user_info.name == "Jane Doe"

    async def test_get_userinfo_with_from_issuer_and_field_present_in_issuer_and_token(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        user_info = await oidc_client.get_user_info(dummy_jwt_token, fields=["name"], from_issuer=True)
        assert user_info.name == "Jane Doe"

    async def test_get_userinfo_with_from_issuer_and_field_missing_in_issuer_present_in_token(
        self,
        dummy_jwt_token: str,
        httpx_mock: HTTPXMock,
        secret_key: OctKey,
    ) -> None:
        httpx_mock.add_response(
            url=OPENID_CONFIG_URL,
            json={"jwks_uri": "http://jwks_uri", "userinfo_endpoint": "http://userinfo_uri"},
        )
        oidc_client = AsyncOidcClient(issuer=IDP_URL)
        keys = {"keys": [secret_key.as_dict()]}
        httpx_mock.add_response(url="http://jwks_uri", json=keys)
        httpx_mock.add_response(
            url="http://userinfo_uri",
            json={
                "sub": "248289761001",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "janedoe@example.com",
                "picture": "http://example.com/janedoe/me.jpg",
            },
        )
        with pytest.raises(
            ValueError,
            match=re.escape("The userinfo response does not include all required fields: ['preferred_username']."),
        ):
            await oidc_client.get_user_info(dummy_jwt_token, fields=["preferred_username"], from_issuer=True)
