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

from collections.abc import Callable, Generator
from pathlib import Path
from typing import TypeVar

import pytest

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.solution.end_to_end import EnableAutomaticProjectMigrationConfig, GlowBaseProcess, ProjectFixture
from tests.e2e.client_server.migration_helper import upgrade_or_import_project

Orig = TypeVar("Orig", bound=Solution)
Mod = TypeVar("Mod", bound=Solution)


@pytest.fixture(params=["db", "import"])
def project_initializer_and_migrator(
    request: pytest.FixtureRequest,
    function_project: ProjectFixture[Orig],
    run_glow: Callable[[type[Mod], Path], GlowBaseProcess[Mod]],
    get_glow_client: Callable[[GlowBaseProcess[Mod]], Client[Mod]],
    tmp_solutions_dir: dict[type[Mod], Path],
    tmp_path: Path,
) -> Generator[Callable[[type[Mod], Callable[[Orig], None]], Mod | None], None, None]:
    glow_clients: list[Client[Mod]] = []

    def f(
        mod: type[Mod],
        initializer: Callable[[Orig], None],
        automatic_project_migration: bool = False,
        expected_status_code: int = 200,
        expected_error_message: str = "",
    ) -> Mod | None:
        initializer(function_project.project)
        function_project.project.export(tmp_path)
        safx_files = list(tmp_path.glob("*.safx"))
        assert len(safx_files) == 1, f"Expected exactly one .safx file, found: {safx_files}"
        safx_path = safx_files[0]
        glow_proc = run_glow(mod, tmp_solutions_dir[mod])
        if automatic_project_migration:
            glow_proc.change_configuration(EnableAutomaticProjectMigrationConfig)
        assert glow_proc is not None
        glow_client = get_glow_client(glow_proc)
        glow_client.__enter__()
        glow_clients.append(glow_client)
        project_info = upgrade_or_import_project(
            request.param,
            glow_client,
            glow_proc.base_api_url,
            function_project.project_id,
            safx_path,
            expected_status_code,
            expected_error_message,
        )

        if project_info is not None:
            return glow_client.get_project(project_info["name"])

    yield f
    if len(glow_clients):
        for client in glow_clients:
            client.close()


@pytest.fixture
def project_migrator(
    project_initializer_and_migrator: Callable[[type[Mod], Callable[[Orig], None]], Mod],
) -> Callable[[type[Mod]], Mod]:
    def f(mod: type[Mod]) -> Mod:
        return project_initializer_and_migrator(mod, lambda _: None)

    return f
