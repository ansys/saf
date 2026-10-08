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
from pathlib import Path
import random
from typing import TypeVar

from fastapi import status
import httpx2
from pydantic import PostgresDsn
import pytest

from ansys.saf.glow.client import Client, NotFoundException
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.database import PostgresqlServerInfo, create_postgres_database_url
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, PostgreSQLConfig
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_second_end_to_end.solution.definition import SecondSolution
from tests.mocks.solution_without_ui_in_ansys.solution.definition import MySolution

T = TypeVar("T", bound=Solution)


@pytest.fixture
def databases(
    solutions: list[T],
    get_temp_postgresql_database: Callable[[], PostgresqlServerInfo],
) -> list[PostgresDsn]:
    databases: list[PostgresDsn] = []
    for _ in range(len(solutions)):
        databases.append(get_temp_postgresql_database().url)
    return databases


@pytest.mark.parametrize(
    "solutions",
    [[EndToEndSolution, EndToEndSolution, EndToEndSolution], [EndToEndSolution, SecondSolution, MySolution]],
    ids=("same-solution", "different-solutions"),
)
def test_multiple_databases(
    databases: list[PostgresDsn],
    solutions: list[T],
    run_glow: Callable[..., GlowBaseProcess[T]],
    get_glow_client: Callable[[GlowBaseProcess[T]], Client[T]],
    random_project_name: Callable[[], str],
    tmp_solutions_dir: dict[type[T], Path],
):
    """
    Test that a single PostgresQL server can host multiple GLOW databases for different solutions in which concurrent
    project creation/access/deletion operations take place.
    """

    # GIVEN: Multiple glow clients, each with its own empty database.
    glow_clients: list[Client[T]] = []
    glow_procs: list[GlowBaseProcess[T]] = []
    for db_url, solution_type in zip(databases, solutions, strict=False):
        glow_proc = run_glow(solution_type, tmp_solutions_dir[solution_type])  # type: ignore
        glow_proc.change_configuration(PostgreSQLConfig, db_location=db_url)
        glow_procs.append(glow_proc)
        glow_clients.append(get_glow_client(glow_proc))

    for client, glow_proc in zip(glow_clients, glow_procs, strict=False):
        assert glow_proc.healthy
        assert not client.list_projects()["projects"]

    # WHEN: Creating a project on one client.
    glow_clients[0].create_project(random_project_name())

    # THEN: The project is not added to the rest of clients.
    for client in glow_clients[1:]:
        assert not client.list_projects()["projects"]

    # WHEN: Creating a project on the rest of clients.
    for client in glow_clients[1:]:
        client.create_project(random_project_name())

    # THEN: There is exactly one project on each database.
    for client in glow_clients:
        assert len(client.list_projects()["projects"]) == 1

    # WHEN: Trying to delete the project ID from one client on all of the others.
    project_name = glow_clients[0].list_projects()["projects"][0]["name"]
    for client in glow_clients[1:]:
        with pytest.raises(NotFoundException):
            client.delete_project(project_name)

    # THEN: Project still there on its client.
    assert glow_clients[0].get_project(project_name).project_display_name


def test_missing_database(
    run_glow: Callable[..., GlowBaseProcess[T]],
    get_glow_client: Callable[[GlowBaseProcess[T]], Client[T]],
    get_temp_postgresql_database: Callable[[], PostgresqlServerInfo],
    tmp_solutions_dir: dict[type[T], Path],
):
    """
    Test that when GLOW is configured with a PostgreSql url that points to a database that does not exist, GLOW
    requests fail. Startup does not fail since DB init is only done when trying to interact with it.
    """

    # GIVEN: Env var GLOW_DATABASE_LOCATION pointing to a postgresql database that was never created.

    # we create a valid DB and then change the db_name to a fake one, so we make sure that everything is alright during
    # the setup except the db_name.
    postgresql_url = get_temp_postgresql_database().url
    missing_database_url = create_postgres_database_url(postgresql_url, str(random.randint(0, 100000)).zfill(6))

    glow_proc = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution])  # type: ignore
    glow_proc.change_configuration(PostgreSQLConfig, db_location=missing_database_url)
    glow_client = get_glow_client(glow_proc)

    # WHEN: Launching a request that uses the database
    response = httpx2.get(f"{glow_client._url}/projects")  # type: ignore
    # THEN: request returns 500 with the expected error message
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    database_name = missing_database_url.unicode_string().split("/")[-1]
    assert f'database "{database_name}" does not exist' in response.text
