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

"""Frontend of report."""

from __future__ import annotations

from ansys.dynamicreporting.core.serverless import ADR
from ansys.saf.glow.client import callback
from ansys.saf.glow.solution import NO_ENTITY, MethodState, MethodStatus
import dash
from dash_extensions.enrich import Input, Output, State, dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from saf.solutions.examples.solution.airfoil_explorer.logic.report.report_utilities import ADR_INSTALLATION_DIRECTORY
from saf.solutions.examples.solution.airfoil_explorer.report_step import ReportStep
from saf.solutions.examples.solution.definition import ExamplesSolution

dash.register_page(
    __name__,
    name="Report",
    path_template="/projects/<project_id>/airfoil-explorer/report",
)


def _adr_report(report_html_content: str):
    return html.Iframe(
        id="solution-report",
        srcDoc=report_html_content,
        style={"width": "100%", "height": "80vh", "border": "none"},
    )


def report_empty_state():
    """Empty state shown when report is not yet available."""
    return dmc.Center(
        id="airfoil-report-empty-state",
        style={"height": "60vh"},
        children=[
            dmc.Stack(
                align="center",
                gap="xs",
                children=[
                    DashIconify(
                        icon="mdi:file-document-outline",
                        width=48,
                        color="#adb5bd",
                    ),
                    dmc.Text(
                        "Engineering report not available yet",
                        fw=600,
                    ),
                    dmc.Text(
                        "The engineering report will be generated automatically once the simulation completes.",
                        c="dimmed",
                        size="sm",
                        ta="center",
                    ),
                ],
            )
        ],
    )


def report_failed_state(error_message: str | None = None):
    """Alert shown when report generation fails."""
    return dmc.Center(
        style={"height": "60vh"},
        children=[
            dmc.Alert(
                title="Report generation failed",
                color="red",
                radius="md",
                children=error_message or "The engineering report could not be generated.",
            )
        ],
    )


def report_not_configured_state():
    """State shown when ADR is not configured on this deployment."""
    return dmc.Center(
        style={"height": "60vh"},
        children=[
            dmc.Stack(
                align="center",
                gap="xs",
                children=[
                    DashIconify(
                        icon="mdi:information-outline",
                        width=48,
                        color="#adb5bd",
                    ),
                    dmc.Text(
                        "Engineering report not available",
                        fw=600,
                    ),
                    dmc.Text(
                        "The report feature requires ADR to be configured. "
                        "Set the ADR_INSTALLATION_DIRECTORY environment variable to enable it.",
                        c="dimmed",
                        size="sm",
                        ta="center",
                    ),
                ],
            )
        ],
    )


def layout(report_step: ReportStep):
    """Layout of the report.

    Args:
        report_step: The ReportStep instance with current state

    Returns:
        Dash HTML Div containing the page layout
    """
    if not ADR_INSTALLATION_DIRECTORY:
        return html.Div(
            children=[report_not_configured_state()],
            style={"height": "100%", "width": "100%"},
        )

    has_report = bool(report_step.report_html_content)

    return html.Div(
        children=[
            dmc.Stack(
                gap="sm",
                children=[
                    dmc.Text(
                        "Engineering Report",
                        size="xl",
                        fw=700,
                    ),
                    dmc.Text(
                        "Generate the engineering report from your airfoil streamline analysis",
                        c="dimmed",
                    ),
                ],
            ),
            dmc.Space(h=20),
            dmc.Group(
                grow=True,
                children=[
                    dmc.Button(
                        "Download Report (PDF)",
                        id="airfoil-export-report",
                        disabled=not has_report,
                    ),
                    dmc.Button(
                        "Download Report (HTML, ZIP)",
                        id="airfoil-export-report-html",
                        disabled=not has_report,
                    ),
                ],
            ),
            dcc.Download(id="download-report-pdf", base64=True),
            dcc.Download(id="download-report-html", base64=True),
            html.Div(
                id="airfoil-report-content",
            ),
        ],
        style={"height": "100%", "width": "100%", "overflowY": "auto", "maxHeight": "calc(100vh - 8vh)"},
    )


def _is_failed(method_state: MethodState | None) -> bool:
    """Indicate whether the given method state represents a failed state."""
    return method_state is not None and method_state.status == MethodStatus.Failed


@callback(
    Input("url", "pathname"),
)
def create_instance_of_serverless_adr(project: ExamplesSolution):
    """Create the instance of ADR and create the report templates."""
    if not ADR_INSTALLATION_DIRECTORY:
        return

    report_step = project.steps.report_step
    project_id = project.project_display_name
    try:
        adr_obj = ADR.get_instance()
    except Exception:
        report_step.setup_adr_instance(
            stored_session_guid=report_step.session_guid, stored_dataset_guid=report_step.dataset_guid
        )

    if not report_step.get_method_state("create_report_templates").status == MethodStatus.Completed:
        project_id = project.project_display_name
        report_step.project_tag = f"project={project_id}"
        report_step.project_name = project.project_display_name
        report_step.create_report_templates()
        report_step.create_static_report_items()


@callback(
    Output("airfoil-report-content", "children"),
    Output("airfoil-export-report", "disabled"),
    Output("airfoil-export-report-html", "disabled"),
    Input("report_termination_listener", "message"),
    Input("url", "pathname"),
)
def update_report_view(message: dict, project: ExamplesSolution):
    """Update the report view and download-button state on page load or get_report termination event.

    The download buttons are enabled per-file: each is enabled only once its
    corresponding stored file exists, so a failed PDF export does not disable the
    working HTML download (and vice versa). This also re-enables the buttons when
    the report finishes generating while the user is already on the page.
    """
    report_step = project.steps.report_step
    pdf_disabled = report_step.report_pdf == NO_ENTITY
    html_disabled = report_step.report_html_file == NO_ENTITY

    # If report HTML content is already available, return it directly
    if report_step.report_html_content:
        return _adr_report(report_step.report_html_content), pdf_disabled, html_disabled

    # If get_report method terminates with failed or completed status, update the report view accordingly
    if message:
        method_state = report_step.get_method_state("get_report")

        if method_state.status == MethodStatus.Failed:
            return report_failed_state(method_state.exception_message), True, True

        if method_state.status == MethodStatus.Completed and report_step.report_html_content:
            return _adr_report(report_step.report_html_content), pdf_disabled, html_disabled

    # Page-load catch-up: reflect failures even if we missed the event
    if any(
        _is_failed(report_step.get_method_state(name))
        for name in ("create_report_setup_and_result_items", "get_report")
    ):
        return (
            report_failed_state(
                "The engineering report could not be generated. Please check the logs for more details."
            ),
            True,
            True,
        )

    return report_empty_state(), True, True


@callback(
    Output("download-report-pdf", "data", allow_duplicate=True),
    Input("airfoil-export-report", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def download_report_pdf(n_clicks, project: ExamplesSolution):
    """Download a PDF copy of the report."""
    if not n_clicks:
        return None
    report_step = project.steps.report_step
    if report_step.report_pdf == NO_ENTITY:
        return None
    filepath = project.storage_scope.get_cached(report_step.report_pdf)
    return dcc.send_bytes(src=filepath.read_bytes(), filename="airfoil_report.pdf")


@callback(
    Output("download-report-html", "data", allow_duplicate=True),
    Input("airfoil-export-report-html", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def download_report_html(n_clicks, project: ExamplesSolution):
    """Download an HTML copy of the report."""
    if not n_clicks:
        return None
    report_step = project.steps.report_step
    if report_step.report_html_file == NO_ENTITY:
        return None
    filepath = project.storage_scope.get_cached(report_step.report_html_file)
    return dcc.send_bytes(src=filepath.read_bytes(), filename="airfoil_report.zip")
