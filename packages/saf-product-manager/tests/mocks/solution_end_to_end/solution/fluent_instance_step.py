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

from ansys.fluent.core.session_solver import Solver  # pyright: ignore[reportMissingTypeStubs]

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.fluent import (
    Fluent2DDPSolverManager,
    Fluent3DDPMeshingManager,
    Fluent3DDPSolverManager,
)


class FluentInstanceStep(StepModel):
    # Solver example copied from https://examples.fluent.docs.pyansys.com/version/dev/examples/00-released_examples/01-brake.html#
    # Meshing example copied from https://fluent.docs.pyansys.com/version/stable/examples/00-fluent/exhaust_system.html#

    version: str = "252"
    max_temperature_file: EntityHandle = NO_ENTITY
    simulation_output: EntityHandle = NO_ENTITY
    fluent_available: bool = False
    fluent_3ddp_solver_product_kind: str = ""
    fluent_2ddp_solver_product_kind: str = ""
    fluent_3ddp_meshing_product_kind: str = ""

    @transaction(self=StepSpec(download=["version"]))
    @create_instance("fluent_3ddp_solver_instance", Fluent3DDPSolverManager)
    @long_running
    def launch_fluent_3ddp_solver(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
        fluent_3ddp_solver_instance.initialize(version=self.version)
        # just to trigger get_client_object(), which does the connection with fluent.
        # The initial creation only covers connection with the wrapper.
        _ = fluent_3ddp_solver_instance.instance

    @transaction(self=StepSpec(upload=["fluent_available"]))
    @instance("fluent_3ddp_solver_instance")
    def refresh_fluent_3ddp_solver_availability(
        self,
        fluent_3ddp_solver_instance: Fluent3DDPSolverManager,
    ) -> None:
        self.fluent_available = bool(
            fluent_3ddp_solver_instance._instance_manager_impl._find_instance(),  # pyright: ignore[reportPrivateUsage]
        )

    @transaction(self=StepSpec(upload=["fluent_3ddp_solver_product_kind"]))
    @instance("fluent_3ddp_solver_instance")
    def upload_fluent_3ddp_solver_product_kind(
        self,
        fluent_3ddp_solver_instance: Fluent3DDPSolverManager,
    ) -> None:
        self.fluent_3ddp_solver_product_kind = fluent_3ddp_solver_instance.instance.product_kind  # type: ignore

    @transaction(self=StepSpec())
    @instance("fluent_3ddp_solver_instance")
    def import_mesh(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
        session = fluent_3ddp_solver_instance.instance

        # Import mesh
        example_file = self.transaction.get_asset_entity_handle("brake.msh.h5")
        example_file_path = fluent_3ddp_solver_instance.storage_scope.get_cached(example_file)
        session.tui.file.read_case(str(example_file_path))  # type: ignore

        # Define models and material
        session.tui.define.models.energy("yes", "no", "no", "no", "yes")  # type: ignore
        session.tui.define.models.unsteady_2nd_order_bounded("yes")  # type: ignore
        session.tui.define.materials.copy("solid", "steel")  # type: ignore

        # Solve only energy equation (conduction)
        session.tui.solve.set.equations("flow", "no", "kw", "no")  # type: ignore

        # Define disc rotation
        session.tui.define.boundary_conditions.set.solid(  # type: ignore
            "disc1",
            "disc2",
            "()",
            "solid-motion?",
            "yes",
            "solid-omega",
            "no",
            -15.79,
            "solid-x-origin",
            "no",
            -0.035,
            "solid-y-origin",
            "no",
            -0.821,
            "solid-z-origin",
            "no",
            0.045,
            "solid-ai",
            "no",
            0,
            "solid-aj",
            "no",
            1,
            "solid-ak",
            "no",
            0,
            "q",
        )

        # Apply frictional heating on pad-disc surfaces
        session.tui.define.boundary_conditions.set.wall(  # type: ignore
            "wall_pad-disc1",
            "wall-pad-disc2",
            "()",
            "wall-thickness",
            "no",
            0.002,
            "q-dot",
            "no",
            2e9,
            "q",
        )

        # session.file.

        # Apply convection cooling on outer surfaces due to air flow
        session.tui.define.boundary_conditions.set.wall(  # type: ignore
            "wall-disc*",
            "wall-geom*",
            "()",
            "thermal-bc",
            "yes",
            "convection",
            "convective-heat-transfer-coefficient",
            "no",
            100,
            "q",
        )

        # Initialize flow
        session.tui.solve.initialize.initialize_flow()  # type: ignore

    @transaction(self=StepSpec(upload=["simulation_output", "max_temperature_file"]))
    @instance("fluent_3ddp_solver_instance")
    @long_running
    def run_simulation(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> dict[str, Path]:
        session = fluent_3ddp_solver_instance.instance

        # Post processing setup
        session.tui.solve.report_definitions.add(  # type: ignore
            "max-pad-temperature",  # type: ignore
            "volume-max",
            "field",
            "temperature",
            "zone-names",  # type: ignore
            "geom-1-innerpad",
            "geom-1-outerpad",
        )
        session.tui.solve.report_definitions.add(  # type: ignore
            "max-disc-temperature",  # type: ignore
            "volume-max",
            "field",
            "temperature",
            "zone-names",  # type: ignore
            "disc1",
            "disc2",
        )

        session.tui.solve.report_plots.add(  # type: ignore
            "max-temperature",  # type: ignore
            "report-defs",
            "max-pad-temperature",
            "max-disc-temperature",
            "()",  # type: ignore
        )

        max_temperature_file_path = fluent_3ddp_solver_instance.storage_scope.get_storage_root() / "max-temperature.out"
        session.tui.solve.report_files.add(  # type: ignore
            "max-temperature",  # type: ignore
            "report-defs",
            "max-pad-temperature",
            "max-disc-temperature",
            "()",  # type: ignore
            "file-name",
            str(max_temperature_file_path),
        )

        session.results.graphics.contour["contour-1"] = {  # type: ignore
            "boundary_values": True,
            "color_map": {
                "color": "field-velocity",
                "font_automatic": True,
                "font_name": "Helvetica",
                "font_size": 0.032,
                "format": "%0.2e",
                "length": 0.54,
                "log_scale": False,
                "position": 1,
                "show_all": True,
                "size": 100,
                "user_skip": 9,
                "visible": True,
                "width": 6.0,
            },
            "coloring": {"smooth": False},
            "contour_lines": False,
            "display_state_name": "None",
            "draw_mesh": False,
            "field": "temperature",
            "filled": True,
            "mesh_object": "",
            "node_values": True,
            "range_option": {"auto_range_on": {"global_range": True}},
        }

        session.tui.display.objects.create(  # type: ignore
            "contour",  # type: ignore
            "temperature",
            "field",
            "temperature",
            "surface-list",  # type: ignore
            "wall*",
            "()",
            "color-map",
            "format",
            "%0.1f",
            "q",
            "range-option",
            "auto-range-off",
            "minimum",
            300,
            "maximum",
            400,
            "q",
            "q",
        )

        session.tui.display.views.restore_view("top")  # type: ignore
        session.tui.display.views.camera.zoom_camera(2)  # type: ignore
        session.tui.display.views.save_view("animation-view")  # type: ignore

        session.tui.solve.animate.objects.create(  # type: ignore
            "animate-temperature",  # type: ignore
            "animate-on",
            "temperature",
            "frequency-of",
            "flow-time",  # type: ignore
            "flow-time-frequency",
            0.05,
            "view",
            "animation-view",
            "q",
        )

        # Run simulation
        simulation_output_path = fluent_3ddp_solver_instance.storage_scope.get_storage_root() / "brake-final.cas.h5"
        session.tui.solve.set.transient_controls.time_step_size(0.01)  # type: ignore
        session.tui.solve.dual_time_iterate(200, 5)  # type: ignore
        session.tui.file.write_case_data(str(simulation_output_path))  # type: ignore

        self.simulation_output = fluent_3ddp_solver_instance.storage_scope.store(simulation_output_path)
        self.max_temperature_file = fluent_3ddp_solver_instance.storage_scope.store(max_temperature_file_path)

        output = {
            "simulation_output": self.storage_scope.get_cached(self.simulation_output),
            "max_temperature_file": self.storage_scope.get_cached(self.max_temperature_file),
        }

        return output

    @transaction()
    @instance("fluent_3ddp_solver_instance")
    def close_fluent_3ddp_solver(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
        fluent_3ddp_solver_instance.shutdown()

    @transaction(self=StepSpec(download=["version"]))
    @create_instance("fluent_2ddp_solver_instance", Fluent2DDPSolverManager)
    @long_running
    def launch_fluent_2ddp_solver(self, fluent_2ddp_solver_instance: Fluent2DDPSolverManager) -> None:
        fluent_2ddp_solver_instance.initialize(version=self.version)
        # just to trigger get_client_object(), which does the connection with fluent.
        # The initial creation only covers connection with the wrapper.
        _ = fluent_2ddp_solver_instance.instance

    @transaction(self=StepSpec(upload=["fluent_available"]))
    @instance("fluent_2ddp_solver_instance")
    def refresh_fluent_2ddp_solver_availability(
        self,
        fluent_2ddp_solver_instance: Fluent2DDPSolverManager,
    ) -> None:
        self.fluent_available = bool(
            fluent_2ddp_solver_instance._instance_manager_impl._find_instance(),  # pyright: ignore[reportPrivateUsage]
        )

    @transaction(self=StepSpec(upload=["fluent_2ddp_solver_product_kind"]))
    @instance("fluent_2ddp_solver_instance")
    def upload_fluent_2ddp_solver_product_kind(
        self,
        fluent_2ddp_solver_instance: Fluent2DDPSolverManager,
    ) -> None:
        self.fluent_2ddp_solver_product_kind = fluent_2ddp_solver_instance.instance.product_kind  # type: ignore

    @transaction()
    @instance("fluent_2ddp_solver_instance")
    def use_fluent_2ddp_solver(self, fluent_2ddp_solver_instance: Fluent2DDPSolverManager) -> None:
        assert isinstance(fluent_2ddp_solver_instance.instance, Solver)

    @transaction()
    @instance("fluent_2ddp_solver_instance")
    def close_fluent_2ddp_solver(self, fluent_2ddp_solver_instance: Fluent2DDPSolverManager) -> None:
        fluent_2ddp_solver_instance.shutdown()

    @transaction(self=StepSpec(download=["version"]))
    @create_instance("fluent_3ddp_meshing_instance", Fluent3DDPMeshingManager)
    @long_running
    def launch_fluent_3ddp_meshing(self, fluent_3ddp_meshing_instance: Fluent3DDPMeshingManager) -> None:
        fluent_3ddp_meshing_instance.initialize(version=self.version)
        # just to trigger get_client_object(), which does the connection with fluent.
        # The initial creation only covers connection with the wrapper.
        _ = fluent_3ddp_meshing_instance.instance

    @transaction(self=StepSpec(upload=["fluent_available"]))
    @instance("fluent_3ddp_meshing_instance")
    def refresh_fluent_3ddp_meshing_availability(
        self,
        fluent_3ddp_meshing_instance: Fluent3DDPMeshingManager,
    ) -> None:
        self.fluent_available = bool(
            fluent_3ddp_meshing_instance._instance_manager_impl._find_instance(),  # pyright: ignore[reportPrivateUsage]
        )

    @transaction(self=StepSpec(upload=["fluent_3ddp_meshing_product_kind"]))
    @instance("fluent_3ddp_meshing_instance")
    def upload_fluent_3ddp_meshing_product_kind(
        self,
        fluent_3ddp_meshing_instance: Fluent3DDPMeshingManager,
    ) -> None:
        self.fluent_3ddp_meshing_product_kind = fluent_3ddp_meshing_instance.instance.product_kind  # type: ignore

    @transaction(self=StepSpec())
    @instance("fluent_3ddp_meshing_instance")
    def prepare_mesh(self, fluent_3ddp_meshing_instance: Fluent3DDPMeshingManager) -> None:
        meshing = fluent_3ddp_meshing_instance.instance

        # Initialize workflow
        meshing.workflow.InitializeWorkflow(WorkflowType="Fault-tolerant Meshing")  # type: ignore

        # Import CAD and manage parts
        example_file_meshing = self.transaction.get_asset_entity_handle("exhaust_system.fmd")
        example_file_meshing_path = fluent_3ddp_meshing_instance.storage_scope.get_cached(example_file_meshing)
        meshing.PartManagement.InputFileChanged(  # type: ignore
            FilePath=str(example_file_meshing_path),  # type: ignore
            IgnoreSolidNames=False,  # type: ignore
            PartPerBody=False,  # type: ignore
        )
        meshing.PMFileManagement.FileManager.LoadFiles()  # type: ignore
        meshing.PartManagement.Node["Meshing Model"].Copy(  # type: ignore
            Paths=[
                "/dirty_manifold-for-wrapper," + "1/dirty_manifold-for-wrapper,1/main,1",
                "/dirty_manifold-for-wrapper," + "1/dirty_manifold-for-wrapper,1/flow-pipe,1",
                "/dirty_manifold-for-wrapper," + "1/dirty_manifold-for-wrapper,1/outpipe3,1",
                "/dirty_manifold-for-wrapper," + "1/dirty_manifold-for-wrapper,1/object2,1",
                "/dirty_manifold-for-wrapper," + "1/dirty_manifold-for-wrapper,1/object1,1",
            ],
        )
        meshing.PartManagement.ObjectSetting["DefaultObjectSetting"].OneZonePer.set_state("part")  # type: ignore
        cad_import = meshing.workflow.TaskObject["Import CAD and Part Management"]  # type: ignore
        cad_import.Arguments.set_state(  # type: ignore
            {
                "Context": 0,
                "CreateObjectPer": "Custom",
                "FMDFileName": example_file_meshing_path.name,
                "FileLoaded": "yes",
                "ObjectSetting": "DefaultObjectSetting",
                "Options": {
                    "Line": False,
                    "Solid": False,
                    "Surface": False,
                },
            },
        )
        cad_import.Execute()  # type: ignore

        # Describe geometry and flow
        describe_geom = meshing.workflow.TaskObject["Describe Geometry and Flow"]  # type: ignore
        describe_geom.Arguments.set_state(  # type: ignore
            {
                "AddEnclosure": "No",
                "CloseCaps": "Yes",
                "FlowType": "Internal flow through the object",
            },
        )
        describe_geom.UpdateChildTasks(SetupTypeChanged=False)  # type: ignore
        describe_geom.Arguments.set_state(  # type: ignore
            {
                "AddEnclosure": "No",
                "CloseCaps": "Yes",
                "DescribeGeometryAndFlowOptions": {
                    "AdvancedOptions": True,
                    "ExtractEdgeFeatures": "Yes",
                },
                "FlowType": "Internal flow through the object",
            },
        )
        describe_geom.UpdateChildTasks(SetupTypeChanged=False)  # type: ignore
        describe_geom.Execute()  # type: ignore

        # Enclose openings
        capping = meshing.workflow.TaskObject["Enclose Fluid Regions (Capping)"]  # type: ignore
        capping.Arguments.set_state(  # type: ignore
            {
                "CreatePatchPreferences": {
                    "ShowCreatePatchPreferences": False,
                },
                "PatchName": "inlet-1",
                "SelectionType": "zone",
                "ZoneSelectionList": ["inlet.1"],
            },
        )
        capping.Arguments.set_state(  # type: ignore
            {
                "CreatePatchPreferences": {
                    "ShowCreatePatchPreferences": False,
                },
                "PatchName": "inlet-1",
                "SelectionType": "zone",
                "ZoneLocation": [
                    "1",
                    "351.68205",
                    "-361.34322",
                    "-301.88668",
                    "396.96205",
                    "-332.84759",
                    "-266.69751",
                    "inlet.1",
                ],
                "ZoneSelectionList": ["inlet.1"],
            },
        )
        capping.AddChildToTask()  # type: ignore

        capping.InsertCompoundChildTask()  # type: ignore
        capping.Arguments.set_state({})  # type: ignore
        meshing.workflow.TaskObject["inlet-1"].Execute()  # type: ignore
        capping.Arguments.set_state(  # type: ignore
            {
                "PatchName": "inlet-2",
                "SelectionType": "zone",
                "ZoneSelectionList": ["inlet.2"],
            },
        )
        capping.Arguments.set_state(  # type: ignore
            {
                "PatchName": "inlet-2",
                "SelectionType": "zone",
                "ZoneLocation": [
                    "1",
                    "441.68205",
                    "-361.34322",
                    "-301.88668",
                    "486.96205",
                    "-332.84759",
                    "-266.69751",
                    "inlet.2",
                ],
                "ZoneSelectionList": ["inlet.2"],
            },
        )
        capping.AddChildToTask()  # type: ignore

        capping.InsertCompoundChildTask()  # type: ignore
        capping.Arguments.set_state({})  # type: ignore
        meshing.workflow.TaskObject["inlet-2"].Execute()  # type: ignore
        capping.Arguments.set_state(  # type: ignore
            {
                "PatchName": "inlet-3",
                "SelectionType": "zone",
                "ZoneSelectionList": ["inlet"],
            },
        )
        capping.Arguments.set_state(  # type: ignore
            {
                "PatchName": "inlet-3",
                "SelectionType": "zone",
                "ZoneLocation": [
                    "1",
                    "261.68205",
                    "-361.34322",
                    "-301.88668",
                    "306.96205",
                    "-332.84759",
                    "-266.69751",
                    "inlet",
                ],
                "ZoneSelectionList": ["inlet"],
            },
        )
        capping.AddChildToTask()  # type: ignore

        capping.InsertCompoundChildTask()  # type: ignore
        capping.Arguments.set_state({})  # type: ignore
        meshing.workflow.TaskObject["inlet-3"].Execute()  # type: ignore
        capping.Arguments.set_state(  # type: ignore
            {
                "PatchName": "outlet-1",
                "SelectionType": "zone",
                "ZoneSelectionList": ["outlet"],
                "ZoneType": "pressure-outlet",
            },
        )
        capping.Arguments.set_state(  # type: ignore
            {
                "PatchName": "outlet-1",
                "SelectionType": "zone",
                "ZoneLocation": [
                    "1",
                    "352.22702",
                    "-197.8957",
                    "84.102381",
                    "394.41707",
                    "-155.70565",
                    "84.102381",
                    "outlet",
                ],
                "ZoneSelectionList": ["outlet"],
                "ZoneType": "pressure-outlet",
            },
        )
        capping.AddChildToTask()  # type: ignore

        capping.InsertCompoundChildTask()  # type: ignore
        capping.Arguments.set_state({})  # type: ignore
        meshing.workflow.TaskObject["outlet-1"].Execute()  # type: ignore

        # Extract edge features
        edge_features = meshing.workflow.TaskObject["Extract Edge Features"]  # type: ignore
        edge_features.Arguments.set_state(  # type: ignore
            {
                "ExtractMethodType": "Intersection Loops",
                "ObjectSelectionList": ["flow_pipe", "main"],
            },
        )
        edge_features.AddChildToTask()  # type: ignore

        edge_features.InsertCompoundChildTask()  # type: ignore
        edge_group = meshing.workflow.TaskObject["edge-group-1"]  # type: ignore
        edge_group.Arguments.set_state(  # type: ignore
            {
                "ExtractEdgesName": "edge-group-1",
                "ExtractMethodType": "Intersection Loops",
                "ObjectSelectionList": ["flow_pipe", "main"],
            },
        )
        edge_features.Arguments.set_state({})  # type: ignore

        edge_group.Execute()  # type: ignore

        # Identify regions
        identify_regions = meshing.workflow.TaskObject["Identify Regions"]  # type: ignore
        identify_regions.Arguments.set_state(  # type: ignore
            {
                "SelectionType": "zone",
                "X": 377.322045740589,
                "Y": -176.800676988458,
                "Z": -37.0764628583475,
                "ZoneSelectionList": ["main.1"],
            },
        )
        identify_regions.Arguments.set_state(  # type: ignore
            {
                "SelectionType": "zone",
                "X": 377.322045740589,
                "Y": -176.800676988458,
                "Z": -37.0764628583475,
                "ZoneLocation": [
                    "1",
                    "213.32205",
                    "-225.28068",
                    "-158.25531",
                    "541.32205",
                    "-128.32068",
                    "84.102381",
                    "main.1",
                ],
                "ZoneSelectionList": ["main.1"],
            },
        )
        identify_regions.AddChildToTask()  # type: ignore

        identify_regions.InsertCompoundChildTask()  # type: ignore
        fluid_region_1 = meshing.workflow.TaskObject["fluid-region-1"]  # type: ignore
        fluid_region_1.Arguments.set_state(  # type: ignore
            {
                "MaterialPointsName": "fluid-region-1",
                "SelectionType": "zone",
                "X": 377.322045740589,
                "Y": -176.800676988458,
                "Z": -37.0764628583475,
                "ZoneLocation": [
                    "1",
                    "213.32205",
                    "-225.28068",
                    "-158.25531",
                    "541.32205",
                    "-128.32068",
                    "84.102381",
                    "main.1",
                ],
                "ZoneSelectionList": ["main.1"],
            },
        )
        identify_regions.Arguments.set_state({})  # type: ignore

        fluid_region_1.Execute()  # type: ignore
        identify_regions.Arguments.set_state(  # type: ignore
            {
                "MaterialPointsName": "void-region-1",
                "NewRegionType": "void",
                "ObjectSelectionList": ["inlet-1", "inlet-2", "inlet-3", "main"],
                "X": 374.722045740589,
                "Y": -278.9775145640143,
                "Z": -161.1700719416913,
            },
        )
        identify_regions.AddChildToTask()  # type: ignore

        identify_regions.InsertCompoundChildTask()  # type: ignore

        identify_regions.Arguments.set_state({})  # type: ignore

        meshing.workflow.TaskObject["void-region-1"].Execute()  # type: ignore

        # Define thresholds for leakages
        leakage_threshold = meshing.workflow.TaskObject["Define Leakage Threshold"]  # type: ignore
        leakage_threshold.Arguments.set_state(  # type: ignore
            {
                "AddChild": "yes",
                "FlipDirection": True,
                "PlaneDirection": "X",
                "RegionSelectionSingle": "void-region-1",
            },
        )
        leakage_threshold.AddChildToTask()  # type: ignore

        leakage_threshold.InsertCompoundChildTask()  # type: ignore
        leakage_1 = meshing.workflow.TaskObject["leakage-1"]  # type: ignore
        leakage_1.Arguments.set_state(  # type: ignore
            {
                "AddChild": "yes",
                "FlipDirection": True,
                "LeakageName": "leakage-1",
                "PlaneDirection": "X",
                "RegionSelectionSingle": "void-region-1",
            },
        )
        leakage_threshold.Arguments.set_state(  # type: ignore
            {
                "AddChild": "yes",
            },
        )
        leakage_1.Execute()  # type: ignore

        # Review region settings
        update_region = meshing.workflow.TaskObject["Update Region Settings"]  # type: ignore
        update_region.Arguments.set_state(  # type: ignore
            {
                "AllRegionFilterCategories": ["2"] * 5 + ["1"] * 2,
                "AllRegionLeakageSizeList": ["none"] * 6 + ["6.4"],
                "AllRegionLinkedConstructionSurfaceList": ["n/a"] * 6 + ["no"],
                "AllRegionMeshMethodList": ["none"] * 6 + ["wrap"],
                "AllRegionNameList": [
                    "main",
                    "flow_pipe",
                    "outpipe3",
                    "object2",
                    "object1",
                    "void-region-1",
                    "fluid-region-1",
                ],
                "AllRegionOversetComponenList": ["no"] * 7,
                "AllRegionSourceList": ["object"] * 5 + ["mpt"] * 2,
                "AllRegionTypeList": ["void"] * 6 + ["fluid"],
                "AllRegionVolumeFillList": ["none"] * 6 + ["tet"],
                "FilterCategory": "Identified Regions",
                "OldRegionLeakageSizeList": [""],
                "OldRegionMeshMethodList": ["wrap"],
                "OldRegionNameList": ["fluid-region-1"],
                "OldRegionOversetComponenList": ["no"],
                "OldRegionTypeList": ["fluid"],
                "OldRegionVolumeFillList": ["hexcore"],
                "RegionLeakageSizeList": [""],
                "RegionMeshMethodList": ["wrap"],
                "RegionNameList": ["fluid-region-1"],
                "RegionOversetComponenList": ["no"],
                "RegionTypeList": ["fluid"],
                "RegionVolumeFillList": ["tet"],
            },
        )
        update_region.Execute()  # type: ignore

    @transaction()
    @instance("fluent_3ddp_meshing_instance")
    @long_running
    def generate_mesh(self, fluent_3ddp_meshing_instance: Fluent3DDPMeshingManager) -> None:
        meshing = fluent_3ddp_meshing_instance.instance

        # Set mesh control options
        meshing.workflow.TaskObject["Choose Mesh Control Options"].Execute()  # type: ignore

        # Generate surface mesh
        meshing.workflow.TaskObject["Generate the Surface Mesh"].Execute()  # type: ignore

        # Confirm and update boundaries
        meshing.workflow.TaskObject["Update Boundaries"].Execute()  # type: ignore

        # Add boundary layers
        meshing.workflow.TaskObject["Add Boundary Layers"].AddChildToTask()  # type: ignore

        meshing.workflow.TaskObject["Add Boundary Layers"].InsertCompoundChildTask()  # type: ignore

        meshing.workflow.TaskObject["aspect-ratio_1"].Arguments.set_state(  # type: ignore
            {
                "BLControlName": "aspect-ratio_1",
            },
        )
        meshing.workflow.TaskObject["Add Boundary Layers"].Arguments.set_state({})  # type: ignore

        meshing.workflow.TaskObject["aspect-ratio_1"].Execute()  # type: ignore

        # Generate volume mesh
        volume_mesh_gen = meshing.workflow.TaskObject["Generate the Volume Mesh"]  # type: ignore
        volume_mesh_gen.Arguments.set_state(  # type: ignore
            {
                "AllRegionNameList": [
                    "main",
                    "flow_pipe",
                    "outpipe3",
                    "object2",
                    "object1",
                    "void-region-1",
                    "fluid-region-1",
                ],
                "AllRegionSizeList": ["11.33375"] * 7,
                "AllRegionVolumeFillList": ["none"] * 6 + ["tet"],
                "EnableParallel": True,
            },
        )
        volume_mesh_gen.Execute()  # type: ignore

        # Check mesh
        meshing.tui.mesh.check_mesh()  # type: ignore

    @transaction()
    @instance("fluent_3ddp_meshing_instance")
    def close_fluent_3ddp_meshing(self, fluent_3ddp_meshing_instance: Fluent3DDPMeshingManager) -> None:
        fluent_3ddp_meshing_instance.shutdown()

    @transaction()
    @instance("fluent_3ddp_solver_instance")
    def get_working_dir_solver(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> Path:
        return Path(str(fluent_3ddp_solver_instance._instance_manager_impl.state_directory))  # type: ignore

    @transaction()
    @instance("fluent_3ddp_meshing_instance")
    def get_working_dir_meshing(self, fluent_3ddp_meshing_instance: Fluent3DDPMeshingManager) -> Path:
        return Path(str(fluent_3ddp_meshing_instance._instance_manager_impl.state_directory))  # type: ignore
