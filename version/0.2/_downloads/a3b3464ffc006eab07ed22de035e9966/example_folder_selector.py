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
Folder Selector
===============

A minimal Dash app showing how to use the
:class:`~ansys.solutions.dash_super_components.FolderSelector` component.

See the `Folder Selector
<https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/folder-selector.html#ref_folder_selector>`_
page in the User Guide for the full reference documentation.

.. note::

   Run this file directly to launch the app:

   .. code-block:: bash

       pip install ansys-solutions-dash-super-components
       python example_folder_selector.py

   Then open ``http://localhost:8050`` in your browser and click **Browse**.
"""

# %%
# Set up the Dash application
# ---------------------------
#
# :class:`~dash_mantine_components.MantineProvider` must wrap the entire layout
# for Mantine-based components to render correctly.  The React version must also
# be set **before** importing the component library — this is a Dash Mantine
# Components requirement when using Dash 2.x.
#
# The ``FolderSelector`` component uses the Dash Mantine Components notification system to show
# error messages and thus requires a :class:`~dash_mantine_components.NotificationContainer` in the
# layout for the notifications to appear.
# This example uses a **custom** notification container ID instead of the default
# ``"notification-container"``.  Call :func:`~ansys.solutions.dash_super_components.configure`
# **before** building the layout to tell every super component about the custom ID,
# then add a :class:`~dash_mantine_components.NotificationContainer` with the same ID
# to the layout.
# Furthermore, to demonstrate the bootstrap mode, which is a beta feature, this example explicitly
# enables beta features in the configuration.

from pathlib import Path

import ansys.solutions.dash_super_components as dsc
from ansys.solutions.dash_super_components import FolderSelector
from ansys.solutions.dash_super_components.folder_selector import FolderSelectorMode
from dash import _dash_renderer
from dash_extensions.enrich import DashProxy, Input, Output, callback, html
import dash_mantine_components as dmc

# Required only for Dash 2.x to use Mantine-based components
_dash_renderer._set_react_version("18.2.0")

# ── Custom notification container ID ─────────────────────────────────────────
# Call configure() *before* building the layout. This example deliberately
# uses a non-default ID to show how to configure Super Components for Dash when
# your application uses a different ID convention. Furthermore, bootstrap mode as
# a beta feature must be explicitly enabled.
dsc.configure(
    notification_container_id="example-notifications",
    enable_beta_features=True,
)

app = DashProxy(__name__)

# %%
# Build the layout
# ----------------
#
# The layout is split into two sections:
#
# 1. **Built-in display** — two ``FolderSelector`` instances that use the
#    component's own ``display_field`` to show the selected path inline.
#    They illustrate the two operating modes: *bootstrap* and *default*.
# 2. **Callback-driven display** — a third ``FolderSelector`` whose selection
#    is read in a callback and rendered as a custom folder card.
#
# The :class:`~dash_mantine_components.NotificationContainer` must use the same
# ID that was passed to :func:`~ansys.solutions.dash_super_components.configure`
# above.

app.layout = dmc.MantineProvider(
    [
        # Use the same custom ID that was passed to dsc.configure() above.
        dmc.NotificationContainer(id="example-notifications", position="bottom-center"),
        html.Div(
            [
                dmc.Title("Folder Selector", order=2, mb="md"),
                dmc.Text(
                    "Click Browse to open the folder selection dialog.",
                    c="dimmed",
                    mb="xl",
                ),
                # ── Section 1: Built-in display field ──────────────────────
                dmc.Title("Operating modes", order=4, mb="xs"),
                dmc.Text("Bootstrap mode (browser modal)", fw=600, mb="xs"),
                FolderSelector(
                    aio_id="folder-bootstrap",
                    mode=FolderSelectorMode.BOOTSTRAP,
                    browse_button_props={"children": "Browse (bootstrap)"},
                    options={"browse_from": "/path/to/root"},
                ),
                dmc.Space(h="xl"),
                dmc.Text("Default mode (tkinter if available)", fw=600, mb="xs"),
                FolderSelector(
                    aio_id="folder-default",
                ),
                dmc.Divider(my="xl"),
                # ── Section 2: Callback-driven custom display ───────────────
                dmc.Title("Accessing the selection in a callback", order=4, mb="xs"),
                dmc.Text("Custom callback display", fw=600, mb="xs"),
                FolderSelector(
                    aio_id="folder-custom",
                    browse_button_props={"children": "Browse (custom display)"},
                    options={"display_field": {"enabled": False}},
                ),
                html.Div(id="card-custom", style={"marginTop": 12}),
            ],
            style={"maxWidth": 720, "margin": "40px auto", "padding": "0 16px"},
        ),
    ]
)

# %%
# Rendering the selected folder as a custom card
# -----------------------------------------------
#
# :attr:`FolderSelector.ids.selected_folder` returns the ID of the
# :class:`~dash_extensions.enrich.dcc.Store` sub-component that holds the
# selected path.  ``_folder_card`` builds a styled card from the path;
# the callback calls it so the display updates on every selection change.

_FOLDER_ICON = "📁"


def _folder_card(path: str | None) -> dmc.Card:
    """Return a styled card representing *path*."""
    folder = Path(path) if path and Path(path).is_dir() else None

    if folder is None:
        content = dmc.Stack(
            [
                dmc.Text(_FOLDER_ICON, style={"fontSize": 40, "textAlign": "center"}),
                dmc.Text(
                    "No folder selected yet — click Browse above.",
                    c="dimmed",
                    size="sm",
                    style={"textAlign": "center"},
                ),
            ],
            align="center",
            gap="xs",
        )
    else:
        content = dmc.Group(
            [
                dmc.Text(_FOLDER_ICON, style={"fontSize": 28, "flexShrink": 0}),
                dmc.Stack(
                    [
                        dmc.Text(folder.name or str(folder), fw=600, size="md"),
                        dmc.Text(
                            str(folder),
                            size="xs",
                            c="dimmed",
                            style={"overflow": "hidden", "textOverflow": "ellipsis"},
                        ),
                    ],
                    gap=0,
                    style={"minWidth": 0, "flex": 1, "overflow": "hidden"},
                ),
            ],
            gap="sm",
            wrap="nowrap",
            style={"overflow": "hidden"},
        )

    return dmc.Card(
        content,
        withBorder=True,
        shadow="sm",
        radius="md",
        p="lg" if folder is None else "md",
        style={"backgroundColor": "#f8f9fa"} if folder is None else {},
    )


@callback(
    Output("card-custom", "children"),
    Input(FolderSelector.ids.selected_folder("folder-custom"), "data"),
)
def show_custom_selection(path: str | None) -> dmc.Card:
    """Render a folder card for the callback-driven selection."""
    return _folder_card(path)


# %%
# Run the app
# -----------

if __name__ == "__main__":
    app.run()
