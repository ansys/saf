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

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from pydantic import PostgresDsn
from pydantic_core import MultiHostUrl
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._repository.abstract_repository import AbstractRepositorySession
from ansys.saf.glow._repository.relational import RelationalSession, RelationalSessionFactory
from ansys.saf.glow._repository.relational_models import (
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
from ansys.saf.glow._server.exceptions import NotFoundError
import ansys.saf.glow._server.models as models
from ansys.saf.glow._server.solution import SolutionService

logger = logging.getLogger(__name__)


class PostgresqlSession(RelationalSession):
    def __init__(self, session: AsyncSession, solution_service: SolutionService, settings: Settings) -> None:
        super().__init__(session, solution_service, settings)
        logger.debug(f"created postgres session {id(self._session)}")

    async def release_locks(self) -> None:
        # postgresql locks via row locks so these are auomatically released at the end of a transaction
        # so this method do nothing
        pass

    async def acquire_project_lock(self) -> None:
        if self._project_id is None:
            raise ValueError("attempting to acquire project lock but no project has been specified")
        # we don't assume the project row is in place instead we assume that concurrent
        # transaction can't occur until the row is in place and the project id exposed via the API
        query = select(Project.id).where(Project.id == self._project_id).with_for_update()
        logger.debug(f"Acquiring lock for project {self._project_id} for session {id(self._session)}")
        await self._session.execute(query)
        logger.debug(f"Acquired lock for project {self._project_id} for session {id(self._session)}")

    async def acquire_hps_auth_lock(self) -> None:
        core_query = select(HpsAuth.id).with_for_update()
        await self._session.execute(core_query)

    async def acquire_method_lock(self) -> None:
        if self._project_id is None:
            raise ValueError("attempting to acquire project method lock but no project has been specified")
        core_query = (
            select(ProjectMethodLock.id).where(ProjectMethodLock.project_id == self._project_id).with_for_update()
        )
        logger.debug(f"Acquiring method lock for project {self._project_id} for session {id(self._session)}")
        await self._session.execute(core_query)
        logger.debug(f"Acquired method lock for project {self._project_id} for session {id(self._session)}")

    async def insert_bdm_table_row(self, project_id: str, bdm_lock: models.BdmLockModel) -> bool:
        expiration_date = bdm_lock.expiration_date

        if expiration_date is None:
            date_string = "NULL::timestamp with time zone"
        else:
            date_string_inner = expiration_date.isoformat(sep=" ")
            date_string = f"TIMESTAMP WITH TIME ZONE '{date_string_inner}'"

        statement_text = (
            "INSERT INTO bdm_locks (project_id, external_id, expiration_date) "  # noqa: S608 #nosec
            "SELECT projects.id, t.external_id, t.expiration_date "
            f"FROM projects, (VALUES (:external_id, {date_string})) "
            "AS t(external_id, expiration_date) "
            "WHERE projects.id = :project_id "
            "RETURNING 1"
        )
        result = await self._session.execute(
            text(statement_text),
            {
                "project_id": project_id,
                "external_id": str(bdm_lock.id),
            },
        )
        return bool(result.all())

    async def remove_project_from_database(self, project_id: str, keep_access: bool = False) -> list[str]:
        await self._log_event_listeners_for_project_delete_on_debug(project_id)

        event_listener_statement = (
            delete(EventListener)
            .where(EventListener.event_source_id == EventSource.id)
            .where(EventSource.step_id == Step.id)
            .where(Step.project_id == project_id)
        )
        await self._session.execute(event_listener_statement)

        event_statement = (
            delete(Event)
            .where(Event.event_source_id == EventSource.id)
            .where(EventSource.step_id == Step.id)
            .where(Step.project_id == project_id)
        )
        await self._session.execute(event_statement)

        event_source_statement = (
            delete(EventSource).where(EventSource.step_id == Step.id).where(Step.project_id == project_id)
        )
        await self._session.execute(event_source_statement)

        field_statement = delete(StepField).where(StepField.step_id == Step.id).where(Step.project_id == project_id)
        await self._session.execute(field_statement)

        method_statement = (
            delete(MethodState).where(MethodState.step_id == Step.id).where(Step.project_id == project_id)
        )
        await self._session.execute(method_statement)

        method_statement = (
            delete(Instance)
            .where(Instance.step_id == Step.id)
            .where(Step.project_id == project_id)
            .returning(Instance.pim_name)
        )
        pim_names_result = await self._session.execute(method_statement)
        pim_names = list(pim_names_result.scalars().all())

        step_statement = delete(Step).where(Step.project_id == project_id)
        await self._session.execute(step_statement)

        project_methods_statement = delete(ProjectMethodLock).where(ProjectMethodLock.project_id == project_id)
        await self._session.execute(project_methods_statement)

        bdm_statement = delete(BdmLock).where(BdmLock.project_id == project_id)
        await self._session.execute(bdm_statement)

        if not keep_access:
            await self._delete_access_rows(project_id)

        project_statement = delete(Project).where(Project.id == project_id)
        result = await self._session.execute(project_statement)

        if result.rowcount == 0:  # pyright: ignore
            raise NotFoundError(f"Project '{project_id}' not found.")

        await self._log_event_row_counts_on_debug("after deleting project")

        return pim_names

    async def delete_instance_row_and_get_pim_name(
        self,
        project_id: str,
        step_name: str,
        instance_id: str,
    ) -> str | None:
        statement = (
            delete(Instance)
            .where(Instance.step_id == Step.id)
            .where(Step.project_id == project_id)
            .where(Step.name == step_name)
            .where(Instance.name == instance_id)
            .returning(Instance.pim_name)
        )
        return await self._session.scalar(statement)


class PostgresqlSessionFactory(RelationalSessionFactory):
    def __init__(self, settings: Settings, solution_service: SolutionService) -> None:
        location = settings.computed_database_location
        if isinstance(location, MultiHostUrl | PostgresDsn):
            database_url = str(location).replace("postgresql:", "postgresql+asyncpg:", 1)
            logger.debug(f"Using Postgresql database at {database_url}")
        else:
            raise ValueError("Invalid database location.")
        self._solution_service = solution_service
        self._settings = settings
        super().__init__(database_url)

    @asynccontextmanager
    async def get_session_implementation(
        self,
    ) -> AsyncGenerator[AbstractRepositorySession]:
        async with super().get_relational_session(
            lambda session: PostgresqlSession(session, self._solution_service, self._settings),
        ) as session:
            yield session
