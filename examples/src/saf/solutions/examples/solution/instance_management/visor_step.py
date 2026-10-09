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

"""Visor step for the instance management examples."""

from pathlib import Path

from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.visor import VisorManager
from ansys.visor.viewer import Metadata

CUBE_PATH = Path(__file__).parent / "shapes" / "cube.vtm"
PISTON_PATH = Path(__file__).parent / "shapes" / "piston_rod.vtkhdf"
SPHERES_PATH = Path(__file__).parent / "shapes" / "vtk_scene_sphere_l2_b3_r32_v3_c1_z3.vtm"
ELBOW_PATH = Path(__file__).parent / "shapes" / "elbow-2-00005.vtkhdf"


class VisorStep(StepModel):
    """Step to manage a Visor instance."""

    version: str = "0"
    visor_started: bool = False
    visor_host: str = ""
    visor_port: int | None = None

    @transaction(
        self=StepSpec(download=["version"], upload=["visor_started", "visor_host", "visor_port"]),
        enable_termination_event=True,
    )
    @create_instance("visor_manager", VisorManager)
    @long_running
    def start_visor(self, visor_manager: VisorManager) -> None:
        """Start the Visor instance."""
        self.transaction.raise_event(message="Initializing VISOR instance.", stream_name="visor-output-stream")
        try:
            visor_manager.initialize(
                version=self.version,
            )
            self.visor_host = visor_manager.instance.host
            self.visor_port = visor_manager.instance.port
            self.visor_started = True
        except Exception as e:
            self.transaction.raise_event(
                message=f"VISOR initialization failed: {e}",
                stream_name="visor-output-stream",
            )
            raise
        self.transaction.raise_event(message="VISOR initialized.", stream_name="visor-output-stream")

    @transaction(self=StepSpec())
    @instance("visor_manager")
    def show_piston(self, visor_manager: VisorManager) -> None:
        """Display the piston rod in the running Visor instance."""
        self.transaction.raise_event(message="Loading piston rod in VISOR.", stream_name="visor-output-stream")
        try:
            visor_manager.instance.update(PISTON_PATH.as_posix(), Metadata(name="Piston Rod", unit="m"))
        except Exception as e:
            self.transaction.raise_event(message=f"VISOR piston rod update failed: {e}", stream_name="visor-output-stream")
            raise
        self.transaction.raise_event(message="Piston rod displayed in VISOR.", stream_name="visor-output-stream")

    @transaction(self=StepSpec())
    @instance("visor_manager")
    def show_spheres(self, visor_manager: VisorManager) -> None:
        """Display the spheres in the running Visor instance."""
        self.transaction.raise_event(message="Loading spheres in VISOR.", stream_name="visor-output-stream")
        try:
            visor_manager.instance.update(SPHERES_PATH.as_posix(), Metadata(name="Spheres", unit="m"))
        except Exception as e:
            self.transaction.raise_event(message=f"VISOR shape update failed: {e}", stream_name="visor-output-stream")
            raise
        self.transaction.raise_event(message="Spheres displayed in VISOR.", stream_name="visor-output-stream")


    @transaction(self=StepSpec())
    @instance("visor_manager")
    def show_elbow(self, visor_manager: VisorManager) -> None:
        """Display the elbow in the running Visor instance."""
        self.transaction.raise_event(message="Loading elbow in VISOR.", stream_name="visor-output-stream")
        try:
            visor_manager.instance.update(ELBOW_PATH.as_posix(), Metadata(name="Elbow", unit="m"))
        except Exception as e:
            self.transaction.raise_event(message=f"VISOR elbow update failed: {e}", stream_name="visor-output-stream")
            raise
        self.transaction.raise_event(message="Elbow displayed in VISOR.", stream_name="visor-output-stream")


    @transaction(self=StepSpec(upload=["visor_started"]))
    @instance("visor_manager")
    def shutdown_visor(self, visor_manager: VisorManager) -> None:
        """Close the Visor instance."""

        self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="visor-output-stream")
        try:
            visor_manager.shutdown()
            self.visor_started = False
        except Exception as e:
            self.transaction.raise_event(message=f"VISOR shutdown failed: {e}", stream_name="visor-output-stream")
            raise
        self.transaction.raise_event(
            message="VISOR instance shutdown complete.",
            stream_name="visor-output-stream",
        )
