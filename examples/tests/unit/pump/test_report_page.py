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

from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, MethodStatus
from dash.testing import ignore_register_page
import pytest

from saf.solutions.examples.solution.steps.pump.pump_report_step import results_fingerprint
from saf.solutions.examples.ui.pages.pump import report_status as status_module
from saf.solutions.examples.ui.pages.pump.report_status import (
    ReportState,
    ReportStatus,
    report_status,
    request_report,
)

with ignore_register_page():
    from saf.solutions.examples.ui.pages.pump import pump_report_page as report_page

_CONTOUR = EntityHandle(is_blob=True, entity_id=uuid.uuid4(), opaque_identifier="contour.png")


def _project(
    contour: EntityHandle = _CONTOUR,
    source_results: str = "",
    method: MethodStatus = MethodStatus.Completed,
    error: str | None = None,
):
    report_step = SimpleNamespace(
        source_results=source_results,
        report_html_content="<html>report</html>",
        report_pdf=_CONTOUR,
        report_html_file=_CONTOUR,
        get_long_running_method_state=lambda name: SimpleNamespace(status=method, exception_message=error),
        generate_report=MagicMock(),
    )
    steps = SimpleNamespace(pump_solve_step=SimpleNamespace(contour_image=contour), pump_report_step=report_step)
    return SimpleNamespace(steps=steps, project_display_name="Duty point A")


@pytest.fixture(autouse=True)
def adr_available(monkeypatch):
    monkeypatch.setattr(status_module, "get_report_settings", lambda: SimpleNamespace(is_available=True))


# --------------------------------------------------------------------------------- report status ----


def test_status_is_unavailable_without_adr(monkeypatch):
    monkeypatch.setattr(status_module, "get_report_settings", lambda: SimpleNamespace(is_available=False))
    assert report_status(_project()).state == ReportState.UNAVAILABLE


def test_status_waits_for_simulation_results():
    assert report_status(_project(contour=NO_ENTITY)).state == ReportState.NO_RESULTS


def test_status_is_ready_when_the_report_describes_the_latest_results():
    project = _project(source_results=results_fingerprint(_CONTOUR))
    assert report_status(project).state == ReportState.READY


def test_status_is_outdated_after_a_new_simulation():
    assert report_status(_project(source_results="older results")).state == ReportState.OUTDATED


def test_status_reports_a_failed_generation_with_its_reason():
    status = report_status(_project(method=MethodStatus.Failed, error="ADR exploded"))
    assert status == ReportStatus(ReportState.FAILED, "ADR exploded")


def test_status_is_running_while_a_generation_is_in_flight():
    assert report_status(_project(method=MethodStatus.Running)).state == ReportState.RUNNING


# -------------------------------------------------------------------------------- request report ----


def test_request_report_generates_an_outdated_report():
    project = _project()
    assert request_report(project) is True
    project.steps.pump_report_step.generate_report.assert_called_once_with(adr_project_name="Duty point A")


def test_request_report_leaves_an_up_to_date_report_alone():
    project = _project(source_results=results_fingerprint(_CONTOUR))
    assert request_report(project) is False
    project.steps.pump_report_step.generate_report.assert_not_called()


def test_request_report_never_starts_a_second_generation():
    project = _project(method=MethodStatus.Running)
    assert request_report(project) is False
    project.steps.pump_report_step.generate_report.assert_not_called()


# ----------------------------------------------------------------------------------- report page ----


def test_report_page_explains_how_to_enable_reporting():
    rendered = str(report_page.report_body(ReportStatus(ReportState.UNAVAILABLE), _project()))
    assert "ADR_INSTALLATION_DIRECTORY" in rendered


def test_report_page_shows_the_rendered_report_when_ready():
    body = report_page.report_body(ReportStatus(ReportState.READY), _project())
    assert body.srcDoc == "<html>report</html>"


def test_report_page_offers_a_retry_after_a_failure():
    rendered = str(report_page.report_body(ReportStatus(ReportState.FAILED, "ADR exploded"), _project()))
    assert "ADR exploded" in rendered
    assert "report-retry" in rendered


def test_downloads_are_disabled_until_the_report_is_ready():
    assert report_page.downloads_disabled(ReportStatus(ReportState.RUNNING), _project()) == (True, True)
    assert report_page.downloads_disabled(ReportStatus(ReportState.READY), _project()) == (False, False)


def test_pdf_download_is_disabled_when_the_pdf_export_failed():
    project = _project()
    project.steps.pump_report_step.report_pdf = NO_ENTITY
    assert report_page.downloads_disabled(ReportStatus(ReportState.READY), project) == (True, False)
