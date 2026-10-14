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
from dash_extensions.enrich import (  # pyright: ignore[reportMissingTypeStubs]
    Input,
    Output,
    State,
    clientside_callback,
    dcc,
    html,
    no_update,
)
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]
from visordash import Visordash

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


def _create_visor_viewer(host: str, port: int, dark_mode: bool) -> Any:
    """Create the VISOR Dash component with the selected solution theme."""
    return Visordash(
        id="visor-viewer-component",
        host=host,
        port=port,
        #basePath=VISOR_BASE_PATH,
        darkMode=dark_mode,
    )


def layout(project: ExamplesSolution) -> html.Div:
    """Layout for the VISOR Instance Manager page."""
    step = project.steps.visor_step
    viewer: Any = []
    if step.visor_started:
        if not step.visor_host or step.visor_port is None:
            raise RuntimeError("VISOR is marked as running without a host and port.")
        viewer = _create_visor_viewer(step.visor_host, step.visor_port, dark_mode=True)

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
                        "Show Piston rod",
                        id="show-visor-piston-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="mdi:eye"),
                        disabled=not step.visor_started,
                        style={"width": "70%", "font-size": "15px"},
                    ),
                    dmc.Button(
                        "Show Spheres",
                        id="show-visor-spheres-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="mdi:eye"),
                        disabled=not step.visor_started,
                        style={"width": "70%", "font-size": "15px"},
                    ),
                    dmc.Button(
                        "Show Elbow",
                        id="show-visor-elbow-button",
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
                    "height": "220px",
                    "width": "100%",
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
                'This example demonstrates how to leverage the instance management API to control VISOR.\
                Click the Launch action button to\
                start the instance. A transaction method will start VISOR which can be used across all transaction\
                methods of the solution. Run VISOR operations with the "Show" buttons. The models used in this\
                example are selected to represent different capabilities of VISOR, do not hesitate to play with\
                them to test the possibilities. Close VISOR using the Shutdown button.',
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
            dcc.Store(id="visor-reload-trigger"),
            html.Div(id="visor-reload-target", style={"display": "none"}),
            html.Div(id="visor-theme-sync-target", style={"display": "none"}),
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
        return no_update, no_update, no_update  # No update to notification, start button disabled, start button loading

    step = project.steps.visor_step
    step.start_visor()

    return (
        [  # Notification
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
        True,  # disable_launch_button
        True,  # loading_launch_button
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("start-visor-button", "disabled", allow_duplicate=True),
    Output("start-visor-button", "loading", allow_duplicate=True),
    Output("stop-visor-button", "disabled", allow_duplicate=True),
    Output("show-visor-piston-button", "disabled", allow_duplicate=True),
    Output("show-visor-spheres-button", "disabled", allow_duplicate=True),
    Output("show-visor-elbow-button", "disabled", allow_duplicate=True),
    Input("start-visor-listener", "message"),
    prevent_initial_call=True,
)
def sync_start_controls_on_backend_event(
    message: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | Any, bool, bool, bool, bool, bool, bool]:
    """Update the Visor controls and notification after startup completes."""
    if not message:
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    method_state = MethodState.model_validate_json(message["data"])
    notification = handle_method_event(
        method_state,
        "start-visor-notification",
        "VISOR instance launched successfully!",
        "VISOR initialization failed. Please check the logs.",
    )
    if method_state.status.value == "completed":
        return notification, True, False, False, False, False, False
    if method_state.status.value == "failed":
        return notification, False, False, True, True, True, True
    return notification, True, True, True, True, True, True


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("show-visor-piston-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def show_visor_piston(n_clicks: int | None, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Display the piston rod in the running VISOR instance."""
    if not n_clicks:
        return no_update

    project.steps.visor_step.show_piston()
    return [
        dict(
            title="Success",
            id="show-visor-shape-notification",
            action="show",
            message="Piston rod displayed in VISOR.",
            color="green",
            autoClose=5000,
            withCloseButton=True,
        )
    ]


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("show-visor-spheres-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def show_visor_spheres(n_clicks: int | None, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Display the spheres in the running VISOR instance."""
    if not n_clicks:
        return no_update

    project.steps.visor_step.show_spheres()
    return [
        dict(
            title="Success",
            id="show-visor-spheres-notification",
            action="show",
            message="Spheres displayed in VISOR.",
            color="green",
            autoClose=5000,
            withCloseButton=True,
        )
    ]


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("show-visor-elbow-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def show_visor_elbow(n_clicks: int | None, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Display the elbow in the running VISOR instance."""
    if not n_clicks:
        return no_update

    project.steps.visor_step.show_elbow()
    return [
        dict(
            title="Success",
            id="show-visor-elbow-notification",
            action="show",
            message="Elbow displayed in VISOR.",
            color="green",
            autoClose=5000,
            withCloseButton=True,
        )
    ]


@callback(
    Output("visor-viewer-container", "children"),
    Input("start-visor-listener", "message"),
    State("color-scheme-switch", "checked"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def display_visor_viewer(
    message: dict[str, Any] | None,
    dark_mode: bool,
    project: ExamplesSolution,
) -> Any:
    """Display or remount the Visor viewer using the selected solution theme."""
    step = project.steps.visor_step
    if message:
        method_state = MethodState.model_validate_json(message["data"])
        if method_state.status.value.lower() != "completed":
            return no_update
    elif not step.visor_started:
        return no_update

    if not step.visor_started:
        return []
    if not step.visor_host or step.visor_port is None:
        raise RuntimeError("Visor is marked as running without a host and port.")
    return [_create_visor_viewer(step.visor_host, step.visor_port, dark_mode=dark_mode)]


clientside_callback(
    """
    function(viewerChildren, switchOn, pathname) {
        if (
            !pathname ||
            !pathname.endsWith("/visor-instance-management") ||
            !viewerChildren ||
            (Array.isArray(viewerChildren) && viewerChildren.length === 0)
        ) {
            return window.dash_clientside.no_update;
        }

        const applyTheme = async () => {
            const visorState = window.__visorState;
            if (!visorState) {
                window.setTimeout(applyTheme, 100);
                return;
            }

            try {
                const appState = await visorState.getAppStateAsync();
                appState.ui.setDarkTheme(Boolean(switchOn));
                await visorState.setAppStateAsync(appState, true);
            } catch (error) {
                console.error("Failed to synchronize the VISOR theme.", error);
            }
        };

        applyTheme();
        return window.dash_clientside.no_update;
    }
    """,
    Output("visor-theme-sync-target", "children"),
    Input("visor-viewer-container", "children"),
    Input("color-scheme-switch", "checked"),
    Input("url", "pathname"),
)


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("visor-viewer-container", "children", allow_duplicate=True),
    Output("start-visor-button", "disabled", allow_duplicate=True),
    Output("stop-visor-button", "disabled", allow_duplicate=True),
    Output("show-visor-piston-button", "disabled", allow_duplicate=True),
    Output("show-visor-spheres-button", "disabled", allow_duplicate=True),
    Output("show-visor-elbow-button", "disabled", allow_duplicate=True),
    Input("stop-visor-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def shutdown_visor(
    n_clicks: int, project: ExamplesSolution
) -> tuple[list[dict[str, Any]] | str, list[Any], bool, bool, bool, bool, bool]:
    """Shutdown the VISOR instance."""
    notification = no_update
    visor_viewer_children = no_update
    disable_launch_button = no_update
    disable_shutdown_button = no_update
    disable_show_piston_button = no_update
    disable_show_spheres_button = no_update
    disable_show_elbow_button = no_update

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
            disable_show_piston_button = True
            disable_show_spheres_button = True
            disable_show_elbow_button = True
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
        disable_show_piston_button,
        disable_show_spheres_button,
        disable_show_elbow_button,
    )


@callback(
    Output("visor-console-logs", "children", allow_duplicate=True),
    Output("visor-reload-trigger", "data", allow_duplicate=True),
    Input("output-listener", "message"),
    State("visor-console-logs", "children"),
    prevent_initial_call=True,
)
def display_visor_output(message: dict[str, Any], current_logs: str) -> tuple[str, Any]:
    """Display Visor transaction output."""
    if message:
        new_content = message["data"].strip('"').replace("\\n", "\n")
        combined = (current_logs or "") + "\n" + new_content
        reload_requested = new_content == "VISOR instance shutdown complete."
        return combined, reload_requested or no_update
    return current_logs, no_update


@callback(
    Output("visor-console-logs", "children"),
    Input("clear-logs-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int) -> str:
    """Clear the console logs."""
    return ""


clientside_callback(
    """
    function(reloadRequested) {
        if (reloadRequested) {
            window.location.reload();
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("visor-reload-target", "children"),
    Input("visor-reload-trigger", "data"),
    prevent_initial_call=True,
)
