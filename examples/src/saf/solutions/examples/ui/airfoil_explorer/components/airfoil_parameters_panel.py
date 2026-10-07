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

"""Reusable inputs for configuring airfoil parameters."""

from __future__ import annotations

from dash import get_asset_url
from dash_extensions.enrich import dcc, html
import dash_mantine_components as dmc

AIRFOIL_PRESET_ID = "airfoil-setup-preset"
AIRFOIL_CAMBER_MAX_ID = "airfoil-setup-camber-max"
AIRFOIL_CAMBER_POS_ID = "airfoil-setup-camber-pos"
AIRFOIL_THICKNESS_MAX_ID = "airfoil-setup-thickness-max"
AIRFOIL_RESET_BUTTON_ID = "airfoil-setup-reset"
AIRFOIL_HELP_ICON_ID = "airfoil-setup-help-icon"
AIRFOIL_HELP_MODAL_ID = "airfoil-setup-help-modal"
AIRFOIL_HELP_IMAGE = "images/airfoil_explorer/airfoil-parameters.png"

_PRESET_DATA = {
    "2412": {"camber": 2.0, "pos": 40.0, "thickness": 12.0},
    "4412": {"camber": 4.0, "pos": 40.0, "thickness": 12.0},
    "0006": {"camber": 0.0, "pos": 0.0, "thickness": 6.0},
}


def airfoil_parameters_panel(
    *,
    naca_preset: str,
    camber_max_percent: float,
    camber_pos_percent: float,
    thickness_max_percent: float,
) -> html.Div:
    """Render the "Airfoil parameters" card."""
    help_icon = dmc.ActionIcon(
        id=AIRFOIL_HELP_ICON_ID,
        variant="subtle",
        radius="xl",
        size="lg",
        c="gray",
        children=dmc.Center("?", style={"fontWeight": 700, "fontSize": "16px"}),
    )
    help_modal = dmc.Modal(
        id=AIRFOIL_HELP_MODAL_ID,
        title="Airfoil parameter definitions",
        centered=True,
        size="xl",
        children=dmc.Image(
            src=get_asset_url(AIRFOIL_HELP_IMAGE),
            alt="Annotated airfoil parameters diagram",
            fit="contain",
        ),
    )

    return dmc.Stack(
        gap="lg",
        children=[
            dmc.Group(
                justify="space-between",
                children=[
                    dmc.Text("Airfoil parameters", fw=600, size="lg"),
                    help_icon,
                ],
            ),
            dmc.Select(
                label="NACA preset",
                id=AIRFOIL_PRESET_ID,
                data=[
                    {"label": "NACA 4-digit airfoil 2412 (2% camber, 40% position, 12% thickness)", "value": "2412"},
                    {"label": "NACA 4-digit airfoil 4412 (4% camber, 40% position, 12% thickness)", "value": "4412"},
                    {"label": "NACA 4-digit airfoil 0006 (0% camber, 0% position, 6% thickness)", "value": "0006"},
                    {"label": "Custom", "value": "custom"},
                ],
                value=naca_preset,
                clearable=False,
            ),
            html.Label("Max camber (%)", style={"fontSize": "14px", "fontWeight": 500}),
            dcc.Input(
                id=AIRFOIL_CAMBER_MAX_ID,
                value=camber_max_percent,
                type="number",
                min=0,
                max=30,
                step=1,
                debounce=True,
                disabled=naca_preset != "custom",
                style={
                    "width": "100%",
                    "height": "36px",
                    "padding": "0 10px",
                    "borderRadius": "4px",
                    "border": "1px solid #ced4da",
                    "backgroundColor": "#f8f9fa" if naca_preset != "custom" else "white",
                },
            ),
            html.Label("Max camber position (%)", style={"fontSize": "14px", "fontWeight": 500}),
            dcc.Input(
                id=AIRFOIL_CAMBER_POS_ID,
                value=camber_pos_percent,
                type="number",
                min=0,
                max=100,
                step=1,
                debounce=True,
                disabled=naca_preset != "custom",
                style={
                    "width": "100%",
                    "height": "36px",
                    "padding": "0 10px",
                    "borderRadius": "4px",
                    "border": "1px solid #ced4da",
                    "backgroundColor": "#f8f9fa" if naca_preset != "custom" else "white",
                },
            ),
            html.Label("Max thickness (%)", style={"fontSize": "14px", "fontWeight": 500}),
            dcc.Input(
                id=AIRFOIL_THICKNESS_MAX_ID,
                value=thickness_max_percent,
                type="number",
                min=1,
                max=50,
                step=1,
                debounce=True,
                disabled=naca_preset != "custom",
                style={
                    "width": "100%",
                    "height": "36px",
                    "padding": "0 10px",
                    "borderRadius": "4px",
                    "border": "1px solid #ced4da",
                    "backgroundColor": "#f8f9fa" if naca_preset != "custom" else "white",
                },
            ),
            dmc.Button("Reset to NACA 2412", id=AIRFOIL_RESET_BUTTON_ID, variant="outline"),
            help_modal,
        ],
    )


def get_preset_defaults(preset: str) -> dict[str, float]:
    """Return the recommended percentages for a preset, if available."""
    return _PRESET_DATA.get(preset, _PRESET_DATA["2412"]).copy()
