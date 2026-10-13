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

"""Solution definition module."""

from ansys.saf.glow.solution import Solution, StepModel, StepsModel, StepSpec, transaction


class FirstStep(StepModel):
    """Step definition of the first step."""

    first_arg: float = 0
    second_arg: float = 0
    result: float = 0

    @transaction(self=StepSpec(upload=["result"], download=["first_arg", "second_arg"]))
    def calculate(self) -> None:
        """Compute the sum of two numbers."""
        # It's important that this transaction uses the method assets for verifying the encryption feature.
        factor_handle = self.transaction.get_asset_entity_handle("factor.txt")
        factor_str = self.storage_scope.get_text(factor_handle)
        try:
            factor = float(factor_str)
        except ValueError as e:
            raise ValueError(f"Invalid value in factor file: {factor_str}") from e
        self.result = factor * (self.first_arg + self.second_arg)


class Steps(StepsModel):
    """Workflow definition."""

    first_step: FirstStep


class MySolutionDashProjectsDashboardSolution(Solution):
    """Solution definition."""

    display_name: str = "My Solution Dash Projects Dashboard"
    version: int = 1
    steps: Steps
