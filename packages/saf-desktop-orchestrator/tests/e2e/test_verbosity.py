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

from pathlib import Path
import platform

from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from tests.e2e.conftest import MINIMAL_COMPLETE_SOLUTION, MINIMAL_SOLUTION_WITH_DASH_UI, OrchestrateSolution
from tests.e2e.orchestrator_process import OrchestratorProcess


def test_logging_verbosity_minimal_run(orchestrate_solution: OrchestrateSolution):
    """
    Test verbosity when orchestrator running with minimal possible services enabled: Solution API.

    Only clean and non-repetitive information should be printed to the user. DEBUG information is logged to file.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--no-ui",
        "--log-to-file",
    ]
    process = orchestrate_solution(args=args)

    assert process.api_running()
    assert not process.ui_running()
    assert process.project_running()
    assert not process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.projects_dashboard_started()
    assert not process.additional_services_running()

    # Remove lines from launched services
    output = [
        line
        for line in process.output
        if line.startswith(("DEBUG", "INFO", "WARNING", "ERROR", "- display name:", "- name:"))
    ]
    expected_output = [
        f"INFO - Extended logging available at {str(process.get_log_file_path())}",
        "INFO - Starting Solution API...",
        "INFO - Solution: My Solution",
        "INFO - Project:",
        f"- display name: {process.get_project_display_name()}",
        f"- name: {process.get_project_name()}",
        f"INFO - Solution API: {process.get_api_docs_url()}",
        "INFO - Solution UI: not launched",
        "INFO - OTEL Dashboard: not launched",
        "INFO - SAF Portal: not launched",
        "INFO - PIM Light Server: not launched",
        "INFO - Additional services: not launched",
    ]
    assert expected_output == output

    # Log file must contain everything above plus DEBUG information
    for line in expected_output:
        assert process.find_msg_in_log_file(line)
    assert process.find_msg_in_log_file("DEBUG -")
    assert not process.find_msg_in_log_file("DEBUG - Splash screen started.")
    assert not process.find_msg_in_log_file("DEBUG - Splash screen stopped.")
    assert not process.find_msg_in_log_file("DEBUG - Set custom icon for pywebview")


@retry(stop=stop_after_attempt(20), wait=wait_fixed(0.25))
def find_custom_icon_loaded(process: OrchestratorProcess, custom_icon_file: Path):
    if not process.find_msg_in_log_file(f"DEBUG - Set custom icon for pywebview from {custom_icon_file}"):
        raise TryAgain


# TODO: parametrize with projects-dashboard and with portal-desktop
def test_logging_verbosity_complete_run(orchestrate_solution: OrchestrateSolution, tmp_path: Path):
    """
    Test verbosity when orchestrator running with all possible services enabled: OTEL Dashboard, PIM Light Server,
    SAF Portal, Solution API, Solution UI and additional services; and loading an env file and a custom pywebview icon.

    Only clean and non-repetitive information should be printed to the user. DEBUG information is logged to file.
    """
    tmp_yaml_file = (
        Path(__file__).parent.parent / "integration" / "additional_services" / "additional_grpc_service.yaml"
    )
    assert tmp_yaml_file.is_file()
    env_file = tmp_path / ".env"
    env_file.write_text(f"SAF_DEFINITION_PATH={str(tmp_yaml_file)}")

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_COMPLETE_SOLUTION + ".main",
        "--portal",
        "--env-file",
        str(env_file),
    ]
    process = orchestrate_solution(args=args)

    projects_dashboard_started = process.projects_dashboard_started()
    assert process.api_running()
    assert process.ui_running(no_project=True)
    assert not process.project_running()
    assert process.otel_running()
    assert process.pim_running()
    if projects_dashboard_started:
        assert process.projects_dashboard_running()
        assert not process.portal_running()
    else:
        assert process.portal_running()
        assert not process.projects_dashboard_running()
    assert process.additional_services_running(yaml_file=Path(tmp_yaml_file))

    # Remove Warnings from product configurations, they will be handled separately
    # Also remove lines from launched services
    output = [
        line
        for line in process.output
        if not line.startswith("WARNING - The configuration for")
        and line.startswith(("DEBUG", "INFO", "WARNING", "ERROR", "- display name:", "- name:"))
    ]

    grpc_service_url = process.get_additional_services_urls(yaml_file=Path(tmp_yaml_file))["GRPC_SERVICE"]
    product_configs_dir = (
        Path(__file__).parent.parent / "mocks" / "solutions" / "minimal_complete_solution" / "product_instance_configs"
    )
    expected_output = [
        f"INFO - Extended logging available at {str(process.get_log_file_path())}",
        f"INFO - Environment variables loaded from {str(env_file)}",
        "INFO - Starting additional services...",
        "INFO - - Starting GRPC_SERVICE...",
        "INFO - Starting OTEL Dashboard...",
        "INFO - Starting PIM Light Server...",
        f"INFO - Found directory with product instance configurations: {product_configs_dir}",
        f"INFO - PIM Light Server logging to {str(process.pim_logging())}",
        f"INFO - Using PIM light command args: {str(process.pim_args())}",
        "INFO - Starting Solution API...",
        "INFO - Starting Solution UI...",
        "INFO - Solution: My Solution",
        "INFO - Project: no project created or selected",
        f"INFO - Solution API: {process.get_api_docs_url()}",
        f"INFO - Solution UI: {process.get_solution_ui_url(no_project=True)}",
        f"INFO - OTEL Dashboard: {process.get_otel_url()}",
        f"INFO - PIM Light Server: {process.get_pim_url()}",
        "INFO - Additional services:",
        f"INFO - - GRPC_SERVICE: {grpc_service_url}",
    ]
    if projects_dashboard_started:
        expected_output.insert(15, f"INFO - Projects Dashboard: {process.get_projects_dashboard_url()}")
        expected_output.insert(17, "INFO - SAF Portal: not launched")
    else:
        expected_output.insert(11, "INFO - Starting SAF Portal...")
        expected_output.insert(17, f"INFO - SAF Portal: {process.get_portal_ui_url()}")
    if platform.system() == "Windows":
        expected_output.append("INFO - Starting webview...")
    else:
        destination_url = (
            process.get_projects_dashboard_url() if projects_dashboard_started else process.get_portal_ui_url()
        )
        expected_output.append(f"INFO - Opening browser at {destination_url}...")
    assert expected_output == output

    # Log file must contain everything above plus DEBUG information
    for line in expected_output:
        assert process.find_msg_in_log_file(line)
    assert process.find_msg_in_log_file("DEBUG -")
    if platform.system() == "Windows":
        assert process.find_msg_in_log_file("DEBUG - Splash screen started.")
        assert process.find_msg_in_log_file("DEBUG - Splash screen stopped.")

    pywebview_custom_icon_path = (
        Path(__file__).parent.parent
        / "mocks"
        / "solutions"
        / "minimal_complete_solution"
        / "ui"
        / "assets"
        / "pywebview"
        / "favicon.ico"
    )
    assert pywebview_custom_icon_path.is_file()
    if platform.system() == "Windows":
        find_custom_icon_loaded(process, pywebview_custom_icon_path)
    else:
        assert not process.find_msg_in_log_file("DEBUG - Set custom icon for pywebview")
