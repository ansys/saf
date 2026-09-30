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

import logging

from ansys.geometry.core import LOG as GEOMETRY_LOGGER  # pyright: ignore
from ansys.geometry.core.math import Point2D  # pyright: ignore
from ansys.geometry.core.misc import UNITS, Distance  # pyright: ignore
from ansys.geometry.core.sketch import Sketch  # pyright: ignore
from pint import Quantity

from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.geometry import GeometryManager

logger = logging.getLogger(__name__)


class GeometryInstanceStep(StepModel):
    version: str = "252"
    body_faces: int = 0
    body_edges: int = 0
    active_design_name: str = ""
    geometry_available: bool = False

    @transaction(self=StepSpec(download=["version"]))
    @create_instance("geometry_manager", GeometryManager)
    @long_running
    def launch_geometry(self, geometry_manager: GeometryManager) -> None:
        geometry_manager.initialize(version=self.version)

    @transaction(self=StepSpec(upload=["geometry_available"]))
    @instance("geometry_manager")
    def refresh_availability(self, geometry_manager: GeometryManager) -> None:
        self.geometry_available = bool(
            geometry_manager._instance_manager_impl._find_instance(),  # pyright: ignore[reportPrivateUsage]
        )

    @transaction(self=StepSpec(upload=["body_faces", "body_edges"]))
    @instance("geometry_manager")
    def extrude_slot(self, geometry_manager: GeometryManager) -> None:
        """Since Geometry is intended to create design plots but not solve simulations,
        here we're running a simple slot extrusion test. Example taken from
        https://github.com/ansys/pyansys-geometry/blob/76365bca7e71ff4b8aa26bfd39dfd52bbbdb887a/tests/integration/test_design.py#L962
        """
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

    @transaction(self=StepSpec(upload=["active_design_name"]))
    @instance("geometry_manager")
    def get_active_design(self, geometry_manager: GeometryManager) -> None:
        self.active_design_name = geometry_manager.instance.read_existing_design().name

    @transaction(self=StepSpec(upload=["active_design_name"]))
    @instance("geometry_manager")
    def clear_active_design(self, geometry_manager: GeometryManager) -> None:
        self.active_design_name = ""

    @transaction(self=StepSpec())
    @instance("geometry_manager")
    def log_message(self, geometry_manager: GeometryManager) -> None:
        GEOMETRY_LOGGER.error("Simulates error message from Geometry.")

    @transaction(self=StepSpec(upload=["geometry_available"]))
    @instance("geometry_manager")
    def close_geometry(self, geometry_manager: GeometryManager) -> None:
        geometry_manager.shutdown()
        self.geometry_available = False
