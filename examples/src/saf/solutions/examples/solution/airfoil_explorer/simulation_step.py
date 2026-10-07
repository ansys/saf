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

"""Backend of the simulation step."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import ClassVar

from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, long_running, transaction

import saf.solutions.examples.solution.airfoil_explorer.logic.ansys_geom_mesh_ops as geom_ops
from saf.solutions.examples.solution.airfoil_explorer.logic.grid import generate_grid, solve_elliptic_grid
from saf.solutions.examples.solution.airfoil_explorer.logic.parameters import (
    AirfoilParameters,
    FlowParameters,
    GridParameters,
)
from saf.solutions.examples.solution.airfoil_explorer.logic.plots import plot_grid
from saf.solutions.examples.solution.airfoil_explorer.logic.png_export import save_mesh_png
from saf.solutions.examples.solution.airfoil_explorer.utils.logging import get_step_logger
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner import (
    HpsSimulationRunner,
    HpsUnavailableError,
    LocalSimulationRunner,
)
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.simulation_status import SimulationStatus

app_logger = logging.getLogger(__name__)


class SimulationStep(StepModel):
    """Mesh refinement and potential flow solve."""

    LOGSUPERVISOR_LOGFILE_NAME: ClassVar[str] = "simulation.log"

    # Mesh parameters
    circumferential_points: int = 51
    radial_points: int = 21

    # Flow parameters
    angle_of_attack_deg: float = 0.0
    free_stream_velocity: float = 70.0

    # Outputs / artifacts
    mesh_figure: dict | None = None
    mesh_png_handle: EntityHandle = NO_ENTITY
    potential_flow_figure: dict | None = None
    flow_png_handle: EntityHandle = NO_ENTITY  # PNG for potential flow
    results_3d_asset: str | None = None
    # Path to a log file written during transactions, used by LogsSupervisor.
    logfile: str | None = None

    # Remote job tracking
    job_id: str | None = None
    submission_time: str | None = None
    job_status: str | None = None

    solve_output: dict = {}
    vtp_comp_streamlines: EntityHandle = NO_ENTITY
    vtp_interp_streamlines: EntityHandle = NO_ENTITY
    vtp_foil_results: EntityHandle = NO_ENTITY
    selected_visor_view: str = "2d_comp"

    def __init__(self, **data):
        """Initialize step and set logfile path when project directory exists."""
        super().__init__(**data)
        # Initialize logfile path early if project_directory is available
        project_dir: Path | None = getattr(self, "project_directory", None)
        if project_dir and self.logfile is None:
            self.logfile = str((Path(project_dir) / self.LOGSUPERVISOR_LOGFILE_NAME).resolve())

    def _log(self, level: str, message: str, *args):
        """Log to both LogSupervisor (UI) and application logger."""
        ui_logger = get_step_logger(self, self.LOGSUPERVISOR_LOGFILE_NAME)

        if not hasattr(ui_logger, level):
            raise ValueError(f"Invalid log level: {level}")

        getattr(ui_logger, level)(message, *args)
        getattr(app_logger, level)(message, *args)

    def update_job_status(self):
        """Update job status and push WebSocket event."""
        self._log("info", "WEBSOCKET: Sending simulation status update")

        self.transaction.raise_event(
            message={
                "job_status": self.job_status,
                "job_id": self.job_id,
                "submission_time": self.submission_time,
            },
            stream_name="simulation-hps-status",
        )

    def to_grid_parameters(self) -> GridParameters:
        """Convert persisted mesh settings to ``GridParameters``."""
        return GridParameters(Nxi=self.circumferential_points, Neta=self.radial_points)

    def to_flow_parameters(self) -> FlowParameters:
        """Convert persisted flow settings to ``FlowParameters``."""
        return FlowParameters(aoa_deg=self.angle_of_attack_deg, Vinf=self.free_stream_velocity)

    @transaction(
        self=StepSpec(
            upload=["mesh_figure", "mesh_png_handle", "logfile"],
            download=["circumferential_points", "radial_points"],
        )
    )
    def generate_mesh(
        self,
        camber_max: float = 0.02,
        camber_pos: float = 0.4,
        thickness_max: float = 0.12,
        chord_length: float = 1.0,
    ) -> None:
        """Generate and smooth the mesh around the airfoil geometry."""
        try:
            grid = self.to_grid_parameters()
            airfoil = AirfoilParameters(
                camber_max=camber_max,
                camber_pos=camber_pos,
                thickness_max=thickness_max,
                chord_length=chord_length,
            )
            X, Y = generate_grid(
                grid.Nxi,
                grid.Neta,
                airfoil.thickness_max,
                airfoil.camber_max,
                airfoil.camber_pos,
                airfoil.chord_length,
            )
            x, y = solve_elliptic_grid(X, Y)

            # Generate plotly figure
            fig = plot_grid(grid.Nxi, grid.Neta, x, y)

            # Store JSON figure
            self.mesh_figure = fig.to_dict()

            # Generate PNG for report and UI fast mode (within BDM storage root)
            png_path = self.storage_scope.get_storage_root() / "mesh.png"
            save_mesh_png(png_path, grid.Nxi, grid.Neta, x, y)
            self.mesh_png_handle = self.storage_scope.store(png_path)

            self._log("info", "Generated mesh with JSON and PNG (%s×%s points).", grid.Nxi, grid.Neta)
        except Exception:  # pragma: no cover - log and re-raise
            self._log("exception", "Mesh generation failed.")
            raise

    @transaction(
        self=StepSpec(
            upload=[
                "mesh_figure",
                "mesh_png_handle",  # Cleared by LocalSimulationRunner
                "potential_flow_figure",
                "flow_png_handle",  # Cleared by LocalSimulationRunner
                "results_3d_asset",
                "logfile",
                "job_id",
                "submission_time",
                "job_status",
                "solve_output",
            ],
            download=[
                "circumferential_points",
                "radial_points",
                "angle_of_attack_deg",
                "free_stream_velocity",
            ],
        ),
        enable_termination_event=True,
    )
    @long_running
    def submit_simulation(
        self,
        camber_max: float = 0.02,
        camber_pos: float = 0.4,
        thickness_max: float = 0.12,
        chord_length: float = 1.0,
    ) -> None:
        """Solve potential flow on the generated mesh.

        This is currently a local, synchronous computation that mirrors
        the logic in the ``usage.py`` example script.
        """
        # Clear old results first to prevent stale data showing
        self.potential_flow_figure = None
        self.flow_png_handle = NO_ENTITY

        self.job_status = SimulationStatus.INITIALIZING.value
        self.update_job_status()

        try:
            grid = self.to_grid_parameters()
            airfoil = AirfoilParameters(
                camber_max=camber_max,
                camber_pos=camber_pos,
                thickness_max=thickness_max,
                chord_length=chord_length,
            )
            flow = self.to_flow_parameters()

            # Prefer HPS runner if configured; fallback to local on any unavailability
            hps_host_and_port = os.getenv("GLOW_HPS_HOST") and os.getenv("GLOW_HPS_PORT")
            if not hps_host_and_port:
                self._log(
                    "warning",
                    "HPS server URL not configured. Using local simulation runner. "
                    "Set GLOW_HPS_HOST and GLOW_HPS_PORT environment variables to use HPS for faster simulations.",
                )
                runner = LocalSimulationRunner(self)
            else:
                runner = HpsSimulationRunner(self)

            try:
                runner.run(airfoil, grid, flow)
            except HpsUnavailableError as exc:
                self._log("warning", "HPS unavailable (%s); falling back to local simulation.", exc)
                LocalSimulationRunner(self).run(airfoil, grid, flow)
        except Exception as e:  # pragma: no cover - log and re-raise
            self._log("exception", "Simulation submission failed: " + str(e))
            raise

    @transaction(self=StepSpec(download=["solve_output"], upload=["vtp_comp_streamlines", "logfile"]))
    def create_streamlines_vtp(self) -> None:
        """Create VTP file with computed streamlines for visualization."""
        self._log("info", "Creating streamline VTP for visualization.")

        surface_vtp_path = self.storage_scope.get_storage_root() / f"comp_streamlines.vtp"
        try:
            geom_ops.create_streamlines_vtp(
                x=self.solve_output["grid_x"],
                y=self.solve_output["grid_y"],
                stream=self.solve_output["stream_function"],
                output_path=surface_vtp_path,
            )
        except Exception:
            self._log("exception", f"Failed to create streamline VTP")
        self.vtp_comp_streamlines = self.storage_scope.store(surface_vtp_path)

    @transaction(self=StepSpec(download=["solve_output"], upload=["vtp_interp_streamlines", "logfile"]))
    def create_streamlines_interpolated_vtp(self) -> None:
        """Create VTP file with interpolated streamlines for visualization."""
        self._log("info", "Creating interpolated streamline VTP for visualization.")

        surface_vtp_path = self.storage_scope.get_storage_root() / "interp_streamlines.vtp"
        try:
            geom_ops.create_streamlines_interpolated_vtp(
                x=self.solve_output["grid_x"],
                y=self.solve_output["grid_y"],
                stream=self.solve_output["stream_function"],
                output_path=surface_vtp_path,
            )
        except Exception:
            self._log("exception", "Failed to create interpolated streamline VTP")
        self.vtp_interp_streamlines = self.storage_scope.store(surface_vtp_path)

    @transaction(
        self=StepSpec(download=["solve_output", "free_stream_velocity"], upload=["vtp_foil_results", "logfile"])
    )
    def map_2d_flow_to_3d_mesh(self, vtp_2D_foil_path: str = "", chord_length: float = 1.0) -> None:
        """Map 2D flow solution results onto 3D airfoil surface mesh."""
        self._log("info", "Mapping fields onto 3D mesh...")

        surface_vtp_path = self.storage_scope.get_storage_root() / f"airfoil_results.vtp"
        geom_ops.map_2d_flow_to_3d_mesh(
            x=self.solve_output["grid_x"],
            y=self.solve_output["grid_y"],
            stream=self.solve_output["stream_function"],
            input_vtp_path=vtp_2D_foil_path,
            output_vtp_path=surface_vtp_path,
            chord_length=chord_length,
            Vinf=self.free_stream_velocity,
        )
        try:
            self.vtp_foil_results = self.storage_scope.store(surface_vtp_path)
        except Exception:
            self._log("exception", "Failed to store 3D flow results")
