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


from dash import Input, Output, State, dcc, html  # pyright: ignore[reportMissingTypeStubs]
from dash_extensions.enrich import (  # pyright: ignore[reportMissingTypeStubs]
    DashProxy,
    MultiplexerTransform,
    TriggerTransform,
)

from ansys.saf.glow.client import callback
from ansys.solutions.my_solution_dash_old.solution.definition import MySolutionDashOldSolution

app = DashProxy(
    __name__,
    suppress_callback_exceptions=True,
    transforms=[TriggerTransform(), MultiplexerTransform()],
)

app.layout = layout = html.Div(
    [
        dcc.Location(id="url", refresh=True),
        html.Div(id="page-content"),
    ],
)


@callback(
    Output("page-content", "children"),
    [Input("url", "pathname")],
)
def display_page(project: MySolutionDashOldSolution):
    """Display page content."""
    step = project.steps.first_step
    return html.Div(
        [
            html.H1("First Step", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.Div(
                [
                    "Input: ",
                    dcc.Input(id="first-arg", value=step.first_arg, type="number"),
                ],
            ),
            html.Div(
                [
                    "Input: ",
                    dcc.Input(id="second-arg", value=step.second_arg, type="number"),
                ],
            ),
            html.Br(),
            html.Div(id="result"),
            html.Button("Calculate", id="calculate", n_clicks=0),
        ],
    )


@callback(
    Output("result", "children"),
    Input("calculate", "n_clicks"),
    State("first-arg", "value"),
    State("second-arg", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def calculate(n_clicks: int, first_arg: float, second_arg: float, project: MySolutionDashOldSolution) -> float:
    """Trigger the computation."""
    step = project.steps.first_step
    step.first_arg = first_arg
    step.second_arg = second_arg
    step.calculate()
    return step.result
