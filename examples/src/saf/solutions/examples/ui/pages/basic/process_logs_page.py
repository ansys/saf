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

# ©2023, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Front end of the Process logs example page.

Demonstrates streaming live log output from a long running backend
transaction to a Dash page. The user starts the ``generate_process_logs``
transaction, which appends timestamped lines to a log file every second;
each new line is pushed to the client via a backend event listener and
appended to the displayed log text in real time. The page also supports
clearing the accumulated logs.
"""

import json
import logging
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState
import dash
from dash_extensions.enrich import Input, Output, State, ctx, html, no_update
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.helpers import handle_method_event

logger = logging.getLogger(__name__)

NO_LOGS_MESSAGE = "No logs are available yet."

dash.register_page(
    __name__,
    name="Process Logs",
    path_template="/projects/<project_id>/process-logs",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def layout(project: ExamplesSolution) -> html.Div:
    """Build the Process logs page layout.

    The page shows a "Start" button that launches the long running
    ``generate_process_logs`` transaction, and a scrollable card that displays
    the log file content. The log content is streamed live from the backend
    via an event listener and initially populated from the persisted log file
    (if any) when the page is first rendered.
    """
    logs_container = dmc.Card(
        [
            dmc.CardSection(
                dmc.Group(
                    children=[
                        dmc.Text("Logs", fw=500),
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
                id="log_container",
                children=html.Pre(
                    id="log_content",
                    children=get_process_logs_text(project),
                    style={"whiteSpace": "pre-wrap", "wordBreak": "break-all", "fontSize": "10px"},
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
            html.H1("Process logs", className="display-3", style={"font-size": "40px", "font-weight": "bold"}),
            dmc.Blockquote(
                "Read the log files for a process and display their content in a solution UI.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Start",
                id="start_button",
                variant="filled",
                radius="sm",
                style={
                    "font-size": "16px",
                    "width": "20%",
                    "background-color": "#2790F1",
                },
                leftSection=DashIconify(icon="streamline:startup-solid"),
            ),
            dmc.Space(h=20),
            dmc.Grid(
                [dmc.GridCol(logs_container, span=9)],
                grow=True,
                gutter="xs",
            ),
        ],
        style={"paddingLeft": "20px"},
    )


@callback(
    Output("process-logs-event-listeners-container", "children"),
    Input("project-layout-generation", "data"),
    State("project-scoped-pathname", "data"),
    prevent_initial_call=True,
)
def mount_event_listeners(_generation: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Mount the backend event listeners used by this page.

    Creates two listeners bound to the ``basic_step``: one for the
    ``generate-process-logs-update`` stream that carries incremental log
    lines while the transaction is running, and one for the
    ``generate-process-logs`` stream that carries the transaction's
    termination event. Listeners are (re)mounted whenever a project page is displayed.
    """
    step = project.steps.basic_step
    return [
        DashClient.create_event_listener(
            step, id="generate-process-logs-update-listener", stream_name="generate-process-logs-update"
        ),
        DashClient.create_event_listener(
            step, id="generate-process-logs-termination-listener", stream_name="generate-process-logs"
        ),
    ]


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("start_button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def start_generate_process_logs_transaction(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Launch the ``generate_process_logs`` long running transaction.

    Triggered when the user clicks the "Start" button. Starts the backend
    transaction, which writes a timestamped log line every second for
    ``wait_time`` seconds, and shows a persistent loading notification while
    the transaction is in progress.
    """
    notification = no_update

    if ctx.triggered_id == "start_button" and n_clicks:  # pyright: ignore[reportUnknownMemberType]
        logger.info("Launch generate_process_logs transaction")

        step = project.steps.basic_step
        step.generate_process_logs(wait_time=10.0)

        notification = [
            dict(
                title="Info",
                id="generate-process-logs-notification",
                action="show",
                message="Generating logs via long running transaction...",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("start_button", "disabled", allow_duplicate=True),
    Output("start_button", "loading", allow_duplicate=True),
    Input("start_button", "n_clicks"),
    Input("generate-process-logs-termination-listener", "message"),
    prevent_initial_call=True,
)
def sync_controls(n_clicks: int, message: dict[str, Any]) -> tuple[bool, bool]:
    """Keep the "Start" button state in sync with the transaction lifecycle.

    Disables and shows a loading spinner on the button as soon as it is
    clicked, then re-enables it once the termination event for
    ``generate_process_logs`` is received from the backend.
    """
    disable_start_button, loading_start_button = no_update, no_update
    if ctx.triggered_id == "start_button" and n_clicks:  # pyright: ignore[reportUnknownMemberType]
        disable_start_button = True
        loading_start_button = True
    elif (
        ctx.triggered_id == "generate-process-logs-termination-listener" and message
    ):  # pyright: ignore[reportUnknownMemberType]
        disable_start_button = False
        loading_start_button = False
    return disable_start_button, loading_start_button


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("generate-process-logs-termination-listener", "message"),
    prevent_initial_call=True,
)
def sync_notifications(message: dict[str, Any]) -> list[dict[str, Any]] | Any:
    """Show a success or failure notification once the transaction ends.

    Parses the termination event's ``MethodState`` payload and replaces the
    in-progress notification with a success or failure message depending on
    whether ``generate_process_logs`` completed successfully.
    """
    notification = no_update
    if (
        ctx.triggered_id == "generate-process-logs-termination-listener" and message
    ):  # pyright: ignore[reportUnknownMemberType]
        method_state = MethodState.model_validate_json(message["data"])
        notification = handle_method_event(
            method_state,
            "generate-process-logs-notification",
            "Successfully ran generate_process_logs.",
            "Failed to run generate_process_logs. Please check the logs.",
        )
    return notification


@callback(
    Output("log_content", "children"),
    Input("generate-process-logs-update-listener", "message"),
    State("log_content", "children"),
    prevent_initial_call=True,
)
def update_logs_on_backend_events(message: dict[str, Any], current_logs: str) -> str | Any:
    """Append a newly streamed log line to the displayed log text.

    The event payload is JSON-encoded, so it is decoded with ``json.loads``
    before being appended. If no logs are currently displayed (or only the
    placeholder message is shown), the new line replaces it instead of being
    appended, so the placeholder disappears as soon as logs start flowing.
    """
    if (
        ctx.triggered_id == "generate-process-logs-update-listener" and message
    ):  # pyright: ignore[reportUnknownMemberType]
        new_line = json.loads(message["data"])
        if not current_logs or current_logs == NO_LOGS_MESSAGE:
            return new_line
        return current_logs + new_line
    return no_update


@callback(
    Output("log_content", "children"),
    Input("clear-logs-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def clear_process_logs(n_clicks: int, project: ExamplesSolution) -> str:
    """Clear the persisted log file and reset the displayed log text.

    Triggered by the "Clear Logs" icon button. Deletes the backend log file
    reference and resets the log panel to the placeholder message.
    """
    if ctx.triggered_id == "clear-logs-button" and n_clicks:  # pyright: ignore[reportUnknownMemberType]
        step = project.steps.basic_step
        step.clear_logs()
        return NO_LOGS_MESSAGE
    return no_update


def get_process_logs_text(project: ExamplesSolution) -> str:
    """Read and return the persisted log file content for the initial render.

    Returns the placeholder message if no log file exists yet, or an error
    message if the log file exists but cannot be read.
    """
    try:
        step = project.steps.basic_step
        log_file = project.storage_scope.get_cached(step.log_file)
    except Exception:
        return NO_LOGS_MESSAGE
    try:
        return log_file.read_text()
    except Exception as e:
        return "Error reading log file: " + str(e)
