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

"""HPS simulation runner -- orchestrates job submission and monitoring via HpsService."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ansys.saf.glow.solution.hps import HpsExecutionSpecification, HpsOutputFileSpecification, HpsSimpleProject

from saf.solutions.examples.solution.airfoil_explorer import logic
from saf.solutions.examples.solution.airfoil_explorer.logic.exec_simulation import main as exec_simulation
from saf.solutions.examples.solution.airfoil_explorer.logic.parameters import SimulationResults
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.base import SimulationRunner
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.simulation_status import SimulationStatus

if TYPE_CHECKING:
    from saf.solutions.examples.solution.airfoil_explorer.logic.parameters import (
        AirfoilParameters,
        FlowParameters,
        GridParameters,
    )


class HpsUnavailableError(RuntimeError):
    """Raised when HPS execution cannot be used."""


class HpsSimulationRunner(SimulationRunner):
    """Attempt to run simulation via HPS service."""

    def _run(self, airfoil: AirfoilParameters, grid: GridParameters, flow: FlowParameters) -> HpsSimpleProject:
        super()._run(airfoil, grid, flow)
        self.step._log("info", "HPS runner selected; attempting remote submission.")

        try:
            execution_spec = HpsExecutionSpecification(
                function=exec_simulation,
                module=logic,
                output_parameters={
                    "simulation_results": SimulationResults,
                    "mesh_figure_png": HpsOutputFileSpecification(evaluation_path="mesh_figure.png"),
                    "flow_figure_png": HpsOutputFileSpecification(evaluation_path="flow_figure.png"),
                },
                dependencies=["numpy==1.26.4", "scipy==1.15.3", "plotly==6.5.2", "pydantic==2.12.5", "matplotlib"],
            )
            hps_project: HpsSimpleProject = execution_spec.execute(
                airfoil=airfoil,
                grid=grid,
                flow=flow,
            )

            self.step.job_id = hps_project.hps_project_identifier
            self.step.job_status = SimulationStatus.QUEUED.value
            while True:
                eval_status = hps_project.status.evaluation_status.value

                self.step.job_status = eval_status
                self.step.update_job_status()

                if eval_status == "evaluated":
                    break
                elif eval_status in ("failed", "aborted", "timeout", "cancelled"):
                    raise HpsUnavailableError(f"HPS job ended with status {eval_status}")
                else:
                    time.sleep(4)

            return hps_project
        except Exception as exc:
            raise HpsUnavailableError(f"HPS submission failed: {exc}") from exc

    def _store_results(self, hps_project: HpsSimpleProject) -> None:
        super()._store_results(hps_project)
        if hps_project.mesh_figure_png:
            self.step.mesh_png_handle = hps_project.mesh_figure_png
            self.step._log("info", "Successfully downloaded mesh PNG from HPS")
        else:
            self.step._log("warning", "Failed to download mesh PNG from HPS")

        if hps_project.flow_figure_png:
            self.step.flow_png_handle = hps_project.flow_figure_png
            self.step._log("info", "Successfully downloaded flow PNG from HPS")
        else:
            self.step._log("warning", "Failed to download flow PNG from HPS")
