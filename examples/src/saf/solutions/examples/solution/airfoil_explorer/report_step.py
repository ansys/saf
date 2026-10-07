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

from __future__ import annotations

from datetime import date
import io
import logging
from pathlib import Path
import tempfile
from typing import Tuple
import zipfile

from ansys.dynamicreporting.core.serverless import ADR, Dataset, Item, Session, Template
from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, transaction
import numpy as np

from saf.solutions.examples.solution.airfoil_explorer.airfoil_setup_step import AirfoilSetupStep
from saf.solutions.examples.solution.airfoil_explorer.logic.report.report_items import (
    create_airfoil_definition_items,
    create_cover_page_items,
    create_introduction_items,
    create_simulation_items,
    create_simulation_result_items,
    create_summary_items,
)
from saf.solutions.examples.solution.airfoil_explorer.logic.report.report_templates import create_report_template
from saf.solutions.examples.solution.airfoil_explorer.logic.report.report_utilities import (
    ADR_INSTALLATION_DIRECTORY,
    PATH_TO_ADR_DB,
)
from saf.solutions.examples.solution.airfoil_explorer.simulation_step import SimulationStep

app_logger = logging.getLogger(__name__)


class ReportStep(StepModel):
    """Step definition of the report_step step."""

    export_is_disabled: bool = True
    load_report_is_disabled: bool = True
    report_html_content: str = ""
    report_html_file: EntityHandle = NO_ENTITY
    report_pdf: EntityHandle = NO_ENTITY

    # Report item identifiers
    session_guid: str = ""
    dataset_guid: str = ""
    project_name: str = ""
    project_tag: str = ""
    study_id: int = 0
    study_count: int = 0

    def _set_adr_directories(self) -> Tuple[str, str]:
        return str(PATH_TO_ADR_DB), str(ADR_INSTALLATION_DIRECTORY)

    def _get_or_create_adr(self, adr_install: str, adr_db: str, static_directory: Path) -> ADR:
        """Get existing ADR instance, or create one if none exists."""
        try:
            return ADR.get_instance()
        except RuntimeError:
            app_logger.info("ADR instance not found; creating a new ADR instance.")
            return ADR(
                ansys_installation=adr_install,
                db_directory=adr_db,
                static_directory=str(static_directory),
                static_url="/static_assets/",
            )

    @transaction(self=StepSpec(upload=["session_guid", "dataset_guid"]))
    def setup_adr_instance(self, stored_session_guid: str, stored_dataset_guid: str) -> None:
        """Set up ADR instance."""
        adr_db, adr_install = self._set_adr_directories()

        static_directory = Path(adr_db).parent / "static_assets"
        static_directory.mkdir(parents=True, exist_ok=True)
        Path(adr_db, "media").mkdir(parents=True, exist_ok=True)

        adr_obj = self._get_or_create_adr(adr_install=adr_install, adr_db=adr_db, static_directory=static_directory)

        if not adr_obj.is_setup:
            app_logger.info("Setting up ADR (collect_static=True).")
            adr_obj.setup(collect_static=True)

        if not stored_session_guid:
            self.session_guid = adr_obj.session.guid
            self.dataset_guid = adr_obj.dataset.guid
            app_logger.info("Initialized new ADR session/dataset GUIDs on step.")

        else:
            app_logger.info("Reusing stored ADR session/dataset GUIDs on step.")
            self._set_session_and_dataset(adr_obj, stored_session_guid, stored_dataset_guid)

    @transaction()
    def create_report_templates(self) -> None:
        """Create report templates."""
        adr_obj = ADR.get_instance()
        report_template = adr_obj.query(query_type=Template, query="A|t_name|eq|solution-report;")
        if not report_template:
            create_report_template(adr_obj)

    @transaction(self=StepSpec(download=["project_name", "project_tag", "study_count"]))
    def create_static_report_items(self) -> None:
        """Create static report items."""
        adr_obj = ADR.get_instance()

        # Remove previously generated static report content
        sections = ["cover-page", "introduction", "summary"]
        for section in sections:
            items_to_delete = adr_obj.query(Item, query=f"A|i_tags|cont|section={section} {self.project_tag};")

            if items_to_delete:
                app_logger.info(f"Deleting existing static report items in section '{section}'.")
                items_to_delete.delete()

        # Resolve assets required for static content
        logo_image_asset_handle = self.transaction.get_asset_entity_handle(
            "sample_report_data/ansys-solutions-logo-white-bg.png"
        )
        report_image_asset_handle = self.transaction.get_asset_entity_handle("sample_report_data/airfoil_explorer.png")

        # Create static report sections
        report_date = date.today().strftime("%B %d, %Y")
        create_cover_page_items(
            adr_obj,
            self.storage_scope.get_cached(logo_image_asset_handle).as_posix(),
            self.storage_scope.get_cached(report_image_asset_handle).as_posix(),
            1,
            report_date,
            self.project_name,
            self.study_count,
            self.project_tag,
        )
        create_introduction_items(adr_obj, self.project_tag)
        create_summary_items(adr_obj, self.project_tag)

    @transaction(
        self=StepSpec(download=["session_guid", "dataset_guid", "study_id", "project_tag"]),
        airfoil_setup_step=StepSpec(
            download=[
                "camber_max_percent",
                "camber_pos_percent",
                "thickness_max_percent",
                "chord_length",
                "airfoil_shape_png_handle",
            ]
        ),
        simulation_step=StepSpec(
            download=[
                "circumferential_points",
                "radial_points",
                "angle_of_attack_deg",
                "free_stream_velocity",
                "mesh_png_handle",
                "flow_png_handle",
            ]
        ),
    )
    def create_report_setup_and_result_items(
        self, airfoil_setup_step: AirfoilSetupStep, simulation_step: SimulationStep
    ) -> None:
        """Create report setup and result report items."""
        adr_obj = ADR.get_instance()
        app_logger.info("Creating report setup and result items.")

        # Remove previously generated simulation-related report content
        sections_to_reset = ("airfoil-definition", "simulation-method", "simulation-results")

        for section in sections_to_reset:
            items = adr_obj.query(Item, query=f"A|i_tags|cont|section={section} {self.project_tag};")

            if items:
                app_logger.info(
                    "Deleting existing report items",
                    extra={"section": section, "project_tag": self.project_tag},
                )
                items.delete()

        # Collect input values for report tables
        airfoil_parameter_values = np.array(
            [
                airfoil_setup_step.camber_max_percent,
                airfoil_setup_step.camber_pos_percent,
                airfoil_setup_step.thickness_max_percent,
                airfoil_setup_step.chord_length,
            ]
        )
        grid_values = np.array(
            [simulation_step.circumferential_points, simulation_step.radial_points, 5, "O-type structured mesh"],
            dtype="|S",
        )
        simulation_values = np.array(
            [simulation_step.angle_of_attack_deg, simulation_step.free_stream_velocity], dtype="|S"
        )

        # Resolve cached assets
        airfoil_png = self.storage_scope.get_cached(airfoil_setup_step.airfoil_shape_png_handle)
        mesh_png = self.storage_scope.get_cached(simulation_step.mesh_png_handle)
        flow_png = self.storage_scope.get_cached(simulation_step.flow_png_handle)

        # Create report items
        create_airfoil_definition_items(adr_obj, airfoil_parameter_values, airfoil_png, self.study_id, self.project_tag)
        create_simulation_items(adr_obj, grid_values, simulation_values, mesh_png, self.study_id, self.project_tag)
        create_simulation_result_items(adr_obj, flow_png, self.study_id, self.project_tag)

    def _write_report_content_to_pdf_file(self, adr_obj) -> None:
        """Export the ADR report as PDF and persist entity handle. Non-fatal on failure."""
        try:
            pdf_file = self.storage_scope.get_storage_root() / "airfoil_report.pdf"
            item_filter = (
                f"A|s_guid|eq|{self.session_guid};"
                f"A|d_guid|eq|{self.dataset_guid};"
                f"A|i_tags|cont|{self.project_tag};"
            )
            adr_obj.export_report_as_pdf(
                name="solution-report",
                filename=pdf_file,
                item_filter=item_filter,
            )
            self.report_pdf = self.storage_scope.store(pdf_file)
        except Exception:
            app_logger.warning("PDF export failed; report_pdf will remain unset.", exc_info=True)
            self.report_pdf = NO_ENTITY

    def _write_report_content_to_html_file(self, adr_obj) -> None:
        """Render the ADR report and persist both the in-app content and a downloadable bundle.

        Two artifacts are produced:

        * ``report_html_content`` -- the raw template render, shown in the in-app viewer
          where GLOW serves the referenced static/media assets.
        * ``report_html_file`` -- a ZIP archive of the report exported via
          ``export_report_as_html``. ADR emits a standalone ``airfoil_report.html`` plus
          sibling asset folders (``media/``, ``ansys*/``, ``webfonts/``); the HTML
          references them with relative paths, so the whole directory is zipped to keep
          the download self-contained. Unzip and open ``airfoil_report.html`` offline.

        The archive is built in memory and handed to BDM via ``store_stream`` so GLOW
        owns writing it into (and resolving it within) the storage root. This avoids
        manually materialising a file under the storage root and then asking ``store``
        to re-resolve it -- a round-trip that proved fragile on Windows CI runners.
        """
        report_template = adr_obj.query(query_type=Template, query="A|t_name|eq|solution-report;")

        if not report_template:
            msg = "ADR report template 'solution-report' was not found."
            app_logger.error(msg)
            raise ValueError(msg)

        item_filter = (
            f"A|s_guid|eq|{self.session_guid};" f"A|d_guid|eq|{self.dataset_guid};" f"A|i_tags|cont|{self.project_tag};"
        )

        try:
            html_content = report_template[0].render(context={}, item_filter=item_filter)
        except Exception:
            app_logger.exception("Failed to render ADR report template 'solution-report'.")
            raise

        self.report_html_content = html_content

        # Export the report bundle (HTML + asset folders) to a scratch directory, zip the
        # whole tree in memory, and let BDM persist the bytes. store_stream writes the
        # archive into the storage root using GLOW's own path resolution, so we never
        # place a file at a path we compute and then ask store() to find it again.
        with tempfile.TemporaryDirectory() as scratch:
            export_dir = Path(scratch)
            adr_obj.export_report_as_html(
                export_dir,
                filename="airfoil_report.html",
                item_filter=item_filter,
                name="solution-report",
            )
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in sorted(export_dir.rglob("*")):
                    if file.is_file():
                        archive.write(file, file.relative_to(export_dir))
            self.report_html_file = self.storage_scope.store_stream(
                buffer.getvalue(), relative_location=Path("airfoil_report.zip")
            )

    @transaction(
        self=StepSpec(
            download=["session_guid", "dataset_guid", "project_tag"],
            upload=["report_html_content", "report_html_file", "report_pdf"],
        ),
        enable_termination_event=True,
    )
    def get_report(self) -> None:
        """Get the report HTML content and export HTML and PDF files."""
        adr_obj = ADR.get_instance()
        self._write_report_content_to_pdf_file(adr_obj)
        self._write_report_content_to_html_file(adr_obj)

    def _set_session_and_dataset(self, adr_obj, session_guid, dataset_guid):
        session = Session.get(guid=session_guid)
        dataset = Dataset.get(guid=dataset_guid)
        adr_obj.set_default_session(session)
        adr_obj.set_default_dataset(dataset)
