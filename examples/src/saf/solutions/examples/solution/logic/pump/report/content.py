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

"""Text and tables of the pump report.

Everything here is plain Python returning HTML fragments, with no ADR dependency, so the
wording and the numbers can be tested without an Ansys installation.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import html

from saf.solutions.examples.solution.logic.pump.constants import (
    CONVERGENCE_TOLERANCE,
    CONVERGENCE_WINDOW_FRACTION,
    DENSITY_WATER,
    INLET_GAUGE_PRESSURE,
    VISCOSITY_WATER,
)


@dataclass(frozen=True)
class PumpReportData:
    """Operating point and results of one solve, as reported."""

    project_name: str
    impeller_speed_rpm: float
    mass_flow_rate: float
    iteration_count: int
    time_step_scale_factor: float
    processor_count: int
    converged: bool
    pump_head_m: float
    hydraulic_efficiency: float
    """Fraction, not percent."""
    shaft_power_w: float
    pressure_rise_pa: float
    blade_torque_nm: float
    volumetric_flow_m3h: float
    inlet_total_pressure_pa: float
    outlet_total_pressure_pa: float
    blade_pressure_pa: float
    convergence_history: tuple[dict[str, float], ...] = ()
    """``iteration`` / ``head`` / ``outlet_total_pressure`` samples of the solve."""


@dataclass(frozen=True)
class ConvergenceSeries:
    """Convergence history split into one sequence per plotted quantity."""

    iterations: list[float]
    head_m: list[float]
    outlet_total_pressure_pa: list[float]


def html_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Return an HTML table. Every cell is escaped."""
    head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table class="table table-sm"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def problem_description() -> str:
    """Describe the engineering problem the solution answers."""
    return (
        "<p>A centrifugal water pump made of an impeller and a volute is simulated with Ansys Fluent "
        "at a single operating point. The impeller speed and the mass flow rate set the duty point; "
        "the simulation returns the head the pump delivers, the shaft power it absorbs and its "
        "hydraulic efficiency.</p>"
    )


def operating_point_rows(data: PumpReportData) -> list[tuple[str, str, str]]:
    """Rows (quantity, value, unit) of the operating point and solver settings."""
    return [
        ("Impeller speed", f"{data.impeller_speed_rpm:.0f}", "rpm"),
        ("Mass flow rate", f"{data.mass_flow_rate:.2f}", "kg/s"),
        ("Iteration count", f"{data.iteration_count:d}", "-"),
        ("Pseudo time step scale factor", f"{data.time_step_scale_factor:g}", "-"),
        ("Processor count", f"{data.processor_count:d}", "-"),
    ]


def assumption_rows() -> list[tuple[str, str]]:
    """Rows (topic, assumption) of the modelling assumptions."""
    return [
        ("Flow regime", "Steady state, frozen rotor: the impeller zone rotates in a moving reference frame (MRF)."),
        ("Turbulence", "k-ω SST model."),
        (
            "Fluid",
            f"Liquid water, single phase and incompressible: ρ = {DENSITY_WATER:g} kg/m³, "
            f"μ = {VISCOSITY_WATER:g} kg/(m·s). No energy equation, no cavitation model.",
        ),
        ("Rotor-stator coupling", "Impeller and volute joined by a turbo interface without pitch scaling."),
        ("Inlet", f"Pressure inlet at {INLET_GAUGE_PRESSURE:g} Pa gauge. It only sets the pressure datum."),
        ("Outlet", "Mass flow outlet carrying the requested mass flow rate."),
        (
            "Convergence",
            f"Converged when the head varies by less than {CONVERGENCE_TOLERANCE:.1%} over the last "
            f"{CONVERGENCE_WINDOW_FRACTION:.0%} of the iterations.",
        ),
    ]


def convergence_summary(data: PumpReportData) -> str:
    """Return a short HTML verdict on the convergence of the solve."""
    if data.converged:
        return (
            '<p><strong style="color:#2b8a3e">Converged.</strong> '
            f"The pump head settled within {data.iteration_count} iterations.</p>"
        )
    return (
        '<p><strong style="color:#c92a2a">Not converged.</strong> '
        f"The pump head was still varying after {data.iteration_count} iterations. "
        "Treat the results below with caution, or run more iterations.</p>"
    )


def convergence_series(data: PumpReportData) -> ConvergenceSeries | None:
    """Return the convergence history as plot series, or ``None`` when none was recorded."""
    samples = sorted(data.convergence_history, key=lambda sample: sample["iteration"])
    if not samples:
        return None
    return ConvergenceSeries(
        iterations=[float(sample["iteration"]) for sample in samples],
        head_m=[float(sample["head"]) for sample in samples],
        outlet_total_pressure_pa=[float(sample["outlet_total_pressure"]) for sample in samples],
    )


def key_result_rows(data: PumpReportData) -> list[tuple[str, str, str]]:
    """Rows (quantity, value, unit) of the headline performance figures."""
    return [
        ("Pump head", f"{data.pump_head_m:.2f}", "m"),
        ("Hydraulic efficiency", f"{data.hydraulic_efficiency * 100:.1f}", "%"),
        ("Shaft power", f"{data.shaft_power_w / 1000:.2f}", "kW"),
    ]


def secondary_result_rows(data: PumpReportData) -> list[tuple[str, str, str]]:
    """Rows (quantity, value, unit) of the supporting results."""
    return [
        ("Total pressure rise", f"{data.pressure_rise_pa / 1000:.2f}", "kPa"),
        ("Blade torque", f"{data.blade_torque_nm:.2f}", "N·m"),
        ("Volumetric flow rate", f"{data.volumetric_flow_m3h:.1f}", "m³/h"),
        ("Inlet total pressure", f"{data.inlet_total_pressure_pa:.0f}", "Pa"),
        ("Outlet total pressure", f"{data.outlet_total_pressure_pa:.0f}", "Pa"),
        ("Blade pressure", f"{data.blade_pressure_pa:.0f}", "Pa"),
    ]
