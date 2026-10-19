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

"""Backend of the report step."""

from pathlib import Path
import uuid

from ansys.saf.glow.solution import (
    NO_ENTITY,
    BadRequestError,
    EntityHandle,
    StepModel,
    StepSpec,
    long_running,
    transaction,
)

from saf.solutions.pump.solution.logic.report.builder import render_report
from saf.solutions.pump.solution.logic.report.content import PumpReportData
from saf.solutions.pump.solution.logic.report.settings import get_report_settings
from saf.solutions.pump.solution.steps.setup_step import SetupStep
from saf.solutions.pump.solution.steps.solve_step import SolveStep

REPORT_ZIP_FILE_NAME = "pump_report.zip"


def results_fingerprint(contour_image: EntityHandle) -> str:
    """Identify the solve a report was built from.

    Every successful solve stores a new contour image, so its handle tells one set of results
    from the next. Comparing it with :attr:`ReportStep.source_results` tells whether the
    report is still up to date.
    """
    return "" if contour_image == NO_ENTITY else contour_image.opaque_identifier


class ReportStep(StepModel):
    """Builds the engineering report of the last solve with Ansys Dynamic Reporting."""

    report_tag: str = ""
    """Tag of this project's items in the ADR database, shared by all projects."""
    source_results: str = ""
    """:func:`results_fingerprint` of the solve the current report describes."""
    report_html_content: str = ""
    report_html_file: EntityHandle = NO_ENTITY
    report_pdf: EntityHandle = NO_ENTITY

    @long_running
    @transaction(
        enable_termination_event=True,
        self=StepSpec(
            download=["report_tag"],
            upload=["report_tag", "source_results", "report_html_content", "report_html_file", "report_pdf"],
        ),
        setup_step=StepSpec(download=["processor_count"]),
        solve_step=StepSpec(
            download=[
                "impeller_speed_rpm",
                "mass_flow_rate",
                "iteration_count",
                "time_step_scale_factor",
                "converged",
                "pump_head_m",
                "hydraulic_efficiency",
                "shaft_power_w",
                "pressure_rise_pa",
                "blade_torque_nm",
                "volumetric_flow_m3h",
                "inlet_total_pressure_pa",
                "outlet_total_pressure_pa",
                "blade_pressure_pa",
                "contour_image",
            ]
        ),
    )
    def generate_report(self, setup_step: SetupStep, solve_step: SolveStep, adr_project_name: str = "") -> None:
        """Rebuild the report from the last solve and store it as HTML, ZIP and PDF."""
        if solve_step.contour_image == NO_ENTITY:
            raise BadRequestError("Run the simulation before generating the report.")
        settings = get_report_settings()
        if not settings.is_available:
            raise BadRequestError(
                "Reporting is unavailable: install ansys-dynamicreporting-core and set ADR_INSTALLATION_DIRECTORY."
            )

        if not self.report_tag:
            self.report_tag = f"pump-report={uuid.uuid4().hex}"

        data = PumpReportData(
            project_name=adr_project_name,
            impeller_speed_rpm=solve_step.impeller_speed_rpm,
            mass_flow_rate=solve_step.mass_flow_rate,
            iteration_count=solve_step.iteration_count,
            time_step_scale_factor=solve_step.time_step_scale_factor,
            processor_count=setup_step.processor_count,
            converged=solve_step.converged,
            pump_head_m=solve_step.pump_head_m,
            hydraulic_efficiency=solve_step.hydraulic_efficiency,
            shaft_power_w=solve_step.shaft_power_w,
            pressure_rise_pa=solve_step.pressure_rise_pa,
            blade_torque_nm=solve_step.blade_torque_nm,
            volumetric_flow_m3h=solve_step.volumetric_flow_m3h,
            inlet_total_pressure_pa=solve_step.inlet_total_pressure_pa,
            outlet_total_pressure_pa=solve_step.outlet_total_pressure_pa,
            blade_pressure_pa=solve_step.blade_pressure_pa,
        )
        work_dir = Path(self.storage_scope.get_storage_root())
        report = render_report(
            settings,
            data,
            Path(self.storage_scope.get_cached(solve_step.contour_image)),
            self.report_tag,
            work_dir,
        )

        self.report_html_content = report.html
        self.report_html_file = self.storage_scope.store_stream(
            report.html_zip, relative_location=Path(REPORT_ZIP_FILE_NAME)
        )
        self.report_pdf = self.storage_scope.store(report.pdf_path) if report.pdf_path else NO_ENTITY
        self.source_results = results_fingerprint(solve_step.contour_image)
