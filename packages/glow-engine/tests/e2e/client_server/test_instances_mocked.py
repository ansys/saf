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
import tempfile

import pytest

from ansys.saf.glow.client import BadRequestException, InternalSolutionException
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solutions.instances_mocked import InstancesMockedSolution

pytestmark = pytest.mark.parametrize(
    ("solution_type", "instance_system_type"),
    [(InstancesMockedSolution, "_MOCK")],
    indirect=True,
)

INSTANCE_NOT_INITIALIZED_MSG = (
    "The method has been called out of sequence. "
    "A shared product instance that this method uses has not been initialized."
)


class TestInstancesMocked:
    def test_creating_and_using_shared_instance(self, function_project: ProjectFixture[InstancesMockedSolution]):
        """
        Test that a shared instance can be created and used within a project step when using the MockSystem. The client
        is properly returned and can be used as long as it doesn't try to communicate with the product since the product
        is not actually running.
        """
        step = function_project.project.steps.instance_step
        step.create().wait()
        assert step.use_instance_client() == "blue"
        step.shutdown()

    def test_using_shared_instance_before_creation(self, function_project: ProjectFixture[InstancesMockedSolution]):
        """
        Test that a shared instance cannot be used before it is created when using the MockSystem.
        """
        step = function_project.project.steps.instance_step
        with pytest.raises(BadRequestException, match=INSTANCE_NOT_INITIALIZED_MSG):
            step.use_instance_client()

    def test_using_shared_instance_after_deletion(self, function_project: ProjectFixture[InstancesMockedSolution]):
        """
        Test that a shared instance cannot be used after it is deleted when using the MockSystem.
        """
        step = function_project.project.steps.instance_step
        step.create().wait()
        step.shutdown()
        with pytest.raises(BadRequestException, match=INSTANCE_NOT_INITIALIZED_MSG):
            step.use_instance_client()

    def test_trying_to_communicate_with_product_instance(
        self,
        function_project: ProjectFixture[InstancesMockedSolution],
    ):
        """
        Test that trying to communicate with the product instance when using the MockSystem raises an exception since
        the product is actually not running.
        """
        step = function_project.project.steps.instance_step
        step.create().wait()
        with pytest.raises(InternalSolutionException):
            step.fetch_server_version()
        step.shutdown()

    def test_using_product_files(self, function_project: ProjectFixture[InstancesMockedSolution]):
        """
        Test that files can be stored in the product instance's file space and retrieved correctly when using the
        MockSystem.
        """
        step = function_project.project.steps.instance_step
        step.create().wait()
        assert not any(function_project.project_files_dir.rglob("bdm/product_*/my_file.txt"))
        step.store_files_in_product_space()
        product_file = next(function_project.project_files_dir.rglob("bdm/product_*/my_file.txt"))
        assert product_file
        assert product_file.read_text() == "some shared content"
        assert function_project.project.storage_scope.get_text(step.transfer_entity_handle) == "some shared content"
        step.shutdown()

    def test_using_unshared_instance(self, function_project: ProjectFixture[InstancesMockedSolution]):
        """
        Test that unshared product instances can be created and used in a transaction when using the MockSystem.
        Files can be transferred from the product's space.
        """
        step = function_project.project.steps.instance_step
        assert not any(function_project.project_files_dir.rglob("bdm/product_*/my_file.txt"))
        assert step.unshared_product_instance() == "blue"
        product_file = next(function_project.project_files_dir.rglob("bdm/product_*/my_file.txt"))
        assert product_file
        assert product_file.read_text() == "some unshared content"
        assert function_project.project.storage_scope.get_text(step.transfer_entity_handle) == "some unshared content"

    def test_manager_impl_functions_are_called(self, function_project: ProjectFixture[InstancesMockedSolution]):
        """
        Test that all manager implemented functions are called during the instance lifecycle when using the MockSystem.
        This is verified by checking the contents of a spy file that the implementation writes to.
        """
        step = function_project.project.steps.instance_step
        spy_file_in_proj = function_project.project_files_dir / "spy.txt"
        assert not spy_file_in_proj.is_file()
        step.create().wait()
        assert spy_file_in_proj.read_text() == "saving state..."

        pim_name = step.get_pim_name()
        assert spy_file_in_proj.read_text() == "saving state...saving state..."

        # "delete" product instance, forcing the manager to recreate it and reload its state
        product_file = next(Path(tempfile.gettempdir()).glob(f"*{pim_name.split('/')[1]}*"))
        product_file.unlink()
        assert step.use_instance_client() == "blue"
        assert spy_file_in_proj.read_text() == "saving state...saving state...loading state...saving state..."

        step.shutdown()
        assert (
            spy_file_in_proj.read_text()
            == "saving state...saving state...loading state...saving state...shutting instance down..."
        )
