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

from pathlib import Path
import tempfile

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow._core.migrations import Migration, MigrationContext, MigrationTransformation
from ansys.saf.glow.solution import (
    Solution,
    StepModel,
    StepsModel,
)


def _remove_old_fields(ctx: MigrationContext) -> None:
    del ctx.steps["first_step"]["always_no_entity_handle"]
    del ctx.steps["first_step"]["existing_entity_handle"]


class AddEntityHandle(MigrationTransformation):
    def migrate(self, ctx: MigrationContext) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_sub_dir = Path(temp_dir) / "subdir"
            temp_sub_dir.mkdir()
            temp_file = temp_sub_dir / "new_file.txt"
            temp_file.write_text("new file content")
            ctx.steps["first_step"]["directory_entity_handle"] = ctx.create_entity_handle(temp_sub_dir)
        _remove_old_fields(ctx)


class FirstStep(StepModel):
    x: int = 88
    directory_entity_handle: EntityHandle = NO_ENTITY


class Steps(StepsModel):
    first_step: FirstStep


class OriginalSolution(Solution):
    version: int = 2
    display_name: str = "Original for File Migration"
    steps: Steps
    migrations: list[Migration] = [Migration(version=1, migration_transformation=AddEntityHandle())]
