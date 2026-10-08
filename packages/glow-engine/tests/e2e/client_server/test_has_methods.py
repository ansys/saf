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

from collections.abc import Generator
from multiprocessing.pool import ThreadPool
import time

import httpx2
import pytest
from starlette import status

from ansys.saf.glow.client import (
    BadRequestException,
    ConflictException,
    InternalSolutionException,
    LongRunning,
    NotFoundException,
)
from ansys.saf.glow.solution import (
    MethodState,
    MethodStatus,
    StepModel,
)
from ansys.saf.testing.platform_specific import xfail_for_ci
from ansys.saf.testing.solution.end_to_end import EnvVarDebug, GlowBaseProcess, ProjectFixture
from tests.mocks.solutions.has_methods import HasMethods

pytestmark = pytest.mark.parametrize("solution_type", [HasMethods], indirect=True)


@pytest.fixture
def enable_debug_mode(session_glow: GlowBaseProcess[HasMethods]) -> Generator[None, None, None]:
    session_glow.change_configuration(EnvVarDebug)
    yield
    session_glow.configure_default_execution()


def test_has_methods_step_schema_use_docstring(
    session_glow: GlowBaseProcess[HasMethods],
):
    """Tests that MethodStep schema use docstring as documentation."""
    url = f"{session_glow.base_api_url}/openapi.json"
    r = httpx2.get(url)

    assert r.json()["components"]["schemas"]["MethodStep"]["description"] == "This is a step for testing purpose."


def test_has_methods_publish_methods_use_docstring(
    session_glow: GlowBaseProcess[HasMethods],
):
    """Tests that methods with @long_running use docstring as documentation."""
    url = f"{session_glow.base_api_url}/openapi.json"
    r = httpx2.get(url)

    assert (
        r.json()["paths"]["/projects/{project_id}/steps/method-step:increment"]["post"]["description"]
        == "Increment x by one."
    )


def test_project_create_for_another_solution(function_project: ProjectFixture[HasMethods]):
    pass


def test_custom_method_can_be_invoked(function_project: ProjectFixture[HasMethods]):
    step = function_project.project.steps.method_step
    step.increment()
    assert function_project.project.steps.method_step.x == 100


def test_custom_method_with_underscore_in_name_can_be_invoked(function_project: ProjectFixture[HasMethods]):
    step = function_project.project.steps.method_step
    step.do_underscore()
    assert function_project.project.steps.method_step.x == 102


def test_hidden_method_cannot_be_invoked(function_project: ProjectFixture[HasMethods]):
    step = function_project.project.steps.method_step
    with pytest.raises(
        AttributeError,
        match=(
            "'MethodStep.hidden' has no '@transaction' decorator and therefore cannot be called.\n"
            "Possible methods are: "
            "act_on_another_step, bang, do_underscore, empty_return, increment, one_second, one_second_sync, "
            "slow, slow_exception, two_seconds."
        ),
    ):
        step.hidden()


def test_custom_method_that_raises_exception_on_server_triggers_malformed_solution_exception_on_client(
    session_glow: GlowBaseProcess[HasMethods],
    function_project: ProjectFixture[HasMethods],
):
    if session_glow.debug_mode_override:
        pytest.skip("This test should only be run in non debug mode; another test is asserting the debug mode.")
    step = function_project.project.steps.method_step
    with pytest.raises(
        InternalSolutionException,
        match="The solution encountered an internal error and was unable to complete the request.",
    ):
        step.bang()


@pytest.mark.usefixtures("enable_debug_mode")
def test_custom_method_that_raises_exception_on_server_triggers_malformed_solution_exception_on_client_debug(
    function_project: ProjectFixture[HasMethods],
):
    step = function_project.project.steps.method_step
    with pytest.raises(
        InternalSolutionException,
        match="BANG!",
    ) as e:
        step.bang()
    message = str(e.value)
    traces = message.split("Traceback")
    first_trace = traces[1]
    assert "RuntimeError: BANG!" in first_trace
    assert 'raise RuntimeError("BANG!")' in first_trace
    assert "has_methods.py" in first_trace
    assert "in bang" in first_trace


def _check_async_no_exception_state(
    step: StepModel,
    expected_statuses: list[MethodStatus],
    method_id: str = "slow",
) -> MethodStatus:
    state = step.get_long_running_method_state(method_id)
    assert state.exception_message is None
    assert state.exception_stack is None
    assert state.status in expected_statuses
    return state.status


def _wait_and_check_result_of_async_method(project: HasMethods, method_id: str = "slow") -> None:
    step = project.steps.method_step
    getattr(step, method_id)()
    while (
        _check_async_no_exception_state(step, [MethodStatus.Running, MethodStatus.Completed], method_id)
        == MethodStatus.Running
    ):
        time.sleep(0.2)


def test_async_method_initially_has_never_started_status(function_project: ProjectFixture[HasMethods]):
    step = function_project.project.steps.method_step
    _check_async_no_exception_state(step, [MethodStatus.RunRequired])


def test_invoking_async_method_puts_the_method_into_running_then_completed_status(
    function_project: ProjectFixture[HasMethods],
):
    _wait_and_check_result_of_async_method(function_project.project)


def _wait_and_check_result_of_exception_throwing_async_method(project: HasMethods):
    step = project.steps.method_step
    step.slow_exception()
    while step.get_long_running_method_state("slow_exception").status == MethodStatus.Running:
        time.sleep(0.2)
    state = step.get_long_running_method_state("slow_exception")
    assert state.status == MethodStatus.Failed
    assert state.exception_message == "Bang! Bang!"
    assert state.exception_stack is not None
    assert 'raise BadRequestError("Bang! Bang!")' in state.exception_stack
    assert "has_methods.py" in state.exception_stack
    assert "in slow_exception" in state.exception_stack


@pytest.mark.usefixtures("enable_debug_mode")
def test_invoking_exception_raising_async_method_puts_the_method_into_running_then_failed_status(
    function_project: ProjectFixture[HasMethods],
):
    _wait_and_check_result_of_exception_throwing_async_method(function_project.project)


def test_get_long_running_method_state_raises_not_found_exception_if_method_is_not_asynchronous(
    function_project: ProjectFixture[HasMethods],
):
    step = function_project.project.steps.method_step
    with pytest.raises(NotFoundException, match="increment is not a long running method on method_step"):
        step.get_long_running_method_state("increment")


def test_invoking_async_method_for_a_second_time_raises_a_conflict_exception(
    function_project: ProjectFixture[HasMethods],
):
    step = function_project.project.steps.method_step
    step.slow_exception()
    with pytest.raises(ConflictException, match="slow_exception is already running"):
        step.slow_exception()
    while step.get_long_running_method_state("slow_exception").status == MethodStatus.Running:
        time.sleep(0.5)


def test_invoking_async_again_after_completion_puts_method_into_running_state_again(
    function_project: ProjectFixture[HasMethods],
):
    project = function_project.project
    _wait_and_check_result_of_async_method(project)
    _wait_and_check_result_of_async_method(project)


@pytest.mark.usefixtures("enable_debug_mode")
def test_invoking_async_again_after_failure_puts_method_into_running_state_again(
    function_project: ProjectFixture[HasMethods],
):
    project = function_project.project
    _wait_and_check_result_of_exception_throwing_async_method(project)
    _wait_and_check_result_of_exception_throwing_async_method(project)


def test_has_method_can_be_invoked(function_project: ProjectFixture[HasMethods]):
    step = function_project.project.steps.method_step
    step.increment()
    assert function_project.project.steps.method_step.x == 100


def test_invoking_async_method_has_the_expected_side_effect(
    function_project: ProjectFixture[HasMethods],
):
    _wait_and_check_result_of_async_method(function_project.project)
    assert function_project.project.steps.method_step.x == 103


def test_invoking_async_method_has_the_expected_side_effect_on_another_step(
    function_project: ProjectFixture[HasMethods],
):
    _wait_and_check_result_of_async_method(function_project.project, "act_on_another_step")
    assert function_project.project.steps.another_step.x == 88
    assert function_project.project.steps.method_step.x == 89


@xfail_for_ci(reason="fails with 3.12 consistently in github-hosted windows runners. OK locally.")
def test_long_running_wait_timeout_raises_exception(
    function_project: ProjectFixture[HasMethods],
):
    step = function_project.project.steps.method_step
    long_running: LongRunning = step.two_seconds()  # type: ignore
    with pytest.raises(TimeoutError, match="Waiting for the long running method 'two_seconds' timed out."):
        long_running.wait(1)
    # Need to wait for the method process to be completed otherwise the
    # teardown will fail due to permission error to cleanup the project files.
    long_running.wait(10)


def test_long_running_wait_for_completion(
    function_project: ProjectFixture[HasMethods],
):
    step = function_project.project.steps.method_step
    long_running: LongRunning = step.one_second()  # type: ignore
    long_running.wait()
    assert step.get_long_running_method_state("one_second").status == MethodStatus.Completed


def test_long_running_wait_on_failed_method_raise_error(
    function_project: ProjectFixture[HasMethods],
):
    step = function_project.project.steps.method_step
    long_running: LongRunning = step.slow_exception()  # type: ignore
    with pytest.raises(BadRequestException, match="Bang! Bang!"):
        long_running.wait()


def test_long_running_is_complete(
    function_project: ProjectFixture[HasMethods],
):
    step = function_project.project.steps.method_step
    long_running: LongRunning = step.two_seconds()  # type: ignore
    is_complete = long_running.is_complete()
    assert not is_complete
    long_running.wait()
    is_complete = long_running.is_complete()
    assert is_complete


def _check_no_exception_state(step: StepModel, expected_statuses: list[MethodStatus], method_id: str) -> MethodStatus:
    state: MethodState = step.get_method_state(method_id)  # type: ignore
    assert state.exception_message is None
    assert state.exception_stack is None
    assert state.status in expected_statuses
    return state.status


@pytest.mark.parametrize("method_id", ["increment", "one_second", "slow"])
def test_get_method_state(
    method_id: str,
    function_project: ProjectFixture[HasMethods],
):
    step = function_project.project.steps.method_step

    status: MethodStatus = _check_no_exception_state(step, [MethodStatus.RunRequired], method_id)

    method = getattr(step, method_id)
    method()
    while status not in [MethodStatus.Completed, MethodStatus.Failed]:
        time.sleep(0.1)
        status = step.get_method_state(method_id).status

    _check_no_exception_state(step, [MethodStatus.Completed], method_id)


@xfail_for_ci(reason="Flaky")
@pytest.mark.parametrize("execution_number", range(3))
def test_invoking_async_method_concurrently_raises_a_conflict_exception(
    session_glow: GlowBaseProcess[HasMethods],
    execution_number: int,
    function_project: ProjectFixture[HasMethods],
):
    # log should be clean
    session_glow.clear_output()

    # Values found heuristically, that consistently make it fail without the fix.
    # Also, repeating it 3 times to reduce the probability of passing it by mistake.
    method_url = f"{function_project.url}/steps/method-step:two-seconds"
    with ThreadPool(4) as p:
        responses = p.map(httpx2.post, [method_url] * 50, chunksize=1)

    # We cannot rely on all 50 requests being done before the first transaction finishes, so
    # we parse the log to check that everything is correct and count the right amount of transactions
    # that were executed:
    # - If a request starts, only allowed if there is no running method or if it's the same already running request
    # (we set the value to running twice for the same request)
    # - If a request fails to start, only allowed if there is already a running method and it's a different request
    # - If a request ends, only allowed if it's the same request as the one that it was running
    executed_requests = 0
    current_method_trace: str | None = None
    for line in session_glow.api_output:
        if "method_step:two_seconds with status=<MethodStatus.Running: 'running'>" in line:
            trace_id = line.split("trace_id=")[1].split(" ")[0]
            if not current_method_trace:
                executed_requests += 1
                current_method_trace = trace_id
            else:
                assert current_method_trace == trace_id
        if "two_seconds is already running" in line:
            trace_id = line.split("trace_id=")[1].split(" ")[0]
            assert current_method_trace
            assert current_method_trace != trace_id
        if "method_step:two_seconds with status=<MethodStatus.Completed: 'completed'>" in line:
            trace_id = line.split("trace_id=")[1].split(" ")[0]
            assert current_method_trace
            assert current_method_trace == trace_id
            current_method_trace = None

    assert sum([1 for resp in responses if resp.status_code == status.HTTP_200_OK]) == executed_requests
    assert sum([1 for resp in responses if resp.status_code == status.HTTP_409_CONFLICT]) == (50 - executed_requests)


def simulate_concurrent_method_calls(method_url: str) -> httpx2.Response:
    return httpx2.post(method_url, timeout=60)


def test_invoking_sync_method_concurrently_makes_them_wait(
    session_glow: GlowBaseProcess[HasMethods],
    function_project: ProjectFixture[HasMethods],
):
    # log should be clean
    session_glow.clear_output()

    # All requests should be OK, dispatched 1 at a time.
    method_url = f"{function_project.url}/steps/method-step:one-second-sync"
    with ThreadPool(4) as p:
        responses = p.map(simulate_concurrent_method_calls, [method_url] * 10, chunksize=1)
    assert all(resp.status_code == status.HTTP_200_OK for resp in responses)

    # We cannot rely on the elapsed times due to the performance difference between the different
    # testing setups, we parse the log to check that everything is correct:
    # Requests should wait for the previous to finish before setting any status in the database or preparing anything.
    current_method_trace: str | None = None
    for line in session_glow.api_output:
        if "STARTING one_second_sync" in line:
            trace_id = line.split("trace_id=")[1].split(" ")[0]
            if not current_method_trace:
                current_method_trace = trace_id
            else:
                assert current_method_trace == trace_id
        if "LEAVING one_second_sync" in line:
            trace_id = line.split("trace_id=")[1].split(" ")[0]
            assert current_method_trace
            assert current_method_trace == trace_id
            current_method_trace = None
