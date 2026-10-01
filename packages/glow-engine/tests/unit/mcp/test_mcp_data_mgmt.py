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
import re
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from ansys.bdm.api import EntityHandle
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict
import pytest

from tests.e2e.mcp.conftest import assert_mcp_response, assert_no_mcp_response


async def test_set_fields_tool(
    mcp_unit_client: Client[FastMCPTransport],
    mock_glow_client: tuple[MagicMock, MagicMock],
):
    _, mock_instance = mock_glow_client
    mock_step = mock_instance.get_project.return_value.steps.transaction_verification_step
    fields: dict[str, Any] = {
        "field_1": 3.5,
        "sleepy_seconds": 2.0,
        "text_content": "updated-through-mcp",
        "child_process_is_running": True,
    }

    result = await mcp_unit_client.call_tool(
        "set_fields",
        {
            "project_name": "test-project",
            "step_name": "transaction_verification_step",
            "fields": fields,
        },
    )
    assert_no_mcp_response(result)
    mock_step.set_fields.assert_called_once_with(fields)


async def test_get_fields_tool(
    mcp_unit_client: Client[FastMCPTransport],
    mock_glow_client: tuple[MagicMock, MagicMock],
):
    _, mock_instance = mock_glow_client
    mock_step = mock_instance.get_project.return_value.steps.transaction_verification_step
    field_names = ["field_1", "sleepy_seconds", "text_content", "child_process_is_running"]
    fields: dict[str, Any] = {
        "field_1": 4.5,
        "sleepy_seconds": 11.0,
        "text_content": "read-through-mcp",
        "child_process_is_running": True,
    }
    mock_step.get_fields.return_value = fields

    result = await mcp_unit_client.call_tool(
        "get_fields",
        {
            "project_name": "test-project",
            "step_name": "transaction_verification_step",
            "field_names": field_names,
        },
    )
    assert result.structured_content == fields
    mock_step.get_fields.assert_called_once_with(field_names)


class CustomObjectWithEntityHandle(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    label: str = "obj"
    file: Any = None


class CustomObjectWithEntityHandleCollections(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    files: list[Any] = []
    file_map: dict[str, Any] = {}
    nested: CustomObjectWithEntityHandle = CustomObjectWithEntityHandle()


def _combination_container(leaf: Any) -> CustomObjectWithEntityHandleCollections:
    return CustomObjectWithEntityHandleCollections(
        files=[leaf],
        file_map={"key1": leaf},
        nested=CustomObjectWithEntityHandle(file=leaf),
    )


# Each entry maps a combination name to the path (relative to the "field" step field) and a builder that places the
# given leaf value (an entity handle for the happy path, or any other value to test the "not an entity handle" case)
# at that path.
ENTITY_HANDLE_COMBINATIONS: dict[str, tuple[str, Callable[[Any], Any]]] = {
    "entity_handle": ("field", lambda leaf: leaf),
    "list": ("field/0", lambda leaf: [leaf]),
    "dict": ("field/key1", lambda leaf: {"key1": leaf}),
    "custom_object": ("field/file", lambda leaf: CustomObjectWithEntityHandle(file=leaf)),
    "nested_list": ("field/0/0", lambda leaf: [[leaf]]),
    "nested_dict": ("field/key1/key2", lambda leaf: {"key1": {"key2": leaf}}),
    "combination_list_item": ("field/files/0", _combination_container),
    "combination_dict_item": ("field/file_map/key1", _combination_container),
    "combination_nested_object": ("field/nested/file", _combination_container),
}

# Each entry maps a combination name to a path missing its final destination segment, and a substring of the
# resulting error message.
MISSING_PATH_CASES: dict[str, tuple[str, str]] = {
    "entity_handle": ("field/extra", "does not exist on"),
    "list": ("field/5", "List index '5' does not exist."),
    "dict": ("field/missing_key", "Dictionary key 'missing_key' does not exist."),
    "custom_object": ("field/missing_attr", "does not exist on"),
    "nested_list": ("field/0/5", "List index '5' does not exist."),
    "nested_dict": ("field/key1/missing_key2", "Dictionary key 'missing_key2' does not exist."),
    "combination_list_item": ("field/files/5", "List index '5' does not exist."),
    "combination_dict_item": ("field/file_map/missing_key", "Dictionary key 'missing_key' does not exist."),
    "combination_nested_object": ("field/nested/missing_attr", "does not exist on"),
}


def _get_at_path(value: Any, segments: list[str]) -> Any:
    for segment in segments:
        if isinstance(value, list):
            value = value[int(segment)]
        elif isinstance(value, dict):
            value = value[segment]
        else:
            value = getattr(value, segment)
    return value


def _entity_handle() -> EntityHandle:
    # a real instance (not a MagicMock) so that isinstance/model_fields checks behave like production data
    return EntityHandle(is_blob=True, entity_id=uuid4(), opaque_identifier=str(uuid4()))


@pytest.mark.parametrize("combination", ENTITY_HANDLE_COMBINATIONS)
async def test_upload_data_tool_combinations(
    mcp_unit_client: Client[FastMCPTransport],
    mock_glow_client: tuple[MagicMock, MagicMock],
    combination: str,
):
    _, mock_instance = mock_glow_client
    mock_step = mock_instance.get_project.return_value.steps.transaction_verification_step
    mock_project = mock_instance.get_project.return_value

    field_path, build_value = ENTITY_HANDLE_COMBINATIONS[combination]
    field_value = build_value(_entity_handle())
    mock_step.get_fields.return_value = {"field": field_value}

    content = b"uploaded-through-mcp"
    result = await mcp_unit_client.call_tool(
        "upload_data",
        {
            "project_name": "test-project",
            "step_name": "transaction_verification_step",
            "field_path": field_path,
            "content": content,
        },
    )
    assert_no_mcp_response(result)
    new_handle = mock_project.storage_scope.store_stream.return_value
    mock_project.storage_scope.store_stream.assert_called_once_with(content)
    mock_step.set_fields.assert_called_once()
    (set_fields_args,), _ = mock_step.set_fields.call_args
    assert _get_at_path(set_fields_args["field"], field_path.split("/")[1:]) == new_handle


@pytest.mark.parametrize("combination", ENTITY_HANDLE_COMBINATIONS)
async def test_download_data_tool_combinations(
    mcp_unit_client: Client[FastMCPTransport],
    mock_glow_client: tuple[MagicMock, MagicMock],
    combination: str,
):
    _, mock_instance = mock_glow_client
    mock_step = mock_instance.get_project.return_value.steps.transaction_verification_step
    mock_project = mock_instance.get_project.return_value

    field_path, build_value = ENTITY_HANDLE_COMBINATIONS[combination]
    existing_handle = _entity_handle()
    field_value = build_value(existing_handle)
    mock_step.get_fields.return_value = {"field": field_value}

    content = b"downloaded-through-mcp"
    mock_project.storage_scope.get_bytes.return_value = content

    result = await mcp_unit_client.call_tool(
        "download_data",
        {
            "project_name": "test-project",
            "step_name": "transaction_verification_step",
            "field_path": field_path,
        },
    )
    assert_mcp_response(result, content.decode(), has_structure_content=False)
    mock_project.storage_scope.get_bytes.assert_called_once_with(existing_handle)


@pytest.mark.parametrize("tool_name", ["set_fields", "get_fields", "upload_data", "download_data"])
async def test_data_tools_with_non_existing_field(
    mcp_unit_client: Client[FastMCPTransport],
    mock_glow_client: tuple[MagicMock, MagicMock],
    tool_name: str,
):
    _, mock_instance = mock_glow_client
    mock_step = mock_instance.get_project.return_value.steps.transaction_verification_step

    call_args: dict[str, Any] = {
        "project_name": "test-project",
        "step_name": "transaction_verification_step",
    }
    expected_error_msg = "At least one of the provided field names is not a 'TransactionVerificationStep' step field."
    if tool_name in ["set_fields", "get_fields"]:
        if tool_name == "set_fields":
            call_args["fields"] = {"non_existing_field": 1.0}
            expected_error_msg = "'TransactionVerificationStep' has no field(s) 'non_existing_field'."
            mock_step.set_fields.side_effect = ValueError(expected_error_msg)
        else:
            call_args["field_names"] = ["non_existing_field"]
            mock_step.get_fields.side_effect = ValueError(expected_error_msg)
    elif tool_name in ["upload_data", "download_data"]:
        call_args["field_path"] = "non_existing_field"
        mock_step.get_fields.side_effect = ValueError(expected_error_msg)
        if tool_name == "upload_data":
            call_args["content"] = b"invalid-target-field"

    with pytest.raises(ToolError, match=re.escape(expected_error_msg)):
        await mcp_unit_client.call_tool(tool_name, call_args)


@pytest.mark.parametrize("tool_name", ["upload_data", "download_data"])
@pytest.mark.parametrize("combination", ENTITY_HANDLE_COMBINATIONS)
async def test_data_tools_with_non_entity_handle_leaf(
    mcp_unit_client: Client[FastMCPTransport],
    mock_glow_client: tuple[MagicMock, MagicMock],
    combination: str,
    tool_name: str,
):
    _, mock_instance = mock_glow_client
    mock_step = mock_instance.get_project.return_value.steps.transaction_verification_step

    field_path, build_value = ENTITY_HANDLE_COMBINATIONS[combination]
    field_value = build_value("not-an-entity-handle")
    mock_step.get_fields.return_value = {"field": field_value}

    call_args: dict[str, Any] = {
        "project_name": "test-project",
        "step_name": "transaction_verification_step",
        "field_path": field_path,
    }
    if tool_name == "upload_data":
        call_args["content"] = b"invalid-target-field"

    expected_error_msg = f"Field path '{field_path}' does not refer to an entity handle field."
    with pytest.raises(ToolError, match=re.escape(expected_error_msg)):
        await mcp_unit_client.call_tool(tool_name, call_args)


@pytest.mark.parametrize("tool_name", ["upload_data", "download_data"])
@pytest.mark.parametrize("combination", MISSING_PATH_CASES)
async def test_data_tools_with_missing_destination_path(
    mcp_unit_client: Client[FastMCPTransport],
    mock_glow_client: tuple[MagicMock, MagicMock],
    combination: str,
    tool_name: str,
):
    _, mock_instance = mock_glow_client
    mock_step = mock_instance.get_project.return_value.steps.transaction_verification_step

    _, build_value = ENTITY_HANDLE_COMBINATIONS[combination]
    field_value = build_value(_entity_handle())
    mock_step.get_fields.return_value = {"field": field_value}

    bad_path, expected_error_msg = MISSING_PATH_CASES[combination]
    call_args: dict[str, Any] = {
        "project_name": "test-project",
        "step_name": "transaction_verification_step",
        "field_path": bad_path,
    }
    if tool_name == "upload_data":
        call_args["content"] = b"invalid-target-field"

    with pytest.raises(ToolError, match=re.escape(expected_error_msg)):
        await mcp_unit_client.call_tool(tool_name, call_args)


@pytest.mark.parametrize("tool_name", ["upload_data", "download_data"])
async def test_data_tools_with_path_through_a_scalar_value(
    mcp_unit_client: Client[FastMCPTransport],
    mock_glow_client: tuple[MagicMock, MagicMock],
    tool_name: str,
):
    # a plain scalar (str) cannot be navigated into any further
    _, mock_instance = mock_glow_client
    mock_step = mock_instance.get_project.return_value.steps.transaction_verification_step
    mock_step.get_fields.return_value = {"field": {"key1": "not-a-container"}}

    call_args: dict[str, Any] = {
        "project_name": "test-project",
        "step_name": "transaction_verification_step",
        "field_path": "field/key1/extra",
    }
    if tool_name == "upload_data":
        call_args["content"] = b"invalid-target-field"

    with pytest.raises(ToolError, match=re.escape("Cannot navigate into a value of type")):
        await mcp_unit_client.call_tool(tool_name, call_args)
