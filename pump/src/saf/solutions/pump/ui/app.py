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

import os

import dash
from dash_extensions.enrich import DashProxy, MultiplexerTransform, TriggerTransform

dash._dash_renderer._set_react_version("18.2.0")

_UI_PATH_PREFIX = os.getenv("GLOW_UI_PATH_PREFIX", "/")

app = DashProxy(
    __name__,
    suppress_callback_exceptions=True,
    transforms=[TriggerTransform(), MultiplexerTransform()],
    requests_pathname_prefix=_UI_PATH_PREFIX,
    use_pages=True,
)

# !IMPORTANT: keep this import after DashProxy initialization.
# Page modules resolve assets at import time and require Dash config to be initialized.
from saf.solutions.pump.ui.pages.page import layout

app.layout = layout
