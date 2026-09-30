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

import importlib
import inspect
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urljoin, urlparse

from ansys.iam.oidc import OidcClient

from ansys.saf.glow._config.const import (
    AUTH_SCRIPT_MARKER,
    DEFAULT_GLOW_AUTH_DISABLED,
    DEFAULT_SOLUTION_API_URL,
    GLOW_API_URL,
    GLOW_AUTH_BYPASS_ROLES,
    GLOW_AUTH_CLIENT_ID,
    GLOW_AUTH_DISABLED,
    GLOW_AUTH_ISSUER_URL,
    GLOW_AUTH_REQUIRED_ROLES,
    GLOW_EXTERNAL_API_URL,
    GLOW_SOLUTION_DEFINITION,
    GLOW_UI_SERVICE_NAME,
    GLOW_WS_EVENTS_ADDR,
)
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._telemetry.instrumentor import Instrumentor
from ansys.saf.glow._utilities.auth_roles import has_required_role, parse_required_roles

logger = logging.getLogger(__name__)

# Path to GLOW's assets folder (for auth refresh handler and other shared assets)
GLOW_ASSETS_PATH = Path(__file__).parent / "assets"


def _inject_auth_refresh_script(ui_app: Any) -> None:
    """Inject GLOW's authentication refresh JavaScript into the Dash app's index HTML.

    This function safely injects the auth refresh script before the closing body tag,
    replacing only the last occurrence to avoid corruption from multiple injections or
    JavaScript strings containing </body>.

    Parameters
    ----------
    ui_app : Any
        The Dash application instance with an index_string attribute.
    """
    auth_refresh_js_path = GLOW_ASSETS_PATH / "glow_auth_refresh.js"

    try:
        auth_refresh_script = auth_refresh_js_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise RuntimeError(f"Failed to load auth refresh script from {auth_refresh_js_path}") from e

    if AUTH_SCRIPT_MARKER in ui_app.index_string:
        logger.info("Auth refresh script already injected, skipping injection")
        return

    script_tag = f"""
    <script>
    {AUTH_SCRIPT_MARKER}
    {auth_refresh_script}
    </script>
    """

    closing_body_tag = "</body>"
    if closing_body_tag not in ui_app.index_string:
        logger.warning("Unable to inject auth refresh script: </body> not found in index_string")
        return

    # Replace only the last occurrence of </body> to avoid corruption
    # if the tag appears multiple times (e.g., in JavaScript strings or previous injections)
    last_index = ui_app.index_string.rfind(closing_body_tag)
    ui_app.index_string = ui_app.index_string[:last_index] + script_tag + "\n" + ui_app.index_string[last_index:]

    logger.info("Auth refresh script injected successfully")


def _set_env_var_if_none(name: str, value: str) -> None:
    if os.environ.get(name) is None:
        os.environ[name] = value


def _get_app_from_app_module(module: ModuleType) -> Any:
    apps = [
        value
        for identifier, value in inspect.getmembers(
            module,
            lambda x: hasattr(x, "run") and callable(getattr(x, "run", None)),
        )
        if identifier == "app"
    ]

    if not apps:
        raise RuntimeError(
            "UI module does not define a variable called 'app'"
            " referring to an object with a 'run' method such as a Dash object",
        )

    return apps[0]


def _get_dash_version() -> tuple[int, int, int]:
    import dash  # pyright: ignore[reportMissingTypeStubs]

    try:
        version_parts = dash.__version__.split(".")
        major = int(version_parts[0])
        minor = int(version_parts[1])
        patch = int(version_parts[2])
        return (major, minor, patch)
    except (ValueError, IndexError, AttributeError):
        raise RuntimeError(
            "Dash version could not be parsed. Ensure Dash is installed and has a valid __version__ attribute.",
        ) from None


def _dash_supports_context_headers() -> bool:
    try:
        # ctx.headers was added in Dash 2.18.2
        # See: https://github.com/plotly/dash/blob/dev/CHANGELOG.md#2182---2024-11-04, PR#3051
        version = _get_dash_version()
        return version >= (2, 18, 2)
    except RuntimeError:
        logger.warning("Dash version could not be parsed. Assuming lower than 2.18.2.")
        return False


def create_app(settings: Settings) -> Any:
    """Create an instance of the Dash app.

    The app variable is enclosed within this function to imitate API server behaviour.
    """
    # keep dash/flask an optional dependency
    from flask import request
    from werkzeug.datastructures import WWWAuthenticate
    from werkzeug.exceptions import Forbidden, Unauthorized

    if settings.glow_ui_module is None:
        raise ValueError("Solution's UI module has not been specified. Set GLOW_UI_MODULE environment variable.")

    Instrumentor.instrumentalize_process(GLOW_UI_SERVICE_NAME, settings)

    # The ui_module is expected to define an app object which has a run method
    ui_module = importlib.import_module(settings.glow_ui_module)
    ui_app = _get_app_from_app_module(ui_module)

    # Inject GLOW's authentication refresh JavaScript into the app's index HTML.
    # This ensures the auth refresh handler is loaded and registered in the client browser,
    # allowing it to proactively refresh authentication before it expires, avoiding disruptions.
    _inject_auth_refresh_script(ui_app)
    # Inject auth validation to the underlying flask app. We return clean responses, leaving for solutions the option
    # to use custom error pages via error_handlers.
    oidc_issuer_url = os.environ.get(GLOW_AUTH_ISSUER_URL)
    audience = os.environ.get(GLOW_AUTH_CLIENT_ID)
    # After saf-portal is fixed, enable auth validation by default for
    # DockerCompose deployments. Leave it disabled for Desktop ones, though.
    disable_auth = os.environ.get(GLOW_AUTH_DISABLED, DEFAULT_GLOW_AUTH_DISABLED) != "False"
    required_roles = parse_required_roles(os.environ.get(GLOW_AUTH_REQUIRED_ROLES))
    bypass_roles = parse_required_roles(os.environ.get(GLOW_AUTH_BYPASS_ROLES))
    oidc_client = OidcClient(oidc_issuer_url, audience)
    if not disable_auth and not (oidc_issuer_url and audience):
        # We could catch exception NoIssuerOrAudienceError from OidcClient when doing validate_access_token, but
        # that would be too late in the chain already, and wouldn't stop the app for launching, just fail every request.
        error_msg = (
            "Authentication cannot be enforced without setting environment variables GLOW_AUTH_ISSUER_URL and "
            "GLOW_AUTH_CLIENT_ID."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg) from None

    authorized_paths = {
        "/health",
        "/favicon.ico",
    }

    @ui_app.server.before_request
    def validate_authorization_header():  # pyright: ignore[reportUnusedFunction]
        if request.authorization and request.authorization.token and not _dash_supports_context_headers():
            # Reasons for this check being here:
            # - We cannot check if ctx has headers attr because Dash prohibits to do so outside a callback context.
            # - We cannot check based on GLOW env vars at launch, because the presence of a authorization token does not
            # necessarily assume anything about the deployment mode or if auth is enforced.
            # - We cannot either within a callback context because then we would need to duplicate this token check
            # logic using flask.
            logger.warning(
                "Dash version is invalid or lower than 2.18.2. Authorization token is present but cannot be propagated "
                "unless Dash is upgraded to 2.18.2 or higher.",
            )

        if (
            disable_auth
            or (request.method not in ["GET", "POST", "PATCH", "DELETE", "PUT"])
            or (request.method == "GET" and request.path in authorized_paths)
        ):
            # We are not interested in the token itself beyond validation.
            # Besides authorized_paths, also skip methods such as OPTIONS that are not expected to be authenticated.
            return
        # validation logic and error types are in agreement with ansys.iam.oidc.OidcScheme
        if not request.authorization:
            logger.error("Missing authorization header")
            raise Forbidden()
        if request.authorization.type.lower() != "bearer" or not request.authorization.token:
            logger.error("Missing access token in authorization header")
            raise Unauthorized(www_authenticate=WWWAuthenticate("Bearer"))
        try:
            token = oidc_client.validate_access_token(request.authorization.token)
        except ValueError as ex:
            logger.error("Invalid access token: %s", str(ex))
            raise Unauthorized(www_authenticate=WWWAuthenticate("Bearer")) from None
        if required_roles and not has_required_role(token.claims, audience, required_roles, bypass_roles):
            logger.error("Access token does not grant the required roles.")
            raise Forbidden()

    # The following environment variables are necessary to for DashClient methods and callbacks.
    # Setting GLOW_SOLUTION_DEFINITION is only necessary in the case of solution definition autodiscovery:
    # autodiscovery gives a value to settings.glow_solution_definition but not to GLOW_SOLUTION_DEFINITION.
    _set_env_var_if_none(GLOW_SOLUTION_DEFINITION, settings.glow_solution_definition)
    _set_env_var_if_none(GLOW_API_URL, DEFAULT_SOLUTION_API_URL)
    glow_api_url = os.environ[GLOW_API_URL]
    _set_env_var_if_none(GLOW_EXTERNAL_API_URL, glow_api_url)
    parsed_glow_api_url = urlparse(glow_api_url)
    ws_events_addr = urljoin(f"ws://{parsed_glow_api_url.netloc}", str(parsed_glow_api_url.path))
    _set_env_var_if_none(GLOW_WS_EVENTS_ADDR, ws_events_addr)

    return ui_app
