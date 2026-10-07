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

"""Reusable controls for the simulation page."""

from __future__ import annotations

from dash import get_asset_url
from dash_extensions.enrich import dcc, html
import dash_mantine_components as dmc

from saf.solutions.examples.ui.airfoil_explorer.ids.simulation import SimulationIds

SIM_HELP_IMAGE = "images/airfoil_explorer/simulation-parameters.png"


def simulation_parameters_panel(
    *,
    circumferential_points: int,
    radial_points: int,
    angle_of_attack_deg: float,
    free_stream_velocity: float,
) -> html.Div:
    """Layout for mesh + simulation parameters with always-visible sections."""
    help_icon = dmc.ActionIcon(
        id=SimulationIds.HELP_ICON,
        variant="subtle",
        radius="xl",
        size="lg",
        c="gray",
        children=dmc.Center("?", style={"fontWeight": 700, "fontSize": "16px"}),
    )
    help_modal = dmc.Modal(
        id=SimulationIds.HELP_MODAL,
        title="Simulation parameter definitions",
        centered=True,
        size="xl",
        children=dmc.Image(
            src=get_asset_url(SIM_HELP_IMAGE),
            alt="Simulation parameters diagram",
            fit="contain",
        ),
    )
    return dmc.Stack(
        gap="lg",
        children=[
            dmc.Stack(
                gap="md",
                children=[
                    dmc.Text("Mesh parameters", fw=600, size="md"),
                    html.Label("Circumferential grid points (Nxi)", style={"fontSize": "14px"}),
                    dcc.Input(
                        id=SimulationIds.NXI_INPUT,
                        value=circumferential_points,
                        type="number",
                        min=11,
                        step=2,
                        debounce=True,
                        style={
                            "width": "100%",
                            "height": "36px",
                            "padding": "0 10px",
                            "borderRadius": "4px",
                            "border": "1px solid #ced4da",
                        },
                    ),
                    html.Label("Radial grid points (Neta)", style={"fontSize": "14px"}),
                    dcc.Input(
                        id=SimulationIds.NETA_INPUT,
                        value=radial_points,
                        type="number",
                        min=11,
                        step=2,
                        debounce=True,
                        style={
                            "width": "100%",
                            "height": "36px",
                            "padding": "0 10px",
                            "borderRadius": "4px",
                            "border": "1px solid #ced4da",
                        },
                    ),
                    dmc.Button(
                        "Generate Mesh",
                        id=SimulationIds.GENERATE_MESH_BUTTON,
                        variant="outline",
                    ),
                ],
            ),
            dmc.Stack(
                gap="md",
                children=[
                    dmc.Group(
                        justify="space-between",
                        children=[
                            dmc.Text("Simulation parameters", fw=600, size="md"),
                            help_icon,
                        ],
                    ),
                    html.Label("Angle of attack (deg)", style={"fontSize": "14px"}),
                    dcc.Input(
                        id=SimulationIds.AOA_INPUT,
                        value=angle_of_attack_deg,
                        type="number",
                        min=-10,
                        max=20,
                        step=1,
                        debounce=True,
                        style={
                            "width": "100%",
                            "height": "36px",
                            "padding": "0 10px",
                            "borderRadius": "4px",
                            "border": "1px solid #ced4da",
                        },
                    ),
                    html.Label("Free-stream velocity (m/s)", style={"fontSize": "14px"}),
                    dcc.Input(
                        id=SimulationIds.VINF_INPUT,
                        value=free_stream_velocity,
                        type="number",
                        min=1,
                        step=1,
                        debounce=True,
                        style={
                            "width": "100%",
                            "height": "36px",
                            "padding": "0 10px",
                            "borderRadius": "4px",
                            "border": "1px solid #ced4da",
                        },
                    ),
                    dmc.Button(
                        "Submit Simulation",
                        id=SimulationIds.SUBMIT_BUTTON,
                        variant="filled",
                    ),
                    help_modal,
                ],
            ),
        ],
    )
