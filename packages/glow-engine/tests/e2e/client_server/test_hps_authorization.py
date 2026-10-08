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
from pathlib import Path
import shutil
import time
from typing import TypeVar

import certifi
import httpx2
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.hps.scripts.hps_installer import HPS_DEPLOYMENTS_DIRECTORY
from ansys.saf.testing.platform_specific import xfail_for_ci
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    CustomHPSClientTTLConfiguration,
    DefaultHPSClientTTLConfiguration,
    GlowBaseProcess,
    HpsAuthConfiguration,
    HpsKeyCloakAuth,
    HpsTokenPassThroughAuth,
    ProjectFixture,
)
from tests.e2e.conftest import interactive_authorization
import tests.mocks.solution_end_to_end.main as solution_end_to_end_module
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.hps_simple_project_step import HpsSimpleProjectStep

T = TypeVar("T", bound=Solution)

pytestmark = [pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)]

METHOD_ASSETS = Path(solution_end_to_end_module.__file__).parent / "method_assets"
HPS_CERTIFICATES_DIR = HPS_DEPLOYMENTS_DIRECTORY / "config" / "certificates"
TOKEN_LIFESPAN_SECONDS = 60


@retry(
    stop=stop_after_attempt(50),
    wait=wait_fixed(2),
)
def wait_for_hps_study_to_finish(step: HpsSimpleProjectStep) -> None:
    step.query_hps()
    if not step.python_name:
        raise TryAgain


@pytest.fixture(autouse=True, scope="class")
def setup_environment(
    session_glow: GlowBaseProcess[EndToEndSolution],
    hps_auth_configuration_type: type[HpsAuthConfiguration],
    hps_host: str,
    deployment_type: TestDeployment,
    hps_client_cache_ttl: float | None,
):
    with pytest.MonkeyPatch().context() as mp:
        # most hps env var from glow are needed for the client, so let's add them.
        for env_name, env_value in hps_auth_configuration_type(deployment_type).env_vars_to_configure.env_vars.items():
            if env_value:
                mp.setenv(env_name, env_value)

        mp.setenv("GLOW_HPS_HOST", hps_host)
        mp.setenv("GLOW_HPS_PORT", "8443")
        if hps_auth_configuration_type is HpsTokenPassThroughAuth:
            # HpsTokenPassThrough needs to use the external hps host that is available from inside and outside docker
            session_glow.change_configuration(hps_auth_configuration_type, restart=False, hps_host=hps_host)
        else:
            session_glow.change_configuration(hps_auth_configuration_type, restart=False)
        if hps_client_cache_ttl is not None:
            session_glow.change_configuration(
                CustomHPSClientTTLConfiguration,
                cache_ttl_seconds=hps_client_cache_ttl,
                restart=False,
            )
        else:
            session_glow.change_configuration(DefaultHPSClientTTLConfiguration, restart=False)
        yield


@pytest.fixture(autouse=True)
def intertest_setup(session_glow: GlowBaseProcess[EndToEndSolution], setup_environment: None):
    session_glow.restart()
    # may be needed to kill all default webbrowser processes on the CI
    # actually is very likely *not* needed because it is never authenticated there (but only via selenium)


@pytest.fixture(autouse=True, scope="module")
def exit_module(session_glow: GlowBaseProcess[EndToEndSolution]):
    yield
    session_glow.configure_default_execution()


@pytest.fixture(scope="session")
def install_hps_certificates(certificates_directory: Path):
    # In order to be able to use verified https connection from within docker and the client,
    # we need to copy the content of the ca.crt into the caroot used by python (i.e. the certifi module)
    cacert_pem = Path(certifi.where())
    cacert_pem_bk = cacert_pem.with_suffix(".bk")
    if cacert_pem_bk.exists():
        # previous test run did not clean up properly
        shutil.move(cacert_pem_bk, cacert_pem)
    shutil.copy(cacert_pem, cacert_pem_bk)
    hps_ca_cert = certificates_directory / "ca.crt"
    cert_content = hps_ca_cert.read_text()
    cacert_pem_content = cacert_pem.read_text()
    if cert_content not in cacert_pem_content:
        cacert_pem.write_text(cacert_pem_content + "\n" + cert_content)

    # By default, traefik is using HPS_DEPLOYMENTS / "config" / "certificates" / "server_docker.localhost.crt"
    # This is defined in HPS_DEPLOYMENTS / "config" / "traefik" / "dynamic" / "tls_setup.yml"
    # Since we want to use  self generated certificate issued to hpst_host, we need to modify tls_setup.yml
    # to reference the self generated certificates.
    server_crt = certificates_directory / "server.crt"
    server_key = certificates_directory / "server.key"
    shutil.copy(server_crt, HPS_CERTIFICATES_DIR)
    shutil.copy(server_key, HPS_CERTIFICATES_DIR)
    yield
    (HPS_CERTIFICATES_DIR / "server.crt").unlink(missing_ok=True)
    (HPS_CERTIFICATES_DIR / "server.key").unlink(missing_ok=True)
    shutil.move(cacert_pem_bk, cacert_pem)


@pytest.fixture
def token_to_obtain_hps_access_and_refresh_tokens(
    hps_host: str,
    deployment_type: str,
    hps_auth_configuration_type: type[HpsAuthConfiguration],
):
    # Create the token using keycloak with the "rep-impersonation" client.
    if deployment_type == TestDeployment.DockerCompose and hps_auth_configuration_type is HpsTokenPassThroughAuth:
        # The values of client_id and client_secret are included by default in the HPS deployment v1.2.217. They can be
        # found in the file hps_deployment/v1.2.217/docker-compose-customer/config/keycloak/realm.json as the last item
        # of the list under the "clients" key.
        body = {
            "client_id": "rep-impersonation",
            "client_secret": "6z1Y3oqKi7iyrTItRr10zGyNIkBsI0uN",
            "grant_type": "client_credentials",
        }
        response = httpx2.post(
            f"https://{hps_host}:8443/hps/auth/realms/rep/protocol/openid-connect/token",
            verify=True,
            data=body,
        )

        return response.json()["access_token"]
    else:
        return ""


@pytest.fixture
def inject_selenium_auth_header(
    session_selenium_webdriver: WebDriver,
    token_to_obtain_hps_access_and_refresh_tokens: str,
) -> YieldFixture[None]:
    headers = {"Authorization": f"Bearer {token_to_obtain_hps_access_and_refresh_tokens}"}
    session_selenium_webdriver.execute_cdp_cmd("Network.enable", {})  # type: ignore
    session_selenium_webdriver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": headers})  # type: ignore
    yield
    session_selenium_webdriver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {}})  # type: ignore
    session_selenium_webdriver.execute_cdp_cmd("Network.disable", {})  # type: ignore


@pytest.fixture
def authenticated_client(
    session_glow: GlowBaseProcess[T],
    token_to_obtain_hps_access_and_refresh_tokens: str,
    get_glow_client: Callable[[GlowBaseProcess[T], str | None], Client[T]],
) -> YieldFixture[Client[T]]:
    with get_glow_client(session_glow, token_to_obtain_hps_access_and_refresh_tokens) as client:
        yield client


@pytest.fixture
def authenticated_project(
    session_glow: GlowBaseProcess[T],
    authenticated_client: Client[T],
) -> YieldFixture[ProjectFixture[T]]:
    with ProjectFixture(session_glow, authenticated_client) as project:
        yield project


@pytest.mark.usefixtures("restore_default_hps_deployment")
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
# HPS Client cache should be enough to use only a single Client during a transaction and slightly more than
# TOKEN_LIFESPAN_SECONDS to make sure tokens are requested again when the cache expires.
@pytest.mark.parametrize(
    ("deployment_type", "hps_auth_configuration_type", "hps_client_cache_ttl"),
    [("Desktop", HpsKeyCloakAuth, TOKEN_LIFESPAN_SECONDS + 5)],
    scope="session",
    indirect=["deployment_type"],
)
@pytest.mark.parametrize(
    "configure_hps_deployment_keycloak",
    [{"accessTokenLifespan": TOKEN_LIFESPAN_SECONDS}],
    ids=["60sec_access"],
    indirect=True,
)
class TestAccessTokenExpiration:
    def test_auth_token_expiration_between_transactions(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        This test verifies that the auth token for HPS is refreshed automatically after expiring when a new transaction
        is executed.
        During each transaction we only expect 1 request for authentication and 1 Client created.
        """

        # GIVEN a glow process in which HPS has been authenticated.
        step = function_project.project.steps.custom_grpc_shared_instance_step
        method = step.initialize_custom_grpc_product_instance()
        interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        expected_msg = "No existing HPS authentication found, authenticating..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        assert not session_glow.text_in_output("Reusing existing valid HPS access token...", "api")

        # WHEN: The lifespan for the auth token has passed.
        # cache doesn't matter here, as a new transaction is launched.
        time.sleep(TOKEN_LIFESPAN_SECONDS + 1)

        # THEN: Token is refreshed automatically if another transaction that requires HPS is launched
        session_glow.clear_output()
        step.retrieve_value_custom_grpc_product_instance_long_running().wait()
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        expected_msg = "HPS access token expired or invalid, refreshing token..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("Reusing existing valid HPS access token.", "api")

        # Authorization is reused when launching another transaction
        session_glow.clear_output()
        step.shutdown_custom_grpc_product_instance()
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        expected_msg = "Reusing existing valid HPS access token."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1

    @xfail_for_ci(reason="Flaky test, needs investigation")
    @pytest.mark.parametrize(
        "method_name",
        ["query_instance_management_on_loop_lr", "query_instance_management_on_loop"],
    )
    def test_auth_token_expiration_using_instance_during_transaction(
        self,
        method_name: str,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        hps_client_cache_ttl: int,
    ):
        """
        This test verifies that the auth token for HPS is refreshed automatically after expiring if it expires during a
        transaction that uses instance management (longrunning and sync).
        For the expiring transaction, we expect only 2 requests for auth and 2 Clients to be created. For the rest,
        only 1 request and 1 Client.
        """
        # GIVEN a glow process in which HPS has been authenticated.
        step = function_project.project.steps.custom_grpc_shared_instance_step
        method = step.initialize_custom_grpc_product_instance()
        interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        expected_msg = "No existing HPS authentication found, authenticating..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        assert not session_glow.text_in_output("Reusing existing valid HPS access token...", "api")

        # WHEN: transaction that queries instance mgmt system on loop, and in some iteration the token will
        # expire.
        session_glow.clear_output()
        method = getattr(step, method_name)
        if method_name == "query_instance_management_on_loop_lr":
            # timeout > cache > expiration, otherwise the client will not be recreated and token will not be checked.
            method(timeout=(hps_client_cache_ttl + 10)).wait()
        else:
            method(timeout=(hps_client_cache_ttl + 10))
        assert step.value == "True"

        # THEN: Token is refreshed automatically during the transaction, despite the continuous queries and initial
        # and final interactions with the instance management system, only 2 auth requests and 2 Clients created.
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        expected_msg = "HPS access token expired or invalid, refreshing token..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        expected_msg = "Reusing existing valid HPS access token."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1

        step.shutdown_custom_grpc_product_instance()

    def test_auth_token_expiration_using_hps_job_during_transaction(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        hps_client_cache_ttl: int,
        get_available_application_on_hps: Callable[[str], str],
    ):
        """
        This test verifies that the auth token for HPS is refreshed automatically after expiring if it expires during a
        transaction that uses HPS parametric studies (longrunning and sync).
        For the expiring transaction, we expect only 2 requests for auth and 2 Clients to be created. For the rest,
        only 1 request and 1 Client.
        """
        # GIVEN a glow process in which HPS has been authenticated.
        hps_job_step = function_project.project.steps.hps_simple_project_step
        python_version = get_available_application_on_hps("Python")
        method = hps_job_step.start_job_using_regular_python(python_version=python_version)
        interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        expected_msg = "No existing HPS authentication found, authenticating..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        assert not session_glow.text_in_output("Reusing existing valid HPS access token...", "api")

        # WHEN: transaction that queries HPS on loop, and in some iteration the token will expire.
        session_glow.clear_output()
        # timeout > cache > expiration, otherwise the client will not be recreated and token will not be checked.
        hps_job_step.query_hps_status_on_loop(timeout=int(hps_client_cache_ttl + 10)).wait()
        assert hps_job_step.hps_status == "evaluated"

        # THEN: Token is refreshed automatically during the transaction, despite the continuous queries,
        # only 2 auth requests and 2 Clients created.
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        expected_msg = "HPS access token expired or invalid, refreshing token..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        expected_msg = "Reusing existing valid HPS access token..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1


@pytest.mark.usefixtures("restore_default_hps_deployment")
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
# HPS Client cache should be enough to use a single Client during a transaction and slightly more than
# TOKEN_LIFESPAN_SECONDS to make sure tokens are requested again when the cache expires.
@pytest.mark.parametrize(
    ("deployment_type", "hps_auth_configuration_type", "hps_client_cache_ttl"),
    [("Desktop", HpsKeyCloakAuth, TOKEN_LIFESPAN_SECONDS + 5)],
    scope="session",
    indirect=["deployment_type"],
)
@pytest.mark.parametrize(
    "configure_hps_deployment_keycloak",
    [
        {
            "accessTokenLifespan": TOKEN_LIFESPAN_SECONDS,
            "ssoSessionIdleTimeout": TOKEN_LIFESPAN_SECONDS,
            "ssoSessionMaxLifespan": TOKEN_LIFESPAN_SECONDS,
        },
    ],
    ids=["60sec_refresh"],
    indirect=True,
)
class TestRefreshTokenExpiration:
    def test_refresh_token_expiration_between_transactions(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        This test verifies that the refresh token for HPS is requested interactively again after the automatic
        refresh fails due to the refresh token reaching its lifespan, between transactions.
        During each transaction we only expect 1 request for authentication and 1 Client created.
        """

        # GIVEN a glow process in which HPS has been authenticated.
        step = function_project.project.steps.custom_grpc_shared_instance_step
        method = step.initialize_custom_grpc_product_instance()
        interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        expected_msg = "No existing HPS authentication found, authenticating..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        assert not session_glow.text_in_output("Reusing existing valid HPS access token...", "api")

        # WHEN: The lifespan for the auth and refresh tokens has passed.
        # cache doesn't matter here, as a new transaction is launched.
        time.sleep(TOKEN_LIFESPAN_SECONDS + 1)

        # THEN: Token fails to refresh automatically if another transaction that requires HPS is launched. Instead,
        # a new interactive authentication is triggered.
        session_glow.clear_output()
        method = step.retrieve_value_custom_grpc_product_instance_long_running()
        interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        expected_msg = "HPS access token expired or invalid, refreshing token..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        expected_msg = (
            "Failed to refresh HPS token: (invalid_grant) Token is not active. Asking user for re-authentication..."
        )
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("Reusing existing valid HPS access token.", "api")

        # Authorization is reused when launching another transaction
        session_glow.clear_output()
        step.shutdown_custom_grpc_product_instance()
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        expected_msg = "Reusing existing valid HPS access token."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1

    @xfail_for_ci(reason="Flaky test, needs investigation")
    def test_refresh_token_expiration_using_instance_during_transaction(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        hps_client_cache_ttl: int,
    ):
        """
        This test verifies that the refresh token for HPS is requested interactively again after the automatic
        refresh fails due to the refresh token reaching its lifespan, during a transaction that queries HPS instance.
        For the expiring transaction, we expect only 2 requests for auth and 2 Clients to be created. For the rest,
        only 1 request and 1 Client.
        """
        # GIVEN a glow process in which HPS has been authenticated.
        step = function_project.project.steps.custom_grpc_shared_instance_step
        method = step.initialize_custom_grpc_product_instance()
        interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        expected_msg = "No existing HPS authentication found, authenticating..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        assert not session_glow.text_in_output("Reusing existing valid HPS access token...", "api")

        # WHEN: transaction that queries instance mgmt system on loop, and in some iteration the token will
        # expire.
        session_glow.clear_output()
        # timeout > cache > expiration, otherwise the client will not be recreated and token will not be checked.
        method = step.query_instance_management_on_loop_lr(timeout=(hps_client_cache_ttl + 10))
        # THEN: GLOW will try to refresh it, but the refresh token will also be expired, so a new
        # interactive authorization will be required.
        interactive_authorization(session_selenium_webdriver, session_glow, attempts=(hps_client_cache_ttl + 10))
        method.wait()
        assert step.value == "True"
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        expected_msg = "Reusing existing valid HPS access token."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        expected_msg = "HPS access token expired or invalid, refreshing token..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        expected_msg = (
            "Failed to refresh HPS token: (invalid_grant) Token is not active. Asking user for re-authentication..."
        )
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        step.shutdown_custom_grpc_product_instance()

    @xfail_for_ci(reason="Flaky test, needs investigation")
    def test_refresh_token_expiration_using_hps_job_during_transaction(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        hps_client_cache_ttl: int,
        get_available_application_on_hps: Callable[[str], str],
    ):
        """
        This test verifies that the refresh token for HPS is requested interactively again after the automatic
        refresh fails due to the refresh token reaching its lifespan, during a transaction that queries an HPS job.
        For the expiring transaction, we expect only 2 requests for auth and 2 Clients to be created. For the rest,
        only 1 request and 1 Client.
        """
        # GIVEN a glow process in which HPS has been authenticated.
        hps_job_step = function_project.project.steps.hps_simple_project_step
        python_version = get_available_application_on_hps("Python")
        method = hps_job_step.start_job_using_regular_python(python_version=python_version)
        interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        expected_msg = "No existing HPS authentication found, authenticating..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        assert not session_glow.text_in_output("Reusing existing valid HPS access token...", "api")

        # WHEN: transaction that queries HPS on loop, and in some iteration the token will expire.
        session_glow.clear_output()
        # timeout > cache > expiration, otherwise the client will not be recreated and token will not be checked.
        method = hps_job_step.query_hps_status_on_loop(timeout=(hps_client_cache_ttl + 10))
        # THEN: GLOW will try to refresh it, but the refresh token will also be expired, so a new
        # interactive authorization will be required.
        interactive_authorization(session_selenium_webdriver, session_glow, attempts=(hps_client_cache_ttl + 10))
        method.wait()
        assert hps_job_step.hps_status == "evaluated"
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        expected_msg = "Reusing existing valid HPS access token."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        expected_msg = "HPS access token expired or invalid, refreshing token..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        expected_msg = (
            "Failed to refresh HPS token: (invalid_grant) Token is not active. Asking user for re-authentication..."
        )
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1


@pytest.mark.usefixtures("restore_default_hps_deployment")
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
# HPS Client cache should be more than any transaction duration and than TOKEN_LIFESPAN_SECONDS, to make sure a single
# Client is used during the transaction, and expiration will only be detected by the HPS Client itself or in a new
# transaction.
@pytest.mark.parametrize(
    ("deployment_type", "hps_auth_configuration_type", "hps_client_cache_ttl"),
    [("Desktop", HpsKeyCloakAuth, TOKEN_LIFESPAN_SECONDS + 100)],
    scope="session",
    indirect=["deployment_type"],
)
@pytest.mark.parametrize(
    "configure_hps_deployment_keycloak",
    [{"accessTokenLifespan": TOKEN_LIFESPAN_SECONDS}],
    ids=["60sec_access"],
    indirect=True,
)
class TestHpsClientRefreshToken:
    @xfail_for_ci(reason="Flaky test, needs investigation")
    def test_hps_client_internally_refreshes_expired_token_and_glow_can_do_it_afterwards_too(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        This test verifies that the HPS Client is initiated with a refresh token. This means that:
        - Once the HPS Client is created, the HPS Client will retrieve an access token by itself.
        - If the same HPS Client is used after the access token expires (e.g., due to cache), the HPS Client will
        refresh the token by itself.
        - Even if the token is refreshed by the HPS Client, GLOW will still be able to detect that the initial token has
        expired (once the cache expires or in a new transaction), and also refresh it and create a new HPS Client with a
        fresh token.
        """
        step = function_project.project.steps.custom_grpc_shared_instance_step
        method = step.initialize_custom_grpc_product_instance()
        interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        expected_msg = "No existing HPS authentication found, authenticating..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert session_glow.text_in_output(
            ["ansys.hps.client.authenticate", "Retrieving access token for rep-jms-web from"],
            "api",
        )
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")
        assert not session_glow.text_in_output("Reusing existing valid HPS access token.", "api")

        session_glow.clear_output()
        # cache > timeout > expiration, so a single client is reused during the transaction, even if the token expires.
        step.query_instance_management_on_loop(timeout=(TOKEN_LIFESPAN_SECONDS + 10))
        expected_msg = "Reusing existing valid HPS access token."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert session_glow.text_in_output(
            ["ansys.hps.client.authenticate", "Retrieving access token for rep-jms-web from"],
            "api",
        )
        assert session_glow.text_in_output(
            ["ansys.hps.client.client", "401 authorization error: Trying to get a new access token."],
            "api",
        )
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        assert not session_glow.text_in_output("HPS access token expired or invalid, refreshing token...", "api")

        session_glow.clear_output()
        step.shutdown_custom_grpc_product_instance()
        assert not session_glow.text_in_output("No existing HPS authentication found, authenticating...", "api")
        expected_msg = "HPS access token expired or invalid, refreshing token..."
        assert len([line for line in session_glow.api_output if expected_msg in line]) == 1
        assert not session_glow.text_in_output("Reusing existing valid HPS access token.", "api")
        assert session_glow.text_in_output(
            ["ansys.hps.client.authenticate", "Retrieving access token for rep-jms-web from"],
            "api",
        )
