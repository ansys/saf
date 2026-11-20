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

"""Frontend of the Fluent instance management page."""

import logging
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, ctx, html, no_update  # pyright: ignore[reportMissingTypeStubs]
from dash_iconify import DashIconify  # pyright: ignore[reportMissingTypeStubs]
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.helpers import get_fluent_page_controls_with_default, handle_method_event

logger = logging.getLogger(__name__)

dash.register_page(
    __name__,
    name="Fluent Instance Management",
    path_template="/projects/<project_id>/fluent-instance-management",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def initialize_fluent_controls(project: ExamplesSolution) -> dict[str, dict[str, Any]] | Any:
    """Initialize the state of controls on the Fluent instance management page."""
    controls = get_fluent_page_controls_with_default()
    for button in controls.keys():
        controls[button]["disabled"] = True
        controls[button]["loading"] = False

    transactions = [
        "launch_fluent",
        "shutdown_fluent",
        "import_mesh",
        "run_simulation",
    ]
    step = project.steps.fluent_step
    transaction_states = {t: step.get_long_running_method_state(t).status.value for t in transactions}
    if any(state == "running" for state in transaction_states.values()):
        for button, config in controls.items():
            if transaction_states[config["transaction"]] == "running":
                controls[button]["disabled"] = True
                break
    elif step.instance_created:
        if transaction_states["import_mesh"] == "completed" or transaction_states["run_simulation"] == "completed":
            controls["import_fluent_mesh"]["disabled"] = False
            controls["run_fluent_simulation"]["disabled"] = False
            controls["shutdown_fluent"]["disabled"] = False
        elif transaction_states["launch_fluent"] == "completed":
            controls["import_fluent_mesh"]["disabled"] = False
            controls["shutdown_fluent"]["disabled"] = False
    else:
        logger.info("No Fluent instance detected, initializing page with default state")
        controls["launch_fluent"]["disabled"] = False
    return controls


def layout(project: ExamplesSolution) -> html.Div:
    """Fluent instance management page layout."""
    controls = initialize_fluent_controls(project)

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
                            id="launch-fluent-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["launch_fluent"]["disabled"],
                            loading=controls["launch_fluent"]["loading"],
                        ),
                        label="Launch Fluent",
                        position="top",
                    ),
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:shutdown", width=30),
                            id="shutdown-fluent-button",
                            size="xl",
                            color="#2790F1",
                            disabled=controls["shutdown_fluent"]["disabled"],
                            loading=controls["shutdown_fluent"]["loading"],
                        ),
                        label="Shutdown Fluent",
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
                        "Import Mesh",
                        id="import-fluent-mesh-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="game-icons:mesh-network"),
                        disabled=controls["import_fluent_mesh"]["disabled"],
                        loading=controls["import_fluent_mesh"]["loading"],
                        style={"width": "70%", "font-size": "15px"},
                    ),
                    dmc.Button(
                        "Run Simulation",
                        id="run-fluent-simulation-button",
                        variant="filled",
                        color="#2790F1",
                        leftSection=DashIconify(icon="codicon:run-all"),
                        disabled=controls["run_fluent_simulation"]["disabled"],
                        loading=controls["run_fluent_simulation"]["loading"],
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
                    id="fluent-console-logs",
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
                "Fluent Instance Manager",
                className="display-3",
                style={"font-size": "40px", "font-weight": "bold"},
            ),
            dmc.Blockquote(
                "This example demonstrates how to leverage the instance management API to control Fluent.\
                Click the Launch button to\
                start the instance. A transaction method will start Fluent which can be used across all transaction\
                methods. Run Fluent operations with the Import Mesh and\
                Run Simulation buttons. Close Fluent using the Shutdown button.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Alert(
                dmc.Text(
                    [
                        "⚠️ This example requires the following prerequisites:\n",
                        "- ",
                        dmc.Mark("Ansys Fluent 2025 R2 Service Pack 4 (25R2 SP4) or later"),
                        " installed and licensed,\n",
                        "- ",
                        dmc.Mark("ansys-saf-pim-light-server package 0.3 or later"),
                        " installed in the Python environment or ",
                        dmc.Mark("optiSLang 2025 R2 or later"),
                        " installed and licensed,\n",
                        "- ",
                        dmc.Mark("GLOW_PRODUCT_HOST"),
                        " environment variable configured to point to the Fluent host machine",
                        " (your local machine if running Fluent locally) in the .env file of the solution,\n",
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
    Output("fluent-instance-event-listeners-container", "children"),
    Input("project-layout-generation", "data"),
    State("project-scoped-pathname", "data"),
    prevent_initial_call=True,
)
def mount_event_listeners(_generation: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Mount Fluent instance event listeners in the persistent main layout."""
    step = project.steps.fluent_step
    return [
        DashClient.create_event_listener(step, id="fluent-output-listener", stream_name="fluent-output-stream"),
        DashClient.create_event_listener(step, id="launch-fluent-listener", stream_name="launch-fluent"),
        DashClient.create_event_listener(step, id="import-fluent-mesh-listener", stream_name="import-mesh"),
        DashClient.create_event_listener(step, id="run-fluent-simulation-listener", stream_name="run-simulation"),
        DashClient.create_event_listener(step, id="shutdown-fluent-listener", stream_name="shutdown-fluent"),
    ]


@callback(
    Output("launch-fluent-button", "disabled", allow_duplicate=True),
    Output("launch-fluent-button", "loading", allow_duplicate=True),
    Output("shutdown-fluent-button", "disabled", allow_duplicate=True),
    Output("shutdown-fluent-button", "loading", allow_duplicate=True),
    Output("import-fluent-mesh-button", "disabled", allow_duplicate=True),
    Output("import-fluent-mesh-button", "loading", allow_duplicate=True),
    Output("run-fluent-simulation-button", "disabled", allow_duplicate=True),
    Output("run-fluent-simulation-button", "loading", allow_duplicate=True),
    Input("launch-fluent-button", "n_clicks"),
    Input("shutdown-fluent-button", "n_clicks"),
    Input("import-fluent-mesh-button", "n_clicks"),
    Input("run-fluent-simulation-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def sync_controls_on_clicks(
    launch_fluent_clicks: int,
    shutdown_fluent_clicks: int,
    import_fluent_mesh_clicks: int,
    run_fluent_simulation_clicks: int,
    project: ExamplesSolution,
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on user interactions."""
    step = project.steps.fluent_step
    triggered_id = ctx.triggered_id
    controls = get_fluent_page_controls_with_default()

    if triggered_id == "launch-fluent-button" and launch_fluent_clicks and not step.instance_created:
        logger.info("Launch button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "launch_fluent":
                controls[button]["loading"] = True
    elif triggered_id == "shutdown-fluent-button" and shutdown_fluent_clicks and step.instance_created:
        logger.info("Shutdown button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "shutdown_fluent":
                controls[button]["loading"] = True
    elif triggered_id == "import-fluent-mesh-button" and import_fluent_mesh_clicks and step.instance_created:
        logger.info("Import Mesh button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "import_fluent_mesh":
                controls[button]["loading"] = True
    elif triggered_id == "run-fluent-simulation-button" and run_fluent_simulation_clicks and step.instance_created:
        logger.info("Run Simulation button clicked, updating controls")
        for button in controls.keys():
            controls[button]["disabled"] = True
            if button == "run_fluent_simulation":
                controls[button]["loading"] = True

    return (
        controls["launch_fluent"]["disabled"],
        controls["launch_fluent"]["loading"],
        controls["shutdown_fluent"]["disabled"],
        controls["shutdown_fluent"]["loading"],
        controls["import_fluent_mesh"]["disabled"],
        controls["import_fluent_mesh"]["loading"],
        controls["run_fluent_simulation"]["disabled"],
        controls["run_fluent_simulation"]["loading"],
    )


@callback(
    Output("launch-fluent-button", "disabled", allow_duplicate=True),
    Output("launch-fluent-button", "loading", allow_duplicate=True),
    Output("shutdown-fluent-button", "disabled", allow_duplicate=True),
    Output("shutdown-fluent-button", "loading", allow_duplicate=True),
    Output("import-fluent-mesh-button", "disabled", allow_duplicate=True),
    Output("import-fluent-mesh-button", "loading", allow_duplicate=True),
    Output("run-fluent-simulation-button", "disabled", allow_duplicate=True),
    Output("run-fluent-simulation-button", "loading", allow_duplicate=True),
    Input("launch-fluent-listener", "message"),
    Input("shutdown-fluent-listener", "message"),
    Input("import-fluent-mesh-listener", "message"),
    Input("run-fluent-simulation-listener", "message"),
    prevent_initial_call=True,
)
def sync_controls_on_backend_events(
    launch_fluent_message: dict[str, Any],
    shutdown_fluent_message: dict[str, Any],
    import_fluent_mesh_message: dict[str, Any],
    run_fluent_simulation_message: dict[str, Any],
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    """Sync the state of the control buttons based on websocket messages from the backend indicating
    Fluent instance state changes."""
    triggered_id = ctx.triggered_id
    controls = get_fluent_page_controls_with_default()

    if triggered_id == "launch-fluent-listener" and launch_fluent_message:
        logger.info("Launch Fluent listener triggered, updating controls")
        method_state = MethodState.model_validate_json(launch_fluent_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button == "launch_fluent":
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button in ["shutdown_fluent", "import_fluent_mesh"]:
                    controls[button]["disabled"] = False
        else:
            controls["launch_fluent"]["disabled"] = False
            controls["launch_fluent"]["loading"] = False
    elif triggered_id == "shutdown-fluent-listener" and shutdown_fluent_message:
        logger.info("Shutdown Fluent listener triggered, updating controls")
        method_state = MethodState.model_validate_json(shutdown_fluent_message["data"])
        if method_state.status.value == "completed":
            for button in controls.keys():
                if button in ["shutdown_fluent", "import_fluent_mesh", "run_fluent_simulation"]:
                    controls[button]["disabled"] = True
                    controls[button]["loading"] = False
                elif button == "launch_fluent":
                    controls[button]["disabled"] = False
                    controls[button]["loading"] = False
        else:
            controls["shutdown_fluent"]["disabled"] = False
            controls["shutdown_fluent"]["loading"] = False
    elif triggered_id == "import-fluent-mesh-listener" and import_fluent_mesh_message:
        logger.info("Import Mesh listener triggered, updating controls")
        method_state = MethodState.model_validate_json(import_fluent_mesh_message["data"])
        if method_state.status.value == "completed":
            controls["import_fluent_mesh"]["disabled"] = False
            controls["import_fluent_mesh"]["loading"] = False
            controls["run_fluent_simulation"]["disabled"] = False
        else:
            controls["import_fluent_mesh"]["disabled"] = False
            controls["import_fluent_mesh"]["loading"] = False
        controls["shutdown_fluent"]["disabled"] = False
    elif triggered_id == "run-fluent-simulation-listener" and run_fluent_simulation_message:
        logger.info("Run Simulation listener triggered, updating controls")
        controls["run_fluent_simulation"]["disabled"] = False
        controls["run_fluent_simulation"]["loading"] = False
        controls["shutdown_fluent"]["disabled"] = False
        controls["import_fluent_mesh"]["disabled"] = False

    return (
        controls["launch_fluent"]["disabled"],
        controls["launch_fluent"]["loading"],
        controls["shutdown_fluent"]["disabled"],
        controls["shutdown_fluent"]["loading"],
        controls["import_fluent_mesh"]["disabled"],
        controls["import_fluent_mesh"]["loading"],
        controls["run_fluent_simulation"]["disabled"],
        controls["run_fluent_simulation"]["loading"],
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-fluent-listener", "message"),
    Input("shutdown-fluent-listener", "message"),
    Input("import-fluent-mesh-listener", "message"),
    Input("run-fluent-simulation-listener", "message"),
    prevent_initial_call=True,
)
def sync_notifications_on_backend_events(
    launch_fluent_message: dict[str, Any],
    shutdown_fluent_message: dict[str, Any],
    import_fluent_mesh_message: dict[str, Any],
    run_fluent_simulation_message: dict[str, Any],
) -> list[dict[str, Any]] | Any:
    """Build and return notifications from backend websocket messages about Fluent method state changes."""
    triggered_id = ctx.triggered_id
    notification = no_update

    if triggered_id == "launch-fluent-listener" and launch_fluent_message:
        logger.info("Launch Fluent listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(launch_fluent_message["data"])
        notification = handle_method_event(
            method_state,
            "launch-fluent-notification",
            "Fluent instance launched successfully!",
            "Fluent initialization failed. Please check the logs.",
        )
    elif triggered_id == "shutdown-fluent-listener" and shutdown_fluent_message:
        logger.info("Shutdown Fluent listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(shutdown_fluent_message["data"])
        notification = handle_method_event(
            method_state,
            "shutdown-fluent-notification",
            "Fluent instance shutdown successfully!",
            "Failed to shutdown Fluent instance. Please check the logs.",
        )
    elif triggered_id == "import-fluent-mesh-listener" and import_fluent_mesh_message:
        logger.info("Import Mesh listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(import_fluent_mesh_message["data"])
        notification = handle_method_event(
            method_state,
            "import-fluent-mesh-notification",
            "Mesh imported successfully!",
            "Mesh import failed. Please check the logs.",
        )
    elif triggered_id == "run-fluent-simulation-listener" and run_fluent_simulation_message:
        logger.info("Run Simulation listener triggered, updating notifications")
        method_state = MethodState.model_validate_json(run_fluent_simulation_message["data"])
        notification = handle_method_event(
            method_state,
            "run-fluent-simulation-notification",
            "Simulation started successfully!",
            "Simulation failed to start. Please check the logs.",
        )

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("launch-fluent-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def launch_fluent(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Launch an instance of Ansys Fluent."""
    notification = no_update

    if ctx.triggered_id == "launch-fluent-button" and n_clicks:
        logger.info("Launch button clicked, starting Fluent instance")
        step = project.steps.fluent_step
        step.launch_fluent()

        notification = [
            dict(
                title="Info",
                id="launch-fluent-notification",
                action="show",
                message="Starting Fluent instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("import-fluent-mesh-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def import_mesh(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Import a mesh into the Fluent instance."""
    notification = no_update

    if ctx.triggered_id == "import-fluent-mesh-button" and n_clicks:
        logger.info("Import Mesh button clicked, importing mesh into Fluent instance")
        step = project.steps.fluent_step
        step.import_mesh()

        notification = [
            dict(
                title="Info",
                id="import-fluent-mesh-notification",
                action="show",
                message="Importing mesh... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("run-fluent-simulation-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def run_simulation(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Run Fluent simulation."""
    notification = no_update

    if ctx.triggered_id == "run-fluent-simulation-button" and n_clicks:
        logger.info("Run Simulation button clicked, running Fluent simulation")
        step = project.steps.fluent_step
        step.run_simulation()

        notification = [
            dict(
                title="Info",
                id="run-fluent-simulation-notification",
                action="show",
                message="Running simulation... Check the logs for progress.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("shutdown-fluent-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def shutdown_fluent(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Shutdown Fluent instance."""
    notification = no_update

    if ctx.triggered_id == "shutdown-fluent-button" and n_clicks:
        logger.info("Shutdown button clicked, shutting down Fluent instance")
        step = project.steps.fluent_step
        step.shutdown_fluent()

        notification = [
            dict(
                title="Info",
                id="shutdown-fluent-notification",
                action="show",
                message="Shutting down Fluent instance... Please wait.",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("fluent-logs-store", "data", allow_duplicate=True),
    Input("fluent-output-listener", "message"),
    State("fluent-logs-store", "data"),
    prevent_initial_call=True,
)
def store_outputs(message: dict[str, Any], current_logs: str) -> str:
    """Store Fluent output."""
    if message:
        new_content = message["data"].strip('"').replace("\\n", "\n")
        combined = (current_logs or "") + "\n" + new_content
        return combined
    return current_logs


@callback(
    Output("fluent-console-logs", "children", allow_duplicate=True),
    Input("fluent-logs-store", "data"),
)
def display_output(current_logs: str) -> str:
    """Display Fluent output."""
    return current_logs


@callback(
    Output("fluent-console-logs", "children"),
    Input("clear-logs-button", "n_clicks"),
    prevent_initial_call=True,
)
def clear_console_logs(n_clicks: int) -> str:
    """Clear the console logs."""
    return ""
