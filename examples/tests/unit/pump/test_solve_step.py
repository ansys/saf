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

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.logic.pump.constants import RUN_SIMULATION_HISTORY_STREAM
from saf.solutions.examples.solution.logic.pump.solver import RawResults
from saf.solutions.examples.solution.steps.pump.pump_solve_step import PumpSolveStep

_STEP_MODULE = "saf.solutions.examples.solution.steps.pump.pump_solve_step"


@pytest.fixture
def prepared_project(client_project: ExamplesSolution) -> ExamplesSolution:
    """Give the solve step a case file to consume."""
    case_file = client_project.storage_scope.get_storage_root() / "case.cas.h5"
    case_file.write_bytes(b"case")
    client_project.steps.pump_model_setup_step.case_file = client_project.storage_scope.store(case_file)
    return client_project


def _fake_run(contour_bytes: bytes = b"png", torque: float = 50.0):
    def _run(case_path: Path, work_dir: Path, params, progress, log, history):
        contour_path = work_dir / "static-pressure-contour.png"
        contour_path.write_bytes(contour_bytes)
        solved_path = work_dir / "pump_volute_setup_solved.cas.h5"
        solved_path.write_bytes(b"solved")
        solved_data_path = work_dir / "pump_volute_setup_solved.dat.h5"
        solved_data_path.write_bytes(b"solved data")
        progress("Launching Fluent", 0.0)
        log(["iter  continuity", "   1  1.0e-02"])
        history([(i, 20.0) for i in range(1, 11)], [(i, 200000.0) for i in range(1, 11)])
        return RawResults(
            inlet_total_pressure_pa=-100.0,
            outlet_total_pressure_pa=998.2 * 9.81 * 20.0 - 100.0,
            blade_pressure_pa=150000.0,
            blade_torque_nm=torque,
            contour_image_path=contour_path,
            solved_case_path=solved_path,
            solved_data_path=solved_data_path,
            head_samples=[(i, 20.0) for i in range(1, 21)],
            outlet_pressure_samples=[(i, 200000.0) for i in range(1, 21)],
        )

    return _run


def test_run_simulation_computes_the_headline_kpis(monkeypatch, prepared_project: ExamplesSolution):
    monkeypatch.setattr(f"{_STEP_MODULE}.run_operating_point", MagicMock(side_effect=_fake_run()))
    solve_step = prepared_project.steps.pump_solve_step
    solve_step.run_simulation().wait(timeout=60)

    assert solve_step.pump_head_m == pytest.approx(20.0, abs=1e-6)
    assert solve_step.volumetric_flow_m3h == pytest.approx(90.0 / 998.2 * 3600.0)
    assert solve_step.shaft_power_w == pytest.approx(50.0 * 151.8436, abs=1e-2)
    assert solve_step.hydraulic_efficiency == pytest.approx(
        998.2 * 9.81 * (90.0 / 998.2) * 20.0 / (50.0 * 151.8436), abs=1e-4
    )
    assert solve_step.converged is True


def test_run_simulation_stores_the_artefacts(monkeypatch, prepared_project: ExamplesSolution):
    monkeypatch.setattr(
        f"{_STEP_MODULE}.run_operating_point",
        MagicMock(side_effect=_fake_run(contour_bytes=b"contour")),
    )
    solve_step = prepared_project.steps.pump_solve_step
    solve_step.run_simulation().wait(timeout=60)

    assert prepared_project.storage_scope.get_bytes(solve_step.contour_image) == b"contour"
    assert prepared_project.storage_scope.get_bytes(solve_step.solved_case_file) == b"solved"
    assert prepared_project.storage_scope.get_bytes(solve_step.solved_data_file) == b"solved data"


def test_prepare_solved_scene_stores_the_converted_case(monkeypatch, prepared_project: ExamplesSolution):
    def fake_export_scene(case_path, data_path, work_dir, scene_file_name):
        assert case_path.read_bytes() == b"solved"
        assert data_path.read_bytes() == b"solved data"
        scene_path = work_dir / scene_file_name
        scene_path.write_bytes(b"scene")
        return scene_path

    monkeypatch.setattr(f"{_STEP_MODULE}.run_operating_point", MagicMock(side_effect=_fake_run()))
    monkeypatch.setattr(f"{_STEP_MODULE}.export_scene", MagicMock(side_effect=fake_export_scene))
    solve_step = prepared_project.steps.pump_solve_step
    solve_step.run_simulation().wait(timeout=60)
    solve_step.prepare_solved_scene().wait(timeout=60)

    assert prepared_project.storage_scope.get_bytes(solve_step.solved_scene_file) == b"scene"


def test_prepare_solved_scene_requires_a_run(prepared_project: ExamplesSolution):
    solve_step = prepared_project.steps.pump_solve_step
    with pytest.raises(Exception, match="Run the simulation before preparing the 3D view"):
        solve_step.prepare_solved_scene().wait(timeout=60)


def test_run_simulation_builds_the_convergence_history(monkeypatch, prepared_project: ExamplesSolution):
    monkeypatch.setattr(f"{_STEP_MODULE}.run_operating_point", MagicMock(side_effect=_fake_run()))
    solve_step = prepared_project.steps.pump_solve_step
    solve_step.run_simulation().wait(timeout=60)

    assert len(solve_step.convergence_history) == 20
    assert solve_step.convergence_history[0] == {
        "iteration": 1,
        "head": 20.0,
        "outlet_total_pressure": 200000.0,
    }


def test_run_simulation_reports_zero_efficiency_when_there_is_no_torque(
    monkeypatch, prepared_project: ExamplesSolution
):
    monkeypatch.setattr(f"{_STEP_MODULE}.run_operating_point", MagicMock(side_effect=_fake_run(torque=0.0)))
    solve_step = prepared_project.steps.pump_solve_step
    solve_step.run_simulation().wait(timeout=60)
    assert solve_step.hydraulic_efficiency == 0.0


def test_report_history_publishes_the_partial_curve_mid_solve(monkeypatch):
    # The solve reports what Fluent has written so far after each chunk; the UI draws it
    # live, and the uploaded field lets a page reloaded mid-run pick the curve back up.
    transaction = MagicMock()
    monkeypatch.setattr(PumpSolveStep, "transaction", transaction)
    step = PumpSolveStep()
    step._report_history([(1, 10.0), (2, 12.0)], [(1, 1000.0), (2, 1200.0)])

    assert step.convergence_history == [
        {"iteration": 1, "head": 10.0, "outlet_total_pressure": 1000.0},
        {"iteration": 2, "head": 12.0, "outlet_total_pressure": 1200.0},
    ]
    transaction.upload.assert_called_once_with(["convergence_history"])
    _, kwargs = transaction.raise_event.call_args
    assert kwargs["stream_name"] == RUN_SIMULATION_HISTORY_STREAM


def test_report_history_stays_quiet_until_fluent_has_written_a_sample(monkeypatch):
    # The report files exist but hold only their header for the first few iterations.
    transaction = MagicMock()
    monkeypatch.setattr(PumpSolveStep, "transaction", transaction)
    step = PumpSolveStep()
    step._report_history([], [])

    assert step.convergence_history == []
    transaction.raise_event.assert_not_called()


def test_run_simulation_fails_clearly_without_a_case_file(client_project: ExamplesSolution):
    with pytest.raises(Exception, match="Build the case"):
        client_project.steps.pump_solve_step.run_simulation().wait(timeout=60)
