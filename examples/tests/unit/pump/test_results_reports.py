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

import pytest

from saf.solutions.examples.solution.logic.pump.results import (
    build_convergence_history,
    is_converged,
    parse_report_file,
)

ASSETS = Path(__file__).parent / "assets"


def test_parse_report_file_skips_header_lines_and_returns_samples():
    samples = parse_report_file(ASSETS / "pump-head-rfile.out")
    assert len(samples) == 22
    assert samples[0] == (1, pytest.approx(5.12))
    assert samples[-1] == (22, pytest.approx(21.0))


def test_parse_report_file_returns_empty_list_for_a_header_only_file(tmp_path):
    report = tmp_path / "empty-rfile.out"
    report.write_text('"Convergence history"\n("Iteration" "pump-head")\n', encoding="utf-8")
    assert parse_report_file(report) == []


def test_build_convergence_history_joins_the_two_series_on_iteration():
    history = build_convergence_history(
        head_samples=[(1, 5.0), (2, 10.0)],
        outlet_pressure_samples=[(1, 1000.0), (2, 2000.0)],
    )
    assert history == [
        {"iteration": 1, "head": 5.0, "outlet_total_pressure": 1000.0},
        {"iteration": 2, "head": 10.0, "outlet_total_pressure": 2000.0},
    ]


def test_build_convergence_history_defaults_missing_pressure_samples_to_zero():
    history = build_convergence_history(head_samples=[(1, 5.0)], outlet_pressure_samples=[])
    assert history == [{"iteration": 1, "head": 5.0, "outlet_total_pressure": 0.0}]


def test_is_converged_is_true_for_a_settled_history():
    samples = parse_report_file(ASSETS / "pump-head-rfile.out")
    assert is_converged(samples) is True


def test_is_converged_is_false_when_head_is_still_moving():
    samples = [(i, float(i)) for i in range(1, 21)]
    assert is_converged(samples) is False


def test_is_converged_is_false_with_too_few_samples():
    assert is_converged([(1, 21.0), (2, 21.0), (3, 21.0)]) is False


def test_is_converged_is_false_when_the_final_head_is_zero():
    samples = [(i, 0.0) for i in range(1, 21)]
    assert is_converged(samples) is False
