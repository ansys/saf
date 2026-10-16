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
Input Row Array
===============

A minimal Dash app showing how to use the
:class:`~ansys.solutions.dash_super_components.InputRowArray` component.

See the `Input Row Array
<https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/input-row-array.html#ref_input_row_array>`_
page in the User Guide for the full reference documentation.

.. note::

   Run this file directly to launch the app:

   .. code-block:: bash

       pip install ansys-solutions-dash-super-components
       python example_input_row_array.py

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

from ansys.solutions.dash_super_components import InputRowArray
from dash import _dash_renderer
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import ALL, DashProxy, Input, Output, State, callback, html
import dash_mantine_components as dmc

# Required only for Dash 2.x to use Mantine-based components
_dash_renderer._set_react_version("18.2.0")

app = DashProxy(__name__)

# %%
# Define the field definitions
# ----------------------------
#
# Each dictionary in the ``items`` list describes one field in every
# row of the array. The ``"id"`` key must be unique within the definition and
# is used to retrieve values in callbacks.

ITEMS = [
    {
        "id": "material",
        "type": "Select",
        "properties": {
            "label": "Material",
            "placeholder": "Select a material",
            "data": ["Aluminium", "Steel", "Titanium", "Carbon fibre"],
        },
    },
    {
        "id": "thickness",
        "type": "NumberInput",
        "properties": {
            "label": "Thickness (mm)",
            "placeholder": "Enter thickness",
            "min": 0.1,
            "step": 0.5,
        },
    },
    {
        "id": "layer-name",
        "type": "TextInput",
        "properties": {
            "label": "Layer name",
            "placeholder": "Enter a name",
        },
    },
]

# %%
# Build the layout
# ----------------
#
# ``enable_multiple_rows=True`` adds **+** and **−** buttons so users can add
# or remove rows at runtime.  A **Collect values** button triggers a callback
# that reads all current field values and displays them below.

app.layout = dmc.MantineProvider(
    html.Div(
        [
            dmc.Title("Input Row Array", order=2, mb="md"),
            dmc.Text(
                "Use the + and − buttons to add or remove rows. "
                "Click Collect values to see the current data.",
                c="dimmed",
                mb="xl",
            ),
            InputRowArray(
                items=ITEMS,
                enable_multiple_rows=True,
                aio_id="layer-array",
            ),
            dmc.Space(h=16),
            dmc.Button("Collect values", id="collect-btn", mt="md"),
            dmc.Paper(
                dmc.Text(id="array-output", p="md"),
                withBorder=True,
                radius="md",
                mt="md",
                p="sm",
            ),
        ],
        style={"maxWidth": 860, "margin": "40px auto", "padding": "0 16px"},
    )
)

# %%
# Add a callback to collect values
# --------------------------------
#
# Use the ``ALL`` pattern-matching wildcard to collect all values from every
# row.  :attr:`InputRowArray.ids.input` accepts ``ALL`` for both ``item_id``
# and ``row_index`` to match every field in every row.


@callback(
    Output("array-output", "children"),
    Input("collect-btn", "n_clicks"),
    State(InputRowArray.ids.input("layer-array", ALL, ALL), "value"),
    prevent_initial_call=True,
)
def collect_values(n_clicks: int, values: list) -> str:
    """Display all current values from the Input Row Array."""
    if not n_clicks:
        raise PreventUpdate
    if not values:
        return "No values entered."
    return f"Current values: {values}"


# %%
# Run the app
# -----------

if __name__ == "__main__":
    app.run()
