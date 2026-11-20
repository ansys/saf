# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ©2026, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.
"""Report page of the beam bending example application."""
import logging

from ansys.dynamicreporting.core.serverless import ADR
from ansys.saf.glow.client import callback
from ansys.saf.glow.solution import MethodStatus
import dash
from dash_extensions.enrich import Input, Output, State, dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from saf.solutions.examples.solution.definition import ExamplesSolution

logger = logging.getLogger(__name__)

dash.register_page(
    __name__,
    name="Beam Bending Report",
    path_template="/projects/<project_id>/beam-bending-report",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)


def _adr_report(report_html_content: str):
    return html.Div(
        [
            html.Iframe(
                id="solution-report-iframe",
                srcDoc=report_html_content,
                style={
                    "width": "100%",
                    "height": "calc(100vh - 250px)",
                    "minHeight": "800px",
                    "border": "none",
                },
            ),
        ],
        style={"height": "100%", "width": "100%"},
    )


def report_empty_state() -> dmc.Center:
    """Empty state shown when report is not yet available."""
    return dmc.Center(
        id="empty-state",
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


def report_not_ready_state() -> dmc.Center:
    """Shown when simulation results are not yet available."""
    return dmc.Center(
        style={"height": "60vh"},
        children=dmc.Alert(
            title="Simulation results not available",
            color="yellow",
            radius="md",
            children=[
                dmc.Text(
                    "The engineering report cannot be generated yet. "
                    "Please return to the Compute page and run the simulation first."
                )
            ],
        ),
    )


def report_failed_state(error_message: str | None = None) -> dmc.Center:
    """Alert shown when report generation fails."""
    return dmc.Center(
        style={"height": "60vh"},
        children=dmc.Alert(
            title="Report generation failed",
            color="red",
            radius="md",
            children=error_message or "The engineering report could not be generated.",
        ),
    )


def report_adr_not_configured_state() -> dmc.Center:
    """Alert shown when ADR (Dynamic Reporting) is not configured."""
    return dmc.Center(
        style={"height": "60vh"},
        children=dmc.Alert(
            title="ADR not configured",
            color="orange",
            radius="md",
            children=[
                dmc.Text(
                    "Ansys Dynamic Reporting (ADR) is not installed or configured. "
                    "See the documentation for setup instructions."
                ),
            ],
        ),
    )


def layout() -> html.Div:
    """Layout of the report.

    Args:
        project: The ExamplesSolution instance with current state

    Returns:
        Dash HTML Div containing the page layout
    """
    return html.Div(
        children=[
            html.H1("Engineering report", className="display-3", style={"font-size": "40px", "font-weight": "bold"}),
            dmc.Text(
                ("Generate the engineering report from your beam bending analysis"),
                c="dimmed",
            ),
            dmc.Space(h=20),
            dmc.Group(
                gap="sm",
                children=[
                    dmc.Button(
                        "Load Report",
                        id="load-report",
                        leftSection=DashIconify(icon="mdi:file-document-refresh"),
                        style={
                            "font-size": "16px",
                            "background-color": "#2790F1",
                        },
                    ),
                    dmc.Tooltip(
                        label="PDF export is coming soon",
                        withArrow=True,
                        children=dmc.Button(
                            "Download PDF",
                            id="export-report",
                            variant="outline",
                            disabled=True,
                            leftSection=DashIconify(icon="mdi:file-pdf-box"),
                            style={"font-size": "16px"},
                        ),
                    ),
                ],
            ),
            dcc.Loading(
                id="loading-report",
                type="circle",
                color="#ffb71b",
                children=[
                    html.Div(
                        id="report-content",
                    ),
                ],
            ),
        ],
    )


@callback(
    Output("report-content", "children"),
    Input("load-report", "n_clicks"),
    State("url", "pathname"),
)
def render_report_content(n_clicks: int, project: ExamplesSolution) -> dmc.Center | html.Div:
    """Initialize ADR and render the report UI.

    This combined callback ensures ADR setup (which happens when the page is displayed)
    completes before report rendering, avoiding race conditions.
    """
    report_step = project.steps.beam_bending_report_step

    # Initialize ADR on first visit to report page or if not yet set up
    try:
        ADR.get_instance()
    except RuntimeError:
        try:
            report_step.setup_adr_instance(
                stored_session_guid=report_step.session_guid,
                stored_dataset_guid=report_step.dataset_guid,
            )
        except Exception as exc:
            logger.warning("ADR initialization skipped because ADR is not configured: %s", exc)
            return report_adr_not_configured_state()

    try:
        if report_step.get_method_state("create_report_templates").status != MethodStatus.Completed:
            report_step.project_tag = f"project={project.project_display_name}"
            report_step.create_report_templates()
            report_step.create_static_report_items()
    except Exception as exc:
        logger.warning("ADR template setup skipped because ADR is not configured: %s", exc)
        return report_adr_not_configured_state()

    if not n_clicks:
        # On initial load, show an empty state if no report content is available yet
        if not report_step.report_html_content:
            return report_empty_state()
        # On initial page load, just show whatever is already stored
        return _adr_report(report_step.report_html_content)

    # User clicked "Load Report" — generate fresh report
    compute_step = project.steps.beam_bending_step
    if not compute_step.get_method_state("compute_theoretical_beam_deflection").status == MethodStatus.Completed:
        return report_not_ready_state()

    if not compute_step.get_method_state("mapdl_postprocessing").status == MethodStatus.Completed:
        return report_not_ready_state()

    try:
        report_step.create_report_setup_and_result_items()
        report_step.get_report()
    except Exception as e:
        return report_failed_state(
            "The engineering report could not be generated. Please check the logs for more details."
        )
    return _adr_report(report_step.report_html_content)
