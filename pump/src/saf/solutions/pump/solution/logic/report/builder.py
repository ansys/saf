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

"""Build, render and export the pump report with ADR.

ADR is imported inside the functions: ``ansys-dynamicreporting-core`` is an optional
dependency, and importing this module must not fail when it is absent.

Every item carries the project's report tag, so one ADR database serves all projects and a
project's report only ever shows its own items.
"""

from dataclasses import dataclass
from datetime import date
import io
import logging
from pathlib import Path
import tempfile
from typing import Any
import zipfile

from saf.solutions.pump.solution.logic.report.content import (
    PumpReportData,
    assumption_rows,
    convergence_series,
    convergence_summary,
    html_table,
    key_result_rows,
    operating_point_rows,
    problem_description,
    secondary_result_rows,
)
from saf.solutions.pump.solution.logic.report.settings import ReportSettings

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "pump-report-v2"
"""Name of the root report template. Bump the suffix when the layout changes."""

REPORT_HTML_FILE_NAME = "pump_report.html"

_NO_ITEM = "A|i_name|eq|__no_item__;"
"""Filter matching nothing, for layout-only templates."""


@dataclass(frozen=True)
class RenderedReport:
    """The report in its three forms."""

    html: str
    """Template render shown in the app. Asset URLs point at the UI server."""
    html_zip: bytes
    """Standalone HTML export with its assets, zipped."""
    pdf_path: Path | None
    """PDF export, or ``None`` when ADR could not produce it."""


def item_filter(tag: str) -> str:
    """Return the ADR filter selecting the items of one project's report."""
    return f"A|i_tags|cont|{tag};"


def get_adr(settings: ReportSettings) -> Any:
    """Return the process-wide ADR instance, creating and setting it up on first use."""
    from ansys.dynamicreporting.core.serverless import ADR

    try:
        adr = ADR.get_instance()
    except RuntimeError:
        settings.media_directory.mkdir(parents=True, exist_ok=True)
        settings.static_directory.mkdir(parents=True, exist_ok=True)
        adr = ADR(
            ansys_installation=settings.adr_installation_directory,
            db_directory=str(settings.db_directory),
            static_directory=str(settings.static_directory),
            static_url="/static_assets/",
        )
    if not adr.is_setup:
        adr.setup(collect_static=True)
    return adr


def ensure_template(adr: Any) -> Any:
    """Return the report template, creating it in the database if needed."""
    from ansys.dynamicreporting.core.serverless import BasicLayout, PanelLayout, Template, TOCLayout

    existing = adr.query(query_type=Template, query=f"A|t_name|eq|{TEMPLATE_NAME};")
    if existing:
        return existing[0]

    def child(layout: Any, name: str, parent: Any, item_filter: str, params: str | None = None) -> Any:
        template = adr.create_template(layout, name=name, parent=parent)
        if params:
            template.params = params
        template.set_filter(item_filter)
        template.save()
        return template

    root = adr.create_template(BasicLayout, name=TEMPLATE_NAME, parent=None)
    root.save()

    cover = child(BasicLayout, "Cover", root, "A|i_tags|cont|section=cover;")
    child(
        BasicLayout,
        "Title",
        cover,
        _NO_ITEM,
        '{"HTML": "<h1>Pump Performance Report</h1>'
        '<h2><em>Impeller-volute frozen-rotor simulation</em></h2>", '
        '"properties": {"justification": "center"}}',
    )
    child(BasicLayout, "Report details", cover, "A|i_name|eq|report-details;")

    toc_section = child(BasicLayout, "Table of contents section", root, _NO_ITEM)
    child(TOCLayout, "Table of contents", toc_section, _NO_ITEM, '{"TOCitems": 1, "HTML": "<h2>Contents</h2>"}')

    problem = child(
        PanelLayout,
        "Engineering problem",
        root,
        "A|i_tags|cont|section=problem;",
        '{"properties": {"TOCItem": "1"}, "HTML": "<h2>1. Engineering Problem</h2>"}',
    )
    child(BasicLayout, "Description", problem, "A|i_name|eq|problem-description;")
    child(
        BasicLayout,
        "Operating point",
        problem,
        "A|i_name|eq|operating-point;",
        '{"properties": {"TOCLevel": "2"}, "HTML": "<h3>1.1 Operating Point and Solver Settings</h3>"}',
    )

    child(
        PanelLayout,
        "Assumptions",
        root,
        "A|i_tags|cont|section=assumptions;",
        '{"properties": {"TOCItem": "1"}, "HTML": "<h2>2. Modelling Assumptions</h2>"}',
    )

    results = child(
        PanelLayout,
        "Results",
        root,
        "A|i_tags|cont|section=results;",
        '{"properties": {"TOCItem": "1"}, "HTML": "<h2>3. Results</h2>"}',
    )
    child(
        BasicLayout,
        "Convergence",
        results,
        "A|i_name|eq|convergence;",
        '{"properties": {"TOCLevel": "2"}, "HTML": "<h3>3.1 Convergence</h3>"}',
    )
    child(BasicLayout, "Head history", results, "A|i_name|eq|convergence-head;")
    child(BasicLayout, "Outlet pressure history", results, "A|i_name|eq|convergence-outlet-pressure;")
    child(
        BasicLayout,
        "Performance",
        results,
        "A|i_name|eq|key-results;",
        '{"properties": {"TOCLevel": "2"}, "HTML": "<h3>3.2 Pump Performance</h3>"}',
    )
    child(
        BasicLayout,
        "Flow quantities",
        results,
        "A|i_name|eq|secondary-results;",
        '{"properties": {"TOCLevel": "2"}, "HTML": "<h3>3.3 Flow Quantities</h3>"}',
    )
    child(
        BasicLayout,
        "Static pressure",
        results,
        "A|i_name|eq|pressure-contour;",
        '{"properties": {"TOCLevel": "2"}, "HTML": "<h3>3.4 Static Pressure on the Mid-Plane</h3>"}',
    )
    return root


def clear_items(adr: Any, tag: str) -> None:
    """Delete the items of a previous report of the same project."""
    from ansys.dynamicreporting.core.serverless import Item

    items = adr.query(Item, query=item_filter(tag))
    if items:
        items.delete()


def create_items(adr: Any, data: PumpReportData, contour_image: Path, tag: str) -> None:
    """Create the report items of one project."""
    from ansys.dynamicreporting.core.serverless import HTML, Image

    quantity_headers = ("Quantity", "Value", "Unit")

    def add_html(name: str, section: str, content: str) -> None:
        adr.create_item(HTML, name=name, content=content, tags=f"section={section} {tag}")

    details = html_table(
        ("", ""),
        [("Project", data.project_name or "-"), ("Date", date.today().strftime("%B %d, %Y"))],
    )
    add_html("report-details", "cover", details)
    add_html("problem-description", "problem", problem_description())
    add_html("operating-point", "problem", html_table(quantity_headers, operating_point_rows(data)))
    add_html("assumptions", "assumptions", html_table(("Topic", "Assumption"), assumption_rows()))
    add_html("convergence", "results", convergence_summary(data))
    _create_convergence_plots(adr, data, tag)
    add_html("key-results", "results", html_table(quantity_headers, key_result_rows(data)))
    add_html("secondary-results", "results", html_table(quantity_headers, secondary_result_rows(data)))
    adr.create_item(Image, name="pressure-contour", content=str(contour_image), tags=f"section=results {tag}")


def _create_convergence_plots(adr: Any, data: PumpReportData, tag: str) -> None:
    """Create one line plot per monitored quantity against the iteration number.

    ADR plots the rows of a table: the ``Iteration`` row is the x axis and the other row the
    curve. Head and outlet pressure get a plot each, as their units differ.
    """
    from ansys.dynamicreporting.core.serverless import Table
    import numpy as np

    series = convergence_series(data)
    if series is None:
        return
    plots = (
        ("convergence-head", "Pump head", "Head (m)", series.head_m),
        (
            "convergence-outlet-pressure",
            "Outlet total pressure",
            "Outlet total pressure (Pa)",
            series.outlet_total_pressure_pa,
        ),
    )
    for name, title, y_title, values in plots:
        table = adr.create_item(
            Table,
            name=name,
            content=np.array([series.iterations, values], dtype=float),
            tags=f"section=results {tag}",
        )
        table.labels_row = ["Iteration", title]
        table.plot = "line"
        table.xaxis = "Iteration"
        table.plot_title = f"{title} history"
        table.xtitle = "Iteration"
        table.ytitle = y_title
        table.save()


def render_report(
    settings: ReportSettings, data: PumpReportData, contour_image: Path, tag: str, output_dir: Path
) -> RenderedReport:
    """Rebuild the project's report items and return the report as HTML, ZIP and PDF.

    Parameters
    ----------
    settings : ReportSettings
        ADR configuration.
    data : PumpReportData
        Operating point and results to report.
    contour_image : Path
        Static pressure contour image.
    tag : str
        Tag identifying the project's items in the shared ADR database.
    output_dir : Path
        Folder where the PDF is written.
    """
    adr = get_adr(settings)
    template = ensure_template(adr)
    clear_items(adr, tag)
    create_items(adr, data, contour_image, tag)

    selection = item_filter(tag)
    html = template.render(context={}, item_filter=selection)

    with tempfile.TemporaryDirectory() as scratch:
        export_dir = Path(scratch)
        adr.export_report_as_html(export_dir, filename=REPORT_HTML_FILE_NAME, item_filter=selection, name=TEMPLATE_NAME)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(export_dir.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(export_dir))

    # PDF export drives a headless browser and is the most fragile part of ADR: losing it
    # must not cost the user the HTML report.
    pdf_path: Path | None = output_dir / "pump_report.pdf"
    try:
        adr.export_report_as_pdf(name=TEMPLATE_NAME, filename=str(pdf_path), item_filter=selection)
    except Exception:
        logger.warning("PDF export of the pump report failed.", exc_info=True)
        pdf_path = None

    return RenderedReport(html=html, html_zip=buffer.getvalue(), pdf_path=pdf_path)
