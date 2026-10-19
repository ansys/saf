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

from unittest.mock import MagicMock

import pytest

from saf.solutions.pump.solution.definition import PumpSolution
from saf.solutions.pump.solution.logic.report.builder import RenderedReport
from saf.solutions.pump.solution.logic.report.settings import ReportSettings
from saf.solutions.pump.solution.steps.report_step import results_fingerprint

_STEP_MODULE = "saf.solutions.pump.solution.steps.report_step"


@pytest.fixture
def solved_project(client_project: PumpSolution) -> PumpSolution:
    """Give the solve step the results a report is built from."""
    contour = client_project.storage_scope.get_storage_root() / "contour.png"
    contour.write_bytes(b"png")
    solve_step = client_project.steps.solve_step
    solve_step.set_fields(
        {
            "contour_image": client_project.storage_scope.store(contour),
            "pump_head_m": 20.0,
            "hydraulic_efficiency": 0.8,
            "converged": True,
            "convergence_history": [{"iteration": 1, "head": 25.0, "outlet_total_pressure": 230000.0}],
        }
    )
    return client_project


@pytest.fixture
def adr_available(monkeypatch):
    monkeypatch.setattr(ReportSettings, "is_available", property(lambda self: True))


def _fake_render(calls: list):
    def render(settings, data, contour_image, tag, output_dir):
        calls.append((data, contour_image.read_bytes(), tag))
        pdf = output_dir / "pump_report.pdf"
        pdf.write_bytes(b"pdf")
        return RenderedReport(html="<html>report</html>", html_zip=b"zip", pdf_path=pdf)

    return render


def test_generate_report_requires_simulation_results(client_project: PumpSolution, adr_available):
    with pytest.raises(Exception, match="Run the simulation before generating the report"):
        client_project.steps.report_step.generate_report().wait(timeout=60)


def test_generate_report_explains_how_to_enable_adr(monkeypatch, solved_project: PumpSolution):
    monkeypatch.setattr(ReportSettings, "is_available", property(lambda self: False))
    with pytest.raises(Exception, match="ADR_INSTALLATION_DIRECTORY"):
        solved_project.steps.report_step.generate_report().wait(timeout=60)


def test_generate_report_stores_the_report_in_every_format(
    monkeypatch, solved_project: PumpSolution, adr_available
):
    calls: list = []
    monkeypatch.setattr(f"{_STEP_MODULE}.render_report", MagicMock(side_effect=_fake_render(calls)))

    report_step = solved_project.steps.report_step
    report_step.generate_report(project_name="Duty point A").wait(timeout=60)

    data, contour_bytes, tag = calls[0]
    assert data.project_name == "Duty point A"
    assert data.pump_head_m == 20.0
    assert data.processor_count == 4
    assert data.convergence_history == ({"iteration": 1.0, "head": 25.0, "outlet_total_pressure": 230000.0},)
    assert contour_bytes == b"png"
    assert tag.startswith("pump-report=")

    assert report_step.report_html_content == "<html>report</html>"
    assert solved_project.storage_scope.get_bytes(report_step.report_html_file) == b"zip"
    assert solved_project.storage_scope.get_bytes(report_step.report_pdf) == b"pdf"
    assert report_step.source_results == results_fingerprint(solved_project.steps.solve_step.contour_image)


def test_generate_report_keeps_the_project_tag_across_runs(
    monkeypatch, solved_project: PumpSolution, adr_available
):
    calls: list = []
    monkeypatch.setattr(f"{_STEP_MODULE}.render_report", MagicMock(side_effect=_fake_render(calls)))

    report_step = solved_project.steps.report_step
    report_step.generate_report().wait(timeout=60)
    report_step.generate_report().wait(timeout=60)

    assert calls[0][2] == calls[1][2] == report_step.report_tag
