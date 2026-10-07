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

from pathlib import Path

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    Solution,
    StepModel,
    StepsModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from tests.mocks.instance_managers.mock_product_manager import MockGrpcProductDummyClientInstanceManager


class InstancesMockedStep(StepModel):
    transfer_entity_handle: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec())
    @create_instance("x_y", MockGrpcProductDummyClientInstanceManager)
    @long_running
    def create(self, x_y: MockGrpcProductDummyClientInstanceManager) -> None:
        x_y.initialize()

    @transaction(self=StepSpec())
    @instance("x_y")
    def use_instance_client(self, x_y: MockGrpcProductDummyClientInstanceManager) -> str:
        return x_y.instance.the_property

    @transaction(self=StepSpec())
    @instance("x_y")
    def fetch_server_version(self, x_y: MockGrpcProductDummyClientInstanceManager) -> str:
        return x_y.instance.server_version

    @transaction(self=StepSpec())
    @instance("x_y")
    def get_pim_name(self, x_y: MockGrpcProductDummyClientInstanceManager) -> str:
        return x_y._instance_manager_impl._record.pim_name  # pyright: ignore[reportPrivateUsage]

    @transaction()
    @instance("x_y")
    def shutdown(self, x_y: MockGrpcProductDummyClientInstanceManager) -> None:
        x_y.shutdown()

    @transaction(self=StepSpec(upload=["transfer_entity_handle"]))
    @instance("x_y")
    def store_files_in_product_space(self, x_y: MockGrpcProductDummyClientInstanceManager) -> None:
        filepath_on_product = x_y.storage_scope.get_storage_root() / "my_file.txt"
        Path(filepath_on_product).write_text("some shared content")
        self.transfer_entity_handle = x_y.storage_scope.store(filepath_on_product)

    @transaction(self=StepSpec(upload=["transfer_entity_handle"]))
    def unshared_product_instance(self) -> str:
        with MockGrpcProductDummyClientInstanceManager(version="1") as mock_product:
            filepath_on_product = mock_product.storage_scope.get_storage_root() / "my_file.txt"
            Path(filepath_on_product).write_text("some unshared content")
            self.transfer_entity_handle = mock_product.storage_scope.store(filepath_on_product)
            return mock_product.instance.the_property


class Steps(StepsModel):
    instance_step: InstancesMockedStep


class InstancesMockedSolution(Solution):
    display_name: str = "instancesMocked"
    steps: Steps
