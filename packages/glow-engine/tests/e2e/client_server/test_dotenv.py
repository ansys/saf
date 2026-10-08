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

from pathlib import Path
from typing import TypeVar

import pytest

from ansys.saf.glow.solution import Solution
from ansys.saf.testing.solution.end_to_end import GlowDesktopProcess, ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)

T = TypeVar("T", bound=Solution)
ENV_VAR_NAME = "NON_GLOW_VAR"
UNUSED_ENV_VAR_NAME = "NON_GLOW_VAR_2"


@pytest.fixture(scope="module", autouse=True)
def cleanup_session_glow(session_glow: GlowDesktopProcess[EndToEndSolution]):
    try:
        yield
    finally:
        session_glow.env_file = None
        session_glow.set_cwd(Path.cwd())
        session_glow.restart()


@pytest.fixture(params=["cwd", "cli", "both"])
def set_project_files_in_dotenv_file(
    request: pytest.FixtureRequest,
    session_glow: GlowDesktopProcess[EndToEndSolution],
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Test that the dotenv file overrides the default settings values.
    This test is parameterized with two scenarios:
    - The .env file is located at the root of the solution in the cwd, where 'glow_engine' is run.
    - The .env file is located somewhere else but passed as an argument from the cli via --env-file.
    These .env files modify the GLOW_PROJECT_FILES_DIRECTORY so that we can control that the
    folder has been created in the right place when the API is used.
    """
    project_file_path = tmp_path_factory.mktemp(basename="project_files")

    # Don't create in pytest's CWD. Even if we unlink it at the end, that CWD is shared by all pytest workers
    # and it would affect their GLOW procs.
    env_file = tmp_path_factory.mktemp(basename="env_file") / ".env"
    env_vars = [
        f"GLOW_PROJECT_FILES_DIRECTORY={project_file_path.as_posix()}",
        "GLOW_DEBUG=True",
        "GLOW_DEBUG_API_PORT=-1",
        f"{ENV_VAR_NAME}=asdf",
    ]
    env_file.write_text("\n".join(env_vars))
    if request.param == "cwd":
        cwd = env_file.parent
        session_glow.env_file = None
    elif request.param == "cli":
        session_glow.env_file = env_file
        cwd = Path.cwd()
        assert cwd != env_file.parent
    else:
        ignored_env_file_in_cwd = tmp_path_factory.mktemp(basename="env_file") / ".env"
        ignored_env_file_in_cwd.write_text(f"{UNUSED_ENV_VAR_NAME}=asdf")
        session_glow.env_file = env_file
        cwd = ignored_env_file_in_cwd.parent

    session_glow.set_cwd(cwd)
    session_glow.restart()


@pytest.mark.usefixtures("set_project_files_in_dotenv_file")
def test_dotenv_override_default_value(
    function_project: ProjectFixture[EndToEndSolution],
    session_glow: GlowDesktopProcess[EndToEndSolution],
):
    """
    Test that environment variables can be overridden by a .env file.
    """
    step = function_project.project.steps.transaction_verification_step
    relative_file_path = "projectFiles/file.txt"
    file_path = function_project.project_files_dir / relative_file_path
    assert not file_path.is_file()
    step.create_text_outside_storage_scope()
    assert file_path.is_file()
    assert step.get_env_var(var_name=ENV_VAR_NAME) == "asdf"
    assert not step.get_env_var(var_name=UNUSED_ENV_VAR_NAME)
