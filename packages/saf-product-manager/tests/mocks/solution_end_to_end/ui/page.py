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

import json
import logging
from typing import Any

from dash_extensions.enrich import (  # pyright: ignore[reportMissingTypeStubs]
    ALL,
    Input,
    Output,
    callback_context,
    dcc,
    html,
)

from ansys.saf.glow.client import DashClient, Deployment, callback
from tests.mocks.solution_end_to_end.solution.definition import (
    EndToEndSolution,
)
from tests.mocks.solution_end_to_end.ui import first_page, visor_page

logger = logging.getLogger(__name__)

page_list = ["first_page", "visor_page"]

layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),  # represents the browser address bar and doesn't render anything
        html.Div(
            [
                html.Div(
                    [
                        html.Button(
                            "Project Name:",
                            id="project-name",
                            disabled=True,
                        ),
                    ],
                    className="ms-auto",
                    style={"display": "inline-block", "verticalAlign": "middle", "marginLeft": "auto"},
                ),
                html.Div(
                    id="return-to-portal",
                    style={"display": "inline-block", "verticalAlign": "middle", "marginLeft": "16px"},
                ),
            ],
            style={
                "display": "flex",
                "flexDirection": "row",
                "alignItems": "center",
                "gap": "1rem",
                "width": "100%",
            },
        ),
        html.Br(),
        html.Div(
            [
                html.Div(
                    [
                        html.Ul(
                            [
                                html.Li(
                                    html.Button(
                                        page.replace("_", " ").title(),
                                        id={"type": "nav-item", "index": page},
                                        n_clicks=0,
                                        style={
                                            "cursor": "pointer",
                                            "padding": "8px",
                                            "backgroundColor": "#f2f2f2",
                                            "marginBottom": "4px",
                                            "borderRadius": "4px",
                                            "width": "100%",
                                        },
                                    ),
                                    style={
                                        "listStyleType": "none",
                                        "padding": 0,
                                        "border": "none",
                                        "background": "none",
                                    },
                                )
                                for page in page_list
                            ],
                            style={"listStyleType": "none", "padding": 0},
                        ),
                    ],
                    style={
                        "width": "16.6667%",
                        "backgroundColor": "rgba(242, 242, 242, 0.6)",
                        "display": "inline-block",
                        "verticalAlign": "top",
                    },
                ),
                html.Div(
                    id="page-content",
                    style={
                        "display": "inline-block",
                        "width": "83.3333%",
                        "paddingRight": "1%",
                        "verticalAlign": "top",
                    },
                ),
            ],
            style={"width": "100%"},
        ),
    ],
)


@callback(
    Output("return-to-portal", "children"),
    Input("url", "pathname"),
)
def return_to_portal(pathname: str):
    """Display Solution Portal when back-to-portal button gets selected."""
    portal_ui_url = DashClient[EndToEndSolution].get_portal_ui_url()
    children = (
        []
        if portal_ui_url is None
        else [
            html.A(
                html.Button(
                    (
                        "Back to Projects"
                        if DashClient[EndToEndSolution].get_deployment_type() == Deployment.Desktop
                        else "Back to Portal"
                    ),
                    id="return-to-portal",
                    className="me-2",
                    n_clicks=0,
                ),
                href=portal_ui_url,
            ),
        ]
    )
    return children


@callback(
    Output("project-name", "children"),
    Input("url", "pathname"),
)
def display_project_name(project: EndToEndSolution):
    """Display current project name."""
    return f"Project Name: {project.project_display_name}"


# this callback is essential for initializing the step based on the persisted
# state of the project when the browser first displays the project to the user
# given the project's URL
@callback(
    Output("page-content", "children"),
    [
        Input("url", "pathname"),
        Input({"type": "nav-item", "index": ALL}, "n_clicks"),
    ],
    prevent_initial_call=True,
)
def display_page(project: EndToEndSolution, nav_clicks: list[Any]):
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]  # type: ignore
    logger.info(f"Switching page, triggered by {triggered_id}")
    if triggered_id == "url":
        page_layout = first_page.layout(project.steps.maxwell_2d_verification_step)
        return page_layout
    if "nav-item" in triggered_id:
        try:
            if not isinstance(triggered_id, str):
                return html.H1("Navigation trigger is not a string!")
            triggered = json.loads(triggered_id)
            page = triggered["index"]
        except Exception:
            return html.H1("Error parsing navigation trigger!")
        if page == "first_page":
            page_layout = first_page.layout(project.steps.maxwell_2d_verification_step)
        elif page == "visor_page":
            page_layout = visor_page.layout(project.steps.visor_instance_step)
        else:
            page_layout = html.H1(f"Unknown page id {page}")
        return page_layout

    return html.H1(f"Unexpected page trigger: {triggered_id}!")
