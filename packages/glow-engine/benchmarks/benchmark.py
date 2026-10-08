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

from collections.abc import Generator
from contextlib import contextmanager
import datetime
import json
from pathlib import Path
import statistics
import time
from typing import Any, cast

from benchmarks.model import BenchmarkData, Measurement
from benchmarks.solutions.simple_solution import BenchmarkSolution
from benchmarks.utils import randomword
import click

from ansys.saf.glow.client import Client


class BenchmarkContext: ...


class Benchmarker:
    def __init__(self, context_dir: Path, tag: str = "NO-TAG"):
        self.context_dir = context_dir
        self._data: dict[str, list[float]] = {}
        self._tag = tag

    @contextmanager
    def benchmark(self, name: str, **kwargs: Any) -> Generator[BenchmarkContext, None, None]:
        kwargs["name"] = name
        key = json.dumps(kwargs, sort_keys=True)
        print(f"Starting benchmark: {key}")
        start = time.time()
        yield BenchmarkContext()
        duration = time.time() - start
        print(f"Finished benchmark: {key} in {duration} seconds")
        durations = self._data.get(key, [])
        durations.append(duration)
        self._data[key] = durations

    def save(self):
        data_list: list[Measurement] = []

        for key, durations in self._data.items():
            parameters: dict[str, str | float] = json.loads(key)
            name = cast("str", parameters.pop("name"))
            m = Measurement(
                name=name,
                mean_duration=statistics.mean(durations),
                median_duration=statistics.median(durations),
                maximum_duration=max(durations),
                minimum_duration=min(durations),
                parameters=cast("dict[str, float]", parameters),
            )

            data_list.append(m)

        data = BenchmarkData(time=datetime.datetime.now(), data=data_list)
        file_path = self.context_dir / f"{int(time.time() * 1000)}-{self._tag}.json"
        file_path.write_text(data.model_dump_json(indent=4))

        # TODO - generate plots using https://plotly.com/python/3d-subplots/


@click.command()
@click.argument("context")
@click.argument("tag")
def main(context: str, tag: str):
    context_dir = Path(__file__).parent / "history" / context
    if not context_dir.is_dir():
        print(f"Warning: The directory {context_dir} does not exist. It will be created")
        context_dir.mkdir()
    benchmarker = Benchmarker(context_dir, tag)

    url = "http://localhost:56565"
    with benchmarker.benchmark("client_connection"):
        client = Client[BenchmarkSolution](BenchmarkSolution, url)

    # delete all projects to create stable baseline
    response = client.http_client.get(url + "/projects")  # pyright: ignore[reportPrivateUsage]
    response.raise_for_status()
    projects = response.json()
    for project in projects:
        client.delete_project(project["name"])

    for x in range(50):
        with benchmarker.benchmark("create project"):
            client.create_project(f"project_default_{x}")

    for i in range(7, 23):
        project_size = 2**i
        project_name = f"project_{project_size}_bytes"

        with benchmarker.benchmark("create project"):
            project = client.create_project(project_name)

        background = randomword(project_size)
        with benchmarker.benchmark("store into empty project", project_size=project_size):
            project.steps.data_step.background = background

        for j in range(7, 23):
            field_size = 2**j

            foreground = randomword(field_size)

            for _ in range(10):
                with benchmarker.benchmark("store field", project_size=project_size, field_size=field_size):
                    project.steps.data_step.foreground = foreground
                with benchmarker.benchmark("fetch field", project_size=project_size, field_size=field_size):
                    foreground = project.steps.data_step.foreground
                with benchmarker.benchmark("empty field", project_size=project_size, previous_size=field_size):
                    project.steps.data_step.foreground = ""
                with benchmarker.benchmark("upload field", project_size=project_size, field_size=field_size):
                    project.steps.data_step.upload_field(field_size=field_size)

        with benchmarker.benchmark("delete project", project_size=project_size):
            project.delete()

    benchmarker.save()


if __name__ == "__main__":
    main()
