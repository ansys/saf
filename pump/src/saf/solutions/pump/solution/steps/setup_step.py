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
)

from saf.solutions.pump.solution.logic.case_builder import build_case
from saf.solutions.pump.solution.logic.constants import (
    BUILD_CASE_LOG_STREAM,
    BUILD_CASE_PROGRESS_STREAM,
    DEFAULT_PROCESSOR_COUNT,
    LOG_TAIL_LINES,
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
        """Convert the built case into a VTKHDF scene."""
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
