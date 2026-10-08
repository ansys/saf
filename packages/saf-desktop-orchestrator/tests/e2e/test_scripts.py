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
import platform
from typing import Any

import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from ansys.saf.desktop.orchestrator._config.schema import SAF_DESKTOP_LOG_TO_FILES
from ansys.saf.testing.selenium import wait_for_element, wait_for_element_and_click, wait_for_element_and_send_text
from tests.conftest import copy_mock_solution_to_layout
from tests.e2e.app_starter_process import SolutionAppStarter


def verify_app_starter(
    selenium_webdriver: WebDriver,
    solution_app_starter: SolutionAppStarter,
    verify_step: Callable[[Any], None],
):
    # GIVEN: A running Solution App Starter
    project_display_name = solution_app_starter.get_project_display_name()
    project_id = solution_app_starter.get_project_id()
    solution_appdata = solution_app_starter.get_solution_appdata()

    # WHEN: Opening the solution UI
    selenium_webdriver.get(solution_app_starter.get_project_ui_url())

    # THEN: the project UI is loaded with the correct information and a transaction can be executed
    wait_for_element(selenium_webdriver, "page-content")
    verify_step(selenium_webdriver)

    # WHEN: Relaunching the Solution App Starter
    solution_app_starter.restart(clear_output=True)

    # THEN: it launches a new glow process using a different appdata and creates a new project
    assert solution_appdata != solution_app_starter.get_solution_appdata()
    assert project_display_name != solution_app_starter.get_project_display_name()
    assert project_id != solution_app_starter.get_project_id()


@pytest.mark.skipif(platform.system() == "Linux", reason="webview disabled temporarily on Linux")
@pytest.mark.parametrize("solution_app_starter", [True, False], ids=["input_archive", "input_dir"], indirect=True)
@pytest.mark.xfail(run=False, reason="App-starter startup health check currently times out in E2E.")
def test_solution_app_starter(selenium_webdriver: WebDriver, solution_app_starter: SolutionAppStarter):
    """
    Test running a solution with the Solution App Starter script. Ensure that it works either using an archived solution
    as input or the solution root directory.
    """

    def run_verification_step(selenium_webdriver: WebDriver):
        wait_for_element_and_click(selenium_webdriver, "//*[contains(text(), 'First Step')]", element_type=By.XPATH)
        wait_for_element_and_send_text(selenium_webdriver, "first-arg", "2")
        wait_for_element_and_send_text(selenium_webdriver, "second-arg", "3")
        wait_for_element_and_click(selenium_webdriver, "calculate")
        wait_for_element(selenium_webdriver, "//*[contains(text(), '5')]", element_type=By.XPATH)

    verify_app_starter(selenium_webdriver, solution_app_starter, run_verification_step)

    assert solution_app_starter.find_msg_in_log_file("Splash screen started.")
    assert solution_app_starter.find_msg_in_log_file("Splash screen stopped.")


@pytest.mark.skipif(platform.system() == "Linux", reason="webview disabled temporarily on Linux")
@pytest.mark.parametrize(
    "namespace_root",
    ["my_namespace", "ansys.solutions", "synopsys.solutions.platform"],
    ids=["single_namespace", "legacy_ansys_solutions", "deep_custom_namespace"],
)
def test_solution_app_starter_with_namespace_dir_input(
    selenium_webdriver: WebDriver,
    tmp_path: Path,
    namespace_root: str,
):
    """Smoke test namespace discovery in solution-app-starter with directory input."""
    copy_mock_solution_to_layout(
        src_dir=tmp_path / "src",
        solution_name="solution_with_minimal_dash_ui",
        namespace_root=namespace_root,
    )

    sas_process = SolutionAppStarter(tmp_path)
    try:
        sas_process.start()
        selenium_webdriver.get(sas_process.get_project_ui_url())
        wait_for_element(selenium_webdriver, "page-content")
    finally:
        sas_process.stop()


@pytest.mark.skipif(platform.system() == "Linux", reason="webview disabled temporarily on Linux")
@pytest.mark.parametrize("option", ["cli", "env", None])
@pytest.mark.xfail(run=False, reason="App-starter startup health check currently times out in E2E.")
def test_solution_app_starter_log_to_files(
    selenium_webdriver: WebDriver,
    archived_solution: Path,
    option: str | None,
):
    """
    Test running a solution with the Solution App Starter script. Ensure that it works either using an archived solution
    as input or the solution root directory.
    """

    match option:
        case "cli":
            sas_process = SolutionAppStarter(archived_solution, log_to_files=True)
        case "env":
            orchestrator_env = os.environ.copy()
            orchestrator_env[SAF_DESKTOP_LOG_TO_FILES] = "True"
            sas_process = SolutionAppStarter(archived_solution, env=orchestrator_env)
        case _:
            sas_process = SolutionAppStarter(archived_solution)

    sas_process.start()
    selenium_webdriver.get(sas_process.get_project_ui_url())
    wait_for_element(selenium_webdriver, "page-content")

    appdata = sas_process.get_solution_appdata()

    logfile = appdata / "ansys" / "glow" / "MySolution" / "orchestrator.log"
    assert logfile.exists()
    logdir = appdata / "ansys" / "glow" / "MySolution" / "logs"
    api_logdir = logdir / "api_server"
    ui_logdir = logdir / "ui_server"

    if option is not None:
        assert not sas_process.otel_running()
        assert api_logdir.is_dir()
        assert ui_logdir.is_dir()
        assert sas_process.find_msg_in_output("INFO - OTEL Dashboard: not launched")
    else:
        assert sas_process.otel_running()
        assert not api_logdir.is_dir()
        assert not ui_logdir.is_dir()
        assert sas_process.find_msg_in_output(r"OTEL Dashboard: http://127\.0\.0\.1:\d+", regex=True)

    if option is not None:
        for logname in ["API", "UI"]:
            log_search = f"GLOW {logname} logging to "
            match = sas_process.find_msg_in_output(log_search)
            assert match
            log_path = match[(match.rindex(log_search) + len(log_search)) :]
            assert Path(log_path).exists()
            assert logdir.expanduser().resolve().as_posix() in log_path

    sas_process.stop()
