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

import importlib
import os
from pathlib import Path
import platform
import random
import subprocess

import httpx2
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.desktop.orchestrator._config.schema import (
    GLOW_PRODUCT_INSTANCE_SYSTEM,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    SAF_DESKTOP_LOG_TO_FILES,
)
from ansys.saf.desktop.orchestrator._utilities.ip_utilities import get_random_free_port
from ansys.saf.testing.common import find_exec_in_venv
from ansys.saf.testing.platform_specific import windows_only
from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_element_and_click,
    wait_for_text,
)
from tests.conftest import copy_mock_solution_to_layout
from tests.e2e.conftest import (
    MINIMAL_COMPLETE_SOLUTION,
    MINIMAL_DASH_UI_CUSTOM_SPLASH_SOLUTION,
    MINIMAL_SOLUTION_WITH_DASH_UI,
    MINIMAL_STREAMLIT_SOLUTION,
    OrchestrateSolution,
)

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("ansys.saf.aspire") is None,  # type: ignore
    reason="Install ansys-saf-aspire to run the tests in test_orchestrator_process.py module.",
)


@pytest.mark.parametrize(
    "solution_main_module",
    [
        MINIMAL_SOLUTION_WITH_DASH_UI,
        MINIMAL_DASH_UI_CUSTOM_SPLASH_SOLUTION,
    ],
)
def test_run_orchestrator_with_module(
    orchestrate_solution: OrchestrateSolution,
    mock_appdata: Path,
    solution_main_module: str,
):
    """
    Test running a solution with --solution-main-module-name option set to a valid name
    and verify that the correct solution is being executed and the UI, the API and OTEL are available.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        solution_main_module + ".main",
    ]

    process = orchestrate_solution(
        args=args,
    )

    if platform.system() == "Windows":
        assert process.find_msg_in_log_file("Splash screen started.")
        assert process.find_msg_in_log_file("Splash screen stopped.")
        if solution_main_module == MINIMAL_DASH_UI_CUSTOM_SPLASH_SOLUTION:
            expected_splash_image_path = (
                Path(__file__).parent.parent
                / "mocks"
                / "solutions"
                / "solution_with_minimal_dash_ui_custom_splash"
                / "ui"
                / "assets"
                / "orchestrator"
                / "splash.png"
            )
        else:
            expected_splash_image_path = (
                Path(__file__).parent.parent.parent
                / "src"
                / "ansys"
                / "saf"
                / "desktop"
                / "orchestrator"
                / "_assets"
                / "splash.png"
            )
        assert process.find_msg_in_log_file(f"Using splash image at {expected_splash_image_path}")

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.pim_logging()
    assert not process.portal_running()
    assert not process.additional_services_running()
    assert process.get_log_file_path()


def test_run_orchestrator_with_portal(orchestrate_solution: OrchestrateSolution):
    """
    Test running a solution with --portal option and verify the portal and OTEL are available on the expected address.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--portal",
    ]

    process = orchestrate_solution(
        args=args,
    )

    assert process.api_running()
    assert process.ui_running(no_project=True)
    assert not process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert process.portal_running()
    assert not process.additional_services_running()


@pytest.mark.parametrize("stop_orchestrator_after_yield", [False], indirect=True)
def test_run_orchestrator_with_portal_in_pre_load_mode(orchestrate_solution: OrchestrateSolution):
    """
    Test running a solution with --pre-load option and verify the AI and UI services are started
    and that the stack shuts down immediately.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--portal",
        "--pre-load",
    ]

    process = orchestrate_solution(
        args=args,
    )

    assert not process.find_msg_in_output("Splash screen started.")
    assert not process.find_msg_in_output("Splash screen stopped.")

    process.assert_started_and_shutting_down()


def test_run_orchestrator_with_no_ui(orchestrate_solution: OrchestrateSolution):
    """
    Test running a solution with --no-ui option and verify UI is not launched.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--no-ui",
    ]

    process = orchestrate_solution(
        args=args,
    )

    assert process.api_running()
    assert not process.ui_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()

    # --no-ui prevents showing the splash screen window even if the solution has a UI module
    assert not process.find_msg_in_log_file("Splash screen started.")
    assert not process.find_msg_in_log_file("Splash screen stopped.")


def test_run_orchestrator_with_browser(orchestrate_solution: OrchestrateSolution):
    """
    Test running a solution with --browser option and verify webview.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--browser",
    ]

    process = orchestrate_solution(
        args=args,
    )

    assert not process.find_msg_in_output("Starting webview")

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()


def test_run_orchestrator_with_project_display_name(
    orchestrate_solution: OrchestrateSolution,
):
    """
    Test running a solution that does not exist before and verify its creation.
    """

    def _check_project_not_exists(project_name: str) -> bool:
        try:
            response = httpx2.get(api_url.replace("/docs", f"/projects/{project_name}"))
            if "not found" in response.json()["detail"]:
                return True
        except Exception:
            pass

        return False

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]

    process = orchestrate_solution(
        args=args,
    )

    api_url = process.get_api_docs_url()

    random_project_name = f"my-random-project-name{random.randint(0, 10000)}"
    project_not_found = _check_project_not_exists(random_project_name)
    assert project_not_found

    process.stop()

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--project-display-name",
        random_project_name,
    ]

    process = orchestrate_solution(
        args=args,
    )

    assert process.find_msg_in_output(f"- display name: {random_project_name}")

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()

    api_url = process.get_api_docs_url()
    list_projects = httpx2.get(api_url.replace("/docs", "/projects"))
    assert any(project["display_name"] == random_project_name for project in list_projects.json()["projects"])


def test_run_orchestrator_with_custom_ports(orchestrate_solution: OrchestrateSolution):
    """
    Test running a solution with services on specific ports and verify that the services are available on those ports.
    """
    glow_api_port = str(get_random_free_port())
    glow_ui_port = str(get_random_free_port())
    glow_portal_port = str(get_random_free_port())
    otel_dashboard_port = str(get_random_free_port())

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--portal",
    ]

    orchestrator_env = os.environ.copy()
    orchestrator_env["GLOW_API_PORT"] = glow_api_port
    orchestrator_env["GLOW_UI_PORT"] = glow_ui_port
    orchestrator_env["PORTAL_UI_PORT"] = glow_portal_port
    orchestrator_env["OTEL_DASHBOARD_PORT"] = otel_dashboard_port

    process = orchestrate_solution(
        args=args,
        env=orchestrator_env,
    )

    assert glow_api_port in process.get_api_docs_url()
    assert glow_ui_port in process.get_solution_ui_url(no_project=True)
    assert glow_portal_port in process.get_portal_ui_url()
    assert otel_dashboard_port in process.get_otel_url()

    assert process.api_running()
    assert process.ui_running(no_project=True)
    assert not process.project_running()
    assert process.portal_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.additional_services_running()


def test_run_orchestrator_with_additional_services(orchestrate_solution: OrchestrateSolution):
    """
    Test running a solution with additional services and verify that those services are available.
    """
    tmp_yaml_file = Path(__file__).parent.parent / "integration" / "additional_services" / "additional_services.yaml"
    assert tmp_yaml_file.is_file()

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]

    orchestrator_env = os.environ.copy()
    orchestrator_env["SAF_DEFINITION_PATH"] = str(tmp_yaml_file)

    process = orchestrate_solution(
        args=args,
        env=orchestrator_env,
    )

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert process.additional_services_running(yaml_file=Path(tmp_yaml_file))


@windows_only(reason="pythonw not available on Linux")
@pytest.mark.parametrize("portal", [True, False], ids=["with_portal", "without_portal"])
def test_run_orchestrator_with_pythonw(orchestrate_solution: OrchestrateSolution, portal: bool, tmp_path: Path):
    """
    Test running a solution with pythonw and verify that all services are available.
    """

    @retry(stop=stop_after_attempt(40), wait=wait_fixed(1))
    def _is_project_listed(url: str, project_name: str):
        try:
            list_projects_json = httpx2.get(url).json()["projects"]
            for project in list_projects_json:
                if project["display_name"] == project_name:
                    project_identifier = project["name"].removeprefix("projects/")
                    return project_identifier
            raise TryAgain
        except Exception:
            raise TryAgain from None

    @retry(stop=stop_after_attempt(30), wait=wait_fixed(1))
    def _check_service_health(url: str):
        try:
            if not httpx2.get(url).status_code == 200:
                raise TryAgain
        except Exception:
            raise TryAgain from None

    glow_api_port = str(get_random_free_port())
    glow_ui_port = str(get_random_free_port())
    otel_dashboard_port = str(get_random_free_port())
    project_name = f"my-project-{random.randint(0, 10000)}"

    orchestrator_env = os.environ.copy()
    orchestrator_env["GLOW_API_PORT"] = glow_api_port
    orchestrator_env["GLOW_UI_PORT"] = glow_ui_port
    orchestrator_env["OTEL_DASHBOARD_PORT"] = otel_dashboard_port

    glow_portal_port = ""
    if portal:
        glow_portal_port = str(get_random_free_port())
        orchestrator_env["PORTAL_UI_PORT"] = glow_portal_port

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]
    args += ["--portal"] if portal else ["--project-display-name", project_name]

    orchestrate_solution(
        args=args,
        pythonw=True,
        env=orchestrator_env,
        wait_for_healthy=False,
    )

    if glow_portal_port:
        _check_service_health(f"http://127.0.0.1:{glow_portal_port}")
        _check_service_health(f"http://127.0.0.1:{glow_ui_port}")
    else:
        project_identifier = _is_project_listed(
            url=f"http://127.0.0.1:{glow_api_port}/projects",
            project_name=project_name,
        )
        _check_service_health(f"http://127.0.0.1:{glow_ui_port}/projects/{project_identifier}")
    _check_service_health(f"http://127.0.0.1:{glow_api_port}/docs")
    _check_service_health(f"http://127.0.0.1:{otel_dashboard_port}/structuredLogs")

    # Orchestrator output is still logged in log file
    log_file = tmp_path / "appdata" / "ansys" / "glow" / "MySolution" / "orchestrator.log"
    assert log_file.is_file()
    log_content = log_file.read_text()
    assert "Starting Solution API..." in log_content


def test_run_orchestrator_with_streamlit_ui_option(
    orchestrate_solution: OrchestrateSolution,
    selenium_webdriver: WebDriver,
):
    """
    Test running a solution with Streamlit UI option and verify Streamlit is running.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_STREAMLIT_SOLUTION + ".main",
        "--streamlit-ui",
    ]

    process = orchestrate_solution(
        args=args,
    )

    assert process.find_msg_in_output("  You can now view your Streamlit app in your browser.")

    ui_url_output = process.find_msg_in_output("Solution UI: ")
    assert ui_url_output
    ui_url = ui_url_output.removeprefix("INFO - Solution UI: ")
    selenium_webdriver.get(ui_url)

    calculation_text_to_search = "first_arg : 8 , second_arg : 9 and result : 17.0"
    calculation_element_id = "first-arg-8-second-arg-9-and-result-17-0"
    wait_for_text(selenium_webdriver, calculation_element_id, calculation_text_to_search, timeout=40)

    # Switch to iframe from Streamlit component
    iframe = wait_for_element(selenium_webdriver, "iframe", element_type=By.TAG_NAME)
    selenium_webdriver.switch_to.frame(iframe)

    wait_for_element_and_click(
        selenium_webdriver,
        "//span[@class='ant-menu-title-content' and text()='Second']",
        element_type=By.XPATH,
    )

    # Switch to the main content
    selenium_webdriver.switch_to.default_content()

    hello_world_text_to_search = "Hello World from Second Page!!!!!"
    hello_world_element_id = "hello-world-from-second-page"
    wait_for_text(selenium_webdriver, hello_world_element_id, hello_world_text_to_search)

    assert process.api_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()


@pytest.mark.parametrize("pass_type", ["cwd", "absolute_path", "relative_path"])
def test_run_orchestrator_with_env_file(orchestrate_solution: OrchestrateSolution, pass_type: str, tmp_path: Path):
    """
    Test running a solution and configuring it with an env file, either placed at CWD or passing its
    absolute/relative path with --env-file option.
    """
    glow_api_port = str(get_random_free_port())
    glow_ui_port = str(get_random_free_port())

    env_file = tmp_path / "subdir" / ".env"
    env_file.parent.mkdir()
    env_file.write_text(f"GLOW_API_PORT={glow_api_port}\nGLOW_UI_PORT={glow_ui_port}")

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]
    if pass_type == "absolute_path":
        args.extend(["--env-file", str(env_file.resolve())])
    elif pass_type == "relative_path":
        args.extend(["--env-file", str(env_file.relative_to(tmp_path))])

    orchestrator_env = os.environ.copy()
    if pass_type in ("cwd", "relative_path"):
        orchestrator_env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent)

    cwd = env_file.parent if pass_type == "cwd" else tmp_path if pass_type == "relative_path" else None

    process = orchestrate_solution(
        args=args,
        cwd=cwd,
        env=orchestrator_env,
    )

    expected_api_log_line = (
        f"starting process run_api with args: '[]' and kwargs: '{{'host': '127.0.0.1', 'port': {glow_api_port}, "
        f"'definition_module': '{MINIMAL_SOLUTION_WITH_DASH_UI}.solution.definition', "
        f"'env_file': WindowsPath('{env_file.resolve().as_posix()}')}}'"
    )
    if platform.system() == "Linux":
        expected_api_log_line = expected_api_log_line.replace("WindowsPath", "PosixPath")
    assert process.find_msg_in_log_file(expected_api_log_line)

    expected_ui_log_line = f"-m {MINIMAL_SOLUTION_WITH_DASH_UI}.main ui --env-file {env_file.resolve()}"
    assert process.find_msg_in_log_file(expected_ui_log_line)

    assert glow_api_port in process.get_api_docs_url()
    assert glow_ui_port in process.get_solution_ui_url()

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()


def test_run_orchestrator_passing_env_file_makes_glow_ignore_file_in_cwd(
    orchestrate_solution: OrchestrateSolution,
    tmp_path: Path,
):
    """
    Test using the --env-file option, propagates the file to the underlying GLOW services, thus making them ignore any
    .env at their CWD.
    """
    glow_api_port = str(get_random_free_port())
    project_files_dir = tmp_path / "project_files"

    env_file = tmp_path / "subdir" / ".env"
    env_file.parent.mkdir()
    env_file.write_text(f"GLOW_API_PORT={glow_api_port}")

    # a second file in the CWD that should be ignored
    cwd = tmp_path
    (cwd / ".env").write_text(f"GLOW_PROJECT_FILES_DIRECTORY={project_files_dir}")

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        f"{MINIMAL_SOLUTION_WITH_DASH_UI}.main",
        "--env-file",
        str(env_file.resolve()),
    ]

    orchestrator_env = os.environ.copy()
    orchestrator_env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent)

    orchestrate_solution(
        args=args,
        cwd=cwd,
        env=orchestrator_env,
    )

    # project files are saved in default dir and not in the one specified in the env located at the CWD
    assert not project_files_dir.is_dir()

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        f"{MINIMAL_SOLUTION_WITH_DASH_UI}.main",
    ]

    # relaunching without passing --env-file, GLOW will load the env located in the CWD
    process_2 = orchestrate_solution(
        args=args,
        cwd=cwd,
        env=orchestrator_env,
    )

    # project files are saved in the dir specified in the env located at the CWD
    assert (project_files_dir / process_2.get_project_name().split("/")[-1]).is_dir()


@pytest.mark.xfail(reason="Portal does not support passing a path for the .env file, always loads the one in the CWD.")
def test_run_orchestrator_passing_env_file_makes_portal_ignore_file_in_cwd(
    orchestrate_solution: OrchestrateSolution,
    tmp_path: Path,
):
    """
    Test using the --env-file option, propagates the file to the underlying Portal service, thus making it ignore any
    .env at its CWD.

    Fails because Portal always tries to load the .env file from its CWD and doesn't support passing a custom path.
    """
    glow_api_port = str(get_random_free_port())
    portal_db_file = tmp_path / "projects.db`"

    env_file = tmp_path / "subdir" / ".env"
    env_file.parent.mkdir()
    env_file.write_text(f"GLOW_API_PORT={glow_api_port}")

    # a second file in the CWD that should be ignored
    cwd = tmp_path
    (cwd / ".env").write_text(f"PORTAL_PROJECT_DATABASE_LOCATION={portal_db_file}")

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        f"{MINIMAL_SOLUTION_WITH_DASH_UI}.main",
        "--env-file",
        str(env_file.resolve()),
        "--portal",
    ]

    orchestrator_env = os.environ.copy()
    orchestrator_env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent)

    orchestrate_solution(
        args=args,
        cwd=cwd,
        env=orchestrator_env,
    )

    # Portal creates DB at default location and not in the path specified at the env located in the CWD
    assert not portal_db_file.is_file()

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        f"{MINIMAL_SOLUTION_WITH_DASH_UI}.main",
        "--portal",
    ]

    # relaunching without passing --env-file, GLOW will load the env located in the CWD
    orchestrate_solution(
        args=args,
        cwd=cwd,
        env=orchestrator_env,
    )

    # Portal creates DB at the path specified in the env located at the CWD
    assert portal_db_file.is_file()


def test_services_logs_on_otlp(orchestrate_solution: OrchestrateSolution, tmp_path: Path):
    """
    Test that services logs are sent to OTLP and not printed to the console.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--portal",
    ]

    process = orchestrate_solution(
        args=args,
    )

    process_output = " ".join(process.output)
    assert process_output.count("service.name=GLOW API") >= 1
    assert process_output.count("service.name=GLOW UI") >= 1
    assert "Running portal server with API version" not in process_output


def test_run_orchestrator_with_minimal_timeout(orchestrate_solution: OrchestrateSolution):
    """
    Test running a solution with SAF_DESKTOP_HEALTH_CHECK_TIMEOUT set up to 0 and check that it raises
    an error.
    """
    tmp_yaml_file = Path(__file__).parent.parent / "integration" / "additional_services" / "additional_services.yaml"
    assert tmp_yaml_file.is_file()

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]

    orchestrator_env = os.environ.copy()
    orchestrator_env["SAF_DESKTOP_HEALTH_CHECK_TIMEOUT"] = "0"
    orchestrator_env["SAF_DEFINITION_PATH"] = str(tmp_yaml_file)

    p = orchestrate_solution(
        args=args,
        env=orchestrator_env,
        wait_for_healthy=False,
        bg=False,
    )

    assert p.find_msg_in_output("Unable to connect to healthy service HTTP_SERVICE after startup")
    assert p.find_msg_in_output("Unable to connect to healthy service GRPC_SERVICE after startup")
    assert p.find_msg_in_output("RuntimeError: tries is less than one")
    assert p.return_code != 0


@pytest.mark.parametrize("automatic_project_migration", [True, False], ids=["enable", "disable"])
def test_run_orchestrator_with_automatic_project_migration(
    orchestrate_solution: OrchestrateSolution,
    automatic_project_migration: bool,
    tmp_path: Path,
):
    """
    Test running a solution with and without --no-automatic-project-migration and trying to upgrade a project
    from an older solution schema.
    """
    solution_src_dir, _, _, module_name = copy_mock_solution_to_layout(
        tmp_path / "src",
        "solution_with_minimal_dash_ui",
        "my_org.my_solutions",
    )

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        module_name,
    ]
    if not automatic_project_migration:
        args.append("--no-automatic-project-migration")

    orchestrator_env = os.environ.copy()
    orchestrator_env["PYTHONPATH"] = str(tmp_path / "src")
    p = orchestrate_solution(args=args, env=orchestrator_env)
    first_project_name = p.get_project_name()
    r = httpx2.get(p.get_project_api_url())
    assert r.status_code == 200

    # WHEN: Modifying the solution schema by adding a new field to the first step and relaunching the solution
    definition_file = solution_src_dir / "solution" / "definition.py"
    assert definition_file.is_file()
    definition_file.write_text(
        definition_file.read_text().replace(
            "result: float = 0",
            "result: float = 0\n    new_step_field: int = 0",
        ),
    )
    p.restart(clear_output=True)

    # THEN: Trying to retrieve the old project raises an error.
    first_project_api_url = p.get_api_docs_url().replace("docs", first_project_name)
    r = httpx2.get(first_project_api_url)
    assert r.status_code == 422
    assert "extra step fields are not allowed without upgrading the solution." in r.json()["detail"]

    # WHEN: Upgrading the project to the new solution schema, fails if automatic solution upgrades are disabled.
    r = httpx2.post(f"{first_project_api_url}:upgrade")
    if not automatic_project_migration:
        assert r.status_code == 422
        assert "Step 'first_step' is missing fields ['new_step_field']" in r.json()["detail"]
    else:
        assert r.status_code == 200

    # THEN: The project is now accessible again if automatic solution upgrades are enabled.
    #       Otherwise, remains inaccessible.
    r = httpx2.get(first_project_api_url)
    if not automatic_project_migration:
        assert r.status_code == 422
        assert "extra step fields are not allowed without upgrading the solution." in r.json()["detail"]
    else:
        assert r.status_code == 200


@pytest.mark.parametrize("option_from_cli", [True, False], ids=("cli", "env"))
def test_run_orchestrator_with_filelogs(
    orchestrate_solution: OrchestrateSolution,
    tmp_path: Path,
    option_from_cli: bool,
):
    """
    Test running a solution with --log-to-files option and verify that the logs are being written
    to files in appdata and that the otel dashboard (aspire) is not launched.
    """
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]

    if option_from_cli:
        args.append("--log-to-files")
        process = orchestrate_solution(
            args=args,
        )
    else:
        orchestrator_env = os.environ.copy()
        orchestrator_env[SAF_DESKTOP_LOG_TO_FILES] = "1"  # use something different than "True" to test parsing
        process = orchestrate_solution(
            args=args,
            env=orchestrator_env,
        )

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert not process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()

    assert process.get_log_file_path()

    logdir = tmp_path / "appdata" / "ansys" / "glow" / "MySolution" / "logs"
    api_logdir = logdir / "api_server"
    assert api_logdir.is_dir()
    ui_logdir = logdir / "ui_server"
    assert ui_logdir.is_dir()

    assert process.find_msg_in_output("INFO - OTEL Dashboard: not launched")

    for logname in ["API", "UI"]:
        log_search = f"GLOW {logname} logging to "
        match = process.find_msg_in_output(log_search)
        assert match
        log_path = match[(match.rindex(log_search) + len(log_search)) :]
        assert Path(log_path).exists()
        assert logdir.expanduser().resolve().as_posix() in log_path


@pytest.mark.parametrize("option_from_cli", [True, False], ids=("cli", "env"))
def test_run_orchestrator_with_filelogs_and_otel_env_var(option_from_cli: bool, monkeypatch: pytest.MonkeyPatch):
    """
    Test that running a solution with --log-to-files option and OTEL_EXPORTER_OTLP_ENDPOINT env var
    raises an error.
    """
    monkeypatch.setenv(OTEL_EXPORTER_OTLP_ENDPOINT, "something")
    python_exec = find_exec_in_venv(Path.cwd(), "python")
    args = [
        python_exec,
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]
    if option_from_cli:
        args.append("--log-to-files")
    else:
        monkeypatch.setenv(SAF_DESKTOP_LOG_TO_FILES, "on")  # use something different than "True" to test parsing
    process = subprocess.run(args, text=True, capture_output=True)
    assert process.returncode == 1
    assert (
        "The env var 'OTEL_EXPORTER_OTLP_ENDPOINT' is defined but it is not compatible with logging to files."
        in process.stderr
    )


def test_run_orchestrator_with_filelogs_env_var_set_to_false(
    monkeypatch: pytest.MonkeyPatch,
    orchestrate_solution: OrchestrateSolution,
):
    """
    Test that running a solution SAF_DESKTOP_LOG_TO_FILES env var configured with a negative value does not enable
    the option and keeps OTEL enabled.
    """
    monkeypatch.setenv(SAF_DESKTOP_LOG_TO_FILES, "f")  # use something different than "False" to test parsing
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]
    process = orchestrate_solution(args=args)

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()

    for logname in ["API", "UI"]:
        log_search = f"GLOW {logname} logging to "
        assert not process.find_msg_in_output(log_search)


def test_run_orchestrator_with_log_to_otel_dashboard_but_aspire_not_installed(
    orchestrate_solution: OrchestrateSolution,
    tmp_path: Path,
):
    """
    Test that running a solution without --log-to-files option when aspire is not installed logs to files.
    """
    # Inject a sitecustomize.py that patches find_spec to return None for ansys.saf.aspire in the subprocess
    mock_dir = tmp_path / "_mock_no_aspire"
    mock_dir.mkdir()
    (mock_dir / "sitecustomize.py").write_text(
        "import importlib.util\n"
        "_orig_find_spec = importlib.util.find_spec\n"
        "def _patched_find_spec(name, *args, **kwargs):\n"
        "    if name == 'ansys.saf.aspire':\n"
        "        return None\n"
        "    return _orig_find_spec(name, *args, **kwargs)\n"
        "importlib.util.find_spec = _patched_find_spec\n",
    )
    orchestrator_env = os.environ.copy()
    orchestrator_env["PYTHONPATH"] = str(mock_dir) + os.pathsep + orchestrator_env.get("PYTHONPATH", "")

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
    ]

    process = orchestrate_solution(args=args, env=orchestrator_env)

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert not process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()

    assert process.get_log_file_path()

    logdir = tmp_path / "appdata" / "ansys" / "glow" / "MySolution" / "logs"
    api_logdir = logdir / "api_server"
    assert api_logdir.is_dir()
    ui_logdir = logdir / "ui_server"
    assert ui_logdir.is_dir()

    assert process.find_msg_in_output("INFO - OTEL Dashboard: not launched")
    expected_aspire_warning = (
        "ansys.saf.aspire module not found, falling back to logging to files. "
        "If you want to use OTEL dashboard, make sure ansys-saf-aspire is installed."
    )
    assert process.find_msg_in_output(expected_aspire_warning)

    for logname in ["API", "UI"]:
        log_search = f"GLOW {logname} logging to "
        match = process.find_msg_in_output(log_search)
        assert match
        log_path = match[(match.rindex(log_search) + len(log_search)) :]
        assert Path(log_path).exists()
        assert logdir.expanduser().resolve().as_posix() in log_path


def test_run_orchestrator_with_hps_as_product_instance_system(
    monkeypatch: pytest.MonkeyPatch,
    orchestrate_solution: OrchestrateSolution,
):
    """
    Test that PIM is not started when setting GLOW_PRODUCT_INSTANCE_SYSTEM
    to HPS when the solution has shared instances.
    """
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "HPS")
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_COMPLETE_SOLUTION + ".main",
    ]
    process = orchestrate_solution(args=args)

    assert process.api_running()
    assert process.ui_running()
    assert process.project_running()
    assert process.otel_running()
    assert not process.pim_running()
    assert not process.portal_running()
    assert not process.additional_services_running()


@pytest.mark.parametrize("no_proxy_env_var", [None, "", "fake,values", "localhost", "127.0.0.1", "::1"])
def test_run_orchestrator_with_http_proxy_env_vars_set(
    orchestrate_solution: OrchestrateSolution,
    no_proxy_env_var: str | None,
    selenium_webdriver: WebDriver,
):
    """
    Test that the orchestrator stack starts successfully when HTTP(S)_PROXY is set.
    """
    tmp_yaml_file = Path(__file__).parent.parent / "integration" / "additional_services" / "additional_services.yaml"
    assert tmp_yaml_file.is_file()

    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_COMPLETE_SOLUTION + ".main",
        "--portal",
    ]

    orchestrator_env = os.environ.copy()
    if no_proxy_env_var is not None:
        orchestrator_env["NO_PROXY"] = no_proxy_env_var
        orchestrator_env["no_proxy"] = no_proxy_env_var
    orchestrator_env["HTTP_PROXY"] = "http://myproxy:8080"
    orchestrator_env["HTTPS_PROXY"] = "https://myproxy:8080"
    orchestrator_env["SAF_DEFINITION_PATH"] = str(tmp_yaml_file)
    process = orchestrate_solution(args=args, env=orchestrator_env)

    assert process.api_running()
    assert process.ui_running(no_project=True)
    assert not process.project_running()
    assert process.otel_running()
    assert process.pim_running()
    assert process.portal_running()
    assert process.additional_services_running(yaml_file=Path(tmp_yaml_file))

    selenium_webdriver.get(process.get_portal_ui_url())
    project_display_name = f"proxy-project-{random.randint(0, 10000)}"

    wait_for_element_and_click(
        selenium_webdriver,
        "[data-cy='add_new_project']",
        timeout=30,
        element_type=By.CSS_SELECTOR,
    )
    wait_for_element(
        selenium_webdriver,
        "[data-cy='new_project_dialog']",
        timeout=30,
        element_type=By.CSS_SELECTOR,
    )
    # The project name field is an `awc-input` web component whose actual <input> lives in its shadow DOM,
    # so it must be reached through the shadow root instead of a light-DOM CSS selector.
    project_name_host = wait_for_element(
        selenium_webdriver,
        "[data-cy='project_name_input']",
        timeout=30,
        element_type=By.CSS_SELECTOR,
    )
    project_name_field = WebDriverWait(selenium_webdriver, 30).until(  # pyright: ignore[reportUnknownVariableType]
        lambda _: project_name_host.shadow_root.find_element(  # pyright: ignore[reportUnknownLambdaType]
            By.CSS_SELECTOR,
            "input",
        ),
    )
    project_name_field.send_keys(project_display_name)  # pyright: ignore[reportUnknownMemberType]
    wait_for_element_and_click(
        selenium_webdriver,
        "[data-cy='create_new_project']",
        timeout=30,
        element_type=By.CSS_SELECTOR,
    )

    # In portal mode no project exists at startup, so the orchestrator log has no project-scoped UI URL.
    # The portal creates the project asynchronously, so poll the API until it shows up by its display name.
    projects_url = process.get_api_docs_url().replace("/docs", "/projects")

    @retry(stop=stop_after_attempt(30), wait=wait_fixed(1))
    def _get_created_project_id() -> str:
        response = httpx2.get(projects_url, params={"filter": f'display_name = "{project_display_name}"'})
        projects = response.json()["projects"]
        if not projects:
            raise TryAgain
        return projects[0]["name"].removeprefix("projects/")

    project_id = _get_created_project_id()

    selenium_webdriver.get(f"{process.get_solution_ui_url(no_project=True)}/projects/{project_id}")
    wait_for_element(selenium_webdriver, "launch-custom-product", timeout=40)
    wait_for_element_and_click(selenium_webdriver, "launch-custom-product")
    wait_for_text(selenium_webdriver, "custom-product-result", "green", timeout=120)
