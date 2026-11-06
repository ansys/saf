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

# ©2024, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Mechanical step for the advanced solution example."""

from pathlib import Path
from time import sleep

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.mechanical import MechanicalManager


class MechanicalStep(StepModel):
    """Step to manage a Mechanical instance."""

    instance_created: bool = False
    version: str = "252"
    output_handle: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(download=["version"], upload=["instance_created"]), enable_termination_event=True)
    @create_instance("mechanical_instance", MechanicalManager)
    @long_running
    def launch_mechanical(self, mechanical_instance: MechanicalManager) -> None:
        """Launch the Mechanical instance."""
        self.transaction.raise_event(
            message="Initializing Mechanical instance.",
            stream_name="mechanical-output-stream",
        )
        try:
            mechanical_instance.initialize(version=self.version)
        except Exception as e:
            self.transaction.raise_event(
                message=f"Mechanical initialization failed: {e}",
                stream_name="mechanical-output-stream",
            )
            raise
        self.transaction.raise_event(message="Mechanical initialized.", stream_name="mechanical-output-stream")
        self.instance_created = True

    @transaction()
    @instance("mechanical_instance")
    def upload_example_file_to_mechanical(self, mechanical_instance: MechanicalManager) -> None:
        """Upload the example file to Mechanical instance."""
        self.transaction.raise_event(message="Uploading file.", stream_name="mechanical-output-stream")

        try:
            mechanical = mechanical_instance.instance
            asset_handle = self.transaction.get_asset_entity_handle("example_01_geometry.agdb")
            geometry_path = self.storage_scope.get_cached(asset_handle)
            mechanical.upload(file_name=geometry_path)  # type: ignore
        except Exception as e:
            self.transaction.raise_event(message=f"File upload failed: {e}", stream_name="mechanical-output-stream")
            raise

    @transaction()
    @instance("mechanical_instance")
    def initialize_variable_workflow(self, mechanical_instance: MechanicalManager) -> None:
        """Initialize the variable workflow in Mechanical instance."""
        self.transaction.raise_event(
            message="Starting to initialize variables.",
            stream_name="mechanical-output-stream",
        )

        mechanical = mechanical_instance.instance

        try:
            self.transaction.raise_event(
                message="Initializing variable workflow in Mechanical instance.",
                stream_name="mechanical-output-stream",
            )
            asset_handle = self.transaction.get_asset_entity_handle("example_01_geometry.agdb")
            geometry_path = mechanical_instance.storage_scope.get_cached(asset_handle)
            self.transaction.raise_event(
                message=f"Geometry path: {geometry_path}",
                stream_name="mechanical-output-stream",
            )
            project_directory = mechanical.project_directory  # type: ignore
            self.transaction.raise_event(
                message=f"Project directory: {project_directory}",
                stream_name="mechanical-output-stream",
            )

            # Build the path relative to project directory.
            combined_path = str(Path(project_directory) / geometry_path.name)  # type: ignore
            path_in_mechanical = combined_path.replace("\\", "\\\\")
            mechanical.run_python_script(f"part_file_path='{path_in_mechanical}'")
        except Exception as e:
            self.transaction.raise_event(
                message=f"Mechanical variables initialized failed: {e}",
                stream_name="mechanical-output-stream",
            )
            raise

    @transaction(enable_termination_event=True)
    @instance("mechanical_instance")
    @long_running
    def run_script(self, mechanical_instance: MechanicalManager) -> None:
        """Run a script in the Mechanical instance."""
        mechanical = mechanical_instance.instance

        self.transaction.raise_event(
            message="Running script in Mechanical instance.",
            stream_name="mechanical-output-stream",
        )

        try:
            # Run the script
            output = mechanical.run_python_script(
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
        except Exception as e:
            self.transaction.raise_event(message=f"Run Script failed: {e}", stream_name="mechanical-output-stream")
            raise

        self.transaction.raise_event(message=f"Run Script succeeded. {output}", stream_name="mechanical-output-stream")

    @transaction(self=StepSpec(upload=["output_handle"]), enable_termination_event=True)
    @instance("mechanical_instance")
    @long_running
    def download_output_file(self, mechanical_instance: MechanicalManager) -> None:
        """Download the output file from Mechanical instance."""
        mechanical = mechanical_instance.instance

        self.transaction.raise_event(
            message="Downloading file to the current working directory.",
            stream_name="mechanical-output-stream",
        )

        try:
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

            downloaded_files = mechanical.download(  # type: ignore
                solve_out_path, target_dir=self.storage_scope.get_storage_root()
            )
            self.output_handle = self.storage_scope.store(downloaded_files[0])  # type: ignore
        except Exception as e:
            self.transaction.raise_event(message=f"File download failed: {e}", stream_name="mechanical-output-stream")
            raise

        self.transaction.raise_event(
            message=f"File downloaded to {downloaded_files[0]}.",
            stream_name="mechanical-output-stream",
        )

    @transaction(self=StepSpec(upload=["instance_created"]), enable_termination_event=True)
    @instance("mechanical_instance")
    @long_running
    def shutdown_mechanical(self, mechanical_instance: MechanicalManager) -> None:
        """Close the Mechanical instance."""
        self.transaction.raise_event(
            message="Starting to shutdown the instance.",
            stream_name="mechanical-output-stream",
        )

        try:
            mechanical_instance.shutdown()
        except Exception as e:
            self.transaction.raise_event(
                message=f"Mechanical shutdown failed: {e}",
                stream_name="mechanical-output-stream",
            )
            raise
        self.transaction.raise_event(
            message="Mechanical instance shutdown complete.",
            stream_name="mechanical-output-stream",
        )
        self.instance_created = False
