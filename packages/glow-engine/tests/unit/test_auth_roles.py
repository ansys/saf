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
import json
from typing import Any

import pytest

from ansys.saf.glow._utilities.auth_roles import (
    decode_token_claims,
    get_client_roles,
    has_required_role,
    parse_required_roles,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, frozenset()),
        ("", frozenset()),
        (" , ", frozenset()),
        ("app-role", frozenset({"app-role"})),
        (" app-role , portal_admin,", frozenset({"app-role", "portal_admin"})),
    ],
)
def test_parse_required_roles(value: str | None, expected: frozenset[str]):
    assert parse_required_roles(value) == expected


def test_decode_token_claims():
    claims = {"sub": "user", "resource_access": {"portal": {"roles": ["app-role"]}}}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    assert decode_token_claims(f"header.{payload}.signature") == claims


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.!!!.c", "a.W10.c"])
def test_decode_token_claims_invalid(token: str):
    assert decode_token_claims(token) == {}


@pytest.mark.parametrize(
    ("claims", "client_id", "expected"),
    [
        ({"resource_access": {"portal": {"roles": ["a", "b"]}}}, "portal", {"a", "b"}),
        ({"resource_access": {"portal": {"roles": ["a", 1]}}}, "portal", {"a"}),
        ({"resource_access": {"other": {"roles": ["a"]}}}, "portal", set()),
        ({"resource_access": {"portal": {"roles": "a"}}}, "portal", set()),
        ({"resource_access": {"portal": {"roles": ["a"]}}}, None, set()),
        ({"realm_access": {"roles": ["a"]}}, "portal", set()),
        ({}, "portal", set()),
    ],
)
def test_get_client_roles(claims: dict[str, Any], client_id: str | None, expected: set[str]):
    assert get_client_roles(claims, client_id) == expected


def test_has_required_role():
    claims = {"resource_access": {"portal": {"roles": ["portal_user", "hello-saf-role"]}}}
    assert has_required_role(claims, "portal", frozenset())
    assert has_required_role({}, "portal", frozenset())
    assert has_required_role(claims, "portal", frozenset({"portal_user", "hello-saf-role"}))
    assert not has_required_role(claims, "portal", frozenset({"portal_user", "beam-calculator-role"}))
    assert not has_required_role(claims, "other", frozenset({"hello-saf-role"}))


def test_has_required_role_bypass():
    required = frozenset({"portal_user", "hello-saf-role"})
    bypass = frozenset({"portal_admin"})
    admin = {"resource_access": {"portal": {"roles": ["portal_admin"]}}}
    only_user = {"resource_access": {"portal": {"roles": ["portal_user"]}}}
    assert has_required_role(admin, "portal", required, bypass)
    assert not has_required_role(only_user, "portal", required, bypass)
    assert not has_required_role(admin, "other", required, bypass)
