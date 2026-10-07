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

"""Simulation status management and state-sync callbacks."""

from __future__ import annotations

import json

from ansys.saf.glow._core.method_status import MethodState
from ansys.saf.glow.client import callback
from ansys.saf.glow.solution import NO_ENTITY
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, no_update

from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.simulation_status import SimulationStatus
from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.airfoil_explorer.ids.simulation import SimulationIds
from saf.solutions.examples.ui.airfoil_explorer.simulation.layout import SIMULATION_JOB_STATUS_ID, job_status_display
from saf.solutions.examples.ui.airfoil_explorer.utils.images import get_image_url_with_cache_bust
from saf.solutions.examples.ui.airfoil_explorer.utils.navigation import get_airfoil_explorer_page


@callback(
    Output("simulation-state", "data", allow_duplicate=True),
    Output("simulation_run_data_storage", "data"),
    Output("simulation-status-store", "data", allow_duplicate=True),
    Input("simulation_process_listener", "message"),
    State("simulation-state", "data"),
    State("simulation_run_data_storage", "data"),
    prevent_initial_call=True,
)
def update_simulation_status(message: dict, state: dict, data_storage: dict) -> tuple[dict, dict, str]:
    """Update simulation status from WebSocket events - clean state management."""
    if not message:
        return no_update, no_update, no_update

    message_data = json.loads(message.get("data", "{}"))

    updated_data = data_storage.copy()
    job_status = message_data.get("job_status", "")
    updated_data["hps_job_status"] = job_status
    updated_data["job_id"] = message_data.get("job_id")
    updated_data["submission_time"] = message_data.get("submission_time")

    updated_state = state.copy()
    updated_state.update(
        {
            "status": job_status or state.get("status", SimulationStatus.IDLE.value),
            "job_id": message_data.get("job_id") or state.get("job_id"),
            "submission_time": message_data.get("submission_time") or state.get("submission_time"),
        }
    )

    return updated_state, updated_data, job_status or no_update


@callback(
    Output("simulation-state", "data", allow_duplicate=True),
    Output(SimulationIds.SUBMIT_BUTTON, "disabled", allow_duplicate=True),
    Output(f"{SimulationIds.FLOW_FIGURE}-graph", "figure", allow_duplicate=True),
    Output(f"{SimulationIds.FLOW_FIGURE}-image", "src", allow_duplicate=True),
    Output(f"{SimulationIds.FLOW_FIGURE}-toggle", "checked", allow_duplicate=True),
    Input("simulation_termination_listener", "message"),
    State("simulation-state", "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def handle_simulation_completion(message: dict, state: dict, project: ExamplesSolution) -> tuple:
    """Handle simulation completion - load results and update final state."""
    if not message:
        return no_update, no_update, no_update, no_update, no_update

    method_state_data = json.loads(message.get("data", "{}"))
    method_state = MethodState.model_validate(method_state_data)

    status = method_state.status.value if hasattr(method_state.status, "value") else str(method_state.status)

    step = project.steps.simulation_step

    fields = step.get_fields(["flow_png_handle", "potential_flow_figure"])
    flow_png_handle = fields.get("flow_png_handle")
    potential_flow_figure = fields.get("potential_flow_figure")

    has_flow_results = flow_png_handle != NO_ENTITY or (
        potential_flow_figure
        and potential_flow_figure != {"data": [], "layout": {}}
        and len(potential_flow_figure.get("data", [])) > 0
    )

    updated_state = state.copy()
    updated_state.update(
        {
            "status": SimulationStatus.RESULTS_READY.value,
            "results_available": has_flow_results,
            "flow_available": potential_flow_figure is not None,
            "error_message": None,
        }
    )

    button_disabled = not has_flow_results

    if has_flow_results and potential_flow_figure and len(potential_flow_figure.get("data", [])) > 0:
        flow_figure = potential_flow_figure
        flow_image_url = (
            get_image_url_with_cache_bust(step, "flow_png_handle") if flow_png_handle != NO_ENTITY else no_update
        )
        flow_toggle = no_update
    elif flow_png_handle != NO_ENTITY:
        flow_figure = no_update
        flow_image_url = get_image_url_with_cache_bust(step, "flow_png_handle")
        flow_toggle = False
    else:
        flow_figure = no_update
        flow_image_url = no_update
        flow_toggle = no_update

    return updated_state, button_disabled, flow_figure, flow_image_url, flow_toggle


@callback(
    Output(SimulationIds.SUBMIT_BUTTON, "disabled", allow_duplicate=True),
    Output(f"{SimulationIds.FLOW_FIGURE}-graph", "figure"),
    Output(f"{SimulationIds.FLOW_FIGURE}-image", "src"),
    Output(f"{SimulationIds.FLOW_FIGURE}-toggle", "checked"),
    Output("simulation-status-store", "data", allow_duplicate=True),
    Output(SIMULATION_JOB_STATUS_ID, "children"),
    Input("simulation-state", "data"),
)
def update_simulation_ui(state: dict) -> tuple:
    """Reactive UI updates based on simulation state - single source of truth."""
    status = state.get("status", SimulationStatus.IDLE.value)
    results_available = state.get("results_available", False)
    flow_available = state.get("flow_available", False)
    error_message = state.get("error_message")

    flow_figure = no_update
    flow_image_url = no_update
    flow_toggle = no_update

    status_messages = {
        SimulationStatus.QUEUED.value: ("Simulation Queued", "Waiting for HPS resources..."),
        SimulationStatus.PENDING.value: ("Preparing Simulation", "Getting ready to run..."),
        SimulationStatus.RUNNING.value: ("Running Simulation", "Computing potential flow solution..."),
        SimulationStatus.PROLOG.value: ("Setting Up Job", "Preparing job environment..."),
        SimulationStatus.EVALUATED.value: ("Simulation Complete", "Processing results..."),
        SimulationStatus.COMPLETED.value: ("Simulation Completed", "Rendering results..."),
        SimulationStatus.RESULTS_READY.value: ("Results Ready", "Interactive plots available"),
    }

    if status == SimulationStatus.IDLE.value:
        flow_figure = {"data": [], "layout": {"title": "Ready to simulate"}}
        flow_image_url = ""
        flow_toggle = True

    elif status == SimulationStatus.INITIALIZING.value:
        initializing_figure = {
            "data": [],
            "layout": {
                "title": "Initializing Simulation",
                "annotations": [
                    {
                        "text": "Starting simulation...",
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.5,
                        "y": 0.5,
                        "showarrow": False,
                        "font": {"size": 16, "color": "#4dabf7"},
                    }
                ],
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
            },
        }
        flow_figure = initializing_figure
        flow_image_url = ""
        flow_toggle = True

    elif status in [
        SimulationStatus.RUNNING.value,
        SimulationStatus.QUEUED.value,
        SimulationStatus.PENDING.value,
        SimulationStatus.PROLOG.value,
        SimulationStatus.EVALUATED.value,
        SimulationStatus.COMPLETED.value,
    ]:
        title, message = status_messages.get(status, (f"Status: {status}", "Processing..."))

        progress_figure = {
            "data": [],
            "layout": {
                "title": "",
                "annotations": [
                    {
                        "text": f"<b>{title}</b><br><br>{message}",
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.5,
                        "y": 0.5,
                        "showarrow": False,
                        "font": {"size": 18, "color": "#228be6"},
                        "align": "center",
                    }
                ],
                "xaxis": {"visible": False, "showgrid": False},
                "yaxis": {"visible": False, "showgrid": False},
                "paper_bgcolor": "#f8f9fa",
                "plot_bgcolor": "#f8f9fa",
                "margin": {"l": 40, "r": 40, "t": 40, "b": 40},
            },
        }
        flow_figure = progress_figure
        flow_image_url = ""
        flow_toggle = no_update

    elif status == SimulationStatus.RESULTS_READY.value:
        flow_figure = no_update
        flow_image_url = no_update
        flow_toggle = no_update

    elif status == SimulationStatus.FAILED.value:
        error_figure = {
            "data": [],
            "layout": {
                "title": "Simulation Failed",
                "annotations": [
                    {
                        "text": f"Error: {error_message or 'Unknown error'}",
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.5,
                        "y": 0.5,
                        "showarrow": False,
                        "font": {"size": 14, "color": "#d32f2f"},
                    }
                ],
            },
        }
        flow_figure = error_figure
        flow_image_url = ""
        flow_toggle = True

    button_disabled = status in [
        SimulationStatus.INITIALIZING.value,
        SimulationStatus.RUNNING.value,
        SimulationStatus.QUEUED.value,
        SimulationStatus.PENDING.value,
        SimulationStatus.PROLOG.value,
        SimulationStatus.EVALUATED.value,
    ]

    job_status_display_component = job_status_display(
        state.get("job_id"), state.get("submission_time"), state.get("status")
    )

    return (button_disabled, flow_figure, flow_image_url, flow_toggle, status, job_status_display_component)


@callback(
    Output("simulation-state", "data", allow_duplicate=True),
    Input("url", "pathname"),
    Input("url", "href"),
    State("simulation-state", "data"),
    prevent_initial_call=True,
)
def sync_state_on_load(project: ExamplesSolution, href: str, session_state: dict) -> dict:
    """Sync session state with actual backend step status to recover missed events.

    Triggered when navigating to the simulation page.
    """
    if get_airfoil_explorer_page(href) != "simulation":
        raise PreventUpdate

    if not session_state:
        raise PreventUpdate

    step = project.steps.simulation_step
    session_status = session_state.get("status")

    active_statuses = [
        SimulationStatus.INITIALIZING.value,
        SimulationStatus.RUNNING.value,
        SimulationStatus.QUEUED.value,
        SimulationStatus.PENDING.value,
        SimulationStatus.PROLOG.value,
        SimulationStatus.EVALUATED.value,
    ]

    # Reconcile: backend completed but UI still shows active status
    if session_status in active_statuses and step.job_status == SimulationStatus.COMPLETED.value:
        has_flow_results = step.flow_png_handle != NO_ENTITY or (
            step.potential_flow_figure
            and step.potential_flow_figure != {"data": [], "layout": {}}
            and len(step.potential_flow_figure.get("data", [])) > 0
        )
        new_state = session_state.copy()
        new_state.update(
            {
                "status": SimulationStatus.RESULTS_READY.value,
                "results_available": has_flow_results,
                "flow_available": step.potential_flow_figure is not None,
                "error_message": None,
            }
        )
        return new_state

    # Reconcile: backend idle but UI shows non-idle status
    if step.job_status in [SimulationStatus.IDLE.value, None] and session_status != SimulationStatus.IDLE.value:
        new_state = session_state.copy()
        new_state.update(
            {
                "status": SimulationStatus.IDLE.value,
                "results_available": False,
                "flow_available": False,
            }
        )
        return new_state

    # Reconcile: UI stuck in INITIALIZING but backend has progressed to other active status
    if session_status == SimulationStatus.INITIALIZING.value and step.job_status in [
        SimulationStatus.RUNNING.value,
        SimulationStatus.QUEUED.value,
        SimulationStatus.PENDING.value,
        SimulationStatus.PROLOG.value,
        SimulationStatus.EVALUATED.value,
    ]:
        new_state = session_state.copy()
        new_state.update({"status": step.job_status})
        return new_state

    raise PreventUpdate
