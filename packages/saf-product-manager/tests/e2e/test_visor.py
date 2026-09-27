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

from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_element_and_click,
    wait_for_partial_text,
)
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
]


@retry(stop=stop_after_attempt(100), wait=wait_fixed(0.5))
def wait_for_text_in_page_source(webdriver: WebDriver, text: str) -> None:
    if text not in webdriver.page_source:
        raise TryAgain


@pytest.mark.use_visor
@pytest.mark.parametrize("ui_enabled", [True], indirect=True)
@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
@pytest.mark.parametrize("deployment_type", ["Desktop", "DockerCompose"], indirect=True)
class TestVisorUI:
    def _open_visor_page(
        self,
        session_selenium_webdriver: WebDriver,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        session_selenium_webdriver.get(function_project.ui_url)
        _ = wait_for_element(session_selenium_webdriver, "page-content")
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'Visor Page')]",
            element_type=By.XPATH,
        )

    def test_visor_ui(
        self,
        request,
        session_selenium_webdriver: WebDriver,
        function_project: ProjectFixture[EndToEndSolution],
        restart_product_instance_system: Callable[..., None],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """Test that Visor can be used with PIM Light Server, both in Desktop and Docker Compose deployments. For HPS,
        we expect GLOW to raise an exception.
        """
        # WHEN: Loading Visor page
        # Conditionally xfail on HPS until HPS/Visor flakiness is resolved (See Issue #103)
        if request.node.get_closest_marker("use_hps"):
            pytest.xfail(reason="Visor unstable on HPS, see Issue #103.")

        self._open_visor_page(session_selenium_webdriver, function_project)
        # THEN: no visor canvas is shown and status text are False
        with pytest.raises(NoSuchElementException):
            session_selenium_webdriver.find_element(By.TAG_NAME, "canvas")
        wait_for_partial_text(session_selenium_webdriver, "visor_started", "Visor Started: False")
        wait_for_partial_text(session_selenium_webdriver, "visor_updated", "Visor Updated: False")

        # WHEN: Launching Visor instance
        session_glow.clear_output()
        wait_for_element_and_click(session_selenium_webdriver, "trigger_start")
        # THEN: visor canvas is shown, status text is updated and updated metadata is not shown yet
        wait_for_partial_text(session_selenium_webdriver, "visor_started", "Visor Started: True", timeout=300)
        wait_for_element(session_selenium_webdriver, "canvas", element_type=By.TAG_NAME, timeout=100)
        assert "UPDATED_NAME" not in session_selenium_webdriver.page_source
        assert session_glow.text_in_output("Creating instance for visor_instance_step", "api")
        assert not session_glow.text_in_output("Restarting visor-instance", "api")

        # WHEN: Updating Visor instance
        wait_for_element_and_click(session_selenium_webdriver, "trigger_update")
        # THEN: visor canvas is updated with new metadata
        wait_for_partial_text(session_selenium_webdriver, "visor_updated", "Visor Updated: True")
        wait_for_element(session_selenium_webdriver, "canvas", element_type=By.TAG_NAME)
        wait_for_text_in_page_source(session_selenium_webdriver, "UPDATED_NAME")

        # WHEN: refreshing page
        session_glow.clear_output()
        self._open_visor_page(session_selenium_webdriver, function_project)
        # THEN: Nothing is loaded
        with pytest.raises(NoSuchElementException):
            session_selenium_webdriver.find_element(By.TAG_NAME, "canvas")
        # WHEN: clicking on start again
        wait_for_element_and_click(session_selenium_webdriver, "trigger_start")
        # THEN: it fetches the visor instance info (doesn't relaunch instance)
        # and recreates the viewer with the updated metadata
        wait_for_element(session_selenium_webdriver, "canvas", element_type=By.TAG_NAME, timeout=100)
        wait_for_text_in_page_source(session_selenium_webdriver, "UPDATED_NAME")
        assert not session_glow.text_in_output("Creating instance for visor_instance_step", "api")
        assert not session_glow.text_in_output("Restarting visor-instance", "api")

        # WHEN: restarting GLOW and refreshing page (also restarts output proc).
        session_glow.restart()
        self._open_visor_page(session_selenium_webdriver, function_project)
        # THEN: Nothing is loaded
        with pytest.raises(NoSuchElementException):
            session_selenium_webdriver.find_element(By.TAG_NAME, "canvas")
        # WHEN: clicking on start again
        wait_for_element_and_click(session_selenium_webdriver, "trigger_start")
        # THEN: it fetches the visor instance info (doesn't relaunch instance)
        # and recreates the viewer with the updated metadata
        wait_for_element(session_selenium_webdriver, "canvas", element_type=By.TAG_NAME, timeout=100)
        wait_for_text_in_page_source(session_selenium_webdriver, "UPDATED_NAME")
        assert not session_glow.text_in_output("Creating instance for visor_instance_step", "api")
        assert not session_glow.text_in_output("Restarting visor-instance", "api")

        # WHEN: restarting PIM/HPS and refreshing page.
        restart_product_instance_system()
        session_glow.clear_output()
        self._open_visor_page(session_selenium_webdriver, function_project)
        # THEN: Nothing is loaded
        with pytest.raises(NoSuchElementException):
            session_selenium_webdriver.find_element(By.TAG_NAME, "canvas")
        assert not session_glow.text_in_output("Restarting visor-instance", "api")
        # WHEN: clicking on start again
        wait_for_element_and_click(session_selenium_webdriver, "trigger_start")
        # THEN: it relaunches the visor instance and recreates the viewer,
        # but it's empty because the state is not restored
        wait_for_element(session_selenium_webdriver, "canvas", element_type=By.TAG_NAME, timeout=100)
        assert "UPDATED_NAME" not in session_selenium_webdriver.page_source
        assert not session_glow.text_in_output("Creating instance for visor_instance_step", "api")
        assert session_glow.text_in_output("Restarting visor-instance", "api")
        # WHEN: clicking on update
        wait_for_element_and_click(session_selenium_webdriver, "trigger_update")
        # THEN: it updates the visor instance and the viewer reflects the changes
        wait_for_text_in_page_source(session_selenium_webdriver, "UPDATED_NAME")
        wait_for_element(session_selenium_webdriver, "canvas", element_type=By.TAG_NAME)

        wait_for_element_and_click(session_selenium_webdriver, "trigger_stop")
        wait_for_partial_text(session_selenium_webdriver, "visor_started", "Visor Started: False")
