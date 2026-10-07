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

"""Backend of the airfoil_setup step."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar, Literal

from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, instance, transaction
from ansys.saf.product_manager.geometry import GeometryManager

from saf.solutions.examples.solution.airfoil_explorer.logic.airfoil import airfoil_surface
import saf.solutions.examples.solution.airfoil_explorer.logic.ansys_geom_mesh_ops as geom_ops
from saf.solutions.examples.solution.airfoil_explorer.logic.parameters import AirfoilParameters
from saf.solutions.examples.solution.airfoil_explorer.logic.plots import plot_airfoil
from saf.solutions.examples.solution.airfoil_explorer.logic.png_export import save_airfoil_png
from saf.solutions.examples.solution.airfoil_explorer.utils.logging import get_step_logger

app_logger = logging.getLogger(__name__)


class AirfoilSetupStep(StepModel):
    """Authoritative state and operations for the airfoil setup workflow."""

    LOGSUPERVISOR_LOGFILE_NAME: ClassVar[str] = "airfoil_setup.log"

    naca_preset: Literal["2412", "4412", "0006", "custom"] = "2412"
    camber_max_percent: float = 2.0
    camber_pos_percent: float = 40.0
    thickness_max_percent: float = 12.0
    chord_length: float = 1.0

    # Computed results / assets
    airfoil_shape_figure: dict | None = None
    airfoil_shape_png_handle: EntityHandle = NO_ENTITY
    geometry_asset_path: str | None = None
    # Path to a log file written during transactions, used by LogsSupervisor.
    logfile: str | None = None

    vtp_2D_foil: EntityHandle = NO_ENTITY
    vtk_metadata: dict = {}
    wing_span: float = 0.2  # Wing span in meters

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

    def _build_airfoil(self) -> AirfoilParameters:
        """Construct an AirfoilParameters instance from the current step parameters."""
        return AirfoilParameters(
            camber_max=self.camber_max_percent / 100.0,
            camber_pos=self.camber_pos_percent / 100.0,
            thickness_max=self.thickness_max_percent / 100.0,
            chord_length=self.chord_length,
        )

    def _compute_airfoil_surfaces(self):
        """Compute upper and lower surfaces of the airfoil."""
        airfoil = self._build_airfoil()

        x_u, y_u = airfoil_surface(
            airfoil.x_coord,
            airfoil.thickness_max,
            +1,
            airfoil.camber_max,
            airfoil.camber_pos,
            airfoil.chord_length,
        )
        x_l, y_l = airfoil_surface(
            airfoil.x_coord,
            airfoil.thickness_max,
            -1,
            airfoil.camber_max,
            airfoil.camber_pos,
            airfoil.chord_length,
        )
        return x_u, y_u, x_l, y_l

    @transaction(
        self=StepSpec(
            upload=[
                "logfile",
                "naca_preset",
                "camber_max_percent",
                "camber_pos_percent",
                "thickness_max_percent",
                "vtp_2D_foil",
            ],
            download=[
                "naca_preset",
                "camber_max_percent",
                "camber_pos_percent",
                "thickness_max_percent",
                "chord_length",
                "wing_span",
            ],
        )
    )
    @instance("service_launch_step.geometry_secure_manager", identifier="geometry_secure_manager")
    def generate_3d(self, geometry_secure_manager: GeometryManager) -> None:
        """Record a placeholder 3D geometry request (no actual 3D generation yet)."""
        self._log(
            "info",
            "Starting 3D airfoil generation | preset=%s, camber_max=%s%%, camber_pos=%s%%, thickness_max=%s%%",
            self.naca_preset,
            self.camber_max_percent,
            self.camber_pos_percent,
            self.thickness_max_percent,
        )

        try:
            modeler = geometry_secure_manager.instance
            surface_vtp_path = self.storage_scope.get_storage_root() / "airfoil_wing_surface_mesh.vtp"

            geom_ops.create_airfoil_geometry_pipeline(
                modeler=modeler,
                camber_max=self.camber_max_percent / 100.0,
                camber_pos=self.camber_pos_percent / 100.0,
                thickness_max=self.thickness_max_percent / 100.0,
                chord_length=self.chord_length,
                wing_span=self.wing_span,
                vtk_out_path=str(surface_vtp_path),
            )
            self.vtp_2D_foil = self.storage_scope.store(surface_vtp_path)

            self._log("info", "3D airfoil geometry generated successfully.")

        except Exception:  # pragma: no cover - log and re-raise
            self._log("exception", "3D airfoil geometry generation failed.")
            raise

    @transaction(
        self=StepSpec(
            upload=["airfoil_shape_figure", "airfoil_shape_png_handle", "geometry_asset_path", "logfile"],
            download=[
                "naca_preset",
                "camber_max_percent",
                "camber_pos_percent",
                "thickness_max_percent",
                "chord_length",
            ],
        )
    )
    def generate_geometry(self) -> None:
        """Generate a NACA 4-digit airfoil using the logic package.

        This method converts the step parameters into ``AirfoilParameters``,
        evaluates the upper and lower surfaces, and stores a Plotly figure
        that can be rendered directly in the UI.
        """
        self._log("info", "Generating airfoil geometry.")

        try:

            upper_x, upper_y, lower_x, lower_y = self._compute_airfoil_surfaces()

            # Generate plotly figure
            fig = plot_airfoil(upper_x, upper_y, lower_x, lower_y)

            # Store JSON figure
            self.airfoil_shape_figure = fig.to_dict()

            # Generate PNG for report and UI fast mode (within BDM storage root)
            png_path = self.storage_scope.get_storage_root() / "airfoil_shape.png"
            save_airfoil_png(png_path, upper_x, upper_y, lower_x, lower_y)
            self.airfoil_shape_png_handle = self.storage_scope.store(png_path)

            self.geometry_asset_path = None
            self._log(
                "info",
                "Airfoil geometry generated (preset=%s camber_max=%s%% camber_pos=%s%% thickness_max=%s%% chord=%s)",
                self.naca_preset,
                self.camber_max_percent,
                self.camber_pos_percent,
                self.thickness_max_percent,
                self.chord_length,
            )

        except Exception:  # pragma: no cover - log and re-raise
            self._log("exception", "Airfoil geometry generation failed.")
            raise

    @transaction(
        self=StepSpec(
            upload=["vtp_2D_foil", "logfile"],
        )
    )
    def reset_vtp_handle(self) -> None:
        """Clear the stored 2D VTP handle (best-effort removal of cached file)."""
        self._log("info", "Resetting 2D VTP handle and attempting to delete cached file.")
        try:
            self.vtp_2D_foil = NO_ENTITY
            self._log("info", "2D VTP handle reset successfully.")
        except Exception:
            self._log("exception", "Failed to reset 2D VTP handle.")
            raise
