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

# ©2026, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Module containing the HPS job submission step.

Demonstrates:
  Events;
  Termination Events;
  HPS Job Submission; and
  Various mechanisms for transferring data between HPS and the solution.
"""

import json
import logging
import time

from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, long_running, transaction
from ansys.saf.glow.solution.hps import (
    HpsExecutionSpecification,
    HpsInputFileSpecification,
    HpsOutputDirectorySpecification,
    HpsOutputFileSpecification,
)

from saf.solutions.examples.solution.scripts.calculate_sum import calculate_sum

logger = logging.getLogger(__name__)

INITIAL_STATUS = "No Job Created"


class HpsJobSubmissionStep(StepModel):
    """Step definition of the HPS job submission step."""

    first_arg: float = 0
    second_arg: float = 0
    result: float | None = None

    input_file: EntityHandle = NO_ENTITY
    input_directory: EntityHandle = NO_ENTITY
    output_file: EntityHandle = NO_ENTITY
    output_directory: EntityHandle = NO_ENTITY

    status: str = INITIAL_STATUS

    @transaction(
        self=StepSpec(upload=["output_file", "output_directory", "input_file", "input_directory", "result", "status"])
    )
    def reset(self) -> None:
        """Reset all the computed fields of the step data model back to their starting state."""
        self.input_file = NO_ENTITY
        self.input_directory = NO_ENTITY
        self.output_file = NO_ENTITY
        self.output_directory = NO_ENTITY
        self.result = None
        self.status = INITIAL_STATUS

    @transaction(self=StepSpec(upload=["input_file", "input_directory"], download=["first_arg", "second_arg"]))
    def write_persisted_inputs(self) -> None:
        """Create persisted files for the step."""
        # generate JSON content
        content = {
            "first_arg": self.first_arg,
            "second_arg": self.second_arg,
        }
        content_str = json.dumps(content)

        # persist file
        file_path = self.storage_scope.get_storage_root() / "persisted_inputs.json"
        file_path.write_text(content_str)
        self.input_file = self.storage_scope.store(file_path)

        # persist directory
        directory_path = self.storage_scope.get_storage_root() / "persisted_input_dir"
        directory_path.mkdir()
        inner_file_path = directory_path / "inputs.json"
        inner_file_path.write_text(content_str)
        self.input_directory = self.storage_scope.store(directory_path)

    def _push_status(self, status: str):
        self.status = status
        self.transaction.raise_event(status, stream_name="status")
        self.transaction.upload(["status"])

    @long_running
    @transaction(
        self=StepSpec(
            upload=["status", "result", "output_file", "output_directory"], download=["input_file", "input_directory"]
        ),
        enable_termination_event=True,
    )
    def run_job(self) -> None:
        """Submit job to HPS."""
        self._push_status("Submitting job to HPS")

        # fetch JSON content
        content_str = self.storage_scope.get_text(self.input_file)
        input_data = json.loads(content_str)
        first_arg = input_data["first_arg"]
        second_arg = input_data["second_arg"]

        # create transient files
        file_path = self.storage_scope.get_storage_root() / "inputs.json"
        file_path.write_text(content_str)
        file_path_for_redirection = self.storage_scope.get_storage_root() / "inputs_for_redirection.json"
        file_path_for_redirection.write_text(content_str)

        # create transient directory
        directory_path = self.storage_scope.get_storage_root() / "input_dir"
        directory_path.mkdir()
        inner_file_path = directory_path / "inputs.json"
        inner_file_path.write_text(content_str)

        execution_spec = HpsExecutionSpecification(
            function=calculate_sum,
            # here we return the result in several different ways from the job
            # this is just an example!!
            output_parameters={
                "result": float,
                "output_directory": HpsOutputDirectorySpecification(),
                # Important: EntityHandle is NOT the default return type
                # on HpsOutputFileSpecification
                "output_file": HpsOutputFileSpecification(
                    return_type=EntityHandle, evaluation_path="output_for_redirection.json"
                ),
            },
        )
        # here we pass the same data in several different ways to the job script
        # this is just an example!!
        hps_project = execution_spec.execute(
            first_arg=first_arg,  # arg passed directly
            second_arg=second_arg,  # arg passed directly
            persisted_input_file=(
                self.input_file
            ),  # args passed as file which a copy of a file referenced by an EntityHandle
            persisted_input_directory=(
                self.input_directory
            ),  # args passed as file inside a directory which is a copy of a directory referenced by an EntityHandle
            transient_input_file=file_path,  # args passed as file which a copy of a file referenced by a Path
            transient_input_redirected_file=HpsInputFileSpecification(
                file_path_for_redirection, "redirected_input.json"
            ),  # args passed as file inside a renamed directory which is a copy of a referenced directory
            transient_input_directory=(
                directory_path
            ),  # args passed as file inside a directory which is a copy of a directory referenced by an EntityHandle
        )

        self._push_status("HPS Job submitted")

        logger.info(f"started monitoring HPS job")
        NUMBER_OF_ITERATIONS = 240
        iterations = 0
        while iterations != NUMBER_OF_ITERATIONS and not hps_project.finished:
            self._push_status(hps_project.status.evaluation_status.value)
            time.sleep(1)
            iterations += 1

        logger.info(f"HPS Job finished with status: {hps_project.status.evaluation_status.value}")

        if hps_project.finished:
            status = hps_project.status.evaluation_status.value
            self.output_file = hps_project.output_file  # type: ignore
            self.output_directory = hps_project.output_directory  # type: ignore
            self.result = hps_project.result  # type: ignore
        else:
            status = "HPS Job took longer than expected"
            self.output_file = NO_ENTITY  # type: ignore
            self.output_directory = NO_ENTITY  # type: ignore
            self.result = None  # type: ignore

        self._push_status(status)
        logger.info(f"completed monitoring HPS job")
