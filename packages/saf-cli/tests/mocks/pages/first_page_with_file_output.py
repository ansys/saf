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

"""Frontend of the job submission step."""

import logging

import dash
from dash_extensions.enrich import Input, Output, State, clientside_callback, dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from saf.solutions.my_solution.solution.definition import MySolution

from ansys.saf.glow.client import callback

logger = logging.getLogger(__name__)
dash.register_page(  # pyright: ignore[reportUnknownMemberType]
    __name__,
    name="First Step",
    path_template="/projects/<project_id>/first-step",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def layout(project: MySolution):
    """Layout of the job submission page."""
    step = project.steps.first_step
    # Get the result from HPS project if available

    return html.Div(
        [
            html.H1("Job Submission", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.P(
                "Example of submitting a simple calculation job to HPS",
                className="lead",
                style={"font-size": "20px"},
            ),
            html.Hr(className="my-2"),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="First Argument",
                id="first-arg",
                value=step.first_arg,
                placeholder="Enter first argument",
                required=True,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="Second Argument",
                id="second-arg",
                value=step.second_arg,
                placeholder="Enter second argument",
                required=True,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Calculate",
                id="calculate",
                leftSection=DashIconify(icon="streamline:startup-solid"),
                radius="md",
                disabled=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Fetch from file",
                id="fetch-from-file",
                leftSection=DashIconify(icon="streamline:startup-solid"),
                radius="md",
                disabled=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="Result",
                id="result",
                value=step.result,
                disabled=True,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            html.A(href="", id="file-anchor"),  # The href will be populated dynamically.
            dmc.TextInput(
                label="File Result",
                id="file-result",
                value="",
                disabled=True,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dcc.Loading(
                type="circle",
                fullscreen=True,
                color="#ffb71b",
                style={
                    "background-color": "rgba(55, 58, 54, 0.1)",
                },
                children=html.Div(id="wait_completion"),
            ),
        ],
    )


@callback(
    Output("result", "value"),
    Output("wait_completion", "children"),
    Output("file-anchor", "href"),
    Input("calculate", "n_clicks"),
    State("first-arg", "value"),
    State("second-arg", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def calculate(n_clicks: int, first_arg: int, second_arg: int, project: MySolution):
    """Trigger the HPS job execution."""
    try:
        step = project.steps.first_step

        step.first_arg = first_arg
        step.second_arg = second_arg

        step.calculate()

        return (
            step.result,
            True,
            project.steps.first_step.get_data("result_file", substitute_file_handles_with_urls=True),
        )

    except Exception as e:
        logger.error(f"Error in HPS job: {str(e)}")
        return None, True, None


clientside_callback(
    """
    function(n_clicks, href) {
        return fetch(href).then(response => {return response.text();})
    }
    """,
    Input("fetch-from-file", "n_clicks"),
    State("file-anchor", "href"),
    Output("file-result", "value"),
)
