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

"""Geometry step for the advanced solution example."""

from ansys.geometry.core.math import Point2D  # type: ignore
from ansys.geometry.core.misc import UNITS, Distance  # type: ignore
from ansys.geometry.core.sketch import Sketch  # type: ignore
from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.geometry import GeometryManager
from pint import Quantity


class GeometryStep(StepModel):
    """Geometry step for the advanced solution example."""

    version: str = "252"
    body_faces: int = 0
    body_edges: int = 0
    active_design_name: str = ""
    geometry_available: bool = False

    @transaction(self=StepSpec(download=["version"]), enable_termination_event=True)
    @create_instance("geometry_manager", GeometryManager)
    @long_running
    def launch_geometry(self, geometry_manager: GeometryManager) -> None:
        """Launch the Geometry instance and check its availability."""
        self.transaction.raise_event(message="Initializing Geometry instance.", stream_name="geometry-output-stream")
        try:
            geometry_manager.initialize(version=self.version)
        except Exception as e:
            self.transaction.raise_event(
                message=f"Geometry initialization failed: {e}",
                stream_name="geometry-output-stream",
            )
            raise
        self.transaction.raise_event(message="Geometry initialized.", stream_name="geometry-output-stream")

    @transaction(self=StepSpec(upload=["body_faces", "body_edges"]), enable_termination_event=True)
    @instance("geometry_manager")
    @long_running
    def extrude_slot(self, geometry_manager: GeometryManager) -> None:
        """Create a slot in the Geometry instance by extruding a sketch."""
        self.transaction.raise_event(message="Starting extrude slot transaction.", stream_name="geometry-output-stream")
        try:
            # Create design on Geometry instance
            design = geometry_manager.instance.create_design("ExtrudeSlot")

            # Create a Sketch object and draw a slot
            sketch = Sketch()
            sketch.slot(Point2D([10, 10], UNITS.mm), Quantity(10, UNITS.mm), Quantity(5, UNITS.mm))  # type: ignore

            # Extrude the sketch
            body = design.extrude_sketch(name="MySlot", sketch=sketch, distance=Distance(50, UNITS.mm))  # type: ignore
            if not body:
                raise RuntimeError("Body was not created.")
            self.body_faces = len(body.faces)
            self.body_edges = len(body.edges)
        except Exception as e:
            self.transaction.raise_event(message=f"Extrude Slot failed: {e}", stream_name="geometry-output-stream")
            raise
        self.transaction.raise_event(message="Extrude Slot succeeded.", stream_name="geometry-output-stream")

    @transaction(self=StepSpec(upload=["active_design_name"]), enable_termination_event=True)
    @instance("geometry_manager")
    @long_running
    def get_active_design(self, geometry_manager: GeometryManager) -> None:
        """Get the name of the currently active design."""
        self.transaction.raise_event(message="Getting active design name.", stream_name="geometry-output-stream")
        try:
            self.active_design_name = geometry_manager.instance.read_existing_design().name
            self.transaction.raise_event(
                message=f"Active design name: {self.active_design_name}.",
                stream_name="geometry-output-stream",
            )
        except Exception as e:
            self.transaction.raise_event(message=f"Get active design failed: {e}", stream_name="geometry-output-stream")
            raise
        self.transaction.raise_event(message="Get active design succeeded.", stream_name="geometry-output-stream")

    @transaction(self=StepSpec(upload=["geometry_available"]))
    @instance("geometry_manager")
    def shutdown_geometry(self, geometry_manager: GeometryManager) -> None:
        """Close the Geometry instance."""
        self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="geometry-output-stream")
        try:
            geometry_manager.shutdown()
            self.geometry_available = False
        except Exception as e:
            self.transaction.raise_event(message=f"Geometry shutdown failed: {e}", stream_name="geometry-output-stream")
            raise
        self.transaction.raise_event(
            message="Geometry instance shutdown complete.",
            stream_name="geometry-output-stream",
        )
