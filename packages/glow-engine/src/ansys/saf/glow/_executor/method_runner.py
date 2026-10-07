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

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Callable, Generator
import concurrent.futures
from contextlib import contextmanager
import functools
import logging
import multiprocessing
import os
import traceback
from typing import Any, TypeVar
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
import httpx2
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator  # type: ignore
import psutil
from pydantic_core import PydanticSerializationError

from ansys.bdm.api import IStorageScope
from ansys.iam.oidc import OidcClient
from ansys.saf.glow._bdm.datarepo import DataRepositoryType
from ansys.saf.glow._bdm.minerva import MinervaDataRepository
from ansys.saf.glow._bdm.multiplexor import SafMultiplexorStorageScopeFactory
from ansys.saf.glow._bdm.storage_contexts import METHOD_CONTEXT
from ansys.saf.glow._config.const import GLOW_METHOD_RUNNER_SERVICE_NAME
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.blob_managers import AssetManager, HpsBlobManager
from ansys.saf.glow._core.gc import create_bdm_db_locks
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow._core.instance.iinstance_system import IProductInstanceSystemFactory
from ansys.saf.glow._core.method_status import MethodState, MethodStatus
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.transaction import SolutionConfigParam
from ansys.saf.glow._crud.crud import Crud
from ansys.saf.glow._server.exceptions import INTERNAL_ERROR_MESSAGE, ConflictError
from ansys.saf.glow._server.method_url import MethodUrl
from ansys.saf.glow._telemetry.inject_trace_http_transport import InjectTraceTransport
from ansys.saf.glow._telemetry.instrumentor import Instrumentor
from ansys.saf.glow._utilities.procs import kill_pids

T = TypeVar("T", bound=Solution)
logger = logging.getLogger(__name__)

# Force same process start method both on Windows and Linux.
# The default on Linux is 'fork'.
multiprocessing.set_start_method("spawn", force=True)


class MethodRunner(ABC):
    def __init__(
        self,
        project_id: str,
        solution: Solution,
        method_url: MethodUrl,
        settings: Settings,
        instance_system_factory: IProductInstanceSystemFactory,
        multiplexor_storage_factory: SafMultiplexorStorageScopeFactory,
        oidc_client: OidcClient,
        running_methods: dict[str, set[str]] | None = None,
        access_token: str | None = None,
    ) -> None:
        # Careful! the following properties need to be pickable to be run in the process pool
        self._project_id = project_id
        self._solution = solution
        self._method_url = method_url
        self._carrier: dict[str, str] = {}
        self._settings = settings
        self._instance_system_factory = instance_system_factory
        self._multiplexor_storage_factory = multiplexor_storage_factory
        self._oidc_client = oidc_client
        self._running_methods = running_methods
        self._access_token = access_token

        self._create_method_storage_scope()
        if self._multiplexor_method_storage_scope:
            self._asset_manager = AssetManager(self._multiplexor_method_storage_scope)
        self._init_data_repository()
        self._init_hps_blob_manager()

        # Write the current trace context into the carrier because the method are running in another thread
        # which doesn't share the context.
        TraceContextTextMapPropagator().inject(self._carrier)

    def _create_method_storage_scope(self) -> None:
        self._multiplexor_method_storage_scope = self._multiplexor_storage_factory.create_storage_scope(
            METHOD_CONTEXT,
        )

    def _init_data_repository(self) -> None:
        self._data_repository = None
        if self._settings.glow_data_repository_type in [DataRepositoryType.FileSystem, DataRepositoryType.Minerva]:
            self._data_repository = MinervaDataRepository(
                multiplexor=self._multiplexor_method_storage_scope,
            )

    def _init_hps_blob_manager(self) -> None:
        # Since a parametric study job can be started without configuration
        # (by setting HPS url / auth through parameters), this needs to be
        # instantiated always. Checking its existence to test the MethodRunner
        # easily.
        if self._multiplexor_method_storage_scope:
            self._hps_blob_manager = HpsBlobManager(
                multiplexor=self._multiplexor_method_storage_scope,
            )

    async def get_result(self, crud: Crud) -> MethodState:
        return await crud.get_method_state(
            self._project_id,
            self._method_url.step_name,
            self._method_url.method_name,
        )

    @abstractmethod
    async def prepare_invoke(self, crud: Crud): ...

    async def invoke(
        self,
        crud: Crud,
        background_tasks: BackgroundTasks,
        bdm_lock_id: UUID | None = None,
        solution_configuration_param: SolutionConfigParam | None = None,
        input_params: dict[str, Any] | None = None,
    ) -> Any:
        worker_pids: list[int] | None = None
        loop = asyncio.get_running_loop()
        try:
            with self.pool_executor() as pool:
                worker_pids = await loop.run_in_executor(
                    pool,
                    functools.partial(self.run_method, solution_configuration_param, input_params),
                )
        finally:
            alive_pids = [pid for pid in worker_pids if psutil.pid_exists(pid)] if worker_pids else []
            if alive_pids:
                if self._settings.glow_method_cleanup_child_procs:
                    logger.info("Cleaning up child process(es) still alive after transaction: %s", alive_pids)
                    await asyncio.to_thread(kill_pids, alive_pids, timeout=1.0)
                else:
                    logger.warning(
                        "Child process cleanup is disabled. PIDs still alive after transaction: %s",
                        alive_pids,
                    )
            if bdm_lock_id:
                # Had to create bdm_lock here because it depends on background_tasks. Otherwise, this lock would be part
                # of self, which is pickled to be sent to another process, and BackgroundTasks is not picklable.
                bdm_lock = create_bdm_db_locks(
                    project_id=self._project_id,
                    settings=self._settings,
                    storage_factory=self._multiplexor_storage_factory,
                    crud=crud,
                    background_tasks=background_tasks,
                )
                await bdm_lock.remove(bdm_lock_id)

    @property
    @abstractmethod
    def pool_executor(self) -> type[concurrent.futures.Executor]: ...

    @property
    @abstractmethod
    def http_client(self) -> httpx2.Client: ...

    @property
    @abstractmethod
    def graphql_client(self) -> GqlClientConnectionPool: ...

    @contextmanager
    def method_storage_scope(self) -> Generator[IStorageScope, None]:
        with self._multiplexor_method_storage_scope as scope:
            yield scope

    def run_method(
        self,
        solution_configuration_param: SolutionConfigParam | None = None,
        input_params: dict[str, Any] | None = None,
    ) -> list[int] | None:
        ctx = TraceContextTextMapPropagator().extract(carrier=self._carrier)
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("METHOD EXECUTION", context=ctx) as span:
            span.set_attribute("method_url", self._method_url.url)
            transaction_step_method = self._get_transaction_step_method()
            try:
                result = self._run_method(
                    transaction_step_method,
                    self.http_client,
                    self.graphql_client,
                    solution_configuration_param,
                    input_params,
                )
            except Exception as exc:
                state = self._set_method_failed(exc, span, self.http_client)
            else:
                try:
                    state = MethodState(status=MethodStatus.Completed, result=result)
                    state.model_dump_json()  # making sure the returned result is json serializable
                    self._set_method_state(state, self.http_client)
                except PydanticSerializationError as ex:
                    state = self._set_method_failed(ex, span, self.http_client)
            finally:
                if transaction_step_method._enable_termination_event:  # pyright: ignore[reportFunctionMemberAccess]
                    self._raise_method_event(
                        # the following ignore is needed because 'state' could be unbound if the second 'try' fails with
                        # an Exception that is not a PydanticSerializationError.
                        state,  # pyright: ignore[reportPossiblyUnboundVariable]
                        self.http_client,
                    )

    def _set_method_failed(self, exception: Exception, span: trace.Span, http_client: httpx2.Client) -> MethodState:
        logger.exception(str(exception)) if self._settings.glow_debug else logger.error(str(exception))
        span.record_exception(exception)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))
        message = INTERNAL_ERROR_MESSAGE
        code = 500
        stack = None
        debug = bool(self._settings.glow_debug)
        if debug:
            message = str(exception)
            stack = traceback.format_exc()
        if isinstance(exception, HTTPException):
            if exception.status_code != 500 or debug:
                # str(exception) does not capture the prefix added in subclasses from HTTPException...
                message = exception.detail
            code = exception.status_code
        method_state = MethodState(
            status=MethodStatus.Failed,
            exception_message=message,
            exception_stack=stack,
            status_code=code,
        )
        self._set_method_state(
            method_state,
            http_client,
        )
        return method_state

    def _run_method(
        self,
        transaction_step_method: Callable[..., Any],
        http_client: httpx2.Client,
        graphql_client: GqlClientConnectionPool,
        solution_configuration_param: SolutionConfigParam | None = None,
        input_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        logger.debug(f"Executing method {self._method_url.step_name}:{self._method_url.method_name}...")
        with self.method_storage_scope() as storage_scope:
            return transaction_step_method(
                project_url=self._method_url.project_url,
                solution=self._solution,
                name_of_step_containing_method=self._method_url.step_name,
                http_client=http_client,
                settings=self._settings,
                instance_system_factory=self._instance_system_factory,
                storage_scope=storage_scope,
                graphql_client=graphql_client,
                oidc_client=self._oidc_client,
                asset_manager=self._asset_manager,
                _multiplexor_storage_factory=self._multiplexor_storage_factory,
                _hps_blob_manager=self._hps_blob_manager,
                _access_token=self._access_token,
                _input_params=input_kwargs,
                _solution_configuration_param=solution_configuration_param,
                _data_repository=self._data_repository,
            )

    def _set_method_state(self, method_state: MethodState, http_client: httpx2.Client) -> None:
        # can't use model_dump() + json= payload due to UUID serialization issue.
        payload = method_state.model_dump_json()
        try:
            r = http_client.patch(self._method_url.url, content=payload, headers={"Content-Type": "application/json"})
        except Exception as e:
            raise RuntimeError(
                f"Failed to send patch to solution server via {self._method_url.url} with payload '{payload}'",
            ) from e
        if r.status_code != 200:
            raise RuntimeError(
                f"Failed to set state on solution server via {self._method_url.url} with payload '{payload}'",
            )

    def _raise_method_event(self, method_state: MethodState, http_client: httpx2.Client) -> None:
        # can't use model_dump() + json= payload due to UUID serialization issue.
        payload = method_state.model_dump_json()
        http_client.post(self._method_url.event_url, content=payload, headers={"Content-Type": "application/json"})

    def _get_transaction_step_method(self) -> Callable[..., Any]:
        step = getattr(self._solution.get_steps(), self._method_url.step_name)
        transaction_step_method = getattr(step, self._method_url.method_name)
        return transaction_step_method

    async def set_running_state(self, crud: Crud):
        method_state = MethodState(status=MethodStatus.Running)
        await crud.update_method_state(
            self._project_id,
            self._method_url.step_name,
            self._method_url.method_name,
            method_state,
            self._running_methods,
        )

    def has_entity_handles(self) -> bool:
        return self._get_transaction_step_method()._has_entity_handles(  # pyright: ignore[reportFunctionMemberAccess]
            self._method_url.step_name,
            self._solution,
        )

    def _set_http_auth_headers(self, headers: dict[str, str] | httpx2.Headers) -> None:
        if self._settings.computed_api_key:
            headers["x-api-key"] = self._settings.computed_api_key
        elif self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

    def _set_graphql_auth(self, graphql_client: GqlClientConnectionPool) -> None:
        if self._settings.computed_api_key:
            graphql_client.api_key = self._settings.computed_api_key
        elif self._access_token:
            graphql_client.access_token = self._access_token


class ProcessMethodRunner(MethodRunner):
    def __init__(
        self,
        project_id: str,
        solution: Solution,
        method_url: MethodUrl,
        settings: Settings,
        instance_system_factory: IProductInstanceSystemFactory,
        multiplexor_storage_factory: SafMultiplexorStorageScopeFactory,
        oidc_client: OidcClient,
        running_methods: dict[str, set[str]] | None = None,
        access_token: str | None = None,
    ) -> None:
        super().__init__(
            project_id=project_id,
            solution=solution,
            method_url=method_url,
            settings=settings,
            instance_system_factory=instance_system_factory,
            multiplexor_storage_factory=multiplexor_storage_factory,
            oidc_client=oidc_client,
            running_methods=running_methods,
            access_token=access_token,
        )
        self._http_client: httpx2.Client | None = None
        self._graphql_client: GqlClientConnectionPool | None = None

    @property
    def http_client(self) -> httpx2.Client:
        if self._http_client is None:
            headers: dict[str, str] = {"shared-volume": "true"}
            self._set_http_auth_headers(headers)
            self._http_client = httpx2.Client(timeout=300, transport=InjectTraceTransport(), headers=headers)
        return self._http_client

    @property
    def graphql_client(self) -> GqlClientConnectionPool:
        if self._graphql_client is None:
            api_url = self._method_url.url.split("/projects")[0]
            self._graphql_client = GqlClientConnectionPool(url=f"{api_url}/graphql", pool_size=1)
            self._set_graphql_auth(self._graphql_client)
        return self._graphql_client

    @property
    def pool_executor(self) -> type[concurrent.futures.ProcessPoolExecutor]:
        return concurrent.futures.ProcessPoolExecutor

    async def prepare_invoke(self, crud: Crud):
        await self._raise_if_running(crud)
        await self.set_running_state(crud)

    def run_method(
        self,
        solution_configuration_param: SolutionConfigParam | None = None,
        input_params: dict[str, Any] | None = None,
    ) -> list[int] | None:
        child_pids: list[int] = []
        try:
            Instrumentor.instrumentalize_process(
                GLOW_METHOD_RUNNER_SERVICE_NAME,
                self._settings,
                self._method_url.method_name,
            )
            super().run_method(solution_configuration_param, input_params)
        finally:
            self.http_client.close()
            child_pids = [c.pid for c in psutil.Process(os.getpid()).children(recursive=True)]
            log_msg = (
                "Tracking child PIDs at end of transaction: %s. "
                "Will allow them to terminate gracefully before forcing cleanup."
            )
            logger.debug(log_msg, child_pids)
        return child_pids

    async def _raise_if_running(self, crud: Crud):
        state = await crud.get_method_state(
            self._project_id,
            self._method_url.step_name,
            self._method_url.method_name,
        )
        if state.status == MethodStatus.Running:
            raise ConflictError(f"{self._method_url.method_name} is already running")


class ThreadMethodRunner(MethodRunner):
    def __init__(
        self,
        project_id: str,
        solution: Solution,
        method_url: MethodUrl,
        settings: Settings,
        instance_system_factory: IProductInstanceSystemFactory,
        http_client: httpx2.Client,
        graphql_client: GqlClientConnectionPool,
        multiplexor_storage_factory: SafMultiplexorStorageScopeFactory,
        oidc_client: OidcClient,
        running_methods: dict[str, set[str]] | None = None,
        access_token: str | None = None,
    ) -> None:
        super().__init__(
            project_id=project_id,
            solution=solution,
            method_url=method_url,
            settings=settings,
            instance_system_factory=instance_system_factory,
            multiplexor_storage_factory=multiplexor_storage_factory,
            oidc_client=oidc_client,
            running_methods=running_methods,
            access_token=access_token,
        )
        self._http_client = http_client
        self._graphql_client = graphql_client

        # We delay the injection of the auth header until here instead of in the get_http_client or get_graphql_client
        # dependencies for easier unit testing. In any case, these clients are expected to be used only here.
        self._set_http_auth_headers(self._http_client.headers)
        self._set_graphql_auth(self._graphql_client)

    async def prepare_invoke(self, crud: Crud):
        await self.set_running_state(crud)

    @property
    def pool_executor(self) -> type[concurrent.futures.ThreadPoolExecutor]:
        return concurrent.futures.ThreadPoolExecutor

    @property
    def http_client(self) -> httpx2.Client:
        return self._http_client

    @property
    def graphql_client(self) -> GqlClientConnectionPool:
        return self._graphql_client
