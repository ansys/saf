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

"""Tabs for the airfoil setup preview area."""

from __future__ import annotations

from dash_extensions.enrich import html
import dash_mantine_components as dmc

from saf.solutions.examples.ui.airfoil_explorer.components.adaptive_figure_display import AdaptiveFigureDisplay
from saf.solutions.examples.ui.airfoil_explorer.components.loading import loading_wrapper
from saf.solutions.examples.ui.airfoil_explorer.settings import settings
from saf.solutions.examples.ui.airfoil_explorer.utils.logs import create_logs_panel

AIRFOIL_TABS_ID = "airfoil-setup-tabs"
AIRFOIL_SHAPE_FIGURE_ID = "airfoil-setup-geometry-figure"
AIRFOIL_3D_CONTAINER_ID = "airfoil-setup-3d-container"
AIRFOIL_LOGS_CONTAINER_ID = "airfoil-setup-logs"
AIRFOIL_LOGS_SUPERVISOR_ID = "airfoil-logs-supervisor"
AIRFOIL_3D_LOADING_OVERLAY_ID = "airfoil-3d-loading-overlay"


def _create_airfoil_logs_panel(log_file: str | None, logs_supervisor_id: str | None = None) -> html.Div:
    """Create a keyed LogsSupervisor wrapper for the airfoil setup step."""
    return create_logs_panel(log_file, logs_supervisor_id or AIRFOIL_LOGS_SUPERVISOR_ID, "airfoil-logs")


def airfoil_tabs(
    *,
    active_tab: str = "shape",
    log_file: str | None = None,
    figure: dict | None = None,
    image_url: str | None = None,
    logs_supervisor_id: str | None = None,
) -> dmc.Tabs:
    """Create the right-hand tab panel."""
    # Use AdaptiveFigureDisplay for hybrid JSON/PNG support
    figure_display = AdaptiveFigureDisplay(
        id=AIRFOIL_SHAPE_FIGURE_ID,
        json_figure=figure,
        image_url=image_url,
        mode="auto",
    )

    shape_child = loading_wrapper(children=figure_display, loading_id="airfoil-shape-loading")

    is_visor_enabled = settings.visor_enabled

    return dmc.Tabs(
        id=AIRFOIL_TABS_ID,
        value=active_tab,
        children=[
            dmc.TabsList(
                [
                    dmc.TabsTab("Airfoil Shape", value="shape"),
                    dmc.TabsTab("3D Visualization" if is_visor_enabled else "Geometry Status", value="3d"),
                    dmc.TabsTab("Logs", value="logs"),
                ]
            ),
            dmc.TabsPanel(
                value="shape",
                children=shape_child,
            ),
            dmc.TabsPanel(
                value="3d",
                children=html.Div(
                    [
                        html.Div(
                            id=AIRFOIL_3D_LOADING_OVERLAY_ID,
                            style={"display": "none"},
                            children=dmc.Alert(
                                title="Generating Geometry",
                                color="blue",
                                children=("Generating geometry — this may take a moment."),
                            ),
                        ),
                        # Content area that is shown/hidden while generating
                        html.Div(
                            id="airfoil-3d-content",
                            children=loading_wrapper(
                                children=(
                                    html.Div(id=AIRFOIL_3D_CONTAINER_ID, style={"flex": "1", "minHeight": "400px"})
                                    if is_visor_enabled
                                    else html.Div(
                                        id=AIRFOIL_3D_CONTAINER_ID,
                                        children=dmc.Text("Click 'Generate Geometry' to see the status."),
                                        style={"padding": "20px"},
                                    )
                                ),
                                loading_id="airfoil-3d-loading",
                            ),
                        ),
                    ],
                    style={"position": "relative", "height": "100%"},
                ),
            ),
            dmc.TabsPanel(
                value="logs",
                children=html.Div(
                    id=AIRFOIL_LOGS_CONTAINER_ID,
                    children=_create_airfoil_logs_panel(log_file),
                ),
            ),
        ],
    )
