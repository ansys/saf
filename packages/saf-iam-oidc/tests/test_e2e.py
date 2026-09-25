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

import os
import re

from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc7523 import ClientSecretJWT
import pytest

from ansys.iam.oidc import AsyncOidcClient

# In order to use those e2e tests, you need to run keycloak as an identity provider,
# and modify the following values to match the ones registered within keycloak.
# To allow the test to be a client, you also need to modify the client capability to use
# Service accounts roles. (in keycloak, navigate to Clients > client-id > Settings > Capability config and check both
# "Client authentication and Service accounts roles")
CLIENT_ID = "rep-jms-web"
CLIENT_SECRET = os.environ["TEST_REP_CLIENT_SECRET"]
AUDIENCE = "realm-management"
ISSUER_URL = "https://localhost:8443/hps/auth/realms/rep"

pytestmark = pytest.mark.skip("Needs keycloak modified configuration")


@pytest.fixture
def oauth_client() -> AsyncOAuth2Client:
    client = AsyncOAuth2Client(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_endpoint_auth_method="client_secret_post",
        scope="openid email profile",
    )
    token_endpoint = f"{ISSUER_URL}/protocol/openid-connect/token"
    client.register_client_auth_method(ClientSecretJWT(token_endpoint))  # pyright: ignore[reportUnknownMemberType]
    return client


@pytest.fixture
async def token(oauth_client: AsyncOAuth2Client) -> str:
    token_endpoint = f"{ISSUER_URL}/protocol/openid-connect/token"
    t = await oauth_client.fetch_token(  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        token_endpoint,
    )
    return t["access_token"]  # pyright: ignore[reportUnknownVariableType]


@pytest.fixture
def oidc_client() -> AsyncOidcClient:
    return AsyncOidcClient(ISSUER_URL, audience="realm-management")


async def test_userinfo(token: str, oidc_client: AsyncOidcClient) -> None:
    userinfo = await oidc_client.get_user_info(token)
    assert userinfo.sub != ""
    assert userinfo.preferred_username != ""


async def test_userinfo_with_fields(token: str, oidc_client: AsyncOidcClient) -> None:
    userinfo = await oidc_client.get_user_info(token, fields=["sub", "preferred_username"])
    assert userinfo.sub != ""
    assert userinfo.preferred_username != ""


async def test_userinfo_with_wrong_field(token: str, oidc_client: AsyncOidcClient) -> None:
    with pytest.raises(ValueError, match=re.escape("The field 'non_existent_field' is not in the userinfo response.")):
        await oidc_client.get_user_info(token, fields=["non_existent_field"])


async def test_validate_token(token: str, oidc_client: AsyncOidcClient) -> None:
    t = await oidc_client.validate_access_token(token)
    assert t.claims["azp"] == CLIENT_ID
