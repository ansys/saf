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

"""Backend of the model setup step."""

import logging
from pathlib import Path

from ansys.saf.glow.solution import (
    NO_ENTITY,
    BadRequestError,
    EntityHandle,
    StepModel,
    StepSpec,
    long_running,
    transaction,
    create_instance,
    instance,
)
from ansys.saf.product_manager.visor import VisorManager
from ansys.visor.viewer import Metadata

from saf.solutions.pump.solution.logic.case_builder import build_case
from saf.solutions.pump.solution.logic.constants import (
    BUILD_CASE_LOG_STREAM,
    BUILD_CASE_PROGRESS_STREAM,
    DEFAULT_PROCESSOR_COUNT,
    LOG_TAIL_LINES,
    SCENE_NAME,
    SCENE_UNIT,
)
from saf.solutions.pump.solution.logic.scene_export import export_scene

logger = logging.getLogger(__name__)


class SetupStep(StepModel):
    """Builds the operating-point-independent Fluent case."""

    processor_count: int = DEFAULT_PROCESSOR_COUNT

    progress_stage: str = ""
    progress_fraction: float = 0.0
    log_text: str = ""

    case_file: EntityHandle = NO_ENTITY
    data_file: EntityHandle = NO_ENTITY
    mesh_image: EntityHandle = NO_ENTITY
    zone_names: list[str] = []
    scene_file: EntityHandle = NO_ENTITY

    visor_version: str = "0"
    visor_started: bool = False
    visor_host: str = ""
    visor_port: int | None = None

    @long_running
    @transaction(
        enable_termination_event=True,
        self=StepSpec(
            upload=[
                "case_file",
                "data_file",
                "mesh_image",
                "zone_names",
                "scene_file",
                "progress_stage",
                "progress_fraction",
                "log_text",
            ],
            download=["processor_count"],
        ),
    )
    def build_case(self) -> None:
        """Read the meshes, configure the model and persist the case file."""
        # Fluent must write into the method storage root: storage_scope.store rejects any path
        # outside it. The root is already private to this method execution, so it needs no further
        # isolation and is cleaned up with the method.
        work_dir = Path(self.storage_scope.get_storage_root())
        self.log_text = ""
        self._log_lines: list[str] = []
        try:
            artifacts = build_case(work_dir, self.processor_count, self._report_progress, self._report_log)
        except ValueError as error:
            # GLOW replaces an uncaught exception with a generic 500 that hides the message.
            # BadRequestError is relayed to the client verbatim, so the validation text reaches the user.
            raise BadRequestError(str(error)) from error

        self.case_file = self.storage_scope.store(artifacts.case_path)
        # Must be stored too: the BDM sweep deletes every unreferenced file in the storage root.
        self.data_file = self.storage_scope.store(artifacts.data_path)
        self.mesh_image = self.storage_scope.store(artifacts.mesh_image_path)
        self.zone_names = artifacts.zone_names
        # The scene shows the previous case; it is out of date until prepare_scene runs again.
        self.scene_file = NO_ENTITY

    @long_running
    @transaction(
        enable_termination_event=True,
        self=StepSpec(download=["case_file", "data_file"], upload=["scene_file"]),
    )
    def prepare_scene(self) -> None:
        """Convert the built case into a VTKHDF scene for the 3D viewer."""
        if self.case_file == NO_ENTITY or self.data_file == NO_ENTITY:
            raise BadRequestError("Build the case before preparing the 3D view.")
        work_dir = Path(self.storage_scope.get_storage_root())
        try:
            scene_path = export_scene(
                Path(self.storage_scope.get_cached(self.case_file)),
                Path(self.storage_scope.get_cached(self.data_file)),
                work_dir,
            )
        except RuntimeError as error:
            raise BadRequestError(str(error)) from error
        self.scene_file = self.storage_scope.store(scene_path)

    @transaction(self=StepSpec(download=["scene_file"]))
    @instance("visor_manager")
    def show_scene(self, visor_manager: VisorManager) -> None:
        """Load the converted case into the running Visor instance."""
        if self.scene_file == NO_ENTITY:
            raise BadRequestError("The 3D view has not been prepared yet.")
        path = Path(self.storage_scope.get_cached(self.scene_file))
        visor_manager.instance.update(path.as_posix(), Metadata(name=SCENE_NAME, unit=SCENE_UNIT))

    @transaction(
        self=StepSpec(download=["visor_version"], upload=["visor_started", "visor_host", "visor_port"]),
        enable_termination_event=True,
    )
    @create_instance("visor_manager", VisorManager)
    @long_running
    def start_visor(self, visor_manager: VisorManager) -> None:
        """Start the Visor instance."""
        self.transaction.raise_event(message="Initializing VISOR instance.", stream_name="visor-output-stream")
        try:
            visor_manager.initialize()
            self.visor_host = visor_manager.instance.host
            self.visor_port = visor_manager.instance.port
            self.visor_started = True
        except Exception as e:
            self.transaction.raise_event(
                message=f"VISOR initialization failed: {e}",
                stream_name="visor-output-stream",
            )
            raise
        self.transaction.raise_event(message="VISOR initialized.", stream_name="visor-output-stream")

    @transaction(self=StepSpec())
    @instance("visor_manager")
    def update_scene(self, visor_manager: VisorManager) -> None:
        """Display the elbow in the running Visor instance."""
        self.transaction.raise_event(message="Loading elbow in VISOR.", stream_name="visor-output-stream")
        try:
            path = Path(__file__).parent.parent / "method_assets" / "visor_shapes" / "elbow.vtm"
            visor_manager.instance.update(path.as_posix(), Metadata(name="Elbow", unit="m"))
        except Exception as e:
            self.transaction.raise_event(message=f"VISOR elbow update failed: {e}", stream_name="visor-output-stream")
            raise
        self.transaction.raise_event(message="Elbow displayed in VISOR.", stream_name="visor-output-stream")

    @transaction(self=StepSpec(upload=["visor_started"]))
    @instance("visor_manager")
    def shutdown_visor(self, visor_manager: VisorManager) -> None:
        """Close the Visor instance."""

        self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="visor-output-stream")
        try:
            visor_manager.shutdown()
            self.visor_started = False
        except Exception as e:
            self.transaction.raise_event(message=f"VISOR shutdown failed: {e}", stream_name="visor-output-stream")
            raise
        self.transaction.raise_event(
            message="VISOR instance shutdown complete.",
            stream_name="visor-output-stream",
        )

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
            {"stage": stage, "fraction": fraction}, stream_name=BUILD_CASE_PROGRESS_STREAM
        )

    def _report_log(self, lines: list[str]) -> None:
        """Publish a batch of Fluent console lines to the UI event stream."""
        self._log_lines = (self._log_lines + lines)[-LOG_TAIL_LINES:]
        self.transaction.raise_event({"lines": lines}, stream_name=BUILD_CASE_LOG_STREAM)
