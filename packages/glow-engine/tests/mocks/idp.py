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

import datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request
from joserfc import jwt
from joserfc.jwk import OctKey
from pydantic import BaseModel

from ansys.iam.oidc import UserInfo


class State(BaseModel):
    user: str = "user_complete_info_from_issuer"


class TokenRequest(BaseModel):
    issuer_name: str
    token_expiration_seconds: int | None = None


app = FastAPI()
app.state.data = State()


def secret_key() -> OctKey:
    key = OctKey.import_key("8f5c0e8d9b3f7e2c1a4d6b9f3e2c8a5d")
    key.ensure_kid()
    return key


def header(secret_key: OctKey) -> dict[str, Any]:
    return {"alg": "HS256", "kid": secret_key.kid}


def get_claims(token_request: TokenRequest) -> dict[str, Any]:
    expiration_seconds = token_request.token_expiration_seconds or 3600
    claims: dict[str, Any] = {
        "iss": token_request.issuer_name,
        "sid": "fake_session_id",
        "exp": datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=expiration_seconds),
        "iat": datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=5),
        "roles": ["admin"],
        "groups": ["admin"],
        "aud": ["rep-jms-web", "realm-management"],
        "preferred_username": "user_partial_info_from_token",
        "email": "user_partial_info_from_token@glow.com",
        "middle_name": "",
    }
    return claims


@app.get("/.well-known/openid-configuration")
async def openid_config(request: Request):
    issuer = str(request.base_url).rstrip("/")
    json = {
        "issuer": issuer,
        "token_endpoint": f"{issuer}/protocol/openid-connect/token",
        "introspection_endpoint": f"{issuer}/protocol/openid-connect/token/introspect",
        "userinfo_endpoint": f"{issuer}/protocol/openid-connect/userinfo",
        "jwks_uri": f"{issuer}/protocol/openid-connect/certs",
    }
    return json


@app.get("/protocol/openid-connect/certs")
async def jwks(secret_key: Annotated[OctKey, Depends(secret_key)]):
    return {"keys": [secret_key.as_dict()]}


@app.get("/protocol/openid-connect/auth")
async def auth(request: Request):
    raise NotImplementedError


@app.post("/protocol/openid-connect/token")
async def token(
    secret_key: Annotated[OctKey, Depends(secret_key)],
    claims: Annotated[dict[str, Any], Depends(get_claims)],
    token_request: TokenRequest,
):
    header: dict[str, Any] = {"alg": "HS256", "kid": secret_key.kid}
    access_token = jwt.encode(header, claims, secret_key)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/protocol/openid-connect/userinfo")
async def userinfo(request: Request) -> UserInfo:
    user = request.app.state.data.user
    if user == "user_complete_info_from_issuer":
        return UserInfo(
            sub="glow_tests",
            name=user,
            given_name=user,
            family_name=user,
            middle_name=user,
            nickname=user,
            preferred_username=user,
            profile=user,
            picture=f"{user}.png",
            website=f"{user}.org",
            email=f"{user}@glow.com",
            email_verified=True,
            gender="some_gender",
            birthdate="01/01/2001",
            zoneinfo="EU/ES",
            locale="some_locale",
            phone_number="some_phone_number",
            phone_number_verified=True,
            address="some_address",
            updated_at="01/12/2025",
        )
    else:
        return UserInfo(
            sub="glow_tests",
            name=user,
            preferred_username=user,
            email=f"{user}@glow.com",
            middle_name="",
        )


@app.patch("/admin")
async def admin(state: State):
    app.state.data = state
