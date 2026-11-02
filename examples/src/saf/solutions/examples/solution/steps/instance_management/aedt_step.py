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

"""Backend of the AEDT step."""

from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.aedt import Maxwell2DManager


class Maxwell2DSetupVerificationStep(StepModel):
    """Step to verify the setup of Maxwell 2D instance."""

    instance_created: bool = False
    aedt_version: str = "252"
    origin: list[float] = [0, 0, 0]
    dimension: list[float] = [10, 10]

    @transaction(self=StepSpec(download=["aedt_version"], upload=["instance_created"]), enable_termination_event=True)
    @create_instance("maxwell_2d_instance", Maxwell2DManager)
    @long_running
    def launch_aedt(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        """Initialize the Maxwell 2D instance."""
        self.transaction.raise_event(message="Initializing AEDT Maxwell 2D instance.", stream_name="aedt-output-stream")
        try:
            maxwell_2d_instance.initialize(version=self.aedt_version)
        except Exception as e:
            self.transaction.raise_event(
                message=f"Failed to initialize AEDT Maxwell 2D instance: {str(e)}", stream_name="aedt-output-stream"
            )
            raise
        self.transaction.raise_event(
            message="AEDT Maxwell 2D instance initialized successfully.",
            stream_name="aedt-output-stream",
        )
        self.instance_created = True

    @transaction(self=StepSpec(download=["origin", "dimension"]), enable_termination_event=True)
    @instance("maxwell_2d_instance")
    @long_running
    def add_rectangle(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        """Add a rectangle to the Maxwell 2D instance."""
        self.transaction.raise_event(
            message="Adding rectangle to AEDT Maxwell 2D instance.",
            stream_name="aedt-output-stream",
        )
        try:
            maxwell_2d_instance.instance.modeler.create_rectangle(self.origin, self.dimension)  # type: ignore
        except Exception as e:
            self.transaction.raise_event(
                message=f"Failed to add rectangle to AEDT Maxwell 2D instance: {e}",
                stream_name="aedt-output-stream",
            )
            raise
        self.transaction.raise_event(
            message="Rectangle added to AEDT Maxwell 2D instance successfully.",
            stream_name="aedt-output-stream",
        )

    @transaction(enable_termination_event=True)
    @instance("maxwell_2d_instance")
    @long_running
    def analyze_design(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        """Run the analysis on the Maxwell 2D instance."""
        self.transaction.raise_event(
            message="Running analysis on AEDT Maxwell 2D instance.",
            stream_name="aedt-output-stream",
        )
        try:
            result = maxwell_2d_instance.instance.analyze()  # type: ignore
            assert result, "Unsuccessful analysis on AEDT Maxwell 2D instance."
        except Exception as e:
            self.transaction.raise_event(
                message=f"Failed to run analysis on AEDT Maxwell 2D instance: {e}",
                stream_name="aedt-output-stream",
            )
            raise
        self.transaction.raise_event(
            message="Analysis on AEDT Maxwell 2D instance completed successfully.",
            stream_name="aedt-output-stream",
        )

    @transaction(self=StepSpec(upload=["instance_created"]), enable_termination_event=True)
    @instance("maxwell_2d_instance")
    @long_running
    def shutdown_aedt(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        """Shutdown the AEDT Maxwell 2D instance."""
        self.transaction.raise_event(
            message="Shutting down AEDT Maxwell 2D instance.",
            stream_name="aedt-output-stream",
        )
        try:
            maxwell_2d_instance.shutdown()
        except Exception as e:
            self.transaction.raise_event(
                message=f"Failed to shutdown AEDT Maxwell 2D instance: {e}",
                stream_name="aedt-output-stream",
            )
            raise
        self.transaction.raise_event(
            message="AEDT Maxwell 2D instance shutdown successfully.",
            stream_name="aedt-output-stream",
        )
        self.instance_created = False
