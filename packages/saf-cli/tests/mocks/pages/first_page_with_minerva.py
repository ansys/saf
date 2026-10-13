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

"""Frontend of the first step."""

import dash
from dash_extensions.enrich import Input, Output, State, dcc, html
import dash_mantine_components as dmc
from saf.solutions.my_solution.solution.definition import MySolution

from ansys.saf.glow.client import callback

dash.register_page(  # pyright: ignore[reportUnknownMemberType]
    __name__,
    name="First Step",
    path_template="/projects/<project_id>/first-step",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def layout(project: MySolution):
    """Layout of the first step page."""
    step = project.steps.first_step
    return html.Div(
        [
            html.H1("First Step", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.P(
                "Compute the sum of two numbers.",
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
                leftSection=html.Img(src=dash.get_asset_url("icons/streamline--startup-solid.svg")),
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
            dmc.Space(h=20),
            dmc.Button(
                "Retrieve result",
                id="retrieve",
                leftSection=html.Img(src=dash.get_asset_url("icons/streamline--startup-solid.svg")),
                radius="md",
                disabled=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="Retrieved result",
                id="retrieved-result",
                disabled=True,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
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
    Input("calculate", "n_clicks"),
    State("first-arg", "value"),
    State("second-arg", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def calculate(n_clicks: int, first_arg: int, second_arg: int, project: MySolution):
    """Trigger the computation."""
    step = project.steps.first_step
    step.first_arg = first_arg
    step.second_arg = second_arg
    step.calculate()
    return step.result, True


@callback(
    Output("retrieved-result", "value"),
    Output("wait_completion", "children"),
    Input("retrieve", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def retrieve_result(n_clicks: int, project: MySolution):
    """Trigger the computation."""
    step = project.steps.first_step
    result = project.storage_scope.get_cached(step.data_repo_result_handle).read_text()
    return float(result), True
