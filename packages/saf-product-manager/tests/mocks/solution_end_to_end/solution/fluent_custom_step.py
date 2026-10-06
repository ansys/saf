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

from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, transaction
from tests.mocks.solution_end_to_end.solution.custom_fluent_manager import CustomFluent2DDPSolverManager


class FluentCustomStep(StepModel):
    version: str = "252"

    @transaction(self=StepSpec(download=["version"]))
    @create_instance("fluent_manager", CustomFluent2DDPSolverManager)
    def launch_instance(self, fluent_manager: CustomFluent2DDPSolverManager) -> None:
        fluent_manager.initialize(version=self.version)
