# /// script
# requires-python = ">=3.11"
# dependencies = ["packaging>=23.0", "requests>=2.32"]
# ///
"""Export Dependabot alerts of a repository to a Markdown report.

The script queries the GitHub GraphQL API (``repository.vulnerabilityAlerts``),
optionally filters alerts by package name and/or manifest file, and writes a
Markdown table with the severity, manifest file, package name and patched
version. It also reports potential dependency paths from local uv and Poetry
lock files when those manifests are available. The paths combine runtime,
optional-extra and development dependencies; they do not prove that a
component is installed for a particular product configuration. Omit either
filter to include all packages or manifests, respectively; omit both to include
all alerts.

Requirements:
  - Set the GITHUB_TOKEN environment variable with a token that can read
    Dependabot alerts ('repo' / 'security_events' scope).

Usage:
    uv run retrieve_dependabot_alerts.py --repository owner/repo --package requests
    uv run retrieve_dependabot_alerts.py --repository owner/repo --manifest uv.lock
    uv run retrieve_dependabot_alerts.py --repository owner/repo
    uv run retrieve_dependabot_alerts.py --repository owner/repo --package requests \
        --manifest backend/requirements.txt --state OPEN FIXED --output alerts.md
"""

import argparse
from collections import deque
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tomllib
from typing import Any, Dict, List, Optional

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
import requests

GRAPHQL_URL = "https://api.github.com/graphql"

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}

ALERTS_QUERY = """
query($owner: String!, $name: String!, $states: [RepositoryVulnerabilityAlertState!], $cursor: String) {
  repository(owner: $owner, name: $name) {
    vulnerabilityAlerts(first: 100, states: $states, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        state
        createdAt
        vulnerableManifestPath
        vulnerableRequirements
        securityVulnerability {
          severity
          vulnerableVersionRange
          firstPatchedVersion { identifier }
          package { name ecosystem }
          advisory { ghsaId summary permalink }
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_github_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is not set.")
    return token


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def _md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _normalize_path(path: str) -> str:
    path = path.replace("\\", "/")
    while path.startswith(("./", "/")):
        path = path[2:] if path.startswith("./") else path[1:]
    return path


def _describe_filters(package: Optional[str], manifest: Optional[str]) -> str:
    parts = []
    if package:
        parts.append(f"package `{package}`")
    if manifest:
        parts.append(f"manifest `{manifest}`")
    return ", ".join(parts) or "all packages, all manifests"


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def _list_alerts(repo: str, states: List[str], headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Return every Dependabot alert of a repository for the given states."""
    owner, name = repo.split("/", 1)
    alerts: List[Dict[str, Any]] = []
    cursor = None
    while True:
        resp = requests.post(
            GRAPHQL_URL,
            json={
                "query": ALERTS_QUERY,
                "variables": {
                    "owner": owner,
                    "name": name,
                    "states": states,
                    "cursor": cursor,
                },
            },
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            raise RuntimeError(f"GraphQL errors: {payload['errors']}")

        repository = payload["data"]["repository"]
        if repository is None:
            raise RuntimeError(f"Repository '{repo}' not found or not accessible.")

        connection = repository["vulnerabilityAlerts"]
        alerts.extend(connection["nodes"])
        if not connection["pageInfo"]["hasNextPage"]:
            break
        cursor = connection["pageInfo"]["endCursor"]
    return alerts


def _filter_alerts(
    alerts: List[Dict[str, Any]], package: Optional[str], manifest: Optional[str]
) -> List[Dict[str, Any]]:
    if package:
        wanted = package.lower()
        alerts = [a for a in alerts if a["securityVulnerability"]["package"]["name"].lower() == wanted]
    if manifest:
        wanted_path = _normalize_path(manifest)
        alerts = [a for a in alerts if _normalize_path(a["vulnerableManifestPath"]) == wanted_path]
    return alerts


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _overall_suggested_patches(
    alerts: List[Dict[str, Any]],
) -> List[tuple[str, str, str]]:
    """Return each ecosystem/package with its highest PEP 440 patched version."""
    versions_by_package: Dict[tuple[str, str], set[str]] = {}
    for alert in alerts:
        vuln = alert["securityVulnerability"]
        patched = (vuln.get("firstPatchedVersion") or {}).get("identifier")
        if not patched:
            continue
        package = vuln["package"]
        key = (package["ecosystem"], package["name"])
        versions_by_package.setdefault(key, set()).add(patched)

    suggestions = []
    for (ecosystem, package), versions in versions_by_package.items():
        try:
            patched = max(versions, key=Version)
        except InvalidVersion as exc:
            raise ValueError(f"Cannot compare patched versions for {ecosystem} package {package!r}.") from exc
        suggestions.append((ecosystem, package, patched))
    return sorted(suggestions, key=lambda item: (item[0], item[1].lower()))


def _read_toml(path: Path) -> Dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in {path}.") from exc


def _uv_dependency_names(value: Any) -> set[str]:
    if isinstance(value, list):
        return set().union(*(_uv_dependency_names(item) for item in value))
    if isinstance(value, dict):
        if isinstance(value.get("name"), str):
            return {canonicalize_name(value["name"])}
        return set().union(*(_uv_dependency_names(item) for item in value.values()))
    return set()


def _uv_dependency_graph(lock: Dict[str, Any]) -> Dict[str, set[str]]:
    graph: Dict[str, set[str]] = {}
    for package in lock.get("package", []):
        name = canonicalize_name(package["name"])
        dependencies: set[str] = set()
        for section in ("dependencies", "dev-dependencies", "optional-dependencies"):
            dependencies.update(_uv_dependency_names(package.get(section, [])))
        graph.setdefault(name, set()).update(dependencies)
    return graph


def _poetry_dependency_graph(lock: Dict[str, Any]) -> Dict[str, set[str]]:
    graph: Dict[str, set[str]] = {}
    for package in lock.get("package", []):
        name = canonicalize_name(package["name"])
        dependencies = package.get("dependencies", {})
        graph.setdefault(name, set()).update(
            canonicalize_name(dependency) for dependency in dependencies if dependency.lower() != "python"
        )
    return graph


def _project_dependencies(project: Dict[str, Any], pyproject_path: Path) -> tuple[str, set[str]]:
    metadata = project.get("project", {})
    poetry = project.get("tool", {}).get("poetry", {})
    root_name = metadata.get("name") or poetry.get("name") or pyproject_path.parent.name
    dependencies: set[str] = set()

    for requirement in metadata.get("dependencies", []):
        dependencies.add(canonicalize_name(Requirement(requirement).name))
    for group in metadata.get("optional-dependencies", {}).values():
        for requirement in group:
            dependencies.add(canonicalize_name(Requirement(requirement).name))

    def add_poetry_dependencies(declarations: Any) -> None:
        if isinstance(declarations, dict):
            dependencies.update(canonicalize_name(name) for name in declarations if name.lower() != "python")

    add_poetry_dependencies(poetry.get("dependencies", {}))
    add_poetry_dependencies(poetry.get("dev-dependencies", {}))
    for group in poetry.get("group", {}).values():
        add_poetry_dependencies(group.get("dependencies", {}))

    return canonicalize_name(root_name), dependencies


def _find_dependency_paths(graph: Dict[str, set[str]], start: str, target: str) -> List[List[str]]:
    if start == target:
        return [[start]]

    reverse_graph: Dict[str, set[str]] = {}
    for package, dependencies in graph.items():
        for dependency in dependencies:
            reverse_graph.setdefault(dependency, set()).add(package)

    can_reach_target = {target}
    pending = deque([target])
    while pending:
        for parent in reverse_graph.get(pending.popleft(), set()):
            if parent not in can_reach_target:
                can_reach_target.add(parent)
                pending.append(parent)
    if start not in can_reach_target:
        return []

    paths = []
    pending_paths = [(start, [start])]
    while pending_paths:
        current, path = pending_paths.pop()
        for dependency in sorted(graph.get(current, set()), reverse=True):
            if dependency not in can_reach_target or dependency in path:
                continue
            next_path = [*path, dependency]
            if dependency == target:
                paths.append(next_path)
            else:
                pending_paths.append((dependency, next_path))
    return sorted(paths)


def _relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _dependency_trace(
    root: Path,
    lock_file: Path,
    manifest_file: Optional[Path],
    workspace_member: Optional[str],
    paths: Optional[List[List[str]]],
    status: Optional[str] = None,
) -> Dict[str, Any]:
    trace = {
        "lock_file": _relative_path(lock_file, root),
        "manifest_file": _relative_path(manifest_file, root) if manifest_file else None,
        "workspace_member": workspace_member,
        "dependency_paths": paths or [],
    }
    if status:
        trace["status"] = status
    return trace


def _trace_uv_lock(root: Path, lock_file: Path, package_name: str) -> List[Dict[str, Any]]:
    lock = _read_toml(lock_file)
    packages = lock.get("package", [])
    graph = _uv_dependency_graph(lock)
    target = canonicalize_name(package_name)

    if lock_file.resolve() == (root / "uv.lock").resolve():
        member_names = lock.get("manifest", {}).get("members", [])
        traces = []
        for member_name in member_names:
            member = canonicalize_name(member_name)
            package = next(
                (
                    item
                    for item in packages
                    if canonicalize_name(item["name"]) == member and item.get("source", {}).get("editable")
                ),
                None,
            )
            if package is None:
                continue
            editable_path = root / package["source"]["editable"]
            manifest_file = editable_path / "pyproject.toml"
            paths = _find_dependency_paths(graph, member, target)
            if paths:
                traces.append(_dependency_trace(root, lock_file, manifest_file, package["name"], paths))
        if traces:
            return traces
        return [
            _dependency_trace(
                root, lock_file, root / "pyproject.toml", None, None, "no workspace member reaches package"
            )
        ]

    project_manifest = lock_file.parent / "pyproject.toml"
    root_package = next(
        (
            package
            for package in packages
            if package.get("source", {}).get("editable")
            and (lock_file.parent / package["source"]["editable"]).resolve() == lock_file.parent.resolve()
        ),
        None,
    )
    if root_package:
        root_name = canonicalize_name(root_package["name"])
    elif project_manifest.is_file():
        root_name, direct_dependencies = _project_dependencies(_read_toml(project_manifest), project_manifest)
        graph.setdefault(root_name, set()).update(direct_dependencies)
    else:
        return [_dependency_trace(root, lock_file, project_manifest, None, None, "project manifest not found")]

    paths = _find_dependency_paths(graph, root_name, target)
    status = None if paths else "no dependency path found"
    return [_dependency_trace(root, lock_file, project_manifest, None, paths, status)]


def _trace_poetry_lock(root: Path, lock_file: Path, package_name: str) -> List[Dict[str, Any]]:
    project_manifest = lock_file.parent / "pyproject.toml"
    if not project_manifest.is_file():
        return [_dependency_trace(root, lock_file, project_manifest, None, None, "project manifest not found")]

    project = _read_toml(project_manifest)
    root_name, direct_dependencies = _project_dependencies(project, project_manifest)
    graph = _poetry_dependency_graph(_read_toml(lock_file))
    graph.setdefault(root_name, set()).update(direct_dependencies)
    paths = _find_dependency_paths(graph, root_name, canonicalize_name(package_name))
    status = None if paths else "no dependency path found"
    return [_dependency_trace(root, lock_file, project_manifest, None, paths, status)]


_COOKIECUTTER_LOCK_DIRECTORY = (
    "packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/lock_files"
)


def _trace_alert_manifest(root: Path, manifest_path: str, package_name: str) -> List[Dict[str, Any]]:
    relative = Path(_normalize_path(manifest_path))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Manifest path must be relative to the repository: {manifest_path}")
    lock_file = (root / relative).resolve()
    if not lock_file.is_relative_to(root.resolve()):
        raise ValueError(f"Manifest path escapes the repository: {manifest_path}")
    normalized = lock_file.relative_to(root.resolve()).as_posix()
    if normalized.startswith(f"{_COOKIECUTTER_LOCK_DIRECTORY}/"):
        return [_dependency_trace(root, lock_file, None, None, None, "cookiecutter template lock file excluded")]
    if not lock_file.is_file():
        return [_dependency_trace(root, lock_file, None, None, None, "lock file not found")]
    if lock_file.name == "uv.lock":
        return _trace_uv_lock(root, lock_file, package_name)
    if lock_file.name == "poetry.lock":
        return _trace_poetry_lock(root, lock_file, package_name)
    return [_dependency_trace(root, lock_file, None, None, None, "unsupported lock file")]


def _package_records(alerts: List[Dict[str, Any]], root: Path) -> List[Dict[str, Any]]:
    versions = {
        (ecosystem, canonicalize_name(package)): version
        for ecosystem, package, version in _overall_suggested_patches(alerts)
    }
    grouped: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    for alert in alerts:
        package = alert["securityVulnerability"]["package"]
        key = (package["ecosystem"], canonicalize_name(package["name"]))
        grouped.setdefault(key, []).append(alert)

    records = []
    for (ecosystem, package_key), package_alerts in sorted(grouped.items()):
        package = package_alerts[0]["securityVulnerability"]["package"]["name"]
        manifest_traces = []
        seen_manifests = set()
        for alert in package_alerts:
            manifest = alert.get("vulnerableManifestPath")
            if manifest and manifest not in seen_manifests:
                seen_manifests.add(manifest)
                manifest_traces.extend(_trace_alert_manifest(root, manifest, package))
        records.append(
            {
                "ecosystem": ecosystem,
                "package": package,
                "suggested_patch_version": versions.get((ecosystem, package_key)),
                "manifest_traces": manifest_traces,
            }
        )
    return records


def _append_dependency_tree(lines: List[str], paths: List[List[str]]) -> None:
    tree: Dict[str, Any] = {}
    for path in paths:
        branch = tree
        for package in path:
            branch = branch.setdefault(package, {})

    def append_branch(branch: Dict[str, Any], indentation: str) -> None:
        for package, children in sorted(branch.items()):
            lines.append(f"{indentation}- `{_md_escape(package)}`")
            append_branch(children, indentation + "  ")

    append_branch(tree, "      ")


def _render_markdown(
    repo: str,
    filters: str,
    states: List[str],
    alerts: List[Dict[str, Any]],
    dependency_records: Optional[List[Dict[str, Any]]] = None,
) -> str:
    alerts = sorted(
        alerts,
        key=lambda a: (
            SEVERITY_ORDER.get(a["securityVulnerability"]["severity"], 99),
            a["vulnerableManifestPath"],
        ),
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Dependabot alerts - `{repo}` - {filters}",
        "",
        f"- Generated: {generated}",
        f"- States: {', '.join(states)}",
        f"- Alerts: {len(alerts)}",
        "",
    ]
    related_issues_section = ["", "## Related Issues", ""]
    related_issues_section.extend(
        f"- Related Issue https://github.com/{repo}/security/dependabot/{alert['number']}" for alert in alerts
    )
    if not alerts:
        lines.append("No Dependabot alerts found.")
        related_issues_section.append("No related alerts.")
        lines.extend(related_issues_section)
        return "\n".join(lines) + "\n"

    patch_counts: Dict[tuple[str, str, str], int] = {}
    unpatched_count = 0
    for alert in alerts:
        vuln = alert["securityVulnerability"]
        patched = (vuln.get("firstPatchedVersion") or {}).get("identifier")
        if not patched:
            unpatched_count += 1
            continue
        ecosystem = vuln["package"]["ecosystem"]
        package = vuln["package"]["name"]
        key = (ecosystem, package, patched)
        patch_counts[key] = patch_counts.get(key, 0) + 1

    lines += ["### Patch summary", ""]
    if patch_counts:
        lines += [
            "| Ecosystem | Package | Suggested patched version | Alerts it would fix |",
            "|-----------|---------|---------------------------|--------------------|",
        ]
        for ecosystem, package, patched in sorted(patch_counts, key=lambda item: (item[0], item[1].lower(), item[2])):
            lines.append(
                f"| {ecosystem} | `{_md_escape(package)}` | "
                f"`{_md_escape(patched)}` | {patch_counts[(ecosystem, package, patched)]} |"
            )
    else:
        lines.append("No patched versions are available for these alerts.")
    if unpatched_count:
        lines += ["", f"Alerts without a known patched version: {unpatched_count}."]
    lines.append("")

    if dependency_records:
        package_label = "package" if len(dependency_records) == 1 else "packages"
        lines += [
            "### Potential dependency traces",
            "",
            "These paths are candidate relationships from lock metadata. The graph "
            "combines runtime, optional-extra and development dependencies without "
            "resolving which extras, groups or environment markers are selected. "
            "A listed path does not prove that the component is installed in a "
            "specific product or runtime configuration; verify the relevant "
            "manifest, extras and environment.",
            "",
            "<details>",
            f"<summary>Show dependency traces for {len(dependency_records)} {package_label}</summary>",
            "",
        ]
        for record in dependency_records:
            lines.append(f"- **{_md_escape(record['package'])}** ({record['ecosystem']})")
            for trace in record["manifest_traces"]:
                lines.append(f"  - Lock file: `{trace['lock_file']}`")
                if trace["workspace_member"]:
                    lines.append(f"    - Workspace member: `{trace['workspace_member']}`")
                if trace["manifest_file"]:
                    lines.append(f"    - Project manifest: `{trace['manifest_file']}`")
                if trace["dependency_paths"]:
                    lines.append("    - Potential dependency tree:")
                    _append_dependency_tree(lines, trace["dependency_paths"])
                elif trace.get("status"):
                    lines.append(f"    - Trace unavailable: {trace['status']}")
        lines += ["", "</details>", ""]

    lines += [
        "### All Dependabot alerts",
        "",
        "| # | Severity | Package | Ecosystem | Manifest | Vulnerable range | Patched version |",
        "|---|----------|---------|-----------|----------|------------------|-----------------|",
    ]
    for a in alerts:
        vuln = a["securityVulnerability"]
        patched = (vuln.get("firstPatchedVersion") or {}).get("identifier") or "No patch"
        alert_url = f"https://github.com/{repo}/security/dependabot/{a['number']}"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"[{a['number']}]({alert_url})",
                    vuln["severity"].capitalize(),
                    vuln["package"]["name"],
                    vuln["package"]["ecosystem"],
                    f"`{a['vulnerableManifestPath']}`",
                    f"`{_md_escape(vuln['vulnerableVersionRange'])}`",
                    patched,
                ]
            )
            + " |"
        )
    lines.extend(related_issues_section)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repository",
        default="ansys/saf",
        help="Repository in OWNER/REPOSITORY format (default: ansys/saf).",
    )
    parser.add_argument(
        "--package",
        help="Package name to filter alerts on (case-insensitive); omit to include all packages.",
    )
    parser.add_argument(
        "--manifest",
        help="Manifest file path to filter alerts on, relative to the repo root "
        "(e.g. backend/requirements.txt); omit to include all manifests.",
    )
    parser.add_argument(
        "--state",
        nargs="+",
        default=["OPEN"],
        choices=["OPEN", "FIXED", "DISMISSED", "AUTO_DISMISSED"],
        help="Alert states to include (default: OPEN).",
    )
    parser.add_argument(
        "--output",
        help=(
            "Output Markdown file (default: dist/dependabot_alerts_<repo>_<filters>.md; "
            "uses 'all' when no filters are given)."
        ),
    )
    return parser.parse_args()


def main() -> List[tuple[str, str, str]]:
    args = parse_args()

    if "/" not in args.repository:
        print("[ERROR] --repository must be in OWNER/REPOSITORY format.", file=sys.stderr)
        sys.exit(1)

    try:
        token = _get_github_token()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        alerts = _list_alerts(args.repository, args.state, _headers(token))
    except Exception as exc:  # noqa: BLE001
        print(f"[FAILED] {exc}", file=sys.stderr)
        sys.exit(1)

    matching = _filter_alerts(alerts, args.package, args.manifest)
    dependency_records = _package_records(matching, Path.cwd())
    suggested_patches = _overall_suggested_patches(matching)
    filters = _describe_filters(args.package, args.manifest)
    if args.output:
        output = args.output
    else:
        suffix = "_".join(f for f in (args.package, args.manifest) if f) or "all"
        for char in "/\\@:":
            suffix = suffix.replace(char, "_")
        dist_dir = Path("dist")
        dist_dir.mkdir(exist_ok=True)
        output = dist_dir / f"dependabot_alerts_{args.repository.replace('/', '_')}_{suffix}.md"
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(_render_markdown(args.repository, filters, args.state, matching, dependency_records))

    print(f"Exported {len(matching)} alert(s) for {filters} to {output}")
    return suggested_patches


if __name__ == "__main__":
    main()
