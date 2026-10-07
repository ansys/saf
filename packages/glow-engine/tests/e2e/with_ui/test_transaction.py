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

import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_element_and_click,
    wait_for_element_and_send_text,
    wait_for_text,
)
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_ui,
    pytest.mark.parametrize("ui_enabled", [True], indirect=True),
    pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    ),
]


def test_transaction_non_stored_inputs_and_outputs_dash(
    function_project: ProjectFixture[EndToEndSolution],
    session_selenium_webdriver: WebDriver,
):
    """
    Test that transactions transaction inputs and outputs work well used with DashClient and custom types.
    """
    # GIVEN: A project with a non-stored I/O workflow not yet run.
    session_selenium_webdriver.get(function_project.ui_url)
    wait_for_element(session_selenium_webdriver, "page-content")
    wait_for_element_and_click(
        session_selenium_webdriver,
        "//*[contains(text(), 'Second Page')]",
        element_type=By.XPATH,
    )

    # WHEN: Running the workflow
    wait_for_text(session_selenium_webdriver, "test_non_stored_result", "Workflow not run yet.")
    wait_for_element_and_send_text(session_selenium_webdriver, "x_arg", "3")
    wait_for_element_and_send_text(session_selenium_webdriver, "y_arg", "4")
    wait_for_element_and_send_text(session_selenium_webdriver, "z_arg", "5")
    wait_for_element_and_click(session_selenium_webdriver, "test_non_stored")

    # THEN: The non-stored I/O workflow runs successfully
    wait_for_text(session_selenium_webdriver, "test_non_stored_result", "Workflow run successful.")
