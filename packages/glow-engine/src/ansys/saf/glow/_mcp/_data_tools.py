# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.server import Context
from pydantic import BaseModel, Field

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._mcp._resolution import get_solution_config, get_step

FIELD_PATH_DESCRIPTION = (
    "Path to the field containing the entity handle, as a slash-separated list of segments. "
    "The first segment is the step field name. Further segments navigate into the field's data structure: "
    "a list index, a dict key, or a custom object's attribute name. For example, 'my_file' refers to an "
    "entity handle field directly, while 'my_list/0' or 'my_object/sub_field' refer to an entity handle "
    "nested inside a list, dict, or custom object stored in the field."
)


def _resolve_segment(value: Any, segment: str) -> Any:
    if isinstance(value, list):
        try:
            index = int(segment)
        except ValueError as e:
            raise ValueError(f"'{segment}' is not a valid list index.") from e
        if not 0 <= index < len(value):  # pyright: ignore[reportUnknownArgumentType]
            raise ValueError(f"List index '{segment}' does not exist.")
        return value[index]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, dict):
        if segment not in value:
            raise ValueError(f"Dictionary key '{segment}' does not exist.")
        return value[segment]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, BaseModel):
        if segment not in type(value).model_fields:
            raise ValueError(f"Field '{segment}' does not exist on '{type(value).__name__}'.")
        return getattr(value, segment)
    raise ValueError(f"Cannot navigate into a value of type '{type(value).__name__}' using segment '{segment}'.")


def _set_segment(container: Any, segment: str, value: Any) -> None:
    if isinstance(container, list):
        container[int(segment)] = value
    elif isinstance(container, dict):
        container[segment] = value
    else:
        setattr(container, segment, value)


def _get_field_value(step: Any, field_path: str) -> tuple[str, Any]:
    field_name, *segments = field_path.split("/")
    value = step.get_fields([field_name])[field_name]
    for segment in segments:
        value = _resolve_segment(value, segment)
    return field_name, value


def register_data_tools(app: FastMCP, client_factory: Any) -> None:
    @app.tool()
    def set_fields(  # pyright: ignore[reportUnusedFunction]
        ctx: Annotated[Context, Field(description="MCP request context.")],
        project_name: Annotated[str, Field(description="Name of the project to update.")],
        step_name: Annotated[str, Field(description="Name of the step containing the fields.")],
        fields: Annotated[dict[str, Any], Field(description="Field names mapped to their new values.")],
    ) -> None:
        """Set field values on a solution step."""
        solution_class, solution_api_url = get_solution_config(ctx)

        with client_factory(solution_class, solution_api_url) as client:
            project = client.get_project(project_name)
            get_step(project, step_name).set_fields(fields)

    @app.tool()
    def get_fields(  # pyright: ignore[reportUnusedFunction]
        ctx: Annotated[Context, Field(description="MCP request context.")],
        project_name: Annotated[str, Field(description="Name of the project to read.")],
        step_name: Annotated[str, Field(description="Name of the step containing the fields.")],
        field_names: Annotated[list[str], Field(description="Names of the fields to read.")],
    ) -> dict[str, Any]:
        """Get field values from a solution step."""
        solution_class, solution_api_url = get_solution_config(ctx)

        with client_factory(solution_class, solution_api_url) as client:
            project = client.get_project(project_name)
            fields = get_step(project, step_name).get_fields(field_names)
        return fields

    @app.tool()
    def upload_data(  # pyright: ignore[reportUnusedFunction]
        ctx: Annotated[Context, Field(description="MCP request context.")],
        project_name: Annotated[str, Field(description="Name of the project to update.")],
        step_name: Annotated[str, Field(description="Name of the step containing the entity handle field.")],
        field_path: Annotated[str, Field(description=FIELD_PATH_DESCRIPTION)],
        content: Annotated[bytes, Field(description="File content to upload.")],
    ) -> None:
        """Upload file content to an entity handle, optionally nested in a list, dict, or custom object field."""
        solution_class, solution_api_url = get_solution_config(ctx)

        with client_factory(solution_class, solution_api_url) as client:
            project = client.get_project(project_name)
            step = get_step(project, step_name)
            field_name, *segments = field_path.split("/")
            field_value = step.get_fields([field_name])[field_name]
            entity = project.storage_scope.store_stream(content)

            if not segments:
                if not isinstance(field_value, EntityHandle):
                    raise ValueError(f"Field path '{field_path}' does not refer to an entity handle field.")
                step.set_fields({field_name: entity})
                return

            *parent_segments, last_segment = segments
            parent = field_value
            for segment in parent_segments:
                parent = _resolve_segment(parent, segment)
            if not isinstance(_resolve_segment(parent, last_segment), EntityHandle):
                raise ValueError(f"Field path '{field_path}' does not refer to an entity handle field.")

            _set_segment(parent, last_segment, entity)
            step.set_fields({field_name: field_value})

    @app.tool()
    def download_data(  # pyright: ignore[reportUnusedFunction]
        ctx: Annotated[Context, Field(description="MCP request context.")],
        project_name: Annotated[str, Field(description="Name of the project to read.")],
        step_name: Annotated[str, Field(description="Name of the step containing the entity handle field.")],
        field_path: Annotated[str, Field(description=FIELD_PATH_DESCRIPTION)],
    ) -> bytes:
        """Download file content from an entity handle, optionally nested in a list, dict, or custom object field."""
        solution_class, solution_api_url = get_solution_config(ctx)

        with client_factory(solution_class, solution_api_url) as client:
            project = client.get_project(project_name)
            step = get_step(project, step_name)
            _, field_value = _get_field_value(step, field_path)
            if not isinstance(field_value, EntityHandle):
                raise ValueError(f"Field path '{field_path}' does not refer to an entity handle field.")
            content = project.storage_scope.get_bytes(field_value)
        return content
