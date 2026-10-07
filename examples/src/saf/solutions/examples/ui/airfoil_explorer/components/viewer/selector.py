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

"""Visor result selector."""

import dash_mantine_components as dmc

from saf.solutions.examples.ui.airfoil_explorer.ids.simulation import SimulationIds

VISOR_VIEW_2D_COMP = "2d_comp"
VISOR_VIEW_2D_INTERP = "2d_interp"
VISOR_VIEW_3D_MAP = "3d_map"


def result_selector_data(
    has_2d_comp: bool,
    has_2d_interp: bool,
    has_3d_map: bool,
) -> list[dict]:
    """Return selector options with correct disabled flags."""
    return [
        {"label": "2D flow field", "value": VISOR_VIEW_2D_COMP, "disabled": not has_2d_comp},
        {"label": "2D flow field (interpolated)", "value": VISOR_VIEW_2D_INTERP, "disabled": not has_2d_interp},
        {"label": "3D surface results", "value": VISOR_VIEW_3D_MAP, "disabled": not has_3d_map},
    ]


def set_visor_selector_value(
    has_2d_comp: bool,
    has_2d_interp: bool,
    has_3d_map: bool,
) -> str:
    """Set the default selected value for Visor result selector."""
    if has_2d_comp:
        selected_value = VISOR_VIEW_2D_COMP
    elif has_2d_interp:
        selected_value = VISOR_VIEW_2D_INTERP
    elif has_3d_map:
        selected_value = VISOR_VIEW_3D_MAP
    else:
        selected_value = VISOR_VIEW_2D_COMP
    return selected_value


def visor_result_selector() -> dmc.Tooltip:
    """3D result selector (state controlled via callbacks)."""
    return dmc.Tooltip(
        id=SimulationIds.VISOR_RESULT_SELECTOR_TOOLTIP,
        label="Run the simulation to generate results.",
        position="top",
        withArrow=True,
        children=dmc.SegmentedControl(
            id=SimulationIds.VISOR_RESULT_SELECTOR,
            data=[],
            value=None,
            fullWidth=True,
            style={"margin": "10px"},
        ),
    )
