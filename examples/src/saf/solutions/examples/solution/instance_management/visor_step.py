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

"""Visor step for the instance management examples."""

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.visor import VisorManager


class VisorStep(StepModel):
    """Step to manage a Visor instance."""

    version: str = "0"
    visor_started: bool = False
    visor_updated: bool = False
    visor_port: int | None = None
    volume_vtp: EntityHandle = NO_ENTITY
    metadata_json: EntityHandle = NO_ENTITY

    @transaction(
        self=StepSpec(
            download=["version", "volume_vtp", "metadata_json"],
            upload=["visor_started", "visor_port"],
        ),
    )
    @create_instance("visor_manager", VisorManager)
    @long_running
    def start_visor(self, visor_manager: VisorManager) -> None:
        """Start the Visor instance with the configured input files."""
        self.transaction.raise_event(message="Initializing VISOR instance.", stream_name="visor-output-stream")
        try:
            visor_manager.initialize(
                version=self.version,
                input_file=self.volume_vtp,
                metadata_file=self.metadata_json,
            )
            self.visor_port = visor_manager.instance.port
            self.visor_started = True
        except Exception as e:
            self.transaction.raise_event(
                message=f"VISOR initialization failed: {e}",
                stream_name="visor-output-stream",
            )
            raise
        self.transaction.raise_event(message="VISOR initialized.", stream_name="visor-output-stream")

    @transaction(self=StepSpec(upload=["visor_port"]))
    @instance("visor_manager")
    @long_running
    def refresh_visor(self, visor_manager: VisorManager) -> None:
        """Refresh the port exposed by the Visor instance."""
        self.visor_port = visor_manager.instance.port

    @transaction(self=StepSpec(download=["volume_vtp"], upload=["visor_updated"]))
    @instance("visor_manager")
    def update_visor(self, visor_manager: VisorManager) -> None:
        """Update the Visor instance with the stored volume."""
        from ansys.visor.viewer import Metadata  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]

        if self.volume_vtp == NO_ENTITY:
            raise ValueError("A volume VTP file must be provided before updating Visor.")

        visor_manager.instance.update(
            file_path=visor_manager.storage_scope.get_cached(self.volume_vtp).as_posix(),
            metadata=Metadata(name="UPDATED_NAME", unit="m"),
        )
        self.visor_updated = True

    @transaction(self=StepSpec(upload=["visor_updated", "visor_started"]))
    @instance("visor_manager")
    def close_visor(self, visor_manager: VisorManager) -> None:
        """Close the Visor instance."""

        self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="visor-output-stream")
        try:
            visor_manager.shutdown()
            self.visor_updated = False
            self.visor_started = False
        except Exception as e:
            self.transaction.raise_event(message=f"VISOR shutdown failed: {e}", stream_name="visor-output-stream")
            raise
        self.transaction.raise_event(
            message="VISOR instance shutdown complete.",
            stream_name="visor-output-stream",
        )
