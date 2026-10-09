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

"""Backend of job submission step."""

import time

from saf.solutions.my_solution.solution.scripts.simple_add import simple_add  #

from ansys.saf.glow.solution import StepModel, StepSpec, transaction
from ansys.saf.glow.solution.hps import (
    NO_HPS_SIMPLE_PROJECT,
    HpsExecutionSpecification,
    HpsJobEvaluationStatus,
    HpsSimpleProject,
)


class FirstStep(StepModel):
    """HPS job submission step model for executing jobs on HPS."""

    hps_project: HpsSimpleProject = NO_HPS_SIMPLE_PROJECT
    first_arg: float = 0
    second_arg: float = 0
    result: float = 0

    @transaction(self=StepSpec(upload=["hps_project"], download=["first_arg", "second_arg"]))
    def create_and_start_hps_job(self) -> None:
        """Create and start an HPS job."""
        execution_spec = HpsExecutionSpecification(
            function=simple_add,
            output_parameters={
                "result": float,
            },
        )
        self.hps_project = execution_spec.execute(a=self.first_arg, b=self.second_arg)

    @transaction(self=StepSpec(download=["hps_project"], upload=["result"]))
    def wait_for_hps_completion(self):
        """Wait for job completion and retrieve result from HPS project."""
        while not self.hps_project.finished:
            time.sleep(5)

        if self.hps_project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED:
            self.result = self.hps_project.result  # pyright: ignore[reportAttributeAccessIssue]
        else:
            raise Exception(f"HPS job failed with status {self.hps_project.status.evaluation_status}")
