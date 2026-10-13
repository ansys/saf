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

from abc import abstractmethod
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from enum import Enum
import json
import logging
import time
from typing import Any, NoReturn, TypeVar, cast
import uuid

from opentelemetry import trace
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import delete, exists, func, insert, inspect, not_, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.field_state import FieldState
from ansys.saf.glow._core.instance.recoverystate import RecoveryStateInfo
from ansys.saf.glow._core.method_status import MethodStatus
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._crud.bdm_helper import update_opaque_identifier
from ansys.saf.glow._crud.project_builder import ProjectBuilder
from ansys.saf.glow._events.ievent_manager import EventPayload, EventSourceIdentifier
from ansys.saf.glow._repository.abstract_repository import AbstractRepositorySession, AbstractRepositorySessionFactory
from ansys.saf.glow._repository.engine import create_glow_async_engine
from ansys.saf.glow._repository.generate_project_id import generate_project_id
from ansys.saf.glow._repository.relational_mapper import (
    create_bdm_lock,
    create_instance_model,
    create_instance_response,
    create_method_state,
    create_project_info,
)
from ansys.saf.glow._repository.relational_models import (
    PROJECT_MAPPING_FIELDS,
    Base,
    BdmLock,
    Event,
    EventListener,
    EventSource,
    HpsAuth,
    Instance,
    MethodState,
    Project,
    ProjectMethodLock,
    Step,
    StepField,
)
from ansys.saf.glow._server.exceptions import BadRequestError, NotFoundError
from ansys.saf.glow._server.filter_parser import ParsedProjectFilter
import ansys.saf.glow._server.models as models
from ansys.saf.glow._server.schemas import (
    CreateInstanceRequest,
    InstanceResponse,
    ListProjectResponse,
    ModifyInstanceRequest,
    ModifyProjectRequest,
    ProjectInfo,
)
from ansys.saf.glow._server.solution import SolutionService

logger = logging.getLogger(__name__)

TTable = TypeVar("TTable", bound=Base)


class RelationalSession(AbstractRepositorySession):
    def __init__(self, session: AsyncSession, solution_service: SolutionService, settings: Settings) -> None:
        self._session = session
        self._solution_service = solution_service
        self._settings = settings
        self._project_id: str | None = None
        self._modification = False
        self._set_update_modification_date = None

    async def indicate_project_id(
        self,
        project_id: str,
    ) -> None:
        if self._project_id is not None and self._project_id != project_id:
            raise RuntimeError(
                "attempting to change project addressed by the current transaction. "
                f"Project ID {project_id} does not match the current project ID {self._project_id}.",
            )
        self._project_id = project_id

    async def indicate_modification(self) -> None:
        self._modification = True

    async def set_update_modification_date(self, update: bool):
        self._set_update_modification_date = update

    async def finalize(self) -> None:
        if (
            self._modification
            and (self._project_id is not None)
            and (self._set_update_modification_date is None or self._set_update_modification_date)
        ):
            # to ensure that this code is portable to legacy sqlite
            # we don't bother detecting if the project exists
            # we simply assume that the modification in the session
            # detected the missing project and that we wouldn't reach this code.
            # although it is harmless if it did!
            mod_time = datetime.now()
            logger.info(f"Updating project modification date {self._project_id} to {mod_time}")
            statement = update(Project).where(Project.id == self._project_id).values(date_modified=mod_time)
            await self._session.execute(statement)

        if self._modification:
            await self._session.commit()
        else:
            await self._session.rollback()

        logger.debug(f"finalized session {id(self._session)}")

    async def get_running_methods(self, project_id: str) -> list[str]:
        statement = (
            select(MethodState.method_name)
            .where(MethodState.step_id == Step.id)
            .where(Step.project_id == project_id)
            .where(MethodState.status == MethodStatus.Running)
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def list_projects(
        self,
        page_size: int,
        page: int,
        order_by: str | None = None,
        filters: ParsedProjectFilter | None = None,
    ) -> ListProjectResponse:
        filter_expr = filters.as_sqlalchemy_expr() if filters else None

        count_statement = select(func.count()).select_from(Project)
        if filter_expr is not None:
            count_statement = count_statement.where(filter_expr)

        total_projects = await self._session.scalar(count_statement) or 0
        if total_projects == 0:
            return ListProjectResponse(
                projects=[],
                current_page=1,
                total_pages=1,
                page_size=page_size,
                total_projects=0,
            )
        total_pages = total_projects // page_size + (1 if total_projects % page_size > 0 else 0)
        if page > total_pages:
            raise BadRequestError("Invalid page number")

        offset = (page - 1) * page_size
        order_expressions = self._parse_project_order_by(order_by)
        statement = select(Project).order_by(*order_expressions).offset(offset).limit(page_size)
        if filter_expr is not None:
            statement = statement.where(filter_expr)
        result = await self._session.execute(statement)

        projects = [create_project_info(project) for project in result.scalars()]
        return ListProjectResponse(
            projects=projects,
            current_page=page,
            total_pages=total_pages,
            page_size=page_size,
            total_projects=total_projects,
        )

    def _parse_project_order_by(self, order_by: str | None) -> list[Any]:
        if order_by is None or not order_by.strip():
            return [Project.date_modified.desc(), Project.id.desc()]

        order_expressions: list[Any] = []
        parsed_fields: set[str] = set()
        for field in order_by.split(","):
            parts = field.strip().split()
            field_name = parts[0].lower()
            direction = parts[1].lower() if len(parts) == 2 else "asc"
            parsed_fields.add(field_name)

            sqlalchemy_field = PROJECT_MAPPING_FIELDS[field_name]
            order_expressions.append(sqlalchemy_field.desc() if direction == "desc" else sqlalchemy_field.asc())

        if "name" not in parsed_fields:
            # Default value if no order_by is set is Project.id.desc() to make it retrocompatible with
            # the previous Portal behavior. However, if a custom ordering without name is used,
            # we default to Project.id.asc() following the guideline: https://google.aip.dev/132#ordering
            order_expressions.append(Project.id.asc())

        return order_expressions

    async def modify_project_info(
        self,
        project_id: str,
        request: ModifyProjectRequest,
    ) -> None:
        update_values: dict[str, Any] = {
            "date_modified": datetime.now(),
        }
        if request.display_name is not None:
            update_values["project_display_name"] = request.display_name
        if request.description is not None:
            update_values["description"] = request.description

        statement = update(Project).where(Project.id == project_id).values(**update_values)
        result = await self._session.execute(statement)
        if result.rowcount == 0:  # pyright: ignore
            await self._raise_response_to_missing_project(project_id)

    async def project_in_database(self, project_id: str) -> bool:
        project = await self._get_project(project_id)
        return project is not None

    async def get_project_as_dict(
        self,
        project_id: str,
    ) -> tuple[models.ProjectInfo, dict[str, Any]]:
        project = await self._get_project(project_id)
        if project is None:
            await self._raise_response_to_missing_project(project_id)

        project_info = create_project_info(project)
        project_as_dict = project_info.model_dump(mode="json")
        solution = {}

        statement = (
            select(Step.name, StepField)
            .join(StepField, StepField.step_id == Step.id, isouter=True)  # Outer join includes steps without fields
            .where(Step.project_id == project_id)
        )
        result = await self._session.execute(statement)
        steps: dict[str, dict[str, Any]] = {}
        for step_name, step_field in result.all():
            if step_name not in steps:
                steps[step_name] = {"state": {}}
            if step_field:
                steps[step_name][step_field.name] = step_field.value
                steps[step_name]["state"][step_field.name] = step_field.state
        solution["display_name"] = project.solution_display_name
        solution["version"] = project.solution_schema_version
        solution["steps"] = steps

        statement = (
            select(Step.name, MethodState).where(Step.project_id == project_id).where(MethodState.step_id == Step.id)
        )
        result = await self._session.execute(statement)

        method_states: dict[str, dict[str, dict[str, Any]]] = {}
        for step_name, method_state in result.all():
            step_method_state = method_states.get(step_name)
            if step_method_state is None:
                step_method_state = {}
                method_states[step_name] = step_method_state
            step_method_state[method_state.method_name] = create_method_state(method_state).model_dump(
                mode="json",
            )

        statement = select(Step.name, Instance).where(Step.project_id == project_id).where(Instance.step_id == Step.id)
        result = await self._session.execute(statement)

        instances: dict[str, dict[str, dict[str, Any]]] = {}
        for step_name, instance in result.all():
            step_instances = instances.get(step_name)
            if step_instances is None:
                step_instances = {}
                instances[step_name] = step_instances
            step_instances[instance.name] = create_instance_model(
                f"projects/{project_id}/steps/{step_name}/instances/{instance.name}",
                instance,
            ).model_dump(mode="json")

        statement = select(BdmLock).where(BdmLock.project_id == project_id)
        result = await self._session.execute(statement)
        bdm_locks = [create_bdm_lock(lock) for lock in result.scalars().all()]

        project_as_dict["method_states"] = method_states
        project_as_dict["instances"] = instances
        project_as_dict["bdm_locks"] = bdm_locks
        project_as_dict["schema_version"] = project.glow_schema_version
        project_as_dict["solution"] = solution
        project_as_dict["display_name"] = project.project_display_name
        project_as_dict["solution_name"] = self._solution_service.solution_type.__name__

        return (project_info, project_as_dict)

    async def _get_project(self, project_id: str):
        statement = select(Project).where(Project.id == project_id)
        result = await self._session.scalars(statement)
        project = result.first()
        return project

    async def build_project_in_database(
        self,
        project: models.ProjectModel[Solution],
        project_id: str | None = None,
    ) -> ProjectInfo:
        project_id = project_id or generate_project_id()

        logger.info(f"Creating project {project_id} with {self._solution_service.solution_type=}")

        project = update_opaque_identifier(project, project_id)

        logger.info(f"Creating project {project.display_name} with {project.date_created=}")

        # move this mapping to a mapping class and reuse elsewhere
        project_in_database = Project(
            id=project_id,
            date_created=project.date_created,
            date_modified=project.date_modified,
            project_display_name=project.display_name,
            description=project.description,
            solution_display_name=project.solution.display_name,
            glow_schema_version=project.schema_version,
            solution_schema_version=project.solution.version,
        )
        self._session.add(project_in_database)
        self._session.add(ProjectMethodLock(project_id=project_id))
        solution = project.solution
        for step_name in self._solution_service.solution_type.get_steps_fields():
            self._build_step_in_database(project, project_in_database, solution, step_name)

        for lock in project.bdm_locks:
            lock_in_database = BdmLock(external_id=str(lock.id), expiration_date=lock.expiration_date)
            project_in_database.bdm_locks.append(lock_in_database)

        return create_project_info(project_in_database)

    def _build_step_in_database(
        self,
        project: models.ProjectModel[Solution],
        project_in_database: Project,
        solution: Solution,
        step_name: str,
    ):
        step_in_database = Step(name=step_name)
        step = cast("StepModel", getattr(solution.get_steps(), step_name))

        for field_name in step.model_fields:  # pyright: ignore[reportDeprecated]
            if field_name != "state":
                field_in_database = StepField(**self._get_field_values(solution, step_name, field_name))
                step_in_database.step_fields.append(field_in_database)

        if step_name in project.method_states:
            for method_name, method_state in project.method_states[step_name].items():
                method_state_in_database = MethodState(
                    method_name=method_name,
                    status=method_state.status,
                    result=self._convert_to_json_object(method_state.result),
                    status_code=method_state.status_code,
                    exception_message=method_state.exception_message,
                    exception_stack=method_state.exception_stack,
                )
                step_in_database.method_states.append(method_state_in_database)

        if step_name in project.instances:
            for instance_name, instance in project.instances[step_name].items():
                instance_in_database = Instance(
                    name=instance_name,
                    pim_name="",
                    product_version=instance.product_version,
                    service_name=instance.service_name,
                    max_execution_time=instance.max_execution_time,
                    recovery_state_info=self._convert_to_json_object(instance.recovery_state_info),
                )
                step_in_database.instances.append(instance_in_database)

        project_in_database.steps.append(step_in_database)

    async def get_step(
        self,
        project_id: str,
        step_name: str,
        step_type: type[StepModel],
        fields_list: list[str] | None = None,
    ) -> dict[str, Any]:
        step_dump: dict[str, Any] = {}
        core_statement = (
            select(StepField.name, StepField.value)
            .where(StepField.step_id == Step.id)
            .where(Step.project_id == project_id)
            .where(Step.name == step_name)
        )
        statement = core_statement if fields_list is None else core_statement.where(StepField.name.in_(fields_list))
        fields_in_database = await self._session.execute(statement)
        for field in fields_in_database:
            field_name = field[0]
            if step_type.model_fields.get(field_name) is not None:
                step_dump[field_name] = field[1]
        if fields_list is None or "state" in fields_list:
            statement = (
                select(StepField.name, StepField.state)
                .where(StepField.step_id == Step.id)
                .where(Step.project_id == project_id)
                .where(Step.name == step_name)
            )
            field_states = await self._session.execute(statement)
            states = {f[0]: f[1] for f in field_states if step_type.model_fields.get(f[0]) is not None}
            step_dump["state"] = states
        return step_dump

    async def get_method_state(
        self,
        project_id: str,
        step_name: str,
        method_name: str,
    ) -> models.MethodState:
        statement = (
            select(MethodState)
            .where(MethodState.step_id == Step.id)
            .where(Step.project_id == project_id)
            .where(Step.name == step_name)
            .where(MethodState.method_name == method_name)
        )
        result = await self._session.scalars(statement)
        method_state = result.first()
        if method_state is None:
            # the following check is perhaps redundant - from a diagnositic perspective its good to retain it
            await self._check_project(self._session, project_id)
            # assume that this has come from a route derived from the solution definition
            # not further check required
            return models.MethodState(status=MethodStatus.RunRequired)
        return create_method_state(method_state)

    async def update_method_state(
        self,
        project_id: str,
        step_name: str,
        method_name: str,
        update_data: dict[str, Any],
    ) -> models.MethodState:
        updated_method_state = await self._update_or_add_row(
            MethodState,
            project_id,
            step_name,
            MethodState.method_name,
            method_name,
            "method_name",
            update_data,
        )
        return create_method_state(updated_method_state)

    async def set_field_state(
        self,
        project_id: str,
        step_name: str,
        field_name: str,
        state: FieldState,
    ) -> None:
        await self._update_or_add_row(
            StepField,
            project_id,
            step_name,
            StepField.name,
            field_name,
            "name",
            values={"state": state},
            default_values=lambda: self._get_field_values(
                self._solution_service.default_instance,
                step_name,
                field_name,
            ),
            fetch_row=False,
        )

    async def get_instance_state(
        self,
        project_id: str,
        step_name: str,
        instance_id: str,
        instance_url: str,
        ignore_not_found: bool = False,
    ) -> InstanceResponse[RecoveryStateInfo] | None:
        statement = (
            select(Instance)
            .where(Instance.step_id == Step.id)
            .where(Step.project_id == project_id)
            .where(Step.name == step_name)
            .where(Instance.name == instance_id)
        )
        result = await self._session.scalars(statement)
        instance = result.first()
        if instance is None:
            if ignore_not_found:
                return
            raise NotFoundError(f"Instance '{instance_id}' on Step '{step_name}' is not found.")
        return create_instance_response(
            instance_url,
            instance,
        )

    async def create_instance(
        self,
        project_id: str,
        step_name: str,
        instance_id: str,
        instance_request: CreateInstanceRequest[RecoveryStateInfo],
    ) -> InstanceResponse[RecoveryStateInfo]:
        instance = await self._update_or_add_row(
            Instance,
            project_id,
            step_name,
            Instance.name,
            instance_id,
            "name",
            values=instance_request.model_dump(mode="json"),
        )

        response = create_instance_response(
            instance_request.name,
            instance,
        )

        return response

    async def update_instance_state(
        self,
        project_id: str,
        step_name: str,
        instance_url: str,
        instance_id: str,
        instance_state: ModifyInstanceRequest[RecoveryStateInfo],
    ) -> InstanceResponse[RecoveryStateInfo]:
        instance_state_dict = instance_state.model_dump(mode="json", exclude_unset=True)
        keys = list(instance_state_dict.keys())
        for key in keys:
            if instance_state_dict[key] is None:
                del instance_state_dict[key]

        if len(instance_state_dict) == 0:
            return await self.get_instance_state(  # pyright: ignore[reportReturnType]
                project_id,
                step_name,
                instance_id,
                instance_url,
            )
        else:
            instance = await self._update_table_row(
                Instance,
                project_id,
                step_name,
                Instance.name,
                instance_id,
                instance_state_dict,
            )
            if instance is None:
                raise NotFoundError(f"Instance '{instance_id}' on Step '{step_name}' is not found.")

            response = create_instance_response(
                instance_url,
                instance,
            )

            return response

    async def add_bdm_lock(
        self,
        project_id: str,
        is_internal_caller: bool = False,
    ) -> models.BdmLockModel:
        tracer = trace.get_tracer(__name__)
        # called from an external client: let's set an expiration date to the bdm lock (1 day by default)
        expiration_date = datetime.now(UTC) + timedelta(days=1) if not is_internal_caller else None
        bdm_lock = models.BdmLockModel(expiration_date=expiration_date)

        with tracer.start_as_current_span("insert bdm lock"):
            project_present = await self.insert_bdm_table_row(project_id, bdm_lock)
            if not project_present:
                await self._raise_response_to_missing_project(project_id)
        return bdm_lock

    async def get_bdm_lock(
        self,
        project_id: str,
        lock_id: uuid.UUID,
    ) -> models.BdmLockModel:
        lock_in_database = await self._session.scalar(
            select(BdmLock).where(BdmLock.external_id == str(lock_id)).where(BdmLock.project_id == project_id),
        )
        if lock_in_database is None:
            raise NotFoundError(f"Bdm lock '{lock_id}' is not found.")
        # create the result model (not anything in database!)
        bdm_lock = create_bdm_lock(lock_in_database)
        return bdm_lock

    async def remove_expired_bdm_locks(self, project_id: str | None = None) -> None:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("remove expired bdm locks"):
            now = datetime.now(UTC)
            statement = (
                delete(BdmLock).where(BdmLock.expiration_date.is_not(None)).where(BdmLock.expiration_date <= now)
            )

            if project_id is not None:
                statement = statement.where(BdmLock.project_id == project_id)

            await self._session.execute(statement)

    async def remove_bdm_lock(
        self,
        lock_id: uuid.UUID,
        project_id: str,
    ) -> list[EntityHandle] | None:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("delete bdm lock entry"):
            statement = (
                delete(BdmLock).where(BdmLock.external_id == str(lock_id)).where(BdmLock.project_id == project_id)
            )
            result = await self._session.execute(statement)
            if result.rowcount == 0:  # pyright: ignore
                raise NotFoundError(f"Bdm lock '{lock_id}' is not found.")

        await self.remove_expired_bdm_locks(project_id)

        # are any bdm locks left?
        with tracer.start_as_current_span("query for bdm locks"):
            statement = select(1).where(select(BdmLock).where(BdmLock.project_id == project_id).exists())
            lock_in_database = await self._session.scalar(statement)
            if lock_in_database is not None:
                return None

        # compute entity handles in project
        with tracer.start_as_current_span("query for fields with entity handles"):
            statement = (
                select(Step.name, StepField.name, StepField.value)
                .where(Step.project_id == project_id)
                .where(StepField.step_id == Step.id)
                .where(StepField.contains_entity_handles)
            )
            fields = await self._session.execute(statement)

        tmp_live_handle_project = ProjectBuilder.build_project_model("live_handle_tmp_project", self._solution_service)
        for step_name, field_name, field_value in fields:
            step = getattr(tmp_live_handle_project.solution.get_steps(), step_name)
            setattr(step, field_name, field_value)

        with tracer.start_as_current_span("query for instances"):
            statement = (
                select(Step.name, Instance).where(Step.project_id == project_id).where(Instance.step_id == Step.id)
            )
            instances = await self._session.execute(statement)

        for step_name, instance in instances:
            tmp_live_handle_project.instances[step_name] = {
                instance.name: create_instance_model(
                    f"projects/{project_id}/steps/{step_name}/instances/{instance.name}",
                    instance,
                ),
            }

        return tmp_live_handle_project.collect_live_handles()

    async def set_fields_in_project(
        self,
        project_id: str,
        steps: dict[str, dict[str, str]],
    ) -> None:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("store field values"):
            for step_name, step_data in steps.items():
                for field_name, field_value_json_str in step_data.items():
                    # important - the route here can be via graphql which doesn't validate the inputs
                    # hence this validation step. The validation is done without fetching updated values for the rest of
                    # step. Therefore, validation that relies on other fields is unsupported. Note
                    # that the validation is still executed but with the default values for the rest of fields.
                    self._validate_field_value(step_name, field_name, field_value_json_str)

                    await self._update_or_add_row(
                        StepField,
                        project_id,
                        step_name,
                        StepField.name,
                        field_name,
                        "name",
                        values={
                            "value": json.loads(field_value_json_str),
                            "state": FieldState.UPTODATE,
                            "name": field_name,
                        },
                        fetch_row=False,
                    )

    async def _get_or_create_event_source(self, event_source_identifier: EventSourceIdentifier) -> int:
        """Fetches an existing event source for the given step or creates a new one."""
        project_id = event_source_identifier.project_id
        step_name = event_source_identifier.step_name
        stream_name = event_source_identifier.stream_name
        statement = (
            select(EventSource.id)
            .where(Step.project_id == project_id)
            .where(Step.name == step_name)
            .where(EventSource.step_id == Step.id)
            .where(EventSource.name == stream_name)
        )
        event_sources = await self._session.execute(statement)
        row = event_sources.first()
        if row is None:
            # create event source
            self._solution_service.get_step_model(step_name)  # validate step name
            step_id = await self._get_or_create_step(project_id, step_name)
            event_source_id = await self._session.scalar(
                insert(EventSource).values(step_id=step_id, name=stream_name).returning(EventSource.id),
            )
            if event_source_id is None:
                raise RuntimeError("Failed to create event source.")
            return event_source_id

        return row.id

    async def create_event_listener(self, event_source_identifier: EventSourceIdentifier) -> str:
        """Creates an event listener for the caller to receive events. Returns the listener ID."""

        event_source_id = await self._get_or_create_event_source(event_source_identifier)

        # get id of last event for this event source
        statement = select(func.max(Event.id)).where(Event.event_source_id == event_source_id)
        latest_event_id = await self._session.scalar(statement)

        # create the event listener
        event_listener_id = await self._session.scalar(
            insert(EventListener)
            .values(
                event_source_id=event_source_id,
                expiration=self._get_expiration_time(),
                last_fetched_event_id=latest_event_id,
            )
            .returning(EventListener.id),
        )
        if event_listener_id is None:
            raise RuntimeError("Failed to create event listener.")

        logger.debug(
            f"created event listener {event_listener_id} stream: {event_source_identifier.stream_name} "
            f"step: {event_source_identifier.step_name} project: {event_source_identifier.project_id}",
        )

        return str(event_listener_id)

    def _get_expiration_time(self) -> int:
        # 1_000_000_000 nanoseconds == 1 second
        # Keep event listeners alive for 100× the configured poll interval.
        # this should only affect event listeners created by a GLOW process process that crashes
        # or by a an event polling loop that crashes in some unexpected way.
        # The default poll interval is 1 so that the default expiration time is 100 seconds.
        return time.time_ns() + (int(self._settings.glow_ws_event_poll_interval * 100) * 1_000_000_000)

    async def store_event(self, event_source_identifier: EventSourceIdentifier, event: EventPayload) -> None:
        """Stores an event for transmission to listeners"""
        event_source_id = await self._get_or_create_event_source(event_source_identifier)
        self._session.add(Event(event_source_id=event_source_id, payload=json.dumps(event)))
        await self._delete_expired_event_data()

    async def _convert_listener_id(self, listener_id: str) -> int:
        try:
            event_listener_id = int(listener_id)
        except ValueError as e:
            raise BadRequestError("Invalid listener ID") from e
        return event_listener_id

    async def get_new_events_and_purge_queue(self, listener_id: str) -> None | list[EventPayload]:
        """fetches all events that have not been processed by this listener

        Returns:
            None if the event source no longer exists, otherwise a list of event payloads
        """

        # In case you are wondering if _tuple is private to SQLAlchemy: it isn't.  According to the documentation:
        # "The Row._tuple method supersedes the previous Row.tuple method, which is now underscored to avoid name
        # conflicts with column names in the same way as other named-tuple methods on Row."

        # fetch listener last_fetched_event_id & event_source_id

        event_listener_id = await self._convert_listener_id(listener_id)
        query = select(EventListener.last_fetched_event_id, EventListener.event_source_id).where(
            EventListener.id == event_listener_id,
        )
        result = await self._session.execute(query)
        event_listener_row = result.first()
        if event_listener_row is None:
            # this happens when the project is deleted
            logger.debug(f"event listener {event_listener_id} not found")
            return None
        last_fetched_event_id, event_source_id = event_listener_row._tuple()  # type: ignore

        # get the new events
        if last_fetched_event_id is None:
            query = select(Event.payload, Event.id).where(Event.event_source_id == event_source_id).order_by(Event.id)
        else:
            query = (
                select(Event.payload, Event.id)
                .where(Event.id > last_fetched_event_id)
                .where(Event.event_source_id == event_source_id)
                .order_by(Event.id)
            )
        result = await self._session.execute(query)
        results = result.all()
        new_events = [json.loads(row._tuple()[0]) for row in results]  # type: ignore

        # update the event listener (we need to update the expiration even if no events were returned)
        max_event_id = results[-1]._tuple()[1] if results else last_fetched_event_id  # type: ignore
        action = (
            update(EventListener)
            .where(EventListener.id == event_listener_id)
            .values(last_fetched_event_id=max_event_id, expiration=self._get_expiration_time())
        )
        await self._session.execute(action)

        # remove processed events
        await self._delete_expired_event_data()
        return new_events

    async def destroy_event_listener(self, listener_id: str) -> None:
        """Cleans up any resources used by this listener"""
        logger.debug(f"destroying event listener {listener_id}")

        event_listener_id = await self._convert_listener_id(listener_id)
        action = (
            delete(EventListener).where(EventListener.id == event_listener_id).execution_options(is_delete_using=True)
        )
        await self._session.execute(action)
        await self._delete_expired_event_data()
        await self._log_event_row_counts_on_debug("after destroying event listener")

    async def _log_event_row_counts_on_debug(self, context: str) -> None:
        if logger.isEnabledFor(logging.DEBUG):
            event_count = await self._session.scalar(select(func.count()).select_from(Event))
            event_listener_count = await self._session.scalar(select(func.count()).select_from(EventListener))
            logger.debug(f"Event row count: {event_count} - {context}")
            logger.debug(f"EventListener row count: {event_listener_count} - {context}")

    async def _log_event_listeners_for_project_delete_on_debug(self, project_id: str) -> None:
        if logger.isEnabledFor(logging.DEBUG):
            event_listener_query = (
                select(EventListener.id)
                .where(EventListener.event_source_id == EventSource.id)
                .where(EventSource.step_id == Step.id)
                .where(Step.project_id == project_id)
            )

            result = await self._session.execute(event_listener_query)
            event_listener_ids = [i._tuple()[0] for i in result.all()]  # type: ignore
            for listener_id in event_listener_ids:
                logger.debug(f"deleting event listener {listener_id} on delete of project {project_id}")

    async def _delete_expired_event_data(self) -> None:
        current_time = time.time_ns()

        if logger.isEnabledFor(logging.DEBUG):
            query = select(EventListener.id).where(EventListener.expiration < current_time)
            expired_event_listener_ids = [i._tuple()[0] for i in (await self._session.execute(query)).all()]  # type: ignore
            for listener_id in expired_event_listener_ids:
                logger.debug(f"deleting expired event listener {listener_id}")

            prior_event_count_on_debug = await self._session.scalar(select(func.count()).select_from(Event)) or 0
        else:
            prior_event_count_on_debug = 0

        # delete any expired listeners (the expectation is that this will only the remains of a server crash)
        action = (
            delete(EventListener).where(EventListener.expiration < current_time).execution_options(is_delete_using=True)
        )
        await self._session.execute(action)

        # delete any events that will never be passed to a listener

        # the following is not super ideal: its possibly
        # faster to use bulk sql operations but you'll probably need to
        # relax the foreign key constraints to do that

        events_to_be_deleted_query = select(Event.id).where(
            Event.id
            <= select(func.min(func.coalesce(EventListener.last_fetched_event_id, -1)))
            .where(
                EventListener.event_source_id == Event.event_source_id,
            )
            .scalar_subquery(),
        )
        events_to_be_deleted = await self._session.execute(events_to_be_deleted_query)

        for event_to_be_deleted in events_to_be_deleted.all():
            (event_to_be_deleted_id,) = event_to_be_deleted._tuple()  # type: ignore
            update_statement = (
                update(EventListener)
                .where(EventListener.last_fetched_event_id == event_to_be_deleted_id)
                .values(last_fetched_event_id=None)
            )
            await self._session.execute(update_statement)
            delete_statement = delete(Event).where(Event.id == event_to_be_deleted_id)
            await self._session.execute(delete_statement)

        delete_events_with_no_listeners_statement = delete(Event).where(
            not_(exists().where(EventListener.event_source_id == Event.event_source_id)),
        )
        await self._session.execute(delete_events_with_no_listeners_statement)

        if logger.isEnabledFor(logging.DEBUG):
            post_event_count_on_debug = await self._session.scalar(select(func.count()).select_from(Event)) or 0
            if prior_event_count_on_debug > post_event_count_on_debug:
                logger.debug(
                    f"Event row count reduced to {post_event_count_on_debug} from {prior_event_count_on_debug}",
                )

    @abstractmethod
    async def insert_bdm_table_row(self, project_id: str, bdm_lock: models.BdmLockModel) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def release_locks(self) -> None:
        raise NotImplementedError()

    async def _raise_response_to_missing_project(self, project_id: str) -> NoReturn:
        raise NotFoundError(f"Project '{project_id}' not found.")

    async def _check_project(self, session: AsyncSession, project_id: str) -> None:
        statement = select(1).where(Project.id == project_id)
        result = await session.scalar(statement)
        if result is None:
            await self._raise_response_to_missing_project(project_id)

    def _convert_to_json_object(self, value: Any) -> Any:
        return value.model_dump(mode="json") if isinstance(value, BaseModel) else value

    def _get_step(self, solution: Solution, step_name: str) -> StepModel:
        steps = solution.get_steps()
        step = getattr(steps, step_name)
        return cast("StepModel", step)

    def _get_field_values(self, solution: Solution, step_name: str, field_name: str) -> dict[str, Any]:
        step = self._get_step(solution, step_name)
        field_value = getattr(step, field_name)
        field_info = step.model_fields[field_name]  # pyright: ignore[reportDeprecated]
        if field_name in step.state:
            state = step.state[field_name]
        else:
            state = FieldState.OUTOFDATE
            logger.warning(f"Field '{field_name}' is missing state on '{step_name}' when building project.")

        step_type_wrapper = step._entity_handle_fields  # pyright: ignore[reportPrivateUsage]

        return {
            "name": field_name,
            "value": TypeAdapter(field_info.annotation).dump_python(  # pyright: ignore[reportUnknownMemberType]
                field_value,
                mode="json",
            ),
            "state": state,
            "contains_entity_handles": step_type_wrapper.field_has_handles(field_name),
        }

    def _validate_field_value(self, step_name: str, field_name: str, field_value_json_str: str) -> None:
        default_step = self._get_step(self._solution_service.default_instance, step_name)
        complete_step_data = default_step.model_dump(mode="json")

        self._validate_field(step_name, field_name)  # check field exists
        complete_step_data[field_name] = json.loads(field_value_json_str)

        TypeAdapter(self._solution_service.get_step_model(step_name)).validate_python(complete_step_data)

    def _validate_field(self, step_name: str, field_name: str):
        step_type = self._solution_service.get_step_model(step_name)
        field_info = step_type.model_fields.get(field_name)
        if field_info is None:
            raise BadRequestError(f"Field '{field_name}' not found in step '{step_name}'.")
        return field_info

    def _query_for_step_id(self, project_id: str, step_name: str):
        return select(Step.id).where(Step.project_id == project_id).where(Step.name == step_name)

    async def _update_or_add_row(
        self,
        table: type[TTable],
        project_id: str,
        step_name: str,
        name_attribute: InstrumentedAttribute[str],
        name_attribute_value: str,
        name_attribute_name: str,
        values: dict[str, Any],
        default_values: Callable[[], dict[str, Any]] | None = None,
        fetch_row: bool = True,
    ) -> TTable:
        """updates or creates row in table which has foreign key to step"""
        # TODO - we assume that the table has a column called step_id
        # it might be possible to refactor a subtype of Base that has a step id field...
        updated_state = await self._update_table_row(
            table,
            project_id,
            step_name,
            name_attribute,
            name_attribute_value,
            values,
            fetch_row,
        )
        if updated_state is None:
            # there is no row to be updated

            # This branch of execution is not optimized because we are assuming updates are much more common.
            # In most cases we only execute this code if we've using a new solution schema
            # and have not migrated the project.
            # One exception is instance rows which are created on the fly here.
            # The following code uses several sql queries to do an insert. It is probably possible
            # to do this in less steps but that is more complex, see add dbm lock for an example.
            # Optimization probably will require the use of table specific code instead of this method.
            step_id = await self._get_or_create_step(project_id, step_name)

            values["step_id"] = step_id
            values[name_attribute_name] = name_attribute_value
            if default_values is not None:
                default_values_dict = default_values()
                for key, value in default_values_dict.items():
                    if key not in values:
                        values[key] = value
            updated_state = table(**values)
            # schedule insert
            self._session.add(updated_state)

        return updated_state

    async def _get_or_create_step(self, project_id: str, step_name: str) -> int:
        # this method doesn't validate the step name in some contexts this is not required
        # because the FastAPI route enforces it...
        query_for_step_id = self._query_for_step_id(project_id, step_name)
        step_id = await self._session.scalar(query_for_step_id)
        if step_id is None:
            await self._check_project(self._session, project_id)

            step_id = await self._insert_step_row(project_id, step_name)
            if step_id is None:
                raise RuntimeError("Failed to insert step.")
        return step_id

    def _create_cast_for_insert(self, k: str, v: Any) -> str:
        if isinstance(v, Enum):
            return f"'{v.name}'"
        if isinstance(v, str):
            return f"CAST(:{k} AS VARCHAR)"
        return f":{k}"

    async def _insert_step_row(self, project_id: str, step_name: str) -> int | None:
        return await self._session.scalar(
            insert(Step).values(project_id=project_id, name=step_name).returning(Step.id),
        )

    async def _update_table_row(
        self,
        table: type[TTable],
        project_id: str,
        step_name: str,
        name_attribute: InstrumentedAttribute[str],
        name_attribute_value: str,
        values: dict[str, Any],
        fetch_row: bool = True,
    ) -> TTable | None:
        """Update a row in a table or return None if the row does not exist
        fetch_row parameter is used to determine if the row should be returned or not as an optimization"""
        query_for_step_id = self._query_for_step_id(project_id, step_name)
        statement = (
            update(table)
            .where(table.step_id == query_for_step_id.scalar_subquery())  # type: ignore
            .where(name_attribute == name_attribute_value)
            .values(**values)
            .returning(table if fetch_row else 1)
        )
        result = await self._session.scalar(statement)
        if result is None:
            return None  # indicates that the row was not found
        if fetch_row:
            return result
        return table()  # empty placeholder


class RelationalSessionFactory(AbstractRepositorySessionFactory):
    _the_url_of_the_last_database_that_was_initialized = None

    def __init__(self, database_url: str) -> None:
        super().__init__()
        self._database_url = database_url

    async def _add_projects_description_column(self, engine: AsyncEngine) -> None:
        async with engine.begin() as conn:

            def has_description_column(sync_conn: Any) -> bool:
                inspector = inspect(sync_conn)
                return any(column["name"] == "description" for column in inspector.get_columns("projects"))

            if not await conn.run_sync(has_description_column):
                try:
                    await conn.execute(text("ALTER TABLE projects ADD COLUMN description VARCHAR DEFAULT ''"))
                except Exception:
                    # Another process may have added the column concurrently.
                    if not await conn.run_sync(has_description_column):
                        raise
                await conn.execute(text("UPDATE projects SET description = '' WHERE description IS NULL"))

    async def _populate_lock_tables(self, engine: AsyncEngine) -> None:
        factory = async_sessionmaker(engine)
        async with factory() as session:
            try:
                project_method_statement = insert(ProjectMethodLock).from_select(
                    ["project_id"],
                    select(Project.id).where(
                        ~exists(select(ProjectMethodLock.id).where(ProjectMethodLock.project_id == Project.id)),
                    ),
                )
                await session.execute(project_method_statement)
                hps_auth_statement = insert(HpsAuth).from_select(["id"], select(1).where(~exists(select(HpsAuth.id))))
                await session.execute(hps_auth_statement)
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()

    @asynccontextmanager
    async def get_relational_session(
        self,
        session_constructor: Callable[[AsyncSession], RelationalSession],
    ) -> AsyncGenerator[RelationalSession]:
        engine = create_glow_async_engine(
            self._database_url,
            json_serializer=json.dumps,
        )  # use echo=True to get verbose output on console, needs more investigation

        # this is an optimization to avoid having to rerun the schema initialization code
        # on a database that's already been initialized
        if self._the_url_of_the_last_database_that_was_initialized != self._database_url:
            logger.debug(f"Initializing database at {self._database_url}")
            try:
                async with engine.begin() as conn:
                    # TODO - add proper schema migration see https://alembic.sqlalchemy.org/en/latest/
                    # the following operation is assumed to be slow or at least
                    # not to be run on every database request
                    # we assume it is idempotent and handles concurrency
                    await conn.run_sync(Base.metadata.create_all)
            except OperationalError as exc:
                # a concurrent request may have created the schema first
                if "already exists" not in str(exc.orig).lower():
                    raise
            await self._add_projects_description_column(engine)  # TODO: Remove once all solutions use GLOW > 2.0
            await self._populate_lock_tables(engine)
            # set on the class, not the instance, so the value survives the per-request factory
            RelationalSessionFactory._the_url_of_the_last_database_that_was_initialized = self._database_url

        factory = async_sessionmaker(engine)
        async with factory() as session:
            try:
                session.info["engine"] = engine
                relational_session = session_constructor(session)
                try:
                    yield relational_session
                    await relational_session.finalize()
                finally:
                    await relational_session.release_locks()

            except Exception:
                await session.rollback()
                raise
            finally:
                await engine.dispose()
