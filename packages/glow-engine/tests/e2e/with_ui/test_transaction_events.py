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

import asyncio
from collections.abc import Callable, Generator
import os
from pathlib import Path
import sys
from typing import TypeVar
from unittest import mock

import aiohttp
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.selenium import (
    move_to_element,
    wait_for_element,
    wait_for_element_and_click,
    wait_for_text,
    wait_for_text_to_be_different,
)
from ansys.saf.testing.solution.end_to_end import (
    EnvVarDebugLogLevel,
    GlowBaseProcess,
    ProjectFixture,
    get_solution_root_dir,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    CustomTypeABC,
    CustomTypeXYZ,
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

T = TypeVar("T", bound=Solution)


@pytest.fixture(scope="class")
def set_logging_level_to_debug(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    session_glow.change_configuration(EnvVarDebugLogLevel)
    yield
    session_glow.configure_default_execution()


def _get_websockets_page(driver: WebDriver, project: ProjectFixture[EndToEndSolution]):
    driver.get(project.ui_url)
    wait_for_element_and_click(driver, "//*[contains(text(), 'Websockets Page')]", element_type=By.XPATH)
    wait_for_element(driver, "//*[contains(text(), 'We are in WebSockets Page')]", element_type=By.XPATH)


@pytest.mark.parametrize("max_number_of_workers", [4], indirect=True)
@pytest.mark.parametrize("shutdown_api_server_first", [None, True, False], indirect=True)
class TestTransactionEvents:
    def test_single_event_single_client(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that events raised on transactions are properly propagated. Single event, single client.
        """
        # GIVEN: an existing project
        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")

        # WHEN: no event is raised
        # THEN: element has the default text
        wait_for_text(session_selenium_webdriver, "event_message", "Not triggered yet.")

        # WHEN: raising an event
        move_to_element(session_selenium_webdriver, "trigger_event")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_event")

        # THEN: the element has the expected text
        wait_for_text(
            session_selenium_webdriver,
            "event_message",
            'Received message: {"message":"testing!"}',
            timeout=100,
        )

    def test_single_event_multiple_clients(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        get_selenium_webdriver: Callable[[], WebDriver],
    ):
        """
        Test that events raised on transactions are properly propagated. Single event, multiple clients.
        """
        # GIVEN: an existing project
        # GIVEN: multiple clients connected to the solution
        first_driver = get_selenium_webdriver()
        _get_websockets_page(first_driver, function_project)
        wait_for_element(first_driver, "page-content")

        wait_for_text(first_driver, "event_message", "Not triggered yet.")

        second_driver = get_selenium_webdriver()
        _get_websockets_page(second_driver, function_project)
        wait_for_element(second_driver, "page-content")

        wait_for_text(second_driver, "event_message", "Not triggered yet.")

        # WHEN: an event is raised from one of the clients
        move_to_element(first_driver, "trigger_event")
        wait_for_element_and_click(first_driver, "trigger_event")

        # THEN: all connected clients receive the message,
        # even if some disconnect
        wait_for_text(first_driver, "event_message", 'Received message: {"message":"testing!"}', timeout=100)
        first_driver.close()

        wait_for_text(second_driver, "event_message", 'Received message: {"message":"testing!"}', timeout=100)
        second_driver.close()

    def test_multiple_events_single_client(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that events raised on transactions are properly propagated. Multiple events, single client.
        """
        # GIVEN: an existing project
        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")

        wait_for_text(session_selenium_webdriver, "event_message", "Not triggered yet.")
        wait_for_text(session_selenium_webdriver, "event_message_second", "Not triggered yet.")

        # WHEN: multiple events are raised on different websockets
        move_to_element(session_selenium_webdriver, "trigger_event_second")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_event")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_event_second")

        # THEN: the right message is received on each websocket
        wait_for_text(
            session_selenium_webdriver,
            "event_message",
            'Received message: {"message":"testing!"}',
            timeout=100,
        )
        wait_for_text(
            session_selenium_webdriver,
            "event_message_second",
            'Received message: {"message":"testing_second!"}',
            timeout=100,
        )

    def test_multiple_events_same_transaction(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that events raised on transactions are properly propagated. Multiple events on the same transaction.
        """
        # GIVEN: an existing project
        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")

        wait_for_text(session_selenium_webdriver, "multiple_events_message", "Not triggered yet.")

        # WHEN: multiple events are raised on the same transaction
        move_to_element(session_selenium_webdriver, "trigger_multiple_events")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_multiple_events")

        # THEN: all events are retrieved through the same websocket and callback
        expected_test = 'Received messages: {"message":0},{"message":1},{"message":2}'
        wait_for_text(session_selenium_webdriver, "multiple_events_message", expected_test, timeout=100)

    def test_events_retain_original_type(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that events are transmitted retaining the type of the original message.
        """
        # GIVEN: an existing project with two clients connected
        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")

        wait_for_text(session_selenium_webdriver, "event_message", "Not triggered yet.")

        # WHEN: an event is raised
        step = function_project.project.steps.transaction_verification_step
        step.field_1 = 1.0
        step.trigger_event_with_field_1()

        # THEN: the event is retrieved on client in the expected type
        expected_text = "Received message: 1.0"
        wait_for_text_to_be_different(session_selenium_webdriver, "event_message", "Not triggered yet.")
        assert session_selenium_webdriver.find_element(By.ID, "event_message").text == expected_text
        wait_for_text(session_selenium_webdriver, "event_message", expected_text, timeout=100)

    def test_multiple_events_multiple_clients(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        get_selenium_webdriver: Callable[[], WebDriver],
    ):
        """
        Test that events raised on transactions are properly propagated. Multiple events with multiple clients.
        """
        # GIVEN: an existing project with two clients connected
        first_driver = get_selenium_webdriver()
        _get_websockets_page(first_driver, function_project)
        wait_for_element(first_driver, "page-content")

        wait_for_text(first_driver, "event_message", "Not triggered yet.")

        second_driver = get_selenium_webdriver()
        _get_websockets_page(second_driver, function_project)
        wait_for_element(second_driver, "page-content")

        wait_for_text(second_driver, "event_message", "Not triggered yet.")

        for x in range(10):
            # WHEN: an event is raised
            step = function_project.project.steps.transaction_verification_step
            step.field_1 = x
            step.trigger_event_with_field_1()

            # THEN: the event is retrieved on both clients
            expected_text = f"Received message: {x}.0"
            wait_for_text(first_driver, "event_message", expected_text, timeout=100)
            wait_for_text(second_driver, "event_message", expected_text, timeout=100)

    def test_stream_custom_data(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that websocket events are able to work with any jsonable data type.
        """
        # GIVEN: an existing project
        step = function_project.project.steps.transaction_verification_step
        step.custom_object_for_events = CustomTypeABC(a=1, b=CustomTypeXYZ(x=2, y=3, z=4), c=5)

        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")
        # WHEN: no event is raised
        # THEN: element has the default text
        wait_for_text(session_selenium_webdriver, "event_message_custom_data", "Not triggered yet.")

        # WHEN: raising an event
        move_to_element(session_selenium_webdriver, "trigger_custom_data_event")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_custom_data_event")

        # THEN: the element has the expected text
        wait_for_text(session_selenium_webdriver, "event_message_custom_data", "Custom data validated")

    def test_transaction_termination_event(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that a transaction can send an event after it has finished successfully.
        """
        # GIVEN: an existing project and an element with the default text
        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")
        wait_for_text(session_selenium_webdriver, "termination_event_message", "No termination event received.")

        # WHEN: when running a transaction that raises a termination event
        move_to_element(session_selenium_webdriver, "trigger_termination_event")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_termination_event")

        # THEN: the element has the expected text
        wait_for_text(
            session_selenium_webdriver,
            "termination_event_message",
            "Transaction finished with status 'completed'",
        )

    def test_no_transaction_termination_event(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that a transaction termination event is not sent by default.
        """
        # GIVEN: an existing project and an element with the default text
        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")
        wait_for_text(session_selenium_webdriver, "termination_event_message", "No termination event received.")

        # WHEN: when running a transaction that does not raise a termination event
        move_to_element(session_selenium_webdriver, "trigger_termination_event")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_termination_event")

        # THEN: the element still has the default text
        wait_for_text(session_selenium_webdriver, "termination_event_message", "No termination event received.")

    def test_long_running_transaction_termination_event(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that a long_running transaction can send an event after it has finished successfully.
        """
        # GIVEN: an existing project and an element with the default text
        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")
        wait_for_text(session_selenium_webdriver, "termination_event_message", "No termination event received.")

        # WHEN: when running a transaction that raises a termination event
        move_to_element(session_selenium_webdriver, "trigger_lr_termination_event")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_lr_termination_event")

        # THEN: the element has the expected text
        wait_for_text(
            session_selenium_webdriver,
            "termination_event_message",
            "Transaction finished with status 'completed'",
            timeout=40,
        )

    def test_failed_method_state_transaction_termination_event(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that a failed transaction can still send an event after it has finished.
        """
        # GIVEN: an existing project and an element with the default text
        _get_websockets_page(session_selenium_webdriver, function_project)
        wait_for_element(session_selenium_webdriver, "page-content")
        wait_for_text(session_selenium_webdriver, "termination_event_message", "No termination event received.")

        # WHEN: when running a transaction that raises a termination event
        move_to_element(session_selenium_webdriver, "trigger_failed_termination_event")
        wait_for_element_and_click(session_selenium_webdriver, "trigger_failed_termination_event")

        # THEN: the element has the expected text
        wait_for_text(
            session_selenium_webdriver,
            "termination_event_message",
            "Transaction finished with status 'failed'",
        )

    def test_events_with_modified_uvicorn_root_path(
        self,
        run_glow_production: Callable[[type[T], Path], GlowBaseProcess[T]],
        tmp_solutions_dir: dict[type[T], Path],
        get_glow_client: Callable[[GlowBaseProcess[EndToEndSolution]], Client[EndToEndSolution]],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test that the websocket works properly when GLOW is available under /api,
        e.g., with --root-path /api passed to uvicorn.
        """
        # GIVEN: a GLOW instance started directly with uvicorn with "--root-path /api"
        solution_src_dir = get_solution_root_dir(tmp_solutions_dir[EndToEndSolution]) / "src"  # type: ignore
        with mock.patch.dict(
            os.environ,
            {"PYTHONPATH": os.pathsep.join(sys.path + [str(solution_src_dir)])},
        ):
            glow_proc = run_glow_production(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], use_root_path=True)  # type: ignore
            glow_client = get_glow_client(glow_proc)  # pyright: ignore[reportUnknownArgumentType]
            with ProjectFixture(glow_proc, glow_client) as project:  # pyright: ignore[reportUnknownArgumentType]
                _get_websockets_page(session_selenium_webdriver, project)
                wait_for_element(session_selenium_webdriver, "page-content")

                # WHEN: no event is raised
                # THEN: element has the default text
                wait_for_text(session_selenium_webdriver, "event_message", "Not triggered yet.")

                # WHEN: raising an event
                move_to_element(session_selenium_webdriver, "trigger_event")
                wait_for_element_and_click(session_selenium_webdriver, "trigger_event")

                # THEN: the element has the expected text
                wait_for_text(session_selenium_webdriver, "event_message", 'Received message: {"message":"testing!"}')


@pytest.mark.usefixtures("set_logging_level_to_debug")
class TestTransactionEventLogging:
    async def test_single_event_single_client_logs_indicate_event_row_removal_and_minimal_project_modification(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """
        Test that when running a simple event propagation scenario the logs
        do not contain unexpected project modification logs,
        which would indicate that the event handling is causing unintended side effects on the project
        and check that we end up with no events in the repository
        """

        # GIVEN: an existing project

        # WHEN - connecting a websocket, receiving one event and then closing the socket

        step = function_project.project.steps.transaction_verification_step
        ws_url = f"ws://{function_project.url.split('/')[2]}/events/{function_project.project_name}/steps/transaction-verification-step/streams/my-stream"
        aiohttp_session = aiohttp.ClientSession()
        try:
            async with aiohttp_session.ws_connect(ws_url) as websocket:
                step.trigger_event()
                received_message = await websocket.receive_json(timeout=10)
                assert received_message == {"message": "testing!"}
        finally:
            # annoyingly the socket is only disconnected when the aiohttp session is closed
            await aiohttp_session.close()

        await asyncio.sleep(20)  # allow time for the GLOW server to detect the disconnect of the websocket

        # WHEN: doing something that triggers identifiable logging - run a transaction method
        step.set_field_1_to_1()

        # THEN: wait until we see the log corresponding to the transaction method
        assert session_glow.text_in_output("set_field_1_to_1")

        # THEN: the number of occurrences of project modification in the log
        #       prior to that point is limited to expectations
        #       and the number of events and event listeners are reduced 0
        project_mod_occurrences = 0
        no_events = False
        no_event_listeners = False
        for line in session_glow.api_output:
            if "set_field_1_to_1" in line:
                break
            if "Updating project modification date" in line:
                project_mod_occurrences += 1
            if "Event row count reduced to 0" in line:
                no_events = True
            if "EventListener row count: 0 - after destroying event listener" in line:
                no_event_listeners = True
        assert project_mod_occurrences == 3
        assert no_events
        assert no_event_listeners
