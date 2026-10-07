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

"""Parameter definitions for the Airfoil Explorer solution."""

## TODO: Move these to the corresponding step class if desired.

import numpy as np
from pydantic import BaseModel


class AirfoilParameters(BaseModel):
    """Airfoil parameters definition."""

    x_coord: list = np.linspace(0, 1, 101)
    camber_max: float = 0.02
    camber_pos: float = 0.4
    thickness_max: float = 0.12
    chord_length: float = 1.0


class GridParameters(BaseModel):
    """Grid parameters definition."""

    Nxi: int = 51
    Neta: int = 21


class FlowParameters(BaseModel):
    """Flow parameters definition."""

    aoa_deg: float = 0.0  # Angle of attack
    Vinf: float = 70.0  # Free-stream velocity

    @property
    def aoa_rad(self):
        """Angle of attack in radians."""
        return np.radians(self.aoa_deg)


class MeshFigure(BaseModel):
    """Mesh figure definition."""

    stream_function: list
    grid_x: list
    grid_y: list


class SimulationResults(BaseModel):
    """Simulation results definition."""

    mesh_figure: dict
    flow_figure: dict
    solve_output: MeshFigure
