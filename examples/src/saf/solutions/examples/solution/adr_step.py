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
"""ADR reference step.

This step generates a report showing every common item type of Ansys Dynamic Reporting (ADR)
with serverless ADR, and exports it as PDF, PowerPoint, and HTML (ZIP archive).

The transactions are regular (not long-running) on purpose: serverless ADR is set up once per
process, and regular transactions all run in the GLOW API process, where the ADR instance is kept.
"""

import logging
from pathlib import Path

from ansys.dynamicreporting.core.serverless import ADR
from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, transaction

from saf.solutions.examples.solution.logic.adr_reference.adr_instance import adr_lock, get_or_create_adr
from saf.solutions.examples.solution.logic.adr_reference.adr_settings import (
    AdrNotAvailableError,
    check_adr_availability,
)
from saf.solutions.examples.solution.logic.adr_reference.report_definition import build_item_filter
from saf.solutions.examples.solution.logic.adr_reference.report_exports import (
    export_report_html_archive,
    export_report_pdf,
    export_report_pptx,
    render_report_html,
)
from saf.solutions.examples.solution.logic.adr_reference.report_items import (
    ReportItemFiles,
    create_report_items,
    delete_report_items,
)
from saf.solutions.examples.solution.logic.adr_reference.report_pptx import recreate_pptx_input_item
from saf.solutions.examples.solution.logic.adr_reference.report_templates import recreate_report_templates

logger = logging.getLogger(__name__)

PLACEHOLDER_IMAGE_ASSET = "adr_reference/placeholder_image.png"
PLACEHOLDER_SCENE_ASSET = "adr_reference/placeholder_cube.avz"
PLACEHOLDER_FILE_ASSET = "adr_reference/placeholder_file.txt"


class AdrStep(StepModel):
    """Step generating the ADR reference report."""

    # Tag selecting the report items of the current project, set by the frontend
    project_tag: str = ""

    # Rendered report, displayed in the page
    report_html_content: str = ""

    # Exported report files
    report_pdf: EntityHandle = NO_ENTITY
    report_pptx: EntityHandle = NO_ENTITY
    report_html_archive: EntityHandle = NO_ENTITY

    @transaction()
    def initialize_adr(self) -> None:
        """Check that ADR is available, then create and set up the serverless ADR instance if needed."""
        availability = check_adr_availability()
        if not availability.is_available:
            logger.error("Ansys Dynamic Reporting is not available: %s", availability.message)
            raise AdrNotAvailableError(availability.message)

        try:
            get_or_create_adr()
        except Exception as error:
            logger.exception("Failed to set up serverless ADR.")
            raise RuntimeError(f"Failed to set up serverless ADR: {error}") from error

    @transaction(
        self=StepSpec(
            download=["project_tag"],
            upload=["report_html_content", "report_pdf", "report_pptx", "report_html_archive"],
        ),
    )
    def generate_report(self) -> None:
        """Create the report items and templates, render the report, and export it."""
        if not self.project_tag:
            raise ValueError("The project tag is not set. Initialize the ADR reference page first.")

        try:
            adr = get_or_create_adr()
        except Exception as error:
            logger.exception("Failed to get the serverless ADR instance.")
            raise RuntimeError(f"Failed to get the serverless ADR instance: {error}") from error

        item_filter = build_item_filter(self.project_tag)
        with adr_lock:
            self._create_report_content(adr)
            self._render_report(adr, item_filter)
            self._export_html_archive(adr, item_filter)
            self._export_pptx(adr, item_filter)
            self._export_pdf(adr, item_filter)

    def _create_report_content(self, adr: ADR) -> None:
        """Replace the report items of the project, and recreate the shared PowerPoint deck and templates."""
        try:
            delete_report_items(adr, self.project_tag)
            create_report_items(adr, self.project_tag, self._get_report_item_files())
            recreate_pptx_input_item(adr)
            recreate_report_templates(adr)
        except Exception as error:
            logger.exception("Failed to create the ADR reference report items and templates.")
            raise RuntimeError(f"Failed to create the report items and templates: {error}") from error

    def _get_report_item_files(self) -> ReportItemFiles:
        """Get local copies of the placeholder files used by the file-based report items."""
        return ReportItemFiles(
            image=self._get_asset_path(PLACEHOLDER_IMAGE_ASSET),
            scene=self._get_asset_path(PLACEHOLDER_SCENE_ASSET),
            file=self._get_asset_path(PLACEHOLDER_FILE_ASSET),
        )

    def _get_asset_path(self, asset_relative_path: str) -> Path:
        """Get the local path of a method asset."""
        asset_handle = self.transaction.get_asset_entity_handle(asset_relative_path)
        return Path(self.storage_scope.get_cached(asset_handle))

    def _render_report(self, adr: ADR, item_filter: str) -> None:
        """Render the report as HTML for display in the page."""
        try:
            self.report_html_content = render_report_html(adr, item_filter)
        except Exception as error:
            logger.exception("Failed to render the ADR reference report.")
            raise RuntimeError(f"Failed to render the report: {error}") from error

    def _export_html_archive(self, adr: ADR, item_filter: str) -> None:
        """Export the report as a ZIP archive containing the HTML file and its static assets."""
        try:
            archive_content = export_report_html_archive(adr, item_filter)
            self.report_html_archive = self.storage_scope.store_stream(
                archive_content, relative_location=Path("adr_reference_report.zip")
            )
        except Exception as error:
            logger.exception("Failed to export the ADR reference report as HTML.")
            raise RuntimeError(f"Failed to export the report as HTML: {error}") from error

    def _export_pptx(self, adr: ADR, item_filter: str) -> None:
        """Export the report as a PowerPoint presentation."""
        try:
            pptx_content = export_report_pptx(adr, item_filter)
            self.report_pptx = self.storage_scope.store_stream(
                pptx_content, relative_location=Path("adr_reference_report.pptx")
            )
        except Exception as error:
            logger.exception("Failed to export the ADR reference report as PowerPoint.")
            raise RuntimeError(f"Failed to export the report as PowerPoint: {error}") from error

    def _export_pdf(self, adr: ADR, item_filter: str) -> None:
        """Export the report as PDF. A failure is not fatal: the PDF export simply stays unavailable."""
        try:
            pdf_content = export_report_pdf(adr, item_filter)
            self.report_pdf = self.storage_scope.store_stream(
                pdf_content, relative_location=Path("adr_reference_report.pdf")
            )
        except Exception:
            logger.warning("PDF export failed; the PDF export stays unavailable.", exc_info=True)
            self.report_pdf = NO_ENTITY
