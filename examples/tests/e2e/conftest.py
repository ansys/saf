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

from __future__ import annotations

from collections.abc import Callable, Iterator, MutableMapping
from copy import deepcopy
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sysconfig
from threading import Thread
import time
from typing import IO, Any, TypeVar
from urllib.parse import urljoin
import uuid

import httpx2
import psutil
import pytest
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------

EXAMPLES_ROOT = Path(__file__).resolve().parents[2]
SOLUTION_DISPLAY_NAME = "Solution Examples"
COMMAND_TIMEOUT_SECONDS = 1_800
SERVICE_TIMEOUT_SECONDS = 300
INSTALL_DEPENDENCY_GROUPS = ("desktop", "ui", "build")
SPLASH_IMAGE_TIMEOUT_SECONDS = 60.0
PROJECT_REQUEST_TIMEOUT_SECONDS = 30.0
CHROME_START_ATTEMPTS = 2
CHROME_RETRY_DELAY_SECONDS = 2.0
UI_TIMEOUT_SECONDS = 60
# Navigation discovery uses many optional elements, so explicit waits are used
# instead of an implicit wait that would slow every missing-element lookup.
BROWSER_IMPLICIT_WAIT_SECONDS = 0
NAVIGATION_LINK_SELECTOR = "#navbar-content a"
NAVIGATION_EXPANDER_SELECTOR = ".tree-expander-control"
NAVIGATION_GROUP_INDICATOR_SELECTOR = "[data-position='right'], .mantine-NavLink-chevron"
PAGE_CONTENT_SELECTOR = "#page-content"
SPLASH_IMAGE_LOG_PATTERN = re.compile(r"Using splash image at (?P<path>.+)$")
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
NO_PROXY_VARIABLES = ("NO_PROXY", "no_proxy")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredPage:
    """Identify a page discovered from the solution's navigation tree."""

    navigation_label: str
    navigation_item_index: str | None
    navigation_href: str | None
    navigation_position: int


# ---------------------------------------------------------------------------
# Data passed between fixtures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExamplesTestEnvironment:
    """Hold temporary folders that stand in for a user's computer.

    Using these paths keeps the tests away from the developer's real files,
    desktop, and SAF configuration.
    """

    root: Path
    home: Path
    data_home: Path
    public: Path
    desktop: Path


@dataclass(frozen=True)
class InstalledExamples:
    """Hold the workspace and result of running ``saf install``.

    The installed workspace is passed to the build fixture. The dependency
    groups record the exact groups requested by the install command so the
    dependency verification test checks the same environment.
    """

    workspace: Path
    command: subprocess.CompletedProcess[str]
    dependency_groups: tuple[str, ...]


@dataclass(frozen=True)
class BuiltExamples:
    """Hold the workspace, command result, and installer from ``saf build``.

    The installer is passed to the deployment fixture.
    """

    workspace: Path
    installer: Path
    command: subprocess.CompletedProcess[str]


@dataclass(frozen=True)
class InstalledDesktopExamples:
    """Hold the result of running the generated desktop installer.

    The paths tell later tests where the application and desktop shortcut should be.
    """

    workspace: Path
    installer: Path
    installation_directory: Path
    shortcut: Path
    command: subprocess.CompletedProcess[str]


@dataclass(frozen=True)
class BrowserDiagnostics:
    """Hold browser problems found while a page is loading.

    Console errors and failed network requests are kept separate for clearer failures.
    """

    console_errors: tuple[str, ...]
    network_failures: tuple[str, ...]


@dataclass(frozen=True)
class LaunchedExamples:
    """Hold the process started by the desktop shortcut.

    The process and selected splash image path are used by the startup check
    and later fixtures.
    """

    process: LaunchedSolutionProcess
    shortcut: Path
    splash_image_path: Path | None


@dataclass(frozen=True)
class RunningExamples:
    """Hold a launched solution whose API and UI are ready to use.

    The URLs and project ID let browser tests open the correct project page.
    """

    process: LaunchedSolutionProcess
    project_id: str
    project_ui_url: str
    solution_api_url: str
    solution_ui_url: str


# ---------------------------------------------------------------------------
# Lifecycle and polling helpers
# ---------------------------------------------------------------------------


ValueT = TypeVar("ValueT")


def _run_successfully(
    command: list[str],
    cwd: Path,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and fail with its output if it does not succeed.

    The examples lifecycle uses this for installation, building, and deployment.
    Capturing standard output and standard error together makes failures easier
    to diagnose.
    """
    command_text = " ".join(command)
    started_at = time.monotonic()
    logger.info("Running command in %s: %s", cwd, command_text)
    process_environment = environment.copy() if environment is not None else os.environ.copy()
    _include_loopback_hosts_in_no_proxy(process_environment)
    try:
        completed_command = subprocess.run(
            command,
            cwd=cwd,
            env=process_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as timeout_error:
        logger.error("Command timed out after %s seconds: %s", timeout, command_text)
        pytest.fail(f"Command timed out after {timeout} seconds: {command_text}\n{timeout_error.stdout or ''}")

    elapsed_seconds = time.monotonic() - started_at
    if completed_command.returncode != 0:
        logger.error(
            "Command failed with exit code %s: %s\n%s",
            completed_command.returncode,
            command_text,
            completed_command.stdout.rstrip(),
        )
        pytest.fail(
            f"Command failed with exit code {completed_command.returncode}: {command_text}\n{completed_command.stdout}",
        )
    logger.info(
        "Command completed successfully in %.2f seconds: %s",
        elapsed_seconds,
        command_text,
    )
    if completed_command.stdout:
        logger.debug(
            "Captured output from %s:\n%s",
            command_text,
            completed_command.stdout.rstrip(),
        )
    return completed_command


def _include_loopback_hosts_in_no_proxy(environment: MutableMapping[str, str]) -> None:
    """Ensure local services bypass any HTTP proxy configured by the runner."""
    no_proxy_entries: list[str] = []
    for variable in NO_PROXY_VARIABLES:
        for raw_entry in environment.get(variable, "").split(","):
            entry = raw_entry.strip()
            if entry and entry not in no_proxy_entries:
                no_proxy_entries.append(entry)

    for host in LOOPBACK_HOSTS:
        if host not in no_proxy_entries:
            no_proxy_entries.append(host)

    no_proxy_value = ",".join(no_proxy_entries)
    for variable in NO_PROXY_VARIABLES:
        environment[variable] = no_proxy_value


def _wait_for_value(
    get_value: Callable[[], ValueT | None],
    description: str,
    timeout: float,
    interval: float = 0.25,
) -> ValueT:
    """Keep calling ``get_value`` until it returns something or times out.

    This small polling helper is used for services, processes, project creation,
    and browser elements that need time to start or appear.
    """
    started_at = time.monotonic()
    logger.debug("Waiting for %s (timeout: %.1f seconds)", description, timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current_value = get_value()
        if current_value is not None:
            logger.debug(
                "Finished waiting for %s in %.2f seconds",
                description,
                time.monotonic() - started_at,
            )
            return current_value
        time.sleep(interval)
    raise AssertionError(f"Timed out after {timeout} seconds while waiting for {description}.")


def _get_shortcut_path(environment: ExamplesTestEnvironment) -> Path:
    """Return the shortcut path that the installer should create."""
    shortcut_suffix = ".lnk" if platform.system() == "Windows" else ".desktop"
    return environment.desktop / f"{SOLUTION_DISPLAY_NAME}{shortcut_suffix}"


def _get_installer_path(workspace: Path) -> Path:
    """Return the installer path that ``saf build`` should create."""
    installer_suffix = ".exe" if platform.system() == "Windows" else ""
    return workspace / "dist" / f"solution-examples-installer{installer_suffix}"


def _get_pywin32_pythonpath_entries(site_packages: str) -> list[str]:
    """Return the path-only entries from pywin32's ``.pth`` file."""
    pywin32_pth = Path(site_packages) / "pywin32.pth"
    if not pywin32_pth.is_file():
        return []

    entries: list[str] = []
    for line in pywin32_pth.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or entry.startswith("import "):
            continue

        entry_path = Path(site_packages) / entry
        if entry_path.is_dir():
            entries.append(str(entry_path))
    return entries


def _append_test_environment_site_packages_to_pythonpath(
    environment: dict[str, str],
) -> str:
    """Expose packages installed beside pytest to the launched application.

    The desktop installer creates a separate virtual environment. The launched
    shortcut receives this environment, so adding the test runner's
    ``site-packages`` directory makes optional CI-installed packages such as
    PIM Light Server importable without changing the install or build commands.
    """
    site_packages = sysconfig.get_path("purelib")
    if not site_packages:
        raise RuntimeError("The test Python environment does not expose a site-packages directory.")

    existing_entries = [entry for entry in environment.get("PYTHONPATH", "").split(os.pathsep) if entry]
    entries_to_add = [site_packages, *_get_pywin32_pythonpath_entries(site_packages)]
    for entry in entries_to_add:
        if entry not in existing_entries:
            existing_entries.append(entry)
    if existing_entries:
        environment["PYTHONPATH"] = os.pathsep.join(existing_entries)
    return site_packages


def _require_linux_shortcut_tools() -> None:
    """Ensure Linux has the tools needed to launch a desktop shortcut."""
    if platform.system() != "Linux":
        return

    required_tools = ("gtk-launch", "xvfb-run")
    missing_tools = [tool for tool in required_tools if shutil.which(tool) is None]
    if missing_tools:
        missing_tool_list = ", ".join(missing_tools)
        raise RuntimeError(
            f"Linux shortcut execution requires {missing_tool_list}. "
            "Install them with:\n"
            "sudo apt update\n"
            "sudo apt install libgtk-3-bin xvfb",
        )


def _wait_for_http_ok(
    url: str,
    description: str,
    timeout: float = SERVICE_TIMEOUT_SECONDS,
) -> None:
    """Wait until ``url`` responds with HTTP status 200.

    Services can take a while to start, so a temporary connection error or a
    non-200 response is retried until the service timeout is reached.
    """
    last_status: str = "no response"

    def _check_service() -> bool | None:
        """Return ``True`` when the service is healthy right now."""
        nonlocal last_status
        try:
            response = httpx2.get(url, timeout=5, trust_env=False)
        except httpx2.RequestError as request_error:
            last_status = f"{type(request_error).__name__}: {request_error}"
            return None
        last_status = str(response.status_code)
        return True if response.status_code == 200 else None

    try:
        _wait_for_value(_check_service, description, timeout)
    except AssertionError as wait_error:
        raise AssertionError(f"{wait_error} Last HTTP status for {url}: {last_status}.") from wait_error


def _create_project(solution_api_url: str) -> str:
    """Create a temporary project and return its ID for browser testing."""
    api_base_url = solution_api_url.removesuffix("/docs")
    display_name = f"Examples E2E {uuid.uuid4().hex[:8]}"
    last_status = "no response"

    def _try_create_project() -> str | None:
        """Try once to create the temporary project."""
        nonlocal last_status
        try:
            response = httpx2.post(
                f"{api_base_url}/projects",
                json={"display_name": display_name},
                timeout=PROJECT_REQUEST_TIMEOUT_SECONDS,
                trust_env=False,
            )
        except httpx2.RequestError as request_error:
            last_status = f"{type(request_error).__name__}: {request_error}"
            return None

        last_status = str(response.status_code)
        if response.status_code not in (200, 201):
            return None

        response_body: Any = response.json()
        project_resource_name = response_body.get("name") if isinstance(response_body, dict) else None
        if not isinstance(project_resource_name, str) or not project_resource_name.startswith("projects/"):
            raise AssertionError(f"Unexpected project response: {response_body!r}")
        return project_resource_name.removeprefix("projects/")

    try:
        project_id = _wait_for_value(
            _try_create_project,
            "a project to be created",
            SERVICE_TIMEOUT_SECONDS,
        )
    except AssertionError as wait_error:
        raise AssertionError(
            f"{wait_error} Last HTTP status for project creation: {last_status}.",
        ) from wait_error
    logger.info("Created temporary project %s", project_id)
    return project_id


def _find_solution_log_url(
    process: LaunchedSolutionProcess,
    pattern: re.Pattern[str],
    description: str,
) -> str:
    """Find a service URL in the launched solution's output or log files."""

    def _find_url() -> str | None:
        """Look through the latest log lines for the requested URL."""
        for log_line in reversed(process.log_lines()):
            match = pattern.search(log_line)
            if match:
                return match.group(1)
        return None

    try:
        return _wait_for_value(_find_url, description, SERVICE_TIMEOUT_SECONDS)
    except AssertionError as wait_error:
        launcher = process.process
        if launcher is None:
            launcher_status = "not started"
        else:
            return_code = launcher.poll()
            launcher_status = "running" if return_code is None else f"exited with code {return_code}"
        recent_logs = process.log_lines()[-40:]
        log_text = "\n".join(recent_logs) if recent_logs else "<no solution output or log lines>"
        raise AssertionError(
            f"{wait_error}\n" f"Launcher status: {launcher_status}\n" f"Recent solution logs:\n{log_text}",
        ) from wait_error


def _find_splash_image(process: LaunchedSolutionProcess) -> Path:
    """Wait for the orchestrator to report the image used by the splash."""

    def _find_splash_image_path() -> Path | None:
        for log_line in reversed(process.log_lines()):
            match = SPLASH_IMAGE_LOG_PATTERN.search(log_line)
            if match:
                return Path(match.group("path").strip().strip("\"'"))
        return None

    return _wait_for_value(
        _find_splash_image_path,
        "the splash image selection",
        SPLASH_IMAGE_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------


def clear_browser_logs(driver: WebDriver) -> None:
    """Discard old console and network logs before navigating to a new page.

    This ensures each page test reports only errors caused by its own navigation.
    """
    driver.get_log("browser")
    driver.get_log("performance")
    logger.debug("Cleared pending browser and performance logs")


def collect_browser_diagnostics(driver: WebDriver) -> BrowserDiagnostics:
    """Collect console errors and failed network events from Chrome.

    HTTP errors and failed requests are returned separately from JavaScript errors.
    """
    console_errors = tuple(
        f"{entry.get('level', 'UNKNOWN')}: {entry.get('message', '')}"
        for entry in driver.get_log("browser")
        if entry.get("level") in {"ERROR", "SEVERE"}
    )

    network_failures: list[str] = []
    for entry in driver.get_log("performance"):
        performance_event: dict[str, Any] = json.loads(entry["message"])["message"]
        method = performance_event.get("method")
        event_parameters = performance_event.get("params", {})
        if method == "Network.responseReceived":
            network_response = event_parameters.get("response", {})
            status = network_response.get("status")
            if isinstance(status, (int, float)) and status >= 400:
                network_failures.append(
                    f"{int(status)} {network_response.get('url', '<unknown URL>')}",
                )
        elif method == "Network.loadingFailed":
            if event_parameters.get("errorText") == "net::ERR_ABORTED":
                continue
            network_failures.append(
                f"{event_parameters.get('errorText', 'Network loading failed')} "
                f"{event_parameters.get('url', '<unknown URL>')}",
            )

    diagnostics = BrowserDiagnostics(tuple(console_errors), tuple(network_failures))
    logger.debug(
        "Collected browser diagnostics: %d console errors, %d network failures",
        len(diagnostics.console_errors),
        len(diagnostics.network_failures),
    )
    return diagnostics


def wait_for_page_rendered(driver: WebDriver, timeout: float = UI_TIMEOUT_SECONDS) -> None:
    """Wait until Dash has placed visible content in the page area.

    This prevents the test from checking the page while it is still loading.

    The first Selenium wait checks that the page container exists. The additional
    JavaScript check is still needed because Dash may create the container before
    it has placed any content inside it.
    """
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, PAGE_CONTENT_SELECTOR)),
    )
    WebDriverWait(driver, timeout).until(
        lambda browser: bool(
            browser.execute_script(
                "return document.readyState !== 'loading' && "
                f"document.querySelector('{PAGE_CONTENT_SELECTOR}') !== null && "
                f"document.querySelector('{PAGE_CONTENT_SELECTOR}').children.length > 0;",
            ),
        ),
    )


def _get_visible_navigation_links(driver: WebDriver) -> list[WebElement]:
    """Return the navigation links that are currently visible."""
    return [link for link in driver.find_elements(By.CSS_SELECTOR, NAVIGATION_LINK_SELECTOR) if link.is_displayed()]


def _get_navigation_item_index(link: WebElement) -> str | None:
    """Read a navigation item's index from its DOM attributes."""
    item_index = link.get_attribute("data-item-index")
    if item_index:
        return item_index

    item_id = link.get_attribute("id")
    if not item_id:
        return None
    try:
        item_definition = json.loads(item_id)
    except json.JSONDecodeError:
        return None
    if not isinstance(item_definition, dict):
        return None

    item_index = item_definition.get("index")
    if item_index is None:
        return None
    return str(item_index)


def _get_navigation_item_identity(link: WebElement) -> tuple[str, str] | None:
    """Return a stable identity for a navigation item."""
    item_index = _get_navigation_item_index(link)
    if item_index:
        return "item-index", item_index

    href = link.get_attribute("href")
    if href:
        return "href", href

    label = link.text.strip()
    if label:
        return "label", label
    return None


def _is_navigation_group(link: WebElement) -> bool:
    """Return whether a navigation link represents an expandable group."""
    return any(
        (
            link.get_attribute("aria-expanded") is not None,
            bool(link.find_elements(By.CSS_SELECTOR, NAVIGATION_EXPANDER_SELECTOR)),
            bool(link.find_elements(By.CSS_SELECTOR, NAVIGATION_GROUP_INDICATOR_SELECTOR)),
            bool(link.find_elements(By.XPATH, "./following-sibling::*[1][@aria-hidden]")),
        ),
    )


def _is_navigation_group_expanded(link: WebElement) -> bool:
    """Return whether an expandable navigation group is open."""
    collapsible_content = link.find_elements(By.XPATH, "./following-sibling::*[1][@aria-hidden]")
    if collapsible_content:
        return (collapsible_content[0].get_attribute("aria-hidden") or "").lower() == "false"

    expanded = link.get_attribute("data-expanded") or link.get_attribute("aria-expanded")
    if expanded is not None:
        return expanded.lower() == "true"

    expander = link.find_elements(By.CSS_SELECTOR, NAVIGATION_EXPANDER_SELECTOR)
    if expander:
        classes = (expander[0].get_attribute("class") or "").split()
        return "tree-expander-open" in classes

    return True


def _is_navigation_link_active(link: WebElement) -> bool:
    """Return whether a navigation link represents the currently displayed page."""
    for attribute in ("data-active", "aria-current", "aria-selected"):
        value = link.get_attribute(attribute)
        if value and value.lower() not in {"false", "none"}:
            return True
    class_names = (link.get_attribute("class") or "").lower().split()
    return any(name in {"active", "current", "selected"} for name in class_names)


def _get_navigation_link(
    driver: WebDriver,
    page: DiscoveredPage,
) -> WebElement | None:
    """Find a visible navigation link for a dynamically discovered page."""
    leaf_links = [link for link in _get_visible_navigation_links(driver) if not _is_navigation_group(link)]
    for link in leaf_links:
        if page.navigation_item_index is not None:
            if _get_navigation_item_index(link) == page.navigation_item_index:
                return link
            continue
        if page.navigation_href is not None:
            if link.get_attribute("href") == page.navigation_href:
                return link
            continue
    if page.navigation_position < len(leaf_links):
        return leaf_links[page.navigation_position]
    return None


def _click_navigation_link(driver: WebDriver, page: DiscoveredPage) -> None:
    """Wait for a discovered link to become clickable and click it once."""

    def click_when_ready(browser: WebDriver) -> bool:
        """Retry while the navigation tree is still updating."""
        link = _get_navigation_link(browser, page)
        if link is None or not link.is_displayed() or not link.is_enabled():
            return False
        try:
            link.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            return False
        return True

    WebDriverWait(
        driver,
        UI_TIMEOUT_SECONDS,
        ignored_exceptions=(StaleElementReferenceException,),
    ).until(click_when_ready)


def _get_navigation_group(
    driver: WebDriver,
    identity: tuple[str, str],
) -> WebElement | None:
    """Find a visible navigation group by its stable identity."""
    for link in _get_visible_navigation_links(driver):
        if _is_navigation_group(link) and _get_navigation_item_identity(link) == identity:
            return link
    return None


def _expand_all_navigation_groups(driver: WebDriver) -> None:
    """Open every collapsed navigation group without knowing its name."""
    expanded_group_identities: set[tuple[str, str]] = set()
    while True:
        collapsed_group_identity: tuple[str, str] | None = None
        try:
            for link in _get_visible_navigation_links(driver):
                if not _is_navigation_group(link):
                    continue
                identity = _get_navigation_item_identity(link)
                if (
                    identity is not None
                    and identity not in expanded_group_identities
                    and not _is_navigation_group_expanded(link)
                ):
                    collapsed_group_identity = identity
                    break
        except StaleElementReferenceException:
            continue

        if collapsed_group_identity is None:
            return

        group_link = WebDriverWait(
            driver,
            UI_TIMEOUT_SECONDS,
            ignored_exceptions=(StaleElementReferenceException,),
        ).until(lambda browser: _get_navigation_group(browser, collapsed_group_identity))
        expander_controls = group_link.find_elements(
            By.CSS_SELECTOR,
            NAVIGATION_EXPANDER_SELECTOR,
        )
        expander = expander_controls[0] if expander_controls else group_link
        has_expansion_state = (
            group_link.get_attribute("data-expanded") is not None
            or group_link.get_attribute("aria-expanded") is not None
            or bool(
                group_link.find_elements(
                    By.XPATH,
                    "./following-sibling::*[1][@aria-hidden]",
                ),
            )
            or "tree-expander-open" in (expander.get_attribute("class") or "").split()
        )
        expander.click()
        expanded_group_identities.add(collapsed_group_identity)

        if has_expansion_state:
            WebDriverWait(
                driver,
                UI_TIMEOUT_SECONDS,
                ignored_exceptions=(StaleElementReferenceException,),
            ).until(
                lambda browser: (
                    (group := _get_navigation_group(browser, collapsed_group_identity)) is not None
                    and _is_navigation_group_expanded(group)
                ),
            )


def discover_navigation_pages(
    driver: WebDriver,
    project_ui_url: str,
) -> tuple[DiscoveredPage, ...]:
    """Discover every leaf page exposed by the solution's navigation tree."""
    driver.get(project_ui_url)
    wait_for_page_rendered(driver)
    _expand_all_navigation_groups(driver)

    pages: list[DiscoveredPage] = []
    seen_identities: set[tuple[str, str]] = set()
    leaf_position = 0
    for link in _get_visible_navigation_links(driver):
        if _is_navigation_group(link):
            continue
        current_position = leaf_position
        leaf_position += 1

        label = link.text.strip()
        item_index = _get_navigation_item_index(link)
        href = link.get_attribute("href")
        identity = _get_navigation_item_identity(link)
        if not label or identity is None:
            continue
        if item_index is None and href is None:
            identity = "position", str(current_position)
        if identity in seen_identities:
            continue

        seen_identities.add(identity)
        pages.append(
            DiscoveredPage(
                navigation_label=label,
                navigation_item_index=item_index,
                navigation_href=href,
                navigation_position=current_position,
            ),
        )

    if not pages:
        raise RuntimeError(
            f"No leaf pages were discovered in {NAVIGATION_LINK_SELECTOR!r} " f"after loading {project_ui_url}.",
        )

    logger.info(
        "Discovered %d navigation pages: %s",
        len(pages),
        ", ".join(page.navigation_label for page in pages),
    )
    return tuple(pages)


def _wait_for_page_navigation(
    driver: WebDriver,
    page: DiscoveredPage,
    initial_url: str,
    initial_content: str,
) -> None:
    """Wait for clicking a page link to complete its route change."""
    target_href = page.navigation_href
    if target_href and not target_href.startswith(("#", "javascript:")):
        target_url = urljoin(initial_url, target_href)
        if target_url.rstrip("/") != initial_url.rstrip("/"):
            WebDriverWait(driver, UI_TIMEOUT_SECONDS).until(
                lambda browser: browser.current_url.rstrip("/") == target_url.rstrip("/"),
            )
            return

    def page_content_changed(browser: WebDriver) -> bool:
        """Return whether the page content changed after the navigation click."""
        try:
            content_elements = browser.find_elements(
                By.CSS_SELECTOR,
                PAGE_CONTENT_SELECTOR,
            )
            if not content_elements:
                return False
            current_content = content_elements[0].get_attribute("innerHTML")
        except StaleElementReferenceException:
            return False
        return (current_content or "") != initial_content

    def navigation_link_is_active(browser: WebDriver) -> bool:
        """Return whether the discovered link became the active navigation item."""
        link = _get_navigation_link(browser, page)
        return link is not None and _is_navigation_link_active(link)

    WebDriverWait(
        driver,
        UI_TIMEOUT_SECONDS,
        ignored_exceptions=(StaleElementReferenceException,),
    ).until(
        lambda browser: (
            browser.current_url != initial_url or page_content_changed(browser) or navigation_link_is_active(browser)
        ),
    )


def navigate_to_discovered_page(
    driver: WebDriver,
    running_examples: RunningExamples,
    page: DiscoveredPage,
) -> str:
    """Open one dynamically discovered page through the solution navigation."""
    logger.info("Navigating to discovered page %s", page.navigation_label)
    if not driver.current_url.startswith(running_examples.solution_ui_url.rstrip("/")):
        driver.get(running_examples.project_ui_url)
        wait_for_page_rendered(driver)
    _expand_all_navigation_groups(driver)
    clear_browser_logs(driver)

    initial_url = driver.current_url
    initial_content = (
        driver.find_element(
            By.CSS_SELECTOR,
            PAGE_CONTENT_SELECTOR,
        ).get_attribute("innerHTML")
        or ""
    )
    _click_navigation_link(driver, page)
    _wait_for_page_navigation(driver, page, initial_url, initial_content)
    wait_for_page_rendered(driver)

    logger.info("Loaded discovered page %s at %s", page.navigation_label, driver.current_url)
    return driver.current_url


# ---------------------------------------------------------------------------
# Installed solution process
# ---------------------------------------------------------------------------


class LaunchedSolutionProcess:
    """Launch the installed solution through its platform desktop shortcut.

    The class also gathers the log files used to find the solution's API and UI URLs.
    """

    def __init__(self, shortcut_path: Path, environment: ExamplesTestEnvironment):
        """Prepare the platform-specific command used to open the shortcut."""
        operating_system = platform.system()
        logger.info("Preparing desktop launch from shortcut %s", shortcut_path)
        if operating_system == "Windows":
            command = ["cmd", "/c", str(shortcut_path)]
        elif operating_system == "Linux":
            applications_directory = environment.data_home / "applications"
            applications_directory.mkdir(parents=True, exist_ok=True)
            shutil.copy2(shortcut_path, applications_directory / shortcut_path.name)
            _require_linux_shortcut_tools()
            command = [
                "xvfb-run",
                "-a",
                "env",
                f"XDG_DATA_HOME={environment.data_home}",
                "gtk-launch",
                shortcut_path.stem,
            ]
        else:
            raise ValueError(f"Unsupported operating system: {operating_system}")

        appdata = environment.root / "appdata"
        log_directory = appdata if operating_system == "Windows" else environment.data_home
        self._log_root = log_directory / "ansys" / "glow"
        if self._log_root.is_dir():
            shutil.rmtree(self._log_root)
        logger.debug("Desktop launcher command: %s", " ".join(command))
        logger.debug("Reading solution logs from %s", self._log_root)
        self._command = command
        self._process: subprocess.Popen[str] | None = None
        self._process_output: list[str] = []

    @classmethod
    def run(cls, shortcut_path: Path, environment: ExamplesTestEnvironment) -> LaunchedSolutionProcess:
        """Create and start a process for the installed solution."""
        process = cls(shortcut_path, environment)
        process.start()
        return process

    @property
    def process(self) -> subprocess.Popen[str] | None:
        """Return the underlying desktop-launcher process."""
        return self._process

    def start(self) -> None:
        """Start the desktop launcher and capture its output."""
        process_environment = os.environ.copy()
        _include_loopback_hosts_in_no_proxy(process_environment)
        test_site_packages = _append_test_environment_site_packages_to_pythonpath(process_environment)
        logger.info(
            "Added test environment site-packages to the desktop process PYTHONPATH: %s",
            test_site_packages,
        )
        self._process = subprocess.Popen(
            self._command,
            env=process_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
        )
        if self._process.stdout is None:
            self.stop()
            raise RuntimeError("The installed solution process did not provide a stdout pipe.")

        output_reader = Thread(
            target=self._read_process_output,
            args=(self._process.stdout,),
            daemon=True,
        )
        output_reader.start()

    def _read_process_output(self, output: IO[str]) -> None:
        """Store non-empty lines emitted by the desktop launcher."""
        for line in iter(output.readline, ""):
            clean_line = line.rstrip()
            if clean_line:
                self._process_output.append(clean_line)

    def stop(self) -> None:
        """Stop the desktop launcher and all of its child processes."""
        if self._process is None:
            return

        try:
            parent_process = psutil.Process(self._process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            parent_process = None

        if parent_process is not None:
            try:
                child_processes = parent_process.children(recursive=True)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                child_processes = []
            for child_process in child_processes:
                self._terminate(child_process)
            self._terminate(parent_process, timeout=20)
        self._process = None

    @staticmethod
    def _terminate(process: psutil.Process, timeout: int = 0) -> None:
        """Terminate one process and optionally wait for it to exit."""
        try:
            process.terminate()
            if timeout > 0:
                process.wait(timeout)
        except psutil.NoSuchProcess:
            pass

    def log_lines(self) -> list[str]:
        """Return process output together with all available solution log lines.

        Reading both sources works even when the desktop launcher does not expose standard output.
        """
        lines = list(self._process_output)
        if self._log_root.is_dir():
            for log_file in sorted(self._log_root.rglob("*.log")):
                if log_file.is_file():
                    lines.extend(log_file.read_text(encoding="utf-8", errors="replace").splitlines())
        return lines


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def check_gtk_launch_and_xvfb_are_installed() -> None:
    """Fail early when Linux shortcut-launching tools are unavailable."""
    _require_linux_shortcut_tools()


@pytest.fixture(scope="session")
def examples_test_environment(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[ExamplesTestEnvironment]:
    """Create isolated home, application-data, and desktop directories.

    The environment variables are changed for this test session and restored
    when the session ends. This prevents the real user environment from being
    modified by the installer or launched application.
    """
    root = tmp_path_factory.mktemp("examples-e2e-environment")
    home = root / "home"
    data_home = home / ".local" / "share"
    public = root / "public"
    desktop = public / "Desktop" if platform.system() == "Windows" else home / "Desktop"

    # Create both possible desktop locations. The installer chooses one based
    # on the operating system, and creating both keeps setup predictable.
    for directory in (home, data_home, public, public / "Desktop", home / "Desktop"):
        directory.mkdir(parents=True, exist_ok=True)

    environment_values: dict[str, str] = {
        "APPDATA": str(root / "appdata"),
        "LOCALAPPDATA": str(root / "localappdata"),
        "HOME": str(home),
        "PUBLIC": str(public),
        "USERPROFILE": str(home),
        "XDG_DATA_HOME": str(data_home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
    }
    proxy_environment = {variable: os.environ.get(variable, "") for variable in NO_PROXY_VARIABLES}
    _include_loopback_hosts_in_no_proxy(proxy_environment)
    environment_values.update(proxy_environment)
    previous_values: dict[str, str | None] = {name: os.environ.get(name) for name in environment_values}

    def _restore_environment() -> None:
        """Put the user's original environment values back after testing."""
        for name, value in previous_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    try:
        for name, value in environment_values.items():
            os.environ[name] = value
        logger.info("Created isolated E2E environment at %s", root)
        yield ExamplesTestEnvironment(
            root=root,
            home=home,
            data_home=data_home,
            public=public,
            desktop=desktop,
        )
    finally:
        _restore_environment()
        logger.info("Restored the original E2E environment variables")


@pytest.fixture(scope="session")
def saf_executable() -> str:
    """Find the SAF command used by the lifecycle tests.

    An explicit ``SAF_EXECUTABLE`` value is preferred over the system PATH.
    """
    executable = os.getenv("SAF_EXECUTABLE") or shutil.which("saf")
    if executable is None:
        raise RuntimeError(
            "The SAF CLI executable was not found. Install saf or set SAF_EXECUTABLE.",
        )
    logger.info("Using SAF CLI executable: %s", executable)
    return executable


@pytest.fixture(scope="session")
def examples_workspace(
    tmp_path_factory: pytest.TempPathFactory,
    examples_test_environment: ExamplesTestEnvironment,
) -> Path:
    """Copy the examples solution into a clean temporary workspace.

    This lets installation and building modify the copy without changing the
    source checkout. The environment fixture is listed as a dependency so its
    isolated environment variables are configured before later fixtures run.
    """
    workspace = tmp_path_factory.mktemp("examples-e2e-workspace") / "examples"
    shutil.copytree(
        EXAMPLES_ROOT,
        workspace,
        ignore=shutil.ignore_patterns(
            # Do not copy generated files, caches, or the tests into the
            # workspace that the real SAF commands will modify.
            ".venv",
            ".poetry",
            ".pytest_cache",
            "__pycache__",
            ".coverage",
            "htmlcov",
            "pytest_logs",
            "dist",
            "build",
            "tests",
        ),
    )
    logger.info("Copied examples into temporary workspace %s", workspace)
    return workspace


@pytest.fixture(scope="session")
def installed_examples(
    examples_workspace: Path,
    examples_test_environment: ExamplesTestEnvironment,
    saf_executable: str,
) -> InstalledExamples:
    """Run the real ``saf install`` command with the E2E dependency groups.

    The environment fixture is listed only to guarantee that the command uses
    the isolated directories created for this test session.
    """
    dependency_groups = INSTALL_DEPENDENCY_GROUPS
    install_command = _run_successfully(
        [
            saf_executable,
            "install",
            "-f",
            "-d",
            ",".join(dependency_groups),
        ],
        examples_workspace,
    )
    logger.info("Examples installation completed in %s", examples_workspace)
    return InstalledExamples(
        workspace=examples_workspace,
        command=install_command,
        dependency_groups=dependency_groups,
    )


@pytest.fixture(scope="session")
def built_examples(installed_examples: InstalledExamples, saf_executable: str) -> BuiltExamples:
    """Run ``saf build`` and locate the generated desktop installer.

    The next fixture uses that installer to deploy the solution.
    """
    build_command = _run_successfully(
        [saf_executable, "build"],
        installed_examples.workspace,
    )
    installer = _get_installer_path(installed_examples.workspace)
    assert installer.is_file(), f"Expected installer was not created: {installer}\n" f"{build_command.stdout}"
    logger.info("Examples build produced installer %s", installer)
    return BuiltExamples(
        workspace=installed_examples.workspace,
        installer=installer,
        command=build_command,
    )


@pytest.fixture(scope="session")
def installed_desktop_examples(
    built_examples: BuiltExamples,
    examples_test_environment: ExamplesTestEnvironment,
) -> InstalledDesktopExamples:
    """Run the generated installer in a temporary installation directory.

    The fixture also records where the installer should create the desktop
    shortcut.
    """
    installation_directory = built_examples.workspace.parent / "desktop-installation"
    installation_directory.mkdir(parents=True, exist_ok=True)
    installer_environment = os.environ.copy()
    test_site_packages = _append_test_environment_site_packages_to_pythonpath(installer_environment)
    logger.info(
        "Added test environment site-packages to the installer process PYTHONPATH: %s",
        test_site_packages,
    )
    installer_command = _run_successfully(
        [
            str(built_examples.installer),
            "--no-ui",
            "--installation-directory",
            str(installation_directory),
        ],
        built_examples.workspace,
        environment=installer_environment,
    )
    shortcut = _get_shortcut_path(examples_test_environment)
    logger.info("Desktop installer deployed to %s", installation_directory)
    logger.info("Expecting desktop shortcut at %s", shortcut)
    return InstalledDesktopExamples(
        workspace=built_examples.workspace,
        installer=built_examples.installer,
        installation_directory=installation_directory,
        shortcut=shortcut,
        command=installer_command,
    )


@pytest.fixture(scope="session")
def launched_examples(
    installed_desktop_examples: InstalledDesktopExamples,
    examples_test_environment: ExamplesTestEnvironment,
    check_gtk_launch_and_xvfb_are_installed: None,
) -> Iterator[LaunchedExamples]:
    """Open the installed solution through its generated desktop shortcut.

    The process is always stopped when the tests finish using it. ``yield`` is
    used so the ``finally`` block runs during pytest fixture cleanup.
    """
    logger.info("Launching installed examples through the desktop shortcut")
    launched_process = LaunchedSolutionProcess.run(
        installed_desktop_examples.shortcut,
        examples_test_environment,
    )
    try:
        splash_image_path = None
        if platform.system() == "Windows":
            splash_image_path = _find_splash_image(launched_process)
        yield LaunchedExamples(
            process=launched_process,
            shortcut=installed_desktop_examples.shortcut,
            splash_image_path=splash_image_path,
        )
    finally:
        logger.info("Stopping the installed examples process")
        launched_process.stop()


@pytest.fixture(scope="session")
def running_examples(
    launched_examples: LaunchedExamples,
) -> RunningExamples:
    """Wait for the API and UI services to become ready after launch.

    A temporary project is created so browser tests can open a real project page.
    """
    # The API and UI print their local URLs when they start. Find those URLs
    # before checking health or creating the browser-test project.
    solution_api_url = _find_solution_log_url(
        launched_examples.process,
        re.compile(r"Solution API:\s+(http://127\.0\.0\.1:\d+/docs)"),
        "the solution API URL",
    )
    logger.info("Found solution API at %s", solution_api_url)
    _wait_for_http_ok(solution_api_url, "the solution API")

    solution_ui_url = _find_solution_log_url(
        launched_examples.process,
        re.compile(r"Solution UI:\s+(http://127\.0\.0\.1:\d+)"),
        "the solution UI URL",
    )
    logger.info("Found solution UI at %s", solution_ui_url)
    project_id = _create_project(solution_api_url)
    project_ui_url = f"{solution_ui_url.rstrip('/')}/projects/{project_id}"
    _wait_for_http_ok(project_ui_url, "the project UI")
    logger.info("Project UI is ready at %s", project_ui_url)

    return RunningExamples(
        process=launched_examples.process,
        project_id=project_id,
        project_ui_url=project_ui_url,
        solution_api_url=solution_api_url,
        solution_ui_url=solution_ui_url,
    )


@pytest.fixture(scope="session")
def examples_chrome_options(tmp_path_factory: pytest.TempPathFactory) -> Options:
    """Create Chrome options without relying on a third-party pytest fixture."""
    chrome_options = Options()
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_experimental_option(
        "prefs",
        {"download.default_directory": str(tmp_path_factory.getbasetemp())},
    )
    for argument in (
        "--headless",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1280,800",
        "--allow-insecure-localhost",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-debugging-pipe",
    ):
        chrome_options.add_argument(argument)
    return chrome_options


@pytest.fixture(scope="session")
def examples_webdriver(
    examples_chrome_options: Options,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[WebDriver]:
    """Create one Chrome driver that records console and network problems.

    Reusing the driver keeps browser setup in one place for all UI tests. The
    logging capabilities must be enabled before the driver is created.
    """
    logger.info("Starting Chrome WebDriver")
    examples_chrome_options.set_capability(
        "goog:loggingPrefs",
        {"browser": "ALL", "performance": "ALL"},
    )
    driver: WebDriver | None = None
    for attempt in range(1, CHROME_START_ATTEMPTS + 1):
        driver_log = tmp_path_factory.mktemp("chromedriver-logs") / f"attempt-{attempt}.log"
        attempt_options = deepcopy(examples_chrome_options)
        attempt_options.add_argument(
            f"--user-data-dir={tmp_path_factory.mktemp(f'chrome-profile-{attempt}')}",
        )
        service = Service(log_output=str(driver_log))
        try:
            driver = webdriver.Chrome(service=service, options=attempt_options)
        except WebDriverException as error:
            service.stop()
            logger.warning(
                "Chrome WebDriver startup attempt %d/%d failed. ChromeDriver log: %s",
                attempt,
                CHROME_START_ATTEMPTS,
                driver_log,
            )
            if attempt == CHROME_START_ATTEMPTS:
                raise WebDriverException(
                    "Chrome WebDriver could not be started after "
                    f"{CHROME_START_ATTEMPTS} attempts. Last ChromeDriver log: {driver_log}",
                ) from error
            time.sleep(CHROME_RETRY_DELAY_SECONDS)

    if driver is None:
        raise RuntimeError("Chrome WebDriver startup completed without creating a driver.")

    driver.implicitly_wait(BROWSER_IMPLICIT_WAIT_SECONDS)
    driver.set_page_load_timeout(UI_TIMEOUT_SECONDS)
    try:
        yield driver
    finally:
        logger.info("Stopping Chrome WebDriver")
        driver.quit()
