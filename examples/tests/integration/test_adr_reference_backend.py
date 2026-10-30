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

"""Integration tests for the ADR reference step transactions."""

import io
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
import zipfile

from ansys.saf.glow.solution import NO_ENTITY, MethodStatus
from pptx import Presentation
import pytest

from saf.solutions.examples.solution import adr_step
from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.logic.adr_reference.report_definition import (
    REPORT_SECTIONS,
    build_item_filter,
    build_project_tag,
)

PROJECT_TAG = build_project_tag("integration-test")


@pytest.fixture
def mocked_report_logic(mocker: Any) -> dict[str, MagicMock]:
    """Replace the ADR logic used by the step with mocks returning valid exports."""
    mocks = {
        name: mocker.patch.object(adr_step, name)
        for name in (
            "get_or_create_adr",
            "delete_report_items",
            "create_report_items",
            "recreate_pptx_input_item",
            "recreate_report_templates",
            "render_report_html",
            "export_report_html_archive",
            "export_report_pptx",
            "export_report_pdf",
        )
    }
    mocks["render_report_html"].return_value = "<html>ADR reference report</html>"
    mocks["export_report_html_archive"].return_value = b"zip"
    mocks["export_report_pptx"].return_value = b"pptx"
    mocks["export_report_pdf"].return_value = b"pdf"
    return mocks


def test_initialize_adr_fails_when_adr_is_not_configured(
    client_project: ExamplesSolution, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify the initialization fails and logs an explicit message when ADR is not configured."""
    monkeypatch.setenv("ADR_INSTALLATION_DIRECTORY", "")
    step = client_project.steps.adr_step

    with pytest.raises(Exception):
        step.initialize_adr()

    assert step.get_method_state("initialize_adr").status == MethodStatus.Failed
    assert "ADR_INSTALLATION_DIRECTORY environment variable is not set" in caplog.text


def test_initialize_adr_sets_up_adr_when_configured(
    client_project: ExamplesSolution, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: Any
) -> None:
    """Verify the initialization creates the ADR instance when ADR is configured."""
    monkeypatch.setenv("ADR_INSTALLATION_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("GLOW_PROJECT_FILES_DIRECTORY", str(tmp_path / "project_files"))
    get_or_create_adr = mocker.patch.object(adr_step, "get_or_create_adr")
    step = client_project.steps.adr_step

    step.initialize_adr()

    assert step.get_method_state("initialize_adr").status == MethodStatus.Completed
    get_or_create_adr.assert_called_once()


def test_initialize_adr_fails_when_adr_setup_fails(
    client_project: ExamplesSolution,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mocker: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify an ADR setup error fails the initialization and is logged."""
    monkeypatch.setenv("ADR_INSTALLATION_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("GLOW_PROJECT_FILES_DIRECTORY", str(tmp_path / "project_files"))
    mocker.patch.object(adr_step, "get_or_create_adr", side_effect=RuntimeError("Invalid installation"))
    step = client_project.steps.adr_step

    with pytest.raises(Exception):
        step.initialize_adr()

    assert step.get_method_state("initialize_adr").status == MethodStatus.Failed
    assert "Failed to set up serverless ADR: Invalid installation" in caplog.text


def test_generate_report_renders_and_exports_the_report(
    client_project: ExamplesSolution, mocked_report_logic: dict[str, MagicMock]
) -> None:
    """Verify the report is rendered and its exports are stored."""
    step = client_project.steps.adr_step
    step.project_tag = PROJECT_TAG

    step.generate_report()

    assert step.get_method_state("generate_report").status == MethodStatus.Completed
    assert step.report_html_content == "<html>ADR reference report</html>"
    storage_scope = client_project.storage_scope
    assert storage_scope.get_cached(step.report_html_archive).read_bytes() == b"zip"
    assert storage_scope.get_cached(step.report_pptx).read_bytes() == b"pptx"
    assert storage_scope.get_cached(step.report_pdf).read_bytes() == b"pdf"

    mocked_report_logic["delete_report_items"].assert_called_once()
    item_files = mocked_report_logic["create_report_items"].call_args.args[2]
    assert all(Path(path).is_file() for path in (item_files.image, item_files.scene, item_files.file))
    assert mocked_report_logic["render_report_html"].call_args.args[1] == build_item_filter(PROJECT_TAG)


def test_generate_report_succeeds_without_pdf_export(
    client_project: ExamplesSolution, mocked_report_logic: dict[str, MagicMock]
) -> None:
    """Verify a PDF export failure does not fail the report generation."""
    mocked_report_logic["export_report_pdf"].side_effect = RuntimeError("GTK3 runtime not found")
    step = client_project.steps.adr_step
    step.project_tag = PROJECT_TAG

    step.generate_report()

    assert step.get_method_state("generate_report").status == MethodStatus.Completed
    assert step.report_pdf == NO_ENTITY
    assert step.report_pptx != NO_ENTITY
    assert step.report_html_archive != NO_ENTITY


@pytest.mark.parametrize(
    ("failing_function", "expected_message"),
    [
        ("get_or_create_adr", "Failed to get the serverless ADR instance"),
        ("create_report_items", "Failed to create the report items and templates"),
        ("recreate_report_templates", "Failed to create the report items and templates"),
        ("render_report_html", "Failed to render the report"),
        ("export_report_html_archive", "Failed to export the report as HTML"),
        ("export_report_pptx", "Failed to export the report as PowerPoint"),
    ],
)
def test_generate_report_fails_when_a_mandatory_stage_fails(
    client_project: ExamplesSolution,
    mocked_report_logic: dict[str, MagicMock],
    caplog: pytest.LogCaptureFixture,
    failing_function: str,
    expected_message: str,
) -> None:
    """Verify a failure while building the report fails the transaction and logs an explicit message."""
    mocked_report_logic[failing_function].side_effect = RuntimeError("Unexpected ADR error")
    step = client_project.steps.adr_step
    step.project_tag = PROJECT_TAG

    with pytest.raises(Exception):
        step.generate_report()

    assert step.get_method_state("generate_report").status == MethodStatus.Failed
    assert f"{expected_message}: Unexpected ADR error" in caplog.text


def test_generate_report_fails_without_project_tag(
    client_project: ExamplesSolution, mocked_report_logic: dict[str, MagicMock]
) -> None:
    """Verify the report is not generated before the page sets the project tag."""
    step = client_project.steps.adr_step

    with pytest.raises(Exception):
        step.generate_report()

    assert step.get_method_state("generate_report").status == MethodStatus.Failed
    mocked_report_logic["create_report_items"].assert_not_called()


@pytest.mark.skipif(
    not os.environ.get("ADR_INSTALLATION_DIRECTORY")
    or not Path(os.environ.get("ADR_INSTALLATION_DIRECTORY", "")).is_dir(),
    reason="Requires an Ansys Dynamic Reporting installation (ADR_INSTALLATION_DIRECTORY).",
)
def test_generate_report_with_adr_installation(
    client_project: ExamplesSolution, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Verify the report is generated and exported with a real serverless ADR instance."""
    monkeypatch.setenv("GLOW_PROJECT_FILES_DIRECTORY", str(tmp_path_factory.mktemp("adr") / "project_files"))
    step = client_project.steps.adr_step
    step.project_tag = PROJECT_TAG

    step.initialize_adr()
    step.generate_report()
    # A second generation replaces the items and recreates the shared templates and PowerPoint deck.
    step.generate_report()

    assert step.get_method_state("generate_report").status == MethodStatus.Completed
    for section in REPORT_SECTIONS:
        assert section.title in step.report_html_content

    storage_scope = client_project.storage_scope
    with zipfile.ZipFile(io.BytesIO(storage_scope.get_cached(step.report_html_archive).read_bytes())) as archive:
        assert "adr_reference_report.html" in archive.namelist()
        assert any(name.endswith(".css") for name in archive.namelist())

    presentation = Presentation(str(storage_scope.get_cached(step.report_pptx)))
    assert len(presentation.slides) == len(REPORT_SECTIONS) + 1
