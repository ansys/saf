# Copyright (C) 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
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

from __future__ import print_function as _

import json
from pathlib import Path
import sys as _sys

import dash as _dash

# noinspection PyUnresolvedReferences
from ._imports_ import *  # noqa: F403
from ._imports_ import __all__

if not hasattr(_dash, "__plotly_dash") and not hasattr(_dash, "development"):
    print(
        "Dash was not successfully imported. "
        "Make sure you don't have a file "
        'named \n"dash.py" in your current directory.',
        file=_sys.stderr,
    )
    _sys.exit(1)

_filepath = Path(__file__).parent / "package-info.json"
with _filepath.open() as f:
    package = json.load(f)

__version__ = package["version"]
package_name = package["name"].replace(" ", "_").replace("-", "_")

_dash_namespace = "ansys_saf_projects_dashboard"

_js_dist = []

_js_dist.extend(
    [
        {"relative_package_path": "ansys_saf_projects_dashboard.js", "namespace": _dash_namespace},
        {"relative_package_path": "ansys_saf_projects_dashboard.js.map", "namespace": _dash_namespace, "dynamic": True},
    ],
)

# Add proptypes.js for runtime prop types validation with tsx components
_js_dist.append({"relative_package_path": "proptypes.js", "dev_only": True, "namespace": _dash_namespace})

_css_dist = []


for _component in __all__:
    setattr(locals()[_component], "_js_dist", _js_dist)  # noqa: B010
    setattr(locals()[_component], "_css_dist", _css_dist)  # noqa: B010
