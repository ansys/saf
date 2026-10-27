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

# ©2023, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""
Frontend of the Plotly graph example page.

This page displays the transcendental butterfly curve computed by the ``BasicStep`` step in
a ``dcc.Graph`` component. One slider per curve parameter lets the user reshape the curve:
each change writes the parameter to the step, invokes the ``compute_butterfly_curve``
transaction method, and refreshes the figure with the new coordinates.

The ``BUTTERFLY_PARAMETERS`` list drives the sliders. Each entry maps a step field name,
used as the component identifier, to the label and the bounds of its slider.
"""

from ansys.saf.glow.client import callback
import dash
from dash_extensions.enrich import Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from saf.solutions.examples.solution.steps.basic_step import BasicStep
from saf.solutions.examples.solution.definition import ExamplesSolution

dash.register_page(
    __name__,
    name="Plotly Graph",
    path_template="/projects/<project_id>/plotly-graph",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)

BUTTERFLY_PARAMETERS = [
    {"id": "butterfly_wing_frequency", "label": "Wing frequency", "min": 1, "max": 12, "step": 0.5},
    {"id": "butterfly_wing_amplitude", "label": "Wing amplitude", "min": 0, "max": 5, "step": 0.1},
    {"id": "butterfly_twist", "label": "Twist", "min": 1, "max": 24, "step": 1},
    {"id": "butterfly_exponent", "label": "Exponent", "min": 1, "max": 9, "step": 1},
    {"id": "butterfly_revolutions", "label": "Revolutions (x pi)", "min": 2, "max": 24, "step": 1},
]


def _butterfly_parameters(step: BasicStep) -> list[html.Div]:
    """
    Build the sliders controlling the butterfly curve parameters.

    Each slider is identified by the name of the step field it controls and is initialized
    with the value currently stored in the step.

    Parameters
    ----------
    step : BasicStep
        Step holding the current value of each butterfly curve parameter.

    Returns
    -------
    list[html.Div]
        One ``html.Div`` per parameter, each containing a label and a ``dmc.Slider``.
    """
    return [
        html.Div(
            [
                dmc.Text(parameter["label"], size="sm", mt="md"),
                dmc.Slider(
                    id=parameter["id"],
                    value=getattr(step, parameter["id"]),
                    min=parameter["min"],
                    max=parameter["max"],
                    step=parameter["step"],
                    precision=1,
                    labelAlwaysOn=True,
                    mt="lg",
                ),
            ]
        )
        for parameter in BUTTERFLY_PARAMETERS
    ]


def _butterfly_figure(step: BasicStep) -> dict:
    """
    Build the Plotly figure of the butterfly curve.

    The points are colored by their distance to the origin with the ``Bluered`` color scale,
    and the axes share the same scale so that the curve is not distorted.

    Parameters
    ----------
    step : BasicStep
        Step holding the coordinates of the curve and the distance of each point to the
        origin.

    Returns
    -------
    dict
        Figure to pass to the ``figure`` property of the ``dcc.Graph`` component, with its
        ``data`` and ``layout`` keys.
    """
    return {
        "data": [
            {
                "type": "scattergl",
                "x": step.x_coords,
                "y": step.y_coords,
                "mode": "markers",
                "marker": {
                    "size": 3,
                    "color": step.distance,
                    "colorscale": "Bluered",
                    "showscale": True,
                    "colorbar": {"title": {"text": "Distance<br>to origin"}},
                },
                "hovertemplate": "x = %{x:.3f}<br>y = %{y:.3f}<br>r = %{marker.color:.3f}<extra></extra>",
            },
        ],
        "layout": {
            "width": 700,
            "height": 600,
            "xaxis": {
                "title": {"text": "x"},
                "zeroline": True,
                "zerolinecolor": "rgba(0,0,0,0.4)",
                "gridcolor": "rgba(0,0,0,0.1)",
            },
            "yaxis": {
                "title": {"text": "y"},
                "zeroline": True,
                "zerolinecolor": "rgba(0,0,0,0.4)",
                "gridcolor": "rgba(0,0,0,0.1)",
                "scaleanchor": "x",
                "scaleratio": 1,
            },
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "margin": {
                "l": 60,
                "r": 10,
                "b": 50,
                "t": 20,
            },
        },
    }


def layout(project: ExamplesSolution) -> html.Div:
    """
    Build the layout of the Plotly graph example page.

    Parameters
    ----------
    project : ExamplesSolution
        Solution instance injected by the ``DashClient``, used to access the step fields.

    Returns
    -------
    html.Div
        Page content: a card with the parameter sliders and a card with the graph.
    """
    step = project.steps.basic_step
    return html.Div(
        [
            html.H1("Plotly graph", className="display-3", style={"font-size": "40px", "font-weight": "bold"}),
            dmc.Blockquote(
                [
                    "Use the ",
                    html.A(
                        "dcc.Graph",
                        href="https://dash.plotly.com/dash-core-components/graph",
                        target="_blank",
                        rel="noopener noreferrer",
                    ),
                    " component to visualize the ",
                    html.A(
                        "transcendental butterfly curve",
                        href="https://en.wikipedia.org/wiki/Butterfly_curve_(transcendental)",
                        target="_blank",
                        rel="noopener noreferrer",
                    ),
                    " computed from step fields.",
                ],
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            html.Br(),
            html.Br(),
            dmc.Grid(
                [
                    dmc.GridCol(
                        [
                            dmc.Card(
                                [
                                    dmc.CardSection(
                                        dmc.Text("Butterfly curve parameters", size="md", fw=700),
                                        style={
                                            "padding": "0.75rem 1rem",
                                            "backgroundColor": "#0A76DB",
                                            "color": "rgba(255, 255, 255, 1)",
                                            "borderRadius": "8px 8px 0 0",
                                        },
                                    ),
                                    dmc.CardSection(
                                        [
                                            dmc.Text(
                                                "r(t) = exp(cos t) - amplitude * cos(frequency * t)"
                                                " - sin(t / twist) ** exponent",
                                                size="xs",
                                                fs="italic",
                                            ),
                                            *_butterfly_parameters(step),
                                        ],
                                        style={"padding": "1rem"},
                                    ),
                                ],
                                withBorder=True,
                                radius="md",
                                shadow="sm",
                            )
                        ],
                        span=4,
                    ),
                    dmc.GridCol(
                        [
                            dmc.Card(
                                [
                                    dmc.CardSection(
                                        dmc.Text("Plot", size="md", fw=700),
                                        style={
                                            "padding": "0.75rem 1rem",
                                            "backgroundColor": "#0A76DB",
                                            "color": "rgba(255, 255, 255, 1)",
                                            "borderRadius": "8px 8px 0 0",
                                        },
                                    ),
                                    dmc.CardSection(
                                        [
                                            dmc.Box(
                                                [
                                                    dmc.LoadingOverlay(
                                                        id="graph_loading",
                                                        visible=False,
                                                        loaderProps={"type": "bars", "color": "#0A76DB", "size": "lg"},
                                                        overlayProps={"radius": "sm", "blur": 2},
                                                        zIndex=10,
                                                    ),
                                                    dcc.Graph(
                                                        id="graph",
                                                        figure=_butterfly_figure(step),
                                                    ),
                                                ],
                                                pos="relative",
                                                style={
                                                    "width": "fit-content",
                                                    "margin": "0 auto",
                                                },
                                            ),
                                        ],
                                        style={"padding": "1rem"},
                                    ),
                                ],
                                withBorder=True,
                                radius="md",
                                shadow="sm",
                            )
                        ],
                        span=8,
                    ),
                ],
                gutter="md",
            ),
            html.Br(),
            html.Br(),
        ],
        style={"paddingLeft": "20px"},
    )


@callback(
    Output("graph", "figure"),
    Output("graph_loading", "visible", allow_duplicate=True),
    Input("butterfly_wing_frequency", "value"),
    Input("butterfly_wing_amplitude", "value"),
    Input("butterfly_twist", "value"),
    Input("butterfly_exponent", "value"),
    Input("butterfly_revolutions", "value"),
    State("url", "pathname"),
)
def draw_butterfly_curve(
    wing_frequency: float,
    wing_amplitude: float,
    twist: float,
    exponent: float,
    revolutions: float,
    project: ExamplesSolution,
) -> tuple[dict, bool]:
    """
    Compute the butterfly curve and refresh the figure.

    On the initial call, the curve is computed with the parameters already stored in the
    step. On any other call, the values of the sliders are written to the step fields
    before the ``compute_butterfly_curve`` transaction method is invoked.

    Parameters
    ----------
    wing_frequency : float
        Value of the wing frequency slider.
    wing_amplitude : float
        Value of the wing amplitude slider.
    twist : float
        Value of the twist slider.
    exponent : float
        Value of the exponent slider. It is cast to an integer for the step field.
    revolutions : float
        Value of the revolutions slider.
    project : ExamplesSolution
        Solution instance injected by the ``DashClient`` from the URL of the page.

    Returns
    -------
    tuple[dict, bool]
        The figure of the computed curve and ``False`` to hide the loading overlay.
    """
    step = project.steps.basic_step

    if ctx.triggered_id is None and not step.distance:
        print("Computing butterfly curve for the first time...")
        step.compute_butterfly_curve()
    else:
        print(
            f"Computing butterfly curve for parameters: wing_frequency={wing_frequency}, "
            f"wing_amplitude={wing_amplitude}, twist={twist}, exponent={exponent}, revolutions={revolutions}"
        )
        step.butterfly_wing_frequency = wing_frequency
        step.butterfly_wing_amplitude = wing_amplitude
        step.butterfly_twist = twist
        step.butterfly_exponent = int(exponent)
        step.butterfly_revolutions = revolutions
        step.compute_butterfly_curve()

    print(f"Computed butterfly curve with {len(step.x_coords)} points.")
    return _butterfly_figure(step), False


@callback(
    Output("graph_loading", "visible", allow_duplicate=True),
    Input("butterfly_revolutions", "value"),
    Input("butterfly_wing_frequency", "value"),
    Input("butterfly_wing_amplitude", "value"),
    Input("butterfly_twist", "value"),
    Input("butterfly_exponent", "value"),
    prevent_initial_call=True,
)
def show_loading_overlay(
    revolutions: float,
    wing_frequency: float,
    wing_amplitude: float,
    twist: float,
    exponent: float,
) -> bool:
    """
    Show the loading overlay as soon as a parameter changes.

    This callback returns immediately, while the ``draw_butterfly_curve`` callback hides
    the overlay once the curve has been computed.

    Parameters
    ----------
    revolutions : float
        Value of the revolutions slider.
    wing_frequency : float
        Value of the wing frequency slider.
    wing_amplitude : float
        Value of the wing amplitude slider.
    twist : float
        Value of the twist slider.
    exponent : float
        Value of the exponent slider.

    Returns
    -------
    bool
        Always ``True`` to make the loading overlay visible.
    """
    return True
