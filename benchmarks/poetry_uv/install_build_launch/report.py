"""Write the SAF install, build, and launch benchmark report in Markdown.

The report can be regenerated from an existing result directory, for example
after merging Windows and Linux results into one tree::

    python report.py results/20261124T160000Z
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import json
from pathlib import Path
import statistics
from typing import Any

STAGE_ORDER = {"install": 0, "build": 1, "launch": 2}
SIZE_ORDER = {"small": 0, "medium": 1, "large": 2}
NETWORK_ORDER = {None: 0, "online": 1, "offline": 2}
OS_ORDER = {"Windows": 0, "Linux": 1}
BACKEND_LABELS = {"poetry": "Poetry", "uv": "UV"}
STAGE_DESCRIPTIONS = {
    "install": "`saf install` on a fresh copy of the solution (dev).",
    "build": "`saf build` after an un-timed `saf install` (dev).",
    "launch": "Unattended installer run: `<installer> --no-ui --installation-directory <dir>` (prod).",
}
LAUNCH_PHASES = (
    ("startup_seconds", "Startup"),
    ("setup_seconds", "Deploy + dependencies"),
    ("preload_seconds", "Preload"),
)

CaseKey = tuple[str, str, str, str | None]


def seconds(value: Any) -> str:
    """Format an optional duration (two decimals below 10 s to keep short stages readable)."""
    if value is None:
        return "-"
    number = float(value)
    return f"{number:.2f}" if abs(number) < 10 else f"{number:.1f}"


def megabytes(value: Any) -> str:
    """Format an optional byte count in MB."""
    return "-" if value is None else f"{float(value) / 1_000_000:.1f}"


def speed(value: Any) -> str:
    """Format an optional byte rate in MB/s."""
    return "-" if value is None else f"{float(value) / 1_000_000:.2f}"



def case_key(record: dict[str, Any]) -> CaseKey:
    """Return the case identity shared by Poetry and UV."""
    return (str(record["stage"]), str(record["os"]), str(record["size"]), record.get("network"))


def sort_key(key: CaseKey) -> tuple[int, int, int, int]:
    """Order cases by stage, OS, size, and network."""
    stage, os_name, size, network = key
    return (
        STAGE_ORDER.get(stage, 9),
        OS_ORDER.get(os_name, 9),
        SIZE_ORDER.get(size, 9),
        NETWORK_ORDER.get(network, 9),
    )


def passed_values(records: Iterable[dict[str, Any]], field: str = "stage_seconds") -> list[float]:
    """Return a field's values from passed runs."""
    return [
        float(record[field])
        for record in records
        if record.get("status") == "passed" and record.get(field) is not None
    ]


def summary(values: list[float]) -> dict[str, float | None]:
    """Return mean, standard deviation, min, and max."""
    if not values:
        return {"mean": None, "stdev": None, "min": None, "max": None}
    return {
        "mean": statistics.fmean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def winner(poetry: float | None, uv: float | None) -> str:
    """Describe which backend was faster and by how much (within 1% is a tie)."""
    if poetry is None or uv is None:
        return "-"
    slower = max(poetry, uv)
    difference = abs(poetry - uv)
    if slower <= 0 or difference / slower < 0.01:
        return "tie"
    name = "UV" if uv < poetry else "Poetry"
    return f"**{name}** by {seconds(difference)} s ({difference / slower * 100:.1f}%)"


def legend(entries: list[tuple[str, str]]) -> list[str]:
    """Return a short list explaining table columns, placed right under the table."""
    return [*(f"- **{name}**: {meaning}" for name, meaning in entries), ""]


COMPARISON_LEGEND = [
    ("Poetry mean / UV mean", "average time of the timed command over the passed runs, in seconds"),
    ("Faster", "the backend with the lower mean, how much faster, and by what share of the slower one"),
    ("Poetry runs / UV runs", "passed runs / all runs of that case"),
]
STATISTICS_LEGEND = [
    ("Passed", "passed runs / all runs"),
    ("Mean, Std dev, Min, Max", "time of the timed command over the passed runs; a large Std dev means unstable runs"),
    ("Prep mean", "un-timed preparation: workspace copy and, for build and launch, the install/build needed first"),
    ("Installer", "size of the installer produced by the build"),
    ("Environment", "`.venv` size after install; installed solution size after launch"),
]
LAUNCH_LEGEND = [
    ("Startup", "from starting the installer until its own logic runs (unpacking, prerequisite checks)"),
    ("Deploy + dependencies", "copying the solution and installing its packages, as printed by the installer"),
    ("Preload", "first start of the installed solution, as printed by the installer"),
    ("Total", "the whole timed launch"),
]
RUNS_LEGEND = [
    ("Attempts", "1 + retries after a network failure"),
    ("Stage", "time of the timed command"),
    ("Download", "time the timed command spent receiving data"),
    ("Download rate", "how fast the tool downloaded during that time; depends on the internet and on the tool "
     "(UV fetches many packages at once, pip one at a time), so it differs between backends"),
    ("Internet speed", "speed of the connection itself, from the same test file downloaded just before the timed "
     "command (not timed); compare it across runs to see whether the internet was slow"),
    ("Prep", "un-timed preparation before the timed command"),
    ("Wall", "the whole run including preparation and cleanup"),
]
ENVIRONMENT_LEGEND = [
    ("Platform, Python", "operating system and Python running the benchmark worker"),
    ("SAF CLI, UV", "versions used by the runs on that OS"),
]


def comparison_section(groups: dict[CaseKey, dict[str, list[dict[str, Any]]]]) -> list[str]:
    """Return the Poetry versus UV summary table for every stage."""
    lines = ["## Poetry versus UV", ""]
    for stage in sorted({key[0] for key in groups}, key=lambda name: STAGE_ORDER.get(name, 9)):
        lines.extend(
            [
                f"### {stage}",
                "",
                STAGE_DESCRIPTIONS.get(stage, ""),
                "",
                "| OS | Size | Network | Poetry mean (s) | UV mean (s) | Faster | Poetry runs | UV runs |",
                "|---|---|---|---:|---:|---|---:|---:|",
            ],
        )
        for key in sorted((key for key in groups if key[0] == stage), key=sort_key):
            by_backend = groups[key]
            poetry_values = passed_values(by_backend.get("poetry", []))
            uv_values = passed_values(by_backend.get("uv", []))
            poetry_mean = summary(poetry_values)["mean"]
            uv_mean = summary(uv_values)["mean"]
            lines.append(
                f"| {key[1]} | {key[2]} | {key[3] or '-'} | {seconds(poetry_mean)} | {seconds(uv_mean)} | "
                f"{winner(poetry_mean, uv_mean)} | {len(poetry_values)}/{len(by_backend.get('poetry', []))} | "
                f"{len(uv_values)}/{len(by_backend.get('uv', []))} |",
            )
        lines.append("")
    if groups:
        lines.extend(legend(COMPARISON_LEGEND))
    return lines


def statistics_section(groups: dict[CaseKey, dict[str, list[dict[str, Any]]]]) -> list[str]:
    """Return per-backend statistics including spread and artifact sizes."""
    lines = [
        "## Statistics per case",
        "",
        "| Stage | OS | Size | Network | Backend | Passed | Mean (s) | Std dev (s) | Min (s) | Max (s) "
        "| Prep mean (s) | Installer (MB) | Environment (MB) |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in sorted(groups, key=sort_key):
        for backend in ("poetry", "uv"):
            records = groups[key].get(backend, [])
            if not records:
                continue
            stats = summary(passed_values(records))
            preparation = summary(passed_values(records, "preparation_seconds"))["mean"]
            installer = summary(passed_values(records, "installer_bytes"))["mean"]
            environment = summary(passed_values(records, "venv_bytes"))["mean"]
            lines.append(
                f"| {key[0]} | {key[1]} | {key[2]} | {key[3] or '-'} | {BACKEND_LABELS.get(backend, backend)} | "
                f"{len(passed_values(records))}/{len(records)} | {seconds(stats['mean'])} | "
                f"{seconds(stats['stdev'])} | {seconds(stats['min'])} | {seconds(stats['max'])} | "
                f"{seconds(preparation)} | {megabytes(installer)} | {megabytes(environment)} |",
            )
    lines.append("")
    lines.extend(legend(STATISTICS_LEGEND))
    return lines


def launch_section(groups: dict[CaseKey, dict[str, list[dict[str, Any]]]]) -> list[str]:
    """Return the launch phase breakdown."""
    launch_keys = sorted((key for key in groups if key[0] == "launch"), key=sort_key)
    if not launch_keys:
        return []
    header = " | ".join(f"{label} (s)" for _, label in LAUNCH_PHASES)
    lines = [
        "## Launch phases (mean)",
        "",
        f"| OS | Size | Network | Backend | {header} | Total (s) |",
        "|---|---|---|---|" + "---:|" * (len(LAUNCH_PHASES) + 1),
    ]
    for key in launch_keys:
        for backend in ("poetry", "uv"):
            records = groups[key].get(backend, [])
            if not records:
                continue
            cells = " | ".join(seconds(summary(passed_values(records, field))["mean"]) for field, _ in LAUNCH_PHASES)
            total = summary(passed_values(records))["mean"]
            lines.append(
                f"| {key[1]} | {key[2]} | {key[3] or '-'} | {BACKEND_LABELS.get(backend, backend)} | "
                f"{cells} | {seconds(total)} |",
            )
    lines.append("")
    lines.extend(legend(LAUNCH_LEGEND))
    return lines


def runs_section(records: list[dict[str, Any]]) -> list[str]:
    """Return the individual runs table."""
    lines = [
        "## Individual runs",
        "",
        "| Run | Status | Attempts | Stage (s) | Download (s) | Download rate (MB/s) | Internet speed (MB/s) "
        "| Prep (s) | Wall (s) | Started (UTC) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for record in sorted(
        records,
        key=lambda item: (*sort_key(case_key(item)), int(item.get("repetition", 0)), str(item.get("backend"))),
    ):
        lines.append(
            f"| `{record['label']}` | {record.get('status', '-')} | {record.get('attempts', 1)} | "
            f"{seconds(record.get('stage_seconds'))} | {seconds(record.get('download_seconds'))} | "
            f"{speed(record.get('download_speed'))} | {speed(record.get('internet_speed'))} | "
            f"{seconds(record.get('preparation_seconds'))} | {seconds(record.get('wall_seconds'))} | "
            f"{record.get('started') or '-'} |",
        )
    lines.append("")
    lines.extend(legend(RUNS_LEGEND))
    return lines


def failures_section(records: list[dict[str, Any]]) -> list[str]:
    """Return a list of failures with log locations."""
    failures = [record for record in records if record.get("status") != "passed"]
    if not failures:
        return []
    lines = ["## Failures", ""]
    for record in failures:
        lines.extend(
            [
                f"### `{record['label']}`",
                "",
                f"- Error: {record.get('error') or 'unknown'}",
                f"- Logs: `{record['label']}/stage.log`, `preparation.log`, `worker.log`",
                "",
            ],
        )
    return lines


def tools_section(records: list[dict[str, Any]]) -> list[str]:
    """Return the tool versions observed per OS."""
    seen: dict[str, dict[str, str]] = {}
    for record in records:
        tools = record.get("tools")
        if isinstance(tools, dict) and record.get("os") not in seen:
            seen[str(record.get("os"))] = {str(key): str(value) for key, value in tools.items()}
    if not seen:
        return []
    lines = ["## Environment", "", "| OS | Platform | Python | SAF CLI | UV |", "|---|---|---|---|---|"]
    for os_name, tools in sorted(seen.items(), key=lambda item: OS_ORDER.get(item[0], 9)):
        lines.append(
            f"| {os_name} | {tools.get('platform', '-')} | {tools.get('python', '-')} | "
            f"{tools.get('saf', '-')} | {tools.get('uv', '-')} |",
        )
    lines.append("")
    lines.extend(legend(ENVIRONMENT_LEGEND))
    return lines


def write_reports(
    output_root: Path,
    records: list[dict[str, Any]],
    planned: int,
    settings: dict[str, Any],
) -> Path:
    """Write ``report.md`` and ``results.json`` for the benchmark session."""
    groups: dict[CaseKey, dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        groups.setdefault(case_key(record), {}).setdefault(str(record["backend"]), []).append(record)

    passed = sum(record.get("status") == "passed" for record in records)
    lines = [
        "# SAF install, build, and launch benchmark: Poetry versus UV",
        "",
        f"- Command: `{settings.get('command', '-')}`",
        f"- Configuration: `{settings.get('config', '-')}`",
        f"- Host: {settings.get('host', '-')} ({settings.get('host_os', '-')})",
        f"- Started: {settings.get('started', '-')}; finished: {settings.get('finished', '-')}",
        f"- Runs per case: {settings.get('runs_per_case', '-')}; "
        f"cold package caches: {settings.get('cold_cache', '-')}",
        f"- Planned runs: {planned}; completed: {len(records)}; passed: {passed}; "
        f"failed: {len(records) - passed}; "
        f"runs retried after a network error: {sum(int(r.get('attempts', 1)) > 1 for r in records)}",
        "",
        "Times are wall-clock seconds of the timed command only. Means use passed runs.",
        "",
    ]
    lines.extend(comparison_section(groups))
    lines.extend(statistics_section(groups))
    lines.extend(launch_section(groups))
    lines.extend(tools_section(records))
    lines.extend(runs_section(records))
    lines.extend(failures_section(records))

    report_file = output_root / "report.md"
    report_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    (output_root / "results.json").write_text(
        json.dumps({"settings": settings, "planned": planned, "records": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_file


def collect_records(root: Path) -> list[dict[str, Any]]:
    """Read every run's ``result.json`` below ``root``."""
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("result.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "label" in data and "backend" in data:
            records.append(data)
    return records


def main() -> int:
    """Regenerate a report from an existing result directory."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("result_directory", type=Path, help="Result directory containing run folders.")
    arguments = parser.parse_args()
    root = arguments.result_directory.resolve()
    records = collect_records(root)
    if not records:
        raise SystemExit(f"No run results found below {root}.")
    settings: dict[str, Any] = {"command": "report.py (regenerated)", "config": "-"}
    previous = root / "results.json"
    if previous.is_file():
        settings.update(json.loads(previous.read_text(encoding="utf-8")).get("settings", {}))
    report_file = write_reports(root, records, len(records), settings)
    print(f"Report: {report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
