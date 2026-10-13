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

from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from inspect import isclass
import json
import logging
from pathlib import Path
import re
import shutil
from typing import Any, TypeVar, get_origin
import uuid

from fastapi import BackgroundTasks
from fastapi.datastructures import UploadFile
from opentelemetry import trace
from pydantic import TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from ansys.bdm.api import EntityHandle, EntityNotFoundInBlobStorageError, IAsyncStorageScope
from ansys.saf.glow._bdm.multiplexor import SafMultiplexorStorageScopeFactory
from ansys.saf.glow._bdm.storage_contexts import GC_CONTEXT, PROJECT_BOUNDARY, RESTAPI_CONTEXT
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.field_state import FieldState
from ansys.saf.glow._core.instance.iinstance_system import IProductInstanceSystem
from ansys.saf.glow._core.instance.null_system import NullSystem
from ansys.saf.glow._core.instance.recoverystate import RecoveryStateInfo
from ansys.saf.glow._core.method_status import MethodStatus
from ansys.saf.glow._core.migrations import MigrationContext
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.state_engine import compute_downstream_steps
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._crud.archive_helper import (
    parse_and_migrate_imported_project,
    unzip_archive,
)
from ansys.saf.glow._crud.bdm_helper import (
    convert_upload_file_to_handle,
    get_stream_generator,
)
from ansys.saf.glow._crud.instance_helper import delete_instance_state_directory, shutdown_instance
from ansys.saf.glow._crud.project_builder import ProjectBuilder
from ansys.saf.glow._crud.step_data_processor import StepDataProcessor
from ansys.saf.glow._hps_auth.hps_authentication_type import HpsAuthenticationType
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator
from ansys.saf.glow._hps_parametric_studies.base import HpsProject
from ansys.saf.glow._repository.abstract_repository import (
    AbstractRepositorySession,
    AbstractRepositorySessionFactory,
    HpsAuthLockSpecification,
    MethodLockSpecification,
    ProjectLockSpecification,
)
from ansys.saf.glow._server.exceptions import BadRequestError, NotFoundError, UnprocessableEntityError
from ansys.saf.glow._server.filter_parser import ParsedProjectFilter
import ansys.saf.glow._server.models as models
from ansys.saf.glow._server.models import ProjectModel
from ansys.saf.glow._server.product_instances_tracker import ProductInstancesTracker
from ansys.saf.glow._server.project_files_manager import ProjectFilesManager
from ansys.saf.glow._server.schemas import (
    CreateInstanceRequest,
    CreateProjectRequest,
    InstanceResponse,
    ListProjectResponse,
    ModifyInstanceRequest,
    ModifyProjectRequest,
    ProjectInfo,
)
from ansys.saf.glow._server.solution import SolutionService
from ansys.saf.glow._utilities.conversion import url_part_to_python_identifier

T = TypeVar("T", bound=Solution)
logger = logging.getLogger(__name__)


# TODO the following 2 functions should be moved to a GC class
@asynccontextmanager
async def _garbage_collector_storage_scope(
    storage_factory: SafMultiplexorStorageScopeFactory,
):
    # Storage scope needed for garbage collection specifically used to call
    # 'get_unreferenced_entities' and destroy()
    async with await storage_factory.create_async_storage_scope(GC_CONTEXT) as scope:
        yield scope


async def _bdm_sweep(
    storage_factory: SafMultiplexorStorageScopeFactory,
    handles: list[EntityHandle],
):
    logger.debug("Starting BDM garbage collection...")
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("bdm_garbage_collection"):
        async with _garbage_collector_storage_scope(storage_factory) as scope:
            unreferenced_entities = await scope.get_unreferenced_entities(PROJECT_BOUNDARY, handles)
            if unreferenced_entities:
                logger.debug(f"Garbage collecting {len(unreferenced_entities)} unreferenced entities...")
                await scope.destroy(*unreferenced_entities)


class Crud:
    # here we assume
    #
    # (1) that all databases we operate on have the schema defined by Base.metadata
    # and that this schema does not change dynamcially in any way
    # (2) that once a database has been initialized it will never need
    # to be reinitialized during the runtime of this OS process
    # (3) that under normal operation the OS process we're running will
    # only refer to a single database (we optimize for this)
    # (4) that under test the OS process may refer to multiple databases (but we do not need to optimize this scenario)
    # which means it is OK rerun the schema initialization code for these multiple databases)

    _the_url_of_the_last_database_that_was_initialized: str | None = None

    def __init__(
        self,
        solution_service: SolutionService,
        session_factory: AbstractRepositorySessionFactory,
    ) -> None:
        self._solution_service = solution_service
        self._session_factory = session_factory

    @asynccontextmanager
    async def get_modifying_project_lock(
        self,
        project_id: str,
    ) -> AsyncGenerator[None]:
        async with self._session_factory.get_session(
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
            modification=True,
        ):
            yield None

    @asynccontextmanager
    async def get_method_lock(
        self,
        project_id: str,
    ) -> AsyncGenerator[None]:
        async with self._session_factory.get_session(
            project_id=project_id,
            lock_spec=MethodLockSpecification(),
            modification=True,
        ):
            yield None

    @asynccontextmanager
    async def hps_auth_lock(self) -> AsyncGenerator[None]:
        async with self._session_factory.get_session(
            lock_spec=HpsAuthLockSpecification(),
        ):
            yield None

    async def get_running_methods(self, project_id: str) -> list[str]:
        async with self._session_factory.get_session() as session:
            return await session.get_running_methods(project_id)

    async def list_projects(
        self,
        page_size: int,
        page: int,
        order_by: str | None = None,
        filters: ParsedProjectFilter | None = None,
    ) -> ListProjectResponse:
        logger.info(
            "Listing projects with params: page_size=%d, page=%d, order_by=%s, filters=%s",
            page_size,
            page,
            order_by,
            filters,
        )
        async with self._session_factory.get_session() as session:
            return await session.list_projects(page_size=page_size, page=page, order_by=order_by, filters=filters)

    async def get_project_info(self, project_id: str) -> ProjectInfo:
        logger.info(f"Getting project information of: {project_id}...")
        async with self._session_factory.get_session() as session:
            return await self._get_validated_project_from_db(session, project_id)

    async def get_project_info_without_validation(self, project_id: str) -> ProjectInfo:
        logger.info(f"Getting project information of: {project_id} (without validation) ...")
        async with self._session_factory.get_session() as session:
            return await self._get_project_from_db_without_validation(session, project_id)

    async def modify_project_info(self, project_id: str, request: ModifyProjectRequest) -> ProjectInfo:
        logger.info(f"Modifying project: {project_id} with {request}...")
        # we don't supply a project_id to the session because we want to update the date modified here
        async with self._session_factory.get_session(
            project_id=project_id,
            modification=True,
            update_modification_date=False,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            await session.modify_project_info(project_id, request)
            try:
                # at some point we need to review if this really makes sense
                # this is a very heavy weight operation to do if all you are doing is changing the project name
                return await self._get_validated_project_from_db(session, project_id)
            except ValidationError as ex:
                raise UnprocessableEntityError(str(ex)) from None

    async def _get_validated_project_from_db(self, session: AbstractRepositorySession, project_id: str) -> ProjectInfo:
        # _get_project_as_dict is not fast so if this method is called frequently
        # we might want to figure out a new REST API for validating a project explicitly
        project_info, project = await session.get_project_as_dict(project_id)
        # validate that the stored project is consistent with the solution schema
        models.ProjectModel[self._solution_service.solution_type].model_validate(project, context={"mode": "from_db"})
        logger.debug(f"Project {project_id=} validated.")
        return project_info

    async def _get_project_from_db_without_validation(
        self,
        session: AbstractRepositorySession,
        project_id: str,
    ) -> ProjectInfo:
        # _get_project_as_dict is not fast so if this method is called frequently
        # we might want to figure out a new REST API for validating a project explicitly.
        project_info, _ = await session.get_project_as_dict(project_id)
        return project_info

    async def project_in_database(self, project_id: str) -> bool:
        async with self._session_factory.get_session(
            modification=False,
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            return await session.project_in_database(project_id)

    async def verify_project_exists(self, project_id: str) -> None:
        async with self._session_factory.get_session(
            modification=False,
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            project_exists = await session.project_in_database(project_id)
            if project_exists:
                return
            raise NotFoundError(f"Project '{project_id}' not found.")

    async def upgrade_project(
        self,
        project_id: str,
        project_files_manager: ProjectFilesManager,
        storage_scope_factory: SafMultiplexorStorageScopeFactory,
        settings: Settings,
    ) -> ProjectInfo:
        async with self._session_factory.get_session(
            modification=True,
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            storage_scope = storage_scope_factory.create_storage_scope(RESTAPI_CONTEXT)
            _, raw_project_definition = await session.get_project_as_dict(project_id)

            # We create an empty project_files_dir if it does not exist so that it can be used in migration
            # transformations without having to check if it exists.
            project_files_manager.create_project_files_dir(project_id)

            def construct_migration_context(values: dict[str, Any]) -> MigrationContext:
                return MigrationContext(
                    solution=values,
                    project_storage_scope=storage_scope,
                    file_manager=project_files_manager,
                    project_id=project_id,
                    settings=settings,
                )

            raw_project_definition["bdm_locks"] = []
            project_model = models.ProjectModel[self._solution_service.solution_type].model_validate_json(
                json.dumps(raw_project_definition),
                context={
                    "mode": "upgrade",
                    "default_solution": self._solution_service.default_instance,
                    "migration_context_constructor": construct_migration_context,
                    "automatic_project_migration": settings.glow_enable_automatic_project_migration,
                },
            )

            project_model.date_modified = datetime.now()

            # if (big if) the following is too slow for a given use case
            # there is obvious scope for optimization
            # which will be complex but involve updating the existing database rows rather
            # destroying then and starting again
            # having said that doing it this way makes the JSON to Relational upgrade conceptually simpler
            await session.remove_project_from_database(project_id)
            project_info = await session.build_project_in_database(
                project_model,
                project_id,
            )

            return project_info

    async def create_project(
        self,
        file_manager: ProjectFilesManager,
        solution_service: SolutionService,
        request: CreateProjectRequest,
    ) -> ProjectInfo:
        async with self._session_factory.get_session(
            modification=True,
            update_modification_date=False,
        ) as session:
            project = ProjectBuilder.build_project_model(
                request.display_name,
                solution_service,
                description=request.description,
            )
            logger.debug(f"Solution data to be saved: {project.model_dump_json()}")
            stored_project = await session.build_project_in_database(project)
            # take a row lock on the new project to ensure that its not modified
            # while we deal with the project directory
            async with self._session_factory.get_session(
                project_id=stored_project.project_id,
                lock_spec=ProjectLockSpecification(),
            ):
                file_manager.create_project_files_dir(stored_project.project_id)
                return stored_project

    async def import_project(
        self,
        project_id: str,
        project_directory: Path,
        file_manager: ProjectFilesManager,
        upload_file: UploadFile,
        tmp_path: Path,
        solution_service: SolutionService,
        display_name: str,
        project_file_manager: ProjectFilesManager,
        storage_scope_factory: SafMultiplexorStorageScopeFactory,
        settings: Settings,
    ) -> ProjectInfo:
        logger.info(f"Importing {upload_file.filename}...")

        async with self._session_factory.get_session(modification=True) as session:
            project_file = await unzip_archive(file_manager, upload_file, tmp_path, project_directory, display_name)
            try:
                project = await parse_and_migrate_imported_project(
                    project_file=project_file,
                    solution_type=solution_service.solution_type,
                    default_instance=solution_service.default_instance,
                    display_name=display_name,
                    project_file_manager=project_file_manager,
                    project_id=project_id,
                    storage_scope_factory=storage_scope_factory,
                    settings=settings,
                )
                logger.info(f"Importing as project {display_name} from {project_file}...")
                return await session.build_project_in_database(project, project_id)
            except Exception:
                logger.error(f"Failed to import project {display_name} from {project_file}")
                if project_directory.is_dir():  # noqa: ASYNC240
                    logger.info("On import exit cleaning up temporary files.")
                    shutil.rmtree(project_directory)
                raise

    def _clean_pim_information_in_imported_project(self, project: ProjectModel[T]):
        if project.instances:
            updated_instances = {}
            for step_name, step_instances in project.instances.items():
                updated_instances[step_name] = {}
                for step_instance_name, step_instance in step_instances.items():
                    instance_definition = step_instance.model_copy(
                        update={
                            "pim_name": "",
                            "name": re.sub("projects/.*/steps", f"{project.name}/steps", step_instance.name),
                        },
                    )
                    updated_instances[step_name][step_instance_name] = instance_definition
            project.instances = updated_instances

    async def get_project_as_dict(
        self,
        project_id: str,
    ) -> tuple[ProjectInfo, dict[str, Any]]:
        logger.info(f"Getting project as dict: {project_id}...")
        async with self._session_factory.get_session(
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            project_info, project_as_dict = await session.get_project_as_dict(project_id)
            return project_info, project_as_dict

    async def remove_project(
        self,
        file_manager: ProjectFilesManager,
        project_id: str,
        instance_system: IProductInstanceSystem,
        product_instances_created_by_this_process: ProductInstancesTracker,
        hps_authenticator: IHpsAuthenticator | None,
        settings: Settings,
    ):
        # TODO - correct this abstraction so that non storage details are moved to common class
        logger.info(f"Removing project: {project_id}...")
        async with self._session_factory.get_session(
            modification=True,
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            await self._stop_project_hps_jobs(session, project_id, settings, hps_authenticator)

            pim_names = await session.remove_project_from_database(project_id)

            if pim_names:
                logger.info(f"shutting down instances: {pim_names}...")
                self._shutdown_project_instances(
                    pim_names,
                    instance_system,
                    product_instances_created_by_this_process,
                    settings,
                )

            file_manager.remove_project_files_dir(project_id)

    def _shutdown_project_instances(
        self,
        pim_names: list[str],
        instance_system: IProductInstanceSystem,
        product_instances_created_by_this_process: ProductInstancesTracker,
        settings: Settings,
    ) -> None:
        if isinstance(instance_system, NullSystem):
            if pim_names:
                logger.debug(
                    "The project contains information about product instances but the product instance system is not "
                    "configured. Skipping the deletion of the product instances.",
                )
            return
        for pim_name in pim_names:
            shutdown_instance(pim_name, instance_system, settings)
            product_instances_created_by_this_process.remove_instance(pim_name)

    async def _stop_project_hps_jobs(
        self,
        session: AbstractRepositorySession,
        project_id: str,
        settings: Settings,
        hps_authenticator: IHpsAuthenticator | None,
    ) -> None:
        hps_projects: list[str] = []

        if hps_authenticator is None:
            return

        for step_name, step_model in self._solution_service.solution_type.get_steps_fields().items():
            for field_name, field_info in step_model.model_fields.items():
                field_type = field_info.annotation
                if (
                    field_type is not None
                    and isclass(field_type)
                    and get_origin(field_type) is None  # field_type is not generic
                    and issubclass(field_type, HpsProject)  # raises exceptions if field_type is generic or not class
                ):
                    step_fields = await session.get_step(project_id, step_name, step_model, [field_name])
                    field = step_fields.get(field_name)
                    if field is not None:
                        hps_project_id = field.get("hps_project_identifier")
                        if hps_project_id:
                            hps_projects.append(hps_project_id)

        if hps_projects:
            if hps_authenticator.auth_type == HpsAuthenticationType.KEYCLOAK_INTERACTIVE:
                logger.warning("HPS system un-authenticated. Cannot stop HPS jobs.")
                return
            # deliberate conditional import because REP/HPS is an optional dependency
            from ansys.saf.glow._hps_parametric_studies.system import HpsParametricStudySystem

            for hps_project_id in hps_projects:
                HpsParametricStudySystem.stop_jobs(hps_project_id, hps_authenticator, settings)

    async def get_step(
        self,
        project_id: str,
        step_name: str,
        fields: str | None = None,
    ) -> dict[str, Any]:
        fields_list = fields.split(",") if fields is not None else None
        logger.info(f"Getting step: '{step_name}' from project: '{project_id}'")
        step_type = self._solution_service.get_step_model(step_name)

        async with self._session_factory.get_session() as session:
            return await session.get_step(project_id, step_name, step_type, fields_list)

    async def get_step_data(
        self,
        project_id: str,
        step_name: str,
        datapath: str,
        storage_scope: IAsyncStorageScope,
        settings: Settings,
        substitute_urls: bool = False,
        dict_for_dir: bool = False,
    ) -> Any:
        data_processor = StepDataProcessor(
            settings,
            storage_scope,
            project_id,
            step_name,
            substitute_urls,
            dict_for_dir,
        )

        # '/' part of the field names need to be escaped '\/' in the datapath
        # because fastapi treat them as path separators otherwise
        if datapath == "":
            step_data = await self.get_step(project_id=project_id, step_name=step_name)
            return await data_processor.process_step_data_value(step_data, datapath)
        segments = datapath.split("/")
        field_name = segments.pop(0)
        field_name = url_part_to_python_identifier(field_name)  # to enable backward compatibility
        step_field = await self.get_step(project_id=project_id, step_name=step_name, fields=field_name)
        try:
            field_value = step_field[field_name]
            while any(segments):
                with suppress(ValidationError):
                    # try converting field_value to entity handle
                    field_value = EntityHandle.model_validate(field_value)
                pending, segment = data_processor.unescape_segment(segments.pop(0))
                while pending and segments:
                    # last char is escaped, so it's part of the next segment
                    pending, next_segment = data_processor.unescape_segment(segments.pop(0))
                    segment = f"{segment}/{next_segment}"
                if pending:
                    raise BadRequestError(
                        f"The datapath '{datapath}' has incorrect syntax: "
                        + "escape character without a following character.",
                    )
                if isinstance(field_value, list):
                    index = int(segment)
                    field_value = field_value[index]  # pyright: ignore[reportUnknownVariableType]
                elif isinstance(field_value, dict):
                    field_value = field_value[segment]  # pyright: ignore[reportUnknownVariableType]
                elif isinstance(field_value, EntityHandle):
                    field_value = await storage_scope.get_child(field_value, segment)
                else:
                    raise NotFoundError(f"The object referenced by the datapath cannot be found: '{datapath}'")
            return await data_processor.process_step_data_value(field_value, datapath)
        except (IndexError, ValueError, KeyError, NotADirectoryError, EntityNotFoundInBlobStorageError):
            raise NotFoundError(f"The object referenced by the datapath cannot be found: '{datapath}'") from None

    async def update_step(
        self,
        project_id: str,
        step_name: str,
        step_body: StepModel,
    ) -> StepModel:
        logger.info(f"Updating step: '{step_name}' from project: '{project_id}'")
        update_data = step_body.model_dump(exclude_unset=True)
        step_fields: dict[str, str] = {}
        for field_name, field_value in update_data.items():
            if field_name == "state":
                raise BadRequestError("Field 'state' cannot be updated.")
            field_info = step_body.model_fields[field_name]  # pyright: ignore[reportDeprecated]
            step_fields[field_name] = self._serialize_field_value(field_info, field_value)
        await self.set_fields_in_project(project_id, {step_name: step_fields})
        raw_result = await self.get_step(project_id, step_name)
        return self._solution_service.get_step_model(step_name).model_validate(raw_result)

    def _serialize_field_value(self, field_info: FieldInfo, field_value: Any) -> str:
        return (
            TypeAdapter(field_info.annotation)
            .dump_json(field_value)  # pyright: ignore[reportUnknownMemberType]
            .decode("utf-8")
        )

    async def get_method_state(
        self,
        project_id: str,
        step_name: str,
        method_name: str,
    ) -> models.MethodState:
        logger.info(f"Getting method state for {step_name}:{method_name}...")
        async with self._session_factory.get_session() as session:
            return await session.get_method_state(project_id, step_name, method_name)

    async def update_method_state(
        self,
        project_id: str,
        step_name: str,
        method_name: str,
        method_state: models.MethodState,
        running_methods: dict[str, set[str]] | None = None,
    ) -> models.MethodState:
        logger.info(f"Updating method state for {step_name}:{method_name} with {method_state}...")
        update_data = method_state.model_dump(exclude_unset=True)
        async with self._session_factory.get_session(
            modification=True,
            project_id=project_id,
        ) as session:
            result = await session.update_method_state(project_id, step_name, method_name, update_data)

        if running_methods is not None:
            self._update_running_methods(running_methods, project_id, f"{step_name}.{method_name}", method_state.status)

        return result

    def _update_running_methods(
        self,
        running_methods: dict[str, set[str]],
        project_id: str,
        method_id: str,
        method_status: MethodStatus,
    ) -> None:
        if method_status == MethodStatus.Running:
            logger.debug(f"Running method {method_id} added.")
            if project_id not in running_methods:
                running_methods[project_id] = {method_id}
            else:
                running_methods[project_id].add(method_id)
        else:
            if project_id in running_methods and method_id in running_methods[project_id]:
                logger.debug(f"Running method {method_id} removed.")
                running_methods[project_id].remove(method_id)
                if not running_methods[project_id]:
                    running_methods.pop(project_id)

    async def get_instance_state(
        self,
        project_id: str,
        step_name: str,
        instance_id: str,
        instance_url: str,
        ignore_not_found: bool = False,
    ) -> InstanceResponse[RecoveryStateInfo] | None:
        logger.info(f"Getting instance state for {step_name}: {instance_id}...")
        async with self._session_factory.get_session() as session:
            return await session.get_instance_state(
                project_id,
                step_name,
                instance_id,
                instance_url,
                ignore_not_found,
            )

    async def create_instance(
        self,
        project_id: str,
        solution_service: SolutionService,
        product_instances_created_by_this_process: ProductInstancesTracker,
        step_name: str,
        instance_id: str,
        instance_request: CreateInstanceRequest[RecoveryStateInfo],
    ) -> InstanceResponse[RecoveryStateInfo]:
        logger.info(f"Creating instance for {step_name}: {instance_id}...")
        async with self._session_factory.get_session(
            modification=True,
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            response = await session.create_instance(
                project_id,
                step_name,
                instance_id,
                instance_request,
            )

            product_instances_created_by_this_process.record_instance(
                solution_type=solution_service.solution_type,
                step_name=step_name,
                instance_id=instance_id,
                instance=response,
                project_id=project_id,
            )
            return response

    async def update_instance_state(
        self,
        project_id: str,
        solution_service: SolutionService,
        product_instances_created_by_this_process: ProductInstancesTracker,
        step_name: str,
        instance_url: str,
        instance_id: str,
        instance_state: ModifyInstanceRequest[RecoveryStateInfo],
    ) -> InstanceResponse[RecoveryStateInfo]:
        logger.info(f"Updating instance state for {step_name}: {instance_id}...")
        async with self._session_factory.get_session(
            modification=True,
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            response = await session.update_instance_state(
                project_id,
                step_name,
                instance_url,
                instance_id,
                instance_state,
            )

            product_instances_created_by_this_process.record_instance(
                solution_type=solution_service.solution_type,
                step_name=step_name,
                instance_id=instance_id,
                instance=response,
                project_id=project_id,
            )
            return response

    async def delete_instance(
        self,
        project_id: str,
        product_instances_created_by_this_process: ProductInstancesTracker,
        step_name: str,
        instance_id: str,
        instance_system: IProductInstanceSystem,
        settings: Settings,
    ) -> None:
        logger.info(f"Removing instance for {step_name}: {instance_id}...")
        instance_url = f"projects/{project_id}/steps/{step_name}/instances/{instance_id}"
        async with self._session_factory.get_session(
            project_id=project_id,
            modification=True,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            instance_state = await session.get_instance_state(
                project_id,
                step_name,
                instance_id,
                instance_url,
                ignore_not_found=True,
            )
            pim_name = await session.delete_instance_row_and_get_pim_name(project_id, step_name, instance_id)
            if pim_name is None:
                raise NotFoundError(f"Instance '{instance_id}' on Step '{step_name}' is not found.")
            shutdown_instance(pim_name, instance_system, settings)
            if instance_state is not None and instance_state.recovery_state_info is not None:
                delete_instance_state_directory(
                    settings.computed_project_files_directory,
                    project_id,
                    instance_state.recovery_state_info.product_instance_state_dirname,
                )
            product_instances_created_by_this_process.remove_instance(pim_name)

    async def get_entity_handle_field_stream(
        self,
        project_storage_scope: IAsyncStorageScope,
        project_id: str,
        step_name: str,
        field_id: str,
    ) -> Callable[[], AsyncGenerator[bytes, None]]:
        raw_handle = (await self.get_step(project_id, step_name, field_id))[field_id]
        handle = EntityHandle(**raw_handle)
        return await get_stream_generator(project_storage_scope, handle)

    async def get_entity_handle(
        self,
        project_id: str,
        step_name: str,
        datapath: str,
        storage_scope: IAsyncStorageScope,
        settings: Settings,
    ) -> EntityHandle:
        raw_handle = await self.get_step_data(project_id, step_name, datapath, storage_scope, settings)
        if isinstance(raw_handle, EntityHandle):
            return raw_handle
        try:
            return EntityHandle(**raw_handle)
        except ValidationError as e:
            raise NotFoundError(detail=str(e)) from e

    async def set_entity_handle_field_value(
        self,
        project_storage_scope: IAsyncStorageScope,
        project_id: str,
        step_id: str,
        field_id: str,
        upload_file: UploadFile,
    ) -> EntityHandle:
        handle = await convert_upload_file_to_handle(project_storage_scope, upload_file)
        await self.set_fields_in_project(project_id, {step_id: {field_id: handle.model_dump_json()}})
        return handle

    async def add_bdm_lock(
        self,
        project_id: str,
        is_internal_caller: bool = False,
    ) -> models.BdmLockModel:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("add_bdm_lock"):
            async with self._session_factory.get_session(
                project_id=project_id,
                modification=True,
                lock_spec=ProjectLockSpecification(),
            ) as session:
                logger.debug(f"Adding BDM lock to project {project_id}...")
                return await session.add_bdm_lock(project_id, is_internal_caller)

    async def get_bdm_lock(
        self,
        project_id: str,
        lock_id: uuid.UUID,
    ) -> models.BdmLockModel:
        async with self._session_factory.get_session(
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            bdm_lock = await session.get_bdm_lock(project_id, lock_id)
        return bdm_lock

    async def remove_bdm_lock(
        self,
        lock_id: uuid.UUID,
        project_id: str,
        storage_factory: SafMultiplexorStorageScopeFactory,
        background_tasks: BackgroundTasks,
    ) -> None:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("remove_bdm_lock"):
            async with self._session_factory.get_session(
                modification=True,
                project_id=project_id,
                lock_spec=ProjectLockSpecification(),
            ) as session:
                logger.debug(f"Removing BDM lock from project {project_id}...")
                handles = await session.remove_bdm_lock(lock_id, project_id)
            if handles is None:
                return  # locks still in place so don't garbage collect

            # NOTE: background task resources must be handled separately and should not depend on the resources
            # of dependencies with yield.
            # This is why a new gc storage scope is created within it.
            background_tasks.add_task(_bdm_sweep, storage_factory, handles)

    async def set_fields_in_project(self, project_id: str, steps: dict[str, dict[str, str]]) -> None:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("set_fields_in_project"):
            async with self._session_factory.get_session(
                modification=True,
                project_id=project_id,
                lock_spec=ProjectLockSpecification(),
            ) as session:
                await session.set_fields_in_project(project_id, steps)
                with tracer.start_as_current_span("set fields out of date"):
                    await self._set_downstream_fields_out_of_date(session, project_id, steps)

    async def _set_downstream_fields_out_of_date(
        self,
        session: AbstractRepositorySession,
        project_id: str,
        steps: Mapping[str, (dict[str, str] | list[str])],
    ) -> None:
        downstream_fields = compute_downstream_steps(steps, self._solution_service.default_instance.dag)
        logger.debug("Invalidating descendant fields...")
        for step_name, field_name in downstream_fields:
            await session.set_field_state(project_id, step_name, field_name, FieldState.OUTOFDATE)
