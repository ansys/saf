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
"""Rendering and exports of the ADR reference report (HTML, ZIP archive of the HTML report, PowerPoint, PDF)."""

import asyncio
import io
import logging
from pathlib import Path
import sys
import tempfile
from threading import Lock, get_ident
import zipfile

from ansys.dynamicreporting.core.serverless import ADR

from saf.solutions.examples.solution.logic.adr_report.report_definition import PPTX_TEMPLATE_NAME, REPORT_TEMPLATE_NAME

logger = logging.getLogger(__name__)

HTML_EXPORT_FILE_NAME = "adr_reference_report.html"
_PDF_EXPORT_LOCK = Lock()


class _RenderThreadProactorPolicy(asyncio.AbstractEventLoopPolicy):
    """Use a Proactor loop only in the PDF-rendering thread."""

    def __init__(self, original_policy: asyncio.AbstractEventLoopPolicy, render_thread_id: int) -> None:
        self._original_policy = original_policy
        self._render_thread_id = render_thread_id

    def get_event_loop(self) -> asyncio.AbstractEventLoop:
        return self._original_policy.get_event_loop()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        self._original_policy.set_event_loop(loop)

    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        if get_ident() == self._render_thread_id:
            return asyncio.ProactorEventLoop()
        return self._original_policy.new_event_loop()


def render_report_html(adr: ADR, item_filter: str) -> str:
    """Render the report as HTML, to be displayed in the application.

    The rendered HTML references the ADR media and static files with the ``/media/`` and
    ``/static_assets/`` URLs, which are served by the routes registered in ``report_routes``.
    """
    return adr.render_report(name=REPORT_TEMPLATE_NAME, item_filter=item_filter)


def export_report_html_archive(adr: ADR, item_filter: str) -> bytes:
    """Export the report as a standalone HTML file with its static assets, packed in a ZIP archive.

    ADR writes the HTML file next to the folders holding its media and static assets (images, CSS,
    JavaScript, fonts), referenced with relative paths. The whole folder is zipped so that the report
    can be opened offline after extracting the archive.

    Returns
    -------
    bytes
        Content of the ZIP archive.
    """
    with tempfile.TemporaryDirectory() as scratch_directory:
        export_directory = Path(scratch_directory)
        adr.export_report_as_html(
            export_directory,
            filename=HTML_EXPORT_FILE_NAME,
            name=REPORT_TEMPLATE_NAME,
            item_filter=item_filter,
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(export_directory.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(export_directory))
    return buffer.getvalue()


def export_report_pptx(adr: ADR, item_filter: str) -> bytes:
    """Export the report as a PowerPoint presentation.

    Returns
    -------
    bytes
        Content of the PowerPoint file.
    """
    return adr.render_report_as_pptx(name=PPTX_TEMPLATE_NAME, item_filter=item_filter)


def export_report_pdf(adr: ADR, item_filter: str) -> bytes:
    """Export the report as a PDF document.

    ``ansys-dynamicreporting-core`` renders PDFs with the headless browser shipped with ADR.
    On Windows, Uvicorn's hot-reload mode selects an event loop that cannot launch Playwright's
    driver subprocess. Use a Proactor loop for this rendering thread while preserving the original
    event-loop policy for the API server and other threads.

    Returns
    -------
    bytes
        Content of the PDF file.
    """
    if sys.platform != "win32":
        return adr.render_report_as_browser_pdf(
            name=REPORT_TEMPLATE_NAME,
            item_filter=item_filter,
        )

    with _PDF_EXPORT_LOCK:
        original_policy = asyncio.get_event_loop_policy()
        if isinstance(original_policy, asyncio.WindowsSelectorEventLoopPolicy):
            asyncio.set_event_loop_policy(_RenderThreadProactorPolicy(original_policy, get_ident()))
            try:
                return adr.render_report_as_browser_pdf(
                    name=REPORT_TEMPLATE_NAME,
                    item_filter=item_filter,
                )
            finally:
                asyncio.set_event_loop_policy(original_policy)

        return adr.render_report_as_browser_pdf(
            name=REPORT_TEMPLATE_NAME,
            item_filter=item_filter,
        )
