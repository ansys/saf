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

"""Frontend of the optiSLang page."""

import logging
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, ctx, html, no_update  # pyright: ignore[reportMissingTypeStubs]
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.helpers import get_optislang_page_controls_with_default, handle_method_event

logger = logging.getLogger(__name__)

dash.register_page(
    __name__,
    name="optiSLang Instance Management",
    path_template="/projects/<project_id>/optislang-instance-management",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def initialize_optislang_controls(project: ExamplesSolution) -> dict[str, dict[str, Any]] | Any:
    """Initialize the state of controls on the optiSLang instance management page."""
    controls = get_optislang_page_controls_with_default()

    for button in controls.keys():
        controls[button]["disabled"] = True
        controls[button]["loading"] = False

    transactions = [
        "launch_optislang",
        "shutdown_optislang",
        "evaluate_design",
        "refine_design",
    ]

    step = project.steps.optislang_step
    transaction_states = {t: step.get_long_running_method_state(t).status.value for t in transactions}

    if any(state == "running" for state in transaction_states.values()):
        for button, config in controls.items():
            if transaction_states[config["transaction"]] == "running":
                controls[button]["disabled"] = True
                break
    elif step.instance_created:
        if transaction_states["evaluate_design"] == "completed" or transaction_states["refine_design"] == "completed":
            controls["evaluate_design"]["disabled"] = False
            controls["refine_design"]["disabled"] = False
            controls["shutdown_optislang"]["disabled"] = False
        elif transaction_states["launch_optislang"] == "completed":
            controls["evaluate_design"]["disabled"] = False
            controls["shutdown_optislang"]["disabled"] = False
    else:
        logger.info("No optiSLang instance detected, initializing page with default state")
        controls["launch_optislang"]["disabled"] = False
    return controls


def layout(project: ExamplesSolution) -> html.Div:
    """Layout of the optiSLang step UI."""
    controls = initialize_optislang_controls(project)

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
                            id="launch-optislang-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["launch_optislang"]["disabled"],
                            loading=controls["launch_optislang"]["loading"],
                        ),
                        label="Launch optiSLang",
                        position="top",
                    ),
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:shutdown", width=30),
                            id="shutdown-optislang-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["shutdown_optislang"]["disabled"],
                            loading=controls["shutdown_optislang"]["loading"],
                        ),
                        label="Shutdown optiSLang",
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
                        "Evaluate Design",
                        id="evaluate-design-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="hugeicons:chart-evaluation"),
                        disabled=controls["evaluate_design"]["disabled"],
                        loading=controls["evaluate_design"]["loading"],
                        style={"width": "70%", "font-size": "15px"},
                    ),
                    dmc.Button(
                        "Refine Design",
                        id="refine-design-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="material-symbols:filter-alt"),
                        disabled=controls["refine_design"]["disabled"],
                        loading=controls["refine_design"]["loading"],
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
                    id="optislang-console-logs",
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
                "optiSLang Instance Manager",
                className="display-3",
                style={"font-size": "40px", "font-weight": "bold"},
            ),
            dmc.Blockquote(
                "This example demonstrates how to leverage the instance management API to control Ansys optiSLang.\
                Click the Launch button to\
                start the instance. A transaction method will start optiSLang which can be used across all transaction\
                methods. Run optiSLang operations with the Evaluate Design and\
                Refine Design buttons. Close optiSLang using the Shutdown button.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Alert(
                dmc.Text(
                    [
                        "⚠️ This example requires the following prerequisites:\n",
                        "- ",
                        dmc.Mark("Ansys optiSLang 2024 R2"),
                        " installed and licensed,\n",
                        "- ",
                        dmc.Mark("ansys-saf-pim-light-server package 0.3 or later"),
                        " installed in the Python environment",
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
    Output("optislang-instance-event-listeners-container", "children"),
    Input("project-layout-generation", "data"),
    State("project-scoped-pathname", "data"),
    prevent_initial_call=True,
)
def mount_event_listeners(_generation: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Mount optiSLang instance event listeners in the persistent main layout."""
    logger.info("Mounting optiSLang instance management event listeners")
    step = project.steps.optislang_step
    return [
        DashClient.create_event_listener(step, id="optislang-output-listener", stream_name="optislang-output-stream"),
        DashClient.create_event_listener(step, id="launch-optislang-listener", stream_name="launch-optislang"),
        DashClient.create_event_listener(step, id="shutdown-optislang-listener", stream_name="shutdown-optislang"),
        DashClient.create_event_listener(step, id="evaluate-design-listener", stream_name="evaluate-design"),
        DashClient.create_event_listener(step, id="refine-design-listener", stream_name="refine-design"),
    ]


@callback(
    Output("launch-optislang-button", "disabled", allow_duplicate=True),
    Output("launch-optislang-button", "loading", allow_duplicate=True),
    Output("shutdown-optislang-button", "disabled", allow_duplicate=True),
    Output("shutdown-optislang-button", "loading", allow_duplicate=True),
    Output("evaluate-design-button", "disabled", allow_duplicate=True),
    Output("evaluate-design-button", "loading", allow_duplicate=True),
    Output("refine-design-button", "disabled", allow_duplicate=True),
    Output("refine-design-button", "loading", allow_duplicate=True),
    Input("launch-optislang-button", "n_clicks"),
    Input("shutdown-optislang-button", "n_clicks"),
    Input("evaluate-design-button", "n_clicks"),
    Input("refine-design-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def sync_controls_on_clicks(
    launch_optislang_clicks: int,
    shutdown_optislang_clicks: int,
    evaluate_design_clicks: int,
    refine_design_clicks: int,
    project: ExamplesSolution,
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on user interactions."""
    step = project.steps.optislang_step
    triggered_id = ctx.triggered_id
    controls = get_optislang_page_controls_with_default()

    if triggered_id == "launch-optislang-button" and launch_optislang_clicks and not step.instance_created:
        logger.info("Launch button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "launch_optislang":
                controls[button]["loading"] = True
    elif triggered_id == "shutdown-optislang-button" and shutdown_optislang_clicks and step.instance_created:
        logger.info("Shutdown button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "shutdown_optislang":
                controls[button]["loading"] = True
    elif triggered_id == "evaluate-design-button" and evaluate_design_clicks and step.instance_created:
        logger.info("Evaluate Design button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "evaluate_design":
                controls[button]["loading"] = True
    elif triggered_id == "refine-design-button" and refine_design_clicks and step.instance_created:
        logger.info("Refine Design button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "refine_design":
                controls[button]["loading"] = True

    return (
        controls["launch_optislang"]["disabled"],
        controls["launch_optislang"]["loading"],
        controls["shutdown_optislang"]["disabled"],
        controls["shutdown_optislang"]["loading"],
        controls["evaluate_design"]["disabled"],
        controls["evaluate_design"]["loading"],
        controls["refine_design"]["disabled"],
        controls["refine_design"]["loading"],
    )


@callback(
    Output("launch-optislang-button", "disabled", allow_duplicate=True),
    Output("launch-optislang-button", "loading", allow_duplicate=True),
    Output("shutdown-optislang-button", "disabled", allow_duplicate=True),
    Output("shutdown-optislang-button", "loading", allow_duplicate=True),
    Output("evaluate-design-button", "disabled", allow_duplicate=True),
    Output("evaluate-design-button", "loading", allow_duplicate=True),
    Output("refine-design-button", "disabled", allow_duplicate=True),
    Output("refine-design-button", "loading", allow_duplicate=True),
    Input("launch-optislang-listener", "message"),
    Input("shutdown-optislang-listener", "message"),
    Input("evaluate-design-listener", "message"),
    Input("refine-design-listener", "message"),
    prevent_initial_call=True,
)
def sync_controls_on_backend_events(
    launch_optislang_message: dict[str, Any],
    shutdown_optislang_message: dict[str, Any],
    evaluate_design_message: dict[str, Any],
    refine_design_message: dict[str, Any],
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on websocket messages from the backend indicating
    optiSLang instance state changes."""
    triggered_id = ctx.triggered_id
    controls = get_optislang_page_controls_with_default()

    if triggered_id == "launch-optislang-listener" and launch_optislang_message:
        logger.info("Launch optiSLang listener triggered, updating controls")
        method_state = MethodState.model_validate_json(launch_optislang_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button == "launch_optislang":
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button in ["shutdown_optislang", "evaluate_design"]:
                    controls[button]["disabled"] = False
        else:
            controls["launch_optislang"]["disabled"] = False
            controls["launch_optislang"]["loading"] = False
    elif triggered_id == "shutdown-optislang-listener" and shutdown_optislang_message:
        logger.info("Shutdown optiSLang listener triggered, updating controls")
        method_state = MethodState.model_validate_json(shutdown_optislang_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button in ["shutdown_optislang", "evaluate_design", "refine_design"]:
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button == "launch_optislang":
                    controls[button]["disabled"] = False
                    controls[button]["loading"] = False
        else:
            controls["shutdown_optislang"]["disabled"] = False
            controls["shutdown_optislang"]["loading"] = False
    elif triggered_id == "evaluate-design-listener" and evaluate_design_message:
        logger.info("Evaluate Design listener triggered, updating controls")
        method_state = MethodState.model_validate_json(evaluate_design_message["data"])
        if method_state.status.value == "completed":
            controls["evaluate_design"]["disabled"] = False
            controls["evaluate_design"]["loading"] = False
            controls["refine_design"]["disabled"] = False
        else:
            controls["evaluate_design"]["disabled"] = False
            controls["evaluate_design"]["loading"] = False
        controls["shutdown_optislang"]["disabled"] = False
    elif triggered_id == "refine-design-listener" and refine_design_message:
        logger.info("Refine Design listener triggered, updating controls")
        controls["refine_design"]["disabled"] = False
        controls["refine_design"]["loading"] = False
        controls["shutdown_optislang"]["disabled"] = False
        controls["evaluate_design"]["disabled"] = False

    return (
        controls["launch_optislang"]["disabled"],
        controls["launch_optislang"]["loading"],
        controls["shutdown_optislang"]["disabled"],
        controls["shutdown_optislang"]["loading"],
        controls["evaluate_design"]["disabled"],
        controls["evaluate_design"]["loading"],
        controls["refine_design"]["disabled"],
        controls["refine_design"]["loading"],
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-optislang-listener", "message"),
    Input("shutdown-optislang-listener", "message"),
    Input("evaluate-design-listener", "message"),
    Input("refine-design-listener", "message"),
    prevent_initial_call=True,
)
def sync_notifications_on_backend_events(
    launch_optislang_message: dict[str, Any],
    shutdown_optislang_message: dict[str, Any],
    evaluate_design_message: dict[str, Any],
    refine_design_message: dict[str, Any],
) -> list[dict[str, Any]] | Any:
    """Build and return notifications from backend websocket messages about optiSLang method state changes."""
    triggered_id = ctx.triggered_id
    notification = no_update

    if triggered_id == "launch-optislang-listener" and launch_optislang_message:
        logger.info("Launch optiSLang listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(launch_optislang_message["data"])
        notification = handle_method_event(
            method_state,
            "launch-optislang-notification",
            "optiSLang instance launched successfully!",
            "optiSLang initialization failed. Please check the logs.",
        )
    elif triggered_id == "shutdown-optislang-listener" and shutdown_optislang_message:
        logger.info("Shutdown optiSLang listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(shutdown_optislang_message["data"])
        notification = handle_method_event(
            method_state,
            "shutdown-optislang-notification",
            "optiSLang instance shutdown successfully!",
            "Failed to shutdown optiSLang instance. Please check the logs.",
        )
    elif triggered_id == "evaluate-design-listener" and evaluate_design_message:
        logger.info("Evaluate Design listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(evaluate_design_message["data"])
        notification = handle_method_event(
            method_state,
            "evaluate-design-notification",
            "Design evaluated successfully!",
            "Design evaluation failed. Please check the logs.",
        )
    elif triggered_id == "refine-design-listener" and refine_design_message:
        logger.info("Refine design listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(refine_design_message["data"])
        notification = handle_method_event(
            method_state,
            "refine-design-notification",
            "Design refined successfully!",
            "Design refinement failed. Please check the logs.",
        )

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-optislang-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def launch_optislang(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Launch an instance of Ansys optiSLang."""
    notification = no_update

    if ctx.triggered_id == "launch-optislang-button" and n_clicks:
        logger.info("Launch button clicked, starting optiSLang instance")
        step = project.steps.optislang_step
        step.download_example_file()
        step.launch_optislang()

        notification = [
            dict(
                title="Info",
                id="launch-optislang-notification",
                action="show",
                message="Starting optiSLang instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("evaluate-design-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def evaluate_design(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Evaluate the design in the optiSLang instance."""
    notification = no_update

    if ctx.triggered_id == "evaluate-design-button" and n_clicks:
        logger.info("Evaluate Design button clicked")
        step = project.steps.optislang_step
        step.evaluate_design()

        notification = [
            dict(
                title="Info",
                id="evaluate-design-notification",
                action="show",
                message="Evaluating design... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("refine-design-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def refine_design(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Refine the design in the optiSLang instance."""
    notification = no_update

    if ctx.triggered_id == "refine-design-button" and n_clicks:
        logger.info("Refine Design button clicked")
        step = project.steps.optislang_step
        step.refine_design()

        notification = [
            dict(
                title="Info",
                id="refine-design-notification",
                action="show",
                message="Refining design... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("shutdown-optislang-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def shutdown_optislang(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Shutdown optiSLang instance."""
    notification = no_update

    if ctx.triggered_id == "shutdown-optislang-button" and n_clicks:
        logger.info("Shutdown button clicked, shutting down optiSLang instance")
        step = project.steps.optislang_step
        step.shutdown_optislang()

        notification = [
            dict(
                title="Info",
                id="shutdown-optislang-notification",
                action="show",
                message="Shutting down optiSLang instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("optislang-logs-store", "data", allow_duplicate=True),
    Input("optislang-output-listener", "message"),
    State("optislang-logs-store", "data"),
    prevent_initial_call=True,
)
def store_outputs(message: dict[str, Any], current_logs: str) -> str:
    """Store optiSLang output."""
    if message:
        new_content = message["data"].strip('"').replace("\\n", "\n")
        combined = (current_logs or "") + "\n" + new_content
        return combined
    return current_logs


@callback(
    Output("optislang-console-logs", "children", allow_duplicate=True),
    Input("optislang-logs-store", "data"),
)
def display_output(current_logs: str) -> str:
    """Display optiSLang output."""
    return current_logs


@callback(
    Output("optislang-console-logs", "children"),
    Input("clear-logs-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int) -> str:
    """Clear the console logs."""
    return ""
