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

"""Check the projects dashboard of the solution launched in portal mode.

The desktop installer adds ``--portal`` to the shortcut when the lock file contains
ansys-saf-projects-dashboard. The solution launched by the shortcut therefore runs in portal
mode, and the desktop orchestrator opens the projects dashboard instead of a project.
"""

import re
from urllib.parse import urlparse

import pytest
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from tests.e2e.conftest import (
    NAVIGATION_LINK_SELECTOR,
    UI_TIMEOUT_SECONDS,
    RunningExamples,
    _find_solution_log_url,
    clear_browser_logs,
    collect_browser_diagnostics,
    wait_for_page_rendered,
)

PROJECTS_DASHBOARD_LOG_PATTERN = re.compile(r"Projects Dashboard:\s+(http://127\.0\.0\.1:\d+/\S*)")
PORTAL_NOT_LAUNCHED_LOG_LINE = "SAF Portal: not launched"
PROJECTS_DASHBOARD_SELECTOR = "#projects-dashboard"
BACK_TO_PROJECTS_SELECTOR = "#back-to-projects-icon"


def _get_project_card_heading(project_id: str) -> tuple[str, str]:
    """Return the locator of the project name in the dashboard card that shows the project ID."""
    return By.XPATH, f"//article[.//*[normalize-space()='Id: {project_id}']]//h6"


def _click_when_ready(driver: WebDriver, locator: tuple[str, str]) -> None:
    """Click an element once it can receive the click, retrying while Dash updates the page."""

    def click(browser: WebDriver) -> bool:
        elements = browser.find_elements(*locator)
        if not elements or not elements[0].is_displayed():
            return False
        try:
            elements[0].click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            return False
        return True

    WebDriverWait(driver, UI_TIMEOUT_SECONDS, ignored_exceptions=(StaleElementReferenceException,)).until(click)


def _wait_for_dashboard(driver: WebDriver, dashboard_path: str, project_id: str) -> None:
    """Wait until the dashboard is displayed and lists the project."""
    WebDriverWait(driver, UI_TIMEOUT_SECONDS).until(
        lambda browser: urlparse(browser.current_url).path == dashboard_path
    )
    wait_for_page_rendered(driver)
    WebDriverWait(driver, UI_TIMEOUT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, PROJECTS_DASHBOARD_SELECTOR)),
    )
    WebDriverWait(driver, UI_TIMEOUT_SECONDS).until(
        EC.visibility_of_element_located(_get_project_card_heading(project_id)),
    )


def _get_visible_navigation_link_count(driver: WebDriver) -> int:
    return sum(link.is_displayed() for link in driver.find_elements(By.CSS_SELECTOR, NAVIGATION_LINK_SELECTOR))


@pytest.mark.xfail(
    reason="The browser-based checks of the solution UI are currently unstable in CI.",
    strict=False,
)
def test_portal_mode_opens_projects_dashboard_and_returns_from_a_project(
    running_examples: RunningExamples,
    examples_webdriver: WebDriver,
) -> None:
    """Verify the dashboard opens a project and the back-to-projects button returns to it.

    The test checks that the orchestrator serves the dashboard from the solution UI instead
    of starting the SAF Portal, opens the temporary project from its dashboard card, and
    comes back with the button of the solution header.
    """
    dashboard_url = _find_solution_log_url(
        running_examples.process,
        PROJECTS_DASHBOARD_LOG_PATTERN,
        "the projects dashboard URL",
    )
    assert dashboard_url.startswith(running_examples.solution_ui_url.rstrip("/"))
    assert PORTAL_NOT_LAUNCHED_LOG_LINE in "\n".join(running_examples.process.log_lines())
    dashboard_path = urlparse(dashboard_url).path
    project_id = running_examples.project_id

    clear_browser_logs(examples_webdriver)
    examples_webdriver.get(dashboard_url)
    _wait_for_dashboard(examples_webdriver, dashboard_path, project_id)
    assert _get_visible_navigation_link_count(examples_webdriver) == 0, "The dashboard must hide the step navigation."

    _click_when_ready(examples_webdriver, _get_project_card_heading(project_id))
    WebDriverWait(examples_webdriver, UI_TIMEOUT_SECONDS).until(
        lambda browser: urlparse(browser.current_url).path.startswith(f"{dashboard_path}/{project_id}"),
    )
    wait_for_page_rendered(examples_webdriver)
    WebDriverWait(examples_webdriver, UI_TIMEOUT_SECONDS).until(
        lambda browser: _get_visible_navigation_link_count(browser) > 0,
    )

    _click_when_ready(examples_webdriver, (By.CSS_SELECTOR, BACK_TO_PROJECTS_SELECTOR))
    _wait_for_dashboard(examples_webdriver, dashboard_path, project_id)

    diagnostics = collect_browser_diagnostics(examples_webdriver)
    failures = [
        *(f"console: {message}" for message in diagnostics.console_errors),
        *(f"network: {message}" for message in diagnostics.network_failures),
    ]
    assert not failures, "Browser failures in the projects dashboard workflow:\n" + "\n".join(failures)
