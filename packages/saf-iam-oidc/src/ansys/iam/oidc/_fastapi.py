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

import logging

from fastapi import HTTPException, WebSocket, WebSocketException
from fastapi.security import OpenIdConnect
from fastapi.security.utils import get_authorization_scheme_param
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, WS_1008_POLICY_VIOLATION

from ansys.iam.oidc._client import AsyncOidcClient, OidcClient
from ansys.iam.oidc._exceptions import NoIssuerOrAudienceError
from ansys.iam.oidc._utilities import decode_base64_token

DEFAULT_SUBPROTOCOL_PREFIX = "saf.auth.bearer."

logger = logging.getLogger(__name__)


class OidcDependency(OpenIdConnect):
    """FastAPI dependency class for OpenID Connect (OIDC) access token validation."""

    def __init__(self, oidc_issuer: str | None = None, audience: str | None = None, *, auto_error: bool = True) -> None:
        """OpenID Connect authentication class used as fastapi dependency to decode and validate access token.

        This dependency will:
        - provides openapi authentication.
        - extract the access token from the incoming request,
        - validate the token's signature against the public keys,
        - verify the token's expiration time and reject expired tokens,
        - validate the audience.

        Parameters
        ----------
        oidc_issuer: str
            The url of the openid connect provider.
        audience: str
            The recipients that the JSON Web Token is intended for.
        auto_error: bool
            By default, if no HTTP Authorization header is provided, required for
            OAuth2 authentication, it will automatically cancel the request and
            send the client an error.

            If `auto_error` is set to `False`, when the HTTP Authorization header
            is not available, instead of erroring out, the dependency result will
            be `None`.

            This is useful when you want to have optional authentication.

            It is also useful when you want to have authentication that can be
            provided in one of multiple optional ways (for example, with OAuth2
            or in a cookie).

        Raises
        ------
        NoIssuerOrAudienceError
            If `auto_error` is True and either `oidc_issuer` or `audience` is not provided.

        Examples
        --------
        from typing import Annotated

        from fastapi import Depends, FastAPI
        from ansys.saf.oauth.fastapi import SafOidc

        app = FastAPI()

        oidc_scheme = OidcDependency(oidc_issuer="https://localhost:8443", audience="client-id")

        @app.get("/items/")
        async def read_items(token: Annotated[str, Depends(oidc_scheme)]):
            return {"token": token}

        """
        self._oidc_issuer = oidc_issuer
        self._audience = audience
        self._oidc_client = AsyncOidcClient(issuer=oidc_issuer, audience=audience)
        # Use a descriptive placeholder URL when issuer is not provided.
        # This URL is not used for actual authentication, but is required by FastAPI's OpenIdConnect schema.
        oidc_url = (
            self._oidc_client.metadata_server
            if oidc_issuer
            else "https://placeholder-issuer-url/.well-known/openid-configuration"
        )
        if auto_error and (not oidc_issuer or not audience):
            msg = "Both 'oidc_issuer' and 'audience' must be provided when 'auto_error' is True."
            raise NoIssuerOrAudienceError(
                msg,
            )
        logger.debug("Authentication is %s.", "required" if auto_error else "optional")
        super().__init__(openIdConnectUrl=oidc_url, description=None, auto_error=auto_error)

    @property
    def async_client(self) -> AsyncOidcClient:
        """Get the asynchronous OIDC client.

        Returns
        -------
        AsyncOidcClient
            The asynchronous OIDC client instance.

        """
        return self._oidc_client

    @property
    def client(self) -> OidcClient:
        """Get a synchronous OIDC client.

        Returns
        -------
        OidcClient
            A new synchronous OIDC client instance.

        """
        client = OidcClient(issuer=self._oidc_issuer, audience=self._audience)
        # perf optim: avoid refetching openid config if it is already cached by the async client
        client._openid_config = self._oidc_client._openid_config  # pyright: ignore[reportPrivateUsage]
        return client

    async def __call__(self, request: Request) -> str | None:
        """Extract and validate the access token from the HTTP request.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        str | None
            If authentication is mandatory, the access token if present and valid.
            If authentication is optional, the access token if present, otherwise None.

        Raises
        ------
        HTTPException
            If `auto_error` is True and authentication fails (missing token, invalid scheme,
            or token validation fails).

        """
        authorization = await super().__call__(request)
        scheme, token = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if not authorization:
                logger.debug("No authorization header was included in the request.")
            else:
                logger.debug("No bearer access token in the request's authorization header.")
            return None

        if self.auto_error:
            try:
                await self._oidc_client.validate_access_token(token)
                logger.debug("The validation of the access token was successful.")
            except ValueError as ex:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail=str(ex),
                    headers={"WWW-Authenticate": "Bearer"},
                ) from None
        else:
            logger.debug("The validation of the access token was skipped.")

        return token


def get_websocket_subprotocol(websocket: WebSocket, subprotocol_prefix: str = DEFAULT_SUBPROTOCOL_PREFIX) -> str | None:
    """Extract the first subprotocol that matches the specified prefix from the WebSocket's subprotocols list.

    Parameters
    ----------
    websocket: WebSocket
        The WebSocket connection object containing the headers.
    subprotocol_prefix: str, optional
        The prefix to match against WebSocket subprotocols. Defaults to DEFAULT_SUBPROTOCOL_PREFIX.

    Returns
    -------
    str | None
        The first matching subprotocol string if found, otherwise None.

    """
    return next(
        (
            subprotocol
            for subprotocol in websocket.scope.get("subprotocols", [])
            if subprotocol.startswith(subprotocol_prefix)
        ),
        None,
    )


class OidcWebSocketDependency(OidcDependency):
    """FastAPI dependency class for OpenID Connect (OIDC) access token validation for WebSocket connections.

    It's expected that the token is found, base64-encoded, as a subprotocol of the WebSocket, followed by a given
    prefix. For example, if the prefix is `saf.auth.bearer.`, the subprotocol should be
    `saf.auth.bearer.<base64-encoded-token>`. Use ``ansys.iam.oidc.encode_base64_token`` to encode the token.
    """

    def __init__(
        self,
        oidc_issuer: str | None = None,
        audience: str | None = None,
        subprotocol_prefix: str = DEFAULT_SUBPROTOCOL_PREFIX,
        *,
        auto_error: bool = True,
    ) -> None:
        """OpenID Connect authentication class used as fastapi dependency to decode and validate access token for
        WebSocket connections.

        This dependency will:
        - provides openapi authentication.
        - extract the access token from the incoming websocket's subprotocol,
        - validate the token's signature against the public keys,
        - verify the token's expiration time and reject expired tokens,
        - validate the audience.

        Parameters
        ----------
        oidc_issuer: str
            The url of the openid connect provider.
        audience: str
            The recipients that the JSON Web Token is intended for.
        subprotocol_prefix: str
            The prefix used to identify the token in the WebSocket subprotocol.
        auto_error: bool
            By default, if no authorization token is provided, required for
            OAuth2 authentication, it will automatically cancel the request and
            send the client an error.

            If `auto_error` is set to `False`, when the authorization token
            is not available, instead of erroring out, the dependency result will
            be `None`.

            This is useful when you want to have optional authentication.

            It is also useful when you want to have authentication that can be
            provided in one of multiple optional ways (for example, with OAuth2
            or in a cookie).

        Raises
        ------
        NoIssuerOrAudienceError
            If `auto_error` is True and either `oidc_issuer` or `audience` is not provided.

        Examples
        --------
        from typing import Annotated

        from fastapi import Depends, FastAPI
        from ansys.saf.oauth.fastapi import SafOidc

        app = FastAPI()

        oidc_ws_scheme = OidcWebSocketDependency(oidc_issuer="https://localhost:8443", audience="client-id")

        @app.websocket("/ws")
        async def exchange_messages(websocket: WebSocket, token: Annotated[str, Depends(oidc_ws_scheme)]):
            await websocket.accept()
            await websocket.send_text(f"Token used: {token}")
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Message text was: {data}")

        """
        if auto_error and (not oidc_issuer or not audience):
            msg = "Both 'oidc_issuer' and 'audience' must be provided when 'auto_error' is True."
            raise NoIssuerOrAudienceError(
                msg,
            )
        super().__init__(oidc_issuer=oidc_issuer, audience=audience, auto_error=auto_error)
        self._subprotocol_prefix = subprotocol_prefix

    async def __call__(self, websocket: WebSocket) -> str | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Extract and validate the access token from the WebSocket subprotocol.

        Parameters
        ----------
        websocket : WebSocket
            The WebSocket connection object.

        Returns
        -------
        str | None
            If authentication is mandatory, the access token if present and valid.
            If authentication is optional, the access token if present, otherwise None.

        Raises
        ------
        WebSocketException
            If `auto_error` is True and authentication fails (missing token, invalid encoding,
            or token validation fails).

        """
        subprotocol_value = get_websocket_subprotocol(websocket, self._subprotocol_prefix)
        encoded_token = subprotocol_value.removeprefix(self._subprotocol_prefix) if subprotocol_value else ""
        if not subprotocol_value or not encoded_token:
            if self.auto_error:
                raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="Not authenticated")
            return None

        try:
            token = decode_base64_token(encoded_token)
        except ValueError as ex:
            if self.auto_error:
                raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason=str(ex)) from None
            return encoded_token

        if self.auto_error:
            try:
                await self._oidc_client.validate_access_token(token)
                logger.debug("The validation of the access token was successful.")
            except ValueError as ex:
                raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason=str(ex)) from None
        else:
            logger.debug("The validation of the access token was skipped.")

        return token
