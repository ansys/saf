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
"""Frontend of the ADR reference page."""

import logging
from typing import Any

from ansys.saf.glow.client import callback
from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, MethodStatus
import dash
from dash_extensions.enrich import Input, Output, State, dcc, html, no_update
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from saf.solutions.examples.solution.adr_step import AdrStep
from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.logic.adr_reference.adr_settings import MEDIA_URL, check_adr_availability
from saf.solutions.examples.solution.logic.adr_reference.report_definition import build_project_tag

logger = logging.getLogger(__name__)

dash.register_page(
    __name__,
    name="ADR Reference",
    path_template="/projects/<project_id>/adr-reference",
    icon_asset_name="game-icons--crossed-air-flows.svg",
    icon_asset_path="icons",
)

PDF_FILE_NAME = "adr_reference_report.pdf"
PPTX_FILE_NAME = "adr_reference_report.pptx"
HTML_ARCHIVE_FILE_NAME = "adr_reference_report.zip"

# Script added to the report displayed in the iframe. Without it, clicking the link of a File item
# replaces the report with the file. Links to ADR media files are downloaded instead, and other
# links (except the table of contents anchors) open in a new tab, so the report stays displayed.
_REPORT_LINK_HANDLER_SCRIPT = f"""
<script>
document.addEventListener("click", function (event) {{
    const link = event.composedPath().find((element) => element.tagName === "A" && element.hasAttribute("href"));
    if (!link) {{
        return;
    }}
    const href = link.getAttribute("href");
    if (href.startsWith("#")) {{
        return;
    }}
    if (href.startsWith("{MEDIA_URL}")) {{
        link.setAttribute("download", href.split("/").pop());
    }} else {{
        link.setAttribute("target", "_blank");
    }}
}}, true);
</script>
"""


# ------------------------------------------------------------------------------------------------ #
# Layout
# ------------------------------------------------------------------------------------------------ #


def layout() -> html.Div:
    """Layout of the ADR reference page.

    A "starting ADR" alert is shown and all buttons are disabled until the ``initialize_adr_page``
    callback has checked that ADR is available and started it.
    """
    return html.Div(
        [
            html.H1(
                "ADR Reference Report",
                className="display-3",
                style={"font-size": "40px", "font-weight": "bold"},
            ),
            dmc.Blockquote(
                "This example demonstrates how to build an engineering report with serverless Ansys Dynamic "
                "Reporting (ADR). Click the Generate Report button to create a report with one section per common "
                "ADR item type (string, HTML, table, tree, image, scene, and file), each rendered by its own "
                "template with placeholder content. Once the report is generated, export it as PDF, PowerPoint, "
                "or HTML (ZIP archive including the static assets).",
                icon=DashIconify(icon="material-symbols:info", width=30),
                style={"font-size": "18px", "fontStyle": "italic"},
            ),
            dmc.Space(h=20),
            dmc.Alert(
                dmc.Text(
                    [
                        "⚠️ This example requires an Ansys Dynamic Reporting installation. Set the "
                        "ADR_INSTALLATION_DIRECTORY variable in the .env file of the solution, for example "
                        "C:\\Program Files\\ANSYS Inc\\v271\\ADR.\n",
                        "⚠️ With ansys-dynamicreporting-core 0.10, the PDF export relies on WeasyPrint, which "
                        "requires the GTK3 runtime. If it is not installed, the PDF export stays disabled.",
                    ],
                    style={"whiteSpace": "pre-line"},
                    size="md",
                ),
                title="Warning",
                color="yellow",
            ),
            dmc.Space(h=20),
            html.Div(id="adr-page-availability-alert", children=_adr_starting_alert()),
            dmc.Group(
                [
                    dmc.Button(
                        "Generate Report",
                        id="adr-page-generate-report-button",
                        leftSection=DashIconify(icon="mdi:file-document-refresh"),
                        disabled=True,
                        loading=True,
                        style={"font-size": "16px", "background-color": "#2790F1"},
                    ),
                    dmc.Divider(orientation="vertical"),
                    _export_button("Export PDF", "adr-page-export-pdf-button", "mdi:file-pdf-box"),
                    _export_button("Export PowerPoint", "adr-page-export-pptx-button", "mdi:file-powerpoint-box"),
                    _export_button("Export HTML (ZIP)", "adr-page-export-html-button", "mdi:folder-zip"),
                ],
                gap="sm",
            ),
            dcc.Download(id="adr-page-download-pdf"),
            dcc.Download(id="adr-page-download-pptx"),
            dcc.Download(id="adr-page-download-html"),
            dmc.Space(h=20),
            dcc.Loading(
                id="adr-page-report-loading",
                type="circle",
                color="#ffb71b",
                children=html.Div(id="adr-page-report-content", children=_report_empty_state()),
            ),
        ],
        style={"paddingLeft": "20px"},
    )


def _export_button(label: str, button_id: str, icon: str) -> dmc.Button:
    """Create an export button, disabled until the report is successfully generated."""
    return dmc.Button(
        label,
        id=button_id,
        variant="outline",
        leftSection=DashIconify(icon=icon),
        disabled=True,
        style={"font-size": "16px"},
    )


def _report_iframe(report_html_content: str) -> html.Iframe:
    """Display the rendered report in an iframe, with links that keep the report displayed."""
    if "</body>" in report_html_content:
        content = report_html_content.replace("</body>", f"{_REPORT_LINK_HANDLER_SCRIPT}</body>", 1)
    else:
        content = report_html_content + _REPORT_LINK_HANDLER_SCRIPT
    return html.Iframe(
        id="adr-page-report-iframe",
        srcDoc=content,
        style={"width": "100%", "height": "calc(100vh - 250px)", "minHeight": "800px", "border": "none"},
    )


def _report_empty_state() -> dmc.Center:
    """Content shown while no report has been generated."""
    return dmc.Center(
        style={"height": "40vh"},
        children=dmc.Stack(
            align="center",
            gap="xs",
            children=[
                DashIconify(icon="mdi:file-document-outline", width=48, color="#adb5bd"),
                dmc.Text("No report generated yet", fw=600),
                dmc.Text("Click Generate Report to create the ADR reference report.", c="dimmed", size="sm"),
            ],
        ),
    )


def _report_failed_state(error_details: str) -> dmc.Alert:
    """Content shown when the report generation failed."""
    return dmc.Alert(
        [
            dmc.Text("The report could not be generated. See the logs for more details."),
            dmc.Text(f"Details: {error_details}", size="sm", c="dimmed"),
        ],
        title="Report generation failed",
        color="red",
    )


def _adr_starting_alert() -> dmc.Alert:
    """Alert shown while the page checks that ADR is available and starts it."""
    return dmc.Alert(
        "Checking the ADR installation and starting serverless ADR. The first start can take several seconds. "
        "The Generate Report button is enabled once ADR is ready.",
        title="Starting Ansys Dynamic Reporting...",
        icon=dmc.Loader(size="sm", color="blue"),
        color="blue",
        mb="md",
    )


def _adr_not_available_alert(message: str, error_details: str | None = None) -> dmc.Alert:
    """Alert shown when ADR is not available."""
    children = [dmc.Text(message)]
    if error_details:
        children.append(dmc.Text(f"Details: {error_details}", size="sm", c="dimmed"))
    children.append(dmc.Text("Report generation is disabled. See the logs for more details.", size="sm", c="dimmed"))
    return dmc.Alert(children, title="Ansys Dynamic Reporting is not available", color="red", mb="md")


# ------------------------------------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------------------------------------ #


def _is_report_generated(step: AdrStep) -> bool:
    """Check whether the last report generation completed successfully."""
    return step.get_method_state("generate_report").status == MethodStatus.Completed


def _get_export_buttons_disabled(step: AdrStep) -> tuple[bool, bool, bool]:
    """Get the disabled state of the PDF, PowerPoint, and HTML export buttons.

    Exports are only available after a successful report generation, and only if the file was exported.
    """
    if not _is_report_generated(step):
        return True, True, True
    return step.report_pdf == NO_ENTITY, step.report_pptx == NO_ENTITY, step.report_html_archive == NO_ENTITY


def _get_error_details(step: AdrStep, method_name: str, error: Exception | None = None) -> str:
    """Get the error message of a failed transaction, falling back to the raised exception."""
    try:
        exception_message = step.get_method_state(method_name).exception_message
    except Exception:
        logger.exception("Failed to get the state of the '%s' transaction.", method_name)
        exception_message = None
    return exception_message or (str(error) if error else "") or "Unknown error."


def _notification(notification_id: str, title: str, message: str, color: str) -> list[dict[str, Any]]:
    """Build a notification for the global notification container."""
    return [
        dict(
            id=notification_id,
            action="show",
            title=title,
            message=message,
            color=color,
            autoClose=5000 if color == "green" else False,
            withCloseButton=True,
        )
    ]


def _download_export(
    project: ExamplesSolution, file_handle: EntityHandle, file_name: str, export_label: str
) -> tuple[dict[str, Any] | Any, list[dict[str, Any]] | Any]:
    """Send an exported report file to the browser, or notify the user if it is not available."""
    step = project.steps.adr_step
    if not _is_report_generated(step) or file_handle == NO_ENTITY:
        message = f"The {export_label} export is not available. Generate the report first."
        logger.warning(message)
        return no_update, _notification("adr-page-export-notification", "Export unavailable", message, "orange")

    try:
        file_path = project.storage_scope.get_cached(file_handle)
        return dcc.send_bytes(file_path.read_bytes(), filename=file_name), no_update
    except Exception as error:
        logger.exception("Failed to download the %s export of the ADR reference report.", export_label)
        message = f"Failed to download the {export_label} export: {error}"
        return no_update, _notification("adr-page-export-notification", "Export failed", message, "red")


# ------------------------------------------------------------------------------------------------ #
# Callbacks
# ------------------------------------------------------------------------------------------------ #


@callback(
    Output("adr-page-availability-alert", "children"),
    Output("adr-page-generate-report-button", "disabled"),
    Output("adr-page-generate-report-button", "loading"),
    Output("adr-page-report-content", "children"),
    Output("adr-page-export-pdf-button", "disabled"),
    Output("adr-page-export-pptx-button", "disabled"),
    Output("adr-page-export-html-button", "disabled"),
    Input("url", "pathname"),
)
def initialize_adr_page(project: ExamplesSolution) -> tuple[Any, bool, bool, Any, bool, bool, bool]:
    """Check that ADR is available and set it up, then restore the last generated report."""
    disabled_page = (True, False, _report_empty_state(), True, True, True)

    availability = check_adr_availability()
    if not availability.is_available:
        logger.error("Ansys Dynamic Reporting is not available: %s", availability.message)
        return _adr_not_available_alert(availability.message), *disabled_page

    step = project.steps.adr_step
    try:
        project_tag = build_project_tag(project.project_id)
        if step.project_tag != project_tag:
            step.project_tag = project_tag
        step.initialize_adr()
        is_adr_set_up = step.get_method_state("initialize_adr").status == MethodStatus.Completed
        error = None
    except Exception as exception:
        is_adr_set_up = False
        error = exception

    if not is_adr_set_up:
        error_details = _get_error_details(step, "initialize_adr", error)
        logger.error("Serverless ADR could not be set up: %s", error_details)
        message = "Serverless ADR could not be set up. Check the ADR installation directory."
        return _adr_not_available_alert(message, error_details), *disabled_page

    pdf_disabled, pptx_disabled, html_disabled = _get_export_buttons_disabled(step)
    if _is_report_generated(step) and step.report_html_content:
        report_content = _report_iframe(step.report_html_content)
    else:
        report_content = _report_empty_state()
    return None, False, False, report_content, pdf_disabled, pptx_disabled, html_disabled


@callback(
    Output("adr-page-report-content", "children", allow_duplicate=True),
    Output("adr-page-export-pdf-button", "disabled", allow_duplicate=True),
    Output("adr-page-export-pptx-button", "disabled", allow_duplicate=True),
    Output("adr-page-export-html-button", "disabled", allow_duplicate=True),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("adr-page-generate-report-button", "n_clicks"),
    State("url", "pathname"),
    running=[(Output("adr-page-generate-report-button", "loading"), True, False)],
    prevent_initial_call=True,
)
def generate_report(n_clicks: int, project: ExamplesSolution) -> tuple[Any, bool, bool, bool, Any]:
    """Generate the report and enable the exports that succeeded."""
    if not n_clicks:
        return no_update, no_update, no_update, no_update, no_update

    step = project.steps.adr_step
    try:
        step.generate_report()
        error = None
    except Exception as exception:
        error = exception

    if error is not None or not _is_report_generated(step):
        error_details = _get_error_details(step, "generate_report", error)
        logger.error("ADR reference report generation failed: %s", error_details)
        notification = _notification(
            "adr-page-generate-notification", "Error", "The report generation failed. See the logs.", "red"
        )
        return _report_failed_state(error_details), True, True, True, notification

    pdf_disabled, pptx_disabled, html_disabled = _get_export_buttons_disabled(step)
    if pdf_disabled:
        notification = _notification(
            "adr-page-generate-notification",
            "Report generated",
            "The report was generated, but the PDF export is not available on this machine. See the logs.",
            "orange",
        )
    else:
        notification = _notification(
            "adr-page-generate-notification", "Success", "The report was generated successfully.", "green"
        )
    return _report_iframe(step.report_html_content), pdf_disabled, pptx_disabled, html_disabled, notification


@callback(
    Output("adr-page-download-pdf", "data"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("adr-page-export-pdf-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def export_report_pdf(n_clicks: int, project: ExamplesSolution) -> tuple[Any, Any]:
    """Download the report as a PDF file."""
    if not n_clicks:
        return no_update, no_update
    return _download_export(project, project.steps.adr_step.report_pdf, PDF_FILE_NAME, "PDF")


@callback(
    Output("adr-page-download-pptx", "data"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("adr-page-export-pptx-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def export_report_pptx(n_clicks: int, project: ExamplesSolution) -> tuple[Any, Any]:
    """Download the report as a PowerPoint presentation."""
    if not n_clicks:
        return no_update, no_update
    return _download_export(project, project.steps.adr_step.report_pptx, PPTX_FILE_NAME, "PowerPoint")


@callback(
    Output("adr-page-download-html", "data"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("adr-page-export-html-button", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def export_report_html(n_clicks: int, project: ExamplesSolution) -> tuple[Any, Any]:
    """Download the report as a ZIP archive containing the HTML file and its static assets."""
    if not n_clicks:
        return no_update, no_update
    return _download_export(project, project.steps.adr_step.report_html_archive, HTML_ARCHIVE_FILE_NAME, "HTML")
