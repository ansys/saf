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

# ©2025, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Frontend of {{ cookiecutter.__step_name }}."""

import logging
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, ctx, html, no_update  # pyright: ignore[reportMissingTypeStubs]
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from {{ cookiecutter.__solution_namespace }}.{{ cookiecutter.__solution_module_name }}.solution.definition import {{ cookiecutter.__solution_definition_class_name }}


dash.register_page(__name__, name="{{ cookiecutter.__step_display_name }}", path_template="/projects/<project_id>/{{ cookiecutter.__step_module_name_hyphenated }}", icon_asset_name="game-icons--crossed-air-flows.svg", icon_asset_path="icons")
logger = logging.getLogger(__name__)


def _get_geometry_controls_with_default() -> dict[str, dict[str, bool]]:
    """Return geometry page controls with default state (all disabled, not loading)."""
    return {
        "launch_geometry": {"disabled": True, "loading": False},
        "shutdown_geometry": {"disabled": True, "loading": False},
    }


def layout(project: {{cookiecutter.__solution_definition_class_name}}) -> html.Div:
    """Layout of the {{ cookiecutter.__step_name }} page."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    controls = _get_geometry_controls_with_default()

    long_running_transactions = ["launch_geometry", "shutdown_geometry"]
    long_running_transaction_states = {
        t: step.get_long_running_method_state(t).status.value for t in long_running_transactions
    }

    if any(state == "running" for state in long_running_transaction_states.values()):
        for button in controls:
            if long_running_transaction_states.get(button, "") == "running":
                controls[button]["loading"] = True
    elif step.geometry_available:
        controls["shutdown_geometry"]["disabled"] = False
    else:
        logger.info("No Geometry instance detected, initializing page with default state")
        controls["launch_geometry"]["disabled"] = False

    controls_card = dmc.Card(
        [
            dmc.CardSection(
                dmc.Group(
                    children=[dmc.Text("Controls", fw=500)],
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
                            id="{{ cookiecutter.__step_name }}-launch-geometry-button",
                            size="xl",
                            disabled=controls["launch_geometry"]["disabled"],
                            loading=controls["launch_geometry"]["loading"],
                        ),
                        label="Launch Geometry",
                        position="top",
                    ),
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:shutdown", width=30),
                            id="{{ cookiecutter.__step_name }}-shutdown-geometry-button",
                            size="xl",
                            disabled=controls["shutdown_geometry"]["disabled"],
                            loading=controls["shutdown_geometry"]["loading"],
                        ),
                        label="Shutdown Geometry",
                        position="top",
                    ),
                ],
                gap="md",
                justify="center",
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
                        dmc.Text("Logs", fw=500),
                        dmc.Tooltip(
                            dmc.ActionIcon(
                                DashIconify(icon="mdi:delete-sweep", width=24),
                                id="{{ cookiecutter.__step_name }}-clear-logs-button",
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
                    "\n".join(step.logs),
                    id="{{ cookiecutter.__step_name }}-console-logs",
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
                "{{ cookiecutter.__step_display_name }}",
                className="display-3",
                style={"font-size": "48px", "fontWeight": "bold"},
            ),
            html.Hr(className="my-2"),
            dmc.Space(h=20),
            dmc.Blockquote(
                "This example demonstrates how to leverage the instance management API to control Geometry.\
                Click the Launch action button to\
                start the instance. A transaction method will start Geometry which can be used across all transaction\
                methods of the solution. Close Geometry using the Shutdown button.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Alert(
                "⚠️ This example requires at least Geometry 2025 R2 Service Pack 4 (25R2 SP4) to run.",
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
                ],
                grow=True,
                gutter="xs",
            ),
        ],
    )


@callback(
    Output("{{ cookiecutter.__step_name }}-event-listeners-container", "children"),
    Input("url", "pathname"),
)
def mount_event_listeners(project: {{ cookiecutter.__solution_definition_class_name }}) -> list:
    """Mount persistent event listeners for {{ cookiecutter.__step_name }}."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    return [
        DashClient.create_event_listener(  # pyright: ignore[reportUnknownMemberType]
            step, id="{{ cookiecutter.__step_name }}-output-listener", stream_name="{{ cookiecutter.__step_name_hyphenated }}-output-stream"
        ),
        DashClient.create_event_listener(  # pyright: ignore[reportUnknownMemberType]
            step, id="{{ cookiecutter.__step_name }}-launch-geometry-listener", stream_name="launch-geometry"
        ),
        DashClient.create_event_listener(  # pyright: ignore[reportUnknownMemberType]
            step, id="{{ cookiecutter.__step_name }}-shutdown-geometry-listener", stream_name="shutdown-geometry"
        ),
    ]


@callback(
    Output("{{ cookiecutter.__step_name }}-launch-geometry-button", "disabled", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-launch-geometry-button", "loading", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-shutdown-geometry-button", "disabled", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-shutdown-geometry-button", "loading", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-launch-geometry-button", "n_clicks"),
    Input("{{ cookiecutter.__step_name }}-shutdown-geometry-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def sync_controls_on_clicks(
    launch_clicks: int,
    shutdown_clicks: int,
    project: {{ cookiecutter.__solution_definition_class_name }},
):
    """Sync the state of the control buttons based on user interactions."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    triggered_id = ctx.triggered_id
    controls = _get_geometry_controls_with_default()

    if triggered_id == "{{ cookiecutter.__step_name }}-launch-geometry-button" and launch_clicks and not step.geometry_available:
        logger.info("Launch button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "launch_geometry":
                controls[button]["loading"] = True
    elif triggered_id == "{{ cookiecutter.__step_name }}-shutdown-geometry-button" and shutdown_clicks and step.geometry_available:
        logger.info("Shutdown button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "shutdown_geometry":
                controls[button]["loading"] = True

    return (
        controls["launch_geometry"]["disabled"],
        controls["launch_geometry"]["loading"],
        controls["shutdown_geometry"]["disabled"],
        controls["shutdown_geometry"]["loading"],
    )


@callback(
    Output("{{ cookiecutter.__step_name }}-launch-geometry-button", "disabled", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-launch-geometry-button", "loading", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-shutdown-geometry-button", "disabled", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-shutdown-geometry-button", "loading", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-launch-geometry-listener", "message"),
    Input("{{ cookiecutter.__step_name }}-shutdown-geometry-listener", "message"),
    prevent_initial_call=True,
)
def sync_controls_on_backend_events(
    launch_message: dict[str, Any],
    shutdown_message: dict[str, Any],
):
    """Sync the state of the control buttons based on websocket messages from the backend."""
    triggered_id = ctx.triggered_id
    controls = _get_geometry_controls_with_default()

    if triggered_id == "{{ cookiecutter.__step_name }}-launch-geometry-listener" and launch_message:
        logger.info("Launch Geometry listener triggered, updating controls")
        method_state = MethodState.model_validate_json(launch_message["data"])
        if method_state.status.value == "completed":
            controls["launch_geometry"]["disabled"] = True
            controls["launch_geometry"]["loading"] = False
            controls["shutdown_geometry"]["disabled"] = False
        else:
            controls["launch_geometry"]["disabled"] = False
            controls["launch_geometry"]["loading"] = False
    elif triggered_id == "{{ cookiecutter.__step_name }}-shutdown-geometry-listener" and shutdown_message:
        logger.info("Shutdown Geometry listener triggered, updating controls")
        method_state = MethodState.model_validate_json(shutdown_message["data"])
        if method_state.status.value == "completed":
            controls["shutdown_geometry"]["disabled"] = True
            controls["shutdown_geometry"]["loading"] = False
            controls["launch_geometry"]["disabled"] = False
            controls["launch_geometry"]["loading"] = False
        else:
            controls["shutdown_geometry"]["disabled"] = False
            controls["shutdown_geometry"]["loading"] = False

    return (
        controls["launch_geometry"]["disabled"],
        controls["launch_geometry"]["loading"],
        controls["shutdown_geometry"]["disabled"],
        controls["shutdown_geometry"]["loading"],
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-launch-geometry-listener", "message"),
    Input("{{ cookiecutter.__step_name }}-shutdown-geometry-listener", "message"),
    prevent_initial_call=True,
)
def sync_notifications_on_backend_events(
    launch_message: dict[str, Any],
    shutdown_message: dict[str, Any],
):
    """Build and return notifications from backend websocket messages about Geometry method state changes."""
    triggered_id = ctx.triggered_id
    notification = no_update

    if triggered_id == "{{ cookiecutter.__step_name }}-launch-geometry-listener" and launch_message:
        logger.info("Launch Geometry listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(launch_message["data"])
        if method_state.status.value == "completed":
            notification = [
                dict(
                    title="Success",
                    id="{{ cookiecutter.__step_name }}-launch-geometry-notification",
                    action="update",
                    message="Geometry instance launched successfully!",
                    color="green",
                    autoClose=5000,
                    withCloseButton=True,
                    loading=False,
                )
            ]
        elif method_state.status.value == "failed":
            notification = [
                dict(
                    title="Error",
                    id="{{ cookiecutter.__step_name }}-launch-geometry-notification",
                    action="update",
                    message="Geometry initialization failed. Please check the logs.",
                    color="red",
                    autoClose=5000,
                    withCloseButton=True,
                    loading=False,
                )
            ]
    elif triggered_id == "{{ cookiecutter.__step_name }}-shutdown-geometry-listener" and shutdown_message:
        logger.info("Shutdown Geometry listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(shutdown_message["data"])
        if method_state.status.value == "completed":
            notification = [
                dict(
                    title="Success",
                    id="{{ cookiecutter.__step_name }}-shutdown-geometry-notification",
                    action="update",
                    message="Geometry instance shutdown successfully!",
                    color="green",
                    autoClose=5000,
                    withCloseButton=True,
                    loading=False,
                )
            ]
        elif method_state.status.value == "failed":
            notification = [
                dict(
                    title="Error",
                    id="{{ cookiecutter.__step_name }}-shutdown-geometry-notification",
                    action="update",
                    message="Failed to shutdown Geometry instance. Please check the logs.",
                    color="red",
                    autoClose=5000,
                    withCloseButton=True,
                    loading=False,
                )
            ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-launch-geometry-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def launch_geometry(n_clicks: int, project: {{ cookiecutter.__solution_definition_class_name }}):
    """Launch an instance of Ansys Geometry."""
    notification = no_update

    if ctx.triggered_id == "{{ cookiecutter.__step_name }}-launch-geometry-button" and n_clicks:
        logger.info("Launch button clicked, starting Geometry instance")
        step = project.steps.{{ cookiecutter.__step_module_name }}
        step.launch_geometry()

        notification = [
            dict(
                title="Info",
                id="{{ cookiecutter.__step_name }}-launch-geometry-notification",
                action="show",
                message="Starting Geometry instance... Please wait.",
                autoClose=False,
                loading=True,
                color="orange",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-shutdown-geometry-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def shutdown_geometry(n_clicks: int, project: {{ cookiecutter.__solution_definition_class_name }}):
    """Shutdown Geometry instance."""
    notification = no_update

    if ctx.triggered_id == "{{ cookiecutter.__step_name }}-shutdown-geometry-button" and n_clicks:
        logger.info("Shutdown button clicked, shutting down Geometry instance")
        step = project.steps.{{ cookiecutter.__step_module_name }}
        step.shutdown_geometry()

        notification = [
            dict(
                title="Info",
                id="{{ cookiecutter.__step_name }}-shutdown-geometry-notification",
                action="show",
                message="Shutting down Geometry instance... Please wait.",
                autoClose=False,
                loading=True,
                color="orange",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("{{ cookiecutter.__step_name }}-console-logs-store", "data", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-output-listener", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def persist_output(message: dict[str, Any], project: {{ cookiecutter.__solution_definition_class_name }}) -> str:
    """Persist geometry output to the store."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    if message:
        new_content = message["data"].strip('"').replace("\\n", "\n")
        step.logs = step.logs + [new_content]
    return "\n".join(step.logs)


@callback(
    Output("{{ cookiecutter.__step_name }}-console-logs", "children", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-console-logs-store", "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def sync_console_logs(logs_data: str, project: {{ cookiecutter.__solution_definition_class_name }}) -> str:
    """Sync the persistent logs store to the visible console and the step logs."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    if logs_data:
        step.logs = logs_data.split("\n")
    return "\n".join(step.logs)


@callback(
    Output("{{ cookiecutter.__step_name }}-console-logs-store", "data", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-console-logs", "children", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-clear-logs-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int, project: {{ cookiecutter.__solution_definition_class_name }}):
    """Clear the console logs and the step logs."""
    if ctx.triggered_id == "{{ cookiecutter.__step_name }}-clear-logs-button" and n_clicks:
        step = project.steps.{{ cookiecutter.__step_module_name }}
        step.logs = []
        return "", ""
    return no_update, no_update
