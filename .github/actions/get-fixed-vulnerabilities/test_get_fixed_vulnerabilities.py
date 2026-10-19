# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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

# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "packaging>=24",
#   "requests>=2.32",
#   "pytest>=8"
# ]
# ///

"""Focused tests for the fixed-vulnerability release-note pipeline."""

import sys
from pathlib import Path
import subprocess
import tomllib
from unittest.mock import Mock, patch

import get_fixed_vulnerabilities as fixes
import pytest
import requests


def alert(
    number: int = 1,
    *,
    manifest: str = "uv.lock",
    fixed_at: str | None = "2026-10-02T00:00:00Z",
    package: str = "example",
    ecosystem: str = "PIP",
) -> fixes.Alert:
    return {
        "number": number,
        "fixedAt": fixed_at,
        "vulnerableManifestPath": manifest,
        "securityVulnerability": {
            "severity": "HIGH",
            "package": {"name": package, "ecosystem": ecosystem},
            "advisory": {"summary": "Unsafe *input* [link](url)\n<script>"},
        },
    }


def response(nodes: list[fixes.Alert], cursor: str | None = None, *, more: bool = False) -> Mock:
    result = Mock()
    result.json.return_value = {
        "data": {
            "repository": {
                "vulnerabilityAlerts": {
                    "nodes": nodes,
                    "pageInfo": {"endCursor": cursor, "hasNextPage": more},
                },
            },
        },
    }
    return result


def test_fetch_paginates_and_authenticates() -> None:
    with patch.object(
        fixes.requests, "post", side_effect=[response([alert()], "next", more=True), response([])]
    ) as post:
        assert fixes.fetch_closed_alerts("owner", "repo", "test-token") == [alert()]
    assert post.call_count == 2
    assert post.call_args.kwargs["json"]["variables"]["cursor"] == "next"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"
    assert post.call_args.kwargs["timeout"] == 30
    assert "states: [FIXED]" in fixes.GRAPHQL_QUERY


@pytest.mark.parametrize("error", ["http", "graphql", "repository", "pagination"])
def test_fetch_errors_never_return_partial_results(error: str) -> None:
    bad = response([], more=error == "pagination")
    expected = RuntimeError
    if error == "http":
        bad.raise_for_status.side_effect = requests.HTTPError("Forbidden")
        expected = requests.HTTPError
    elif error == "graphql":
        bad.json.return_value = {"errors": [{"message": "Forbidden"}]}
    elif error == "repository":
        bad.json.return_value = {"data": {"repository": None}}
    with (
        patch.object(fixes.requests, "post", side_effect=[response([alert()], "next", more=True), bad]),
        pytest.raises(expected),
    ):
        fixes.fetch_closed_alerts("owner", "repo", "test-token")


def test_filters_multiple_exact_manifests_and_resolution_times() -> None:
    alerts = [
        alert(1, fixed_at="2026-10-04T00:00:00Z"),
        alert(2, manifest="frontend/package-lock.json"),
        alert(3, fixed_at="2026-10-01T00:00:00Z"),
        alert(4, fixed_at="2026-09-30T00:00:00Z"),
        alert(5, fixed_at=None),
        alert(6, manifest="other/uv.lock"),
        alert(7, fixed_at="2026-10-01T02:00:00+02:00"),
    ]
    with patch.object(fixes, "fetch_closed_alerts", return_value=alerts):
        result = fixes.get_closed_alerts_since_for_manifest_file(
            fixes.parse_date("2026-10-01"),
            ["uv.lock", "frontend\\package-lock.json"],
            owner="owner",
            name="repo",
            token="test-token",
        )
    assert [item["number"] for item in result] == [2, 1]


def test_export_selected_members_includes_extras_and_normalizes_names(tmp_path: Path) -> None:
    exported = (
        "# comment\n\nExample_Package[extra]==1.0 ; sys_platform == 'win32'\n"
        "example-package==2.0 ; sys_platform == 'linux'\n"
        "other @ https://example.com/other.whl\n"
    )
    with patch.object(fixes.subprocess, "run", return_value=Mock(stdout=exported)) as run:
        assert fixes.get_packages_from_members(["saf-cli", "glow-engine"], tmp_path) == ["example-package", "other"]
    command = run.call_args.args[0]
    assert command[-4:] == ["--package", "ansys-saf-cli", "--package", "ansys-saf-glow-engine"]
    for flag in ["--all-extras", "--no-dev", "--no-emit-workspace", "--no-hashes", "--locked"]:
        assert flag in command
    assert run.call_args.kwargs["check"] is True
    assert run.call_args.kwargs["cwd"] == tmp_path


def test_export_failure_is_not_swallowed() -> None:
    with (
        patch.object(fixes.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["uv", "export"])),
        pytest.raises(subprocess.CalledProcessError),
    ):
        fixes.get_packages_from_members(["saf-cli"])


def test_unknown_directory_is_rejected_before_export() -> None:
    with patch.object(fixes.subprocess, "run") as run, pytest.raises(ValueError, match="Unknown package directories"):
        fixes.get_packages_from_members(["saf-cli", "unknown"])
    run.assert_not_called()


@pytest.mark.parametrize(("directory", "member"), fixes.MEMBER_PER_LIBRARY_DIRECTORY.items())
def test_directory_mapping_matches_package_metadata(directory: str, member: str) -> None:
    repository = Path(__file__).resolve().parents[3]
    with (repository / "packages" / directory / "pyproject.toml").open("rb") as metadata:
        project = tomllib.load(metadata)
    assert project["project"]["name"] == member


def test_empty_members_and_manifests_are_rejected() -> None:
    with pytest.raises(ValueError, match="member"):
        fixes.get_packages_from_members([])
    with pytest.raises(ValueError, match="manifest"):
        fixes.get_closed_alerts_since_for_manifest_file(
            fixes.parse_date("2026-10-01"),
            [],
            owner="owner",
            name="repo",
            token="test-token",
        )


def test_package_filtering_normalizes_only_python_names() -> None:
    alerts = [
        alert(1, package="Example_Package"),
        alert(2, package="not-selected"),
        alert(3, package="example-package", ecosystem="NPM"),
        alert(4, package="example_package", ecosystem="NPM"),
    ]
    assert [item["number"] for item in fixes.filter_alerts_per_packages(alerts, ["example-package"])] == [1, 3]


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_markdown_preserves_notes_escapes_summary_and_is_repeatable(tmp_path: Path, newline: str) -> None:
    notes = tmp_path / "notes.md"
    prefix = newline.join(["# Release", "", "Public notes.", fixes.INTERNAL_NOTES_MARKER, ""])
    suffix = "## Features" + newline + "Existing internal notes."
    original = prefix + suffix
    notes.write_bytes(original.encode("utf-8"))
    fixes.add_alerts_to_release_notes([alert(), alert()], notes, owner="owner", name="repo")
    result = notes.read_bytes().decode("utf-8")
    assert result.startswith(prefix + newline + "## 🛡️ Security fixes" + newline * 2)
    assert result.endswith(newline * 2 + suffix)
    if newline == "\r\n":
        assert "\n" not in result.replace("\r\n", "")
    expected_entry = (
        "* 🟠 **High** - Upgraded **example**<br>"
        r"Unsafe \*input\* \[link\](url) &lt;script&gt;<br>"
        "_Closure reason:_ Fixed ([#1](https://github.com/owner/repo/security/dependabot/1))<br><br>"
    )
    assert expected_entry in result
    assert "(PIP)" not in result
    assert "2026-10-02" not in result
    assert "Reason for fix" not in result
    assert result.count("https://github.com/owner/repo/security/dependabot/1") == 1
    fixes.add_alerts_to_release_notes([alert()], notes, owner="owner", name="repo")
    assert notes.read_bytes().decode("utf-8") == result


@pytest.mark.parametrize(
    ("severity", "label"),
    [
        ("CRITICAL", "🔴 **Critical**"),
        ("HIGH", "🟠 **High**"),
        ("MODERATE", "🟡 **Moderate**"),
        ("LOW", "⚪ **Low**"),
    ],
)
def test_severity_styles(tmp_path: Path, severity: str, label: str) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text(fixes.INTERNAL_NOTES_MARKER, encoding="utf-8")
    item = alert(package="example_package")
    item["securityVulnerability"]["severity"] = severity
    fixes.add_alerts_to_release_notes([item], notes, owner="owner", name="repo")
    result = notes.read_text(encoding="utf-8")
    assert f"* {label} - Upgraded **example\\_package**<br>" in result


def test_release_notes_order_alerts_by_severity_without_mutating_input(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text(fixes.INTERNAL_NOTES_MARKER, encoding="utf-8")
    alerts = [alert(number) for number in range(1, 6)]
    for item, severity in zip(alerts, ["LOW", "HIGH", "MODERATE", "CRITICAL", "HIGH"], strict=True):
        item["securityVulnerability"]["severity"] = severity
    fixes.add_alerts_to_release_notes(alerts, notes, owner="owner", name="repo")
    result = notes.read_text(encoding="utf-8")
    assert [line.split("([#")[1].split("]")[0] for line in result.splitlines() if line.startswith("* ")] == [
        "4",
        "2",
        "5",
        "3",
        "1",
    ]
    assert [item["number"] for item in alerts] == [1, 2, 3, 4, 5]


def test_marker_at_end_of_file(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text(fixes.INTERNAL_NOTES_MARKER, encoding="utf-8")
    fixes.add_alerts_to_release_notes([alert()], notes, owner="owner", name="repo")
    assert notes.read_text(encoding="utf-8").startswith(
        fixes.INTERNAL_NOTES_MARKER + "\n\n## 🛡️ Security fixes\n\n",
    )


def test_missing_marker_fails_without_modifying_notes(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    original = b"# Release\r\nExisting notes.\r\n"
    notes.write_bytes(original)
    with pytest.raises(ValueError, match="internal-information marker"):
        fixes.add_alerts_to_release_notes([alert()], notes, owner="owner", name="repo")
    assert notes.read_bytes() == original


def test_no_alerts_leaves_notes_untouched(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_bytes(b"# Notes\r\nExisting notes.\r\n")
    fixes.add_alerts_to_release_notes([], notes, owner="owner", name="repo")
    assert notes.read_bytes() == b"# Notes\r\nExisting notes.\r\n"


def test_missing_notes_and_missing_resolution_date_fail(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    with pytest.raises(FileNotFoundError):
        fixes.add_alerts_to_release_notes([], notes, owner="owner", name="repo")
    notes.write_text("# Notes", encoding="utf-8")
    with pytest.raises(ValueError, match="timestamp"):
        fixes.add_alerts_to_release_notes([alert(fixed_at=None)], notes, owner="owner", name="repo")
    assert notes.read_text(encoding="utf-8") == "# Notes"


def test_cli_wires_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("# Notes\n" + fixes.INTERNAL_NOTES_MARKER + "\n## Features\n", encoding="utf-8")
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setattr(
        "sys.argv",
        [
            "get_fixed_vulnerabilities.py",
            "--last-release-date",
            "2026-10-01",
            "--manifest-file",
            "uv.lock",
            "--manifest-file",
            "frontend/package-lock.json",
            "--member",
            "saf-cli",
            "--member",
            "glow-engine",
            "--release-notes",
            str(notes),
        ],
    )
    with (
        patch.object(fixes, "get_packages_from_members", return_value=["example"]) as export,
        patch.object(fixes, "fetch_closed_alerts", return_value=[alert(), alert(2, package="unrelated")]),
    ):
        fixes.main()
    export.assert_called_once_with(["saf-cli", "glow-engine"], Path())
    assert "[#1]" in notes.read_text(encoding="utf-8")
    assert "[#2]" not in notes.read_text(encoding="utf-8")

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, *sys.argv[1:]] if sys.argv[1:] else [__file__, "-v"]))