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

"""Tabs for mesh preview, potential flow, results, and logs."""

from __future__ import annotations

from dash_extensions.enrich import dcc, html
import dash_mantine_components as dmc

from saf.solutions.examples.ui.airfoil_explorer.components.adaptive_figure_display import AdaptiveFigureDisplay
from saf.solutions.examples.ui.airfoil_explorer.components.loading import loading_wrapper
from saf.solutions.examples.ui.airfoil_explorer.components.viewer.selector import visor_result_selector
from saf.solutions.examples.ui.airfoil_explorer.ids.simulation import SimulationIds
from saf.solutions.examples.ui.airfoil_explorer.settings import settings
from saf.solutions.examples.ui.airfoil_explorer.utils.logs import create_logs_panel


def _create_simulation_logs_panel(log_file: str | None, logs_supervisor_id: str | None = None) -> html.Div:
    """Create a LogsSupervisor wrapper for the simulation step."""
    return create_logs_panel(log_file, logs_supervisor_id or SimulationIds.LOGS_SUPERVISOR, "simulation-logs")


def simulation_tabs(
    *,
    active_tab: str = "mesh",
    log_file: str | None = None,
    mesh_figure: dict | None = None,
    mesh_image_url: str | None = None,
    flow_figure: dict | None = None,
    flow_image_url: str | None = None,
) -> dmc.Tabs:
    """Create the right-hand tabs for the simulation page."""
    mesh_display = AdaptiveFigureDisplay(
        id=SimulationIds.MESH_FIGURE,
        json_figure=mesh_figure,
        image_url=mesh_image_url,
        mode="interactive",
    )

    flow_display = AdaptiveFigureDisplay(
        id=SimulationIds.FLOW_FIGURE,
        json_figure=flow_figure,
        image_url=flow_image_url,
        mode="interactive",
    )

    is_visor_enabled = settings.visor_enabled

    tabs_list = [
        dmc.TabsTab("Mesh Preview", value="mesh"),
        dmc.TabsTab("Potential Flow", value="flow"),
    ]
    if is_visor_enabled:
        tabs_list.append(dmc.TabsTab("3D Visualization", value="3d"))
    tabs_list.append(dmc.TabsTab("Logs", value="logs"))

    tabs_panels = [
        dmc.TabsPanel(
            value="mesh",
            children=loading_wrapper(
                children=mesh_display,
                loading_id="mesh-preview-loading",
            ),
        ),
        dmc.TabsPanel(
            value="flow",
            children=[
                # Loading overlay - shown during simulation
                html.Div(
                    id="simulation-loading-overlay",
                    style={"display": "none"},
                    children=dmc.Alert(
                        title="Computing Potential Flow",
                        color="blue",
                        children="This might take a few minutes. Go sip a coffee... ☕",
                        icon=dcc.Loading(
                            type="circle",
                            color="#ffb71b",
                            overlay_style={"visibility": "visible", "filter": "blur(2px)"},
                        ),
                    ),
                ),
                # Actual content - hidden during simulation
                html.Div(
                    id="simulation-flow-content",
                    children=flow_display,  # No dcc.Loading - we manage state explicitly
                ),
            ],
        ),
    ]

    if is_visor_enabled:
        tabs_panels.append(
            dmc.TabsPanel(
                value="3d",
                children=[
                    dmc.Alert(
                        title="Demonstration only",
                        color="yellow",
                        variant="light",
                        withCloseButton=False,
                        children=(
                            "This visualization is provided for demonstration purposes only. "
                            "Results may be approximate or inaccurate and must not be used for "
                            "validation or design decisions."
                        ),
                        style={"margin": "10px"},
                    ),
                    dmc.Tooltip(
                        id=SimulationIds.VISOR_RESULT_SELECTOR_TOOLTIP,
                        label="Run the simulation to generate results.",
                        children=visor_result_selector(),
                    ),
                    dmc.Paper(
                        withBorder=True,
                        style={
                            "position": "relative",
                            "flex": "1",
                            "minHeight": "400px",
                            "margin": "10px",
                        },
                        children=[
                            loading_wrapper(
                                loading_id="loading-3d-results",
                                children=html.Div(
                                    id=SimulationIds.RESULTS_3D,
                                    style={"height": "100%"},
                                    children=[],
                                ),
                            ),
                        ],
                    ),
                ],
            )
        )

    tabs_panels.append(
        dmc.TabsPanel(
            value="logs",
            children=html.Div(
                id=SimulationIds.LOGS_CONTAINER,
                children=_create_simulation_logs_panel(log_file),
            ),
        )
    )

    return dmc.Tabs(
        id="simulation-tabs",
        value=active_tab,
        children=[
            dmc.TabsList(tabs_list),
            *tabs_panels,
        ],
    )
