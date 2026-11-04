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

"""Frontend of the first step."""


from ansys.saf.glow.client import callback
import dash
from dash_extensions.enrich import Input, Output, State, dcc, html
import dash_mantine_components as dmc

from saf.solutions.solution03e2bfd.solution.definition import Solution03E2BfdSolution

dash.register_page(
    __name__,
    name="First Step",
    path_template="/projects/<project_id>/first-step",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def layout(project: Solution03E2BfdSolution):
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
                leftSection=html.Img(src=dash.get_asset_url("icons/dark/streamline--startup-solid.svg")),
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
                "Store result",
                id="save-result-to-file",
                leftSection=html.Img(src=dash.get_asset_url("icons/dark/streamline--startup-solid.svg")),
                radius="md",
                disabled=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Load stored result",
                id="load-result-from-file",
                leftSection=html.Img(src=dash.get_asset_url("icons/dark/streamline--startup-solid.svg")),
                radius="md",
                disabled=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="Stored result",
                id="loaded-result",
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
                children=html.Div(id="wait-completion"),
            ),
        ]
    )


@callback(
    Output("result", "value"),
    Output("wait-completion", "children"),
    Input("calculate", "n_clicks"),
    State("first-arg", "value"),
    State("second-arg", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def calculate(n_clicks: int, first_arg: int, second_arg: int, project: Solution03E2BfdSolution):
    """Trigger the calculation."""
    step = project.steps.first_step
    step.first_arg = first_arg
    step.second_arg = second_arg
    step.calculate()
    return step.result, True


@callback(
    Output("wait-completion", "children"),
    Input("save-result-to-file", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def save_result(n_clicks: int, project: Solution03E2BfdSolution):
    """Trigger the result storage. Store the result through a transaction."""
    project.steps.first_step.save_result()
    return True


@callback(
    Output("loaded-result", "value"),
    Output("wait-completion", "children"),
    Input("load-result-from-file", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def load_result(n_clicks: int, project: Solution03E2BfdSolution):
    """Trigger the result loading. Load the result directly accessing the file."""
    result_file = project.steps.first_step.result_file
    result = project.storage_scope.get_text(result_file)
    return float(result), True
