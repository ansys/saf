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

"""Generate SDK dependency summaries and versioned Sphinx release notes.

The release action writes a Markdown summary for GitHub Actions and a separate
reStructuredText file for each SDK release. The RST files are included by the
documentation build, so keep the rendering behavior covered by the focused tests.
"""

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
from packaging.version import InvalidVersion, Version
import requests

MD_RELEASE_NOTES_FILE = REPO_ROOT / "release_notes.md"
RST_RELEASE_NOTES_DIR = REPO_ROOT / "doc" / "source" / "release_notes" / "notes_per_release"
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

def _write_rst_release_notes(release_notes: str, meta_package_version: str) -> Path:
    """Write generated release notes to a versioned RST file.

    If this is a newly-created version newer than all existing versioned files,
    close the outer dropdown in the previous latest release. Nested package
    dropdowns and older release files are intentionally left unchanged.

    Parameters
    ----------
    release_notes : str
        Fully rendered RST content for this SDK release.
    meta_package_version : str
        SDK release version used as the output filename.

    Returns
    -------
    pathlib.Path
        Path to the written versioned RST file.
    """
    version = Version(meta_package_version)
    RST_RELEASE_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    release_notes_path = RST_RELEASE_NOTES_DIR / f"{version}.rst"

    existing_releases: list[tuple[Version, Path]] = []
    for existing_path in RST_RELEASE_NOTES_DIR.glob("*.rst"):
        if existing_path == release_notes_path:
            continue
        try:
            existing_version = Version(existing_path.stem)
        except InvalidVersion:
            continue
        existing_releases.append((existing_version, existing_path))

    if existing_releases and not release_notes_path.exists():
        previous_latest_version, previous_latest_path = max(existing_releases, key=lambda entry: entry[0])
        if version > previous_latest_version:
            content = previous_latest_path.read_text(encoding="utf-8").splitlines(keepends=True)
            open_index = next(
                (idx for idx, line in enumerate(content) if line.strip() == RST_MARKER_FOR_OPEN_DROPDOWN),
                None,
            )
            if open_index is not None:
                del content[open_index]
                previous_latest_path.write_text("".join(content), encoding="utf-8")

    release_notes_path.write_text(release_notes, encoding="utf-8")
    return release_notes_path


def _render_rst_release_notes(
    versions: dict[str, str],
    meta_package_version: str,
    private_package_versions: dict[str, str],
    package_release_notes: dict[str, str],
    minimum_pip_version: str,
) -> str:
    """Render the full RST document for one SDK release.

    Package notes are rendered as individual dropdowns; private package versions
    are shown in a separate table because their versions are resolved independently.
    """
    release_date = date.today().strftime("%B %d, %Y").replace(" 0", " ")
    title = (
        f"`{meta_package_version} "
        f"<https://github.com/ansys/saf/releases/tag/v{meta_package_version}-saf-sdk>`_ — {release_date}"
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
        f"  The public package versions below were resolved for this version of ``{META_PACKAGE_NAME}``.",
    ]

    for package, notes in package_release_notes.items():
        rst_lines.extend(_render_package_release_notes(package, versions[package], notes))

    if private_package_versions:
        rst_lines.extend(
            [
                "",
                "  The private-package versions were fetched separately as the latest available versions",
                "",
                "    .. list-table::",
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

    return "\n".join(rst_lines).rstrip() + "\n"


def _render_package_release_notes(package: str, version: str, notes: str) -> list[str]:
    """Convert one package's Markdown release notes into an RST dropdown.

    Markdown headings become list-table categories, and each item is split into
    a description and an optional pull-request link. Author attribution is
    omitted, HTML tags are stripped while retaining their text, and inline
    Markdown code and links are converted to RST syntax. Notes without a
    heading are assigned to the default ``Changes`` category.

    Parameters
    ----------
    package : str
        Package name shown in the dropdown title.
    version : str
        Package version shown in the dropdown title.
    notes : str
        Markdown release-note body, or one of the known no-notes messages.

    Returns
    -------
    list[str]
        RST lines for the package dropdown.
    """
    rendered = ["", "", f"  .. dropdown:: {package} {version}", ""]
    if notes == "No changes":
        return [*rendered, "    No changes"]
    if notes == "No release notes available":
        return [*rendered, "    No release notes available"]

    # Unheaded release-note bullets are kept under a predictable default category.
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
            # Remove PR author attribution; the PR is linked separately in the rendered table.
            rst_line = re.sub(r"\s+by @[\w-]+(?=\s+in \[)", "", line)
            # Preserve text from HTML tags, replacing explicit line breaks with spaces.
            rst_line = re.sub(r"<br\b[^>]*>", " ", rst_line, flags=re.IGNORECASE)
            rst_line = re.sub(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^<>]*?)?\s*/?>", "", rst_line)
            # Convert Markdown inline code and links to their reStructuredText equivalents.
            rst_line = re.sub(r"(?<!`)`([^`]+)`(?!`)", r"``\1``", rst_line)
            rst_line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"`\1 <\2>`_", rst_line)
            current_lines.append(rst_line)
    categories.append((current_category, current_lines))

    # Keep :open: adjacent to the dropdown directive; the following blank line is intentional.
    rendered[3:3] = ["    :open:"]
    for category, category_lines in categories:
        items = [line.strip().lstrip("*- ").strip() for line in category_lines if line.strip()]
        if not items:
            continue
        rendered.extend(
            [
                "    .. list-table::",
                "      :header-rows: 1",
                "      :stub-columns: 1",
                "      :widths: 80 20",
                "",
                f"      * - {category}",
                "        - Pull Request",
            ],
        )
        for item in items:
            pull_request = re.search(r"`([^`]*#\d+)\s*<([^>]+)>`_", item)
            if pull_request:
                description = item[: pull_request.start()].rstrip()
                pull_request_link = f"`{pull_request.group(1)} <{pull_request.group(2)}>`_"
            else:
                description = item
                pull_request_link = ""
            rendered.extend([f"      * - {description}", f"        - {pull_request_link}"])
        rendered.append("")
    return rendered


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
    """Generate the dependency summary and release notes for an SDK release.

    Writes a Markdown report, a versioned RST document, and—when configured—a
    GitHub Actions step summary. The returned list is the Markdown report split
    into lines.

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
    The documentation file is written under ``notes_per_release`` using the
    meta-package version as its filename. ``GITHUB_STEP_SUMMARY`` is optional.
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

    rst_package_release_notes = {
        package: package_release_notes.get(
            package,
            "No changes"
            if versions[package] == current_versions[package] and meta_package_version != INITIAL_META_PACKAGE_VERSION
            else "No release notes available",
        )
        for package in PACKAGES
    }

    md_content += "<!-- THIS LINE IS A PLACEHOLDER FOR PYANSYS COMPATIBILITY SECTION -->"

    MD_RELEASE_NOTES_FILE.write_text(md_content, encoding="utf-8")
    rst_content = _render_rst_release_notes(
        versions,
        meta_package_version,
        private_package_versions,
        rst_package_release_notes,
        minimum_pip_version,
    )
    _write_rst_release_notes(rst_content, meta_package_version)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("w", encoding="utf-8") as summary_file:
            summary_file.write(md_content)

    print(f"Package versions summary written to {MD_RELEASE_NOTES_FILE}.")
    return md_content.splitlines()
