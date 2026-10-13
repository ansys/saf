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

from enum import Enum
import logging
import sys
from typing import cast

from pydantic import Field

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow._hps_parametric_studies.api import (
    NO_HPS_SIMPLE_PROJECT,
)
from ansys.saf.glow.solution import StepModel, StepSpec, long_running, transaction
from ansys.saf.glow.solution.hps import (
    HpsJobEvaluationStatus,
    HpsOutputFileSpecification,
    HpsSimpleProject,
)

logger = logging.getLogger(__name__)


class SimpleJobStep(StepModel):
    """simple HPS job which uses files to get data in and out of the job"""

    class State(Enum):
        """states in which the step can exist."""

        Calculating = "calculating"
        ResultAvailable = "result-available"
        ResultNotAvailable = "result-not-available"

    step_state: State = Field(default=State.ResultNotAvailable, strict=False)
    file_path: str = ""
    result_file_content: str = ""
    input_file: EntityHandle = NO_ENTITY
    add_script: EntityHandle = NO_ENTITY
    result_handle: EntityHandle = NO_ENTITY
    hps_project: HpsSimpleProject = NO_HPS_SIMPLE_PROJECT
    time_to_generate_the_output_file: float = 0.0
    collect_interval: int = 0
    inputs_outputs_result: str = ""

    @transaction(
        self=StepSpec(
            upload=["hps_project", "step_state"],
            download=[
                "input_file",
                "add_script",
                "time_to_generate_the_output_file",
                "collect_interval",
            ],
        ),
    )
    @long_running
    def start_job(self) -> None:
        """Compute the sum of two numbers."""
        add_script_handle = self.transaction.get_asset_entity_handle("add_from_file_script.py")
        custom_input_file = self.storage_scope.get_storage_root() / "custom_input.txt"
        custom_input_file.write_text("3 4")
        self.hps_project = HpsSimpleProject.start_hps_job(
            input_values={
                "script": add_script_handle,
                "custom_input_file": custom_input_file,
                "time_to_generate_the_output_file": self.time_to_generate_the_output_file,
            },
            output_parameters={
                "result": HpsOutputFileSpecification(
                    collect_interval=self.collect_interval,
                ),
            },
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )
        self.step_state = SimpleJobStep.State.Calculating

    @transaction(self=StepSpec(upload=["step_state"], download=["hps_project"]))
    def query_hps(self) -> None:
        """Query the parameter study and update results."""
        was_finished = self.hps_project.finished
        status = self.hps_project.status
        if status.evaluation_status == HpsJobEvaluationStatus.EVALUATED:
            self.step_state = SimpleJobStep.State.ResultAvailable
        elif status.evaluation_status in [
            HpsJobEvaluationStatus.FAILED,
            HpsJobEvaluationStatus.ABORTED,
            HpsJobEvaluationStatus.TIMEOUT,
        ]:
            self.step_state = SimpleJobStep.State.ResultNotAvailable
        else:
            self.step_state = SimpleJobStep.State.Calculating

        if self.step_state == SimpleJobStep.State.Calculating:
            assert not was_finished
        else:
            assert self.hps_project.finished

    @transaction(self=StepSpec(upload=["result_file_content", "result_handle"], download=["step_state", "hps_project"]))
    def fetch_file(self) -> None:
        """Upload the result file."""
        if self.step_state != SimpleJobStep.State.ResultAvailable:
            raise RuntimeError("result not available")
        self.result_handle = cast("EntityHandle", self.hps_project.result)  # type: ignore
        self.result_file_content = self.storage_scope.get_text(self.result_handle)

    @transaction(self=StepSpec(upload=["result_file_content"], download=["hps_project"]))
    def fetch_file_before_job_completion(self) -> None:
        """Upload the result file during the job execution."""
        self.result_file_content = ""
        result_handle = cast("EntityHandle", self.hps_project.result)  # type: ignore
        if result_handle is not None:  # type: ignore
            self.result_file_content = self.storage_scope.get_text(result_handle)
