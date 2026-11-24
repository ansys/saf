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

# /// script
# requires-python = ">=3.11"
# dependencies = ["packaging>=23.0", "pytest>=9.0.3,<10", "requests>=2.32"]
# ///
"""Test the Dependabot report with uv run tests/test_retrieve_dependabot_alerts.py."""

import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "retrieve_dependabot_alerts.py"
spec = importlib.util.spec_from_file_location("retrieve_dependabot_alerts", SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
retrieve_dependabot_alerts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retrieve_dependabot_alerts)


def _alert(number: int, package: str, patched: str | None) -> dict:
    return {
        "number": number,
        "vulnerableManifestPath": "uv.lock",
        "securityVulnerability": {
            "severity": "HIGH",
            "vulnerableVersionRange": "< 2.0",
            "firstPatchedVersion": {"identifier": patched} if patched else None,
            "package": {"name": package, "ecosystem": "PIP"},
        },
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_overall_suggested_patches_returns_highest_version_per_package() -> None:
    suggestions = retrieve_dependabot_alerts._overall_suggested_patches(
        [
            _alert(1, "mcp", "1.9.0"),
            _alert(2, "mcp", "1.10.0"),
            _alert(3, "other-package", None),
        ]
    )

    assert suggestions == [("PIP", "mcp", "1.10.0")]


def test_main_returns_overall_suggested_patches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    alerts = [_alert(1, "mcp", "1.9.0"), _alert(2, "mcp", "1.10.0")]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["retrieve_dependabot_alerts.py", "--repository", "owner/repo"])
    monkeypatch.setattr(retrieve_dependabot_alerts, "_get_github_token", lambda: "token")
    monkeypatch.setattr(retrieve_dependabot_alerts, "_list_alerts", lambda *_args: alerts)

    suggestions = retrieve_dependabot_alerts.main()

    assert suggestions == [("PIP", "mcp", "1.10.0")]
    report = (tmp_path / "dist" / "dependabot_alerts_owner_repo_all.md").read_text(encoding="utf-8")
    assert "### Potential dependency traces" in report
    assert "combines runtime, optional-extra and development dependencies" in report
    assert "does not prove that the component is installed" in report
    assert "Trace unavailable: lock file not found" in report


def test_main_writes_github_output_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    github_output = tmp_path / "github_output"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setattr(sys, "argv", ["retrieve_dependabot_alerts.py", "--output", "report.md"])
    monkeypatch.setattr(retrieve_dependabot_alerts, "_get_github_token", lambda: "token")
    monkeypatch.setattr(
        retrieve_dependabot_alerts,
        "_list_alerts",
        lambda *_args: [_alert(1, "MCP", "1.9.0"), _alert(2, "mcp", "1.10.0"), _alert(3, "other", None)],
    )

    retrieve_dependabot_alerts.main()

    assert github_output.read_text(encoding="utf-8") == "packages=mcp\npatches=mcp>=1.10.0\n"


def test_main_skips_github_output_without_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setattr(sys, "argv", ["retrieve_dependabot_alerts.py", "--output", "report.md"])
    monkeypatch.setattr(retrieve_dependabot_alerts, "_get_github_token", lambda: "token")
    monkeypatch.setattr(retrieve_dependabot_alerts, "_list_alerts", lambda *_args: [_alert(1, "mcp", "1.9.0")])

    retrieve_dependabot_alerts.main()

    assert [path.name for path in tmp_path.iterdir()] == ["report.md"]


def test_root_uv_workspace_traces_affected_member_and_dependency_path(tmp_path: Path) -> None:
    _write(
        tmp_path / "uv.lock",
        """
[manifest]
members = ["member-a", "member-b"]

[[package]]
name = "member-a"
version = "1.0"
source = { editable = "packages/member-a" }
dependencies = [{ name = "middle" }, { name = "branch" }]

[[package]]
name = "member-b"
version = "1.0"
source = { editable = "packages/member-b" }
dependencies = [{ name = "unrelated" }]

[[package]]
name = "middle"
version = "1.0"
dependencies = [{ name = "mcp" }]

[[package]]
name = "branch"
version = "1.0"
dependencies = [{ name = "mcp" }]

[[package]]
name = "mcp"
version = "1.0"

[[package]]
name = "unrelated"
version = "1.0"
""",
    )

    traces = retrieve_dependabot_alerts._trace_alert_manifest(tmp_path, "uv.lock", "mcp")

    assert len(traces) == 1
    assert traces[0]["workspace_member"] == "member-a"
    assert traces[0]["manifest_file"] == "packages/member-a/pyproject.toml"
    assert traces[0]["dependency_paths"] == [
        ["member-a", "branch", "mcp"],
        ["member-a", "middle", "mcp"],
    ]


def test_standalone_uv_lock_traces_from_project_root(tmp_path: Path) -> None:
    project = tmp_path / "package"
    _write(
        project / "pyproject.toml",
        '[project]\nname = "sample-app"\ndependencies = ["middle>=1"]\n',
    )
    _write(
        project / "uv.lock",
        """
[[package]]
name = "sample-app"
version = "1.0"
source = { editable = "." }
dependencies = [{ name = "middle" }]

[[package]]
name = "middle"
version = "1.0"
dependencies = [{ name = "mcp" }]

[[package]]
name = "mcp"
version = "1.0"
""",
    )

    traces = retrieve_dependabot_alerts._trace_alert_manifest(tmp_path, "package/uv.lock", "mcp")

    assert traces[0]["workspace_member"] is None
    assert traces[0]["manifest_file"] == "package/pyproject.toml"
    assert traces[0]["dependency_paths"] == [["sample-app", "middle", "mcp"]]


def test_poetry_lock_traces_from_project_dependencies(tmp_path: Path) -> None:
    project = tmp_path / "poetry-project"
    _write(
        project / "pyproject.toml",
        '[tool.poetry]\nname = "sample-app"\n[tool.poetry.dependencies]\npython = ">=3.11"\nmiddle = "^1.0"\n',
    )
    _write(
        project / "poetry.lock",
        """
[[package]]
name = "middle"
version = "1.0"

[package.dependencies]
mcp = ">=1.0"

[[package]]
name = "mcp"
version = "1.0"
""",
    )

    traces = retrieve_dependabot_alerts._trace_alert_manifest(tmp_path, "poetry-project/poetry.lock", "mcp")

    assert traces[0]["manifest_file"] == "poetry-project/pyproject.toml"
    assert traces[0]["dependency_paths"] == [["sample-app", "middle", "mcp"]]


def test_cookiecutter_template_lock_is_excluded(tmp_path: Path) -> None:
    manifest = (
        "packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/"
        "{{cookiecutter.__solution_name}}/lock_files/dash/poetry.lock"
    )

    traces = retrieve_dependabot_alerts._trace_alert_manifest(tmp_path, manifest, "mcp")

    assert traces[0]["status"] == "cookiecutter template lock file excluded"


def test_render_markdown_preserves_per_version_alert_counts() -> None:
    report = retrieve_dependabot_alerts._render_markdown(
        "owner/repo",
        "all packages, all manifests",
        ["OPEN"],
        [
            _alert(1, "mcp", "1.30.0"),
            _alert(2, "mcp", "1.30.0"),
            _alert(3, "mcp", "1.31.0"),
            _alert(4, "other-package", None),
        ],
    )

    assert "| PIP | `mcp` | `1.30.0` | 2 |" in report
    assert "| PIP | `mcp` | `1.31.0` | 1 |" in report
    assert "| Alerts it would fix |" in report
    assert "Overall suggested patch version" not in report
    assert report.index("### Patch summary") < report.index("### All Dependabot alerts")
    assert report.index("### All Dependabot alerts") < report.index("| # | Severity |")
    assert "| State |" not in report
    assert "| Advisory |" not in report
    for alert_number in (1, 2, 3, 4):
        assert (f"- Related Issue https://github.com/owner/repo/security/dependabot/{alert_number}") in report


def test_render_markdown_includes_workspace_dependency_trace() -> None:
    report = retrieve_dependabot_alerts._render_markdown(
        "owner/repo",
        "all packages, all manifests",
        ["OPEN"],
        [_alert(1, "mcp", "1.10.0")],
        [
            {
                "ecosystem": "PIP",
                "package": "mcp",
                "manifest_traces": [
                    {
                        "lock_file": "uv.lock",
                        "manifest_file": "packages/member/pyproject.toml",
                        "workspace_member": "member-package",
                        "dependency_paths": [["member-package", "middle", "mcp"]],
                    }
                ],
            }
        ],
    )

    assert "### Potential dependency traces" in report
    assert "<details>" in report
    assert "<summary>Show dependency traces for 1 package</summary>" in report
    assert "</details>" in report
    assert "Workspace member: `member-package`" in report
    assert "Project manifest: `packages/member/pyproject.toml`" in report
    assert "Potential dependency tree:" in report
    assert "      - `member-package`" in report
    assert "        - `middle`" in report
    assert "          - `mcp`" in report


def test_render_markdown_includes_related_issues_when_no_alerts() -> None:
    report = retrieve_dependabot_alerts._render_markdown("ansys/saf", "all packages, all manifests", ["OPEN"], [])

    assert "## Related Issues\n\nNo related alerts." in report


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve()), *sys.argv[1:]]))
