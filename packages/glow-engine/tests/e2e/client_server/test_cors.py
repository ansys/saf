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

from collections.abc import Generator

import httpx2
import pytest

from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, GlowDesktopProcess
from tests.mocks.solutions.minimal_solution import MinimalSolution

pytestmark = pytest.mark.parametrize("solution_type", [MinimalSolution], indirect=True)


def test_server_without_cors_configuration_fails_cors_protocol(
    session_glow: GlowBaseProcess[MinimalSolution],
):
    url = f"{session_glow.base_api_url}/health"
    origin = "http://example.com"

    response = httpx2.options(url, headers={"Origin": origin, "Access-Control-Request-Method": "GET"})

    assert response.status_code == 400
    assert response.text == "Disallowed CORS origin"


@pytest.fixture
def origin(session_glow: GlowBaseProcess[MinimalSolution]) -> Generator[str, None, None]:
    if not isinstance(session_glow, GlowDesktopProcess):
        raise RuntimeError("Wrong deployment.")
    session_glow._solution_api_args = ["--cors-origin", "http://example.com"]  # type: ignore
    session_glow.restart()
    yield "http://example.com"
    session_glow._solution_api_args = []  # type: ignore


def test_server_with_cors_configuration_passes_cors_protocol(
    session_glow: GlowBaseProcess[MinimalSolution],
    origin: str,
):
    url = f"{session_glow.base_api_url}/health"
    assert origin

    response = httpx2.options(url, headers={"Origin": origin, "Access-Control-Request-Method": "GET"})

    assert response.text == "OK"
    assert response.status_code == 200

    response = httpx2.get(url, headers={"Origin": origin})

    assert response.text == '"The GLOW API server is healthy."'
    assert response.status_code == 200
