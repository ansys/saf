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
from collections.abc import AsyncGenerator
from typing import Any

from fastmcp import Client as MCPClient
from fastmcp.client.client import CallToolResult
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import TextContent
import pytest

from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess
from tests.e2e.conftest import EnableMCPConfiguration
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution


@pytest.fixture(scope="class")
def enable_mcp_server(session_glow: GlowBaseProcess[EndToEndSolution]) -> YieldFixture[list[str]]:
    session_glow.change_configuration(EnableMCPConfiguration)
    yield list(session_glow.api_output)
    session_glow.configure_default_execution()


@pytest.fixture
async def mcp_client(
    enable_mcp_server: list[str],
    session_glow: GlowBaseProcess[EndToEndSolution],
) -> AsyncGenerator[MCPClient[StreamableHttpTransport], None]:
    transport = StreamableHttpTransport(url=f"{session_glow.base_api_url}/sse")
    async with MCPClient(transport=transport) as client:
        yield client


@pytest.fixture
def add_solution_md_file(
    session_glow: GlowBaseProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> YieldFixture[None]:
    solution_md_file = session_glow.solution_dir / "solution" / "SOLUTION.md"
    content = getattr(request, "param", "")
    solution_md_file.write_text(content)
    session_glow.restart()
    yield
    solution_md_file.unlink(missing_ok=True)
    session_glow.restart()


def assert_no_mcp_response(result: CallToolResult):
    # tools with a `None` return type now have an output schema, so FastMCP reports a null-wrapped result.
    assert result.structured_content in (None, {"result": None})
    assert len(result.content) == 0


def assert_mcp_response(
    result: CallToolResult,
    expected_text: str,
    has_structure_content: bool = False,
    structured_result: Any | None = None,
):
    if not has_structure_content:
        assert result.structured_content is None
    else:
        assert isinstance(result.structured_content, dict)
        assert result.structured_content.get("result") == (structured_result or expected_text)
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text == expected_text
