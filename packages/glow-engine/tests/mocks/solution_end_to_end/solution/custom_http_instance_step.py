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

import time

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from tests.mocks.instance_managers.mock_product_manager import (
    CustomRouteHttpProductManager,
    FakeRouteHttpProductManager,
    MockHttpNoServiceNameProductInstanceManager,
    MockHttpNoVersionArgProductInstanceManager,
    MockHttpProductInstanceManager,
    WrongServiceTypeProductManager,
)
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    TransactionVerificationStep,
)

INSTANCE_MAX_EXECUTION_TIME = 20


class CustomHttpSharedInstanceStep(StepModel):
    value: str = "white"
    healthy_before_timeout: bool = False
    healthy_after_timeout: bool = True  # Set to True to avoid false positives
    my_entity_handle: EntityHandle = NO_ENTITY
    state_entity_handle: EntityHandle = NO_ENTITY
    input_file: EntityHandle = NO_ENTITY
    output_file: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(upload=["value"]))
    def reset_value(self) -> None:
        self.value = "white"

    @transaction(self=StepSpec())
    @create_instance("custom_http_product_instance", MockHttpProductInstanceManager)
    @long_running
    def initialize_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        custom_http_product_instance.initialize(version="1")

    @transaction(self=StepSpec(upload=["value"]))
    @create_instance("custom_http_product_instance", MockHttpProductInstanceManager)
    @long_running
    def initialize_custom_http_product_instance_and_use(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        custom_http_product_instance.initialize(version="1")
        self.value = custom_http_product_instance.instance.the_property

    @transaction(self=StepSpec(download=["input_file"], upload=["output_file"]))
    @instance("custom_http_product_instance")
    def use_product_files_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        filepath_on_product = custom_http_product_instance.storage_scope.get_cached(self.input_file).as_posix()
        output_data = str(custom_http_product_instance.instance.process_input_file(filepath_on_product))  # type: ignore
        self.output_file = custom_http_product_instance.storage_scope.store_stream(output_data.encode())

    @transaction(self=StepSpec(upload=["value"]))
    @instance("custom_http_product_instance")
    @long_running
    def retrieve_value_custom_http_product_instance_long_running(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        self.value = custom_http_product_instance.instance.the_property

    @transaction(self=StepSpec())
    @instance("custom_http_product_instance")
    def retrieve_nested_value_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> str:
        project = custom_http_product_instance.instance.odesktop.GetActiveProject()  # type: ignore
        design = project.GetActiveDesign()  # type: ignore
        return design.GetName()  # type: ignore

    @transaction(self=StepSpec())
    @create_instance("custom_http_product_instance", MockHttpProductInstanceManager)
    def launch_shared_and_retrieve_version_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
        version: str | None = None,
        using_kwarg: bool = False,
    ) -> str:
        if version:
            if using_kwarg:
                custom_http_product_instance.initialize(version=version)
            else:
                custom_http_product_instance.initialize(version)
        else:
            custom_http_product_instance.initialize()
        return custom_http_product_instance.product_version

    @transaction(self=StepSpec())
    @create_instance("custom_http_without_version_arg", MockHttpNoVersionArgProductInstanceManager)
    def launch_and_use_http_product_without_version_arg(
        self,
        custom_http_without_version_arg: MockHttpNoVersionArgProductInstanceManager,
    ) -> str:
        custom_http_without_version_arg.initialize()
        return custom_http_without_version_arg.instance.the_property

    @transaction(self=StepSpec())
    @create_instance("custom_http_no_service_name", MockHttpNoServiceNameProductInstanceManager)
    def launch_and_use_http_product_without_service_name(
        self,
        custom_http_no_service_name: MockHttpNoServiceNameProductInstanceManager,
    ) -> str:
        custom_http_no_service_name.initialize()
        return custom_http_no_service_name.instance.the_property

    @transaction(self=StepSpec())
    @create_instance(
        "custom_http_product_instance",
        MockHttpProductInstanceManager,
        max_execution_time=INSTANCE_MAX_EXECUTION_TIME,
    )
    def initialize_max_exec_time_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        custom_http_product_instance.initialize(version="1")

    @transaction(self=StepSpec(upload=["value"]))
    @instance("custom_http_product_instance")
    def retrieve_value_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        self.value = custom_http_product_instance.instance.the_property

    @transaction(self=StepSpec(upload=["value", "healthy_before_timeout", "healthy_after_timeout"]))
    @instance("custom_http_product_instance")
    def change_retrieve_and_timeout_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        custom_http_product_instance.instance.the_property = "brown"
        self.value = custom_http_product_instance.instance.the_property
        self.healthy_before_timeout = custom_http_product_instance.instance.healthy()
        time.sleep(INSTANCE_MAX_EXECUTION_TIME + 20)
        self.healthy_after_timeout = custom_http_product_instance.instance.healthy()
        self.transaction.upload(["healthy_before_timeout", "healthy_after_timeout"])

    @transaction(self=StepSpec(upload=["value"]))
    @instance("custom_http_product_instance")
    def change_timeout_and_retrieve_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        custom_http_product_instance.instance.the_property = "brown"
        time.sleep(INSTANCE_MAX_EXECUTION_TIME + 20)
        self.value = custom_http_product_instance.instance.the_property

    @transaction(self=StepSpec(upload=["value"]))
    @instance("custom_http_product_instance")
    def timeout_and_retrieve_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        time.sleep(INSTANCE_MAX_EXECUTION_TIME + 20)
        self.value = custom_http_product_instance.instance.the_property

    @transaction(self=StepSpec(download=["my_entity_handle"]))
    @instance("custom_http_product_instance")
    def upload_entity_handle_with_value_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        filepath_on_product = custom_http_product_instance.storage_scope.get_cached(self.my_entity_handle)
        custom_http_product_instance.instance.restore_given_absolute_path(str(filepath_on_product))

    @transaction(self=StepSpec(upload=["my_entity_handle"]))
    @instance("custom_http_product_instance")
    def download_entity_handle_with_value_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        filepath_on_product = custom_http_product_instance.storage_scope.get_storage_root() / "my_file.txt"
        custom_http_product_instance.instance.store_given_absolute_path(str(filepath_on_product))
        self.my_entity_handle = custom_http_product_instance.storage_scope.store(filepath_on_product)

    @transaction(self=StepSpec(download=["value"]))
    @instance("custom_http_product_instance")
    def change_value_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
        val: str = "",
    ) -> None:
        custom_http_product_instance.instance.the_property = val if val else self.value

    @transaction(self=StepSpec(download=["value"]))
    @instance("custom_http_product_instance")
    def set_red_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        custom_http_product_instance.instance.the_property = "red"

    @transaction()
    @instance("custom_http_product_instance")
    @long_running
    def compute_value_custom_http_product_instance_lr(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        current_value = custom_http_product_instance.instance.the_property
        current_value *= 2
        custom_http_product_instance.instance.the_property = current_value

    @transaction(self=StepSpec())
    @instance("custom_http_product_instance")
    def shutdown_custom_http_product_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        custom_http_product_instance.shutdown()

    @transaction(self=StepSpec())
    @create_instance("custom_route_http_product_instance", CustomRouteHttpProductManager)
    @long_running
    def initialize_custom_route_http_product_instance(
        self,
        custom_route_http_product_instance: CustomRouteHttpProductManager,
    ) -> None:
        custom_route_http_product_instance.initialize(version="1")

    @transaction(self=StepSpec(upload=["value"]))
    @instance("custom_route_http_product_instance")
    def retrieve_value_custom_route_http_product_instance(
        self,
        custom_route_http_product_instance: CustomRouteHttpProductManager,
    ) -> None:
        self.value = custom_route_http_product_instance.instance.the_property

    @transaction(self=StepSpec(download=["value"]))
    @instance("custom_route_http_product_instance")
    def change_value_custom_route_http_product_instance(
        self,
        custom_route_http_product_instance: CustomRouteHttpProductManager,
    ) -> None:
        custom_route_http_product_instance.instance.the_property = self.value

    @transaction(self=StepSpec())
    @instance("custom_route_http_product_instance")
    def shutdown_custom_route_http_product_instance(
        self,
        custom_route_http_product_instance: CustomRouteHttpProductManager,
    ) -> None:
        custom_route_http_product_instance.shutdown()

    @transaction(self=StepSpec())
    @create_instance("fake_route_http_product_instance", FakeRouteHttpProductManager)
    @long_running
    def initialize_fake_route_http_product_instance(
        self,
        fake_route_http_product_instance: FakeRouteHttpProductManager,
    ) -> None:
        fake_route_http_product_instance.initialize(version="1")

    @transaction(self=StepSpec())
    @create_instance("wrong_service_type_product_instance", WrongServiceTypeProductManager)
    @long_running
    def initialize_wrong_service_type_product_instance(
        self,
        wrong_service_type_product_instance: WrongServiceTypeProductManager,
    ) -> None:
        wrong_service_type_product_instance.initialize(version="1")

    @transaction(self=StepSpec())
    @long_running
    @create_instance("wrong_port_http_product", WrongServiceTypeProductManager)
    def initialize_wrong_port_http_product(self, wrong_port_http_product: WrongServiceTypeProductManager) -> None:
        wrong_port_http_product.initialize(version="1")

    @transaction(self=StepSpec())
    @instance("custom_http_product_instance")
    @long_running
    def harakiri(self, custom_http_product_instance: MockHttpProductInstanceManager) -> None:
        custom_http_product_instance.instance.harakiri()

    @transaction(self=StepSpec(upload=["value"]))
    @instance("custom_http_product_instance")
    @long_running
    def retrieve_http_product_value_and_kill_instance(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        self.value = custom_http_product_instance.instance.the_property
        custom_http_product_instance.instance.harakiri()

    @transaction(self=StepSpec())
    @instance("custom_http_product_instance")
    @long_running
    def kill_product_directly_from_instance_system(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        product_instance = custom_http_product_instance._instance_manager_impl._find_instance()  # type: ignore
        product_instance.delete()  # type: ignore

    @transaction(
        self=StepSpec(),
        transaction_verification_step=StepSpec(download=["e2e_file_entity_api", "e2e_file_entity_ui"]),
    )
    @create_instance("http_instance", MockHttpProductInstanceManager)
    def use_project_cached_at_ui(
        self,
        http_instance: MockHttpProductInstanceManager,
        transaction_verification_step: TransactionVerificationStep,
    ) -> tuple[str, str, str]:
        http_instance.initialize(version="1")

        filepath_on_product = http_instance.storage_scope.get_cached(transaction_verification_step.e2e_file_entity_ui)
        http_instance.instance.restore_given_absolute_path(str(filepath_on_product))

        return (
            self.storage_scope.get_text(transaction_verification_step.e2e_file_entity_api),
            transaction_verification_step.storage_scope.get_text(transaction_verification_step.e2e_file_entity_ui),
            http_instance.instance.the_property,
        )

    @transaction(self=StepSpec())
    @instance("custom_http_product_instance")
    def store_decrypted_asset_from_product(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        asset_file1 = self.transaction.get_asset_entity_handle("asset_file1.txt")
        filepath = custom_http_product_instance.storage_scope.get_cached(asset_file1)
        custom_http_product_instance.instance.the_property = str(filepath)

    @transaction(self=StepSpec(upload=["state_entity_handle"]))
    @instance("custom_http_product_instance")
    def store_from_product_state_dir(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        filepath = custom_http_product_instance.state_directory / "project.txt"
        self.state_entity_handle = custom_http_product_instance.storage_scope.store_from_state_directory(filepath)

    @transaction(self=StepSpec(upload=["state_entity_handle"]))
    @instance("custom_http_product_instance")
    def store_dir_from_product_state_dir(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        filepath = custom_http_product_instance.state_directory / "dir" / "project.txt"
        custom_http_product_instance.instance.store_given_absolute_path(str(filepath))
        self.state_entity_handle = custom_http_product_instance.storage_scope.store_from_state_directory(
            filepath.parent,
        )

    @transaction(self=StepSpec())
    @instance("custom_http_product_instance")
    def store_encrypted_asset_from_product(
        self,
        custom_http_product_instance: MockHttpProductInstanceManager,
    ) -> None:
        asset_file = self.transaction.get_asset_entity_handle("asset_encrypted_file1_e.txt")
        filepath = custom_http_product_instance.storage_scope.get_cached(asset_file)
        custom_http_product_instance.instance.the_property = str(filepath)

    @transaction(self=StepSpec())
    def is_glow_src_readable(self) -> bool:
        import inspect

        try:
            inspect.getsource(StepSpec)
        except OSError:
            return False
        else:
            return True
