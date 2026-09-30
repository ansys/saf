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
import pytest_mock

from ansys.saf.desktop.orchestrator._config.schema import GLOW_API_HOST, GLOW_API_PORT, PORTAL_UI_HOST, PORTAL_UI_PORT
from ansys.saf.desktop.orchestrator._orchestration.streamlit_client import StreamlitClient
from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import Solution


class DummySolution(Solution):
    pass


@pytest.fixture
def mock_client(mocker: pytest_mock.MockerFixture):
    mocked_client = mocker.patch("ansys.saf.glow.client.Client")
    return mocked_client


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_API_HOST, "mock_api_host")
    monkeypatch.setenv(GLOW_API_PORT, "1234")
    monkeypatch.setenv(PORTAL_UI_HOST, "mock_portal_host")
    monkeypatch.setenv(PORTAL_UI_PORT, "5678")


@pytest.mark.usefixtures("mock_client", "mock_env_vars")
def test_initialize():
    # Initialize StreamlitClient
    StreamlitClient.initialize(DummySolution)  # type: ignore
    # Check if the singleton is correctly initialized
    assert StreamlitClient._singleton is not None  # type: ignore
    assert isinstance(StreamlitClient._singleton, Client)  # type: ignore


@pytest.mark.usefixtures("mock_client", "mock_env_vars")
def test_get_project():
    StreamlitClient.initialize(DummySolution)  # type: ignore
    result = StreamlitClient.get_project("/test/path")  # type: ignore
    assert result.__class__.__name__ == "ProjectProxy"  # type: ignore


@pytest.mark.usefixtures("mock_env_vars")
def test_get_portal_ui_url():
    assert StreamlitClient.get_portal_ui_url() == "http://mock_portal_host:5678"
