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

from ansys.bdm.api import NO_ENTITY, EntityHandle  # type: ignore
from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.visor import VisorManager

logger = logging.getLogger(__name__)


class VisorInstanceStep(StepModel):
    version: str = "0"
    visor_available: bool = False
    visor_started: bool = False
    visor_updated: bool = False
    visor_port: int | None = None
    volume_vtp: EntityHandle = NO_ENTITY
    metadata_json: EntityHandle = NO_ENTITY

    @transaction(
        self=StepSpec(
            download=["version"],
            upload=["visor_started", "visor_port", "volume_vtp", "metadata_json"],
        ),
    )
    @create_instance("visor_manager", VisorManager)
    @long_running
    def start_visor(self, visor_manager: VisorManager) -> None:
        root_path = self.storage_scope.get_storage_root()
        volume_asset = self.transaction.get_asset_entity_handle("volume.vtp")
        volume_path = root_path / "volume.vtp"
        # TODO: for now copying assets
        self.storage_scope.get_copy(volume_asset, volume_path)
        self.volume_vtp = self.storage_scope.store(volume_path)
        metadata_path = root_path / "metadata.json"
        metadata_asset = self.transaction.get_asset_entity_handle("metadata.json")
        # TODO: for now copying assets
        self.storage_scope.get_copy(metadata_asset, metadata_path)
        self.metadata_json = self.storage_scope.store(metadata_path)
        visor_manager.initialize(
            version=self.version,
            input_file=self.volume_vtp,
            metadata_file=self.metadata_json,
        )
        self.visor_port = visor_manager.instance.port
        self.visor_started = True

    @transaction(self=StepSpec(download=[], upload=["visor_port"]))
    @instance("visor_manager")
    @long_running
    def refresh_visor(self, visor_manager: VisorManager) -> None:
        self.visor_port = visor_manager.instance.port

    @transaction(self=StepSpec(download=["volume_vtp"], upload=["visor_updated"]))
    @instance("visor_manager")
    def update_visor(self, visor_manager: VisorManager) -> None:
        from ansys.visor.viewer import Metadata  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]

        visor_manager.instance.update(
            file_path=visor_manager.storage_scope.get_cached(self.volume_vtp).as_posix(),
            metadata=Metadata(name="UPDATED_NAME", unit="m"),
        )
        self.visor_updated = True

    @transaction(self=StepSpec(upload=["visor_updated", "visor_started"]))
    @instance("visor_manager")
    def close_visor(self, visor_manager: VisorManager) -> None:
        visor_manager.shutdown()
        self.visor_updated = False
        self.visor_started = False
