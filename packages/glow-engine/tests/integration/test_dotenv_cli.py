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

from enum import Enum
import os
from pathlib import Path
import shutil
import sys

import httpx2
from pydantic import BaseModel
import pytest

from ansys.saf.glow._config.settings import Settings
from ansys.saf.testing.common import YieldFixture
from tests.conftest import SOLUTIONS_MOCKS_DIR
from tests.integration.conftest import BasicGlowProcess


class DotEnvTestScenario(Enum):
    DOTENV_IN_CWD = 1
    DOTENV_AS_CLI_OPTION = 2
    WITHOUT_DOTENV = 3
    DOTENV_IN_CWD_OVERRIDDEN_BY_CLI = 4
    ENV_VAR_OVERRIDE_DOTENV = 5


class MockSolution(BaseModel):
    dotenv_test_scenario: DotEnvTestScenario
    root_path: Path
    definition_path: Path
    dotenv_location: Path | None
    projects_path: Path


class MockSolutionProcess(BaseModel, arbitrary_types_allowed=True):
    glow_process: BasicGlowProcess
    mock_solution: MockSolution
    use_uvicorn: bool


def create_solution(target_solution_root_path: Path) -> Path:
    orig_solution_file = SOLUTIONS_MOCKS_DIR / "minimal_solution.py"
    solutions_dir = target_solution_root_path / "src" / "ansys" / "solutions"
    solutions_dir.mkdir(parents=True, exist_ok=True)
    new_solution_file = solutions_dir / orig_solution_file.name
    shutil.copyfile(orig_solution_file, new_solution_file)
    return new_solution_file


@pytest.fixture(scope="module")
def mock_solutions(tmpdir_factory: pytest.TempPathFactory) -> list[MockSolution]:
    # A bit convoluted but we want to run the solution concurrently to speed up the tests
    # so we need to prepare everything in advance, at the module fixture.
    mock_solutions: list[MockSolution] = []
    for dotenv_test_scenario in DotEnvTestScenario:
        target_solution_root_path = Path(tmpdir_factory.mktemp("solutions")) / dotenv_test_scenario.name
        new_solution_file = create_solution(target_solution_root_path)
        if dotenv_test_scenario == DotEnvTestScenario.DOTENV_IN_CWD:
            # Create a .env file in the root folder of the solution
            projects_path = target_solution_root_path
            dotenv_location = target_solution_root_path / ".env"
            dotenv_location.write_text(f"GLOW_PROJECT_FILES_DIRECTORY={projects_path}")
        elif dotenv_test_scenario == DotEnvTestScenario.DOTENV_AS_CLI_OPTION:
            # Create a .env file in root/env/.env
            dotenv_location = target_solution_root_path / "env" / ".env"
            projects_path = dotenv_location.parent
            dotenv_location.parent.mkdir(exist_ok=True, parents=True)
            dotenv_location.write_text(f"GLOW_PROJECT_FILES_DIRECTORY={projects_path}")
        elif dotenv_test_scenario == DotEnvTestScenario.DOTENV_IN_CWD_OVERRIDDEN_BY_CLI:
            # Create a .env file in both root and elsewhere
            root_dotenv_location = target_solution_root_path / ".env"
            # set GLOW_DATABASE_LOCATION in .env from the cwd to ensure it is not used when .env from cli is used
            root_dotenv_location.write_text(
                f"GLOW_PROJECT_FILES_DIRECTORY={target_solution_root_path}\nGLOW_DATABASE_LOCATION={target_solution_root_path}",
            )
            dotenv_location = target_solution_root_path / "env" / ".env"
            projects_path = dotenv_location.parent
            dotenv_location.parent.mkdir(exist_ok=True, parents=True)
            dotenv_location.write_text(f"GLOW_PROJECT_FILES_DIRECTORY={projects_path}")
        elif dotenv_test_scenario == DotEnvTestScenario.ENV_VAR_OVERRIDE_DOTENV:
            # Create a .env file that should be overridden by the env var.
            projects_path = target_solution_root_path
            dotenv_location = target_solution_root_path / ".env"
            dotenv_location.write_text(f"GLOW_PROJECT_FILES_DIRECTORY={projects_path}")
            projects_path = new_solution_file.parent
        else:
            # No .env file
            projects_path = Settings(
                glow_solution_definition="tests.mocks.solutions.minimal_solution",
            ).computed_project_files_directory
            dotenv_location = None
        mock_solutions.append(
            MockSolution(
                root_path=target_solution_root_path,
                definition_path=new_solution_file,
                projects_path=projects_path,
                dotenv_location=dotenv_location,
                dotenv_test_scenario=dotenv_test_scenario,
            ),
        )
    return mock_solutions


@pytest.fixture(scope="module", params=["cli", "uvicorn"])
def glow_processes(
    request: pytest.FixtureRequest,
    mock_solutions: list[MockSolution],
) -> YieldFixture[dict[str, MockSolutionProcess]]:
    # A bit convoluted but we want to run the solution concurrently to speed up the tests
    # so we need to prepare everything in advance, at the module fixture.
    glow_processes: dict[str, MockSolutionProcess] = {}
    mp = pytest.MonkeyPatch()
    for mock_solution in mock_solutions:
        match request.param:
            case "cli":
                glow_args = [
                    sys.executable,
                    "-m",
                    "ansys.saf.glow.cli",
                    "api",
                    "--definition",
                    str(mock_solution.definition_path),
                ]
            case "uvicorn":
                mp.setenv("PYTHONPATH", str(mock_solution.root_path / "src"))
                mp.setenv("GLOW_SOLUTION_DEFINITION", "ansys.solutions.minimal_solution")
                glow_args = [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "ansys.saf.glow.api:app",
                ]
            case _:
                raise ValueError("unsupported glow_process")
        if (
            mock_solution.dotenv_test_scenario == DotEnvTestScenario.DOTENV_AS_CLI_OPTION
            or mock_solution.dotenv_test_scenario == DotEnvTestScenario.DOTENV_IN_CWD_OVERRIDDEN_BY_CLI
        ):
            glow_args.extend(["--env-file", str(mock_solution.dotenv_location)])
        if mock_solution.dotenv_test_scenario == DotEnvTestScenario.ENV_VAR_OVERRIDE_DOTENV:
            mp.setenv("GLOW_PROJECT_FILES_DIRECTORY", str(mock_solution.definition_path.parent))
            glow_args.extend(["--env-file", str(mock_solution.dotenv_location)])
        glow_process = BasicGlowProcess.run(glow_args, cwd=mock_solution.root_path, env=os.environ.copy())
        glow_processes[mock_solution.dotenv_test_scenario.name] = MockSolutionProcess(
            glow_process=glow_process,
            mock_solution=mock_solution,
            use_uvicorn=request.param == "uvicorn",
        )
    yield glow_processes
    mp.undo()
    for glow_process in glow_processes.values():
        glow_process.glow_process.stop()


dotenv_test_types = [dotenv_test_scenario.name for dotenv_test_scenario in DotEnvTestScenario]


@pytest.mark.parametrize("dotenv_test_scenario", dotenv_test_types)
def test_dotenv_override_default_value(
    glow_processes: dict[str, MockSolutionProcess],
    dotenv_test_scenario: str,
    mock_appdata: Path,
):
    """Test that dotenv file override default settings values.
    This test is parameterized with multiple scenario, both using 'ansys.saf.glow.cli api' and
    'uvicorn ansys.saf.glow.api:app':
    - .env file is located at the root of the solution in the cwd where 'saf run' is used.
    - .env file is located somewhere else but passed as argument from the cli via --env-file
    - no .env file
    - .env file located in cwd and somewhere else to verify that --env-file cli override the cwd .env
    - .env file in cwd but verify that env var override the .env
    Each of those .env file are modifying the GLOW_PROJECT_FILES_DIRECTORY so that we can control that the
    folder has been created at the right place when the API is used.
    """
    mock_solution_process = glow_processes[dotenv_test_scenario]
    glow_proc = mock_solution_process.glow_process
    glow_proc.wait_for_healthy()
    create_project_request = {"display_name": "test_witout_env"}
    response = httpx2.post(f"http://localhost:{glow_proc.port}/projects", json=create_project_request)
    assert response.status_code == 200
    project_id = str(response.json()["name"].split("/")[-1])
    if mock_solution_process.use_uvicorn and (dotenv_test_scenario == DotEnvTestScenario.DOTENV_IN_CWD.name):
        # (.env is not loaded implicitly when in cwd from uvicorn)
        assert not (mock_solution_process.mock_solution.projects_path / project_id).exists()
    else:
        assert (mock_solution_process.mock_solution.projects_path / project_id).exists()
    db_path = mock_appdata / "ansys" / "glow" / "MinimalSolution" / "glow.db"
    assert db_path.exists()


def test_dotenv_in_cwd_not_loaded_if_dotenv_from_cli(
    glow_processes: dict[str, MockSolutionProcess],
    mock_appdata: Path,
):
    """Test that dotenv file from the cwd is not loaded if a .env is passed as an explicit argument to the cli."""
    mock_solution_process = glow_processes[DotEnvTestScenario.DOTENV_IN_CWD_OVERRIDDEN_BY_CLI.name]
    glow_proc = mock_solution_process.glow_process
    glow_proc.wait_for_healthy()
    create_project_request = {"display_name": "test_witout_env"}
    response = httpx2.post(f"http://localhost:{glow_proc.port}/projects", json=create_project_request)
    assert response.status_code == 200
    # GLOW_DATABASE_LOCATION is set in .env from the cwd and not from the .env passed to the cli
    # so the db would be elsewhere if the one from cwd was loaded
    db_path = mock_appdata / "ansys" / "glow" / "MinimalSolution" / "glow.db"
    assert db_path.exists()
