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

"""Frontend of the AEDT page."""

import logging
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, ctx, html, no_update  # pyright: ignore[reportMissingTypeStubs]
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.helpers import get_aedt_page_controls_with_default, handle_method_event

logger = logging.getLogger(__name__)

dash.register_page(
    __name__,
    name="AEDT Instance Management",
    path_template="/projects/<project_id>/aedt-instance-management",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def initialize_aedt_controls(project: ExamplesSolution) -> dict[str, dict[str, Any]] | Any:
    """Initialize the state of controls on the AEDT instance management page."""
    controls = get_aedt_page_controls_with_default()

    step = project.steps.aedt_step

    for button in controls.keys():
        controls[button]["disabled"] = True
        controls[button]["loading"] = False

    transactions = [
        "launch_aedt",
        "shutdown_aedt",
        "add_rectangle",
        "analyze_design",
    ]

    transaction_states = {t: step.get_long_running_method_state(t).status.value for t in transactions}

    if any(state == "running" for state in transaction_states.values()):
        for button, config in controls.items():
            if transaction_states[config["transaction"]] == "running":
                controls[button]["disabled"] = True
                break
    elif step.instance_created:
        if transaction_states["add_rectangle"] == "completed" or transaction_states["analyze_design"] == "completed":
            controls["add_rectangle"]["disabled"] = False
            controls["analyze_design"]["disabled"] = False
            controls["shutdown_aedt"]["disabled"] = False
        elif transaction_states["launch_aedt"] == "completed":
            controls["add_rectangle"]["disabled"] = False
            controls["shutdown_aedt"]["disabled"] = False
    else:
        logger.info("No AEDT instance detected, initializing page with default state")
        controls["launch_aedt"]["disabled"] = False
    return controls


def layout(project: ExamplesSolution) -> html.Div:
    """Layout of the AEDT step UI."""
    controls = initialize_aedt_controls(project)

    controls_card = dmc.Card(
        [
            dmc.CardSection(
                dmc.Group(
                    children=[dmc.Text("Controls", fw=500, style={"font-size": "17px"})],
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
                            id="launch-aedt-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["launch_aedt"]["disabled"],
                            loading=controls["launch_aedt"]["loading"],
                        ),
                        label="Launch AEDT",
                        position="top",
                    ),
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:shutdown", width=30),
                            id="shutdown-aedt-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["shutdown_aedt"]["disabled"],
                            loading=controls["shutdown_aedt"]["loading"],
                        ),
                        label="Shutdown AEDT",
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
                        "Add Rectangle",
                        id="add-rectangle-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="material-symbols:square-outline"),
                        disabled=controls["add_rectangle"]["disabled"],
                        loading=controls["add_rectangle"]["loading"],
                        style={"width": "70%", "font-size": "15px"},
                    ),
                    dmc.Button(
                        "Analyze Design",
                        id="analyze-design-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="tabler:analyze"),
                        disabled=controls["analyze_design"]["disabled"],
                        loading=controls["analyze_design"]["loading"],
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
                    id="aedt-console-logs",
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
                "AEDT Instance Manager",
                className="display-3",
                style={"font-size": "40px", "font-weight": "bold"},
            ),
            dmc.Blockquote(
                "This example demonstrates how to leverage the instance management API to control AEDT.\
                Click the Launch button to\
                start the instance. A transaction method will start AEDT which can be used across all transaction\
                methods. Run AEDT operations with the Add Rectangle and\
                Analyze Design buttons. Close AEDT using the Shutdown button.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Alert(
                dmc.Text(
                    [
                        "⚠️ This example requires the following prerequisites:\n",
                        "- ",
                        dmc.Mark("AEDT 2025 R1 (25R1)"),
                        " installed and licensed,\n",
                        "- ",
                        dmc.Mark("ansys-saf-pim-light-server package 0.3 or later"),
                        " installed in the Python environment or ",
                        dmc.Mark("optiSLang 2025 R2 or later"),
                        " installed and licensed,\n",
                    ],
                    style={"whiteSpace": "pre-line"},
                    size="md",
                ),
                title="Prerequisites",
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
            html.Br(),
            html.Br(),
        ],
        style={"paddingLeft": "20px"},
    )


@callback(
    Output("aedt-instance-event-listeners-container", "children"),
    Input("project-layout-generation", "data"),
    State("project-scoped-pathname", "data"),
    prevent_initial_call=True,
)
def mount_event_listeners(_generation: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Mount AEDT instance event listeners in the persistent main layout."""
    logger.info("Mounting AEDT instance management event listeners")
    step = project.steps.aedt_step
    return [
        DashClient.create_event_listener(step, id="aedt-output-listener", stream_name="aedt-output-stream"),
        DashClient.create_event_listener(step, id="launch-aedt-listener", stream_name="launch-aedt"),
        DashClient.create_event_listener(step, id="shutdown-aedt-listener", stream_name="shutdown-aedt"),
        DashClient.create_event_listener(step, id="add-rectangle-listener", stream_name="add-rectangle"),
        DashClient.create_event_listener(step, id="analyze-design-listener", stream_name="analyze-design"),
    ]


@callback(
    Output("launch-aedt-button", "disabled", allow_duplicate=True),
    Output("launch-aedt-button", "loading", allow_duplicate=True),
    Output("shutdown-aedt-button", "disabled", allow_duplicate=True),
    Output("shutdown-aedt-button", "loading", allow_duplicate=True),
    Output("add-rectangle-button", "disabled", allow_duplicate=True),
    Output("add-rectangle-button", "loading", allow_duplicate=True),
    Output("analyze-design-button", "disabled", allow_duplicate=True),
    Output("analyze-design-button", "loading", allow_duplicate=True),
    Input("launch-aedt-button", "n_clicks"),
    Input("shutdown-aedt-button", "n_clicks"),
    Input("add-rectangle-button", "n_clicks"),
    Input("analyze-design-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def sync_controls_on_clicks(
    launch_aedt_clicks: int,
    shutdown_aedt_clicks: int,
    add_rectangle_clicks: int,
    analyze_design_clicks: int,
    project: ExamplesSolution,
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on user interactions."""
    step = project.steps.aedt_step
    triggered_id = ctx.triggered_id
    controls = get_aedt_page_controls_with_default()

    if triggered_id == "launch-aedt-button" and launch_aedt_clicks and not step.instance_created:
        logger.info("Launch button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "launch_aedt":
                controls[button]["loading"] = True
    elif triggered_id == "shutdown-aedt-button" and shutdown_aedt_clicks and step.instance_created:
        logger.info("Shutdown button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "shutdown_aedt":
                controls[button]["loading"] = True
    elif triggered_id == "add-rectangle-button" and add_rectangle_clicks and step.instance_created:
        logger.info("Add Rectangle button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "add_rectangle":
                controls[button]["loading"] = True
    elif triggered_id == "analyze-design-button" and analyze_design_clicks and step.instance_created:
        logger.info("Analyze Design button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "analyze_design":
                controls[button]["loading"] = True

    return (
        controls["launch_aedt"]["disabled"],
        controls["launch_aedt"]["loading"],
        controls["shutdown_aedt"]["disabled"],
        controls["shutdown_aedt"]["loading"],
        controls["add_rectangle"]["disabled"],
        controls["add_rectangle"]["loading"],
        controls["analyze_design"]["disabled"],
        controls["analyze_design"]["loading"],
    )


@callback(
    Output("launch-aedt-button", "disabled", allow_duplicate=True),
    Output("launch-aedt-button", "loading", allow_duplicate=True),
    Output("shutdown-aedt-button", "disabled", allow_duplicate=True),
    Output("shutdown-aedt-button", "loading", allow_duplicate=True),
    Output("add-rectangle-button", "disabled", allow_duplicate=True),
    Output("add-rectangle-button", "loading", allow_duplicate=True),
    Output("analyze-design-button", "disabled", allow_duplicate=True),
    Output("analyze-design-button", "loading", allow_duplicate=True),
    Input("launch-aedt-listener", "message"),
    Input("shutdown-aedt-listener", "message"),
    Input("add-rectangle-listener", "message"),
    Input("analyze-design-listener", "message"),
    prevent_initial_call=True,
)
def sync_controls_on_backend_events(
    launch_aedt_message: dict[str, Any],
    shutdown_aedt_message: dict[str, Any],
    add_rectangle_message: dict[str, Any],
    analyze_design_message: dict[str, Any],
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on websocket messages from the backend indicating
    AEDT instance state changes."""
    triggered_id = ctx.triggered_id
    controls = get_aedt_page_controls_with_default()

    if triggered_id == "launch-aedt-listener" and launch_aedt_message:
        logger.info("Launch AEDT listener triggered, updating controls")
        method_state = MethodState.model_validate_json(launch_aedt_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button == "launch_aedt":
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button in ["shutdown_aedt", "add_rectangle"]:
                    controls[button]["disabled"] = False
        else:
            controls["launch_aedt"]["disabled"] = False
            controls["launch_aedt"]["loading"] = False
    elif triggered_id == "shutdown-aedt-listener" and shutdown_aedt_message:
        logger.info("Shutdown AEDT listener triggered, updating controls")
        method_state = MethodState.model_validate_json(shutdown_aedt_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button in ["shutdown_aedt", "add_rectangle", "analyze_design"]:
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button == "launch_aedt":
                    controls[button]["disabled"] = False
                    controls[button]["loading"] = False
        else:
            controls["shutdown_aedt"]["disabled"] = False
            controls["shutdown_aedt"]["loading"] = False
    elif triggered_id == "add-rectangle-listener" and add_rectangle_message:
        logger.info("Add Rectangle listener triggered, updating controls")
        method_state = MethodState.model_validate_json(add_rectangle_message["data"])
        if method_state.status.value == "completed":
            controls["add_rectangle"]["disabled"] = False
            controls["add_rectangle"]["loading"] = False
            controls["analyze_design"]["disabled"] = False
        else:
            controls["add_rectangle"]["disabled"] = False
            controls["add_rectangle"]["loading"] = False
        controls["shutdown_aedt"]["disabled"] = False
    elif triggered_id == "analyze-design-listener" and analyze_design_message:
        logger.info("Analyze Design listener triggered, updating controls")
        controls["analyze_design"]["disabled"] = False
        controls["analyze_design"]["loading"] = False
        controls["shutdown_aedt"]["disabled"] = False
        controls["add_rectangle"]["disabled"] = False

    return (
        controls["launch_aedt"]["disabled"],
        controls["launch_aedt"]["loading"],
        controls["shutdown_aedt"]["disabled"],
        controls["shutdown_aedt"]["loading"],
        controls["add_rectangle"]["disabled"],
        controls["add_rectangle"]["loading"],
        controls["analyze_design"]["disabled"],
        controls["analyze_design"]["loading"],
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-aedt-listener", "message"),
    Input("shutdown-aedt-listener", "message"),
    Input("add-rectangle-listener", "message"),
    Input("analyze-design-listener", "message"),
    prevent_initial_call=True,
)
def sync_notifications_on_backend_events(
    launch_aedt_message: dict[str, Any],
    shutdown_aedt_message: dict[str, Any],
    add_rectangle_message: dict[str, Any],
    analyze_design_message: dict[str, Any],
) -> list[dict[str, Any]] | Any:
    """Build and return notifications from backend websocket messages about AEDT method state changes."""
    triggered_id = ctx.triggered_id
    notification = no_update

    if triggered_id == "launch-aedt-listener" and launch_aedt_message:
        logger.info("Launch AEDT listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(launch_aedt_message["data"])
        notification = handle_method_event(
            method_state,
            "launch-aedt-notification",
            "AEDT instance launched successfully!",
            "AEDT initialization failed. Please check the logs.",
        )
    elif triggered_id == "shutdown-aedt-listener" and shutdown_aedt_message:
        logger.info("Shutdown AEDT listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(shutdown_aedt_message["data"])
        notification = handle_method_event(
            method_state,
            "shutdown-aedt-notification",
            "AEDT instance shutdown successfully!",
            "Failed to shutdown AEDT instance. Please check the logs.",
        )
    elif triggered_id == "add-rectangle-listener" and add_rectangle_message:
        logger.info("Add Rectangle listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(add_rectangle_message["data"])
        notification = handle_method_event(
            method_state,
            "add-rectangle-notification",
            "Rectangle added successfully!",
            "Failed to add rectangle. Please check the logs.",
        )
    elif triggered_id == "analyze-design-listener" and analyze_design_message:
        logger.info("Analyze Design listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(analyze_design_message["data"])
        notification = handle_method_event(
            method_state,
            "analyze-design-notification",
            "Design analyzed successfully!",
            "Design analysis failed. Please check the logs.",
        )

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-aedt-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def launch_aedt(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Launch an instance of Ansys AEDT."""
    notification = no_update

    if ctx.triggered_id == "launch-aedt-button" and n_clicks:
        logger.info("Launch button clicked, starting AEDT instance")
        step = project.steps.aedt_step
        step.launch_aedt()

        notification = [
            dict(
                title="Info",
                id="launch-aedt-notification",
                action="show",
                message="Starting AEDT instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("add-rectangle-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def add_rectangle(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Add a rectangle in the AEDT instance."""
    notification = no_update

    if ctx.triggered_id == "add-rectangle-button" and n_clicks:
        logger.info("Add Rectangle button clicked")
        step = project.steps.aedt_step
        step.add_rectangle()

        notification = [
            dict(
                title="Info",
                id="add-rectangle-notification",
                action="show",
                message="Adding rectangle... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("analyze-design-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def analyze_design(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Analyze the design in the AEDT instance."""
    notification = no_update

    if ctx.triggered_id == "analyze-design-button" and n_clicks:
        logger.info("Analyze Design button clicked")
        step = project.steps.aedt_step
        step.analyze_design()

        notification = [
            dict(
                title="Info",
                id="analyze-design-notification",
                action="show",
                message="Analyzing design... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("shutdown-aedt-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def shutdown_aedt(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Shutdown AEDT instance."""
    notification = no_update

    if ctx.triggered_id == "shutdown-aedt-button" and n_clicks:
        logger.info("Shutdown button clicked, shutting down AEDT instance")
        step = project.steps.aedt_step
        step.shutdown_aedt()

        notification = [
            dict(
                title="Info",
                id="shutdown-aedt-notification",
                action="show",
                message="Shutting down AEDT instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("aedt-logs-store", "data", allow_duplicate=True),
    Input("aedt-output-listener", "message"),
    State("aedt-logs-store", "data"),
    prevent_initial_call=True,
)
def store_outputs(message: dict[str, Any], current_logs: str) -> str:
    """Store AEDT output."""
    if message:
        new_content = message["data"].strip('"').replace("\\n", "\n")
        combined = (current_logs or "") + "\n" + new_content
        return combined
    return current_logs


@callback(
    Output("aedt-console-logs", "children", allow_duplicate=True),
    Input("aedt-logs-store", "data"),
)
def display_output(current_logs: str) -> str:
    """Display AEDT output."""
    return current_logs


@callback(
    Output("aedt-console-logs", "children"),
    Input("clear-logs-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int) -> str:
    """Clear the console logs."""
    return ""
