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

import math

import pytest

from saf.solutions.examples.solution.logic.pump.results import (
    angular_velocity,
    hydraulic_efficiency,
    hydraulic_power,
    pump_head,
    shaft_power,
    volumetric_flow_rate,
)


def test_angular_velocity_converts_rpm_to_rad_per_second():
    assert angular_velocity(1450.0) == pytest.approx(1450.0 * 2.0 * math.pi / 60.0)
    assert angular_velocity(1450.0) == pytest.approx(151.8436, abs=1e-4)


def test_angular_velocity_of_zero_speed_is_zero():
    assert angular_velocity(0.0) == 0.0


def test_volumetric_flow_rate_divides_mass_flow_by_density():
    assert volumetric_flow_rate(998.2) == pytest.approx(1.0)
    assert volumetric_flow_rate(90.0) == pytest.approx(90.0 / 998.2)


def test_pump_head_uses_total_pressure_difference():
    # A 98 062 Pa rise in water is exactly 10 m of head.
    head = pump_head(inlet_total_pressure=0.0, outlet_total_pressure=998.2 * 9.81 * 10.0)
    assert head == pytest.approx(10.0)


def test_pump_head_is_negative_when_outlet_pressure_is_lower():
    assert pump_head(inlet_total_pressure=1000.0, outlet_total_pressure=0.0) < 0.0


def test_hydraulic_power_is_rho_g_q_h():
    assert hydraulic_power(volumetric_flow=0.1, head=10.0) == pytest.approx(998.2 * 9.81 * 0.1 * 10.0)


def test_shaft_power_is_torque_times_omega():
    assert shaft_power(torque=50.0, omega=151.8436) == pytest.approx(7592.18, abs=1e-2)


def test_shaft_power_ignores_the_sign_of_the_fluid_moment():
    # Fluent reports the moment of the fluid on the blades, which opposes the rotation it is
    # driven at. The shaft still supplies power rather than absorbing it.
    assert shaft_power(torque=-207.0, omega=151.8436) == pytest.approx(31431.6, abs=1e-1)


def test_hydraulic_efficiency_is_the_power_ratio():
    assert hydraulic_efficiency(hydraulic_power_w=7500.0, shaft_power_w=10000.0) == pytest.approx(0.75)


def test_hydraulic_efficiency_is_zero_when_shaft_power_is_negligible():
    assert hydraulic_efficiency(hydraulic_power_w=7500.0, shaft_power_w=0.0) == 0.0
    assert hydraulic_efficiency(hydraulic_power_w=7500.0, shaft_power_w=1e-12) == 0.0
