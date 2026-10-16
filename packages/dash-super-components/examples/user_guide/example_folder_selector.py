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
User guide example for the FolderSelector component.

Demonstrates basic usage and advanced usage (bootstrap mode with custom button
props and options).  Includes a callback that displays the selected folder path.
See the FolderSelector page in the User Guide for the full reference documentation.
"""

# [imports-start]
from pathlib import Path
import sys

from ansys.solutions.dash_super_components import FolderSelector
from ansys.solutions.dash_super_components.folder_selector import FolderSelectorMode
# [imports-end]

from dash import _dash_renderer
from dash_extensions.enrich import DashProxy, Input, Output, callback, html
import dash_mantine_components as dmc

# [configure-start]
import ansys.solutions.dash_super_components as dsc

dsc.configure(enable_beta_features=True)
# [configure-end]

_dash_renderer._set_react_version("18.2.0")

app = DashProxy(__name__)


# [basic-layout-start]
def layout():
    return html.Div(
        [
            FolderSelector(
                aio_id="select_folder_basic",
                options={"browse_from": str(Path.home())}
                if sys.platform.startswith("linux")
                else None,
            )
        ]
    )


# [basic-layout-end]


# [advanced-layout-start]
def advanced_layout():
    return html.Div(
        [
            FolderSelector(
                aio_id="select_folder_advanced",
                mode=FolderSelectorMode.BOOTSTRAP,
                browse_button_props={
                    "disabled": False,
                    "children": "Select the data source directory",
                },
                clear_button_props={
                    "size": "lg",
                },
                options={
                    "display_field": {"enabled": False},
                    "default_path": "/path/to/default",
                    "browse_from": "/path/to/root",
                    "topmost": True,
                    "max_path_length": 260,
                    "max_tree_depth": 8,
                    "max_children_per_node": 20,
                },
                value="/path/to/preselected/folder",
                style={"margin": "2rem"},
            )
        ]
    )


# [advanced-layout-end]


app.layout = dmc.MantineProvider(
    children=[
        dmc.NotificationContainer(id="notification-container", position="bottom-center"),
        html.Div(
            [
                dmc.Title("Folder Selector — User Guide Example", order=2, mb="md"),
                dmc.Text("Basic (auto-detect mode):", fw=600, mb="xs"),
                layout(),
                dmc.Divider(my="xl"),
                dmc.Text("Advanced (bootstrap mode):", fw=600, mb="xs"),
                advanced_layout(),
                html.Div(id="output-div", style={"marginTop": "8px", "color": "dimgray"}),
            ],
            style={"maxWidth": 1000, "margin": "40px auto", "padding": "0 16px"},
        ),
    ]
)


# [callback-start]
@callback(
    Output("output-div", "children"),
    Input(FolderSelector.ids.selected_folder("select_folder_advanced"), "data"),
)
def display_selected_folder(selected_folder):
    if selected_folder:
        return f"Selected folder: {selected_folder}"
    return "No folder selected"


# [callback-end]


if __name__ == "__main__":
    app.run(debug=True)
