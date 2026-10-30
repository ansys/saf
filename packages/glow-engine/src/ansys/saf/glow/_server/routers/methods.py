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
import inspect
import logging
from typing import Annotated, Any, TypeVar, get_type_hints
from uuid import UUID

import fastapi
from fastapi import BackgroundTasks, Body, Request
from fastapi.exceptions import FastAPIError
from pydantic import BaseModel, ValidationError

from ansys.saf.glow._access.dependencies import require_project_read, require_project_write
from ansys.saf.glow._core.exceptions import SolutionLoadException
from ansys.saf.glow._core.method_status import MethodState
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._core.transaction import SolutionConfigParam, build_pydantic_model_from_transaction_parameters
from ansys.saf.glow._server.dependencies import (
    AccessCrudDep,
    CrudDep,
    MethodRunnerDep,
    PrincipalDep,
    RunningMethodsDep,
    SettingsDep,
    validate_project,
)
from ansys.saf.glow._server.exceptions import EXCEPTIONS_BY_CODE, UnprocessableEntityError
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part

T = TypeVar("T", bound=Solution)
PersistenceModelType = TypeVar("PersistenceModelType", bound=BaseModel)

logger = logging.getLogger(__name__)


def make_routes(solution_type: type[Solution]):
    """Create the methods routes.

    Note: the router variable is enclosed within this function
    for testing purpose, so that we do not have to reload the module
    to test another solution.
    """
    router = fastapi.APIRouter(
        prefix="/projects/{project_id}/steps",
        tags=["steps"],
        responses={404: {"description": "Unable to find the method."}},
        dependencies=[fastapi.Depends(require_project_read), fastapi.Depends(validate_project)],
    )

    for step_id, step_type in solution_type.get_steps_fields().items():
        step_name = python_identifier_to_url_part(step_id)
        url = f"/{step_name}"
        for method_id in step_type.get_transaction_method_names():
            try:
                _make_routes(router, url, step_type, method_id, step_id)
            except FastAPIError as ex:
                raise SolutionLoadException(
                    f"Invalid return type for the @transaction '{method_id}'!"
                    " Check that the return type is a valid pydantic field types.",
                ) from ex
    return router


def _make_routes(
    router: fastapi.APIRouter,
    step_url: str,
    step_type: type[StepModel],
    method_id: str,
    step_id: str,
) -> fastapi.APIRouter:
    method_name = python_identifier_to_url_part(method_id)
    method_url = f"{step_url}:{method_name}"
    is_long_running = method_id in step_type.get_long_running_method_names()
    method_func = getattr(step_type, method_id)
    docstring = method_func.__doc__
    unwrapped_func = inspect.unwrap(method_func)
    DynamicTransactionBodyModel, solution_configuration_param = (  # noqa: N806
        build_pydantic_model_from_transaction_parameters(
            unwrapped_func,
        )
    )
    return_type_hints = get_type_hints(unwrapped_func)
    response_model: type | None = (
        (None if return_type_hints["return"] is type(None) else return_type_hints["return"])
        if "return" in return_type_hints and not is_long_running
        else type(None)
    )

    @router.post(method_url, description=docstring, response_model=response_model)
    async def invoke_method(
        project_id: str,
        background_tasks: BackgroundTasks,
        method_runner: MethodRunnerDep,
        request: Request,
        crud: CrudDep,
        settings: SettingsDep,
        principal: PrincipalDep,
        access: AccessCrudDep,
        body_params: Annotated[DynamicTransactionBodyModel, Body(embed=False)] = None,  # type: ignore
    ):
        body = await request.body()
        if not body and DynamicTransactionBodyModel.model_fields:
            # Empty body but the transaction has parameters,
            # let's verify if they are optionals by validating the model created from those parameters.
            try:
                DynamicTransactionBodyModel.model_validate({})
            except ValidationError:
                raise UnprocessableEntityError(
                    "The transaction method requires argument(s) but none was provided.",
                ) from None

        # separate stand-alone transaction to setup method state before invoking method
        async with crud.get_modifying_project_lock(project_id):
            # The write lock may have moved since the caller's access was first checked. Checking again with the
            # project locked guarantees that nobody changes it until the method is marked as running below.
            await access.check_write(project_id, principal)
            typed_params: dict[str, Any] = {}
            if body_params:
                # recreate parameter values and types out of the model
                for param_name in body_params.model_fields:  # type: ignore
                    typed_params[param_name] = getattr(body_params, param_name)  # type: ignore
            # longrunning methods are not locked during their execution,
            # they rely on prepare_invoke, that, for long running methods,
            # internally does 2 database requests to get status and set status,
            # to be sure that only 1 longrunning method is running at a given moment.
            await method_runner.prepare_invoke(crud)
            bdm_lock_id: UUID | None = None
            if not settings.glow_bdm_gc_disabled and method_runner.has_entity_handles():
                bdm_lock_model = await crud.add_bdm_lock(project_id)
                bdm_lock_id = bdm_lock_model.id

        return await _invoke_method(
            project_id,
            background_tasks,
            method_runner,
            crud,
            bdm_lock_id,
            solution_configuration_param,
            typed_params,
            is_long_running,
        )

    @router.get(
        method_url,
        response_model=MethodState,
        description=f"Get status of '{method_id}' method on '{step_type.__name__}'",
        include_in_schema=is_long_running,
    )
    async def get_method_state(
        project_id: str,
        crud: CrudDep,
    ):
        return await crud.get_method_state(project_id, step_id, method_id)

    @router.patch(
        method_url,
        response_model=MethodState,
        description=f"Update status of '{method_name}' method on '{step_type.__name__}'",
        include_in_schema=is_long_running,
        dependencies=[fastapi.Depends(require_project_write)],
    )
    async def patch_method_state(
        project_id: str,
        method_state: MethodState,
        crud: CrudDep,
        running_methods: RunningMethodsDep,
    ):
        return await crud.update_method_state(
            project_id,
            step_id,
            method_id,
            method_state,
            running_methods,
        )

    return router


async def _invoke_method(
    project_id: str,
    background_tasks: BackgroundTasks,
    method_runner: MethodRunnerDep,
    crud: CrudDep,
    bdm_lock_id: UUID | None,
    solution_configuration_param: SolutionConfigParam | None,
    typed_params: dict[str, Any],
    is_long_running: bool,
):
    if is_long_running:
        background_tasks.add_task(
            method_runner.invoke,
            crud=crud,
            background_tasks=background_tasks,
            bdm_lock_id=bdm_lock_id,
            solution_configuration_param=solution_configuration_param,
            input_params=typed_params,
        )
    else:
        # separate transaction to invoke the method and get the result
        # use method lock so that methods on same project cannot be concurrent
        async with crud.get_method_lock(project_id):
            await method_runner.invoke(
                crud=crud,
                background_tasks=background_tasks,
                bdm_lock_id=bdm_lock_id,
                solution_configuration_param=solution_configuration_param,
                input_params=typed_params,
            )
            # get state in transaction so that result corresponds exactly to this execution
            state = await method_runner.get_result(crud)
        # raise exception outside transaction so that the method state
        # and bdm state are committed and not rolled back
        logger.debug(f"Method result: {state.status=} {state.exception_message=} {state.exception_stack=}")
        state.raise_for_error(EXCEPTIONS_BY_CODE)
        return state.result
