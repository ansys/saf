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
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import TypeVar

import pytest

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.solution.end_to_end import GlowDesktopProcess, ProjectFixture
from tests.e2e.conftest import PACKAGE_ROOT
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

DIST_DIR = PACKAGE_ROOT / "dist"
T = TypeVar("T", bound=Solution)

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


@pytest.fixture
def clear_dist_dir():
    """Cleanup before and after in case of halted executions and/or errors in earlier executions making a mess."""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    yield
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)


@pytest.mark.parametrize("use_obfuscated_solution", [False, True], indirect=True)
def test_glow_obfuscated(
    run_glow: Callable[..., GlowDesktopProcess[EndToEndSolution]],
    get_glow_client: Callable[[GlowDesktopProcess[EndToEndSolution]], Client[EndToEndSolution]],
    function_project: ProjectFixture[EndToEndSolution],
    obfuscated_glow_source: Path,
    random_project_name: Callable[[], str],
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
):
    """
    Test that obfuscated (pyc) GLOW code can run a solution without a readable src.
    """

    # GIVEN a project running on a GLOW process using the src code.
    step_from_src = function_project.project.steps.transaction_verification_step

    # GIVEN another project running on a GLOW process from pyc isolated files.
    deps = PACKAGE_ROOT / ".venv" / "Lib" / "site-packages"
    glow_and_deps = obfuscated_glow_source.as_posix() + os.pathsep + deps.as_posix()
    glow_process = run_glow(
        EndToEndSolution,
        tmp_solutions_dir[EndToEndSolution],
        obfuscated_glow_pythonpath=glow_and_deps,
    )
    assert glow_process.healthy
    client = get_glow_client(glow_process)
    project = client.create_project(random_project_name())
    step_from_obfuscated_glow = project.steps.transaction_verification_step

    # THEN the glow src code is readable ONLY from the solution running from src.
    assert step_from_src.is_glow_src_readable()
    assert not step_from_obfuscated_glow.is_glow_src_readable()


def test_glow_engine_wheel_can_be_compiled(clear_dist_dir: None):
    """
    Test that a solution created from ansys-templates can be compiled using pyc_wheel.
    """
    # GIVEN: glow-engine wheel
    assert not DIST_DIR.exists()
    p = subprocess.run(["poetry", "build"])
    assert p.returncode == 0
    expected_wheel_path = [f for f in DIST_DIR.iterdir() if f.suffix == ".whl"]
    assert len(expected_wheel_path) == 1
    expected_wheel_path = expected_wheel_path[0]

    # WHEN: running pyc_wheel to compile the python files
    p = subprocess.run([sys.executable, "-m", "pyc_wheel", str(expected_wheel_path)])

    # THEN: process ends successfully
    assert p.returncode == 0
