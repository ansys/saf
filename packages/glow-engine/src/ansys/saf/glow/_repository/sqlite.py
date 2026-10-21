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

from asyncio import Lock
import logging

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._repository.relational import RelationalSession
from ansys.saf.glow._repository.relational_models import (
    BdmLock,
    Event,
    EventListener,
    EventSource,
    Instance,
    MethodState,
    Project,
    ProjectMethodLock,
    Step,
    StepField,
)
from ansys.saf.glow._server import models
from ansys.saf.glow._server.exceptions import NotFoundError
from ansys.saf.glow._server.solution import SolutionService

logger = logging.getLogger(__name__)


class SqliteSession(RelationalSession):
    # sqlite doesn't support row-level locking, so we use in memory locks.
    # This means that locks are not shared between different processes or servers.
    # The sqlite factory attempts to detect if the server is running
    # in uvicorn multi-worker mode and raises an error if it is.
    # See SqliteSessionFactory for more details.
    # That check will detect uvicorn multi-worker single node deployments
    # however other multi-process deployments will not be detected.
    # This means its possible to start a sqlite based multi-process deployment that won't work.
    _lock_by_name: dict[str, Lock] = {}

    def __init__(self, session: AsyncSession, solution_service: SolutionService, settings: Settings) -> None:
        super().__init__(session, solution_service, settings)
        self._locks: list[str] = []

    async def release_locks(self) -> None:
        for lock_id in self._locks:
            self._lock_by_name[lock_id].release()

    async def _lock(self, lock_id: str) -> None:
        if lock_id in self._locks:
            return
        if lock_id not in self._lock_by_name:
            self._lock_by_name[lock_id] = Lock()
        await self._lock_by_name[lock_id].acquire()
        self._locks.append(lock_id)

    async def acquire_project_lock(self) -> None:
        logger.debug(f"Acquiring lock for project {self._project_id} for session {id(self._session)}")
        await self._lock(f"project/{self._project_id}")
        logger.debug(f"Acquired lock for project {self._project_id} for session {id(self._session)}")

    async def acquire_hps_auth_lock(self) -> None:
        await self._lock("hps_auth")

    async def acquire_method_lock(
        self,
    ) -> None:
        await self._lock(f"method/{self._project_id}")

    async def insert_bdm_table_row(self, project_id: str, bdm_lock: models.BdmLockModel) -> bool:
        statement_text = (
            "INSERT INTO bdm_locks (project_id, external_id, expiration_date) "
            "SELECT id, :external_id, :expiration_date FROM projects WHERE id = :project_id "
            "RETURNING 1"
        )
        result = await self._session.execute(
            text(statement_text),
            {"project_id": project_id, "external_id": str(bdm_lock.id), "expiration_date": bdm_lock.expiration_date},
        )
        return bool(result.all())

    async def remove_project_from_database(self, project_id: str) -> list[str]:
        await self._log_event_listeners_for_project_delete_on_debug(project_id)

        event_source_subquery = (
            select(EventSource.id)
            .where(EventSource.step_id == Step.id)
            .where(Step.project_id == project_id)
            .scalar_subquery()
        )

        event_listener_statement = delete(EventListener).where(EventListener.event_source_id.in_(event_source_subquery))
        await self._session.execute(event_listener_statement)

        event_statement = delete(Event).where(Event.event_source_id.in_(event_source_subquery))
        await self._session.execute(event_statement)

        subquery = select(Step.id).where(Step.project_id == project_id).scalar_subquery()

        event_source_statement = delete(EventSource).where(EventSource.step_id.in_(subquery))
        await self._session.execute(event_source_statement)

        field_statement = delete(StepField).where(StepField.step_id.in_(subquery))
        await self._session.execute(field_statement)

        method_statement = delete(MethodState).where(MethodState.step_id.in_(subquery))
        await self._session.execute(method_statement)

        instance_query = select(Instance.pim_name).where(Instance.step_id.in_(subquery))
        pim_names_result = await self._session.execute(instance_query)
        pim_names = list(pim_names_result.scalars().all())

        instance_statement = delete(Instance).where(Instance.step_id.in_(subquery))
        await self._session.execute(instance_statement)

        bdm_statement = delete(BdmLock).where(BdmLock.project_id == project_id)
        await self._session.execute(bdm_statement)

        step_statement = delete(Step).where(Step.project_id == project_id)
        await self._session.execute(step_statement)

        project_methods_statement = delete(ProjectMethodLock).where(ProjectMethodLock.project_id == project_id)
        await self._session.execute(project_methods_statement)

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
            select(Instance.pim_name, Instance.id)
            .where(Step.project_id == project_id)
            .where(Step.name == step_name)
            .where(Step.id == Instance.step_id)
            .where(Instance.name == instance_id)
        )
        result = await self._session.execute(statement)
        row = result.first()
        if row is None:
            return None
        await self._session.execute(delete(Instance).where(Instance.id == row[1]))
        return row[0]

    @classmethod
    async def table_exists(cls, session: AsyncSession, table_name: str) -> bool:
        statement = text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:table_name")
        result = await session.execute(statement, params={"table_name": table_name})
        return bool(result.all())
