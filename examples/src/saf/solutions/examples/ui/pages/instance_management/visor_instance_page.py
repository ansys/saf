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

import json
import os
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, html, no_update  # pyright: ignore[reportMissingTypeStubs]
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.helpers import handle_method_event

VISOR_BASE_PATH = os.getenv("GLOW_UI_PATH_PREFIX", "/").rstrip("/")

dash.register_page(
    __name__,
    name="Visor Instance Management",
    path_template="/projects/<project_id>/visor-instance-management",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def _create_visor_viewer(host: str, port: int) -> Any:
    """Create an isolated viewer document connected to the local Visor instance."""
    viewer_args = json.dumps(
        {
            "host": host,
            "port": port,
            "basePath": VISOR_BASE_PATH,
        }
    ).replace("<", "\\u003c")
    asset_prefix = VISOR_BASE_PATH or ""
    src_doc = f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="{asset_prefix}/visordash/css.css">
</head>
<body style="margin: 0; width: 100vw; height: 100vh; overflow: hidden;">
    <div id="VisorContainer" style="width: 100%; height: 100%;"></div>
    <script>window.__visorArgs = {viewer_args};</script>
    <script type="module" src="{asset_prefix}/visordash/js.js"></script>
</body>
</html>"""
    return html.Iframe(
        id="visor-viewer-component",
        srcDoc=src_doc,
        title="VISOR viewer",
        style={
            "width": "100%",
            "height": "100%",
            "border": "0",
            "display": "block",
        },
    )


def layout(project: ExamplesSolution) -> html.Div:
    """Layout for the VISOR Instance Manager page."""
    step = project.steps.visor_step
    viewer: Any = []
    if step.visor_started:
        if not step.visor_host or step.visor_port is None:
            raise RuntimeError("VISOR is marked as running without a host and port.")
        viewer = _create_visor_viewer(step.visor_host, step.visor_port)

    controls_card = dmc.Card(
        [
            dmc.CardSection(
                dmc.Group(
                    children=[
                        dmc.Text("Controls", fw=500, style={"font-size": "17px"}),
                    ],
                    justify="space-between",
                ),
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
                            disabled=step.visor_started,
                            loading=False,
                        ),
                        label="Start Visor",
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
            dmc.Divider(variant="solid"),
            dmc.Space(h=20),
                dmc.Stack(
                [
                    dmc.Button(
                        "Show Shape",
                        id="show-visor-shape-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="mdi:eye"),
                        disabled=not step.visor_started,
                        style={"width": "70%", "font-size": "15px"},
                    ),
                ],
                align="center",
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
    )

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
                    "height": "200px",
                    "width": "100%",
                    "overflowY": "scroll",
                },
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
    )

    visor_viewer_container = dmc.Card(
        [
            dmc.CardSection(
                dmc.Text("Viewer", fw=500, style={"font-size": "17px"}),
                withBorder=True,
                inheritPadding=True,
                py="xs",
            ),
            html.Div(
                viewer,
                id="visor-viewer-container",
                style={
                    "width": "100%",
                    "height": "calc(100vh - 240px)",
                    "minHeight": "0",
                    "overflow": "hidden",
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
                "This example demonstrates how to leverage the instance management API to control VISOR.\
                Click the Launch action button to\
                start the instance. A transaction method will start VISOR which can be used across all transaction\
                methods of the solution. Run VISOR operations with the Show Shape and\
                button. Close VISOR using the Shutdown button.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Grid(
                [
                    dmc.GridCol(
                        controls_card,
                        span={"base": 12, "lg": 3},
                    ),
                    dmc.GridCol(
                        logs_container,
                        span={"base": 12, "lg": 9},
                    ),
                    dmc.GridCol(
                        visor_viewer_container,
                        span=12,
                    ),
                ],
                grow=True,
                gutter="xs",
            ),
            DashClient.create_event_listener(  # pyright: ignore[reportUnknownMemberType]
                step, id="output-listener", stream_name="visor-output-stream"
            ),
            DashClient.create_event_listener(  # pyright: ignore[reportUnknownMemberType]
                step, id="start-visor-listener", stream_name="start-visor"
            ),
        ],
        style={"paddingLeft": "20px"},
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("start-visor-button", "disabled", allow_duplicate=True),
    Output("start-visor-button", "loading", allow_duplicate=True),
    Input("start-visor-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def start_visor(n_clicks: int, project: ExamplesSolution) -> tuple[list[dict[str, Any]] | str, bool, bool]:
    """Initialize the VISOR instance."""
    if not n_clicks:
        return no_update, no_update, no_update # No update to notification, start button disabled, start button loading

    step = project.steps.visor_step
    step.start_visor()

    return (
        [ # Notification
            dict(
                title="Info",
                id="start-visor-notification",
                action="show",
                message="Starting VISOR instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ],
        True, # disable_launch_button
        True, # loading_launch_button
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("start-visor-button", "disabled", allow_duplicate=True),
    Output("start-visor-button", "loading", allow_duplicate=True),
    Output("stop-visor-button", "disabled", allow_duplicate=True),
    Output("show-visor-shape-button", "disabled", allow_duplicate=True),
    Input("start-visor-listener", "message"),
    prevent_initial_call=True,
)
def sync_start_controls_on_backend_event(
    message: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | Any, bool, bool, bool, bool]:
    """Update the Visor controls and notification after startup completes."""
    if not message:
        return no_update, no_update, no_update, no_update, no_update

    method_state = MethodState.model_validate_json(message["data"])
    notification = handle_method_event(
        method_state,
        "start-visor-notification",
        "VISOR instance launched successfully!",
        "VISOR initialization failed. Please check the logs.",
    )
    if method_state.status.value == "completed":
        return notification, True, False, False, False
    if method_state.status.value == "failed":
        return notification, False, False, True, True
    return notification, True, True, True, True


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("show-visor-shape-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def show_visor_shape(n_clicks: int | None, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Display the cube in the running VISOR instance."""
    if not n_clicks:
        return no_update

    project.steps.visor_step.show_shape()
    return [
        dict(
            title="Success",
            id="show-visor-shape-notification",
            action="show",
            message="Cube displayed in VISOR.",
            color="green",
            autoClose=5000,
            withCloseButton=True,
        )
    ]


@callback(
    Output("visor-viewer-container", "children"),
    Input("start-visor-listener", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def display_visor_viewer(
    message: dict[str, Any] | None,
    project: ExamplesSolution,
) -> Any:
    """Display the Visor viewer after its start transaction completes."""
    if not message:
        return no_update

    method_state = MethodState.model_validate_json(message["data"])
    status = method_state.status.value.lower()
    if status == "completed":
        step = project.steps.visor_step
        if not step.visor_host or step.visor_port is None:
            raise RuntimeError("Visor completed without reporting its host and port.")
        return [_create_visor_viewer(step.visor_host, step.visor_port)]

    return no_update


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("visor-viewer-container", "children", allow_duplicate=True),
    Output("start-visor-button", "disabled", allow_duplicate=True),
    Output("stop-visor-button", "disabled", allow_duplicate=True),
    Output("show-visor-shape-button", "disabled", allow_duplicate=True),
    Input("stop-visor-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def shutdown_visor(n_clicks: int, project: ExamplesSolution) -> tuple[list[dict[str, Any]] | str, list[Any], bool, bool, bool]:
    """Shutdown the VISOR instance."""
    notification = no_update
    visor_viewer_children = no_update
    disable_launch_button = no_update
    disable_shutdown_button = no_update
    disable_show_shape_button = no_update

    if n_clicks:
        step = project.steps.visor_step

        try:
            step.shutdown_visor()
            notification = [
                dict(
                    title="Success",
                    id="shutdown-visor-notification",
                    action="show",
                    message="Visor instance shutdown successfully.",
                    autoClose=5000,
                    color="green",
                    withCloseButton=True,
                )
            ]
            visor_viewer_children = []
            disable_launch_button = False
            disable_shutdown_button = True
            disable_show_shape_button = True
        except Exception:
            notification = [
                dict(
                    title="Error",
                    id="shutdown-visor-notification",
                    action="show",
                    message="Failed to shutdown Visor instance.",
                    autoClose=5000,
                    color="red",
                    withCloseButton=True,
                )
            ]
            
    return (
        notification,
        visor_viewer_children,
        disable_launch_button,
        disable_shutdown_button,
        disable_show_shape_button,
    )

@callback(
    Output("visor-console-logs", "children", allow_duplicate=True),
    Input("output-listener", "message"),
    State("visor-console-logs", "children"),
    prevent_initial_call=True,
)
def display_visor_output(message: dict[str, Any], current_logs: str) -> str:
    """Display Visor transaction output."""
    if message:
        new_content = message["data"].strip('"').replace("\\n", "\n")
        combined = (current_logs or "") + "\n" + new_content
        return combined
    return current_logs


@callback(
    Output("visor-console-logs", "children"),
    Input("clear-logs-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int) -> str:
    """Clear the console logs."""
    return ""