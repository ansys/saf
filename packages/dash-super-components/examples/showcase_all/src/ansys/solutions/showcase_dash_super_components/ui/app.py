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


"""Application."""

import os

import ansys.solutions.dash_super_components as dsc
from dash_extensions.enrich import (
    DashProxy,
    MultiplexerTransform,
    NoOutputTransform,  # pyright: ignore[reportAttributeAccessIssue]
    TriggerTransform,
)

# uncomment the following lines when using dash 2.x:
# from dash import _dash_renderer
# _dash_renderer._set_react_version("18.2.0")

app = DashProxy(
    __name__,
    suppress_callback_exceptions=True,
    transforms=[NoOutputTransform(), TriggerTransform(), MultiplexerTransform()],
    requests_pathname_prefix=f"{os.getenv('GLOW_UI_PATH_PREFIX', '/')}",
    # External scripts required for LogsSupervisor component:
    # This script contains custom cell renderers for Dash AG Grid
    external_scripts=["/super-components/dashAgGridComponentFunctions.js"],
)

# Register Flask endpoint to serve super-components assets (required for LogsSupervisor)
dsc.add_super_components_assets(app)
# Enable beta features (required for FolderSelector bootstrap mode)
dsc.configure(enable_beta_features=True)
# Optional: Configure non-default notification container ID
# dsc.configure(notification_container_id="custom-notification-container-id")

# !IMPORTANT Keeping the import line here to adapt with dash_uploader config, moving the import
# above will fail the dash uploader configuration
from ansys.solutions.showcase_dash_super_components.ui.pages.page import layout  # noqa: E402

app.layout = layout
