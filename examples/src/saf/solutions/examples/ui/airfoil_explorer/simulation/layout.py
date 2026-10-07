# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Simulation page layout and constants."""

from __future__ import annotations

from ansys.saf.glow.solution import NO_ENTITY
import dash_bootstrap_components as dbc
from dash_extensions.enrich import dcc, html
import dash_mantine_components as dmc

from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.simulation_status import SimulationStatus
from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.airfoil_explorer.components.simulation_parameters_panel import (
    simulation_parameters_panel,
)
from saf.solutions.examples.ui.airfoil_explorer.components.simulation_tabs import simulation_tabs
from saf.solutions.examples.ui.airfoil_explorer.utils.images import get_image_url_with_cache_bust
from saf.solutions.examples.ui.airfoil_explorer.utils.paths import LOG_FILE_NAMES, get_step_log_file_path

SIMULATION_JOB_STATUS_ID = "simulation-job-status"
SIM_LOGFILE_STORE_ID = "simulation-logfile-store"
SIM_DEFAULTS_STORE_ID = "simulation-defaults"


def layout(project: ExamplesSolution) -> html.Div:
    """Layout of the simulation page.

    Args:
        step: The SimulationStep instance with current state

    Returns:
        Dash HTML Div containing the page layout
    """
    step = project.steps.simulation_step

    log_file = get_step_log_file_path(step, project, LOG_FILE_NAMES["simulation"])

    # Generate flow image URL ONLY if PNG handle exists AND simulation is completed
    flow_image_url = None
    if step.flow_png_handle != NO_ENTITY and step.job_status == "completed":
        flow_image_url = get_image_url_with_cache_bust(step, "flow_png_handle")

    return html.Div(
        [
            dmc.Alert(
                id="simulation-error-alert",
                color="red",
                variant="light",
                withCloseButton=True,
                style={"display": "none"},
            ),
            dcc.Store(id=SIM_LOGFILE_STORE_ID, data=log_file),
            dcc.Store(
                id=SIM_DEFAULTS_STORE_ID,
                data={
                    "nxi": step.circumferential_points,
                    "neta": step.radial_points,
                    "aoa": step.angle_of_attack_deg,
                    "vinf": step.free_stream_velocity,
                },
            ),
            dcc.Store(id="simulation-status-store", data=step.job_status or SimulationStatus.IDLE.value),
            dcc.Store(
                id="simulation-state",
                data={
                    "status": (
                        SimulationStatus.RESULTS_READY.value
                        if step.job_status == SimulationStatus.COMPLETED.value
                        else (step.job_status or SimulationStatus.IDLE.value)
                    ),
                    "execution_mode": "local" if step.job_id == "LOCAL" else ("hps" if step.job_id else "idle"),
                    "job_id": step.job_id,
                    "submission_time": step.submission_time,
                    "results_available": step.job_status == SimulationStatus.COMPLETED.value,
                    "error_message": None,
                    "mesh_available": step.mesh_figure is not None,
                    "flow_available": step.potential_flow_figure is not None,
                },
                storage_type="memory",
            ),
            dcc.Store(
                id="simulation_run_data_storage",
                data={
                    "method_status": None,
                    "hps_job_status": None,
                    "job_id": None,
                },
                storage_type="memory",
            ),
            dmc.Stack(
                gap="sm",
                children=[
                    dmc.Text("Simulation Setup and Solve", size="xl", fw=700),
                    dmc.Text(
                        "Refine the mesh, preview mesh quality, set simulation parameters, and submit the solve.",
                        c="dimmed",
                    ),
                ],
            ),
            dmc.Space(h=20),
            dbc.Row(
                [
                    dbc.Col(
                        dmc.Stack(
                            gap="lg",
                            children=[
                                dmc.Card(
                                    withBorder=True,
                                    shadow="sm",
                                    p="lg",
                                    children=simulation_parameters_panel(
                                        circumferential_points=step.circumferential_points,
                                        radial_points=step.radial_points,
                                        angle_of_attack_deg=step.angle_of_attack_deg,
                                        free_stream_velocity=step.free_stream_velocity,
                                    ),
                                ),
                                dmc.Card(
                                    withBorder=True,
                                    shadow="xs",
                                    p="md",
                                    children=html.Div(
                                        id=SIMULATION_JOB_STATUS_ID,
                                        children=job_status_display(step),
                                    ),
                                ),
                            ],
                        ),
                        width=4,
                    ),
                    dbc.Col(
                        dmc.Stack(
                            gap="lg",
                            children=[
                                dmc.Card(
                                    withBorder=True,
                                    shadow="sm",
                                    p="lg",
                                    children=simulation_tabs(
                                        log_file=log_file,
                                        mesh_figure=step.mesh_figure
                                        or {},  # Load from step - persists across navigation
                                        mesh_image_url=get_image_url_with_cache_bust(
                                            step, "mesh_png_handle"
                                        ),  # Cache-busting
                                        flow_figure=step.potential_flow_figure
                                        or {},  # Load from step - persists across navigation
                                        flow_image_url=flow_image_url,
                                    ),
                                )
                            ],
                        ),
                        width=8,
                    ),
                ],
            ),
        ]
    )


def job_status_display(step_or_job_id, submission_time=None, job_status=None) -> dmc.Stack:
    """Render a compact job status summary.

    Args:
        step_or_job_id: Either a SimulationStep object, or job_id string if submission_time and job_status are provided
        submission_time: Submission time string (if step_or_job_id is job_id)
        job_status: Job status string (if step_or_job_id is job_id)

    Returns:
        Mantine Stack component with job status information
    """
    if hasattr(step_or_job_id, "job_id"):  # It's a step object
        step = step_or_job_id
        job_id = step.job_id
        submission_time = step.submission_time
        job_status = step.job_status
    else:  # It's individual parameters
        job_id = step_or_job_id
        # submission_time and job_status are passed as arguments

    dash = "\u2014"
    return dmc.Stack(
        gap="xs",
        children=[
            dmc.Text("Job Status", fw=600),
            dmc.Text(f"Job ID: {job_id or dash}", size="sm"),
            dmc.Text(f"Submission time: {submission_time or dash}", size="sm"),
            dmc.Text(f"Status: {job_status or dash}", size="sm"),
        ],
    )
