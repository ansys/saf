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

"""Shared utilities for LogsSupervisor components."""

from __future__ import annotations

from ansys.solutions.dash_super_components import LogsSupervisor
from dash_extensions.enrich import html

from saf.solutions.examples.solution.airfoil_explorer.utils.logging import LOG_FORMAT

# Standard grid props for LogsSupervisor components
LOGS_GRID_PROPS = {
    "columnDefs": [
        LogsSupervisor.get_logging_formatter_representation("message"),
        LogsSupervisor.get_logging_formatter_representation("asctime"),
        LogsSupervisor.get_logging_formatter_representation("levelname"),
        LogsSupervisor.get_logging_formatter_representation("module"),
    ],
    "columnSize": "sizeToFit",
    "columnSizeOptions": {"keys": ["asctime", "levelname"], "skipHeader": True},
    "style": {
        "width": "100%",
        "height": "260px",
        "margin": "auto",
        "overflow": "auto",
    },
}


def create_logs_panel(log_file: str, component_id: str, key_prefix: str) -> html.Div:
    """Create a stable LogsSupervisor wrapper (no remount on log_file change)."""
    return html.Div(
        LogsSupervisor(
            log_file=log_file,
            log_format=LOG_FORMAT,
            aio_id=component_id,
            grid_props=LOGS_GRID_PROPS,
        ),
        key=key_prefix,
    )
