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
from typing import Any


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
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, binascii.Error):
        return {}
    return claims if isinstance(claims, dict) else {}


def get_client_roles(claims: dict[str, Any], client_id: str | None) -> set[str]:
    """Return the roles granted to the user for ``client_id`` (Keycloak ``resource_access`` claim)."""
    if not client_id:
        return set()
    resource_access = claims.get("resource_access")
    if not isinstance(resource_access, dict):
        return set()
    client_access = resource_access.get(client_id)
    if not isinstance(client_access, dict):
        return set()
    roles = client_access.get("roles")
    if not isinstance(roles, list):
        return set()
    return {role for role in roles if isinstance(role, str)}


def has_required_role(claims: dict[str, Any], client_id: str | None, required_roles: frozenset[str]) -> bool:
    """Check that the user holds at least one of ``required_roles``. Always true when no role is required."""
    if not required_roles:
        return True
    return not required_roles.isdisjoint(get_client_roles(claims, client_id))
