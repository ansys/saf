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

"""Log supervisor callbacks for the simulation page."""

from __future__ import annotations

from ansys.saf.glow.client import callback
from ansys.solutions.dash_super_components import LogsSupervisor
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, no_update

from saf.solutions.examples.solution.airfoil_explorer.utils.logging import LOG_FORMAT
from saf.solutions.examples.ui.airfoil_explorer.simulation.layout import SIM_LOGFILE_STORE_ID


@callback(
    Output("simulation-logs-supervisor", "log_file"),
    Input(SIM_LOGFILE_STORE_ID, "data"),
)
def update_simulation_logs_supervisor(log_file: str | None) -> str | type[no_update]:
    """Keep the simulation LogsSupervisor pointed to the latest logfile without remounting."""
    if not log_file:
        raise PreventUpdate
    return log_file


@callback(
    Output(LogsSupervisor.ids._log_file_and_format("simulation-logs-supervisor"), "data"),
    Input(SIM_LOGFILE_STORE_ID, "data"),
)
def sync_simulation_logs_storage(log_file: str | None) -> dict | type[no_update]:
    """Keep LogsSupervisor storage in sync with the latest logfile path/format."""
    if not log_file:
        raise PreventUpdate
    return {"log_file_path": log_file, "log_format": LOG_FORMAT}
