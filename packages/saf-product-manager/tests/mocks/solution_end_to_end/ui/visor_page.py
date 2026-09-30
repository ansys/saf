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

"""Frontend of the first page."""

import logging

from dash_extensions.enrich import Input, Output, State, html  # pyright: ignore[reportMissingTypeStubs]
from visordash import Visordash  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.glow.client import callback
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.visor_instance_step import (
    VisorInstanceStep,
)

logger = logging.getLogger(__name__)


def layout(step: VisorInstanceStep):
    """Layout of a step that uses websockets."""
    return html.Div(
        [
            html.H1("We are in Visor Page"),
            html.Div(
                [
                    html.Button("Start Visualization Service (Visor)", id="trigger_start", n_clicks=0),
                ],
            ),
            html.Div(
                id="visor_dash",
                children=[],
                style={
                    "flex": "1",
                    "width": "100%",
                    "height": "calc(100vh - 100px)",  # Full viewport height minus header/padding
                    "overflow": "hidden",  # Prevent scrollbars
                },
            ),
            html.Div(
                [
                    html.Button("Update Visualization", id="trigger_update", n_clicks=0),
                ],
            ),
            html.Div(
                [
                    html.Button("Stop Visualization", id="trigger_stop", n_clicks=0),
                ],
            ),
            html.Div(id="visor_started", children=f"Visor Started: {step.visor_started}"),
            html.Div(id="visor_updated", children=f"Visor Updated: {step.visor_updated}"),
        ],
    )


@callback(
    Output("visor_dash", "children"),
    Output("visor_started", "children"),
    Input("trigger_start", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def trigger_start(n_clicks: int, project: EndToEndSolution) -> tuple[list[Visordash], str] | None:
    step = project.steps.visor_instance_step
    if n_clicks > 0:
        if not step.visor_started:
            step.start_visor().wait()
        else:
            step.refresh_visor().wait()
        logger.info(f"Visor instance is ready and listening at {step.visor_port}")
        visor_dash = [
            # this connection is done between the browser and the Visor instance, like a websocket in GLOW, so we cannot
            # always use the instance host in the form that it's reachable from the API / UI servers
            # (e.g., host.docker.internal in Docker Compose).
            Visordash(
                host="localhost",
                port=step.visor_port,
                aspectRatio=1,
                pixelDensity=800,
            ),
        ]
        return visor_dash, f"Visor Started: {step.visor_started}"


@callback(
    Output("visor_updated", "children"),
    Input("trigger_update", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def trigger_update(n_clicks: int, project: EndToEndSolution) -> str | None:
    if n_clicks > 0:
        step = project.steps.visor_instance_step
        step.update_visor()
        return f"Visor Updated: {step.visor_updated}"


@callback(
    Output("visor_started", "children"),
    Input("trigger_stop", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def trigger_stop(n_clicks: int, project: EndToEndSolution) -> str | None:
    if n_clicks > 0:
        step = project.steps.visor_instance_step
        step.close_visor()
        return f"Visor Started: {step.visor_started}"
