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

from pathlib import Path

from ansys.saf.glow.solution import (
    NO_ENTITY,
    EntityHandle,
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.aedt import Maxwell2DManager
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION

MAXWELL_2D_DESIGN = "Design_MAX2D"
INPUT_AEDT_FILE = Path("./tests/mocks/solution_end_to_end/method_assets/Transformer_leakage_inductance.aedt")


class Maxwell2DSetupVerificationStep(StepModel):
    aedt_version: str = LATEST_VERSION
    origin: list[float] = [0, 0, 0]
    dimension: list[float] = [10, 10]
    object_dimension_list: list[list[float]] = []
    aedt_project_file: EntityHandle = NO_ENTITY
    aedt_project_file_input: EntityHandle = NO_ENTITY
    aedt_variables_file: EntityHandle = NO_ENTITY
    project_list: list[str] = []
    design_name: str = ""
    design_name_list: list[str] = []
    m2d_available: bool = False
    e2e_file_entity_api: EntityHandle = NO_ENTITY
    e2e_file_entity_ui: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(download=["aedt_version"]))
    @create_instance("maxwell_2d_instance", Maxwell2DManager)
    @long_running
    def initialize_maxwell_2d_instance(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        maxwell_2d_instance.initialize(version=self.aedt_version)

    @transaction(self=StepSpec(download=["aedt_version", "aedt_project_file_input"]))
    @create_instance("maxwell_2d_instance", Maxwell2DManager)
    @long_running
    def initialize_maxwell_2d_instance_with_project(self, maxwell_2d_instance: Maxwell2DManager) -> None:

        assert self.aedt_project_file_input != NO_ENTITY

        maxwell_2d_instance.initialize(
            project_file=self.aedt_project_file_input,
            version=self.aedt_version,
        )

    @transaction(self=StepSpec(upload=["aedt_version"]))
    @instance("maxwell_2d_instance")
    @long_running
    def upload_aedt_version_from_aedt(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        self.aedt_version = maxwell_2d_instance.instance.aedt_version_id

    @transaction(self=StepSpec())
    @instance("maxwell_2d_instance")
    def run_analysis(self, maxwell_2d_instance: Maxwell2DManager) -> bool:
        return maxwell_2d_instance.instance.analyze()  # type: ignore

    @transaction(self=StepSpec())
    @instance("maxwell_2d_instance")
    def health_check(self, maxwell_2d_instance: Maxwell2DManager) -> bool:
        return maxwell_2d_instance.is_instance_healthy()

    @transaction(self=StepSpec(download=["aedt_version"], upload=["design_name"]))
    @create_instance("maxwell_2d_instance", Maxwell2DManager)
    @long_running
    def initialize_maxwell_2d_instance_then_access_instance(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        maxwell_2d_instance.initialize(version=self.aedt_version)
        maxwell_2d_instance.instance.set_active_design(MAXWELL_2D_DESIGN)  # type: ignore
        project = maxwell_2d_instance.instance.odesktop.GetActiveProject()  # type: ignore
        design = project.GetActiveDesign()  # type: ignore
        self.design_name = design.GetName()  # type: ignore

    @transaction(self=StepSpec(download=["origin", "dimension"]))
    @instance("maxwell_2d_instance")
    def add_rectangle(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        maxwell_2d_instance.instance.modeler.create_rectangle(self.origin, self.dimension)  # type: ignore

    @transaction(self=StepSpec(upload=["aedt_project_file"]))
    @instance("maxwell_2d_instance")
    def save_project(self, maxwell_2d_instance: Maxwell2DManager) -> bool:
        aedt_project_file = maxwell_2d_instance.storage_scope.get_storage_root() / "project2.aedt"
        outcome = maxwell_2d_instance.instance.save_project(file_name=str(aedt_project_file), overwrite=True)  # type: ignore
        self.aedt_project_file = maxwell_2d_instance.storage_scope.store(aedt_project_file)
        return outcome

    @transaction(self=StepSpec(upload=["aedt_variables_file"]))
    @instance("maxwell_2d_instance")
    def export_variables(self, maxwell_2d_instance: Maxwell2DManager) -> bool:
        # pyaedt's export_variables_to_csv gets information from remote AEDT instance but writes CSV locally,
        # so the path must be the local one. It requires for the path to exist, though.
        aedt_variable_file_path = self.storage_scope.get_storage_root() / "maxwell_project.csv"
        outcome = maxwell_2d_instance.instance.export_variables_to_csv(str(aedt_variable_file_path))  # type: ignore
        self.aedt_variables_file = self.storage_scope.store(aedt_variable_file_path)
        return outcome

    @transaction(self=StepSpec(download=["aedt_project_file"], upload=["project_list"]))
    @instance("maxwell_2d_instance")
    def load_project(self, maxwell_2d_instance: Maxwell2DManager) -> bool:
        project_path = maxwell_2d_instance.storage_scope.get_cached(self.aedt_project_file)
        outcome = maxwell_2d_instance.instance.load_project(file_name=str(project_path), close_active=True)  # type: ignore
        desktop = maxwell_2d_instance.instance.desktop_class
        self.project_list = desktop.project_list  # type: ignore
        return outcome  # type: ignore

    @transaction(self=StepSpec(upload=["object_dimension_list"]))
    @instance("maxwell_2d_instance")
    @long_running
    def upload_object_dimension_from_aedt(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        self.object_dimension_list = []

        def get_object_dimensions_from_odesktop(maxwell_object):  # type: ignore
            dimensions = [
                float(maxwell_object.GetPropSIValue("xSize")) * 1000,  # type: ignore
                float(maxwell_object.GetPropSIValue("ySize")) * 1000,  # type: ignore
                0,
            ]
            return dimensions

        project = maxwell_2d_instance.instance.odesktop.GetActiveProject()  # type: ignore
        design = project.GetActiveDesign()  # type: ignore
        modeler = design.GetChildObject("3D Modeler")  # type: ignore
        object_names = modeler.GetChildNames()  # type: ignore

        for object_name in object_names:  # type: ignore
            maxwell_object = modeler.GetChildObject(object_name)  # type: ignore
            rectangle_object_name = [name for name in maxwell_object.GetChildNames() if "Rectangle" in name]  # type: ignore
            rectangle_object = maxwell_object.GetChildObject(rectangle_object_name[0])  # type: ignore
            self.object_dimension_list.append(get_object_dimensions_from_odesktop(rectangle_object))  # type: ignore

    @transaction(self=StepSpec())
    @instance("maxwell_2d_instance")
    def exit_aedt(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        maxwell_2d_instance.shutdown()

    @transaction(self=StepSpec(upload=["m2d_available"]))
    @instance("maxwell_2d_instance")
    def refresh_availability(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        self.m2d_available = bool(
            maxwell_2d_instance._instance_manager_impl._find_instance(),  # pyright: ignore[reportPrivateUsage]
        )

    @transaction(self=StepSpec(upload=["e2e_file_entity_api"]))
    def store_data_content_into_file_entity(self, file_content: bytes, file_name: str):
        file_entity_path = self.storage_scope.get_storage_root() / file_name
        file_entity_path.write_bytes(file_content)
        self.e2e_file_entity_api = self.storage_scope.store(file_entity_path)

    @transaction(self=StepSpec(download=["aedt_version", "e2e_file_entity_ui"], upload=["design_name_list"]))
    @create_instance("m2d_for_bdm_e2e", Maxwell2DManager)
    @long_running
    def use_project_cached_at_ui(self, m2d_for_bdm_e2e: Maxwell2DManager) -> None:
        m2d_for_bdm_e2e.initialize(
            project_file=self.e2e_file_entity_ui,
            version=self.aedt_version,
        )

        self.design_name_list: list[str] = m2d_for_bdm_e2e.instance.design_list

    @transaction(self=StepSpec(upload=["aedt_version"]))
    @instance("m2d_for_bdm_e2e")
    @long_running
    def upload_bdm_e2e_aedt_version_from_aedt(self, m2d_for_bdm_e2e: Maxwell2DManager) -> None:
        self.aedt_version = m2d_for_bdm_e2e.instance.aedt_version_id
