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
import re
from typing import Any

from fastmcp import Client as MCPClient
from fastmcp.client.transports import SSETransport, StreamableHttpTransport
from fastmcp.exceptions import ToolError
import pytest

from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.e2e.conftest import (
    CustomPathMCPConfiguration,
    DisableMCPConfiguration,
    EnableMCPConfiguration,
    EnableMCPWithAuthConfiguration,
    SSETransportMCPConfiguration,
)
from tests.mcp_expectations import (
    LONG_RUNNING_DESCRIPTION_SUFFIX,
    NONEXISTENT_PROJECT_CASES,
    NONEXISTENT_STEP_CASES,
    STATIC_TOOL_DESCRIPTIONS,
    STATIC_TOOL_PARAMETER_DESCRIPTIONS,
    SYNC_DESCRIPTION_SUFFIX,
    TRANSACTION_TOOL_DESCRIPTIONS,
    TRANSACTION_TOOL_PARAMETER_DESCRIPTIONS,
    parameter_descriptions,
    transaction_tool_names,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


@pytest.fixture
def change_mcp_configuration(
    enable_mcp_server: list[str],
    request: pytest.FixtureRequest,
    session_glow: GlowBaseProcess[EndToEndSolution],
) -> YieldFixture[list[str]]:
    session_glow.change_configuration(request.param)
    yield list(session_glow.api_output)
    session_glow.change_configuration(EnableMCPConfiguration)


@pytest.mark.usefixtures("enable_mcp_server")
class TestMCPServer:
    def test_mcp_server_is_served(self, enable_mcp_server: list[str]):
        assert any("MCP mounted at path /sse" in line for line in enable_mcp_server)

    @pytest.mark.parametrize("change_mcp_configuration", [DisableMCPConfiguration], indirect=True)
    def test_mcp_server_is_disabled(self, change_mcp_configuration: list[str]):
        assert not any("MCP mounted" in line for line in change_mcp_configuration)

    @pytest.mark.parametrize("change_mcp_configuration", [EnableMCPWithAuthConfiguration], indirect=True)
    def test_mcp_server_is_disabled_when_auth_is_enabled(self, change_mcp_configuration: list[str]):
        assert any(
            "MCP not mounted: authentication is enabled and not supported" in line for line in change_mcp_configuration
        )

    async def test_mcp_server_is_responsive(self, mcp_client: MCPClient[StreamableHttpTransport]):
        healthy = await mcp_client.ping()
        assert healthy

    async def test_mcp_server_name_is_solution_display_name(self, mcp_client: MCPClient[StreamableHttpTransport]):
        assert mcp_client.initialize_result is not None
        assert mcp_client.initialize_result.serverInfo.name == EndToEndSolution.model_construct().display_name

    async def test_mcp_server_instructions_is_set(self, mcp_client: MCPClient[StreamableHttpTransport]):
        assert mcp_client.initialize_result is not None
        assert mcp_client.initialize_result.instructions == "Instructions for using the solution End-to-end solution."

    @pytest.mark.usefixtures("add_solution_md_file")
    @pytest.mark.parametrize("add_solution_md_file", ["## Instructions\nmy-custom-instructions"], indirect=True)
    async def test_mcp_server_instructions_can_be_customized(self, mcp_client: MCPClient[StreamableHttpTransport]):
        assert mcp_client.initialize_result is not None
        assert mcp_client.initialize_result.instructions == "my-custom-instructions"

    @pytest.mark.parametrize("change_mcp_configuration", [CustomPathMCPConfiguration], indirect=True)
    async def test_mcp_server_is_served_with_custom_path(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        change_mcp_configuration: list[str],
    ):
        assert any("MCP mounted at path /custom-mcp-path" in line for line in change_mcp_configuration)
        transport = StreamableHttpTransport(url=f"{session_glow.base_api_url}/custom-mcp-path")
        async with MCPClient(transport=transport) as mcp_client:
            healthy = await mcp_client.ping()
            assert healthy

    @pytest.mark.parametrize("change_mcp_configuration", [SSETransportMCPConfiguration], indirect=True)
    async def test_mcp_server_is_served_with_other_transport_mode(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        change_mcp_configuration: list[str],
    ):
        assert any("MCP mounted at path /sse" in line for line in change_mcp_configuration)
        transport = SSETransport(url=f"{session_glow.base_api_url}/sse")
        async with MCPClient(transport=transport) as mcp_client:
            healthy = await mcp_client.ping()
            assert healthy

    async def test_mcp_server_has_expected_resources(self, mcp_client: MCPClient[StreamableHttpTransport]):
        resources = await mcp_client.list_resources()
        assert not resources

    async def test_mcp_server_has_expected_tools(self, mcp_client: MCPClient[StreamableHttpTransport]):
        tools = await mcp_client.list_tools()
        descriptions = {tool.name: tool.description for tool in tools}

        transaction_tools = transaction_tool_names()
        assert transaction_tools
        assert set(descriptions) == set(STATIC_TOOL_DESCRIPTIONS) | set(transaction_tools)

        assert {name: descriptions[name] for name in STATIC_TOOL_DESCRIPTIONS} == STATIC_TOOL_DESCRIPTIONS

        for tool_name, is_long_running in transaction_tools.items():
            description = descriptions[tool_name]
            assert description is not None
            expected_suffix = LONG_RUNNING_DESCRIPTION_SUFFIX if is_long_running else SYNC_DESCRIPTION_SUFFIX
            assert description.endswith(expected_suffix)
            assert description.removesuffix(expected_suffix).strip()

    async def test_mcp_server_tool_parameters_have_descriptions(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
    ):
        tools = {tool.name: tool for tool in await mcp_client.list_tools()}

        for tool_name, expected_descriptions in STATIC_TOOL_PARAMETER_DESCRIPTIONS.items():
            assert parameter_descriptions(tools[tool_name].inputSchema) == expected_descriptions

    async def test_mcp_server_transaction_tools_have_descriptions(self, mcp_client: MCPClient[StreamableHttpTransport]):
        tools = await mcp_client.list_tools()

        descriptions = {tool.name: tool.description for tool in tools}
        assert {name: descriptions[name] for name in TRANSACTION_TOOL_DESCRIPTIONS} == TRANSACTION_TOOL_DESCRIPTIONS

    async def test_mcp_server_transaction_tool_parameters_have_descriptions(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
    ):
        tools = {tool.name: tool for tool in await mcp_client.list_tools()}

        project_name_description = {"project_name": TRANSACTION_TOOL_PARAMETER_DESCRIPTIONS["project_name"]}
        cases = [
            # sync transactions
            ("transaction_verification_step__get_field_1_and_2_and_set_the_sum_in_result", project_name_description),
            ("custom_http_shared_instance_step__retrieve_value_custom_http_product_instance", project_name_description),
            (
                "transaction_verification_step__sum_two_floats_with_inputs_and_output",
                TRANSACTION_TOOL_PARAMETER_DESCRIPTIONS,
            ),
            ("transaction_verification_step__use_solution_configuration", project_name_description),
            # long-running transactions
            ("transaction_verification_step__lr_get_field_1_and_2_and_set_the_sum_in_result", project_name_description),
            (
                "custom_http_shared_instance_step__retrieve_value_custom_http_product_instance_long_running",
                project_name_description,
            ),
            (
                "transaction_verification_step__lr_sum_two_floats_with_inputs_and_output",
                TRANSACTION_TOOL_PARAMETER_DESCRIPTIONS,
            ),
            ("transaction_verification_step__lr_use_solution_configuration", project_name_description),
        ]

        for tool_name, expected_descriptions in cases:
            assert parameter_descriptions(tools[tool_name].inputSchema) == expected_descriptions

    async def test_mcp_server_has_expected_prompts(self, mcp_client: MCPClient[StreamableHttpTransport]):
        prompts = await mcp_client.list_prompts()
        assert not prompts

    @pytest.mark.parametrize(("tool_name", "extra_args"), NONEXISTENT_STEP_CASES)
    async def test_tools_raise_on_nonexistent_step(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
        tool_name: str,
        extra_args: dict[str, Any],
    ):
        call_args = {"project_name": function_project.project_name, "step_name": "nonexistent_step", **extra_args}
        with pytest.raises(ToolError, match=re.escape("Step 'nonexistent_step' not found.")):
            await mcp_client.call_tool(tool_name, call_args)

    @pytest.mark.parametrize(("tool_name", "extra_args"), NONEXISTENT_PROJECT_CASES)
    async def test_tools_raise_on_nonexistent_project(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        tool_name: str,
        extra_args: dict[str, Any],
    ):
        with pytest.raises(ToolError) as exc_info:
            await mcp_client.call_tool(tool_name, {"project_name": "nonexistent_project", **extra_args})
        assert "not found" in str(exc_info.value).lower()
