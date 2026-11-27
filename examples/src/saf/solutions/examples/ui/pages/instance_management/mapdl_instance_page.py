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

"""Frontend of the MAPDL page."""

import logging
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, ctx, html, no_update  # pyright: ignore[reportMissingTypeStubs]
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.helpers import get_mapdl_page_controls_with_default, handle_method_event

logger = logging.getLogger(__name__)

dash.register_page(
    __name__,
    name="MAPDL Instance Management",
    path_template="/projects/<project_id>/mapdl-instance-management",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def initialize_mapdl_controls(project: ExamplesSolution) -> dict[str, dict[str, Any]] | Any:
    """Initialize the state of controls on the MAPDL instance management page."""
    controls = get_mapdl_page_controls_with_default()

    for button in controls.keys():
        controls[button]["disabled"] = True
        controls[button]["loading"] = False

    transactions = [
        "launch_mapdl",
        "shutdown_mapdl",
        "solve_model",
        "postprocessing",
    ]

    step = project.steps.mapdl_step
    transaction_states = {t: step.get_long_running_method_state(t).status.value for t in transactions}

    if any(state == "running" for state in transaction_states.values()):
        for button, config in controls.items():
            if transaction_states[config["transaction"]] == "running":
                controls[button]["disabled"] = True
                break
    elif step.instance_created:
        if transaction_states["solve_model"] == "completed" or transaction_states["postprocessing"] == "completed":
            controls["solve_model"]["disabled"] = False
            controls["postprocess_results"]["disabled"] = False
            controls["shutdown_mapdl"]["disabled"] = False
        elif transaction_states["launch_mapdl"] == "completed":
            controls["solve_model"]["disabled"] = False
            controls["shutdown_mapdl"]["disabled"] = False
    else:
        logger.info("No MAPDL instance detected, initializing page with default state")
        controls["launch_mapdl"]["disabled"] = False

    return controls


def layout(project: ExamplesSolution) -> html.Div:
    """Layout for the MAPDL Instance Manager page."""
    controls = initialize_mapdl_controls(project)

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
                            id="launch-mapdl-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["launch_mapdl"]["disabled"],
                            loading=controls["launch_mapdl"]["loading"],
                        ),
                        label="Launch MAPDL",
                        position="top",
                    ),
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:shutdown", width=30),
                            id="shutdown-mapdl-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["shutdown_mapdl"]["disabled"],
                            loading=controls["shutdown_mapdl"]["loading"],
                        ),
                        label="Shutdown MAPDL",
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
                        "Solve Model",
                        id="solve-model-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="carbon:result"),
                        disabled=controls["solve_model"]["disabled"],
                        loading=controls["solve_model"]["loading"],
                        style={"width": "70%", "font-size": "15px"},
                    ),
                    dmc.Button(
                        "Postprocess Results",
                        id="postprocess-results-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="uil:process"),
                        disabled=controls["postprocess_results"]["disabled"],
                        loading=controls["postprocess_results"]["loading"],
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
                    id="mapdl-console-logs",
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
                "MAPDL Instance Manager",
                className="display-3",
                style={"font-size": "40px", "font-weight": "bold"},
            ),
            dmc.Blockquote(
                "This example demonstrates how to leverage the instance management API to control MAPDL.\
                Click the Launch button to\
                start the instance. A transaction method will start MAPDL which can be used across all transaction\
                methods. Run MAPDL operations with the Solve Model and\
                Postprocess Results buttons. Close MAPDL using the Shutdown button.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Alert(
                dmc.Text(
                    [
                        "⚠️ This example requires the following prerequisites:\n",
                        "- ",
                        dmc.Mark("Ansys MAPDL 2025 R2 Service Pack 4 (25R2 SP4) or later"),
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
    Output("mapdl-instance-event-listeners-container", "children"),
    Input("project-layout-generation", "data"),
    State("project-scoped-pathname", "data"),
    prevent_initial_call=True,
)
def mount_event_listeners(_generation: int, project: ExamplesSolution) -> list:
    """Mount MAPDL instance event listeners in the persistent main layout."""
    logger.info("Mounting MAPDL instance management event listeners")
    step = project.steps.mapdl_step
    return [
        DashClient.create_event_listener(step, id="mapdl-output-listener", stream_name="mapdl-output-stream"),
        DashClient.create_event_listener(step, id="launch-mapdl-listener", stream_name="launch-mapdl"),
        DashClient.create_event_listener(step, id="solve-model-listener", stream_name="solve-model"),
        DashClient.create_event_listener(step, id="postprocess-results-listener", stream_name="postprocessing"),
        DashClient.create_event_listener(step, id="shutdown-mapdl-listener", stream_name="shutdown-mapdl"),
    ]


@callback(
    Output("launch-mapdl-button", "disabled", allow_duplicate=True),
    Output("launch-mapdl-button", "loading", allow_duplicate=True),
    Output("shutdown-mapdl-button", "disabled", allow_duplicate=True),
    Output("shutdown-mapdl-button", "loading", allow_duplicate=True),
    Output("solve-model-button", "disabled", allow_duplicate=True),
    Output("solve-model-button", "loading", allow_duplicate=True),
    Output("postprocess-results-button", "disabled", allow_duplicate=True),
    Output("postprocess-results-button", "loading", allow_duplicate=True),
    Input("launch-mapdl-button", "n_clicks"),
    Input("shutdown-mapdl-button", "n_clicks"),
    Input("solve-model-button", "n_clicks"),
    Input("postprocess-results-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def sync_controls_on_clicks(
    launch_mapdl_clicks: int,
    shutdown_mapdl_clicks: int,
    solve_model_clicks: int,
    postprocess_results_clicks: int,
    project: ExamplesSolution,
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on user interactions."""
    step = project.steps.mapdl_step
    triggered_id = ctx.triggered_id
    controls = get_mapdl_page_controls_with_default()

    if triggered_id == "launch-mapdl-button" and launch_mapdl_clicks and not step.instance_created:
        logger.info("Launch button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "launch_mapdl":
                controls[button]["loading"] = True
    elif triggered_id == "shutdown-mapdl-button" and shutdown_mapdl_clicks and step.instance_created:
        logger.info("Shutdown button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "shutdown_mapdl":
                controls[button]["loading"] = True
    elif triggered_id == "solve-model-button" and solve_model_clicks and step.instance_created:
        logger.info("Solve Model button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "solve_model":
                controls[button]["loading"] = True
    elif triggered_id == "postprocess-results-button" and postprocess_results_clicks and step.instance_created:
        logger.info("Postprocess Results button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "postprocess_results":
                controls[button]["loading"] = True

    return (
        controls["launch_mapdl"]["disabled"],
        controls["launch_mapdl"]["loading"],
        controls["shutdown_mapdl"]["disabled"],
        controls["shutdown_mapdl"]["loading"],
        controls["solve_model"]["disabled"],
        controls["solve_model"]["loading"],
        controls["postprocess_results"]["disabled"],
        controls["postprocess_results"]["loading"],
    )


@callback(
    Output("launch-mapdl-button", "disabled", allow_duplicate=True),
    Output("launch-mapdl-button", "loading", allow_duplicate=True),
    Output("shutdown-mapdl-button", "disabled", allow_duplicate=True),
    Output("shutdown-mapdl-button", "loading", allow_duplicate=True),
    Output("solve-model-button", "disabled", allow_duplicate=True),
    Output("solve-model-button", "loading", allow_duplicate=True),
    Output("postprocess-results-button", "disabled", allow_duplicate=True),
    Output("postprocess-results-button", "loading", allow_duplicate=True),
    Input("launch-mapdl-listener", "message"),
    Input("shutdown-mapdl-listener", "message"),
    Input("solve-model-listener", "message"),
    Input("postprocess-results-listener", "message"),
    prevent_initial_call=True,
)
def sync_controls_on_backend_events(
    launch_mapdl_message: dict[str, Any],
    shutdown_mapdl_message: dict[str, Any],
    solve_model_message: dict[str, Any],
    postprocess_results_message: dict[str, Any],
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on websocket messages from the backend indicating
    MAPDL instance state changes."""
    triggered_id = ctx.triggered_id
    controls = get_mapdl_page_controls_with_default()

    if triggered_id == "launch-mapdl-listener" and launch_mapdl_message:
        logger.info("Launch MAPDL listener triggered, updating controls")
        method_state = MethodState.model_validate_json(launch_mapdl_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button == "launch_mapdl":
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button in ["shutdown_mapdl", "solve_model"]:
                    controls[button]["disabled"] = False
        else:
            controls["launch_mapdl"]["disabled"] = False
            controls["launch_mapdl"]["loading"] = False
    elif triggered_id == "shutdown-mapdl-listener" and shutdown_mapdl_message:
        logger.info("Shutdown MAPDL listener triggered, updating controls")
        method_state = MethodState.model_validate_json(shutdown_mapdl_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button in ["shutdown_mapdl", "solve_model", "postprocess_results"]:
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button == "launch_mapdl":
                    controls[button]["disabled"] = False
                    controls[button]["loading"] = False
        else:
            controls["shutdown_mapdl"]["disabled"] = False
            controls["shutdown_mapdl"]["loading"] = False
    elif triggered_id == "solve-model-listener" and solve_model_message:
        logger.info("Solve Model listener triggered, updating controls")
        method_state = MethodState.model_validate_json(solve_model_message["data"])
        if method_state.status.value == "completed":
            controls["solve_model"]["disabled"] = False
            controls["solve_model"]["loading"] = False
            controls["postprocess_results"]["disabled"] = False
        else:
            controls["solve_model"]["disabled"] = False
            controls["solve_model"]["loading"] = False
        controls["shutdown_mapdl"]["disabled"] = False
    elif triggered_id == "postprocess-results-listener" and postprocess_results_message:
        logger.info("Postprocess Results listener triggered, updating controls")
        controls["postprocess_results"]["disabled"] = False
        controls["postprocess_results"]["loading"] = False
        controls["shutdown_mapdl"]["disabled"] = False
        controls["solve_model"]["disabled"] = False

    return (
        controls["launch_mapdl"]["disabled"],
        controls["launch_mapdl"]["loading"],
        controls["shutdown_mapdl"]["disabled"],
        controls["shutdown_mapdl"]["loading"],
        controls["solve_model"]["disabled"],
        controls["solve_model"]["loading"],
        controls["postprocess_results"]["disabled"],
        controls["postprocess_results"]["loading"],
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-mapdl-listener", "message"),
    Input("shutdown-mapdl-listener", "message"),
    Input("solve-model-listener", "message"),
    Input("postprocess-results-listener", "message"),
    prevent_initial_call=True,
)
def sync_notifications_on_backend_events(
    launch_mapdl_message: dict[str, Any],
    shutdown_mapdl_message: dict[str, Any],
    solve_model_message: dict[str, Any],
    postprocess_results_message: dict[str, Any],
) -> list[dict[str, Any]] | str:
    """Build and return notifications from backend websocket messages about MAPDL method state changes."""
    triggered_id = ctx.triggered_id
    notification = no_update

    if triggered_id == "launch-mapdl-listener" and launch_mapdl_message:
        logger.info("Launch MAPDL listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(launch_mapdl_message["data"])
        notification = handle_method_event(
            method_state,
            "launch-mapdl-notification",
            "MAPDL instance launched successfully!",
            "MAPDL initialization failed. Please check the logs.",
        )
    elif triggered_id == "shutdown-mapdl-listener" and shutdown_mapdl_message:
        logger.info("Shutdown MAPDL listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(shutdown_mapdl_message["data"])
        notification = handle_method_event(
            method_state,
            "shutdown-mapdl-notification",
            "MAPDL instance shutdown successfully!",
            "Failed to shutdown MAPDL instance. Please check the logs.",
        )
    elif triggered_id == "solve-model-listener" and solve_model_message:
        logger.info("Solve Model listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(solve_model_message["data"])
        notification = handle_method_event(
            method_state,
            "solve-model-notification",
            "Model solved successfully!",
            "Model solving failed. Please check the logs.",
        )
    elif triggered_id == "postprocess-results-listener" and postprocess_results_message:
        logger.info("Postprocess Results listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(postprocess_results_message["data"])
        notification = handle_method_event(
            method_state,
            "postprocess-results-notification",
            "Postprocessing completed successfully!",
            "Postprocessing failed. Please check the logs.",
        )

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-mapdl-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def launch_mapdl(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | str:
    """Launch an instance of Ansys MAPDL."""
    notification = no_update

    if ctx.triggered_id == "launch-mapdl-button" and n_clicks:
        logger.info("Launch button clicked, starting MAPDL instance")
        step = project.steps.mapdl_step
        step.launch_mapdl()

        notification = [
            dict(
                title="Info",
                id="launch-mapdl-notification",
                action="show",
                message="Starting MAPDL instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("solve-model-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def solve_model(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | str:
    """Solve a model in the MAPDL instance."""
    notification = no_update

    if ctx.triggered_id == "solve-model-button" and n_clicks:
        logger.info("Solve Model button clicked, solving model in MAPDL instance")
        step = project.steps.mapdl_step
        step.solve_model()

        notification = [
            dict(
                title="Info",
                id="solve-model-notification",
                action="show",
                message="Solving model... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("postprocess-results-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def postprocessing(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | str:
    """Run MAPDL postprocessing."""
    notification = no_update

    if ctx.triggered_id == "postprocess-results-button" and n_clicks:
        logger.info("Postprocessing button clicked, running MAPDL postprocessing")
        step = project.steps.mapdl_step
        step.postprocessing()

        notification = [
            dict(
                title="Info",
                id="postprocess-results-notification",
                action="show",
                message="Running postprocessing... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("shutdown-mapdl-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def shutdown_mapdl(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | str:
    """Shutdown MAPDL instance."""
    notification = no_update

    if ctx.triggered_id == "shutdown-mapdl-button" and n_clicks:
        logger.info("Shutdown button clicked, shutting down MAPDL instance")
        step = project.steps.mapdl_step
        step.shutdown_mapdl()

        notification = [
            dict(
                title="Info",
                id="shutdown-mapdl-notification",
                action="show",
                message="Shutting down MAPDL instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("mapdl-logs-store", "data", allow_duplicate=True),
    Input("mapdl-output-listener", "message"),
    State("mapdl-logs-store", "data"),
    prevent_initial_call=True,
)
def store_outputs(message: dict[str, Any], current_logs: str) -> str:
    """Store MAPDL output."""
    if message:
        new_content = message["data"].strip('"').replace("\\n", "\n")
        combined = (current_logs or "") + "\n" + new_content
        return combined
    return current_logs


@callback(
    Output("mapdl-console-logs", "children", allow_duplicate=True),
    Input("mapdl-logs-store", "data"),
)
def display_output(current_logs: str) -> str:
    """Display MAPDL output."""
    return current_logs


@callback(
    Output("mapdl-console-logs", "children"),
    Input("clear-logs-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int) -> str:
    """Clear the console logs."""
    return ""
