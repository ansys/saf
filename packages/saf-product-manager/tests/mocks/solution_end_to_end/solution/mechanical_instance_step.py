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
from pathlib import Path
from time import sleep

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.mechanical import MechanicalManager

logger = logging.getLogger(__name__)


class MechanicalInstanceStep(StepModel):
    # Example copied from https://examples.mechanical.docs.pyansys.com/examples/00_basic/example_01_simple_structural_solve.html#

    version: str = "252"
    example_file: EntityHandle = NO_ENTITY
    output_handle: EntityHandle = NO_ENTITY
    test_file: EntityHandle = NO_ENTITY
    working_files: list[str] = []
    mechanical_available: bool = False
    working_dir: str = ""

    @transaction(self=StepSpec(download=["version"], upload=["test_file"]))
    @create_instance("mechanical_instance", MechanicalManager)
    @long_running
    def launch_mechanical(self, mechanical_instance: MechanicalManager) -> None:
        mechanical_instance.initialize(version=self.version)
        test_file_path = self.storage_scope.get_storage_root() / "test_file.txt"
        test_file_path.write_text("my_test_file")
        self.test_file = self.storage_scope.store(test_file_path)

    @transaction(self=StepSpec())
    @instance("mechanical_instance")
    def mechanical_port(self, mechanical_instance: MechanicalManager) -> int:
        return mechanical_instance.instance._port  # type: ignore

    @transaction(self=StepSpec(download=["example_file"]))
    @instance("mechanical_instance")
    def upload_example_file_to_mechanical(self, mechanical_instance: MechanicalManager) -> None:
        mechanical = mechanical_instance.instance
        geometry_path = self.storage_scope.get_cached(self.example_file)
        mechanical.upload(file_name=geometry_path)  # type: ignore

    @transaction(self=StepSpec(download=["example_file"]))
    @instance("mechanical_instance")
    def initialize_variable_workflow(self, mechanical_instance: MechanicalManager) -> None:
        mechanical = mechanical_instance.instance
        geometry_path = mechanical_instance.storage_scope.get_cached(self.example_file)
        project_directory = mechanical.project_directory  # type: ignore

        # Build the path relative to project directory.
        combined_path = str(Path(project_directory) / geometry_path.name)  # type: ignore
        path_in_mechanical = combined_path.replace("\\", "\\\\")
        mechanical.run_python_script(f"part_file_path='{path_in_mechanical}'")

    @transaction()
    @instance("mechanical_instance")
    def log_message(self, mechanical_instance: MechanicalManager) -> None:
        mechanical = mechanical_instance.instance
        mechanical.log_warning("Simulates warning message from mechanical.")  # type: ignore

    @transaction(self=StepSpec(download=["test_file"]))
    @instance("mechanical_instance")
    def upload_files(self, mechanical_instance: MechanicalManager) -> None:
        mechanical = mechanical_instance.instance
        test_file = self.storage_scope.get_cached(self.test_file)
        mechanical.upload(str(test_file))  # type: ignore

    @transaction(self=StepSpec(upload=["test_file"]))
    @instance("mechanical_instance")
    def download_files(self, mechanical_instance: MechanicalManager) -> None:
        mechanical = mechanical_instance.instance
        test_file_path = ""
        for file_path in mechanical.list_files():  # type: ignore
            if file_path.find("test_file.txt") != -1:  # type: ignore
                test_file_path = file_path  # type: ignore
                break
        if not test_file_path:
            raise RuntimeError("test_file.txt not found.")
        file_paths = mechanical.download(  # type: ignore
            test_file_path,
            target_dir=self.storage_scope.get_storage_root() / "downloaded_files",
        )
        self.test_file = self.storage_scope.store(file_paths[0])  # type: ignore

    @transaction(self=StepSpec(upload=["working_files"]))
    @instance("mechanical_instance")
    def export_working_dir_file_list(self, mechanical_instance: MechanicalManager) -> None:
        mechanical = mechanical_instance.instance
        self.working_files = mechanical.list_files()  # type: ignore

    @transaction()
    @instance("mechanical_instance")
    @long_running
    def run_script(self, mechanical_instance: MechanicalManager) -> None:
        mechanical = mechanical_instance.instance

        # Run the script
        mechanical.run_python_script(
            """
import json

# Section 1: Read geometry information
geometry_import_group_11 = Model.GeometryImportGroup
geometry_import_19 = geometry_import_group_11.AddGeometryImport()

geometry_import_19_format = Ansys.Mechanical.DataModel.Enums.GeometryImportPreference.\
    Format.Automatic
geometry_import_19_preferences = Ansys.ACT.Mechanical.Utilities.GeometryImportPreferences()
geometry_import_19_preferences.ProcessNamedSelections = True
geometry_import_19_preferences.ProcessCoordinateSystems = True

geometry_import_19.Import(part_file_path, geometry_import_19_format, geometry_import_19_preferences)

Model.AddStaticStructuralAnalysis()
STAT_STRUC = Model.Analyses[0]
CS_GRP = Model.CoordinateSystems
ANALYSIS_SETTINGS = STAT_STRUC.Children[0]
SOLN= STAT_STRUC.Solution

# Section 2: Set up the unit system.

ExtAPI.Application.ActiveUnitSystem = MechanicalUnitSystem.StandardMKS
ExtAPI.Application.ActiveAngleUnit = AngleUnitType.Radian

# Section 3: Define named selection and coordinate system.

NS1 = Model.NamedSelections.Children[0]
NS2 = Model.NamedSelections.Children[1]
NS3 = Model.NamedSelections.Children[2]
NS4 = Model.NamedSelections.Children[3]
GCS = CS_GRP.Children[0]
LCS1 = CS_GRP.Children[1]

# Section 4: Define remote point.

RMPT_GRP = Model.RemotePoints
RMPT_1 = RMPT_GRP.AddRemotePoint()
RMPT_1.Location = NS1
RMPT_1.XCoordinate=Quantity("7 [m]")
RMPT_1.YCoordinate=Quantity("0 [m]")
RMPT_1.ZCoordinate=Quantity("0 [m]")

#  Section 5: Define mesh settings.

MSH = Model.Mesh
MSH.ElementSize =Quantity("0.5 [m]")
MSH.GenerateMesh()

#  Section 6: Define boundary conditions.

# Insert fixed support.
FIX_SUP = STAT_STRUC.AddFixedSupport()
FIX_SUP.Location = NS2

# Insert frictionless support.
FRIC_SUP = STAT_STRUC.AddFrictionlessSupport()
FRIC_SUP.Location = NS3

#  Section 7: Define remote force.

REM_FRC1 = STAT_STRUC.AddRemoteForce()
REM_FRC1.Location = RMPT_1
REM_FRC1.DefineBy =LoadDefineBy.Components
REM_FRC1.XComponent.Output.DiscreteValues = [Quantity("1e10 [N]")]

#  Section 8: Define thermal condition.

THERM_COND = STAT_STRUC.AddThermalCondition()
THERM_COND.Location = NS4
THERM_COND.Magnitude.Output.DefinitionType=VariableDefinitionType.Formula
THERM_COND.Magnitude.Output.Formula="50*(20+z)"
THERM_COND.XYZFunctionCoordinateSystem=LCS1
THERM_COND.RangeMinimum=Quantity("-20 [m]")
THERM_COND.RangeMaximum=Quantity("1 [m]")

#  Section 9: Insert directional deformation.

DIR_DEF = STAT_STRUC.Solution.AddDirectionalDeformation()
DIR_DEF.Location = NS1
DIR_DEF.NormalOrientation =NormalOrientationType.XAxis

# Section 10: Add total deformation and force reaction probe.

TOT_DEF = STAT_STRUC.Solution.AddTotalDeformation()

# Add force reaction.
FRC_REAC_PROBE = STAT_STRUC.Solution.AddForceReaction()
FRC_REAC_PROBE.BoundaryConditionSelection = FIX_SUP
FRC_REAC_PROBE.ResultSelection =ProbeDisplayFilter.XAxis

# Section 11: Solve and get the results.

# Solve static analysis.
STAT_STRUC.Solution.Solve(True)

dir_deformation_details = {
"Minimum": str(DIR_DEF.Minimum),
"Maximum": str(DIR_DEF.Maximum),
"Average": str(DIR_DEF.Average),
}

json.dumps(dir_deformation_details)""",
        )

    @transaction(self=StepSpec(upload=["output_handle"]))
    @instance("mechanical_instance")
    def download_output_solve(self, mechanical_instance: MechanicalManager) -> None:
        mechanical = mechanical_instance.instance

        solve_out_path = ""
        n = 0
        nmax = 10
        while not solve_out_path and n < nmax:
            for file_path in mechanical.list_files():  # type: ignore
                if file_path.find("solve.out") != -1:  # type: ignore
                    solve_out_path = file_path  # type: ignore
                    break
            n += 1
            sleep(0.1)
        if not solve_out_path:
            raise RuntimeError("solve.out not found.")

        downloaded_files = mechanical.download(solve_out_path, target_dir=self.storage_scope.get_storage_root())  # type: ignore
        self.output_handle = self.storage_scope.store(downloaded_files[0])  # type: ignore

    @transaction(self=StepSpec())
    @instance("mechanical_instance")
    def close_mechanical(self, mechanical_instance: MechanicalManager) -> None:
        mechanical_instance.shutdown()

    @transaction(self=StepSpec(upload=["mechanical_available"]))
    @instance("mechanical_instance")
    def refresh_availability(self, mechanical_instance: MechanicalManager) -> None:
        self.mechanical_available = bool(
            mechanical_instance._instance_manager_impl._find_instance(),  # pyright: ignore[reportPrivateUsage]
        )
