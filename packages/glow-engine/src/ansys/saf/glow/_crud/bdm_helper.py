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

from pathlib import Path
import platform
import re

from anyio import EndOfStream
from fastapi import UploadFile

from ansys.bdm.api import EntityHandle, IAsyncStorageScope
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._server.exceptions import NotFoundError
from ansys.saf.glow._server.models import ProjectModel


def steps_contain_entity_handles(solution_type: type[Solution], steps: dict[str, dict[str, str]]) -> bool:
    # `steps` is not required to contain only full dumps of the steps. For every step, it can be only the fields
    # that have to be updated/used. See usage in graphql.py:resolve_update_project_steps_with_json
    # That's why we use `.field_has_handles` instead of just `.has_handles` for the entire step.
    for step_name, fields in steps.items():
        step_type = solution_type.get_steps_fields().get(step_name)
        if step_type is None:
            raise NotFoundError(f"Step {step_name} not found.")
        for field_name, _ in fields.items():
            if step_type()._entity_handle_fields.field_has_handles(field_name):  # pyright: ignore[reportPrivateUsage]
                return True

    return False


async def convert_upload_file_to_handle(
    project_storage_scope: IAsyncStorageScope,
    upload_file: UploadFile,
) -> EntityHandle:
    relative_location = None if upload_file.filename is None else Path(upload_file.filename)
    async with await project_storage_scope.begin_store(relative_location) as writer:
        # Use shutil.copyfileobj logic to handles the difference
        # in ideal buffer size between Windows and other operating systems.
        # TODO: review the following calculation so that it is optimized for real GLOW performance
        # critical use cases
        copy_bufsize = 1024 * 1024 if platform.system() == "windows" else 64 * 1024
        while content := await upload_file.read(copy_bufsize):
            await writer.stream.send(content)

    return writer.handle


async def get_stream_generator(project_storage_scope: IAsyncStorageScope, handle: EntityHandle):
    stream = await project_storage_scope.get_stream(handle)

    async def generator():
        async with stream as s:
            done = False
            while not done:
                try:
                    yield await s.receive()
                except EndOfStream:
                    done = True

    return generator


def update_opaque_identifier_in_project_text(project_json_str: str, new_project_id: str) -> str:
    # The entity handle opaque identifiers contain the project id from the original exported project.
    # They need to be updated with the current project id to make the bdm storage scope working.
    def replace_project_id(matchobj: re.Match[str]):
        replaced_value = f'{matchobj.group(1)}:"{matchobj.group(2)}{new_project_id}{matchobj.group(3)}'
        return replaced_value

    return re.sub(r'("opaque_identifier"):"(\w+?/)\w{24}([^"]+")', replace_project_id, project_json_str)


def update_opaque_identifier(project: ProjectModel[Solution], project_id: str) -> ProjectModel[Solution]:
    json_model = project.model_dump_json()
    updated_model = update_opaque_identifier_in_project_text(json_model, project_id)
    return project.model_validate_json(updated_model)
