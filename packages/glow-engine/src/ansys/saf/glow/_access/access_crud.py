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

"""The rules of project access control: ownership, sharing, the single-writer lock and write requests."""

from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from ansys.saf.glow._access.principal import Principal
from ansys.saf.glow._access.schemas import (
    AuditEntryInfo,
    ProjectAccess,
    ProjectAccessRecord,
    ProjectRole,
    WriteRequestInfo,
    WriteRequestStatus,
)
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._repository.abstract_repository import (
    AbstractRepositorySession,
    AbstractRepositorySessionFactory,
    ProjectLockSpecification,
)
from ansys.saf.glow._server.exceptions import ConflictError, ForbiddenError, LockedError, NotFoundError
from ansys.saf.glow._server.schemas import ProjectInfo

RUNNING_TRANSACTION_MESSAGE = "A transaction is running on this project; try again when it finishes."
SYSTEM_ACTOR = "system"
"""Actor recorded in the audit table when the caller has no user id (framework internals)."""

AUDIT_OWNERSHIP_TRANSFERRED = "ownership_transferred"
AUDIT_OWNER_ASSIGNED = "owner_assigned"
AUDIT_LOCK_FORCE_RELEASED = "lock_force_released"
AUDIT_LOCK_EXPIRED = "lock_expired"
AUDIT_METHODS_FAILED = "methods_failed"
AUDIT_PROJECT_DELETED = "project_deleted"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _is_bypass(principal: Principal) -> bool:
    """Framework internals (API key without an on-behalf-of user) bypass every check."""
    return principal.is_internal and principal.user_id is None


def _role_of(record: ProjectAccessRecord, user_id: str | None) -> ProjectRole | None:
    if user_id is None:
        return None
    for member in record.members:
        if member.user_id == user_id:
            return member.role
    return None


def _owner_of(record: ProjectAccessRecord) -> str | None:
    for member in record.members:
        if member.role == ProjectRole.owner:
            return member.user_id
    return None


def _not_found(project_id: str) -> NotFoundError:
    return NotFoundError(f"Project '{project_id}' not found.")


def _actor(principal: Principal) -> str:
    return principal.user_id or SYSTEM_ACTOR


def _ensure_identified(principal: Principal) -> None:
    """Tokens without a ``sub`` claim are unauthenticated for access control purposes."""
    if not principal.user_id:
        raise ForbiddenError(
            "Authentication required: the access token must contain a subject (sub) claim.",
        )


class AccessCrud:
    """Evaluates and applies the project access rules.

    Every method takes the calling ``principal``. Non-members get 404 (the project existence is not leaked), members
    attempting an action reserved to another role get 403, writes without the lock get 423, and lock moves refused
    because a transaction is running get 409. Mutations run in a modifying session holding the project lock, so lock
    transitions are serialised per project; when called inside an outer session of the same repository factory they
    join it.
    """

    def __init__(
        self,
        session_factory: AbstractRepositorySessionFactory,
        settings: Settings,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._now = now

    # ----------------------------------------------------------------------------------------------------------------
    # Helpers

    @property
    def _enabled(self) -> bool:
        return self._settings.glow_project_access_control_enabled

    @asynccontextmanager
    async def _modifying_session(self, project_id: str) -> AsyncGenerator[AbstractRepositorySession]:
        # Access changes must not bump the project modification date, but an outer session decides for itself.
        nested = self._session_factory.current_session is not None
        async with self._session_factory.get_session(
            modification=True,
            update_modification_date=None if nested else False,
            project_id=project_id,
            lock_spec=ProjectLockSpecification(),
        ) as session:
            yield session

    async def _require_member(
        self,
        session: AbstractRepositorySession,
        project_id: str,
        principal: Principal,
    ) -> tuple[ProjectAccessRecord, ProjectRole]:
        record = await session.get_access_record(project_id)
        role = _role_of(record, principal.user_id)
        if role is None:
            raise _not_found(project_id)
        return record, role

    async def _require_existing(self, session: AbstractRepositorySession, project_id: str) -> ProjectAccessRecord:
        if not await session.project_in_database(project_id):
            raise _not_found(project_id)
        return await session.get_access_record(project_id)

    async def _require_super_admin(
        self,
        session: AbstractRepositorySession,
        project_id: str,
        principal: Principal,
    ) -> ProjectAccessRecord:
        """Super admins (and framework internals) pass; members get 403, others 404."""
        if principal.is_super_admin or _is_bypass(principal):
            return await self._require_existing(session, project_id)
        await self._require_member(session, project_id, principal)
        raise ForbiddenError("Only a super admin can perform this action.")

    async def _ensure_not_running(self, session: AbstractRepositorySession, project_id: str) -> None:
        if await session.get_running_methods(project_id):
            raise ConflictError(RUNNING_TRANSACTION_MESSAGE)

    async def _apply_expiry(
        self,
        session: AbstractRepositorySession,
        record: ProjectAccessRecord,
        principal: Principal,
    ) -> ProjectAccessRecord:
        """Release the lock if it has been idle for longer than the timeout and no transaction is running."""
        if record.holder_id is None or record.last_write_at is None:
            return record
        now = self._now()
        if record.last_write_at + timedelta(seconds=self._settings.glow_project_lock_idle_timeout) >= now:
            return record
        if await session.get_running_methods(record.project_id):
            return record
        await session.set_lock_holder(record.project_id, None, now)
        await session.insert_audit_entry(
            record.project_id,
            _actor(principal),
            AUDIT_LOCK_EXPIRED,
            {"holder_id": record.holder_id},
            now,
        )
        return await session.get_access_record(record.project_id)

    async def _set_holder(self, session: AbstractRepositorySession, project_id: str, holder_id: str | None) -> None:
        await self._ensure_not_running(session, project_id)
        await session.set_lock_holder(project_id, holder_id, self._now())

    async def _access(self, session: AbstractRepositorySession, project_id: str, principal: Principal) -> ProjectAccess:
        record = await session.get_access_record(project_id)
        return self._to_access(record, principal)

    @staticmethod
    def _to_access(record: ProjectAccessRecord, principal: Principal) -> ProjectAccess:
        owner_id = _owner_of(record)
        return ProjectAccess(
            project_id=record.project_id,
            owner_id=owner_id,
            members=record.members,
            holder_id=record.holder_id,
            lock_acquired_at=record.acquired_at,
            last_write_at=record.last_write_at,
            version=record.version,
            pending_requests=[r for r in record.requests if r.status == WriteRequestStatus.pending],
            my_role=_role_of(record, principal.user_id),
            can_write=principal.user_id is not None and record.holder_id == principal.user_id,
            is_orphan=owner_id is None,
        )

    @staticmethod
    def _pending_request(record: ProjectAccessRecord, request_id: str) -> WriteRequestInfo:
        request = next((r for r in record.requests if r.id == request_id), None)
        if request is None:
            raise NotFoundError(f"Write request '{request_id}' not found.")
        if request.status != WriteRequestStatus.pending:
            raise ConflictError(f"Write request '{request_id}' is already {request.status.value}.")
        return request

    # ----------------------------------------------------------------------------------------------------------------
    # Checks

    async def check_read(self, project_id: str, principal: Principal) -> None:
        """Members only. Super admins are not members: they get 404 like anyone else."""
        if not self._enabled or _is_bypass(principal):
            return
        _ensure_identified(principal)
        async with self._session_factory.get_session() as session:
            await self._require_member(session, project_id, principal)

    async def check_metadata(self, project_id: str, principal: Principal) -> None:
        """Members and super admins."""
        if not self._enabled or _is_bypass(principal):
            return
        _ensure_identified(principal)
        async with self._session_factory.get_session() as session:
            if principal.is_super_admin:
                await self._require_existing(session, project_id)
            else:
                await self._require_member(session, project_id, principal)

    async def check_owner(self, project_id: str, principal: Principal, allow_super_admin: bool = False) -> None:
        """Owner only: 404 for non-members, 403 for other members. ``allow_super_admin`` admits super admins too."""
        if not self._enabled or _is_bypass(principal):
            return
        _ensure_identified(principal)
        async with self._session_factory.get_session() as session:
            if allow_super_admin and principal.is_super_admin:
                await self._require_existing(session, project_id)
                return
            _, role = await self._require_member(session, project_id, principal)
            if role != ProjectRole.owner:
                raise ForbiddenError("Only the project owner can perform this action.")

    async def check_write(self, project_id: str, principal: Principal, touch: bool = True) -> None:
        """Lock holder only: 404 for non-members, 423 (with the current holder id) for other members."""
        if not self._enabled or _is_bypass(principal):
            return
        _ensure_identified(principal)
        async with self._modifying_session(project_id) as session:
            record, _ = await self._require_member(session, project_id, principal)
            record = await self._apply_expiry(session, record, principal)
            if record.holder_id is None:
                raise LockedError(
                    {"message": "Nobody holds the write lock of this project; acquire it first.", "holder_id": None},
                )
            if record.holder_id != principal.user_id:
                raise LockedError(
                    {"message": "Another user holds the write lock of this project.", "holder_id": record.holder_id},
                )
            if touch:
                await session.touch_lock(project_id, self._now())

    # ----------------------------------------------------------------------------------------------------------------
    # Lifecycle and reads

    def require_identified(self, principal: Principal) -> None:
        """Refuse callers that cannot be identified when access control is on.

        Framework internals (API key without an on-behalf-of user) are exempt. Used before creating or importing a
        project so that an unidentified token cannot leave an ownerless project behind.
        """
        if not self._enabled or _is_bypass(principal):
            return
        _ensure_identified(principal)

    async def on_project_created(self, project_id: str, principal: Principal) -> None:
        """The creator becomes the owner and holds the lock."""
        if not self._enabled or _is_bypass(principal):
            return
        _ensure_identified(principal)
        async with self._modifying_session(project_id) as session:
            assert principal.user_id is not None  # noqa: S101 #nosec
            await session.upsert_member(project_id, principal.user_id, ProjectRole.owner)
            await session.set_lock_holder(project_id, principal.user_id, self._now())

    def list_scope(self, principal: Principal) -> str | None:
        """The id of the member whose projects the principal may list, or ``None`` to list every project.

        Super admins, framework internals and deployments without access control list everything. A caller that
        cannot be identified is refused (403): they must never match a member row.
        """
        if not self._enabled or principal.is_super_admin or principal.is_internal:
            return None
        _ensure_identified(principal)
        return principal.user_id

    def check_orphans_listing(self, principal: Principal) -> None:
        """Only super admins (and framework internals) may restrict a project list to the projects without owner."""
        if not (principal.is_super_admin or principal.is_internal):
            raise ForbiddenError("Only a super admin can list the projects without an owner.")

    async def fill_access_summaries(self, projects: Sequence[ProjectInfo], principal: Principal) -> None:
        """Set ``ProjectInfo.access`` of ``projects``. Leaves it ``None`` when access control is disabled.

        Idle write locks are expired before the summaries are built, so the list shows a free lock when the idle
        timeout has elapsed (subject to the running-transaction rule).
        """
        if not self._enabled or not projects:
            return
        for project in projects:
            async with self._modifying_session(project.project_id) as session:
                record = await session.get_access_record(project.project_id)
                await self._apply_expiry(session, record, principal)
        async with self._session_factory.get_session() as session:
            summaries = await session.get_access_summaries([p.project_id for p in projects], principal.user_id)
        for project in projects:
            project.access = summaries.get(project.project_id)

    async def get_access(self, project_id: str, principal: Principal) -> ProjectAccess:
        """Access state of the project, for members and super admins."""
        async with self._modifying_session(project_id) as session:
            if principal.is_super_admin or _is_bypass(principal):
                record = await self._require_existing(session, project_id)
            else:
                record, _ = await self._require_member(session, project_id, principal)
            record = await self._apply_expiry(session, record, principal)
            return self._to_access(record, principal)

    # ----------------------------------------------------------------------------------------------------------------
    # Lock

    async def acquire(self, project_id: str, principal: Principal) -> ProjectAccess:
        """Take the lock when nobody holds it. A held lock is a conflict, even for the owner (who uses take_over)."""
        async with self._modifying_session(project_id) as session:
            record, _ = await self._require_member(session, project_id, principal)
            record = await self._apply_expiry(session, record, principal)
            if record.holder_id == principal.user_id:
                return self._to_access(record, principal)
            if record.holder_id is not None:
                raise ConflictError("Another user holds the write lock of this project; request write access instead.")
            await self._set_holder(session, project_id, principal.user_id)
            return await self._access(session, project_id, principal)

    async def release(self, project_id: str, principal: Principal) -> ProjectAccess:
        """Holder only."""
        async with self._modifying_session(project_id) as session:
            record, _ = await self._require_member(session, project_id, principal)
            record = await self._apply_expiry(session, record, principal)
            if record.holder_id != principal.user_id:
                raise ForbiddenError("Only the lock holder can release the write lock.")
            await self._set_holder(session, project_id, None)
            return await self._access(session, project_id, principal)

    async def take_over(self, project_id: str, principal: Principal) -> ProjectAccess:
        """Owner only: take the lock whoever holds it."""
        async with self._modifying_session(project_id) as session:
            record, role = await self._require_member(session, project_id, principal)
            if role != ProjectRole.owner:
                raise ForbiddenError("Only the project owner can take over the write lock.")
            record = await self._apply_expiry(session, record, principal)
            if record.holder_id != principal.user_id:
                await self._set_holder(session, project_id, principal.user_id)
            return await self._access(session, project_id, principal)

    async def force_release(self, project_id: str, principal: Principal) -> ProjectAccess:
        """Super admin only. Audited."""
        async with self._modifying_session(project_id) as session:
            record = await self._require_super_admin(session, project_id, principal)
            record = await self._apply_expiry(session, record, principal)
            if record.holder_id is not None:
                await self._set_holder(session, project_id, None)
                await session.insert_audit_entry(
                    project_id,
                    _actor(principal),
                    AUDIT_LOCK_FORCE_RELEASED,
                    {"holder_id": record.holder_id},
                    self._now(),
                )
            return await self._access(session, project_id, principal)

    # ----------------------------------------------------------------------------------------------------------------
    # Write requests

    async def create_request(self, project_id: str, principal: Principal) -> WriteRequestInfo:
        """Members, when someone else holds the lock. At most one pending request per user."""
        async with self._modifying_session(project_id) as session:
            record, _ = await self._require_member(session, project_id, principal)
            record = await self._apply_expiry(session, record, principal)
            if record.holder_id is None:
                raise ConflictError("Nobody holds the write lock of this project; acquire it instead.")
            if record.holder_id == principal.user_id:
                raise ConflictError("You already hold the write lock of this project.")
            if any(
                r.requester_id == principal.user_id and r.status == WriteRequestStatus.pending for r in record.requests
            ):
                raise ConflictError("You already have a pending write request on this project.")
            assert principal.user_id is not None  # noqa: S101 #nosec  (members always have a user id)
            return await session.insert_write_request(project_id, principal.user_id, self._now())

    async def withdraw_request(self, project_id: str, request_id: str, principal: Principal) -> ProjectAccess:
        """Requester only."""
        async with self._modifying_session(project_id) as session:
            record, _ = await self._require_member(session, project_id, principal)
            request = next((r for r in record.requests if r.id == request_id), None)
            if request is not None and request.requester_id != principal.user_id:
                raise ForbiddenError("Only the requester can withdraw a write request.")
            self._pending_request(record, request_id)
            await session.set_write_request_status(
                request_id,
                WriteRequestStatus.withdrawn,
                principal.user_id,
                self._now(),
            )
            return await self._access(session, project_id, principal)

    async def approve_request(self, project_id: str, request_id: str, principal: Principal) -> ProjectAccess:
        """Owner or holder: the lock moves to the requester. Other pending requests stay pending."""
        async with self._modifying_session(project_id) as session:
            record, role = await self._require_member(session, project_id, principal)
            record = await self._apply_expiry(session, record, principal)
            request = self._decidable_request(record, role, request_id, principal)
            if _role_of(record, request.requester_id) is None:
                raise ConflictError("The requester is no longer a member of this project.")
            if record.holder_id != request.requester_id:
                await self._set_holder(session, project_id, request.requester_id)
            await session.set_write_request_status(
                request_id,
                WriteRequestStatus.approved,
                principal.user_id,
                self._now(),
            )
            return await self._access(session, project_id, principal)

    async def deny_request(self, project_id: str, request_id: str, principal: Principal) -> ProjectAccess:
        """Owner or holder."""
        async with self._modifying_session(project_id) as session:
            record, role = await self._require_member(session, project_id, principal)
            record = await self._apply_expiry(session, record, principal)
            self._decidable_request(record, role, request_id, principal)
            await session.set_write_request_status(
                request_id, WriteRequestStatus.denied, principal.user_id, self._now()
            )
            return await self._access(session, project_id, principal)

    def _decidable_request(
        self,
        record: ProjectAccessRecord,
        role: ProjectRole,
        request_id: str,
        principal: Principal,
    ) -> WriteRequestInfo:
        if not any(r.id == request_id for r in record.requests):
            raise NotFoundError(f"Write request '{request_id}' not found.")
        if role != ProjectRole.owner and record.holder_id != principal.user_id:
            raise ForbiddenError("Only the project owner or the lock holder can decide on write requests.")
        return self._pending_request(record, request_id)

    # ----------------------------------------------------------------------------------------------------------------
    # Members and ownership

    async def _require_owner(
        self,
        session: AbstractRepositorySession,
        project_id: str,
        principal: Principal,
    ) -> ProjectAccessRecord:
        record, role = await self._require_member(session, project_id, principal)
        if role != ProjectRole.owner:
            raise ForbiddenError("Only the project owner can perform this action.")
        return record

    async def share(self, project_id: str, user_id: str, principal: Principal) -> ProjectAccess:
        """Owner only: add ``user_id`` as a viewer."""
        async with self._modifying_session(project_id) as session:
            record = await self._require_owner(session, project_id, principal)
            role = _role_of(record, user_id)
            if role == ProjectRole.owner:
                raise ConflictError("The project owner is already a member.")
            if role is None:
                await session.upsert_member(project_id, user_id, ProjectRole.viewer)
            return await self._access(session, project_id, principal)

    async def unshare(self, project_id: str, user_id: str, principal: Principal) -> ProjectAccess:
        """Owner only: remove a viewer. Removing the holder releases the lock; their pending requests are denied."""
        async with self._modifying_session(project_id) as session:
            record = await self._require_owner(session, project_id, principal)
            role = _role_of(record, user_id)
            if role == ProjectRole.owner:
                raise ConflictError("The project owner cannot be removed; transfer the ownership first.")
            if role is None:
                raise NotFoundError(f"User '{user_id}' is not a member of project '{project_id}'.")
            record = await self._apply_expiry(session, record, principal)
            if record.holder_id == user_id:
                await self._set_holder(session, project_id, None)
            for request in record.requests:
                if request.requester_id == user_id and request.status == WriteRequestStatus.pending:
                    await session.set_write_request_status(
                        request.id,
                        WriteRequestStatus.denied,
                        principal.user_id,
                        self._now(),
                    )
            await session.delete_member(project_id, user_id)
            return await self._access(session, project_id, principal)

    async def transfer_ownership(self, project_id: str, user_id: str, principal: Principal) -> ProjectAccess:
        """Owner only, to an existing member. The previous owner stays as a viewer; the lock is unchanged. Audited."""
        async with self._modifying_session(project_id) as session:
            record = await self._require_owner(session, project_id, principal)
            if _role_of(record, user_id) is None:
                raise ConflictError("Ownership can only be transferred to a member of the project.")
            if user_id != principal.user_id:
                assert principal.user_id is not None  # noqa: S101 #nosec  (owners always have a user id)
                await session.upsert_member(project_id, user_id, ProjectRole.owner)
                await session.upsert_member(project_id, principal.user_id, ProjectRole.viewer)
                await session.insert_audit_entry(
                    project_id,
                    principal.user_id,
                    AUDIT_OWNERSHIP_TRANSFERRED,
                    {"from": principal.user_id, "to": user_id},
                    self._now(),
                )
            return await self._access(session, project_id, principal)

    async def assign_owner(self, project_id: str, user_id: str, principal: Principal) -> ProjectAccess:
        """Super admin only: ``user_id`` becomes the owner (and a member). The previous owner becomes a viewer.
        Audited.
        """
        if not (principal.is_super_admin or _is_bypass(principal)):
            raise ForbiddenError("Only a super admin can assign the owner of a project.")
        async with self._modifying_session(project_id) as session:
            record = await self._require_existing(session, project_id)
            previous_owner = _owner_of(record)
            if previous_owner != user_id:
                await session.upsert_member(project_id, user_id, ProjectRole.owner)
                if previous_owner is not None:
                    await session.upsert_member(project_id, previous_owner, ProjectRole.viewer)
                await session.insert_audit_entry(
                    project_id,
                    _actor(principal),
                    AUDIT_OWNER_ASSIGNED,
                    {"from": previous_owner, "to": user_id},
                    self._now(),
                )
            return await self._access(session, project_id, principal)

    # ----------------------------------------------------------------------------------------------------------------
    # Super admin and maintenance

    async def record_deletion(self, project_id: str, principal: Principal) -> None:
        """Record that a super admin deleted the project. No-op for owners and when the feature is off.

        Audit rows deliberately outlive the project (no foreign key), so this must run before the project is removed.
        """
        if not self._enabled or _is_bypass(principal) or not principal.is_super_admin:
            return
        async with self._session_factory.get_session(modification=True) as session:
            await session.insert_audit_entry(
                project_id,
                _actor(principal),
                AUDIT_PROJECT_DELETED,
                {},
                self._now(),
            )

    async def fail_stuck_methods(self, project_id: str, principal: Principal) -> list[str]:
        """Owner or super admin: mark failed the methods running for longer than the stuck-method timeout. Audited.

        Returns the ``"step.method"`` names of the methods marked failed.
        """
        async with self._modifying_session(project_id) as session:
            if principal.is_super_admin or _is_bypass(principal):
                await self._require_existing(session, project_id)
            else:
                await self._require_owner(session, project_id, principal)
            now = self._now()
            timeout = timedelta(seconds=self._settings.glow_project_stuck_method_timeout)
            stuck = [
                (step_name, method_name)
                for step_name, method_name, started_at in await session.get_running_methods_with_start(project_id)
                if started_at is None or now - started_at > timeout
            ]
            message = f"Marked as failed by {_actor(principal)}: exceeded stuck-method timeout"
            for step_name, method_name in stuck:
                await session.mark_method_failed(project_id, step_name, method_name, message)
            names = [f"{step_name}.{method_name}" for step_name, method_name in stuck]
            if names:
                await session.insert_audit_entry(
                    project_id,
                    _actor(principal),
                    AUDIT_METHODS_FAILED,
                    {"methods": names},
                    now,
                )
            return names

    async def list_audit(
        self,
        project_id: str | None,
        page: int,
        page_size: int,
        principal: Principal,
    ) -> list[AuditEntryInfo]:
        """Super admin only. Most recent entries first."""
        if not (principal.is_super_admin or _is_bypass(principal)):
            raise ForbiddenError("Only a super admin can read the audit log.")
        async with self._session_factory.get_session() as session:
            return await session.list_audit_entries(project_id, page, page_size)
