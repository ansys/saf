# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Toasts of the pump's long-running methods, kept up to date by the application shell.

The build and solve toasts can neither expire nor be dismissed: only the end of the method
they track closes them. Their running message invites the user to browse other pages while
Fluent works, and anything mounted by a page goes away with it, so the termination listeners
and the callbacks that update the toasts live in the shell instead. The pages keep their own
listeners for what only they display: progress, console, results and the 3D view.

The scene conversion that follows a successful build or solve is started here too, so that
it happens whichever page the user is on when Fluent finishes.

This module is not a page. The shell imports it, which registers its callbacks exactly once.
"""

from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodStatus
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, dcc, html, no_update

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.logic.pump.constants import (
    BUILD_CASE_STREAM,
    PREPARE_SCENE_STREAM,
    PREPARE_SOLVED_SCENE_STREAM,
    RUN_SIMULATION_STREAM,
)
from saf.solutions.examples.ui.pages.pump.feedback import (
    NotificationCopy,
    closing_notification,
    opening_notification,
    parse_event,
)

BUILD_CASE_NOTIFICATION = NotificationCopy(
    notification_id="build-case-notification",
    running_title="Building case",
    success_title="Case ready",
    success_message="The Fluent case has been built. Continue to Operating Point.",
    failure_title="Case build failed",
)

PREPARE_SCENE_NOTIFICATION = NotificationCopy(
    notification_id="prepare-scene-notification",
    running_title="Preparing the 3D view",
    running_message="The case is being converted for the 3D viewer.",
    success_title="3D view ready",
    success_message="The pump is displayed in the 3D view.",
    failure_title="3D view preparation failed",
    failure_message="The case could not be converted for the 3D viewer.",
)

RUN_SIMULATION_NOTIFICATION = NotificationCopy(
    notification_id="run-simulation-notification",
    running_title="Running simulation",
    success_title="Simulation complete",
    success_message="The results are ready.",
    failure_title="Simulation failed",
)

PREPARE_SOLVED_SCENE_NOTIFICATION = NotificationCopy(
    notification_id="prepare-solved-scene-notification",
    running_title="Preparing the 3D view",
    running_message="The solved case is being converted for the 3D viewer.",
    success_title="3D view ready",
    success_message="The solved pump is displayed in the 3D view.",
    failure_title="3D view preparation failed",
    failure_message="The solved case could not be converted for the 3D viewer.",
)

LISTENERS_CONTAINER_ID = "pump-event-listeners-container"
MOUNTED_PROJECT_STORE_ID = "pump-event-listeners-project"

# Distinct from the identifiers the pages give their own listeners on the same streams.
BUILD_CASE_LISTENER_ID = "pump-shell-build-case-ws"
PREPARE_SCENE_LISTENER_ID = "pump-shell-prepare-scene-ws"
RUN_SIMULATION_LISTENER_ID = "pump-shell-run-simulation-ws"
PREPARE_SOLVED_SCENE_LISTENER_ID = "pump-shell-prepare-solved-scene-ws"


def listeners_slot() -> html.Div:
    """Return the part of the shell layout the termination listeners are mounted into."""
    return html.Div([dcc.Store(id=MOUNTED_PROJECT_STORE_ID), html.Div(id=LISTENERS_CONTAINER_ID)])


@callback(
    Output(LISTENERS_CONTAINER_ID, "children"),
    Output(MOUNTED_PROJECT_STORE_ID, "data"),
    Input("active-project-id", "data"),
    State(MOUNTED_PROJECT_STORE_ID, "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def mount_termination_listeners(
    project_id: str | None, mounted_project_id: str | None, project: ExamplesSolution
) -> tuple[Any, str | None]:
    """Listen for the end of the build, the solve and the scene conversions of the open project.

    The listeners need step proxies, which do not exist at import time, so they are mounted
    once a project is open. Navigating within the same project leaves them in place: a fresh
    set would reconnect, and a termination published during the reconnection would be lost
    along with the chance to close its toast.

    Parameters
    ----------
    project_id : str or None
        Identifier resolved from the URL, ``None`` when the URL names no project.
    mounted_project_id : str or None
        Project the current listeners belong to.
    project : ExamplesSolution
        Injected by the SAF callback wrapper in place of the URL path.
    """
    if project_id == mounted_project_id:
        raise PreventUpdate
    if project_id is None:
        return [], None
    setup_step = project.steps.pump_model_setup_step
    solve_step = project.steps.pump_solve_step
    return [
        DashClient.create_event_listener(setup_step, stream_name=BUILD_CASE_STREAM, id=BUILD_CASE_LISTENER_ID),
        DashClient.create_event_listener(setup_step, stream_name=PREPARE_SCENE_STREAM, id=PREPARE_SCENE_LISTENER_ID),
        DashClient.create_event_listener(solve_step, stream_name=RUN_SIMULATION_STREAM, id=RUN_SIMULATION_LISTENER_ID),
        DashClient.create_event_listener(
            solve_step, stream_name=PREPARE_SOLVED_SCENE_STREAM, id=PREPARE_SOLVED_SCENE_LISTENER_ID
        ),
    ], project_id


def _start_scene_preparation(step: Any, method_name: str) -> None:
    """Start converting the case for the 3D viewer, unless a conversion is already running.

    Every open browser tab receives the termination, so a second tab must not queue a
    second conversion of the same case.
    """
    if step.get_long_running_method_state(method_name).status != MethodStatus.Running:
        getattr(step, method_name)()


def _close_and_chain(
    message: dict | None,
    copy: NotificationCopy,
    step: Any,
    scene_method: str,
    scene_copy: NotificationCopy,
) -> Any:
    """Close the toast of a Fluent run and, on success, open the one of its scene conversion."""
    event = parse_event(message)
    if not event.finished:
        raise PreventUpdate
    notifications = closing_notification(copy, event) or []
    if event.succeeded:
        _start_scene_preparation(step, scene_method)
        notifications += opening_notification(scene_copy)
    return notifications


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input(BUILD_CASE_LISTENER_ID, "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_build_case_terminated(message: dict | None, project: ExamplesSolution) -> Any:
    """Close the build toast and, after a successful build, start preparing the 3D view."""
    return _close_and_chain(
        message,
        BUILD_CASE_NOTIFICATION,
        project.steps.pump_model_setup_step,
        "prepare_scene",
        PREPARE_SCENE_NOTIFICATION,
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input(PREPARE_SCENE_LISTENER_ID, "message"),
    prevent_initial_call=True,
)
def on_prepare_scene_terminated(message: dict | None) -> Any:
    """Close the 3D view toast of the model setup."""
    return closing_notification(PREPARE_SCENE_NOTIFICATION, parse_event(message)) or no_update


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input(RUN_SIMULATION_LISTENER_ID, "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_run_simulation_terminated(message: dict | None, project: ExamplesSolution) -> Any:
    """Close the solve toast and, after a successful solve, start preparing the 3D view."""
    return _close_and_chain(
        message,
        RUN_SIMULATION_NOTIFICATION,
        project.steps.pump_solve_step,
        "prepare_solved_scene",
        PREPARE_SOLVED_SCENE_NOTIFICATION,
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input(PREPARE_SOLVED_SCENE_LISTENER_ID, "message"),
    prevent_initial_call=True,
)
def on_prepare_solved_scene_terminated(message: dict | None) -> Any:
    """Close the 3D view toast of the solve."""
    return closing_notification(PREPARE_SOLVED_SCENE_NOTIFICATION, parse_event(message)) or no_update
