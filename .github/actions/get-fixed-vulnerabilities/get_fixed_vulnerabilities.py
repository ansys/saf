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
#   "requests>=2.32"
# ]
# ///

"""Insert fixed Dependabot alerts for selected uv members into Markdown release notes."""

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
import html
import os
from pathlib import Path
import re
import subprocess
from typing import TypedDict

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import requests

MEMBER_PER_LIBRARY_DIRECTORY = {
    "bdm-python-api": "ansys-bdm-api",
    "bdm-python-shared-volume": "ansys-bdm-shared-volume",
    "dash-super-components": "ansys-solutions-dash-super-components",
    "glow-engine": "ansys-saf-glow-engine",
    "saf-cli": "ansys-saf-cli",
    "saf-desktop-installer": "ansys-saf-desktop-installer",
    "saf-desktop-orchestrator": "ansys-saf-desktop-orchestrator",
    "saf-iam-oidc": "ansys-iam-oidc",
    "saf-product-configuration": "ansys-saf-product-configuration",
    "saf-product-manager": "ansys-saf-product-manager",
    "saf-projects-dashboard": "ansys-saf-projects-dashboard",
    "saf-sdk": "ansys-saf-sdk",
    "saf-templates": "ansys-saf-templates",
    "saf-testing": "ansys-saf-testing",
}


class Package(TypedDict):
    name: str
    ecosystem: str


class Advisory(TypedDict):
    summary: str


class Vulnerability(TypedDict):
    severity: str
    package: Package
    advisory: Advisory


class Alert(TypedDict):
    number: int
    fixedAt: str | None
    vulnerableManifestPath: str
    securityVulnerability: Vulnerability


INTERNAL_NOTES_MARKER = (
    "<!-- DO NOT EDIT BELOW THIS LINE; INTERNAL INFORMATION WILL BE REMOVED AUTOMATICALLY FOR THE END USERS -->"
)

GRAPHQL_QUERY = """
query GetClosedAlerts($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    vulnerabilityAlerts(first: 100, after: $cursor, states: [FIXED]) {
      pageInfo { endCursor hasNextPage }
      nodes {
        number
        fixedAt
        vulnerableManifestPath
        securityVulnerability {
          severity
          package { name ecosystem }
          advisory { summary }
        }
      }
    }
  }
}
"""


def parse_date(value: str) -> datetime:
    """Parse an ISO date or timestamp, interpreting naive values as UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def fetch_closed_alerts(owner: str, name: str, token: str) -> list[Alert]:
    """Fetch all fixed alerts, raising on HTTP, GraphQL, or pagination errors."""
    alerts: list[Alert] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    while True:
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": GRAPHQL_QUERY, "variables": {"owner": owner, "name": name, "cursor": cursor}},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise RuntimeError(f"GitHub GraphQL errors: {data['errors']}")
        repository = data["data"]["repository"]
        if repository is None:
            raise RuntimeError(f"Repository {owner}/{name} not found or inaccessible.")
        connection = repository["vulnerabilityAlerts"]
        alerts.extend(connection["nodes"])
        page_info = connection["pageInfo"]
        if not page_info["hasNextPage"]:
            return alerts
        cursor = page_info["endCursor"]
        if not cursor or cursor in seen_cursors:
            raise RuntimeError("GitHub returned an invalid pagination cursor.")
        seen_cursors.add(cursor)


def get_closed_alerts_since_for_manifest_file(
    last_release_date: datetime,
    manifest_files: Sequence[str],
    *,
    owner: str,
    name: str,
    token: str,
) -> list[Alert]:
    """Return alerts fixed strictly after the release date for any exact manifest path."""
    if not manifest_files:
        raise ValueError("At least one manifest path is required.")
    cutoff = last_release_date
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)
    manifests = {path.replace("\\", "/") for path in manifest_files}
    alerts = [
        alert
        for alert in fetch_closed_alerts(owner, name, token)
        if alert["vulnerableManifestPath"] in manifests
        and alert["fixedAt"] is not None
        and parse_date(alert["fixedAt"]) > cutoff
    ]
    return sorted(alerts, key=lambda alert: parse_date(alert["fixedAt"] or ""))


def get_packages_from_members(members: Sequence[str], repository: Path = Path()) -> list[str]:
    """Export dependencies for selected directories under packages, including all extras.

    Directory names are resolved through MEMBER_PER_LIBRARY_DIRECTORY.
    Dependency names are normalized and deduplicated. Environment markers are not evaluated,
    so dependencies for every platform represented in the lockfile are retained.
    """
    if not members:
        raise ValueError("At least one uv workspace member is required.")
    unknown = sorted(set(members) - MEMBER_PER_LIBRARY_DIRECTORY.keys())
    if unknown:
        raise ValueError(f"Unknown package directories: {', '.join(unknown)}")
    command = [
        "uv",
        "export",
        "--format",
        "requirements.txt",
        "--all-extras",
        "--no-dev",
        "--no-emit-workspace",
        "--no-hashes",
        "--no-annotate",
        "--no-header",
        "--locked",
    ]
    for member in members:
        command.extend(["--package", MEMBER_PER_LIBRARY_DIRECTORY[member]])
    result = subprocess.run(command, cwd=repository, check=True, stdout=subprocess.PIPE, text=True)
    return sorted(
        {
            canonicalize_name(Requirement(line.strip()).name)
            for line in result.stdout.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        },
    )


def filter_alerts_per_packages(alerts: Sequence[Alert], packages: Sequence[str]) -> list[Alert]:
    """Keep alerts whose package names occur in the exported dependency list."""
    names = set(packages)
    python_names = {canonicalize_name(name) for name in packages}
    return [
        alert
        for alert in alerts
        if (
            canonicalize_name(alert["securityVulnerability"]["package"]["name"]) in python_names
            if alert["securityVulnerability"]["package"]["ecosystem"] == "PIP"
            else alert["securityVulnerability"]["package"]["name"] in names
        )
    ]


def _markdown_text(value: str) -> str:
    text = html.escape(" ".join(value.split()), quote=False)
    return re.sub(r"([\\`*_\[\]{}|])", r"\\\1", text)


def add_alerts_to_release_notes(
    alerts: Sequence[Alert],
    release_notes: Path,
    *,
    owner: str,
    name: str,
) -> None:
    """Insert a security section immediately after the internal-information marker.

    Existing alert links are skipped to make reruns safe. An existing release-note
    file is required, including when there are no matching alerts. Missing markers
    raise an error when new alerts need to be inserted.
    """
    with release_notes.open(encoding="utf-8", newline="") as notes:
        content = notes.read()
    rows: list[str] = []
    seen: set[int] = set()
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
    for alert in sorted(alerts, key=lambda item: severity_order[item["securityVulnerability"]["severity"]]):
        number = alert["number"]
        url = f"https://github.com/{owner}/{name}/security/dependabot/{number}"
        if number in seen or f"]({url})" in content:
            continue
        seen.add(number)
        fixed_at = alert["fixedAt"]
        if fixed_at is None:
            raise ValueError(f"Fixed alert {number} has no resolution timestamp.")
        parse_date(fixed_at)
        vulnerability = alert["securityVulnerability"]
        package = vulnerability["package"]
        severity = vulnerability["severity"]
        severity_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "⚪"}[severity]
        rows.append(
            f"* {severity_icon} **{severity.capitalize()}** - "
            f"Upgraded **{_markdown_text(package['name'])}**<br>"
            f"{_markdown_text(vulnerability['advisory']['summary'])}<br>"
            f"_Closure reason:_ Fixed ([#{number}]({url}))<br><br>",
        )
    if rows:
        marker = re.search(rf"^{re.escape(INTERNAL_NOTES_MARKER)}(?:\r?\n|$)", content, re.MULTILINE)
        if marker is None:
            raise ValueError(f"Release notes are missing the internal-information marker: {INTERNAL_NOTES_MARKER}")
        newline = "\r\n" if "\r\n" in content else "\n"
        position = marker.end()
        separator = newline if content[:position].endswith("\n") else newline * 2
        section = newline.join(["## 🛡️ Security fixes", "", *rows, "", ""])
        with release_notes.open("w", encoding="utf-8", newline="") as notes:
            notes.write(content[:position] + separator + section + content[position:])


def main() -> None:
    """Run the fixed-alert release-note pipeline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--last-release-date", required=True, type=parse_date)
    parser.add_argument("--manifest-file", action="append", required=True, dest="manifest_files")
    parser.add_argument(
        "--member",
        action="append",
        required=True,
        dest="members",
        choices=sorted(MEMBER_PER_LIBRARY_DIRECTORY),
        help="Directory name under packages (repeat for multiple directories).",
    )
    parser.add_argument("--release-notes", required=True, type=Path)
    parser.add_argument("--repository", type=Path, default=Path())
    parser.add_argument("--owner", default="ansys")
    parser.add_argument("--name", default="saf")
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("Set GH_TOKEN or GITHUB_TOKEN to a token with Dependabot alerts read access.")
    packages = get_packages_from_members(args.members, args.repository)
    alerts = get_closed_alerts_since_for_manifest_file(
        args.last_release_date,
        args.manifest_files,
        owner=args.owner,
        name=args.name,
        token=token,
    )
    filtered = filter_alerts_per_packages(alerts, packages)
    add_alerts_to_release_notes(filtered, args.release_notes, owner=args.owner, name=args.name)
    print(f"Processed {len(filtered)} matching fixed alerts for {args.release_notes}.")


if __name__ == "__main__":
    main()
