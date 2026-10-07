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

"""Local simulation runner -- synchronous, in-process execution."""

from __future__ import annotations

from saf.solutions.examples.solution.airfoil_explorer.logic.exec_simulation import main as exec_simulation
from saf.solutions.examples.solution.airfoil_explorer.logic.parameters import (
    AirfoilParameters,
    FlowParameters,
    GridParameters,
    SimulationResults,
)
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.base import SimulationRunner
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.simulation_status import SimulationStatus


class LocalSimulationRunner(SimulationRunner):
    """Run simulation locally using existing logic."""

    def _get_storage_root(self):
        return self.step.storage_scope.get_storage_root()

    def _get_mesh_png_path(self) -> str:
        return str(self._get_storage_root() / "mesh.png")

    def _get_flow_png_path(self) -> str:
        return str(self._get_storage_root() / "flow.png")

    def _run(self, airfoil: AirfoilParameters, grid: GridParameters, flow: FlowParameters) -> SimulationResults:
        super()._run(airfoil, grid, flow)
        self.step._log("info", "Starting local simulation.")

        self.step.job_status = SimulationStatus.RUNNING.value
        self.step.update_job_status()

        result = exec_simulation(
            airfoil,
            grid,
            flow,
            mesh_figure_output_path=self._get_mesh_png_path(),
            flow_figure_output_path=self._get_flow_png_path(),
        )
        return result["simulation_results"]

    def _store_results(self, results: SimulationResults) -> None:
        super()._store_results(results)
        self.step.mesh_png_handle = self.step.storage_scope.store(self._get_mesh_png_path())
        self.step.flow_png_handle = self.step.storage_scope.store(self._get_flow_png_path())
        self.step.job_id = "LOCAL"
        self.step._log("info", "Local simulation completed successfully.")
