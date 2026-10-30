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
"""Templates of the ADR reference report.

Templates define the layout of the report and select the items to display with filters.
Two report templates are created in the ADR database:

- ``adr-reference-report``: HTML report (also used for the PDF export). It contains a table of
  contents and one section template per item type.
- ``adr-reference-pptx-report``: PowerPoint report, built from an input deck whose placeholders
  are filled with the report items.

The templates are shared by all projects. They are recreated at every report generation, so that
they always match this code. Deleting a template also deletes its child templates.
"""

import logging

from ansys.dynamicreporting.core.serverless import ADR, BasicLayout, PanelLayout, PPTXLayout, Template, TOCLayout

from saf.solutions.examples.solution.logic.adr_reference.report_definition import (
    PPTX_INPUT_ITEM_NAME,
    PPTX_TEMPLATE_NAME,
    REPORT_SECTIONS,
    REPORT_TEMPLATE_NAME,
    REPORT_TITLE,
    ReportSection,
)

logger = logging.getLogger(__name__)

PPTX_OUTPUT_FILE_NAME = "adr_reference_report.pptx"

# Filter matching no item, for templates that only display their HTML header.
_NO_ITEM_FILTER = "A|i_name|eq|__NonexistentName__;"


def delete_template(adr: ADR, template_name: str) -> None:
    """Delete the templates with the given name, together with their child templates."""
    templates = adr.query(Template, query=f"A|t_name|eq|{template_name};")
    if templates:
        logger.info("Deleting the '%s' ADR template.", template_name)
        templates.delete()


def create_report_template(adr: ADR) -> Template:
    """Create the HTML report template: a title, a table of contents, and one section per item type.

    If the creation fails, the partially created template is deleted.
    """
    logger.info("Creating the '%s' ADR template.", REPORT_TEMPLATE_NAME)
    report_template = adr.create_template(BasicLayout, name=REPORT_TEMPLATE_NAME, parent=None)
    report_template.set_html(
        f"<h1>{REPORT_TITLE}</h1>"
        "<p>This report shows every common item type of Ansys Dynamic Reporting (ADR). "
        "Each section explains an item type and shows an example item.</p>"
    )
    report_template.save()

    try:
        _create_table_of_contents_template(adr, report_template)
        for section_number, section in enumerate(REPORT_SECTIONS, start=1):
            create_section_template(adr, report_template, section, section_number)
    except Exception:
        logger.exception("Failed to create the '%s' ADR template. Deleting it.", REPORT_TEMPLATE_NAME)
        report_template.delete()
        raise

    return report_template


def _create_table_of_contents_template(adr: ADR, parent: Template) -> Template:
    """Create the table of contents listing the sections flagged as TOC items."""
    toc_template = adr.create_template(TOCLayout, name="adr-reference-table-of-contents", parent=parent)
    toc_template.set_html("<h2>Table of contents</h2>")
    toc_template.add_params({"TOCitems": 1})
    toc_template.set_filter(_NO_ITEM_FILTER)
    toc_template.save()
    return toc_template


def create_section_template(adr: ADR, parent: Template, section: ReportSection, section_number: int) -> Template:
    """Create the template of one section: a title, the explanation of the item type, and the example item."""
    section_template = adr.create_template(PanelLayout, name=section.template_name, parent=parent)
    section_template.set_html(f"<h2>{section_number}. {section.title}</h2><p>{section.description}</p>")
    section_template.add_property({"TOCItem": "1"})
    section_template.set_filter(f"A|i_name|eq|{section.item_name};")
    section_template.save()
    return section_template


def create_pptx_report_template(adr: ADR) -> Template:
    """Create the PowerPoint report template.

    The template fills the placeholders of the input deck stored in the ``PPTX_INPUT_ITEM_NAME``
    File item, using every slide of the deck.
    """
    logger.info("Creating the '%s' ADR template.", PPTX_TEMPLATE_NAME)
    pptx_template = adr.create_template(PPTXLayout, name=PPTX_TEMPLATE_NAME, parent=None)
    pptx_template.input_pptx = PPTX_INPUT_ITEM_NAME
    pptx_template.output_pptx = PPTX_OUTPUT_FILE_NAME
    pptx_template.use_all_slides = "1"
    pptx_template.save()
    return pptx_template


def recreate_report_templates(adr: ADR) -> None:
    """Delete the HTML and PowerPoint report templates if they exist, then create them."""
    delete_template(adr, REPORT_TEMPLATE_NAME)
    create_report_template(adr)
    delete_template(adr, PPTX_TEMPLATE_NAME)
    create_pptx_report_template(adr)
