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

import httpx2
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from tests.e2e.conftest import (
    MINIMAL_SOLUTION_WITH_DASH_UI,
    OrchestrateSolution,
)


@retry(stop=stop_after_attempt(60), wait=wait_fixed(0.5))
def wait_for_method_completion(method_url: str):
    """Wait for a long-running method to complete via retry polling."""
    response = httpx2.get(method_url)
    if response.json()["status"] != "completed":
        raise TryAgain


def test_aspire_runs_without_insecure_warnings(
    orchestrate_solution: OrchestrateSolution,
    selenium_webdriver: WebDriver,
):
    """Test that no insecure warning message is shown on Aspire."""
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
    otel_url = process.get_otel_url()
    selenium_webdriver.get(otel_url)
    assert selenium_webdriver.find_elements(By.XPATH, "//*[contains(text(), 'Structured logs')]")
    assert not selenium_webdriver.find_elements(By.XPATH, "//*[contains(text(), 'Telemetry endpoint is unsecured')]")


@pytest.mark.parametrize(
    "portal_backend",
    ["projects-dashboard", "desktop-portal"],
    ids=["projects-dashboard", "desktop-portal"],
    indirect=True,
)
def test_services_traces_appear_in_aspire_dashboard(
    orchestrate_solution: OrchestrateSolution,
    selenium_webdriver: WebDriver,
    portal_backend: tuple[str, dict[str, str], Path | None],
):
    """Test that traces from GLOW API, GLOW METHOD RUNNER, GLOW UI and Portal are visible in Aspire dashboard."""
    args = [
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        MINIMAL_SOLUTION_WITH_DASH_UI + ".main",
        "--portal",
    ]

    backend, environment, python_exec = portal_backend
    process = orchestrate_solution(args=args, env=environment, python_exec=python_exec)

    if backend == "projects-dashboard":
        assert process.projects_dashboard_running()
        assert not process.portal_running()
    else:
        assert process.portal_running()
        assert not process.projects_dashboard_running()

    # Launch a long running method to ensure we have traces from the method runner in the OTLP data
    api_url = process.get_api_docs_url().replace("/docs", "/projects")
    project_name = httpx2.post(api_url, json={"display_name": "test_project"}).json()["name"]
    project_api_url = api_url.replace("projects", project_name)
    lr_method_url = project_api_url + "/steps/first-step:calculate-lr"
    httpx2.post(lr_method_url).raise_for_status()
    wait_for_method_completion(lr_method_url)

    otel_url = process.get_otel_url()
    selenium_webdriver.get(otel_url)
    if backend == "desktop-portal":
        assert selenium_webdriver.find_elements(By.XPATH, "//*[contains(text(), 'PORTAL')]")
    else:
        assert not selenium_webdriver.find_elements(By.XPATH, "//*[contains(text(), 'PORTAL')]")
    assert selenium_webdriver.find_elements(By.XPATH, "//*[contains(text(), 'GLOW API')]")
    assert selenium_webdriver.find_elements(By.XPATH, "//*[contains(text(), 'GLOW UI')]")
    assert selenium_webdriver.find_elements(By.XPATH, "//*[contains(text(), 'GLOW METHOD RUNNER')]")
