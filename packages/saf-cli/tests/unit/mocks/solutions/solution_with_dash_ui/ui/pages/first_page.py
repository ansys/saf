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

import dash  # pyright: ignore[reportMissingTypeStubs]
from dash_extensions.enrich import Input, Output, State, dcc, html  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.glow.client import callback
from ansys.solutions.dash_super_components import InputRow, OutputRow  # type: ignore
from tests.unit.mocks.solutions.solution_with_dash_ui.solution.definition import SolutionWithDashUiSolution

dash.register_page(  # pyright: ignore[reportUnknownMemberType]
    __name__,
    name="First Step",
    path_template="/projects/<project_id>/first-step",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def layout(project: SolutionWithDashUiSolution):
    """Layout of the first step page."""
    step = project.steps.first_step
    return html.Div(
        [  # pyright: ignore[reportUnknownArgumentType]
            html.H1("First Step", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.P(
                "Compute the sum of two numbers.",
                className="lead",
                style={"font-size": "20px"},
            ),
            html.Br(),
            InputRow(  # pyright: ignore[reportUnknownMemberType]
                "number",
                "first-arg",
                "First Argument",
                row_default_value=step.first_arg,
                row_description="Enter a value.",
                label_width=2,
                value_width=4,
                unit_width=1,
                description_width=4,
                font_size="16px",
            ).get(),
            InputRow(  # pyright: ignore[reportUnknownMemberType]
                "number",
                "second-arg",
                "Second Argument",
                row_default_value=step.second_arg,
                row_description="Enter a value.",
                label_width=2,
                value_width=4,
                unit_width=1,
                description_width=4,
                font_size="16px",
            ).get(),
            html.Br(),
            html.Div(
                dmc.Button(
                    "Calculate",
                    id="calculate",
                    leftIcon=html.Img(
                        src=dash.get_asset_url(  # pyright: ignore[reportUnknownMemberType]
                            "icons/streamline--startup-solid.svg",
                        ),
                    ),
                    radius="xl",
                    disabled=False,
                    className="mantine-button",
                    style={"color": "#FFFFFF", "width": "100%", "background-color": "#000000", "font-size": "14px"},
                ),
                style={
                    "textAlign": "center",
                    "margin-left": "275px",
                    "width": "500px",
                },
            ),
            html.Br(),
            OutputRow(  # pyright: ignore[reportUnknownMemberType]
                "number",
                "result",
                "Result",
                row_default_value=step.result,
                label_width=2,
                value_width=4,
                unit_width=1,
                description_width=4,
                class_name="button",
                font_size="16px",
            ).get(),
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
def calculate(n_clicks: int, first_arg: int, second_arg: int, project: SolutionWithDashUiSolution):
    """Trigger the computation."""
    step = project.steps.first_step
    step.first_arg = first_arg
    step.second_arg = second_arg
    step.calculate()
    return step.result, True
