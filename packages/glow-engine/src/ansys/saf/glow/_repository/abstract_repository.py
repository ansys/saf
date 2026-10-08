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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
import uuid

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._core.field_state import FieldState
from ansys.saf.glow._core.instance.recoverystate import RecoveryStateInfo
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._events.ievent_manager import EventPayload, EventSourceIdentifier
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


class AbstractRepositorySession(ABC):
    @abstractmethod
    async def project_in_database(self, project_id: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def get_running_methods(self, project_id: str) -> list[str]:
        raise NotImplementedError()

    @abstractmethod
    async def list_projects(
        self,
        page_size: int,
        page: int,
        order_by: str | None = None,
        filters: ParsedProjectFilter | None = None,
    ) -> ListProjectResponse:
        raise NotImplementedError()

    @abstractmethod
    async def modify_project_info(
        self,
        project_id: str,
        request: ModifyProjectRequest,
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def get_project_as_dict(
        self,
        project_id: str,
    ) -> tuple[ProjectInfo, dict[str, Any]]:
        raise NotImplementedError()

    @abstractmethod
    async def remove_project_from_database(self, project_id: str) -> list[str]:
        raise NotImplementedError()

    @abstractmethod
    async def build_project_in_database(
        self,
        project: models.ProjectModel[Solution],
        project_id: str | None = None,
    ) -> ProjectInfo:
        raise NotImplementedError()

    @abstractmethod
    async def get_step(
        self,
        project_id: str,
        step_name: str,
        step_type: type[StepModel],
        fields_list: list[str] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError()

    @abstractmethod
    async def get_method_state(
        self,
        project_id: str,
        step_name: str,
        method_name: str,
    ) -> models.MethodState:
        raise NotImplementedError()

    @abstractmethod
    async def update_method_state(
        self,
        project_id: str,
        step_name: str,
        method_name: str,
        update_data: dict[str, Any],
    ) -> models.MethodState:
        raise NotImplementedError()

    @abstractmethod
    async def set_field_state(
        self,
        project_id: str,
        step_name: str,
        field_name: str,
        state: FieldState,
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def get_instance_state(
        self,
        project_id: str,
        step_name: str,
        instance_id: str,
        instance_url: str,
        ignore_not_found: bool = False,
    ) -> InstanceResponse[RecoveryStateInfo] | None:
        raise NotImplementedError()

    @abstractmethod
    async def create_instance(
        self,
        project_id: str,
        step_name: str,
        instance_id: str,
        instance_request: CreateInstanceRequest[RecoveryStateInfo],
    ) -> InstanceResponse[RecoveryStateInfo]:
        raise NotImplementedError()

    @abstractmethod
    async def update_instance_state(
        self,
        project_id: str,
        step_name: str,
        instance_url: str,
        instance_id: str,
        instance_state: ModifyInstanceRequest[RecoveryStateInfo],
    ) -> InstanceResponse[RecoveryStateInfo]:
        raise NotImplementedError()

    @abstractmethod
    async def delete_instance_row_and_get_pim_name(
        self,
        project_id: str,
        step_name: str,
        instance_id: str,
    ) -> str | None:
        raise NotImplementedError()

    @abstractmethod
    async def add_bdm_lock(
        self,
        project_id: str,
        is_internal_caller: bool = False,
    ) -> models.BdmLockModel:
        raise NotImplementedError()

    @abstractmethod
    async def get_bdm_lock(
        self,
        project_id: str,
        lock_id: uuid.UUID,
    ) -> models.BdmLockModel:
        raise NotImplementedError()

    @abstractmethod
    async def remove_expired_bdm_locks(
        self,
        project_id: str | None = None,
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def remove_bdm_lock(
        self,
        lock_id: uuid.UUID,
        project_id: str,
    ) -> list[EntityHandle] | None:
        raise NotImplementedError()

    @abstractmethod
    async def set_fields_in_project(
        self,
        project_id: str,
        steps: dict[str, dict[str, str]],
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def create_event_listener(self, event_source_identifier: EventSourceIdentifier) -> str:
        """Creates an event listener for the caller to receive events. Returns the listener ID."""
        raise NotImplementedError()

    @abstractmethod
    async def destroy_event_listener(self, listener_id: str) -> None:
        """Cleans up any resources used by this listener"""
        raise NotImplementedError()

    @abstractmethod
    async def store_event(self, event_source_identifier: EventSourceIdentifier, event: EventPayload) -> None:
        """Stores an event for transmission to listeners"""
        raise NotImplementedError()

    @abstractmethod
    async def get_new_events_and_purge_queue(self, listener_id: str) -> None | list[EventPayload]:
        """fetches all events that have not been processed by this listener

        Returns:
            None if the event source no longer exists, otherwise a list of event payloads
        """
        raise NotImplementedError()

    @abstractmethod
    async def acquire_project_lock(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def acquire_hps_auth_lock(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def acquire_method_lock(
        self,
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def indicate_project_id(
        self,
        project_id: str,
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def indicate_modification(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def set_update_modification_date(self, update: bool) -> None:
        raise NotImplementedError()


class AbstractLockSpecification(ABC):
    @abstractmethod
    async def acquire_lock(
        self,
        session: AbstractRepositorySession,
    ) -> None:
        raise NotImplementedError()


class ProjectLockSpecification(AbstractLockSpecification):
    async def acquire_lock(
        self,
        session: AbstractRepositorySession,
    ) -> None:
        await session.acquire_project_lock()


class HpsAuthLockSpecification(AbstractLockSpecification):
    async def acquire_lock(
        self,
        session: AbstractRepositorySession,
    ) -> None:
        await session.acquire_hps_auth_lock()


class MethodLockSpecification(AbstractLockSpecification):
    async def acquire_lock(
        self,
        session: AbstractRepositorySession,
    ) -> None:
        await session.acquire_method_lock()


class AbstractRepositorySessionFactory(ABC):
    def __init__(self):
        self._session: AbstractRepositorySession | None = None

    @asynccontextmanager
    @abstractmethod
    async def get_session_implementation(
        self,
    ) -> AsyncGenerator[AbstractRepositorySession]:
        raise NotImplementedError()
        # need this to stop type error on @asynccontextmanager and
        # enable typing system to establish type of this function
        yield None

    async def _apply_args_to_session(
        self,
        modification: bool = False,
        update_modification_date: bool | None = None,
        project_id: str | None = None,
        lock_spec: AbstractLockSpecification | None = None,
    ) -> None:
        assert self._session is not None, "Session must be initialized before applying arguments."  # noqa: S101 #nosec
        if project_id is not None:
            await self._session.indicate_project_id(project_id)
        if modification:
            await self._session.indicate_modification()
        if update_modification_date is not None:
            await self._session.set_update_modification_date(update_modification_date)
        if lock_spec is not None:
            await lock_spec.acquire_lock(self._session)

    @asynccontextmanager
    async def get_session(
        self,
        modification: bool = False,
        update_modification_date: bool | None = None,
        project_id: str | None = None,
        lock_spec: AbstractLockSpecification | None = None,
    ) -> AsyncGenerator[AbstractRepositorySession]:
        if self._session is None:
            async with self.get_session_implementation() as session:
                try:
                    self._session = session
                    await self._apply_args_to_session(modification, update_modification_date, project_id, lock_spec)
                    yield self._session
                finally:
                    self._session = None

        else:
            assert self._session is not None  # noqa: S101 #nosec
            await self._apply_args_to_session(modification, update_modification_date, project_id, lock_spec)
            yield self._session
