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
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from ansys.saf.glow._config.const import DatabaseType, Deployment
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._crud.project_builder import ProjectBuilder
from ansys.saf.glow._repository.abstract_repository import AbstractRepositorySession, AbstractRepositorySessionFactory
from ansys.saf.glow._repository.postgresql import PostgresqlSessionFactory
from ansys.saf.glow._repository.relational import RelationalSession
from ansys.saf.glow._repository.relational_models import Base
from ansys.saf.glow._repository.sqlite_factory import SqliteSessionFactory
from ansys.saf.glow._server.schemas import ModifyProjectRequest
from ansys.saf.glow._server.solution import SolutionService
from ansys.saf.testing.database import PostgresqlServerInfo
import tests.mocks.solutions.minimal_solution as minimal_solution_module


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
    else:
        settings.glow_database_type = DatabaseType.PostgreSql
        settings.glow_database_location = get_temp_postgresql_database().url
        return PostgresqlSessionFactory(settings, solution_service)


@pytest.fixture(params=["sqlite", "postgresql"])
async def session_factory_schema_without_description(
    request: pytest.FixtureRequest,
    solution_service: SolutionService,
    get_temp_postgresql_database: Callable[[], PostgresqlServerInfo],
    tmp_path: Path,
):
    settings = Settings(
        glow_solution_definition=minimal_solution_module.__name__,  # pyright: ignore[reportPrivateLocalImportUsage]
        glow_deployment=Deployment.Desktop,
    )
    database_url: str
    if request.param == "sqlite":
        sqlite_file = tmp_path / "legacy_projects_without_description.sqlite"
        database_url = f"sqlite+aiosqlite:///{sqlite_file.as_posix()}"
        settings.glow_database_location = sqlite_file
        factory = SqliteSessionFactory(settings, solution_service)
    else:
        postgres_server_info = get_temp_postgresql_database()
        database_url = str(postgres_server_info.url).replace("postgresql:", "postgresql+asyncpg:", 1)
        settings.glow_database_type = DatabaseType.PostgreSql
        settings.glow_database_location = postgres_server_info.url
        factory = PostgresqlSessionFactory(settings, solution_service)

    legacy_engine = create_async_engine(database_url)
    async with legacy_engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE projects ("
                "id VARCHAR PRIMARY KEY, "
                "date_created TIMESTAMP NOT NULL, "
                "date_modified TIMESTAMP NOT NULL, "
                "project_display_name VARCHAR NOT NULL, "
                "solution_display_name VARCHAR NOT NULL, "
                "glow_schema_version INTEGER NOT NULL, "
                "solution_schema_version INTEGER NOT NULL"
                ")",
            ),
        )
        now = datetime.now()
        await conn.execute(
            text(
                "INSERT INTO projects "
                "(id, date_created, date_modified, project_display_name, solution_display_name, "
                "glow_schema_version, solution_schema_version) "
                "VALUES (:id, :date_created, :date_modified, :display_name, :solution_display_name, "
                ":glow_schema_version, :solution_schema_version)",
            ),
            {
                "id": "legacy-project",
                "date_created": now,
                "date_modified": now,
                "display_name": "Legacy",
                "solution_display_name": "MinimalSolution",
                "glow_schema_version": 1,
                "solution_schema_version": 1,
            },
        )
    await legacy_engine.dispose()

    return factory


async def check_database_empty(session: AbstractRepositorySession) -> None:
    # lets just make this assumption for now
    assert isinstance(session, RelationalSession)

    for table in Base.metadata.tables.values():
        if table.name != "hps_auth":
            statement = select(1).select_from(table)
            internal_session = session._session  # pyright: ignore[reportPrivateUsage]
            result = await internal_session.scalar(statement)
            assert result is None, f"Table {table.name} is not empty"


@pytest.mark.parametrize("solution_service", [minimal_solution_module], indirect=True)
async def test_database_is_empty_after_deleting_project(
    solution_service: SolutionService,
    session_factory: AbstractRepositorySessionFactory,
) -> None:
    async with session_factory.get_session() as session:
        project = ProjectBuilder.build_project_model("DISPLAY_NAME", solution_service)
        project_info = await session.build_project_in_database(project)
        project_id = project_info.project_id.split("/")[-1]
        await session.remove_project_from_database(project_id)
        await check_database_empty(session)


@pytest.mark.parametrize("solution_service", [minimal_solution_module], indirect=True)
async def test_add_projects_description_column_for_existing_database(
    session_factory_schema_without_description: AbstractRepositorySessionFactory,
) -> None:
    project_id = "legacy-project"
    async with session_factory_schema_without_description.get_session() as session:
        modified_project_info, _ = await session.get_project_as_dict(project_id)
        assert modified_project_info.description == ""

        modify_request = ModifyProjectRequest(description="Repository description")
        await session.modify_project_info(project_id, modify_request)
        modified_project_info, _ = await session.get_project_as_dict(project_id)
        assert modified_project_info.description == "Repository description"
