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

"""Backend of the {{ cookiecutter.__step_name }} step."""


from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.geometry import GeometryManager
from pydantic import Field


class {{ cookiecutter.__step_definition_class_name }}(StepModel):
    """Step definition of the {{ cookiecutter.__step_name }} step."""

    version: str = "261"
    geometry_available: bool = False
    logs: list[str] = Field(default_factory=list)

    @transaction(
        self=StepSpec(download=["version"], upload=["geometry_available"]),
        enable_termination_event=True,
    )
    @create_instance("geometry_manager", GeometryManager)
    @long_running
    def launch_geometry(self, geometry_manager: GeometryManager) -> None:
        self.transaction.raise_event(message="Initializing Geometry instance.", stream_name="{{ cookiecutter.__step_name_hyphenated }}-output-stream")
        try:
            geometry_manager.initialize(version=self.version)
            self.geometry_available = True
        except Exception as e:
            self.transaction.raise_event(message=f"Failed to initialize Geometry instance: {e}", stream_name="{{ cookiecutter.__step_name_hyphenated }}-output-stream")
            raise
        self.transaction.raise_event(message="Geometry instance initialized.", stream_name="{{ cookiecutter.__step_name_hyphenated }}-output-stream")

    @transaction(self=StepSpec())
    @instance("geometry_manager")
    @long_running
    def use_geometry(self, geometry_manager: GeometryManager) -> None:
        # Add actual usage of the Geometry instance here:
        # geometry = geometry_manager.instance
        ...

    @transaction(self=StepSpec(upload=["geometry_available"]), enable_termination_event=True)
    @instance("geometry_manager")
    @long_running
    def shutdown_geometry(self, geometry_manager: GeometryManager) -> None:
        self.transaction.raise_event(message="Shutting Geometry instance down.", stream_name="{{ cookiecutter.__step_name_hyphenated }}-output-stream")
        try:
            geometry_manager.shutdown()
            self.geometry_available = False
        except Exception as e:
            self.transaction.raise_event(message=f"Failed to shut down Geometry instance: {e}", stream_name="{{ cookiecutter.__step_name_hyphenated }}-output-stream")
            raise
        self.transaction.raise_event(message="Geometry instance shut down.", stream_name="{{ cookiecutter.__step_name_hyphenated }}-output-stream")
