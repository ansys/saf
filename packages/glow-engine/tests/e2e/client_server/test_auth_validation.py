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

from collections.abc import AsyncGenerator, Generator
from typing import TypeVar

import aiohttp
import httpx2
import pytest

from ansys.iam.oidc import DEFAULT_SUBPROTOCOL_PREFIX, encode_base64_token
from ansys.saf.glow.client import Client, PermissionException, UnauthorizedException
from ansys.saf.glow.solution import MethodStatus, Solution
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DesktopDeploymentConfiguration,
    DisableAuthValidationConfiguration,
    DockerDeploymentConfiguration,
    EnableAuthValidationConfiguration,
    GlowBaseProcess,
)
from tests.mocks.solutions.events import EventsSolution
from tests.mocks.solutions.instances import InstancesSolution
from tests.mocks.solutions.solution_configuration import SolutionConfigurationSolution
from tests.mocks.solutions.transactions import TransactionsSolution

T = TypeVar("T", bound=Solution)


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowBaseProcess[TransactionsSolution]) -> Generator[None, None, None]:
    yield
    session_glow.configure_default_execution()


@pytest.fixture
def auth_validation_enabled(authenticated_solution: tuple[BaseGlowConfiguration, BaseGlowConfiguration]) -> bool:
    return isinstance(authenticated_solution[1], EnableAuthValidationConfiguration)


@pytest.fixture(scope="class")
def authenticated_solution(
    request: pytest.FixtureRequest,
    session_glow: GlowBaseProcess[TransactionsSolution],
    session_idp_mock_server: str,
) -> tuple[BaseGlowConfiguration, BaseGlowConfiguration]:
    deployment_config, auth_validation_config = request.param
    deployment = session_glow.change_configuration(deployment_config, restart=False)
    auth_validation = session_glow.change_configuration(auth_validation_config, idp_server=session_idp_mock_server)
    return deployment, auth_validation


@pytest.fixture
async def aiohttp_session() -> AsyncGenerator[aiohttp.ClientSession, None]:
    session = aiohttp.ClientSession()
    yield session
    await session.close()


async def send_and_receive_event(
    ws: aiohttp.ClientWebSocketResponse[bool],
    step_url: str,
    transaction_url: str,
    access_token: str,
    message: dict[str, str],
) -> str:
    async with httpx2.AsyncClient() as http_client:
        r = await http_client.patch(
            step_url,
            json={"stream_name": "test-stream", "message": message},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        r = await http_client.post(transaction_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        r.raise_for_status()
        return await ws.receive_json(timeout=10)


@pytest.mark.parametrize(
    "authenticated_solution",
    [
        (DesktopDeploymentConfiguration, DisableAuthValidationConfiguration),
        (DesktopDeploymentConfiguration, EnableAuthValidationConfiguration),
        (DockerDeploymentConfiguration, DisableAuthValidationConfiguration),
        (DockerDeploymentConfiguration, EnableAuthValidationConfiguration),
    ],
    ids=["desktop_without_auth", "desktop_with_auth", "docker_without_auth", "docker_with_auth"],
    indirect=True,
)
class TestAuthenticatedSolution:
    @pytest.mark.parametrize("solution_type", [TransactionsSolution], indirect=True)
    def test_get_project(
        self,
        existing_project: TransactionsSolution,
        authenticated_client: Client[TransactionsSolution],
        function_client: Client[TransactionsSolution],
        wrong_token_client: Client[TransactionsSolution],
        auth_validation_enabled: bool,
    ):
        """Test that the project REST API routes require valid tokens when authentication validation is enabled."""
        existing_project_name = existing_project.project_name

        # No token returns 403 Forbidden (fastapi < 0.122) or 401 Unauthorized (fastapi >= 0.122)
        # if auth validation is enabled
        if auth_validation_enabled:
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                _ = function_client.get_project(existing_project_name).project_display_name
        else:
            assert (
                existing_project.project_display_name
                == function_client.get_project(existing_project_name).project_display_name
            )

        # Wrong token returns 401 Unauthorized if auth validation is enabled
        if auth_validation_enabled:
            with pytest.raises(UnauthorizedException, match="The token is invalid"):
                _ = wrong_token_client.get_project(existing_project_name).project_display_name
        else:
            assert (
                existing_project.project_display_name
                == wrong_token_client.get_project(existing_project_name).project_display_name
            )

        # Valid token returns project for all configs
        assert (
            existing_project.project_display_name
            == authenticated_client.get_project(existing_project_name).project_display_name
        )

    @pytest.mark.parametrize("solution_type", [TransactionsSolution], indirect=True)
    def test_graphql_step_update(
        self,
        authenticated_client: Client[TransactionsSolution],
        function_client: Client[TransactionsSolution],
        existing_project: TransactionsSolution,
        auth_validation_enabled: bool,
    ):
        """Test that an authenticated client can update step fields (which is using the underlying graphql route)
        but that unauthenticated client can only update step fields when authentication is disabled.
        """

        existing_project_name = existing_project.project_name
        authenticated_project = authenticated_client.get_project(existing_project_name)
        authenticated_step = authenticated_project.steps.transaction_step

        # authenticated client can use graphql endpoint in any context
        authenticated_step.x = 100
        authenticated_step.from_dict({"y": 50})  # type: ignore
        assert authenticated_step.x == 100
        assert authenticated_step.y == 50

        unauthenticated_project = function_client.get_project(existing_project_name)
        unauthenticated_step = unauthenticated_project.steps.transaction_step

        if auth_validation_enabled:
            # unauthenticated client is failing to use graphql endpoint
            # it raises 403 Forbidden (fastapi < 0.122) or 401 Unauthorized (fastapi >= 0.122)
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.x = 100
        else:
            # unauthenticated client can use graphql endpoint if auth validation disabled
            unauthenticated_step.x = 100
            unauthenticated_step.from_dict({"y": 50})  # type: ignore
            assert unauthenticated_step.x == 100
            assert unauthenticated_step.y == 50

    @pytest.mark.parametrize("solution_type", [EventsSolution], indirect=True)
    async def test_authenticated_websocket(
        self,
        existing_project: EventsSolution,
        aiohttp_session: aiohttp.ClientSession,
        access_token: str,
        auth_validation_enabled: bool,
    ):
        """Test that the websocket connection requires valid token when authentication validation is enabled."""
        existing_project_name = existing_project.project_name
        step_url = f"{existing_project.url}/steps/events-step"
        transaction_url = f"{step_url}:raise-event"
        ws_url = f"ws://{existing_project.url.split('/')[2]}/events/{existing_project_name}/steps/events-step/streams/test-stream"
        message = {"message": "test"}

        # WHEN: we try to connect to the websocket without authentication
        # THEN: it raises a handshake error only if deployment is DockerCompose and Auth Validation is enabled
        if auth_validation_enabled:
            with pytest.raises(aiohttp.WSServerHandshakeError):
                async with aiohttp_session.ws_connect(ws_url):
                    ...
        else:
            async with aiohttp_session.ws_connect(ws_url) as ws:
                # THEN: otherwise, we receive the event message
                assert message == await send_and_receive_event(ws, step_url, transaction_url, access_token, message)

        # WHEN: we try to connect to the websocket with invalid token
        # THEN: it raises a handshake error only if deployment is DockerCompose and Auth Validation is enabled
        encoded_token = encode_base64_token("my-mock-token")
        if auth_validation_enabled:
            with pytest.raises(aiohttp.WSServerHandshakeError):
                async with aiohttp_session.ws_connect(
                    ws_url,
                    protocols=[f"{DEFAULT_SUBPROTOCOL_PREFIX}{encoded_token}"],
                ):
                    ...
        else:
            async with aiohttp_session.ws_connect(
                ws_url,
                protocols=[f"{DEFAULT_SUBPROTOCOL_PREFIX}{encoded_token}"],
            ) as ws:
                # THEN: otherwise, we receive the event message
                assert message == await send_and_receive_event(ws, step_url, transaction_url, access_token, message)

        # WHEN: we try to connect to the websocket with valid token but wrong protocol prefix
        # THEN: it raises a handshake error only if deployment is DockerCompose and Auth Validation is enabled
        encoded_token = encode_base64_token(access_token)
        if auth_validation_enabled:
            with pytest.raises(aiohttp.WSServerHandshakeError):
                async with aiohttp_session.ws_connect(ws_url, protocols=[f"wrong.prefix.{encoded_token}"]):
                    ...
        else:
            async with aiohttp_session.ws_connect(ws_url, protocols=[f"wrong.prefix.{encoded_token}"]) as ws:
                # THEN: otherwise, we receive the event message
                assert message == await send_and_receive_event(ws, step_url, transaction_url, access_token, message)

        # WHEN: we connect to the websocket with authentication
        async with aiohttp_session.ws_connect(
            ws_url,
            protocols=[f"{DEFAULT_SUBPROTOCOL_PREFIX}{encoded_token}"],
        ) as ws:
            # THEN: we receive the event message for all deployments and validation configurations
            assert message == await send_and_receive_event(ws, step_url, transaction_url, access_token, message)

    @pytest.mark.parametrize("method_name", ["store_entity_handle", "store_entity_handle_lr"])
    @pytest.mark.parametrize("solution_type", [TransactionsSolution], indirect=True)
    def test_entity_handle_operations_with_authentication(
        self,
        method_name: str,
        function_client: Client[TransactionsSolution],
        authenticated_client: Client[TransactionsSolution],
        existing_project: TransactionsSolution,
        auth_validation_enabled: bool,
    ):
        """Test that entity handle operations within transactions correctly set and remove BDM locks, handling
        authentication if required to communicate with the GLOW API server.

        Test remains here because we used to do it with an http-based class for longrunning methods that created a
        client internally. Now it's done with a direct crud-based class for any kind of method.
        """
        existing_project_name = existing_project.project_name

        # WHEN: we try to interact with an entityhandle in a transaction, which sets and deletes BDM locks.

        # THEN: it works correctly
        authenticated_project = authenticated_client.get_project(existing_project_name)
        authenticated_step = authenticated_project.steps.transaction_step
        method = getattr(authenticated_step, method_name)
        if method_name == "store_entity_handle":
            method()
        else:
            method().wait()
        assert authenticated_project.storage_scope.get_text(authenticated_step.stored_entity) == "entity handle content"

        unauthenticated_project = function_client.get_project(existing_project_name)
        unauthenticated_step = unauthenticated_project.steps.transaction_step
        if auth_validation_enabled:
            # WHEN: doing the same with an unauthenticated client if auth is enabled
            # THEN: it raises 403 Forbidden (fastapi < 0.122) or 401 Unauthorized (fastapi >= 0.122)
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                getattr(unauthenticated_step, method_name)()
        else:
            # WHEN: doing the same with an unauthenticated client if auth is not enabled
            # THEN: it works correctly
            method = getattr(unauthenticated_step, method_name)
            if method_name == "store_entity_handle":
                method()
            else:
                method().wait()
            assert (
                unauthenticated_project.storage_scope.get_text(unauthenticated_step.stored_entity)
                == "entity handle content"
            )

    @pytest.mark.parametrize("solution_type", [InstancesSolution], indirect=True)
    @pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
    def test_instance_lifecycle_with_authentication(
        self,
        authenticated_client: Client[InstancesSolution],
        function_client: Client[InstancesSolution],
        existing_project: InstancesSolution,
        auth_validation_enabled: bool,
    ):
        """Test that the instance identification client used within transactions for shared product instances handles
        authentication correctly.
        """
        existing_project_name = existing_project.project_name

        # WHEN: we try to interact with a shared instance in transactions, which should use http-based identification
        # client
        # THEN: it works correctly
        authenticated_project = authenticated_client.get_project(existing_project_name)
        authenticated_step = authenticated_project.steps.instance_step
        authenticated_step.create()
        authenticated_step.set_is_blue()
        authenticated_step.shutdown()

        unauthenticated_project = function_client.get_project(existing_project_name)
        unauthenticated_step = unauthenticated_project.steps.instance_step
        if auth_validation_enabled:
            # WHEN: doing the same with an unauthenticated client if auth is enabled
            # THEN: it raises 403 Forbidden (fastapi < 0.122) or 401 Unauthorized (fastapi >= 0.122)
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.create()
        else:
            # WHEN: doing the same with an unauthenticated client if auth is not enabled
            # THEN: it works correctly
            unauthenticated_step.create()
            unauthenticated_step.set_is_blue()
            unauthenticated_step.shutdown()

    @pytest.mark.parametrize("method_name", ["long_running_download_x_upload_y", "download_x_upload_y"])
    @pytest.mark.parametrize("solution_type", [TransactionsSolution], indirect=True)
    def test_transactions_with_authentication(
        self,
        method_name: str,
        authenticated_client: Client[TransactionsSolution],
        function_client: Client[TransactionsSolution],
        existing_project: TransactionsSolution,
        auth_validation_enabled: bool,
    ):
        """Test that invoking transactions require valid tokens when authentication validation is enabled.

        This test also verifies that the HTTP client used to set method states, get and fetch fields
        correctly handles authentication.
        """
        existing_project_name = existing_project.project_name
        authenticated_project = authenticated_client.get_project(existing_project_name)
        authenticated_step = authenticated_project.steps.transaction_step

        method = getattr(authenticated_step, method_name)
        if method_name == "download_x_upload_y":
            method()
        else:
            method().wait()
        assert authenticated_step.get_method_state(method_name).status == MethodStatus.Completed
        assert authenticated_step.y == 99

        unauthenticated_project = function_client.get_project(existing_project_name)
        unauthenticated_step = unauthenticated_project.steps.transaction_step
        if auth_validation_enabled:
            # WHEN: doing the same with an unauthenticated client if auth is enabled
            # THEN: it raises 403 Forbidden (fastapi < 0.122) or 401 Unauthorized (fastapi >= 0.122)
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                getattr(unauthenticated_step, method_name)()
        else:
            method = getattr(unauthenticated_step, method_name)
            if method_name == "download_x_upload_y":
                method()
            else:
                method().wait()
            assert unauthenticated_step.get_method_state(method_name).status == MethodStatus.Completed
            assert unauthenticated_step.y == 99

    @pytest.mark.skip(reason="receive_json timeout not working properly.")
    @pytest.mark.parametrize("solution_type", [TransactionsSolution], indirect=True)
    async def test_raise_event_with_authentication(
        self,
        aiohttp_session: aiohttp.ClientSession,
        authenticated_client: Client[TransactionsSolution],
        function_client: Client[TransactionsSolution],
        existing_project: TransactionsSolution,
        auth_validation_enabled: bool,
        access_token: str,
    ):
        """Test that raising events from transactions require valid tokens when authentication validation is enabled.

        This test verifies that the HTTP client used to send event messages from within transactions correctly handles
        authentication.
        """
        existing_project_name = existing_project.project_name
        authenticated_project = authenticated_client.get_project(existing_project_name)
        authenticated_step = authenticated_project.steps.transaction_step
        encoded_token = encode_base64_token(access_token)
        ws_url = f"ws://{existing_project.url.split('/')[2]}/events/{existing_project_name}/steps/transaction-step/streams/raise-event"

        async with aiohttp_session.ws_connect(
            ws_url,
            protocols=[f"{DEFAULT_SUBPROTOCOL_PREFIX}{encoded_token}"],
        ) as ws:
            authenticated_step.raise_event()
            assert await ws.receive_json(timeout=30) == {"message": "hello1"}

        unauthenticated_project = function_client.get_project(existing_project_name)
        unauthenticated_step = unauthenticated_project.steps.transaction_step
        if auth_validation_enabled:
            # WHEN: doing the same with an unauthenticated client if auth is enabled
            # THEN: it raises 403 Forbidden (fastapi < 0.122) or 401 Unauthorized (fastapi >= 0.122)
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.raise_event()
        else:
            async with aiohttp_session.ws_connect(ws_url) as ws:
                unauthenticated_step.raise_event()
                assert await ws.receive_json(timeout=30) == {"message": "hello1"}

    @pytest.mark.parametrize("solution_type", [SolutionConfigurationSolution], indirect=True)
    def test_solution_configuration_access_with_authentication(
        self,
        authenticated_client: Client[SolutionConfigurationSolution],
        function_client: Client[SolutionConfigurationSolution],
        existing_project: SolutionConfigurationSolution,
        auth_validation_enabled: bool,
    ):
        """Test that solution configuration access from within transactions requires valid tokens when authentication
        validation is enabled.
        """
        existing_project_name = existing_project.project_name
        authenticated_project = authenticated_client.get_project(existing_project_name)
        authenticated_step = authenticated_project.steps.solution_configuration_step

        # WHEN: retrieving solution configuration in a transaction with an authenticated client
        # THEN: it works correctly
        assert authenticated_step.read_solution_configuration() == "SolutionConfiguration"

        unauthenticated_project = function_client.get_project(existing_project_name)
        unauthenticated_step = unauthenticated_project.steps.solution_configuration_step
        if auth_validation_enabled:
            # WHEN: doing the same with an unauthenticated client if auth is enabled
            # THEN: it raises 403 Forbidden (fastapi < 0.122) or 401 Unauthorized (fastapi >= 0.122)
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.read_solution_configuration()
        else:
            # WHEN: doing the same with an unauthenticated client if auth is not enabled
            # THEN: it works correctly
            assert unauthenticated_step.read_solution_configuration() == "SolutionConfiguration"
