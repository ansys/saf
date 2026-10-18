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

"""Frontend of the report step."""

import time
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import NO_ENTITY
import dash
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, dcc, html
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from saf.solutions.pump.solution.definition import PumpSolution
from saf.solutions.pump.solution.logic.constants import GENERATE_REPORT_STREAM
from saf.solutions.pump.solution.steps.report_step import REPORT_ZIP_FILE_NAME
from saf.solutions.pump.ui.feedback import parse_event, require_click
from saf.solutions.pump.ui.report_status import ReportState, ReportStatus, report_status, request_report

dash.register_page(
    __name__,
    name="Report",
    path_template="/projects/<project_id>/report",
    icon_asset_name="carbon:report",
    order=3,
)

REPORT_PDF_FILE_NAME = "pump_report.pdf"


def _alert(title: str, message: Any, color: str, icon: str) -> dmc.Alert:
    return dmc.Alert(message, title=title, color=color, variant="light", icon=DashIconify(icon=icon, width=20))


def report_body(status: ReportStatus, project: PumpSolution) -> Any:
    """Return what the page shows for a given report state."""
    if status.state == ReportState.UNAVAILABLE:
        return _alert(
            "Reporting is not configured",
            "Install ansys-dynamicreporting-core (Python 3.12 or earlier) and set ADR_INSTALLATION_DIRECTORY to "
            "the ADR folder of an Ansys 2025 R1 or later installation, then restart the solution.",
            "yellow",
            "carbon:warning-alt",
        )
    if status.state == ReportState.NO_RESULTS:
        return _alert(
            "No results yet",
            "Run a simulation on the Operating Point page. The report is generated automatically when it completes.",
            "gray",
            "carbon:information",
        )
    if status.state == ReportState.FAILED:
        return _alert(
            "Report generation failed",
            dmc.Stack(
                [
                    dmc.Text(status.error or "The report could not be generated.", size="sm"),
                    dmc.Group(dmc.Button("Try again", id="report-retry", variant="light", color="red", size="xs")),
                ],
                gap="sm",
            ),
            "red",
            "carbon:warning-filled",
        )
    if status.state == ReportState.READY:
        return html.Iframe(
            id="report-frame",
            srcDoc=project.steps.report_step.report_html_content,
            title="Pump performance report",
            style={"width": "100%", "height": "80vh", "border": "none", "backgroundColor": "white"},
        )
    return dmc.Center(
        dmc.Stack(
            [dmc.Loader(), dmc.Text("Generating the report of the last simulation.", c="dimmed")],
            align="center",
        ),
        h=300,
    )


def downloads_disabled(status: ReportStatus, project: PumpSolution) -> tuple[bool, bool]:
    """Return whether the PDF and the ZIP download buttons are disabled."""
    if status.state != ReportState.READY:
        return True, True
    report_step = project.steps.report_step
    return report_step.report_pdf == NO_ENTITY, report_step.report_html_file == NO_ENTITY


def layout(project: PumpSolution) -> html.Div:
    """Layout of the report page."""
    status = report_status(project)
    pdf_disabled, zip_disabled = downloads_disabled(status, project)
    listener = (
        html.Div()
        if status.state == ReportState.UNAVAILABLE
        else DashClient.create_event_listener(
            project.steps.report_step, stream_name=GENERATE_REPORT_STREAM, id="report-page-ws"
        )
    )
    return html.Div(
        [
            dmc.Group(
                [
                    html.Div(
                        [
                            dmc.Title("Report", order=1),
                            dmc.Space(h=6),
                            dmc.Text(
                                "Engineering problem, modelling assumptions and results of the last simulation.",
                                c="dimmed",
                            ),
                        ]
                    ),
                    dmc.Group(
                        [
                            dmc.Button(
                                "Download PDF",
                                id="report-download-pdf",
                                disabled=pdf_disabled,
                                variant="light",
                                leftSection=DashIconify(icon="carbon:document-pdf", width=18),
                            ),
                            dmc.Button(
                                "Download HTML",
                                id="report-download-zip",
                                disabled=zip_disabled,
                                variant="light",
                                leftSection=DashIconify(icon="carbon:zip", width=18),
                            ),
                        ]
                    ),
                ],
                justify="space-between",
                align="flex-end",
            ),
            dmc.Space(h=24),
            html.Div(report_body(status, project), id="report-body"),
            dmc.Space(h=40),
            dcc.Download(id="report-pdf-download"),
            dcc.Download(id="report-zip-download"),
            # A fresh value on every visit fires the catch-up callback once per visit.
            dcc.Store(id="report-page-boot", data=time.monotonic()),
            listener,
        ]
    )


@callback(
    Output("report-body", "children"),
    Input("report-page-boot", "data"),
    State("url", "pathname"),
)
def catch_up_report(_boot: float, project: PumpSolution) -> Any:
    """Generate the report on arrival when it is behind the latest results.

    The shell generates it when a simulation completes, but not if the UI was closed at
    that moment or the project predates the report.
    """
    if report_status(project).state != ReportState.OUTDATED or not request_report(project):
        raise PreventUpdate
    return report_body(ReportStatus(ReportState.RUNNING), project)


@callback(
    Output("report-body", "children", allow_duplicate=True),
    Input("report-retry", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def retry_report(n_clicks: int | None, project: PumpSolution) -> Any:
    """Generate the report again after a failure."""
    require_click(n_clicks)
    request_report(project)
    return report_body(ReportStatus(ReportState.RUNNING), project)


@callback(
    Output("report-body", "children", allow_duplicate=True),
    Output("report-download-pdf", "disabled"),
    Output("report-download-zip", "disabled"),
    Input("report-page-ws", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_report_generated(message: dict, project: PumpSolution) -> tuple[Any, bool, bool]:
    """Show the new report, or why it failed, when a generation ends."""
    if not parse_event(message).finished:
        raise PreventUpdate
    status = report_status(project)
    return (report_body(status, project), *downloads_disabled(status, project))


@callback(
    Output("report-pdf-download", "data"),
    Input("report-download-pdf", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def download_pdf(n_clicks: int | None, project: PumpSolution) -> dict:
    """Send the PDF report to the browser."""
    require_click(n_clicks)
    handle = project.steps.report_step.report_pdf
    if handle == NO_ENTITY:
        raise PreventUpdate
    return dcc.send_bytes(project.storage_scope.get_bytes(handle), REPORT_PDF_FILE_NAME)


@callback(
    Output("report-zip-download", "data"),
    Input("report-download-zip", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def download_zip(n_clicks: int | None, project: PumpSolution) -> dict:
    """Send the standalone HTML report, zipped with its assets, to the browser."""
    require_click(n_clicks)
    handle = project.steps.report_step.report_html_file
    if handle == NO_ENTITY:
        raise PreventUpdate
    return dcc.send_bytes(project.storage_scope.get_bytes(handle), REPORT_ZIP_FILE_NAME)
