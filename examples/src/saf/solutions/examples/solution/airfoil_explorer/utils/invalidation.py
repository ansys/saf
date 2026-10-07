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

"""Utility functions for invalidating downstream data when upstream parameters change."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ansys.saf.glow.solution import NO_ENTITY

if TYPE_CHECKING:
    from saf.solutions.examples.solution.airfoil_explorer.simulation_step import SimulationStep


def invalidate_mesh(step: SimulationStep, reason: str = "Airfoil Changed") -> None:
    """Invalidate mesh data when upstream parameters change.

    Args:
        step: The SimulationStep instance to invalidate
        reason: Short description of why mesh is invalid (e.g., "Airfoil Changed")
    """
    step.mesh_figure = {
        "data": [],
        "layout": {
            "title": f"Mesh Invalidated - {reason}",
            "annotations": [
                {
                    "text": "Airfoil shape parameters were modified.<br><br>Please click 'Generate Mesh' "
                    "to create a new mesh.",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"size": 16, "color": "#ff6b6b"},
                }
            ],
        },
    }
    step.mesh_png_handle = NO_ENTITY


def invalidate_simulation_results(step: SimulationStep, reason: str = "Mesh Changed") -> None:
    """Invalidate simulation results when upstream parameters change.

    Args:
        step: The SimulationStep instance to invalidate
        reason: Short description of why results are invalid (e.g., "Mesh Changed", "Airfoil Changed")
    """
    step.potential_flow_figure = {
        "data": [],
        "layout": {
            "title": f"Simulation Invalidated - {reason}",
            "annotations": [
                {
                    "text": "Airfoil shape or mesh parameters were modified.<br><br>Please click 'Submit Simulation' "
                    "to run a new simulation.",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"size": 16, "color": "#ff6b6b"},
                }
            ],
        },
    }
    step.flow_png_handle = NO_ENTITY
    step.job_status = None
    step.job_id = None
    step.submission_time = None
