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
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING
from unittest import mock
import uuid

import httpx2
import pytest
from pytest_mock.plugin import MockerFixture

from ansys.iam.oidc import DEFAULT_SUBPROTOCOL_PREFIX, encode_base64_token
from ansys.saf.glow._client.step_proxy import StepProxy
from ansys.saf.glow._config.const import Deployment
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow.client import DashClient
from tests.mocks.solution_with_ui.solution.definition import MyStep
from tests.mocks.solutions.minimal_solution import MinimalSolution
from tests.unit.conftest import build_mock_dash_app

if TYPE_CHECKING:
    from flask import Flask

VALID_API_URLS = [
    "http://127.0.0.1:5432",
    "http://127.0.0.1:5432/my_application",
    "http://127.0.0.1:5432/my_application/",
    "https://127.0.0.1:5432",
]
VALID_WS_ENDPOINT_ADDRS = [
    "ws://127.0.0.1:5432",
    "ws://127.0.0.1:5432/my_application",
    "ws://127.0.0.1:5432/my_application/",
    "wss://127.0.0.1:5432",
]


@pytest.fixture(autouse=True)
def clean_env():
    # Tests here instantiate the GLOW Dash/Client, which internally modifies the sys.path/sys.modules and
    # sets environment variables such as GLOW_DEPLOYMENT, _API_URL... Clean it up between tests
    old_paths = sys.path.copy()
    with mock.patch.dict(os.environ, os.environ.copy()):
        yield
    sys.path = old_paths


@pytest.fixture
def mock_step_proxy() -> Callable[[str], StepProxy]:
    def _get_step_proxy(step_name: str) -> StepProxy:
        return StepProxy(
            os.environ["GLOW_API_URL"] + "/projects/my_project_id",
            os.environ["GLOW_EXTERNAL_API_URL"] + "/projects/my_project_id",
            step_name,
            MyStep,
            httpx2.Client(),
            Path.cwd(),
            GqlClientConnectionPool(url=f"{os.environ['GLOW_API_URL']}/graphql"),
        )

    return _get_step_proxy


def test_get_portal_ui_url_returns_none_if_glow_portal_url_is_not_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    if "GLOW_PORTAL_URL" in os.environ:
        monkeypatch.delenv("GLOW_PORTAL_URL")
    assert DashClient.get_portal_ui_url() is None


def test_get_portal_ui_url_returns_url_if_glow_portal_url_is_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    url = "http://portal.this-computer.on-my-domain.com:12345"
    monkeypatch.setenv("GLOW_PORTAL_URL", url)
    assert DashClient.get_portal_ui_url() == url


def test_get_deployment_type_returns_desktop_if_glow_deployment_is_not_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    if "GLOW_DEPLOYMENT" in os.environ:
        monkeypatch.delenv("GLOW_DEPLOYMENT")
    assert DashClient.get_deployment_type() == Deployment.Desktop


@pytest.mark.parametrize(
    ("deployment_string", "deployment_value"),
    [
        ("Desktop", Deployment.Desktop),
        ("DockerCompose", Deployment.DockerCompose),
    ],
)
def test_get_deployment_type_returns_deployment_if_glow_deployment_is_set(
    monkeypatch: pytest.MonkeyPatch,
    deployment_string: str,
    deployment_value: Deployment,
):
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    monkeypatch.setenv("GLOW_DEPLOYMENT", deployment_string)
    assert DashClient.get_deployment_type() == deployment_value


def test_get_deployment_type_raises_exception_if_glow_deployment_is_incorrectly_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    monkeypatch.setenv("GLOW_DEPLOYMENT", "JUNK")
    with pytest.raises(ValueError, match="'JUNK' is not a valid Deployment"):
        DashClient.get_deployment_type()


def test_create_event_listener(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    mock_step_proxy: Callable[[str], StepProxy],
):
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_WS_EVENTS_ADDR", "ws://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    step_name = "minimal-step"
    stream_name = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    p = mocker.patch("dash_extensions.WebSocket")
    DashClient[MinimalSolution].create_event_listener(mock_step_proxy(step_name), stream_name, ws_id)  # type: ignore
    expected_url = (
        f"{os.environ['GLOW_API_URL'].replace('http', 'ws')}/"
        f"events/projects/my_project_id/steps/{step_name}/streams/{stream_name}"
    )
    p.assert_called_once_with(url=expected_url, id=ws_id)


def test_create_event_listener_glow_ws_event_addr_without_prefix(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    mock_step_proxy: Callable[[str], StepProxy],
):
    """Test backward compatibilities when GLOW_WS_EVENT_ADDR was not containing ws:// prefix"""
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_WS_EVENTS_ADDR", "127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    step_name = "minimal-step"
    stream_name = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    p = mocker.patch("dash_extensions.WebSocket")
    DashClient[MinimalSolution].create_event_listener(mock_step_proxy(step_name), stream_name, ws_id)  # type: ignore
    expected_url = (
        f"{os.environ['GLOW_API_URL'].replace('http', 'ws')}/"
        f"events/projects/my_project_id/steps/{step_name}/streams/{stream_name}"
    )
    p.assert_called_once_with(url=expected_url, id=ws_id)


@pytest.mark.parametrize(("api_url", "ws_events_addr"), zip(VALID_API_URLS, VALID_WS_ENDPOINT_ADDRS, strict=True))
def test_create_event_listener_api_urls(
    api_url: str,
    ws_events_addr: str,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    mock_step_proxy: Callable[[str], StepProxy],
):
    monkeypatch.setenv("GLOW_API_URL", api_url)
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", api_url)
    monkeypatch.setenv("GLOW_WS_EVENTS_ADDR", ws_events_addr)
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    step_name = "minimal-step"
    stream_name = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    p = mocker.patch("dash_extensions.WebSocket")
    DashClient[MinimalSolution].create_event_listener(mock_step_proxy(step_name), stream_name, ws_id)  # type: ignore
    expected_url = (
        f"{os.environ['GLOW_WS_EVENTS_ADDR']}/events/projects/my_project_id/steps/{step_name}/streams/{stream_name}"
    )
    p.assert_called_once_with(url=expected_url, id=ws_id)


def test_create_event_listener_without_env_var_raises_exception(
    monkeypatch: pytest.MonkeyPatch,
    mock_step_proxy: Callable[[str], StepProxy],
):
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solutions.minimal_solution")
    step_name = "minimal-step"
    stream_name = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    with pytest.raises(
        RuntimeError,
        match="The GLOW_WS_EVENTS_ADDR environment variable must be configured to use websockets on the UI.",
    ):
        DashClient[MinimalSolution].create_event_listener(mock_step_proxy(step_name), stream_name, ws_id)  # type: ignore


def test_bearer_token_injected_into_websocket(
    monkeypatch: pytest.MonkeyPatch,
    mock_step_proxy: Callable[[str], StepProxy],
):
    ui_app = build_mock_dash_app(monkeypatch)
    flask_app: Flask = ui_app.server  # type: ignore

    step = mock_step_proxy("minimal-step")
    with flask_app.test_request_context("/"):
        # Do a request within a request context that doesn't have headers
        websocket = DashClient.create_event_listener(step, "my_stream", "ws_id")  # type: ignore
        assert not hasattr(websocket, "protocols")  # type: ignore

    with flask_app.test_request_context("/", headers={"Authorization": "wrong auth content"}):
        # Do a request within a request context that has invalid auth header
        websocket = DashClient.create_event_listener(step, "my_stream", "ws_id")  # type: ignore
        assert not hasattr(websocket, "protocols")  # type: ignore

    with flask_app.test_request_context("/", headers={"Authorization": "Bearer XXXXX"}):
        # Do a request within a request context that has auth header
        websocket = DashClient.create_event_listener(step, "my_stream", "ws_id")  # type: ignore
        assert websocket.protocols == [f"{DEFAULT_SUBPROTOCOL_PREFIX}{encode_base64_token('XXXXX')}"]  # type: ignore
