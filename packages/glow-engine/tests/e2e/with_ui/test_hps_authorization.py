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
import shutil
from threading import Thread
import time
from typing import TypeVar

import certifi
import httpx2
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.hps import GetHpsJobIdsType
from ansys.saf.testing.hps.scripts.hps_installer import HPS_DEPLOYMENTS_DIRECTORY
from ansys.saf.testing.selenium import wait_for_element_and_click, wait_for_text
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    CustomHPSClientTTLConfiguration,
    DefaultHPSClientTTLConfiguration,
    GlowBaseProcess,
    HpsAuthConfiguration,
    HpsKeyCloakAuth,
    HpsMissingAuth,
    HpsParametricSystemNoEnvVarConfig,
    HpsTokenPassThroughAuth,
    HpsUserPswdAuth,
    ProjectFixture,
)
from tests.e2e.conftest import interactive_authorization
import tests.mocks.solution_end_to_end.main as solution_end_to_end_module
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.hps_simple_project_step import HpsSimpleProjectStep
from tests.mocks.solution_end_to_end.solution.simple_job_step import SimpleJobStep

T = TypeVar("T", bound=Solution)

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_ui,
    pytest.mark.parametrize("ui_enabled", [True], indirect=True),
    pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True),
]

METHOD_ASSETS = Path(solution_end_to_end_module.__file__).parent / "method_assets"
HPS_CERTIFICATES_DIR = HPS_DEPLOYMENTS_DIRECTORY / "config" / "certificates"


def _get_hps_page(driver: WebDriver, project: ProjectFixture[EndToEndSolution]):
    driver.get(project.ui_url)
    wait_for_element_and_click(driver, "//*[contains(text(), 'Hps Page')]", element_type=By.XPATH)
    wait_for_text(driver, "hps_status", "Not triggered yet.")


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
            "client_secret": os.environ["TEST_REP_CLIENT_SECRET"],
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


@pytest.mark.xfail(reason="FIXME: HPS fails to start.")
@pytest.mark.parametrize(
    ("deployment_type", "hps_auth_configuration_type", "hps_client_cache_ttl"),
    [
        ("Desktop", HpsUserPswdAuth, None),
        ("Desktop", HpsKeyCloakAuth, None),
        ("Desktop", HpsMissingAuth, None),
        pytest.param("DockerCompose", HpsUserPswdAuth, None, marks=pytest.mark.use_containerized),
        pytest.param("DockerCompose", HpsTokenPassThroughAuth, None, marks=pytest.mark.use_containerized),
    ],
    scope="session",
    indirect=["deployment_type"],
)
@pytest.mark.parametrize(
    "configure_hps_deployment_traefik_tls_setup",
    ["server"],
    ids=["traefik_tls"],
    indirect=True,
)
@pytest.mark.usefixtures("inject_selenium_auth_header", "install_hps_certificates")
class TestHpsAuth:
    """These tests will spawn a web browser windows that can't be closed automatically. On the CI, it should run on a
    GitHub hosted runner. Enhancement suggestion #1540 tries to address this issue."""

    def test_hps_batch_job(
        self,
        authenticated_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        get_selenium_webdriver: Callable[[], WebDriver],
        get_available_application_on_hps: Callable[[str], str],
    ):
        """
        Launch an HPS job from within a Solution step method using GLOW's HPS API. Ensure authentication works when
        accessing the project properties from the Client. Ensure the project finishes successfully.
        """
        # GIVEN: environment variables are set for keycloak authorization (setup_environment fixture)
        step = authenticated_project.project.steps.hps_simple_project_step

        # THEN: Webbrowser authorization is triggered if an HPS job is launched from a longrunning transaction.
        python_version = get_available_application_on_hps("Python")
        method = step.start_job_using_regular_python(python_version=python_version)

        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            # This web browser auth is done once. It is implicit that auth will persist for the following HPS actions.
            interactive_authorization(get_selenium_webdriver(), session_glow)

        # Let the method finish
        method.wait()

        step.query_hps()  # Authorization reused when launching another sync transaction
        wait_for_hps_study_to_finish(step)
        assert step.python_name

        # Using the UI Dashclient to make it on-prem compatible.
        # Authorization reused when calling sync transaction from UI Callback
        _get_hps_page(session_selenium_webdriver, authenticated_project)
        wait_for_element_and_click(session_selenium_webdriver, "hps_status_check")
        wait_for_text(session_selenium_webdriver, "hps_status", "evaluated")

    def test_hps_batch_job_on_sync_transaction(
        self,
        authenticated_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        get_selenium_webdriver: Callable[[], WebDriver],
        get_available_application_on_hps: Callable[[str], str],
    ):
        """
        Test that an HPS parametric study is properly authenticated into HPS when working with sync transactions.
        Auth is reused in future interactions.
        """
        # GIVEN: environment variables are set for keycloak authorization (setup_environment fixture)
        step = authenticated_project.project.steps.hps_simple_project_step

        # WHEN: executing a longrunning transaction that submits a job to HPS
        python_version = get_available_application_on_hps("Python")
        method = step.start_job_using_regular_python(python_version=python_version)

        # THEN: Authentication is triggered if required and transaction ends OK
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            interactive_authorization(get_selenium_webdriver(), session_glow)
        method.wait()

        # GIVEN: fresh GLOW API server without stored tokens
        session_glow.restart()

        # WHEN: executing a sync transaction that queries a job to HPS
        # (separate thread so we can proceed with the interactive_authorization)
        query_hps_thread = Thread(target=step.query_hps, daemon=True)
        query_hps_thread.start()

        # THEN: Authentication is re-triggered and transaction ends OK
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            interactive_authorization(get_selenium_webdriver(), session_glow)
        try:
            query_hps_thread.join()
        except Exception as ex:
            pytest.fail(str(ex))

    @pytest.mark.parametrize(
        "method_name",
        ["initialize_custom_grpc_product_instance", "initialize_custom_grpc_product_instance_sync"],
    )
    def test_hps_instance_method(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        authenticated_project: ProjectFixture[EndToEndSolution],
        method_name: str,
    ):
        """
        With HPS as Product Instance System, launch a create_instance decorated transaction (sync and longrunning)
        which creates and uses a product instance.
        """
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsTokenPassThroughAuth):
            pytest.skip(reason="FIXME.")

        step = authenticated_project.project.steps.custom_grpc_shared_instance_step

        # WHEN: executing a sync / longrunning transaction that creates in an instance in HPS
        method = getattr(step, method_name)
        if method_name == "initialize_custom_grpc_product_instance":
            method = method()
        else:
            # separate thread so we can proceed with the interactive_authorization
            start_transaction_thread = Thread(target=method, daemon=True)
            start_transaction_thread.start()

        # THEN: Authentication is triggered if required
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            interactive_authorization(session_selenium_webdriver, session_glow)

        # THEN: and transaction ends OK
        if method_name == "initialize_custom_grpc_product_instance":
            method.wait()
        else:
            start_transaction_thread.join()  # type: ignore

        # WHEN: trying to use with the instance in another transaction
        # THEN: authentication is reused and transaction ends OK
        step.shutdown_custom_grpc_product_instance()

    def test_client_authentication(
        self,
        authenticated_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        get_selenium_webdriver: Callable[[], WebDriver],
        get_available_application_on_hps: Callable[[str], str],
    ):
        """
        Verify the Client method authenticate_hps works properly and that the authorization is persisted for methods
        executed after that for both instance systems and HPS jobs.
        """
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsTokenPassThroughAuth):
            pytest.skip(reason="FIXME")

        _get_hps_page(session_selenium_webdriver, authenticated_project)
        # Triggering .authenticate_hps() from a UI Callback
        wait_for_element_and_click(session_selenium_webdriver, "trigger_dashclient_auth")

        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            # Web browser auth is done once. It is implicit that auth will persist for the following HPS actions.
            interactive_authorization(get_selenium_webdriver(), session_glow)

        wait_for_text(session_selenium_webdriver, "auth_launched", "All good.", timeout=100)

        # Reusing authentication in future usages of HPS in sync and longrunning transactions, and for instances and
        # also parametric studies.
        instance_step = authenticated_project.project.steps.custom_grpc_shared_instance_step
        instance_step.initialize_custom_grpc_product_instance().wait()

        hps_job_step = authenticated_project.project.steps.hps_simple_project_step
        python_version = get_available_application_on_hps("Python")
        hps_job_step.start_job_using_regular_python(python_version=python_version).wait()

        instance_step.shutdown_custom_grpc_product_instance()
        wait_for_hps_study_to_finish(hps_job_step)

    def test_hps_api_server_outside_transaction(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        authenticated_client: Client[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
        get_hps_job_ids: GetHpsJobIdsType,
    ):
        """
        Test that the GLOW API server can authenticate into and interact with HPS system outside of transactions.
        Auth is reused in future interactions.
        """
        # GIVEN: Project in a freshly started GLOW API server without stored tokens
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsTokenPassThroughAuth):
            pytest.skip(reason="FIXME")
        project_fixture = ProjectFixture(session_glow, authenticated_client)
        step = project_fixture.project.steps.custom_grpc_shared_instance_step
        job_name = "custom-grpc-product-1-GLOW-Instance"
        old_job_ids = get_hps_job_ids(job_name, "running", [])

        # Launching a longrunning transaction that triggers HPS Authentication and creates an instance in HPS
        method = step.initialize_custom_grpc_product_instance()
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        new_job_ids = get_hps_job_ids(job_name, "running", old_job_ids)
        assert len(new_job_ids) == 1

        # Restart GLOW to clean up stored tokens
        session_glow.restart()

        # WHEN: Trying to use a route that requires HPS auth outside a transaction
        # (delete project -> deletes product instances -> deletes HPS jobs)
        project_fixture.project.delete()

        existing_job_ids = get_hps_job_ids(job_name, "running", old_job_ids)
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            # THEN: Authentication is not re-triggered, operation ends OK, but job is not deleted from HPS
            assert session_glow.text_in_output("HPS system un-authenticated. Cannot shutdown product instance.", "api")
            assert existing_job_ids == new_job_ids
        else:
            # THEN: Operation ends OK and job is deleted from HPS
            assert not existing_job_ids

    def test_hps_client_storage_scope(
        self,
        authenticated_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that HPS entity handles can be accessed from the glow client.
        """
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            pytest.skip(reason="FIXME")

        step = authenticated_project.project.steps.simple_job_step
        method = step.start_job()
        if isinstance(session_glow.applied_configurations["hps_auth_configuration"], HpsKeyCloakAuth | HpsMissingAuth):
            interactive_authorization(session_selenium_webdriver, session_glow)
        method.wait()
        step.query_hps()

        attempts = 0
        while step.step_state == SimpleJobStep.State.Calculating and attempts < 30:
            step.query_hps()
            time.sleep(2)
            attempts += 1

        step.fetch_file()
        result_path = authenticated_project.project.storage_scope.get_cached(step.result_handle)
        assert result_path.read_text() == "result=7.0"

    @pytest.mark.skip(reason="FIXME")
    def test_auth_ui_hps_storage_scope(
        self,
        authenticated_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that HPS entity handles can be accessed from Dash.
        """
        _get_hps_page(session_selenium_webdriver, authenticated_project)
        # page loads project info, step fields can be set and transactions work as expected.
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'First Page')]",
            element_type=By.XPATH,
        )
        wait_for_text(session_selenium_webdriver, "handle_from_hps", "No content yet")
        wait_for_element_and_click(session_selenium_webdriver, "read_hps_handle")
        wait_for_text(session_selenium_webdriver, "handle_from_hps", "Text: result=7.0", timeout=150)


@pytest.mark.parametrize(
    ("deployment_type", "hps_auth_configuration_type", "hps_client_cache_ttl"),
    [("Desktop", HpsParametricSystemNoEnvVarConfig, None)],
    scope="session",
    indirect=["deployment_type"],
)
@pytest.mark.parametrize(("with_custom_params"), [True, False], ids=["with_custom_params", "without_custom_params"])
def test_client_auth_with_custom_params(
    function_project: ProjectFixture[EndToEndSolution],
    session_glow: GlowBaseProcess[EndToEndSolution],
    session_selenium_webdriver: WebDriver,
    get_selenium_webdriver: Callable[[], WebDriver],
    with_custom_params: bool,
):
    """
    Verify the Client method authenticate_hps works properly with custom HPS params and that the authorization
    is persisted for methods executed after that.
    """
    _get_hps_page(session_selenium_webdriver, function_project)

    if with_custom_params:
        wait_for_element_and_click(session_selenium_webdriver, "trigger_dashclient_auth_custom_params")
    else:
        # Trigger authentication without custom HPS params to make it fail explicitly
        wait_for_element_and_click(session_selenium_webdriver, "trigger_dashclient_auth")
        wait_for_text(session_selenium_webdriver, "auth_launched", "Something went wrong.", timeout=100)
        return

    # This web browser auth is done once. It is implicit that auth will persist for the following HPS actions.
    interactive_authorization(get_selenium_webdriver(), session_glow)

    wait_for_text(session_selenium_webdriver, "custom_params_auth_launched", "All good.", timeout=100)
