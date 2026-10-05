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

from __future__ import annotations

from contextlib import contextmanager, suppress
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any

import httpx2
from joserfc import jws

from ansys.saf.glow._config.const import (
    DEFAULT_HPS_CLIENT_CACHE_TTL_SECONDS,
    TEST_HPS_CLIENT_CACHE_TTL_SECONDS,
    Deployment,
)
from ansys.saf.glow._hps_auth.hps_authentication_type import HpsAuthenticationType
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator
from ansys.saf.glow._server.exceptions import InternalError
from ansys.saf.glow._telemetry.inject_trace_http_transport import InjectTraceTransport
from ansys.saf.glow._utilities.requests import build_params_for_hps_auth_request

if TYPE_CHECKING:
    from ansys.saf.glow._config.settings import Settings

logger = logging.getLogger(__name__)


class CachedClient:
    def __init__(
        self,
        client: Client,  # noqa: F821  # pyright: ignore[reportUnknownParameterType, reportUndefinedVariable]
        timestamp: float,
    ) -> None:
        self.client = client  # pyright: ignore[reportUnknownMemberType]
        self.timestamp = timestamp

    def is_expired(self, cache_ttl_seconds: float) -> bool:
        # TODO: replace with token validation, bringing logic from get_hps_auth_info
        return (time.time() - self.timestamp) > cache_ttl_seconds

    def close(self) -> None:
        """Release the resources held by the cached client.

        ansys-hps-client exposes no close(). As of 0.13.0 it holds a token refresh
        thread and a data transfer child process (~227 MB), both of which it only stops
        at interpreter exit, so they have to be released through private attributes.
        """
        stop_event = getattr(self.client, "_stop_event", None)  # pyright: ignore[reportUnknownArgumentType]
        if stop_event is not None:
            stop_event.set()
        refresh_thread = getattr(self.client, "_token_refresh_thread", None)  # pyright: ignore[reportUnknownArgumentType]
        if refresh_thread is not None:
            # Upstream waits 5s at exit; keep it short here because this runs inside a request.
            # The thread polls the stop event, so it exits on its own even if the join times out.
            refresh_thread.join(timeout=1.0)
        dt_client = getattr(self.client, "_dt_client", None)  # pyright: ignore[reportUnknownArgumentType]
        if dt_client is not None:
            try:
                dt_client.stop()
            except Exception:
                logger.warning("Failed to stop the HPS data transfer client.", exc_info=True)
        session = getattr(self.client, "session", None)  # pyright: ignore[reportUnknownArgumentType]
        if session is not None:
            try:
                session.close()
            except Exception:
                logger.warning("Failed to close the HPS client session.", exc_info=True)


class CachedClients:
    """HPS clients cached per server URL, keyed by the URL they were built for."""

    def __init__(self) -> None:
        self._clients: dict[str, CachedClient] = {}

    def close(self) -> None:
        """Release every cached client now, instead of waiting for collection."""
        for cached in self._clients.values():
            cached.close()
        self._clients.clear()

    def __del__(self) -> None:
        # Authenticators are per request in the main API process, so most caches are dropped without their entry ever
        # being replaced; this is the only point where those clients get released.
        with suppress(Exception):
            self.close()

    def get(self, hps_server_url: str, cache_ttl_seconds: float) -> Client | None:  # noqa: F821  # pyright: ignore[reportUnknownParameterType, reportUndefinedVariable]
        """Return the cached client for the URL, or None when absent or expired."""
        cached = self._clients.get(hps_server_url)
        if cached is None or cached.is_expired(cache_ttl_seconds):
            return None
        logger.debug(f"Using cached HPS client for {hps_server_url}")
        return cached.client  # pyright: ignore[reportUnknownMemberType]

    def set(self, hps_server_url: str, client: Client) -> None:  # noqa: F821  # pyright: ignore[reportUndefinedVariable]
        """Cache the client, releasing the entry it replaces.

        Only the replaced entry is closed; a client still held by an open
        get_hps_client context is never touched.
        """
        if replaced := self._clients.get(hps_server_url):
            logger.debug(f"Releasing replaced HPS client for {hps_server_url}")
            replaced.close()
        self._clients[hps_server_url] = CachedClient(client, time.time())


class DesktopHpsAuthenticator(IHpsAuthenticator):
    def __init__(
        self,
        glow_api_url: str,
        client_id: str,
        glow_hps_username: str = "",
        glow_hps_password: str = "",
    ) -> None:
        self._hps_user = glow_hps_username
        self._hps_pwd = glow_hps_password
        self._auth_url = f"{glow_api_url}/desktop:hps-auth-info"
        self._client_id = client_id
        self._client_cache = CachedClients()

    @contextmanager
    def get_hps_client(  # pyright: ignore[reportUnknownParameterType]
        self,
        hps_server_url: str,
        client_id: str | None = None,
    ) -> Client:  # noqa: F821  # pyright: ignore[reportUndefinedVariable]
        from ansys.hps.client import Client  # pyright: ignore[reportMissingTypeStubs]

        # Check if we have a valid cached client
        cache_ttl = float(os.environ.get(TEST_HPS_CLIENT_CACHE_TTL_SECONDS, DEFAULT_HPS_CLIENT_CACHE_TTL_SECONDS))
        if cached_client := self._client_cache.get(hps_server_url, cache_ttl):
            yield cached_client
            return

        # Create a new client if not cached or expired
        logger.debug(f"Creating new HPS client for {hps_server_url}")
        if self.auth_type == HpsAuthenticationType.USER_PASSWORD:
            client = Client(url=hps_server_url, username=self._hps_user, password=self._hps_pwd)
        else:
            # If username and password are not provided, we authenticate automatically using Keycloak.

            # TODO: if it is feasible, move token validation here to minimize REST calls
            # TODO: raise error if GLOW_AUTH_DISABLED is enabled but we end up here
            with httpx2.Client(transport=InjectTraceTransport(), timeout=60) as httpx_client:
                logger.info(f"Asking for HPS authorization to {self._auth_url}...")
                params = build_params_for_hps_auth_request(
                    hps_server_url=hps_server_url,
                    client_id=client_id or self._client_id,
                )
                r = httpx_client.get(self._auth_url, params=params)
                r.raise_for_status()
                refresh_token = r.json()["refresh_token"]

            # We try to create clients with fresh/verified tokens and for a limited scope via contextmanager.
            # However, there is the possibility that the token expires between the Client validation done just
            # above and the actual moment when the Client sends the request to the server. For this, we pass
            # the refresh token instead to let the Client automatically refresh it when needed.
            client = Client(url=hps_server_url, client_id=client_id or self._client_id, refresh_token=refresh_token)

        # Cache the new client
        self._client_cache.set(hps_server_url, client)
        yield client


class OnPremHpsAuthenticator(IHpsAuthenticator):
    def __init__(
        self,
        token: str | None = None,
        client_id: str | None = None,
        glow_hps_username: str = "",
        glow_hps_password: str = "",
        glow_auth_issuer_url: str | None = None,
        glow_auth_service_account_client_id: str | None = None,
        glow_auth_service_account_client_secret: str | None = None,
    ) -> None:
        self._access_token = token or ""
        self._client_id = client_id
        self._hps_user = glow_hps_username
        self._hps_pwd = glow_hps_password
        self._glow_auth_issuer_url = glow_auth_issuer_url
        self._client_cache = CachedClients()
        self._service_account_client_id = glow_auth_service_account_client_id
        self._service_account_client_secret = glow_auth_service_account_client_secret

    @contextmanager
    def get_hps_client(  # pyright: ignore[reportUnknownParameterType]
        self,
        hps_server_url: str,
        client_id: str | None = None,
    ) -> Client:  # noqa: F821  # pyright: ignore[reportUndefinedVariable]
        if self._access_token == "" and (not self._hps_user or not self._hps_pwd):
            raise RuntimeError(
                "On-prem HPS authentication requires either token or username and password authentication.",
            )

        from ansys.hps.client import Client  # pyright: ignore[reportMissingTypeStubs]

        # Check if we have a valid cached client
        cache_ttl = float(os.environ.get(TEST_HPS_CLIENT_CACHE_TTL_SECONDS, DEFAULT_HPS_CLIENT_CACHE_TTL_SECONDS))
        if cached_client := self._client_cache.get(hps_server_url, cache_ttl):
            yield cached_client
            return

        # Create a new client if not cached or expired
        logger.debug(f"Creating new HPS client for {hps_server_url}")

        if self.auth_type == HpsAuthenticationType.TOKEN_EXCHANGE:
            if not self._client_id or not self._glow_auth_issuer_url:
                error_msg = (
                    "GLOW_AUTH_CLIENT_ID and GLOW_AUTH_ISSUER_URL must be provided"
                    " for token exchange authentication with HPS."
                )
                raise ValueError(error_msg)
            username = self._get_username_from_access_token(self._access_token)
            # In on-premises deployments using HPS, GLOW_AUTH_ISSUER_URL must be configured to point to the
            # Keycloak service of the HPS deployment so that the access token allows access to the Keycloak
            # action token endpoint. That is why here self._glow_auth_issuer_url is a subpath of, and therefore
            # compatible with, hps_server_url.
            #
            # Contrary to what we do for desktop deployments, in on-premises we do not persist tokens because there
            # can be simultaneous user sessions using different tokens, and we want to avoid keeping track and
            # storing the state of multiple user sessions. This implies that we cannot check whether the tokens
            # have expired or not, so we create new ones every time.
            if self._service_account_client_id and self._service_account_client_secret:
                # Authenticated user does not typically have privileges for requesting action tokens for any username.
                # Use service account if configured.
                bearer_token = self._get_service_account_access_token(
                    issuer_url=self._glow_auth_issuer_url,
                    service_account_client_id=self._service_account_client_id,
                    service_account_client_secret=self._service_account_client_secret,
                )
                logger.debug(
                    f"Using access token of service account {self._service_account_client_id} "
                    f"for action token request (platform flow)"
                )
            else:
                bearer_token = self._access_token

            action_token_url = self._request_action_token_url(
                auth_url=self._glow_auth_issuer_url,
                client_id=self._client_id,
                username=username,
                access_token=bearer_token,
            )
            tokens = self._get_access_and_refresh_tokens(
                action_token_url=action_token_url,
                client_id=self._client_id,
                username=username,
            )
            hps_access_token = tokens.get("access_token")
            # We try to create clients with fresh/verified tokens and for a limited scope via contextmanager.
            # However, there is the possibility that the token expires between the Client validation done just
            # above and the actual moment when the Client sends the request to the server. For this, we pass
            # the refresh token instead to let the Client automatically refresh it when needed.
            hps_refresh_token = tokens.get("refresh_token")
            # Internally, an auth_url variable is created by appending the value of the url argument. The resulting
            # auth_url value coincides with the value of self._glow_auth_issuer_url.
            client = Client(url=hps_server_url, access_token=hps_access_token, refresh_token=hps_refresh_token)
        else:
            client = Client(url=hps_server_url, username=self._hps_user, password=self._hps_pwd)

        # Cache the new client
        self._client_cache.set(hps_server_url, client)
        yield client

    @staticmethod
    def _get_username_from_access_token(access_token: str) -> str:
        token_content = jws.extract_compact(access_token.encode())
        token = json.loads(token_content.payload)
        if preferred_username := token.get("preferred_username", ""):
            return preferred_username
        if username := token.get("username", ""):
            return username
        raise ValueError("The access token must contain a 'preferred_username' or a 'username' claim.")

    def _get_service_account_access_token(
        self, issuer_url: str, service_account_client_id: str, service_account_client_secret: str
    ) -> str:
        """Obtain an access token for the service account via client_credentials grant."""
        token_url = str(issuer_url).rstrip("/") + "/protocol/openid-connect/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": service_account_client_id,
            "client_secret": service_account_client_secret,
        }
        with httpx2.Client(verify=True, timeout=10) as client:
            logger.debug(f"Requesting access token for service account {service_account_client_id}")
            response = client.post(token_url, data=data)
            response.raise_for_status()
            token_response = response.json()
            return token_response["access_token"]

    def _request_action_token_url(self, auth_url: str, client_id: str, username: str, access_token: str):
        """Request an action token for a user fully authenticated. If this method is successful,
        the response includes an action token and the link that can be used to get an access and refresh tokens.

        Parameters
        ----------
        auth_url : str, required
            Base path for the server to call. Example: ``'https://127.0.0.1:8443/rep'``.
        client_id : str, required
            target client id to impersonate.
        username : str, required
            Username of the user to impersonate.
        access_token : str, required
            The access token for the client service account.

        Returns
        -------
        str
            URL to obtain the access and refresh tokens.
        """
        logger.info(f"Generating an action token for {username} using client {client_id}")
        action_token_url = str(auth_url).rstrip("/") + "/job-action-token"
        headers: dict[str, str] = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        data: dict[str, Any] = {
            "clientId": client_id,
            "username": username,
        }

        with httpx2.Client(verify=True, timeout=10) as client:
            logger.debug(f"Requesting an action token for client {client_id} to impersonate {username}.")
            response = client.post(action_token_url, headers=headers, json=data)
            get_action_token_response = response.json()
            error = get_action_token_response.get("error")
            if error:
                error_messages = {
                    "role": (
                        f"The client {client_id} service account "
                        "does not have the 'manage-job-access-token' role.\n"
                        "Fix this error by adding the necessary role to the service account."
                    ),
                    "client": (
                        f"The client {client_id} does not have the permission to request "
                        "an action token. Fix this by adding the client to the list of "
                        "authored clients and then restart the OIDC provider."
                    ),
                }
                logger.error(
                    error_messages.get(
                        error,
                        (
                            f"Failed to get action token for '{username}' using client '{client_id}'. "
                            f"The request returned the error: '{error}'"
                        ),
                    ),
                )
            else:
                logger.debug(
                    f"Generated an action token for {get_action_token_response.get('issued_for')} "
                    f"impersonating {get_action_token_response.get('subject')} that will expire in "
                    f"{get_action_token_response.get('expire_in')}.",
                )
            response.raise_for_status()
            return get_action_token_response["link"]

    def _get_access_and_refresh_tokens(self, action_token_url: str, client_id: str, username: str):
        """Authenticate the user by requesting an action token. If this method is successful,
        the response includes access and refresh tokens.

        Parameters
        ----------
        action_token_url : str, required
            URL to request the action token. Example: ``'https://127.0.0.1:8443/job-action-token'``.
        client_id : str, required
            target client id to impersonate.
        username : str, required
            Username of the user to impersonate.

        Returns
        -------
        dict
            JSON-encoded content of a :class:`httpx2.Response` object.
        """
        logger.info(f"Generating an access and refresh tokens for {username} using client {client_id}")
        with httpx2.Client(verify=True, timeout=10) as client:
            use_action_token_response = client.get(action_token_url).raise_for_status().json()
            logger.debug(
                (
                    f"The access and refresh tokens will expire in {use_action_token_response.get('expires_in')} and "
                    f"{use_action_token_response.get('refresh_expires_in')}, respectively."
                ),
            )
            return use_action_token_response


class NullHpsAuthenticator(IHpsAuthenticator):
    """Dummy implementation of an HPS Authenticator that is used when the deployment type is Unknown."""

    ERROR_MESSAGE: str = "Unknown deployment type."

    @contextmanager
    def get_hps_client(  # pyright: ignore[reportUnknownParameterType]
        self,
        hps_server_url: str,
        client_id: str | None = None,
    ) -> Client:  # noqa: F821  # pyright: ignore[reportUndefinedVariable]
        raise InternalError(self.ERROR_MESSAGE)


def create_hps_authenticator(settings: Settings, access_token: str | None = None) -> IHpsAuthenticator:
    if settings.glow_deployment == Deployment.Desktop:
        hps_authenticator = DesktopHpsAuthenticator(
            glow_api_url=f"http://localhost:{settings.glow_api_port}",
            client_id=settings.glow_hps_client_id,
            glow_hps_username=settings.glow_hps_username,
            glow_hps_password=settings.glow_hps_password,
        )
    elif settings.glow_deployment == Deployment.DockerCompose:
        hps_authenticator = OnPremHpsAuthenticator(
            token=access_token,
            client_id=settings.glow_hps_client_id,
            glow_hps_username=settings.glow_hps_username,
            glow_hps_password=settings.glow_hps_password,
            glow_auth_issuer_url=settings.glow_auth_issuer_url,
            glow_auth_service_account_client_id=settings.glow_auth_service_account_client_id,
            glow_auth_service_account_client_secret=settings.glow_auth_service_account_client_secret,
        )
    else:
        hps_authenticator = NullHpsAuthenticator()
    return hps_authenticator
