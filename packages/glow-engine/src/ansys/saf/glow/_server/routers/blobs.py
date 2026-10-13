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
from typing import TypeVar

import fastapi
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ansys.bdm.api import NO_ENTITY, InvalidContextError
from ansys.bdm.api.entity_handle import EntityHandle
from ansys.saf.glow._core.gc import bdm_garbage_collector
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._server.dependencies import (
    CrudDep,
    GetBdmLocksDbDep,
    ProjectStorageScopeDep,
    SettingsDep,
    validate_project,
)
from ansys.saf.glow._server.exceptions import BadRequestError, ForbiddenError, NotFoundError
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part

T = TypeVar("T", bound=Solution)
PersistenceModelType = TypeVar("PersistenceModelType", bound=BaseModel)


def make_routes(solution_type: type[Solution]):
    """Create the fields routes.

    Note: the router variable is enclosed within this function
    for testing purpose, so that we do not have to reload the module
    to test another solution.
    """
    router = fastapi.APIRouter(
        prefix="/projects/{project_id}/steps",
        tags=["steps"],
        responses={404: {"description": "Unable to find the field."}},
        dependencies=[fastapi.Depends(validate_project)],
    )

    for step_id, step_type in solution_type.get_steps_fields().items():
        step_url_part = python_identifier_to_url_part(step_id)
        url = f"/{step_url_part}"
        for field_id, field_info in step_type.model_fields.items():
            if field_info.annotation == EntityHandle:
                _make_routes(router, url, step_id, step_type, field_id)

        _make_get_route(router, url, step_id, step_type)
    return router


def _make_get_route(
    router: fastapi.APIRouter,
    step_url: str,
    step_id: str,
    step_type: type[StepModel],
) -> fastapi.APIRouter:
    @router.get(
        f"{step_url}/blobs/{{datapath:path}}",
        description=(
            "Get the content of the entity referenced by entity handle "
            + f"referenced by data path on '{step_type.__name__}'. "
        ),
        # Both response_class and responses must be set together to produce the correct OpenAPI spec:
        # - return typehint alone causes FastAPI to specify application/json as content-type.
        # - response_class alone omits content-type information from the spec entirely.
        # - responses alone causes FastAPI to inject an additional application/json entry from the return annotation.
        # See https://github.com/fastapi/fastapi/discussions/9551
        response_class=FileResponse,
        responses={
            # Explicitly declare application/octet-stream so API clients and code generators treat this as a
            # binary download rather than a JSON response. The schema type/format follows the OpenAPI 3.x
            # convention for raw binary content. Note that the actual Content-Type header in the response is
            # resolved at runtime by Starlette via mimetypes.guess_type(). It falls back to application/octet-stream
            # for unknown extensions.
            200: {
                "description": "The content of the entity referenced by the entity handle.",
                "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
            },
        },
    )
    async def get_blob(
        project_id: str,
        datapath: str,
        crud: CrudDep,
        project_storage_scope: ProjectStorageScopeDep,
        settings: SettingsDep,
    ):
        try:
            entity_handle = await crud.get_entity_handle(project_id, step_id, datapath, project_storage_scope, settings)
            if entity_handle == NO_ENTITY:
                raise NotFoundError(detail="entity does not exist") from None
            if not entity_handle.is_blob:
                raise BadRequestError(detail="cannot create stream for directory") from None

            entity_path = await project_storage_scope.get_cached(entity_handle)
            return FileResponse(entity_path, filename=entity_path.name)
        except InvalidContextError as e:
            raise ForbiddenError(detail=str(e)) from None

    return router


def _make_routes(
    router: fastapi.APIRouter,
    step_url: str,
    step_id: str,
    step_type: type[StepModel],
    field_id: str,
) -> fastapi.APIRouter:
    field_url_part = python_identifier_to_url_part(field_id)
    field_url = f"{step_url}/blobs/{field_url_part}"

    @router.put(
        field_url,
        description=(
            f"Update field '{field_id}' value on '{step_type.__name__}' "
            "so that it refers to the content of the supplied entity. "
            "This is part of the incomplete blob data management alpha feature."
        ),
    )
    async def update_blob(
        project_id: str,
        upload_file: fastapi.UploadFile,
        crud: CrudDep,
        project_storage_scope: ProjectStorageScopeDep,
        get_bdm_locks_db: GetBdmLocksDbDep,
    ) -> EntityHandle:
        handle = await crud.set_entity_handle_field_value(
            project_storage_scope,
            project_id,
            step_id,
            field_id,
            upload_file,
        )
        locks_db = await get_bdm_locks_db(project_id)
        async with bdm_garbage_collector(locks_db):
            return handle

    return router
