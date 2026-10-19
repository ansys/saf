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

"""Constants for the pump frozen-rotor workflow.

Values mirror the reference script ``frozen_rotor_workflow.py``.
"""

from typing import Final

# --------------------------------------------------------------------------------------------- Fluid properties ----

DENSITY_WATER: Final[float] = 998.2
"""Density of liquid water, in kg/m^3."""

VISCOSITY_WATER: Final[float] = 0.001002
"""Dynamic viscosity of liquid water, in kg/(m.s)."""

GRAVITY: Final[float] = 9.81
"""Standard gravitational acceleration, in m/s^2."""

FLUID_MATERIAL: Final[str] = "water-liquid"
"""Name of the fluid material in the Fluent material database."""

# ------------------------------------------------------------------------------------------------------- Meshes ----

MESH_REPOSITORY: Final[str] = "pyfluent/examples/pump-volute"
IMPELLER_MESH_FILE: Final[str] = "impeller.msh.h5"
VOLUTE_MESH_FILE: Final[str] = "volute.msh.h5"

# -------------------------------------------------------------------------------------------------------- Zones ----

IMPELLER_CELL_ZONE: Final[str] = "impeller"
VOLUTE_CELL_ZONE: Final[str] = "volute"

INLET_ZONE: Final[str] = "inlet"
OUTLET_ZONE: Final[str] = "mass-flow-inlet-11"
IMPELLER_INTERFACE_ZONE: Final[str] = "interface-impeller-outlet"
VOLUTE_INTERFACE_ZONE: Final[str] = "interface-volute-inlet"
BLADE_ZONE: Final[str] = "blade"
IMPELLER_HUB_ZONE: Final[str] = "impeller-hub"
IMPELLER_SHROUD_ZONE: Final[str] = "impeller-shroud"
INBLOCK_HUB_ZONE: Final[str] = "inblock-hub"
INBLOCK_SHROUD_ZONE: Final[str] = "inblock-shroud"
VOLUTE_INLET_WALL_ZONE: Final[str] = "volute-inlet-wall"
VOLUTE_WALL_ZONE: Final[str] = "volute-wall"

MESH_DISPLAY_SURFACES: Final[tuple[str, ...]] = (
    INLET_ZONE,
    OUTLET_ZONE,
    IMPELLER_INTERFACE_ZONE,
    VOLUTE_INTERFACE_ZONE,
    BLADE_ZONE,
    IMPELLER_HUB_ZONE,
    IMPELLER_SHROUD_ZONE,
    INBLOCK_HUB_ZONE,
    INBLOCK_SHROUD_ZONE,
    VOLUTE_INLET_WALL_ZONE,
    VOLUTE_WALL_ZONE,
)
"""Surfaces rendered in the mesh preview image."""

ROTATING_WALL_ZONES: Final[tuple[str, ...]] = (BLADE_ZONE, IMPELLER_HUB_ZONE, IMPELLER_SHROUD_ZONE)
"""Walls whose moment about the rotation axis makes up the shaft torque."""

ROTATION_AXIS_ORIGIN: Final[tuple[float, float, float]] = (0.0, 0.0, 0.0)
ROTATION_AXIS_DIRECTION: Final[tuple[float, float, float]] = (0.0, 0.0, 1.0)

# ----------------------------------------------------------------------------------------- Fluent object names ------

MESH_OBJECT_NAME: Final[str] = "mesh-1"
TURBO_INTERFACE_NAME: Final[str] = "imp-volute-interface"
MID_PLANE_SURFACE_NAME: Final[str] = "z_mid_plane"
CONTOUR_OBJECT_NAME: Final[str] = "static-pressure-contour"
Z_MID_PLANE: Final[float] = -0.015

HEAD_EXPRESSION_NAME: Final[str] = "head"
INLET_PRESSURE_REPORT: Final[str] = "p-in"
OUTLET_PRESSURE_REPORT: Final[str] = "p-out"
PUMP_HEAD_REPORT: Final[str] = "pump-head"
BLADE_PRESSURE_REPORT: Final[str] = "p-blade"
BLADE_TORQUE_REPORT: Final[str] = "blade-torque"

MOMENT_OUTPUT_TYPE: Final[str] = "Moment"
"""Preferred ``report_output_type`` for the torque report.

Fluent serves the legal values for this setting at run time, so the literal cannot be
verified statically. :func:`~...case_builder._create_report_definitions` only applies it
when the solver offers it, and otherwise keeps the solver default.
"""

OUTLET_PRESSURE_REPORT_FILE: Final[str] = "p-out-rfile"
PUMP_HEAD_REPORT_FILE: Final[str] = "pump-head-rfile"
OUTLET_PRESSURE_REPORT_FILE_NAME: Final[str] = "p-out-rfile.out"
PUMP_HEAD_REPORT_FILE_NAME: Final[str] = "pump-head-rfile.out"

# ---------------------------------------------------------------------------------------------------- Artefacts ----

CASE_FILE_NAME: Final[str] = "pump_volute_setup.cas.h5"
DATA_FILE_NAME: Final[str] = "pump_volute_setup.dat.h5"
"""Written by Fluent next to :data:`CASE_FILE_NAME` when the case is saved as ``case-data``."""
SOLVED_CASE_FILE_NAME: Final[str] = "pump_volute_setup_solved.cas.h5"
SOLVED_DATA_FILE_NAME: Final[str] = "pump_volute_setup_solved.dat.h5"
"""Written by Fluent next to :data:`SOLVED_CASE_FILE_NAME` when the case is saved as ``case-data``."""
SCENE_FILE_NAME: Final[str] = "pump_volute_setup.vtkhdf"
"""VTKHDF conversion of the setup case."""
SOLVED_SCENE_FILE_NAME: Final[str] = "pump_volute_setup_solved.vtkhdf"
"""VTKHDF conversion of the solved case."""
MESH_IMAGE_NAME: Final[str] = "pump-volute-mesh.png"
CONTOUR_IMAGE_NAME: Final[str] = "static-pressure-contour.png"

# ------------------------------------------------------------------------------------------------ Event streams ----

# GLOW owns the termination stream names: when a transaction sets ``enable_termination_event``,
# it publishes its final ``MethodState`` on a stream named after the method in URL form. These
# constants must therefore stay equal to the URL form of the method names.

BUILD_CASE_STREAM: Final[str] = "build-case"
"""Event stream on which GLOW publishes the final state of ``SetupStep.build_case``."""

RUN_SIMULATION_STREAM: Final[str] = "run-simulation"
"""Event stream on which GLOW publishes the final state of ``SolveStep.run_simulation``."""

BUILD_CASE_PROGRESS_STREAM: Final[str] = "build-case-progress"
"""Event stream carrying model-setup progress to the UI."""

RUN_SIMULATION_PROGRESS_STREAM: Final[str] = "run-simulation-progress"
"""Event stream carrying solve progress to the UI."""

BUILD_CASE_LOG_STREAM: Final[str] = "build-case-log"
"""Event stream carrying Fluent transcript lines from the model setup to the UI."""

RUN_SIMULATION_LOG_STREAM: Final[str] = "run-simulation-log"
"""Event stream carrying Fluent transcript lines from the solve to the UI."""

RUN_SIMULATION_HISTORY_STREAM: Final[str] = "run-simulation-history"
"""Event stream carrying the convergence history of the solve to the UI, while it runs."""

# ------------------------------------------------------------------------------------------ Transcript capture ----

LOG_FLUSH_INTERVAL_SECONDS: Final[float] = 1.0
"""How often buffered Fluent transcript lines are published to the UI."""

LOG_TAIL_LINES: Final[int] = 2000
"""Number of transcript lines retained. Older lines are dropped, keeping the field bounded."""

# ----------------------------------------------------------------------------------------- Defaults and ranges ------

DEFAULT_PROCESSOR_COUNT: Final[int] = 4
DEFAULT_IMPELLER_SPEED_RPM: Final[float] = 1450.0
DEFAULT_MASS_FLOW_RATE: Final[float] = 90.0
DEFAULT_ITERATION_COUNT: Final[int] = 200
DEFAULT_TIME_STEP_SCALE_FACTOR: Final[float] = 10.0

INLET_GAUGE_PRESSURE: Final[float] = -100.0
"""Gauge pressure applied at the pump inlet, in Pa. Not a user input.

The case is single-phase, constant-density water with no energy equation and no cavitation
model, so pressure enters the momentum equation only through its gradient. This value merely
pins the datum of an otherwise undetermined additive constant: shift it and the whole
pressure field shifts with it. Head and pressure rise are differences, and a uniform offset
contributes no net moment about the shaft axis, so head, torque, shaft power and efficiency
are all independent of it. Exposing it as an input would suggest an influence it does not
have. Taken from the reference workflow.
"""

PROCESSOR_COUNT_RANGE: Final[tuple[int, int]] = (1, 32)
IMPELLER_SPEED_RANGE: Final[tuple[float, float]] = (100.0, 3000.0)
MASS_FLOW_RATE_RANGE: Final[tuple[float, float]] = (1.0, 300.0)
ITERATION_COUNT_RANGE: Final[tuple[int, int]] = (1, 5000)
TIME_STEP_SCALE_FACTOR_RANGE: Final[tuple[float, float]] = (0.1, 100.0)

# -------------------------------------------------------------------------------------------------- Convergence ----

CONVERGENCE_WINDOW_FRACTION: Final[float] = 0.1
"""Fraction of the iteration history inspected when judging convergence."""

CONVERGENCE_MIN_SAMPLES: Final[int] = 10
"""Minimum number of samples required before convergence can be declared."""

CONVERGENCE_TOLERANCE: Final[float] = 0.005
"""Allowed peak-to-peak head variation, relative to the final head value."""

ITERATION_CHUNKS: Final[int] = 20
"""Number of chunks the solve is split into.

Each chunk boundary is a chance to report iteration progress and to publish the convergence
history read back from the report files, so the count sets how smoothly the live chart fills
in. Chunking has been verified not to perturb the solution: the head history shows no
discontinuity at a boundary.
"""

# ------------------------------------------------------------------------------------------- Session lifecycle ------

SOLVER_EXIT_WAIT_SECONDS: Final[int] = 120
"""How long to wait for the local Fluent processes to terminate before forcing them.

The BDM garbage collector deletes the method storage root as soon as the transaction returns,
which fails on Windows while Fluent still holds its transcript file open.
"""

# ------------------------------------------------------------------------------------------------------ Stages ------

SETUP_STAGES: Final[tuple[tuple[float, str], ...]] = (
    (0.00, "Launching Fluent"),
    (0.15, "Reading meshes"),
    (0.35, "Rendering mesh"),
    (0.55, "Configuring model"),
    (0.90, "Writing case"),
)

SOLVE_STAGES: Final[tuple[tuple[float, str], ...]] = (
    (0.00, "Launching Fluent"),
    (0.10, "Reading case"),
    (0.20, "Applying operating point"),
    (0.30, "Initializing"),
    (0.40, "Iterating"),
    (0.90, "Post-processing"),
    (0.97, "Saving results"),
)
