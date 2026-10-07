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

"""Frontend of the about page."""

import logging

from ansys.saf.glow.client import callback
from ansys.saf.glow.solution import MethodStatus
import dash
import dash_bootstrap_components as dbc
from dash_extensions.enrich import Input, dcc, html
import dash_mantine_components as dmc

from saf.solutions.examples.solution.definition import ExamplesSolution

# Registers the application-scoped callbacks (event listeners, ADR setup) of the Airfoil Explorer.
from saf.solutions.examples.ui.airfoil_explorer import shell_callbacks  # noqa: F401
from saf.solutions.examples.ui.airfoil_explorer.settings import settings
from saf.solutions.examples.ui.airfoil_explorer.utils.navigation import get_airfoil_explorer_page

logger = logging.getLogger(__name__)

dash.register_page(
    __name__,
    name="About",
    path_template="/projects/<project_id>/airfoil-explorer/about",
)


def layout():
    """Layout of the about page."""
    return html.Div(
        dbc.Container(
            [
                html.H1(
                    "Airfoil Explorer",
                    className="display-3",
                    style={"font-size": "48px", "fontWeight": "bold"},
                ),
                html.P(
                    """
                    Airfoil Explorer demonstrates how airfoil shape influences airflow behavior.
                    """,
                    className="lead",
                    style={"font-size": "20px"},
                ),
                html.Hr(className="my-2"),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Row(
                                    [
                                        html.H4("Description", style={"font-size": "24px", "fontWeight": "bold"}),
                                        dcc.Markdown(
                                            """
                                            Airfoil Explorer demonstrates how **airfoil shape** influences airflow
                                            behavior. By adjusting parameters such as maximum camber, camber position,
                                            thickness, and angle of attack, users can observe how these changes affect
                                            the surrounding flow.

                                            The application simulates airflow over **NACA-style airfoils** and
                                            visualizes the resulting flow field using streamlines.
                                            """,
                                            style={"font-size": "16px", "textAlign": "justify"},
                                        ),
                                        dmc.Space(h=30),
                                        html.H4(
                                            "Engineering Problem", style={"font-size": "24px", "fontWeight": "bold"}
                                        ),
                                        dcc.Markdown(
                                            """
                                            This application models **two-dimensional potential flow** around an
                                            airfoil placed in a uniform, inviscid flow with free stream velocity.

                                            **Objectives:**
                                            - Predict the potential-flow pattern around the airfoil
                                            - Visualize flow behavior using streamlines
                                            - Assess how airfoil parameters affect the resulting flow field
                                            """,
                                            style={"font-size": "16px", "textAlign": "justify"},
                                        ),
                                        dmc.Space(h=30),
                                        html.H4("How the App Works", style={"font-size": "24px", "fontWeight": "bold"}),
                                        dcc.Markdown(
                                            """
                                            The application guides users from **airfoil setup**, to **running the
                                            simulation**, to **reviewing a generated engineering report**
                                            """,
                                            style={"font-size": "16px", "textAlign": "justify"},
                                        ),
                                    ]
                                )
                            ],
                            width=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Row(
                                    [
                                        dbc.Card(
                                            [
                                                dbc.CardImg(
                                                    src=dash.get_asset_url(
                                                        "images/airfoil_explorer/airfoil_explorer.png"
                                                    )
                                                ),  # pragma: no cover
                                                dbc.CardFooter(
                                                    "Airflow over a NACA-style airfoil.",
                                                    style={"textAlign": "center", "fontSize": "14px", "color": "#666"},
                                                ),
                                            ],
                                            style={
                                                "maxWidth": "80%",
                                                "margin": "0 auto",
                                                "display": "block",
                                                "borderRadius": "8px",
                                                "boxShadow": "0 2px 8px rgba(0,0,0,0.08)",
                                            },
                                        )
                                    ]
                                )
                            ],
                            width=6,
                        ),
                    ]
                ),
            ],
            fluid=True,
        ),
    )


@callback(Input("url", "pathname"), Input("url", "href"), prevent_initial_call=True)
def launch_visor(project: ExamplesSolution, href: str):
    """Launch the Visor service when navigating to the Airfoil Explorer."""
    if not settings.visor_enabled or get_airfoil_explorer_page(href) is None:
        return
    try:
        step = project.steps.service_launch_step
        if step.get_method_state("launch_visor").status == MethodStatus.RunRequired:
            step.launch_visor()
        else:
            step.restart_visor()
    except Exception:
        logger.exception("Visor launch from about page failed")
