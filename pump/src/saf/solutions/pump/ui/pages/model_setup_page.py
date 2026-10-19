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

"""Frontend of the model setup step."""

import logging
import os
from typing import Any

from ansys.saf.glow.client import DashClient, Deployment, callback
from ansys.saf.glow.solution import NO_ENTITY, MethodStatus
import dash
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, clientside_callback, dcc, html, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from saf.solutions.pump.solution.definition import PumpSolution
from saf.solutions.pump.solution.logic.constants import (
    BUILD_CASE_LOG_STREAM,
    BUILD_CASE_PROGRESS_STREAM,
    BUILD_CASE_STREAM,
    PROCESSOR_COUNT_RANGE,
)
from saf.solutions.pump.ui.feedback import (
    NotificationCopy,
    append_lines,
    closing_notification,
    log_viewer,
    opening_notification,
    parse_event,
    progress_panel,
    require_click,
    scroll_to_bottom,
    split_log,
)

dash.register_page(
    __name__,
    name="Model Setup",
    path_template="/projects/<project_id>/model-setup",
    icon_asset_name="boxicons:mesh-filled",
    order=1,
)

NOTIFICATION = NotificationCopy(
    notification_id="build-case-notification",
    running_title="Building case",
    success_title="Case ready",
    success_message="The Fluent case has been built. Continue to Operating Point.",
    failure_title="Case build failed",
)

LOG_VIEWPORT = "build-case-log-viewport"


logger = logging.getLogger(__name__)


def status_alert(step: Any) -> html.Div:
    """Render the post-build verdict, or nothing when no case has been built yet.

    The alert sits under the input card rather than on top of the results, where it was the
    first thing between the user and the mesh preview they came to look at.

    Parameters
    ----------
    step : Any
        Proxy of the setup step.
    """
    if step.mesh_image == NO_ENTITY:
        return html.Div()
    return html.Div(
        dmc.Alert(
            "The case is built and stored. You can now set an operating point.",
            title="Case ready",
            color="green",
            variant="light",
            icon=DashIconify(icon="carbon:checkmark-filled", width=20),
        )
    )


def results_panel(step: Any) -> html.Div:
    """Render the mesh preview and the detected zones.

    Parameters
    ----------
    step : Any
        Proxy of the setup step.

    Returns
    -------
    html.Div
        The rendered panel, or a placeholder when no case has been built yet.
    """
    if step.mesh_image == NO_ENTITY:
        return html.Div(
            dmc.Card(
                dmc.Stack(
                    [
                        dmc.ThemeIcon(
                            DashIconify(icon="carbon:3d-mpr-toggle", width=28),
                            size=56,
                            radius="xl",
                            variant="light",
                            color="gray",
                        ),
                        dmc.Text("No case yet", fw=600),
                        dmc.Text(
                            "Build the case to read the meshes and preview the assembled model.",
                            size="sm",
                            c="dimmed",
                            ta="center",
                        ),
                    ],
                    align="center",
                    gap="xs",
                ),
                withBorder=True,
                radius="md",
                p="xl",
            )
        )

    return html.Div(
        [
            dmc.Card(
                [
                    dmc.Group(
                        [
                            dmc.Title("Mesh preview", order=4),
                            dmc.Badge(f"{len(step.zone_names)} zones", variant="light"),
                        ],
                        justify="space-between",
                    ),
                    dmc.Space(h=12),
                    dmc.Image(
                        src=step.get_entity_url("mesh_image"),
                        alt="Impeller and volute mesh.",
                        radius="sm",
                        fit="contain",
                    ),
                ],
                withBorder=True,
                shadow="sm",
                radius="md",
                p="lg",
            ),
            dmc.Space(h=16),
            dmc.Accordion(
                [
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl("Detected zones"),
                            dmc.AccordionPanel(
                                dmc.Group(
                                    [
                                        dmc.Badge(name, variant="outline", color="gray")
                                        for name in step.zone_names
                                    ],
                                    gap="xs",
                                )
                            ),
                        ],
                        value="zones",
                    )
                ],
                variant="separated",
                radius="md",
            ),
        ]
    )


def processor_count_limit() -> int:
    """Return the largest processor count the input should offer.

    On the desktop deployment Fluent is launched on this very machine, so asking for more
    solver processes than there are cores oversubscribes it and makes the run slower, not
    faster. Every other deployment hands the job to a remote resource, where the core count
    of the browsing machine says nothing useful, so the declared range stands.

    ``DashClient.get_deployment_type`` reads the ``GLOW_DEPLOYMENT`` environment variable
    and falls back to ``Desktop`` when it is unset.

    Returns
    -------
    int
        Upper bound for the processor count input, never below the declared minimum.
    """
    if DashClient.get_deployment_type() != Deployment.Desktop:
        return PROCESSOR_COUNT_RANGE[1]
    available = os.cpu_count() or PROCESSOR_COUNT_RANGE[0]
    return max(PROCESSOR_COUNT_RANGE[0], min(available, PROCESSOR_COUNT_RANGE[1]))


def _settings_card(step: Any, is_running: bool) -> dmc.Card:
    """Render the compute settings and the action button.

    Parameters
    ----------
    step : Any
        Proxy of the setup step.
    is_running : bool
        Whether a build is already in flight, in which case the button stays busy.
    """
    maximum = processor_count_limit()
    return dmc.Card(
        [
            dmc.Title("Compute resources", order=4),
            dmc.Space(h=4),
            dmc.Text(
                "Fluent is launched locally with this many solver processes.",
                size="sm",
                c="dimmed",
            ),
            dmc.Space(h=16),
            dmc.NumberInput(
                label="Processor count",
                description=f"Up to {maximum} on this machine.",
                id="processor-count",
                value=min(step.processor_count, maximum),
                min=PROCESSOR_COUNT_RANGE[0],
                max=maximum,
                step=1,
                clampBehavior="strict",
                allowDecimal=False,
                disabled=is_running,
                leftSection=DashIconify(icon="carbon:chip", width=16),
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Build Case",
                id="build-case",
                leftSection=DashIconify(icon="carbon:play-filled-alt", width=18),
                fullWidth=True,
                radius="md",
                disabled=is_running,
                loading=is_running,
            ),
            # The single home of the progress bar. Nothing else in the application reports
            # percentages, so there is never a second, out-of-date copy on screen.
            html.Div(
                progress_panel(step.progress_stage, step.progress_fraction, running=is_running),
                id="build-case-progress",
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
        p="lg",
    )


def layout(project: PumpSolution) -> html.Div:
    """Layout of the model setup page."""
    step = project.steps.setup_step
    # A run started on an earlier visit is still going: the page must come back busy rather
    # than offering a button that would queue a second Fluent session.
    is_running = step.get_long_running_method_state("build_case").status == MethodStatus.Running
    log_lines = split_log(step.log_text)

    return html.Div(
        [
            dmc.Title("Model Setup", order=1),
            dmc.Space(h=6),
            dmc.Text(
                "Read the impeller and volute meshes, join them and configure the physics. This is "
                "done once per project; the operating point is set on the next page.",
                c="dimmed",
            ),
            dmc.Space(h=24),
            dmc.Grid(
                [
                    dmc.GridCol(
                        html.Div(
                            [
                                _settings_card(step, is_running),
                                dmc.Space(h=16),
                                html.Div(status_alert(step), id="setup-status"),
                            ]
                        ),
                        span={"base": 12, "md": 4},
                    ),
                    dmc.GridCol(
                        dmc.Tabs(
                            [
                                dmc.TabsList(
                                    [
                                        dmc.TabsTab(
                                            "Outputs",
                                            value="output",
                                            leftSection=DashIconify(icon="carbon:result", width=16),
                                        ),
                                        dmc.TabsTab(
                                            "Monitoring",
                                            value="logs",
                                            leftSection=DashIconify(icon="carbon:terminal", width=16),
                                        ),
                                    ]
                                ),
                                dmc.TabsPanel(
                                    html.Div(results_panel(step), id="setup-results"),
                                    value="output",
                                    pt="md",
                                ),
                                dmc.TabsPanel(
                                    html.Div(log_viewer(LOG_VIEWPORT, log_lines), id="build-case-log"),
                                    value="logs",
                                    pt="md",
                                ),
                            ],
                            id="setup-tabs",
                            value="logs" if is_running else "output",
                            variant="outline",
                            radius="md",
                        ),
                        span={"base": 12, "md": 8},
                    ),
                ],
                gutter="xl",
            ),
            dmc.Space(h=40),
            dcc.Store(id="build-case-log-store", data=log_lines),
            dcc.Store(id="build-case-scroll-sink"),
            # Three streams, three listeners. GLOW owns the termination stream, the step owns
            # the other two; keeping them apart means a log batch never has to be told apart
            # from a progress tick.
            DashClient.create_event_listener(step, stream_name=BUILD_CASE_STREAM, id="build-case-ws"),
            DashClient.create_event_listener(
                step, stream_name=BUILD_CASE_PROGRESS_STREAM, id="build-case-progress-ws"
            ),
            DashClient.create_event_listener(step, stream_name=BUILD_CASE_LOG_STREAM, id="build-case-log-ws"),
        ]
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("build-case-progress", "children", allow_duplicate=True),
    Output("build-case", "disabled", allow_duplicate=True),
    Output("build-case", "loading", allow_duplicate=True),
    Output("setup-tabs", "value"),
    Output("setup-status", "children"),
    Input("build-case", "n_clicks"),
    State("processor-count", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def start_build_case(
    n_clicks: int | None,
    processor_count: int,
    project: PumpSolution,
) -> tuple[list[dict], html.Div, bool, bool, str, html.Div]:
    """Start the long-running case build, open the toast and reveal the console."""
    require_click(n_clicks)
    step = project.steps.setup_step
    step.processor_count = int(processor_count)
    step.build_case()
    # The verdict of the previous build is about to be out of date, so it goes now rather
    # than sitting there green while a new case is being written.
    return opening_notification(NOTIFICATION), progress_panel(None, 0.0), True, True, "logs", html.Div()


@callback(
    Output("build-case-progress", "children", allow_duplicate=True),
    Input("build-case-progress-ws", "message"),
    prevent_initial_call=True,
)
def on_build_case_progress(message: dict) -> html.Div:
    """Move the progress bar under the button."""
    event = parse_event(message)
    if event.stage is None:
        raise PreventUpdate
    return progress_panel(event.stage, event.fraction)


@callback(
    Output("build-case-log", "children"),
    Output("build-case-log-store", "data"),
    Input("build-case-log-ws", "message"),
    State("build-case-log-store", "data"),
    prevent_initial_call=True,
)
def on_build_case_log(message: dict, buffered: list[str] | None) -> tuple[html.Div, list[str]]:
    """Append the newest Fluent console lines."""
    event = parse_event(message)
    if not event.lines:
        raise PreventUpdate
    lines = append_lines(buffered, event.lines)
    return log_viewer(LOG_VIEWPORT, lines), lines


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("build-case-progress", "children", allow_duplicate=True),
    Output("setup-results", "children", allow_duplicate=True),
    Output("build-case", "disabled", allow_duplicate=True),
    Output("build-case", "loading", allow_duplicate=True),
    Output("setup-tabs", "value", allow_duplicate=True),
    Output("setup-status", "children", allow_duplicate=True),
    Input("build-case-ws", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_build_case_finished(message: dict, project: PumpSolution) -> tuple[Any, Any, Any, bool, bool, Any, Any]:
    """Close out the run: clear the progress bar, free the button and show the results."""
    event = parse_event(message)
    if not event.finished:
        raise PreventUpdate
    step = project.steps.setup_step
    notifications = closing_notification(NOTIFICATION, event) or no_update
    results = results_panel(step) if event.succeeded else no_update
    status = status_alert(step) if event.succeeded else no_update
    tab = "output" if event.succeeded else no_update
    return notifications, html.Div(), results, False, False, tab, status


clientside_callback(
    scroll_to_bottom(LOG_VIEWPORT),
    Output("build-case-scroll-sink", "data"),
    Input("build-case-log", "children"),
    prevent_initial_call=True,
)
