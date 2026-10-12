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

from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.aedt import Maxwell3DManager
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION


class Maxwell3DSetupVerificationStep(StepModel):
    aedt_version: str = LATEST_VERSION
    origin: list[float] = [0, 0, 0]
    dimension: list[float] = [10, 10, 10]
    box_name: str = "box_A"
    m3d_available: bool = False

    @transaction(self=StepSpec(download=["aedt_version"]))
    @create_instance("maxwell_3d_instance", Maxwell3DManager)
    @long_running
    def initialize_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        maxwell_3d_instance.initialize(version=self.aedt_version)

    @transaction(self=StepSpec(download=["origin", "dimension", "box_name"]))
    @instance("maxwell_3d_instance")
    def add_box(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        maxwell_3d_instance.instance.modeler.create_box(self.origin, self.dimension, self.box_name)  # type: ignore

    @transaction(self=StepSpec(download=["box_name"], upload=["dimension"]))
    @instance("maxwell_3d_instance")
    @long_running
    def upload_object_dimension_from_aedt(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        project = maxwell_3d_instance.instance.odesktop.GetActiveProject()  # type: ignore
        design = project.GetActiveDesign()  # type: ignore
        editor = design.SetActiveEditor("3D Modeler")  # type: ignore
        self.dimension = [float(dim) for dim in editor.GetModelBoundingBox()[3:]]  # type: ignore

    @transaction(self=StepSpec(upload=["aedt_version"]))
    @instance("maxwell_3d_instance")
    @long_running
    def upload_aedt_version_from_aedt(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        self.aedt_version = maxwell_3d_instance.instance.aedt_version_id  # type: ignore

    @transaction(self=StepSpec())
    @instance("maxwell_3d_instance")
    def exit_aedt(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        maxwell_3d_instance.shutdown()

    @transaction(self=StepSpec(upload=["m3d_available"]))
    @instance("maxwell_3d_instance")
    def refresh_availability(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        self.m3d_available = bool(
            maxwell_3d_instance._instance_manager_impl._find_instance(),  # pyright: ignore[reportPrivateUsage]
        )
