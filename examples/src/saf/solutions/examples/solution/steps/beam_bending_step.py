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

# ©2023, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""This module defines the ``BeamBendingStep`` class.

It computes both the analytical solution based on Euler-Bernoulli beam theory and the
numerical solution using MAPDL for a simply supported beam subjected to a concentrated
load. The workflow covers instance management, model preprocessing, solving, and
postprocessing, including nodal displacement and element stress results.
"""

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
from ansys.saf.product_manager.mapdl import MapdlManager

from saf.solutions.examples.solution.scripts.beam_bending import mapdl_model, theoretical_model


class BeamBendingStep(StepModel):
    """Step model for the analytical and numerical solution of a simply supported beam under a concentrated load."""

    # Input parameters

    length_a: float = 1000  # mm
    length_b: float = 1000  # mm
    diameter: float = 50  # mm

    elasticity_modulus: float = 210e3  # MPa
    poisson_ratio: float = 0.27

    load: float = 10e3  # N

    nbr_of_pts: int = 100  # number of points where the deflection is computed for the theoretical solution

    mapdl_nbr_of_elements: int = 4  # must be >= 2
    mapdl_version: int = 252
    mapdl_host: str = "127.0.0.1"
    mapdl_port: int = 8080
    mapdl_start_timeout: int = 60
    mapdl_loglevel: str = "INFO"
    mapdl_nproc: int = 2
    mapdl_jobname: str = "mapdl_2d_beam"
    mapdl_instance_started: bool = False

    # Output parameters

    theoretical_deflection: list[list[float]] = []  # [[mm], [mm]]

    mapdl_deflection: list[list[float]] = []  # [[mm], [mm]]
    mapdl_nodal_displacement: EntityHandle = NO_ENTITY
    mapdl_element_stress: EntityHandle = NO_ENTITY

    @transaction(
        self=StepSpec(
            download=["length_a", "length_b", "diameter", "elasticity_modulus", "load", "nbr_of_pts"],
            upload=["theoretical_deflection"],
        ),
        enable_termination_event=True,
    )
    @long_running
    def compute_theoretical_beam_deflection(self) -> None:
        """Compute the deflection of a simply supported beam using Euler-Bernoulli beam theory."""
        self.theoretical_deflection = theoretical_model.compute_beam_deflection(  # type: ignore
            self.length_a, self.length_b, self.diameter, self.elasticity_modulus, self.load, n=self.nbr_of_pts
        )

    @transaction(self=StepSpec(download=["mapdl_version"]), enable_termination_event=True)
    @create_instance("mapdl_manager", MapdlManager)
    def start_mapdl(self, mapdl_manager: MapdlManager) -> None:
        """Start the MAPDL instance."""
        mapdl_manager.initialize(version=str(self.mapdl_version))

    @transaction(
        self=StepSpec(
            download=[
                "length_a",
                "length_b",
                "diameter",
                "elasticity_modulus",
                "poisson_ratio",
                "load",
                "mapdl_nbr_of_elements",
            ]
        ),
        enable_termination_event=True,
    )
    @instance("mapdl_manager", identifier="mapdl_manager")
    @long_running
    def mapdl_preprocessing(self, mapdl_manager: MapdlManager) -> None:
        """Set up the beam model."""
        mapdl = mapdl_manager.instance
        setup = mapdl_model.Setup(
            mapdl,
            self.length_a + self.length_b,
            self.diameter / 2.0,
            self.elasticity_modulus,
            self.poisson_ratio,
            self.length_a,
            self.load,
            number_of_elements=self.mapdl_nbr_of_elements,
        )
        setup.mesh()
        setup.boundary_conditions()
        setup.load()
        # TODO: compute mesh quality metrics and return in step field

    @transaction(self=StepSpec(), enable_termination_event=True)
    @instance("mapdl_manager", identifier="mapdl_manager")
    @long_running
    def mapdl_solve(self, mapdl_manager: MapdlManager) -> None:
        """Solve the beam model."""
        mapdl = mapdl_manager.instance
        solve = mapdl_model.Solve(mapdl)
        solve.solve()

    @transaction(
        self=StepSpec(upload=["mapdl_deflection", "mapdl_nodal_displacement", "mapdl_element_stress"]),
        enable_termination_event=True,
    )
    @instance("mapdl_manager", identifier="mapdl_manager")
    @long_running
    def mapdl_postprocessing(self, mapdl_manager: MapdlManager) -> None:
        """Postprocess the results of the model."""
        mapdl = mapdl_manager.instance
        post_process = mapdl_model.PostProcess(mapdl)
        deformed_state = post_process.get_deformed_state().tolist()  # type: ignore
        x = [node_coordinates[0] for node_coordinates in deformed_state]  # pyright: ignore[reportUnknownVariableType]
        y = [node_coordinates[2] for node_coordinates in deformed_state]  # pyright: ignore[reportUnknownVariableType]
        self.mapdl_deflection = [x, y]  # pyright: ignore[reportUnknownMemberType]
        mapdl_nodal_displacement_path = mapdl_manager.storage_scope.get_storage_root() / "nodal_displacement.png"
        mapdl_element_stress_path = mapdl_manager.storage_scope.get_storage_root() / "element_stress.png"
        post_process.plot_nodal_displacement(str(mapdl_nodal_displacement_path))
        post_process.plot_element_stress(str(mapdl_element_stress_path))
        self.mapdl_nodal_displacement = mapdl_manager.storage_scope.store(mapdl_nodal_displacement_path)
        self.mapdl_element_stress = mapdl_manager.storage_scope.store(mapdl_element_stress_path)
