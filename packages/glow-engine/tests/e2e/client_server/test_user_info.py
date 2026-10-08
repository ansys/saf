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

import httpx2
import pytest

from ansys.iam.oidc import UserInfo
from ansys.saf.glow.client import Client, InternalSolutionException, PermissionException, UnauthorizedException
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    DefaultSolutionAuthConfiguration,
    DisableAuthValidationConfiguration,
    EnableAuthValidationConfiguration,
    GlowBaseProcess,
    SolutionAuthConfiguration,
)
from tests.e2e.conftest import GlowApiKeyConfiguration, SetGlowApiKeyConfiguration
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

INTERNAL_SOLUTION_ERROR_MESSAGE = "The solution encountered an internal error and was unable to complete the request"

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    ),
]


@pytest.fixture(scope="module", autouse=True)
def cleanup_session_glow(
    session_glow: GlowBaseProcess[EndToEndSolution],
    session_idp_mock_server: str,
) -> YieldFixture[None]:
    yield
    httpx2.patch(f"{session_idp_mock_server}/admin", json={"user": "user_complete_info_from_issuer"})
    session_glow.configure_default_execution()


@pytest.fixture(scope="class")
def user(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(scope="class")
def auth_config(request: pytest.FixtureRequest) -> type[SolutionAuthConfiguration]:
    return request.param


@pytest.fixture(scope="class")
def api_key_config(request: pytest.FixtureRequest) -> type[GlowApiKeyConfiguration]:
    return request.param


@pytest.fixture(scope="class")
def configure_auth(
    user: str,
    auth_config: type[SolutionAuthConfiguration],
    api_key_config: type[GlowApiKeyConfiguration],
    deployment_type: TestDeployment,
    session_glow: GlowBaseProcess[EndToEndSolution],
    session_idp_mock_server: str,
) -> None:
    idp_server_url = session_idp_mock_server
    if deployment_type == TestDeployment.DockerCompose:
        idp_server_url = idp_server_url.replace("localhost", "host.docker.internal")
    session_glow.change_configuration(auth_config, idp_server=idp_server_url, restart=False)
    session_glow.change_configuration(api_key_config, api_key="my-mock-api-key")
    httpx2.patch(f"{session_idp_mock_server}/admin", json={"user": user})


@pytest.mark.parametrize(
    "user",
    ["user_complete_info_from_issuer", "user_partial_info_from_issuer"],
    ids=["full_user", "partial_user"],
    indirect=True,
)
@pytest.mark.parametrize(
    "auth_config",
    [DefaultSolutionAuthConfiguration, EnableAuthValidationConfiguration, DisableAuthValidationConfiguration],
    ids=["unconfigured_auth", "enabled_auth", "disabled_auth"],
    indirect=True,
)
@pytest.mark.parametrize(
    "api_key_config",
    [GlowApiKeyConfiguration, SetGlowApiKeyConfiguration],  # api_key should not change the behaviour of any test.
    ids=["no_api_key", "with_api_key"],
    indirect=True,
)
@pytest.mark.usefixtures("configure_auth")
class TestUserInfo:
    def test_user_info_from_property_no_token(
        self,
        auth_config: type[SolutionAuthConfiguration],
        function_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when no access token is provided, accessing user info through the property raises an error if
        auth validation is enabled, and returns empty user info if auth validation is disabled or unconfigured."""
        unauthenticated_project = function_client.get_project(existing_project.project_name)
        unauthenticated_step = unauthenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            # fastapi < 0.122 returns 403. the behaviour changed afterwards, returning 401 instead.
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.get_user_info_with_property()
        else:
            assert unauthenticated_step.get_user_info_with_property() == UserInfo()

    def test_user_info_from_property_invalid_token(
        self,
        user: str,
        auth_config: type[SolutionAuthConfiguration],
        wrong_token_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when an invalid token is provided, accessing user info through the property raises an error if
        auth validation is enabled or the issuer is not configured, and returns user info from the issuer if auth
        validation is disabled."""
        wrong_authenticated_project = wrong_token_client.get_project(existing_project.project_name)
        wrong_authenticated_step = wrong_authenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            # fastapi < 0.122 returns 403. the behaviour changed afterwards, returning 401 instead.
            with pytest.raises((PermissionException, UnauthorizedException), match="The token is invalid"):
                wrong_authenticated_step.get_user_info_with_property()
        elif auth_config == DefaultSolutionAuthConfiguration:
            # The property always tries to ask the issuer, which is not configured
            with pytest.raises(InternalSolutionException, match=INTERNAL_SOLUTION_ERROR_MESSAGE):
                wrong_authenticated_step.get_user_info_with_property()
        else:
            # The property always tries to ask the issuer
            user_info = wrong_authenticated_step.get_user_info_with_property()
            assert user_info.preferred_username == user

    def test_user_info_from_property_valid_token(
        self,
        user: str,
        auth_config: type[SolutionAuthConfiguration],
        authenticated_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when a valid token is provided, accessing user info through the property raises an error if
        the issuer is not configured, and returns user info from the issuer otherwise."""
        authenticated_project = authenticated_client.get_project(existing_project.project_name)
        authenticated_step = authenticated_project.steps.user_info_step
        if auth_config == DefaultSolutionAuthConfiguration:
            # The property always tries to ask the issuer, which is not configured
            with pytest.raises(InternalSolutionException, match=INTERNAL_SOLUTION_ERROR_MESSAGE):
                authenticated_step.get_user_info_with_property()
        else:
            user_info = authenticated_step.get_user_info_with_property()
            assert user_info.preferred_username == user

    def test_user_info_from_method_no_fields_no_token(
        self,
        auth_config: type[SolutionAuthConfiguration],
        function_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when no auth header is provided, accessing user info through the method with no fields raises
        an error if auth validation is enabled, and returns empty user info otherwise."""
        unauthenticated_project = function_client.get_project(existing_project.project_name)
        unauthenticated_step = unauthenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.get_user_info_with_method(fields=None)
        else:
            assert unauthenticated_step.get_user_info_with_method(fields=None) == UserInfo()

    def test_user_info_from_method_no_fields_invalid_token(
        self,
        auth_config: type[SolutionAuthConfiguration],
        wrong_token_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when an invalid token is provided, accessing user info through the method with no fields raises
        an error if auth validation is enabled, and returns local token data otherwise."""
        wrong_authenticated_project = wrong_token_client.get_project(existing_project.project_name)
        wrong_authenticated_step = wrong_authenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            with pytest.raises((PermissionException, UnauthorizedException), match="The token is invalid"):
                wrong_authenticated_step.get_user_info_with_method(fields=None)
        else:
            user_info = wrong_authenticated_step.get_user_info_with_method(fields=None)
            assert user_info.preferred_username == "invalid_partial_user_info_from_token"

    def test_user_info_from_method_no_fields_valid_token(
        self,
        authenticated_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when a valid token is provided, accessing user info through the method with no fields returns
        the local token data regardless of auth configuration."""
        authenticated_project = authenticated_client.get_project(existing_project.project_name)
        authenticated_step = authenticated_project.steps.user_info_step
        user_info = authenticated_step.get_user_info_with_method(fields=None)
        assert user_info.preferred_username == "user_partial_info_from_token"

    def test_user_info_from_method_local_field_no_token(
        self,
        auth_config: type[SolutionAuthConfiguration],
        function_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when no auth header is provided, accessing user info through the method with a local field raises
        an error if auth validation is enabled, and returns empty user info otherwise."""
        unauthenticated_project = function_client.get_project(existing_project.project_name)
        unauthenticated_step = unauthenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.get_user_info_with_method(fields=["preferred_username"])
        else:
            assert unauthenticated_step.get_user_info_with_method(fields=["preferred_username"]) == UserInfo()

    def test_user_info_from_method_local_field_invalid_token(
        self,
        auth_config: type[SolutionAuthConfiguration],
        wrong_token_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when an invalid token is provided, accessing user info through the method with a local field raises
        an error if auth validation is enabled, and returns local token data otherwise."""
        wrong_authenticated_project = wrong_token_client.get_project(existing_project.project_name)
        wrong_authenticated_step = wrong_authenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            with pytest.raises((PermissionException, UnauthorizedException), match="The token is invalid"):
                wrong_authenticated_step.get_user_info_with_method(fields=["preferred_username"])
        else:
            user_info = wrong_authenticated_step.get_user_info_with_method(fields=["preferred_username"])
            assert user_info.preferred_username == "invalid_partial_user_info_from_token"

    def test_user_info_from_method_local_field_valid_token(
        self,
        authenticated_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when a valid token is provided, accessing user info through the method with a local field returns
        the local token data regardless of auth configuration."""
        authenticated_project = authenticated_client.get_project(existing_project.project_name)
        authenticated_step = authenticated_project.steps.user_info_step
        user_info = authenticated_step.get_user_info_with_method(fields=["preferred_username"])
        assert user_info.preferred_username == "user_partial_info_from_token"

    def test_user_info_from_method_external_field_no_token(
        self,
        auth_config: type[SolutionAuthConfiguration],
        function_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when no auth header is provided, accessing user info through the method with an external field
        raises an error if auth validation is enabled, and returns empty user info otherwise."""
        unauthenticated_project = function_client.get_project(existing_project.project_name)
        unauthenticated_step = unauthenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.get_user_info_with_method(fields=["middle_name"])
        else:
            assert unauthenticated_step.get_user_info_with_method(fields=["middle_name"]) == UserInfo()

    def test_user_info_from_method_external_field_invalid_token(
        self,
        user: str,
        auth_config: type[SolutionAuthConfiguration],
        wrong_token_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when an invalid token is provided, accessing user info through the method with an external field
        raises an error if auth validation is enabled or the issuer is not configured, and falls back to the issuer
        if auth validation is disabled."""
        wrong_authenticated_project = wrong_token_client.get_project(existing_project.project_name)
        wrong_authenticated_step = wrong_authenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            with pytest.raises((PermissionException, UnauthorizedException), match="The token is invalid"):
                wrong_authenticated_step.get_user_info_with_method(fields=["middle_name"])
        elif auth_config == DefaultSolutionAuthConfiguration:
            # The requested field is not in the token, it defaults to asking the issuer, which is not configured
            with pytest.raises(InternalSolutionException, match=INTERNAL_SOLUTION_ERROR_MESSAGE):
                wrong_authenticated_step.get_user_info_with_method(fields=["middle_name"])
        else:
            if user == "user_complete_info_from_issuer":
                # The issuer includes the requested field, a user info is returned
                user_info = wrong_authenticated_step.get_user_info_with_method(fields=["middle_name"])
                assert user_info.middle_name == user
            else:
                # Neither the token nor the issuer include the requested field, an error is raised
                with pytest.raises(InternalSolutionException, match=INTERNAL_SOLUTION_ERROR_MESSAGE):
                    wrong_authenticated_step.get_user_info_with_method(fields=["middle_name"])

    def test_user_info_from_method_external_field_valid_token(
        self,
        user: str,
        auth_config: type[SolutionAuthConfiguration],
        authenticated_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when a valid token is provided, accessing user info through the method with an external field
        raises an error if the issuer is not configured, and falls back to the issuer otherwise."""
        authenticated_project = authenticated_client.get_project(existing_project.project_name)
        authenticated_step = authenticated_project.steps.user_info_step
        if auth_config == DefaultSolutionAuthConfiguration:
            # The requested field is not in the token, it defaults to asking the issuer, which is not configured
            with pytest.raises(InternalSolutionException, match=INTERNAL_SOLUTION_ERROR_MESSAGE):
                authenticated_step.get_user_info_with_method(fields=["middle_name"])
        else:
            if user == "user_complete_info_from_issuer":
                # The issuer includes the requested field, a user info is returned
                user_info = authenticated_step.get_user_info_with_method(fields=["middle_name"])
                assert user_info.middle_name == user
            else:
                # Neither the token nor the issuer include the requested field, an error is raised
                with pytest.raises(InternalSolutionException, match=INTERNAL_SOLUTION_ERROR_MESSAGE):
                    authenticated_step.get_user_info_with_method(fields=["middle_name"])

    def test_access_token_no_token(
        self,
        auth_config: type[SolutionAuthConfiguration],
        function_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
    ):
        """Test that when no auth header is provided, accessing the access token raises an error if auth validation
        is enabled, and returns None otherwise."""
        unauthenticated_project = function_client.get_project(existing_project.project_name)
        unauthenticated_step = unauthenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            with pytest.raises((PermissionException, UnauthorizedException), match="Not authenticated"):
                unauthenticated_step.get_access_token()
        else:
            assert unauthenticated_step.get_access_token() is None

    def test_access_token_invalid_token(
        self,
        auth_config: type[SolutionAuthConfiguration],
        wrong_token_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
        invalid_access_token: str,
    ):
        """Test that when an invalid token is provided, accessing the access token raises an error if auth validation
        is enabled, and returns the invalid token otherwise."""
        wrong_authenticated_project = wrong_token_client.get_project(existing_project.project_name)
        wrong_authenticated_step = wrong_authenticated_project.steps.user_info_step
        if auth_config == EnableAuthValidationConfiguration:
            with pytest.raises((PermissionException, UnauthorizedException), match="The token is invalid"):
                wrong_authenticated_step.get_access_token()
        else:
            assert wrong_authenticated_step.get_access_token() == invalid_access_token

    def test_access_token_valid_token(
        self,
        authenticated_client: Client[EndToEndSolution],
        existing_project: EndToEndSolution,
        access_token: str,
    ):
        """Test that when a valid token is provided, accessing the access token returns the token regardless of
        auth configuration."""
        authenticated_project = authenticated_client.get_project(existing_project.project_name)
        authenticated_step = authenticated_project.steps.user_info_step
        assert authenticated_step.get_access_token() == access_token
