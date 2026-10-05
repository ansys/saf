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

from ansys.saf.testing.solution.end_to_end import ProjectFixture
from fastmcp import Client as MCPClient
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
import pytest

from tests.e2e.mcp.conftest import assert_mcp_response, assert_no_mcp_response
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    CustomTypeWithEntityHandle,
    CustomTypeWithEntityHandleCollections,
)

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)

# Field paths exercising an entity handle directly on a step field, nested in a list, dict, or custom object, nested
# two levels deep (list of lists / dict of dicts), and combined together in a single custom object.
ENTITY_HANDLE_FIELD_PATHS: dict[str, str] = {
    "entity_handle": "text_file",
    "list": "entity_handle_list/0",
    "dict": "entity_handle_dict/key1",
    "custom_object": "entity_handle_object/file",
    "nested_list": "nested_entity_handle_list/0/0",
    "nested_dict": "nested_entity_handle_dict/key1/key2",
    "combination_list_item": "entity_handle_collections/files/0",
    "combination_dict_item": "entity_handle_collections/file_map/key1",
    "combination_nested_object": "entity_handle_collections/nested/file",
}

# Field paths that resolve to a value that exists but is not an entity handle.
NON_ENTITY_HANDLE_FIELD_PATHS: dict[str, str] = {
    "entity_handle": "field_1",
    "custom_object": "entity_handle_object/label",
    "combination_nested_object": "entity_handle_collections/nested/label",
}

# Field paths whose final segment does not exist, paired with a substring of the expected error message.
MISSING_PATH_FIELD_PATHS: dict[str, tuple[str, str]] = {
    "entity_handle": ("text_file/extra", "does not exist on"),
    "list": ("entity_handle_list/5", "List index '5' does not exist."),
    "dict": ("entity_handle_dict/missing_key", "Dictionary key 'missing_key' does not exist."),
    "custom_object": ("entity_handle_object/missing_attr", "does not exist on"),
    "nested_list": ("nested_entity_handle_list/0/5", "List index '5' does not exist."),
    "nested_dict": ("nested_entity_handle_dict/key1/missing_key2", "Dictionary key 'missing_key2' does not exist."),
    "combination_list_item": ("entity_handle_collections/files/5", "List index '5' does not exist."),
    "combination_dict_item": (
        "entity_handle_collections/file_map/missing_key",
        "Dictionary key 'missing_key' does not exist.",
    ),
    "combination_nested_object": ("entity_handle_collections/nested/missing_attr", "does not exist on"),
}


def _initialize_entity_handle_fields(step: Any, storage_scope: Any) -> None:
    """Populate every container field with a placeholder entity handle so paths into them can be resolved."""
    placeholder = storage_scope.store_stream(b"placeholder")
    step.text_file = placeholder
    step.entity_handle_list = [placeholder]
    step.entity_handle_dict = {"key1": placeholder}
    step.entity_handle_object = CustomTypeWithEntityHandle(file=placeholder)
    step.nested_entity_handle_list = [[placeholder]]
    step.nested_entity_handle_dict = {"key1": {"key2": placeholder}}
    step.entity_handle_collections = CustomTypeWithEntityHandleCollections(
        files=[placeholder],
        file_map={"key1": placeholder},
        nested=CustomTypeWithEntityHandle(file=placeholder),
    )


@pytest.mark.usefixtures("enable_mcp_server")
class TestMCPDataManagement:
    async def test_set_fields_tool(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        fields: dict[str, Any] = {
            "field_1": 3.5,
            "sleepy_seconds": 2,
            "text_content": "updated-through-mcp",
            "child_process_is_running": True,
        }
        for field_name, value in fields.items():
            assert getattr(step, field_name) != value

        result = await mcp_client.call_tool(
            "set_fields",
            {
                "project_name": function_project.project_name,
                "step_name": "transaction_verification_step",
                "fields": fields,
            },
        )
        assert_no_mcp_response(result)

        for field_name, value in fields.items():
            assert getattr(step, field_name) == value

    async def test_get_fields_tool(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        step = function_project.project.steps.transaction_verification_step
        fields: dict[str, Any] = {
            "field_1": 4.5,
            "sleepy_seconds": 11,
            "text_content": "read-through-mcp",
            "child_process_is_running": True,
        }
        for field_name, value in fields.items():
            setattr(step, field_name, value)

        result = await mcp_client.call_tool(
            "get_fields",
            {
                "project_name": function_project.project_name,
                "step_name": "transaction_verification_step",
                "field_names": list(fields),
            },
        )
        assert result.structured_content == {**fields, "sleepy_seconds": 11.0}

    @pytest.mark.parametrize("combination", ENTITY_HANDLE_FIELD_PATHS)
    async def test_upload_data_and_download_data_tool_combinations(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
        combination: str,
    ):
        step = function_project.project.steps.transaction_verification_step
        _initialize_entity_handle_fields(step, function_project.project.storage_scope)
        field_path = ENTITY_HANDLE_FIELD_PATHS[combination]
        content = b"uploaded-through-mcp"

        upload_result = await mcp_client.call_tool(
            "upload_data",
            {
                "project_name": function_project.project_name,
                "step_name": "transaction_verification_step",
                "field_path": field_path,
                "content": content,
            },
        )
        assert_no_mcp_response(upload_result)

        download_result = await mcp_client.call_tool(
            "download_data",
            {
                "project_name": function_project.project_name,
                "step_name": "transaction_verification_step",
                "field_path": field_path,
            },
        )
        assert_mcp_response(download_result, content.decode(), has_structure_content=False)

    @pytest.mark.parametrize("tool_name", ["set_fields", "get_fields", "upload_data", "download_data"])
    async def test_data_tools_with_non_existing_field(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
        tool_name: str,
    ):
        call_args: dict[str, Any] = {
            "project_name": function_project.project_name,
            "step_name": "transaction_verification_step",
        }
        expected_error_msg = (
            "At least one of the provided field names is not a 'TransactionVerificationStep' step field."
        )
        if tool_name in ["set_fields", "get_fields"]:
            if tool_name == "set_fields":
                call_args["fields"] = {"non_existing_field": 1.0}
                expected_error_msg = "'TransactionVerificationStep' has no field(s) 'non_existing_field'."
            else:
                call_args["field_names"] = ["non_existing_field"]
        elif tool_name in ["upload_data", "download_data"]:
            call_args["field_path"] = "non_existing_field"
            if tool_name == "upload_data":
                call_args["content"] = b"invalid-target-field"

        with pytest.raises(ToolError, match=re.escape(expected_error_msg)):
            await mcp_client.call_tool(tool_name, call_args)

    @pytest.mark.parametrize("tool_name", ["upload_data", "download_data"])
    @pytest.mark.parametrize("combination", NON_ENTITY_HANDLE_FIELD_PATHS)
    async def test_data_tools_with_non_entity_handle_leaf(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
        combination: str,
        tool_name: str,
    ):
        step = function_project.project.steps.transaction_verification_step
        _initialize_entity_handle_fields(step, function_project.project.storage_scope)
        field_path = NON_ENTITY_HANDLE_FIELD_PATHS[combination]

        call_args: dict[str, str | bytes] = {
            "project_name": function_project.project_name,
            "step_name": "transaction_verification_step",
            "field_path": field_path,
        }
        if tool_name == "upload_data":
            call_args["content"] = b"invalid-target-field"

        expected_error_msg = f"Field path '{field_path}' does not refer to an entity handle field."
        with pytest.raises(ToolError, match=re.escape(expected_error_msg)):
            await mcp_client.call_tool(tool_name, call_args)

    @pytest.mark.parametrize("tool_name", ["upload_data", "download_data"])
    @pytest.mark.parametrize("combination", MISSING_PATH_FIELD_PATHS)
    async def test_data_tools_with_missing_destination_path(
        self,
        mcp_client: MCPClient[StreamableHttpTransport],
        function_project: ProjectFixture[EndToEndSolution],
        combination: str,
        tool_name: str,
    ):
        step = function_project.project.steps.transaction_verification_step
        _initialize_entity_handle_fields(step, function_project.project.storage_scope)
        field_path, expected_error_msg = MISSING_PATH_FIELD_PATHS[combination]

        call_args: dict[str, str | bytes] = {
            "project_name": function_project.project_name,
            "step_name": "transaction_verification_step",
            "field_path": field_path,
        }
        if tool_name == "upload_data":
            call_args["content"] = b"invalid-target-field"

        with pytest.raises(ToolError, match=re.escape(expected_error_msg)):
            await mcp_client.call_tool(tool_name, call_args)
