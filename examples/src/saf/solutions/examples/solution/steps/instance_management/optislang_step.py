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

# ©2025, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""optiSLang step for the advanced solution example."""

from pathlib import Path
from typing import TYPE_CHECKING

from ansys.bdm.api import NO_ENTITY, EntityHandle
import ansys.optislang.core.examples as examples  # type: ignore
from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.optislang_wrapper import OslManager

if TYPE_CHECKING:
    from ansys.optislang.core.project_parametric import Design  # pyright: ignore[reportMissingTypeStubs]


class OptislangStep(StepModel):
    """optiSLang step for the advanced solution example."""

    instance_created: bool = False
    version: str = "242"
    working_dir: str = ""
    objective: str = ""
    evaluate_design_example: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(upload=["evaluate_design_example"]))
    def download_example_file(self) -> None:
        """Download the example file for optiSLang evaluation."""
        self.transaction.raise_event(message="Downloading example file.", stream_name="optislang-output-stream")
        try:
            example_path: str = examples.get_files("ten_bar_truss")[1][0]  # type: ignore
            with Path(example_path).open(mode="rb") as f:  # type: ignore
                self.evaluate_design_example = self.storage_scope.store_stream(f, Path("project.opf"))
        except Exception as e:
            self.transaction.raise_event(
                message=f"Download failed: {e}",
                stream_name="optislang-output-stream",
            )
            raise
        self.transaction.raise_event(message="Example file downloaded.", stream_name="optislang-output-stream")

    @transaction(
        self=StepSpec(download=["version", "evaluate_design_example"], upload=["instance_created"]),
        enable_termination_event=True,
    )
    @create_instance("osl_manager", OslManager)
    @long_running
    def launch_optislang(self, osl_manager: OslManager) -> None:
        """Initialize the optiSLang instance with the project file."""
        self.transaction.raise_event(message="Initializing optiSLang instance.", stream_name="optislang-output-stream")
        try:
            osl_manager.initialize(self.evaluate_design_example, self.version)
        except Exception as e:
            self.transaction.raise_event(
                message=f"optiSLang initialization failed: {e}",
                stream_name="optislang-output-stream",
            )
            raise
        self.instance_created = True
        self.transaction.raise_event(message="optiSLang initialized.", stream_name="optislang-output-stream")

    @transaction(self=StepSpec(upload=["objective", "working_dir"]), enable_termination_event=True)
    @instance("osl_manager")
    @long_running
    def evaluate_design(self, osl_manager: OslManager):
        """Evaluate the reference design of the optiSLang project."""
        self.transaction.raise_event(message="Evaluating design.", stream_name="optislang-output-stream")
        try:
            osl = osl_manager.instance
            project = osl.application.project
            # Evaluate reference design
            root_system = project.root_system  # type: ignore
            design = root_system.get_reference_design()
            evaluated_design = root_system.evaluate_design(design)
            self.objective = str(evaluated_design.objectives[0].value)  # type: ignore
        except Exception as e:
            self.transaction.raise_event(
                message=f"Design evaluation failed: {e}", stream_name="optislang-output-stream"
            )
            raise
        self.transaction.raise_event(message="Design evaluation succeeded.", stream_name="optislang-output-stream")
        self.transaction.raise_event(
            message=f"Current objective: {self.objective}.",
            stream_name="optislang-output-stream",
        )

    @transaction(self=StepSpec(upload=["objective", "working_dir"]), enable_termination_event=True)
    @instance("osl_manager")
    @long_running
    def refine_design(self, osl_manager: OslManager):
        """Refine the design by modifying the parameters of the reference design."""
        successful_designs: list[Design] = []
        self.transaction.raise_event(message="Refining design.", stream_name="optislang-output-stream")
        try:
            root_system = osl_manager.instance.application.project.root_system  # type: ignore
            design = root_system.get_reference_design()
            evaluated_design = root_system.evaluate_design(design)
            successful_designs.append(evaluated_design)
            for i in range(1):
                design = successful_designs[-1].copy_unevaluated_design()
                parameters = design.parameters
                parameter_value = parameters[i].value  # type: ignore
                parameters[i].value = parameter_value - 1  # type: ignore
                evaluated_design = root_system.evaluate_design(design)
                successful_designs.append(evaluated_design)
                self.objective = str(evaluated_design.objectives[0].value)  # type: ignore

        except Exception as e:
            self.transaction.raise_event(message=f"Design refine failed: {e}", stream_name="optislang-output-stream")
            raise
        self.transaction.raise_event(message="Design refine succeeded.", stream_name="optislang-output-stream")
        self.transaction.raise_event(
            message=f"Current objective: {self.objective}.",
            stream_name="optislang-output-stream",
        )

    @transaction(self=StepSpec(upload=["instance_created"]), enable_termination_event=True)
    @instance("osl_manager")
    @long_running
    def shutdown_optislang(self, osl_manager: OslManager) -> None:
        """Close the optiSLang instance."""
        self.transaction.raise_event(
            message="Starting to shutdown the instance.",
            stream_name="optislang-output-stream",
        )
        try:
            osl_manager.shutdown()
        except Exception as e:
            self.transaction.raise_event(
                message=f"optiSLang shutdown failed: {e}",
                stream_name="optislang-output-stream",
            )
            raise
        self.instance_created = False
        self.transaction.raise_event(
            message="optiSLang instance shutdown complete.",
            stream_name="optislang-output-stream",
        )
