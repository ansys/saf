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

"""Simulation submission and mesh generation callbacks."""

from __future__ import annotations

import logging

from ansys.saf.glow.client import callback
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, no_update

from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.simulation_status import SimulationStatus
from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.airfoil_explorer.ids.simulation import SimulationIds
from saf.solutions.examples.ui.airfoil_explorer.simulation.layout import SIM_LOGFILE_STORE_ID
from saf.solutions.examples.ui.airfoil_explorer.utils.callbacks import create_button_disable_callbacks
from saf.solutions.examples.ui.airfoil_explorer.utils.images import get_image_url_with_cache_bust

logger = logging.getLogger(__name__)

# Create button disable/enable callbacks using factory
_disable_mesh_button, _re_enable_mesh_button = create_button_disable_callbacks(
    SimulationIds.GENERATE_MESH_BUTTON,
    SimulationIds.MESH_FIGURE,
)
_disable_submit_button, _re_enable_submit_button = create_button_disable_callbacks(
    SimulationIds.SUBMIT_BUTTON,
    SimulationIds.FLOW_FIGURE,
)


@callback(
    Output(f"{SimulationIds.MESH_FIGURE}-graph", "figure"),
    Output(f"{SimulationIds.MESH_FIGURE}-image", "src"),
    Output(f"{SimulationIds.MESH_FIGURE}-toggle", "checked"),
    Output("simulation-error-alert", "children"),
    Output("simulation-error-alert", "style"),
    Output(SIM_LOGFILE_STORE_ID, "data"),
    Input(SimulationIds.GENERATE_MESH_BUTTON, "n_clicks"),
    State(SimulationIds.NXI_INPUT, "value"),
    State(SimulationIds.NETA_INPUT, "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def generate_mesh(
    n_clicks: int,
    circumferential_points: int,
    radial_points: int,
    project: ExamplesSolution,
) -> tuple[dict, str, bool, str, dict, str | None]:
    """Generate and preview the mesh only."""
    if not n_clicks:
        raise PreventUpdate
    step = project.steps.simulation_step
    step.circumferential_points = circumferential_points
    step.radial_points = radial_points
    try:
        airfoil_step = project.steps.airfoil_setup_step
        step.generate_mesh(
            camber_max=airfoil_step.camber_max_percent / 100.0,
            camber_pos=airfoil_step.camber_pos_percent / 100.0,
            thickness_max=airfoil_step.thickness_max_percent / 100.0,
            chord_length=airfoil_step.chord_length,
        )
        mesh_figure = step.mesh_figure or {}
        mesh_image_url = get_image_url_with_cache_bust(step, "mesh_png_handle")
        toggle_checked = True  # Interactive view (JSON generated)
        return mesh_figure, mesh_image_url, toggle_checked, "", {"display": "none"}, step.logfile
    except Exception as exc:  # noqa: BLE001
        return (
            no_update,
            no_update,
            no_update,
            f"Mesh generation failed: {exc}",
            {"display": "block"},
            step.logfile,
        )


@callback(
    Output("simulation-state", "data", allow_duplicate=True),
    Output(SimulationIds.SUBMIT_BUTTON, "disabled", allow_duplicate=True),
    Output(f"{SimulationIds.FLOW_FIGURE}-graph", "figure", allow_duplicate=True),
    Output(f"{SimulationIds.FLOW_FIGURE}-image", "src", allow_duplicate=True),
    Output(f"{SimulationIds.FLOW_FIGURE}-toggle", "checked", allow_duplicate=True),
    Input(SimulationIds.SUBMIT_BUTTON, "n_clicks"),
    State(SimulationIds.NXI_INPUT, "value"),
    State(SimulationIds.NETA_INPUT, "value"),
    State(SimulationIds.AOA_INPUT, "value"),
    State(SimulationIds.VINF_INPUT, "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def submit_simulation(
    n_clicks: int,
    circumferential_points: int,
    radial_points: int,
    angle_of_attack_deg: float,
    free_stream_velocity: float,
    project: ExamplesSolution,
) -> tuple:
    """Unified simulation submission with hybrid completion handling."""
    if not n_clicks:
        raise PreventUpdate

    try:
        step = project.steps.simulation_step
        step.circumferential_points = circumferential_points
        step.radial_points = radial_points
        step.angle_of_attack_deg = angle_of_attack_deg
        step.free_stream_velocity = free_stream_velocity

        airfoil_step = project.steps.airfoil_setup_step
        execution_mode = "local" if step.job_id == "LOCAL" else "hps"

        # submit_simulation is @long_running — returns immediately; the termination
        # listener in status_callbacks.py drives all completion handling uniformly.
        step.submit_simulation(
            camber_max=airfoil_step.camber_max_percent / 100.0,
            camber_pos=airfoil_step.camber_pos_percent / 100.0,
            thickness_max=airfoil_step.thickness_max_percent / 100.0,
            chord_length=airfoil_step.chord_length,
        )

        logger.info("Simulation submitted with job ID: %s using mode: %s", step.job_id, execution_mode)
        new_state = {
            "status": SimulationStatus.INITIALIZING.value,
            "execution_mode": execution_mode,
            "job_id": None,
            "submission_time": None,
            "results_available": False,
            "error_message": None,
            "flow_available": False,
        }

        return new_state, True, no_update, no_update, no_update

    except Exception as e:
        logger.exception("Simulation submission failed")

        error_state = {
            "status": SimulationStatus.FAILED.value,
            "execution_mode": execution_mode,
            "error_message": str(e)[:200],
            "results_available": False,
        }

        return error_state, False, no_update, no_update, no_update


@callback(
    Output(SimulationIds.GENERATE_MESH_BUTTON, "disabled"),
    Input(SimulationIds.GENERATE_MESH_BUTTON, "n_clicks"),
    State(SimulationIds.GENERATE_MESH_BUTTON, "disabled"),
    prevent_initial_call=True,
)
def disable_mesh_button_on_click(n_clicks: int | None, currently_disabled: bool) -> bool | type[no_update]:
    """Disable the Generate Mesh button immediately when clicked."""
    return _disable_mesh_button(n_clicks, currently_disabled)


@callback(
    Output(SimulationIds.GENERATE_MESH_BUTTON, "disabled"),
    Input(f"{SimulationIds.MESH_FIGURE}-graph", "figure"),
    Input(f"{SimulationIds.MESH_FIGURE}-graph", "loading_state"),
    State(SimulationIds.GENERATE_MESH_BUTTON, "disabled"),
)
def re_enable_mesh_button(
    _figure: dict,
    loading_state: dict | None,
    currently_disabled: bool,
) -> bool | type[no_update]:
    """Re-enable the Generate Mesh button when the transaction completes."""
    return _re_enable_mesh_button(_figure, loading_state, currently_disabled)
