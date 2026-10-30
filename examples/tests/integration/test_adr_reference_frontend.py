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

"""Integration tests for the ADR reference page callbacks."""

import base64
from collections.abc import Iterator
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from ansys.saf.glow._testing.solution import is_within_dash_callback_context
from dash.testing import ignore_register_page
import pytest

from saf.solutions.examples.solution import adr_step
from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.logic.adr_reference.report_definition import build_project_tag

with ignore_register_page():
    from saf.solutions.examples.ui.app import app as examples_app
    from saf.solutions.examples.ui.pages import adr_page


pytestmark = pytest.mark.usefixtures("init_dashclient")

EXPORT_BUTTON_IDS = ("adr-page-export-pdf-button", "adr-page-export-pptx-button", "adr-page-export-html-button")


@pytest.fixture(scope="module")
def dash_app(init_dashclient: None) -> Any:
    """Return the example Dash app with all callbacks registered."""
    if not examples_app.callback_map:
        examples_app.register_callbacks()
    return examples_app


@pytest.fixture
def dash_ui_client(dash_app: Any) -> Iterator[Any]:
    """Provide a Flask test client for the example Dash UI."""
    with dash_app.server.test_client() as client:
        yield client


@pytest.fixture
def adr_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: Any) -> MagicMock:
    """Configure ADR in the environment and mock the creation of the ADR instance.

    GLOW_PROJECT_FILES_DIRECTORY is only set if missing, because the Dash client reads the project files from it.
    """
    monkeypatch.setenv("ADR_INSTALLATION_DIRECTORY", str(tmp_path))
    if not os.environ.get("GLOW_PROJECT_FILES_DIRECTORY"):
        monkeypatch.setenv("GLOW_PROJECT_FILES_DIRECTORY", str(tmp_path / "project_files"))
    return mocker.patch.object(adr_step, "get_or_create_adr")


@pytest.fixture
def mocked_report_logic(adr_configured: MagicMock, mocker: Any) -> dict[str, MagicMock]:
    """Mock the ADR logic used to generate the report. The PDF export fails, like without GTK3."""
    mocks = {
        name: mocker.patch.object(adr_step, name)
        for name in (
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
    mocks["export_report_pdf"].side_effect = RuntimeError("GTK3 runtime not found")
    return mocks


def _invoke_dash_callback(
    dash_ui_client: Any,
    dash_app: Any,
    *,
    input_component_id: str,
    output_component_id: str,
    input_values: list[Any],
    state_values: list[Any],
    changed_prop_id: str,
) -> dict[str, Any]:
    """Invoke the registered callback with the given input and output through Dash's update endpoint."""
    matching_callbacks = [
        (callback_id, callback_entry)
        for callback_id, callback_entry in dash_app.callback_map.items()
        if any(input_definition["id"] == input_component_id for input_definition in callback_entry["inputs"])
        and any(output.component_id == output_component_id for output in _callback_outputs(callback_entry))
    ]
    if len(matching_callbacks) != 1:
        raise AssertionError(f"Expected one callback for {input_component_id!r}, found {len(matching_callbacks)}.")

    callback_id, callback_entry = matching_callbacks[0]
    payload = {
        "output": callback_id,
        "outputs": [
            {"id": output.component_id, "property": output.component_property}
            for output in _callback_outputs(callback_entry)
        ],
        "inputs": [
            {"id": definition["id"], "property": definition["property"], "value": value}
            for definition, value in zip(callback_entry["inputs"], input_values, strict=True)
        ],
        "state": [
            {"id": definition["id"], "property": definition["property"], "value": value}
            for definition, value in zip(callback_entry["state"], state_values, strict=True)
        ],
        "changedPropIds": [changed_prop_id],
    }
    context_token = is_within_dash_callback_context.set(True)
    try:
        response = dash_ui_client.post("/_dash-update-component", json=payload)
    finally:
        is_within_dash_callback_context.reset(context_token)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["response"]


def _callback_outputs(callback_entry: dict[str, Any]) -> list[Any]:
    """Return callback outputs as a list."""
    outputs = callback_entry["output"]
    return list(outputs) if isinstance(outputs, (list, tuple)) else [outputs]


def _initialize_page(dash_ui_client: Any, dash_app: Any, project_name: str) -> dict[str, Any]:
    """Run the page initialization callback, as when the page is opened."""
    return _invoke_dash_callback(
        dash_ui_client,
        dash_app,
        input_component_id="url",
        output_component_id="adr-page-availability-alert",
        input_values=[project_name],
        state_values=[],
        changed_prop_id="url.pathname",
    )


def _click(dash_ui_client: Any, dash_app: Any, button_id: str, output_component_id: str, project_name: str) -> dict:
    """Run the callback of a button click."""
    return _invoke_dash_callback(
        dash_ui_client,
        dash_app,
        input_component_id=button_id,
        output_component_id=output_component_id,
        input_values=[1],
        state_values=[project_name],
        changed_prop_id=f"{button_id}.n_clicks",
    )


def _find_components(value: Any) -> list[dict[str, Any]]:
    """Recursively collect the serialized components of a Dash component tree."""
    if hasattr(value, "to_plotly_json"):
        return _find_components(value.to_plotly_json())
    components = []
    if isinstance(value, dict):
        if "props" in value and "type" in value:
            components.append(value)
        for child in value.values():
            components.extend(_find_components(child))
    elif isinstance(value, list):
        for child in value:
            components.extend(_find_components(child))
    return components


def _component_props(value: Any, component_id: str) -> dict[str, Any]:
    """Get the properties of the component with the given ID."""
    for component in _find_components(value):
        if component["props"].get("id") == component_id:
            return component["props"]
    raise AssertionError(f"Component {component_id!r} not found.")


def test_layout_disables_buttons_until_adr_is_checked() -> None:
    """Verify the page starts with the generation and export buttons disabled."""
    layout = adr_page.layout()

    generate_button = _component_props(layout, "adr-page-generate-report-button")
    assert generate_button["disabled"] is True
    assert generate_button["loading"] is True
    for button_id in EXPORT_BUTTON_IDS:
        assert _component_props(layout, button_id)["disabled"] is True
    for component_id in ("adr-page-availability-alert", "adr-page-report-content", "adr-page-download-pdf"):
        _component_props(layout, component_id)
    starting_alert = _component_props(layout, "adr-page-availability-alert")["children"]
    assert starting_alert.title == "Starting Ansys Dynamic Reporting..."


def test_report_iframe_keeps_the_report_displayed_when_clicking_links() -> None:
    """Verify the link handler script is added to the report, before the end of its body if any."""
    with_body = adr_page._report_iframe("<html><body><p>Report</p></body></html>").srcDoc
    without_body = adr_page._report_iframe("<p>Report</p>").srcDoc

    assert with_body.startswith("<html><body><p>Report</p>\n<script>")
    assert with_body.endswith("</script>\n</body></html>")
    assert without_body.startswith("<p>Report</p>\n<script>")
    assert 'href.startsWith("/media/")' in without_body
    assert 'link.setAttribute("download"' in without_body


def test_layout_shows_title_information_and_warning() -> None:
    """Verify the page starts with a title, an information block, and a warning, like the other pages."""
    top_level_types = [type(child).__name__ for child in adr_page.layout().children]

    assert [component_type for component_type in top_level_types if component_type != "Space"][:3] == [
        "H1",
        "Blockquote",
        "Alert",
    ]


def test_initialization_shows_alert_when_adr_is_not_configured(
    dash_ui_client: Any,
    dash_app: Any,
    project_name: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify the page logs the problem, shows an alert, and keeps the buttons disabled without ADR."""
    monkeypatch.setenv("ADR_INSTALLATION_DIRECTORY", "")

    result = _initialize_page(dash_ui_client, dash_app, project_name)

    alert = result["adr-page-availability-alert"]["children"]
    assert alert["props"]["title"] == "Ansys Dynamic Reporting is not available"
    assert "ADR_INSTALLATION_DIRECTORY" in str(alert)
    assert result["adr-page-generate-report-button"] == {"disabled": True, "loading": False}
    assert all(result[button_id]["disabled"] for button_id in EXPORT_BUTTON_IDS)
    assert "Ansys Dynamic Reporting is not available" in caplog.text


def test_initialization_shows_alert_when_adr_setup_fails(
    dash_ui_client: Any, dash_app: Any, project_name: str, adr_configured: MagicMock
) -> None:
    """Verify the page shows an alert and keeps the buttons disabled when ADR cannot be set up."""
    adr_configured.side_effect = RuntimeError("Invalid installation")

    result = _initialize_page(dash_ui_client, dash_app, project_name)

    assert "Serverless ADR could not be set up" in str(result["adr-page-availability-alert"]["children"])
    assert result["adr-page-generate-report-button"] == {"disabled": True, "loading": False}


def test_initialization_enables_generation_when_adr_is_available(
    client_project: ExamplesSolution, dash_ui_client: Any, dash_app: Any, project_name: str, adr_configured: MagicMock
) -> None:
    """Verify the generation is enabled, the exports stay disabled, and the project tag is set."""
    result = _initialize_page(dash_ui_client, dash_app, project_name)

    assert result["adr-page-availability-alert"]["children"] is None
    assert result["adr-page-generate-report-button"] == {"disabled": False, "loading": False}
    assert all(result[button_id]["disabled"] for button_id in EXPORT_BUTTON_IDS)
    assert client_project.steps.adr_step.project_tag == build_project_tag(client_project.project_id)
    adr_configured.assert_called_once()


def test_generate_report_displays_report_and_enables_successful_exports(
    dash_ui_client: Any, dash_app: Any, project_name: str, mocked_report_logic: dict[str, MagicMock]
) -> None:
    """Verify the report is displayed in an iframe and only the successful exports are enabled."""
    _initialize_page(dash_ui_client, dash_app, project_name)

    result = _click(
        dash_ui_client, dash_app, "adr-page-generate-report-button", "adr-page-report-content", project_name
    )

    iframe = result["adr-page-report-content"]["children"]
    assert iframe["type"] == "Iframe"
    assert iframe["props"]["srcDoc"].startswith("<html>ADR reference report</html>")
    assert "addEventListener" in iframe["props"]["srcDoc"]
    assert result["adr-page-export-pdf-button"]["disabled"] is True
    assert result["adr-page-export-pptx-button"]["disabled"] is False
    assert result["adr-page-export-html-button"]["disabled"] is False
    assert result["notification-container"]["sendNotifications"][0]["color"] == "orange"


def test_generate_report_failure_keeps_exports_disabled(
    dash_ui_client: Any, dash_app: Any, project_name: str, mocked_report_logic: dict[str, MagicMock]
) -> None:
    """Verify a failed generation shows an error and disables every export, even after a previous success."""
    _initialize_page(dash_ui_client, dash_app, project_name)
    _click(dash_ui_client, dash_app, "adr-page-generate-report-button", "adr-page-report-content", project_name)
    mocked_report_logic["export_report_pptx"].side_effect = RuntimeError("PPTX export failed")

    result = _click(
        dash_ui_client, dash_app, "adr-page-generate-report-button", "adr-page-report-content", project_name
    )

    assert result["adr-page-report-content"]["children"]["props"]["title"] == "Report generation failed"
    assert all(result[button_id]["disabled"] for button_id in EXPORT_BUTTON_IDS)
    assert result["notification-container"]["sendNotifications"][0]["color"] == "red"

    initialization = _initialize_page(dash_ui_client, dash_app, project_name)
    assert all(initialization[button_id]["disabled"] for button_id in EXPORT_BUTTON_IDS)


@pytest.mark.parametrize(
    ("button_id", "download_id", "file_name", "content"),
    [
        ("adr-page-export-pptx-button", "adr-page-download-pptx", "adr_reference_report.pptx", b"pptx"),
        ("adr-page-export-html-button", "adr-page-download-html", "adr_reference_report.zip", b"zip"),
    ],
)
def test_export_buttons_download_the_exported_files(
    dash_ui_client: Any,
    dash_app: Any,
    project_name: str,
    mocked_report_logic: dict[str, MagicMock],
    button_id: str,
    download_id: str,
    file_name: str,
    content: bytes,
) -> None:
    """Verify each export button downloads its exported file."""
    _initialize_page(dash_ui_client, dash_app, project_name)
    _click(dash_ui_client, dash_app, "adr-page-generate-report-button", "adr-page-report-content", project_name)

    result = _click(dash_ui_client, dash_app, button_id, download_id, project_name)

    download = result[download_id]["data"]
    assert download["filename"] == file_name
    assert download["base64"] is True
    assert download["content"] == base64.b64encode(content).decode()


def test_pdf_export_is_refused_when_pdf_was_not_exported(
    dash_ui_client: Any, dash_app: Any, project_name: str, mocked_report_logic: dict[str, MagicMock]
) -> None:
    """Verify the PDF export callback notifies the user instead of failing when no PDF exists."""
    _initialize_page(dash_ui_client, dash_app, project_name)
    _click(dash_ui_client, dash_app, "adr-page-generate-report-button", "adr-page-report-content", project_name)

    result = _click(dash_ui_client, dash_app, "adr-page-export-pdf-button", "adr-page-download-pdf", project_name)

    assert "adr-page-download-pdf" not in result
    assert result["notification-container"]["sendNotifications"][0]["title"] == "Export unavailable"
