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

import os

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
from tests.mocks.instance_managers.mock_product_manager import (
    MockGrpcProductInstanceManager,
    MockHttpNoSaveProductInstanceManager,
    MockHttpProductInstanceManager,
    MockTcpProductInstanceManager,
)


class InstanceStep(StepModel):
    color: str = ""
    is_blue: bool = False
    transfer_entity_handle: EntityHandle = NO_ENTITY
    pim_name: str = ""
    instance_healthy: bool = False
    was_instance_shutdown: bool = False
    http_pid: int = -1
    mock_result: str = ""
    project: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(upload=["color"]))
    @instance("x_y")
    def fetch_the_property(self, x_y: MockGrpcProductInstanceManager) -> None:
        self.color = x_y.instance.the_property

    @transaction(self=StepSpec(upload=["color"]))
    @create_instance("x_y", MockGrpcProductInstanceManager)
    def create(self, x_y: MockGrpcProductInstanceManager) -> None:
        x_y.initialize()
        self.color = x_y.instance.the_property

    @transaction(self=StepSpec(upload=["color", "project"]))
    @create_instance("x_y", MockGrpcProductInstanceManager)
    def create_with_project(self, x_y: MockGrpcProductInstanceManager) -> None:
        root = self.storage_scope.get_storage_root()
        project_file = root / "project.txt"
        project_file.write_text("brown")
        self.project = self.storage_scope.store(project_file)
        x_y.initialize(project=self.project)
        self.color = x_y.instance.the_property

    @transaction()
    @instance("x_y")
    def shutdown(self, x_y: MockGrpcProductInstanceManager) -> None:
        x_y.shutdown()

    @transaction(self=StepSpec(upload=["color"]))
    @create_instance("tcp", MockTcpProductInstanceManager)
    def create_tcp(self, tcp: MockTcpProductInstanceManager) -> None:
        tcp.initialize()
        self.color = tcp.instance.the_property

    @transaction(self=StepSpec(upload=["is_blue"]))
    @instance("tcp")
    def set_is_blue_tcp(self, tcp: MockTcpProductInstanceManager) -> None:
        self.is_blue = tcp.instance.the_property == "blue"

    @transaction()
    @instance("tcp")
    def shutdown_tcp(self, tcp: MockTcpProductInstanceManager) -> None:
        tcp.shutdown()

    @transaction(self=StepSpec(upload=["is_blue"]))
    @instance("x_y")
    def set_is_blue(self, x_y: MockGrpcProductInstanceManager) -> None:
        self.is_blue = x_y.instance.the_property == "blue"

    @transaction(self=StepSpec(upload=["color"]))
    @create_instance("x_y", MockGrpcProductInstanceManager)
    def create_no_type(self, x_y: MockGrpcProductInstanceManager) -> None:
        x_y.initialize()
        self.color = x_y.instance.the_property

    @transaction(self=StepSpec(upload=["pim_name"]))
    @instance("x_y")
    def get_pim_name(self, x_y: MockGrpcProductInstanceManager) -> None:
        self.pim_name = x_y._instance_manager_impl._record.pim_name  # pyright: ignore[reportPrivateUsage]

    @transaction(self=StepSpec(upload=["color"]))
    @long_running
    @create_instance("x_y", MockGrpcProductInstanceManager)
    def long_running_before_create_instance(self, x_y: MockGrpcProductInstanceManager) -> None:
        x_y.initialize()
        self.color = x_y.instance.the_property

    @transaction(self=StepSpec(upload=["color"]))
    @long_running
    @instance("x_y")
    def long_running_before_instance(self, x_y: MockGrpcProductInstanceManager) -> None:
        self.color = "yellow"

    @transaction(self=StepSpec(upload=["is_blue"]))
    @instance("x_y")
    def set_is_blue_no_type(self, x_y: MockGrpcProductInstanceManager) -> None:
        self.is_blue = x_y.instance.the_property == "blue"  # type: ignore

    @transaction()
    @instance("x_y")
    def set_instance_red(self, x_y: MockGrpcProductInstanceManager) -> None:
        x_y.instance.the_property = "red"

    @transaction(self=StepSpec(upload=["transfer_entity_handle"]))
    def store_red_in_entity_handle(self) -> None:
        transfer_file = self.storage_scope.get_storage_root() / "transfer.txt"
        transfer_file.write_text("red")
        self.transfer_entity_handle = self.storage_scope.store(transfer_file)

    @transaction(self=StepSpec(download=["transfer_entity_handle"]))
    @instance("x_y")
    def set_instance_from_entity_handle(self, x_y: MockGrpcProductInstanceManager) -> None:
        filepath_on_product = x_y.storage_scope.get_cached(self.transfer_entity_handle)
        x_y.instance.restore_given_absolute_path(str(filepath_on_product))

    @transaction(self=StepSpec(upload=["transfer_entity_handle"]))
    @instance("x_y")
    def get_instance_to_entity_handle(self, x_y: MockGrpcProductInstanceManager) -> None:
        filepath_on_product = x_y.storage_scope.get_storage_root() / "my_file.txt"
        x_y.instance.store_given_absolute_path(str(filepath_on_product))
        self.transfer_entity_handle = x_y.storage_scope.store(filepath_on_product)

    @transaction(self=StepSpec(download=["transfer_entity_handle"]))
    def set_is_blue_from_entity_handle(self) -> None:
        filepath = self.storage_scope.get_cached(self.transfer_entity_handle)
        self.is_blue = filepath.read_text() == "blue"

    @transaction()
    @instance("x_y")
    def check_pim_config_env_var_is_not_set(self, x_y: MockGrpcProductInstanceManager) -> None:
        if "ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG" in os.environ:
            raise RuntimeError(
                "test failed: ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG set in method "
                "(which will screwup attempts to use pyansys libraries)",
            )

    @transaction(self=StepSpec(upload=["color"]))
    def unshared_product_instance(self) -> None:
        with MockGrpcProductInstanceManager(version="1") as mock_product:
            self.color = mock_product.instance.the_property

    @transaction(self=StepSpec(upload=["mock_result", "color"]))
    def unshared_bdm_product_instance(self):
        state_file_on_transaction = self.storage_scope.get_storage_root() / "state.txt"
        state_file_on_transaction.write_text("red")
        self.transaction_handle = self.storage_scope.store(state_file_on_transaction)
        with MockGrpcProductInstanceManager() as grpc_manager:
            state_file_on_product = grpc_manager.storage_scope.get_cached(self.transaction_handle)
            grpc_manager.instance.restore_given_absolute_path(str(state_file_on_product))
            self.color = grpc_manager.instance.the_property
            product_handle = grpc_manager.storage_scope.store_stream(b"fake solve results")
        self.mock_result = self.storage_scope.get_text(product_handle)

    @transaction(self=StepSpec(upload=["color"]))
    @create_instance("http", MockHttpProductInstanceManager)
    def create_http(self, http: MockHttpProductInstanceManager) -> None:
        http.initialize()

    @transaction(self=StepSpec(upload=["instance_healthy"]))
    @instance("http")
    def check_instance_health(self, http: MockHttpProductInstanceManager) -> None:
        self.instance_healthy = http.is_instance_healthy()

    @transaction(self=StepSpec(upload=["was_instance_shutdown"]))
    @instance("http")
    def set_http_instance_red(self, http: MockHttpProductInstanceManager) -> None:
        http.instance.the_property = "red"
        self.was_instance_shutdown = (
            http._instance_manager_impl._was_instance_shutdown  # pyright: ignore[reportPrivateUsage]
        )

    @transaction(self=StepSpec(upload=["http_pid"]))
    @instance("http")
    def get_http_process_pid(self, http: MockHttpProductInstanceManager) -> None:
        self.http_pid = http.instance.pid

    @transaction(self=StepSpec(upload=["color"]))
    @instance("http")
    def get_http_instance_color_and_kill_instance(self, http: MockHttpProductInstanceManager) -> None:
        self.color = http.instance.the_property
        http.instance.harakiri()

    @transaction()
    @instance("http")
    def harakiri(self, http: MockHttpProductInstanceManager) -> None:
        http.instance.harakiri()

    @transaction(self=StepSpec(upload=["was_instance_shutdown", "color"]))
    @instance("http")
    def shutdown_http(self, http: MockHttpProductInstanceManager) -> None:
        self.color = http.instance.the_property
        http.shutdown()
        self.was_instance_shutdown = (
            http._instance_manager_impl._was_instance_shutdown  # pyright: ignore[reportPrivateUsage]
        )

    @transaction()
    @instance("http")
    def be_healthy_http(self, http: MockHttpProductInstanceManager) -> None:
        http.instance.be_healthy()

    @transaction()
    @instance("http")
    def be_unhealthy_http(self, http: MockHttpProductInstanceManager) -> None:
        http.instance.be_unhealthy()

    @transaction()
    @create_instance("http_no_save", MockHttpNoSaveProductInstanceManager)
    def create_http_no_save(self, http_no_save: MockHttpNoSaveProductInstanceManager) -> None:
        http_no_save.initialize()

    @transaction()
    @instance("http_no_save")
    def set_http_no_save_red(self, http_no_save: MockHttpNoSaveProductInstanceManager) -> None:
        http_no_save.instance.the_property = "red"

    @transaction(self=StepSpec(upload=["color"]))
    @instance("http_no_save")
    def http_no_save_get_color_harakiri(self, http_no_save: MockHttpNoSaveProductInstanceManager) -> None:
        self.color = http_no_save.instance.the_property
        http_no_save.instance.harakiri()

    @transaction(self=StepSpec())
    @instance("http")
    @long_running
    def kill_product_directly_from_instance_system(self, http: MockHttpProductInstanceManager) -> None:
        product_instance = http._instance_manager_impl._find_instance()  # type: ignore
        product_instance.delete()  # type: ignore


class OtherStep(StepModel):
    color: str = ""
    is_blue: bool = False

    @transaction(self=StepSpec(upload=["is_blue"]))
    @instance("instance_step.x_y", identifier="inst")
    def set_is_blue(self, inst: MockGrpcProductInstanceManager) -> None:
        self.is_blue = inst.instance.the_property == "blue"


class Steps(StepsModel):
    instance_step: InstanceStep
    other_step: OtherStep


class InstancesSolution(Solution):
    display_name: str = "instancesV2"
    steps: Steps
