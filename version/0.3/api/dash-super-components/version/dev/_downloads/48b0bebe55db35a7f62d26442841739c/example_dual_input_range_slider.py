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
Dual Input Range Slider
=======================

A minimal Dash app showing how to use the
:class:`~ansys.solutions.dash_super_components.DualInputRangeSlider` component.

See the `Dual Input Range Slider
<https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/dual-input-range-slider.html#ref_dual_input_range_slider>`_
page in the User Guide for the full reference documentation.

.. note::

   Run this file directly to launch the app:

   .. code-block:: bash

       pip install ansys-solutions-dash-super-components
       python example_dual_input_range_slider.py

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

from ansys.solutions.dash_super_components import DualInputRangeSlider
from dash import _dash_renderer
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import DashProxy, Input, Output, callback, html
import dash_mantine_components as dmc

# Required only for Dash 2.x to use Mantine-based components
_dash_renderer._set_react_version("18.2.0")

app = DashProxy(__name__)

# %%
# Build the layout
# ----------------
#
# Three ``DualInputRangeSlider`` instances demonstrate the key configuration
# options:
#
# * **Basic** — integer range 0 – 100 with default step and precision.
# * **Fine-grained** — float range −1 to 1 with custom step and decimal scale,
#   plus labelled marks on the slider track.
# * **Callback demo** — the currently selected range is read in a
#   :func:`~dash.callback` and displayed below the slider.

app.layout = dmc.MantineProvider(
    html.Div(
        [
            dmc.Title("Dual Input Range Slider", order=2, mb="md"),
            dmc.Text(
                "Drag the slider handles or type in the number inputs — they stay in sync.",
                c="dimmed",
                mb="xl",
            ),
            # ── Basic ──────────────────────────────────────────────────────
            dmc.Text("Basic (0 - 100)", fw=600, mb="xs"),
            DualInputRangeSlider(
                aio_id="slider-basic",
                min=0,
                max=100,
                value=[20, 80],
            ),
            dmc.Space(h=32),
            # ── Fine-grained ────────────────────────────────────────────────
            dmc.Text("Fine-grained (-1 to 1, step 0.1)", fw=600, mb="xs"),
            DualInputRangeSlider(
                aio_id="slider-fine",
                min=-1,
                max=1,
                step=0.1,
                decimal_scale=2,
                value=[0.2, 0.8],
                slider_props={
                    "marks": [
                        {"value": -1, "label": "-1"},
                        {"value": 0, "label": "0"},
                        {"value": 1, "label": "1"},
                    ],
                },
            ),
            dmc.Space(h=32),
            # ── Callback demo ───────────────────────────────────────────────
            dmc.Text("Read the selected range in a callback", fw=600, mb="xs"),
            DualInputRangeSlider(
                aio_id="slider-read",
                min=0,
                max=1000,
                step=50,
                value=[200, 600],
            ),
            dmc.Text("Move the slider to see its value here.", id="slider-read-output", mt="sm"),
        ],
        style={"maxWidth": 640, "margin": "40px auto", "padding": "0 16px"},
    )
)

# %%
# Add a callback
# --------------
#
# Use :attr:`DualInputRangeSlider.ids.slider` to build the component ID of the
# underlying :class:`~dash_mantine_components.RangeSlider` sub-component and
# subscribe to its ``value`` property.


@callback(
    Output("slider-read-output", "children"),
    Input(DualInputRangeSlider.ids.slider("slider-read"), "value"),
)
def show_value(value: list[float | int]) -> str:
    """Display the currently selected range."""
    if value is None:
        raise PreventUpdate
    lower, upper = value
    return f"Selected range: {lower} - {upper}"


# %%
# Run the app
# -----------

if __name__ == "__main__":
    app.run()
