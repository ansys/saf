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

from ansys.saf.glow.solution import Solution, StepsModel
from tests.mocks.solution_end_to_end.solution.aedt_solution_types_verification_step import (
    AedtSolutionTypesVerificationStep,
)
from tests.mocks.solution_end_to_end.solution.design_name_verification_step import (
    DesignNameVerificationStep,
)
from tests.mocks.solution_end_to_end.solution.fluent_custom_step import FluentCustomStep
from tests.mocks.solution_end_to_end.solution.fluent_instance_step import FluentInstanceStep
from tests.mocks.solution_end_to_end.solution.geometry_instance_step import GeometryInstanceStep
from tests.mocks.solution_end_to_end.solution.mapdl_step import MapdlStep
from tests.mocks.solution_end_to_end.solution.maxwell_2d_setup_verification_step import (
    Maxwell2DSetupVerificationStep,
)
from tests.mocks.solution_end_to_end.solution.maxwell_3d_setup_verification_step import (
    Maxwell3DSetupVerificationStep,
)
from tests.mocks.solution_end_to_end.solution.mechanical_instance_step import MechanicalInstanceStep
from tests.mocks.solution_end_to_end.solution.optislang_wrapper_step import OptislangWrapperStep
from tests.mocks.solution_end_to_end.solution.visor_instance_step import (
    VisorInstanceStep,
)


class Steps(StepsModel):
    fluent_custom_step: FluentCustomStep
    optislang_wrapper_step: OptislangWrapperStep
    mapdl_step: MapdlStep
    maxwell_2d_verification_step: Maxwell2DSetupVerificationStep
    maxwell_3d_verification_step: Maxwell3DSetupVerificationStep
    design_name_verification_step: DesignNameVerificationStep
    aedt_solution_types_verification_step: AedtSolutionTypesVerificationStep
    mechanical_instance_step: MechanicalInstanceStep
    fluent_instance_step: FluentInstanceStep
    geometry_instance_step: GeometryInstanceStep
    visor_instance_step: VisorInstanceStep


class EndToEndSolution(Solution):
    display_name: str = "End-to-end solution"
    steps: Steps
