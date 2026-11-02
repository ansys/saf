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

"""Fluent step for the advanced solution example."""

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.fluent import Fluent3DDPSolverManager


class FluentStep(StepModel):
    """Step to manage the Fluent 3DDP Solver instance."""

    instance_created: bool = False
    version: str = "252"
    max_temperature_file: EntityHandle = NO_ENTITY
    simulation_output: EntityHandle = NO_ENTITY

    fluent_output_file: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(download=["version"], upload=["instance_created"]), enable_termination_event=True)
    @create_instance("fluent_3ddp_solver_instance", Fluent3DDPSolverManager)
    @long_running
    def launch_fluent(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
        """Initialize the Fluent 3DDP Solver instance."""
        self.transaction.raise_event(
            message="Initializing Fluent 3DDP Solver instance.",
            stream_name="fluent-output-stream",
        )
        try:
            fluent_3ddp_solver_instance.initialize(version=self.version)
        except Exception as e:
            self.transaction.raise_event(
                message=f"Fluent initialization failed: {e}",
                stream_name="fluent-output-stream",
            )
            raise
        self.instance_created = True
        self.transaction.raise_event(message="Fluent initialized.", stream_name="fluent-output-stream")

    @transaction(self=StepSpec(upload=["fluent_output_file"]), enable_termination_event=True)
    @instance("fluent_3ddp_solver_instance")
    @long_running
    def import_mesh(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
        """Import the mesh into the Fluent 3DDP Solver instance."""
        self.transaction.raise_event(message="Starting to import the mesh.", stream_name="fluent-output-stream")

        filepath = self.storage_scope.get_storage_root() / "fluent_output.txt"

        def on_transcript(transcript):  # type: ignore
            try:
                filepath.write_text(str(transcript))  # type: ignore
                self.fluent_output_file = self.storage_scope.store(filepath)
                self.transaction.raise_event(
                    message=str(transcript),  # type: ignore
                    stream_name="fluent-output-stream",
                )
            except Exception as e:
                self.transaction.raise_event(message=f"Mesh import failed: {e}", stream_name="fluent-output-stream")
                raise

        session = fluent_3ddp_solver_instance.instance

        session.transcript.register_callback(on_transcript)  # type: ignore

        self.transaction.raise_event(message="Started importing Mesh", stream_name="fluent-output-stream")

        # Import mesh
        try:
            example_file = self.transaction.get_asset_entity_handle("brake.msh.h5")
            example_file_path = fluent_3ddp_solver_instance.storage_scope.get_cached(example_file)
            session.tui.file.read_case(str(example_file_path))  # type: ignore
        except Exception as e:
            self.transaction.raise_event(message=f"Mesh import failed: {e}", stream_name="fluent-output-stream")
            raise

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

        session.transcript.stop()  # type: ignore

        self.transaction.raise_event(message="Mesh import success.", stream_name="fluent-output-stream")

    @transaction(
        self=StepSpec(upload=["simulation_output", "max_temperature_file", "fluent_output_file"]),
        enable_termination_event=True,
    )
    @instance("fluent_3ddp_solver_instance")
    @long_running
    def run_simulation(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
        """Run the simulation in the Fluent 3DDP Solver instance."""
        filepath = self.storage_scope.get_storage_root() / "fluent_output.txt"

        self.transaction.raise_event(message="Starting to run the simulation.", stream_name="fluent-output-stream")

        def on_trancript(transcript):  # type: ignore
            try:
                filepath.write_text(str(transcript))  # type: ignore
                self.fluent_output_file = self.storage_scope.store(filepath)
                self.transaction.raise_event(
                    message=str(transcript),  # type: ignore
                    stream_name="fluent-output-stream",
                )
            except Exception as e:
                self.transaction.raise_event(message=f"Run simulation failed: {e}", stream_name="fluent-output-stream")
                raise

        session = fluent_3ddp_solver_instance.instance

        session.transcript.register_callback(on_trancript)  # type: ignore

        try:
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

            max_temperature_file_path = (
                fluent_3ddp_solver_instance.storage_scope.get_storage_root() / "max-temperature.out"
            )
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
            session.tui.solve.dual_time_iterate(20, 5)  # type: ignore
            session.tui.file.write_case_data(str(simulation_output_path))  # type: ignore

            self.simulation_output = fluent_3ddp_solver_instance.storage_scope.store(simulation_output_path)
            self.max_temperature_file = fluent_3ddp_solver_instance.storage_scope.store(max_temperature_file_path)

        except Exception as e:
            self.transaction.raise_event(message=f"Run simulation failed: {e}", stream_name="fluent-output-stream")
            raise

        self.transaction.raise_event(message="Run simulation success.", stream_name="fluent-output-stream")

    @transaction(self=StepSpec(upload=["instance_created"]), enable_termination_event=True)
    @instance("fluent_3ddp_solver_instance")
    @long_running
    def shutdown_fluent(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
        """Shutdown the Fluent 3DDP Solver instance."""
        self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="fluent-output-stream")
        try:
            fluent_3ddp_solver_instance.shutdown()
        except Exception as e:
            self.transaction.raise_event(message=f"Fluent shutdown failed: {e}", stream_name="fluent-output-stream")
            raise
        self.instance_created = False
        self.transaction.raise_event(message="Fluent instance shutdown complete.", stream_name="fluent-output-stream")
