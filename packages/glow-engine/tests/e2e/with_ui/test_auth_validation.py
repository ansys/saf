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

from collections.abc import Callable, Generator
from pathlib import Path
import platform
from typing import TypeVar

import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from ansys.saf.glow.solution import Solution
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.platform_specific import is_ci_run
from ansys.saf.testing.selenium import (
    move_to_element,
    wait_for_element,
    wait_for_element_and_click,
    wait_for_element_and_send_text,
    wait_for_partial_text,
    wait_for_text,
)
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DisableAuthValidationConfiguration,
    EnableAuthValidationConfiguration,
    GlowBaseProcess,
    InvalidAuthValidationConfiguration,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_ui,
    pytest.mark.parametrize("ui_enabled", [True], indirect=True),
]

T = TypeVar("T", bound=Solution)


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    yield
    session_glow.configure_default_execution()


@pytest.fixture(scope="class")
def authenticated_solution(
    request: pytest.FixtureRequest,
    session_glow: GlowBaseProcess[EndToEndSolution],
    session_idp_mock_server: str,
    deployment_type: TestDeployment,
) -> BaseGlowConfiguration:
    if deployment_type == TestDeployment.DockerCompose:
        session_idp_mock_server = session_idp_mock_server.replace("localhost", "host.docker.internal")
    return session_glow.change_configuration(request.param, idp_server=session_idp_mock_server)


@pytest.fixture
def auth_validation_enabled(authenticated_solution: BaseGlowConfiguration) -> bool:
    return isinstance(authenticated_solution, EnableAuthValidationConfiguration)


@pytest.fixture
def auth_token_type(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def set_selenium_auth_header(
    session_selenium_webdriver: WebDriver,
    auth_token_type: str,
    access_token: str,
    invalid_access_token: str,
) -> YieldFixture[None]:
    if auth_token_type != "no_token":
        headers = {
            "Authorization": f"Bearer {access_token if auth_token_type == 'valid_token' else invalid_access_token}",
        }
        session_selenium_webdriver.execute_cdp_cmd("Network.enable", {})  # type: ignore
        session_selenium_webdriver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": headers})  # type: ignore
    yield
    if auth_token_type != "no_token":
        session_selenium_webdriver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {}})  # type: ignore
        session_selenium_webdriver.execute_cdp_cmd("Network.disable", {})  # type: ignore


@pytest.fixture
def project_ui_url(session_glow: GlowBaseProcess[EndToEndSolution], existing_project: Solution) -> str:
    return f"{session_glow.base_ui_url}/{existing_project.project_name}"


@pytest.mark.parametrize(
    "authenticated_solution",
    [EnableAuthValidationConfiguration, DisableAuthValidationConfiguration],
    ids=["with_auth", "without_auth"],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
@pytest.mark.parametrize("auth_token_type", ["no_token", "invalid_token", "valid_token"], indirect=True)
@pytest.mark.usefixtures("set_selenium_auth_header")
class TestAuthenticatedSolution:
    def _assert_error_page(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        auth_token_type: str,
    ):
        # UI loads clean default error page.
        error_type = "Forbidden" if auth_token_type == "no_token" else "Unauthorized"
        error_msg = (
            "You don't have the permission to access the requested resource."
            if auth_token_type == "no_token"
            else "The server could not verify that you are authorized to access the URL requested."
        )
        real_error_msg = (
            "Missing authorization header"
            if auth_token_type == "no_token"
            else "Invalid access token: The token is invalid"
        )
        wait_for_text(session_selenium_webdriver, "h1", error_type, element_type=By.TAG_NAME)
        wait_for_partial_text(session_selenium_webdriver, "body", error_msg, element_type=By.TAG_NAME)
        # real error message is logged as ERROR
        assert session_glow.text_in_output(["ERROR", real_error_msg], "ui")

    def test_http_requests(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        auth_token_type: str,
        project_ui_url: str,
        auth_validation_enabled: bool,
        existing_project: Solution,
    ):
        """
        Test that HTTP requests done by DashClient/Client, including REST routes such as GET `project` and GraphQL ones
        such as when setting step fields, behave correctly when auth validation is enabled and access tokens are
        present at the header of the initial request for accessing the page.
        Cover all scenarios in terms of solution deployment, auth validation enforcement and token
        presence.
        """
        session_selenium_webdriver.get(project_ui_url)
        if auth_validation_enabled and auth_token_type != "valid_token":
            # UI only shows expected error message. UI error prevents the client from even doing any http request to the
            # Solution API. However, these are covered in the client-server E2E tests.
            self._assert_error_page(session_glow, session_selenium_webdriver, auth_token_type)
        else:
            # page loads project info, step fields can be set and transactions work as expected.
            wait_for_text(
                session_selenium_webdriver,
                "project-name",
                f"Project Name: {existing_project.project_display_name}",
            )
            wait_for_element_and_click(
                session_selenium_webdriver,
                "//*[contains(text(), 'First Page')]",
                element_type=By.XPATH,
            )
            # without refreshing, selenium fails to send keys at some point...
            session_selenium_webdriver.refresh()
            wait_for_partial_text(session_selenium_webdriver, "result-inj", "Result:0.0")
            wait_for_element_and_send_text(session_selenium_webdriver, "first-arg-inj", "1")
            wait_for_element_and_send_text(session_selenium_webdriver, "second-arg-inj", "2")
            wait_for_element_and_click(session_selenium_webdriver, "calculate_project_injected")
            wait_for_partial_text(session_selenium_webdriver, "result-inj", "Result:3.0")

    def test_background_callbacks(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        auth_token_type: str,
        project_ui_url: str,
        auth_validation_enabled: bool,
        existing_project: Solution,
        deployment_type: TestDeployment,
        request: pytest.FixtureRequest,
    ):
        """
        Test that HTTP requests done by DashClient/Client, including REST routes such as GET `project` and GraphQL ones
        such as when setting step fields, behave correctly in background callbacks when auth validation is enabled and
        access tokens are present at the header of the initial request for accessing the page.
        Cover all scenarios in terms of solution deployment, auth validation enforcement and token
        presence.
        """
        session_selenium_webdriver.get(project_ui_url)
        if auth_validation_enabled and auth_token_type != "valid_token":
            # UI only shows expected error message. UI error prevents the client from even doing any http request to the
            # Solution API. However, these are covered in the client-server E2E tests.
            self._assert_error_page(session_glow, session_selenium_webdriver, auth_token_type)
        else:
            # page loads project info, step fields can be set and transactions work as expected.
            if deployment_type == TestDeployment.Desktop:
                request.node.add_marker(  # type: ignore
                    pytest.mark.xfail(
                        condition=platform.system() == "Windows" and is_ci_run(),
                        reason="Background callback tests fails on windows CI Desktop.",
                    ),
                )
            wait_for_text(
                session_selenium_webdriver,
                "project-name",
                f"Project Name: {existing_project.project_display_name}",
            )
            wait_for_element_and_click(
                session_selenium_webdriver,
                "//*[contains(text(), 'First Page')]",
                element_type=By.XPATH,
            )
            # without refreshing, selenium fails to send keys at some point...
            session_selenium_webdriver.refresh()
            wait_for_element_and_send_text(session_selenium_webdriver, "third-arg-inj", "1")
            wait_for_element_and_send_text(session_selenium_webdriver, "fourth-arg-inj", "2")
            wait_for_element_and_click(session_selenium_webdriver, "calculate_in_background_with_project_injected")
            wait_for_partial_text(session_selenium_webdriver, "result_background_new", "Result:3.0")

    @pytest.mark.parametrize("max_number_of_workers", [1], indirect=True)
    def test_websockets(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        auth_token_type: str,
        project_ui_url: str,
        auth_validation_enabled: bool,
    ):
        """
        Test that websockets created using `DashClient.create_event_listener` behave correctly when auth validation
        is enabled and access tokens are present at the request context. Cover all scenarios in terms of solution
        deployment, auth validation enforcement and token presence.
        """
        session_selenium_webdriver.get(project_ui_url)
        if auth_validation_enabled and auth_token_type != "valid_token":
            # UI only shows expected error message. UI error prevents the client from create any websocket. However,
            # these are covered in the client-server E2E tests.
            self._assert_error_page(session_glow, session_selenium_webdriver, auth_token_type)
        else:
            # websockets are created and messages are received.
            wait_for_element_and_click(
                session_selenium_webdriver,
                "//*[contains(text(), 'Websockets Page')]",
                element_type=By.XPATH,
            )
            wait_for_element(
                session_selenium_webdriver,
                "//*[contains(text(), 'We are in WebSockets Page')]",
                element_type=By.XPATH,
            )
            wait_for_text(session_selenium_webdriver, "event_state", "WebSocket is open and ready to use.")
            wait_for_text(session_selenium_webdriver, "event_message", "Not triggered yet.")
            move_to_element(session_selenium_webdriver, "trigger_event")
            wait_for_element_and_click(session_selenium_webdriver, "trigger_event")
            wait_for_text(session_selenium_webdriver, "event_message", 'Received message: {"message":"testing!"}')

    def test_load_solution_ui(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        auth_token_type: str,
        project_ui_url: str,
        auth_validation_enabled: bool,
    ):
        """
        Test that the Dash app validates the access token and loads the UI correctly when auth validation is enabled.
        Otherwise, a clean error page is shown and the status code is 403 Forbidden or 401 Unauthorized. Cover all
        scenarios in terms of solution deployment, auth validation enforcement and token presence.
        """
        session_selenium_webdriver.get(project_ui_url)
        if auth_validation_enabled and auth_token_type != "valid_token":
            # UI only shows expected error message.
            self._assert_error_page(session_glow, session_selenium_webdriver, auth_token_type)
        else:
            # UI loads page
            wait_for_element(session_selenium_webdriver, "page-content")
            wait_for_element(session_selenium_webdriver, "//*[contains(text(), 'First Page')]", element_type=By.XPATH)


def test_enabling_auth_requires_setting_issuer_url_and_client_id(
    run_glow: Callable[..., GlowBaseProcess[EndToEndSolution]],
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
):
    """Test that enabling authentication requires setting both issuer URL and client ID, since they don't have default
    values. Applies to both, API and UI servers.
    """
    glow_proc = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], prevent_start=True)
    _ = glow_proc.change_configuration(InvalidAuthValidationConfiguration)
    assert not glow_proc.healthy
    expected_error_msg = (
        "RuntimeError: Authentication cannot be enforced without setting environment variables GLOW_AUTH_ISSUER_URL and"
        " GLOW_AUTH_CLIENT_ID."
    )
    assert glow_proc.text_in_output(expected_error_msg, "api")
    assert glow_proc.text_in_output(expected_error_msg, "ui")
