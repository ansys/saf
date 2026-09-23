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
# dependencies = ["pytest>=8"]
# ///

"""Tests for ``ci_cd_job_matrices.py``."""

import json
import os
from pathlib import Path
import sys
import tempfile

import pytest

# Set up environment variables BEFORE importing the module
# (The module executes code at import time that requires GITHUB_OUTPUT and GITHUB_STEP_SUMMARY)
with tempfile.TemporaryDirectory() as temp_dir:
    _temp_output = Path(temp_dir) / "output.txt"
    _temp_summary = Path(temp_dir) / "summary.md"
    _temp_output.touch()
    _temp_summary.touch()
    os.environ["GITHUB_OUTPUT"] = str(_temp_output)
    os.environ["GITHUB_STEP_SUMMARY"] = str(_temp_summary)

    from ci_cd_job_matrices import (
        SAF_PACKAGES,
        TESTS_DEFINITIONS_PER_TARGET,
        TESTS_DEFINITIONS_DIR,
        write_output,
        write_to_github_step_summary,
        write_matrix_to_output,
        get_pr_changes,
        get_changed_moon_packages,
        get_changed_poetry_packages,
        get_changed_packages,
        get_code_style_matrix_entries,
        get_compatibility_matrix_entries,
        get_tests_matrix_entries,
        get_tests_generated_solution_flag,
    )


@pytest.fixture
def github_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide ``GITHUB_OUTPUT`` and ``GITHUB_STEP_SUMMARY`` environment variables for each test.

    Sets up temporary output and summary files and patches the necessary environment variables.
    Automatically cleans up after the test completes.

    Args:
        tmp_path: pytest temporary directory for this test.
        monkeypatch: pytest fixture for environment variable patching.

    Yields:
        Tuple of (output_file, summary_file) paths.
    """
    output_file = tmp_path / "output.txt"
    summary_file = tmp_path / "summary.md"
    output_file.touch()
    summary_file.touch()

    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    return output_file, summary_file


def parse_outputs(output_file: Path) -> dict[str, str]:
    """Parse the ``name<<EOF ... EOF`` blocks written to the output file."""
    outputs: dict[str, str] = {}
    lines = output_file.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        name, _, delimiter = lines[index].partition("<<")
        assert delimiter == "EOF"
        index += 1
        start = index
        while lines[index] != "EOF":
            index += 1
        outputs[name] = "\n".join(lines[start:index])
        index += 1
    return outputs


def read_summary(summary_file: Path) -> str:
    """Read the GitHub step summary file content."""
    return summary_file.read_text(encoding="utf-8")


class TestWriteOutput:
    """Test the write_output function with various input types."""

    @pytest.mark.parametrize(
        "key,value,validator",
        [
            ("single_key", "single_value", lambda v: v == "single_value"),
            (
                "multiline_key",
                "line1\nline2\nline3",
                lambda v: v == "line1\nline2\nline3",
            ),
            (
                "json_key",
                json.dumps({"key": "value"}),
                lambda v: json.loads(v) == {"key": "value"},
            ),
            ("empty_key", "", lambda v: v == ""),
            ("long_value", "x" * 1000, lambda v: len(v) == 1000),
        ],
        ids=["single_line", "multiline", "json", "empty", "long_value"],
    )
    def test_write_output_types(
        self, github_env: tuple[Path, Path], key: str, value: str, validator
    ):
        """Test writing different types of output values."""
        output_file, _ = github_env
        write_output(key, value)

        outputs = parse_outputs(output_file)
        assert key in outputs
        assert validator(outputs[key])

    def test_write_multiple_outputs(self, github_env: tuple[Path, Path]):
        """Multiple outputs can be written sequentially."""
        output_file, _ = github_env
        write_output("key1", "value1")
        write_output("key2", "value2")
        write_output("key3", "value3")

        outputs = parse_outputs(output_file)
        assert outputs["key1"] == "value1"
        assert outputs["key2"] == "value2"
        assert outputs["key3"] == "value3"


class TestWriteToGithubStepSummary:
    """Test the write_to_github_step_summary function."""

    def test_write_single_line_summary(self, github_env: tuple[Path, Path]):
        """Single line summary is written correctly."""
        _, summary_file = github_env
        write_to_github_step_summary("Summary line")

        summary = read_summary(summary_file)
        assert "Summary line" in summary

    def test_write_multiline_summary(self, github_env: tuple[Path, Path]):
        """Multiline summary is written correctly."""
        _, summary_file = github_env
        content = "Line 1\nLine 2\nLine 3"
        write_to_github_step_summary(content)

        summary = read_summary(summary_file)
        assert content in summary

    def test_write_markdown_summary(self, github_env: tuple[Path, Path]):
        """Markdown formatted summary is written correctly."""
        _, summary_file = github_env
        markdown_content = "## Header\n- Item 1\n- Item 2"
        write_to_github_step_summary(markdown_content)

        summary = read_summary(summary_file)
        assert "## Header" in summary
        assert "- Item 1" in summary

    def test_write_multiple_summaries(self, github_env: tuple[Path, Path]):
        """Multiple summary writes are appended."""
        _, summary_file = github_env
        write_to_github_step_summary("First summary")
        write_to_github_step_summary("Second summary")

        summary = read_summary(summary_file)
        assert "First summary" in summary
        assert "Second summary" in summary


class TestWriteMatrixToOutput:
    """Test the write_matrix_to_output function."""

    def test_write_empty_matrix(self, github_env: tuple[Path, Path]):
        """Empty matrix is written as empty JSON object."""
        output_file, summary_file = github_env
        write_matrix_to_output("empty_matrix", [])

        outputs = parse_outputs(output_file)
        assert outputs["empty_matrix"] == "{}"

        summary = read_summary(summary_file)
        assert "### empty_matrix:" in summary
        assert "{}" in summary

    def test_write_single_entry_matrix(self, github_env: tuple[Path, Path]):
        """Single entry matrix is written correctly."""
        output_file, summary_file = github_env
        entries = [{"key": "value"}]
        write_matrix_to_output("single_matrix", entries)

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["single_matrix"])
        assert matrix["include"] == entries

        summary = read_summary(summary_file)
        assert "### single_matrix:" in summary

    def test_write_multiple_entries_matrix(self, github_env: tuple[Path, Path]):
        """Multiple entries matrix is written correctly."""
        output_file, summary_file = github_env
        entries = [
            {"library-name": "pkg1"},
            {"library-name": "pkg2"},
            {"library-name": "pkg3"},
        ]
        write_matrix_to_output("multi_matrix", entries)

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["multi_matrix"])
        assert matrix["include"] == entries
        assert len(matrix["include"]) == 3

    def test_matrix_includes_summary_header(self, github_env: tuple[Path, Path]):
        """Matrix name appears in summary as a header."""
        _, summary_file = github_env
        write_matrix_to_output("test_matrix", [{"item": "value"}])

        summary = read_summary(summary_file)
        assert "### test_matrix:" in summary
        assert "```json" in summary

    def test_matrix_json_formatting(self, github_env: tuple[Path, Path]):
        """Matrix JSON is properly formatted with indentation."""
        output_file, _ = github_env
        entries = [{"key1": "value1"}, {"key2": "value2"}]
        write_matrix_to_output("formatted_matrix", entries)

        outputs = parse_outputs(output_file)
        # The output should be valid JSON that can be parsed
        matrix = json.loads(outputs["formatted_matrix"])
        assert "include" in matrix
        assert len(matrix["include"]) == 2


class TestGetPrChanges:
    """Test the get_pr_changes function."""

    def test_get_pr_changes_empty(
        self, github_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ):
        """Empty PR changes returns empty list."""
        monkeypatch.delenv("PR_CHANGES_JSON", raising=False)
        result = get_pr_changes()

        assert result == []

    def test_get_pr_changes_single_package(
        self, github_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ):
        """Single package in PR changes is returned."""
        monkeypatch.setenv("PR_CHANGES_JSON", json.dumps(["glow-engine"]))
        result = get_pr_changes()

        assert result == ["glow-engine"]

    def test_get_pr_changes_multiple_packages(
        self, github_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ):
        """Multiple packages in PR changes are returned."""
        packages = ["glow-engine", "saf-cli", "saf-testing"]
        monkeypatch.setenv("PR_CHANGES_JSON", json.dumps(packages))
        result = get_pr_changes()

        assert result == packages

    def test_get_pr_changes_outputs_matrix(
        self, github_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ):
        """PR changes are written to output as a list."""
        output_file, _ = github_env
        packages = ["pkg1", "pkg2"]
        monkeypatch.setenv("PR_CHANGES_JSON", json.dumps(packages))
        get_pr_changes()

        outputs = parse_outputs(output_file)
        assert "pr_changes" in outputs
        pr_changes_list = json.loads(outputs["pr_changes"])
        assert len(pr_changes_list) == 2


class TestGetChangedPackages:
    """Test the get_changed_packages function."""

    def test_get_changed_packages_empty_input(self, github_env: tuple[Path, Path]):
        """Empty input returns empty list."""
        result = get_changed_packages([])
        assert result == []

    def test_get_changed_packages_single_valid_package(
        self, github_env: tuple[Path, Path]
    ):
        """Single valid package is returned."""
        result = get_changed_packages(["glow-engine"])
        assert result == ["glow-engine"]

    def test_get_changed_packages_multiple_valid_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Multiple valid packages are returned."""
        packages = ["glow-engine", "saf-cli", "saf-testing"]
        result = get_changed_packages(packages)
        assert result == packages

    def test_get_changed_packages_filters_invalid_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Invalid packages are filtered out."""
        packages = ["glow-engine", "invalid-pkg", "saf-cli"]
        result = get_changed_packages(packages)
        assert result == ["glow-engine", "saf-cli"]
        assert "invalid-pkg" not in result

    def test_get_changed_packages_all_invalid_packages(
        self, github_env: tuple[Path, Path]
    ):
        """All invalid packages returns empty list."""
        packages = ["unknown-pkg", "fake-pkg"]
        result = get_changed_packages(packages)
        assert result == []

    def test_get_changed_packages_preserves_order(self, github_env: tuple[Path, Path]):
        """Package order is preserved."""
        packages = ["saf-testing", "glow-engine", "saf-cli"]
        result = get_changed_packages(packages)
        assert result == packages

    def test_get_changed_packages_all_valid_packages(
        self, github_env: tuple[Path, Path]
    ):
        """All SAF packages can be in the input."""
        result = get_changed_packages(SAF_PACKAGES)
        assert result == SAF_PACKAGES

    def test_get_changed_packages_includes_moon_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Moon-managed packages are included in the package matrix."""
        output_file, _ = github_env
        result = get_changed_packages(["bdm-python-api", "glow-engine"])

        assert result == ["bdm-python-api", "glow-engine"]
        outputs = parse_outputs(output_file)
        assert json.loads(outputs["packages_matrix"]) == {
            "include": [
                {"library-name": "bdm-python-api"},
                {"library-name": "glow-engine"},
            ]
        }


class TestGetChangedPoetryPackages:
    """Test the get_changed_poetry_packages function."""

    def test_get_changed_poetry_packages_excludes_moon_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Moon-managed packages are excluded from the Poetry package matrix."""
        output_file, _ = github_env

        result = get_changed_poetry_packages(["bdm-python-api", "glow-engine"])

        assert result == ["glow-engine"]
        outputs = parse_outputs(output_file)
        assert json.loads(outputs["poetry_packages_matrix"]) == {
            "include": [{"library-name": "glow-engine"}]
        }

    def test_get_changed_poetry_packages_empty_input(
        self, github_env: tuple[Path, Path]
    ):
        """Empty input returns no Poetry packages."""
        output_file, _ = github_env

        result = get_changed_poetry_packages([])

        assert result == []
        outputs = parse_outputs(output_file)
        assert outputs["poetry_packages_matrix"] == "{}"


class TestGetChangedMoonPackages:
    """Test the get_changed_moon_packages function."""

    def test_get_changed_moon_packages_empty_input(self, github_env: tuple[Path, Path]):
        """Empty input returns no Moon packages."""
        output_file, _ = github_env

        result = get_changed_moon_packages([])

        assert result == []
        outputs = parse_outputs(output_file)
        assert outputs["moon_packages_matrix"] == "{}"

    def test_get_changed_moon_packages_returns_moon_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Moon-managed packages are returned and written to their matrix."""
        output_file, _ = github_env

        result = get_changed_moon_packages(["glow-engine", "bdm-python-api"])

        assert result == ["bdm-python-api"]
        outputs = parse_outputs(output_file)
        assert json.loads(outputs["moon_packages_matrix"]) == {
            "include": [{"library-name": "bdm-python-api"}]
        }

    def test_get_changed_moon_packages_filters_invalid_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Invalid and non-Moon packages are filtered out."""
        result = get_changed_moon_packages(["invalid-pkg", "saf-testing"])

        assert result == []


class TestGetCodeStyleMatrixEntries:
    """Test the get_code_style_matrix_entries function."""

    def test_get_code_style_matrix_empty_packages(self, github_env: tuple[Path, Path]):
        """Empty packages produce an empty matrix."""
        output_file, _ = github_env
        get_code_style_matrix_entries([])

        outputs = parse_outputs(output_file)
        assert outputs["code_style_matrix"] == "{}"

    def test_get_code_style_matrix_single_package(self, github_env: tuple[Path, Path]):
        """Single package includes one package entry."""
        output_file, _ = github_env
        get_code_style_matrix_entries(["saf-testing"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["code_style_matrix"])
        assert len(matrix["include"]) == 1
        assert matrix["include"][0]["target-directory"] == "packages/saf-testing"
        assert matrix["include"][0]["dependency-manager"] == "poetry"

    def test_get_code_style_matrix_includes_examples(
        self, github_env: tuple[Path, Path]
    ):
        """Examples changes add a style job for the examples project."""
        output_file, _ = github_env
        get_code_style_matrix_entries([], ["examples"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["code_style_matrix"])
        assert len(matrix["include"]) == 1
        assert matrix["include"][0] == {
            "target-directory": "examples",
            "dependency-manager": "poetry",
            "poetry-install-args": "--with tests --all-extras",
        }

    def test_get_code_style_matrix_multiple_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Multiple packages are all included."""
        output_file, _ = github_env
        get_code_style_matrix_entries(["glow-engine", "saf-iam-oidc"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["code_style_matrix"])
        assert len(matrix["include"]) == 2

    def test_get_code_style_matrix_uses_default_poetry_args(
        self, github_env: tuple[Path, Path]
    ):
        """Packages without custom args use default."""
        output_file, _ = github_env
        get_code_style_matrix_entries(["saf-testing"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["code_style_matrix"])
        package_entry = matrix["include"][0]
        assert package_entry["poetry-install-args"] == "--with tests --all-extras"

    def test_get_code_style_matrix_uses_custom_poetry_args(
        self, github_env: tuple[Path, Path]
    ):
        """Packages with custom args use those args."""
        output_file, _ = github_env
        get_code_style_matrix_entries(["glow-engine"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["code_style_matrix"])
        package_entry = matrix["include"][0]
        assert package_entry["poetry-install-args"] == "--with tests,style --all-extras"

    def test_get_code_style_matrix_multiple_packages_custom_args(
        self, github_env: tuple[Path, Path]
    ):
        """Multiple packages with different custom args are handled correctly."""
        output_file, _ = github_env
        get_code_style_matrix_entries(
            ["glow-engine", "saf-iam-oidc", "saf-desktop-orchestrator"]
        )

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["code_style_matrix"])

        # Check glow-engine entry
        glow_entry = [
            e
            for e in matrix["include"]
            if e["target-directory"] == "packages/glow-engine"
        ][0]
        assert glow_entry["poetry-install-args"] == "--with tests,style --all-extras"

        # Check saf-iam-oidc entry (default args)
        iam_entry = [
            e
            for e in matrix["include"]
            if e["target-directory"] == "packages/saf-iam-oidc"
        ][0]
        assert iam_entry["poetry-install-args"] == "--with tests --all-extras"

        # Check saf-desktop-orchestrator entry (custom args)
        desktop_entry = [
            e
            for e in matrix["include"]
            if e["target-directory"] == "packages/saf-desktop-orchestrator"
        ][0]
        assert desktop_entry["poetry-install-args"] == "--with tests,dev --all-extras"

    def test_get_code_style_matrix_filters_invalid_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Invalid packages are filtered out."""
        output_file, _ = github_env
        get_code_style_matrix_entries(["glow-engine", "invalid-pkg"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["code_style_matrix"])
        # Only glow-engine is included; invalid-pkg is filtered out.
        assert len(matrix["include"]) == 1
        assert all("invalid-pkg" not in str(e) for e in matrix["include"])


class TestGetCompatibilityMatrixEntries:
    """Test the get_compatibility_matrix_entries function."""

    def test_get_compatibility_matrix_empty_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Empty packages returns empty matrix."""
        output_file, _ = github_env
        get_compatibility_matrix_entries([])

        outputs = parse_outputs(output_file)
        assert outputs["compatibility_matrix"] == "{}"

    def test_get_compatibility_matrix_single_package(
        self, github_env: tuple[Path, Path]
    ):
        """Single package is included in matrix."""
        output_file, _ = github_env
        get_compatibility_matrix_entries(["glow-engine"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["compatibility_matrix"])
        assert len(matrix["include"]) == 1
        assert matrix["include"][0]["library-name"] == "glow-engine"

    def test_get_compatibility_matrix_multiple_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Multiple packages are included in matrix."""
        output_file, _ = github_env
        packages = ["glow-engine", "saf-testing", "saf-product-manager"]
        get_compatibility_matrix_entries(packages)

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["compatibility_matrix"])
        assert len(matrix["include"]) == 3
        names = [e["library-name"] for e in matrix["include"]]
        assert names == packages

    def test_get_compatibility_matrix_excludes_saf_cli(
        self, github_env: tuple[Path, Path]
    ):
        """saf-cli is excluded from compatibility matrix."""
        output_file, _ = github_env
        packages = ["glow-engine", "saf-cli", "saf-testing"]
        get_compatibility_matrix_entries(packages)

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["compatibility_matrix"])
        names = [e["library-name"] for e in matrix["include"]]
        assert "saf-cli" not in names
        assert "glow-engine" in names
        assert "saf-testing" in names

    def test_get_compatibility_matrix_only_saf_cli(self, github_env: tuple[Path, Path]):
        """Only saf-cli returns empty matrix."""
        output_file, _ = github_env
        get_compatibility_matrix_entries(["saf-cli"])

        outputs = parse_outputs(output_file)
        assert outputs["compatibility_matrix"] == "{}"

    def test_get_compatibility_matrix_outputs_to_summary(
        self, github_env: tuple[Path, Path]
    ):
        """Compatibility matrix is written to summary."""
        _, summary_file = github_env
        get_compatibility_matrix_entries(["glow-engine"])

        summary = read_summary(summary_file)
        assert "### compatibility_matrix:" in summary


class TestGetTestsMatrixEntries:
    """Test the get_tests_matrix_entries function."""

    def test_get_tests_matrix_empty_packages(self, github_env: tuple[Path, Path]):
        """Empty packages returns empty matrix."""
        output_file, _ = github_env
        get_tests_matrix_entries([], [])

        outputs = parse_outputs(output_file)
        assert outputs["tests_matrix"] == "{}"

    def test_get_tests_matrix_single_package_single_definition(
        self, github_env: tuple[Path, Path]
    ):
        """Single package with single test definition."""
        output_file, _ = github_env
        get_tests_matrix_entries(["saf-testing"], ["saf-testing"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["tests_matrix"])
        assert len(matrix["include"]) == 1
        assert matrix["include"][0]["library-name"] == "saf-testing"
        assert "saf-testing.json" in matrix["include"][0]["tests-groups-file-path"]

    def test_get_tests_matrix_examples(self, github_env: tuple[Path, Path]):
        """Examples changes produce an examples test entry."""
        output_file, _ = github_env
        get_tests_matrix_entries(["examples"], [])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["tests_matrix"])
        # Examples run from the examples directory with their dedicated definition.
        assert matrix["include"] == [
            {
                "library-name": "examples",
                "tests-groups-file-path": f"{TESTS_DEFINITIONS_DIR}/examples.json",
                "working-directory": "examples",
            }
        ]

    def test_get_tests_matrix_single_package_multiple_definitions(
        self, github_env: tuple[Path, Path]
    ):
        """Single package with multiple test definitions."""
        output_file, _ = github_env
        get_tests_matrix_entries(["glow-engine"], ["glow-engine"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["tests_matrix"])
        assert len(matrix["include"]) == 2  # glow-engine and glow-engine-extended
        library_names = [e["library-name"] for e in matrix["include"]]
        assert all(name == "glow-engine" for name in library_names)

    def test_get_tests_matrix_multiple_packages(self, github_env: tuple[Path, Path]):
        """Multiple packages with varying definitions."""
        output_file, _ = github_env
        get_tests_matrix_entries(
            ["glow-engine", "saf-iam-oidc"], ["glow-engine", "saf-iam-oidc"]
        )

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["tests_matrix"])
        # glow-engine has 2 definitions, saf-iam-oidc has 1
        assert len(matrix["include"]) == 3

    def test_get_tests_matrix_unknown_package(self, github_env: tuple[Path, Path]):
        """Unknown package is ignored."""
        output_file, _ = github_env
        get_tests_matrix_entries(["unknown-package"], ["unknown-package"])

        outputs = parse_outputs(output_file)
        assert outputs["tests_matrix"] == "{}"

    def test_get_tests_matrix_mixed_valid_invalid_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Only valid packages are included."""
        output_file, _ = github_env
        get_tests_matrix_entries(
            ["glow-engine", "unknown-package", "saf-testing"],
            ["glow-engine", "unknown-package", "saf-testing"],
        )

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["tests_matrix"])
        # glow-engine (2) + saf-testing (1) = 3 entries
        assert len(matrix["include"]) == 3
        names = [e["library-name"] for e in matrix["include"]]
        assert "unknown-package" not in names

    def test_get_tests_matrix_file_paths_are_correct(
        self, github_env: tuple[Path, Path]
    ):
        """File paths in matrix entries are correct."""
        output_file, _ = github_env
        get_tests_matrix_entries(["saf-testing"], ["saf-testing"])

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["tests_matrix"])
        file_path = matrix["include"][0]["tests-groups-file-path"]
        assert file_path.startswith(TESTS_DEFINITIONS_DIR)
        assert file_path.endswith("saf-testing.json")

    def test_get_tests_matrix_outputs_to_summary(self, github_env: tuple[Path, Path]):
        """Tests matrix is written to summary."""
        _, summary_file = github_env
        get_tests_matrix_entries(["glow-engine"], ["glow-engine"])

        summary = read_summary(summary_file)
        assert "### tests_matrix:" in summary

    def test_get_tests_matrix_includes_changed_product_manager_products(
        self, github_env: tuple[Path, Path]
    ):
        """Product-specific matrices are included when their labels and parent package changed."""
        output_file, _ = github_env
        get_tests_matrix_entries(
            [
                "saf-product-manager",
                "saf-product-manager-aedt",
                "saf-product-manager-fluent",
            ],
            ["saf-product-manager"],
        )

        outputs = parse_outputs(output_file)
        matrix = json.loads(outputs["tests_matrix"])
        assert len(matrix["include"]) == 3
        assert {entry["library-name"] for entry in matrix["include"]} == {
            "saf-product-manager"
        }
        assert {entry["tests-groups-file-path"] for entry in matrix["include"]} == {
            f"{TESTS_DEFINITIONS_DIR}/saf-product-manager.json",
            f"{TESTS_DEFINITIONS_DIR}/saf-product-manager-aedt.json",
            f"{TESTS_DEFINITIONS_DIR}/saf-product-manager-fluent.json",
        }

    def test_get_tests_matrix_excludes_product_manager_products_without_parent(
        self, github_env: tuple[Path, Path]
    ):
        """Product-specific matrices require a change to saf-product-manager."""
        output_file, _ = github_env
        get_tests_matrix_entries(["saf-product-manager-aedt"], [])

        outputs = parse_outputs(output_file)
        assert outputs["tests_matrix"] == "{}"


class TestGetTestGeneratedSolutionFlag:
    """Test the get_tests_generated_solution_flag function."""

    def test_get_tests_generated_solution_flag_empty_packages(
        self, github_env: tuple[Path, Path]
    ):
        """Empty packages outputs false flag."""
        output_file, _ = github_env
        get_tests_generated_solution_flag([])

        outputs = parse_outputs(output_file)
        assert outputs["tests_generated_solution_flag"] == "false"

    def test_get_tests_generated_solution_flag_without_saf_cli(
        self, github_env: tuple[Path, Path]
    ):
        """Packages without saf-cli output false flag."""
        output_file, _ = github_env
        get_tests_generated_solution_flag(["glow-engine", "saf-testing"])

        outputs = parse_outputs(output_file)
        assert outputs["tests_generated_solution_flag"] == "false"

    def test_get_tests_generated_solution_flag_with_saf_cli(
        self, github_env: tuple[Path, Path]
    ):
        """saf-cli in packages outputs true flag."""
        output_file, _ = github_env
        get_tests_generated_solution_flag(["saf-cli"])

        outputs = parse_outputs(output_file)
        assert outputs["tests_generated_solution_flag"] == "true"

    def test_get_tests_generated_solution_flag_saf_cli_with_others(
        self, github_env: tuple[Path, Path]
    ):
        """saf-cli with other packages outputs true flag."""
        output_file, _ = github_env
        get_tests_generated_solution_flag(["glow-engine", "saf-cli", "saf-testing"])

        outputs = parse_outputs(output_file)
        assert outputs["tests_generated_solution_flag"] == "true"


class TestIntegration:
    """Integration tests for the full workflow."""

    def test_full_workflow_no_changes(
        self, github_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ):
        """Full workflow with no changes produces correct output."""
        output_file, summary_file = github_env
        monkeypatch.delenv("PR_CHANGES_JSON", raising=False)

        pr_changes = get_pr_changes()
        get_changed_moon_packages(pr_changes)
        changed_packages = get_changed_packages(pr_changes)
        get_code_style_matrix_entries(changed_packages, pr_changes)
        get_compatibility_matrix_entries(changed_packages)
        get_tests_matrix_entries(pr_changes, changed_packages)
        get_tests_generated_solution_flag(changed_packages)

        outputs = parse_outputs(output_file)
        assert outputs["code_style_matrix"] == "{}"
        assert outputs["compatibility_matrix"] == "{}"
        assert outputs["tests_matrix"] == "{}"
        assert outputs["tests_generated_solution_flag"] == "false"

    def test_full_workflow_with_changes(
        self, github_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ):
        """Full workflow with multiple packages."""
        output_file, summary_file = github_env
        monkeypatch.setenv(
            "PR_CHANGES_JSON",
            json.dumps(["bdm-python-api", "glow-engine", "saf-cli", "examples"]),
        )

        pr_changes = get_pr_changes()
        moon_packages = get_changed_moon_packages(pr_changes)
        changed_packages = get_changed_packages(pr_changes)
        get_code_style_matrix_entries(changed_packages, pr_changes)
        get_compatibility_matrix_entries(changed_packages)
        get_tests_matrix_entries(pr_changes, changed_packages)
        get_tests_generated_solution_flag(changed_packages)

        outputs = parse_outputs(output_file)

        # Check all matrices are present
        assert "code_style_matrix" in outputs
        assert "moon_packages_matrix" in outputs
        assert "compatibility_matrix" in outputs
        assert "tests_matrix" in outputs
        assert "tests_generated_solution_flag" in outputs

        code_style = json.loads(outputs["code_style_matrix"])
        assert code_style["include"][-1] == {
            "target-directory": "examples",
            "dependency-manager": "poetry",
            "poetry-install-args": "--with tests --all-extras",
        }

        assert moon_packages == ["bdm-python-api"]
        assert json.loads(outputs["moon_packages_matrix"]) == {
            "include": [{"library-name": "bdm-python-api"}]
        }

        # Verify that the working directory for examples is correctly set
        tests = json.loads(outputs["tests_matrix"])
        examples_entries = [
            entry for entry in tests["include"] if entry["library-name"] == "examples"
        ]
        assert examples_entries == [
            {
                "library-name": "examples",
                "tests-groups-file-path": f"{TESTS_DEFINITIONS_DIR}/examples.json",
                "working-directory": "examples",
            }
        ]

        # Verify saf-cli is excluded from compatibility matrix
        compatibility = json.loads(outputs["compatibility_matrix"])
        names = [e["library-name"] for e in compatibility["include"]]
        assert "saf-cli" not in names

        # Verify test flag is set to true
        assert outputs["tests_generated_solution_flag"] == "true"

    def test_full_workflow_summary_content(
        self, github_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ):
        """All matrices appear in the step summary."""
        _, summary_file = github_env
        monkeypatch.setenv("PR_CHANGES_JSON", json.dumps(["glow-engine"]))

        pr_changes = get_pr_changes()
        get_changed_moon_packages(pr_changes)
        changed_packages = get_changed_packages(pr_changes)
        get_code_style_matrix_entries(changed_packages, pr_changes)
        get_compatibility_matrix_entries(changed_packages)
        get_tests_matrix_entries(pr_changes, changed_packages)

        summary = read_summary(summary_file)
        assert "### pr_changes:" in summary
        assert "### moon_packages_matrix:" in summary
        assert "### packages_matrix:" in summary
        assert "### code_style_matrix:" in summary
        assert "### compatibility_matrix:" in summary
        assert "### tests_matrix:" in summary
        assert summary.count("```json") == 6


class TestDataValidation:
    """Validate that test data files exist and constants are correct."""

    def test_tests_definitions_files_exist(self) -> None:
        """Every referenced test group definition file exists in the repository."""
        repository_root = Path(__file__).parents[3]
        for definitions in TESTS_DEFINITIONS_PER_TARGET.values():
            for definition in definitions:
                file_path = (
                    repository_root / TESTS_DEFINITIONS_DIR / f"{definition}.json"
                )
                assert file_path.is_file(), (
                    f"Test definition file not found: {file_path}"
                )

    def test_saf_packages_list_is_not_empty(self) -> None:
        """SAF_PACKAGES list is not empty."""
        assert len(SAF_PACKAGES) > 0

    def test_all_packages_have_test_definitions(self) -> None:
        """All SAF packages have test definitions."""
        for package in SAF_PACKAGES:
            assert package in TESTS_DEFINITIONS_PER_TARGET


if __name__ == "__main__":
    sys.exit(
        pytest.main([__file__, *sys.argv[1:]] if sys.argv[1:] else [__file__, "-v"])
    )
