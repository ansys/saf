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

import json
import logging
from typing import Any

import httpx2
from joserfc import jws, jwt
from joserfc.errors import JoseError
from joserfc.jwk import Key, KeySet
from joserfc.jws import CompactSignature
from joserfc.jwt import JWTClaimsRegistry, Token

from ansys.iam.oidc._exceptions import NoIssuerError, NoIssuerOrAudienceError
from ansys.iam.oidc._userinfo import UserInfo

logger = logging.getLogger(__name__)


class OidcClientBase:
    def __init__(self, issuer: str | None = None, audience: str | None = None) -> None:
        """Initialize the base OIDC client.

        Parameters
        ----------
        issuer: str | None
            The url of the auth provider.
        audience: str | None
            The recipients that the JSON Web Token is intended for.

        Notes
        -----
        If no issuer is provided, the client will not validate the tokens. Still, you will be able to retrieve them and
        decode them.

        """
        self._issuer = issuer
        self._audience = audience
        self._openid_config: dict[str, Any] = {}

    @property
    def metadata_server(self) -> str:
        """Get the url of the openid connect configuration endpoint.

        Returns
        -------
        str
            The OpenID configuration URL.

        Raises
        ------
        NoIssuerError
            If the issuer URL is not set.

        """
        if not self._issuer:
            msg = "Cannot build OpenID configuration URL because issuer URL is not set."
            raise NoIssuerError(msg)
        return f"{self._issuer}/.well-known/openid-configuration"

    def _validate_requested_fields(self, fields: list[str] | None) -> list[str]:
        """Validate a list of requested ``UserInfo`` attribute names.

        Normalizes ``None`` to an empty list. Each provided field name must correspond to a
        valid attribute defined on the ``UserInfo`` model.

        Parameters
        ----------
        fields : list[str] | None
            Field names whose presence (non-null) is required in local token claims to skip a
            remote ``userinfo`` call. ``None`` is treated as ``[]``.

        Returns
        -------
        list[str]
            A new list of validated field names (may be empty).

        Raises
        ------
        ValueError
            If any provided field name is not a valid ``UserInfo`` attribute.

        """
        fields = fields or []
        if invalid_fields := [field for field in fields if field not in UserInfo.model_fields]:
            msg = f"Invalid field(s) requested: {invalid_fields}. Valid fields are: {list(UserInfo.model_fields)}"
            raise ValueError(
                msg,
            )
        return fields

    def _token_field_is_valid(self, value: str | bool | None) -> bool:
        """Check if a value is valid (not None and not empty string)."""
        return value is not None and value != ""

    def _retrieve_user_info_from_access_token(
        self,
        access_token: str,
        key_set: KeySet | None,
        fields: list[str],
    ) -> UserInfo | None:
        """Attempt to build ``UserInfo`` directly from the access token claims.

        Decodes the JWT. If every required field is present and non-null in the claims, returns a
        ``UserInfo`` model built from those claims; otherwise returns ``None`` so the caller can
        fall back to the remote ``userinfo`` endpoint.

        Parameters
        ----------
        access_token : str
            The encoded JWT access token.
        key_set : KeySet | None
            The set of keys used to verify the token signature.
            If not available, the token will be decoded without verification.
        fields : list[str]
            Required field names to satisfy locally.

        Returns
        -------
        UserInfo | None
            ``UserInfo`` if local claims satisfy all requested fields, else ``None``.

        """
        if key_set:
            try:
                token = jwt.decode(access_token, key_set)
                if all(self._token_field_is_valid(token.claims.get(field, None)) for field in fields):
                    logger.debug("User info obtained from decoded token.")
                    return UserInfo.model_validate(token.claims)
            except JoseError as ex:
                logger.exception("Failed to decode token: %s", ex.description)
                raise ValueError(ex.description) from None
        else:
            # See: https://github.com/authlib/joserfc/issues/25. The joserfc library does not provide a direct method
            # for extracting JWT claims, as discussed in the linked issue. This workaround uses jws.extract_compact to
            # decode the token payload, allowing us to avoid adding another dependency such as pyjwt or python-jose.
            token_content = jws.extract_compact(access_token.encode())
            token = json.loads(token_content.payload)
            if all(self._token_field_is_valid(token.get(field, None)) for field in fields):
                logger.debug("User info obtained from decoded token.")
                return UserInfo.model_validate(token)
        logger.debug("Decoded token does not include all required fields: %s.", fields)
        return None

    def _retrieve_user_info_from_response(self, response: httpx2.Response, fields: list[str]) -> UserInfo:
        """Attempt to build ``UserInfo`` from a remote ``userinfo`` endpoint response.

        Validates that every required field is present and non-null in the response JSON before
        building and returning a ``UserInfo`` model.

        Parameters
        ----------
        response : httpx2.Response
            The HTTP response from the ``userinfo`` endpoint.
        fields : list[str]
            Required field names to satisfy locally.

        Returns
        -------
        UserInfo
            The user information object derived from the remote endpoint.

        Raises
        ------
        ValueError
            If any required field is missing or null in the response JSON.

        """
        user_info = response.json()
        if not all(self._token_field_is_valid(user_info.get(field, None)) for field in fields):
            msg = f"The userinfo response does not include all required fields: {fields}."
            raise ValueError(msg)
        return UserInfo.model_validate(user_info)


class AsyncOidcClient(OidcClientBase):
    """OIDC Async client."""

    async def _fetch_openid_configuration(self) -> dict[str, Any]:
        """Fetch the openid configuration from the metadata server url.

        (To avoid performance issues due to the repeated retrieval of keys, the response is cached).

        Returns
        -------
        dict[str, Any]
            The OpenID configuration dictionary.

        Raises
        ------
        NoIssuerError
            If the issuer URL is not set.

        """
        if not self._issuer:
            msg = "Cannot fetch OpenID configuration because issuer URL is not set."
            raise NoIssuerError(msg)
        if not self._openid_config:
            async with httpx2.AsyncClient() as client:
                logger.debug("Fetching openid configuration for %s...", self._issuer)
                resp = await client.get(self.metadata_server)
                resp.raise_for_status()
            self._openid_config = resp.json()
        return self._openid_config

    async def _fetch_key_set(self, openid_config: dict[str, Any]) -> KeySet:
        """Retrieve the JSON Web Key Set (JWKS) referenced in the OpenID configuration.

        Parameters
        ----------
        openid_config : dict[str, Any]
            The OpenID Provider configuration.

        """
        jwks_uri = openid_config["jwks_uri"]
        async with httpx2.AsyncClient() as client:
            logger.debug("Fetching JWKS at %s", jwks_uri)
            resp = await client.get(jwks_uri)
            return KeySet.import_key_set(resp.json())

    async def _load_key(self, obj: CompactSignature, openid_config: dict[str, Any]) -> Key:
        """Return the JWK matching the ``kid`` header in the given compact signature.

        Parameters
        ----------
        obj : CompactSignature
            The compact JWS/JWT signature object whose protected headers contain ``kid``.
        openid_config : dict[str, Any]
            The OpenID Provider configuration.

        Returns
        -------
        Key
            The JWK associated with the provided key identifier.

        """
        key_set = await self._fetch_key_set(openid_config)
        return key_set.get_by_kid(obj.headers()["kid"])

    async def validate_access_token(self, value: str) -> Token:
        """Validate the JSON Web Token string.

        The following validations are performed: exp, nbf, iss and aud.

        Parameters
        ----------
        value: str
            text of the JWT

        Returns
        -------
        Token
            The validated JWT token.

        Raises
        ------
        NoIssuerOrAudienceError
            If the issuer URL or audience is not set.
        ValueError
            If the token is invalid (expired, wrong issuer, wrong audience, not yet valid, etc.).

        """
        if not self._issuer or not self._audience:
            msg = "Cannot validate access token because issuer URL or audience is not set."
            raise NoIssuerOrAudienceError(msg)
        openid_config = await self._fetch_openid_configuration()
        key_set = await self._fetch_key_set(openid_config)

        try:
            token = jwt.decode(value, key_set)
        except JoseError as ex:
            logger.exception("The token is invalid: %s", ex.description)
            msg = f"The token is invalid: {ex.description}"
            raise ValueError(msg) from None

        claims_requests = JWTClaimsRegistry(
            aud={"essential": True, "value": self._audience},
            iss={"essential": True, "value": self._issuer},
        )

        try:
            claims_requests.validate(token.claims)
        except JoseError as ex:
            logger.exception("The token is invalid: %s", ex.description)
            msg = f"The token is invalid: {ex.description}"
            raise ValueError(msg) from None

        return token

    async def validate_token_with_introspection(self) -> None:
        """Not implemented yet..."""
        msg = ""
        raise NotImplementedError(msg)

    async def get_user_info(
        self,
        access_token: str,
        fields: list[str] | None = None,
        *,
        from_issuer: bool = False,
    ) -> UserInfo:
        """Retrieve user information, preferring local token claims and falling back to the
        OpenID Provider ``userinfo`` endpoint only when required.

        Workflow:

        - Decode the access token using the provider JWKS.
        - If ``fields`` is ``None`` or empty, immediately return a ``UserInfo`` built from all claims.
        - If ``fields`` is provided and every requested field exists and is non-null in the decoded
          claims, return the locally built ``UserInfo``.
        - Otherwise perform a network request to the ``userinfo`` endpoint and build ``UserInfo`` from
          that response.
        - If ``from_issuer`` is True, skip local token claims and perform a network request to the
          ``userinfo`` endpoint and build ``UserInfo`` from that response.

        Field validation: any element of ``fields`` not matching a ``UserInfo`` attribute triggers a
        ``ValueError``.

        see also: https://openid.net/specs/openid-connect-core-1_0.html#UserInfoResponse

        Parameters
        ----------
        access_token : str
            The JWT access token.
        fields : list[str] | None
            Fields that must be present in the local token claims to avoid the remote userinfo call.
        from_issuer : bool
            If True, forces retrieval of user info from the identity provider, bypassing local token claims.

        Returns
        -------
        UserInfo
            The user information object derived from local claims or the remote endpoint.

        Raises
        ------
        ValueError
            If any provided field name is invalid.
        NoIssuerError
            If the requested fields are not present in the token and the issuer URL is not set,
            preventing retrieval from the identity provider.

        """
        fields = self._validate_requested_fields(fields)

        openid_config: dict[str, Any] | None = None
        key_set: KeySet | None = None
        try:
            openid_config = await self._fetch_openid_configuration()
            key_set = await self._fetch_key_set(openid_config)
        except NoIssuerError:
            pass

        if not from_issuer and (user_info := self._retrieve_user_info_from_access_token(access_token, key_set, fields)):
            return user_info

        if not openid_config:
            msg = (
                "Requested fields are not present locally at the token and they cannot be retrieved from the identity "
                "provider because issuer URL is not set."
            )
            raise NoIssuerError(msg)

        async with httpx2.AsyncClient() as client:
            logger.debug("Fetching user info from the identity provider.")
            response = await client.get(
                openid_config["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return self._retrieve_user_info_from_response(response, fields)


class OidcClient(OidcClientBase):
    """OIDC client."""

    def _fetch_openid_configuration(self) -> dict[str, Any]:
        """Fetch the openid configuration from the metadata server url.

        (To avoid performance issues due to the repeated retrieval of keys, the response is cached).

        Returns
        -------
        dict[str, Any]
            The OpenID configuration dictionary.

        Raises
        ------
        NoIssuerError
            If the issuer URL is not set.

        """
        if not self._issuer:
            msg = "Cannot fetch OpenID configuration because issuer URL is not set."
            raise NoIssuerError(msg)
        if not self._openid_config:
            with httpx2.Client() as client:
                logger.debug("Fetching openid configuration for %s...", self._issuer)
                resp = client.get(self.metadata_server)
                resp.raise_for_status()
            self._openid_config = resp.json()
        return self._openid_config

    def _fetch_key_set(self, openid_config: dict[str, Any]) -> KeySet:
        """Retrieve the JSON Web Key Set (JWKS) referenced in the OpenID configuration.

        Parameters
        ----------
        openid_config : dict[str, Any]
            The OpenID Provider configuration.

        """
        jwks_uri = openid_config["jwks_uri"]
        with httpx2.Client() as client:
            logger.debug("Fetching JWKS at %s", jwks_uri)
            resp = client.get(jwks_uri)
            return KeySet.import_key_set(resp.json())

    def _load_key(self, obj: CompactSignature, openid_config: dict[str, Any]) -> Key:
        """Return the JWK matching the ``kid`` header in the given compact signature.

        Parameters
        ----------
        obj : CompactSignature
            The compact JWS/JWT signature object whose protected headers contain ``kid``.
        openid_config : dict[str, Any]
            The OpenID Provider configuration.

        Returns
        -------
        Key
            The JWK associated with the provided key identifier.

        """
        key_set = self._fetch_key_set(openid_config)
        return key_set.get_by_kid(obj.headers()["kid"])

    def validate_access_token(self, value: str) -> Token:
        """Validate the JSON Web Token string.

        The following validations are performed: exp, nbf, iss and aud.

        Parameters
        ----------
        value: str
            text of the JWT

        Returns
        -------
        Token
            The validated JWT token.

        Raises
        ------
        NoIssuerOrAudienceError
            If the issuer URL or audience is not set.
        ValueError
            If the token is invalid (expired, wrong issuer, wrong audience, not yet valid, etc.).

        """
        if not self._issuer or not self._audience:
            msg = "Cannot validate access token because issuer URL or audience is not set."
            raise NoIssuerOrAudienceError(msg)
        openid_config = self._fetch_openid_configuration()
        key_set = self._fetch_key_set(openid_config)

        try:
            token = jwt.decode(value, key_set)
        except JoseError as ex:
            logger.exception("The token is invalid: %s", ex.description)
            msg = f"The token is invalid: {ex.description}"
            raise ValueError(msg) from None

        claims_requests = JWTClaimsRegistry(
            aud={"essential": True, "value": self._audience},
            iss={"essential": True, "value": self._issuer},
        )

        try:
            claims_requests.validate(token.claims)
        except JoseError as ex:
            logger.exception("The token is invalid: %s", ex.description)
            msg = f"The token is invalid: {ex.description}"
            raise ValueError(msg) from None

        return token

    def validate_token_with_introspection(self) -> None:
        """Not implemented yet..."""
        msg = ""
        raise NotImplementedError(msg)

    def get_user_info(
        self,
        access_token: str,
        fields: list[str] | None = None,
        *,
        from_issuer: bool = False,
    ) -> UserInfo:
        """Retrieve user information, preferring local token claims and falling back to the
        OpenID Provider ``userinfo`` endpoint only when required.

        Workflow:

        - Decode the access token using the provider JWKS.
        - If ``fields`` is ``None`` or empty, immediately return a ``UserInfo`` built from all claims.
        - If ``fields`` is provided and every requested field exists and is non-null in the decoded
          claims, return the locally built ``UserInfo``.
        - Otherwise perform a network request to the ``userinfo`` endpoint and build ``UserInfo`` from
          that response.
        - If ``from_issuer`` is True, skip local token claims and perform a network request to the
          ``userinfo`` endpoint and build ``UserInfo`` from that response.

        Field validation: any element of ``fields`` not matching a ``UserInfo`` attribute triggers a
        ``ValueError``.

        see also: https://openid.net/specs/openid-connect-core-1_0.html#UserInfoResponse

        Parameters
        ----------
        access_token : str
            The JWT access token.
        fields : list[str] | None
            Fields that must be present in the local token claims to avoid the remote userinfo call.
        from_issuer : bool
            If True, forces retrieval of user info from the identity provider, bypassing local token claims.

        Returns
        -------
        UserInfo
            The user information object derived from local claims or the remote endpoint.

        Raises
        ------
        ValueError
            If any provided field name is invalid.
        NoIssuerError
            If the requested fields are not present in the token and the issuer URL is not set,
            preventing retrieval from the identity provider.

        """
        fields = self._validate_requested_fields(fields)

        openid_config: dict[str, Any] | None = None
        key_set: KeySet | None = None
        try:
            openid_config = self._fetch_openid_configuration()
            key_set = self._fetch_key_set(openid_config)
        except NoIssuerError:
            pass

        if not from_issuer and (user_info := self._retrieve_user_info_from_access_token(access_token, key_set, fields)):
            return user_info

        if not openid_config:
            msg = (
                "Requested fields are not present locally at the token and they cannot be retrieved from the identity "
                "provider because issuer URL is not set."
            )
            raise NoIssuerError(msg)

        with httpx2.Client() as client:
            logger.debug("Fetching user info from the identity provider.")
            response = client.get(
                openid_config["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return self._retrieve_user_info_from_response(response, fields)
