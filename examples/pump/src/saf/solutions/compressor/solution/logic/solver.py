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

"""Operating-point solve and post-processing for the pump frozen-rotor workflow.

The case built by :mod:`~...logic.case_builder` is read back, the duty point is applied,
the solve is run in chunks so progress can be reported, and the results are post-processed.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ansys.fluent.core as pyfluent

from saf.solutions.compressor.solution.logic.case_builder import ProgressCallback
from saf.solutions.compressor.solution.logic.constants import (
    BLADE_PRESSURE_REPORT,
    BLADE_TORQUE_REPORT,
    CONTOUR_IMAGE_NAME,
    CONTOUR_OBJECT_NAME,
    IMPELLER_CELL_ZONE,
    IMPELLER_SPEED_RANGE,
    INLET_GAUGE_PRESSURE,
    INLET_PRESSURE_REPORT,
    INLET_ZONE,
    ITERATION_CHUNKS,
    ITERATION_COUNT_RANGE,
    MASS_FLOW_RATE_RANGE,
    MID_PLANE_SURFACE_NAME,
    OUTLET_PRESSURE_REPORT,
    OUTLET_PRESSURE_REPORT_FILE_NAME,
    OUTLET_ZONE,
    PROCESSOR_COUNT_RANGE,
    PUMP_HEAD_REPORT_FILE_NAME,
    SOLVED_CASE_FILE_NAME,
    SOLVED_DATA_FILE_NAME,
    TIME_STEP_SCALE_FACTOR_RANGE,
    Z_MID_PLANE,
)
from saf.solutions.compressor.solution.logic.fluent_session import shutdown_solver
from saf.solutions.compressor.solution.logic.results import angular_velocity, parse_report_file
from saf.solutions.compressor.solution.logic.transcript import LogCallback, TranscriptForwarder
from saf.solutions.compressor.solution.logic.validation import validate_range

HistoryCallback = Callable[[list[tuple[int, float]], list[tuple[int, float]]], None]
"""Receives the head and outlet-pressure samples read back so far, after each chunk."""


@dataclass(frozen=True)
class OperatingPoint:
    """Everything the solve needs that is not already baked into the case."""

    impeller_speed_rpm: float
    mass_flow_rate: float
    iteration_count: int
    time_step_scale_factor: float
    processor_count: int


@dataclass(frozen=True)
class RawResults:
    """Unprocessed solver output. Derived quantities are computed by the step."""

    inlet_total_pressure_pa: float
    outlet_total_pressure_pa: float
    blade_pressure_pa: float
    blade_torque_nm: float
    contour_image_path: Path
    solved_case_path: Path
    solved_data_path: Path
    head_samples: list[tuple[int, float]]
    outlet_pressure_samples: list[tuple[int, float]]


def run_operating_point(
    case_path: Path,
    work_dir: Path,
    params: OperatingPoint,
    progress: ProgressCallback,
    log: LogCallback | None = None,
    history: HistoryCallback | None = None,
) -> RawResults:
    """Solve the case at one operating point and post-process the results.

    Parameters
    ----------
    case_path : Path
        Case file produced by :func:`~...logic.case_builder.build_case`.
    work_dir : Path
        Directory that receives the report files, contour image and solved case.
    params : OperatingPoint
        Operating point and solver settings.
    progress : ProgressCallback
        Progress reporter.
    log : LogCallback, optional
        Receives batches of Fluent console lines as they are produced.
    history : HistoryCallback, optional
        Receives the convergence samples read back after each iteration chunk, so the UI
        can draw the curve while the solve is still running.

    Returns
    -------
    RawResults
        Report values, convergence samples and artefact paths.

    Raises
    ------
    ValueError
        If any field of ``params`` falls outside its allowed range.
    """
    _validate(params)

    progress("Launching Fluent", 0.0)
    solver = pyfluent.launch_fluent(
        mode="solver",
        processor_count=params.processor_count,
        cleanup_on_exit=True,
        cwd=str(work_dir),
    )
    try:
        with TranscriptForwarder(log) as transcript:
            transcript.attach(solver)
            return _solve(solver, case_path, work_dir, params, progress, history)
    finally:
        shutdown_solver(solver)


def _solve(
    solver: Any,
    case_path: Path,
    work_dir: Path,
    params: OperatingPoint,
    progress: ProgressCallback,
    history: HistoryCallback | None = None,
) -> RawResults:
    """Drive an already launched solver session through one operating point.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    case_path : Path
        Case file to read back.
    work_dir : Path
        Directory that receives the report files, contour image and solved case.
    params : OperatingPoint
        Operating point and solver settings.
    progress : ProgressCallback
        Progress reporter.
    history : HistoryCallback, optional
        Receives the convergence samples read back after each iteration chunk.

    Returns
    -------
    RawResults
        Report values, convergence samples and artefact paths.
    """
    progress("Reading case", 0.10)
    solver.settings.file.read_case(file_name=str(case_path))

    progress("Applying operating point", 0.20)
    _apply_operating_point(solver, params)

    progress("Initializing", 0.30)
    initialization = solver.settings.solution.initialization
    initialization.reference_frame = "absolute"
    initialization.hybrid_init_options.general_settings.initialization_options.initial_pressure = True
    initialization.hybrid_initialize()

    _iterate(solver, work_dir, params, progress, history)

    progress("Post-processing", 0.90)
    contour_image_path = _render_contour(solver, work_dir)
    reports = {
        name: _compute_report(solver, name)
        for name in (INLET_PRESSURE_REPORT, OUTLET_PRESSURE_REPORT, BLADE_PRESSURE_REPORT, BLADE_TORQUE_REPORT)
    }

    progress("Saving results", 0.97)
    solved_case_path = work_dir / SOLVED_CASE_FILE_NAME
    solver.settings.file.write(file_type="case-data", file_name=str(solved_case_path))
    # Fluent derives the data file name from the case file name; it is not returned by the API.
    solved_data_path = work_dir / SOLVED_DATA_FILE_NAME

    progress("Results ready", 1.0)
    return RawResults(
        inlet_total_pressure_pa=reports[INLET_PRESSURE_REPORT],
        outlet_total_pressure_pa=reports[OUTLET_PRESSURE_REPORT],
        blade_pressure_pa=reports[BLADE_PRESSURE_REPORT],
        blade_torque_nm=reports[BLADE_TORQUE_REPORT],
        contour_image_path=contour_image_path,
        solved_case_path=solved_case_path,
        solved_data_path=solved_data_path,
        head_samples=_read_samples(work_dir / PUMP_HEAD_REPORT_FILE_NAME),
        outlet_pressure_samples=_read_samples(work_dir / OUTLET_PRESSURE_REPORT_FILE_NAME),
    )


def _validate(params: OperatingPoint) -> None:
    """Re-check every bound, because the GLOW API can be called without the UI.

    Parameters
    ----------
    params : OperatingPoint
        Operating point to check.

    Raises
    ------
    ValueError
        If any field falls outside its allowed range.
    """
    validate_range("impeller_speed_rpm", params.impeller_speed_rpm, IMPELLER_SPEED_RANGE)
    validate_range("mass_flow_rate", params.mass_flow_rate, MASS_FLOW_RATE_RANGE)
    validate_range("iteration_count", params.iteration_count, ITERATION_COUNT_RANGE)
    validate_range("time_step_scale_factor", params.time_step_scale_factor, TIME_STEP_SCALE_FACTOR_RANGE)
    validate_range("processor_count", params.processor_count, PROCESSOR_COUNT_RANGE)


def _apply_operating_point(solver: Any, params: OperatingPoint) -> None:
    """Write the boundary-condition values that define the duty point.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    params : OperatingPoint
        Operating point to apply.
    """
    impeller = solver.settings.setup.cell_zone_conditions.fluid[IMPELLER_CELL_ZONE]
    # ``mrf_omega.value`` is SI (rad/s), regardless of the "rev/min" display unit selected in
    # case_builder. PyFluent resolves the unit from a hard-coded SI table in ``solver/flunits.py``
    # ("angular-velocity" -> "radian s^-1"), which ``set_units`` cannot influence. Assigning the
    # raw rpm figure here would run the pump ~9.55x too slow.
    impeller.reference_frame.mrf_omega.value = angular_velocity(params.impeller_speed_rpm)

    # Only the datum of the pressure field, never an operating-point choice. See the
    # ``INLET_GAUGE_PRESSURE`` docstring for why it cannot change the reported performance.
    inlet = solver.settings.setup.boundary_conditions.pressure_inlet[INLET_ZONE]
    inlet.momentum.supersonic_or_initial_gauge_pressure.value = INLET_GAUGE_PRESSURE

    outlet = solver.settings.setup.boundary_conditions.mass_flow_outlet[OUTLET_ZONE]
    outlet.momentum.mass_flow_rate.value = params.mass_flow_rate


def _iterate(
    solver: Any,
    work_dir: Path,
    params: OperatingPoint,
    progress: ProgressCallback,
    history: HistoryCallback | None = None,
) -> None:
    """Run the solve in chunks so that iteration progress can be reported.

    Fluent appends to its report files as it iterates, so each chunk boundary is also a
    chance to read back the convergence samples written so far and hand them on. The parser
    skips any line that does not hold two numbers, so a half-written final line is harmless.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    work_dir : Path
        Directory Fluent writes its report files to.
    params : OperatingPoint
        Operating point, providing the iteration count and pseudo-time scale factor.
    progress : ProgressCallback
        Progress reporter.
    history : HistoryCallback, optional
        Receives the samples read back after each chunk.
    """
    run_calculation = solver.settings.solution.run_calculation
    run_calculation.pseudo_time_settings.time_step_method.time_step_size_scale_factor = params.time_step_scale_factor

    chunk_size = max(1, params.iteration_count // ITERATION_CHUNKS)
    completed = 0
    while completed < params.iteration_count:
        iterations = min(chunk_size, params.iteration_count - completed)
        run_calculation.iter_count = iterations
        run_calculation.calculate()
        completed += iterations
        progress(
            f"Iterating {completed}/{params.iteration_count}",
            0.40 + 0.50 * completed / params.iteration_count,
        )
        if history is not None:
            history(
                _read_samples(work_dir / PUMP_HEAD_REPORT_FILE_NAME),
                _read_samples(work_dir / OUTLET_PRESSURE_REPORT_FILE_NAME),
            )


def _render_contour(solver: Any, work_dir: Path) -> Path:
    """Render the mid-plane static pressure contour to a PNG and return its path.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    work_dir : Path
        Directory that receives the rendered image.

    Returns
    -------
    Path
        Path of the written contour image.
    """
    mid_plane = solver.settings.results.surfaces.plane_surface.create(name=MID_PLANE_SURFACE_NAME)
    mid_plane.method = "xy-plane"
    mid_plane.z = Z_MID_PLANE
    mid_plane.display()

    contour = solver.settings.results.graphics.contour.create(name=CONTOUR_OBJECT_NAME)
    contour.field = "pressure"
    contour.surfaces_list = [MID_PLANE_SURFACE_NAME]

    graphics = solver.settings.results.graphics
    graphics.picture.driver_options.hardcopy_format = "png"
    graphics.views.restore_view(view_name="front")
    contour.display()
    graphics.views.auto_scale()

    image_path = work_dir / CONTOUR_IMAGE_NAME
    graphics.picture.save_picture(file_name=str(image_path))
    return image_path


def _compute_report(solver: Any, name: str) -> float:
    """Evaluate a report definition and return its scalar value.

    Fluent returns a nested structure such as ``[{'p-in': [101325.0]}]``.

    Parameters
    ----------
    solver : Any
        Live PyFluent solver session.
    name : str
        Name of the report definition to evaluate.

    Returns
    -------
    float
        Scalar value of the report definition.
    """
    result = solver.settings.solution.report_definitions.compute(report_defs=[name])
    entry = result[0][name]
    if isinstance(entry, (list, tuple)):
        return float(entry[0])
    return float(entry)


def _read_samples(path: Path) -> list[tuple[int, float]]:
    """Return the samples from a report file, or an empty list if it was not written.

    Parameters
    ----------
    path : Path
        Path to the ``.out`` report file.

    Returns
    -------
    list[tuple[int, float]]
        Parsed ``(iteration, value)`` samples.
    """
    if not path.is_file():
        return []
    return parse_report_file(path)
