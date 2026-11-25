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
# dependencies = ["pytest>=9.0.3,<10"]
# ///

r"""Test the VEX generator with uv run tests\test_generate_vex.py."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

GENERATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_vex.py"
spec = importlib.util.spec_from_file_location("generate_vex", GENERATOR_PATH)
assert spec is not None
assert spec.loader is not None
generate_vex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_vex)


class TestGenerateVex:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path) -> None:
        self.root = tmp_path
        package = self.root / "packages" / "saf-cli"
        package.mkdir(parents=True)
        (package / "pyproject.toml").write_text(
            '[project]\nname = "ansys-saf-cli"\nversion = "4.5.dev0"\n', encoding="utf-8"
        )
        self.path = self.root / "VEX" / "saf-cli.openvex.json"

    def run_generator(self, *options: str) -> None:
        args = generate_vex.parser_for_cli().parse_args(["saf-cli", *options])
        generate_vex.generate(args, self.root)

    def add_statement(self, component: str = "2.10", *options: str) -> None:
        self.run_generator(
            "--vulnerability",
            "CVE-2026-126190",
            "--status",
            "under_investigation",
            "--subcomponent",
            f"pkg:pypi/soupsieve@{component}",
            *options,
        )

    def test_create_and_replace_preserve_metadata_and_creation_time(self) -> None:
        self.add_statement()
        original = json.loads(self.path.read_text())
        original["timestamp"] = "2026-01-01T00:00:00Z"
        original["tooling"] = "existing tooling"
        self.path.write_text(json.dumps(original))

        self.add_statement("2.10", "--notes", "Updated assessment")

        updated = json.loads(self.path.read_text())
        assert updated["version"] == 2
        assert updated["timestamp"] == original["timestamp"]
        assert updated["last_updated"].endswith("Z")
        assert updated["tooling"] == "existing tooling"
        assert len(updated["statements"]) == 1
        assert updated["statements"][0]["status_notes"] == "Updated assessment"

    def test_different_subcomponents_are_separate_assessments(self) -> None:
        self.add_statement()
        self.add_statement("4.1")
        document = json.loads(self.path.read_text())
        assert len(document["statements"]) == 2

    def test_product_version_update_replaces_matching_statement_only(self) -> None:
        self.add_statement()
        document = json.loads(self.path.read_text())
        product = document["statements"][0]["products"][0]
        document["statements"].append(
            {
                "vulnerability": {"name": "CVE-other"},
                "products": [{"identifiers": {"purl": "pkg:pypi/another-product@1.0"}}],
                "status": "under_investigation",
            }
        )
        self.path.write_text(json.dumps(document))

        self.add_statement("2.10", "--product-version", "4.5.0", "--notes", "Reassessed")

        updated = json.loads(self.path.read_text())
        assert len(updated["statements"]) == 2
        updated_product = updated["statements"][0]["products"][0]
        assert updated_product["identifiers"]["purl"] == "pkg:pypi/ansys-saf-cli@4.5.0"
        assert updated_product["subcomponents"] == product["subcomponents"]
        assert updated["statements"][1] == document["statements"][1]

    def test_existing_product_version_is_used_for_new_statement(self) -> None:
        self.add_statement("2.10", "--product-version", "4.5.0")
        self.add_statement("4.1")
        document = json.loads(self.path.read_text())
        assert document["statements"][1]["products"][0]["identifiers"]["purl"] == "pkg:pypi/ansys-saf-cli@4.5.0"

    @pytest.mark.parametrize(
        ("options", "message"),
        [
            (["--vulnerability", "CVE-other", "--status", "affected"], "affected requires --action-statement"),
            (["--vulnerability", "CVE-other", "--status", "not_affected"], "not_affected requires"),
            (["--notes", "No vulnerability provided"], "Statement options require --vulnerability"),
            (
                ["--vulnerability", "CVE-other", "--status", "fixed", "--subcomponent", "soupsieve"],
                "Expected a versioned subcomponent PURL",
            ),
        ],
    )
    def test_invalid_assessment_does_not_change_existing_file(self, options: list[str], message: str) -> None:
        self.add_statement()
        original = self.path.read_bytes()
        with pytest.raises(ValueError, match=message):
            self.run_generator(*options)
        assert self.path.read_bytes() == original

    def test_new_document_requires_a_statement(self) -> None:
        with pytest.raises(ValueError, match="A new document requires"):
            self.run_generator("--product-version", "4.5.0")
        assert not self.path.exists()

    def test_refresh_only_increments_revision_without_changing_statements(self) -> None:
        self.add_statement()
        original = json.loads(self.path.read_text())
        self.run_generator()
        updated = json.loads(self.path.read_text())
        assert updated["version"] == original["version"] + 1
        assert updated["statements"] == original["statements"]

    @pytest.mark.parametrize("content", ['{"statements": []}', "[]", "not JSON"])
    def test_malformed_existing_document_is_not_replaced(self, content: str) -> None:
        self.path.parent.mkdir()
        self.path.write_text(content)
        with pytest.raises(ValueError, match="OpenVEX|JSON|Expecting"):
            self.run_generator("--product-version", "4.5.0")
        assert self.path.read_text() == content

    def test_not_affected_statement_includes_required_evidence(self) -> None:
        self.run_generator(
            "--vulnerability",
            "CVE-example",
            "--status",
            "not_affected",
            "--justification",
            "component_not_present",
            "--impact-statement",
            "The affected component is absent.",
        )
        statement = json.loads(self.path.read_text())["statements"][0]
        assert statement["justification"] == "component_not_present"
        assert statement["impact_statement"] == "The affected component is absent."

    def test_examples_project_metadata_is_read_from_poetry_table(self) -> None:
        examples = self.root / "examples"
        examples.mkdir()
        (examples / "pyproject.toml").write_text(
            '[tool.poetry]\nname = "saf-solutions-examples"\nversion = "0.2.dev0"\n', encoding="utf-8"
        )
        args = generate_vex.parser_for_cli().parse_args(
            ["examples", "--vulnerability", "CVE-example", "--status", "fixed"]
        )
        path = generate_vex.generate(args, self.root)
        assert path == self.root / "VEX" / "examples.openvex.json"
        product = json.loads(path.read_text())["statements"][0]["products"][0]
        assert product["identifiers"]["purl"] == "pkg:pypi/saf-solutions-examples@0.2.dev0"

    def test_standalone_cli_uses_its_repository_not_working_directory(self) -> None:
        script = self.root / "scripts" / "generate_vex.py"
        script.parent.mkdir()
        script.write_text(GENERATOR_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "saf-cli",
                "--vulnerability",
                "CVE-example",
                "--status",
                "under_investigation",
            ],
            cwd=script.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Saved VEX document" in result.stdout
        document = json.loads(self.path.read_text())
        assert document["version"] == 1
        assert document["statements"][0]["products"][0]["identifiers"]["purl"] == "pkg:pypi/ansys-saf-cli@4.5.dev0"


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve()), *sys.argv[1:]]))
