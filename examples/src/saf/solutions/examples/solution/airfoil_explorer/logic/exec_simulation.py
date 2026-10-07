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

"""Execution script for Airfoil Explorer simulation."""

from __future__ import annotations

from saf.solutions.examples.solution.airfoil_explorer.logic.grid import generate_grid, solve_elliptic_grid
from saf.solutions.examples.solution.airfoil_explorer.logic.parameters import (
    AirfoilParameters,
    FlowParameters,
    GridParameters,
    MeshFigure,
    SimulationResults,
)
from saf.solutions.examples.solution.airfoil_explorer.logic.plots import plot_grid, plot_streamlines
from saf.solutions.examples.solution.airfoil_explorer.logic.png_export import save_mesh_png, save_streamlines_png
from saf.solutions.examples.solution.airfoil_explorer.logic.potential_flow_solver import solve_potential_flow


def main(
    airfoil: AirfoilParameters,
    grid: GridParameters,
    flow: FlowParameters,
    mesh_figure_output_path: str = "./mesh_figure.png",
    flow_figure_output_path: str = "./flow_figure.png",
) -> dict:
    """Execute the airfoil simulation using parameters from an input JSON file,\
        and outputs results as JSON and PNG files."""
    # Mesh
    X, Y = generate_grid(
        grid.Nxi,
        grid.Neta,
        airfoil.thickness_max,
        airfoil.camber_max,
        airfoil.camber_pos,
        airfoil.chord_length,
    )
    x, y = solve_elliptic_grid(X, Y)

    # Potential flow
    stream = solve_potential_flow(grid.Nxi, grid.Neta, flow.aoa_rad, flow.Vinf, x, y)

    # Generate Plotly figures for interactive JSON output
    mesh_fig = plot_grid(grid.Nxi, grid.Neta, x, y)
    flow_fig = plot_streamlines(x, y, stream)

    mesh_json = mesh_fig.to_dict()
    flow_json = flow_fig.to_dict()

    # Minimal PNGs for report and UI fast mode
    save_mesh_png(mesh_figure_output_path, grid.Nxi, grid.Neta, x, y)
    save_streamlines_png(flow_figure_output_path, x, y, stream)

    # returning a dictionary is necessary for backward compatibility with HPS
    return {
        "simulation_results": SimulationResults(
            solve_output=MeshFigure(stream_function=stream.tolist(), grid_x=x.tolist(), grid_y=y.tolist()),
            mesh_figure=mesh_json,
            flow_figure=flow_json,
        )
    }
