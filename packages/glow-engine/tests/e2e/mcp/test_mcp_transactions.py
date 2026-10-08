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
from fastmcp import Client as MCPClient
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.e2e.mcp.conftest import assert_mcp_response, assert_no_mcp_response
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import TransactionVerificationStep

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


@retry(stop=stop_after_attempt(100), wait=wait_fixed(0.5))
def _wait_for_method_status(step: TransactionVerificationStep, method_name: str, status: MethodStatus) -> bool:
    if step.get_method_state(method_name).status != status:
        raise TryAgain
    return True


@pytest.mark.usefixtures("enable_mcp_server")
class TestMCPTransactions:
    async def test_wait_for_longrunning_transaction_tool(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        step.field_1 = 2
        step.field_2 = 3
        assert (
            step.get_long_running_method_state("lr_get_field_1_and_2_and_set_the_sum_in_result").status
            == MethodStatus.RunRequired
        )
        step.lr_get_field_1_and_2_and_set_the_sum_in_result()
        assert (
            step.get_long_running_method_state("lr_get_field_1_and_2_and_set_the_sum_in_result").status
            == MethodStatus.Running
        )

        result = await mcp_client.call_tool(
            "wait_for_longrunning_transaction",
            {
                "project_name": function_project.project_name,
                "step_name": "transaction_verification_step",
                "transaction_name": "lr_get_field_1_and_2_and_set_the_sum_in_result",
            },
        )
        assert_no_mcp_response(result)

        assert (
            step.get_long_running_method_state("lr_get_field_1_and_2_and_set_the_sum_in_result").status
            == MethodStatus.Completed
        )
        assert step.result == 5

    async def test_wait_for_longrunning_transaction_tool_with_return_value(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        assert (
            step.get_long_running_method_state("lr_sum_two_floats_with_inputs_and_output").status
            == MethodStatus.RunRequired
        )
        step.lr_sum_two_floats_with_inputs_and_output(field_1=2, field_2=3)
        assert (
            step.get_long_running_method_state("lr_sum_two_floats_with_inputs_and_output").status
            == MethodStatus.Running
        )

        result = await mcp_client.call_tool(
            "wait_for_longrunning_transaction",
            {
                "project_name": function_project.project_name,
                "step_name": "transaction_verification_step",
                "transaction_name": "lr_sum_two_floats_with_inputs_and_output",
            },
        )
        assert_mcp_response(result, "5.0", has_structure_content=True, structured_result=5.0)
        assert (
            step.get_long_running_method_state("lr_sum_two_floats_with_inputs_and_output").status
            == MethodStatus.Completed
        )

    async def test_wait_for_longrunning_transaction_tool_with_timeout(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        method = step.lr_get_field_1_and_2_and_set_the_sum_in_result()
        assert (
            step.get_long_running_method_state("lr_get_field_1_and_2_and_set_the_sum_in_result").status
            == MethodStatus.Running
        )

        with pytest.raises(ToolError, match="timed out"):
            await mcp_client.call_tool(
                "wait_for_longrunning_transaction",
                {
                    "project_name": function_project.project_name,
                    "step_name": "transaction_verification_step",
                    "transaction_name": "lr_get_field_1_and_2_and_set_the_sum_in_result",
                    "timeout": 1,
                },
            )
        assert (
            step.get_long_running_method_state("lr_get_field_1_and_2_and_set_the_sum_in_result").status
            == MethodStatus.Running
        )
        method.wait()
        assert (
            step.get_long_running_method_state("lr_get_field_1_and_2_and_set_the_sum_in_result").status
            == MethodStatus.Completed
        )

    async def test_wait_for_longrunning_transaction_tool_with_sync_transaction(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        with pytest.raises(ToolError, match="is not a long-running transaction"):
            await mcp_client.call_tool(
                "wait_for_longrunning_transaction",
                {
                    "project_name": function_project.project_name,
                    "step_name": "transaction_verification_step",
                    "transaction_name": "get_field_1_and_2_and_set_the_sum_in_result",
                },
            )

    async def test_wait_for_longrunning_transaction_tool_that_fails(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        step.lr_raise_exception()
        assert step.get_long_running_method_state("lr_raise_exception").status == MethodStatus.Running

        with pytest.raises(ToolError, match="The solution encountered an internal error"):
            await mcp_client.call_tool(
                "wait_for_longrunning_transaction",
                {
                    "project_name": function_project.project_name,
                    "step_name": "transaction_verification_step",
                    "transaction_name": "lr_raise_exception",
                },
            )
        assert step.get_long_running_method_state("lr_raise_exception").status == MethodStatus.Failed

    async def test_wait_for_longrunning_transaction_tool_with_not_started_transaction(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        with pytest.raises(ToolError, match="has not been started"):
            await mcp_client.call_tool(
                "wait_for_longrunning_transaction",
                {
                    "project_name": function_project.project_name,
                    "step_name": "transaction_verification_step",
                    "transaction_name": "lr_get_field_1_and_2_and_set_the_sum_in_result",
                },
            )

    async def test_wait_for_longrunning_transaction_tool_with_non_existent_transaction(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        with pytest.raises(ToolError, match="is not a long-running transaction"):
            await mcp_client.call_tool(
                "wait_for_longrunning_transaction",
                {
                    "project_name": function_project.project_name,
                    "step_name": "transaction_verification_step",
                    "transaction_name": "my_non_existent_transaction",
                },
            )

    async def test_sync_transaction_tool(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        assert step.get_method_state("get_field_1_and_2_and_set_the_sum_in_result").status == MethodStatus.RunRequired
        step.field_1 = 2
        step.field_2 = 3

        result = await mcp_client.call_tool(
            "transaction_verification_step__get_field_1_and_2_and_set_the_sum_in_result",
            {
                "project_name": function_project.project_name,
            },
        )
        assert_no_mcp_response(result)
        assert step.result == 5
        assert step.get_method_state("get_field_1_and_2_and_set_the_sum_in_result").status == MethodStatus.Completed

    async def test_sync_transaction_tool_that_fails(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        assert step.get_method_state("raise_exception").status == MethodStatus.RunRequired

        with pytest.raises(ToolError, match="The solution encountered an internal error"):
            await mcp_client.call_tool(
                "transaction_verification_step__raise_exception",
                {
                    "project_name": function_project.project_name,
                },
            )

    async def test_sync_transaction_tool_with_custom_args_and_return_value(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        assert step.get_method_state("sum_two_floats_with_inputs_and_output").status == MethodStatus.RunRequired

        result = await mcp_client.call_tool(
            "transaction_verification_step__sum_two_floats_with_inputs_and_output",
            {
                "project_name": function_project.project_name,
                "field_1": 2,
                "field_2": 3,
            },
        )
        assert_mcp_response(result, "5.0", has_structure_content=True, structured_result=5.0)
        assert step.get_method_state("sum_two_floats_with_inputs_and_output").status == MethodStatus.Completed

    async def test_longrunning_transaction_tool(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        assert (
            step.get_method_state("lr_get_field_1_and_2_and_set_the_sum_in_result").status == MethodStatus.RunRequired
        )
        step.field_1 = 2
        step.field_2 = 3

        result = await mcp_client.call_tool(
            "transaction_verification_step__lr_get_field_1_and_2_and_set_the_sum_in_result",
            {
                "project_name": function_project.project_name,
            },
        )
        assert_no_mcp_response(result)
        assert step.get_method_state("lr_get_field_1_and_2_and_set_the_sum_in_result").status == MethodStatus.Running

        _wait_for_method_status(step, "lr_get_field_1_and_2_and_set_the_sum_in_result", MethodStatus.Completed)
        assert step.result == 5

    async def test_longrunning_transaction_tool_with_custom_args_and_return_value(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        assert step.get_method_state("lr_sum_two_floats_with_inputs_and_output").status == MethodStatus.RunRequired

        result = await mcp_client.call_tool(
            "transaction_verification_step__lr_sum_two_floats_with_inputs_and_output",
            {
                "project_name": function_project.project_name,
                "field_1": 2,
                "field_2": 3,
            },
        )
        assert_no_mcp_response(result)
        assert step.get_method_state("lr_sum_two_floats_with_inputs_and_output").status == MethodStatus.Running

        # don't know how to retrieve value using GLOW Client.
        result = await mcp_client.call_tool(
            "wait_for_longrunning_transaction",
            {
                "project_name": function_project.project_name,
                "step_name": "transaction_verification_step",
                "transaction_name": "lr_sum_two_floats_with_inputs_and_output",
            },
        )
        assert_mcp_response(result, "5.0", has_structure_content=True, structured_result=5.0)
