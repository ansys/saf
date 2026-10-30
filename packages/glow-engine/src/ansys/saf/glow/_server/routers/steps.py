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

# pyright complains about some of the functions associated with routes because nothing calls them
# so switch that error off
# pyright: reportUnusedFunction=false
from typing import Annotated, TypeVar

import fastapi
from pydantic import BaseModel

from ansys.saf.glow._access.dependencies import require_project_read, require_project_write
from ansys.saf.glow._core.gc import bdm_garbage_collector
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._crud.bdm_helper import steps_contain_entity_handles
from ansys.saf.glow._server.dependencies import (
    CrudDep,
    GetBdmLocksDbDep,
    ProjectStorageScopeDep,
    SettingsDep,
    validate_project,
)
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part

T = TypeVar("T", bound=Solution)
PersistenceModelType = TypeVar("PersistenceModelType", bound=BaseModel)


def make_routes(solution_type: type[Solution]):
    """Create the steps routes.

    Note: the router variable is enclosed within this function
    for testing purpose, so that we do not have to reload the module
    to test another solution.
    """
    router = fastapi.APIRouter(
        prefix="/projects/{project_id}/steps",
        tags=["steps"],
        dependencies=[fastapi.Depends(require_project_read), fastapi.Depends(validate_project)],
    )

    for step_id, step_type in solution_type.get_steps_fields().items():
        _make_routes(router, step_id, step_type, solution_type)
    return router


def _make_routes(router: fastapi.APIRouter, step_id: str, step_type: type[StepModel], solution_type: type[Solution]):
    step_name = python_identifier_to_url_part(step_id)
    url = f"/{step_name}"
    doc = f"{step_type.__name__}: {step_type.__doc__}" if step_type.__doc__ is not None else ""

    @router.get(
        url,
        response_model=step_type,
        response_model_exclude_unset=True,
        responses={404: {"description": "Unable to find the step."}},
        description=f"Get {step_type.__name__} for the specified project. <br><br> {doc}",
    )
    async def get_step(
        project_id: str,
        crud: CrudDep,
        fields: str | None = None,
    ):
        """Get the step resource for the specified project."""
        return await crud.get_step(project_id, step_id, fields)

    @router.patch(
        url,
        response_model=step_type,
        responses={404: {"description": "Unable to find the step."}},
        description=f"Update '{step_type.__name__}' for the specified project. <br><br> {doc}",
        dependencies=[fastapi.Depends(require_project_write)],
    )
    async def update_step(
        project_id: str,
        step_body: step_type,  # type: ignore
        crud: CrudDep,
        get_bdm_locks_db: GetBdmLocksDbDep,
    ):
        """Update the step resource for the specified project."""
        locks_db = await get_bdm_locks_db(project_id)
        steps = {  # pyright: ignore[reportUnknownVariableType]
            step_id: step_body.model_dump(exclude_unset=True),  # pyright: ignore[reportUnknownMemberType]
        }
        if steps_contain_entity_handles(solution_type, steps):  # pyright: ignore[reportUnknownArgumentType]
            async with bdm_garbage_collector(locks_db):
                return await crud.update_step(
                    project_id,
                    step_id,
                    step_body,  # pyright: ignore[reportUnknownArgumentType]
                )
        else:
            return await crud.update_step(project_id, step_id, step_body)  # pyright: ignore[reportUnknownArgumentType]

    @router.get(
        f"{url}/data/{{datapath:path}}",
        responses={404: {"description": "Unable to find the data."}},
        description=f"Retrieve nested data items from step '{step_type.__name__}' for the specified project.",
    )
    async def get_data(
        project_id: str,
        datapath: str,
        crud: CrudDep,
        project_storage_scope: ProjectStorageScopeDep,
        settings: SettingsDep,
        files_as_urls: Annotated[bool, fastapi.Query(alias="files-as-urls")] = False,
        directories_as_dictionaries: Annotated[bool, fastapi.Query(alias="directories-as-dictionaries")] = False,
    ):
        """Get the step resource for the specified project."""
        return await crud.get_step_data(
            project_id,
            step_id,
            datapath,
            project_storage_scope,
            settings,
            files_as_urls,
            directories_as_dictionaries,
        )
