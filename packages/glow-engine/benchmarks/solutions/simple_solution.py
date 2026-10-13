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

from benchmarks.utils import randomword

from ansys.saf.glow.solution import (
    Solution,
    StepModel,
    StepsModel,
    StepSpec,
    transaction,
)


class PaddingStep0(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep1(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep2(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep3(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep4(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep5(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep6(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep7(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep8(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class PaddingStep9(StepModel):
    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0


class DataStep(StepModel):
    """A step for testing purpose."""

    background: str = "background"
    foreground: str = "foreground"

    field0: float = 0.0
    field1: float = 1.0
    field2: float = 2.0
    field3: float = 3.0
    field4: float = 4.0
    field5: float = 5.0
    field6: float = 6.0
    field7: float = 7.0
    field8: float = 8.0
    field9: float = 9.0

    @transaction(self=StepSpec(upload=["foreground"]))
    def upload_field(self, field_size: int) -> None:
        self.foreground = randomword(field_size)
        self.transaction.upload(["foreground"])


class Steps(StepsModel):
    data_step: DataStep
    padding_step0: PaddingStep0
    padding_step1: PaddingStep1
    padding_step2: PaddingStep2
    padding_step3: PaddingStep3
    padding_step4: PaddingStep4
    padding_step5: PaddingStep5
    padding_step6: PaddingStep6
    padding_step7: PaddingStep7
    padding_step8: PaddingStep8
    padding_step9: PaddingStep9


class BenchmarkSolution(Solution):
    display_name: str = "Benchmark Solution"
    steps: Steps
