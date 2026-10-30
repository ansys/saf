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

from ansys.saf.glow._access.dependencies import require_project_read, require_project_write
from ansys.saf.glow._core.instance.attribute import CreateInstance
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._server.dependencies import (
    CrudDep,
    InstanceSystemDep,
    ProductInstancesTrackerDep,
    SettingsDep,
    SolutionServiceDep,
    validate_project,
)
from ansys.saf.glow._server.schemas import (
    CreateInstanceRequest,
    InstanceResponse,
    ModifyInstanceRequest,
    NoInstanceResponse,
)
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part

T = TypeVar("T", bound=Solution)


def make_routes(solution_type: type[Solution]):
    """Create the instances routes.

    Note: the router variable is enclosed within this function
    for testing purpose, so that we do not have to reload the module
    to test another solution.
    """
    router = fastapi.APIRouter(
        prefix="/projects/{project_id}/steps",
        tags=["steps"],
        responses={404: {"description": "Unable to find the instance."}},
        dependencies=[fastapi.Depends(require_project_read), fastapi.Depends(validate_project)],
    )
    for step_id, step_type in solution_type.get_steps_fields().items():
        step_url_part = python_identifier_to_url_part(step_id)
        url = f"/{step_url_part}"
        for (
            instance_name,
            create_instance,
        ) in step_type._get_create_instance_by_name().items():  # pyright: ignore[reportPrivateUsage]
            _make_routes(router, url, step_id, step_type, instance_name, create_instance)
    return router


def _make_routes(
    router: fastapi.APIRouter,
    step_url: str,
    step_id: str,
    step_type: type[StepModel],
    instance_id: str,
    create_instance: CreateInstance,
) -> fastapi.APIRouter:
    instance_url_part = python_identifier_to_url_part(instance_id)
    instance_url = f"{step_url}/instances/{instance_url_part}"
    recovery_state_type = create_instance.recovery_state_type

    def _get_instance_url(project_id: str) -> str:
        return f"projects/{project_id}/steps{instance_url}"

    @router.post(
        instance_url,
        response_model=InstanceResponse[recovery_state_type],
        description=f"Create '{instance_id}' instance on '{step_type.__name__}'",
        dependencies=[fastapi.Depends(require_project_write)],
    )
    async def post_instance(  # pyright: ignore
        project_id: str,
        instance_state: CreateInstanceRequest[recovery_state_type],  # pyright: ignore
        crud: CrudDep,
        solution_service: SolutionServiceDep,
        product_instances_created_by_this_process: ProductInstancesTrackerDep,
    ):
        instance_state.name = _get_instance_url(project_id)
        return await crud.create_instance(
            project_id=project_id,
            solution_service=solution_service,
            product_instances_created_by_this_process=product_instances_created_by_this_process,
            step_name=step_id,
            instance_id=instance_id,
            instance_request=instance_state,  # pyright: ignore
        )

    @router.get(
        instance_url,
        response_model=InstanceResponse[recovery_state_type],
        description=f"get state of {instance_id}' instance on '{step_type.__name__}'",
    )
    async def get_instance_state(
        project_id: str,
        crud: CrudDep,
        ignore_not_found: bool = False,
    ):
        instance_state = await crud.get_instance_state(
            project_id,
            step_id,
            instance_id,
            _get_instance_url(project_id),
            ignore_not_found,
        )
        return instance_state or NoInstanceResponse()

    @router.patch(
        instance_url,
        response_model=InstanceResponse[recovery_state_type],
        description=f"Update status of '{instance_id}' instance on '{step_type.__name__}'",
        dependencies=[fastapi.Depends(require_project_write)],
    )
    async def patch_instance_state(
        project_id: str,
        instance_state: ModifyInstanceRequest[recovery_state_type],  # type: ignore
        crud: CrudDep,
        solution_service: SolutionServiceDep,
        product_instances_created_by_this_process: ProductInstancesTrackerDep,
    ):
        return await crud.update_instance_state(
            project_id,
            solution_service,
            product_instances_created_by_this_process,
            step_id,
            _get_instance_url(project_id),
            instance_id,
            instance_state,  # type: ignore
        )

    @router.delete(
        instance_url,
        description=f"Delete instance '{instance_id}' on '{step_type.__name__}'",
        dependencies=[fastapi.Depends(require_project_write)],
    )
    async def delete_instance(
        project_id: str,
        crud: CrudDep,
        product_instances_created_by_this_process: ProductInstancesTrackerDep,
        product_instance_system: InstanceSystemDep,
        settings: SettingsDep,
    ):
        await crud.delete_instance(
            project_id,
            product_instances_created_by_this_process,
            step_id,
            instance_id,
            product_instance_system,
            settings,
        )

    return router
