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

from ansys.saf.glow.solution import StepModel, StepSpec, transaction
from ansys.saf.glow.solution.hps import NO_HPS_STUDY_PROJECT, HpsJobEvaluationStatus, HpsParametricStudyProject
from ansys.saf.product_configuration.interfaces import Software as GlowSoftware


class ParametricStudiesStep(StepModel):
    x: list[float] = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    y: list[float] = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    number_left: int = 0
    result: list[str] = []

    hps_project: HpsParametricStudyProject = NO_HPS_STUDY_PROJECT

    @transaction(
        self=StepSpec(
            upload=["hps_project"],
            download=[
                "x",
                "y",
            ],
        ),
    )
    def start_parametric_study(self, python_version: str) -> None:
        self.hps_project = HpsParametricStudyProject.start_hps_parametric_study(
            common_input_files={"script": self.transaction.get_asset_entity_handle("add_script.py")},
            input_parameter_values={"x": self.x, "y": self.y},
            output_parameters={"result": float},
            products=[GlowSoftware("Python", version=python_version)],
        )

    @transaction(
        self=StepSpec(upload=["result", "number_left"], download=["hps_project"]),
    )
    def query_parametric_study(self) -> None:
        """Query the parameter study and update results."""
        number_left = 0

        for index, status in enumerate(self.hps_project.get_status_of_design_points()):
            if status.evaluation_status == HpsJobEvaluationStatus.EVALUATED:
                result = str(self.hps_project.result[index])  # type: ignore
            elif status.evaluation_status in (
                HpsJobEvaluationStatus.FAILED,
                HpsJobEvaluationStatus.ABORTED,
                HpsJobEvaluationStatus.TIMEOUT,
            ):
                result = status.evaluation_status.name
            else:
                result = "None"
                number_left += 1
            self.result.append(result)

        self.number_left = number_left
        if self.number_left == 0:
            assert self.hps_project.finished

    @transaction(self=StepSpec(download=["hps_project"]))
    def fetch_result_values(self) -> list[str | float | None]:
        return self.hps_project.fetch_values_of_parameter("result")  # type: ignore
