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

from pathlib import Path

from benchmarks.model import BenchmarkData, Measurement
import click
import numpy
from prettytable import PrettyTable


def _parameters_product(parameters: dict[str, float]) -> float:
    y = list(parameters.values())
    x = numpy.array(y)
    return numpy.prod(x)  # type: ignore


def _extract_measurements(benchmark: BenchmarkData) -> dict[str, tuple[Measurement, Measurement]]:
    measurements: dict[str, tuple[Measurement, Measurement]] = {}
    for item in benchmark.data:
        if item.name in measurements:
            if _parameters_product(item.parameters) > _parameters_product(measurements[item.name][0].parameters):
                measurements[item.name] = (measurements[item.name][0], item)
            if _parameters_product(item.parameters) < _parameters_product(measurements[item.name][1].parameters):
                measurements[item.name] = (item, measurements[item.name][1])
        else:
            measurements[item.name] = (item, item)

    return measurements


def _parameters_match(old_item: Measurement, new_item: Measurement) -> bool:
    return all(old_value == new_item.parameters[key] for key, old_value in old_item.parameters.items())


def _parameters_string(item: Measurement) -> str:
    return ",".join([f"{key}={value}" for key, value in item.parameters.items()])


def _add_row(table: PrettyTable, size: str, old_item: Measurement, new_item: Measurement):
    assert old_item.name == new_item.name  # noqa: S101
    row: list[str | float] = [old_item.name, size]
    if not _parameters_match(old_item, new_item):
        row.extend(
            [
                f"parameters do not match, old: {_parameters_string(old_item)}  new: {_parameters_string(new_item)}",
                "",
                "",
                "",
                "",
            ],
        )
    else:
        old = old_item.mean_duration
        new = new_item.mean_duration

        if old < new:
            row.extend(["slower", new / old])
        else:
            row.extend(["faster", old / new])

        row.extend([old, new, _parameters_string(old_item)])

    table.add_row(row=row)


def _add_rows(
    table: PrettyTable,
    old_measurements: dict[str, tuple[Measurement, Measurement]],
    new_measurements: dict[str, tuple[Measurement, Measurement]],
):
    for key in sorted(key for key in old_measurements):
        old_item = old_measurements[key]
        new_item = new_measurements[key]

        if old_item[0] is old_item[1]:
            _add_row(table, "std", old_item[0], new_item[0])
        else:
            _add_row(table, "smallest", old_item[0], new_item[0])
            _add_row(table, "biggest", old_item[1], new_item[1])


def _resolve_file(context_dir: Path, platform_pattern: str, tag_pattern: str) -> Path:
    files = list(context_dir.glob(f"{platform_pattern}\\{tag_pattern}.json"))
    pattern_string = f"{context_dir}/{platform_pattern}/{tag_pattern}.json"
    if not files:
        raise RuntimeError(f"No file found for pattern {pattern_string}")
    if len(files) > 1:
        raise RuntimeError(f"Multiple files found for pattern {pattern_string}: {files}")
    return files[0]


def _extract_data(file_path: Path) -> BenchmarkData:
    return BenchmarkData.model_validate_json(file_path.read_text())


@click.command()
@click.argument("platform_pattern")
@click.argument("old_tag_pattern")
@click.argument("new_tag_pattern")
def main(platform_pattern: str, old_tag_pattern: str, new_tag_pattern: str):
    context_dir = Path(__file__).parent / "history"
    if not context_dir.is_dir():
        raise RuntimeError(f"{context_dir} is not a directory")
    if not context_dir.exists():
        raise RuntimeError(f"{context_dir} does not exist")

    print(f"extracting data from {context_dir}")

    old_file_path = _resolve_file(context_dir, platform_pattern, old_tag_pattern)
    new_file_path = _resolve_file(context_dir, platform_pattern, new_tag_pattern)

    if old_file_path == new_file_path:
        raise RuntimeError(f"Old and new file paths are the same: {old_file_path}")

    old_data = _extract_data(old_file_path)
    new_data = _extract_data(new_file_path)

    if old_data.time > new_data.time:
        print("Warning: Old data is newer than new data")

    old_measurements = _extract_measurements(old_data)
    new_measurements = _extract_measurements(new_data)

    print("Old File: ", old_file_path)
    print("New File: ", new_file_path)
    table = PrettyTable()
    table.field_names = [
        "Measure",
        "size",
        "status",
        "multiple",
        "old (seconds)",
        "new (seconds)",
        "parameters (bytes)",
    ]
    _add_rows(table, old_measurements, new_measurements)
    print(table)


if __name__ == "__main__":
    main()
