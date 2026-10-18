# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Application."""

import logging
import os

import dash
from dash_extensions.enrich import DashProxy, MultiplexerTransform, TriggerTransform
import flask

from saf.solutions.pump.solution.logic.report.settings import get_report_settings

dash._dash_renderer._set_react_version("18.2.0")

_UI_PATH_PREFIX = os.getenv("GLOW_UI_PATH_PREFIX", "/")

app = DashProxy(
    __name__,
    suppress_callback_exceptions=True,
    transforms=[TriggerTransform(), MultiplexerTransform()],
    requests_pathname_prefix=_UI_PATH_PREFIX,
    use_pages=True,
)

# The viewer widget loads its JS/CSS from routes on this app. Without them the
# component renders blank even when the Visor server is running.
try:
    import visordash

    visordash.init_endpoints(app, base_path=_UI_PATH_PREFIX.rstrip("/"))
except ImportError:
    logging.getLogger(__name__).warning(
        "visordash is not installed. The 3D view stays empty until the ui dependency group is installed.",
    )


# The rendered ADR report links its images and stylesheets to these two URL prefixes.
# send_from_directory rejects paths that escape the folder.
@app.server.route("/media/<path:filename>")
def serve_report_media(filename: str) -> flask.Response:
    """Serve an image of the ADR report."""
    return flask.send_from_directory(get_report_settings().media_directory, filename)


@app.server.route("/static_assets/<path:filename>")
def serve_report_static(filename: str) -> flask.Response:
    """Serve a stylesheet, script or font of the ADR report."""
    return flask.send_from_directory(get_report_settings().static_directory, filename)


# !IMPORTANT: keep this import after DashProxy initialization.
# Page modules resolve assets at import time and require Dash config to be initialized.
from saf.solutions.pump.ui.pages.page import layout

app.layout = layout
