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

from collections.abc import AsyncGenerator, Callable, Coroutine
import logging
import os
from pathlib import Path
import secrets
import tempfile
from typing import Annotated, TypeVar

import fastapi
from fastapi import BackgroundTasks, Depends, HTTPException, Request, UploadFile, WebSocket
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
import httpx2
from pydantic import ValidationError

from ansys.bdm.api import IAsyncStorageScope
from ansys.iam.oidc import NoIssuerOrAudienceError, OidcClient, OidcDependency, OidcWebSocketDependency
from ansys.saf.glow._bdm.datarepo import DataRepositoryType
from ansys.saf.glow._bdm.multiplexor import SafMultiplexorStorageScopeFactory
from ansys.saf.glow._bdm.storage_contexts import RESTAPI_CONTEXT
from ansys.saf.glow._config.const import (
    DEFAULT_GLOW_AUTH_DISABLED,
    GLOW_AUTH_BYPASS_ROLES,
    GLOW_AUTH_CLIENT_ID,
    GLOW_AUTH_DISABLED,
    GLOW_AUTH_ISSUER_URL,
    GLOW_AUTH_REQUIRED_ROLES,
    LOCALHOST_HOSTS,
    DatabaseType,
    Deployment,
    ExecutorType,
    ProductInstanceSystemType,
)
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.gc import BdmLocksDb, BdmLocksNoOp, IBdmLocks
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow._core.instance.iinstance_system import IProductInstanceSystem, IProductInstanceSystemFactory
from ansys.saf.glow._core.instance.mock_system import MockSystemFactory
from ansys.saf.glow._core.instance.null_system import NullSystemFactory
from ansys.saf.glow._core.project_files_locator import ProjectFilesLocator
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._crud.crud import Crud
from ansys.saf.glow._crud.solution_configuration_abstract import AbstractSolutionConfigurationCRUD
from ansys.saf.glow._crud.solution_configuration_models import SolutionConfiguration, get_default_solution_configuration
from ansys.saf.glow._crud.solution_configuration_relational import RelationalSolutionConfigurationCRUD
from ansys.saf.glow._events.ievent_manager import IEventManager
from ansys.saf.glow._events.repository_event_manager import RepositoryEventManager
from ansys.saf.glow._executor.method_runner import MethodRunner, ProcessMethodRunner, ThreadMethodRunner
from ansys.saf.glow._hps_auth.hps_authenticator import create_hps_authenticator
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator
from ansys.saf.glow._repository.abstract_repository import AbstractRepositorySessionFactory
from ansys.saf.glow._repository.postgresql import PostgresqlSessionFactory
from ansys.saf.glow._repository.sqlite_factory import SqliteSessionFactory
from ansys.saf.glow._server.exceptions import NotFoundError, UnprocessableEntityError
from ansys.saf.glow._server.hps_auth_info import HpsAuthInfo
from ansys.saf.glow._server.method_url import MethodUrl
from ansys.saf.glow._server.product_instances_tracker import (
    ActiveProductInstancesTracker,
    InactiveProductInstancesTracker,
    ProductInstancesTracker,
)
from ansys.saf.glow._server.project_files_manager import ProjectFilesManager
from ansys.saf.glow._server.schemas import ProjectInfo
from ansys.saf.glow._server.solution import SolutionService
from ansys.saf.glow._telemetry.inject_trace_http_transport import InjectTraceTransport
from ansys.saf.glow._utilities.auth_roles import decode_token_claims, has_required_role, parse_required_roles
from ansys.saf.glow._utilities.conversion import url_part_to_python_identifier
from ansys.saf.glow._utilities.requests import build_api_url_for_internal_requests_from_request

T = TypeVar("T", bound=Solution)
TSolutionConfig = TypeVar("TSolutionConfig", bound=SolutionConfiguration)
logger = logging.getLogger(__name__)

running_methods: dict[str, set[str]] = {}
product_instances_created_by_this_process: ProductInstancesTracker | None = None
_hps_auth_info: dict[str, HpsAuthInfo] = {}

# Unfortunately we have to use env variables instead of settings injected within dependencies.
# This makes testing quite difficult since those env var are read during import time,
# but this is the price to pay to get openapi "authorize" button on the /docs page.
oidc_issuer_url = os.environ.get(GLOW_AUTH_ISSUER_URL)
audience = os.environ.get(GLOW_AUTH_CLIENT_ID)
# Aftersaf-portal is fixed, enable auth validation by default for
# DockerCompose deployments. Leave it disabled for Desktop ones, though.
disable_auth = os.environ.get(GLOW_AUTH_DISABLED, DEFAULT_GLOW_AUTH_DISABLED) != "False"
required_roles = parse_required_roles(os.environ.get(GLOW_AUTH_REQUIRED_ROLES))
bypass_roles = parse_required_roles(os.environ.get(GLOW_AUTH_BYPASS_ROLES))

try:
    oidc_scheme = OidcDependency(oidc_issuer=oidc_issuer_url, audience=audience, auto_error=not disable_auth)
    oidc_scheme_ws = OidcWebSocketDependency(
        oidc_issuer=oidc_issuer_url,
        audience=audience,
        auto_error=not disable_auth,
    )
except NoIssuerOrAudienceError:
    error_msg = (
        "Authentication cannot be enforced without setting environment variables GLOW_AUTH_ISSUER_URL and "
        "GLOW_AUTH_CLIENT_ID."
    )
    logger.error(error_msg)
    raise RuntimeError(error_msg) from None

# Keeping an independent auth scheme for hps as it currently uses a custom auth flow (and needs auto_error=False).
# (this needs to be refactored to use oidc_scheme too)
hps_auth_scheme = OAuth2PasswordBearer("/token", auto_error=False)


async def hps_auth_info() -> dict[str, HpsAuthInfo]:
    return _hps_auth_info


async def get_oidc_client() -> OidcClient:
    # creating a dependency out of the global var to help testing
    return oidc_scheme.client


async def get_solution_service(request: Request) -> SolutionService:
    return request.app.state.solution_service


async def get_solution_service_for_websocket(request: WebSocket) -> SolutionService:
    return request.app.state.solution_service


async def get_tracer(request: Request) -> SolutionService:
    return request.app.state.tracer


def get_settings() -> Settings:
    return Settings.model_validate({})


api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def oidc_scheme_with_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> str | None:
    if settings.computed_api_key and request.client and request.client.host in LOCALHOST_HOSTS:  # noqa: SIM102
        if api_key and secrets.compare_digest(api_key, settings.computed_api_key):
            logger.debug("API key authentication successful.")
            return api_key
    token = await oidc_scheme(request)
    if (
        oidc_scheme.auto_error
        and token
        and not has_required_role(decode_token_claims(token), audience, required_roles, bypass_roles)
    ):
        logger.error("Access token does not grant the required roles.")
        raise HTTPException(status_code=403, detail="Forbidden")
    return token


async def oidc_scheme_ws_with_roles(token: Annotated[str | None, Depends(oidc_scheme_ws)]) -> str | None:
    if (
        oidc_scheme_ws.auto_error
        and token
        and not has_required_role(decode_token_claims(token), audience, required_roles, bypass_roles)
    ):
        logger.error("Access token does not grant the required roles.")
        raise fastapi.WebSocketException(code=fastapi.status.WS_1008_POLICY_VIOLATION, reason="Forbidden")
    return token


def _get_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    solution_service: Annotated[SolutionService, Depends(get_solution_service)],
) -> AbstractRepositorySessionFactory:
    if settings.glow_database_type == DatabaseType.Sqlite:
        return SqliteSessionFactory(settings, solution_service)
    elif settings.glow_database_type == DatabaseType.PostgreSql:
        return PostgresqlSessionFactory(settings, solution_service)
    else:
        raise RuntimeError("Invalid database settings.")


def get_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    solution_service: Annotated[SolutionService, Depends(get_solution_service)],
) -> AbstractRepositorySessionFactory:
    return _get_repository(settings, solution_service)


def get_repository_for_websocket(
    settings: Annotated[Settings, Depends(get_settings)],
    solution_service: Annotated[SolutionService, Depends(get_solution_service_for_websocket)],
) -> AbstractRepositorySessionFactory:
    return _get_repository(settings, solution_service)


def get_event_manager(
    repository: Annotated[AbstractRepositorySessionFactory, Depends(get_repository)],
) -> IEventManager:
    return RepositoryEventManager(repository)


def get_event_manager_for_websocket(
    repository: Annotated[AbstractRepositorySessionFactory, Depends(get_repository_for_websocket)],
) -> IEventManager:
    return RepositoryEventManager(repository)


async def get_crud(
    repository: Annotated[AbstractRepositorySessionFactory, Depends(get_repository)],
    solution_service: Annotated[SolutionService, Depends(get_solution_service)],
) -> Crud:
    return Crud(solution_service, repository)


async def get_crud_for_websocket(
    repository: Annotated[AbstractRepositorySessionFactory, Depends(get_repository_for_websocket)],
    solution_service: Annotated[SolutionService, Depends(get_solution_service_for_websocket)],
) -> Crud:
    return Crud(solution_service, repository)


async def get_hps_authenticator(
    auth_token: Annotated[str | None, Depends(hps_auth_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> IHpsAuthenticator:
    return create_hps_authenticator(settings, auth_token)


async def get_instance_system_factory(
    settings: Annotated[Settings, Depends(get_settings)],
    hps_authenticator: Annotated[IHpsAuthenticator | None, Depends(get_hps_authenticator)],
) -> IProductInstanceSystemFactory:
    if settings.computed_glow_product_instance_system_uri:
        if settings.glow_product_instance_system == ProductInstanceSystemType.HPS and hps_authenticator:
            # deliberate conditional import because REP/HPS is an optional dependency
            from ansys.saf.glow._core.instance.hps_system import HpsSystemFactory

            return HpsSystemFactory(hps_authenticator)
        elif settings.glow_product_instance_system == ProductInstanceSystemType.PIM:
            if settings.glow_product_instance_system_host in LOCALHOST_HOSTS:
                # deliberate conditional import because PIM is an optional dependency
                from ansys.saf.glow._core.instance.pim_system import LocalPimSystemFactory

                return LocalPimSystemFactory(settings.glow_product_host)
            else:
                # deliberate conditional import because PIM is an optional dependency
                from ansys.saf.glow._core.instance.pim_system import ExternalPimSystemFactory

                return ExternalPimSystemFactory(
                    settings.ansys_grpc_certificates,  # pyright: ignore[reportArgumentType]  # already validated at Settings
                    settings.glow_product_host,
                )
        else:
            raise RuntimeError(f"Invalid product instance system: {settings.glow_product_instance_system}.")
    elif (
        settings.glow_product_instance_system == ProductInstanceSystemType._MOCK  # pyright: ignore[reportPrivateUsage]
    ):
        return MockSystemFactory()

    return NullSystemFactory()


async def get_instance_system(
    solution_service: Annotated[SolutionService, Depends(get_solution_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    instance_system_factory: Annotated[IProductInstanceSystemFactory, Depends(get_instance_system_factory)],
) -> IProductInstanceSystem:
    # Product Instance System URI doesn't exist for _MOCK system.
    product_instance_system_uri = settings.computed_glow_product_instance_system_uri or ""
    instance_system = instance_system_factory.create_system(product_instance_system_uri)
    instance_system.load_configurations_from_solution(solution_service.solution_module)
    return instance_system


async def get_solution_configuration_crud(
    settings: Annotated[Settings, Depends(get_settings)],
    solution_service: Annotated[SolutionService, Depends(get_solution_service)],
) -> AbstractSolutionConfigurationCRUD[SolutionConfiguration]:
    if not solution_service.solution_configuration_type:
        raise RuntimeError("The solution does not have solution_configuration field defined.")
    if settings.glow_database_type not in [DatabaseType.Sqlite, DatabaseType.PostgreSql]:
        raise RuntimeError(f"Invalid database settings: {settings.glow_database_type}")

    crud = RelationalSolutionConfigurationCRUD[solution_service.solution_configuration_type](
        settings.glow_database_type,
        settings.computed_database_location,
        solution_service.solution_configuration_type,
    )
    default_solution_configuration = get_default_solution_configuration(
        solution_service.solution_configuration_type,
    )
    await crud.initialize_database(default_solution_configuration)
    return crud


async def get_project_files_manager(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[ProjectFilesManager, None]:
    project_files_directory = ProjectFilesLocator.get_project_files_root(settings)
    project_files_directory.mkdir(exist_ok=True, parents=True)
    files_manager = ProjectFilesManager(project_files_directory)
    yield files_manager


async def get_project_info(
    project_id: str,
    crud: Annotated[Crud, Depends(get_crud)],
) -> ProjectInfo:
    """Retrieve the project info based on the project_id."""
    # fastapi keeps the colon in "project_id:export", so let's remove it.
    logger.debug("Fetching project info...")
    project_id = project_id.split(":")[0]
    try:
        project_info = await crud.get_project_info(project_id)
    except ValidationError as ex:
        # The project probably needs migration from the user so let's raise 422 and not 500.
        raise UnprocessableEntityError(str(ex)) from None
    logger.debug(f"project_info={project_info}")
    return project_info


async def get_project_info_without_validation(
    project_id: str,
    crud: Annotated[Crud, Depends(get_crud)],
) -> ProjectInfo:
    """Retrieve the project info based on the project_id."""
    # fastapi keeps the colon in "project_id:export", so let's remove it.
    logger.debug("Fetching project info...")
    project_id = project_id.split(":")[0]
    project_info = await crud.get_project_info_without_validation(project_id)
    logger.debug(f"project_info={project_info}")
    return project_info


async def get_filesystem_data_repository_query_map(
    settings: Annotated[Settings, Depends(get_settings)],
    solution_service: Annotated[SolutionService, Depends(get_solution_service)],
) -> dict[str, list[tuple[str, str]]] | None:
    if (
        solution_service.solution_configuration_type is None
        or settings.glow_data_repository_type != DataRepositoryType.FileSystem
    ):
        return None
    # The present coroutine can be called for Solutions without a SolutionConfiguration. In this case, calling
    # get_solution_configuration_crud as a dependency would raise an Exception. That is why we call it here, after
    # checking that solution_service.solution_configuration_type is not None, and not as a dependency.
    solution_configuration_crud = await get_solution_configuration_crud(settings, solution_service)
    solution_configuration = await solution_configuration_crud.get_solution_configuration()
    fs_datarepo_query_map = getattr(solution_configuration, "filesystem_data_repository_query_map", None)
    return fs_datarepo_query_map


async def get_multiplexor_storage_factory(
    project_info: Annotated[ProjectInfo, Depends(get_project_info_without_validation)],
    settings: Annotated[Settings, Depends(get_settings)],
    auth_token: Annotated[str | None, Depends(hps_auth_scheme)],
    access_token: Annotated[str | None, Depends(oidc_scheme_with_api_key)],
    solution_service: Annotated[SolutionService, Depends(get_solution_service)],
    filesystem_data_repository_query_map: Annotated[
        dict[str, list[tuple[str, str]]] | None,
        Depends(get_filesystem_data_repository_query_map),
    ],
) -> SafMultiplexorStorageScopeFactory:
    project_files_directory = ProjectFilesLocator.get_project_files_root(settings)
    multiplexor_scope_factory = SafMultiplexorStorageScopeFactory(
        project_files_dir=str(project_files_directory),
        project_id=project_info.project_id,
        settings=settings,
    )
    multiplexor_scope_factory.with_asset_storage_scope(solution_service.solution_type)
    multiplexor_scope_factory.with_datarepo_storage_scope(
        project_display_name=project_info.display_name,
        access_token=access_token or "",
        filesystem_data_repository_query_map=filesystem_data_repository_query_map,
    )
    multiplexor_scope_factory.with_hps_storage_scope(
        access_token=auth_token,
    )
    return multiplexor_scope_factory


async def get_project_storage_scope(
    storage_factory: Annotated[SafMultiplexorStorageScopeFactory, Depends(get_multiplexor_storage_factory)],
) -> AsyncGenerator[IAsyncStorageScope, None]:
    scope = await storage_factory.create_async_storage_scope(
        RESTAPI_CONTEXT,
    )
    async with scope as s:
        yield s


async def get_get_bdm_lock_db(
    settings: Annotated[Settings, Depends(get_settings)],
    crud: Annotated[Crud, Depends(get_crud)],
    background_tasks: BackgroundTasks,
) -> Callable[[str], Coroutine[None, None, IBdmLocks]]:
    async def f(project_id: str) -> IBdmLocks:
        project_files_directory = ProjectFilesLocator.get_project_files_root(settings)
        # Storage factory only used for garbage collection which only needs the primary system
        # -> no need to instantiate subsystems
        storage_factory = SafMultiplexorStorageScopeFactory(
            project_files_dir=str(project_files_directory),
            project_id=project_id,
            settings=settings,
        )
        return (
            BdmLocksDb(
                project_id=project_id,
                crud=crud,
                storage_factory=storage_factory,
                background_tasks=background_tasks,
            )
            if not settings.glow_bdm_gc_disabled
            else BdmLocksNoOp()
        )

    return f


async def verify_safx_archive(safx_file: UploadFile):
    """Verify the safx archive file."""
    logger.debug("Verifying safx archive file...")
    if safx_file.filename is None:
        raise UnprocessableEntityError(detail="Expected a .safx file, but received nothing.")
    if not safx_file.filename.endswith(".safx"):
        raise UnprocessableEntityError(detail=f"Expected a .safx file, but received: '{safx_file.filename}'.")


async def verify_project_no_running_methods(project_id: str, crud: Annotated[Crud, Depends(get_crud)]):
    """Throw 400 error if the given project have any methods
    running."""
    # fastapi keep the colon in "project_id:export", so let's remove it.
    project_id = project_id.split(":")[0]
    logger.debug(f"Verifying running methods on {project_id}.")

    running_methods = await crud.get_running_methods(project_id)

    if running_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to perform this action because the following methods are still running: "
            f"'{running_methods}'.",
        )


async def _validate_project(project_id: str, crud: Crud) -> None:
    """Validate that the project exists in the database. Raises 404 if not found."""
    await crud.verify_project_exists(project_id)


async def validate_project(project_id: str, crud: Annotated[Crud, Depends(get_crud)]) -> None:
    await _validate_project(project_id, crud)


async def validate_project_for_websocket(
    project_id: str,
    crud: Annotated[Crud, Depends(get_crud_for_websocket)],
) -> None:
    await _validate_project(project_id, crud)


def _validate_step(step_id: str, solution_service: SolutionService) -> None:
    """Validate that the step exists in the solution definition. Raises 404 if not found."""
    step_name = url_part_to_python_identifier(step_id)
    solution_service.get_step_model(step_name)


def validate_step(step_id: str, solution_service: Annotated[SolutionService, Depends(get_solution_service)]) -> None:
    _validate_step(step_id, solution_service)


def validate_step_for_websocket(
    step_id: str,
    solution_service: Annotated[SolutionService, Depends(get_solution_service_for_websocket)],
) -> None:
    _validate_step(step_id, solution_service)


async def create_tmp_path() -> AsyncGenerator[Path, None]:
    """Create a temporary directory that will be removed on completion
    of the context."""
    tmp_path = Path(tempfile.mkdtemp(prefix="ansys_saf_"))
    logger.debug(f"Temporary directory created at: {tmp_path}")
    yield tmp_path


async def get_running_methods(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, set[str]] | None:
    """Return a list of running methods on desktop.

    This is used to avoid the case where a method is kept in "running"
    state if the process is shutdown from the user on desktop.
    """
    if settings.glow_deployment == Deployment.Desktop:
        return running_methods
    return None


async def get_product_instances_created_by_this_process(
    settings: Annotated[Settings, Depends(get_settings)],
    instance_system_factory: Annotated[IProductInstanceSystemFactory, Depends(get_instance_system_factory)],
) -> ProductInstancesTracker:
    if settings.glow_deployment == Deployment.Desktop:
        global product_instances_created_by_this_process
        if product_instances_created_by_this_process is None:
            if isinstance(instance_system_factory, NullSystemFactory):
                product_instances_created_by_this_process = InactiveProductInstancesTracker()
            else:
                product_instances_created_by_this_process = ActiveProductInstancesTracker()
        return product_instances_created_by_this_process
    return InactiveProductInstancesTracker()


async def get_method_url(
    project_id: str,
    request: fastapi.Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MethodUrl:
    # future http requests done by the method runner should use internal netloc instead of reusing the request,
    # which may contain: subdomains, subpaths, different host and ports...
    method_url = f"projects/{project_id}{request.url.path.split(project_id)[-1]}"
    internal_url = build_api_url_for_internal_requests_from_request(request, settings.glow_api_port, method_url)
    return MethodUrl(str(internal_url))


async def get_http_client() -> AsyncGenerator[httpx2.Client, None]:
    # This client should not be shared between sync transactions or used outside of it.
    headers = {"shared-volume": "true"}
    http_client = httpx2.Client(timeout=300, transport=InjectTraceTransport(), headers=headers)
    yield http_client
    http_client.close()


async def get_graphql_client(
    method_url: Annotated[MethodUrl, Depends(get_method_url)],
) -> GqlClientConnectionPool:
    api_url = method_url.url.split("/projects")[0]
    graphql_client = GqlClientConnectionPool(url=f"{api_url}/graphql", pool_size=1)
    return graphql_client
    # TODO: implement graphql_client.close()


async def get_method_runner(
    project_id: str,
    request: fastapi.Request,
    solution_service: Annotated[SolutionService, Depends(get_solution_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    running_methods: Annotated[dict[str, set[str]], Depends(get_running_methods)],
    instance_system_factory: Annotated[IProductInstanceSystemFactory, Depends(get_instance_system_factory)],
    transaction_http_client: Annotated[httpx2.Client, Depends(get_http_client)],
    transaction_gql_client: Annotated[GqlClientConnectionPool, Depends(get_graphql_client)],
    method_url: Annotated[MethodUrl, Depends(get_method_url)],
    multiplexor_storage_factory: Annotated[SafMultiplexorStorageScopeFactory, Depends(get_multiplexor_storage_factory)],
    access_token: Annotated[str | None, Depends(oidc_scheme_with_api_key)],
    oidc_client: Annotated[OidcClient, Depends(get_oidc_client)],
) -> MethodRunner:
    step_types = solution_service.solution_type.get_steps_fields()
    if method_url.step_name not in step_types:
        raise NotFoundError(f"Step '{method_url.step_name}' not found.")

    step_type = step_types[method_url.step_name]
    if (
        method_url.method_name in step_type.get_long_running_method_names()
        and settings.glow_long_running_executor_type == ExecutorType.Process
    ):
        runner = ProcessMethodRunner(
            project_id=project_id,
            solution=solution_service.default_instance,
            method_url=method_url,
            settings=settings,
            instance_system_factory=instance_system_factory,
            multiplexor_storage_factory=multiplexor_storage_factory,
            running_methods=running_methods,
            access_token=access_token,
            oidc_client=oidc_client,
        )
    else:
        runner = ThreadMethodRunner(
            project_id=project_id,
            solution=solution_service.default_instance,
            method_url=method_url,
            settings=settings,
            instance_system_factory=instance_system_factory,
            http_client=transaction_http_client,
            graphql_client=transaction_gql_client,
            multiplexor_storage_factory=multiplexor_storage_factory,
            running_methods=running_methods,
            access_token=access_token,
            oidc_client=oidc_client,
        )
    return runner


ProductInstancesTrackerDep = Annotated[ProductInstancesTracker, Depends(get_product_instances_created_by_this_process)]
ProjectInfoDep = Annotated[ProjectInfo, Depends(get_project_info)]
ProjectFilesManagerDep = Annotated[ProjectFilesManager, Depends(get_project_files_manager)]
CrudDep = Annotated[Crud, Depends(get_crud)]
WSCrudDep = Annotated[Crud, Depends(get_crud_for_websocket)]
RunningMethodsDep = Annotated[dict[str, set[str]], Depends(get_running_methods)]
SolutionServiceDep = Annotated[SolutionService, Depends(get_solution_service)]
WSSolutionServiceDep = Annotated[SolutionService, Depends(get_solution_service_for_websocket)]
TmpPathDep = Annotated[Path, Depends(create_tmp_path)]
ProjectStorageScopeDep = Annotated[IAsyncStorageScope, Depends(get_project_storage_scope)]
InstanceSystemFactoryDep = Annotated[IProductInstanceSystemFactory, Depends(get_instance_system_factory)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
MethodRunnerDep = Annotated[MethodRunner, Depends(get_method_runner)]
InstanceSystemDep = Annotated[IProductInstanceSystem, Depends(get_instance_system)]
StorageFactoryDep = Annotated[SafMultiplexorStorageScopeFactory, Depends(get_multiplexor_storage_factory)]
GetBdmLocksDbDep = Annotated[Callable[[str], Coroutine[None, None, BdmLocksDb]], Depends(get_get_bdm_lock_db)]
HpsAuthInfoDep = Annotated[dict[str, HpsAuthInfo], Depends(hps_auth_info)]
SolutionConfigurationCrudDep = Annotated[
    AbstractSolutionConfigurationCRUD[TSolutionConfig],
    Depends(get_solution_configuration_crud),
]
HpsAuthenticatorDep = Annotated[IHpsAuthenticator | None, Depends(get_hps_authenticator)]
MultiplexorStorageScopeFactoryDep = Annotated[
    SafMultiplexorStorageScopeFactory,
    Depends(get_multiplexor_storage_factory),
]
AccessTokenDep = Annotated[str | None, Depends(oidc_scheme_with_api_key)]
WSAccessTokenDep = Annotated[str | None, Depends(oidc_scheme_ws_with_roles)]
FileSystemDataRepoQueryMapDep = Annotated[
    dict[str, list[tuple[str, str]]] | None,
    Depends(get_filesystem_data_repository_query_map),
]
EventManagerDep = Annotated[IEventManager, Depends(get_event_manager)]
WSEventManagerDep = Annotated[IEventManager, Depends(get_event_manager_for_websocket)]
