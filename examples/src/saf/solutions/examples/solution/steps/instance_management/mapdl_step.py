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

"""MAPDL step for the advanced solution example."""

from ansys.mapdl.core.plotting.theme import PyMAPDL_cmap  # pyright: ignore[reportMissingTypeStubs]
from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.mapdl import MapdlManager
import numpy as np
import pyvista as pv


class MapdlStep(StepModel):
    """MAPDL step for the advanced solution example."""

    instance_created: bool = False
    version: str = "252"
    nodal_values: list[float] = []
    solved: bool = False

    @transaction(self=StepSpec(download=["version"], upload=["instance_created"]), enable_termination_event=True)
    @create_instance("mapdl_instance", MapdlManager)
    @long_running
    def launch_mapdl(self, mapdl_instance: MapdlManager) -> None:
        """Launch a MAPDL instance with the specified version."""
        self.transaction.raise_event(message="Initializing MAPDL instance.", stream_name="mapdl-output-stream")
        try:
            mapdl_instance.initialize(version=self.version)

            mapdl = mapdl_instance.instance

            mapdl.clear()  # type: ignore
            mapdl.prep7()  # type: ignore
            mapdl.title("2-D Solenoid Actuator Static Analysis")  # type: ignore

            # Set up the FE model
            mapdl.et(1, "PLANE233")  # Define PLANE233 as element type  # type: ignore
            mapdl.keyopt(1, 3, 1)  # Use axisymmetric analysis option  # type: ignore
            mapdl.keyopt(1, 7, 1)  # Condense forces at the corner nodes  # type: ignore

            # Set material properties
            mapdl.mp("MURX", 1, 1)  # Define material properties (permeability), Air  # type: ignore
            mapdl.mp("MURX", 2, 1000)  # Permeability of backiron  # type: ignore
            mapdl.mp("MURX", 3, 1)  # Permeability of coil  # type: ignore
            mapdl.mp("MURX", 4, 2000)  # Permeability of armature  # type: ignore

            # Set parameters
            n_turns = 650  # Number of coil turns
            i_current = 1.0  # Current per turn
            ta = 0.75  # Model dimensions (centimeters)
            tb = 0.75
            tc = 0.50
            td = 0.75
            wc = 1
            hc = 2
            gap = 0.25
            space = 0.25
            ws = wc + 2 * space
            hs = hc + 0.75
            w = ta + ws + tc
            hb = tb + hs
            h = hb + gap + td
            acoil = wc * hc  # Cross-section area of coil (cm**2)
            jdens = n_turns * i_current / acoil  # Current density (A/cm**2)

            smart_size = 4  # Smart Size Level for Meshing

            # Create geometry
            mapdl.rectng(0, w, 0, tb)  # Create rectangular areas  # type: ignore
            mapdl.rectng(0, w, tb, hb)  # type: ignore
            mapdl.rectng(ta, ta + ws, 0, h)  # type: ignore
            mapdl.rectng(ta + space, ta + space + wc, tb + space, tb + space + hc)  # type: ignore
            mapdl.aovlap("ALL")  # type: ignore
            mapdl.rectng(0, w, 0, hb + gap)  # type: ignore
            mapdl.rectng(0, w, 0, h)  # type: ignore
            mapdl.aovlap("ALL")  # type: ignore
            mapdl.numcmp("AREA")  # Compress out unused area numbers  # type: ignore

            # Mesh
            mapdl.asel("S", "AREA", "", 2)  # Assign attributes to coil  # type: ignore
            mapdl.aatt(3, 1, 1, 0)  # type: ignore

            mapdl.asel("S", "AREA", "", 1)  # Assign attributes to armature  # type: ignore
            mapdl.asel("A", "AREA", "", 12, 13)  # type: ignore
            mapdl.aatt(4, 1, 1)  # type: ignore

            mapdl.asel("S", "AREA", "", 3, 5)  # Assign attributes to backiron  # type: ignore
            mapdl.asel("A", "AREA", "", 7, 8)  # type: ignore
            mapdl.aatt(2, 1, 1, 0)  # type: ignore

            mapdl.pnum("MAT", 1)  # Turn material numbers on  # type: ignore
            mapdl.allsel("ALL")  # type: ignore

            mapdl.smrtsize(smart_size)  # Set smart size meshing  # type: ignore
            mapdl.amesh("ALL")  # Mesh all areas  # type: ignore

            # Scale mesh to meters
            mapdl.esel("S", "MAT", "", 4)  # Select armature elements  # type: ignore
            mapdl.cm("ARM", "ELEM")  # Define armature as a component  # type: ignore
            mapdl.allsel("ALL")  # type: ignore
            mapdl.arscale(na1="all", rx=0.01, ry=0.01, rz=1, imove=1)  # Scale model to MKS (meters)  # type: ignore
            mapdl.finish()  # type: ignore

            # Loads and boundary conditions
            mapdl.slashsolu()  # type: ignore

            # Apply current density (A/m**2)
            mapdl.esel("S", "MAT", "", 3)  # Select coil elements  # type: ignore
            mapdl.bfe("ALL", "JS", 1, "", "", jdens / 0.01**2)  # type: ignore

            mapdl.esel("ALL")  # type: ignore
            mapdl.nsel("EXT")  # Select exterior nodes  # type: ignore
            mapdl.d("ALL", "AZ", 0)  # Set potentials to zero (flux-parallel)  # type: ignore

        except Exception as e:
            self.transaction.raise_event(message=f"MAPDL initialization failed: {e}", stream_name="mapdl-output-stream")
            raise
        self.instance_created = True
        self.transaction.raise_event(message="MAPDL initialized.", stream_name="mapdl-output-stream")

    @transaction(self=StepSpec(upload=["solved"]), enable_termination_event=True)
    @instance("mapdl_instance")
    @long_running
    def solve_model(self, mapdl_instance: MapdlManager) -> None:
        """Solve the finite element model using MAPDL."""
        self.transaction.raise_event(message="Solving Model.", stream_name="mapdl-output-stream")
        try:
            mapdl = mapdl_instance.instance

            mapdl.allsel("ALL")  # type: ignore
            mapdl.solve()  # type: ignore
            mapdl.finish()  # type: ignore

            self.solved = True
        except Exception as e:
            self.transaction.raise_event(message=f"Solve model failed: {e}", stream_name="mapdl-output-stream")
            raise
        self.transaction.raise_event(message="Solve model succeeded.", stream_name="mapdl-output-stream")

    @transaction(self=StepSpec(upload=["nodal_values"]), enable_termination_event=True)
    @instance("mapdl_instance")
    @long_running
    def postprocessing(self, mapdl_instance: MapdlManager) -> None:
        """Post-process the results and create a plot of the magnetic flux in the X direction."""
        self.transaction.raise_event(message="Postprocessing results.", stream_name="mapdl-output-stream")
        try:
            mapdl = mapdl_instance.instance

            mapdl.post1()  # type: ignore
            mapdl.file("file", "rmg")  # type: ignore
            mapdl.set("last")  # type: ignore

            self.nodal_values = mapdl.post_processing.nodal_values("b", "x").tolist()  # type: ignore

            # Create an MAPDL Power Graphics plot of the X-direction magnetic flux
            mapdl.graphics("power")  # type: ignore
            mapdl.rgb("INDEX", 100, 100, 100, 0)  # type: ignore
            mapdl.rgb("INDEX", 80, 80, 80, 13)  # type: ignore
            mapdl.rgb("INDEX", 60, 60, 60, 14)  # type: ignore
            mapdl.rgb("INDEX", 0, 0, 0, 15)  # type: ignore

            mapdl.edge(1, 1)  # type: ignore

            # Obtain grid and scalar data
            elem_mats = mapdl.mesh.material_type  # type: ignore
            grids = []
            scalars = []
            for mat in np.unique(elem_mats):  # type: ignore
                mapdl.esel("s", "mat", "", mat)  # type: ignore
                mapdl.nsle()  # type: ignore
                grids.append(mapdl.mesh.grid)  # type: ignore
                scalars.append(mapdl.post_processing.nodal_values("b", "x"))  # type: ignore
            mapdl.allsel()  # type: ignore

            # Color map and result plot
            plotter = pv.Plotter()  # type: ignore
            for i, grid in enumerate(grids):  # type: ignore
                plotter.add_mesh(  # type: ignore
                    grid,  # type: ignore
                    scalars=scalars[i],  # type: ignore
                    show_edges=True,
                    cmap=PyMAPDL_cmap,  # type: ignore
                    n_colors=9,
                    scalar_bar_args={
                        "color": "black",
                        "title": "B Flux X",
                        "vertical": False,
                        "n_labels": 10,
                    },
                )

            plotter.set_background(color="white")  # type: ignore
            _ = plotter.camera_position = "xy"
        except Exception as e:
            self.transaction.raise_event(
                message=f"Results postprocessing failed: {e}",
                stream_name="mapdl-output-stream",
            )
            raise
        self.transaction.raise_event(message="Results postprocessing succeeded.", stream_name="mapdl-output-stream")

    @transaction(self=StepSpec(upload=["instance_created"]), enable_termination_event=True)
    @instance("mapdl_instance")
    @long_running
    def shutdown_mapdl(self, mapdl_instance: MapdlManager) -> None:
        """Close the MAPDL instance."""
        self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="mapdl-output-stream")
        try:
            mapdl = mapdl_instance.instance
            mapdl.graphics("FULL")  # Returning to default mode.  # type: ignore

            mapdl_instance.shutdown()
        except Exception as e:
            self.transaction.raise_event(message=f"MAPDL shutdown failed: {e}", stream_name="mapdl-output-stream")
            raise
        self.instance_created = False
        self.transaction.raise_event(message="MAPDL instance shutdown complete.", stream_name="mapdl-output-stream")
