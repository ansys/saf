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

import pytest
from selenium.webdriver.chrome.webdriver import WebDriver

from tests.e2e.conftest import (
    ExecuteCommand,
    InstallSolution,
    NewSolution,
    RunSolution,
    check_api_is_functional,
    check_ui_is_functional,
    configure_hps_solution,
)
from tests.e2e.saf_process import SAFProcess


@pytest.fixture
def solution_with_hps(
    new_solution: NewSolution,
    install_solution: InstallSolution,
    run_solution: RunSolution,
    execute_command: ExecuteCommand,
    tmp_path: Path,
    session_solution_namespace: str,
):
    """
    Setup a new solution configured to use HPS.
    """

    # Create a new solution.
    solution_name = "my_solution"
    new_solution(
        ["--solution-name", solution_name, "--namespace", session_solution_namespace],
        input_str="\n\n",
        cwd=tmp_path,
    )
    solution_dir = tmp_path / solution_name

    # Install the solution.
    install_solution([solution_name, "-d", "desktop,ui"])

    # update pyproject, first step and first page to use HPS.
    configure_hps_solution(solution_dir, solution_name, session_solution_namespace)
    # install HPS dependency
    install_solution([solution_name, "-d", "desktop,ui"])

    # Run the solution.
    p = run_solution([solution_name])
    return p


@pytest.fixture
def hps_env_vars_config(monkeypatch: pytest.MonkeyPatch):
    """Configure HPS environment variables."""

    monkeypatch.setenv("GLOW_HPS_HOST", "127.0.0.1")
    monkeypatch.setenv("GLOW_HPS_PORT", "8443")
    # HPS authentication
    monkeypatch.setenv("GLOW_HPS_USERNAME", "repadmin")
    monkeypatch.setenv("GLOW_HPS_PASSWORD", "repadmin")


@pytest.mark.parametrize("deployment_type", ["MultiContainer"], indirect=True)
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
def test_hps_job_submission(
    hps_scaler: None,
    hps_env_vars_config: None,
    solution_with_hps: SAFProcess,
    session_selenium_webdriver: WebDriver,
):
    """
    Test that a solution can submit a job to HPS and retrieve results correctly.
    """

    p = solution_with_hps

    # check job submission step is functional
    check_api_is_functional(p)
    check_ui_is_functional(session_selenium_webdriver, p, timeout=180)
