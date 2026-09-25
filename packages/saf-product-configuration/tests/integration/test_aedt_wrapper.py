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

from fastapi.testclient import TestClient
import pytest
from pytest_mock import MockerFixture

from ansys.saf.product_configuration.wrappers.aedt import (
    DataModel,
    State,
    _run_service_manager,  # pyright: ignore[reportPrivateUsage]
    app,
)
from ansys.saf.product_configuration.wrappers.types import TransportMode


@pytest.fixture
def client() -> TestClient:
    DataModel.state = State()
    return TestClient(app)


def test_health(client: TestClient):
    # GIVEN: app running
    # WHEN: checking health
    response = client.get("/health")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    # THEN: returns 200 code and healthy message
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.text == '"healthy"'  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def test_start_service_manager_success(client: TestClient, mocker: MockerFixture):
    # GIVEN: app running with no service manager
    mocked_service_manager = mocker.patch("multiprocessing.Process")

    # WHEN: starting the service manager
    client.post("/start_service_manager").raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    response.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    state = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: service manager is launched with expected port and version
    mocked_service_manager.assert_called_once_with(
        target=_run_service_manager,
        args=["0.0.0.0", state["service_manager_port"], "261", TransportMode.INSECURE],
    )

    # WHEN: getting state
    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    response.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    state = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: service manager is running in expected port and 2 int ports are returned as candidates for rpyc and grpc
    assert state["service_manager_running"]
    assert not state["session_running"]
    assert isinstance(state["session_rpyc_port"], int)
    assert isinstance(state["session_grpc_port"], int)


def test_start_service_manager_failure_already_running(client: TestClient, mocker: MockerFixture):
    # GIVEN: app running with service manager
    mocked_service_manager = mocker.patch("multiprocessing.Process")

    client.post("/start_service_manager").raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # WHEN: starting the service manager
    response = client.post("/start_service_manager")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: service manager is not launched again
    assert response.status_code == 400  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json() == {"detail": "service manager already running"}  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    mocked_service_manager.assert_called_once()

    # WHEN: getting state
    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    response.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    state = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: service manager is running in expected port and 2 int ports are returned as candidates for rpyc and grpc
    assert state["service_manager_running"]
    assert not state["session_running"]
    assert isinstance(state["session_rpyc_port"], int)
    assert isinstance(state["session_grpc_port"], int)


def test_start_service_manager_failure_local_session(client: TestClient, mocker: MockerFixture):
    # GIVEN: app running with no service manager
    mocked_service_manager = mocker.patch("multiprocessing.Process")

    # WHEN: starting the service manager in a local transport mode
    mocker.patch("ansys.saf.product_configuration.wrappers.aedt._transport_mode", new=TransportMode.UDS)
    response = client.post("/start_service_manager")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: service manager is not launched again
    assert response.status_code == 400  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json() == {"detail": "remote session creation is not supported in UDS mode"}  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    mocked_service_manager.assert_not_called()


@pytest.mark.parametrize("session_running", [True, False])
def test_get_or_create_local_session_success(client: TestClient, mocker: MockerFixture, session_running: bool):
    mocked_desktop = mocker.patch("ansys.aedt.core.Desktop")

    # WHEN: calling get_or_create_local_session when no session is running
    response = client.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        "/get_or_create_local_session",
        json={"session_running": session_running, "session_grpc_port": 54321},
    )
    response.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: returns 200 and Desktop was launched with expected arguments
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    mocked_desktop.assert_called_once_with(
        version="261",
        non_graphical=True,
        new_desktop=not session_running,
        port=54321,
    )


def test_get_or_create_local_session_failure_mtls(client: TestClient, mocker: MockerFixture):
    # WHEN: calling get_or_create_local_session with MTLS transport mode
    mocker.patch("ansys.saf.product_configuration.wrappers.aedt._transport_mode", new=TransportMode.MTLS)
    response = client.post("/get_or_create_local_session", json={})  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: returns 400 with expected error
    assert response.status_code == 400  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json() == {"detail": "local session creation is not supported in MTLS mode"}  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def test_get_state_no_service_manager(client: TestClient):
    # GIVEN: app running with no service manager
    # WHEN: getting state
    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    response.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    state = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    # THEN: service manager is not running, session is not running, and service manager port is -1
    assert not state["service_manager_running"]
    assert not state["session_running"]
    assert state["service_manager_port"] == -1


def test_get_state_with_no_session_confirmation(client: TestClient):
    # WHEN: getting state
    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    response.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    state = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: 2 int ports are returned as candidates for rpyc and grpc
    rpyc_port = state["session_rpyc_port"]  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    grpc_port = state["session_grpc_port"]  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert isinstance(rpyc_port, int)
    assert isinstance(grpc_port, int)

    # WHEN: getting state again
    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    response.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    state = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: two different ports are returned as candidates for rpyc and grpc
    new_rpyc_port = state["session_rpyc_port"]  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    new_grpc_port = state["session_grpc_port"]  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert isinstance(new_rpyc_port, int)
    assert isinstance(new_grpc_port, int)
    assert new_rpyc_port != rpyc_port
    assert new_grpc_port != grpc_port


def test_get_state_with_confirmed_session(client: TestClient):
    # WHEN: confirming session running and getting state
    client.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        "/confirm_session_running",
        json={"session_rpyc_port": 12345, "session_grpc_port": 54321},
    ).raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # THEN: session is running and ports are the expected ones
    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json()["session_running"] is True  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json()["session_rpyc_port"] == 12345  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json()["session_grpc_port"] == 54321  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # WHEN: getting state again
    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    # THEN: ports haven't changed
    assert response.json()["session_running"] is True  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json()["session_rpyc_port"] == 12345  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json()["session_grpc_port"] == 54321  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def test_confirm_session_running_failure_already_running(client: TestClient, mocker: MockerFixture):
    # GIVEN: app running with service manager and session confirmed
    mocked_service_manager = mocker.patch("multiprocessing.Process")
    client.post("/start_service_manager").raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    client.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        "/confirm_session_running",
        json={"session_rpyc_port": 12345, "session_grpc_port": 54321},
    ).raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    mocked_service_manager.assert_called_once()

    # WHEN: trying to confirm session again
    response = client.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        "/confirm_session_running",
        json={"session_rpyc_port": 67890, "session_grpc_port": 9876},
    )

    # THEN: fails to do it
    assert response.status_code == 400  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json() == {"detail": "session already running"}  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    # WHEN: getting state
    response = client.get("/")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    # THEN: ports haven't changed from first confirmation
    assert response.json()["session_running"] is True  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json()["session_rpyc_port"] == 12345  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json()["session_grpc_port"] == 54321  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
