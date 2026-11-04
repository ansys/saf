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

"""Frontend of the second step."""


import dash
from dash_extensions.enrich import html

from saf.solutions.solution03e2bfd.solution.definition import Solution03E2BfdSolution

dash.register_page(
    __name__,
    name="Second Step",
    path_template="/projects/<project_id>/second-step",
    icon_asset_name="carbon--ibm-engineering-workflow-mgmt.svg",
    icon_asset_path="icons",
)


def layout(project: Solution03E2BfdSolution):
    """Layout of the second step page."""
    return html.Div(
        [
            html.H1("Second Step", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.P(
                "This page is empty for now.",
                className="lead",
                style={"font-size": "20px"},
            ),
            html.Br(),
        ]
    )
