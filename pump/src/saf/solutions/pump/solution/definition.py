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

"""Solution definition module."""


from ansys.saf.glow.solution import Migration, MigrationContext, MigrationTransformation, Solution, StepsModel

from saf.solutions.pump.solution.steps.setup_step import SetupStep
from saf.solutions.pump.solution.steps.solve_step import SolveStep


class Steps(StepsModel):
    """Workflow definition."""

    setup_step: SetupStep
    solve_step: SolveStep


class DropRemovedFields(MigrationTransformation):
    """Drop the fields of the removed Visor viewer and ADR report, which steps now reject.

    Version 1 projects hold the Visor fields; version 2 projects also hold the report step.
    """

    def migrate(self, ctx: MigrationContext) -> None:
        """Remove the obsolete fields when present."""
        ctx.steps.pop("report_step", None)
        setup_step = ctx.steps.get("setup_step", {})
        for field in ("visor_version", "visor_started", "visor_host", "visor_port"):
            setup_step.pop(field, None)


class PumpSolution(Solution):
    """Solution definition."""

    display_name: str = "Pump"
    version: int = 3
    migrations: list[Migration] = [
        Migration(version=1, migration_transformation=DropRemovedFields()),
        Migration(version=2, migration_transformation=DropRemovedFields()),
    ]
    steps: Steps
