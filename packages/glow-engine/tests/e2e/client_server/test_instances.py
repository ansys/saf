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

from collections.abc import Callable
import contextlib
from pathlib import Path
import re
from threading import Thread

import httpx2
import psutil
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import BadRequestException, Client, InternalSolutionException
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.mocks.solutions.instances import InstancesSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [InstancesSolution], indirect=True),
    pytest.mark.use_instances,
]


@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
class TestInstances:
    def test_method_with_create_instance_can_access_property_of_shared_object(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        assert step.color == ""
        step.create()
        assert step.color == "blue"
        # Product creates state file that it's accessible from GLOW server no matter deployment type
        product_state_file = next(function_project.project_files_dir.rglob("project.txt"))
        assert product_state_file.read_text() == "blue"
        step.shutdown()

    def test_method_with_instance_can_access_property_of_shared_object(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        step.create()
        step.set_is_blue()
        assert step.is_blue
        step.shutdown()

    def test_method_with_instance_can_access_property_of_shared_object_in_another_step(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        function_project.project.steps.instance_step.create()
        step = function_project.project.steps.other_step
        step.set_is_blue()
        assert step.is_blue
        function_project.project.steps.instance_step.shutdown()

    def test_method_with_instance_can_have_untyped_instance_parameter(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        step.create_no_type()
        step.set_is_blue_no_type()
        assert step.is_blue
        step.shutdown()

    def test_method_with_create_instance_after_long_running(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        assert step.color == ""
        long_running = step.long_running_before_create_instance()
        long_running.wait()
        assert step.color == "blue"
        long_running = step.long_running_before_instance()
        long_running.wait()
        assert step.color == "yellow"
        step.shutdown()

    def test_product_instance_created_state_is_restored_after_restart(
        self,
        function_project: ProjectFixture[InstancesSolution],
        session_glow: GlowBaseProcess[InstancesSolution],
    ):
        # Create instance
        function_project.project.steps.instance_step.create()

        # Restart GLOW without shutting down instance
        session_glow.restart()

        # reopen same project
        step = function_project.project.steps.instance_step
        step.set_is_blue()
        assert step.is_blue
        # reexecute method just to check that state is stable
        step.set_is_blue()
        step.shutdown()

    def test_method_with_side_effect_on_instance(self, function_project: ProjectFixture[InstancesSolution]):
        step = function_project.project.steps.instance_step
        step.create()
        step.set_instance_red()
        step.set_is_blue()
        assert not step.is_blue
        step.shutdown()

    def test_product_instance_intermeadiate_state_is_restored_after_restart(
        self,
        function_project: ProjectFixture[InstancesSolution],
        session_glow: GlowBaseProcess[InstancesSolution],
    ):
        # Create instance and set intermediate state
        step = function_project.project.steps.instance_step
        step.create()
        step.set_instance_red()

        # Restart GLOW without shutting down instance
        session_glow.restart()

        # reopen same project
        step = function_project.project.steps.instance_step
        step.set_is_blue()
        assert not step.is_blue
        # reexecute method just to check that state is stable
        step.set_is_blue()
        assert not step.is_blue
        step.shutdown()

    def test_method_with_instance_can_upload_and_download_entity_handle_to_shared_object(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        step.create()
        step.store_red_in_entity_handle()
        step.set_instance_from_entity_handle()
        # File uploaded to Product is accessible from GLOW server no matter deployment type
        step.get_instance_to_entity_handle()
        step.set_is_blue_from_entity_handle()
        assert not step.is_blue
        step.shutdown()

    def test_on_desktop_that_method_on_product_instance_can_be_invoked_by_product_manager_as_part_of_server_exit(
        self,
        session_glow: GlowBaseProcess[InstancesSolution],
        function_project: ProjectFixture[InstancesSolution],
    ):
        # GIVEN - running server in which project state is red
        step = function_project.project.steps.instance_step
        step.create()
        assert step.color != "SHUTDOWN"

        spy_file_in_proj = function_project.project_files_dir / "spy.txt"
        assert spy_file_in_proj.read_text() == "saving state..."
        # WHEN - signalling user shutdown
        response = httpx2.post(f"{session_glow.base_api_url}/desktop:exit")
        response.raise_for_status()
        assert spy_file_in_proj.read_text() == "saving state...shutting instance down..."

        # reopen same project
        step.fetch_the_property()
        assert spy_file_in_proj.read_text() == "saving state...shutting instance down...loading state...saving state..."
        step.shutdown()
        assert (
            spy_file_in_proj.read_text()
            == "saving state...shutting instance down...loading state...saving state...shutting instance down..."
        )

    def test_on_desktop_create_instance_called_after_restart(
        self,
        session_glow: GlowBaseProcess[InstancesSolution],
        function_project: ProjectFixture[InstancesSolution],
    ):
        """Test that after a GLOW API restart, a product instance can be re-created
        even if the previous instance was not cleanly shutdown.
        """

        # GIVEN - running server in which project state is red
        step = function_project.project.steps.instance_step
        step.create()
        step.set_instance_red()
        # WHEN - closing the solution (simulating user closing the desktop window)
        response = httpx2.post(f"{session_glow.base_api_url}/desktop:exit", timeout=300)
        response.raise_for_status()
        session_glow.restart()
        # THEN - reopening the project and re-creating the instance works
        step.create()
        assert step.color == "blue"

    def test_that_reinitialization_resets_instance_state(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        step.create()
        step.set_instance_red()
        step.create()
        step.set_is_blue()
        assert step.is_blue
        step.shutdown()

    def test_that_reinitialization_triggers_deletion_of_instance_directory(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        """Test that when reinitializing a product instance, the instance state directory is deleted."""
        # GIVEN - running instance with file in instance
        step = function_project.project.steps.instance_step
        step.create()
        step.store_red_in_entity_handle()
        step.set_instance_from_entity_handle()
        instance_project_file = next(function_project.project_files_dir.rglob("project.txt"))
        assert instance_project_file.exists()
        # WHEN - reinitializing the instance
        step.create()

        # THEN - the file doesn't exist in instance file space
        # after the garbage collection has been triggered
        @retry(stop=stop_after_attempt(10), wait=wait_fixed(0.1))
        def project_file_deleted():
            if instance_project_file.exists():
                raise TryAgain

        # AND - a new one has been created
        project_file_deleted()
        assert not instance_project_file.exists()
        assert next(function_project.project_files_dir.rglob("project.txt")).exists()

    def test_product_state_dir_created_at_initialize_and_removed_at_shutdown(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        """Test that the product instance state directory is created when initializing the product instance,
        and removed when shutting down the product instance.
        """
        step = function_project.project.steps.instance_step
        assert not any(function_project.project_files_dir.rglob("project.txt"))
        step.create()
        # Product creates state file that it's accessible from GLOW server no matter deployment type
        product_state_file = next(function_project.project_files_dir.rglob("project.txt"))
        assert product_state_file.exists()
        assert re.match(
            rf"{function_project.project_files_dir.as_posix()}/is_\w{{8}}/project.txt",
            product_state_file.as_posix(),
        )
        step.shutdown()
        assert not product_state_file.exists()
        assert not any(function_project.project_files_dir.rglob("project.txt"))

    def test_create_product_with_project_file(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        """Test that the product instance can be initialized with a project file,
        and that the product instance state directory is initialized with a copy of the given project file.
        """
        step = function_project.project.steps.instance_step
        assert not any(function_project.project_files_dir.rglob("project.txt"))
        # When creating a product instance with a project file
        step.create_with_project()
        # Then both the original project file and the one in the product instance state directory exist
        project_files = list(function_project.project_files_dir.rglob("project.txt"))
        assert len(project_files) == 2
        assert all(p.exists() for p in project_files)
        step.color = "brown"
        # When shutting down the product instance
        step.shutdown()
        # Then only the original project file within the method storage scope remains
        for p in project_files:
            assert p.exists() if "method_" in p.as_posix() else not p.exists()
        project_files = list(function_project.project_files_dir.rglob("project.txt"))
        assert len(project_files) == 1

    def test_on_desktop_that_shutdown_is_not_invoked_twice_on_reinitialized_product_instance(
        self,
        session_glow: GlowBaseProcess[InstancesSolution],
        function_project: ProjectFixture[InstancesSolution],
    ):
        # GIVEN - running instance
        function_project.project.steps.instance_step.create()

        # WHEN - re-initalizing the product instance
        function_project.project.steps.instance_step.create()

        # THEN - exit is successful (shutdown is not reinvoked for the 'old' product instance)
        response = httpx2.post(f"{session_glow.base_api_url}/desktop:exit")
        response.raise_for_status()
        function_project.project.steps.instance_step.shutdown()

    def test_method_on_solution_using_shared_product_instance_does_not_have_pim_config_env_var_set(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        step.create()
        step.check_pim_config_env_var_is_not_set()
        step.shutdown()

    def test_that_reinitialization_is_triggered_when_importing_project(
        self,
        session_glow: GlowBaseProcess[InstancesSolution],
        tmp_path: Path,
        function_client: Client[InstancesSolution],
        function_project: ProjectFixture[InstancesSolution],
    ):
        function_project.project.steps.instance_step.create()
        function_project.project.steps.instance_step.get_pim_name()
        pim_name = function_project.project.steps.instance_step.pim_name
        assert pim_name.startswith("instances/custom-grpc-product")

        # WHEN - exporting and re-importing a project
        function_project.project.export(tmp_path)
        safx_path = tmp_path / f"{function_project.project.project_display_name}.safx"
        with ProjectFixture(session_glow, function_client, display_name="y", safx_path=safx_path) as project_context:
            # THEN - pim_name is reinitialized when new @instance is called
            project_context.project.steps.instance_step.get_pim_name()
            # THEN - pim_name is properly set again
            new_pim_name = project_context.project.steps.instance_step.pim_name
            assert new_pim_name.startswith("instances/custom-grpc-product")
            assert new_pim_name != pim_name
            project_context.project.steps.instance_step.shutdown()

    def test_method_with_unshared_product(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        assert step.color == ""
        step.unshared_product_instance()
        assert step.color == "blue"

    def test_method_with_unshared_bdm_product(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        # GIVEN: a product step with default values
        step = function_project.project.steps.instance_step
        assert step.color == ""
        assert step.mock_result == ""
        # WHEN: executing a transaction using an unshared product with bdm
        step.unshared_bdm_product_instance()
        # THEN: the product could resolve files from the transaction
        assert step.color == "red"
        # AND: the transaction could resolve files from the product
        assert step.mock_result == "fake solve results"

    def test_method_with_tcp_instance_manager(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        assert step.color == ""
        step.create_tcp()
        assert step.color == "blue"
        step.set_is_blue_tcp()
        assert step.is_blue
        step.shutdown_tcp()

    def test_manager_impl_functions_are_called(self, function_project: ProjectFixture[InstancesSolution]):
        step = function_project.project.steps.instance_step
        assert step.color == ""
        spy_file_in_proj = function_project.project_files_dir / "spy.txt"
        assert not spy_file_in_proj.exists()
        step.create()
        assert spy_file_in_proj.exists()
        assert spy_file_in_proj.read_text() == "saving state..."
        step.shutdown()
        assert spy_file_in_proj.exists()
        assert spy_file_in_proj.read_text() == "saving state...shutting instance down..."

    def test_manager_instance_transaction_called_after_shutdown(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        # instance is launched
        step.create()
        # instance is manually shutdown
        step.shutdown()
        # then transaction cannot be executed without redoing create_instance
        with pytest.raises(BadRequestException):
            step.fetch_the_property()

    def test_manager_instance_recreate_after_shutdown(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        # instance is launched
        step.create()
        assert step.color == "blue"
        # instance is manually shutdown
        step.shutdown()
        # when recreate instance
        step.color = "red"
        step.create()
        assert step.color == "blue"
        step.color = "red"
        # then transaction can be executed
        step.fetch_the_property()
        assert step.color == "blue"

    def test_manager_instance_health_check_after_init_and_shutdown(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step

        # instance is launched
        step.create_http()
        step.check_instance_health()
        assert step.instance_healthy

        step.shutdown_http()

    def test_manager_instance_health_check_after_reinitialize_raise_exception(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        step.create_http()

        # instance is manually shutdown
        with contextlib.suppress(InternalSolutionException):
            # Since we are closing the product from the pim/hps and not the manager itself,
            # the dispose of the client in the end of the transaction is raising an exception
            step.kill_product_directly_from_instance_system().wait()
        step.check_instance_health()
        assert step.instance_healthy

        step.shutdown_http()

    def test_manager_instance_health_check_after_instance_unhealthy(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        step.create_http()
        # instance is ready but unhealthy, so instance_manager will
        # relaunch it and the new one will be healthy.
        step.be_unhealthy_http()
        step.check_instance_health()
        assert step.instance_healthy
        # instance is back to healthy
        step.be_healthy_http()
        step.check_instance_health()
        assert step.instance_healthy

        step.shutdown_http()
        assert step.was_instance_shutdown

    def test_manager_instance_health_check_after_instance_killed(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        step.create_http()

        # instance is externally killed
        with pytest.raises(InternalSolutionException):
            step.harakiri()
        step.check_instance_health()
        assert step.instance_healthy

        step.shutdown_http()

    def test_fields_not_uploaded_when_instance_killed(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        # WHEN: initializing a product instance and setting a property
        step.create_http()
        step.set_http_instance_red()

        assert step.color == ""

        # THEN: the instance state couldn't be saved (instance killed / unreachable)
        # and the field is not uploaded
        with pytest.raises(InternalSolutionException):
            step.get_http_instance_color_and_kill_instance()
        assert step.color == ""

    def test_fields_uploaded_when_instance_shutdown(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step
        # WHEN: initializing a product instance and setting a property
        step.create_http()
        step.set_http_instance_red()

        assert step.color == ""

        # THEN: the instance is shutdown, and the field is uploaded
        step.shutdown_http()
        assert step.was_instance_shutdown
        assert step.color == "red"

    def test_no_save_impl_killed_uploads_fields(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        step = function_project.project.steps.instance_step

        # WHEN: initializing a product instance that doesn't implement save_state
        step.create_http_no_save()
        step.set_http_no_save_red()

        assert step.color == ""

        # THEN: the instance is killed, but since save_state doesn't raise
        # an exception, the field is uploaded
        step.http_no_save_get_color_harakiri()

        assert step.color == "red"

    def test_product_instance_is_shutdown_and_state_dir_is_deleted_when_instance_record_is_removed(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        """Test that after a call to the API to delete a product instance, the product instance client cannot be used
        nor reinitialized, and the product instance process is killed."""
        step = function_project.project.steps.instance_step

        # GIVEN: an initialized product instance with stored state files
        step.create_http()
        step.get_http_process_pid()
        assert psutil.pid_exists(step.http_pid)

        instance_state = function_project.get_instance("instance-step", "http")
        state_dirname = instance_state["recovery_state_info"]["product_instance_state_dirname"]
        state_dir = function_project.project_files_dir / state_dirname
        state_marker = state_dir / "delete-me.txt"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_marker.write_text("state")

        # WHEN: it is deleted via the API
        response = httpx2.delete(f"{step._url}/instances/http", timeout=300)  # type: ignore
        response.raise_for_status()

        # THEN: the client can no longer be used and does not reinitialize
        with pytest.raises(BadRequestException):
            step.set_http_instance_red()

        # THEN: the process running the product instance is killed
        assert not psutil.pid_exists(step.http_pid)
        # AND: the instance state directory is removed from project files
        assert not state_dir.exists()

    def test_other_instance_state_directories_when_instance_record_is_removed(
        self,
        function_project: ProjectFixture[InstancesSolution],
        create_project: Callable[[], ProjectFixture[InstancesSolution]],
    ):
        # GIVEN: two product instances in 1 project and another product instance in another project
        step = function_project.project.steps.instance_step
        step.create_http()
        instance_state_1 = function_project.get_instance("instance-step", "http")
        instance1_state_dirname = instance_state_1["recovery_state_info"]["product_instance_state_dirname"]

        step.create_tcp()
        instance_state_2 = function_project.get_instance("instance-step", "tcp")
        instance2_state_dirname = instance_state_2["recovery_state_info"]["product_instance_state_dirname"]

        project_2 = create_project()
        project_2.project.steps.instance_step.create_http()
        instance_state_3 = project_2.get_instance("instance-step", "http")
        instance3_state_dirname = instance_state_3["recovery_state_info"]["product_instance_state_dirname"]

        project_1_instance1_state_dir = function_project.project_files_dir / instance1_state_dirname
        project_1_instance2_state_dir = function_project.project_files_dir / instance2_state_dirname
        project_2_instance1_state_dir = project_2.project_files_dir / instance3_state_dirname

        project_1_instance1_state_dir.mkdir(parents=True, exist_ok=True)
        project_1_instance2_state_dir.mkdir(parents=True, exist_ok=True)
        project_2_instance1_state_dir.mkdir(parents=True, exist_ok=True)

        # WHEN: deleting instance1 in project1
        response = httpx2.delete(f"{step._url}/instances/http", timeout=300)  # type: ignore
        response.raise_for_status()

        # THEN: only instance1 state dir from project1 is removed
        assert not project_1_instance1_state_dir.exists()
        assert project_1_instance2_state_dir.is_dir()
        assert project_2_instance1_state_dir.is_dir()

    def test_product_instance_config_loaded_once_bug_1265(
        self,
        function_project: ProjectFixture[InstancesSolution],
    ):
        """Test that the product instance configurations used by the global instance system
        (for non long_running method) is not loaded multiple times, in case multiple transactions
        are called simultaneously."""
        # GIVEN: a step with instances
        step = function_project.project.steps.instance_step

        # WHEN: executing a transaction using an instance
        create_http_thread = Thread(target=step.create_http, daemon=True)
        create_http_thread.start()
        # AND: executing a second transaction also using an instance
        try:
            step.create()
            # THEN: no exception is raised
            create_http_thread.join()
        except Exception as ex:
            # in case of bug #1265 this failed with the error message:
            # "More than one configuration matches product {product_name}"
            pytest.fail(str(ex))

    def test_method_with_create_instance_does_not_trigger_instance_not_found(
        self,
        function_project: ProjectFixture[InstancesSolution],
        session_glow: GlowBaseProcess[InstancesSolution],
    ):
        # GIVEN: a step with instances
        step = function_project.project.steps.instance_step
        assert step.color == ""
        # WHEN: executing a transaction using the create instance decorator
        step.create()
        # THEN: no ERROR is shown in the API logs
        assert not any("ERROR" in line for line in session_glow.api_output)
        assert not any(
            "404: Instance 'x_y' on Step 'instance_step' is not found." in line for line in session_glow.api_output
        )
        step.shutdown()

    def test_method_with_instance_triggers_instance_not_found_if_instance_deleted(
        self,
        function_project: ProjectFixture[InstancesSolution],
        session_glow: GlowBaseProcess[InstancesSolution],
    ):
        # GIVEN: a step with instances
        step = function_project.project.steps.instance_step
        assert step.color == ""
        # WHEN: executing a transaction using the create instance decorator
        step.create()
        # WHEN: we delete the instance via the API
        response = httpx2.delete(f"{step._url}/instances/x-y")  # type: ignore
        response.raise_for_status()
        # WHEN: and we call a transaction that uses that instance
        with pytest.raises(BadRequestException, match="The method has been called out of sequence."):
            step.set_is_blue()
        # THEN: an 404 error is shown in the API logs saying the instance could no be found
        assert any(
            "404: Instance 'x_y' on Step 'instance_step' is not found." in line for line in session_glow.api_output
        )
