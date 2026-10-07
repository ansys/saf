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

import httpx2
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.bdm.api import NO_ENTITY
from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.platform_specific import xfail_for_ci
from ansys.saf.testing.selenium import (
    move_to_element,
    wait_for_element,
    wait_for_element_and_click,
    wait_for_element_and_send_text,
    wait_for_partial_text,
    wait_for_text,
    wait_for_text_to_be_different,
)
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.conftest import MOCKS_DIR
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    TransactionVerificationStep,
)

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

MAX_READ_WRITE_TIME = 40


@retry(
    stop=stop_after_attempt(50),
    wait=wait_fixed(0.1),
)
def wait_for_img_to_be_loaded(image: WebElement) -> None:
    if not image.get_attribute("src"):  # type: ignore
        raise TryAgain


class TestDashUI:
    def test_solution_ui(
        self,
        deployment_type: TestDeployment,
        session_selenium_webdriver: WebDriver,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """
        Test that the UI callbacks are working as expected. Test that the UI shows the project name and portal button
        works.
        """
        session_selenium_webdriver.get(function_project.ui_url)
        wait_for_element(session_selenium_webdriver, "page-content")
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'First Page')]",
            element_type=By.XPATH,
        )

        # test project injected from dash callback with typehints
        wait_for_partial_text(session_selenium_webdriver, "result-inj", "Result:0.0")
        wait_for_element_and_send_text(session_selenium_webdriver, "first-arg-inj", "1")
        wait_for_element_and_send_text(session_selenium_webdriver, "second-arg-inj", "1")
        wait_for_element_and_click(session_selenium_webdriver, "calculate_project_injected")
        wait_for_partial_text(session_selenium_webdriver, "result-inj", "Result:2.0")

        # test project injected from dash callback without typehint
        wait_for_partial_text(session_selenium_webdriver, "result-inj-no-typehint", "Result:0.0")
        wait_for_element_and_send_text(session_selenium_webdriver, "first-arg-inj-no-typehint", "1")
        wait_for_element_and_send_text(session_selenium_webdriver, "second-arg-inj-no-typehint", "3")
        wait_for_element_and_click(session_selenium_webdriver, "calculate_project_injected_no_typehint")
        wait_for_partial_text(session_selenium_webdriver, "result-inj-no-typehint", "Result:4.0")

        # test project injected from dash callback with typehints and a Trigger input before pathname
        wait_for_partial_text(session_selenium_webdriver, "result-inj-trig-before-pathname", "Result:0.0")
        wait_for_element_and_send_text(session_selenium_webdriver, "first-arg-inj-trig-before-pathname", "1")
        wait_for_element_and_send_text(session_selenium_webdriver, "second-arg-inj-trig-before-pathname", "1")
        wait_for_element_and_click(session_selenium_webdriver, "calculate_project_injected_trigger_before_pathname")
        wait_for_partial_text(session_selenium_webdriver, "result-inj-trig-before-pathname", "Result:2.0")

        # test project injected from dash callback with typehints and a Trigger input after pathname
        wait_for_partial_text(session_selenium_webdriver, "result-inj-trig-after-pathname", "Result:0.0")
        wait_for_element_and_send_text(session_selenium_webdriver, "first-arg-inj-trig-after-pathname", "1")
        wait_for_element_and_send_text(session_selenium_webdriver, "second-arg-inj-trig-after-pathname", "1")
        wait_for_element_and_click(session_selenium_webdriver, "calculate_project_injected_trigger_after_pathname")
        wait_for_partial_text(session_selenium_webdriver, "result-inj-trig-after-pathname", "Result:2.0")

        # test project injected from dash callback with from __future__ import annotations
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'Future Page')]",
            element_type=By.XPATH,
        )
        wait_for_partial_text(session_selenium_webdriver, "result-future", "Result:2.0")
        wait_for_element_and_send_text(session_selenium_webdriver, "arg1", "2")
        wait_for_element_and_send_text(session_selenium_webdriver, "arg2", "2")
        wait_for_element_and_click(session_selenium_webdriver, "calculate-future")
        wait_for_partial_text(session_selenium_webdriver, "result-future", "Result:4.0")

        wait_for_element(
            session_selenium_webdriver,
            f"//button[contains(text(), 'Project Name: {function_project.display_name}')]",
            element_type=By.XPATH,
        )

        expected_text = "Back to Projects" if deployment_type == TestDeployment.Desktop else "Back to Portal"
        return_button = wait_for_element(
            session_selenium_webdriver,
            f"//*[contains(text(), '{expected_text}')]",
            element_type=By.XPATH,
        )
        assert return_button.is_enabled()

    @xfail_for_ci(reason="Fix test_dash_background_callbacks CI failures.")
    def test_dash_background_callbacks(
        self,
        session_selenium_webdriver: WebDriver,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that the Dash background callbacks are working as expected, via a background callback manager that runs
        them on a different thread.
        """
        session_selenium_webdriver.get(function_project.ui_url)
        wait_for_element(session_selenium_webdriver, "page-content")

        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'First Page')]",
            element_type=By.XPATH,
        )
        wait_for_partial_text(session_selenium_webdriver, "result_background", "Result:0.0")
        element = wait_for_element(session_selenium_webdriver, "result_background")
        ui_pid = int(element.text.split("/PID:")[-1])

        wait_for_element_and_send_text(session_selenium_webdriver, "third-arg-inj", "3")
        wait_for_element_and_send_text(session_selenium_webdriver, "fourth-arg-inj", "4")
        wait_for_element_and_click(session_selenium_webdriver, "calculate_in_background")

        @retry(
            stop=stop_after_attempt(300),
            wait=wait_fixed(0.1),
        )
        def wait_for_transaction_to_finish(step: TransactionVerificationStep, method_name: str) -> bool:
            if step.get_method_state(method_name).status != MethodStatus.Completed:
                raise TryAgain
            return True

        assert wait_for_transaction_to_finish(
            function_project.project.steps.transaction_verification_step,
            "get_field_1_and_2_and_set_the_sum_in_result",
        )

        wait_for_partial_text(session_selenium_webdriver, "result_background", "Result:7.0")
        element = wait_for_element(session_selenium_webdriver, "result_background")
        ui_pid_background_callback = int(element.text.split("/PID:")[-1])

        assert ui_pid != ui_pid_background_callback

        wait_for_partial_text(session_selenium_webdriver, "result_background_new", "Result:0.0")
        # this appends 0 to the existing 3, so the input text will be 30
        wait_for_element_and_send_text(session_selenium_webdriver, "third-arg-inj", "0")
        wait_for_element_and_send_text(session_selenium_webdriver, "fourth-arg-inj", "0")
        wait_for_element_and_click(session_selenium_webdriver, "calculate_in_background_with_project_injected")
        assert wait_for_transaction_to_finish(
            function_project.project.steps.transaction_verification_step,
            "get_field_1_and_2_and_set_the_sum_in_result",
        )

        wait_for_partial_text(session_selenium_webdriver, "result_background_new", "Result:70.0")
        element = wait_for_element(session_selenium_webdriver, "result_background_new")
        ui_pid_background_callback_new = int(element.text.split("/PID:")[-1])

        assert ui_pid != ui_pid_background_callback != ui_pid_background_callback_new

    def test_read_entity_from_ui_using_injected_project_scope(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that an entity can be read from the storage scope of the client using
        the project injected from the dash callback.
        """
        step = function_project.project.steps.transaction_verification_step
        step.store_file_entity_with_text(text="Hello World!")

        session_selenium_webdriver.get(function_project.ui_url)
        wait_for_element(session_selenium_webdriver, "page-content")

        wait_for_text_to_be_different(session_selenium_webdriver, "text_from_entity", "Text: Hello World!")
        wait_for_element_and_click(session_selenium_webdriver, "read_entity")
        wait_for_text(session_selenium_webdriver, "text_from_entity", "Text: Hello World!")

    def test_project_scope_lock_removed_after_callback(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that the lock created when using the project scope in a UI callback is removed
        after the callback is done.
        """
        step = function_project.project.steps.transaction_verification_step
        session_selenium_webdriver.get(function_project.ui_url)
        wait_for_element(session_selenium_webdriver, "page-content")
        assert step.lock_id == ""
        wait_for_element_and_click(session_selenium_webdriver, "save_lock_id")
        wait_for_text(session_selenium_webdriver, "lock_id", "ok", timeout=50)
        assert step.lock_id != ""  # lock created
        # verify lock does not exists
        response = httpx2.get(f"{function_project.project.url}/bdm-locks/{step.lock_id}")
        assert response.status_code == 404

    def test_file_ui_roundtrip(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that the same file can be created on the UI service and re-downloaded again on a different callback.
        """
        session_selenium_webdriver.get(function_project.ui_url)
        wait_for_element(session_selenium_webdriver, "page-content")

        wait_for_element_and_click(session_selenium_webdriver, "create_file")
        wait_for_text(session_selenium_webdriver, "created_file_check", "File Created!")

        wait_for_text_to_be_different(session_selenium_webdriver, "text_from_file", "Text: text from ui callback")
        wait_for_element_and_click(session_selenium_webdriver, "read_file")
        wait_for_text(session_selenium_webdriver, "text_from_file", "Text: text from ui callback")

    def test_navigate_pages_with_and_without_websockets(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that there are no errors while navigating between pages with and without WS Events.
        """

        @retry(
            stop=stop_after_attempt(200),
            wait=wait_fixed(0.1),
        )
        def wait_for_msgs_in_output(log_lines: list[str], start_line_idx: int, msg: str, expected_msgs: int) -> int:
            connect_msgs = len([line for line in log_lines[start_line_idx:] if msg in line])
            if connect_msgs != expected_msgs:
                raise TryAgain
            return len(log_lines)

        # GIVEN: Solution with at least three pages:
        # - first page with 0 websockets
        # - websockets page with N websockets
        # - third page with M websocket (M != N)
        expected_websockets = {"first": 0, "websockets": 8, "third": 1}
        connect_api_msg = "Streaming events for"
        connect_ui_msg = "Creating websocket with url="
        disconnect_api_msg = "websocket disconnected"

        # WHEN: Navigating to page with N websockets (From 0)
        session_selenium_webdriver.get(function_project.ui_url)
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'Websockets Page')]",
            element_type=By.XPATH,
        )
        wait_for_element(
            session_selenium_webdriver,
            "//*[contains(text(), 'We are in WebSockets Page')]",
            element_type=By.XPATH,
        )
        last_api_idx = wait_for_msgs_in_output(
            session_glow.api_output,
            0,
            connect_api_msg,
            expected_websockets["websockets"],
        )
        last_ui_idx = wait_for_msgs_in_output(
            session_glow.ui_output,
            0,
            connect_ui_msg,
            expected_websockets["websockets"],
        )

        # WHEN: Navigating to page with M websockets (From N)
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'Third Page')]",
            element_type=By.XPATH,
        )
        wait_for_element(
            session_selenium_webdriver,
            "//*[contains(text(), 'We are in Third Page')]",
            element_type=By.XPATH,
        )
        wait_for_msgs_in_output(
            session_glow.api_output,
            last_api_idx,
            disconnect_api_msg,
            expected_websockets["websockets"],
        )
        last_api_idx = wait_for_msgs_in_output(
            session_glow.api_output,
            last_api_idx,
            connect_api_msg,
            expected_websockets["third"],
        )
        last_ui_idx = wait_for_msgs_in_output(
            session_glow.ui_output,
            last_ui_idx,
            connect_ui_msg,
            expected_websockets["third"],
        )

        # WHEN: Navigating to page with 0 websockets (From M)
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'First Page')]",
            element_type=By.XPATH,
        )
        wait_for_element(
            session_selenium_webdriver,
            "//*[contains(text(), 'We are in First Page')]",
            element_type=By.XPATH,
        )
        wait_for_msgs_in_output(session_glow.api_output, last_api_idx, disconnect_api_msg, expected_websockets["third"])
        last_api_idx = wait_for_msgs_in_output(
            session_glow.api_output,
            last_api_idx,
            connect_api_msg,
            expected_websockets["first"],
        )
        last_ui_idx = wait_for_msgs_in_output(
            session_glow.ui_output,
            last_ui_idx,
            connect_ui_msg,
            expected_websockets["first"],
        )

        # THEN: No error has occurred and all websockets connected and disconnected properly

    @xfail_for_ci(reason="Consistently fails in github-hosted runner.")
    def test_multithread_graphql_on_dashclient(
        self,
        session_selenium_webdriver: WebDriver,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that the graphql client used within DashClient is working properly when a callback
        is triggered multiple times quickly.
        (The original sync graphql client does not work in multithreaded environment -which is what
        dash is about- so we had to write a custom client)
        """
        # GIVEN: a solution UI
        session_selenium_webdriver.get(function_project.ui_url)
        wait_for_element(session_selenium_webdriver, "page-content")
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'First Page')]",
            element_type=By.XPATH,
        )

        # WHEN: triggering the callback quickly by changing the input
        for i in range(10):
            wait_for_element_and_send_text(session_selenium_webdriver, "my-input", str(i))

        # THEN: all the characters sent can be seen from the output.
        # (In case of 'TransportAlreadyConnected' graphql error, not all values would be sent)
        expected_value = "Value: 0123456789"
        wait_for_text(session_selenium_webdriver, "my-output", expected_value, timeout=100)

    def test_use_get_entity_url_in_ui_component(
        self,
        session_selenium_webdriver: WebDriver,
        function_project: ProjectFixture[EndToEndSolution],
        deployment_type: TestDeployment,
    ):
        """
        Test that the BDM system can handle workflows in which a file cached from the UI can properly reach the API.
        """
        step = function_project.project.steps.transaction_verification_step
        if deployment_type == TestDeployment.Desktop:
            source_path = str(MOCKS_DIR / "solution_end_to_end" / "method_assets" / "logo.png")
        else:
            source_path = "/app/src/ansys/solutions/solution_end_to_end/method_assets/logo.png"
        step.store_image_entity(source_path=source_path)
        assert step.image_entity != NO_ENTITY

        # GIVEN: a solution UI
        session_selenium_webdriver.get(function_project.ui_url)
        wait_for_element(session_selenium_webdriver, "page-content")
        wait_for_element_and_click(
            session_selenium_webdriver,
            "//*[contains(text(), 'Second Page')]",
            element_type=By.XPATH,
        )

        image = wait_for_element(session_selenium_webdriver, "entity_img")
        assert image.get_attribute("src") is None  # pyright: ignore[reportUnknownMemberType]

        # WHEN: calling a blob endpoint from a UI component
        move_to_element(session_selenium_webdriver, "render_image")
        wait_for_element_and_click(session_selenium_webdriver, "render_image")

        # loaded image has src pointing to API URL accessible from outside of the API container
        expected_src = (
            f"{function_project.api_url}/projects/{function_project.project_id}/"
            "steps/transaction-verification-step/blobs/image-entity"
        )
        wait_for_img_to_be_loaded(image)
        assert image.get_attribute("src") == expected_src  # pyright: ignore[reportUnknownMemberType]
        assert function_project.project.storage_scope.get_bytes(step.image_entity) == httpx2.get(expected_src).content
