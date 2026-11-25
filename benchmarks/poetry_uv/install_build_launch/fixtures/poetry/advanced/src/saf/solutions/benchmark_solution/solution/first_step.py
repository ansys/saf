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

"""Backend of the first step."""


from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, transaction


class FirstStep(StepModel):
    """Step definition of the first step."""

    first_arg: float = 0
    second_arg: float = 0
    result: float = 0

    result_file: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(upload=["result"], download=["first_arg", "second_arg"]))
    def calculate(self) -> None:
        """Compute the sum of two numbers."""
        self.result = self.first_arg + self.second_arg

    @transaction(self=StepSpec(upload=["result_file"], download=["result"]))
    def save_result(self) -> None:
        """Save the result to result file."""
        self.result_file = self.storage_scope.store_stream(str(self.result).encode("utf-8"))

    @transaction(self=StepSpec(download=["result_file"]))
    def load_result(self) -> float | None:
        """Load the result from result file."""
        if self.result_file == NO_ENTITY:
            return None
        result = self.storage_scope.get_text(self.result_file)
        return float(result)
