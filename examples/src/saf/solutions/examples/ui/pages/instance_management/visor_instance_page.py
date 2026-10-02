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

"""Frontend of the Visor instance management page."""

import base64
from pathlib import Path
from typing import Any

from ansys.bdm.api import NO_ENTITY
from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, dcc, html, no_update  # pyright: ignore[reportMissingTypeStubs]
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from saf.solutions.examples.solution.definition import ExamplesSolution

dash.register_page(
    __name__,
    name="Visor Instance Management",
    path_template="/projects/<project_id>/visor-instance-management",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def _create_visor_viewer(port: int) -> Any:
    """Create a Visor viewer connected to the local Visor instance."""
    try:
        from visordash import Visordash  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The Visor UI dependency is not installed. Install ansys-visor-viewer to use this page."
        ) from exc

    return Visordash(
        host="localhost",
        port=port,
        aspectRatio=1,
        pixelDensity=800,
    )


def layout(project: ExamplesSolution) -> html.Div:
    """Layout for the VISOR Instance Manager page."""
    step = project.steps.visor_step

    controls_card = dmc.Card(
        [
            dmc.CardSection(
                dmc.Text("Input files", fw=500, style={"font-size": "17px"}),
                withBorder=True,
                inheritPadding=True,
                py="xs",
            ),
            dmc.Space(h=20),
            dmc.Group(
                [
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="streamline:startup-solid", width=30),
                            id="start-visor-button",
                            size="xl",
                            color="#2790F1",
                        ),
                        label="Start or refresh Visor",
                        position="top",
                    ),
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:shutdown", width=30),
                            id="stop-visor-button",
                            size="xl",
                            color="#2790F1",
                            disabled=not step.visor_started,
                        ),
                        label="Stop Visor",
                        position="top",
                    ),
                ],
                gap="md",
                justify="center",
            ),
            dmc.Space(h=20),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
    ),
    
    logs_container = dmc.Card(
        [
            dmc.CardSection(
                dmc.Group(
                    children=[
                        dmc.Text("Logs", fw=500, style={"font-size": "17px"}),
                        dmc.Tooltip(
                            dmc.ActionIcon(
                                DashIconify(icon="mdi:delete-sweep", width=24),
                                id="clear-logs-button",
                                color="gray",
                                variant="transparent",
                            ),
                            label="Clear Logs",
                            position="left",
                        ),
                    ],
                    justify="space-between",
                ),
                withBorder=True,
                inheritPadding=True,
                py="xs",
            ),
            dmc.Space(h=20),
            html.Div(
                html.Pre(
                    id="visor-console-logs",
                    style={
                        "whiteSpace": "pre-wrap",
                        "wordBreak": "break-all",
                        "fontSize": "14px",
                        "height": "100%",
                        "overflowY": "auto",
                        "margin": "0",
                    },
                ),
                style={
                    "height": "600px",
                    "width": "100%",
                    "overflowY": "scroll",
                },
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
    )

    return html.Div(
        [
            html.H1(
                "VISOR Instance Manager",
                className="display-3",
                style={"font-size": "40px", "font-weight": "bold"},
            ),
            dmc.Blockquote(
                "This example demonstrates how to leverage the instance management API to control VISOR. \
                Click the lauch button to start the instance.\
                A transaction method will start VISOR which can be used across transaction methods of the solution. \
                run VISOR operations with the TO DEFINE buttons. Close VISOR using the shutdown button.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Alert(
                dmc.Text(
                    "⚠️ Install ansys-visor-viewer and configure the VISOR product instance before launching this example.",
                ),
                title="Warning",
                color="yellow",
            ),
            dmc.Space(h=20),
            dmc.Grid(
                [
                    dmc.GridCol(
                        controls_card,
                        span=3,
                    ),
                    dmc.GridCol(logs_container, span=9),
                    dmc.GridCol(
                        dmc.Card(
                            [
                                dmc.CardSection(
                                    dmc.Text("Viewer", fw=500, style={"font-size": "17px"}),
                                    withBorder=True,
                                    inheritPadding=True,
                                    py="xs",
                                ),
                                html.Div(
                                    id="visor-viewer",
                                    style={
                                        "width": "100%",
                                        "height": "calc(100vh - 240px)",
                                        "minHeight": "500px",
                                        "overflow": "hidden",
                                    },
                                ),
                            ],
                            withBorder=True,
                            shadow="sm",
                            radius="md",
                        ),
                        span=9,
                    ),
                ],
                grow=True,
                gutter="xs",
            ),
            DashClient.create_event_listener(  # pyright: ignore[reportUnknownMemberType]
                step, id="output-listener", stream_name="visor-output-stream"
            ),
            DashClient.create_event_listener(
                step, id="start-visor-listener", stream_name="start-visor"
            ),
            DashClient.create_event_listener(
                step, id="refresh-visor-listener", stream_name="refresh-visor"
            ),
        ],
        style={"paddingLeft": "20px"},
    )


@callback(
    Output("start-visor-button", "disabled", allow_duplicate=True),
    Input("start-visor-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def start_or_refresh_visor(n_clicks: int | None, project: ExamplesSolution) -> tuple[str, bool]:
    """Start Visor or refresh the connection to an existing instance."""
    if not n_clicks:
        return no_update, no_update

    step = project.steps.visor_step
    if step.visor_started:
        step.refresh_visor()
        return "Refreshing Visor...", True

    step.start_visor()
    return "Starting Visor...", True


@callback(
    Output("visor-viewer", "children"),
    Output("start-visor-button", "disabled"),
    Output("stop-visor-button", "disabled"),
    Input("start-visor-listener", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def display_visor_viewer(
    start_message: dict[str, Any] | None,
    refresh_message: dict[str, Any] | None,
    project: ExamplesSolution,
) -> tuple[Any, str, bool, bool, bool]:
    """Display the Visor viewer after its start or refresh transaction completes."""
    message = start_message or refresh_message
    if not message:
        return no_update, no_update, no_update, no_update, no_update

    method_state = MethodState.model_validate_json(message["data"])
    status = method_state.status.value.lower()
    if status == "completed":
        step = project.steps.visor_step
        if step.visor_port is None:
            raise RuntimeError("Visor completed without reporting a port.")
        return (
            [_create_visor_viewer(step.visor_port)],
            f"Visor started: {step.visor_started}",
            False,
            not (step.visor_started and step.volume_vtp != NO_ENTITY),
            False,
        )
    if status == "failed":
        return no_update, "Visor failed to start. Check the transaction logs.", False, True, True

    return no_update, f"Visor status: {method_state.status.value}", True, True, True


@callback(
    Output("visor-viewer", "children", allow_duplicate=True),
    Output("visor-started-status", "children", allow_duplicate=True),
    Output("visor-updated-status", "children"),
    Output("start-visor-button", "disabled", allow_duplicate=True),
    Output("update-visor-button", "disabled", allow_duplicate=True),
    Output("stop-visor-button", "disabled", allow_duplicate=True),
    Input("stop-visor-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def stop_visor(
    n_clicks: int | None,
    project: ExamplesSolution,
) -> tuple[list[Any], str, str, bool, bool, bool]:
    """Stop the Visor instance and clear the viewer."""
    if not n_clicks:
        return no_update, no_update, no_update, no_update, no_update, no_update
    project.steps.visor_step.close_visor()
    return [], "Visor started: False", "Visor updated: False", False, True, True


@callback(
    Output("visor-console-logs", "children"),
    Input("clear-logs-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int) -> str:
    """Clear the console logs."""
    return ""