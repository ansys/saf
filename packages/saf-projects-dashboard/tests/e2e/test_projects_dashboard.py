# Copyright (C) 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""End-to-end tests for the Projects Dashboard component.

These tests require:
1. The SAF solution to be running (saf run dashboard --browser)
2. Chrome browser installed
3. ChromeDriver installed (or webdriver-manager package)

Run with: pytest tests/e2e/test_projects_dashboard.py -v -m e2e
Or run visible: pytest tests/e2e/test_projects_dashboard.py -v -m e2e --browser-visible
"""

import time
import urllib.error
import urllib.request

import pytest
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def is_solution_running(url: str, timeout: float = 2.0) -> bool:
    """Check if the solution is accessible at the given URL."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


# Mark all tests in this module as E2E tests
pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def require_solution_running(solution_url):
    """Skip tests if the solution is not running."""
    if not is_solution_running(solution_url):
        pytest.skip(f"Solution not running at {solution_url}. Start with: saf run dashboard")


class TestProjectsPageLoad:
    """Tests for verifying the Projects page loads correctly."""

    def test_solution_is_accessible(self, browser, solution_url):
        """Test that the SAF solution is running and accessible."""
        browser.get(solution_url)
        time.sleep(2)  # Wait for initial load

        # Check that the page loaded (no error page)
        assert "Internal Server Error" not in browser.page_source, "Solution returned 500 error"
        assert "404" not in browser.title, "Solution returned 404 error"

    def test_navigation_tree_exists(self, browser, solution_url):
        """Test that the navigation tree is present."""
        browser.get(solution_url)
        time.sleep(2)

        # Wait for navigation tree to load
        wait = WebDriverWait(browser, 10)
        try:
            nav_tree = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "nav-tree")))
            assert nav_tree is not None, "Navigation tree not found"
        except TimeoutException:
            # Try alternative selectors
            try:
                nav_links = browser.find_elements(By.CSS_SELECTOR, "[class*='nav']")
                assert len(nav_links) > 0, "No navigation elements found"
            except NoSuchElementException:
                pytest.fail("Navigation tree not found on page")

    def test_navigate_to_projects_page(self, browser, solution_url):
        """Test navigating to the Projects page."""
        browser.get(solution_url)
        time.sleep(2)

        wait = WebDriverWait(browser, 15)

        # Find and click on Projects in the navigation
        try:
            # Look for the Projects link in navigation
            projects_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Projects')]")))
            projects_link.click()
            time.sleep(2)

            # Verify we're on the Projects page
            assert "Projects" in browser.page_source, "Projects page title not found after navigation"
        except TimeoutException:
            pytest.fail("Could not find or click Projects navigation link")

    def test_projects_dashboard_component_loads(self, browser, solution_url):
        """Test that the ProjectsDashboard component loads without errors."""
        browser.get(solution_url)
        time.sleep(2)

        wait = WebDriverWait(browser, 15)

        # Navigate to Projects page
        try:
            projects_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Projects')]")))
            projects_link.click()
            time.sleep(3)  # Wait for component to fully load

            # Check for the projects-dashboard component
            dashboard = browser.find_elements(By.ID, "projects-dashboard")
            assert len(dashboard) > 0, "ProjectsDashboard component not found"

            # Verify no 500 error occurred
            assert "Internal Server Error" not in browser.page_source, "500 error when loading ProjectsDashboard"

        except TimeoutException:
            pytest.fail("Timeout waiting for Projects page to load")


class TestProjectsDashboardFunctionality:
    """Tests for ProjectsDashboard CRUD operations."""

    @pytest.fixture(autouse=True)
    def navigate_to_projects(self, browser, solution_url):
        """Navigate to the Projects page before each test."""
        browser.get(solution_url)
        time.sleep(2)

        wait = WebDriverWait(browser, 15)
        try:
            projects_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Projects')]")))
            projects_link.click()
            time.sleep(3)
        except TimeoutException:
            pytest.skip("Could not navigate to Projects page")

    def test_projects_list_displays(self, browser, solution_url):
        """Test that the projects list is displayed."""
        wait = WebDriverWait(browser, 10)

        # Look for project cards or list container
        try:
            # Check for projects container
            projects_container = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".projects-grid, .projects-list, [class*='project']")),
            )
            assert projects_container is not None, "Projects container not found"
        except TimeoutException:
            # It's okay if there are no projects yet, but the container should exist
            dashboard = browser.find_elements(By.ID, "projects-dashboard")
            assert len(dashboard) > 0, "ProjectsDashboard component not found"

    def test_create_project_button_exists(self, browser, solution_url):
        """Test that the Create Project button is visible."""
        wait = WebDriverWait(browser, 10)

        try:
            # Look for create button with various possible selectors
            create_btn = wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//*[contains(text(), 'Create') or contains(text(), 'New Project') or contains(text(), '+ Create')]",
                    ),
                ),
            )
            assert create_btn is not None, "Create project button not found"
            assert create_btn.is_displayed(), "Create project button is not visible"
        except TimeoutException:
            pytest.fail("Create project button not found on page")

    def test_create_project_form_opens(self, browser, solution_url):
        """Test that clicking Create opens the project form."""
        wait = WebDriverWait(browser, 10)

        try:
            # Find and click create button
            create_btn = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//*[contains(text(), 'Create') or contains(text(), 'New Project') or contains(@class, 'btn-primary')]",
                    ),
                ),
            )
            create_btn.click()
            time.sleep(1)

            # Check that form appeared
            form_elements = browser.find_elements(By.CSS_SELECTOR, "input, form, [class*='form'], [class*='modal']")
            assert len(form_elements) > 0, "Project form did not open"

        except TimeoutException:
            pytest.fail("Could not interact with create project button")

    def test_project_count_displays(self, browser, solution_url):
        """Test that the project count is displayed."""
        wait = WebDriverWait(browser, 10)

        try:
            # Look for project count element
            project_count = wait.until(EC.presence_of_element_located((By.ID, "project-count")))
            assert project_count is not None, "Project count element not found"

            # Verify it contains some text about projects
            count_text = project_count.text
            assert "project" in count_text.lower() or count_text.strip() != "", (
                f"Project count text unexpected: {count_text}"
            )

        except TimeoutException:
            pytest.fail("Project count element not found")

    def test_action_log_exists(self, browser, solution_url):
        """Test that the action log container exists."""
        wait = WebDriverWait(browser, 10)

        try:
            action_output = wait.until(EC.presence_of_element_located((By.ID, "action-output")))
            assert action_output is not None, "Action output container not found"
        except TimeoutException:
            pytest.fail("Action output container not found")


class TestProjectsCRUDOperations:
    """Tests for Create, Read, Update, Delete operations."""

    @pytest.fixture(autouse=True)
    def navigate_to_projects(self, browser, solution_url):
        """Navigate to the Projects page before each test."""
        browser.get(solution_url)
        time.sleep(2)

        wait = WebDriverWait(browser, 15)
        try:
            projects_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Projects')]")))
            projects_link.click()
            time.sleep(3)
        except TimeoutException:
            pytest.skip("Could not navigate to Projects page")

    def test_create_new_project(self, browser, solution_url):
        """Test creating a new project."""
        wait = WebDriverWait(browser, 10)
        test_project_name = f"Test Project {int(time.time())}"

        try:
            # Click create button
            create_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//*[contains(text(), 'Create') or contains(text(), 'New Project')]"),
                ),
            )
            create_btn.click()
            time.sleep(1)

            # Find input field and enter project name
            name_input = wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "input[type='text'], input[name='displayName'], input[name='display_name'], input[id*='name']",
                    ),
                ),
            )
            name_input.clear()
            name_input.send_keys(test_project_name)

            # Submit the form
            submit_btn = browser.find_element(
                By.CSS_SELECTOR,
                "button[type='submit'], .btn-primary, button:contains('Create'), button:contains('Save')",
            )
            submit_btn.click()
            time.sleep(2)

            # Verify project was created (check for success message or project in list)
            page_source = browser.page_source
            assert (
                test_project_name in page_source or "success" in page_source.lower() or "created" in page_source.lower()
            ), "Project creation not confirmed"

        except TimeoutException:
            pytest.fail("Timeout during project creation flow")
        except NoSuchElementException as e:
            pytest.fail(f"Required element not found during project creation: {e}")

    def test_import_upload_exists(self, browser, solution_url):
        """Test that the file upload for import exists."""
        wait = WebDriverWait(browser, 10)

        try:
            # Look for file upload element
            upload_area = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#upload-safx, [class*='upload'], input[type='file'], [class*='dcc-upload']"),
                ),
            )
            assert upload_area is not None, "Upload area not found"
        except TimeoutException:
            pytest.fail("Import upload area not found")


class TestErrorHandling:
    """Tests for error handling in the ProjectsDashboard."""

    @pytest.fixture(autouse=True)
    def navigate_to_projects(self, browser, solution_url):
        """Navigate to the Projects page before each test."""
        browser.get(solution_url)
        time.sleep(2)

        wait = WebDriverWait(browser, 15)
        try:
            projects_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Projects')]")))
            projects_link.click()
            time.sleep(3)
        except TimeoutException:
            pytest.skip("Could not navigate to Projects page")

    def test_no_console_errors(self, browser, solution_url):
        """Test that there are no JavaScript console errors."""
        # Get browser console logs
        logs = browser.get_log("browser")

        # Filter for SEVERE errors (ignore warnings)
        severe_errors = [log for log in logs if log.get("level") == "SEVERE"]

        # Filter out known acceptable errors (like network errors for missing resources)
        critical_errors = [error for error in severe_errors if "favicon" not in error.get("message", "").lower()]

        assert len(critical_errors) == 0, f"JavaScript console errors found: {critical_errors}"

    def test_page_loads_within_timeout(self, browser, solution_url):
        """Test that the page loads within an acceptable timeout."""
        start_time = time.time()

        wait = WebDriverWait(browser, 30)  # 30 second max
        try:
            # Wait for dashboard component to be present
            wait.until(EC.presence_of_element_located((By.ID, "projects-dashboard")))
            load_time = time.time() - start_time

            assert load_time < 15, f"Page took too long to load: {load_time:.2f} seconds"

        except TimeoutException:
            pytest.fail("Page did not load within 30 seconds")
