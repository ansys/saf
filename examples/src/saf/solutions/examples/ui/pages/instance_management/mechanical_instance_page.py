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

# ©2022, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Frontend of the mechanical page."""

import logging
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, ctx, html, no_update  # pyright: ignore[reportMissingTypeStubs]
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.helpers import get_mechanical_page_controls_with_default, handle_method_event

logger = logging.getLogger(__name__)

dash.register_page(
    __name__,
    name="Mechanical Instance Management",
    path_template="/projects/<project_id>/mechanical-instance-management",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def _run_script(project: ExamplesSolution) -> None:
    """Handle all operations related to the Mechanical step.run_script."""
    step = project.steps.mechanical_step
    step.upload_example_file_to_mechanical()
    step.initialize_variable_workflow()
    step.run_script()


def initialize_mechanical_controls(project: ExamplesSolution) -> dict[str, dict[str, Any]] | Any:
    """Initialize the state of controls on the Mechanical instance management page."""
    controls = get_mechanical_page_controls_with_default()

    for button in controls.keys():
        controls[button]["disabled"] = True
        controls[button]["loading"] = False

    transactions = [
        "launch_mechanical",
        "shutdown_mechanical",
        "run_script",
        "download_output_file",
    ]

    step = project.steps.mechanical_step
    transaction_states = {t: step.get_long_running_method_state(t).status.value for t in transactions}

    if any(state == "running" for state in transaction_states.values()):
        for button, config in controls.items():
            if transaction_states[config["transaction"]] == "running":
                controls[button]["disabled"] = True
                break
    elif step.instance_created:
        if transaction_states["run_script"] == "completed" or transaction_states["download_output_file"] == "completed":
            controls["run_script"]["disabled"] = False
            controls["download_output_file"]["disabled"] = False
            controls["shutdown_mechanical"]["disabled"] = False
        elif transaction_states["launch_mechanical"] == "completed":
            controls["run_script"]["disabled"] = False
            controls["shutdown_mechanical"]["disabled"] = False
    else:
        logger.info("No Mechanical instance detected, initializing page with default state")
        controls["launch_mechanical"]["disabled"] = False
    return controls


def layout(project: ExamplesSolution) -> html.Div:
    """Layout for the Mechanical Instance Manager page."""
    controls = initialize_mechanical_controls(project)

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
                            id="launch-mechanical-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["launch_mechanical"]["disabled"],
                            loading=controls["launch_mechanical"]["loading"],
                        ),
                        label="Launch Mechanical",
                        position="top",
                    ),
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:shutdown", width=30),
                            id="shutdown-mechanical-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["shutdown_mechanical"]["disabled"],
                            loading=controls["shutdown_mechanical"]["loading"],
                        ),
                        label="Shutdown Mechanical",
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
                        "Run Script",
                        id="run-script-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="codicon:run-all"),
                        disabled=controls["run_script"]["disabled"],
                        loading=controls["run_script"]["loading"],
                        style={"width": "70%", "font-size": "15px"},
                    ),
                    dmc.Button(
                        "Download Output File",
                        id="download-output-file-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="material-symbols:download"),
                        disabled=controls["download_output_file"]["disabled"],
                        loading=controls["download_output_file"]["loading"],
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
                    id="mechanical-console-logs",
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
                "Mechanical Instance Manager",
                className="display-3",
                style={"font-size": "40px", "font-weight": "bold"},
            ),
            dmc.Blockquote(
                "This example demonstrates how to leverage the instance management API to control Ansys Mechanical.\
                Click the Launch button to\
                start the instance. A transaction method will start Mechanical which can be used across all transaction\
                methods. Run Mechanical operations with the Run Script and\
                Download Output File buttons. Close Mechanical using the Shutdown button.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Alert(
                dmc.Text(
                    [
                        "⚠️ This example requires the following prerequisites:\n",
                        "- ",
                        dmc.Mark("Ansys Mechanical 2025 R2 Service Pack 4 (25R2 SP4) or later"),
                        " installed and licensed,\n",
                        "- ",
                        dmc.Mark("ansys-saf-pim-light-server package 0.3 or later"),
                        " installed in the Python environment or ",
                        dmc.Mark("optiSLang 2025 R2 or later"),
                        " installed,\n",
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
    Output("mechanical-instance-event-listeners-container", "children"),
    Input("project-layout-generation", "data"),
    State("project-scoped-pathname", "data"),
    prevent_initial_call=True,
)
def mount_event_listeners(_generation: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Mount Mechanical instance event listeners in the persistent main layout."""
    logger.info("Mounting Mechanical instance management event listeners")
    step = project.steps.mechanical_step
    return [
        DashClient.create_event_listener(step, id="mechanical-output-listener", stream_name="mechanical-output-stream"),
        DashClient.create_event_listener(step, id="launch-mechanical-listener", stream_name="launch-mechanical"),
        DashClient.create_event_listener(step, id="run-script-listener", stream_name="run-script"),
        DashClient.create_event_listener(step, id="download-output-file-listener", stream_name="download-output-file"),
        DashClient.create_event_listener(step, id="shutdown-mechanical-listener", stream_name="shutdown-mechanical"),
    ]


@callback(
    Output("launch-mechanical-button", "disabled", allow_duplicate=True),
    Output("launch-mechanical-button", "loading", allow_duplicate=True),
    Output("shutdown-mechanical-button", "disabled", allow_duplicate=True),
    Output("shutdown-mechanical-button", "loading", allow_duplicate=True),
    Output("run-script-button", "disabled", allow_duplicate=True),
    Output("run-script-button", "loading", allow_duplicate=True),
    Output("download-output-file-button", "disabled", allow_duplicate=True),
    Output("download-output-file-button", "loading", allow_duplicate=True),
    Input("launch-mechanical-button", "n_clicks"),
    Input("shutdown-mechanical-button", "n_clicks"),
    Input("run-script-button", "n_clicks"),
    Input("download-output-file-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def sync_controls_on_clicks(
    launch_mechanical_clicks: int,
    shutdown_mechanical_clicks: int,
    run_script_clicks: int,
    download_output_file_clicks: int,
    project: ExamplesSolution,
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on user interactions."""
    step = project.steps.mechanical_step
    triggered_id = ctx.triggered_id
    controls = get_mechanical_page_controls_with_default()

    if triggered_id == "launch-mechanical-button" and launch_mechanical_clicks and not step.instance_created:
        logger.info("Launch button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "launch_mechanical":
                controls[button]["loading"] = True
    elif triggered_id == "shutdown-mechanical-button" and shutdown_mechanical_clicks and step.instance_created:
        logger.info("Shutdown button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "shutdown_mechanical":
                controls[button]["loading"] = True
    elif triggered_id == "run-script-button" and run_script_clicks and step.instance_created:
        logger.info("Run Script button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "run_script":
                controls[button]["loading"] = True
    elif triggered_id == "download-output-file-button" and download_output_file_clicks and step.instance_created:
        logger.info("Download Output File button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "download_output_file":
                controls[button]["loading"] = True

    return (
        controls["launch_mechanical"]["disabled"],
        controls["launch_mechanical"]["loading"],
        controls["shutdown_mechanical"]["disabled"],
        controls["shutdown_mechanical"]["loading"],
        controls["run_script"]["disabled"],
        controls["run_script"]["loading"],
        controls["download_output_file"]["disabled"],
        controls["download_output_file"]["loading"],
    )


@callback(
    Output("launch-mechanical-button", "disabled", allow_duplicate=True),
    Output("launch-mechanical-button", "loading", allow_duplicate=True),
    Output("shutdown-mechanical-button", "disabled", allow_duplicate=True),
    Output("shutdown-mechanical-button", "loading", allow_duplicate=True),
    Output("run-script-button", "disabled", allow_duplicate=True),
    Output("run-script-button", "loading", allow_duplicate=True),
    Output("download-output-file-button", "disabled", allow_duplicate=True),
    Output("download-output-file-button", "loading", allow_duplicate=True),
    Input("launch-mechanical-listener", "message"),
    Input("shutdown-mechanical-listener", "message"),
    Input("run-script-listener", "message"),
    Input("download-output-file-listener", "message"),
    prevent_initial_call=True,
)
def sync_controls_on_backend_events(
    launch_mechanical_message: dict[str, Any],
    shutdown_mechanical_message: dict[str, Any],
    run_script_message: dict[str, Any],
    download_output_file_message: dict[str, Any],
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on websocket messages from the backend indicating
    Mechanical instance state changes."""
    triggered_id = ctx.triggered_id
    controls = get_mechanical_page_controls_with_default()

    if triggered_id == "launch-mechanical-listener" and launch_mechanical_message:
        logger.info("Launch Mechanical listener triggered, updating controls")
        method_state = MethodState.model_validate_json(launch_mechanical_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button == "launch_mechanical":
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button in ["shutdown_mechanical", "run_script"]:
                    controls[button]["disabled"] = False
        else:
            controls["launch_mechanical"]["disabled"] = False
            controls["launch_mechanical"]["loading"] = False
    elif triggered_id == "shutdown-mechanical-listener" and shutdown_mechanical_message:
        logger.info("Shutdown Mechanical listener triggered, updating controls")
        method_state = MethodState.model_validate_json(shutdown_mechanical_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button in ["shutdown_mechanical", "run_script", "download_output_file"]:
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button == "launch_mechanical":
                    controls[button]["disabled"] = False
                    controls[button]["loading"] = False
        else:
            controls["shutdown_mechanical"]["disabled"] = False
            controls["shutdown_mechanical"]["loading"] = False
    elif triggered_id == "run-script-listener" and run_script_message:
        logger.info("Run Script listener triggered, updating controls")
        method_state = MethodState.model_validate_json(run_script_message["data"])
        if method_state.status.value == "completed":
            controls["run_script"]["disabled"] = False
            controls["run_script"]["loading"] = False
            controls["download_output_file"]["disabled"] = False
        else:
            controls["run_script"]["disabled"] = False
            controls["run_script"]["loading"] = False
        controls["shutdown_mechanical"]["disabled"] = False
    elif triggered_id == "download-output-file-listener" and download_output_file_message:
        logger.info("Download Output File listener triggered, updating controls")
        controls["download_output_file"]["disabled"] = False
        controls["download_output_file"]["loading"] = False
        controls["shutdown_mechanical"]["disabled"] = False
        controls["run_script"]["disabled"] = False

    return (
        controls["launch_mechanical"]["disabled"],
        controls["launch_mechanical"]["loading"],
        controls["shutdown_mechanical"]["disabled"],
        controls["shutdown_mechanical"]["loading"],
        controls["run_script"]["disabled"],
        controls["run_script"]["loading"],
        controls["download_output_file"]["disabled"],
        controls["download_output_file"]["loading"],
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-mechanical-listener", "message"),
    Input("shutdown-mechanical-listener", "message"),
    Input("run-script-listener", "message"),
    Input("download-output-file-listener", "message"),
    prevent_initial_call=True,
)
def sync_notifications_on_backend_events(
    launch_mechanical_message: dict[str, Any],
    shutdown_mechanical_message: dict[str, Any],
    run_script_message: dict[str, Any],
    download_output_file_message: dict[str, Any],
) -> list[dict[str, Any]] | Any:
    """Build and return notifications from backend websocket messages about Mechanical method state changes."""
    triggered_id = ctx.triggered_id
    notification = no_update

    if triggered_id == "launch-mechanical-listener" and launch_mechanical_message:
        logger.info("Launch Mechanical listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(launch_mechanical_message["data"])
        notification = handle_method_event(
            method_state,
            "launch-mechanical-notification",
            "Mechanical instance launched successfully!",
            "Mechanical initialization failed. Please check the logs.",
        )
    elif triggered_id == "shutdown-mechanical-listener" and shutdown_mechanical_message:
        logger.info("Shutdown Mechanical listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(shutdown_mechanical_message["data"])
        notification = handle_method_event(
            method_state,
            "shutdown-mechanical-notification",
            "Mechanical instance shutdown successfully!",
            "Failed to shutdown Mechanical instance. Please check the logs.",
        )
    elif triggered_id == "run-script-listener" and run_script_message:
        logger.info("Run Script listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(run_script_message["data"])
        notification = handle_method_event(
            method_state,
            "run-script-notification",
            "Script ran successfully!",
            "Script execution failed. Please check the logs.",
        )
    elif triggered_id == "download-output-file-listener" and download_output_file_message:
        logger.info("Download output file listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(download_output_file_message["data"])
        notification = handle_method_event(
            method_state,
            "download-output-file-notification",
            "Output file downloaded successfully!",
            "Output file download failed. Please check the logs.",
        )

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-mechanical-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def launch_mechanical(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Launch an instance of Ansys Mechanical."""
    notification = no_update

    if ctx.triggered_id == "launch-mechanical-button" and n_clicks:
        logger.info("Launch button clicked, starting Mechanical instance")
        step = project.steps.mechanical_step
        step.launch_mechanical()

        notification = [
            dict(
                title="Info",
                id="launch-mechanical-notification",
                action="show",
                message="Starting Mechanical instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("run-script-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def run_script(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Run a script in the Mechanical instance."""
    notification = no_update

    if ctx.triggered_id == "run-script-button" and n_clicks:
        logger.info("Run Script button clicked, running script in Mechanical instance")

        _run_script(project)

        notification = [
            dict(
                title="Info",
                id="run-script-notification",
                action="show",
                message="Running script in Mechanical instance... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("download-output-file-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def download_output_file(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Run Mechanical postprocessing to generate the output file."""
    notification = no_update

    if ctx.triggered_id == "download-output-file-button" and n_clicks:
        logger.info("Download Output File button clicked, running postprocessing in Mechanical instance")
        step = project.steps.mechanical_step
        step.download_output_file()

        notification = [
            dict(
                title="Info",
                id="download-output-file-notification",
                action="show",
                message="Downloading output file from Mechanical instance... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("shutdown-mechanical-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def shutdown_mechanical(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Shutdown Mechanical instance."""
    notification = no_update

    if ctx.triggered_id == "shutdown-mechanical-button" and n_clicks:
        logger.info("Shutdown button clicked, shutting down Mechanical instance")
        step = project.steps.mechanical_step
        step.shutdown_mechanical()

        notification = [
            dict(
                title="Info",
                id="shutdown-mechanical-notification",
                action="show",
                message="Shutting down Mechanical instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("mechanical-logs-store", "data", allow_duplicate=True),
    Input("mechanical-output-listener", "message"),
    State("mechanical-logs-store", "data"),
    prevent_initial_call=True,
)
def store_outputs(message: dict[str, Any], current_logs: str) -> str:
    """Store Mechanical output."""
    if message:
        new_content = message["data"].strip('"').replace("\\n", "\n")
        combined = (current_logs or "") + "\n" + new_content
        return combined
    return current_logs


@callback(
    Output("mechanical-console-logs", "children", allow_duplicate=True),
    Input("mechanical-logs-store", "data"),
)
def display_output(current_logs: str) -> str:
    """Display Mechanical output."""
    return current_logs


@callback(
    Output("mechanical-console-logs", "children"),
    Input("clear-logs-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int) -> str:
    """Clear the console logs."""
    return ""
