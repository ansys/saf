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

from collections.abc import Callable, Coroutine
import logging
import re
from typing import TYPE_CHECKING, Any, TypeVar

from ariadne import MutationType, QueryType, gql, make_executable_schema
from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLHTTPHandler
from ariadne.contrib.tracing.opentelemetry import opentelemetry_extension  # type: ignore
import fastapi
from graphql import GraphQLResolveInfo
from opentelemetry import trace
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.gc import bdm_garbage_collector
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._crud.bdm_helper import steps_contain_entity_handles
from ansys.saf.glow._server.dependencies import AccessCrudDep, CrudDep, GetBdmLocksDbDep, PrincipalDep
from ansys.saf.glow._server.exceptions import ForbiddenError, LockedError, NotFoundError

if TYPE_CHECKING:
    from ansys.saf.glow._crud.crud import Crud

logger = logging.getLogger(__name__)


def _process_exception(settings: Settings | None, exc: Exception, status: str, error: str | None = None):
    logger.exception(str(exc)) if settings is None or settings.glow_debug else logger.error(str(exc))
    return {"status": status, "error": str(exc) if error is None else error}


# TODO - extend to support return values and make it a decorator
async def _process_result(info: GraphQLResolveInfo, crud_method_call: Callable[[], Coroutine[Any, Any, None]]):
    settings = None
    try:
        settings = info.context["settings"]
        await crud_method_call()
    except ValidationError as e:
        return _process_exception(settings, e, "BAD_REQUEST", str(e))
    except NotFoundError as e:
        return _process_exception(settings, e, "NOT_FOUND")
    except (LockedError, ForbiddenError) as e:
        return _process_exception(settings, e, "PERMISSION_DENIED")
    except Exception as e:
        # TODO - add more specific error handling
        return _process_exception(settings, e, "INTERNAL_SERVER_ERROR", "The returned data is invalid.")

    return {"status": "SUCCESS", "error": None}


T = TypeVar("T", bound=Solution)

query = QueryType()
mutation = MutationType()


@mutation.field("update_project_steps_with_json")
async def resolve_update_project_steps_with_json(
    _,
    info: GraphQLResolveInfo,
    project_id: str,
    steps: dict[str, dict[str, str]],
):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("resolve_update_project_steps_with_json"):

        async def set_fields_in_project():
            crud: Crud = info.context["db"]
            await info.context["access"].check_write(project_id, info.context["principal"])
            solution_type = info.context["solution_type"]

            # TODO - move all this business logic into crud ??
            if steps_contain_entity_handles(solution_type, steps):
                get_bdm_locks_db = info.context["get_bdm_locks_db"]
                locks_db = await get_bdm_locks_db(project_id)
                async with bdm_garbage_collector(locks_db):
                    await crud.set_fields_in_project(project_id, steps)
            else:
                await crud.set_fields_in_project(project_id, steps)

        return await _process_result(info, set_fields_in_project)


def _generate_type_def_str(solution_type: type[Solution]) -> str:
    # all the update step models have optional fields so that the caller can pass
    # in a sparse update.
    step_type_defs = ""
    steps_type_def_fields = ""
    for step_id, step_type in solution_type.get_steps_fields().items():
        field_type_defs = ""
        for field_name in step_type.model_fields:
            field_type_defs += f"{field_name}: String\n"  # will always contain the JSON for the field
        step_input_type_name = f"{step_type.__name__}JsonInput"
        step_type_defs += f"input {step_input_type_name} {{ {field_type_defs} }}\n"
        steps_type_def_fields += f"{step_id}: {step_input_type_name}\n"

    steps_type_def = f"input StepsJsonInput {{ {steps_type_def_fields} }}\n"

    return (
        step_type_defs
        + steps_type_def
        + """
    enum MutationStatus {
        BAD_REQUEST
        PERMISSION_DENIED
        UNAUTHORIZED
        NOT_FOUND
        CONFLICT
        INTERNAL_SERVER_ERROR
        SUCCESS
    }

    type MutationResult {
        status: MutationStatus!
        error: String
    }

    type Mutation {
        update_project_steps_with_json(project_id: String!, steps : StepsJsonInput!): MutationResult!
    }

    type Query {
        _empty: String
    }
    """
    )


def _get_context_value(request: Request, _data: Any):
    return {
        "request": request,
        "db": request.scope["db"],
        "principal": request.scope["principal"],
        "access": request.scope["access"],
        "settings": request.scope["settings"],
        "get_bdm_locks_db": request.scope["get_bdm_locks_db"],
        "solution_type": request.scope["solution_type"],
    }


def _opentelemetry_arg_filter(args: dict[str, Any], _: GraphQLResolveInfo) -> dict[str, Any]:
    for key, value in args.items():
        if isinstance(value, str | int | float | bool | bytes):
            args[key] = value
        else:
            args[key] = value.__class__.__name__
    return args


class _NotFoundAwareGraphQLHTTPHandler(GraphQLHTTPHandler):
    """Custom HTTP handler that converts schema validation errors for undefined fields/steps into NOT_FOUND
    responses."""

    NOT_FOUND_PATTERN = re.compile(r"Field '.*' is not defined by type")

    async def create_json_response(self, request: Request, result: dict[str, Any], success: bool) -> Response:
        if not success and "errors" in result:
            error_messages: list[str] = [e.get("message", "") for e in result["errors"]]
            if any(self.NOT_FOUND_PATTERN.search(msg) for msg in error_messages):
                combined_error = "; ".join(error_messages)
                result = {
                    "data": {
                        "update_project_steps_with_json": {
                            "status": "NOT_FOUND",
                            "error": combined_error,
                        },
                    },
                }
                success = True
        return await super().create_json_response(request, result, success)  # pyright: ignore[reportUnknownMemberType]


def make_routes(settings: Settings, solution_type: type[Solution]) -> fastapi.APIRouter:
    type_defs = gql(_generate_type_def_str(solution_type))
    schema = make_executable_schema(type_defs, [query, mutation])
    graphql_app = GraphQL(
        schema,
        context_value=_get_context_value,
        debug=settings.glow_debug is not None,
        http_handler=_NotFoundAwareGraphQLHTTPHandler(
            extensions=[
                opentelemetry_extension(arg_filter=_opentelemetry_arg_filter),
            ],
        ),
    )

    router = fastapi.APIRouter(
        prefix="/graphql",
        tags=["graphql"],
    )

    # Handle GET requests to serve GraphQL explorer
    # Handle OPTIONS requests for CORS
    @router.get("")
    @router.options("")
    async def handle_graphql_explorer(request: Request):
        return await graphql_app.handle_request(request)

    # Handle POST requests to execute GraphQL queries
    @router.post("")
    async def handle_graphql_query(
        request: Request,
        crud: CrudDep,
        get_bdm_locks_db: GetBdmLocksDbDep,
        principal: PrincipalDep,
        access: AccessCrudDep,
    ):
        # Expose database connection, settings and the caller's identity to the GraphQL through request's scope
        request.scope["db"] = crud
        request.scope["principal"] = principal
        request.scope["access"] = access
        request.scope["settings"] = settings
        request.scope["get_bdm_locks_db"] = get_bdm_locks_db
        request.scope["solution_type"] = solution_type
        return await graphql_app.handle_request(request)

    return router
