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

# ©2023, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Solution definition module."""

from ansys.saf.glow.solution import Solution, StepsModel

from saf.solutions.examples.solution.basic_step import BasicStep
from saf.solutions.examples.solution.beam_bending_report_step import BeamBendingReportStep
from saf.solutions.examples.solution.beam_bending_step import BeamBendingStep
from saf.solutions.examples.solution.file_handling_step import FileHandlingStep
from saf.solutions.examples.solution.game_of_life_step import GameOfLifeStep
from saf.solutions.examples.solution.hps_job_submission_step import HpsJobSubmissionStep
from saf.solutions.examples.solution.instance_management.aedt_step import Maxwell2DSetupVerificationStep
from saf.solutions.examples.solution.instance_management.fluent_step import FluentStep
from saf.solutions.examples.solution.instance_management.geometry_step import GeometryStep
from saf.solutions.examples.solution.instance_management.mapdl_step import MapdlStep
from saf.solutions.examples.solution.instance_management.mechanical_step import MechanicalStep
from saf.solutions.examples.solution.instance_management.optislang_step import OptislangStep
from saf.solutions.examples.solution.instance_management.visor_step import VisorStep
from saf.solutions.examples.solution.long_transaction_step import LongTransactionStep


class Steps(StepsModel):
    """Workflow definition."""

    basic_step: BasicStep
    aedt_step: Maxwell2DSetupVerificationStep
    fluent_step: FluentStep
    optislang_step: OptislangStep
    mechanical_step: MechanicalStep
    geometry_step: GeometryStep
    mapdl_step: MapdlStep
    visor_step: VisorStep
    long_transaction_step: LongTransactionStep
    file_handling_step: FileHandlingStep
    hps_job_submission_step: HpsJobSubmissionStep
    beam_bending_step: BeamBendingStep
    beam_bending_report_step: BeamBendingReportStep
    game_of_life_step: GameOfLifeStep


class ExamplesSolution(Solution):
    """Solution definition."""

    display_name: str = "Solution Examples"
    version: int = 1
    steps: Steps
