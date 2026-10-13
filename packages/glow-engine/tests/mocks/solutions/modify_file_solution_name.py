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


class FirstStep(StepModel):
    x: int = 88
    always_no_entity_handle: EntityHandle = NO_ENTITY
    existing_entity_handle: EntityHandle = NO_ENTITY

    @transaction(
        self=StepSpec(upload=["existing_entity_handle"]),
    )
    def initialize(self) -> None:
        with self.storage_scope as storage_scope:
            file = storage_scope.get_storage_root() / "file.txt"
            file.write_text("new file content")
            self.existing_entity_handle = storage_scope.store(file)


class Steps(StepsModel):
    first_step: FirstStep


class NotOriginalSolution(Solution):
    display_name: str = "Not Original"
    steps: Steps
