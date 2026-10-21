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

from contextlib import asynccontextmanager
import importlib.metadata
import logging
import sys

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # pyright: ignore[reportMissingTypeStubs]
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from ansys.saf.glow._config.const import (
    GLOW_API_SERVICE_NAME,
    Deployment,
)
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.exceptions import SolutionLoadException
from ansys.saf.glow._core.gc import cleanup_expired_bdm_locks_on_startup
from ansys.saf.glow._server.dependencies import SettingsDep, SolutionServiceDep, oidc_scheme_with_api_key
from ansys.saf.glow._server.routers import (
    blobs,
    desktop,
    events,
    graphql,
    instances,
    methods,
    projects,
    solution_configuration,
    steps,
)
from ansys.saf.glow._server.schemas import ServerInfo, SolutionInfo
from ansys.saf.glow._server.solution import SolutionService
from ansys.saf.glow._telemetry.instrumentor import Instrumentor
from ansys.saf.glow._telemetry.metrics_middleware import MetricsMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings):  # noqa: C901
    """Create an instance of the FastAPI app.

    The app variable is enclosed within this function so that multiple
    apps can be created for testing purpose, without having to reload
    the import.
    """
    tags_metadata = [
        {
            "name": "projects",
            "description": "Create and manage projects for the Solution.",
        },
        {
            "name": "steps",
            "description": "Create and manage the steps in Solution projects.",
        },
    ]
    if settings.glow_project_access_control_enabled and settings.glow_auth_disabled:
        raise RuntimeError(
            "GLOW_PROJECT_ACCESS_CONTROL_ENABLED requires authentication: set GLOW_AUTH_DISABLED to False.",
        )
    instrumentor = Instrumentor.instrumentalize_process(GLOW_API_SERVICE_NAME, settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await cleanup_expired_bdm_locks_on_startup(
            settings,
            app.state.solution_service,
        )
        yield

    try:
        solution_service = SolutionService(settings.computed_definition_module)
        solution_service.build_and_validate()
    except SolutionLoadException as ex:
        message = (
            f"Error: the program had to exit because the solution '{settings.computed_definition_module.__name__}'"
            f" contains the following error(s): \n{ex.errors}"
        )
        sys.exit(message)

    swagger_ui_init_oauth = {
        "clientId": settings.glow_auth_client_id,
        "scopes": ["openid", "profile", "email"],
        "appName": solution_service.name,
    }
    app = FastAPI(
        title="Ansys Solutions Application Framework / Guided Low Code Workflow (SAF/GLOW)",
        lifespan=lifespan,
        openapi_tags=tags_metadata,
        debug=settings.glow_debug is not None,
        swagger_ui_init_oauth=swagger_ui_init_oauth,
    )
    app.state.solution_service = solution_service
    # Add step routes on startup since we need to wait
    # for the solution singleton to be configured with the
    # proper definition.
    solution_type = solution_service.solution_type
    global_dependencies = [Depends(oidc_scheme_with_api_key)]
    app.include_router(steps.make_routes(solution_type), dependencies=global_dependencies)
    app.include_router(methods.make_routes(solution_type), dependencies=global_dependencies)
    app.include_router(instances.make_routes(solution_type), dependencies=global_dependencies)
    app.include_router(blobs.make_routes(solution_type), dependencies=global_dependencies)
    app.include_router(graphql.make_routes(settings, solution_type), dependencies=global_dependencies)
    if solution_service.solution_configuration_type:
        app.include_router(solution_configuration.make_routes(solution_service), dependencies=global_dependencies)
    if settings.glow_deployment == Deployment.Desktop:
        # omit auth for desktop routes, TODO: should we, now that it's not coupled deployment and auth?
        app.include_router(desktop.router)

    display_name = solution_type.model_construct().display_name
    description = f"""
Solution: {display_name}
==============================

Ansys GLOW is an application programming framework for creating and
managing engineering simulation solutions.

This page provides details on the API for the ``{display_name}``
Solution.
"""
    app.description = description

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.glow_cors_origins or [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(MetricsMiddleware, app_name=instrumentor.name, meter=instrumentor.meter)

    app.include_router(projects.router, dependencies=global_dependencies)
    # voluntarily omitting oidc_scheme on events since the events router contains a mix of websocket and http routes.
    # Each one explicitly defines the auth dependency that it needs.
    app.include_router(events.router)

    FastAPIInstrumentor.instrument_app(app)  # type: ignore

    @app.get("/health")
    async def health() -> str:
        return "The GLOW API server is healthy."

    @app.get("/schema")
    async def schema(solution_service: SolutionServiceDep):
        return solution_service.solution_type.model_json_schema()

    @app.get("/", dependencies=[Depends(oidc_scheme_with_api_key)])
    async def server_info(solution_service: SolutionServiceDep, settings: SettingsDep) -> ServerInfo:
        return ServerInfo(
            solution=SolutionInfo(
                name=solution_service.name,
                display_name=solution_service.default_instance.display_name,
                schema_version=solution_service.default_instance.version,
            ),
            external_api_url=settings.computed_external_api_url,
            glow_version=importlib.metadata.version("ansys-saf-glow-engine"),
        )

    def _record_exception_in_span(request: Request, exc: Exception):
        span = trace.get_current_span()  # type: ignore
        span.record_exception(exc)  # type: ignore
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))  # type: ignore
        if str(exc) != "":
            # eption handler, exc can be empty and
            # therefore not worth adding into the logs.
            logger.exception(str(exc)) if settings.glow_debug else logger.error(str(exc))

    @app.exception_handler(RequestValidationError)  # type: ignore
    async def custom_request_validation_exception_handler(request: Request, exc: RequestValidationError):
        _record_exception_in_span(request, exc)
        # not returning a PlainTextResponse because it does not format errors consistently for all pydantic errors:
        # there are still some bits of json within the plain text (e.g: {'loc': ..., 'msg':...})
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
        _record_exception_in_span(request, exc)
        return await http_exception_handler(request, exc)

    @app.exception_handler(ResponseValidationError)
    async def response_validation_handler(request: Request, exc: ResponseValidationError):
        _record_exception_in_span(request, exc)
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "The returned data is invalid."},
        )

    # A specific handler for ModuleNotFoundError exception type is required since
    # this kind of error usually happens before Starlette can handle it on the
    # StarletteHTTPException handler.
    # On the Python Exception type hierarchy, ModuleNotFoundError is not derived directly
    # from Exception, but from ImportError: Exception -> ImportError -> ModuleNotFoundError.
    # When the @app.exception_handler checks the exception type it looks for the concrete type
    # and the parent's type, but not further. That implies that ModuleNotFoundError needs a
    # specific exception handler (or ImportError handler).
    @app.exception_handler(ModuleNotFoundError)
    async def module_not_found_exception_handler(request: Request, exc: ModuleNotFoundError):
        _record_exception_in_span(request, exc)
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )

    return app


def mount_mcp_app(app: FastAPI, settings: Settings) -> FastAPI:
    if settings.glow_mcp_disabled:
        logger.debug("MCP is disabled in configuration")
        return app
    if not settings.glow_auth_disabled:
        logger.warning("MCP not mounted: authentication is enabled and not supported")
        return app
    try:
        import fastmcp  # noqa: F401  # pyright: ignore[reportUnusedImport]
        import mcp  # pyright: ignore[reportUnusedImport]
    except ImportError:
        logger.warning("MCP not mounted: missing dependencies: fastmcp, mcp")
        return app

    # keep fastmcp/mcp an optional dependency
    from fastmcp.utilities.lifespan import combine_lifespans

    from ansys.saf.glow._mcp.server import build_app

    mcp = build_app(
        definition_module=settings.computed_definition_module,
        solution_class=settings.computed_solution_type,
        solution_api_url=f"http://localhost:{settings.glow_api_port}",
    )
    mcp_app = mcp.http_app(path="/", transport=settings.glow_mcp_transport_mode)
    app.mount(settings.glow_mcp_path, mcp_app)
    logger.info(f"MCP mounted at path {settings.glow_mcp_path}")
    app.router.lifespan_context = combine_lifespans(app.router.lifespan_context, mcp_app.lifespan)

    return app
