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

"""Runner protocol interface for simulation execution."""

from __future__ import annotations

from abc import ABC
from datetime import datetime
from typing import TYPE_CHECKING

from ansys.saf.glow.solution.hps import HpsSimpleProject

from saf.solutions.examples.solution.airfoil_explorer.logic.parameters import (
    AirfoilParameters,
    FlowParameters,
    GridParameters,
    SimulationResults,
)
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.simulation_status import SimulationStatus

if TYPE_CHECKING:
    from saf.solutions.examples.solution.airfoil_explorer.simulation_step import SimulationStep


class SimulationRunner(ABC):
    """Runner interface for simulation execution."""

    step: "SimulationStep"

    def __init__(self, step: "SimulationStep"):
        """Instantiate base simulation runner."""
        self.step = step

    def _run(
        self, airfoil: AirfoilParameters, grid: GridParameters, flow: FlowParameters
    ) -> SimulationResults | HpsSimpleProject | None:
        self.step.submission_time = datetime.now().isoformat()
        self.step.update_job_status()

    def _store_results(self, tmp: SimulationResults | HpsSimpleProject) -> None:
        if isinstance(tmp, SimulationResults):
            result = tmp
        else:
            result = tmp.simulation_results

        self.step.solve_output = result.solve_output
        self.step.mesh_figure = result.mesh_figure
        self.step.potential_flow_figure = result.flow_figure
        self.step.results_3d_asset = None

        self.step.update_job_status()

    def run(self, airfoil: AirfoilParameters, grid: GridParameters, flow: FlowParameters) -> SimulationStep:
        """Run simulation and store results."""
        results = self._run(airfoil, grid, flow)
        self._store_results(results)
        self.step.job_status = SimulationStatus.COMPLETED.value
        return self.step
