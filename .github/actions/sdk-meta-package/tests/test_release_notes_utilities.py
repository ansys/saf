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
        with (
            patch.object(release_utils, "RELEASE_NOTES_FILE", root / "release_notes.md"),
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
