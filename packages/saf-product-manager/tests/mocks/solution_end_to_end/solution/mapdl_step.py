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

from ansys.mapdl.core.plotting.theme import PyMAPDL_cmap  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
import pyvista as pv

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.mapdl import MapdlManager

logger = logging.getLogger(__name__)


class MapdlStep(StepModel):
    # Example copied from https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/2d_magnetostatic_solenoid-BodyFlux_Averaging.html#sphx-glr-examples-gallery-examples-00-mapdl-examples-2d-magnetostatic-solenoid-bodyflux-averaging-py
    version: str = "252"
    nodal_values: list[float] = []
    test_file: EntityHandle = NO_ENTITY
    files_in_working_dir: list[str] = []
    working_dir: str = ""
    solved: bool = False
    mapdl_available: bool = False

    @transaction(self=StepSpec(download=["version"], upload=["test_file"]))
    @create_instance("mapdl_instance", MapdlManager)
    @long_running
    def launch_mapdl(self, mapdl_instance: MapdlManager) -> int:
        mapdl_instance.initialize(version=self.version)
        test_file = self.storage_scope.get_storage_root() / "test_file.txt"
        test_file.write_text("my_test_file")
        self.test_file = self.storage_scope.store(test_file)
        return mapdl_instance.instance.port

    @transaction()
    @instance("mapdl_instance")
    def prepare_env(self, mapdl_instance: MapdlManager) -> None:
        mapdl = mapdl_instance.instance
        mapdl.clear()  # type: ignore
        mapdl.prep7()  # type: ignore
        mapdl.title("2-D Solenoid Actuator Static Analysis")  # type: ignore

    @transaction(self=StepSpec(download=["test_file"]))
    @instance("mapdl_instance")
    def upload_files(self, mapdl_instance: MapdlManager) -> None:
        mapdl = mapdl_instance.instance
        test_file = self.storage_scope.get_cached(self.test_file)
        mapdl.upload(str(test_file))  # type: ignore

    @transaction(self=StepSpec(upload=["test_file"]))
    @instance("mapdl_instance")
    def download_files(self, mapdl_instance: MapdlManager) -> None:
        mapdl = mapdl_instance.instance
        target_dir = str(self.storage_scope.get_storage_root() / "downloaded_files")
        mapdl.download(files="test_file.txt", target_dir=target_dir)
        self.test_file = self.storage_scope.store(Path(target_dir) / "test_file.txt")

    @transaction(self=StepSpec(upload=["files_in_working_dir", "working_dir"]))
    @instance("mapdl_instance")
    def list_files(self, mapdl_instance: MapdlManager) -> None:
        mapdl = mapdl_instance.instance
        self.files_in_working_dir = mapdl.list_files()
        self.working_dir = mapdl.directory  # type: ignore

    @transaction()
    @instance("mapdl_instance")
    def log_message(self, mapdl_instance: MapdlManager) -> None:
        mapdl = mapdl_instance.instance
        mapdl._log.warning("Simulates warning message from mapdl.")  # type: ignore

    @transaction()
    @instance("mapdl_instance")
    def setup_fe_model(self, mapdl_instance: MapdlManager) -> None:
        mapdl = mapdl_instance.instance

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

    @transaction(self=StepSpec(upload=["solved"]))
    @instance("mapdl_instance")
    @long_running
    def solve_model(self, mapdl_instance: MapdlManager) -> None:
        mapdl = mapdl_instance.instance

        mapdl.allsel("ALL")  # type: ignore
        mapdl.solve()  # type: ignore
        mapdl.finish()  # type: ignore

        self.solved = True

    @transaction(self=StepSpec(upload=["nodal_values"]))
    @instance("mapdl_instance")
    def postprocessing(self, mapdl_instance: MapdlManager) -> None:
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

        # mapdl.show("png") <- don't plot, it spawns a window showing the mesh
        # mapdl.pngr("tmod", 0)

        # mapdl.plnsol("b", "x")
        # mapdl.show("") <- don't plot, it spawns a window showing the mesh

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
                grid,  # pyright: ignore[reportUnknownArgumentType]
                scalars=scalars[i],  # pyright: ignore[reportUnknownArgumentType]
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
        # plotter.show() <- don't plot, it spawns a window showing the mesh

    @transaction(self=StepSpec())
    @instance("mapdl_instance")
    def close_mapdl(self, mapdl_instance: MapdlManager) -> None:
        mapdl = mapdl_instance.instance
        mapdl.graphics("FULL")  # Returning to default mode.  # type: ignore

        mapdl_instance.shutdown()

    @transaction(self=StepSpec(upload=["mapdl_available"]))
    @instance("mapdl_instance")
    def refresh_availability(self, mapdl_instance: MapdlManager) -> None:
        self.mapdl_available = bool(
            mapdl_instance._instance_manager_impl._find_instance(),  # pyright: ignore[reportPrivateUsage]
        )
