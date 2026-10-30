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

# ©2026, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.
"""Routes serving the ADR media and static files referenced by the rendered ADR reference report.

The report is displayed in an iframe of the Dash application. Its HTML references images, scenes,
and files with the ``/media/`` URL, and CSS, JavaScript, and fonts with the ``/static_assets/`` URL.
"""

import logging
from typing import Any

import flask

from saf.solutions.examples.solution.logic.adr_reference.adr_settings import (
    MEDIA_URL,
    STATIC_URL,
    AdrNotAvailableError,
    get_adr_paths,
)

logger = logging.getLogger(__name__)

_MEDIA_RULE = f"{MEDIA_URL}<path:filename>"
_STATIC_RULE = f"{STATIC_URL}<path:filename>"


def serve_report_media_file(filename: str) -> flask.Response:
    """Serve a media file of the ADR database."""
    try:
        media_directory = get_adr_paths().media_directory
    except AdrNotAvailableError:
        flask.abort(404)
    return flask.send_from_directory(media_directory, filename)


def serve_report_static_file(filename: str) -> flask.Response:
    """Serve a static file collected by ADR."""
    try:
        static_directory = get_adr_paths().static_directory
    except AdrNotAvailableError:
        flask.abort(404)
    return flask.send_from_directory(static_directory, filename)


def register_report_asset_routes(app: Any) -> None:
    """Register the routes serving the ADR media and static files on the Dash application server.

    Serverless ADR uses the same media and static directories for every report of the process,
    so a route that is already registered (for example by another example of the solution) is kept.
    """
    registered_rules = {rule.rule for rule in app.server.url_map.iter_rules()}

    if _MEDIA_RULE not in registered_rules:
        app.server.add_url_rule(_MEDIA_RULE, endpoint="adr_reference_media", view_func=serve_report_media_file)
    if _STATIC_RULE not in registered_rules:
        app.server.add_url_rule(_STATIC_RULE, endpoint="adr_reference_static", view_func=serve_report_static_file)

    logger.debug("ADR media and static routes are available on the Dash application server.")
