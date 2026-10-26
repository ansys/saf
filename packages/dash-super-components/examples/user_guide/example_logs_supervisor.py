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
User guide example for the LogsSupervisor component.

Demonstrates how to configure the Dash app with the required external script,
define a log file layout, and activate real-time monitoring via a callback.
A background thread writes random log messages to a temporary file to simulate
a long-running process.
See the LogsSupervisor page in the User Guide for the full reference documentation.
"""

from pathlib import Path

# [imports-start]
from ansys.solutions.dash_super_components import LogsSupervisor

# [imports-end]
from ansys.solutions.dash_super_components import add_super_components_assets

from dash import _dash_renderer

from dash_extensions.enrich import DashProxy, html
import dash_mantine_components as dmc

_dash_renderer._set_react_version("18.2.0")

app = DashProxy(
    __name__,
    external_scripts=["/super-components/dashAgGridComponentFunctions.js"],
)
add_super_components_assets(app)


log_file_path = Path(__file__).parent / "sample_files/sample_log_file.log"


# [basic-layout-start]
def layout():
    return html.Div(
        [
            LogsSupervisor(
                log_file=log_file_path,
                log_format="%(levelname)s - %(module)s - %(message)s",
                aio_id="logs-supervisor",
            ),
        ]
    )


# [basic-layout-end]


log_file_path_advanced = Path(__file__).parent / "sample_files/sample_log_file_long.log"


# [advanced-layout-start]
def layout_advanced():
    return html.Div(
        [
            LogsSupervisor(
                log_file=log_file_path_advanced,
                log_format="%(levelname)s - %(module)s - %(message)s",
                aio_id="logs-supervisor-advanced",
                width="70%",
                grid_props={
                    "style": {
                        "height": "600px",
                    },
                    "dashGridOptions": {"theme": "themeBalham"},
                },
                interval=1000,
                show_error_notifications=False,
            ),
        ]
    )


# [advanced-layout-end]


app.layout = dmc.MantineProvider(
    [
        dmc.NotificationContainer(id="notification-container", position="top-right"),
        html.Div(
            [
                dmc.Title("Logs Supervisor — User Guide Example", order=2, mb="md"),
                dmc.Text(
                    "Default LogsSupervisor. "
                    "For this simple example, the logs are read from a sample log file which "
                    "is included in the repository and does not update. ",
                    c="dimmed",
                    mb="xl",
                ),
                layout(),
                dmc.Divider(my="xl"),
                dmc.Text(
                    "Customized LogsSupervisor. "
                    "For this simple example, the logs are read from a longer sample log file "
                    "which is included in the repository and does not update. ",
                    c="dimmed",
                    mb="xl",
                ),
                layout_advanced(),
            ],
            style={"maxWidth": 960, "margin": "40px auto", "padding": "0 16px"},
        ),
    ]
)


if __name__ == "__main__":
    app.run(debug=True)
