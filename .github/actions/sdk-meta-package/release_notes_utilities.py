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

import os
from pathlib import Path
import re

from azdo_feed_fetch_version import get_latest_versions
from constants import (
    INITIAL_META_PACKAGE_VERSION,
    META_PACKAGE_NAME,
    PACKAGE_LIBRARY_DIRS,
    REPO_ROOT,
)
import requests

RELEASE_NOTES_FILE = REPO_ROOT / "release_notes.md"
GITHUB_RELEASE_URL = "https://api.github.com/repos/ansys/saf/releases/tags/{tag}"
PACKAGES = list(PACKAGE_LIBRARY_DIRS)

PRIVATE_PACKAGES = [
    "ansys-saf-pim-light-server",
    "ansys-translation-utilities",
    "ansys-saf-desktop-portal",
    "ansys-saf-web-portal",
    "ansys-minerva-python-client",
    "ansys-datarepository-python-client",
    "ansys-saf-hermes",
    "ansys-saf-aspire",
]


def get_release_notes(package: str, version: str) -> str | None:
    """Return GitHub release notes for a package version.

    The release is looked up using the tag ``v{version}-{library-dir}``. HTML
    comments are removed, and when present, only the content after the
    ``What's changed`` heading is returned.

    Parameters
    ----------
    package : str
        Package name used to determine its repository library directory.
    version : str
        Package release version.

    Returns
    -------
    str or None
        Cleaned release-note content, or ``None`` when the release is missing
        or has an empty body.

    Raises
    ------
    requests.HTTPError
        If GitHub returns an unsuccessful response other than ``404``.
    """
    tag = f"v{version}-{PACKAGE_LIBRARY_DIRS[package]}"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(GITHUB_RELEASE_URL.format(tag=tag), headers=headers, timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    body = response.json()["body"]
    if not body:
        return None

    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
    match = re.search(r"^#{1,6}\s*what's changed\s*$", body, flags=re.IGNORECASE | re.MULTILINE)
    notes = body[match.end() :].lstrip("\n").strip() if match else body
    return notes or None


def generate_release_notes(
    versions: dict[str, str],
    meta_package_version: str,
    current_versions: dict[str, str],
) -> None:
    """Write dependency versions and package release notes to Markdown files.

    Parameters
    ----------
    versions : dict[str, str]
        Resolved package versions to include in the report.
    meta_package_version : str
        Version of the generated meta-package.
    current_versions : dict[str, str]
        Versions currently declared by the meta-package, used to identify
        packages without changes.

    Notes
    -----
    The report is written to ``RELEASE_NOTES_FILE`` and, when configured, to
    the GitHub Actions step summary identified by ``GITHUB_STEP_SUMMARY``.
    """
    print(f"Generating package versions summary in {RELEASE_NOTES_FILE}...")

    rows = [f"| `{package}` | `{versions[package]}` |" for package in PACKAGES]

    minimum_pip_version = os.environ["MINIMUM_PIP_VERSION"]

    content = "\n".join(
        [
            "<!-- DO NOT EDIT BELOW THIS LINE; THIS SECTION OF THE FILE IS AUTO-GENERATED -->",
            f"# {META_PACKAGE_NAME} {meta_package_version}",
            f"**Note:** Installing `{META_PACKAGE_NAME}` requires **pip {minimum_pip_version}** or higher.",
            "## Dependency Versions",
            "",
            f"The following versions were resolved when this version of the {META_PACKAGE_NAME} was generated.",
            "",
            "| Package | Version |",
            "| --- | --- |",
            *rows,
            "",
        ],
    )

    private_package_versions = get_latest_versions(PRIVATE_PACKAGES)
    if private_package_versions:
        content += "\n\n" + "\n".join(
            [
                "",
                "| Private Package | Version |",
                "| --- | --- |",
                *[f"| `{package}` | `{version}` |" for package, version in private_package_versions.items()],
                "---",
            ],
        )

    for package in PACKAGES:
        if versions[package] == current_versions[package] and meta_package_version != INITIAL_META_PACKAGE_VERSION:
            package_notes = "No changes"
        else:
            package_notes = get_release_notes(package, versions[package])

        if package_notes:
            content += "\n\n" + "\n".join(
                [
                    f"# {package} {versions[package]}",
                    "",
                    package_notes,
                    "",
                ],
            )

    RELEASE_NOTES_FILE.write_text(content, encoding="utf-8")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("w", encoding="utf-8") as summary_file:
            summary_file.write(content)

    print(f"Package versions summary written to {RELEASE_NOTES_FILE}.")
