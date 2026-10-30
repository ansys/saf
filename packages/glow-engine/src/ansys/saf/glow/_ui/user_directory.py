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

"""Pluggable user directory of the UI server.

The GLOW API only stores user ids. Resolving what a user typed (email, username...) into a user id, and user ids into
display names, is done in the UI server, using the directory selected with ``GLOW_UI_USER_DIRECTORY``.
"""

from collections.abc import Sequence
import logging
import threading
import time
from typing import Any, Protocol
from urllib.parse import quote

import httpx2

from ansys.saf.glow._config.settings import Settings

logger = logging.getLogger(__name__)

MAX_NAMES_PER_REQUEST = 200
_HTTP_TIMEOUT_SECONDS = 10
_TOKEN_EXPIRY_MARGIN_SECONDS = 10


class UserDirectory(Protocol):
    """Directory able to find users and give their display names."""

    def resolve(self, identifier: str) -> str | None:
        """Return the id of the user designated by ``identifier``, or ``None`` if there is not exactly one."""
        ...

    def display_names(self, user_ids: Sequence[str]) -> dict[str, str]:
        """Return the display name of each known user id. Unknown ids are omitted."""
        ...


class NoUserDirectory:
    """Directory used when no user directory is configured: users are designated by their id."""

    def resolve(self, identifier: str) -> str | None:
        stripped = identifier.strip()
        if not stripped or "@" in stripped or any(c.isspace() for c in stripped):
            return None
        return stripped

    def display_names(self, user_ids: Sequence[str]) -> dict[str, str]:
        return {user_id: user_id for user_id in user_ids}


class KeycloakUserDirectory:
    """User directory backed by the Keycloak admin API, authenticated with the client-credentials grant."""

    def __init__(
        self,
        base_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._realm = realm
        self._client_id = client_id
        self._client_secret = client_secret
        self._cache_ttl_seconds = cache_ttl_seconds
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._names: dict[str, tuple[float, str]] = {}

    @property
    def _admin_url(self) -> str:
        return f"{self._base_url}/admin/realms/{quote(self._realm, safe='')}"

    def _get_token(self, client: httpx2.Client) -> str:
        with self._lock:
            if self._token is not None and time.monotonic() < self._token_expires_at:
                return self._token
        response = client.post(
            f"{self._base_url}/realms/{quote(self._realm, safe='')}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload["access_token"])
        lifetime = float(payload.get("expires_in", 60))
        with self._lock:
            self._token = token
            self._token_expires_at = time.monotonic() + max(lifetime - _TOKEN_EXPIRY_MARGIN_SECONDS, 0.0)
        return token

    def _get(self, client: httpx2.Client, path: str, params: dict[str, str] | None = None) -> httpx2.Response:
        token = self._get_token(client)
        response = client.get(f"{self._admin_url}{path}", params=params, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 401:
            # The token may have been revoked or expired early: get a fresh one and retry once.
            with self._lock:
                self._token = None
            token = self._get_token(client)
            response = client.get(
                f"{self._admin_url}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        return response

    def resolve(self, identifier: str) -> str | None:
        identifier = identifier.strip()
        if not identifier:
            return None
        with httpx2.Client(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            for field in ("email", "username"):
                response = self._get(client, "/users", {field: identifier, "exact": "true"})
                response.raise_for_status()
                users: list[dict[str, Any]] = response.json()
                if len(users) == 1:
                    return str(users[0]["id"])
                if len(users) > 1:
                    logger.warning("Ambiguous user lookup by %s: %d matches", field, len(users))
                    return None
        return None

    def display_names(self, user_ids: Sequence[str]) -> dict[str, str]:
        now = time.monotonic()
        names: dict[str, str] = {}
        missing: list[str] = []
        with self._lock:
            for user_id in dict.fromkeys(user_ids):
                cached = self._names.get(user_id)
                if cached is not None and cached[0] > now:
                    names[user_id] = cached[1]
                else:
                    missing.append(user_id)
        if not missing:
            return names
        with httpx2.Client(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            for user_id in missing:
                response = self._get(client, f"/users/{quote(user_id, safe='')}")
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                user = response.json()
                name = f"{user.get('firstName') or ''} {user.get('lastName') or ''}".strip() or user.get("username")
                if not name:
                    continue
                names[user_id] = str(name)
                with self._lock:
                    self._names[user_id] = (time.monotonic() + self._cache_ttl_seconds, str(name))
        return names


class ScimUserDirectory:
    """Placeholder for a SCIM user directory."""

    def __init__(self) -> None:
        raise NotImplementedError("SCIM user directory is not implemented yet")


class MsGraphUserDirectory:
    """Placeholder for a Microsoft Graph user directory."""

    def __init__(self) -> None:
        raise NotImplementedError("Microsoft Graph user directory is not implemented yet")


def create_user_directory(settings: Settings) -> UserDirectory:
    """Build the user directory selected by ``settings.glow_ui_user_directory``."""
    kind = settings.glow_ui_user_directory
    if kind == "none":
        return NoUserDirectory()
    if kind == "scim":
        return ScimUserDirectory()
    if kind == "msgraph":
        return MsGraphUserDirectory()
    url = settings.glow_ui_keycloak_url
    realm = settings.glow_ui_keycloak_realm
    client_id = settings.glow_ui_keycloak_client_id
    secret = (
        settings.glow_ui_keycloak_client_secret.get_secret_value() if settings.glow_ui_keycloak_client_secret else ""
    )
    missing = [
        name
        for name, value in (
            ("GLOW_UI_KEYCLOAK_URL", url),
            ("GLOW_UI_KEYCLOAK_REALM", realm),
            ("GLOW_UI_KEYCLOAK_CLIENT_ID", client_id),
            ("GLOW_UI_KEYCLOAK_CLIENT_SECRET", secret),
        )
        if not value
    ]
    if missing or not (url and realm and client_id):
        raise ValueError(f"GLOW_UI_USER_DIRECTORY=keycloak requires these settings: {', '.join(missing)}")
    return KeycloakUserDirectory(url, realm, client_id, secret)


_user_directory: UserDirectory = NoUserDirectory()


def get_user_directory() -> UserDirectory:
    return _user_directory


def set_user_directory(directory: UserDirectory) -> None:
    global _user_directory
    _user_directory = directory


def register_user_directory_routes(flask_app: Any) -> None:
    """Register the user directory routes on the Flask server of the UI.

    The routes are protected by the authentication ``before_request`` hook of the UI server.
    """
    from flask import Response, jsonify, request

    def no_store(response: Response) -> Response:
        response.headers["Cache-Control"] = "no-store"
        return response

    def error(message: str, status: int) -> Response:
        response = jsonify({"error": message})
        response.status_code = status
        return no_store(response)

    @flask_app.get("/_saf/users/resolve")
    def resolve_user():  # pyright: ignore[reportUnusedFunction]
        query = request.args.get("q", "")
        try:
            user_id = get_user_directory().resolve(query)
        except Exception:
            logger.exception("User directory lookup failed")
            return error("User directory unavailable", 502)
        if user_id is None:
            return error("User not found", 404)
        return no_store(jsonify({"user_id": user_id}))

    @flask_app.post("/_saf/users/names")
    def user_names():  # pyright: ignore[reportUnusedFunction]
        body = request.get_json(silent=True)
        user_ids = body.get("user_ids") if isinstance(body, dict) else None
        if not isinstance(user_ids, list) or not all(isinstance(u, str) for u in user_ids):
            return error("'user_ids' must be a list of strings", 400)
        if len(user_ids) > MAX_NAMES_PER_REQUEST:
            return error(f"At most {MAX_NAMES_PER_REQUEST} user ids are allowed", 400)
        try:
            names = get_user_directory().display_names(user_ids)
        except Exception:
            logger.exception("User directory lookup failed")
            return error("User directory unavailable", 502)
        return no_store(jsonify({"names": names}))
