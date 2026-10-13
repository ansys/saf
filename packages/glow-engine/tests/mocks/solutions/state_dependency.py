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

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    Solution,
    StepModel,
    StepsModel,
    StepSpec,
    transaction,
)


class AStep(StepModel):
    """This is a step for testing purpose."""

    a1: int = 99
    a2: int = 1
    a3: str = "hello"
    a_file: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(download=["a1", "a2"], upload=["a3"]))
    def a_method(self) -> None:
        self.a3 = f"{self.a1}.{self.a2}"


class BStep(StepModel):
    b1: int = 88
    b2: int = 3
    b3: str = "b3"
    b4: str = "b4"

    @transaction(self=StepSpec(download=["b1", "b2"], upload=["b3"]), a_step=StepSpec(download=["a3"]))
    def b3_method(self, a_step: AStep) -> None:
        self.b3 = f"{a_step.a3}.{self.b2}.{self.b1}"

    @transaction(self=StepSpec(upload=["b4"]), a_step=StepSpec(download=["a3", "a_file"]))
    def b4_method(self, a_step: AStep) -> None:
        self.b4 = f"{a_step.a3}"


class CStep(StepModel):
    c1: str = "c1"
    c2: int = 2
    c_file_group: dict[str, EntityHandle] = {}

    @transaction(self=StepSpec(download=["c_file_group"], upload=["c1"]), b_step=StepSpec(download=["b4"]))
    def c1_method(self, b_step: BStep) -> None:
        self.c1 = f"{b_step.b4}"


class Steps(StepsModel):
    a_step: AStep
    b_step: BStep
    c_step: CStep


class StateDependencySolution(Solution):
    display_name: str = "State Dependency"
    steps: Steps
