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

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from ansys.saf.glow._access.schemas import (
    ProjectMemberInfo,
    ProjectRole,
    WriteRequestStatus,
)
from ansys.saf.glow._config.const import DatabaseType, Deployment
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.method_status import MethodStatus
from ansys.saf.glow._crud.project_builder import ProjectBuilder
from ansys.saf.glow._repository.abstract_repository import AbstractRepositorySession, AbstractRepositorySessionFactory
from ansys.saf.glow._repository.postgresql import PostgresqlSessionFactory
from ansys.saf.glow._repository.relational import RelationalSession
from ansys.saf.glow._repository.relational_models import (
    Base,
    MethodState,
    ProjectAuditEntry,
    ProjectMember,
    ProjectWriteLock,
    ProjectWriteRequest,
)
from ansys.saf.glow._repository.sqlite_factory import SqliteSessionFactory
from ansys.saf.glow._server.solution import SolutionService
from ansys.saf.testing.database import PostgresqlServerInfo
import tests.mocks.solutions.minimal_solution as minimal_solution_module

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

pytestmark = pytest.mark.parametrize("solution_service", [minimal_solution_module], indirect=True)


@pytest.fixture(params=["sqlite", "postgresql"])
async def session_factory(
    request: pytest.FixtureRequest,
    solution_service: SolutionService,
    get_temp_postgresql_database: Callable[[], PostgresqlServerInfo],
):
    settings = Settings(
        glow_solution_definition=minimal_solution_module.__name__,  # pyright: ignore[reportPrivateLocalImportUsage]
        glow_deployment=Deployment.Desktop,
    )
    if request.param == "sqlite":
        return SqliteSessionFactory(settings, solution_service)
    settings.glow_database_type = DatabaseType.PostgreSql
    settings.glow_database_location = get_temp_postgresql_database().url
    return PostgresqlSessionFactory(settings, solution_service)


async def _create_project(session: AbstractRepositorySession, solution_service: SolutionService, name: str) -> str:
    project = ProjectBuilder.build_project_model(name, solution_service)
    info = await session.build_project_in_database(project)
    return info.project_id.split("/")[-1]


async def test_member_roundtrip(solution_service: SolutionService, session_factory: AbstractRepositorySessionFactory):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        await session.upsert_member(pid, "u1", ProjectRole.owner)
        await session.upsert_member(pid, "u2", ProjectRole.viewer)
        record = await session.get_access_record(pid)
    assert record.members == [
        ProjectMemberInfo(user_id="u1", role=ProjectRole.owner),
        ProjectMemberInfo(user_id="u2", role=ProjectRole.viewer),
    ]


async def test_upsert_member_changes_role(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        await session.upsert_member(pid, "u1", ProjectRole.viewer)
        await session.upsert_member(pid, "u1", ProjectRole.owner)
        record = await session.get_access_record(pid)
    assert record.members == [ProjectMemberInfo(user_id="u1", role=ProjectRole.owner)]


async def test_delete_member(solution_service: SolutionService, session_factory: AbstractRepositorySessionFactory):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        await session.upsert_member(pid, "u1", ProjectRole.owner)
        await session.upsert_member(pid, "u2", ProjectRole.viewer)
        await session.delete_member(pid, "u2")
        record = await session.get_access_record(pid)
    assert [m.user_id for m in record.members] == ["u1"]


async def test_access_record_of_project_without_access_rows(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        record = await session.get_access_record(pid)
    assert record.project_id == pid
    assert record.members == []
    assert record.holder_id is None
    assert record.version == 0
    assert record.requests == []


async def test_lock_version_increments(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        await session.set_lock_holder(pid, "u1", NOW)
        await session.touch_lock(pid, NOW + timedelta(minutes=1))
        record = await session.get_access_record(pid)
    assert record.version == 2
    assert record.holder_id == "u1"
    assert record.acquired_at == NOW
    assert record.last_write_at == NOW + timedelta(minutes=1)


async def test_release_lock_clears_holder(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        await session.set_lock_holder(pid, "u1", NOW)
        await session.set_lock_holder(pid, None, NOW)
        record = await session.get_access_record(pid)
    assert record.holder_id is None
    assert record.acquired_at is None
    assert record.version == 2


async def test_member_changes_bump_version(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        await session.upsert_member(pid, "u1", ProjectRole.owner)
        await session.delete_member(pid, "u1")
        record = await session.get_access_record(pid)
    assert record.version == 2


async def test_write_request_lifecycle(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        request = await session.insert_write_request(pid, "u2", NOW)
        assert request.status == WriteRequestStatus.pending
        assert request.requester_id == "u2"
        assert request.decided_by is None
        decided = await session.set_write_request_status(
            request.id,
            WriteRequestStatus.approved,
            "u1",
            NOW + timedelta(seconds=5),
        )
        record = await session.get_access_record(pid)
    assert decided.status == WriteRequestStatus.approved
    assert decided.decided_by == "u1"
    assert decided.decided_at == NOW + timedelta(seconds=5)
    assert record.requests == [decided]
    assert record.version == 2


async def test_access_summaries(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        p1 = await _create_project(session, solution_service, "p1")
        p2 = await _create_project(session, solution_service, "p2")
        await session.upsert_member(p1, "u1", ProjectRole.owner)
        await session.upsert_member(p1, "u2", ProjectRole.viewer)
        await session.set_lock_holder(p1, "u1", NOW)
        await session.insert_write_request(p1, "u2", NOW)
        denied = await session.insert_write_request(p1, "u3", NOW)
        await session.set_write_request_status(denied.id, WriteRequestStatus.denied, "u1", NOW)
        summaries = await session.get_access_summaries([p1, p2], "u2")
        anonymous = await session.get_access_summaries([p1], None)
    assert summaries[p1].owner_id == "u1"
    assert summaries[p1].holder_id == "u1"
    assert summaries[p1].my_role == ProjectRole.viewer
    assert summaries[p1].pending_request_count == 1
    assert summaries[p1].member_ids == ["u1", "u2"]
    assert summaries[p2].owner_id is None
    assert summaries[p2].holder_id is None
    assert summaries[p2].my_role is None
    assert summaries[p2].pending_request_count == 0
    assert summaries[p2].member_ids == []
    assert anonymous[p1].my_role is None
    assert anonymous[p1].member_ids == ["u1", "u2"]


async def test_audit_entries(solution_service: SolutionService, session_factory: AbstractRepositorySessionFactory):
    async with session_factory.get_session(modification=True) as session:
        p1 = await _create_project(session, solution_service, "p1")
        p2 = await _create_project(session, solution_service, "p2")
        for index in range(3):
            await session.insert_audit_entry(p1, "u1", f"a{index}", {"n": index}, NOW + timedelta(seconds=index))
        await session.insert_audit_entry(p2, "u2", "other", {}, NOW)
        for_p1 = await session.list_audit_entries(p1, page=1, page_size=2)
        second_page = await session.list_audit_entries(p1, page=2, page_size=2)
        everything = await session.list_audit_entries(None, page=1, page_size=10)
    # newest first
    assert [e.action for e in for_p1] == ["a2", "a1"]
    assert for_p1[0].details == {"n": 2}
    assert for_p1[0].at == NOW + timedelta(seconds=2)
    assert [e.action for e in second_page] == ["a0"]
    assert len(everything) == 4


async def test_list_projects_filters_by_member(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        p1 = await _create_project(session, solution_service, "p1")
        p2 = await _create_project(session, solution_service, "p2")
        await _create_project(session, solution_service, "p3")
        await session.upsert_member(p1, "u1", ProjectRole.owner)
        await session.upsert_member(p2, "u1", ProjectRole.viewer)
        await session.upsert_member(p2, "u2", ProjectRole.owner)
        result = await session.list_projects(page_size=10, page=1, member_id="u1")
        everything = await session.list_projects(page_size=10, page=1)
    assert result.total_projects == 2
    assert {p.name for p in result.projects} == {f"projects/{p1}", f"projects/{p2}"}
    assert everything.total_projects == 3


async def test_list_projects_orphans_only(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        p1 = await _create_project(session, solution_service, "p1")
        p2 = await _create_project(session, solution_service, "p2")
        p3 = await _create_project(session, solution_service, "p3")
        await session.upsert_member(p1, "u1", ProjectRole.owner)
        await session.upsert_member(p2, "u1", ProjectRole.viewer)  # viewer only: still an orphan
        result = await session.list_projects(page_size=10, page=1, orphans_only=True)
    assert result.total_projects == 2
    assert {p.name for p in result.projects} == {f"projects/{p2}", f"projects/{p3}"}


async def test_remove_project_deletes_access_rows(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        await session.upsert_member(pid, "u1", ProjectRole.owner)
        await session.set_lock_holder(pid, "u1", NOW)
        await session.insert_write_request(pid, "u2", NOW)
        await session.insert_audit_entry(pid, "u1", "created", {}, NOW)
        await session.remove_project_from_database(pid)

        assert isinstance(session, RelationalSession)
        internal = session._session  # pyright: ignore[reportPrivateUsage]
        for table in (ProjectMember, ProjectWriteLock, ProjectWriteRequest):
            assert await internal.scalar(select(func.count()).select_from(table)) == 0
        assert await internal.scalar(select(func.count()).select_from(ProjectAuditEntry)) == 1


async def test_started_at_set_when_running(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
):
    async with session_factory.get_session(modification=True) as session:
        assert isinstance(session, RelationalSession)
        internal = session._session  # pyright: ignore[reportPrivateUsage]
        pid = await _create_project(session, solution_service, "p")
        before = datetime.now(UTC)
        await session.update_method_state(pid, "step", "method", {"status": MethodStatus.Running})
        started_at = await internal.scalar(select(MethodState.started_at).where(MethodState.method_name == "method"))
        running = await session.get_running_methods_with_start(pid)
        await session.update_method_state(pid, "step", "other", {"status": MethodStatus.Completed})
        not_started = await internal.scalar(select(MethodState.started_at).where(MethodState.method_name == "other"))
    assert started_at is not None
    assert not_started is None
    assert len(running) == 1
    step_name, method_name, run_started_at = running[0]
    assert (step_name, method_name) == ("step", "method")
    assert run_started_at is not None
    assert run_started_at.tzinfo is not None
    assert run_started_at >= before - timedelta(seconds=1)


async def test_mark_method_failed(solution_service: SolutionService, session_factory: AbstractRepositorySessionFactory):
    async with session_factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "p")
        await session.update_method_state(pid, "step", "method", {"status": MethodStatus.Running})
        await session.mark_method_failed(pid, "step", "method", "stuck")
        state = await session.get_method_state(pid, "step", "method")
        running = await session.get_running_methods_with_start(pid)
    assert state.status == MethodStatus.Failed
    assert state.exception_message == "stuck"
    assert running == []


async def test_add_started_at_column_for_existing_database(solution_service: SolutionService, tmp_path: Path):
    sqlite_file = tmp_path / "legacy_method_states.sqlite"
    settings = Settings(
        glow_solution_definition=minimal_solution_module.__name__,  # pyright: ignore[reportPrivateLocalImportUsage]
        glow_deployment=Deployment.Desktop,
    )
    settings.glow_database_location = sqlite_file
    engine = create_async_engine(f"sqlite+aiosqlite:///{sqlite_file.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE method_states DROP COLUMN started_at"))
    await engine.dispose()

    factory = SqliteSessionFactory(settings, solution_service)
    async with factory.get_session(modification=True) as session:
        pid = await _create_project(session, solution_service, "legacy")
        await session.update_method_state(pid, "step", "method", {"status": MethodStatus.Running})
        running = await session.get_running_methods_with_start(pid)
    assert len(running) == 1
    assert running[0][2] is not None
