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
from unittest.mock import MagicMock

import pytest

from saf.solutions.pump.solution.logic import solver as solver_module
from saf.solutions.pump.solution.logic.constants import (
    BLADE_PRESSURE_REPORT,
    BLADE_TORQUE_REPORT,
    INLET_GAUGE_PRESSURE,
    INLET_PRESSURE_REPORT,
    ITERATION_CHUNKS,
    OUTLET_PRESSURE_REPORT,
    PUMP_HEAD_REPORT_FILE_NAME,
    SOLVED_CASE_FILE_NAME,
    SOLVED_DATA_FILE_NAME,
    SOLVER_EXIT_WAIT_SECONDS,
)
from saf.solutions.pump.solution.logic.solver import OperatingPoint, run_operating_point

REPORT_VALUES: dict[str, float] = {
    INLET_PRESSURE_REPORT: -100.0,
    OUTLET_PRESSURE_REPORT: 200000.0,
    BLADE_PRESSURE_REPORT: 150000.0,
    BLADE_TORQUE_REPORT: 50.0,
}
"""Scalar values the fake solver returns for each report definition."""


def _operating_point(**overrides: float) -> OperatingPoint:
    """Build an operating point from the defaults, with selected fields overridden."""
    values: dict[str, float] = {
        "impeller_speed_rpm": 1450.0,
        "mass_flow_rate": 90.0,
        "iteration_count": 200,
        "time_step_scale_factor": 10.0,
        "processor_count": 4,
    }
    values.update(overrides)
    return OperatingPoint(**values)  # type: ignore[arg-type]


@pytest.fixture
def fake_fluent(monkeypatch, tmp_path):
    """Patch PyFluent so run_operating_point runs without a solver."""
    session = MagicMock()
    session.settings.solution.report_definitions.compute.side_effect = lambda report_defs: [
        {report_defs[0]: [REPORT_VALUES[report_defs[0]]]}
    ]
    monkeypatch.setattr(solver_module.pyfluent, "launch_fluent", MagicMock(return_value=session))
    (tmp_path / PUMP_HEAD_REPORT_FILE_NAME).write_text("1 20.0\n2 20.1\n", encoding="utf-8")
    return session


def test_run_operating_point_applies_the_rotation_speed_in_rad_per_second(fake_fluent, tmp_path):
    run_operating_point(tmp_path / "case.cas.h5", tmp_path, _operating_point(), lambda stage, fraction: None)
    impeller = fake_fluent.settings.setup.cell_zone_conditions.fluid.__getitem__.return_value
    assert impeller.reference_frame.mrf_omega.value == pytest.approx(1450.0 * 2.0 * math.pi / 60.0)


def test_run_operating_point_applies_the_mass_flow_at_the_outlet(fake_fluent, tmp_path):
    run_operating_point(
        tmp_path / "case.cas.h5",
        tmp_path,
        _operating_point(mass_flow_rate=120.0),
        lambda stage, fraction: None,
    )
    outlet = fake_fluent.settings.setup.boundary_conditions.mass_flow_outlet.__getitem__.return_value
    assert outlet.momentum.mass_flow_rate.value == 120.0


def test_run_operating_point_pins_the_inlet_pressure_at_the_fixed_datum(fake_fluent, tmp_path):
    # The suction pressure is not a user input: it only sets the datum of an otherwise
    # undetermined additive constant and cannot change the reported performance.
    run_operating_point(tmp_path / "case.cas.h5", tmp_path, _operating_point(), lambda stage, fraction: None)
    inlet = fake_fluent.settings.setup.boundary_conditions.pressure_inlet.__getitem__.return_value
    assert inlet.momentum.supersonic_or_initial_gauge_pressure.value == INLET_GAUGE_PRESSURE


def test_run_operating_point_iterates_in_chunks_totalling_the_requested_count(fake_fluent, tmp_path):
    run_operating_point(
        tmp_path / "case.cas.h5", tmp_path, _operating_point(iteration_count=200), lambda stage, fraction: None
    )
    run_calculation = fake_fluent.settings.solution.run_calculation
    assert run_calculation.calculate.call_count == ITERATION_CHUNKS
    assert run_calculation.iter_count == 200 // ITERATION_CHUNKS


def test_run_operating_point_handles_an_iteration_count_below_the_chunk_count(fake_fluent, tmp_path):
    run_operating_point(
        tmp_path / "case.cas.h5", tmp_path, _operating_point(iteration_count=5), lambda stage, fraction: None
    )
    assert fake_fluent.settings.solution.run_calculation.calculate.call_count == 5


def test_run_operating_point_reports_the_convergence_samples_after_every_chunk(fake_fluent, tmp_path):
    # Fluent appends to its report files as it iterates, so the UI can draw the curve long
    # before the run ends.
    batches: list[tuple[list, list]] = []
    run_operating_point(
        tmp_path / "case.cas.h5",
        tmp_path,
        _operating_point(iteration_count=200),
        lambda stage, fraction: None,
        history=lambda head, outlet: batches.append((head, outlet)),
    )
    assert len(batches) == ITERATION_CHUNKS
    assert batches[0][0] == [(1, 20.0), (2, 20.1)]


def test_run_operating_point_returns_the_computed_reports(fake_fluent, tmp_path):
    results = run_operating_point(
        tmp_path / "case.cas.h5", tmp_path, _operating_point(), lambda stage, fraction: None
    )
    assert results.inlet_total_pressure_pa == -100.0
    assert results.outlet_total_pressure_pa == 200000.0
    assert results.blade_pressure_pa == 150000.0
    assert results.blade_torque_nm == 50.0
    assert results.head_samples == [(1, 20.0), (2, 20.1)]
    assert results.outlet_pressure_samples == []


def test_run_operating_point_writes_the_solved_case(fake_fluent, tmp_path):
    results = run_operating_point(
        tmp_path / "case.cas.h5", tmp_path, _operating_point(), lambda stage, fraction: None
    )
    assert results.solved_case_path == tmp_path / SOLVED_CASE_FILE_NAME
    assert results.solved_data_path == tmp_path / SOLVED_DATA_FILE_NAME
    fake_fluent.settings.file.write.assert_called_once_with(
        file_type="case-data", file_name=str(tmp_path / SOLVED_CASE_FILE_NAME)
    )


def test_run_operating_point_always_exits_the_session_even_on_failure(fake_fluent, tmp_path):
    fake_fluent.settings.file.read_case.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        run_operating_point(tmp_path / "case.cas.h5", tmp_path, _operating_point(), lambda stage, fraction: None)
    # Waiting matters: the BDM garbage collector wipes the method storage root -- which doubles as
    # Fluent's working directory -- the moment the transaction returns.
    fake_fluent.exit.assert_called_once_with(wait=SOLVER_EXIT_WAIT_SECONDS)


def test_run_operating_point_rejects_an_out_of_range_speed(fake_fluent, tmp_path):
    with pytest.raises(ValueError, match="impeller_speed_rpm must be between"):
        run_operating_point(
            tmp_path / "case.cas.h5", tmp_path, _operating_point(impeller_speed_rpm=9000.0), lambda s, f: None
        )


def test_run_operating_point_rejects_an_out_of_range_mass_flow(fake_fluent, tmp_path):
    with pytest.raises(ValueError, match="mass_flow_rate must be between"):
        run_operating_point(
            tmp_path / "case.cas.h5", tmp_path, _operating_point(mass_flow_rate=0.0), lambda s, f: None
        )
