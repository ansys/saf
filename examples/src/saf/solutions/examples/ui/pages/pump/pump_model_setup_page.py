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

import json
import logging
import os
import time
from typing import Any

from ansys.saf.glow.client import DashClient, Deployment, callback
from ansys.saf.glow.solution import NO_ENTITY, MethodStatus
import dash
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, clientside_callback, dcc, html, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.logic.pump.constants import (
    BUILD_CASE_LOG_STREAM,
    BUILD_CASE_PROGRESS_STREAM,
    BUILD_CASE_STREAM,
    PREPARE_SCENE_STREAM,
    PROCESSOR_COUNT_RANGE,
    START_VISOR_STREAM,
)
from saf.solutions.examples.ui.pages.pump.feedback import (
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
    path_template="/projects/<project_id>/pump-model-setup",
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

SCENE_NOTIFICATION = NotificationCopy(
    notification_id="prepare-scene-notification",
    running_title="Preparing the 3D view",
    running_message="The case is being converted for the 3D viewer.",
    success_title="3D view ready",
    success_message="The pump is displayed in the 3D view.",
    failure_title="3D view preparation failed",
    failure_message="The case could not be converted for the 3D viewer.",
)

LOG_VIEWPORT = "build-case-log-viewport"

# Must match the base path given to ``visordash.init_endpoints`` in ``ui/app.py``.
VISOR_BASE_PATH = os.getenv("GLOW_UI_PATH_PREFIX", "/").rstrip("/")


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


def viewer_message(icon: str, title: str, detail: str, color: str = "gray") -> dmc.Stack:
    """Render what the viewer slot shows while it has no live stream to show.

    Parameters
    ----------
    icon : str
        Iconify name.
    title : str
        One-line headline.
    detail : str
        Supporting sentence.
    color : str
        Mantine colour of the icon.
    """
    return dmc.Stack(
        [
            dmc.ThemeIcon(DashIconify(icon=icon, width=28), size=56, radius="xl", variant="light", color=color),
            dmc.Text(title, fw=600),
            dmc.Text(detail, size="sm", c="dimmed", ta="center"),
        ],
        align="center",
        justify="center",
        gap="xs",
        h="100%",
    )


def viewer_spinner(
    title: str = "Preparing the 3D view", detail: str = "The case is being converted for the viewer."
) -> dmc.Stack:
    """Render what the viewer slot shows while the 3D view is on its way."""
    print("viewer_spinner called")
    return dmc.Stack(
        [
            dmc.Loader(size="lg"),
            dmc.Text(title, fw=600),
            dmc.Text(detail, size="sm", c="dimmed", ta="center"),
        ],
        align="center",
        justify="center",
        gap="xs",
        h="100%",
    )


def viewer_card() -> dmc.Card:
    """Render the shell the Visor stream is embedded into.

    The shell is part of the page layout rather than of ``results_panel`` on purpose. The
    results are re-rendered wholesale when a build finishes, which would tear the viewer out
    of the DOM and drop its websocket; and before the first build ``results_panel`` returns a
    placeholder that contains no viewer slot at all, so the callback had no output to write
    to and Dash refused to fire it.
    """
    return dmc.Card(
        [
            dmc.Group(
                [
                    dmc.Title("3D view", order=4),
                    dmc.Badge("Visor", variant="light", color="indigo"),
                ],
                justify="space-between",
            ),
            dmc.Space(h=12),
            html.Div(
                viewer_spinner("Loading the 3D view", "Connecting to the Visor service."),
                id="model-setup-viewer-container",
                style={
                    "height": "520px",
                    "overflow": "hidden",
                    "borderRadius": "var(--mantine-radius-sm)",
                    "border": "1px solid var(--mantine-color-default-border)",
                },
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
        p="lg",
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


def layout(project: ExamplesSolution) -> html.Div:
    """Layout of the model setup page."""
    step = project.steps.pump_model_setup_step
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
                                    html.Div(
                                        [
                                            viewer_card(),
                                            dmc.Space(h=16),
                                            html.Div(results_panel(step), id="setup-results"),
                                        ]
                                    ),
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
            dcc.Store(id="visor-scene-sink"),
            # The viewer is embedded off this store rather than off the URL: the URL belongs
            # to the whole application, so a callback listening to it would also fire on pages
            # where the viewer slot does not exist and Dash would refuse to dispatch it. A
            # store created here exists only while this page is mounted, and a fresh value on
            # every visit is what makes the callback fire again after navigating away and back.
            dcc.Store(id="visor-boot", data=time.monotonic()),
            # Three streams, three listeners. GLOW owns the termination stream, the step owns
            # the other two; keeping them apart means a log batch never has to be told apart
            # from a progress tick.
            DashClient.create_event_listener(step, stream_name=BUILD_CASE_STREAM, id="build-case-ws"),
            DashClient.create_event_listener(
                step, stream_name=BUILD_CASE_PROGRESS_STREAM, id="build-case-progress-ws"
            ),
            DashClient.create_event_listener(step, stream_name=BUILD_CASE_LOG_STREAM, id="build-case-log-ws"),
            # The Build Case button starts the Visor server. This page listens to its start so
            # that the viewer is embedded as soon as the server comes up, without reloading.
            DashClient.create_event_listener(step, stream_name=START_VISOR_STREAM, id="model-setup-visor-ws"),
            DashClient.create_event_listener(step, stream_name=PREPARE_SCENE_STREAM, id="prepare-scene-ws"),
        ]
    )


def _browser_visor_host(host: str) -> str:
    """Return a host the browser can open.

    The Visor process often binds ``0.0.0.0``. That address is not a destination the
    browser can connect to, so the widget has to use localhost on this machine.
    """
    if host in {"", "0.0.0.0", "::"}:
        return "localhost"
    return host


def visor_frame(host: str, port: int) -> html.Iframe:
    """Return an isolated viewer document connected to the Visor server.

    Same approach as the SAF Visor instance example: the viewer bundle served by
    ``visordash.init_endpoints`` runs inside its own document instead of being mounted as a
    React component in the page. Its global reset CSS therefore cannot leak into the Mantine
    inputs, and every render starts from a clean document with a fresh websocket.
    """
    # Escaping ``<`` stops a value from closing the inline <script> element early.
    viewer_args = json.dumps(
        {"host": host, "port": port, "basePath": VISOR_BASE_PATH, "aspectRatio": 1.6, "pixelDensity": 800}
    ).replace("<", "\\u003c")
    src_doc = f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="{VISOR_BASE_PATH}/visordash/css.css">
</head>
<body style="margin: 0; width: 100vw; height: 100vh; overflow: hidden;">
    <div id="VisorContainer" style="width: 100%; height: 100%;"></div>
    <script>window.__visorArgs = {viewer_args};</script>
    <script type="module" src="{VISOR_BASE_PATH}/visordash/js.js"></script>
</body>
</html>"""
    print(f"visor_frame called with host {host}, port {port}")
    print(src_doc)
    return html.Iframe(
        id="model-setup-visor-frame",
        srcDoc=src_doc,
        title="3D view of the pump",
        style={"width": "100%", "height": "100%", "border": "0", "display": "block"},
    )


def scene_viewer(step: Any) -> tuple[Any, bool]:
    """Load the prepared scene into Visor and return the viewer that streams it.

    The scene is loaded before the viewer document is created, so the viewer connects to a
    server that already holds the pump instead of racing the update. The Visor server is
    shared with the Operating Point page, which loads its own scene into it, so the pump is
    loaded again on every visit.

    Returns
    -------
    tuple
        The viewer slot content, and whether the scene is now on screen. ``False`` lets
        :func:`embed_visor_viewer` try again when the Visor server comes up.
    """
    if not step.visor_started or not step.visor_port:
        visor_status = step.get_long_running_method_state("start_visor").status
        if visor_status == MethodStatus.Failed:
            return (
                viewer_message(
                    "carbon:warning-alt",
                    "3D viewer unavailable",
                    "The Visor server could not be started. Build the case again to retry.",
                    color="red",
                ),
                False,
            )
        if visor_status != MethodStatus.Running:
            return (
                viewer_message(
                    "carbon:3d-mpr-toggle", "3D viewer not started", "Build the case to start the Visor service."
                ),
                False,
            )
        return viewer_spinner("Starting the 3D viewer", "Connecting to the Visor service."), False
    try:
        step.show_scene()
    except Exception:
        logger.exception("Could not load the pump scene into Visor.")
        return (
            viewer_message(
                "carbon:warning-alt", "3D view unavailable", "The scene could not be loaded into Visor.", color="red"
            ),
            False,
        )
    print(f"Visor host {step.visor_host}, port {step.visor_port}")
    return visor_frame(_browser_visor_host(step.visor_host), step.visor_port), True


@callback(
    Output("model-setup-viewer-container", "children"),
    Output("visor-scene-sink", "data"),
    Input("visor-boot", "data"),
    Input("model-setup-visor-ws", "message"),
    State("visor-scene-sink", "data"),
    State("url", "pathname"),
)
def embed_visor_viewer(
    _boot: float,
    _message: dict | None,
    scene_loaded: bool | None,
    project: ExamplesSolution,
) -> tuple[Any, Any]:
    """Show the prepared scene when the page opens and again when the Visor server comes up.

    Once the scene is on screen the callback stops, so later stream messages do not tear the
    widget down and drop its websocket.
    """
    print("embed_visor_viewer called")
    if scene_loaded:
        raise PreventUpdate
    step = project.steps.pump_model_setup_step
    # The page was reopened while the conversion is still going: its end is caught by
    # on_prepare_scene_finished, which is listening on this page too.
    if step.get_long_running_method_state("prepare_scene").status == MethodStatus.Running:
        return viewer_spinner(), no_update
    if step.scene_file == NO_ENTITY:
        return (
            viewer_message(
                "carbon:3d-mpr-toggle", "No 3D model yet", "Build the case to display the pump in 3D."
            ),
            no_update,
        )
    return scene_viewer(step)


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("model-setup-viewer-container", "children", allow_duplicate=True),
    Output("visor-scene-sink", "data", allow_duplicate=True),
    Input("prepare-scene-ws", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_prepare_scene_finished(message: dict, project: ExamplesSolution) -> tuple[Any, Any, Any]:
    """Close the toast and replace the spinner with the scene, or with the reason it failed."""
    event = parse_event(message)
    if not event.finished:
        raise PreventUpdate
    notifications = closing_notification(SCENE_NOTIFICATION, event) or no_update
    if not event.succeeded:
        failed = viewer_message(
            "carbon:warning-alt", "3D view unavailable", "The case could not be converted.", color="red"
        )
        return notifications, failed, False
    viewer, loaded = scene_viewer(project.steps.pump_model_setup_step)
    return notifications, viewer, loaded


def _ensure_visor_started(step: Any) -> None:
    """Provision the Visor instance through the instance management transaction.

    The server is booted alongside the case build so that it is up by the time the scene is
    prepared. A server already running, or still booting, is left alone: starting a second
    one would leave an orphan behind. A Visor that cannot be started costs the 3D view and
    nothing else, so it must not prevent the build.
    """
    if step.visor_started or step.get_long_running_method_state("start_visor").status == MethodStatus.Running:
        return
    try:
        step.start_visor()
    except Exception:
        logger.exception("Could not start the Visor server.")


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
    project: ExamplesSolution,
) -> tuple[list[dict], html.Div, bool, bool, str, html.Div]:
    """Start the long-running case build, open the toast and reveal the console."""
    require_click(n_clicks)
    step = project.steps.pump_model_setup_step
    _ensure_visor_started(step)
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
    Output("model-setup-viewer-container", "children", allow_duplicate=True),
    Output("visor-scene-sink", "data", allow_duplicate=True),
    Input("build-case-ws", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_build_case_finished(
    message: dict, project: ExamplesSolution
) -> tuple[Any, Any, Any, bool, bool, Any, Any, Any, Any]:
    """Close out the run: clear the progress bar, free the button and show the results.

    A successful build also starts converting the case for the 3D viewer. That is done here
    rather than in a second callback on the same stream: Dash tells duplicate outputs apart
    by hashing the callback Inputs, so two callbacks listening to ``build-case-ws`` alone
    would collide on ``notification-container``.
    """
    event = parse_event(message)
    if not event.finished:
        raise PreventUpdate
    step = project.steps.pump_model_setup_step
    notifications = closing_notification(NOTIFICATION, event) or no_update
    results = results_panel(step) if event.succeeded else no_update
    status = status_alert(step) if event.succeeded else no_update
    tab = "output" if event.succeeded else no_update
    if not event.succeeded:
        return notifications, html.Div(), results, False, False, tab, status, no_update, no_update
    step.prepare_scene()
    notifications = (closing_notification(NOTIFICATION, event) or []) + opening_notification(SCENE_NOTIFICATION)
    # The scene on screen belongs to the previous case; clearing the flag lets the next Visor
    # start, if any, embed the new one.
    return notifications, html.Div(), results, False, False, tab, status, viewer_spinner(), False


clientside_callback(
    scroll_to_bottom(LOG_VIEWPORT),
    Output("build-case-scroll-sink", "data"),
    Input("build-case-log", "children"),
    prevent_initial_call=True,
)
