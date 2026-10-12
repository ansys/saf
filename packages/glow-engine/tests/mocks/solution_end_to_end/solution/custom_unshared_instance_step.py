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

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    StepModel,
    StepSpec,
    long_running,
    transaction,
)
from tests.mocks.instance_managers.mock_product_manager import (
    MockGrpcProductInstanceManager,
    MockHttpProductInstanceManager,
)


class CustomUnsharedInstanceStep(StepModel):
    value: str = "white"
    my_entity_handle_input: EntityHandle = NO_ENTITY
    my_entity_handle_output: EntityHandle = NO_ENTITY
    input_file: EntityHandle = NO_ENTITY
    output_file: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(upload=["value"]))
    def reset_value(self) -> None:
        self.value = "white"

    @transaction(self=StepSpec(upload=["value"]))
    @long_running
    def assign_value_from_unshared_custom_grpc_product_instance_long_running(self) -> None:
        with MockGrpcProductInstanceManager(version="1") as mock_product:
            self.value = mock_product.instance.the_property

    @transaction(self=StepSpec(upload=["value"]))
    def assign_value_from_unshared_custom_grpc_product_instance(self) -> None:
        with MockGrpcProductInstanceManager(version="1") as mock_product:
            self.value = mock_product.instance.the_property

    @transaction(self=StepSpec(upload=["value"]))
    @long_running
    def assign_value_from_unshared_custom_http_product_instance_long_running(self) -> None:
        with MockHttpProductInstanceManager(version="1") as mock_product:
            self.value = mock_product.instance.the_property

    @transaction(self=StepSpec(upload=["value"]))
    def assign_value_from_unshared_custom_http_product_instance(self) -> None:
        with MockHttpProductInstanceManager(version="1") as mock_product:
            self.value = mock_product.instance.the_property

    @transaction(self=StepSpec())
    def use_unshared_custom_product_instance(self) -> str:
        with MockHttpProductInstanceManager() as custom_http:
            return custom_http.instance.the_property

    @transaction(self=StepSpec(download=["input_file"], upload=["output_file"]))
    def use_product_files_with_unshared(self) -> None:
        with MockHttpProductInstanceManager() as custom_http:
            filepath_on_product = custom_http.storage_scope.get_cached(self.input_file).as_posix()
            output_data = str(custom_http.instance.process_input_file(filepath_on_product))  # type: ignore
            self.output_file = custom_http.storage_scope.store_stream(output_data.encode())

    @transaction(self=StepSpec())
    def launch_unshared_and_retrieve_version_custom_http_product_instance(self, version: str | None = None) -> str:
        if version:
            with MockHttpProductInstanceManager(version=version) as custom_http:
                return custom_http.product_version
        with MockHttpProductInstanceManager() as custom_http:
            return custom_http.product_version

    @transaction(self=StepSpec(upload=["my_entity_handle_input"]))
    def write_entity_handle_input(self) -> None:
        filepath = self.storage_scope.get_storage_root() / "my_file_input.txt"
        filepath.write_text("black")
        self.my_entity_handle_input = self.storage_scope.store(filepath)

    @transaction(self=StepSpec(download=["my_entity_handle_input"], upload=["my_entity_handle_output", "value"]))
    def unshared_custom_http_entity_handle_to_and_from_transaction(self) -> None:
        with MockHttpProductInstanceManager(version="1") as mock_product:
            # using input file to restore instance property
            input_filepath_from_product = mock_product.storage_scope.get_cached(self.my_entity_handle_input)
            mock_product.instance.restore_given_absolute_path(str(input_filepath_from_product))
            # storing instance property to file within product space
            output_filepath_from_product = mock_product.storage_scope.get_storage_root() / "my_file_output.txt"
            mock_product.instance.store_given_absolute_path(str(output_filepath_from_product))
            # saving output file as entity_handle
            self.my_entity_handle_output = mock_product.storage_scope.store(output_filepath_from_product)
        # using transaction storage_scope to see if entity handle stored by product can be used
        output_filepath_from_transaction = self.storage_scope.get_cached(self.my_entity_handle_output)
        self.value = output_filepath_from_transaction.read_text()
