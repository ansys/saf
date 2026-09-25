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
# dependencies = []
# ///

"""Build the job matrices consumed by the CI/CD workflow."""

import json
import os
from pathlib import Path

SAF_PACKAGES = [
    "bdm-python-api",
    "bdm-python-shared-volume",
    "dash-super-components",
    "glow-engine",
    "saf-cli",
    "saf-desktop-installer",
    "saf-desktop-orchestrator",
    "saf-iam-oidc",
    "saf-product-configuration",
    "saf-product-manager",
    "saf-templates",
    "saf-testing",
]

FLAGSHIP_PRODUCTS = [
    "aedt",
    "fluent",
    "geometry",
    "mapdl",
    "mechanical",
    "optislang",
    "visor",
]


DEFAULT_CODE_STYLE_POETRY_ARGS = "--with tests --all-extras"

CODE_STYLE_POETRY_ARGS = {
    "glow-engine": "--with tests,style --all-extras",
    "saf-desktop-installer": "--with tests,style --all-extras",
    "saf-desktop-orchestrator": "--with tests,dev --all-extras",
    "dash-super-components": "--with tests,style --all-extras",
}

TESTS_DEFINITIONS_DIR = ".github/workflows/tests_groups_definitions"

TESTS_DEFINITIONS_PER_TARGET = {
    "bdm-python-api": ["bdm-python-api"],
    "bdm-python-shared-volume": ["bdm-python-shared-volume"],
    "dash-super-components": ["dash-super-components"],
    "glow-engine": ["glow-engine", "glow-engine-extended"],
    "saf-cli": ["saf-cli", "saf-cli-extended"],
    "saf-desktop-installer": [
        "saf-desktop-installer",
        "saf-desktop-installer-extended",
    ],
    "saf-desktop-orchestrator": ["saf-desktop-orchestrator"],
    "saf-iam-oidc": ["saf-iam-oidc"],
    "saf-product-configuration": ["saf-product-configuration"],
    "saf-product-manager": ["saf-product-manager"],
    "saf-templates": ["saf-templates"],
    "saf-testing": ["saf-testing"],
    "examples": ["examples"],
}

UV_PACKAGES = [
    "bdm-python-api",
    "bdm-python-shared-volume",
    "saf-desktop-installer",
    "saf-iam-oidc",
    "saf-product-configuration",
]


def write_output(name: str, value: str) -> None:
    """Append a multiline output to the ``GITHUB_OUTPUT`` file."""
    output_file = Path(os.environ["GITHUB_OUTPUT"])
    with output_file.open("a", encoding="utf-8") as f:
        f.write(f"{name}<<EOF\n{value}\nEOF\n")


def write_to_github_step_summary(content: str) -> None:
    """Append content to the GitHub step summary file."""
    summary_file = Path(os.environ["GITHUB_STEP_SUMMARY"])
    with summary_file.open("a", encoding="utf-8") as f:
        f.write(content + "\n")


def write_matrix_to_output(name: str, entries: list[dict[str, str]]) -> None:
    """Write a matrix as an output and echo it in the job summary."""
    value = json.dumps({"include": entries}, indent=2) if entries else "{}"
    write_output(name, value)
    write_to_github_step_summary(f"### {name}:\n```json\n{value}\n```\n")


def get_pr_changes() -> list[str]:
    pr_changes = json.loads(os.environ.get("PR_CHANGES_JSON") or "[]")
    write_output("pr_changes", json.dumps(list(pr_changes)))
    write_to_github_step_summary(
        f"### pr_changes:\n```json\n{json.dumps(list(pr_changes), indent=2)}\n```\n",
    )
    return pr_changes


def get_changed_moon_packages(pr_changes: list[str]) -> list[str]:
    changed_packages = [pkg for pkg in pr_changes if pkg in UV_PACKAGES]
    write_matrix_to_output("moon_packages_matrix", [{"library-name": pkg} for pkg in changed_packages])
    return changed_packages


def get_changed_poetry_packages(pr_changes: list[str]) -> list[str]:
    changed_packages = [pkg for pkg in pr_changes if pkg in SAF_PACKAGES and pkg not in UV_PACKAGES]
    write_matrix_to_output("poetry_packages_matrix", [{"library-name": pkg} for pkg in changed_packages])
    return changed_packages


def get_changed_packages(pr_changes: list[str]) -> list[str]:
    changed_packages = [pkg for pkg in pr_changes if pkg in SAF_PACKAGES]
    write_matrix_to_output("packages_matrix", [{"library-name": pkg} for pkg in changed_packages])
    return changed_packages


def get_code_style_matrix_entries(changed_packages: list[str], pr_changes: list[str] | None = None) -> None:
    package_entries = [
        {
            "target-directory": f"packages/{pkg}",
            "dependency-manager": "poetry",
            "poetry-install-args": CODE_STYLE_POETRY_ARGS.get(pkg, DEFAULT_CODE_STYLE_POETRY_ARGS),
        }
        for pkg in changed_packages
        if pkg in SAF_PACKAGES and pkg not in UV_PACKAGES
    ]
    code_style_entries = [*package_entries]
    if pr_changes and "examples" in pr_changes:
        code_style_entries.append(
            {
                "target-directory": "examples",
                "dependency-manager": "poetry",
                "poetry-install-args": DEFAULT_CODE_STYLE_POETRY_ARGS,
            },
        )
    write_matrix_to_output("code_style_matrix", code_style_entries)


def get_compatibility_matrix_entries(changed_packages: list[str]) -> None:
    write_matrix_to_output(
        "compatibility_matrix",
        [{"library-name": pkg} for pkg in changed_packages if pkg != "saf-cli"],
    )


def get_tests_matrix_entries(pr_changes: list[str], changed_packages: list[str]) -> None:
    tests_matrix = [
        {
            "library-name": pkg,
            "tests-groups-file-path": f"{TESTS_DEFINITIONS_DIR}/{definition}.json",
            "working-directory": f"packages/{pkg}",
        }
        for pkg in changed_packages
        for definition in TESTS_DEFINITIONS_PER_TARGET.get(pkg, [])
    ]

    if "saf-product-manager" in changed_packages:
        for product in FLAGSHIP_PRODUCTS:
            if f"saf-product-manager-{product}" in pr_changes:
                tests_matrix.append(
                    {
                        "library-name": "saf-product-manager",
                        "tests-groups-file-path": f"{TESTS_DEFINITIONS_DIR}/saf-product-manager-{product}.json",
                        "working-directory": "packages/saf-product-manager",
                    },
                )

    if "examples" in pr_changes:
        tests_matrix.append(
            {
                "library-name": "examples",
                "tests-groups-file-path": f"{TESTS_DEFINITIONS_DIR}/examples.json",
                "working-directory": "examples",
            },
        )

    write_matrix_to_output(
        "tests_matrix",
        tests_matrix,
    )


def get_tests_generated_solution_flag(changed_packages: list[str]) -> None:
    flag = "true" if "saf-cli" in changed_packages else "false"
    write_output("tests_generated_solution_flag", flag)


pr_changes = get_pr_changes()
changed_packages = get_changed_packages(pr_changes)
get_changed_poetry_packages(pr_changes)
get_changed_moon_packages(pr_changes)
get_code_style_matrix_entries(changed_packages, pr_changes)
get_compatibility_matrix_entries(changed_packages)
get_tests_matrix_entries(pr_changes, changed_packages)
get_tests_generated_solution_flag(changed_packages)
