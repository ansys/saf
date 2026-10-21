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

"""Repository operations backing project access control (members, write lock, write requests, audit)."""

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ansys.saf.glow._access.schemas import (
    AuditEntryInfo,
    ProjectAccessRecord,
    ProjectAccessSummary,
    ProjectMemberInfo,
    ProjectRole,
    WriteRequestInfo,
    WriteRequestStatus,
)
from ansys.saf.glow._core.method_status import MethodStatus
from ansys.saf.glow._repository.relational_models import (
    MethodState,
    ProjectAuditEntry,
    ProjectMember,
    ProjectWriteLock,
    ProjectWriteRequest,
    Step,
)
from ansys.saf.glow._server.exceptions import NotFoundError


def _to_utc(value: datetime) -> datetime:
    """Normalise a datetime for storage. SQLite drops the time zone, so everything is stored as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _from_db(value: datetime | None) -> datetime | None:
    """Restore the UTC time zone that SQLite drops when reading timezone-aware columns."""
    if value is None:
        return None
    return _to_utc(value)


def _to_request_info(row: ProjectWriteRequest) -> WriteRequestInfo:
    created_at = _from_db(row.created_at)
    assert created_at is not None  # noqa: S101 #nosec
    return WriteRequestInfo(
        id=row.id,
        requester_id=row.requester_id,
        status=row.status,
        created_at=created_at,
        decided_by=row.decided_by,
        decided_at=_from_db(row.decided_at),
    )


class RelationalAccessMixin:
    """Access control operations of the relational repository sessions.

    None of these methods commit: the session wrapper commits when the session was opened with ``modification=True``.
    """

    _session: AsyncSession

    async def _bump_lock(self, project_id: str, **values: Any) -> None:
        """Increment the version of the lock row of the project, creating the row if it is missing."""
        statement = (
            update(ProjectWriteLock)
            .where(ProjectWriteLock.project_id == project_id)
            .values(version=ProjectWriteLock.version + 1, **values)
        )
        result = await self._session.execute(statement)
        if result.rowcount == 0:  # pyright: ignore
            await self._session.execute(insert(ProjectWriteLock).values(project_id=project_id, version=1, **values))

    async def _delete_access_rows(self, project_id: str) -> None:
        """Removes the members, lock and write requests of a project. Audit entries are deliberately kept."""
        await self._session.execute(delete(ProjectWriteRequest).where(ProjectWriteRequest.project_id == project_id))
        await self._session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
        await self._session.execute(delete(ProjectWriteLock).where(ProjectWriteLock.project_id == project_id))

    async def get_access_record(self, project_id: str) -> ProjectAccessRecord:
        members_result = await self._session.execute(
            select(ProjectMember.user_id, ProjectMember.role)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.id),
        )
        members = [ProjectMemberInfo(user_id=user_id, role=role) for user_id, role in members_result.all()]

        lock = (
            await self._session.execute(
                select(
                    ProjectWriteLock.holder_id,
                    ProjectWriteLock.acquired_at,
                    ProjectWriteLock.last_write_at,
                    ProjectWriteLock.version,
                ).where(ProjectWriteLock.project_id == project_id),
            )
        ).first()

        requests_result = await self._session.scalars(
            select(ProjectWriteRequest)
            .where(ProjectWriteRequest.project_id == project_id)
            .order_by(ProjectWriteRequest.created_at, ProjectWriteRequest.id)
            .execution_options(populate_existing=True),
        )
        requests = [_to_request_info(row) for row in requests_result.all()]

        return ProjectAccessRecord(
            project_id=project_id,
            members=members,
            holder_id=lock.holder_id if lock else None,
            acquired_at=_from_db(lock.acquired_at) if lock else None,
            last_write_at=_from_db(lock.last_write_at) if lock else None,
            version=lock.version if lock else 0,
            requests=requests,
        )

    async def get_access_summaries(
        self,
        project_ids: list[str],
        user_id: str | None,
    ) -> dict[str, ProjectAccessSummary]:
        if not project_ids:
            return {}
        owners: dict[str, str] = {}
        my_roles: dict[str, ProjectRole] = {}
        members_result = await self._session.execute(
            select(ProjectMember.project_id, ProjectMember.user_id, ProjectMember.role)
            .where(ProjectMember.project_id.in_(project_ids))
            .where((ProjectMember.role == ProjectRole.owner) | (ProjectMember.user_id == user_id))
            .order_by(ProjectMember.id),
        )
        for project_id, member_id, role in members_result.all():
            if role == ProjectRole.owner:
                owners.setdefault(project_id, member_id)
            if user_id is not None and member_id == user_id:
                my_roles[project_id] = role

        holders_result = await self._session.execute(
            select(ProjectWriteLock.project_id, ProjectWriteLock.holder_id).where(
                ProjectWriteLock.project_id.in_(project_ids),
            ),
        )
        holders = dict(holders_result.all())

        pending_result = await self._session.execute(
            select(ProjectWriteRequest.project_id, func.count())
            .where(ProjectWriteRequest.project_id.in_(project_ids))
            .where(ProjectWriteRequest.status == WriteRequestStatus.pending)
            .group_by(ProjectWriteRequest.project_id),
        )
        pending = dict(pending_result.all())

        return {
            project_id: ProjectAccessSummary(
                owner_id=owners.get(project_id),
                holder_id=holders.get(project_id),
                my_role=my_roles.get(project_id),
                pending_request_count=pending.get(project_id, 0),
            )
            for project_id in project_ids
        }

    async def upsert_member(self, project_id: str, user_id: str, role: ProjectRole) -> None:
        result = await self._session.execute(
            update(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .where(ProjectMember.user_id == user_id)
            .values(role=role),
        )
        if result.rowcount == 0:  # pyright: ignore
            await self._session.execute(insert(ProjectMember).values(project_id=project_id, user_id=user_id, role=role))
        await self._bump_lock(project_id)

    async def delete_member(self, project_id: str, user_id: str) -> None:
        await self._session.execute(
            delete(ProjectMember).where(ProjectMember.project_id == project_id).where(ProjectMember.user_id == user_id),
        )
        await self._bump_lock(project_id)

    async def set_lock_holder(self, project_id: str, holder_id: str | None, now: datetime) -> None:
        if holder_id is None:
            await self._bump_lock(project_id, holder_id=None, acquired_at=None, last_write_at=None)
        else:
            moment = _to_utc(now)
            await self._bump_lock(project_id, holder_id=holder_id, acquired_at=moment, last_write_at=moment)

    async def touch_lock(self, project_id: str, now: datetime) -> None:
        await self._bump_lock(project_id, last_write_at=_to_utc(now))

    async def insert_write_request(self, project_id: str, requester_id: str, now: datetime) -> WriteRequestInfo:
        request = WriteRequestInfo(
            id=str(uuid.uuid4()),
            requester_id=requester_id,
            status=WriteRequestStatus.pending,
            created_at=_to_utc(now),
            decided_by=None,
            decided_at=None,
        )
        await self._session.execute(
            insert(ProjectWriteRequest).values(
                id=request.id,
                project_id=project_id,
                requester_id=requester_id,
                status=request.status,
                created_at=request.created_at,
            ),
        )
        await self._bump_lock(project_id)
        return request

    async def set_write_request_status(
        self,
        request_id: str,
        status: WriteRequestStatus,
        decided_by: str | None,
        now: datetime,
    ) -> WriteRequestInfo:
        result = await self._session.execute(
            update(ProjectWriteRequest)
            .where(ProjectWriteRequest.id == request_id)
            .values(status=status, decided_by=decided_by, decided_at=_to_utc(now))
            .returning(ProjectWriteRequest.project_id),
        )
        project_id = result.scalar_one_or_none()
        if project_id is None:
            raise NotFoundError(f"Write request '{request_id}' not found.")
        await self._bump_lock(project_id)
        row = await self._session.scalar(
            select(ProjectWriteRequest)
            .where(ProjectWriteRequest.id == request_id)
            .execution_options(populate_existing=True),
        )
        assert row is not None  # noqa: S101 #nosec
        return _to_request_info(row)

    async def insert_audit_entry(
        self,
        project_id: str,
        actor_id: str,
        action: str,
        details: dict[str, Any],
        now: datetime,
    ) -> None:
        await self._session.execute(
            insert(ProjectAuditEntry).values(
                project_id=project_id,
                actor_id=actor_id,
                action=action,
                details=details,
                at=_to_utc(now),
            ),
        )

    async def list_audit_entries(self, project_id: str | None, page: int, page_size: int) -> list[AuditEntryInfo]:
        statement = select(ProjectAuditEntry).order_by(ProjectAuditEntry.at.desc(), ProjectAuditEntry.id.desc())
        if project_id is not None:
            statement = statement.where(ProjectAuditEntry.project_id == project_id)
        statement = statement.offset((max(page, 1) - 1) * page_size).limit(page_size)
        rows = await self._session.scalars(statement)
        entries: list[AuditEntryInfo] = []
        for row in rows.all():
            at = _from_db(row.at)
            assert at is not None  # noqa: S101 #nosec
            entries.append(
                AuditEntryInfo(
                    project_id=row.project_id,
                    actor_id=row.actor_id,
                    action=row.action,
                    details=row.details or {},
                    at=at,
                ),
            )
        return entries

    async def get_running_methods_with_start(self, project_id: str) -> list[tuple[str, str, datetime | None]]:
        result = await self._session.execute(
            select(Step.name, MethodState.method_name, MethodState.started_at)
            .where(MethodState.step_id == Step.id)
            .where(Step.project_id == project_id)
            .where(MethodState.status == MethodStatus.Running),
        )
        return [(step_name, method_name, _from_db(started_at)) for step_name, method_name, started_at in result.all()]

    async def mark_method_failed(self, project_id: str, step_name: str, method_name: str, message: str) -> None:
        step_id = select(Step.id).where(Step.project_id == project_id).where(Step.name == step_name).scalar_subquery()
        await self._session.execute(
            update(MethodState)
            .where(MethodState.step_id == step_id)
            .where(MethodState.method_name == method_name)
            .values(
                status=MethodStatus.Failed,
                exception_message=message,
                exception_stack=None,
                status_code=500,
            ),
        )
