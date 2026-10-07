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

"""Application-scoped callbacks of the Airfoil Explorer pages.

These callbacks used to live in the solution's standalone page shell. They are registered when the Airfoil Explorer
about page is imported by Dash.
"""

from __future__ import annotations

import json
import logging

from ansys.dynamicreporting.core.serverless import ADR
from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodState, MethodStatus
from dash_extensions.enrich import Input, Output, State, html, no_update

from saf.solutions.examples.solution.airfoil_explorer.logic.report.report_utilities import ADR_INSTALLATION_DIRECTORY
from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.airfoil_explorer.settings import settings
from saf.solutions.examples.ui.airfoil_explorer.utils.navigation import get_airfoil_explorer_page

logger = logging.getLogger(__name__)

EVENT_LISTENERS_CONTAINER_ID = "airfoil-explorer-event-listeners-container"


@callback(
    Output(EVENT_LISTENERS_CONTAINER_ID, "children"),
    Input("url", "pathname"),
    Input("url", "href"),
)
def mount_event_listeners(project: ExamplesSolution, href: str):
    """Mount the backend event listeners used by the Airfoil Explorer pages.

    The listeners are mounted in the application layout so they stay alive when navigating between the
    Airfoil Explorer pages. Nothing is mounted for the other example pages.
    """
    if get_airfoil_explorer_page(href) is None:
        return no_update

    step = project.steps.simulation_step
    report_step = project.steps.report_step
    service_launch_step = project.steps.service_launch_step
    # Use inert divs when Visor is disabled to keep component IDs in the DOM
    # without triggering launch_visor() on every page load.
    visor_listeners = (
        [
            DashClient.create_event_listener(
                service_launch_step,
                id="visor_termination_listener",
                stream_name="launch-visor",
            ),
            DashClient.create_event_listener(
                service_launch_step,
                id="visor_restart_listener",
                stream_name="restart-visor",
            ),
        ]
        if settings.visor_enabled
        else [
            html.Div(id="visor_termination_listener"),
            html.Div(id="visor_restart_listener"),
        ]
    )
    return [
        DashClient.create_event_listener(step, id="simulation_process_listener", stream_name="simulation-hps-status"),
        DashClient.create_event_listener(
            step,
            id="simulation_termination_listener",
            stream_name="submit-simulation",  # Termination events use method name as stream
        ),
        DashClient.create_event_listener(
            report_step,
            id="report_termination_listener",
            stream_name="get-report",  # Termination events use method name as stream
        ),
        *visor_listeners,
    ]


@callback(
    Input("simulation_termination_listener", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def create_report_when_simulation_completes(message: dict, project: ExamplesSolution):
    """Create the report when the simulation completes successfully.

    Ensures report item creation is triggered no matter what page the user is on.
    """
    if message:
        method_state_data = json.loads(message.get("data", "{}"))
        method_state = MethodState.model_validate(method_state_data)

        status = method_state.status.value if hasattr(method_state.status, "value") else str(method_state.status)
        if status == "completed":
            try:
                project.steps.report_step.create_report_setup_and_result_items()
                project.steps.report_step.get_report()
            except Exception as e:
                logger.error(f"Error creating report: {e}")
