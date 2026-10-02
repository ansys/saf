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

"""
Input Form
==========

A minimal Dash app showing how to use the
:class:`~ansys.solutions.dash_super_components.InputForm` component.

See the `Input Form
<https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/input-form.html#ref_input_form>`_
page in the User Guide for the full reference documentation.

.. note::

   Run this file directly to launch the app:

   .. code-block:: bash

       pip install ansys-solutions-dash-super-components
       python example_input_form.py

   Then open ``http://localhost:8050`` in your browser.
"""

# %%
# Set up the Dash application
# ---------------------------
#
# :class:`~dash_mantine_components.MantineProvider` must wrap the entire layout
# for Mantine-based components to render correctly.  The React version must also
# be set **before** importing the component library — this is a Dash Mantine
# Components requirement when using Dash 2.x.

from ansys.solutions.dash_super_components import InputForm
from dash import _dash_renderer
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import DashProxy, Input, Output, State, callback, html
import dash_mantine_components as dmc

# Required only for Dash 2.x to use Mantine-based components
_dash_renderer._set_react_version("18.2.0")

app = DashProxy(__name__)

# %%
# Define the form items
# ---------------------
#
# An ``InputForm`` is made up of rows.  Each row can contain a ``label``,
# one or more ``fields``, an optional ``unit``, and optional ``help`` content
# displayed in a modal.
#
# The form below models a simple CFD solver configuration panel with a variety
# of input types:
#
# * **Solver** — a ``Select`` field to choose the physics solver.
# * **Iterations** — a ``NumberInput`` which only accepts integer values.
# * **Convergence tolerance** — a ``NumberInput`` with a floating-point step.
# * **Export results** — a ``Switch`` toggle.
# * **Output file** — a ``TextInput`` for the result filename.

FORM_ITEMS = [
    {
        "id": "solver-row",
        "label": "Solver",
        "fields": [
            {
                "type": "Select",
                "id": "solver-select",
                "value": "fluent",
                "data": ["fluent", "cfx", "polyflow"],
            }
        ],
        "help": "Physics solver to use for the simulation.",
    },
    {
        "id": "iterations-row",
        "label": "Iterations",
        "fields": [
            {
                "type": "NumberInput",
                "id": "iterations-input",
                "value": 500,
                "min": 1,
                "max": 10000,
                "step": 1,
                "allowDecimal": False,
            }
        ],
        "help": "Maximum number of solver iterations.",
    },
    {
        "id": "tolerance-row",
        "label": "Convergence tolerance",
        "fields": [
            {
                "type": "NumberInput",
                "id": "tolerance-input",
                "value": 1e-4,
                "min": 1e-12,
                "step": 1e-5,
            }
        ],
        "help": "Residual convergence threshold.",
    },
    {
        "id": "export-row",
        "label": "Export results",
        "fields": [
            {
                "type": "Switch",
                "id": "export-switch",
                "checked": True,
            }
        ],
        "help": "Write results to disk after the run.",
    },
    {
        "id": "output-row",
        "label": "Output file",
        "fields": [
            {
                "type": "TextInput",
                "id": "output-input",
                "value": "results.dat",
                "placeholder": "Enter filename",
            }
        ],
        "help": "Name of the output results file.",
    },
]

# %%
# Build the layout
# ----------------
#
# Wrap the form in a ``MantineProvider`` and add a summary panel that reflects
# the current field values when the **Apply** button is clicked.

app.layout = dmc.MantineProvider(
    html.Div(
        [
            dmc.Title("Input Form", order=2, mb="md"),
            dmc.Text(
                "Edit the parameters below and click Apply to see the current values.",
                c="dimmed",
                mb="xl",
            ),
            InputForm(
                items=FORM_ITEMS,
                aio_id="solver-config",
                title="Solver Configuration",
                columns=["label", "fields", "help"],
            ),
            dmc.Space(h=16),
            dmc.Button("Apply", id="apply-btn", mt="md"),
            dmc.Paper(
                dmc.Text(id="form-output", p="md"),
                withBorder=True,
                radius="md",
                mt="md",
                p="sm",
            ),
        ],
        style={"maxWidth": 750, "margin": "40px auto", "padding": "0 16px"},
    )
)

# %%
# Add a callback
# --------------
#
# Read the current value of each field using
# :attr:`InputForm.ids.field` and display a summary when the **Apply** button
# is clicked.


@callback(
    Output("form-output", "children"),
    Input("apply-btn", "n_clicks"),
    State(InputForm.ids.field("solver-config", "Select", "solver-select", "solver-row"), "value"),
    State(
        InputForm.ids.field("solver-config", "NumberInput", "iterations-input", "iterations-row"),
        "value",
    ),
    State(
        InputForm.ids.field("solver-config", "NumberInput", "tolerance-input", "tolerance-row"),
        "value",
    ),
    State(InputForm.ids.field("solver-config", "Switch", "export-switch", "export-row"), "checked"),
    State(InputForm.ids.field("solver-config", "TextInput", "output-input", "output-row"), "value"),
    prevent_initial_call=True,
)
def show_form_values(
    n_clicks: int,
    solver: str | None,
    iterations: int | None,
    tolerance: float | None,
    export: bool,
    output_file: str | None,
) -> str:
    """Display a summary of the current form values."""
    if not n_clicks:
        raise PreventUpdate
    return (
        f"Solver: {solver} | Iterations: {iterations} | "
        f"Tolerance: {tolerance} | Export: {export} | Output file: {output_file}"
    )


# %%
# Run the app
# -----------

if __name__ == "__main__":
    app.run()
