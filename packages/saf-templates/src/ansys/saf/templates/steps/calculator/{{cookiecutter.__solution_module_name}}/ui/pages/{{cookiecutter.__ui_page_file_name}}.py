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

"""Frontend of {{ cookiecutter.__step_name }}."""

from ansys.saf.glow.client import callback
import dash
from dash_extensions.enrich import Input, Output, State, dcc, html
import dash_mantine_components as dmc

from {{ cookiecutter.__solution_namespace }}.{{ cookiecutter.__solution_module_name }}.solution.definition import {{ cookiecutter.__solution_definition_class_name }}


dash.register_page(__name__, name="{{ cookiecutter.__step_display_name }}", path_template="/projects/<project_id>/{{ cookiecutter.__step_module_name_hyphenated }}", icon_asset_name="game-icons--crossed-air-flows.svg", icon_asset_path="icons")


def layout(project: {{cookiecutter.__solution_definition_class_name}}):
    """Layout of the {{ cookiecutter.__step_name }} page."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    return html.Div(
        [
            html.H1("{{ cookiecutter.__step_display_name }}", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.P(
                "Compute the sum of two numbers.",
                className="lead",
                style={"font-size": "20px"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="First Argument",
                id="{{ cookiecutter.__step_name }}-first-arg",
                value=step.first_arg,
                placeholder="Enter first argument",
                required=True,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="Second Argument",
                id="{{ cookiecutter.__step_name }}-second-arg",
                value=step.second_arg,
                placeholder="Enter second argument",
                required=True,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Calculate",
                id="{{ cookiecutter.__step_name }}-calculate",
                leftSection=html.Img(src=dash.get_asset_url("icons/dark/streamline--startup-solid.svg")),
                radius="md",
                disabled=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="Result",
                id="{{ cookiecutter.__step_name }}-result",
                value=step.result,
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
                children=html.Div(id="{{ cookiecutter.__step_name }}_wait_completion"),
            ),
        ]
    )


@callback(
    Output("{{ cookiecutter.__step_name }}-result", "value"),
    Output("{{ cookiecutter.__step_name }}_wait_completion", "children"),
    Input("{{ cookiecutter.__step_name }}-calculate", "n_clicks"),
    State("{{ cookiecutter.__step_name }}-first-arg", "value"),
    State("{{ cookiecutter.__step_name }}-second-arg", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def calculate(n_clicks: int, first_arg: int, second_arg: int, project: {{cookiecutter.__solution_definition_class_name}}):
    """Trigger the computation."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    step.first_arg = first_arg
    step.second_arg = second_arg
    step.calculate()
    return step.result, True
