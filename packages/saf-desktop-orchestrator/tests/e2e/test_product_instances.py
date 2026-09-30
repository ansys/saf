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

import os
from pathlib import Path
import platform
import random

import httpx2
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.desktop.orchestrator._utilities.ip_utilities import get_local_ip, get_random_free_port
from ansys.saf.testing.platform_specific import linux_only, windows_only
from tests.e2e.conftest import MINIMAL_PIM_SOLUTION, OrchestrateSolution
from tests.e2e.orchestrator_process import OrchestratorProcess

TIMEOUT = 120  # seconds. Note that github-hosted runners can be very slow...


@pytest.fixture
def set_grpc_certificates(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    certificates_directory: Path,
) -> None:
    if getattr(request, "param", False):
        monkeypatch.setenv("ANSYS_GRPC_CERTIFICATES", certificates_directory.as_posix())


@pytest.fixture
def set_pim_host(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str | None:
    if pim_host := getattr(request, "param", None):
        monkeypatch.setenv("GLOW_PRODUCT_INSTANCE_SYSTEM_HOST", pim_host)
        return pim_host


@pytest.fixture
def log_to_file(request: pytest.FixtureRequest) -> bool:
    return getattr(request, "param", True)


@pytest.fixture
def solution_with_pim(
    orchestrate_solution: OrchestrateSolution,
    set_grpc_certificates: None,
    set_pim_host: str | None,
    log_to_file: bool,
) -> OrchestratorProcess:
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_PIM_SOLUTION + ".main",
        "--no-ui",
    ]
    if log_to_file:
        args.append("--log-to-file")

    process = orchestrate_solution(args=args)
    assert process.api_running()
    assert not process.ui_running()
    assert process.project_running()
    if log_to_file:
        assert process.find_msg_in_output("GLOW API logging to ")
        assert not process.otel_running()
    else:
        assert not process.find_msg_in_output("GLOW API logging to ")
        assert process.otel_running()
    assert process.pim_running()
    assert process.pim_logging()
    assert not process.portal_running()
    assert not process.additional_services_running()

    return process


def _use_shared_product_instance(step_url: str) -> None:
    with httpx2.Client(timeout=TIMEOUT) as http_client:
        assert http_client.get(step_url).json()["value"] == "blue"

        http_client.post(f"{step_url}:initialize-custom-product").raise_for_status()
        http_client.post(f"{step_url}:set-value-on-custom-product", json={"new_value": "red"}).raise_for_status()
        assert http_client.get(step_url).json()["value"] == "blue"

        http_client.post(f"{step_url}:retrieve-value-from-custom-product").raise_for_status()
        assert http_client.get(step_url).json()["value"] == "red"

        http_client.post(f"{step_url}:shutdown-custom-product").raise_for_status()

        r = http_client.post(f"{step_url}:retrieve-value-from-custom-product")
        assert r.status_code == 400
        expected_error_msg = (
            "The method has been called out of sequence. "
            "A shared product instance that this method uses has not been initialized."
        )
        assert r.json()["detail"] == expected_error_msg


def _verify_pim_log_contains_messages(log_file: Path) -> None:
    pim_logs = log_file.read_text()
    product_msgs = [
        "Starting instance instances/custom-http-product",
        "Get product instance for instances/custom-http-product",
        "Uvicorn running on http://0.0.0.0:",
        "GET /health HTTP/1.1",
        "GET /property HTTP/1.1",
        "POST /property HTTP/1.1",
        "Delete product instance for instances/custom-http-product",
    ]
    assert all(msg in pim_logs for msg in product_msgs)


def test_shared_product_instance(solution_with_pim: OrchestratorProcess):
    """
    Test that a solution that uses shared product instances is properly launched with PIM Light Server and that
    the transactions that use the shared product instance are successful. PIM light server and product logs should
    be available at the log file.
    """
    # PIM Light Server args
    if platform.system() == "Windows":
        expected_pim_args = r"--transport-mode=WNUA --urls=http://127\.0\.0\.1:\d+"
    else:
        expected_pim_args = r"--transport-mode=UDS --uds-dir=/.* --uds-id=\w+"
    assert solution_with_pim.find_msg_in_log_file(expected_pim_args, regex=True)

    # PIM Light Server URI printed to user
    expected_pim_uri = r"http://127\.0\.0\.1:\d+" if platform.system() == "Windows" else r"unix:/.*/pim-.*\.sock"
    assert solution_with_pim.find_msg_in_output(expected_pim_uri, regex=True)

    # Transactions are successful
    project_api_url = solution_with_pim.get_project_api_url()
    step_url = f"{project_api_url}/steps/custom-shared-instance-step"
    _use_shared_product_instance(step_url)

    # Product instance output is logged in PIM log file
    log_file = solution_with_pim.pim_logging()
    assert log_file is not None
    _verify_pim_log_contains_messages(log_file)


def test_unshared_product_instance(solution_with_pim: OrchestratorProcess):
    """
    Test that a solution that uses unshared product instances is properly launched with PIM Light Server and that
    the transactions that use the unshared product instance are successful. PIM light server and product logs should
    be available at the log file.
    """
    # PIM Light Server args
    if platform.system() == "Windows":
        expected_pim_args = r"--transport-mode=WNUA --urls=http://127\.0\.0\.1:\d+"
    else:
        expected_pim_args = r"--transport-mode=UDS --uds-dir=/.* --uds-id=\w+"
    assert solution_with_pim.find_msg_in_log_file(expected_pim_args, regex=True)

    # PIM Light Server URI printed to user
    expected_pim_uri = r"http://127\.0\.0\.1:\d+" if platform.system() == "Windows" else r"unix:/.*/pim-.*\.sock"
    assert solution_with_pim.find_msg_in_output(expected_pim_uri, regex=True)

    # Transactions are successful
    project_api_url = solution_with_pim.get_project_api_url()
    step_url = f"{project_api_url}/steps/custom-shared-instance-step"
    with httpx2.Client(timeout=TIMEOUT) as http_client:
        assert http_client.get(step_url).json()["value"] == "blue"
        http_client.post(f"{step_url}:use-unshared-custom-product", json={"new_value": "red"}).raise_for_status()
        assert http_client.get(step_url).json()["value"] == "red"

    # Product instance output is logged in PIM log file
    log_file = solution_with_pim.pim_logging()
    assert log_file is not None
    _verify_pim_log_contains_messages(log_file)


@windows_only(reason="pythonw not available on Linux")
def test_product_instance_with_pythonw(orchestrate_solution: OrchestrateSolution, tmp_path: Path):
    """
    Test that launching the orchestrator with pythonw works when the solution uses product instances and that
    the transactions that use the product instance are successful. PIM light server and product logs should be
    available at the log file.
    """

    @retry(stop=stop_after_attempt(30), wait=wait_fixed(1))
    def _is_project_listed(url: str, project_name: str):
        try:
            list_projects_json = httpx2.get(url).json()["projects"]
            for project in list_projects_json:
                if project["display_name"] == project_name:
                    project_identifier = project["name"]
                    return project_identifier
            raise TryAgain
        except Exception:
            raise TryAgain from None

    glow_api_port = str(get_random_free_port())
    project_name = f"my-project-{random.randint(0, 10000)}"
    orchestrator_env = os.environ.copy()
    orchestrator_env["GLOW_API_PORT"] = glow_api_port

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_PIM_SOLUTION + ".main",
        "--no-ui",
        "--project-display-name",
        project_name,
        "--log-to-file",
    ]
    orchestrate_solution(args=args, pythonw=True, env=orchestrator_env, wait_for_healthy=False)

    # Transactions are successful
    project_name = _is_project_listed(url=f"http://127.0.0.1:{glow_api_port}/projects", project_name=project_name)
    project_api_url = f"http://127.0.0.1:{glow_api_port}/{project_name}"
    step_url = f"{project_api_url}/steps/custom-shared-instance-step"
    _use_shared_product_instance(step_url)

    # Product instance output is logged in PIM log file
    log_file = tmp_path / "appdata" / "ansys" / "glow" / "ExportSolution" / "pim_light_server.log"
    assert log_file.is_file()
    _verify_pim_log_contains_messages(log_file)


@pytest.mark.parametrize("log_to_file", [False], indirect=True)
def test_product_instance_without_logging_to_file(solution_with_pim: OrchestratorProcess):
    """
    Test that launching the orchestrator without logging to file does not affect PIM Light server, which always logs
    to file.
    """
    # Transactions are successful
    project_api_url = solution_with_pim.get_project_api_url()
    step_url = f"{project_api_url}/steps/custom-shared-instance-step"
    _use_shared_product_instance(step_url)

    # Product instance output is logged in PIM log file
    log_file = solution_with_pim.pim_logging()
    assert log_file is not None
    _verify_pim_log_contains_messages(log_file)


@pytest.mark.parametrize("set_grpc_certificates", [True], indirect=True)
@pytest.mark.parametrize("set_pim_host", [get_local_ip()], indirect=True)
def test_non_localhost_product_instances(solution_with_pim: OrchestratorProcess, certificates_directory: Path):
    """
    Test that launching the orchestrator with a non-localhost host for PIM Light Server works and that
    the solution that uses shared product instances is properly launched and that the transactions that use the
    shared product instance are successful.
    """
    # PIM Light Server args
    expected_pim_args = (
        rf"--transport-mode=MTLS --urls=https://{get_local_ip()}:\d+ --certs-dir={certificates_directory.as_posix()}"
    )
    assert solution_with_pim.find_msg_in_log_file(expected_pim_args, regex=True)

    # PIM Light Server URI printed to user
    expected_pim_uri = rf"https://{get_local_ip()}:\d+"
    assert solution_with_pim.find_msg_in_output(expected_pim_uri, regex=True)

    # Transactions are successful
    project_api_url = solution_with_pim.get_project_api_url()
    step_url = f"{project_api_url}/steps/custom-shared-instance-step"
    _use_shared_product_instance(step_url)


@pytest.mark.parametrize("set_pim_host", [get_local_ip()], indirect=True)
@pytest.mark.usefixtures("set_pim_host")
def test_non_localhost_without_certificates_raises_error(orchestrate_solution: OrchestrateSolution):
    """
    Test that launching the orchestrator with a non-localhost host for PIM Light Server but without setting
    gRPC certificates raises an error.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_PIM_SOLUTION + ".main",
        "--log-to-file",
        "--no-ui",
    ]
    process = orchestrate_solution(args=args, wait_for_healthy=False, bg=False)
    assert process.return_code == 1
    assert process.find_msg_in_output("RuntimeError: PIM is running on a non-localhost IP without gRPC certificates.")


@pytest.mark.parametrize("set_grpc_certificates", [True], indirect=True)
def test_localhost_with_certificates_logs_a_warning(solution_with_pim: OrchestratorProcess):
    """
    Test that launching the orchestrator with a localhost host for PIM Light Server and setting
    gRPC certificates logs a warning to notify the user that they will be ignored.
    """
    assert solution_with_pim.find_msg_in_output(
        "PIM is running on a localhost IP with gRPC certificates. They will not be used.",
    )

    # PIM Light Server args
    if platform.system() == "Windows":
        expected_pim_args = r"--transport-mode=WNUA --urls=http://127\.0\.0\.1:\d+"
    else:
        expected_pim_args = r"--transport-mode=UDS --uds-dir=/.* --uds-id=\w+"
    assert solution_with_pim.find_msg_in_log_file(expected_pim_args, regex=True)

    # PIM Light Server URI printed to user
    expected_pim_uri = r"http://127\.0\.0\.1:\d+" if platform.system() == "Windows" else r"unix:/.*/pim-.*\.sock"
    assert solution_with_pim.find_msg_in_output(expected_pim_uri, regex=True)

    # Transactions are successful
    project_api_url = solution_with_pim.get_project_api_url()
    step_url = f"{project_api_url}/steps/custom-shared-instance-step"
    _use_shared_product_instance(step_url)


@linux_only()
def test_localhost_on_linux_with_port_logs_a_warning(
    monkeypatch: pytest.MonkeyPatch,
    orchestrate_solution: OrchestrateSolution,
):
    """
    Test that launching the orchestrator with a localhost host for PIM Light Server on Linux and with a port
    configured through environment variable logs a warning to notify the user that it will be ignored.

    Note that the warning is to notify that the orchestrator will not launch PIM Light Server on that port. However,
    the information from the environment variable still reaches GLOW, which then raises an error due to conflicting
    configuration.
    """
    monkeypatch.setenv("GLOW_PRODUCT_INSTANCE_SYSTEM_PORT", str(get_random_free_port()))

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_PIM_SOLUTION + ".main",
        "--log-to-file",
        "--no-ui",
    ]
    process = orchestrate_solution(args=args, wait_for_healthy=False, bg=False)
    assert process.return_code == 1

    expected_warning_msg = (
        "WARNING - PIM on Linux with a localhost IP can only be run with UDS. "
        "Ignoring the environment variable GLOW_PRODUCT_INSTANCE_SYSTEM_PORT."
    )
    assert process.find_msg_in_output(expected_warning_msg)
    assert process.find_msg_in_log_file(r"--transport-mode=UDS --uds-dir=/.* --uds-id=\w+", regex=True)

    expected_glow_error = (
        "Value error, Conflicting PIM configuration detected: both socket path (GLOW_PIM_SOCKET_PATH) "
        "and host/port (GLOW_PRODUCT_INSTANCE_SYSTEM_HOST/GLOW_PRODUCT_INSTANCE_SYSTEM_PORT) are provided."
    )
    assert process.find_msg_in_output(expected_glow_error)
