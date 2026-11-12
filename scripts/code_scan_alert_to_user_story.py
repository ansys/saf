# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32"]
# ///
"""Create Task issues from GitHub code-scanning alerts.

`code_scan_alert_to_user_story.py` fetches open GitHub Code Scanning alerts and
creates one GitHub issue for each alert at or above a configurable security
severity. Each issue is created with the Task issue type and the
`security` label. The alert's security severity is included as its priority
in the issue description and, when available, is also written to the
organization's Priority issue field.

The script creates the repository's `security` label if it does not
already exist. For a single-select Priority field, the script maps Critical to
Urgent, and High/Medium/Low to the correspondingly named options. The default
severity-to-number mapping for a numeric Priority field is Critical=1, High=2,
Medium=3, Low=4.

Accepted `--min-severity` values are `critical`, `high`, `medium`, and `low`.
The threshold is inclusive: for example, `high` includes Critical and High
alerts. Only alerts that provide a recognized security severity are eligible.
Before creating an issue, the script checks open repository issues for the
alert marker or code-scanning alert link. If an open issue already references
that alert, it skips creating another one. Closed issues do not prevent a new
issue from being created.

Use `--priority-field FIELD_NAME` if the organization's issue field has a
different name. If setting the field fails, the script prints a warning and
continues; the severity remains in the issue description.

The alert's security severity determines the issue priority. Issues are created
with the ``security`` label and the repository's ``Task`` issue type.

Requirements:
    - [uv](https://docs.astral.sh/uv/)
    - A `GITHUB_TOKEN` environment variable with permission to read code-scanning
    alerts and create issues in the target repository.
    - The repository must have the **Task** issue type available.
    - The token needs access to organization issue fields to set the optional
    **Priority** field. If the field is unavailable, inaccessible, or cannot
    represent the alert severity, the script warns and still creates the issue.

Usage:
    Set the token in PowerShell:
        $env:GITHUB_TOKEN = "github_pat_..."

    Preview matching alerts without making changes:
        uv run scripts/code_scan_alert_to_user_story.py --repository ansys/saf --min-severity high --dry-run

    Create issues for Critical, High, and Medium alerts (the default threshold):
        uv run scripts/code_scan_alert_to_user_story.py --repository ansys/saf

    Include Low severity alerts as well:
        uv run scripts/code_scan_alert_to_user_story.py --repository ansys/saf --min-severity low
"""

import argparse
import os
import re
import sys
from typing import Any
from urllib.parse import quote

import requests

API_URL = "https://api.github.com"
API_VERSION = "2026-03-10"
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SEVERITY_PRIORITY = {"critical": 1, "high": 2, "medium": 3, "low": 4}
PRIORITY_OPTIONS = {
    "critical": "urgent",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "GraphQL-Features": "issue_types",
    }


def _list_alerts(repository: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    """Fetch all open code-scanning alerts for a repository."""
    owner, name = repository.split("/", 1)
    url: str | None = (
        f"{API_URL}/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
        "/code-scanning/alerts"
    )
    params: dict[str, Any] = {"state": "open", "per_page": 100}
    alerts: list[dict[str, Any]] = []

    while url:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise RuntimeError("GitHub returned an unexpected code-scanning alert response.")
        alerts.extend(page)
        url = response.links.get("next", {}).get("url")
        params = {}

    return alerts


def _find_open_alert_stories(
    repository: str, headers: dict[str, str]
) -> dict[int, str]:
    """Find open issues that already reference a code-scanning alert."""
    owner, name = repository.split("/", 1)
    url: str | None = (
        f"{API_URL}/repos/{quote(owner, safe='')}/{quote(name, safe='')}/issues"
    )
    params: dict[str, Any] = {"state": "open", "per_page": 100}
    marker = re.compile(r"<!--\s*code-scanning-alert:\s*(\d+)\s*-->")
    alert_link = re.compile(
        rf"https://github\.com/{re.escape(repository)}/security/code-scanning/(\d+)",
        re.IGNORECASE,
    )
    existing: dict[int, str] = {}

    while url:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise RuntimeError("GitHub returned an unexpected issues response.")
        for issue in page:
            if "pull_request" in issue:
                continue
            body = issue.get("body") or ""
            match = marker.search(body) or alert_link.search(body)
            if match:
                existing[int(match.group(1))] = issue["html_url"]
        url = response.links.get("next", {}).get("url")
        params = {}

    return existing


def _severity(alert: dict[str, Any]) -> str | None:
    rule = alert.get("rule") or {}
    severity = str(rule.get("security_severity_level") or "").lower()
    if severity == "moderate":
        severity = "medium"
    return severity if severity in SEVERITY_RANK else None


def _filter_alerts(
    alerts: list[dict[str, Any]], minimum_severity: str
) -> tuple[list[dict[str, Any]], int]:
    threshold = SEVERITY_RANK[minimum_severity]
    matches = []
    unclassified = 0
    for alert in alerts:
        severity = _severity(alert)
        if severity is None:
            unclassified += 1
        elif SEVERITY_RANK[severity] <= threshold:
            matches.append(alert)
    return matches, unclassified


def _graphql(
    query: str, variables: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    response = requests.post(
        f"{API_URL}/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("GitHub returned an unexpected GraphQL response.")
    return data


def _get_repository_and_task_type(
    repository: str, headers: dict[str, str]
) -> tuple[str, str]:
    owner, name = repository.split("/", 1)
    data = _graphql(
        """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            id
            issueTypes(first: 100) { nodes { id name } }
          }
        }
        """,
        {"owner": owner, "name": name},
        headers,
    )
    repo_data = data.get("repository")
    if not repo_data:
        raise RuntimeError(f"Repository '{repository}' was not found or is inaccessible.")
    task = next(
        (
            issue_type
            for issue_type in repo_data["issueTypes"]["nodes"]
            if issue_type["name"].casefold() == "task"
        ),
        None,
    )
    if task is None:
        raise RuntimeError(
            f"Repository '{repository}' does not have an available 'Task' issue type."
        )
    return repo_data["id"], task["id"]


def _ensure_security_label(
    repository: str, headers: dict[str, str]
) -> str:
    owner, name = repository.split("/", 1)
    repo_url = f"{API_URL}/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    label_url = f"{repo_url}/labels/{quote('security', safe='')}"
    response = requests.get(label_url, headers=headers, timeout=30)
    if response.status_code == 404:
        response = requests.post(
            f"{repo_url}/labels",
            json={
                "name": "security",
                "color": "0075ca",
                "description": "Security-related work",
            },
            headers=headers,
            timeout=30,
        )
    response.raise_for_status()
    label_id = response.json().get("node_id")
    if not label_id:
        raise RuntimeError("GitHub did not return an ID for the security label.")
    return label_id


def _priority_field(
    repository: str, field_name: str, headers: dict[str, str]
) -> dict[str, Any] | None:
    owner = repository.split("/", 1)[0]
    response = requests.get(
        f"{API_URL}/orgs/{quote(owner, safe='')}/issue-fields",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    fields = response.json()
    if not isinstance(fields, list):
        raise RuntimeError("GitHub returned an unexpected issue-fields response.")
    return next(
        (
            field
            for field in fields
            if str(field.get("name", "")).casefold() == field_name.casefold()
        ),
        None,
    )


def _priority_value(field: dict[str, Any], severity: str) -> str | int | None:
    data_type = field.get("data_type")
    if data_type == "text":
        return severity.title()
    if data_type == "number":
        return SEVERITY_PRIORITY[severity]
    if data_type == "single_select":
        options = field.get("options") or []
        normalized = re.sub(r"[^a-z0-9]", "", severity)
        for option in options:
            name = str(option.get("name", ""))
            option_normalized = re.sub(r"[^a-z0-9]", "", name.casefold())
            if normalized in option_normalized:
                return name
        expected = PRIORITY_OPTIONS[severity]
        for option in options:
            name = str(option.get("name", ""))
            option_normalized = re.sub(r"[^a-z0-9]", "", name.casefold())
            if expected in option_normalized:
                return name
    return None


def _set_priority(
    repository: str,
    issue_number: int,
    field: dict[str, Any],
    severity: str,
    headers: dict[str, str],
) -> str | int:
    value = _priority_value(field, severity)
    if value is None:
        raise RuntimeError(
            f"Could not map severity '{severity}' to the '{field['name']}' field."
        )

    owner, name = repository.split("/", 1)
    response = requests.post(
        f"{API_URL}/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
        f"/issues/{issue_number}/issue-field-values",
        json={"issue_field_values": [{"field_id": field["id"], "value": value}]},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return value


def _issue_title(alert: dict[str, Any]) -> str:
    number = alert["number"]
    rule_name = str((alert.get("rule") or {}).get("name") or "Code scanning finding")
    rule_name = " ".join(rule_name.split())
    return f"Fix code scanning alert #{number}: {rule_name}"[:256]


def _issue_body(repository: str, alert: dict[str, Any], severity: str) -> str:
    number = alert["number"]
    rule = alert.get("rule") or {}
    instance = alert.get("most_recent_instance") or {}
    location = instance.get("location") or {}
    message = (instance.get("message") or {}).get("text") or ""
    alert_url = f"https://github.com/{repository}/security/code-scanning/{number}"
    location_text = location.get("path") or "Unknown"
    if location.get("start_line") is not None:
        location_text += f":{location['start_line']}"

    lines = [
        "### User Story Description",
        "",
        f"As a repository maintainer, I want to remediate the "
        f"**{rule.get('name') or 'code scanning finding'}** finding, "
        "so that the codebase meets its security and certification requirements.",
        "",
        "#### Alert details",
        "",
        f"- **Priority:** {severity.title()}",
        f"- **Security severity:** {severity}",
        f"- **Alert:** {alert_url}",
        f"- **Location:** `{location_text}`",
        f"- **Rule:** {rule.get('name') or 'Unknown'}",
        f"- **Tool:** {(alert.get('tool') or {}).get('name') or 'Unknown'}",
        "### Acceptance Criteria",
        "",
        f"- [ ] Remediate the alert {alert_url} or provide a justification for not doing so."
    ]
    if message:
        lines += ["", "**Finding message**", "", f"> {message.replace(chr(10), chr(10) + '> ')}"]
    lines += ["", f"<!-- code-scanning-alert: {number} -->"]
    return "\n".join(lines)


def _create_issue(
    repository: str,
    alert: dict[str, Any],
    severity: str,
    repository_id: str,
    task_type_id: str,
    label_id: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    data = _graphql(
        """
        mutation($input: CreateIssueInput!) {
          createIssue(input: $input) {
            issue { number url }
          }
        }
        """,
        {
            "input": {
                "repositoryId": repository_id,
                "title": _issue_title(alert),
                "body": _issue_body(repository, alert, severity),
                "labelIds": [label_id],
                "issueTypeId": task_type_id,
            }
        },
        headers,
    )
    issue = (data.get("createIssue") or {}).get("issue")
    if not issue:
        raise RuntimeError(
            f"GitHub did not return the created issue for alert #{alert['number']}."
        )
    return issue


def _process(args: argparse.Namespace, token: str) -> int:
    headers = _headers(token)
    alerts = _list_alerts(args.repository, headers)
    matching, unclassified = _filter_alerts(alerts, args.min_severity)
    print(
        f"Found {len(alerts)} open alert(s); {len(matching)} meet the "
        f"minimum severity '{args.min_severity}'."
    )
    if unclassified:
        print(
            f"Skipped {unclassified} alert(s) without a recognized security severity."
        )
    if not matching:
        return 0

    existing_stories = _find_open_alert_stories(args.repository, headers)
    to_create = [
        alert for alert in matching if alert["number"] not in existing_stories
    ]
    already_open = len(matching) - len(to_create)
    if already_open:
        print(f"Skipped {already_open} alert(s) that already have an open issue:")
        for alert in matching:
            issue_url = existing_stories.get(alert["number"])
            if issue_url:
                print(f"  Alert #{alert['number']}: {issue_url}")
    if not to_create:
        print("No new issues to create.")
        return 0

    if args.dry_run:
        for alert in to_create:
            print(
                f"  [DRY-RUN] Would create Task for alert #{alert['number']} "
                f"({(_severity(alert) or '').title()}): {_issue_title(alert)}"
            )
        return 0

    repository_id, task_type_id = _get_repository_and_task_type(
        args.repository, headers
    )
    label_id = _ensure_security_label(args.repository, headers)
    try:
        priority_field = _priority_field(
            args.repository, args.priority_field, headers
        )
        if priority_field is None:
            print(
                f"[WARN] Organization issue field '{args.priority_field}' was not "
                "found; priorities will be included in issue descriptions only.",
                file=sys.stderr,
            )
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        priority_field = None
        print(
            f"[WARN] Could not read the '{args.priority_field}' issue field "
            f"({exc}); priorities will be included in issue descriptions only.",
            file=sys.stderr,
        )

    failures = 0
    for alert in to_create:
        severity = _severity(alert)
        if severity is None:
            continue
        try:
            issue = _create_issue(
                args.repository,
                alert,
                severity,
                repository_id,
                task_type_id,
                label_id,
                headers,
            )
        except (requests.RequestException, RuntimeError) as exc:
            print(
                f"[FAILED] Could not create issue for alert #{alert['number']}: {exc}",
                file=sys.stderr,
            )
            failures += 1
            continue

        print(
            f"Created Task {issue['url']} for alert #{alert['number']} "
            f"({severity.title()})."
        )
        if priority_field is not None:
            try:
                priority = _set_priority(
                    args.repository,
                    issue["number"],
                    priority_field,
                    severity,
                    headers,
                )
                print(f"  Set {args.priority_field} priority to {priority}.")
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                print(
                    f"[WARN] Could not set the '{args.priority_field}' field on "
                    f"issue #{issue['number']} ({exc}); continuing.",
                    file=sys.stderr,
                )

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repository",
        required=True,
        help="GitHub repository in OWNER/REPOSITORY format.",
    )
    parser.add_argument(
        "--min-severity",
        choices=list(SEVERITY_RANK),
        default="medium",
        help="Create issues for alerts at or above this security severity (default: medium).",
    )
    parser.add_argument(
        "--priority-field",
        default="Priority",
        help="Organization issue field to set from alert severity (default: Priority).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matching alerts without creating issues or changing labels/fields.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repository):
        print(
            "[ERROR] --repository must be in OWNER/REPOSITORY format.",
            file=sys.stderr,
        )
        sys.exit(2)

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("[ERROR] GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    try:
        failures = _process(args, token)
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    if failures:
        print(f"Completed with {failures} issue creation failure(s).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()