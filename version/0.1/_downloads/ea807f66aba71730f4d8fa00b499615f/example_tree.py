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
Tree
====

A minimal Dash app showing how to use the :class:`~ansys.solutions.dash_super_components.Tree`
component.

See the `Tree
<https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/tree.html#ref_tree>`_
page in the User Guide for the full reference documentation.

.. note::

   Run this file directly to launch the app:

   .. code-block:: bash

       pip install ansys-solutions-dash-super-components
       python example_tree.py

   Then open ``http://localhost:8050`` in your browser.

   To test with a URL path prefix:

   .. code-block:: bash

       REQUESTS_PATHNAME_PREFIX=/myapp/ python example_tree.py

   Then open ``http://localhost:8050/myapp`` in your browser.
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
# The optional ``REQUESTS_PATHNAME_PREFIX`` environment variable lets you test the
# app behind a URL path prefix. See the `Adding external scripts with a URL path prefix
# <https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/getting-started.html#ref_path_prefix>`_
# section of the Getting Started page for details.

import os
from typing import Any

from ansys.solutions.dash_super_components import Tree, add_super_components_assets
from dash import _dash_renderer
from dash_extensions.enrich import DashProxy, Input, Output, callback, html
import dash_mantine_components as dmc

# Required only for Dash 2.x to use Mantine-based components
_dash_renderer._set_react_version("18.2.0")

# Set REQUESTS_PATHNAME_PREFIX to test the app with a URL prefix.
# For example: REQUESTS_PATHNAME_PREFIX="myapp"
_url_prefix = os.getenv("REQUESTS_PATHNAME_PREFIX", "").strip("/")
_url_base_pathname = f"/{_url_prefix}/" if _url_prefix else "/"

app = DashProxy(__name__, url_base_pathname=_url_base_pathname)
add_super_components_assets(app)

# %%
# Define the tree data
# --------------------
#
# The ``items`` prop accepts a list of item dictionaries.
# The full schema for each item dictionary is documented in the `Tree structure definition
# <https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/tree.html#tree_item_definition_properties>`_
# section in the User Guide.
#
# The tree below models a three-stage CFD workflow with three levels of nesting:
#
# * **Pre-processing** is expanded on load (``"expanded": True``) so the user
#   immediately sees its child nodes *Geometry* and *Mesh*.
# * **Solving** and **Post-processing** are collapsed.  *Post-processing* has no
#   children (a leaf node).
# * Icons for the tree items are given through their ``icon`` values, which use
#   `Iconify <https://icon-sets.iconify.design/>`_ icon identifiers and require the app to have
#   internet access to load the icons from the Iconify CDN. For alternatives that work in offline
#   environments, see the ``Tree`` `Icons
#   <https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/icons.html#ref_icons>`_
#   section in the User Guide.
# * The **Geometry** node is preselected further below via ``selected_item``.

TREE_ITEMS = [
    {
        "id": "pre-processing",
        "text": "Pre-processing",
        "icon": "mdi:file-settings-outline",
        "expanded": True,
        "disabled": False,
        "description": "Geometry and mesh",
        "children": [
            {
                "id": "geometry",
                "text": "Geometry",
                "icon": "mdi:vector-square",
                "expanded": False,
                "disabled": False,
                "description": "CAD geometry",
            },
            {
                "id": "mesh",
                "text": "Mesh",
                "icon": "mdi:grid",
                "expanded": False,
                "disabled": False,
                "description": "Volume mesh",
            },
        ],
    },
    {
        "id": "solving",
        "text": "Solving",
        "icon": "mdi:play-circle-outline",
        "expanded": False,
        "disabled": False,
        "description": "Solver settings and execution",
        "children": [
            {
                "id": "solver-settings",
                "text": "Solver settings",
                "icon": "mdi:tune",
                "expanded": False,
                "disabled": False,
                "description": "Physics and numerics",
            },
            {
                "id": "run",
                "text": "Run",
                "icon": "mdi:rocket-launch-outline",
                "expanded": False,
                "disabled": False,
                "description": "Submit the job",
            },
        ],
    },
    {
        "id": "post-processing",
        "text": "Post-processing",
        "icon": "mdi:chart-line",
        "expanded": False,
        "disabled": False,
        "description": "Results and visualisation",
    },
]

# %%
# Build the layout
# ----------------
#
# The tree lives in the left column. Clicking a node updates the text in the
# right column. Pass ``selected_item`` to preselect a node on first render.

app.layout = dmc.MantineProvider(
    html.Div(
        [
            dmc.Title("Tree", order=2, mb="md"),
            dmc.Text(
                "Click a node to select it. The node ID is shown on the right.",
                c="dimmed",
                mb="xl",
            ),
            dmc.Grid(
                [
                    dmc.GridCol(
                        Tree(
                            aio_id="nav-tree",
                            items=TREE_ITEMS,
                            selected_item="geometry",
                        ),
                        span=4,
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Text(id="active-node-display", p="md"),
                            withBorder=True,
                            radius="md",
                            p="md",
                        ),
                        span=8,
                    ),
                ]
            ),
        ],
        style={"maxWidth": 900, "margin": "40px auto", "padding": "0 16px"},
    )
)

# %%
# Add a callback
# --------------
#
# :attr:`Tree.ids.selected_item` returns the ID of the
# :class:`~dash_extensions.enrich.dcc.Store` sub-component that holds the
# currently selected node.  Its ``data`` property is a dict with an ``index``
# key containing the node ID string.


@callback(
    Output("active-node-display", "children"),
    Input(Tree.ids.selected_item("nav-tree"), "data"),
)
def show_active_node(selected_item: dict[str, Any]) -> str:
    """Display the currently selected tree node."""
    if not selected_item:
        return "No node selected."
    try:
        node_id = Tree.ids.get_index_from_navlink_item_id(selected_item)
        if node_id is None:
            return "No node selected."
    except ValueError:
        return "Invalid selection."
    return f"Active node ID: {node_id}"


# %%
# Run the app
# -----------

if __name__ == "__main__":
    app.run()
