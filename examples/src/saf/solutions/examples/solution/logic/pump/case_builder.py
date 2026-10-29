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

"""Operating-point-independent Fluent setup for the pump frozen-rotor workflow.

Everything configured here is reused for every operating point, so it is built once
and persisted as a case file.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ansys.fluent.core as pyfluent
from ansys.fluent.core import examples

from saf.solutions.examples.solution.logic.pump.constants import (
    BLADE_PRESSURE_REPORT,
    BLADE_TORQUE_REPORT,
    BLADE_ZONE,
    CASE_FILE_NAME,
    DATA_FILE_NAME,
    DENSITY_WATER,
    FLUID_MATERIAL,
    GRAVITY,
    HEAD_EXPRESSION_NAME,
    IMPELLER_CELL_ZONE,
    IMPELLER_HUB_ZONE,
    IMPELLER_INTERFACE_ZONE,
    IMPELLER_MESH_FILE,
    INBLOCK_SHROUD_ZONE,
    INLET_PRESSURE_REPORT,
    INLET_ZONE,
    MESH_DISPLAY_SURFACES,
    MESH_IMAGE_NAME,
    MESH_OBJECT_NAME,
    MESH_REPOSITORY,
    MOMENT_OUTPUT_TYPE,
    OUTLET_PRESSURE_REPORT,
    OUTLET_PRESSURE_REPORT_FILE,
    OUTLET_PRESSURE_REPORT_FILE_NAME,
    OUTLET_ZONE,
    PROCESSOR_COUNT_RANGE,
    PUMP_HEAD_REPORT,
    PUMP_HEAD_REPORT_FILE,
    PUMP_HEAD_REPORT_FILE_NAME,
    ROTATING_WALL_ZONES,
    ROTATION_AXIS_DIRECTION,
    ROTATION_AXIS_ORIGIN,
    TURBO_INTERFACE_NAME,
    VOLUTE_CELL_ZONE,
    VOLUTE_INTERFACE_ZONE,
    VOLUTE_MESH_FILE,
)
from saf.solutions.examples.solution.logic.pump.fluent_session import shutdown_solver
from saf.solutions.examples.solution.logic.pump.transcript import LogCallback, TranscriptForwarder
from saf.solutions.examples.solution.logic.pump.validation import validate_range

ProgressCallback = Callable[[str, float], None]
"""Called with a stage label and a 0-1 progress fraction."""


@dataclass(frozen=True)
class CaseArtifacts:
    """Files and metadata produced by :func:`build_case`."""

    case_path: Path
    data_path: Path
    mesh_image_path: Path
    zone_names: list[str]


def build_case(
    work_dir: Path,
    processor_count: int,
    progress: ProgressCallback,
    log: LogCallback | None = None,
) -> CaseArtifacts:
    """Build and persist the operating-point-independent Fluent case.

    Parameters
    ----------
    work_dir : Path
        Directory that receives the meshes, the case file and the mesh image.
    processor_count : int
        Number of solver processes.
    progress : ProgressCallback
        Progress reporter.
    log : LogCallback, optional
        Receives batches of Fluent console lines as they are produced.

    Returns
    -------
    CaseArtifacts
        Paths to the written case and mesh image, plus the detected zone names.

    Raises
    ------
    ValueError
        If ``processor_count`` falls outside :data:`PROCESSOR_COUNT_RANGE`.
    """
    validate_range("processor_count", processor_count, PROCESSOR_COUNT_RANGE)

    progress("Launching Fluent", 0.0)
    solver = pyfluent.launch_fluent(
        mode="solver",
        processor_count=processor_count,
        cleanup_on_exit=True,
        cwd=str(work_dir),
    )
    try:
        with TranscriptForwarder(log) as transcript:
            transcript.attach(solver)
            return _build(solver, work_dir, progress)
    finally:
        shutdown_solver(solver)


def _build(solver: Any, work_dir: Path, progress: ProgressCallback) -> CaseArtifacts:
    """Drive the setup of an already launched solver session.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    work_dir : Path
        Directory that receives the meshes, the case file and the mesh image.
    progress : ProgressCallback
        Progress reporter.

    Returns
    -------
    CaseArtifacts
        Paths to the written case and mesh image, plus the detected zone names.
    """
    progress("Reading meshes", 0.15)
    impeller_mesh = examples.download_file(IMPELLER_MESH_FILE, MESH_REPOSITORY, save_path=str(work_dir))
    volute_mesh = examples.download_file(VOLUTE_MESH_FILE, MESH_REPOSITORY, save_path=str(work_dir))
    solver.settings.file.read_mesh(file_name=impeller_mesh)
    solver.settings.mesh.modify_zones.append_mesh(file_name=volute_mesh)

    # Rendered before _configure_model on purpose, to match the reference script, which saves the
    # mesh picture (frozen_rotor_workflow.py:170) while the outlet zone is still typed as a
    # mass-flow-inlet, and only converts it with set_zone_type afterwards (:258). Rendering after
    # _configure_model draws that zone as an outlet instead, which flips the boundary arrows and
    # recolours them red. Purely cosmetic -- both orders solve identical boundary conditions -- but
    # kept faithful so the image is byte-comparable with the reference.
    progress("Rendering mesh", 0.35)
    mesh_image_path = _render_mesh(solver, work_dir)

    progress("Configuring model", 0.55)
    _configure_model(solver)
    _create_report_definitions(solver)

    zone_names = sorted(solver.settings.results.graphics.mesh[MESH_OBJECT_NAME].surfaces_list.allowed_values())

    progress("Writing case", 0.90)
    case_path = work_dir / CASE_FILE_NAME
    solver.settings.solution.initialization.reference_frame = "absolute"
    initialization_options = solver.settings.solution.initialization.hybrid_init_options.general_settings
    initialization_options.initialization_options.initial_pressure = True
    solver.settings.solution.initialization.hybrid_initialize()
    solver.settings.file.write(file_type="case-data", file_name=str(case_path))
    # Fluent derives the data file name from the case file name; it is not returned by the API.
    data_path = work_dir / DATA_FILE_NAME

    progress("Case ready", 1.0)
    return CaseArtifacts(
        case_path=case_path, data_path=data_path, mesh_image_path=mesh_image_path, zone_names=zone_names
    )


def _configure_model(solver: Any) -> None:
    """Apply units, turbulence model, materials, zones and solver methods.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    """
    # Display-only: this changes what the Fluent console and GUI show for angular velocity.
    # It does NOT change the unit of values assigned through the settings API, which are always
    # SI. See the rad/s note in solver._apply_operating_point before changing either.
    solver.settings.setup.general.units.set_units(quantity="angular-velocity", units_name="rev/min")

    viscous = solver.settings.setup.models.viscous
    viscous.model = "k-omega"
    viscous.k_omega_model = "sst"

    solver.settings.setup.materials.database.copy_by_name(type="fluid", name=FLUID_MATERIAL)

    impeller = solver.settings.setup.cell_zone_conditions.fluid[IMPELLER_CELL_ZONE]
    impeller.general.material = FLUID_MATERIAL
    impeller.reference_frame.reference_frame_axis_origin = list(ROTATION_AXIS_ORIGIN)
    impeller.reference_frame.reference_frame_axis_direction = list(ROTATION_AXIS_DIRECTION)
    impeller.reference_frame.frame_motion = True
    # mrf_omega belongs to the operating point and is applied in solver.run_operating_point.

    volute = solver.settings.setup.cell_zone_conditions.fluid[VOLUTE_CELL_ZONE]
    volute.general.material = FLUID_MATERIAL

    impeller_hub = solver.settings.setup.boundary_conditions.wall[IMPELLER_HUB_ZONE].momentum
    impeller_hub.wall_motion = "Moving Wall"
    impeller_hub.relative = "Relative to Adjacent Cell Zone"
    impeller_hub.velocity_spec = "Rotational"

    inblock_shroud = solver.settings.setup.boundary_conditions.wall[INBLOCK_SHROUD_ZONE].momentum
    inblock_shroud.wall_motion = "Moving Wall"
    inblock_shroud.relative = "Absolute"
    inblock_shroud.velocity_spec = "Rotational"

    solver.settings.setup.boundary_conditions.set_zone_type(zone_list=[OUTLET_ZONE], new_type="mass-flow-outlet")

    solver.settings.setup.turbo_models.enabled = True
    solver.settings.setup.mesh_interfaces.turbo_create.create(
        adjacent_cell_zone_1=IMPELLER_CELL_ZONE,
        adjacent_cell_zone_2=VOLUTE_CELL_ZONE,
        mesh_interface_name=TURBO_INTERFACE_NAME,
        turbo_choice="No-Pitch-Scale",
        zone1=IMPELLER_INTERFACE_ZONE,
        zone2=VOLUTE_INTERFACE_ZONE,
    )

    methods = solver.settings.solution.methods
    methods.spatial_discretization.gradient_scheme = "green-gauss-node-based"
    methods.high_order_term_relaxation.enable = True


def _create_report_definitions(solver: Any) -> None:
    """Create the surface, expression and moment reports plus their report files.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    """
    report_definitions = solver.settings.solution.report_definitions

    outlet_pressure = report_definitions.surface.create(OUTLET_PRESSURE_REPORT)
    outlet_pressure.report_type = "surface-massavg"
    outlet_pressure.surface_names = [OUTLET_ZONE]
    outlet_pressure.field = "total-pressure"
    outlet_pressure.per_surface = False

    inlet_pressure = report_definitions.surface.create(INLET_PRESSURE_REPORT)
    inlet_pressure.report_type = "surface-massavg"
    inlet_pressure.surface_names = [INLET_ZONE]
    inlet_pressure.field = "total-pressure"
    inlet_pressure.per_surface = False

    blade_pressure = report_definitions.surface.create(BLADE_PRESSURE_REPORT)
    blade_pressure.report_type = "surface-massavg"
    blade_pressure.surface_names = [BLADE_ZONE]
    blade_pressure.field = "pressure"
    blade_pressure.per_surface = False

    # Torque about the rotation axis, needed for shaft power and efficiency.
    # The property names below are verified against the generated 2025 R2 settings API and are
    # stable from 2024 R2 to 2027 R1. ``report_output_type`` is the exception: Fluent serves its
    # legal values at run time, so it is applied only when the solver actually offers it.
    blade_torque = report_definitions.moment.create(BLADE_TORQUE_REPORT)
    blade_torque.zones = list(ROTATING_WALL_ZONES)
    blade_torque.mom_center = list(ROTATION_AXIS_ORIGIN)
    blade_torque.mom_axis = list(ROTATION_AXIS_DIRECTION)
    if MOMENT_OUTPUT_TYPE in blade_torque.report_output_type.allowed_values():
        blade_torque.report_output_type = MOMENT_OUTPUT_TYPE

    # Built from the density constant so the expression cannot drift out of sync.
    head_expression = solver.settings.setup.named_expressions.create(HEAD_EXPRESSION_NAME)
    head_expression.definition = (
        f"(({{{OUTLET_PRESSURE_REPORT}}} - {{{INLET_PRESSURE_REPORT}}}) "
        f"/ ({DENSITY_WATER} [kg/m^3] * {GRAVITY}[m/s^2]))"
    )
    head_expression.output_parameter = True

    pump_head_report = report_definitions.single_valued_expression.create(PUMP_HEAD_REPORT)
    pump_head_report.definition = HEAD_EXPRESSION_NAME

    monitor = solver.settings.solution.monitor
    monitor.report_plots.create(f"{OUTLET_PRESSURE_REPORT}-rplot").report_defs = OUTLET_PRESSURE_REPORT
    monitor.report_plots.create(f"{PUMP_HEAD_REPORT}-rplot").report_defs = PUMP_HEAD_REPORT

    outlet_report_file = monitor.report_files.create(OUTLET_PRESSURE_REPORT_FILE)
    outlet_report_file.report_defs = OUTLET_PRESSURE_REPORT
    outlet_report_file.file_name = OUTLET_PRESSURE_REPORT_FILE_NAME

    head_report_file = monitor.report_files.create(PUMP_HEAD_REPORT_FILE)
    head_report_file.report_defs = PUMP_HEAD_REPORT
    head_report_file.file_name = PUMP_HEAD_REPORT_FILE_NAME


def _render_mesh(solver: Any, work_dir: Path) -> Path:
    """Render the mesh to a PNG and return its path.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    work_dir : Path
        Directory that receives the rendered image.

    Returns
    -------
    Path
        Path of the written mesh image.
    """
    graphics = solver.settings.results.graphics

    mesh_object = graphics.mesh.create(name=MESH_OBJECT_NAME)
    mesh_object.surfaces_list = list(MESH_DISPLAY_SURFACES)
    mesh_object.options.edges = True

    graphics.picture.driver_options.hardcopy_format = "png"
    graphics.views.restore_view(view_name="front")
    mesh_object.display()
    graphics.views.auto_scale()

    image_path = work_dir / MESH_IMAGE_NAME
    graphics.picture.save_picture(file_name=str(image_path))
    return image_path
