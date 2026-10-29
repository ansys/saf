# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Backend of the operating point step."""

from pathlib import Path

from ansys.saf.glow.solution import (
    NO_ENTITY,
    BadRequestError,
    EntityHandle,
    StepModel,
    StepSpec,
    long_running,
    transaction,
    instance,
)
from ansys.saf.product_manager.visor import VisorManager
from ansys.visor.viewer import Metadata

from saf.solutions.examples.solution.logic.pump.constants import (
    CASE_FILE_NAME,
    DEFAULT_IMPELLER_SPEED_RPM,
    DEFAULT_ITERATION_COUNT,
    DEFAULT_MASS_FLOW_RATE,
    DEFAULT_TIME_STEP_SCALE_FACTOR,
    LOG_TAIL_LINES,
    RUN_SIMULATION_HISTORY_STREAM,
    RUN_SIMULATION_LOG_STREAM,
    RUN_SIMULATION_PROGRESS_STREAM,
    SCENE_UNIT,
    SOLVED_SCENE_FILE_NAME,
    SOLVED_SCENE_NAME,
)
from saf.solutions.examples.solution.logic.pump.results import (
    angular_velocity,
    build_convergence_history,
    hydraulic_efficiency,
    hydraulic_power,
    is_converged,
    pump_head,
    shaft_power,
    volumetric_flow_rate,
)
from saf.solutions.examples.solution.logic.pump.solver import OperatingPoint, RawResults, run_operating_point
from saf.solutions.examples.solution.logic.pump.scene_export import export_scene

_SECONDS_PER_HOUR: float = 3600.0


class PumpSolveStep(StepModel):
    """Solves the case at one operating point and exposes the pump KPIs."""

    impeller_speed_rpm: float = DEFAULT_IMPELLER_SPEED_RPM
    mass_flow_rate: float = DEFAULT_MASS_FLOW_RATE
    iteration_count: int = DEFAULT_ITERATION_COUNT
    time_step_scale_factor: float = DEFAULT_TIME_STEP_SCALE_FACTOR

    progress_stage: str = ""
    progress_fraction: float = 0.0
    log_text: str = ""

    pump_head_m: float = 0.0
    hydraulic_efficiency: float = 0.0
    shaft_power_w: float = 0.0
    pressure_rise_pa: float = 0.0
    inlet_total_pressure_pa: float = 0.0
    outlet_total_pressure_pa: float = 0.0
    blade_pressure_pa: float = 0.0
    blade_torque_nm: float = 0.0
    volumetric_flow_m3h: float = 0.0
    converged: bool = False
    convergence_history: list[dict[str, float]] = []

    contour_image: EntityHandle = NO_ENTITY
    solved_case_file: EntityHandle = NO_ENTITY
    solved_data_file: EntityHandle = NO_ENTITY
    solved_scene_file: EntityHandle = NO_ENTITY

    @long_running
    @transaction(
        # Without this, the UI never learns that the run ended: the progress events stop at 100%
        # and the notification stays open. GLOW publishes the final MethodState, success or
        # failure, on a stream named after the method, which is RUN_SIMULATION_STREAM.
        enable_termination_event=True,
        self=StepSpec(
            upload=[
                "pump_head_m",
                "hydraulic_efficiency",
                "shaft_power_w",
                "pressure_rise_pa",
                "inlet_total_pressure_pa",
                "outlet_total_pressure_pa",
                "blade_pressure_pa",
                "blade_torque_nm",
                "volumetric_flow_m3h",
                "converged",
                "convergence_history",
                "contour_image",
                "solved_case_file",
                "solved_data_file",
                "solved_scene_file",
                "progress_stage",
                "progress_fraction",
                "log_text",
            ],
            download=[
                "impeller_speed_rpm",
                "mass_flow_rate",
                "iteration_count",
                "time_step_scale_factor",
            ],
        ),
        pump_model_setup_step=StepSpec(download=["case_file", "processor_count"]),
    )
    def run_simulation(self, pump_model_setup_step) -> None:
        """Solve at the configured operating point and store the KPIs and artefacts."""
        if pump_model_setup_step.case_file == NO_ENTITY:
            raise BadRequestError("Build the case on the Model Setup page before running a simulation.")

        params = OperatingPoint(
            impeller_speed_rpm=self.impeller_speed_rpm,
            mass_flow_rate=self.mass_flow_rate,
            iteration_count=self.iteration_count,
            time_step_scale_factor=self.time_step_scale_factor,
            processor_count=pump_model_setup_step.processor_count,
        )

        # Fluent must work inside the method storage root: storage_scope.store rejects any path
        # outside it. The root is already private to this method execution.
        work_dir = Path(self.storage_scope.get_storage_root())
        case_path = work_dir / CASE_FILE_NAME
        case_path.write_bytes(self.storage_scope.get_bytes(pump_model_setup_step.case_file))

        self.log_text = ""
        self._log_lines: list[str] = []
        try:
            raw = run_operating_point(
                case_path, work_dir, params, self._report_progress, self._report_log, self._report_history
            )
        except ValueError as error:
            # GLOW replaces an uncaught exception with a generic 500 that hides the message.
            # BadRequestError is relayed to the client verbatim, so the validation text reaches the user.
            raise BadRequestError(str(error)) from error

        self._store_results(raw, params)

    @long_running
    @transaction(
        enable_termination_event=True,
        self=StepSpec(download=["solved_case_file", "solved_data_file"], upload=["solved_scene_file"]),
    )
    def prepare_solved_scene(self) -> None:
        """Convert the solved case into a VTKHDF scene for the 3D viewer."""
        if self.solved_case_file == NO_ENTITY or self.solved_data_file == NO_ENTITY:
            raise BadRequestError("Run the simulation before preparing the 3D view.")
        work_dir = Path(self.storage_scope.get_storage_root())
        try:
            scene_path = export_scene(
                Path(self.storage_scope.get_cached(self.solved_case_file)),
                Path(self.storage_scope.get_cached(self.solved_data_file)),
                work_dir,
                SOLVED_SCENE_FILE_NAME,
            )
        except RuntimeError as error:
            raise BadRequestError(str(error)) from error
        self.solved_scene_file = self.storage_scope.store(scene_path)

    @transaction(self=StepSpec(download=["solved_scene_file"]))
    @instance("pump_model_setup_step.visor_manager")
    def show_solved_scene(self, visor_manager: VisorManager) -> None:
        """Load the converted solved case into the Visor instance started by the setup step."""
        if self.solved_scene_file == NO_ENTITY:
            raise BadRequestError("The 3D view has not been prepared yet.")
        path = Path(self.storage_scope.get_cached(self.solved_scene_file))
        visor_manager.instance.update(path.as_posix(), Metadata(name=SOLVED_SCENE_NAME, unit=SCENE_UNIT))

    def _store_results(self, raw: RawResults, params: OperatingPoint) -> None:
        """Derive the engineering quantities and persist everything."""
        head = pump_head(raw.inlet_total_pressure_pa, raw.outlet_total_pressure_pa)
        flow = volumetric_flow_rate(params.mass_flow_rate)
        omega = angular_velocity(params.impeller_speed_rpm)
        power_in = shaft_power(raw.blade_torque_nm, omega)

        self.pump_head_m = head
        self.volumetric_flow_m3h = flow * _SECONDS_PER_HOUR
        self.shaft_power_w = power_in
        self.hydraulic_efficiency = hydraulic_efficiency(hydraulic_power(flow, head), power_in)
        self.pressure_rise_pa = raw.outlet_total_pressure_pa - raw.inlet_total_pressure_pa
        self.inlet_total_pressure_pa = raw.inlet_total_pressure_pa
        self.outlet_total_pressure_pa = raw.outlet_total_pressure_pa
        self.blade_pressure_pa = raw.blade_pressure_pa
        self.blade_torque_nm = raw.blade_torque_nm
        self.converged = is_converged(raw.head_samples)
        self.convergence_history = build_convergence_history(raw.head_samples, raw.outlet_pressure_samples)
        self.contour_image = self.storage_scope.store(raw.contour_image_path)
        self.solved_case_file = self.storage_scope.store(raw.solved_case_path)
        # Must be stored too: the BDM sweep deletes every unreferenced file in the storage root.
        self.solved_data_file = self.storage_scope.store(raw.solved_data_path)
        # The scene shows the previous run; it is out of date until prepare_solved_scene runs again.
        self.solved_scene_file = NO_ENTITY

    def _report_progress(self, stage: str, fraction: float) -> None:
        """Persist the current stage and publish it to the UI event stream.

        GLOW has no built-in progress concept. Fields only reach the project at transaction
        boundaries unless ``transaction.upload`` is called explicitly, so both the persisted
        fields and the event stream are updated here.
        """
        self.progress_stage = stage
        self.progress_fraction = fraction
        # The log is persisted at stage boundaries rather than on every batch: that keeps the
        # number of writes bounded while still letting a reload show what has happened so far.
        self.log_text = "\n".join(self._log_lines)
        self.transaction.upload(["progress_stage", "progress_fraction", "log_text"])
        self.transaction.raise_event(
            {"stage": stage, "fraction": fraction}, stream_name=RUN_SIMULATION_PROGRESS_STREAM
        )

    def _report_log(self, lines: list[str]) -> None:
        """Publish a batch of Fluent console lines to the UI event stream."""
        self._log_lines = (self._log_lines + lines)[-LOG_TAIL_LINES:]
        self.transaction.raise_event({"lines": lines}, stream_name=RUN_SIMULATION_LOG_STREAM)

    def _report_history(
        self, head_samples: list[tuple[int, float]], outlet_pressure_samples: list[tuple[int, float]]
    ) -> None:
        """Persist and publish the convergence curve read back mid-solve.

        The field is uploaded as well as raised so that a browser that joins late, or
        reloads the page, still sees the part of the curve that has already been computed.

        Parameters
        ----------
        head_samples : list[tuple[int, float]]
            ``(iteration, head)`` samples written so far.
        outlet_pressure_samples : list[tuple[int, float]]
            ``(iteration, outlet total pressure)`` samples written so far.
        """
        history = build_convergence_history(head_samples, outlet_pressure_samples)
        if not history:
            return
        self.convergence_history = history
        self.transaction.upload(["convergence_history"])
        self.transaction.raise_event({"history": history}, stream_name=RUN_SIMULATION_HISTORY_STREAM)
