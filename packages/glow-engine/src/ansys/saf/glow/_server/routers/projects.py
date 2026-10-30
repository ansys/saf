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

import logging
from typing import Annotated, TypeVar
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ValidationError
from stream_zip import async_stream_zip

from ansys.saf.glow._access.access_crud import NoProjects
from ansys.saf.glow._access.dependencies import (
    require_project_metadata,
    require_project_owner,
    require_project_read,
    require_project_write,
)
from ansys.saf.glow._bdm.multiplexor import SafMultiplexorStorageScopeFactory
from ansys.saf.glow._core.gc import BdmLocksNoOp, bdm_garbage_collector, create_bdm_db_locks
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._repository.generate_project_id import generate_project_id
from ansys.saf.glow._server.dependencies import (
    AccessCrudDep,
    AccessTokenDep,
    CrudDep,
    FileSystemDataRepoQueryMapDep,
    HpsAuthenticatorDep,
    InstanceSystemDep,
    MultiplexorStorageScopeFactoryDep,
    PrincipalDep,
    ProductInstancesTrackerDep,
    ProjectFilesManagerDep,
    ProjectInfoDep,
    SettingsDep,
    SolutionServiceDep,
    StorageFactoryDep,
    TmpPathDep,
    validate_project,
    verify_project_no_running_methods,
    verify_safx_archive,
)
from ansys.saf.glow._server.exceptions import ForbiddenError, UnprocessableEntityError
from ansys.saf.glow._server.filter_parser import ParsedProjectFilter
from ansys.saf.glow._server.models import BdmLockModel
from ansys.saf.glow._server.schemas import (
    CreateProjectRequest,
    ListProjectRequest,
    ListProjectResponse,
    ModifyProjectRequest,
    ProjectInfo,
)

T = TypeVar("T", bound=Solution)
PersistenceModelType = TypeVar("PersistenceModelType", bound=BaseModel)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


@router.post(
    "",
    response_model=ProjectInfo,
    responses={
        400: {"description": "Unable to create the project."},
    },
)
async def create_project(
    request: CreateProjectRequest,
    crud: CrudDep,
    file_manager: ProjectFilesManagerDep,
    solution_service: SolutionServiceDep,
    principal: PrincipalDep,
    access: AccessCrudDep,
):
    """Create a project with the given display_name and optional description and return a record
    of the project."""
    project_info = await crud.create_project(file_manager, solution_service, request)
    await access.on_project_created(project_info.project_id, principal)
    await access.fill_access_summaries([project_info], principal)
    return project_info


@router.post(
    ":import",
    response_model=ProjectInfo,
    responses={
        400: {"description": "Unable to import the project."},
        404: {"description": "Unable to find the project'."},
        409: {"description": "Destination already exists."},
    },
    dependencies=[Depends(verify_safx_archive)],
)
async def import_project(
    safx_file: UploadFile,
    crud: CrudDep,
    settings: SettingsDep,
    file_manager: ProjectFilesManagerDep,
    tmp_path: TmpPathDep,
    solution_service: SolutionServiceDep,
    background_tasks: BackgroundTasks,
    access_token: AccessTokenDep,
    filesystem_data_repository_query_map: FileSystemDataRepoQueryMapDep,
    principal: PrincipalDep,
    access: AccessCrudDep,
    display_name: Annotated[
        str,
        Form(
            ...,
            description="The project name displayed to the user.",
            examples=["my project"],
        ),
    ],
):
    """Import the given project with the specified display_name
    and return a record of the project."""

    project_id = generate_project_id()
    project_files_dir = file_manager.get_project_files_dir(project_id).parent

    multiplexor_scope_factory = SafMultiplexorStorageScopeFactory(
        project_files_dir=str(project_files_dir),
        project_id=project_id,
        settings=settings,
    )
    multiplexor_scope_factory.with_datarepo_storage_scope(
        project_display_name=display_name,
        access_token=access_token or "",
        filesystem_data_repository_query_map=filesystem_data_repository_query_map,
    )
    multiplexor_scope_factory.with_hps_storage_scope(
        access_token=access_token,
    )
    multiplexor_scope_factory.with_asset_storage_scope(solution_type=solution_service.solution_type)

    project_info = await crud.import_project(
        project_id=project_id,
        project_directory=(project_files_dir / project_id),
        file_manager=file_manager,
        upload_file=safx_file,
        tmp_path=tmp_path,
        solution_service=solution_service,
        display_name=display_name,
        project_file_manager=file_manager,
        storage_scope_factory=multiplexor_scope_factory,
        settings=settings,
    )
    await access.on_project_created(project_info.project_id, principal)
    await access.fill_access_summaries([project_info], principal)
    locker = create_bdm_db_locks(
        project_info.project_id,
        settings,
        multiplexor_scope_factory,
        crud,
        background_tasks,
    )
    async with bdm_garbage_collector(locker):
        return project_info


@router.get("")
async def list_projects(
    crud: CrudDep,
    list_project_request: Annotated[ListProjectRequest, Query()],
    principal: PrincipalDep,
    access: AccessCrudDep,
) -> ListProjectResponse:
    """Return a paginated list of projects, optionally filtered.

    By default, returns the first page of results with a maximum of 100 projects per page.
    An optional filter expression can be provided to narrow down results.

    When project access control is enabled, only the projects the caller is a member of are listed. Super admins
    list every project.
    """
    if list_project_request.orphans_only:
        access.check_orphans_listing(principal)
    filters = None
    if list_project_request.filter:
        try:
            filters = ParsedProjectFilter.from_str(list_project_request.filter)
        except (ValueError, ValidationError) as ex:
            raise UnprocessableEntityError(str(ex)) from None

    scope = access.list_scope(principal)
    if isinstance(scope, NoProjects):
        return ListProjectResponse(
            projects=[],
            current_page=1,
            total_pages=1,
            page_size=list_project_request.page_size,
            total_projects=0,
        )

    response = await crud.list_projects(
        page_size=list_project_request.page_size,
        page=list_project_request.page,
        order_by=list_project_request.order_by,
        filters=filters,
        member_id=scope,
        orphans_only=list_project_request.orphans_only,
    )
    await access.fill_access_summaries(response.projects, principal)
    return response


@router.get(
    "/{project_id}:export",
    # Both response_class and responses must be set for FastAPI to properly generate the OpenAPI spec.
    responses={
        200: {
            "description": "The project exported as a SAFX archive.",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        },
        400: {"description": "Unable to export the project."},
        404: {"description": "Unable to find the project'."},
    },
    # using FileResponse instead of StreamingResponse to be able to download the file from the Swagger UI.
    response_class=FileResponse,
    dependencies=[Depends(require_project_read), Depends(verify_project_no_running_methods)],
)
async def export_project(
    project_id: str,
    crud: CrudDep,
    file_manager: ProjectFilesManagerDep,
):
    """Export the given project."""
    # FastAPI keeps the colon in "project_id:export", so let's remove it.
    logger.info(f"Exporting project: {project_id}...")
    project_id = project_id.split(":")[0]
    project_info, project_as_dict = await crud.get_project_as_dict(project_id)
    project_as_dict["bdm_locks"] = []
    async_project_files_generator = file_manager.create_async_project_files_generator(project_info, project_as_dict)
    return StreamingResponse(
        async_stream_zip(async_project_files_generator()),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_info.display_name}.safx"'},
    )


@router.get(
    "/{project_id}",  # noqa: FAST003
    responses={
        404: {"description": "Unable to find the project'."},
        422: {"description": "Invalid project."},
    },
    dependencies=[Depends(require_project_metadata)],
)
async def get_project(project_info: ProjectInfoDep, principal: PrincipalDep, access: AccessCrudDep) -> ProjectInfo:
    """Return details for a specific project."""
    await access.fill_access_summaries([project_info], principal)
    return project_info


@router.patch(
    "/{project_id}",
    responses={
        400: {"description": "Unable to modify the project."},
        404: {"description": "Unable to find the project."},
        422: {"description": "Invalid project."},
    },
    dependencies=[Depends(require_project_write), Depends(verify_project_no_running_methods)],
)
async def modify_project(
    project_id: str,
    request: ModifyProjectRequest,
    crud: CrudDep,
) -> ProjectInfo:
    """Modify details for a specific project."""
    return await crud.modify_project_info(project_id, request)


@router.post(
    "/{project_id}:upgrade",
    responses={
        400: {"description": "Unable to upgrade the stored solution of the project."},
        404: {"description": "Unable to find the project."},
    },
    dependencies=[Depends(require_project_write), Depends(verify_project_no_running_methods)],
)
async def upgrade_project(
    project_id: str,
    crud: CrudDep,
    storage_scope_factory: MultiplexorStorageScopeFactoryDep,
    file_manager: ProjectFilesManagerDep,
    settings: SettingsDep,
    background_tasks: BackgroundTasks,
) -> ProjectInfo:
    """Upgrade the details of a solution data stored in a specific project."""

    try:
        project_info = await crud.upgrade_project(
            project_id=project_id,
            project_files_manager=file_manager,
            storage_scope_factory=storage_scope_factory,
            settings=settings,
        )
    except ValidationError as ex:
        raise UnprocessableEntityError(str(ex)) from None

    if await crud.project_in_database(project_id):
        # this is the case where the project is stored in the database
        locker = create_bdm_db_locks(project_id, settings, storage_scope_factory, crud, background_tasks)
    else:
        # this is the case where the project is still stored in a legacy JSON file
        locker = BdmLocksNoOp()

    # we GC separately because the update deletes the project which can't happen
    # whilst we have BDM locks with references to the project
    async with bdm_garbage_collector(locker):
        return project_info


@router.delete(
    "/{project_id}",
    responses={
        403: {"description": "Only the owner of the project or a super admin can delete it."},
        404: {"description": "Unable to find the project'."},
    },
    dependencies=[Depends(require_project_owner)],
)
async def delete_project(
    project_id: str,
    crud: CrudDep,
    file_manager: ProjectFilesManagerDep,
    product_instance_system: InstanceSystemDep,
    product_instances_created_by_this_process: ProductInstancesTrackerDep,
    hps_authenticator: HpsAuthenticatorDep,
    settings: SettingsDep,
):
    """Delete the project from the database and delete its project directory."""
    return await crud.remove_project(
        file_manager,
        project_id,
        product_instance_system,
        product_instances_created_by_this_process,
        hps_authenticator,
        settings,
    )


async def raise_error_if_gc_disabled(settings: SettingsDep):
    if settings.glow_bdm_gc_disabled:
        raise ForbiddenError("Garbage collection is disabled.")


@router.post(
    "/{project_id}/bdm-locks",
    dependencies=[Depends(require_project_write), Depends(raise_error_if_gc_disabled), Depends(validate_project)],
    responses={
        403: {"description": "Permission denied."},
        404: {"description": "Project not found."},
    },
)
async def create_bdm_lock(
    project_id: str,
    crud: CrudDep,
    request: Request,
) -> BdmLockModel:
    return await crud.add_bdm_lock(
        project_id=project_id,
        is_internal_caller=request.headers.get("GLOW_INTERNAL_TOKEN") == "NOT_FROM_CLIENT_TOKEN",
    )


@router.get(
    "/{project_id}/bdm-locks/{lock_id}",
    dependencies=[Depends(require_project_write), Depends(raise_error_if_gc_disabled), Depends(validate_project)],
    responses={
        403: {"description": "Permission denied."},
        404: {"description": "Project or bdm lock not found."},
        410: {"description": "Bdm lock expired."},
    },
)
async def get_bdm_lock(
    project_id: str,
    lock_id: uuid.UUID,
    crud: CrudDep,
) -> BdmLockModel:
    return await crud.get_bdm_lock(
        lock_id=lock_id,
        project_id=project_id,
    )


@router.delete(
    "/{project_id}/bdm-locks/{lock_id}",
    dependencies=[Depends(require_project_write), Depends(raise_error_if_gc_disabled), Depends(validate_project)],
    responses={
        403: {"description": "Permission denied."},
        404: {"description": "Project or bdm lock not found."},
    },
)
async def delete_bdm_lock(
    project_id: str,
    lock_id: uuid.UUID,
    crud: CrudDep,
    storage_factory: StorageFactoryDep,
    background_tasks: BackgroundTasks,
) -> None:
    await crud.remove_bdm_lock(
        lock_id=lock_id,
        project_id=project_id,
        storage_factory=storage_factory,
        background_tasks=background_tasks,
    )
