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

"""Where the report of a project stands, and how to bring it up to date.

Shared by the shell, which generates the report when a simulation completes, and by the
report page, which catches up when that did not happen. Kept out of both page modules so
that neither has to import the other.
"""

from dataclasses import dataclass
from enum import Enum
import logging

from ansys.saf.glow.solution import MethodStatus

from saf.solutions.pump.solution.definition import PumpSolution
from saf.solutions.pump.solution.logic.report.settings import get_report_settings
from saf.solutions.pump.solution.steps.report_step import results_fingerprint
from saf.solutions.pump.ui.feedback import NotificationCopy

logger = logging.getLogger(__name__)

REPORT_NOTIFICATION = NotificationCopy(
    notification_id="generate-report-notification",
    running_title="Generating the report",
    running_message="The report of the last simulation is being built. It appears on the Report page once ready.",
    success_title="Report ready",
    success_message="The report of the last simulation is available on the Report page.",
    failure_title="Report generation failed",
    failure_message="The report could not be generated. The simulation results are unaffected.",
)


class ReportState(str, Enum):
    """Stages of the report of a project."""

    UNAVAILABLE = "unavailable"
    """ADR is not installed or not configured."""
    NO_RESULTS = "no-results"
    """No simulation has completed yet."""
    RUNNING = "running"
    READY = "ready"
    """The report describes the latest results."""
    FAILED = "failed"
    """The last generation failed and the report is behind the latest results."""
    OUTDATED = "outdated"
    """The report is behind the latest results and no generation is running."""


@dataclass(frozen=True)
class ReportStatus:
    """State of the report, with the reason of a failure."""

    state: ReportState
    error: str | None = None


def report_status(project: PumpSolution) -> ReportStatus:
    """Return where the report of ``project`` stands."""
    if not get_report_settings().is_available:
        return ReportStatus(ReportState.UNAVAILABLE)
    current = results_fingerprint(project.steps.solve_step.contour_image)
    if not current:
        return ReportStatus(ReportState.NO_RESULTS)
    report_step = project.steps.report_step
    method_state = report_step.get_long_running_method_state("generate_report")
    if method_state.status == MethodStatus.Running:
        return ReportStatus(ReportState.RUNNING)
    if report_step.source_results == current:
        return ReportStatus(ReportState.READY)
    if method_state.status == MethodStatus.Failed:
        return ReportStatus(ReportState.FAILED, method_state.exception_message)
    return ReportStatus(ReportState.OUTDATED)


def request_report(project: PumpSolution) -> bool:
    """Start the report generation if the report is behind the latest results.

    Safe to call repeatedly: it does nothing while a generation is running, or when the
    report already describes the latest solve.

    Returns
    -------
    bool
        Whether a generation was started.
    """
    report_step = project.steps.report_step
    current = results_fingerprint(project.steps.solve_step.contour_image)
    if not current or report_step.source_results == current:
        return False
    if report_step.get_long_running_method_state("generate_report").status == MethodStatus.Running:
        return False
    logger.info("Generating the report of project %s.", project.project_display_name)
    report_step.generate_report(adr_project_name=project.project_display_name)
    return True
