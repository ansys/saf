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
from tests.mocks.solutions.minimal_complete_solution.solution.first_step import FirstStep
from tests.mocks.solutions.minimal_complete_solution.solution.instance_manager_step import CustomSharedInstanceStep


class Steps(StepsModel):
    first_step: FirstStep
    instance_manager_step: CustomSharedInstanceStep


class MySolution(Solution):
    display_name: str = "My Solution"
    version: int = 1
    steps: Steps
