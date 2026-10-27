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

"""Frontend of the about page.

The landing page of the solution. It is written for someone who has never run a CFD
simulation: what the application is for, what it asks for and what it hands back. Everything
an expert would want — the modelling assumptions, the governing equations, the full
parameter reference — is folded into an accordion at the bottom so that it is available
without being in the way.

Static content only: no step model, no transaction, no project dependency. Keeping the
layout free of asset and project lookups is what makes it renderable in a unit test.
"""

from ansys.saf.glow.client import callback
import dash
from dash_extensions.enrich import Input, Output, State, dcc, html, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from saf.solutions.examples.solution.logic.pump.constants import (
    DEFAULT_IMPELLER_SPEED_RPM,
    DEFAULT_ITERATION_COUNT,
    DEFAULT_MASS_FLOW_RATE,
    DENSITY_WATER,
    IMPELLER_SPEED_RANGE,
    INLET_GAUGE_PRESSURE,
    ITERATION_COUNT_RANGE,
    MASS_FLOW_RATE_RANGE,
)

dash.register_page(
    __name__,
    name="About",
    path_template="/projects/<project_id>",
    icon_asset_name="material-symbols:home",
    order=0,
)

# Dash ships MathJax with ``boldsymbol`` registered for autoload only; the package itself is
# fetched from a CDN on first use, so on an offline machine the macro renders as literal
# text. Every macro below is part of the bundled TeX base, which is why the rotation vector
# is written with ``\mathbf`` and the stress tensor is left unbolded.
EQUATIONS = r"""
**Momentum in the rotating frame**

$$\nabla\cdot(\rho\,\mathbf{u}_r\mathbf{u}_r)
+ \rho\,\underbrace{(2\,\mathbf{\Omega}\times\mathbf{u}_r
+ \mathbf{\Omega}\times\mathbf{\Omega}\times\mathbf{r})}_{\text{Coriolis and centrifugal}}
= -\nabla p + \nabla\cdot\tau$$

The two bracketed terms are the price of freezing the rotor: instead of moving the mesh,
the rotation is paid for with extra body forces. That single idea is what makes the
simulation finish in minutes rather than hours.

**Performance quantities**

$$\omega = \frac{2\pi N}{60} \qquad Q = \frac{\dot{m}}{\rho} \qquad
H = \frac{p_{0,\text{out}} - p_{0,\text{in}}}{\rho g}$$

$$P_h = \rho g Q H \qquad P_s = T\omega \qquad \eta = \frac{P_h}{P_s}$$

**Affinity laws** — how the pump responds to a change of speed:

$$Q \propto N \qquad H \propto N^2 \qquad P \propto N^3$$
"""

_INPUT_CARDS = [
    (
        "carbon:rotate-360",
        "Impeller speed",
        f"{DEFAULT_IMPELLER_SPEED_RPM:.0f} rpm",
        "How fast the shaft turns. Spin it faster and the pump pushes harder.",
    ),
    (
        "carbon:flow",
        "Flow rate",
        f"{DEFAULT_MASS_FLOW_RATE:.0f} kg/s",
        "How much water you ask the pump to deliver.",
    ),
]

# The three numbers that describe a pump's performance; the Operating Point page shows them
# as headline cards. The rest sit in its "Secondary results" accordion.
_KEY_OUTPUT_CARDS = [
    ("ant-design:column-height-outlined", "Pump head", "m", "How high the pump can lift the water."),
    ("carbon:meter", "Efficiency", "%", "How much of the motor's power reaches the water."),
    ("carbon:flash", "Shaft power", "kW", "How much power the motor has to supply."),
]

_SECONDARY_OUTPUT_CARDS = [
    ("carbon:pressure", "Pressure rise", "kPa", "The pressure gained across the pump."),
    ("carbon:rotate-360", "Blade torque", "N·m", "The twisting force on the impeller."),
    ("carbon:flow", "Volumetric flow", "m³/h", "The same duty point in the units pumps are sold in."),
]

_INPUT_ROWS = [
    [
        "N",
        "Impeller speed",
        "rpm",
        f"{DEFAULT_IMPELLER_SPEED_RPM:.0f}",
        f"{IMPELLER_SPEED_RANGE[0]:.0f} – {IMPELLER_SPEED_RANGE[1]:.0f}",
        "Head rises with the square of speed, power with the cube.",
    ],
    [
        "ṁ",
        "Mass flow rate",
        "kg/s",
        f"{DEFAULT_MASS_FLOW_RATE:.0f}",
        f"{MASS_FLOW_RATE_RANGE[0]:.0f} – {MASS_FLOW_RATE_RANGE[1]:.0f}",
        "The duty point. Head falls as you demand more flow.",
    ],
    [
        "n",
        "Iteration count",
        "–",
        f"{DEFAULT_ITERATION_COUNT}",
        f"{ITERATION_COUNT_RANGE[0]} – {ITERATION_COUNT_RANGE[1]}",
        "Advanced. Trades runtime against how tightly the solution converges.",
    ],
]

_OUTPUT_ROWS = [
    ["H", "Pump head", "m", "Key", "How high the pump can lift the fluid. The headline number."],
    ["η", "Hydraulic efficiency", "%", "Key", "Fraction of shaft power that reaches the fluid."],
    ["P_s", "Shaft power", "kW", "Key", "Mechanical power the motor must supply."],
    ["Δp", "Pressure rise", "kPa", "Secondary", "Total pressure gain across the pump; head in pressure units."],
    ["T", "Blade torque", "N·m", "Secondary", "Moment on the rotating surfaces; shaft power divided by ω."],
    ["Q", "Volumetric flow", "m³/h", "Secondary", "The mass flow input restated in the units pump engineers use."],
]

_MODELLING_CHOICES = [
    ["Approach", "Frozen rotor (multiple reference frame), steady state."],
    ["Turbulence", "k-ω SST, the standard choice for turbomachinery."],
    ["Fluid", f"Liquid water at {DENSITY_WATER:.1f} kg/m³ and 0.001003 kg/(m·s)."],
    ["Geometry", "The supplied impeller and volute meshes, joined by a turbo interface."],
    [
        "Inlet pressure",
        f"Fixed at {INLET_GAUGE_PRESSURE:.0f} Pa gauge. It sets the pressure datum and nothing else.",
    ],
    ["Caveat", "These are sensible defaults, not values tuned for your pump."],
]

_STEP_ROWS = [
    ["Model Setup", "build_case", "Fluent case file, mesh render, zone list"],
    ["Operating Point", "run_simulation", "Head, efficiency, power, convergence, contour"],
]


def _table(headers: list[str], rows: list[list[str]]) -> dmc.Table:
    """Build a Mantine table from plain string rows."""
    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        verticalSpacing="sm",
        data={"head": headers, "body": rows},
    )


def _section(title: str, *children) -> html.Div:
    """Wrap content under a titled heading."""
    return html.Div(
        [
            dmc.Space(h=20),
            dmc.Group([dmc.Title(title, order=4), dmc.Divider(style={"flex": 1}, variant="dashed")], gap="md"),
            dmc.Space(h=10),
            *children,
        ]
    )


def _quantity_card(icon: str, name: str, value: str, meaning: str) -> dmc.Card:
    """Render one input or output as a small, self-explanatory card.

    The card is deliberately two lines tall: the whole page has to fit on one screen, so a
    quantity gets a name, its unit or default, and a single line of plain English.
    """
    return dmc.Card(
        dmc.Group(
            [
                dmc.ThemeIcon(DashIconify(icon=icon, width=16), variant="light", size="md", radius="md"),
                html.Div(
                    [
                        dmc.Group(
                            [
                                dmc.Text(name, fw=600, size="sm"),
                                dmc.Text(value, size="xs", c="dimmed"),
                            ],
                            gap=6,
                            align="baseline",
                        ),
                        dmc.Text(meaning, size="xs", c="dimmed"),
                    ]
                ),
            ],
            gap="sm",
            wrap="nowrap",
            align="flex-start",
        ),
        withBorder=True,
        radius="md",
        p="xs",
    )


def _quantity_grid(cards: list[tuple[str, str, str, str]]) -> dmc.SimpleGrid:
    """Lay the quantity cards out in a responsive grid."""
    return dmc.SimpleGrid(
        [_quantity_card(*card) for card in cards],
        cols={"base": 1, "sm": 2, "md": 3},
        spacing="xs",
        verticalSpacing="xs",
    )


def _workflow_steps() -> dmc.Stepper:
    """Render the three-step guide to using the application.

    The stepper is pinned horizontal: stacking the three stages vertically pushed
    everything below them off the first screen. Mantine lets the steps container wrap and
    gives each step its natural width, so the descriptions shoved the third step onto a
    second row. The overrides below forbid the wrap and make every step an equal share of
    the row that is free to shrink, which lets the descriptions wrap inside their own
    column instead.
    """
    return dmc.Stepper(
        active=0,
        orientation="horizontal",
        size="sm",
        iconSize=34,
        styles={
            "steps": {"flexWrap": "nowrap", "alignItems": "flex-start"},
            "step": {"flex": "1 1 0", "minWidth": 0, "alignItems": "flex-start"},
            "separator": {"flex": "0 0 16px", "minWidth": 16, "marginTop": 17},
            "stepBody": {"minWidth": 0},
            "stepDescription": {"whiteSpace": "normal", "overflowWrap": "anywhere"},
        },
        children=[
            dmc.StepperStep(
                label="Build the case",
                description="Model Setup reads the two meshes, joins them and configures the "
                "physics. Needed once per project.",
                icon=DashIconify(icon="carbon:build-tool", width=16),
                progressIcon=DashIconify(icon="carbon:build-tool", width=16),
            ),
            dmc.StepperStep(
                label="Set the operating point",
                description="Choose a shaft speed and a flow rate, then run the solve.",
                icon=DashIconify(icon="carbon:settings-adjust", width=16),
                progressIcon=DashIconify(icon="carbon:settings-adjust", width=16),
            ),
            dmc.StepperStep(
                label="Read the results",
                description="Head, efficiency, power, the convergence history and a pressure contour.",
                icon=DashIconify(icon="carbon:chart-line", width=16),
                progressIcon=DashIconify(icon="carbon:chart-line", width=16),
            ),
        ],
    )


def _expert_item(value: str, title: str, subtitle: str, *children) -> dmc.AccordionItem:
    """Build one entry of the expert accordion."""
    return dmc.AccordionItem(
        [
            dmc.AccordionControl(
                html.Div(
                    [
                        dmc.Text(title, fw=600),
                        dmc.Text(subtitle, size="xs", c="dimmed"),
                    ]
                )
            ),
            dmc.AccordionPanel(list(children)),
        ],
        value=value,
    )


def expert_details() -> dmc.Accordion:
    """Render the technical reference aimed at simulation engineers.

    The whole section is collapsed behind a single control, so a first-time user sees one
    line rather than four sub-headings they have no use for.
    """
    return dmc.Accordion(
        dmc.AccordionItem(
            [
                dmc.AccordionControl(
                    dmc.Group(
                        [
                            dmc.ThemeIcon(
                                DashIconify(icon="carbon:function-math", width=16),
                                variant="light",
                                size="md",
                                radius="md",
                            ),
                            html.Div(
                                [
                                    dmc.Text("For the simulation engineer", fw=600),
                                    dmc.Text(
                                        "Assumptions, governing equations, parameter reference, "
                                        "architecture — none of it needed to run the application.",
                                        size="xs",
                                        c="dimmed",
                                    ),
                                ]
                            ),
                        ],
                        gap="sm",
                        wrap="nowrap",
                    )
                ),
                dmc.AccordionPanel(
                    dmc.Accordion(
                        [
                            _expert_item(
                                "assumptions",
                                "Modelling assumptions",
                                "Why the rotor is frozen, and what that costs you",
                                dmc.Text(
                                    "Simulating the impeller actually spinning means moving the mesh "
                                    "every time step — accurate, but expensive. The frozen rotor "
                                    "approach instead holds the impeller still and solves its zone in "
                                    "a rotating reference frame, adding Coriolis and centrifugal "
                                    "source terms in its place. The result is a steady-state solution "
                                    "that captures the pump's performance at a fraction of the cost.",
                                    size="sm",
                                    style={"textAlign": "justify"},
                                ),
                                dmc.Space(h=12),
                                dmc.Alert(
                                    "The approximation ignores the unsteady interaction as each blade "
                                    "sweeps past the volute tongue, so the blade position relative to "
                                    "the volute is baked into the answer. Predictions are most "
                                    "trustworthy near the design point and degrade as you move away "
                                    "from it.",
                                    title="What this method cannot tell you",
                                    color="yellow",
                                    variant="light",
                                    icon=DashIconify(icon="carbon:warning-alt", width=20),
                                ),
                                dmc.Space(h=16),
                                dmc.Text("Why suction pressure is not an input", fw=600, size="sm"),
                                dmc.Space(h=4),
                                dmc.Text(
                                    "The fluid is constant-density water with no energy equation "
                                    "and no cavitation model, so pressure enters the momentum "
                                    "equation only through its gradient. The inlet value merely "
                                    "pins the datum: raise it and the whole field shifts with it. "
                                    "Head and pressure rise are differences, and a uniform offset "
                                    "contributes no net moment about the shaft axis, so head, "
                                    "torque, power and efficiency are all unchanged. It is held at "
                                    f"{INLET_GAUGE_PRESSURE:.0f} Pa gauge. Assessing a cavitation "
                                    "margin would need a vapour-pressure and cavitation model, "
                                    "which this case does not have.",
                                    size="sm",
                                    style={"textAlign": "justify"},
                                ),
                                dmc.Space(h=16),
                                dmc.Text("What the application decides for you", fw=600, size="sm"),
                                dmc.Space(h=8),
                                _table(["Choice", "Value"], _MODELLING_CHOICES),
                            ),
                            _expert_item(
                                "equations",
                                "Governing equations",
                                "Rotating-frame momentum, performance quantities, affinity laws",
                                dcc.Markdown(EQUATIONS, mathjax=True),
                            ),
                            _expert_item(
                                "parameters",
                                "Parameter reference",
                                "Symbols, units, defaults and admissible ranges",
                                _table(
                                    ["Symbol", "Quantity", "Unit", "Default", "Range", "Why it matters"],
                                    _INPUT_ROWS,
                                ),
                                dmc.Space(h=20),
                                dmc.Text("Reported quantities", fw=600, size="sm"),
                                dmc.Space(h=8),
                                _table(["Symbol", "Quantity", "Unit", "Priority", "Interpretation"], _OUTPUT_ROWS),
                            ),
                            _expert_item(
                                "architecture",
                                "Under the hood",
                                "How the two steps map onto Fluent sessions",
                                dmc.Text(
                                    "Each step runs an Ansys Fluent session through PyFluent as a "
                                    "long-running transaction and streams its progress and console "
                                    "output back to this interface. The artefacts it produces stay "
                                    "with the project and can be downloaded at any time.",
                                    size="sm",
                                    style={"textAlign": "justify"},
                                ),
                                dmc.Space(h=16),
                                _table(["Step", "Transaction", "Produces"], _STEP_ROWS),
                            ),
                        ],
                        variant="separated",
                        radius="md",
                    )
                ),
            ],
            value="expert",
        ),
        variant="contained",
        radius="md",
        chevronPosition="left",
    )


def layout() -> html.Div:
    """Layout of the about page."""
    return html.Div(
        [
            html.Div(
                [
                    dmc.Title("About", order=1),
                    dmc.Text(
                        "Predict the head, efficiency and power of a centrifugal pump at one "
                        "operating point.",
                        size="lg",
                        c="dimmed",
                    ),
                ]
            ),
            dmc.Space(h=20),
            dmc.Accordion(
                value="about",
                variant="contained",
                radius="md",
                chevronPosition="left",
                children=[
                    dmc.AccordionItem(
                        value="about",
                        children=[
                            dmc.AccordionControl(
                                dmc.Group(
                                    [
                                        DashIconify(icon="carbon:information", width=18),
                                        dmc.Text("About this app", fw=600),
                                    ],
                                    gap="sm",
                                )
                            ),
                            dmc.AccordionPanel(
                                [
                                    _section(
                                        "What this application is for",
                                        dmc.Text(
                                            "This application answers one question: for a given shaft speed "
                                            "and a given flow rate, how does the pump perform?",
                                            size="lg",
                                        ),
                                    ),
                                    _section(
                                        "What you give it",
                                        _quantity_grid(_INPUT_CARDS),
                                    ),
                                    _section(
                                        "What you get back",
                                        dmc.Text(
                                            "Three numbers tell you how the pump performs:",
                                            size="sm",
                                        ),
                                        dmc.Space(h=6),
                                        _quantity_grid(_KEY_OUTPUT_CARDS),
                                        dmc.Space(h=12),
                                        dmc.Text(
                                            "Also reported, under Secondary results, for a closer look:",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                        dmc.Space(h=6),
                                        _quantity_grid(_SECONDARY_OUTPUT_CARDS),
                                        dmc.Space(h=8),
                                        dmc.Text(
                                            "Alongside the numbers you get a pressure contour through the pump "
                                            "and a chart showing how the solution settled down, so you can "
                                            "judge how much to trust them.",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ),
                                    _section(
                                        "How to use it",
                                        _workflow_steps(),
                                    ),
                                    dmc.Space(h=8),
                                ]
                            ),
                        ],
                    )
                ],
            ),
            dmc.Space(h=24),
            expert_details(),
            dmc.Space(h=24),
            dmc.Button(
                "Start",
                id="go-to-model-setup",
                size="md",
                radius="md",
                fullWidth=True,
                leftSection=DashIconify(icon="carbon:play-filled-alt", width=18),
            ),
            dmc.Space(h=32),
        ]
    )


@callback(
    Output("url", "href", allow_duplicate=True),
    Input("go-to-model-setup", "n_clicks"),
    State("active-project-id", "data"),
    prevent_initial_call=True,
)
def go_to_model_setup(n_clicks: int | None, project_id: str | None) -> str:
    """Send the user to the Model Setup page of the current project.

    ``prevent_initial_call`` only covers the first load of the application. This page is
    mounted by the shell's routing callback, so the callback also fires the moment the
    button appears, with ``n_clicks`` still ``None``. That first firing must be ignored.
    """
    if not n_clicks or not project_id:
        return no_update
    return dash.get_relative_path(f"/projects/{project_id}/model-setup")
