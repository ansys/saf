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

import asyncio
import threading
import time

import httpx2
import pytest

from ansys.saf.glow.client import BadRequestException, InternalSolutionException
from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    DefaultDebug,
    EnvVarDebug,
    GlowBaseProcess,
    ProjectFixture,
)
from tests.e2e.conftest import ChildCleanupConfiguration, DisableChildCleanupConfiguration
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    LOGGING_ERROR_TESTING_STRING,
    LOGGING_INFO_TESTING_STRING,
    CustomTypeXYZ,
)

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)

EXCEPTION_TYPES = ["Exception", "RuntimeError", "BadRequestError", "ModuleNotFoundError"]
EXCEPTION_MESSAGES = {
    "Exception": "test exception message",
    "RuntimeError": "other test message",
    "BadRequestError": "another original test message",
    "ModuleNotFoundError": "No module named 'wrong_module'",
}


@pytest.fixture
def debug_mode(debug: bool, session_glow: GlowBaseProcess[EndToEndSolution]):
    """Modifies the debug mode for a single test and returns to the former configuration after."""
    debug_config_altered = False
    session_glow_debug_config_type = session_glow.applied_configurations.get("debug_configuration", None)

    if debug:
        if not session_glow_debug_config_type or not isinstance(session_glow_debug_config_type, EnvVarDebug):
            session_glow.change_configuration(EnvVarDebug)
            debug_config_altered = True
    else:
        if not session_glow_debug_config_type or not isinstance(session_glow_debug_config_type, DefaultDebug):
            session_glow.change_configuration(DefaultDebug)
            debug_config_altered = True

    yield

    if debug_config_altered and session_glow_debug_config_type:
        session_glow.change_configuration(type(session_glow_debug_config_type))


@pytest.fixture
def no_child_cleanup(session_glow: GlowBaseProcess[EndToEndSolution]):
    session_glow.change_configuration(DisableChildCleanupConfiguration)
    yield
    session_glow.change_configuration(ChildCleanupConfiguration)


@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestTransactions:
    def test_upload_and_download(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test if a transaction can download multiple numeric fields as input and upload its output as a result.
        """
        step = function_project.project.steps.transaction_verification_step

        assert step.result != 3.0
        step.field_1 = 1
        step.field_2 = 2
        step.get_field_1_and_2_and_set_the_sum_in_result()
        assert step.result == 3.0

    def test_data_persists_after_glow_restart(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """
        Test if project data persists after a GLOW session restart.
        """

        def verify_restart_glow() -> None:
            """Restart GLOW process and verify that it has spawned a new process,
            different than the older one."""
            old_glow_process = session_glow.api_process
            assert old_glow_process
            session_glow.restart()
            new_glow_process = session_glow.api_process
            assert new_glow_process
            assert old_glow_process != new_glow_process

        step = function_project.project.steps.transaction_verification_step

        assert step.result != 4.0
        step.field_1 = 2
        step.field_2 = 2
        step.get_field_1_and_2_and_set_the_sum_in_result()

        verify_restart_glow()

        assert step.result == 4.0

    @pytest.mark.parametrize(
        ("method_name", "log_string"),
        [("log_an_error", LOGGING_ERROR_TESTING_STRING), ("log_some_info", LOGGING_INFO_TESTING_STRING)],
    )
    def test_error_and_info_logs(
        self,
        method_name: str,
        log_string: str,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """
        Test if a transaction can log ERROR and INFO messages and return the right status code.
        """
        method = getattr(function_project.project.steps.transaction_verification_step, method_name)
        method()
        assert session_glow.text_in_output(log_string, "api")

    @pytest.mark.usefixtures("debug_mode")
    @pytest.mark.parametrize(("debug"), [False, True])
    @pytest.mark.parametrize("exception_type", EXCEPTION_TYPES)
    def test_transaction_exceptions(
        self,
        exception_type: str,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        debug: bool,
        request: pytest.FixtureRequest,
    ):
        """
        Test that the right exceptions message and status code are returned for generic exceptions and run-time
        errors.
        """
        exception_message = EXCEPTION_MESSAGES[exception_type]
        if exception_type == "BadRequestError":
            # 4XX Responses
            exception_class = BadRequestException
            client_exception_message = exception_message
        else:
            # 5XX Responses
            exception_class = InternalSolutionException
            client_exception_message = (
                exception_message
                if debug
                else "The solution encountered an internal error and was unable to complete the request. "
            )

        step = function_project.project.steps.transaction_verification_step
        step.exception_type = exception_type
        step.exception_message = exception_message

        with pytest.raises(exception_class, match=client_exception_message):
            step.raise_exception()

        # This happens regardless of debug mode.
        assert session_glow.text_in_output(["_executor.method_runner", exception_message], "api")

        # Server logging depends on debug mode.
        error_logged = session_glow.text_in_output(["[ansys.saf.glow._server.server]", exception_message], "api")
        generic_message_logged = session_glow.text_in_output(
            [
                "[ansys.saf.glow._server.server]",
                "The solution encountered an internal error and was unable to complete the request.",
            ],
            "api",
        )

        if debug or exception_type == "BadRequestError":
            assert error_logged
            assert not generic_message_logged
        else:
            assert not error_logged
            assert generic_message_logged

    @pytest.mark.usefixtures("debug_mode")
    @pytest.mark.parametrize(("debug"), [False, True])
    def test_long_running_subprocess_is_terminated_after_transaction_finishes(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        debug: bool,
    ):
        """Test if a subprocess spawn by a long running transaction is terminated correctly after the transaction
        finishes.
        """
        step = function_project.project.steps.transaction_verification_step

        step.check_child_process_is_running()
        assert not step.child_process_is_running

        # Run long-running transaction that internally launches a subprocess and doesn't wait for it to finish
        step.start_process_in_long_running_method().wait()
        assert step.child_process_pid != -1
        assert session_glow.text_in_output(
            ["INFO", "Cleaning up child process(es) still alive after transaction", str(step.child_process_pid)],
            "api",
        )
        if debug:
            # The child PID was tracked by the framework (collected before the worker process exited) and killed
            assert session_glow.text_in_output(
                [
                    "DEBUG",
                    "Tracking child PIDs at end of transaction",
                    str(step.child_process_pid),
                    "Will allow them to terminate gracefully before forcing cleanup.",
                ],
                "api",
            )
            assert session_glow.text_in_output(
                ["DEBUG", f"Killing child process (pid: {step.child_process_pid})"],
                "api",
            )

        # Check that process is not alive
        step.check_child_process_is_running()
        assert not step.child_process_is_running

    @pytest.mark.usefixtures("debug_mode")
    @pytest.mark.parametrize(("debug"), [True])
    def test_long_running_subprocess_is_gracefully_terminated_after_worker_process_exits(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """Test that a subprocess launched in a long-running transaction and gracefully terminated by its spawner
        when the ProcessPoolExecutor worker process exits, it's not being killed previously by GLOW.
        """
        step = function_project.project.steps.transaction_verification_step

        step.check_child_process_is_running()
        assert not step.child_process_is_running

        step.start_and_teardown_process_in_long_running_method().wait()
        assert step.child_process_pid != -1

        # The child PID was tracked by the framework (collected before the worker process exited)
        assert session_glow.text_in_output(
            [
                "DEBUG",
                "Tracking child PIDs at end of transaction",
                str(step.child_process_pid),
                "Will allow them to terminate gracefully before forcing cleanup.",
            ],
            "api",
        )
        # and killed by the atexit handler, not by the framework's child cleanup logic.
        assert session_glow.text_in_output(
            ["INFO", "Gracefully terminating subprocess with PID", str(step.child_process_pid)],
            "api",
        )
        # The atexit handler already terminated it when the worker process shut down, so no cleanup was needed.
        assert not session_glow.text_in_output("Cleaning up child process(es) still alive after transaction", "api")

        # Check that process is not alive
        step.check_child_process_is_running()
        assert not step.child_process_is_running

    @pytest.mark.usefixtures("debug_mode")
    @pytest.mark.parametrize(("debug"), [False, True])
    @pytest.mark.usefixtures("no_child_cleanup")
    def test_long_running_subprocess_is_not_terminated_after_transaction_finishes_if_cleanup_disabled(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        debug: bool,
        deployment_type: TestDeployment,
    ):
        """Test that a subprocess spawn by a long running transaction is not terminated after the transaction
        finishes when child cleanup is disabled, instead it's logged as a warning. Launching other transactions
        will not clean it up, not even restarting GLOW.
        """
        step = function_project.project.steps.transaction_verification_step

        step.check_child_process_is_running()
        assert not step.child_process_is_running

        # Run long-running transaction that internally launches a subprocess and doesn't wait for it to finish
        step.start_process_in_long_running_method().wait()
        assert step.child_process_pid != -1
        assert session_glow.text_in_output(
            [
                "WARNING",
                "Child process cleanup is disabled. PIDs still alive after transaction",
                str(step.child_process_pid),
            ],
            "api",
        )
        if debug:
            # The child PID was tracked by the framework (collected before the worker process exited)
            assert session_glow.text_in_output(
                [
                    "DEBUG",
                    "Tracking child PIDs at end of transaction",
                    str(step.child_process_pid),
                    "Will allow them to terminate gracefully before forcing cleanup.",
                ],
                "api",
            )

        # Check that process is alive
        step.check_child_process_is_running()
        assert step.child_process_is_running

        # Run another sync transaction method
        step.field_1 = 3
        step.field_2 = 5
        step.get_field_1_and_2_and_set_the_sum_in_result()
        assert step.result == (3 + 5)

        # Check that process is still alive
        step.check_child_process_is_running()
        assert step.child_process_is_running

        # Run another long-running transaction method
        step.field_1 = 4
        step.field_2 = 6
        step.lr_get_field_1_and_2_and_set_the_sum_in_result().wait()
        assert step.result == (4 + 6)

        # Check that process is still alive
        step.check_child_process_is_running()
        assert step.child_process_is_running

        # Restart glow and check that the process is still alive
        session_glow.restart()
        step.check_child_process_is_running()
        if deployment_type == TestDeployment.DockerCompose:
            # when containerized, the process ends because the whole container is restarted.
            assert not step.child_process_is_running
        else:
            assert step.child_process_is_running

            # force cleanup
            step.kill_process()
            step.check_child_process_is_running()
            assert not step.child_process_is_running

    def test_sync_transaction_subprocess_is_terminated_after_solution_is_closed(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """Test that the process started by a synchronous transaction is not killed after the transaction completes
        and cannot be killed due to the execution of another synchronous or long-running transaction.
        Test that it is killed after a GLOW session restart.
        """
        step = function_project.project.steps.transaction_verification_step

        step.check_child_process_is_running()
        assert not step.child_process_is_running

        # Run sync transaction that internally launches a subprocess and doesn't wait for it to finish
        step.start_process()
        assert step.child_process_pid != -1

        # Check that process is still alive
        step.check_child_process_is_running()
        assert step.child_process_is_running

        # Run another sync transaction method
        step.field_1 = 3
        step.field_2 = 5
        step.get_field_1_and_2_and_set_the_sum_in_result()
        assert step.result == (3 + 5)

        # Check that process is still alive
        step.check_child_process_is_running()
        assert step.child_process_is_running

        # Run another long-running transaction method
        step.field_1 = 4
        step.field_2 = 6
        step.lr_get_field_1_and_2_and_set_the_sum_in_result().wait()
        assert step.result == (4 + 6)

        # Check that process is still alive
        step.check_child_process_is_running()
        assert step.child_process_is_running

        # Restart glow and check that the process is no longer alive
        session_glow.restart()
        step.check_child_process_is_running()
        assert not step.child_process_is_running

    @pytest.mark.parametrize("max_number_of_workers", [1], indirect=True)
    async def test_api_fulfills_requests_after_sync_blocking_method(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """
        Test that requests submitted during a blocking method are resolved after the blockage finishes.
        """

        async def get_projects(async_client: httpx2.AsyncClient, url: str) -> httpx2.Response:
            response = await async_client.get(url=url, timeout=None)
            return response

        step = function_project.project.steps.transaction_verification_step

        # call sync transaction in a separate thread so we can launch other requests in parallel
        step.sleepy_seconds = 5
        invoke_thread = threading.Thread(target=step.block_process)
        invoke_thread.start()

        # We use a project file for sync between transaction and test.
        # Using a step field is not possible since the API is going to stop responding requests
        # once the block starts.
        file_path = function_project.project_files_dir / "gil_lock.txt"
        tries = 0
        while (not file_path.is_file() or file_path.read_text() != "GIL LOCKED") and tries < 50:
            tries += 1
            await asyncio.sleep(0.1)
        assert file_path.read_text() == "GIL LOCKED"
        # even if the text contains the expected message, there is a delay until the GIL is actually locked
        await asyncio.sleep(0.5)

        # Make requests asynchronously during solver method execution
        responses: list[httpx2.Response] = []
        async with httpx2.AsyncClient() as client:
            responses = await asyncio.gather(
                *[get_projects(client, f"{session_glow.base_api_url}/projects") for _ in range(20)],
            )

        invoke_thread.join()
        assert step.get_method_state("block_process").status == MethodStatus.Completed

        # Check that requests were not resolved until the solver transaction ended
        assert len(responses) == 20
        for response in responses:
            assert response.elapsed.total_seconds() > 4
            assert response.status_code == 200

    def test_api_fulfills_requests_during_long_running_blocking_method(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """
        Test that the API can resolve requests while a long_running method is running.
        """
        step = function_project.project.steps.transaction_verification_step
        step.sleepy_seconds = 5
        step.block_process_long_running()

        # We can use a step field to sync between the transaction and this test, because
        # we expect the API to be responsive once the block starts.
        tries = 0
        while step.text_content != "GIL LOCKED" and tries < 50:
            tries += 1
            time.sleep(0.1)

        # Check that every request done during blocking method is responded shortly after
        num_requests = 0
        while step.get_long_running_method_state("block_process_long_running").status == MethodStatus.Running:
            try:
                num_requests += 1
                httpx2.get(f"{session_glow.base_api_url}/projects", timeout=2)
            except httpx2.TimeoutException:
                pytest.fail("GLOW API did not reply on time")
            time.sleep(0.2)
        assert num_requests > 0
        assert step.get_long_running_method_state("block_process_long_running").status == MethodStatus.Completed

    def test_transaction_non_stored_inputs_and_outputs_client(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that transactions now allow to specify inputs and outputs that are not stored as part of the project state.
        """

        x, y, z = 3, 4, 5
        expected_result = CustomTypeXYZ(x=x, y=y**2, z=z)

        step = function_project.project.steps.transaction_verification_step

        step.process_input_before_uploading(y=y)  # y = y**2
        output = step.build_and_return_custom_type(x=x, z=z)
        step.store_custom_type_from_client(ct=output)

        assert step.custom_object == expected_result
