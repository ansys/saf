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

"""Backend of the service launch step."""

import logging

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
from ansys.saf.product_manager.geometry import GeometryManager
from ansys.saf.product_manager.visor import VisorManager
from ansys.visor.viewer import Metadata

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(asctime)s | %(levelname)s] %(message)s", level=logging.INFO)


class ServiceLaunchStep(StepModel):
    """Service launch step for initializing geometry and visualization services."""

    version: str = "261"
    visor_host: str = "localhost"
    visor_port: int = 8081

    @transaction(self=StepSpec(download=["version"]))
    @create_instance("geometry_secure_manager", GeometryManager)
    @long_running
    def launch_geom_service(self, geometry_secure_manager: GeometryManager) -> None:
        """Launch and initialize the geometry service."""
        geometry_secure_manager.initialize(version=self.version)

    @transaction(
        self=StepSpec(upload=["visor_host", "visor_port"], download=[]),
        enable_termination_event=True,
    )
    @create_instance("visor", VisorManager)
    @long_running
    def launch_visor(self, visor: VisorManager) -> None:
        """Launch and initialize the Visor visualization service."""
        logging.info("\n\nLaunching Visor...\n\n")
        visor.initialize()
        if visor.instance:
            self.visor_host = visor.instance.host
            self.visor_port = visor.instance.port
        logging.info("\n\nLaunched Visor...\n\n")

    @transaction(self=StepSpec(upload=["visor_host", "visor_port"]), enable_termination_event=True)
    @instance("visor")
    def restart_visor(self, visor: VisorManager) -> None:
        """Fetch  Visor host and port from the restarted Visor instance."""
        self.visor_host = visor.instance.host
        self.visor_port = visor.instance.port

    @transaction()
    @instance("visor")
    def update_visor(
        self,
        visor: VisorManager,
        vtp_handle: EntityHandle = NO_ENTITY,
        model_name: str = "model",
    ) -> None:
        """Update the Visor instance with model metadata and file path."""
        if vtp_handle == NO_ENTITY:
            return

        vtp_path = visor.storage_scope.get_cached(vtp_handle)
        visor.instance.update(
            file_path=str(vtp_path),
            metadata=Metadata(name=model_name, unit="mm"),
        )
