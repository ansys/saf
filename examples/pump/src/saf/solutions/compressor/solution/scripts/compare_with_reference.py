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

"""Run the refactored logic layer exactly as the reference script runs.

``frozen_rotor_workflow.py`` prints no numbers: its only quantitative output is the
pair of report files Fluent writes during ``calculate()``. This harness drives the
same workflow through :func:`build_case` and :func:`run_operating_point`, then logs
the values so the two can be compared.

With no arguments the operating point is identical to the reference script
(1450 rev/min, 90 kg/s, -100 Pa, 200 iterations, scale factor 10, 4 processes).

Usage
-----
Full comparison run, matching the reference::

    saf execute compressor "python src/saf/solutions/compressor/solution/scripts/compare_with_reference.py --work-dir runs/refactored"

Quick smoke run of a few iterations::

    saf execute compressor "python src/saf/solutions/compressor/solution/scripts/compare_with_reference.py --work-dir runs/smoke --iterations 5"

Compare against a directory holding the reference script's own report files::

    saf execute compressor "python src/saf/solutions/compressor/solution/scripts/compare_with_reference.py --work-dir runs/refactored --compare-to src/saf/solutions/compressor/solution/logic"
"""

import argparse
import logging
from pathlib import Path
import sys
import time

from saf.solutions.compressor.solution.logic.case_builder import build_case
from saf.solutions.compressor.solution.logic.constants import (
    DEFAULT_IMPELLER_SPEED_RPM,
    DEFAULT_ITERATION_COUNT,
    DEFAULT_MASS_FLOW_RATE,
    DEFAULT_PROCESSOR_COUNT,
    DEFAULT_TIME_STEP_SCALE_FACTOR,
    INLET_GAUGE_PRESSURE,
    PUMP_HEAD_REPORT_FILE_NAME,
)
from saf.solutions.compressor.solution.logic.results import (
    angular_velocity,
    hydraulic_efficiency,
    hydraulic_power,
    is_converged,
    parse_report_file,
    pump_head,
    shaft_power,
    volumetric_flow_rate,
)
from saf.solutions.compressor.solution.logic.solver import OperatingPoint, run_operating_point

_SECONDS_PER_HOUR = 3600.0

logger = logging.getLogger(__name__)


def _progress(stage: str, fraction: float) -> None:
    """Log a progress line, mirroring what the UI shows as a notification."""
    logger.info("  [%5.1f%%] %s", fraction * 100, stage)


def _row(label: str, value: str, unit: str = "") -> str:
    """Format one line of the results table."""
    return f"  {label:<34}{value:>18} {unit}"


def _heading(title: str) -> None:
    """Log a section heading."""
    logger.info("")
    logger.info(title)
    logger.info("-" * 74)


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Run the refactored pump frozen-rotor logic and print comparable results.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        required=True,
        help="Directory for meshes, case files, report files and images. Created if absent.",
    )
    parser.add_argument("--processors", type=int, default=DEFAULT_PROCESSOR_COUNT)
    parser.add_argument("--speed", type=float, default=DEFAULT_IMPELLER_SPEED_RPM, help="Impeller speed, rev/min.")
    parser.add_argument("--mass-flow", type=float, default=DEFAULT_MASS_FLOW_RATE, help="Mass flow rate, kg/s.")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATION_COUNT)
    parser.add_argument("--time-step-scale", type=float, default=DEFAULT_TIME_STEP_SCALE_FACTOR)
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse the case file already present in the work directory instead of rebuilding it.",
    )
    parser.add_argument(
        "--compare-to",
        type=Path,
        default=None,
        help="Directory holding the reference script's report files, for a side-by-side head comparison.",
    )
    return parser.parse_args(argv)


def _report_configuration(arguments: argparse.Namespace) -> None:
    """Echo the operating point, including the rad/s value Fluent actually receives."""
    omega = angular_velocity(arguments.speed)
    _heading("Operating point")
    logger.info(_row("Impeller speed", f"{arguments.speed:.1f}", "rev/min"))
    logger.info(_row("  as angular velocity", f"{omega:.4f}", "rad/s"))
    logger.info(_row("Mass flow rate", f"{arguments.mass_flow:.1f}", "kg/s"))
    logger.info(_row("Inlet gauge pressure (fixed)", f"{INLET_GAUGE_PRESSURE:.1f}", "Pa"))
    logger.info(_row("Iterations", f"{arguments.iterations}", ""))
    logger.info(_row("Pseudo-time scale factor", f"{arguments.time_step_scale:.1f}", ""))
    logger.info(_row("Processor count", f"{arguments.processors}", ""))

    if arguments.iterations == DEFAULT_ITERATION_COUNT and arguments.speed == DEFAULT_IMPELLER_SPEED_RPM:
        logger.info("")
        logger.info("  This matches the reference script exactly.")


def _report_results(raw, arguments: argparse.Namespace) -> None:
    """Print the raw reports and every derived engineering quantity."""
    _heading("Raw Fluent reports")
    logger.info(_row("Inlet total pressure  (p-in)", f"{raw.inlet_total_pressure_pa:.3f}", "Pa"))
    logger.info(_row("Outlet total pressure (p-out)", f"{raw.outlet_total_pressure_pa:.3f}", "Pa"))
    logger.info(_row("Blade surface pressure (p-blade)", f"{raw.blade_pressure_pa:.3f}", "Pa"))
    logger.info(_row("Blade torque", f"{raw.blade_torque_nm:.4f}", "N.m"))

    head = pump_head(raw.inlet_total_pressure_pa, raw.outlet_total_pressure_pa)
    flow = volumetric_flow_rate(arguments.mass_flow)
    omega = angular_velocity(arguments.speed)
    power_hydraulic = hydraulic_power(flow, head)
    power_shaft = shaft_power(raw.blade_torque_nm, omega)

    _heading("Derived quantities")
    logger.info(_row("Pump head", f"{head:.4f}", "m"))
    logger.info(_row("Volumetric flow", f"{flow * _SECONDS_PER_HOUR:.2f}", "m3/h"))
    logger.info(_row("Pressure rise", f"{raw.outlet_total_pressure_pa - raw.inlet_total_pressure_pa:.3f}", "Pa"))
    logger.info(_row("Hydraulic power", f"{power_hydraulic:.2f}", "W"))
    logger.info(_row("Shaft power", f"{power_shaft:.2f}", "W"))
    logger.info(_row("Hydraulic efficiency", f"{hydraulic_efficiency(power_hydraulic, power_shaft) * 100:.2f}", "%"))

    _heading("Convergence")
    logger.info(_row("Head samples captured", f"{len(raw.head_samples)}", ""))
    logger.info(_row("Outlet pressure samples", f"{len(raw.outlet_pressure_samples)}", ""))
    logger.info(_row("Converged", "yes" if is_converged(raw.head_samples) else "NO", ""))

    if raw.head_samples:
        final_iteration, final_head = raw.head_samples[-1]
        logger.info(_row(f"Head at iteration {final_iteration}", f"{final_head:.4f}", "m"))
        # Cross-check: the expression report and the surface reports are computed by two
        # independent routes and must agree. A mismatch means one of them is misconfigured.
        logger.info(_row("  vs head from p-in/p-out", f"{head:.4f}", "m"))
        logger.info(_row("  difference", f"{abs(final_head - head):.6f}", "m"))


def _compare_with_reference(reference_dir: Path, raw) -> None:
    """Diff our head history against the reference script's report file, if present."""
    reference_report = reference_dir / PUMP_HEAD_REPORT_FILE_NAME
    _heading(f"Comparison with {reference_report}")

    if not reference_report.is_file():
        logger.warning("  Reference report file not found. Run frozen_rotor_workflow.py first,")
        logger.warning("  then point --compare-to at the directory holding its output.")
        return

    reference_samples = parse_report_file(reference_report)
    if not reference_samples or not raw.head_samples:
        logger.warning("  One of the two runs produced no head samples; nothing to compare.")
        return

    reference_final = reference_samples[-1][1]
    ours_final = raw.head_samples[-1][1]
    difference = ours_final - reference_final
    relative = abs(difference) / abs(reference_final) * 100.0 if reference_final else float("inf")

    logger.info(_row("Reference final head", f"{reference_final:.4f}", "m"))
    logger.info(_row("Refactored final head", f"{ours_final:.4f}", "m"))
    logger.info(_row("Difference", f"{difference:+.4f}", "m"))
    logger.info(_row("Relative difference", f"{relative:.3f}", "%"))
    logger.info(_row("Reference sample count", f"{len(reference_samples)}", ""))
    logger.info(_row("Refactored sample count", f"{len(raw.head_samples)}", ""))


def main(argv: list[str] | None = None) -> int:
    """Run the workflow and print a comparison report."""
    arguments = _parse_arguments(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

    work_dir: Path = arguments.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 74)
    logger.info("Pump frozen-rotor workflow - refactored logic layer")
    logger.info("=" * 74)
    logger.info("Work directory: %s", work_dir)
    _report_configuration(arguments)

    started = time.monotonic()

    _heading("Phase 1 - building the case")
    case_path = work_dir / "pump_volute_setup.cas.h5"
    if arguments.skip_build:
        if not case_path.is_file():
            logger.error("--skip-build was given but %s does not exist.", case_path)
            return 1
        logger.info("  Reusing existing case file: %s", case_path)
    else:
        artifacts = build_case(work_dir, arguments.processors, _progress)
        case_path = artifacts.case_path
        logger.info("")
        logger.info("  Case file:  %s", artifacts.case_path)
        logger.info("  Mesh image: %s", artifacts.mesh_image_path)
        logger.info("  Zones detected: %d", len(artifacts.zone_names))

    build_finished = time.monotonic()

    _heading("Phase 2 - solving the operating point")
    params = OperatingPoint(
        impeller_speed_rpm=arguments.speed,
        mass_flow_rate=arguments.mass_flow,
        iteration_count=arguments.iterations,
        time_step_scale_factor=arguments.time_step_scale,
        processor_count=arguments.processors,
    )
    raw = run_operating_point(case_path, work_dir, params, _progress)
    solve_finished = time.monotonic()

    _report_results(raw, arguments)

    _heading("Artefacts")
    logger.info("  Solved case:   %s", raw.solved_case_path)
    logger.info("  Contour image: %s", raw.contour_image_path)

    _heading("Timing")
    logger.info(_row("Case build", f"{build_finished - started:.1f}", "s"))
    logger.info(_row("Solve", f"{solve_finished - build_finished:.1f}", "s"))
    logger.info(_row("Total", f"{solve_finished - started:.1f}", "s"))

    if arguments.compare_to is not None:
        _compare_with_reference(arguments.compare_to.resolve(), raw)

    logger.info("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
