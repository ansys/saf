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

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

import release_notes_utilities as release_utils


def test_get_release_notes() -> None:
    response = Mock(status_code=200)
    response.json.return_value = {"body": "<!-- hidden -->\n## What's changed\n\n- Added feature"}
    with patch.object(release_utils.requests, "get", return_value=response) as get:
        assert release_utils.get_release_notes("ansys-bdm-api", "0.5.0") == "- Added feature"
    get.assert_called_once()


def test_get_release_notes_returns_none_for_missing_or_empty_release() -> None:
    missing = Mock(status_code=404)
    empty = Mock(status_code=200)
    empty.json.return_value = {"body": ""}
    with patch.object(release_utils.requests, "get", side_effect=[missing, empty]):
        assert release_utils.get_release_notes("ansys-bdm-api", "0.5.0") is None
        assert release_utils.get_release_notes("ansys-bdm-api", "0.5.0") is None


def test_generate_release_notes_writes_report_and_summary() -> None:
    versions = dict.fromkeys(release_utils.PACKAGES, "1.2.3")
    current_versions = versions | {"ansys-bdm-api": "1.2.2"}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        summary = root / "summary.md"
        release_notes_dir = root / "notes_per_release"
        with (
            patch.object(release_utils, "MD_RELEASE_NOTES_FILE", root / "release_notes.md"),
            patch.object(release_utils, "RST_RELEASE_NOTES_DIR", release_notes_dir),
            patch.dict(
                os.environ,
                {"GITHUB_STEP_SUMMARY": str(summary), "MINIMUM_PIP_VERSION": "26.0"},
            ),
            patch.object(
                release_utils,
                "get_release_notes",
                side_effect=["- Added feature", *([None] * (len(versions) - 1))],
            ) as get,
            patch.object(
                release_utils,
                "get_latest_versions",
                return_value={"ansys-saf-pim-light-server": "0.1.0"},
            ) as get_latest_versions,
        ):
            release_utils.generate_release_notes(versions, "0.1.0", current_versions)

        report = (root / "release_notes.md").read_text(encoding="utf-8")
        assert "| `ansys-bdm-api` | `1.2.3` |" in report
        assert "| `ansys-saf-pim-light-server` | `0.1.0` |" in report
        assert "---#" not in report
        assert "# ansys-bdm-api 1.2.3\n\n- Added feature" in report
        assert "# ansys-bdm-shared-volume 1.2.3\n\nNo changes" not in report
        get.assert_any_call("ansys-bdm-shared-volume", "1.2.3")
        get_latest_versions.assert_called_once_with(release_utils.PRIVATE_PACKAGES)
        assert summary.read_text(encoding="utf-8") == report

        rst_report = (release_notes_dir / "0.1.0.rst").read_text(encoding="utf-8")
        assert "`0.1.0 <https://github.com/ansys/saf/releases/tag/v0.1.0-saf-sdk>`_" in rst_report
        assert "Installing ``ansys-saf-sdk`` requires pip 26.0 or higher." in rst_report
        assert ".. dropdown:: ansys-bdm-api 1.2.3" in rst_report
        assert f".. dropdown:: {release_utils.PACKAGES[-1]} 1.2.3" in rst_report
        assert ".. dropdown:: ansys-bdm-shared-volume 1.2.3" in rst_report
        assert "No release notes available" in rst_report
        assert "The private-package versions were fetched separately as the latest available versions" in rst_report
        assert rst_report.index(".. dropdown:: ansys-bdm-api 1.2.3") < rst_report.index("Private package")
        assert ".. tab-item:: Private packages" not in rst_report
        assert "Add" in rst_report
        assert rst_report.count(":open:") == 2


def test_render_rst_release_notes_formats_package_notes() -> None:
    versions = dict.fromkeys(release_utils.PACKAGES, "1.2.3")
    package = release_utils.PACKAGES[0]

    rst_report = release_utils._render_rst_release_notes(
        versions,
        "0.1.0",
        {},
        {
            package: (
                "## Feature\n\n- Use [feature](https://example.com) with `code` by @test-author "
                "in [#42](https://example.com/pull/42)\n"
                "## Security fixes\n\n- <strong>Fix token handling</strong><br>without losing its text"
            ),
            release_utils.PACKAGES[1]: "No changes",
            release_utils.PACKAGES[2]: "No release notes available",
        },
        "26.0",
    )

    assert f"  .. dropdown:: {package} 1.2.3\n    :open:\n" in rst_report
    assert "      :header-rows: 1\n      :stub-columns: 1\n      :widths: 80 20" in rst_report
    assert "      * - Feature\n        - Pull Request" in rst_report
    assert "      * - Security fixes\n        - Pull Request" in rst_report
    assert "* - Fix token handling without losing its text" in rst_report
    assert "<strong>" not in rst_report
    assert "</strong>" not in rst_report
    assert "<br>" not in rst_report
    assert "- Use `feature <https://example.com>`_ with ``code``" in rst_report
    assert "- `#42 <https://example.com/pull/42>`_" in rst_report
    assert "@test-author" not in rst_report
    assert ".. dropdown:: ansys-bdm-shared-volume 1.2.3\n\n    No changes" in rst_report
    assert ".. dropdown:: ansys-saf-glow-engine 1.2.3\n\n    No release notes available" in rst_report
    assert ".. tab-item:: Private packages" not in rst_report


def test_write_rst_release_notes_closes_only_previous_latest_release_dropdown() -> None:
    with tempfile.TemporaryDirectory() as directory:
        release_notes_dir = Path(directory) / "notes_per_release"
        release_notes_dir.mkdir()
        older_notes = release_notes_dir / "0.2.0.rst"
        older_notes.write_text(".. dropdown:: package\n    :open:\n", encoding="utf-8")
        previous_latest_notes = release_notes_dir / "0.3.0.rst"
        previous_latest_notes.write_text(
            ".. dropdown::\n  :open:\n\n  .. dropdown:: package\n    :open:\n",
            encoding="utf-8",
        )

        with patch.object(release_utils, "RST_RELEASE_NOTES_DIR", release_notes_dir):
            written_path = release_utils._write_rst_release_notes("New release\n  :open:\n", "0.4.0")

        assert written_path == release_notes_dir / "0.4.0.rst"
        assert written_path.read_text(encoding="utf-8") == "New release\n  :open:\n"
        previous_content = previous_latest_notes.read_text(encoding="utf-8")
        assert ".. dropdown::\n\n" in previous_content
        assert "  .. dropdown:: package\n    :open:" in previous_content
        assert older_notes.read_text(encoding="utf-8") == ".. dropdown:: package\n    :open:\n"


def test_write_rst_release_notes_does_not_close_latest_for_older_release() -> None:
    with tempfile.TemporaryDirectory() as directory:
        release_notes_dir = Path(directory) / "notes_per_release"
        release_notes_dir.mkdir()
        latest_notes = release_notes_dir / "0.3.0.rst"
        latest_content = ".. dropdown::\n  :open:\n\n  .. dropdown:: package\n    :open:\n"
        latest_notes.write_text(latest_content, encoding="utf-8")

        with patch.object(release_utils, "RST_RELEASE_NOTES_DIR", release_notes_dir):
            written_path = release_utils._write_rst_release_notes("Older release\n", "0.2.1")

        assert written_path == release_notes_dir / "0.2.1.rst"
        assert latest_notes.read_text(encoding="utf-8") == latest_content
