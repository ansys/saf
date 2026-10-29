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

"""Frontend of the operating point step."""

import json
import logging
import os
import time
from typing import Any

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import NO_ENTITY, MethodStatus
import dash
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, clientside_callback, dcc, html, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.logic.pump.constants import (
    CONTOUR_IMAGE_NAME,
    DENSITY_WATER,
    IMPELLER_SPEED_RANGE,
    ITERATION_COUNT_RANGE,
    MASS_FLOW_RATE_RANGE,
    PREPARE_SOLVED_SCENE_STREAM,
    RUN_SIMULATION_HISTORY_STREAM,
    RUN_SIMULATION_LOG_STREAM,
    RUN_SIMULATION_PROGRESS_STREAM,
    RUN_SIMULATION_STREAM,
    SOLVED_CASE_FILE_NAME,
    START_VISOR_STREAM,
    TIME_STEP_SCALE_FACTOR_RANGE,
)
from saf.solutions.examples.ui.pages.pump.feedback import (
    append_lines,
    log_viewer,
    opening_notification,
    parse_event,
    progress_panel,
    require_click,
    scroll_to_bottom,
    split_log,
)
from saf.solutions.examples.ui.pages.pump.shell_notifications import RUN_SIMULATION_NOTIFICATION

dash.register_page(
    __name__,
    name="Operating Point",
    path_template="/projects/<project_id>/operating-point",
    icon_asset_name="at-icons:wind",
    order=2,
)

LOG_VIEWPORT = "run-simulation-log-viewport"

# Must match the base path given to ``visordash.init_endpoints`` in ``ui/app.py``.
VISOR_BASE_PATH = os.getenv("GLOW_UI_PATH_PREFIX", "/").rstrip("/")


logger = logging.getLogger(__name__)

_SECONDS_PER_HOUR = 3600.0

_PARAMETER_ROWS = [
    ["Outlet", "mass_flow_rate", "kg/s", "Duty point: how much water the pump must deliver."],
    ["Impeller", "impeller_speed_rpm", "rpm", "Rotational speed of the moving reference frame."],
]


def parameters_panel() -> html.Div:
    """Render the annotated sketch that explains what each input controls."""
    return html.Div(
        [
            dmc.Card(
                [
                    dmc.Title("What the model represents", order=4),
                    dmc.Space(h=4),
                    dmc.Text(
                        "Water enters the suction eye, the rotating impeller adds energy to it, and the "
                        "stationary volute collects the flow and converts velocity into pressure.",
                        size="sm",
                        c="dimmed",
                    ),
                    dmc.Space(h=12),
                    dmc.Image(
                        src=dash.get_asset_url("images/pump-parameters.svg"),
                        alt=(
                            "Sketch of the pump showing the inlet, impeller, volute, turbo interface "
                            "and outlet, each labelled with the parameter that controls it."
                        ),
                        fit="contain",
                    ),
                ],
                withBorder=True,
                shadow="sm",
                radius="md",
                p="lg",
            ),
            dmc.Space(h=16),
            dmc.Table(
                striped=True,
                withTableBorder=True,
                data={
                    "head": ["Location", "Parameter", "Unit", "Effect"],
                    "body": _PARAMETER_ROWS,
                },
            ),
        ]
    )


def live_convergence(step: Any, is_running: bool) -> html.Div:
    """Render the convergence curve of the current run, however far along it is.

    The solve publishes the samples it has read back from Fluent's report files after every
    iteration chunk, and the step persists them, so a page opened or reloaded mid-run picks
    up the curve where it stands instead of showing an empty placeholder. The curve stays
    on the Monitoring tab once the run ends too, so coming back to it still answers "how did
    that solve behave?"; only the "Live" badge goes.

    Parameters
    ----------
    step : Any
        Proxy of the solve step.
    is_running : bool
        Whether a solve is in flight, which decides the badge.
    """
    if not step.convergence_history:
        return html.Div()
    return html.Div([convergence_card(step.convergence_history, live=is_running), dmc.Space(h=20)])


def status_alert(step: Any) -> html.Div:
    """Render the post-run convergence verdict, or nothing before the first run.

    The verdict sits under the input card rather than on top of the results, where it stood
    between the user and the numbers they came to read.

    Parameters
    ----------
    step : Any
        Proxy of the solve step.
    """
    if step.contour_image == NO_ENTITY:
        return html.Div()
    if step.converged:
        return html.Div(
            dmc.Alert(
                "The residuals met the convergence criteria, so the numbers have settled.",
                title="Converged",
                color="green",
                variant="light",
                icon=DashIconify(icon="carbon:checkmark-filled", width=20),
            )
        )
    return html.Div(
        dmc.Alert(
            "The run stopped at the iteration limit, so the results may still be drifting. "
            "Raise the iteration count to tighten them.",
            title="Iteration limit reached",
            color="yellow",
            variant="light",
            icon=DashIconify(icon="carbon:warning-alt", width=20),
        )
    )


def flow_rate_hint(mass_flow_rate: float) -> float:
    """Convert a mass flow rate in kg/s to m³/h, for the input helper text.

    Parameters
    ----------
    mass_flow_rate : float
        Mass flow rate, in kg/s.

    Returns
    -------
    float
        Volumetric flow rate, in m³/h.
    """
    return mass_flow_rate / DENSITY_WATER * _SECONDS_PER_HOUR


def _kpi_card(icon: str, title: str, value: str, unit: str, color: str) -> dmc.Card:
    """Render one headline number."""
    return dmc.Card(
        [
            dmc.Group(
                [
                    dmc.Text(title, size="sm", c="dimmed"),
                    dmc.ThemeIcon(
                        DashIconify(icon=icon, width=16), variant="light", color=color, size="md", radius="md"
                    ),
                ],
                justify="space-between",
                wrap="nowrap",
            ),
            dmc.Space(h=8),
            dmc.Group(
                [dmc.Title(value, order=2), dmc.Text(unit, size="sm", c="dimmed")],
                gap=6,
                align="baseline",
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
        p="md",
    )


def convergence_card(history: list[dict[str, float]], live: bool = False) -> dmc.Card:
    """Render the head and outlet-pressure history.

    Parameters
    ----------
    history : list[dict[str, float]]
        ``iteration`` / ``head`` / ``outlet_total_pressure`` rows.
    live : bool
        Whether the solve is still running, in which case the card says so and the curve is
        only as long as the iterations completed so far.
    """
    return dmc.Card(
        [
            dmc.Group(
                [
                    dmc.Title("Convergence", order=4),
                    dmc.Badge(
                        "Live",
                        color="blue",
                        variant="light",
                        leftSection=DashIconify(icon="carbon:circle-filled", width=8),
                    )
                    if live
                    else html.Div(),
                ],
                justify="space-between",
            ),
            dmc.Space(h=12),
            dmc.LineChart(
                h=280,
                data=history,
                dataKey="iteration",
                withDots=False,
                withRightYAxis=True,
                curveType="linear",
                withLegend=True,
                # The built-in rightYAxisLabel is drawn at angle +90, so it reads downwards,
                # and the anchor the chart picks for it leaves the text hanging off one end of
                # the axis. Passing the label through rightYAxisProps gives control of both:
                # -90 makes it read upwards like the left one, and a CSS textAnchor beats the
                # SVG presentation attribute, so the text recentres on the axis.
                rightYAxisProps={
                    "label": {
                        "value": "Outlet total pressure (Pa)",
                        "position": "insideRight",
                        "angle": -90,
                        "offset": -5,
                        "fontSize": 12,
                        "style": {"textAnchor": "middle", "fill": "currentColor"},
                    }
                },
                yAxisLabel="Head (m)",
                xAxisLabel="Iteration",
                series=[
                    {"name": "head", "color": "indigo.6", "label": "Head"},
                    {
                        "name": "outlet_total_pressure",
                        "color": "teal.6",
                        "label": "Outlet total pressure",
                        "yAxisId": "right",
                    },
                ],
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
        p="lg",
    )


def _download_links(step: Any) -> dmc.Group:
    """Render direct links to the stored artefacts.

    The blob endpoints are served by GLOW, so the browser streams the files itself instead
    of routing hundreds of megabytes of case data through the Dash process.
    """
    return dmc.Group(
        [
            html.A(
                dmc.Button(
                    "Download solved case",
                    variant="outline",
                    radius="md",
                    leftSection=DashIconify(icon="carbon:download", width=18),
                ),
                href=step.get_entity_url("solved_case_file"),
                download=SOLVED_CASE_FILE_NAME,
            ),
            html.A(
                dmc.Button(
                    "Download contour",
                    variant="outline",
                    radius="md",
                    leftSection=DashIconify(icon="carbon:image", width=18),
                ),
                href=step.get_entity_url("contour_image"),
                download=CONTOUR_IMAGE_NAME,
            ),
        ],
        gap="sm",
    )


def results_panel(step: Any) -> html.Div:
    """Render the KPIs, or a placeholder when no run has completed yet.

    The 3D viewer sits between this panel and :func:`results_details` in the layout, so the
    rest of the results lives there.

    Parameters
    ----------
    step : Any
        Proxy of the solve step.

    Returns
    -------
    html.Div
        The rendered panel, or a placeholder when no run has completed yet.
    """
    if step.contour_image == NO_ENTITY:
        return html.Div(
            dmc.Card(
                dmc.Stack(
                    [
                        dmc.ThemeIcon(
                            DashIconify(icon="carbon:chart-line-data", width=28),
                            size=56,
                            radius="xl",
                            variant="light",
                            color="gray",
                        ),
                        dmc.Text("No results yet", fw=600),
                        dmc.Text(
                            "Choose an operating point and run the simulation to see the pump "
                            "performance here.",
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
        dmc.SimpleGrid(
            [
                _kpi_card("ant-design:column-height-outlined", "Pump head", f"{step.pump_head_m:.2f}", "m", "indigo"),
                _kpi_card(
                    "carbon:meter",
                    "Hydraulic efficiency",
                    f"{step.hydraulic_efficiency * 100:.1f}",
                    "%",
                    "teal",
                ),
                _kpi_card("carbon:flash", "Shaft power", f"{step.shaft_power_w / 1000.0:.2f}", "kW", "orange"),
            ],
            cols={"base": 1, "sm": 3},
            spacing="md",
        )
    )


def results_details(step: Any) -> html.Div:
    """Render the contour, the secondary results and the downloads, or nothing before a run.

    Parameters
    ----------
    step : Any
        Proxy of the solve step.
    """
    if step.contour_image == NO_ENTITY:
        return html.Div()

    secondary_rows = [
        ["Pressure rise", f"{step.pressure_rise_pa / 1000.0:,.2f}", "kPa"],
        ["Blade torque", f"{step.blade_torque_nm:,.2f}", "N·m"],
        ["Volumetric flow", f"{step.volumetric_flow_m3h:,.1f}", "m³/h"],
        ["Inlet total pressure", f"{step.inlet_total_pressure_pa:,.1f}", "Pa"],
        ["Outlet total pressure", f"{step.outlet_total_pressure_pa:,.1f}", "Pa"],
        ["Blade surface pressure", f"{step.blade_pressure_pa:,.1f}", "Pa"],
    ]

    return html.Div(
        [
            dmc.Space(h=20),
            dmc.Card(
                [
                    dmc.Title("Static pressure contour", order=4),
                    dmc.Space(h=12),
                    dmc.Image(
                        src=step.get_entity_url("contour_image"),
                        alt="Static pressure contour on the mid plane.",
                        radius="sm",
                        fit="contain",
                    ),
                ],
                withBorder=True,
                shadow="sm",
                radius="md",
                p="lg",
            ),
            dmc.Space(h=20),
            dmc.Accordion(
                [
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl("Secondary results"),
                            dmc.AccordionPanel(
                                dmc.Table(
                                    striped=True,
                                    withTableBorder=True,
                                    data={"head": ["Quantity", "Value", "Unit"], "body": secondary_rows},
                                )
                            ),
                        ],
                        value="secondary",
                    )
                ],
                variant="separated",
                radius="md",
            ),
            dmc.Space(h=20),
            _download_links(step),
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
    title: str = "Preparing the 3D view", detail: str = "The solved case is being converted for the viewer."
) -> dmc.Stack:
    """Render what the viewer slot shows while the 3D view is on its way."""
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

    As on the model setup page, the shell is part of the page layout rather than of
    ``results_panel``: the results are re-rendered wholesale when a run finishes, which would
    tear the viewer out of the DOM and drop its websocket.
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
                id="operating-point-viewer-container",
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


def _inputs_card(step: Any, case_is_ready: bool, is_running: bool) -> dmc.Card:
    """Render the operating point form.

    Parameters
    ----------
    step : Any
        Proxy of the solve step.
    case_is_ready : bool
        Whether a case exists to solve.
    is_running : bool
        Whether a solve is already in flight, in which case the button stays busy.
    """
    return dmc.Card(
        [
            dmc.Title("Operating point", order=4),
            dmc.Space(h=16),
            dmc.NumberInput(
                label="Impeller speed",
                description="Head rises with the square of speed, power with the cube.",
                id="impeller-speed",
                value=step.impeller_speed_rpm,
                min=IMPELLER_SPEED_RANGE[0],
                max=IMPELLER_SPEED_RANGE[1],
                step=50,
                clampBehavior="strict",
                disabled=is_running,
                suffix=" rpm",
                leftSection=DashIconify(icon="carbon:rotate-360", width=16),
            ),
            dmc.Space(h=16),
            dmc.NumberInput(
                label="Mass flow rate",
                description="The duty point. Head falls as you demand more flow.",
                id="mass-flow-rate",
                value=step.mass_flow_rate,
                min=MASS_FLOW_RATE_RANGE[0],
                max=MASS_FLOW_RATE_RANGE[1],
                step=5,
                clampBehavior="strict",
                disabled=is_running,
                suffix=" kg/s",
                leftSection=DashIconify(icon="carbon:flow", width=16),
            ),
            dmc.Space(h=4),
            dmc.Text(
                f"≈ {flow_rate_hint(step.mass_flow_rate):.0f} m³/h",
                id="flow-rate-hint",
                size="xs",
                c="dimmed",
            ),
            dmc.Space(h=16),
            dmc.Accordion(
                [
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl("Advanced solver settings"),
                            dmc.AccordionPanel(
                                [
                                    dmc.NumberInput(
                                        label="Iteration count",
                                        description="More iterations converge further but take longer.",
                                        id="iteration-count",
                                        value=step.iteration_count,
                                        min=ITERATION_COUNT_RANGE[0],
                                        max=ITERATION_COUNT_RANGE[1],
                                        step=50,
                                        clampBehavior="strict",
                                        allowDecimal=False,
                                        disabled=is_running,
                                    ),
                                    dmc.Space(h=16),
                                    dmc.NumberInput(
                                        label="Pseudo-time step scale factor",
                                        description="Lower values are slower but more robust.",
                                        id="time-step-scale-factor",
                                        value=step.time_step_scale_factor,
                                        min=TIME_STEP_SCALE_FACTOR_RANGE[0],
                                        max=TIME_STEP_SCALE_FACTOR_RANGE[1],
                                        step=1,
                                        clampBehavior="strict",
                                        disabled=is_running,
                                    ),
                                ]
                            ),
                        ],
                        value="advanced",
                    )
                ],
                variant="separated",
                radius="md",
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Run Simulation",
                id="run-simulation",
                disabled=is_running or not case_is_ready,
                loading=is_running,
                leftSection=DashIconify(icon="carbon:play-filled-alt", width=18),
                fullWidth=True,
                radius="md",
            ),
            # The single home of the progress bar. Nothing else in the application reports
            # percentages, so there is never a second, out-of-date copy on screen.
            html.Div(
                progress_panel(step.progress_stage, step.progress_fraction, running=is_running),
                id="run-simulation-progress",
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
        p="lg",
    )


def layout(project: ExamplesSolution) -> html.Div:
    """Layout of the operating point page."""
    setup_step = project.steps.pump_model_setup_step
    solve_step = project.steps.pump_solve_step
    case_is_ready = setup_step.case_file != NO_ENTITY
    # A run started on an earlier visit is still going: the page must come back busy rather
    # than offering a button that would queue a second Fluent session.
    is_running = solve_step.get_long_running_method_state("run_simulation").status == MethodStatus.Running
    log_lines = split_log(solve_step.log_text)
    # Coming back to the page lands on whatever is worth looking at: the console and the live
    # curve while a solve is in flight, the results once there are some, and the sketch of the
    # parameters when nothing has run yet and the Outputs tab holds only a placeholder.
    if is_running:
        default_tab = "logs"
    elif solve_step.contour_image != NO_ENTITY:
        default_tab = "output"
    else:
        default_tab = "parameters"

    guard = (
        html.Div()
        if case_is_ready
        else html.Div(
            [
                dmc.Alert(
                    "Build the case on the Model Setup page before running a simulation.",
                    title="No case available",
                    color="yellow",
                    variant="light",
                    icon=DashIconify(icon="carbon:warning-alt", width=20),
                ),
                dmc.Space(h=16),
            ]
        )
    )

    return html.Div(
        [
            dmc.Title("Operating Point & Results", order=1),
            dmc.Space(h=6),
            dmc.Text(
                "Pick a duty point, solve the frozen-rotor case and read the pump performance.",
                c="dimmed",
            ),
            dmc.Space(h=24),
            guard,
            dmc.Grid(
                [
                    dmc.GridCol(
                        html.Div(
                            [
                                _inputs_card(solve_step, case_is_ready, is_running),
                                dmc.Space(h=16),
                                html.Div(status_alert(solve_step), id="solve-status"),
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
                                            "Parameters",
                                            value="parameters",
                                            leftSection=DashIconify(icon="carbon:image", width=16),
                                        ),
                                        dmc.TabsTab(
                                            "Monitoring",
                                            value="logs",
                                            leftSection=DashIconify(icon="carbon:terminal", width=16),
                                        ),
                                        dmc.TabsTab(
                                            "Outputs",
                                            value="output",
                                            leftSection=DashIconify(icon="carbon:result", width=16),
                                        ),
                                    ]
                                ),
                                dmc.TabsPanel(parameters_panel(), value="parameters", pt="md"),
                                # The live curve belongs next to the console it is being read
                                # from: both answer "how is the run going?", and the Outputs tab
                                # stays reserved for the finished numbers.
                                dmc.TabsPanel(
                                    html.Div(
                                        [
                                            html.Div(
                                                live_convergence(solve_step, is_running),
                                                id="live-convergence",
                                            ),
                                            html.Div(log_viewer(LOG_VIEWPORT, log_lines), id="run-simulation-log"),
                                        ]
                                    ),
                                    value="logs",
                                    pt="md",
                                ),
                                dmc.TabsPanel(
                                    html.Div(
                                        [
                                            html.Div(results_panel(solve_step), id="results-panel"),
                                            dmc.Space(h=20),
                                            viewer_card(),
                                            html.Div(results_details(solve_step), id="results-details"),
                                        ]
                                    ),
                                    value="output",
                                    pt="md",
                                ),
                            ],
                            id="solve-tabs",
                            value=default_tab,
                            variant="outline",
                            radius="md",
                        ),
                        span={"base": 12, "md": 8},
                    ),
                ],
                gutter="xl",
            ),
            dmc.Space(h=40),
            dcc.Store(id="run-simulation-log-store", data=log_lines),
            dcc.Store(id="run-simulation-scroll-sink"),
            dcc.Store(id="operating-point-scene-sink"),
            # Same mechanism as the model setup page: a fresh value on every visit makes the
            # viewer callback fire again after navigating away and back.
            dcc.Store(id="operating-point-visor-boot", data=time.monotonic()),
            # Four streams, four listeners. GLOW owns the termination stream, the step owns
            # the other three; keeping them apart means a log batch never has to be told apart
            # from a progress tick or a convergence update.
            DashClient.create_event_listener(
                solve_step, stream_name=RUN_SIMULATION_STREAM, id="run-simulation-ws"
            ),
            DashClient.create_event_listener(
                solve_step, stream_name=RUN_SIMULATION_PROGRESS_STREAM, id="run-simulation-progress-ws"
            ),
            DashClient.create_event_listener(
                solve_step, stream_name=RUN_SIMULATION_LOG_STREAM, id="run-simulation-log-ws"
            ),
            DashClient.create_event_listener(
                solve_step, stream_name=RUN_SIMULATION_HISTORY_STREAM, id="run-simulation-history-ws"
            ),
            # The Visor server is started and owned by the setup step; this page listens to its
            # start under its own identifier, like the model setup page does.
            DashClient.create_event_listener(
                setup_step, stream_name=START_VISOR_STREAM, id="operating-point-visor-ws"
            ),
            DashClient.create_event_listener(
                solve_step, stream_name=PREPARE_SOLVED_SCENE_STREAM, id="prepare-solved-scene-ws"
            ),
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

    Same approach as the SAF Visor instance example, and duplicated from the model setup
    page because importing another page module would register its callbacks twice. The
    viewer bundle served by ``visordash.init_endpoints`` runs inside its own document, so its
    global reset CSS cannot leak into the Mantine inputs, and every render starts from a
    clean document with a fresh websocket.
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
    return html.Iframe(
        id="operating-point-visor-frame",
        srcDoc=src_doc,
        title="3D view of the solved pump",
        style={"width": "100%", "height": "100%", "border": "0", "display": "block"},
    )


def scene_viewer(project: ExamplesSolution) -> tuple[Any, bool]:
    """Load the solved scene into Visor and return the viewer that streams it.

    The scene is loaded before the viewer document is created, so the viewer connects to a
    server that already holds the solved pump instead of racing the update. The Visor server
    is shared with the Model Setup page, which loads its own scene into it, so the solved
    pump is loaded again on every visit.

    Returns
    -------
    tuple
        The viewer slot content, and whether the scene is now on screen. ``False`` lets
        :func:`embed_visor_viewer` try again when the Visor server comes up.
    """
    setup_step = project.steps.pump_model_setup_step
    if not setup_step.visor_started or not setup_step.visor_port:
        visor_status = setup_step.get_long_running_method_state("start_visor").status
        if visor_status == MethodStatus.Failed:
            return (
                viewer_message(
                    "carbon:warning-alt",
                    "3D viewer unavailable",
                    "The Visor server could not be started. Build the case again on Model Setup to retry.",
                    color="red",
                ),
                False,
            )
        if visor_status != MethodStatus.Running:
            return (
                viewer_message(
                    "carbon:3d-mpr-toggle",
                    "3D viewer not started",
                    "Build the case on Model Setup to start the Visor service.",
                ),
                False,
            )
        return viewer_spinner("Starting the 3D viewer", "Connecting to the Visor service."), False
    try:
        project.steps.pump_solve_step.show_solved_scene()
    except Exception:
        logger.exception("Could not load the solved pump scene into Visor.")
        return (
            viewer_message(
                "carbon:warning-alt", "3D view unavailable", "The scene could not be loaded into Visor.", color="red"
            ),
            False,
        )
    return visor_frame(_browser_visor_host(setup_step.visor_host), setup_step.visor_port), True


@callback(
    Output("operating-point-viewer-container", "children"),
    Output("operating-point-scene-sink", "data"),
    Input("operating-point-visor-boot", "data"),
    Input("operating-point-visor-ws", "message"),
    State("operating-point-scene-sink", "data"),
    State("url", "pathname"),
)
def embed_visor_viewer(
    _boot: float,
    _message: dict | None,
    scene_loaded: bool | None,
    project: ExamplesSolution,
) -> tuple[Any, Any]:
    """Show the solved scene when the page opens and again when the Visor server comes up.

    Once the scene is on screen the callback stops, so later stream messages do not tear the
    widget down and drop its websocket.
    """
    if scene_loaded:
        raise PreventUpdate
    step = project.steps.pump_solve_step
    # The page was reopened while the conversion is still going: its end is caught by
    # on_prepare_solved_scene_finished, which is listening on this page too.
    if step.get_long_running_method_state("prepare_solved_scene").status == MethodStatus.Running:
        return viewer_spinner(), no_update
    if step.solved_scene_file == NO_ENTITY:
        return (
            viewer_message(
                "carbon:3d-mpr-toggle", "No 3D results yet", "Run the simulation to display the solved pump in 3D."
            ),
            no_update,
        )
    return scene_viewer(project)


@callback(
    Output("operating-point-viewer-container", "children", allow_duplicate=True),
    Output("operating-point-scene-sink", "data", allow_duplicate=True),
    Input("prepare-solved-scene-ws", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_prepare_solved_scene_finished(message: dict, project: ExamplesSolution) -> tuple[Any, Any]:
    """Replace the spinner with the scene, or with the reason it failed.

    The toast is closed by the shell, which keeps listening once the user leaves this page.
    """
    event = parse_event(message)
    if not event.finished:
        raise PreventUpdate
    if not event.succeeded:
        failed = viewer_message(
            "carbon:warning-alt", "3D view unavailable", "The solved case could not be converted.", color="red"
        )
        return failed, False
    return scene_viewer(project)


@callback(
    Output("flow-rate-hint", "children"),
    Input("mass-flow-rate", "value"),
    prevent_initial_call=True,
)
def update_flow_rate_hint(mass_flow_rate: float | None) -> str:
    """Keep the m³/h hint in step with the kg/s input."""
    if mass_flow_rate is None:
        return ""
    return f"≈ {flow_rate_hint(float(mass_flow_rate)):.0f} m³/h"


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("run-simulation-progress", "children"),
    Output("run-simulation", "disabled"),
    Output("run-simulation", "loading"),
    Output("solve-tabs", "value"),
    Output("solve-status", "children"),
    Output("live-convergence", "children"),
    Input("run-simulation", "n_clicks"),
    State("impeller-speed", "value"),
    State("mass-flow-rate", "value"),
    State("iteration-count", "value"),
    State("time-step-scale-factor", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def start_run_simulation(
    n_clicks: int | None,
    impeller_speed: float,
    mass_flow_rate: float,
    iteration_count: int,
    time_step_scale_factor: float,
    project: ExamplesSolution,
) -> tuple[list[dict], html.Div, bool, bool, str, html.Div, html.Div]:
    """Start the long-running solve, open the toast and reveal the console."""
    require_click(n_clicks)
    step = project.steps.pump_solve_step
    step.set_fields(
        {
            "impeller_speed_rpm": float(impeller_speed),
            "mass_flow_rate": float(mass_flow_rate),
            "iteration_count": int(iteration_count),
            "time_step_scale_factor": float(time_step_scale_factor),
        }
    )
    step.run_simulation()
    # The verdict of the previous run is about to be out of date, so it goes now rather than
    # sitting there green while a new operating point is being solved. The convergence curve
    # starts empty again and is refilled from the history stream.
    # The toast is closed by the shell, so it is not left spinning if the user moves on.
    return (
        opening_notification(RUN_SIMULATION_NOTIFICATION),
        progress_panel(None, 0.0),
        True,
        True,
        "logs",
        html.Div(),
        html.Div(),
    )


@callback(
    Output("live-convergence", "children", allow_duplicate=True),
    Input("run-simulation-history-ws", "message"),
    prevent_initial_call=True,
)
def on_run_simulation_history(message: dict) -> html.Div:
    """Draw the convergence curve as far as the solver has got."""
    event = parse_event(message)
    if not event.history:
        raise PreventUpdate
    return html.Div([convergence_card(event.history, live=True), dmc.Space(h=20)])


@callback(
    Output("run-simulation-progress", "children", allow_duplicate=True),
    Input("run-simulation-progress-ws", "message"),
    prevent_initial_call=True,
)
def on_run_simulation_progress(message: dict) -> html.Div:
    """Move the progress bar under the button."""
    event = parse_event(message)
    if event.stage is None:
        raise PreventUpdate
    return progress_panel(event.stage, event.fraction)


@callback(
    Output("run-simulation-log", "children"),
    Output("run-simulation-log-store", "data"),
    Input("run-simulation-log-ws", "message"),
    State("run-simulation-log-store", "data"),
    prevent_initial_call=True,
)
def on_run_simulation_log(message: dict, buffered: list[str] | None) -> tuple[html.Div, list[str]]:
    """Append the newest Fluent console lines."""
    event = parse_event(message)
    if not event.lines:
        raise PreventUpdate
    lines = append_lines(buffered, event.lines)
    return log_viewer(LOG_VIEWPORT, lines), lines


@callback(
    Output("run-simulation-progress", "children", allow_duplicate=True),
    Output("results-panel", "children"),
    Output("results-details", "children"),
    Output("run-simulation", "disabled", allow_duplicate=True),
    Output("run-simulation", "loading", allow_duplicate=True),
    Output("solve-tabs", "value", allow_duplicate=True),
    Output("solve-status", "children", allow_duplicate=True),
    Output("live-convergence", "children", allow_duplicate=True),
    Output("operating-point-viewer-container", "children", allow_duplicate=True),
    Output("operating-point-scene-sink", "data", allow_duplicate=True),
    Input("run-simulation-ws", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_run_simulation_finished(
    message: dict, project: ExamplesSolution
) -> tuple[Any, Any, Any, bool, bool, Any, Any, Any, Any, Any]:
    """Close out the run: clear the progress bar, free the button and show the results.

    The toast, and the scene conversion a successful run starts, are handled by the shell,
    which keeps listening once the user leaves this page.
    """
    event = parse_event(message)
    if not event.finished:
        raise PreventUpdate
    step = project.steps.pump_solve_step
    if not event.succeeded:
        return (
            html.Div(),
            no_update,
            no_update,
            False,
            False,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )
    # The curve stays on the Monitoring tab after the run: redrawn from the stored history it
    # loses the "Live" badge but keeps the record of how the solve behaved. The scene on
    # screen belongs to the previous run; clearing the flag lets the next Visor start, if
    # any, embed the new one.
    return (
        html.Div(),
        results_panel(step),
        results_details(step),
        False,
        False,
        "output",
        status_alert(step),
        live_convergence(step, False),
        viewer_spinner(),
        False,
    )


clientside_callback(
    scroll_to_bottom(LOG_VIEWPORT),
    Output("run-simulation-scroll-sink", "data"),
    Input("run-simulation-log", "children"),
    prevent_initial_call=True,
)
