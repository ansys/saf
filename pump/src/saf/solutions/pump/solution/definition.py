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

from saf.solutions.pump.solution.steps.report_step import ReportStep
from saf.solutions.pump.solution.steps.setup_step import SetupStep
from saf.solutions.pump.solution.steps.solve_step import SolveStep


class Steps(StepsModel):
    """Workflow definition."""

    setup_step: SetupStep
    solve_step: SolveStep
    report_step: ReportStep


class AddReportStep(MigrationTransformation):
    """Version 1 to 2: projects created before the report existed get an empty report step."""

    def migrate(self, ctx: MigrationContext) -> None:
        """Add the report step with its default values."""
        ctx.steps.setdefault("report_step", ReportStep().model_dump(mode="json"))


class PumpSolution(Solution):
    """Solution definition."""

    display_name: str = "Pump"
    version: int = 2
    migrations: list[Migration] = [Migration(version=1, migration_transformation=AddReportStep())]
    steps: Steps
