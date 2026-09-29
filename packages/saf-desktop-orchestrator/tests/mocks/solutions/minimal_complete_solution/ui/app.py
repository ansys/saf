# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#

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
#


from dash import Input, Output, State, dcc, html  # pyright: ignore[reportMissingTypeStubs]
from dash_extensions.enrich import (  # pyright: ignore[reportMissingTypeStubs]
    DashProxy,
    MultiplexerTransform,
    TriggerTransform,
)

from ansys.saf.glow.client import callback
from tests.mocks.solutions.minimal_complete_solution.solution.definition import MySolution

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
def display_page(project: MySolution):
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
            html.Div(id="custom-product-result"),
            html.Button("Calculate", id="calculate", n_clicks=0),
            html.Button("Launch custom product", id="launch-custom-product", n_clicks=0),
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
def calculate(n_clicks: int, first_arg: float, second_arg: float, project: MySolution) -> float:
    """Trigger the computation."""
    step = project.steps.first_step
    step.first_arg = first_arg
    step.second_arg = second_arg
    step.calculate()
    return step.result


@callback(
    Output("custom-product-result", "children"),
    Input("launch-custom-product", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def launch_custom_product_and_shutdown(n_clicks: int, project: MySolution) -> str:
    """Launch and initialize the custom shared product instance."""
    step = project.steps.instance_manager_step
    assert step.value == "blue"
    step.value = "red"
    assert step.value == "red"
    step.initialize_custom_product()
    step.set_value_on_custom_product(new_value="green")
    step.retrieve_value_from_custom_product()
    step.shutdown_custom_product()
    return step.value
