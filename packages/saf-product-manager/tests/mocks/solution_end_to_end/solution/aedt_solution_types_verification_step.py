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

from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
from ansys.saf.product_manager.aedt import HfssManager, IcepakManager
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION


class AedtSolutionTypesVerificationStep(StepModel):
    aedt_version: str = LATEST_VERSION
    target_solution_type: str | None = None
    retrieved_solution_type: str | None = None

    @transaction(self=StepSpec(download=["aedt_version", "target_solution_type"], upload=["retrieved_solution_type"]))
    @create_instance("hfss_instance", HfssManager)
    @long_running
    def initialize_hfss_instance_with_solution_type(self, hfss_instance: HfssManager) -> None:
        hfss_instance.initialize(version=self.aedt_version, solution_type=self.target_solution_type)
        self.retrieved_solution_type = hfss_instance.instance.solution_type  # pyright: ignore[reportUnknownMemberType]

    @transaction(self=StepSpec(download=["aedt_version", "target_solution_type"], upload=["retrieved_solution_type"]))
    @create_instance("icepak_instance", IcepakManager)
    @long_running
    def initialize_icepak_instance_with_solution_type(self, icepak_instance: IcepakManager) -> None:
        icepak_instance.initialize(version=self.aedt_version, solution_type=self.target_solution_type)
        self.retrieved_solution_type = icepak_instance.instance.solution_type  # pyright: ignore[reportUnknownMemberType]

    @transaction(self=StepSpec(upload=["aedt_version"]))
    @instance("icepak_instance")
    @long_running
    def upload_icepak_aedt_version_from_aedt(self, icepak_instance: IcepakManager) -> None:
        self.aedt_version = icepak_instance.instance.aedt_version_id  # type: ignore

    @transaction(self=StepSpec(upload=["aedt_version"]))
    @instance("hfss_instance")
    @long_running
    def upload_hfss_aedt_version_from_aedt(self, hfss_instance: HfssManager) -> None:
        self.aedt_version = hfss_instance.instance.aedt_version_id  # type: ignore

    @transaction(self=StepSpec())
    @instance("hfss_instance")
    def exit_hfss_instance(self, hfss_instance: HfssManager) -> None:
        hfss_instance.shutdown()

    @transaction(self=StepSpec())
    @instance("icepak_instance")
    def exit_icepak_instance(self, icepak_instance: IcepakManager) -> None:
        icepak_instance.shutdown()
