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

"""Role-based access checks on access tokens that have already been validated."""

import base64
import binascii
import json
from typing import Any, cast

DEFAULT_ROLES_CLAIM = "resource_access.{client_id}.roles"


def parse_required_roles(value: str | None) -> frozenset[str]:
    """Parse a comma-separated list of role names, ignoring blanks."""
    if not value:
        return frozenset()
    return frozenset(role.strip() for role in value.split(",") if role.strip())


def decode_token_claims(access_token: str) -> dict[str, Any]:
    """Decode the payload of a JWT without verifying it.

    Only use this on tokens whose signature has already been validated.
    """
    try:
        payload = access_token.split(".")[1]
        claims: object = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, binascii.Error):
        return {}
    return cast("dict[str, Any]", claims) if isinstance(claims, dict) else {}


def get_roles_from_claims(claims: dict[str, Any], roles_claim: str, client_id: str | None) -> set[str]:
    """Return the roles found in ``claims`` at the dotted path ``roles_claim``.

    The ``{client_id}`` placeholder in the path is replaced by ``client_id``. The value at the path can be either a list
    of strings or a space-separated string.
    """
    if "{client_id}" in roles_claim and not client_id:
        return set()
    value: object = claims
    # Split first, then substitute: a client id may itself contain dots.
    for segment in roles_claim.split("."):
        key = segment.replace("{client_id}", client_id or "")
        if not isinstance(value, dict):
            return set()
        value = cast("dict[str, object]", value).get(key)
    if isinstance(value, str):
        return set(value.split())
    if isinstance(value, list):
        return {role for role in cast("list[object]", value) if isinstance(role, str)}
    return set()


def get_client_roles(claims: dict[str, Any], client_id: str | None) -> set[str]:
    """Return the roles granted to the user for ``client_id`` (Keycloak ``resource_access`` claim)."""
    return get_roles_from_claims(claims, DEFAULT_ROLES_CLAIM, client_id)


def has_required_role(
    claims: dict[str, Any],
    client_id: str | None,
    required_roles: frozenset[str],
    bypass_roles: frozenset[str] = frozenset(),
    roles_claim: str = DEFAULT_ROLES_CLAIM,
) -> bool:
    """Check that the user holds all of ``required_roles``, or at least one of ``bypass_roles``.

    The user roles are read from the ``roles_claim`` path of ``claims``. Always true when no role is required.
    """
    if not required_roles:
        return True
    user_roles = get_roles_from_claims(claims, roles_claim, client_id)
    return required_roles <= user_roles or not bypass_roles.isdisjoint(user_roles)
