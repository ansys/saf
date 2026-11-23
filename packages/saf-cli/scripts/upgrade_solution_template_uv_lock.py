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
# dependencies = [
#     "ansys-saf-cli",
#     "packaging>=24.2",
#     "python-dotenv>=1.0.0,<2",
#     "tomlkit>=0.14.0,<1.0.0",
# ]
#
# [tool.uv.sources]
# ansys-saf-cli = { path = "..", editable = true }
# ///

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import html
import json
import operator
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import cast

from dotenv import dotenv_values
from packaging.requirements import Requirement
from packaging.version import Version
import tomlkit

from ansys.saf.cli._config.const import SOLUTION_TEMPLATE_PATH, UI_FRAMEWORKS

CLI_DIR = Path(__file__).resolve().parent.parent
REPOSITORY_DIR = CLI_DIR.parent.parent
TEMPLATE_DIR = CLI_DIR / "src" / "ansys" / "saf" / "cli" / "_solutions" / "templates" / "solution"
LOCK_DIR = TEMPLATE_DIR / "{{cookiecutter.__solution_name}}" / "lock_files"
VARIANTS = {"dash": "dash", "awc-dash": "awc", "none": "no_ui"}
LOCK_NAME = "uv.lock"
PKG_NAME_PLACEHOLDER = "{{ cookiecutter.__pkg_name }}"
VERSION_PLACEHOLDER = "{{ cookiecutter.__version }}"
OPERATORS: dict[str, Callable[[Version, Version], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
}


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def object_fields(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("Expected a JSON object with string keys.")
    return cast("dict[str, object]", value)


def string_field(fields: dict[str, object], key: str) -> str:
    value = fields.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Expected a nonempty string for {key}.")
    return value


@dataclass(frozen=True)
class Alert:
    number: int
    url: str
    manifest: str
    package: str
    advisory: str
    severity: str
    affected: str
    patched: str | None


def fetch_alerts(repository: str) -> list[Alert]:
    gh = shutil.which("gh")
    if gh is None:
        raise RuntimeError("GitHub CLI is missing. Install gh and authenticate with gh auth login.")
    result = subprocess.run(
        [
            gh,
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repository}/dependabot/alerts?state=open&ecosystem=pip&per_page=100",
        ],
        cwd=REPOSITORY_DIR,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    pages = json.loads(result.stdout)
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise ValueError("Unexpected paginated Dependabot response.")
    prefix = LOCK_DIR.relative_to(REPOSITORY_DIR).as_posix() + "/"
    alerts: list[Alert] = []
    for page in pages:
        for item in page:
            fields = object_fields(item)
            dependency = object_fields(fields.get("dependency"))
            package = object_fields(dependency.get("package"))
            manifest = string_field(dependency, "manifest_path")
            if (
                fields.get("state") != "open"
                or package.get("ecosystem") != "pip"
                or not manifest.startswith(prefix)
                or not manifest.endswith(f"/{LOCK_NAME}")
            ):
                continue
            advisory = object_fields(fields.get("security_advisory"))
            vulnerability = object_fields(fields.get("security_vulnerability"))
            patched = vulnerability.get("first_patched_version")
            number = fields.get("number")
            if not isinstance(number, int) or isinstance(number, bool):
                raise ValueError("Expected an integer alert number.")
            alerts.append(
                Alert(
                    number=number,
                    url=string_field(fields, "html_url"),
                    manifest=manifest,
                    package=normalize_name(string_field(package, "name")),
                    advisory=string_field(advisory, "ghsa_id"),
                    severity=string_field(advisory, "severity"),
                    affected=string_field(vulnerability, "vulnerable_version_range"),
                    patched=string_field(object_fields(patched), "identifier") if patched is not None else None,
                )
            )
    return alerts


def locked_versions(lockfile: Path) -> dict[str, list[str]]:
    with lockfile.open("rb") as stream:
        lock = tomllib.load(stream)
    versions: dict[str, list[str]] = {}
    for package in lock["package"]:
        if "version" in package:
            versions.setdefault(normalize_name(package["name"]), []).append(package["version"])
    return versions


def parse_affected_range(affected: str) -> list[list[tuple[Callable[[Version, Version], bool], Version]]]:
    """Parse a Dependabot vulnerable range such as ``>= 1.0, < 2.0 || >= 3.0, < 3.2``.

    Comparisons are made directly on versions rather than through PEP 440 specifiers, which would not treat
    pre-releases of the upper bound (for example ``2.0rc1`` for ``< 2.0``) as affected.
    """
    alternatives: list[list[tuple[Callable[[Version, Version], bool], Version]]] = []
    for alternative in affected.split("||"):
        clauses: list[tuple[Callable[[Version, Version], bool], Version]] = []
        for clause in alternative.split(","):
            match = re.fullmatch(r"\s*(>=|<=|==|!=|=|>|<)\s*(\S+)\s*", clause)
            if match is None:
                raise ValueError(f"Unsupported vulnerable version range: {affected!r}")
            clauses.append((OPERATORS["==" if match[1] == "=" else match[1]], Version(match[2])))
        alternatives.append(clauses)
    return alternatives


def is_affected(alert: Alert, versions: list[str]) -> bool:
    alternatives = parse_affected_range(alert.affected)
    return any(
        all(compare(Version(version), bound) for compare, bound in clauses)
        for version in versions
        for clauses in alternatives
    )


def direct_dependencies(manifest: Path) -> set[str]:
    with manifest.open("rb") as stream:
        pyproject = tomllib.load(stream)
    project = pyproject.get("project", {})
    requirements: list[str] = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        requirements.extend(extra)
    for group in pyproject.get("dependency-groups", {}).values():
        # Entries can also be {include-group = "..."} tables, which only reference other groups.
        requirements.extend(entry for entry in group if isinstance(entry, str))
    return {normalize_name(Requirement(requirement).name) for requirement in requirements}


def to_template_lock(lockfile: Path) -> str:
    """Return the lockfile content with the solution's own package name and version templated."""
    lock = tomlkit.parse(lockfile.read_text(encoding="utf-8"))
    solution_packages = [package for package in lock["package"] if package.get("source") == {"editable": "."}]  # pyright: ignore[reportAttributeAccessIssue, reportGeneralTypeIssues]
    if len(solution_packages) != 1:
        raise RuntimeError(f"Expected exactly one editable solution package in {lockfile}.")
    solution_packages[0]["name"] = PKG_NAME_PLACEHOLDER
    solution_packages[0]["version"] = VERSION_PLACEHOLDER
    return tomlkit.dumps(lock)


def generate_solution(directory: Path, framework: str) -> Path:
    name = f"solution-{framework}"
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from ansys.saf.cli._cli.main import entry_point; entry_point()",
            "new",
            "--solution-name",
            name,
            "--solution-display-name",
            "temp",
            "--ui-framework",
            framework,
            "--namespace",
            "my_temp",
        ],
        cwd=directory,
        check=True,
    )
    solution = directory / name
    # The generated solution starts from the template lockfile, copied by the post-generation hook.
    if not (solution / LOCK_NAME).is_file():
        raise RuntimeError(f"Generated solution {name} has no {LOCK_NAME}.")
    return solution


def solution_environment(solution: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key, value in dotenv_values(solution / ".env").items():
        if value is not None:
            env.setdefault(key, value)
    return env


def run_uv(solution: Path, *arguments: str) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is missing. Install uv from https://docs.astral.sh/uv/.")
    print(f"{solution.name}: uv {' '.join(arguments)}", flush=True)
    subprocess.run(
        [uv, *arguments],
        cwd=solution,
        env=solution_environment(solution),
        check=True,
    )


def plan_updates(
    alerts: list[Alert],
    solutions: dict[str, Path],
) -> tuple[dict[str, set[str]], dict[int, str]]:
    updates: dict[str, set[str]] = {}
    statuses: dict[int, str] = {}
    for alert in alerts:
        manifest = Path(alert.manifest)
        variant = manifest.parent.name
        expected = LOCK_DIR / variant / LOCK_NAME
        if alert.manifest != expected.relative_to(REPOSITORY_DIR).as_posix() or variant not in solutions:
            statuses[alert.number] = "BLOCKED: unsupported lockfile variant"
            continue
        before = locked_versions(expected).get(alert.package, [])
        if not is_affected(alert, before):
            statuses[alert.number] = "ALREADY SAFE: no affected locked versions"
        elif alert.package in direct_dependencies(solutions[variant] / "pyproject.toml"):
            statuses[alert.number] = "BLOCKED: direct dependency requires developer approval"
        elif alert.patched is None:
            statuses[alert.number] = "BLOCKED: advisory has no patched version"
        else:
            statuses[alert.number] = "PLANNED"
            updates.setdefault(variant, set()).add(alert.package)
    return updates, statuses


def report_alerts(
    alerts: list[Alert],
    statuses: dict[int, str],
    staged: dict[str, Path],
    *,
    dry_run: bool = False,
) -> None:
    lines = [
        "# Solution-template Dependabot report",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        f"Mode: {'Dry run (no lockfiles changed)' if dry_run else 'Update verification'}",
        "",
    ]
    if not alerts:
        lines.extend(["No matching open Dependabot alerts in the solution-template lockfiles.", ""])
    if any(status.startswith("FAILED:") for status in statuses.values()):
        lines.extend(["No lockfiles copied: uv resolution or validation failed.", ""])
    elif any(status.startswith("UNRESOLVED") for status in statuses.values()):
        lines.extend(["No staged lockfiles will be copied: targeted alerts remain vulnerable.", ""])
    elif staged:
        lines.extend(["Validated staged lockfiles are ready to copy; review the command result for copy errors.", ""])
    for alert in alerts:
        variant = Path(alert.manifest).parent.name
        source = REPOSITORY_DIR / alert.manifest
        before = locked_versions(source).get(alert.package, []) if source.is_file() else []
        after = locked_versions(staged[variant]).get(alert.package, []) if variant in staged else before
        lines.extend(
            [
                f"## Alert {alert.number}: {html.escape(alert.advisory)}",
                "",
                f"- Alert: <{alert.url}>",
                f"- Severity: {html.escape(alert.severity)}",
                f"- Lockfile: <code>{html.escape(alert.manifest)}</code>",
                f"- Package: <code>{html.escape(alert.package)}</code>",
                f"- Before: {html.escape(', '.join(before) or 'absent')}",
                f"- After (staged): {html.escape(', '.join(after) or 'absent')}",
                f"- Affected range: <code>{html.escape(alert.affected)}</code>",
                f"- First patched version: {html.escape(alert.patched or 'none')}",
                f"- Status: {html.escape(statuses[alert.number])}",
                "",
            ]
        )
    destination = REPOSITORY_DIR / "dist" / "solution-template-dependabot-report.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    print(f"Dependabot report saved to {destination}")


def verify_alerts(alerts: list[Alert], statuses: dict[int, str], staged: dict[str, Path]) -> bool:
    for alert in alerts:
        status = statuses[alert.number]
        if status in {"PLANNED", "ALREADY SAFE"} or status.startswith("ALREADY SAFE:"):
            variant = Path(alert.manifest).parent.name
            lockfile = staged.get(variant, REPOSITORY_DIR / alert.manifest)
            after = locked_versions(lockfile).get(alert.package, [])
            if is_affected(alert, after):
                statuses[alert.number] = "UNRESOLVED: staged lockfile is affected; inspect update constraints"
            elif status == "PLANNED":
                statuses[alert.number] = "REMEDIATED in proposed lockfile"
    return not any(status.startswith("UNRESOLVED") for status in statuses.values())


def stage_lockfiles(solutions: dict[str, Path], updates: dict[str, set[str]]) -> dict[str, Path]:
    staged: dict[str, Path] = {}
    for variant, selected in updates.items():
        solution = solutions[variant]
        run_uv(solution, "lock")
        if selected:
            run_uv(solution, "lock", *(arg for package in sorted(selected) for arg in ("--upgrade-package", package)))
        run_uv(solution, "lock", "--check")
        staged[variant] = solution / LOCK_NAME
    return staged


def update_lockfiles(packages: list[str], dependabot: bool, repository: str, dry_run: bool) -> int:  # noqa: C901
    if SOLUTION_TEMPLATE_PATH.resolve() != TEMPLATE_DIR.resolve():
        raise RuntimeError("CLI templates are not from this checkout. Run with uv and the editable local CLI.")
    alerts = fetch_alerts(repository) if dependabot else []
    if dependabot:
        if packages:
            alerts = [alert for alert in alerts if alert.package in {normalize_name(name) for name in packages}]
        if not alerts:
            report_alerts([], {}, {}, dry_run=dry_run)
            return 0

    with tempfile.TemporaryDirectory(prefix="saf-lock-update-") as temporary:
        directory = Path(temporary)
        solutions = {VARIANTS[framework]: generate_solution(directory, framework) for framework in UI_FRAMEWORKS}
        statuses: dict[int, str] = {}
        if dependabot:
            updates, statuses = plan_updates(alerts, solutions)
        else:
            updates = {variant: set(packages) for variant in solutions}
        if dry_run:
            report_alerts(alerts, statuses, {}, dry_run=True)
            print("\nDry run: no uv updates or lockfile writes performed.")
            return int(any(status.startswith("BLOCKED") for status in statuses.values()))

        try:
            staged = stage_lockfiles(solutions, updates)
        except subprocess.CalledProcessError as error:
            if dependabot:
                failure_status = f"FAILED: uv command exited with code {error.returncode}"
                statuses = {
                    number: failure_status if status == "PLANNED" else status for number, status in statuses.items()
                }
                report_alerts(alerts, statuses, {})
            raise
        verified = verify_alerts(alerts, statuses, staged)
        if dependabot:
            report_alerts(alerts, statuses, staged)
        if not verified:
            print("\nNo lockfiles copied: targeted alerts remain vulnerable.")
            return 1
        # Render every template first so that an invalid lockfile does not leave a partial update behind.
        rendered = {variant: to_template_lock(staged_lock) for variant, staged_lock in staged.items()}
        for variant, content in rendered.items():
            destination = LOCK_DIR / variant / LOCK_NAME
            print(f"Copying validated lockfile to {destination}")
            destination.write_text(content, encoding="utf-8", newline="\n")
        return int(any(status.startswith("BLOCKED") for status in statuses.values()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upgrade uv.lock files for solution templates",
    )
    parser.add_argument(
        "-p",
        "--packages",
        type=str,
        default="",
        help=(
            "Comma-separated list of packages to explicitly update (e.g., 'package1,package2'). "
            "Use it for packages that weren't modified in the pyproject.toml."
        ),
    )
    parser.add_argument(
        "--dependabot",
        action="store_true",
        help="Fetch open Dependabot alerts and update only affected transitive dependencies.",
    )
    parser.add_argument("--repository", default="ansys/saf", help="GitHub repository for alert retrieval (owner/repo).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --dependabot, report planned updates without changing lockfiles.",
    )
    args = parser.parse_args()
    if args.dry_run and not args.dependabot:
        parser.error("--dry-run requires --dependabot")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repository):
        parser.error("--repository must be owner/repo")
    packages = [pkg.strip() for pkg in args.packages.split(",") if pkg.strip()]
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", package) for package in packages):
        parser.error("--packages must contain comma-separated Python package names")
    try:
        return update_lockfiles(packages, args.dependabot, args.repository, args.dry_run)
    except subprocess.CalledProcessError as error:
        print(f"Command failed (exit {error.returncode}): {error.cmd}", file=sys.stderr)
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"Lockfile update failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
