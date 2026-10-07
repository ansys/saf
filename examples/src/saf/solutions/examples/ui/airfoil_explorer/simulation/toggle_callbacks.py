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

"""Toggle and input-restoration callbacks for the simulation page."""

from __future__ import annotations

from ansys.saf.glow.client import callback
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, no_update

from saf.solutions.examples.ui.airfoil_explorer.ids.simulation import SimulationIds
from saf.solutions.examples.ui.airfoil_explorer.simulation.layout import SIM_DEFAULTS_STORE_ID


@callback(
    Output(f"{SimulationIds.MESH_FIGURE}-graph", "style"),
    Output(f"{SimulationIds.MESH_FIGURE}-image", "style"),
    Input(f"{SimulationIds.MESH_FIGURE}-toggle", "checked"),
)
def toggle_mesh_view(is_interactive: bool) -> tuple[dict, dict]:
    """Toggle between interactive (graph) and fast (image) views for mesh."""
    graph_style = {"display": "block", "width": "100%", "height": "auto"} if is_interactive else {"display": "none"}
    image_style = {"display": "none"} if is_interactive else {"display": "block", "width": "100%", "height": "auto"}
    return graph_style, image_style


@callback(
    Output(f"{SimulationIds.FLOW_FIGURE}-graph", "style"),
    Output(f"{SimulationIds.FLOW_FIGURE}-image", "style"),
    Input(f"{SimulationIds.FLOW_FIGURE}-toggle", "checked"),
)
def toggle_flow_view(is_interactive: bool) -> tuple[dict, dict]:
    """Toggle between interactive (graph) and fast (image) views for potential flow."""
    graph_style = {"display": "block", "width": "100%", "height": "auto"} if is_interactive else {"display": "none"}
    image_style = {"display": "none"} if is_interactive else {"display": "block", "width": "100%", "height": "auto"}
    return graph_style, image_style


@callback(
    Output(SimulationIds.NXI_INPUT, "value"),
    Output(SimulationIds.NETA_INPUT, "value"),
    Output(SimulationIds.AOA_INPUT, "value"),
    Output(SimulationIds.VINF_INPUT, "value"),
    Input(SimulationIds.NXI_INPUT, "value"),
    Input(SimulationIds.NETA_INPUT, "value"),
    Input(SimulationIds.AOA_INPUT, "value"),
    Input(SimulationIds.VINF_INPUT, "value"),
    State(SIM_DEFAULTS_STORE_ID, "data"),
)
def restore_defaults(nxi, neta, aoa, vinf, defaults):
    """Restore cleared inputs to defaults; leave user edits untouched."""
    d = defaults or {}

    def _restore(v, key):
        if v is None:
            return d.get(key)
        if isinstance(v, str) and v.strip() == "":
            return d.get(key)
        return no_update

    return (
        _restore(nxi, "nxi"),
        _restore(neta, "neta"),
        _restore(aoa, "aoa"),
        _restore(vinf, "vinf"),
    )


@callback(
    Output(SimulationIds.HELP_MODAL, "opened"),
    Input(SimulationIds.HELP_ICON, "n_clicks"),
    prevent_initial_call=True,
)
def open_simulation_help_modal(n_clicks: int) -> bool:
    """Open the simulation parameters help modal when the icon is clicked."""
    if not n_clicks:
        raise PreventUpdate
    return True
