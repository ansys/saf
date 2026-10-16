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

"""Derived engineering quantities and Fluent report post-processing."""

import math
from pathlib import Path

from saf.solutions.compressor.solution.logic.constants import (
    CONVERGENCE_MIN_SAMPLES,
    CONVERGENCE_TOLERANCE,
    CONVERGENCE_WINDOW_FRACTION,
    DENSITY_WATER,
    GRAVITY,
)

_NEGLIGIBLE_POWER: float = 1e-9

# ------------------------------------------------------------------------------------------ Derived quantities ----


def angular_velocity(speed_rpm: float) -> float:
    """Convert a rotational speed from rev/min to rad/s.

    Parameters
    ----------
    speed_rpm : float
        Rotational speed, in rev/min.

    Returns
    -------
    float
        Angular velocity, in rad/s.
    """
    return speed_rpm * 2.0 * math.pi / 60.0


def volumetric_flow_rate(mass_flow_rate: float, density: float = DENSITY_WATER) -> float:
    """Convert a mass flow rate to a volumetric flow rate.

    Parameters
    ----------
    mass_flow_rate : float
        Mass flow rate, in kg/s.
    density : float, optional
        Fluid density, in kg/m^3.

    Returns
    -------
    float
        Volumetric flow rate, in m^3/s.
    """
    return mass_flow_rate / density


def pump_head(
    inlet_total_pressure: float,
    outlet_total_pressure: float,
    density: float = DENSITY_WATER,
    gravity: float = GRAVITY,
) -> float:
    """Return the pump head from the total pressure rise.

    Parameters
    ----------
    inlet_total_pressure : float
        Mass-averaged inlet total pressure, in Pa.
    outlet_total_pressure : float
        Mass-averaged outlet total pressure, in Pa.
    density : float, optional
        Fluid density, in kg/m^3.
    gravity : float, optional
        Gravitational acceleration, in m/s^2.

    Returns
    -------
    float
        Pump head, in m.
    """
    return (outlet_total_pressure - inlet_total_pressure) / (density * gravity)


def hydraulic_power(
    volumetric_flow: float,
    head: float,
    density: float = DENSITY_WATER,
    gravity: float = GRAVITY,
) -> float:
    """Return the hydraulic power delivered to the fluid.

    Parameters
    ----------
    volumetric_flow : float
        Volumetric flow rate, in m^3/s.
    head : float
        Pump head, in m.
    density : float, optional
        Fluid density, in kg/m^3.
    gravity : float, optional
        Gravitational acceleration, in m/s^2.

    Returns
    -------
    float
        Hydraulic power, in W.
    """
    return density * gravity * volumetric_flow * head


def shaft_power(torque: float, omega: float) -> float:
    """Return the mechanical power the shaft has to supply.

    Fluent's moment report gives the moment the *fluid* exerts on the impeller walls. The
    fluid resists being pushed around, so that moment opposes the imposed rotation and comes
    out negative for a positive omega: a converged run of this case reports about
    -207 N.m at 1450 rpm. The shaft supplies the equal and opposite reaction, hence the
    magnitude. Keeping the raw sign would hand back a negative shaft power, and with it a
    negative efficiency, which would say the pump is giving energy back to its motor.

    Parameters
    ----------
    torque : float
        Moment about the rotation axis as reported by Fluent, in N.m.
    omega : float
        Angular velocity, in rad/s.

    Returns
    -------
    float
        Shaft power, in W, always positive.
    """
    return abs(torque * omega)


def hydraulic_efficiency(hydraulic_power_w: float, shaft_power_w: float) -> float:
    """Return the hydraulic efficiency.

    Parameters
    ----------
    hydraulic_power_w : float
        Hydraulic power, in W.
    shaft_power_w : float
        Shaft power, in W.

    Returns
    -------
    float
        Efficiency as a fraction. Zero when the shaft power is negligible, so that a
        stalled or zero-speed case does not divide by zero.
    """
    if abs(shaft_power_w) < _NEGLIGIBLE_POWER:
        return 0.0
    return hydraulic_power_w / shaft_power_w


# --------------------------------------------------------------------------------------- Report post-processing ----


def parse_report_file(path: Path) -> list[tuple[int, float]]:
    """Parse a Fluent report file into ``(iteration, value)`` samples.

    Header lines written by Fluent are quoted or parenthesised and therefore fail to
    parse as numbers; they are skipped.

    Parameters
    ----------
    path : Path
        Path to the ``.out`` report file.

    Returns
    -------
    list[tuple[int, float]]
        Samples in file order. Empty if the file holds no data rows.
    """
    samples: list[tuple[int, float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        tokens = line.split()
        if len(tokens) < 2:
            continue
        try:
            iteration = int(tokens[0])
            value = float(tokens[1])
        except ValueError:
            continue
        samples.append((iteration, value))
    return samples


def build_convergence_history(
    head_samples: list[tuple[int, float]],
    outlet_pressure_samples: list[tuple[int, float]],
) -> list[dict[str, float]]:
    """Join the head and outlet pressure series on the iteration number.

    Parameters
    ----------
    head_samples : list[tuple[int, float]]
        ``(iteration, head)`` samples, in m.
    outlet_pressure_samples : list[tuple[int, float]]
        ``(iteration, outlet total pressure)`` samples, in Pa.

    Returns
    -------
    list[dict[str, float]]
        One record per head sample, ready for ``dmc.LineChart``.
    """
    outlet_by_iteration = dict(outlet_pressure_samples)
    return [
        {
            "iteration": iteration,
            "head": head,
            "outlet_total_pressure": outlet_by_iteration.get(iteration, 0.0),
        }
        for iteration, head in head_samples
    ]


def is_converged(head_samples: list[tuple[int, float]]) -> bool:
    """Judge convergence from the flatness of the tail of the head history.

    Convergence is assessed on head rather than on residuals because head is the
    quantity the user cares about and the report file is trivial to parse.

    Parameters
    ----------
    head_samples : list[tuple[int, float]]
        ``(iteration, head)`` samples, in m.

    Returns
    -------
    bool
        True when the peak-to-peak head variation over the tail window is below the
        configured tolerance, relative to the final head value.
    """
    if len(head_samples) < CONVERGENCE_MIN_SAMPLES:
        return False

    window = max(CONVERGENCE_MIN_SAMPLES, int(len(head_samples) * CONVERGENCE_WINDOW_FRACTION))
    window = min(window, len(head_samples))
    values = [value for _, value in head_samples[-window:]]

    final_value = values[-1]
    if abs(final_value) < 1e-12:
        return False

    return (max(values) - min(values)) / abs(final_value) < CONVERGENCE_TOLERANCE

