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

"""Rules of project access control (ownership, sharing, write lock, write requests, super admin)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import update

from ansys.saf.glow._access.access_crud import AccessCrud
from ansys.saf.glow._access.principal import Principal
from ansys.saf.glow._access.schemas import ProjectMemberInfo, ProjectRole, WriteRequestStatus
from ansys.saf.glow._config.const import Deployment
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.method_status import MethodStatus
from ansys.saf.glow._crud.project_builder import ProjectBuilder
from ansys.saf.glow._repository.abstract_repository import ProjectLockSpecification
from ansys.saf.glow._repository.relational import RelationalSession
from ansys.saf.glow._repository.relational_models import MethodState
from ansys.saf.glow._repository.sqlite_factory import SqliteSessionFactory
from ansys.saf.glow._server.exceptions import ConflictError, ForbiddenError, LockedError, NotFoundError
from ansys.saf.glow._server.solution import SolutionService
import tests.mocks.solutions.minimal_solution as minimal_solution_module

pytestmark = pytest.mark.parametrize("solution_service", [minimal_solution_module], indirect=True)

ALICE = Principal(user_id="alice", is_super_admin=False, is_internal=False)
BOB = Principal(user_id="bob", is_super_admin=False, is_internal=False)
CAROL = Principal(user_id="carol", is_super_admin=False, is_internal=False)
ADMIN = Principal(user_id="admin", is_super_admin=True, is_internal=False)
INTERNAL = Principal(user_id=None, is_super_admin=False, is_internal=True)
IDLE_TIMEOUT = 28800
STUCK_TIMEOUT = 86400


@dataclass
class Env:
    access: AccessCrud
    factory: SqliteSessionFactory
    settings: Settings
    solution_service: SolutionService
    clock: list[datetime]
    project_id: str

    def advance(self, seconds: float) -> None:
        self.clock[0] = self.clock[0] + timedelta(seconds=seconds)

    async def new_project(self, name: str) -> str:
        async with self.factory.get_session(modification=True) as session:
            project = ProjectBuilder.build_project_model(name, self.solution_service)
            info = await session.build_project_in_database(project)
        return info.project_id.split("/")[-1]

    async def set_status(self, status: MethodStatus) -> None:
        async with self.factory.get_session(modification=True) as session:
            await session.update_method_state(self.project_id, "step", "method", {"status": status})


@pytest.fixture
async def env(solution_service: SolutionService) -> Env:
    settings = Settings(
        glow_solution_definition=minimal_solution_module.__name__,  # pyright: ignore[reportPrivateLocalImportUsage]
        glow_deployment=Deployment.Desktop,
        glow_project_access_control_enabled=True,
        glow_project_lock_idle_timeout=IDLE_TIMEOUT,
        glow_project_stuck_method_timeout=STUCK_TIMEOUT,
    )
    factory = SqliteSessionFactory(settings, solution_service)
    clock = [datetime.now(UTC)]
    access = AccessCrud(factory, settings, now=lambda: clock[0])
    environment = Env(access, factory, settings, solution_service, clock, "")
    environment.project_id = await environment.new_project("p")
    await access.on_project_created(environment.project_id, ALICE)
    return environment


async def _share(env: Env, *user_ids: str) -> None:
    for user_id in user_ids:
        await env.access.share(env.project_id, user_id, ALICE)


async def _bob_holds(env: Env) -> None:
    await _share(env, "bob")
    await env.access.release(env.project_id, ALICE)
    await env.access.acquire(env.project_id, BOB)


async def test_creator_is_owner_and_holder(env: Env):
    access = await env.access.get_access(env.project_id, ALICE)
    assert access.owner_id == "alice"
    assert access.holder_id == "alice"
    assert access.members == [ProjectMemberInfo(user_id="alice", role=ProjectRole.owner)]
    assert access.my_role == ProjectRole.owner
    assert access.can_write is True
    assert access.is_orphan is False
    assert access.lock_acquired_at == env.clock[0]
    assert access.last_write_at == env.clock[0]


async def test_list_scope(env: Env):
    nobody = Principal(user_id=None, is_super_admin=False, is_internal=False)
    assert env.access.list_scope(ALICE) == "alice"
    assert env.access.list_scope(ADMIN) is None
    assert env.access.list_scope(INTERNAL) is None
    with pytest.raises(ForbiddenError):
        env.access.list_scope(nobody)


async def test_non_member_read_is_404(env: Env):
    with pytest.raises(NotFoundError):
        await env.access.check_read(env.project_id, CAROL)
    with pytest.raises(NotFoundError):
        await env.access.check_metadata(env.project_id, CAROL)
    with pytest.raises(NotFoundError):
        await env.access.get_access(env.project_id, CAROL)
    with pytest.raises(NotFoundError):
        await env.access.check_write(env.project_id, CAROL)
    await env.access.check_read(env.project_id, ALICE)


async def test_super_admin_metadata_ok_but_read_404(env: Env):
    await env.access.check_metadata(env.project_id, ADMIN)
    access = await env.access.get_access(env.project_id, ADMIN)
    assert access.my_role is None
    assert access.can_write is False
    with pytest.raises(NotFoundError):
        await env.access.check_read(env.project_id, ADMIN)
    with pytest.raises(NotFoundError):
        await env.access.check_write(env.project_id, ADMIN)
    with pytest.raises(NotFoundError):
        await env.access.check_owner(env.project_id, ADMIN)
    await env.access.check_owner(env.project_id, ADMIN, allow_super_admin=True)
    with pytest.raises(NotFoundError):
        await env.access.check_metadata("missing-project", ADMIN)


async def test_viewer_write_is_423_with_holder(env: Env):
    await _share(env, "bob")
    with pytest.raises(LockedError) as error:
        await env.access.check_write(env.project_id, BOB)
    assert error.value.status_code == 423
    detail = cast("Any", error.value.detail)
    assert isinstance(detail, dict)
    assert detail["holder_id"] == "alice"
    assert detail["message"]
    await env.access.release(env.project_id, ALICE)
    with pytest.raises(LockedError) as error:
        await env.access.check_write(env.project_id, BOB)
    assert cast("Any", error.value.detail)["holder_id"] is None


async def test_acquire_free_lock(env: Env):
    await _share(env, "bob")
    await env.access.release(env.project_id, ALICE)
    access = await env.access.acquire(env.project_id, BOB)
    assert access.holder_id == "bob"
    assert access.can_write is True
    await env.access.check_write(env.project_id, BOB)


async def test_acquire_held_lock_conflicts(env: Env):
    await _share(env, "bob")
    with pytest.raises(ConflictError):
        await env.access.acquire(env.project_id, BOB)
    await env.access.release(env.project_id, ALICE)
    await env.access.acquire(env.project_id, BOB)
    with pytest.raises(ConflictError):
        await env.access.acquire(env.project_id, ALICE)
    with pytest.raises(NotFoundError):
        await env.access.acquire(env.project_id, CAROL)


async def test_release_by_non_holder_403(env: Env):
    await _share(env, "bob")
    with pytest.raises(ForbiddenError):
        await env.access.release(env.project_id, BOB)
    with pytest.raises(NotFoundError):
        await env.access.release(env.project_id, CAROL)
    access = await env.access.release(env.project_id, ALICE)
    assert access.holder_id is None


async def test_owner_take_over(env: Env):
    await _bob_holds(env)
    with pytest.raises(ForbiddenError):
        await env.access.take_over(env.project_id, BOB)
    access = await env.access.take_over(env.project_id, ALICE)
    assert access.holder_id == "alice"


async def test_take_over_while_running_conflicts(env: Env):
    await _bob_holds(env)
    await env.set_status(MethodStatus.Running)
    with pytest.raises(ConflictError) as error:
        await env.access.take_over(env.project_id, ALICE)
    assert error.value.detail == "A transaction is running on this project; try again when it finishes."
    assert (await env.access.get_access(env.project_id, ALICE)).holder_id == "bob"


async def test_lock_expires_after_idle_timeout(env: Env):
    env.advance(IDLE_TIMEOUT)
    assert (await env.access.get_access(env.project_id, ALICE)).holder_id == "alice"
    env.advance(1)
    access = await env.access.get_access(env.project_id, ALICE)
    assert access.holder_id is None
    entries = await env.access.list_audit(env.project_id, 1, 100, ADMIN)
    assert [entry.action for entry in entries] == ["lock_expired"]
    assert entries[0].details == {"holder_id": "alice"}


async def test_lock_does_not_expire_while_running(env: Env):
    await env.set_status(MethodStatus.Running)
    env.advance(IDLE_TIMEOUT + 1)
    assert (await env.access.get_access(env.project_id, ALICE)).holder_id == "alice"
    await env.access.check_write(env.project_id, ALICE)


async def test_write_touches_last_write_at(env: Env):
    env.advance(IDLE_TIMEOUT - 10)
    await env.access.check_write(env.project_id, ALICE)
    assert (await env.access.get_access(env.project_id, ALICE)).last_write_at == env.clock[0]
    env.advance(20)
    assert (await env.access.get_access(env.project_id, ALICE)).holder_id == "alice"
    before = (await env.access.get_access(env.project_id, ALICE)).last_write_at
    env.advance(5)
    await env.access.check_write(env.project_id, ALICE, touch=False)
    assert (await env.access.get_access(env.project_id, ALICE)).last_write_at == before


async def test_request_when_free_conflicts(env: Env):
    await _share(env, "bob")
    with pytest.raises(ConflictError):
        await env.access.create_request(env.project_id, ALICE)
    await env.access.release(env.project_id, ALICE)
    with pytest.raises(ConflictError):
        await env.access.create_request(env.project_id, BOB)
    with pytest.raises(NotFoundError):
        await env.access.create_request(env.project_id, CAROL)


async def test_single_pending_request_per_user(env: Env):
    await _share(env, "bob")
    request = await env.access.create_request(env.project_id, BOB)
    assert request.requester_id == "bob"
    assert request.status == WriteRequestStatus.pending
    with pytest.raises(ConflictError):
        await env.access.create_request(env.project_id, BOB)
    await env.access.withdraw_request(env.project_id, request.id, BOB)
    again = await env.access.create_request(env.project_id, BOB)
    access = await env.access.get_access(env.project_id, ALICE)
    assert [r.id for r in access.pending_requests] == [again.id]


async def test_approve_by_holder_moves_lock(env: Env):
    await _bob_holds(env)
    await _share(env, "carol")
    request = await env.access.create_request(env.project_id, CAROL)
    access = await env.access.approve_request(env.project_id, request.id, BOB)
    assert access.holder_id == "carol"
    assert access.pending_requests == []
    with pytest.raises(LockedError):
        await env.access.check_write(env.project_id, BOB)
    await env.access.check_write(env.project_id, CAROL)


async def test_approve_by_owner_when_not_holder(env: Env):
    await _bob_holds(env)
    await _share(env, "carol")
    request = await env.access.create_request(env.project_id, CAROL)
    access = await env.access.approve_request(env.project_id, request.id, ALICE)
    assert access.holder_id == "carol"
    with pytest.raises(ConflictError):
        await env.access.approve_request(env.project_id, request.id, ALICE)


async def test_viewer_cannot_approve_403(env: Env):
    await _share(env, "bob", "carol")
    request = await env.access.create_request(env.project_id, BOB)
    with pytest.raises(ForbiddenError):
        await env.access.approve_request(env.project_id, request.id, CAROL)
    with pytest.raises(ForbiddenError):
        await env.access.deny_request(env.project_id, request.id, CAROL)
    with pytest.raises(NotFoundError):
        await env.access.approve_request(env.project_id, "unknown-request", ALICE)
    access = await env.access.deny_request(env.project_id, request.id, ALICE)
    assert access.pending_requests == []
    assert access.holder_id == "alice"


async def test_request_of_other_project_is_404(env: Env):
    await _share(env, "bob")
    request = await env.access.create_request(env.project_id, BOB)
    other_id = await env.new_project("other")
    await env.access.on_project_created(other_id, ALICE)
    with pytest.raises(NotFoundError):
        await env.access.approve_request(other_id, request.id, ALICE)


async def test_other_requests_stay_pending_after_approve(env: Env):
    await _share(env, "bob", "carol")
    bob_request = await env.access.create_request(env.project_id, BOB)
    carol_request = await env.access.create_request(env.project_id, CAROL)
    access = await env.access.approve_request(env.project_id, bob_request.id, ALICE)
    assert access.holder_id == "bob"
    assert [r.id for r in access.pending_requests] == [carol_request.id]
    access = await env.access.approve_request(env.project_id, carol_request.id, BOB)
    assert access.holder_id == "carol"


async def test_withdraw_only_by_requester(env: Env):
    await _share(env, "bob", "carol")
    request = await env.access.create_request(env.project_id, BOB)
    with pytest.raises(ForbiddenError):
        await env.access.withdraw_request(env.project_id, request.id, ALICE)
    with pytest.raises(ForbiddenError):
        await env.access.withdraw_request(env.project_id, request.id, CAROL)
    access = await env.access.withdraw_request(env.project_id, request.id, BOB)
    assert access.pending_requests == []
    with pytest.raises(ConflictError):
        await env.access.withdraw_request(env.project_id, request.id, BOB)


async def test_share_and_unshare_owner_only(env: Env):
    await _share(env, "bob")
    with pytest.raises(ForbiddenError):
        await env.access.share(env.project_id, "carol", BOB)
    with pytest.raises(NotFoundError):
        await env.access.share(env.project_id, "dave", CAROL)
    access = await env.access.share(env.project_id, "carol", ALICE)
    assert ProjectMemberInfo(user_id="carol", role=ProjectRole.viewer) in access.members
    await env.access.check_read(env.project_id, CAROL)
    with pytest.raises(ForbiddenError):
        await env.access.unshare(env.project_id, "carol", BOB)
    access = await env.access.unshare(env.project_id, "carol", ALICE)
    assert "carol" not in [m.user_id for m in access.members]
    with pytest.raises(NotFoundError):
        await env.access.check_read(env.project_id, CAROL)


async def test_cannot_unshare_owner(env: Env):
    with pytest.raises(ConflictError):
        await env.access.unshare(env.project_id, "alice", ALICE)
    with pytest.raises(ConflictError):
        await env.access.share(env.project_id, "alice", ALICE)
    assert (await env.access.get_access(env.project_id, ALICE)).owner_id == "alice"


async def test_unshare_holder_releases_lock(env: Env):
    await _bob_holds(env)
    access = await env.access.unshare(env.project_id, "bob", ALICE)
    assert access.holder_id is None
    assert access.members == [ProjectMemberInfo(user_id="alice", role=ProjectRole.owner)]


async def test_unshare_holder_while_running_conflicts(env: Env):
    await _bob_holds(env)
    await env.set_status(MethodStatus.Running)
    with pytest.raises(ConflictError):
        await env.access.unshare(env.project_id, "bob", ALICE)
    access = await env.access.get_access(env.project_id, ALICE)
    assert access.holder_id == "bob"
    assert "bob" in [m.user_id for m in access.members]


async def test_transfer_requires_member(env: Env):
    with pytest.raises(ConflictError):
        await env.access.transfer_ownership(env.project_id, "bob", ALICE)
    await _share(env, "bob")
    with pytest.raises(ForbiddenError):
        await env.access.transfer_ownership(env.project_id, "bob", BOB)
    with pytest.raises(NotFoundError):
        await env.access.transfer_ownership(env.project_id, "bob", ADMIN)


async def test_transfer_keeps_old_owner_as_viewer_and_lock(env: Env):
    await _share(env, "bob")
    request = await env.access.create_request(env.project_id, BOB)
    access = await env.access.transfer_ownership(env.project_id, "bob", ALICE)
    assert access.owner_id == "bob"
    assert access.my_role == ProjectRole.viewer
    assert access.holder_id == "alice"
    assert [r.id for r in access.pending_requests] == [request.id]
    assert sorted(access.members, key=lambda m: m.user_id) == [
        ProjectMemberInfo(user_id="alice", role=ProjectRole.viewer),
        ProjectMemberInfo(user_id="bob", role=ProjectRole.owner),
    ]
    entries = await env.access.list_audit(env.project_id, 1, 100, ADMIN)
    assert [e.action for e in entries] == ["ownership_transferred"]
    assert entries[0].actor_id == "alice"
    assert entries[0].details == {"from": "alice", "to": "bob"}


async def test_assign_owner_super_admin_only(env: Env):
    await _share(env, "bob")
    with pytest.raises(ForbiddenError):
        await env.access.assign_owner(env.project_id, "bob", ALICE)
    with pytest.raises(ForbiddenError):
        await env.access.assign_owner(env.project_id, "bob", CAROL)
    access = await env.access.assign_owner(env.project_id, "carol", ADMIN)
    assert access.owner_id == "carol"
    assert {m.user_id: m.role for m in access.members} == {
        "alice": ProjectRole.viewer,
        "bob": ProjectRole.viewer,
        "carol": ProjectRole.owner,
    }
    entries = await env.access.list_audit(env.project_id, 1, 100, ADMIN)
    assert [e.action for e in entries] == ["owner_assigned"]
    assert entries[0].actor_id == "admin"
    assert entries[0].details == {"from": "alice", "to": "carol"}
    with pytest.raises(NotFoundError):
        await env.access.assign_owner("missing-project", "carol", ADMIN)


async def test_assign_owner_on_orphan(env: Env):
    orphan_id = await env.new_project("orphan")
    access = await env.access.get_access(orphan_id, ADMIN)
    assert access.is_orphan is True
    assert access.owner_id is None
    with pytest.raises(NotFoundError):
        await env.access.check_read(orphan_id, BOB)
    access = await env.access.assign_owner(orphan_id, "bob", ADMIN)
    assert access.owner_id == "bob"
    assert access.is_orphan is False
    assert access.holder_id is None
    await env.access.check_read(orphan_id, BOB)
    entries = await env.access.list_audit(orphan_id, 1, 100, ADMIN)
    assert entries[0].details == {"from": None, "to": "bob"}


async def test_fail_stuck_methods_respects_timeout(env: Env):
    await _share(env, "bob")
    await env.set_status(MethodStatus.Running)
    with pytest.raises(ForbiddenError):
        await env.access.fail_stuck_methods(env.project_id, BOB)
    with pytest.raises(NotFoundError):
        await env.access.fail_stuck_methods(env.project_id, CAROL)
    env.advance(23 * 3600)
    assert await env.access.fail_stuck_methods(env.project_id, ALICE) == []
    env.advance(3600 + 1)
    assert await env.access.fail_stuck_methods(env.project_id, ADMIN) == ["step.method"]
    async with env.factory.get_session() as session:
        state = await session.get_method_state(env.project_id, "step", "method")
    assert state.status == MethodStatus.Failed
    assert state.exception_message == "Marked as failed by admin: exceeded stuck-method timeout"
    entries = await env.access.list_audit(env.project_id, 1, 100, ADMIN)
    assert [e.action for e in entries] == ["methods_failed"]
    assert entries[0].details == {"methods": ["step.method"]}


async def test_fail_stuck_methods_null_started_at_is_eligible(env: Env):
    await env.set_status(MethodStatus.Running)
    async with env.factory.get_session(modification=True) as session:
        assert isinstance(session, RelationalSession)
        internal = session._session  # pyright: ignore[reportPrivateUsage]
        await internal.execute(update(MethodState).values(started_at=None))
    assert await env.access.fail_stuck_methods(env.project_id, ALICE) == ["step.method"]


async def test_force_release_audited(env: Env):
    await _share(env, "bob")
    with pytest.raises(ForbiddenError):
        await env.access.force_release(env.project_id, BOB)
    await env.set_status(MethodStatus.Running)
    with pytest.raises(ConflictError):
        await env.access.force_release(env.project_id, ADMIN)
    await env.set_status(MethodStatus.Completed)
    access = await env.access.force_release(env.project_id, ADMIN)
    assert access.holder_id is None
    entries = await env.access.list_audit(env.project_id, 1, 100, ADMIN)
    assert [e.action for e in entries] == ["lock_force_released"]
    assert entries[0].actor_id == "admin"
    assert entries[0].details == {"holder_id": "alice"}
    with pytest.raises(ForbiddenError):
        await env.access.list_audit(env.project_id, 1, 100, ALICE)
    assert [e.action for e in await env.access.list_audit(None, 1, 100, ADMIN)] == ["lock_force_released"]


async def test_record_deletion_audited_for_super_admin_only(env: Env):
    await env.access.record_deletion(env.project_id, ADMIN)
    entries = await env.access.list_audit(env.project_id, 1, 100, ADMIN)
    assert [e.action for e in entries] == ["project_deleted"]
    assert entries[0].actor_id == "admin"
    other_id = await env.new_project("q")
    await env.access.on_project_created(other_id, ALICE)
    await env.access.record_deletion(other_id, ALICE)
    assert await env.access.list_audit(other_id, 1, 100, ADMIN) == []


async def test_unidentified_principal_is_forbidden(env: Env):
    unidentified = Principal(user_id=None, is_super_admin=False, is_internal=False)
    with pytest.raises(ForbiddenError):
        await env.access.check_read(env.project_id, unidentified)
    with pytest.raises(ForbiddenError):
        await env.access.check_metadata(env.project_id, unidentified)
    with pytest.raises(ForbiddenError):
        await env.access.check_write(env.project_id, unidentified)
    with pytest.raises(ForbiddenError):
        env.access.list_scope(unidentified)
    with pytest.raises(ForbiddenError):
        await env.access.on_project_created(await env.new_project("q"), unidentified)


async def test_list_summaries_apply_lock_expiry(env: Env):
    from ansys.saf.glow._server.schemas import ProjectInfo

    await _share(env, "bob")
    env.advance(IDLE_TIMEOUT + 1)
    project = ProjectInfo(
        display_name="p",
        description="",
        date_created=env.clock[0],
        date_modified=env.clock[0],
        name=f"projects/{env.project_id}",
    )
    await env.access.fill_access_summaries([project], ALICE)
    assert project.access is not None
    assert project.access.holder_id is None
    assert project.access.member_ids == ["alice", "bob"]
    assert (await env.access.get_access(env.project_id, ALICE)).holder_id is None


async def test_disabled_feature_checks_are_noops(env: Env):
    env.settings.glow_project_access_control_enabled = False
    await env.access.check_read(env.project_id, CAROL)
    await env.access.check_metadata(env.project_id, CAROL)
    await env.access.check_write(env.project_id, CAROL)
    await env.access.check_owner(env.project_id, CAROL)
    other_id = await env.new_project("q")
    await env.access.on_project_created(other_id, BOB)
    env.settings.glow_project_access_control_enabled = True
    assert (await env.access.get_access(other_id, ADMIN)).members == []


async def test_check_write_joins_outer_project_session(env: Env):
    env.advance(10)
    async with env.factory.get_session(
        modification=True,
        project_id=env.project_id,
        lock_spec=ProjectLockSpecification(),
    ):
        await env.access.check_write(env.project_id, ALICE)
    assert (await env.access.get_access(env.project_id, ALICE)).last_write_at == env.clock[0]


async def test_internal_without_user_bypasses(env: Env):
    await env.access.check_read(env.project_id, INTERNAL)
    await env.access.check_metadata(env.project_id, INTERNAL)
    await env.access.check_write(env.project_id, INTERNAL)
    await env.access.check_owner(env.project_id, INTERNAL)
    on_behalf_of_bob = Principal(user_id="bob", is_super_admin=False, is_internal=True)
    with pytest.raises(NotFoundError):
        await env.access.check_read(env.project_id, on_behalf_of_bob)
    on_behalf_of_alice = Principal(user_id="alice", is_super_admin=False, is_internal=True)
    await env.access.check_write(env.project_id, on_behalf_of_alice)
