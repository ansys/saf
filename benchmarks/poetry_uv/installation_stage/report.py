"""Write benchmark results in Markdown format."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def format_seconds(value: Any) -> str:
    """Format an optional timing value for a Markdown table."""
    return "-" if value is None else f"{float(value):.3f}"


def write_reports(
    output_root: Path,
    records: list[dict[str, Any]],
    plan: list[Any],
    config_file: Path | None,
    preparation_records: list[dict[str, Any]],
) -> Path:
    """Write the Markdown report for the completed matrix."""
    markdown_file = output_root / "report.md"

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(
            (str(record["mode"]), str(record["backend"]), str(record["variant"])),
            [],
        ).append(record)

    markdown: list[str] = [
        "# SAF Poetry versus UV benchmark results",
        "",
        f"- Configuration: `{config_file.resolve() if config_file is not None else 'defaults'}`",
        f"- Planned runs: {len(plan)}",
        f"- Passed: {sum(record['status'] == 'passed' for record in records)}",
        f"- Failed: {sum(record['status'] == 'failed' for record in records)}",
        "",
        "## Preparation",
        "",
        "| Mode | Status | Preparation (s) | Payload |",
        "|---|---|---:|---|",
    ]
    for preparation in preparation_records:
        seconds_text = format_seconds(preparation.get("seconds"))
        markdown.append(
            f"| {preparation['mode']} | {preparation['status']} | {seconds_text} | "
            f"`{preparation.get('payload', '-')}` |",
        )

    markdown.extend(
        [
            "",
            "## Individual runs",
            "",
            "| Run | Status | Preparation (s) | Backend (s) | Preload (s) | Shortcut (s) | Total (s) |",
            "|---|---|---:|---:|---:|---:|---:|",
        ],
    )
    for record in records:
        markdown.append(
            f"| `{record['label']}` | {record['status']} | "
            f"{format_seconds(record.get('preparation_seconds'))} | "
            f"{format_seconds(record.get('backend_seconds'))} | "
            f"{format_seconds(record.get('preload_seconds'))} | "
            f"{format_seconds(record.get('shortcut_seconds'))} | "
            f"{format_seconds(record.get('total_seconds'))} |",
        )

    markdown.extend(["", "## Averages", ""])
    markdown.extend(
        [
            "| Mode | Backend | Variant | Passed | Backend average (s) | Total average (s) |",
            "|---|---|---|---:|---:|---:|",
        ],
    )
    for (mode, backend, variant), group in groups.items():
        passed = [record for record in group if record["status"] == "passed"]
        average_backend = (
            sum(float(record["backend_seconds"]) for record in passed) / len(passed) if passed else None
        )
        average_total = sum(float(record["total_seconds"]) for record in passed) / len(passed) if passed else None
        backend_text = "-" if average_backend is None else f"{average_backend:.3f}"
        total_text = "-" if average_total is None else f"{average_total:.3f}"
        markdown.append(
            f"| {mode} | {backend} | {variant} | {len(passed)}/{len(group)} | "
            f"{backend_text} | {total_text} |",
        )

    failures = [record for record in records if record["status"] == "failed"]
    if failures:
        markdown.extend(["", "## Failures", ""])
        for record in failures:
            markdown.extend(
                [
                    f"### `{record['label']}`",
                    "",
                    f"- Run directory: `{record['run_directory']}`",
                    f"- Error: {record['error']}",
                    "",
                ],
            )
    markdown_file.write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return markdown_file
