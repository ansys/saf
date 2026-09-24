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

"""Frontend of the long transaction step.

Demonstrates how to drive a progress bar from a long-running backend
transaction without polling. The ``stream_updates`` transaction raises a
progress event on every increment and a termination event when it ends;
both are pushed to the client through backend event listeners that are
mounted in the global application layout so they stay alive across pages.
"""

import json
import logging
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState, MethodStatus
import dash
from dash_extensions.enrich import Input, Output, State, ctx, html, no_update
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.long_transaction_step import PROGRESS_STREAM_NAME, TERMINATION_STREAM_NAME
from saf.solutions.examples.ui.helpers import handle_method_event

logger = logging.getLogger(__name__)

NOTIFICATION_ID = "long-transaction-notification"

dash.register_page(
    __name__,
    name="Long Transaction",
    path_template="/projects/<project_id>/long-transaction",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def layout(project: ExamplesSolution) -> html.Div:
    """Layout of the long transaction example page."""
    step = project.steps.long_transaction_step
    is_running = step.get_long_running_method_state("stream_updates").status == MethodStatus.Running
    completed_increments = max(step.current_increment + 1, 0)
    progress = _to_percentage(completed_increments, step.number_of_increments)

    return html.Div(
        [
            html.H1(
                "Long-transaction streaming update",
                className="display-3",
                style={"font-size": "40px", "font-weight": "bold"},
            ),
            dmc.Blockquote(
                "Use SAF GLOW backend events to show a progress bar that displays the status of a long-running "
                "transaction, without polling the backend.",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            html.Br(),
            html.Br(),
            html.Br(),
            dmc.Button(
                "Run test",
                id="run-button",
                n_clicks=0,
                disabled=is_running,
                loading=is_running,
                style={"font-size": "16px", "background-color": "#2790F1", "width": "20%"},
            ),
            html.Br(),
            html.Br(),
            dmc.Group(
                [
                    dmc.Progress(
                        id="completion-progress",
                        className="mb-3",
                        value=progress,
                        animated=is_running,
                        style={"flex": 1},
                    ),
                    dmc.Text(f"{progress}%", id="completion-progress-label", w=50, ta="right", fw=500),
                ],
                gap="sm",
                wrap="nowrap",
                align="center",
            ),
            # Page scoped listeners: they are created and destroyed together with the widgets they
            # drive, so a backend event can never reach a callback whose components are unmounted.
            html.Div(
                [
                    DashClient.create_event_listener(
                        step, id="long-transaction-page-progress-listener", stream_name=PROGRESS_STREAM_NAME
                    ),
                    DashClient.create_event_listener(
                        step, id="long-transaction-page-termination-listener", stream_name=TERMINATION_STREAM_NAME
                    ),
                ]
            ),
        ],
        style={"paddingLeft": "20px"},
    )


def _to_percentage(completed_increments: int, number_of_increments: int) -> int:
    if number_of_increments <= 0:
        return 0
    return int((completed_increments * 100) / number_of_increments)


@callback(
    Output("long-transaction-event-listeners-container", "children"),
    Input("url", "pathname"),
)
def mount_event_listeners(project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Mount the application scoped backend event listeners used by this page.

    Creates two listeners bound to the ``long_transaction_step``: one for the
    progress stream that carries an update on every increment of the
    ``stream_updates`` transaction, and one for the termination event stream
    of that transaction. The listeners are mounted into a container that
    lives in the global application layout, so they remain active even when
    the user navigates to another page.

    Because these listeners outlive the page, the callbacks they trigger must
    only write to components that also live in the global layout, such as
    ``notification-container``. Writing to a widget of this page would raise a
    "nonexistent object" error as soon as an event is received while another
    page is displayed.
    """
    step = project.steps.long_transaction_step
    return [
        DashClient.create_event_listener(
            step, id="long-transaction-progress-listener", stream_name=PROGRESS_STREAM_NAME
        ),
        DashClient.create_event_listener(
            step, id="long-transaction-termination-listener", stream_name=TERMINATION_STREAM_NAME
        ),
    ]


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("run-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def start_long_running_transaction(n_clicks: int, project: ExamplesSolution) -> list[dict[str, Any]] | Any:
    """Launch the ``stream_updates`` long running transaction.

    Triggered when the user clicks the "Run test" button. Resets the
    increment counter, starts the backend transaction, and shows a persistent
    loading notification while the transaction is in progress.
    """
    notification = no_update

    if ctx.triggered_id == "run-button" and n_clicks:  # pyright: ignore[reportUnknownMemberType]
        logger.info("Launch stream_updates transaction")

        step = project.steps.long_transaction_step
        step.current_increment = -1
        step.stream_updates()

        notification = [
            dict(
                title="Info",
                id=NOTIFICATION_ID,
                action="show",
                message="Streaming updates from the long running transaction...",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]

    return notification


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("long-transaction-progress-listener", "message"),
    Input("long-transaction-termination-listener", "message"),
    prevent_initial_call=True,
)
def sync_notifications(
    progress_message: dict[str, Any], termination_message: dict[str, Any]
) -> list[dict[str, Any]] | Any:
    """Keep the notification in sync with the transaction lifecycle.

    This callback is driven by the application scoped listeners and only
    writes to ``notification-container``, which belongs to the global layout.
    The user therefore keeps following the transaction from any page of the
    solution.

    Progress events refresh the in-progress notification with the latest
    status, and the termination event replaces it with a success or failure
    message built from the ``MethodState`` payload.
    """
    notification = no_update

    if (
        ctx.triggered_id == "long-transaction-progress-listener" and progress_message
    ):  # pyright: ignore[reportUnknownMemberType]
        update = json.loads(progress_message["data"])
        progress = _to_percentage(update["current_increment"] + 1, update["number_of_increments"])
        notification = [
            dict(
                title="Info",
                id=NOTIFICATION_ID,
                action="update",
                message=f"{update['status']} ({progress}%)",
                autoClose=False,
                loading=True,
                color="blue",
                withCloseButton=False,
            )
        ]
    elif (
        ctx.triggered_id == "long-transaction-termination-listener" and termination_message
    ):  # pyright: ignore[reportUnknownMemberType]
        method_state = MethodState.model_validate_json(termination_message["data"])
        if method_state.status == MethodStatus.Completed:
            logger.info("stream_updates transaction completed")
        else:
            logger.error(f"stream_updates transaction failed: {method_state.exception_message}")
        notification = handle_method_event(
            method_state,
            NOTIFICATION_ID,
            "Successfully ran stream_updates.",
            "Failed to run stream_updates. Please check the logs.",
        )

    return notification


@callback(
    Output("run-button", "disabled", allow_duplicate=True),
    Output("run-button", "loading", allow_duplicate=True),
    Output("completion-progress", "animated", allow_duplicate=True),
    Output("completion-progress", "value", allow_duplicate=True),
    Output("completion-progress-label", "children", allow_duplicate=True),
    Input("run-button", "n_clicks"),
    Input("long-transaction-page-progress-listener", "message"),
    Input("long-transaction-page-termination-listener", "message"),
    State("run-button", "disabled"),
    prevent_initial_call=True,
)
def sync_controls(
    n_clicks: int, progress_message: dict[str, Any], termination_message: dict[str, Any], is_running: bool
) -> tuple[bool, bool, bool, int, str] | Any:
    """Keep the "Run test" button and the progress bar in sync with the transaction lifecycle.

    Every input and output of this callback belongs to the page layout, so it
    can never be triggered while its components are unmounted. Handles the
    three events that drive the page controls, dispatched on
    ``ctx.triggered_id``:

    * a click on the button disables it and starts the animated progress bar,
    * a progress event advances the progress bar and refreshes the percentage
      displayed next to it,
    * the termination event re-enables the button and completes the progress
      bar.

    Progress event payloads are JSON-encoded, so they are decoded with
    ``json.loads`` before the completion percentage is computed. Progress
    events are ignored once the button has been re-enabled: the progress and
    the termination streams are independent, so a progress event delayed by
    the network must not restart a transaction that already ended. When the
    user comes back to the page, ``layout`` rebuilds the controls from the
    step fields, so no update is lost while the page is not displayed.
    """
    disable_run_button, loading_run_button = no_update, no_update
    animated, progress, progress_label = no_update, no_update, no_update

    if ctx.triggered_id == "run-button" and n_clicks:  # pyright: ignore[reportUnknownMemberType]
        disable_run_button, loading_run_button = True, True
        animated, progress, progress_label = True, 0, "0%"
    elif (
        ctx.triggered_id == "long-transaction-page-progress-listener" and progress_message and is_running
    ):  # pyright: ignore[reportUnknownMemberType]
        update = json.loads(progress_message["data"])
        progress = _to_percentage(update["current_increment"] + 1, update["number_of_increments"])
        progress_label = f"{progress}%"
    elif (
        ctx.triggered_id == "long-transaction-page-termination-listener" and termination_message
    ):  # pyright: ignore[reportUnknownMemberType]
        method_state = MethodState.model_validate_json(termination_message["data"])
        disable_run_button, loading_run_button = False, False
        animated = False
        if method_state.status == MethodStatus.Completed:
            progress, progress_label = 100, "100%"

    return disable_run_button, loading_run_button, animated, progress, progress_label
