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

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.aedt import Maxwell3DManager
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION


class DesignNameVerificationStep(StepModel):
    aedt_version: str = LATEST_VERSION
    design_name: str | None = None
    design_names: list[str] = []
    object_names: list[str] | None = None
    project_input: EntityHandle = NO_ENTITY
    project_list: list[str] | None = None
    project_closed: bool = False

    @transaction(self=StepSpec(download=["project_input", "aedt_version", "design_name"]))
    @create_instance("maxwell_3d_instance", Maxwell3DManager)
    @long_running
    def initialize_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        maxwell_3d_instance.initialize(
            project_file=self.project_input,
            version=self.aedt_version,
            design_name=self.design_name,
        )

    @transaction(self=StepSpec(upload=["aedt_version"]))
    @instance("maxwell_3d_instance")
    @long_running
    def upload_aedt_version_from_aedt(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        self.aedt_version = maxwell_3d_instance.instance.aedt_version_id  # type: ignore

    @transaction(self=StepSpec(download=["design_name"]))
    @instance("maxwell_3d_instance")
    def set_active_design_for_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        maxwell_3d_instance.instance.set_active_design(self.design_name)  # type: ignore

    @transaction(self=StepSpec(upload=["design_name"]))
    @instance("maxwell_3d_instance")
    def get_active_design_for_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        self.design_name = maxwell_3d_instance.instance.odesign.GetName()  # type: ignore

    @transaction(self=StepSpec(upload=["project_list"]))
    @instance("maxwell_3d_instance")
    @long_running
    def get_project_list_from_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        self.project_list = maxwell_3d_instance.instance.desktop_class.project_list  # type: ignore

    @transaction(self=StepSpec(upload=["design_names"]))
    @instance("maxwell_3d_instance")
    @long_running
    def upload_design_names_from_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        self.design_names = maxwell_3d_instance.instance.design_list  # type: ignore

    @transaction(self=StepSpec())
    @instance("maxwell_3d_instance")
    def add_object_to_maxwell_3d_instance_without_long_running(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        maxwell_3d_instance.instance.modeler.create_box([0, 0, 0], [10, 10, 10])  # type: ignore

    @transaction(self=StepSpec())
    @instance("maxwell_3d_instance")
    @long_running
    def add_object_to_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        maxwell_3d_instance.instance.modeler.create_box([0, 0, 0], [10, 10, 10])  # type: ignore

    @transaction(self=StepSpec(upload=["object_names"]))
    @instance("maxwell_3d_instance")
    @long_running
    def upload_object_names_from_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        self.object_names = maxwell_3d_instance.instance.modeler.solid_bodies  # type: ignore

    @transaction(self=StepSpec(upload=["project_closed", "project_list"]))
    @instance("maxwell_3d_instance")
    def close_project_for_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        self.project_closed = maxwell_3d_instance.instance.close_project()  # type: ignore
        self.project_list = maxwell_3d_instance.instance.desktop_class.project_list  # type: ignore

    @transaction(self=StepSpec())
    @instance("maxwell_3d_instance")
    def exit_maxwell_3d_instance(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        maxwell_3d_instance.shutdown()

    @transaction(self=StepSpec())
    @instance("maxwell_3d_instance")
    def kill_aedt_from_instance_system(self, maxwell_3d_instance: Maxwell3DManager) -> None:
        instance = maxwell_3d_instance._instance_manager_impl._find_instance()  # type: ignore
        instance.delete(missing_ok=True)  # type: ignore
