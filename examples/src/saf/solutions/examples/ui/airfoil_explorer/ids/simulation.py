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

"""IDs for simulation components."""


class SimulationIds:
    """Simulation page component IDs."""

    # layout
    TABS = "simulation-tabs"

    # displays
    MESH_FIGURE = "simulation-mesh-figure"
    FLOW_FIGURE = "simulation-flow-figure"
    RESULTS_3D = "simulation-3d-container"

    # logs
    LOGS_CONTAINER = "simulation-logs-container"
    LOGS_SUPERVISOR = "simulation-logs-supervisor"

    # Visor result selector
    VISOR_RESULT_SELECTOR = "sim-visor-result-selector"
    VISOR_RESULT_SELECTOR_TOOLTIP = "simulation-visor-selector-tooltip"

    # input form
    NXI_INPUT = "simulation-nxi"
    NETA_INPUT = "simulation-neta"
    AOA_INPUT = "simulation-aoa"
    VINF_INPUT = "simulation-vinf"
    GENERATE_MESH_BUTTON = "simulation-generate-mesh"
    SUBMIT_BUTTON = "simulation-submit"
    HELP_ICON = "simulation-setup-help-icon"
    HELP_MODAL = "simulation-setup-help-modal"
