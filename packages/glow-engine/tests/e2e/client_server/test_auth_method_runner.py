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
import threading
import time

import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import Client, UnauthorizedException
from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    EnableAuthValidationConfiguration,
    GlowBaseProcess,
)
from tests.e2e.conftest import GlowApiKeyConfiguration, SetGlowApiKeyConfiguration
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import TransactionVerificationStep

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    ),
]


@retry(stop=stop_after_attempt(100), wait=wait_fixed(0.5))
def _wait_for_method_status(step: TransactionVerificationStep, method_name: str, status: MethodStatus) -> bool:
    if step.get_method_state(method_name).status != status:
        raise TryAgain
    return True


@pytest.fixture(scope="module", autouse=True)
def authenticated_solution(
    session_glow: GlowBaseProcess[EndToEndSolution],
    session_idp_mock_server: str,
    deployment_type: TestDeployment,
) -> YieldFixture[None]:
    idp_server_url = session_idp_mock_server
    if deployment_type == TestDeployment.DockerCompose:
        idp_server_url = idp_server_url.replace("localhost", "host.docker.internal")
    session_glow.change_configuration(EnableAuthValidationConfiguration, idp_server=idp_server_url)
    yield
    session_glow.configure_default_execution()


@pytest.fixture
def enable_glow_api_key(session_glow: GlowBaseProcess[EndToEndSolution]) -> YieldFixture[None]:
    session_glow.change_configuration(SetGlowApiKeyConfiguration, api_key="my-mock-api-key")
    yield
    session_glow.change_configuration(GlowApiKeyConfiguration)


@pytest.mark.parametrize("long_running", [True, False], ids=["long_running", "sync"])
def test_transaction_fails_if_access_token_expires_during_execution(
    session_glow: GlowBaseProcess[EndToEndSolution],
    get_glow_client: Callable[[GlowBaseProcess[EndToEndSolution], str | None], Client[EndToEndSolution]],
    get_access_token: Callable[[int | None], str],
    long_running: bool,
):
    # WHEN: Launching transaction with access token that expires soon
    with (
        get_glow_client(session_glow, get_access_token(10)) as authenticated_expiring_client,
        get_glow_client(
            session_glow,
            get_access_token(None),
        ) as authenticated_client,
    ):
        expiring_project = authenticated_expiring_client.create_project("auth-method-runner-1")
        project_id = expiring_project.project_id
        assert not expiring_project.steps.transaction_verification_step.text_content

        invoke_thread: threading.Thread | None = None
        method_name = "n_second_async" if long_running else "n_second_sync"
        if long_running:
            expiring_project.steps.transaction_verification_step.n_second_async(sleep_seconds=20)
        else:
            invoke_thread = threading.Thread(
                target=expiring_project.steps.transaction_verification_step.n_second_sync,
                kwargs={"sleep_seconds": 20},
            )
            invoke_thread.start()

        # THEN: Transaction starts correctly
        _wait_for_method_status(expiring_project.steps.transaction_verification_step, method_name, MethodStatus.Running)

        # THEN: Transaction fails to upload field 'text_content' at the end
        session_glow.text_in_output(
            [
                "GLOW METHOD RUNNER",
                "500: Client error '401 Unauthorized' for url "
                f"{session_glow.base_api_url}/projects/{project_id}/steps/transaction-verification-step?fields=",
            ],
            "api",
            timeout=30,
        )
        # THEN: Transaction fails to set state at failed and it's left as running
        session_glow.text_in_output(
            [
                "RuntimeError: Failed to set state on solution server via "
                f"{session_glow.base_api_url}/projects/{project_id}/steps/transaction-verification-step:{method_name}",
                '"status":"failed"',
            ],
            "api",
        )
        if invoke_thread:
            invoke_thread.join()

        # Trying to use the client with the expired token also fails
        with pytest.raises(UnauthorizedException):
            expiring_project.steps.transaction_verification_step.get_method_state(method_name)

        # THEN: Using another client with a valid token, we can see the transaction was left as running and
        # field 'text_content' was not updated
        project = authenticated_client.get_project(f"projects/{project_id}")
        assert project.steps.transaction_verification_step.get_method_state(method_name).status == MethodStatus.Running
        assert not project.steps.transaction_verification_step.text_content


@pytest.mark.usefixtures("enable_glow_api_key")
@pytest.mark.parametrize("long_running", [True, False], ids=["long_running", "sync"])
def test_transaction_succeeds_if_access_token_expires_during_execution_but_api_key_is_enabled(
    session_glow: GlowBaseProcess[EndToEndSolution],
    get_glow_client: Callable[[GlowBaseProcess[EndToEndSolution], str | None], Client[EndToEndSolution]],
    get_access_token: Callable[[int | None], str],
    long_running: bool,
):
    # WHEN: Launching transaction with access token that expires soon
    with (
        get_glow_client(session_glow, get_access_token(10)) as authenticated_expiring_client,
        get_glow_client(
            session_glow,
            get_access_token(None),
        ) as authenticated_client,
    ):
        expiring_project = authenticated_expiring_client.create_project("auth-method-runner-1")
        project_id = expiring_project.project_id
        assert not expiring_project.steps.transaction_verification_step.text_content

        invoke_thread: threading.Thread | None = None
        method_name = "n_second_async" if long_running else "n_second_sync"
        if long_running:
            expiring_project.steps.transaction_verification_step.n_second_async(sleep_seconds=20)
        else:
            invoke_thread = threading.Thread(
                target=expiring_project.steps.transaction_verification_step.n_second_sync,
                kwargs={"sleep_seconds": 20},
            )
            invoke_thread.start()

        # THEN: Transaction starts correctly
        _wait_for_method_status(expiring_project.steps.transaction_verification_step, method_name, MethodStatus.Running)

        # THEN: Transaction completes successfully even after the token expires because API key is enabled
        session_glow.text_in_output(
            [
                f"Updating method state for transaction_verification_step:{method_name} with",
                "status=<MethodStatus.Completed: 'completed'>",
            ],
            "api",
            timeout=30,
        )

        # Trying to use the client with the expired token fails
        with pytest.raises(UnauthorizedException):
            expiring_project.steps.transaction_verification_step.get_method_state(method_name)

        # THEN: Using another client with a valid token, we can see the transaction completed successfully
        # and field 'text_content' was updated
        project = authenticated_client.get_project(f"projects/{project_id}")
        _wait_for_method_status(project.steps.transaction_verification_step, method_name, MethodStatus.Completed)
        assert project.steps.transaction_verification_step.text_content == "20"


@pytest.mark.parametrize("long_running", [True, False], ids=["long_running", "sync"])
def test_transaction_auth_headers_are_isolated_across_projects(
    session_glow: GlowBaseProcess[EndToEndSolution],
    get_access_token: Callable[[int | None], str],
    get_glow_client: Callable[[GlowBaseProcess[EndToEndSolution], str], Client[EndToEndSolution]],
    long_running: bool,
):
    """Verify concurrent transactions do not leak Authorization header across projects."""
    # GIVEN: two clients with different access tokens working in different projects
    # Different expiration times to force generating different tokens.
    token_1 = get_access_token(1800)
    token_2 = get_access_token(3600)
    assert token_1 != token_2
    client_1 = get_glow_client(session_glow, token_1)
    client_2 = get_glow_client(session_glow, token_2)
    project_1 = client_1.create_project("headers-isolation-1")
    project_2 = client_2.create_project("headers-isolation-2")
    project_1.steps.transaction_verification_step.field_1 = 1
    project_2.steps.transaction_verification_step.field_1 = 2

    # WHEN: launching two concurrent transactions of different projects
    if long_running:
        method_1 = project_1.steps.transaction_verification_step.log_http_client_headers_long_running()
        project_2.steps.transaction_verification_step.log_http_client_headers_long_running().wait()
        method_1.wait()
    else:
        invoke_thread = threading.Thread(target=project_1.steps.transaction_verification_step.log_http_client_headers)
        invoke_thread.start()
        time.sleep(1)  # give time for the first transaction to start
        project_2.steps.transaction_verification_step.log_http_client_headers()
        invoke_thread.join()

    # THEN: every transaction logs its own header for the whole execution time.
    found_request_1 = 0
    found_request_2 = 0
    for line in session_glow.api_output:
        if "AUTH_HEADERS" in line:
            request_id = line.split("request_id=")[-1].split(" ")[0]
            if request_id == "1":
                found_request_1 += 1
                assert f"http={token_1}" in line
                assert f"graphql={token_1}" in line
                assert token_2 not in line
            elif request_id == "2":
                found_request_2 += 1
                assert f"http={token_2}" in line
                assert f"graphql={token_2}" in line
                assert token_1 not in line
            else:
                raise AssertionError(f"Unexpected request_id {request_id} in line: {line}")
    assert found_request_1 == 10
    assert found_request_2 == 10
