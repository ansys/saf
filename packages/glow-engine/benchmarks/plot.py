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

import json
from pathlib import Path

from benchmarks.model import BenchmarkData
import click
import numpy
import plotly.express as px  # pyright: ignore[reportMissingTypeStubs]
import plotly.graph_objects as go  # pyright: ignore[reportMissingTypeStubs]
from pydantic import BaseModel


class Plot(BaseModel):
    dimensions: int = 0
    x: list[float] = []
    y: list[float] = []
    median_duration: list[float] = []
    mean_duration: list[float] = []
    max_duration: list[float] = []
    min_duration: list[float] = []
    x_name: str = ""
    y_name: str = ""


def _extract_plots(benchmark: BenchmarkData):
    plots: dict[str, Plot] = {}
    for item in benchmark.data:
        other_keys = sorted(item.parameters.keys())

        if len(other_keys) in [1, 2]:
            name = item.name
            plot = plots.get(name, Plot())

            plot.dimensions = len(other_keys)
            plot.max_duration.append(item.maximum_duration)
            plot.min_duration.append(item.minimum_duration)
            plot.mean_duration.append(item.mean_duration)
            if item.median_duration is not None:
                plot.median_duration.append(item.median_duration)
            plot.x.append(item.parameters[other_keys[0]])
            plot.x_name = other_keys[0]
            if plot.dimensions == 2:
                plot.y.append(item.parameters[other_keys[1]])
                plot.y_name = other_keys[1]

            plots[name] = plot
    return plots


def show_plot(directory_name: str, file_name: str, name: str, plot: Plot, plot_property: str, label: str):
    title = f"{directory_name} - {file_name} - {name} - {label}"
    surfaces: list[go.Surface] = []

    plot_data = getattr(plot, plot_property)

    if not plot_data:
        return

    if plot.dimensions == 2:
        x = sorted(set(plot.x))
        y = sorted(set(plot.y))

        data: list[list[float]] = []
        for y_value in y:
            x_data: list[float] = []
            for x_value in x:
                indexes = [index for index, value in enumerate(plot.x) if value == x_value and plot.y[index] == y_value]
                if indexes:
                    x_data.append(plot_data[indexes[0]])
                else:
                    x_data.append(numpy.nan)

            data.append(x_data)
        z = numpy.array(data)
        surfaces.append(go.Surface(x=x, y=y, z=z, showscale=True))

        fig = go.Figure(data=surfaces)
        fig.update_layout(  # type: ignore
            title=title,
            scene={
                "xaxis_title": plot.x_name,
                "yaxis_title": plot.y_name,
                "zaxis_title": label,
            },
        )
        fig.show()  # type: ignore
    else:
        x = sorted(set(plot.x))
        y: list[float] = []
        for x_value in x:
            indexes = [index for index, value in enumerate(plot.x) if value == x_value]
            if indexes:
                y.append(plot_data[indexes[0]])
            else:
                y.append(numpy.nan)

        fig = px.line(x=x, y=y, title=title, labels={plot.x_name, label})  # type: ignore
        fig.show()  # type: ignore


@click.command()
@click.argument("json_file_path")
@click.argument("plot_name")
def main(json_file_path: str, plot_name: str):
    json_file = Path(json_file_path)

    assert json_file.is_file(), f"File {json_file_path} does not exist"  # noqa: S101

    file_name = json_file.name
    directory_name = json_file.parent.name
    benchmark = BenchmarkData(**json.loads(json_file.read_text()))
    plots = _extract_plots(benchmark)

    if plot_name == "all":
        for name, plot in plots.items():
            show_plot(directory_name, file_name, name, plot, "mean_duration", "mean duration")
            # show_plot(directory_name, file_name, name, plot, "median_duration", "median duration")
    else:
        plot_name = plot_name.replace("-", " ")
        if plot_name not in plots:
            print(
                f"Plot {plot_name} not found in {json_file_path}, "
                f"available plots: {[x.replace(' ', '-') for x in plots]}",
            )
            return

        plot = plots[plot_name]
        show_plot(directory_name, file_name, plot_name, plot, "mean_duration", "mean duration")


if __name__ == "__main__":
    main()
