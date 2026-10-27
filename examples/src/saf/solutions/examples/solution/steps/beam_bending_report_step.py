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
"""
Provide the report generation step for the beam bending example.

This module defines the ``BeamBendingReportStep`` class, which generates
an engineering report summarizing the analytical and MAPDL simulation results.
"""
import logging
from pathlib import Path
from typing import Tuple

from ansys.dynamicreporting.core.serverless import ADR, Dataset, Item, Session, Template
from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, transaction
import numpy as np

from saf.solutions.examples.solution.steps.beam_bending_step import BeamBendingStep
from saf.solutions.examples.solution.scripts.beam_bending.report.adr_config import get_adr_config
from saf.solutions.examples.solution.scripts.beam_bending.report.report_items import (
    create_conclusion_items,
    create_introduction_items,
    create_model_items,
    create_results_items,
    create_setup_items,
)
from saf.solutions.examples.solution.scripts.beam_bending.report.report_templates import create_report_template

logger = logging.getLogger(__name__)


class BeamBendingReportStep(StepModel):
    """Step model responsible for generating an engineering report based on the results of the simulation."""

    # Frontend persistence
    export_is_disabled: bool = True
    report_html_content: str = ""

    # Backend data model
    session_guid: str = ""
    dataset_guid: str = ""
    project_tag: str = ""

    # File storage
    report_pdf: EntityHandle = NO_ENTITY

    def _get_adr_paths(self) -> Tuple[str, str]:
        adr_config = get_adr_config()
        return str(adr_config["PATH_TO_ADR_DB"]), str(adr_config["ADR_INSTALLATION_DIRECTORY"])

    def _get_or_create_adr(self, adr_install: str, adr_db: str, static_directory: Path) -> ADR:
        """Get existing ADR instance, or create one if none exists."""
        try:
            return ADR.get_instance()
        except RuntimeError:
            logger.info("ADR instance not found; creating a new ADR instance.")
            return ADR(
                ansys_installation=adr_install,
                db_directory=adr_db,
                static_directory=str(static_directory),
                static_url="/static_assets/",
            )

    @transaction(self=StepSpec(upload=["session_guid", "dataset_guid"]))
    def setup_adr_instance(self, stored_session_guid: str, stored_dataset_guid: str) -> None:
        """Set up ADR instance."""
        adr_db, adr_install = self._get_adr_paths()

        static_directory = Path(adr_db).parent / "static_assets"
        static_directory.mkdir(parents=True, exist_ok=True)

        adr = self._get_or_create_adr(adr_install=adr_install, adr_db=adr_db, static_directory=static_directory)

        if not adr.is_setup:
            logger.info("Setting up ADR (collect_static=True).")
            adr.setup(collect_static=True)

        if not stored_session_guid:
            self.session_guid = adr.session.guid
            self.dataset_guid = adr.dataset.guid
            logger.info("Initialized new ADR session/dataset GUIDs on step.")

        else:
            logger.info("Reusing stored ADR session/dataset GUIDs on step.")
            self._set_session_and_dataset(adr, stored_session_guid, stored_dataset_guid)

    @transaction()
    def create_report_templates(self) -> None:
        """Create report templates."""
        adr = ADR.get_instance()
        report_template = adr.query(query_type=Template, query="A|t_name|eq|solution-report;")
        if not report_template:
            create_report_template(adr)

    @transaction(self=StepSpec(download=["session_guid", "dataset_guid", "project_tag"]))
    def create_static_report_items(self) -> None:
        """Create static report items."""
        adr = ADR.get_instance()

        items_to_delete = adr.query(Item, query=f"A|i_tags|cont|{self.project_tag};")
        if items_to_delete:
            logger.info(
                "Removing %d existing report items for project_tag=%s",
                len(items_to_delete),
                self.project_tag,
            )
            items_to_delete.delete()

        report_image_asset_handle = self.transaction.get_asset_entity_handle("beam_model.png")

        logger.info("Creating static report items")

        try:
            logger.info("Creating introduction section")
            create_introduction_items(adr, self.project_tag)

            logger.info("Creating model section")
            create_model_items(
                adr, self.storage_scope.get_cached(report_image_asset_handle).as_posix(), self.project_tag
            )

            logger.info("Creating conclusion section")
            create_conclusion_items(adr, self.project_tag)

        except Exception:
            logger.exception("Failed while creating static report items")
            raise

    @transaction(
        self=StepSpec(download=["session_guid", "dataset_guid", "project_tag"]),
        beam_bending_step=StepSpec(
            download=[
                "theoretical_deflection",
                "mapdl_deflection",
                "length_a",
                "length_b",
                "diameter",
                "elasticity_modulus",
                "load",
                "nbr_of_pts",
            ]
        ),
    )
    def create_report_setup_and_result_items(self, beam_bending_step: BeamBendingStep) -> None:
        """Create report setup and results items."""
        adr = ADR.get_instance()

        # Remove previously generated simulation-related report content
        sections_to_reset = ("setup", "results")

        for section in sections_to_reset:
            items = adr.query(Item, query=f"A|i_tags|cont|section={section} {self.project_tag};")

            if items:
                logger.info(
                    "Deleting existing report items",
                    extra={"section": section, "project_tag": self.project_tag},
                )
                items.delete()

        parameter_names = [
            "Length a [mm]",
            "Length b [mm]",
            "Diameter [mm]",
            "Elastic Modulus [MPa]",
            "Load [N]",
            "Number of nodes",
        ]
        parameter_values = np.array(
            [
                beam_bending_step.length_a,
                beam_bending_step.length_b,
                beam_bending_step.diameter,
                beam_bending_step.elasticity_modulus,
                beam_bending_step.load,
                beam_bending_step.nbr_of_pts,
            ]
        )
        # Analytical solution
        x_analytical, y_analytical = beam_bending_step.theoretical_deflection

        # MAPDL solution
        x_mapdl, y_mapdl = beam_bending_step.mapdl_deflection

        analytical_deflection = np.array(
            [
                x_analytical,
                y_analytical,
            ]
        )

        mapdl_deflection = np.array(
            [
                x_mapdl,
                y_mapdl,
            ]
        )

        try:
            logger.info("Creating setup table")
            create_setup_items(adr, parameter_names, parameter_values, self.project_tag)

            logger.info("Creating results items")
            create_results_items(adr, analytical_deflection, mapdl_deflection, self.project_tag)

        except Exception:
            logger.exception(
                "Failed to create report setup/results items for project_tag=%s",
                self.project_tag,
            )
            raise

    @transaction(
        self=StepSpec(
            download=["session_guid", "dataset_guid", "project_tag"],
            upload=["report_html_content"],
        ),
    )
    def get_report(self) -> None:
        """Get the report content."""
        adr = ADR.get_instance()

        report_template = adr.query(query_type=Template, query="A|t_name|eq|solution-report;")

        if not report_template:
            logger.error("ADR report template 'solution-report' was not found.")
            self.report_html_content = "<h2>Report template missing</h2>" "<p>The ADR report was not found.</p>"
        else:
            item_filter = (
                f"A|s_guid|eq|{self.session_guid};"
                f"A|d_guid|eq|{self.dataset_guid};"
                f"A|i_tags|cont|{self.project_tag};"
            )

            try:
                html_content = report_template[0].render(context={}, item_filter=item_filter)
            except Exception:
                logger.exception("Failed to get ADR report template 'solution-report'.")
                raise

            self.report_html_content = html_content

    def _set_session_and_dataset(self, adr, session_guid, dataset_guid):
        session = Session.get(guid=session_guid)
        dataset = Dataset.get(guid=dataset_guid)
        adr.set_default_session(session)
        adr.set_default_dataset(dataset)
