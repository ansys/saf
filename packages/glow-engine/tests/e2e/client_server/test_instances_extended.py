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
import os
from pathlib import Path
import platform
import re

import httpx2
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import Client, InternalSolutionException
from ansys.saf.testing.hps import GetHpsJobIdsType
from ansys.saf.testing.network import get_docker_gateway_ip
from ansys.saf.testing.pim.process import PimProcess
from ansys.saf.testing.solution.const import TestDeployment, TestProductInstanceSystemType
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.e2e.conftest import PACKAGE_ROOT
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_instances,
]
DOCKER_GATEWAY_IP = get_docker_gateway_ip() if platform.system() == "Linux" else "127.0.0.1"


@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestCustomProductInstances:
    @retry(
        stop=stop_after_attempt(20),
        wait=wait_fixed(0.2),
    )
    def wait_for_gc_contains_one_project_txt(self, function_project: ProjectFixture[EndToEndSolution]) -> Path:
        project_files = list(function_project.project_files_dir.rglob("project.txt"))
        if len(project_files) != 1:
            raise TryAgain
        return project_files[0]

    @pytest.mark.parametrize(
        "instance_name",
        ["fake_route_http_product_instance", "wrong_service_type_product_instance"],
    )
    def test_shared_instance_wrong_health_check(
        self,
        instance_name: str,
        instance_system_type: TestProductInstanceSystemType,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that a Client exception is thrown when trying to initialize an instance with the wrong health check route.
        """
        if instance_system_type == TestProductInstanceSystemType.PIM:
            pytest.skip("Exposed PIM function wait_for_ready() never returns if service type is incorrect.")

        # WHEN initializing custom product instance with wrong health check: route or type
        # THEN fails to launch it
        method = getattr(function_project.project.steps.custom_http_shared_instance_step, f"initialize_{instance_name}")
        with pytest.raises(InternalSolutionException):
            method().wait()

        # THEN instance can not be found
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            function_project.get_instance("custom_http_shared_instance_step", instance_name)

    @pytest.mark.parametrize(
        ("step_name", "instance_name"),
        [
            ("custom_grpc_shared_instance_step", "custom_grpc_product_instance"),
            ("custom_http_shared_instance_step", "custom_http_product_instance"),
            ("custom_tcp_shared_instance_step", "custom_tcp_product_instance"),
            ("custom_http_shared_instance_step", "custom_route_http_product_instance"),
        ],
    )
    def test_shared_instance_workflow(
        self,
        step_name: str,
        instance_name: str,
        instance_system_type: TestProductInstanceSystemType,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        pim_port: int | None,
        deployment_type: TestDeployment,
        session_pim: PimProcess | None,
    ):
        """Test that a custom product can be launched via a custom configuration and that the same instance
        is used across transaction methods.
        """
        step = getattr(function_project.project.steps, step_name)

        # GIVEN instance cannot be found since it hasn't been initialized and step field has default value
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            function_project.get_instance(step_name, instance_name)
        assert step.value == "white"  # type: ignore

        if (
            instance_name == "custom_route_http_product_instance"
            and instance_system_type == TestProductInstanceSystemType.PIM
        ):
            pytest.skip("PIM Light Server doesn't support custom health routes for products.")
        # WHEN initializing custom product instance
        method = getattr(step, f"initialize_{instance_name}")
        method().wait()

        product_host = (
            "host.docker.internal"
            if deployment_type == TestDeployment.DockerCompose
            else "127.0.0.1"
            if instance_system_type == TestProductInstanceSystemType.PIM
            else "localhost"
        )
        if instance_name == "custom_grpc_product_instance":
            # assert compatibility with insecure products.
            # for secure products, see test_custom_secure_grpc_product_instance.
            assert session_glow.text_in_output(
                [
                    f"Health check: creating insecure grpc channel with uri={product_host}:",
                    "localhost as default authority",
                ],
            )

        if instance_system_type == TestProductInstanceSystemType.PIM:
            if deployment_type == TestDeployment.DockerCompose:
                assert session_glow.text_in_output(
                    f"Connecting to PIM Light Server via {product_host}:{pim_port} with credentials from /certs.",
                    "api",
                )
            elif platform.system() == "Windows":
                assert session_glow.text_in_output(
                    f"Connecting to PIM Light Server via {product_host}:{pim_port} without credentials.",
                    "api",
                )
            else:
                assert session_glow.text_in_output(
                    f"Connecting to PIM Light Server via unix:{session_pim.socket_path.as_posix()} without credentials.",  # type: ignore  # noqa: E501
                    "api",
                )

        # THEN instance can be found
        assert function_project.get_instance(step_name, instance_name)
        # custom instance state file is properly set
        project_txt_files = list(function_project.project_files_dir.rglob("project.txt"))
        assert len(project_txt_files) == 1
        custom_product_state_file = project_txt_files[0]
        assert custom_product_state_file.read_text() == "blue"

        # retrieving value from product
        assert step.value == "white"  # type: ignore
        # modifying the content of the state file (even though it is prohibited normally with bdm)
        # to check if it is being used by the product
        assert custom_product_state_file.write_text("overwrite_state")
        getattr(step, f"retrieve_value_{instance_name}")()
        assert step.value == "blue"  # type: ignore
        # instance state file is properly set after end of transaction that uses instance
        project_txt_files = list(function_project.project_files_dir.rglob("project.txt"))
        assert len(project_txt_files) == 1
        assert project_txt_files[0].read_text() == "blue"

        # changing internal value on the custom product instance
        step.value = "red"
        step = getattr(function_project.project.steps, step_name)
        getattr(step, f"change_value_{instance_name}")()

        assert self.wait_for_gc_contains_one_project_txt(function_project).read_text() == "red"

        getattr(step, f"retrieve_value_{instance_name}")()
        assert step.value == "red"  # type: ignore

        # shutdown product
        getattr(step, f"shutdown_{instance_name}")()
        # state file and instance record have been deleted
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            function_project.get_instance(step_name, instance_name)
        assert not custom_product_state_file.exists()

    @pytest.mark.parametrize(
        ("step_name", "instance_name"),
        [
            ("custom_grpc_shared_instance_step", "custom_grpc_product_instance"),
            ("custom_http_shared_instance_step", "custom_http_product_instance"),
            ("custom_tcp_shared_instance_step", "custom_tcp_product_instance"),
            ("custom_http_shared_instance_step", "custom_route_http_product_instance"),
        ],
    )
    def test_product_instance_system_restart(
        self,
        restart_product_instance_system: Callable[..., None],
        step_name: str,
        instance_name: str,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that a custom product instance can be restored after the Product Instance System is restarted (BDM
        Version).
        """

        step = getattr(function_project.project.steps, step_name)

        # GIVEN An initialized custom product instance
        method = getattr(step, f"initialize_{instance_name}")
        method().wait()

        assert function_project.get_instance(step_name, instance_name)
        # custom instance state file is properly set
        custom_product_state_file = next(function_project.project_files_dir.rglob("project.txt"))
        assert custom_product_state_file.read_text() == "blue"

        # WHEN: Restarting PIS
        restart_product_instance_system()

        # THEN: The instance remains usable and can be closed to end the workflow.
        step.value = "red"
        step = getattr(function_project.project.steps, step_name)
        getattr(step, f"change_value_{instance_name}")()

        # AND: previous product state files have been removed
        assert self.wait_for_gc_contains_one_project_txt(function_project).read_text() == "red"
        getattr(step, f"shutdown_{instance_name}")()

    def test_shared_instance_reinitialized(
        self,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that a custom product instance is reinitialized to the default state.
        """
        # GIVEN running instance that is shutdown afterwards.
        step = function_project.project.steps.custom_http_shared_instance_step
        step.initialize_custom_http_product_instance().wait()
        assert next(function_project.project_files_dir.rglob("project.txt"), None) is not None

        step.shutdown_custom_http_product_instance()

        @retry(
            stop=stop_after_attempt(20),
            wait=wait_fixed(0.2),
        )
        def wait_for_gc_cleanup_project_state_file() -> bool:
            if next(function_project.project_files_dir.rglob("project.txt"), None) is not None:
                raise TryAgain
            return True

        assert wait_for_gc_cleanup_project_state_file()
        # reinitializing the product
        step.initialize_custom_http_product_instance().wait()
        # default value is used
        assert step.value == "white"
        step.retrieve_value_custom_http_product_instance()
        assert step.value == "blue"

        # shutdown product
        step.shutdown_custom_http_product_instance()

    def test_shared_instance_recreated(
        self,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """Test that a custom product instance is recreated with clean state without shutdown first."""
        # GIVEN running instance that is shutdown afterwards.
        step = function_project.project.steps.custom_http_shared_instance_step
        step.initialize_custom_http_product_instance().wait()

        custom_product_state_file = next(function_project.project_files_dir.rglob("project.txt"))
        assert custom_product_state_file.is_file()

        # force create product again, check that doesn't require to shutdown first and that
        # state is not restored
        custom_product_state_file.write_text("overwrite_state_offline")
        step.initialize_custom_http_product_instance().wait()

        # AND: previous product state files have been removed
        assert self.wait_for_gc_contains_one_project_txt(function_project).read_text() == "blue"
        step.retrieve_value_custom_http_product_instance()
        assert step.value == "blue"

        # shutdown product
        step.shutdown_custom_http_product_instance()

    def test_shared_instance_running_across_glow_restart(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that custom product instances are resilient to Product Instance System (PIM, HPS) restarts.
        """
        # Initializing custom product instance
        step = function_project.project.steps.custom_http_shared_instance_step
        step.initialize_custom_http_product_instance().wait()

        custom_product_state_file = next(function_project.project_files_dir.rglob("project.txt"))
        assert custom_product_state_file.is_file()

        # change instance property to red
        step.value = "red"
        step.change_value_custom_http_product_instance()
        step.retrieve_value_custom_http_product_instance()
        assert step.value == "red"

        # overwrite instance state and restart glow
        self.wait_for_gc_contains_one_project_txt(function_project).write_text("overwrite_state_offline")
        session_glow.restart()

        # retrieve value from instance and check that it didn't load the state file since it wasn't reinitialized
        step.retrieve_value_custom_http_product_instance()
        assert step.value == "red"

        # shutdown product
        step.shutdown_custom_http_product_instance()

    @pytest.mark.parametrize("instance_name", ["custom_grpc_product_instance", "custom_http_product_instance"])
    def test_unshared_instance(
        self,
        instance_name: str,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test unshared instance with custom products. The unshare instance uses the product manager from transaction
        methods not decorated with @create_instance and @instance.
        """
        step = function_project.project.steps.custom_unshared_instance_step

        # GIVEN step field has default value
        assert step.value == "white"
        # WHEN using custom product unshared instance in a longrunning transaction
        getattr(step, f"assign_value_from_unshared_{instance_name}_long_running")().wait()
        # THEN step field has value retrieved from product
        assert step.value == "blue"

        # GIVEN step field has default value
        step.reset_value()
        assert step.value == "white"
        # WHEN using custom product unshared instance in a regular transaction
        getattr(step, f"assign_value_from_unshared_{instance_name}")()
        # THEN step field has value retrieved from product
        assert step.value == "blue"

    def test_unhealthy_product_cleaned_up(
        self,
        instance_system_type: TestProductInstanceSystemType,
        function_project: ProjectFixture[EndToEndSolution],
        get_hps_job_ids: GetHpsJobIdsType,
    ):
        """
        Test that a custom product instance is cleaned up if it is running but unhealthy.
        """
        if instance_system_type == TestProductInstanceSystemType.PIM:
            pytest.skip("Test not implemented for PIM.")

        # GIVEN instance with wrong service type
        step = function_project.project.steps.custom_http_shared_instance_step
        job_name = "custom-http-product-wrong-service-type-1-GLOW-Instance"
        old_aborted_job_ids = get_hps_job_ids(job_name, "aborted", [])

        # WHEN initializing unhealthy custom product instance
        with pytest.raises(InternalSolutionException):
            step.initialize_wrong_port_http_product().wait()

        # THEN a new job created by this test is aborted
        aborted_jobs_in_test = get_hps_job_ids(job_name, "aborted", old_aborted_job_ids)
        assert len(aborted_jobs_in_test) == 1

    def test_old_product_cleaned_up(
        self,
        instance_system_type: TestProductInstanceSystemType,
        function_project: ProjectFixture[EndToEndSolution],
        get_hps_job_ids: GetHpsJobIdsType,
    ):
        """
        Test that a custom product instance is cleaned up if recreated.
        """
        if instance_system_type == TestProductInstanceSystemType.PIM:
            pytest.skip("Test not implemented for PIM.")

        # GIVEN new project
        step = function_project.project.steps.custom_http_shared_instance_step
        job_name = "custom-http-product-1-GLOW-Instance"
        old_running_job_ids = get_hps_job_ids(job_name, "running", [])

        # WHEN initializing custom product instance
        step.initialize_custom_http_product_instance().wait()

        # THEN a new job is running
        running_job_ids_after_create = get_hps_job_ids(job_name, "running", old_running_job_ids)
        assert len(running_job_ids_after_create) == 1

        # WHEN recreating product instance
        step.initialize_custom_http_product_instance().wait()

        # THEN old job is aborted and a new one is created
        aborted_jobs_after_recreate = [
            job_id
            for job_id in get_hps_job_ids(job_name, "aborted", [])  # type: ignore
            if job_id == running_job_ids_after_create[0]  # type: ignore
        ]
        assert len(aborted_jobs_after_recreate) == 1
        running_jobs_after_recreate = get_hps_job_ids(job_name, "running", old_running_job_ids)
        assert len(running_jobs_after_recreate) == 1

        # shutdown product
        step.shutdown_custom_http_product_instance()

    def test_shared_instance_entity_handles_bdm(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that custom product instance managers can work with BDM EntityHandles. A file shall be provided to the
        product using the product manager storage scope.
        """
        # Initializing custom product instance
        step = function_project.project.steps.custom_http_shared_instance_step
        step.initialize_custom_http_product_instance().wait()
        project_files_directory = session_glow.project_files_directory
        project_directory = project_files_directory / function_project.project_id
        assert not any(project_directory.rglob("my_file.txt"))
        # Transaction that passes file through PRODUCT (retrieves value) -> TRANSACTION -> PROJECT
        assert step.value == "white"
        step.download_entity_handle_with_value_custom_http_product_instance()
        # Not using rglob because it sometimes raises a FileNotFoundError related to a GC path
        my_files = list(project_directory.glob("bdm/product*/my_file.txt"))
        assert len(my_files) == 1
        my_file_txt = my_files[0]
        assert my_file_txt.read_text() == "blue"
        step.retrieve_value_custom_http_product_instance()
        assert step.value == "blue"

        # Transaction that passes file through PROJECT -> TRANSACTION -> PRODUCT (sets value)
        my_file_txt.write_text("my_custom_value")
        step.upload_entity_handle_with_value_custom_http_product_instance()
        assert my_file_txt.read_text() == "my_custom_value"
        step.retrieve_value_custom_http_product_instance()
        assert step.value == "my_custom_value"

        # shutdown product
        step.shutdown_custom_http_product_instance()

    def test_unshared_instance_use_entity_handle_from_and_to_transaction(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that unshared instances can use EntityHandles.
        """
        # GIVEN: a step using unshared instance and no project files
        step = function_project.project.steps.custom_unshared_instance_step
        project_files_directory = session_glow.project_files_directory
        project_directory = project_files_directory / function_project.project_id
        assert not any(project_directory.rglob("my_file_input.txt"))
        assert not any(project_directory.rglob("my_file_output.txt"))
        # WHEN: using unshared product to create and use files using bdm both from transaction and product
        step.write_entity_handle_input()
        step.unshared_custom_http_entity_handle_to_and_from_transaction()
        # THEN: files exists and were used by product and transaction
        assert step.value == "black"
        my_file_input_in_project = next(project_directory.rglob("my_file_input.txt"))
        assert my_file_input_in_project.exists()
        my_file_output_in_project = next(project_directory.rglob("my_file_output.txt"))
        assert my_file_output_in_project.exists()
        assert my_file_output_in_project.read_text() == "black"

    def test_shared_instance_deleted_on_project_removal(
        self,
        get_hps_job_ids: GetHpsJobIdsType,
        instance_system_type: TestProductInstanceSystemType,
        function_client: Client[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        random_project_name: Callable[[], str],
    ):
        """
        Test that a custom shared product instance is removed if its project is deleted.
        """
        if instance_system_type == TestProductInstanceSystemType.PIM:
            pytest.skip("Test not implemented for PIM.")

        # GIVEN - project with running custom product instance
        job_name = "custom-http-product-1-GLOW-Instance"

        # GIVEN - two projects
        project1_display_name = random_project_name()
        temp_project1 = function_client.create_project(project1_display_name)

        project2_display_name = random_project_name()
        temp_project2 = function_client.create_project(project2_display_name)

        old_running_job_ids = get_hps_job_ids(job_name, "running", [])
        old_aborted_job_ids = get_hps_job_ids(job_name, "aborted", [])

        step1 = temp_project1.steps.custom_http_shared_instance_step
        step1.initialize_custom_http_product_instance().wait()

        running_job_ids_after_create_project1 = get_hps_job_ids(job_name, "running", old_running_job_ids)
        assert len(running_job_ids_after_create_project1) == 1

        step2 = temp_project2.steps.custom_http_shared_instance_step
        step2.initialize_custom_http_product_instance().wait()

        old_running_job_ids.append(running_job_ids_after_create_project1[0])

        running_job_ids_after_create_project2 = get_hps_job_ids(job_name, "running", old_running_job_ids)
        assert len(running_job_ids_after_create_project2) == 1

        # WHEN - removing the first project
        temp_project1.delete()

        # THEN - only its instance has been shutdown
        aborted_job_ids = get_hps_job_ids(job_name, "aborted", old_aborted_job_ids)
        assert len(aborted_job_ids) == 1
        assert running_job_ids_after_create_project1[0] == aborted_job_ids[0]

        # THEN - second project's product instance is still alive
        running_job_ids = get_hps_job_ids(job_name, "running", old_running_job_ids)
        assert len(running_job_ids) == 1
        assert running_job_ids_after_create_project2[0] == running_job_ids[0]

        # WHEN - restarting glow session
        session_glow.restart()

        # WHEN - removing the second project
        temp_project2.delete()

        # THEN - second project's product instance has been shutdown
        old_aborted_job_ids.append(aborted_job_ids[0])
        aborted_job_ids = get_hps_job_ids(job_name, "aborted", old_aborted_job_ids)
        assert len(aborted_job_ids) == 1
        assert aborted_job_ids[0] == running_job_ids_after_create_project2[0]

    def test_shared_instance_shutdown_with_concurrent_glow(
        self,
        get_hps_job_ids: GetHpsJobIdsType,
        instance_system_type: TestProductInstanceSystemType,
        get_glow_client: Callable[[GlowBaseProcess[EndToEndSolution]], Client[EndToEndSolution]],
        run_glow: Callable[[type[EndToEndSolution], Path], GlowBaseProcess[EndToEndSolution]],
        tmp_solutions_dir: dict[type[EndToEndSolution], Path],
        random_project_name: Callable[[], str],
    ):
        """
        Test that removing a project with an initialized instance only shuts down the instance associated with that
        project without stopping the instance with the same name on a different project.
        """
        if instance_system_type == TestProductInstanceSystemType.PIM:
            pytest.skip("Test not implemented for PIM.")

        job_name = "custom-http-product-1-GLOW-Instance"

        old_running_job_ids = get_hps_job_ids(job_name, "running", [])
        old_aborted_job_ids = get_hps_job_ids(job_name, "aborted", [])

        # GIVEN - two glow processes, the first one with a product instance
        glow_process_client_1 = get_glow_client(run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution]))
        project_display_name_1 = random_project_name()
        project_1 = glow_process_client_1.create_project(project_display_name_1)
        project_1.steps.custom_http_shared_instance_step.initialize_custom_http_product_instance().wait()

        running_job_ids = get_hps_job_ids(job_name, "running", old_running_job_ids)
        assert len(running_job_ids) == 1

        glow_process_client_2 = get_glow_client(run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution]))
        project_display_name_2 = random_project_name()
        project_2 = glow_process_client_2.create_project(project_display_name_2)

        # WHEN - removing the second project
        project_2.delete()

        # THEN - the first project's product instance is still running
        running_job_ids_after_removal = get_hps_job_ids(job_name, "running", old_running_job_ids)
        assert len(running_job_ids_after_removal) == 1
        assert running_job_ids_after_removal[0] == running_job_ids[0]

        project_1.delete()

        aborted_jobs_ids = get_hps_job_ids(job_name, "aborted", old_aborted_job_ids)
        assert len(aborted_jobs_ids) == 1
        assert aborted_jobs_ids[0] == running_job_ids[0]

    def test_shared_instance_deleted_within_transaction(
        self,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that an instance abruptly killed from within a transaction method can be re-initialized.
        """
        # GIVEN new project with initialized http product
        step = function_project.project.steps.custom_http_shared_instance_step
        step.initialize_custom_http_product_instance().wait()

        # WHEN changing product instance properties to red
        # but not saving the value onto the step
        step.set_red_custom_http_product_instance()

        # THEN: step has default value
        assert step.value == "white"

        # WHEN killing the product from the instance system
        with pytest.raises(InternalSolutionException):
            step.kill_product_directly_from_instance_system().wait()

        # THEN retrieving value from product, forcing to reinitialize the product instance and restore its state
        step.retrieve_value_custom_http_product_instance()
        assert step.value == "red"

        # shutdown product
        step.shutdown_custom_http_product_instance()

    def test_shared_instance_killed_externally(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test instance can be re-initialized after the product killed itself internally.
        """
        # GIVEN new project with initialized http product
        step = function_project.project.steps.custom_http_shared_instance_step

        step.initialize_custom_http_product_instance().wait()
        custom_product_state_file = next(function_project.project_files_dir.rglob("project.txt"))
        assert custom_product_state_file.is_file()

        # WHEN changing product instance properties to red
        # but not saving the value onto the step
        step.set_red_custom_http_product_instance()

        # THEN step has default value
        assert step.value == "white"

        # WHEN killing the product from itself
        with pytest.raises(InternalSolutionException):
            step.harakiri().wait()

        # THEN retrieving value from product, forcing to reinitialize the product instance and restore its state
        # retrieving value from product, forcing to reinitialize the product instance and restore its state
        for custom_product_state_file in function_project.project_files_dir.rglob("project.txt"):
            custom_product_state_file.write_text("overwrite_state_offline")
        step.retrieve_value_custom_http_product_instance()
        assert step.value == "overwrite_state_offline"
        assert session_glow.text_in_output("Restarting custom-http-product-instance")

        # shutdown product
        step.shutdown_custom_http_product_instance()

    def test_shared_instance_used_same_transaction_as_init(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that an instance can be accessed in the same create_instance decorated transaction it was created in.
        """
        step = function_project.project.steps.custom_http_shared_instance_step

        # GIVEN: solution with default value
        assert step.value == "white"

        # WHEN: Launching instance and using it in the same transaction
        step.initialize_custom_http_product_instance_and_use().wait()

        # THEN: value was correctly retrieved from product
        assert step.value == "blue"

        # shutdown product
        step.shutdown_custom_http_product_instance()

    def test_fields_upload_when_state_was_not_stored(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that a field is not uploaded when the product instance is killed during transaction.
        """
        step = function_project.project.steps.custom_http_shared_instance_step

        # GIVEN: solution with default value
        assert step.value == "white"

        # WHEN: Launching instance
        step.initialize_custom_http_product_instance().wait()

        # WHEN: changing the value and killing the instance
        # THEN: the transaction ends successfully
        step.change_value_custom_http_product_instance(val="brown")
        with pytest.raises(InternalSolutionException):
            step.retrieve_http_product_value_and_kill_instance().wait()

        # THEN: the changed value has not been uploaded
        assert step.value == "white"

    def test_concurrent_shared_instances(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
    ):
        """
        Test that custom products support two instances of the same product concurrently.
        """
        # Setup second project
        second_project = ProjectFixture(session_glow, function_client)

        # Launch instance with first project
        step_a = function_project.project.steps.custom_http_shared_instance_step
        step_a.initialize_custom_http_product_instance().wait()

        # Launch instance with second project
        step_b = second_project.project.steps.custom_http_shared_instance_step
        step_b.initialize_custom_http_product_instance().wait()

        # Use both instances with regular and longrunning transactions using different inputs, make sure
        # steps execution is not synchronized between both projects, so
        # avoid pattern: call f1 in project1, call f1 in project2, call f2 in project1, call f2 in project2, etc.
        step_a.value = "custom_value_a"
        step_b.value = "custom_value_b"
        step_a.change_value_custom_http_product_instance()
        method = step_a.compute_value_custom_http_product_instance_lr()
        step_b.change_value_custom_http_product_instance()
        step_b.compute_value_custom_http_product_instance_lr().wait()
        step_b.retrieve_value_custom_http_product_instance()
        method.wait()
        step_a.retrieve_value_custom_http_product_instance()

        assert step_a.value == "custom_value_acustom_value_a"
        step_b = second_project.project.steps.custom_http_shared_instance_step
        assert step_b.value == "custom_value_bcustom_value_b"

        # shutdown products
        step_a.shutdown_custom_http_product_instance()
        step_b.shutdown_custom_http_product_instance()

        second_project.project.delete()

    def test_product_instance_can_resolve_decrypted_asset_handle(
        self,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that a product instance can resolve decrypted asset entity handle by
        using get_cached.
        """
        step = function_project.project.steps.custom_http_shared_instance_step
        # WHEN: initializing a product instance
        step.initialize_custom_http_product_instance().wait()
        # AND: accessing a decrypted asset file from a product storage scope
        step.store_decrypted_asset_from_product()
        step.retrieve_value_custom_http_product_instance()
        asset_path = Path(step.value)
        # THEN: the asset file is copied to the product cache
        uuid_regex = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        assert re.match(
            rf"{function_project.project_files_dir.as_posix()}/is_\w{{8}}/.product_cache/{uuid_regex}/asset_file1.txt",
            asset_path.as_posix(),
        )
        # AND: it still exists at the end of the transaction
        assert asset_path.exists()
        step.shutdown_custom_http_product_instance()
        assert not asset_path.exists()

    def test_product_instance_store_file_from_state_directory(
        self,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that a product instance can store a file from the state directory
        and that it is being copied over the storage root.
        """
        step = function_project.project.steps.custom_http_shared_instance_step
        # WHEN: initializing a product instance
        step.initialize_custom_http_product_instance().wait()
        # AND: storing a file from the product state directory
        step.store_from_product_state_dir()
        client_scope = function_project.project.storage_scope
        state_entity_path = client_scope.get_cached(step.state_entity_handle)
        # THEN: the entity handle references an existing state file within the product storage scope
        assert state_entity_path.read_text() == "blue"
        # AND: it has been copied over within the product storage scope
        assert re.match(
            rf"{function_project.project_files_dir.as_posix()}/bdm/product_\w{{8}}/project.txt",
            state_entity_path.as_posix(),
        )
        # AND: it still exists after the product is shutdown
        step.shutdown_custom_http_product_instance()
        assert state_entity_path.exists()

    def test_product_instance_store_dir_from_state_directory(
        self,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that a product instance can store a directory from the state directory
        and that it is being copied over the storage root.
        """
        step = function_project.project.steps.custom_http_shared_instance_step
        # WHEN: initializing a product instance
        step.initialize_custom_http_product_instance().wait()
        # AND: storing a directory from the product state directory
        step.store_dir_from_product_state_dir()
        client_scope = function_project.project.storage_scope
        child_entity = client_scope.get_child(step.state_entity_handle, "project.txt")
        state_entity_path = client_scope.get_cached(child_entity)
        # THEN: the entity handle references an existing state file within the product storage scope
        assert state_entity_path.read_text() == "blue"
        # AND: it has been copied over within the product storage scope
        assert re.match(
            rf"{function_project.project_files_dir.as_posix()}/bdm/product_\w{{8}}/dir/project.txt",
            state_entity_path.as_posix(),
        )
        # # AND: it still exists after the product is shutdown
        step.shutdown_custom_http_product_instance()
        assert state_entity_path.exists()


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize("deployment_type", ["Desktop"], indirect=True)
def test_custom_product_instance_shutdown_with_concurrent_glow_same_project(
    get_hps_job_ids: GetHpsJobIdsType,
    get_glow_client: Callable[[GlowBaseProcess[EndToEndSolution]], Client[EndToEndSolution]],
    run_glow: Callable[[type[EndToEndSolution], Path], GlowBaseProcess[EndToEndSolution]],
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
    random_project_name: Callable[[], str],
):
    """
    Test that deleting a project from a second glow process will also shut down the instance which was created on that
    same project from a different glow process.

    This test is Desktop only because our current testing containers don't share their database.
    """
    job_name = "custom-http-product-1-GLOW-Instance"

    old_running_job_ids = get_hps_job_ids(job_name, "running", [])
    old_aborted_job_ids = get_hps_job_ids(job_name, "aborted", [])

    # GIVEN - two glow processes, the first one with a product instance
    # and both open the same project
    glow_process_client_1 = get_glow_client(run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution]))
    project_display_name_1 = random_project_name()
    project_1 = glow_process_client_1.create_project(project_display_name_1)
    project_1.steps.custom_http_shared_instance_step.initialize_custom_http_product_instance().wait()

    running_job_ids = get_hps_job_ids(job_name, "running", old_running_job_ids)
    assert len(running_job_ids) == 1

    glow_process_client_2 = get_glow_client(run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution]))
    project_2 = glow_process_client_2.get_project(project_1.project_name)

    # WHEN - removing the project from the second glow process
    project_2.delete()

    # THEN - the product instance created by the first glow process
    # is aborted when the project is removed from the second glow process
    aborted_jobs_ids = get_hps_job_ids(job_name, "aborted", old_aborted_job_ids)
    assert len(aborted_jobs_ids) == 1
    assert aborted_jobs_ids[0] == running_job_ids[0]


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
# @pytest.mark.parametrize("deployment_type", ["Desktop"], indirect=True)
def test_custom_product_instance_on_hps_with_compiled_glow(
    run_glow: Callable[..., GlowBaseProcess[EndToEndSolution]],
    get_glow_client: Callable[[GlowBaseProcess[EndToEndSolution]], Client[EndToEndSolution]],
    obfuscated_glow_source: Path,
    random_project_name: Callable[[], str],
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
):
    """
    Test that it is possible to run a product instance on HPS when GLOW / dependencies are compiled.
    """
    # GIVEN: a project created with a compiled GLOW process
    deps = PACKAGE_ROOT / ".venv" / "Lib" / "site-packages"
    glow_and_deps = obfuscated_glow_source.as_posix() + os.pathsep + deps.as_posix()
    glow_process = run_glow(
        EndToEndSolution,
        tmp_solutions_dir[EndToEndSolution],
        obfuscated_glow_pythonpath=glow_and_deps,
    )
    assert glow_process.healthy
    client = get_glow_client(glow_process)
    project = client.create_project(random_project_name())
    step = project.steps.custom_http_shared_instance_step

    # THEN: ensure GLOW is compiled
    assert not step.is_glow_src_readable()

    # THEN: the product instance can be used
    step.initialize_custom_http_product_instance().wait()
    assert step.value == "white"
    step.retrieve_value_custom_http_product_instance()
    assert step.value == "blue"


@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host"),
    [
        ("Desktop", None, None),
        ("Desktop", None, "127.0.0.1"),
        pytest.param("DockerCompose", "host.docker.internal", None, marks=pytest.mark.use_containerized),
        pytest.param("DockerCompose", "host.docker.internal", DOCKER_GATEWAY_IP, marks=pytest.mark.use_containerized),
    ],
    ids=["desktop_insecure", "desktop_custom_host", "dockercompose_insecure", "dockercompose_custom_host"],
    indirect=True,
)
def test_default_binding_host_in_insecure_product_configs(
    instance_system_type: TestProductInstanceSystemType,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    session_pim: PimProcess,
    product_host: str | None,
    product_binding_host: str | None,
    get_hps_job_ids: GetHpsJobIdsType,
    get_hps_job_output: Callable[[str], list[str]],
):
    """Test that product_binding_host is configurable in insecure products and it defaults to 0.0.0.0 instead of
    localhost."""
    step = function_project.project.steps.custom_grpc_shared_instance_step

    job_name = "custom-grpc-product-custom-host-1-GLOW-Instance"
    old_job_ids = []
    if instance_system_type == TestProductInstanceSystemType.HPS:
        old_job_ids = get_hps_job_ids(job_name, "all", [])

    step.initialize_custom_host_grpc_product_instance().wait()
    step.shutdown_custom_host_grpc_product_instance()

    bind_host = product_binding_host or "0.0.0.0"
    if instance_system_type == TestProductInstanceSystemType.PIM:
        assert session_pim.find_msg_in_output(f"--host,{bind_host},--version,1")
    else:
        job_ids = get_hps_job_ids(job_name, "all", old_job_ids)
        assert len(job_ids) == 1
        job_output = "\n".join(get_hps_job_output(job_ids[0]))
        assert f"--host {bind_host} --version 1" in job_output

    product_host = product_host or (
        "127.0.0.1" if instance_system_type == TestProductInstanceSystemType.PIM else "localhost"
    )
    assert session_glow.text_in_output(f"Health check: creating insecure grpc channel with uri={product_host}", "api")
