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

from datetime import date
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

MD_RELEASE_NOTES_FILE = REPO_ROOT / "release_notes.md"
ORIGINAL_RELEASE_NOTES_FILE = REPO_ROOT / "doc" / "source" / "release_notes" / "index.rst"
RST_MARKER_FOR_INSERT = ".. NEW_RELEASES_NOTES-INSERT-HERE (auto-generated entries go here; do no edit or removed)"
RST_MARKER_FOR_OPEN_DROPDOWN = ":open:"
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

def _remove_open_directive_from_dropdown() -> list[str]:
    if not ORIGINAL_RELEASE_NOTES_FILE.exists():
        raise FileNotFoundError(f"The file {ORIGINAL_RELEASE_NOTES_FILE} does not exist.")

    with ORIGINAL_RELEASE_NOTES_FILE.open("r", encoding="utf-8") as file:
        content = file.readlines()

    marker_index = next(
        (idx for idx, line in enumerate(content) if RST_MARKER_FOR_INSERT in line),
        None,
    )
    if marker_index is None:
        raise ValueError(f"Could not find release-note insertion marker in {ORIGINAL_RELEASE_NOTES_FILE}.")

    open_index = next(
        (
            idx
            for idx, line in enumerate(content[marker_index + 1 :], marker_index + 1)
            if line.strip() == RST_MARKER_FOR_OPEN_DROPDOWN
        ),
        None,
    )
    if open_index is not None:
        del content[open_index]

    return content


def _render_rst_release_notes(
    versions: dict[str, str],
    meta_package_version: str,
    private_package_versions: dict[str, str],
    package_release_notes: dict[str, str],
    minimum_pip_version: str,
) -> str:
    """Render a release-note entry in the format used by the documentation."""
    release_date = date.today().strftime("%B %d, %Y").replace(" 0", " ")
    title = (
        f"`{meta_package_version} "
        f"<https://github.com/ansys/saf/releases#release-v{meta_package_version}-saf-sdk>`_ — {release_date}"
    )
    rst_lines = [
        title,
        "=" * len(title),
        "",
        ".. dropdown::",
        "  :class-container: dropdown",
        "  :open:",
        "  :chevron: down-up",
        "",
        "  .. note::",
        f"     Installing ``{META_PACKAGE_NAME}`` requires pip {minimum_pip_version} or higher.",
        "",
        "  .. rubric:: Dependency versions",
        "",
        (
            f"  The public package versions below were resolved for this version of ``{META_PACKAGE_NAME}``. "
            "The private-package versions were fetched separately as the latest available versions:"
        ),
        "",
        "  .. tab-set::",
        "",
        "    .. tab-item:: Packages",
        "",
        "      .. list-table::",
        "        :header-rows: 1",
        "        :stub-columns: 1",
        "        :widths: 60 20 20",
        "",
        "        * - Package",
        "          - Version",
        "          - Maintenance window",
    ]

    for package in PACKAGES:
        rst_lines.extend([f"        * - ``{package}``", f"          - ``{versions[package]}``", "          - —"])

    if private_package_versions:
        rst_lines.extend(
            [
                "",
                "    .. tab-item:: Private packages",
                "",
                "      .. list-table::",
                "        :header-rows: 1",
                "        :stub-columns: 1",
                "        :widths: 80 20",
                "",
                "        * - Private package",
                "          - Version",
            ],
        )
        for package, version in private_package_versions.items():
            rst_lines.extend([f"        * - ``{package}``", f"          - ``{version}``"])

    for package, notes in package_release_notes.items():
        rst_lines.extend(_render_package_release_notes(package, versions[package], notes))

    return "\n".join(rst_lines).rstrip() + "\n"


def _render_package_release_notes(package: str, version: str, notes: str) -> list[str]:
    """Render a package's Markdown release notes as RST tabs."""
    rendered = [
        "",
        "",
        f"  .. rubric:: ``{package}`` `{version} "
        f"<https://github.com/ansys/saf/releases/tag/v{version}-{PACKAGE_LIBRARY_DIRS[package]}>`_",
        "",
        "  .. tab-set::",
        "",
    ]
    categories: list[tuple[str, list[str]]] = []
    current_category = "Changes"
    current_lines: list[str] = []
    for line in notes.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            categories.append((current_category, current_lines))
            current_category = heading.group(1).strip()
            current_lines = []
        else:
            rst_line = re.sub(r"(?<!`)`([^`]+)`(?!`)", r"``\1``", line)
            rst_line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"`\1 <\2>`_", rst_line)
            current_lines.append(rst_line)
    categories.append((current_category, current_lines))

    for category, category_lines in categories:
        while category_lines and not category_lines[0].strip():
            category_lines.pop(0)
        while category_lines and not category_lines[-1].strip():
            category_lines.pop()
        if category_lines:
            rendered.extend([f"    .. tab-item:: {category}", ""])
            rendered.extend(f"      {line}" if line else "" for line in category_lines)
            rendered.append("")
    return rendered


def _insert_rst_release_notes(release_notes: str, meta_package_version: str) -> None:
    """Insert a generated release-note entry into the documentation."""
    content = _remove_open_directive_from_dropdown()
    marker_index = next(idx for idx, line in enumerate(content) if RST_MARKER_FOR_INSERT in line)
    if any(f"#release-v{meta_package_version}-saf-sdk" in line for line in content[marker_index + 1 :]):
        print(f"Release notes for {META_PACKAGE_NAME} {meta_package_version} are already present.")
        return

    content[marker_index + 1 : marker_index + 1] = ["\n", release_notes, "\n"]
    ORIGINAL_RELEASE_NOTES_FILE.write_text("".join(content), encoding="utf-8")



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
) -> list[str]:
    """Write dependency versions and package release notes to Markdown file and return its content as a list of strings.

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
    The Markdown report and documentation release-note entry are written to
    their respective files. The Markdown report is also written to the GitHub
    Actions step summary when ``GITHUB_STEP_SUMMARY`` is configured.
    Returns
    -------
    list[str]
        Content of the generated release notes as a list of strings.
    """
    print(f"Generating package versions summary in {MD_RELEASE_NOTES_FILE}...")

    rows = [f"| `{package}` | `{versions[package]}` |" for package in PACKAGES]

    minimum_pip_version = os.environ["MINIMUM_PIP_VERSION"]

    md_content = "\n".join(
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
        md_content += "\n\n" + "\n".join(
            [
                "",
                "| Private Package | Version |",
                "| --- | --- |",
                *[f"| `{package}` | `{version}` |" for package, version in private_package_versions.items()],
                "---",
            ],
        )

    package_release_notes: dict[str, str] = {}
    for package in PACKAGES:
        if versions[package] == current_versions[package] and meta_package_version != INITIAL_META_PACKAGE_VERSION:
            package_notes = "No changes"
        else:
            package_notes = get_release_notes(package, versions[package])

        if package_notes:
            package_release_notes[package] = package_notes
            md_content += "\n\n" + "\n".join(
                [
                    f"# {package} {versions[package]}",
                    "",
                    package_notes,
                    "",
                ],
            )

    md_content += "<!-- THIS LINE IS A PLACEHOLDER FOR PYANSYS COMPATIBILITY SECTION -->"

    MD_RELEASE_NOTES_FILE.write_text(md_content, encoding="utf-8")
    rst_content = _render_rst_release_notes(
        versions,
        meta_package_version,
        private_package_versions,
        package_release_notes,
        minimum_pip_version,
    )
    _insert_rst_release_notes(rst_content, meta_package_version)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("w", encoding="utf-8") as summary_file:
            summary_file.write(md_content)

    print(f"Package versions summary written to {MD_RELEASE_NOTES_FILE}.")
    return md_content.splitlines()
