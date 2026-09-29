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

from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    transaction,
)
from tests.mocks.solutions.minimal_complete_solution.solution.custom_product_manager import CustomProductManager


class CustomSharedInstanceStep(StepModel):
    value: str = "blue"

    @transaction(self=StepSpec())
    @create_instance("custom_product_instance", CustomProductManager)
    def initialize_custom_product(self, custom_product_instance: CustomProductManager) -> None:
        custom_product_instance.initialize(version="1")

    @transaction(self=StepSpec(upload=["value"]))
    @instance("custom_product_instance")
    def retrieve_value_from_custom_product(self, custom_product_instance: CustomProductManager) -> None:
        self.value = custom_product_instance.instance.the_property

    @transaction(self=StepSpec(download=["value"]))
    @instance("custom_product_instance")
    def set_value_on_custom_product(self, custom_product_instance: CustomProductManager, new_value: str) -> None:
        custom_product_instance.instance.the_property = new_value

    @transaction(self=StepSpec())
    @instance("custom_product_instance")
    def shutdown_custom_product(self, custom_product_instance: CustomProductManager) -> None:
        custom_product_instance.shutdown()

    @transaction(self=StepSpec(upload=["value"]))
    def use_unshared_custom_product(self, new_value: str) -> None:
        with CustomProductManager(version="1") as custom_product_instance:
            custom_product_instance.instance.the_property = new_value
            self.value = custom_product_instance.instance.the_property
