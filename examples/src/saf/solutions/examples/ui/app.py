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

# ©2023, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Application."""

import logging
import os
import tempfile

import dash
from dash_extensions.enrich import DashProxy, MultiplexerTransform, TriggerTransform
import dash_uploader as du

dash._dash_renderer._set_react_version("18.2.0")

logger = logging.getLogger(__name__)


app = DashProxy(
    __name__,
    suppress_callback_exceptions=True,
    transforms=[TriggerTransform(), MultiplexerTransform()],
    requests_pathname_prefix=f"{os.getenv('GLOW_UI_PATH_PREFIX', '/')}",
    use_pages=True,
)

# If folder doesn't exist, it will be created later
UPLOAD_DIRECTORY = os.path.join(tempfile.gettempdir(), "GLOW")
du.configure_upload(app, UPLOAD_DIRECTORY)


def _register_adr_asset_routes_if_configured(dash_app) -> None:
    """Register ADR asset routes only when ADR is configured.

    This keeps the UI startup resilient for environments where the report
    feature is not enabled or configured.
    """
    try:
        from saf.solutions.examples.solution.scripts.beam_bending.report.adr_config import get_adr_config

        get_adr_config()

        from saf.solutions.examples.solution.scripts.beam_bending.report.adr_routes import register_adr_asset_routes

        register_adr_asset_routes(dash_app)
    except Exception as exc:
        logger.warning(
            "ADR asset routes were not registered because ADR is not configured. "
            "Set ADR_INSTALLATION_DIRECTORY and GLOW_PROJECT_FILES_DIRECTORY to enable report assets. "
            "Details: %s",
            exc,
        )


# !IMPORTANT Keeping the import line here to adapt with dash_uploader config, moving the import above will fail the
# dash uploader configuration
from saf.solutions.examples.ui.pages.page import layout

_register_adr_asset_routes_if_configured(app)

# Visor endpoints are only needed by the Airfoil Explorer 3D viewers.
from saf.solutions.examples.ui.airfoil_explorer.settings import settings as airfoil_explorer_settings

if airfoil_explorer_settings.visor_enabled:
    import visordash

    visordash.init_endpoints(app)

app.layout = layout
