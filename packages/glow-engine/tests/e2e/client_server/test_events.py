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
from collections.abc import AsyncGenerator, Generator
from typing import Any

import aiohttp
from aiohttp.http_websocket import WSMsgType
import pytest

from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DebugConfiguration,
    DefaultDebug,
    EnvVarDebug,
    GlowBaseProcess,
    ProjectFixture,
)
from tests.mocks.solutions.events import CustomField, EventsSolution

pytestmark = pytest.mark.parametrize("solution_type", [EventsSolution], indirect=True)

step_id = "events-step"
stream_name = "test-stream"

# TIMEOUT is the timeout period between when a message is stored and when the message is expected to be
# received on the websocket. This might seem a long time but the event listener polling loop has
# a default interval of 1 second to minimize the load on the database.
TIMEOUT = 10.0


@pytest.fixture
def ws_url(function_project: ProjectFixture[EventsSolution]) -> str:
    # function_project.url.split('/')[2] contains the host address in the format: localhost:5432
    return f"ws://{function_project.url.split('/')[2]}/events/{function_project.project_name}/steps/{step_id}/streams/{stream_name}"


@pytest.fixture
def ws_url_with_stream_name(function_project: ProjectFixture[EventsSolution], request: pytest.FixtureRequest) -> str:
    # function_project.url.split('/')[2] contains the host address in the format: localhost:5432
    return f"ws://{function_project.url.split('/')[2]}/events/{function_project.project_name}/steps/{step_id}/streams/{request.param}"


@pytest.fixture
async def aiohttp_session() -> AsyncGenerator[aiohttp.ClientSession, None]:
    session = aiohttp.ClientSession()
    yield session
    await session.close()


async def test_single_event_single_client(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised and the client receives the message."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        step.raise_event()
        received_message = await websocket.receive_json(timeout=TIMEOUT)
        assert received_message == message


async def test_event_raised_before_connect_times_out(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised before the client is connected and the client does not receive any message."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    step.raise_event()

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        with pytest.raises(asyncio.TimeoutError):
            await websocket.receive_json(timeout=TIMEOUT)


@pytest.mark.parametrize("ws_url_with_stream_name", ["raise-event"], indirect=True)
async def test_single_event_single_client_default_stream_name(
    function_project: ProjectFixture[EventsSolution],
    ws_url_with_stream_name: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised on a stream with the default name and the client receives the message."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message

    async with aiohttp_session.ws_connect(ws_url_with_stream_name) as websocket:
        step.raise_event()
        received_message = await websocket.receive_json(timeout=TIMEOUT)
        assert received_message == message


async def test_single_event_single_client_raise_after_create_ws(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised after the client connects to the websocket and the message is received."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        with pytest.raises(asyncio.TimeoutError):
            await websocket.receive_json(timeout=TIMEOUT)
        step.raise_event()
        received_message = await websocket.receive_json(timeout=TIMEOUT)
        assert received_message == message


async def test_single_event_single_client_long_running(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised on a long running transaction and the message is received."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        step.raise_event_long().wait()
        received_message = await websocket.receive_json(timeout=TIMEOUT)
        assert received_message == message


async def test_event_raised_before_connect_times_out_long_running(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised on a long running transaction and the message is received."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    step.raise_event_long().wait()

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        with pytest.raises(asyncio.TimeoutError):
            await websocket.receive_json(timeout=TIMEOUT)


async def test_multiple_events_single_client(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """Multiple events are raised and the messages are received in order."""
    step = function_project.project.steps.events_step
    first_message = {"message": "first_message"}
    second_message = {"message": "second_message"}

    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        step.message = first_message
        step.raise_event()
        step.message = second_message
        step.raise_event()
        first_received_message = await websocket.receive_json(timeout=TIMEOUT)
        second_received_message = await websocket.receive_json(timeout=TIMEOUT)
        assert first_received_message == first_message
        assert second_received_message == second_message


async def test_multiple_clients_single_event(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised and all the clients receive the message."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as first_ws, aiohttp_session.ws_connect(ws_url) as second_ws:
        step.raise_event()
        first_message = await first_ws.receive_json(timeout=TIMEOUT)
        second_message = await second_ws.receive_json(timeout=TIMEOUT)
        assert first_message == second_message == message


async def test_a_websocket_only_receives_messages_that_are_transmitted_after_the_web_socket_connects(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    # GIVEN - glow server containing a solution with a project that transmits events
    step = function_project.project.steps.events_step
    message1 = {"message": "message 1"}
    message2 = {"message": "message 2"}

    # WHEN - an event is raised
    step.message = message1
    step.stream_name = stream_name
    step.raise_event()

    # THEN - if a client connects after the event is raised,
    #        it doesn't receive the event but can receive the next event
    async with aiohttp_session.ws_connect(ws_url) as websocket:
        step.message = message2
        step.raise_event()
        received_message = await websocket.receive_json(timeout=TIMEOUT)
        assert received_message == message2

        # THEN - the client doesn't receive any more events
        with pytest.raises(asyncio.TimeoutError):
            await websocket.receive_json(timeout=TIMEOUT)


async def test_multiple_clients_single_event_one_client_disconnects(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised, all clients receive the message even if one disconnects before all of them receive it."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as first_ws, aiohttp_session.ws_connect(ws_url) as second_ws:
        step.raise_event()
        first_message = await first_ws.receive_json(timeout=TIMEOUT)
        await first_ws.close()
        second_message = await second_ws.receive_json(timeout=TIMEOUT)
        assert first_message == second_message == message
        async with aiohttp_session.ws_connect(ws_url) as second_ws:
            with pytest.raises(asyncio.TimeoutError):
                await second_ws.receive_json(timeout=TIMEOUT)


async def test_multiple_clients_single_event_one_client_is_late(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """An event is raised and only connected clients receive the message."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as first_ws:
        step.raise_event()
        first_message = await first_ws.receive_json(timeout=5)
        assert first_message == message
        async with aiohttp_session.ws_connect(ws_url) as second_ws:
            with pytest.raises(asyncio.TimeoutError):
                await second_ws.receive_json(timeout=TIMEOUT)


@pytest.mark.parametrize("ws_url_with_stream_name", ["other-stream"], indirect=True)
async def test_multiple_events_multiple_clients(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    ws_url_with_stream_name: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """Multiple events are raised on multiple streams and the clients receive the right message."""
    step = function_project.project.steps.events_step
    first_message = {"message": "first_message"}

    step.message = first_message

    async with (
        aiohttp_session.ws_connect(ws_url) as first_ws,
        aiohttp_session.ws_connect(
            ws_url_with_stream_name,
        ) as second_ws,
    ):
        step.stream_name = stream_name
        step.raise_event()
        step.stream_name = "other-stream"
        step.raise_other_event()
        first_response = await first_ws.receive_json(timeout=5)
        assert first_response == first_message
        second_response = await second_ws.receive_json(timeout=5)
        assert second_response == {"message": "other event"}

        with pytest.raises(asyncio.TimeoutError):
            await first_ws.receive_json(timeout=TIMEOUT)


async def test_multiple_events_single_transaction(
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """Multiple events are raised on the same transaction and the messages are received in the right order."""
    step = function_project.project.steps.events_step
    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        step.raise_multiple_events()
        responses: list[dict[str, Any]] = [await websocket.receive_json(timeout=5) for _ in range(3)]
        assert responses == [{"message": 0}, {"message": 1}, {"message": 2}]


async def test_glow_restart_erases_events_queue(
    session_glow: GlowBaseProcess[EventsSolution],
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """If GLOW is restarted after an event is raised but before the client receives the message, then the
    message queue is empty."""
    step = function_project.project.steps.events_step
    message = {"message": "Hello event!"}
    step.message = message
    step.stream_name = stream_name

    step.raise_event()

    session_glow.restart()

    async with aiohttp_session.ws_connect(ws_url) as ws:
        with pytest.raises(asyncio.TimeoutError):
            await ws.receive_json(timeout=TIMEOUT)


async def test_glow_restart_closes_websockets(
    session_glow: GlowBaseProcess[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """If GLOW is restarted after websockets are connected, they are disconnected."""
    async with aiohttp_session.ws_connect(ws_url) as ws:
        session_glow.restart()
        response = await ws.receive()
        # Aiohttp handles the websocket close from the server,
        # and the message type is CLOSE (Linux) or CLOSED (Win)
        assert response.type in [WSMsgType.CLOSE, WSMsgType.CLOSED]
    if ws:
        await ws.close()


@pytest.mark.parametrize(
    "message",
    [
        "test",
        3,
        3.2,
        True,
        [3, "hello", False, 0.4, None],
        {"test": 3, "why": "byte"},
        (4.7, "ei"),
        {3, 4, 6},
        CustomField(x=7, y=8, z=9),
    ],
)
async def test_event_with_different_types(
    message: Any,
    function_project: ProjectFixture[EventsSolution],
    ws_url: str,
    aiohttp_session: aiohttp.ClientSession,
):
    """Test that raise_event handle basic python types."""
    step = function_project.project.steps.events_step
    step.message = message
    step.stream_name = stream_name

    async with aiohttp_session.ws_connect(ws_url) as ws:
        step.raise_event()
        received_message = await ws.receive_json(timeout=TIMEOUT)
        if isinstance(message, set):
            # sets, when jsonified, are converted to arrays and decoded back to lists
            assert list(message) == received_message  # type: ignore
            assert message == set(received_message)
        elif isinstance(message, tuple):
            # tuples, when jsonified, are converted to arrays and decoded back to lists
            assert list(message) == received_message  # type: ignore
            assert message == tuple(received_message)
        elif isinstance(message, CustomField):
            # custom types, when jsonified, are dumped and require to build the type again
            assert message.model_dump() == received_message
            assert message == CustomField.model_validate(received_message)
        else:
            assert message == received_message


async def test_completed_transaction_termination_event(
    function_project: ProjectFixture[EventsSolution],
    aiohttp_session: aiohttp.ClientSession,
):
    """The transaction termination event is raised in a successful transaction and the status is correct."""
    step = function_project.project.steps.events_step
    stream_name = "raise-termination-event"
    ws_url = (
        f"ws://{function_project.url.split('/')[2]}/events/{function_project.project_name}"
        f"/steps/{step_id}/streams/{stream_name}"
    )

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        step.raise_termination_event()
        response: dict[str, Any] = await websocket.receive_json(timeout=5)
        assert response["status"] == "completed"


async def test_completed_long_running_transaction_termination_event(
    function_project: ProjectFixture[EventsSolution],
    aiohttp_session: aiohttp.ClientSession,
):
    """The transaction termination event is raised in a successful long-running transaction
    and the status is correct."""
    step = function_project.project.steps.events_step
    stream_name = "raise-termination-event-long-running"
    ws_url = (
        f"ws://{function_project.url.split('/')[2]}/events/{function_project.project_name}"
        f"/steps/{step_id}/streams/{stream_name}"
    )

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        step.raise_termination_event_long_running().wait()
        response: dict[str, Any] = await websocket.receive_json(timeout=30)
        assert response["status"] == "completed"


async def test_failed_transaction_termination_event(
    session_glow: GlowBaseProcess[EventsSolution],
    function_project: ProjectFixture[EventsSolution],
    aiohttp_session: aiohttp.ClientSession,
):
    """The transaction termination event is raised in a failed transaction and the status is correct."""
    if session_glow.debug_mode_override:
        pytest.xfail("failing in debug, see #2342")
    step = function_project.project.steps.events_step
    stream_name = "raise-failed-termination-event"
    ws_url = (
        f"ws://{function_project.url.split('/')[2]}/events/{function_project.project_name}"
        f"/steps/{step_id}/streams/{stream_name}"
    )

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        with pytest.raises(InternalSolutionException, match=INTERNAL_ERROR_MESSAGE):
            step.raise_failed_termination_event()
        response: dict[str, Any] = await websocket.receive_json(timeout=5)
        assert response["status"] == "failed"


async def test_failed_long_running_transaction_termination_event(
    session_glow: GlowBaseProcess[EventsSolution],
    function_project: ProjectFixture[EventsSolution],
    aiohttp_session: aiohttp.ClientSession,
):
    """The transaction termination event is raised in a failed long-running transaction and the status is correct."""
    if session_glow.debug_mode_override:
        pytest.xfail("failing in debug, see #2342")
    step = function_project.project.steps.events_step
    stream_name = "raise-failed-termination-event-long-running"
    ws_url = (
        f"ws://{function_project.url.split('/')[2]}/events/{function_project.project_name}"
        f"/steps/{step_id}/streams/{stream_name}"
    )

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        with pytest.raises(InternalSolutionException, match=INTERNAL_ERROR_MESSAGE):
            step.raise_failed_termination_event_long_running().wait()
        response: dict[str, Any] = await websocket.receive_json(timeout=5)
        assert response["status"] == "failed"


async def test_no_transaction_termination_event(
    function_project: ProjectFixture[EventsSolution],
    aiohttp_session: aiohttp.ClientSession,
):
    """No transaction termination event is raised in a successful transaction and no event is received."""
    step = function_project.project.steps.events_step
    stream_name = "dont-raise-termination-event"
    ws_url = (
        f"ws://{function_project.url.split('/')[2]}/events/{function_project.project_name}"
        f"/steps/{step_id}/streams/{stream_name}"
    )

    async with aiohttp_session.ws_connect(ws_url) as websocket:
        step.dont_raise_termination_event()
        with pytest.raises(asyncio.exceptions.TimeoutError):
            await websocket.receive_json(timeout=1)


INTERNAL_ERROR_MESSAGE = "The solution encountered an internal error and was unable to complete the request. "


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowBaseProcess[EventsSolution]) -> Generator[None, None, None]:
    yield
    session_glow.configure_default_execution()


@pytest.fixture
def debug_mode(session_glow: GlowBaseProcess[EventsSolution], request: pytest.FixtureRequest) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param)


@pytest.mark.parametrize("debug_mode", [EnvVarDebug, DefaultDebug], indirect=True)
async def test_event_with_non_jsonable_message_raises_exception(
    function_project: ProjectFixture[EventsSolution],
    debug_mode: DebugConfiguration,
):
    """Test that raise_event fails if message is not jsonable"""
    step = function_project.project.steps.events_step
    step.stream_name = stream_name
    expected_error_message = (
        INTERNAL_ERROR_MESSAGE
        if isinstance(debug_mode, DefaultDebug)
        else "Object of type <class 'numpy.ndarray'> is not JSON serializable"
    )
    with pytest.raises(InternalSolutionException, match=expected_error_message):
        step.raise_invalid_event()
