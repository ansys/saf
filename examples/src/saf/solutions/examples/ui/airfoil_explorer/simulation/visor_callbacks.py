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

"""Visor 3D viewer callbacks for the simulation page."""

from __future__ import annotations

from ansys.saf.glow.client import callback
from ansys.saf.glow.solution import NO_ENTITY
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, no_update

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.airfoil_explorer.components.viewer import visor_dash_viewer as tdv
from saf.solutions.examples.ui.airfoil_explorer.components.viewer.selector import (
    result_selector_data,
    set_visor_selector_value,
)
from saf.solutions.examples.ui.airfoil_explorer.ids.simulation import SimulationIds
from saf.solutions.examples.ui.airfoil_explorer.settings import settings


def load_vtp_into_visor(
    project: ExamplesSolution,
    vtp_entity,
    model_name: str,
):
    """Load a VTP entity into Visor viewer."""
    is_visor_enabled = settings.visor_enabled
    if not is_visor_enabled:
        return

    service_launch_step = project.steps.service_launch_step

    if vtp_entity == NO_ENTITY:
        return

    service_launch_step.update_visor(vtp_handle=vtp_entity, model_name=model_name)


def load_simulation_results_in_visor_viewer(project: ExamplesSolution):
    """Load simulation results into Visor viewer based on selected view."""
    service_launch_step = project.steps.service_launch_step
    sim_step = project.steps.simulation_step

    viewer = tdv.get_visor_dash_component(
        id="visor_geom_viewer",
        host=service_launch_step.visor_host,
        port=service_launch_step.visor_port,
    )

    if sim_step.vtp_comp_streamlines != NO_ENTITY:
        load_vtp_into_visor(
            project=project,
            vtp_entity=sim_step.vtp_comp_streamlines,
            model_name="computational_grid",
        )

    elif sim_step.vtp_interp_streamlines != NO_ENTITY:
        load_vtp_into_visor(
            project=project,
            vtp_entity=sim_step.vtp_interp_streamlines,
            model_name="interpolated_grid",
        )

    return viewer


@callback(
    Output("loading-3d-results", "children"),
    Output(SimulationIds.VISOR_RESULT_SELECTOR, "data"),
    Output(SimulationIds.VISOR_RESULT_SELECTOR, "value"),
    Output(SimulationIds.VISOR_RESULT_SELECTOR, "disabled"),
    Output(SimulationIds.VISOR_RESULT_SELECTOR_TOOLTIP, "label"),
    Input("simulation_termination_listener", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def generate_3d_results(message, project: ExamplesSolution):
    """Generate 3D results and update Visor viewer selector upon simulation completion."""
    if not message:
        return no_update, no_update, no_update, no_update, no_update
    is_visor_enabled = settings.visor_enabled
    if not is_visor_enabled:
        return no_update, no_update, no_update, True, no_update

    simulation_step = project.steps.simulation_step
    airfoil_step = project.steps.airfoil_setup_step

    simulation_step.create_streamlines_vtp()
    simulation_step.create_streamlines_interpolated_vtp()

    if airfoil_step.vtp_2D_foil != NO_ENTITY:
        simulation_step.map_2d_flow_to_3d_mesh(
            vtp_2D_foil_path=str(project.storage_scope.get_cached(airfoil_step.vtp_2D_foil)),
            chord_length=airfoil_step.chord_length,
        )

    has_2d_comp = simulation_step.vtp_comp_streamlines != NO_ENTITY
    has_2d_interp = simulation_step.vtp_interp_streamlines != NO_ENTITY
    has_3d_map = simulation_step.vtp_foil_results != NO_ENTITY
    enable_selector = has_2d_comp or has_2d_interp or has_3d_map

    selector_tooltip_label = no_update
    if enable_selector:
        selector_tooltip_label = "Select the type of results to visualize."

    simulation_step.selected_visor_view = set_visor_selector_value(
        has_2d_comp,
        has_2d_interp,
        has_3d_map,
    )
    return (
        load_simulation_results_in_visor_viewer(project),
        result_selector_data(has_2d_comp, has_2d_interp, has_3d_map),
        simulation_step.selected_visor_view,
        not enable_selector,
        selector_tooltip_label,
    )


@callback(
    Input(SimulationIds.VISOR_RESULT_SELECTOR, "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def update_visor_result_view(selected_view: str, project: ExamplesSolution):
    """Update Visor viewer based on selected result view."""
    is_visor_enabled = settings.visor_enabled
    if not selected_view or not is_visor_enabled:
        return no_update

    simulation_step = project.steps.simulation_step
    simulation_step.selected_visor_view = selected_view

    if selected_view == "2d_comp":
        load_vtp_into_visor(
            project=project,
            vtp_entity=simulation_step.vtp_comp_streamlines,
            model_name="computational_grid",
        )

    elif selected_view == "2d_interp":
        load_vtp_into_visor(
            project=project,
            vtp_entity=simulation_step.vtp_interp_streamlines,
            model_name="interpolated_grid",
        )

    elif selected_view == "3d_map":
        load_vtp_into_visor(
            project=project,
            vtp_entity=simulation_step.vtp_foil_results,
            model_name="foil_results",
        )

    return no_update


@callback(
    Output(SimulationIds.RESULTS_3D, "children"),
    Output(SimulationIds.VISOR_RESULT_SELECTOR, "data"),
    Output(SimulationIds.VISOR_RESULT_SELECTOR, "value"),
    Output(SimulationIds.VISOR_RESULT_SELECTOR, "disabled"),
    Output(SimulationIds.VISOR_RESULT_SELECTOR_TOOLTIP, "label"),
    Input("url", "pathname"),
)
def update_visualization_tab_on_page_load(project: ExamplesSolution):
    """Update Visor viewer and selector state when navigating to the simulation page."""
    step = project.steps.simulation_step

    is_visor_enabled = settings.visor_enabled
    if not is_visor_enabled:
        return no_update, no_update, project.steps.simulation_step.selected_visor_view, True, no_update

    has_2d_comp = step.vtp_comp_streamlines != NO_ENTITY
    has_2d_interp = step.vtp_interp_streamlines != NO_ENTITY
    has_3d_map = step.vtp_foil_results != NO_ENTITY
    enable_selector = has_2d_comp or has_2d_interp or has_3d_map

    selector_tooltip_label = no_update
    if enable_selector:
        selector_tooltip_label = "Select the type of results to visualize."

    return (
        load_simulation_results_in_visor_viewer(project),
        result_selector_data(has_2d_comp, has_2d_interp, has_3d_map),
        step.selected_visor_view,
        not enable_selector,
        selector_tooltip_label,
    )


@callback(
    Output(SimulationIds.RESULTS_3D, "children", allow_duplicate=True),
    Input(SimulationIds.TABS, "value"),
    Input("visor_termination_listener", "message"),
    Input("visor_restart_listener", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_tab_selected(tab_value: str, visor_message: dict, visor_restart_message: dict, project: ExamplesSolution):
    """Load Visor viewer when 3D tab is selected or Visor service completes."""
    is_visor_enabled = settings.visor_enabled
    if is_visor_enabled and (tab_value == "3d" or visor_message or visor_restart_message):
        return load_simulation_results_in_visor_viewer(project)
    else:
        raise PreventUpdate
