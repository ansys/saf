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
import shutil

import pytest

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_DISPLAY_NAME, DEFAULT_SOLUTION_NAME, DEFAULT_SOLUTION_NAMESPACE
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.testing.common import find_exec_in_venv
from tests.e2e.conftest import (
    BuildSolution,
    InstallSolution,
    ListSolutions,
    NewSolution,
    is_solution_registered,
)
from tests.outcome_checks import check_built_solution_files


def test_saf_build(
    new_solution: NewSolution,
    install_solution: InstallSolution,
    build_solution: BuildSolution,
    tmp_path: Path,
):
    """
    Test ``saf build`` with the default option values and the solution name of a registered solution.
    """
    solution_dir = tmp_path / DEFAULT_SOLUTION_NAME
    new_solution(input_str="\n\n\n\n", cwd=solution_dir.parent)
    install_solution([DEFAULT_SOLUTION_NAME, "-d", "doc,build"], cwd=solution_dir)
    build_solution([DEFAULT_SOLUTION_NAME])
    check_built_solution_files(
        SolutionRegistry(
            name=DEFAULT_SOLUTION_NAME,
            root_dir=tmp_path / DEFAULT_SOLUTION_NAME,
            display_name=DEFAULT_SOLUTION_DISPLAY_NAME,
        ),
        solution_namespace=DEFAULT_SOLUTION_NAMESPACE,
    )


@pytest.mark.parametrize("namespace", [None, "ansys.solutions", "myorg.apps"])
@pytest.mark.parametrize("solution_param_type", [None, "relative", "absolute"])
def test_saf_build_unregistered_solution(
    tmp_path: Path,
    database_path: Path,
    new_solution: NewSolution,
    list_solutions: ListSolutions,
    build_solution: BuildSolution,
    solution_param_type: str | None,
    namespace: str | None,
):
    """
    Test ``saf build`` with the default option values and all solution argument types for unregistered solutions:
    an empty string, a relative path and an absolute path. Check that the solution is registered afterwards.

    We avoid building the solution and just check that the command fails with the expected error msg, since building
    is a very time-consuming process that is already tested for the default solution argument.
    """
    namespace_input = f"{namespace}\n" if namespace is not None else "\n"
    new_solution(input_str=f"\n\n\n{namespace_input}", cwd=tmp_path)
    solution_root_dir = tmp_path / DEFAULT_SOLUTION_NAME
    database_path.unlink()
    assert not is_solution_registered(list_solutions(), solution_root_dir)

    if solution_param_type == "relative":
        p = build_solution([f"./{solution_root_dir.name}"], cwd=solution_root_dir.parent, expected_return_code=1)
    elif solution_param_type == "absolute":
        p = build_solution([solution_root_dir.absolute().as_posix()], expected_return_code=1)
    elif not solution_param_type:
        p = build_solution([""], cwd=solution_root_dir, expected_return_code=1)
    else:
        raise ValueError(f"Invalid solution_param_type: {solution_param_type}")

    solution_python_bin = find_exec_in_venv(solution_root_dir, "python", verify=False)
    assert p.find_msg_in_output(f"FileNotFoundError: Executable not found at {solution_python_bin}")

    assert is_solution_registered(list_solutions(), solution_root_dir)


def test_build_invalid_solution(
    tmp_path: Path,
    new_solution: NewSolution,
    build_solution: BuildSolution,
):
    """
    Test building an existing solution that is invalid raises an error.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    shutil.rmtree(tmp_path / DEFAULT_SOLUTION_NAME)

    p = build_solution([DEFAULT_SOLUTION_NAME], cwd=tmp_path, expected_return_code=1)
    assert p.find_msg_in_output(f"NotADirectoryError: Solution not found at {str(tmp_path / DEFAULT_SOLUTION_NAME)}")


def test_build_multiple_solutions_same_name_invalid_solution(
    tmp_path: Path,
    new_solution: NewSolution,
    build_solution: BuildSolution,
):
    """
    Test building an existing solution that has the same name as other that is invalid.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    (tmp_path / "another_solution").mkdir()
    new_solution(input_str="\n\n\n\n", cwd=(tmp_path / "another_solution"))
    shutil.rmtree(tmp_path / "another_solution")

    p = build_solution([DEFAULT_SOLUTION_NAME], expected_return_code=1)
    # fails to launch because we didn't install the env, but the solution was correctly selected
    assert p.find_msg_in_output(
        f"FileNotFoundError: Executable not found at {str(tmp_path / DEFAULT_SOLUTION_NAME)}",
    )


def test_build_multiple_solutions_same_name(
    tmp_path: Path,
    new_solution: NewSolution,
    build_solution: BuildSolution,
):
    """
    Test building an existing solution that has the same name as other raises an error.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    (tmp_path / "another_solution").mkdir()
    new_solution(input_str="\n\n\n\n", cwd=(tmp_path / "another_solution"))

    p = build_solution([DEFAULT_SOLUTION_NAME], expected_return_code=1)

    assert p.find_msg_in_output(f"ValueError: Multiple solutions found with the name {DEFAULT_SOLUTION_NAME}.")
    assert p.find_msg_in_output(str(tmp_path / DEFAULT_SOLUTION_NAME))
    assert p.find_msg_in_output(str(tmp_path / "another_solution" / DEFAULT_SOLUTION_NAME))
    assert p.find_msg_in_output("Hint: You can specify the correct one by using the full path")


def test_saf_build_subprocess_fails(
    new_solution: NewSolution,
    install_solution: InstallSolution,
    build_solution: BuildSolution,
    tmp_path: Path,
):
    """
    Test ``saf build`` propagates subprocess failure by returning non-zero exit code and printing the exception.
    """
    solution_root_dir = tmp_path / DEFAULT_SOLUTION_NAME
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    install_solution([DEFAULT_SOLUTION_NAME, "-d", "doc,build"], cwd=tmp_path)

    # remove pyproject.toml to make build fail
    pyproject_file = solution_root_dir / "pyproject.toml"
    assert pyproject_file.is_file()
    pyproject_file.unlink()

    p = build_solution([DEFAULT_SOLUTION_NAME], expected_return_code=1)
    assert p.find_msg_in_output("subprocess.CalledProcessError")
    assert p.find_msg_in_output("returned non-zero exit status 1.")
