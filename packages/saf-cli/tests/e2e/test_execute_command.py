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
import platform
import shutil
import uuid

import pytest

from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._utilities.conversion import namespace_to_pkg_name, to_package_name
from ansys.saf.testing.common import find_exec_in_venv
from tests.e2e.conftest import ExecuteCommand, ListSolutions, is_solution_registered


def _find_executable_path_in_output(process_output: list[str], solution_root_dir: Path, executable: str) -> None:
    expected_python_path = find_exec_in_venv(solution_root_dir, executable, verify=False)
    assert any(str(expected_python_path) in line for line in process_output) or any(
        str(expected_python_path.resolve()) in line for line in process_output
    )


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.parametrize("solution_param_type", [None, "relative", "absolute", "solution_name"])
def test_saf_execute(
    session_database_path: Path,
    session_solution: SolutionRegistry,
    list_solutions: ListSolutions,
    execute_command: ExecuteCommand,
    solution_param_type: str | None,
):
    """
    Test ``saf execute`` with the default option values and all the possible solution argument types: an empty string,
    a relative path, an absolute path, and a solution name.
    """
    if solution_param_type != "solution_name":
        session_database_path.unlink()
        assert not is_solution_registered(
            list_solutions(),
            session_solution.root_dir,
            session_solution.name,
            session_solution.display_name,
        )

    command = "python -c 'import sys; print(sys.executable)'"
    if solution_param_type == "solution_name":
        process_output = execute_command([session_solution.name, command])
    elif solution_param_type == "relative":
        process_output = execute_command([f"./{session_solution.name}", command], session_solution.root_dir.parent)
    elif solution_param_type == "absolute":
        process_output = execute_command([session_solution.root_dir.absolute().as_posix(), command])
    elif not solution_param_type:
        process_output = execute_command([command], session_solution.root_dir)
    else:
        raise ValueError(f"Invalid solution_param_type: {solution_param_type}")

    _find_executable_path_in_output(process_output, session_solution.root_dir, "python")
    assert is_solution_registered(
        list_solutions(),
        session_solution.root_dir,
        session_solution.name,
        session_solution.display_name,
    )


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_with_cwd(
    session_solution: SolutionRegistry,
    execute_command: ExecuteCommand,
    temporary_python_script: Path,
):
    """
    Test ``saf execute`` with the --cwd option.
    """
    temporary_python_script.write_text(
        """
from pathlib import Path
print(f"We are in {Path.cwd()}")
""",
    )
    command = "python script.py"
    process_output = execute_command([session_solution.name, command], expected_return_code=1)

    assert any("[Errno 2] No such file or directory" in line for line in process_output)

    env_file = session_solution.root_dir / ".env"
    process_output = execute_command([session_solution.name, command, "--cwd", str(temporary_python_script.parent)])

    assert (
        "\n".join(process_output)
        == f"Environment variables loaded from {env_file}\nWe are in {temporary_python_script.parent}"
    )


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_loads_solution_env_file(
    session_solution: SolutionRegistry,
    execute_command: ExecuteCommand,
    temporary_python_script: Path,
    env_file_with_mock_value: tuple[str, str],
):
    """
    Test ``saf execute`` loads solution's env file and passes its information to the executed command.
    """
    env_var_name, env_var_value = env_file_with_mock_value

    temporary_python_script.write_text(
        f"""
import os
print(os.environ.get('{env_var_name}', "not set"))
""",
    )

    env_file = session_solution.root_dir / ".env"
    command = f"python {temporary_python_script.resolve().as_posix()}"
    process_output = execute_command([session_solution.name, command])
    assert "\n".join(process_output) == f"Environment variables loaded from {env_file}\n{env_var_value}"


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_loads_passed_env_file(
    tmp_path: Path,
    session_solution: SolutionRegistry,
    execute_command: ExecuteCommand,
    temporary_python_script: Path,
    env_file_with_mock_value: tuple[str, str],
):
    """
    Test ``saf execute`` loads env file from option --env-file, ignoring the solution's env file, and passes its
    information to the executed command.
    """
    env_var_name, _ = env_file_with_mock_value

    env_file = tmp_path / "my_env_file.env"
    env_var_name_2 = "MY_CUSTOM_ENV_VAR_2"
    env_var_value_2 = str(uuid.uuid4())
    env_file.write_text(f"{env_var_name_2}={env_var_value_2}")

    temporary_python_script.write_text(
        f"""
import os
print(os.environ.get('{env_var_name}', "not set"))
print(os.environ.get('{env_var_name_2}', "not set"))
""",
    )

    command = f"python {temporary_python_script.resolve().as_posix()}"
    process_output = execute_command([session_solution.name, command, "--env-file", env_file.as_posix()])
    assert "\n".join(process_output) == f"Environment variables loaded from {env_file}\nnot set\n{env_var_value_2}"


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_pip(
    session_solution: SolutionRegistry,
    execute_command: ExecuteCommand,
    session_solution_namespace: str,
):
    """
    Test ``saf execute`` with the default option values and a pip command.
    """
    command = "pip list"
    process_output = execute_command([session_solution.name, command])
    expected_pkg = f"{namespace_to_pkg_name(session_solution_namespace)}-{to_package_name(session_solution.name)}"
    assert any(expected_pkg in line for line in process_output)
    assert any(str(session_solution.root_dir) in line for line in process_output)


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_poetry(session_solution: SolutionRegistry, execute_command: ExecuteCommand):
    """
    Test ``saf execute`` with the default option values and a poetry command.
    """
    if platform.system() == "Windows":
        command = "poetry run where poetry"
    elif platform.system() == "Linux":
        command = "poetry run which poetry"
    else:
        raise ValueError("Unsupported operating system.")
    process_output = execute_command([session_solution.name, command])
    _find_executable_path_in_output(process_output, session_solution.root_dir, "poetry")


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_pytest(session_solution: SolutionRegistry, execute_command: ExecuteCommand):
    """
    Test ``saf execute`` with the default option values and a pytest command. This test also verifies that the
    solution template example tests pass.
    """
    command = "pytest -v"
    process_output = execute_command([session_solution.name, command])
    _find_executable_path_in_output(process_output, session_solution.root_dir, "python")
    assert not any("failed" in line or "error" in line for line in process_output)


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.usefixtures("cleanup_built_documentation")
def test_saf_execute_sphinx(session_solution: SolutionRegistry, execute_command: ExecuteCommand):
    """
    Test ``saf execute`` with the default option values and a sphinx command.
    """
    command = "sphinx-build doc/source doc/build/html --color -vW -bhtml"
    process_output = execute_command([session_solution.name, command])

    solution_doc_dir = session_solution.root_dir / "doc"
    assert any(str(solution_doc_dir.resolve()) in line for line in process_output)
    doc_path = Path("doc") / "build" / "html"
    assert any(f"The HTML pages are in {doc_path}." in line for line in process_output)


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_black(session_solution: SolutionRegistry, execute_command: ExecuteCommand):
    """
    Test ``saf execute`` with the default option values and a black command.
    """

    command = "black src/ -v"
    process_output = execute_command([session_solution.name, command])
    expected_line = f"Identified `{session_solution.root_dir.resolve()}` as project root containing a pyproject.toml."
    assert any(expected_line in line for line in process_output)
    assert any("All done!" in line for line in process_output)


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_non_existent_binary(session_solution: SolutionRegistry, execute_command: ExecuteCommand):
    """
    Test ``saf execute`` with the default option values and a non existent command.
    """
    command = "not_a_command --not-an-option fake_value"
    process_output = execute_command([session_solution.name, command], expected_return_code=1)
    expected_line = f"FileNotFoundError: Executable 'not_a_command' not found in solution '{session_solution.name}'."
    assert any(expected_line in line for line in process_output)


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_external_binary(session_solution: SolutionRegistry, execute_command: ExecuteCommand):
    """
    Test ``saf execute`` with the default option values and a command external to the solution's environment.
    """
    if platform.system() == "Windows":
        command = "powershell -Command ls"
    elif platform.system() == "Linux":
        command = "ls"
    else:
        raise ValueError("Unsupported operating system")
    process_output = execute_command([session_solution.name, command], expected_return_code=1)
    expected_line = (
        f"FileNotFoundError: Executable '{command.split(' ')[0]}' not found in solution '{session_solution.name}'."
    )
    assert any(expected_line in line for line in process_output)


@pytest.mark.use_session_solution
@pytest.mark.usefixtures(
    "cleanup_solution_pyproject",
    "cleanup_solution_poetry_lock",
    "cleanup_solution_venv",
    "cleanup_solution_wheels_dir",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_poetry_add_local_wheel_with_path(
    session_solution: SolutionRegistry,
    execute_command: ExecuteCommand,
):
    """
    Test ``saf execute`` with a poetry add command pointing to a local wheel.
    """
    wheel_file = Path(__file__).resolve().parents[1] / "mocks" / "wheels" / "mock_no_deps-0.0.1-py3-none-any.whl"
    assert wheel_file.is_file(), f"Mock wheel file not found: {wheel_file}"

    wheels_dir = session_solution.root_dir / "wheels"
    wheels_dir.mkdir(exist_ok=True)
    shutil.copyfile(wheel_file, wheels_dir / wheel_file.name)

    command = "poetry show mock-no-deps"
    process_output = execute_command([session_solution.name, command], expected_return_code=1)
    assert any("Package mock-no-deps not found" in line for line in process_output)

    command = f"poetry add '{(wheels_dir / wheel_file.name).as_posix()}'"
    execute_command([session_solution.name, command])

    command = "poetry show mock-no-deps"
    process_output = execute_command([session_solution.name, command])
    assert any("mock-no-deps" in line for line in process_output), (
        "The mock-no-deps package was not found in poetry show output."
    )


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_execute_subprocess_fails(session_solution: SolutionRegistry, execute_command: ExecuteCommand):
    """
    Test ``saf execute`` propagates subprocess failure by returning non-zero exit code and printing the exception.
    """
    command = "python -c 'import sys; sys.exit(2)'"
    process_output = execute_command([session_solution.name, command], expected_return_code=1)
    assert any("subprocess.CalledProcessError" in line for line in process_output)
    assert any("returned non-zero exit status 2." in line for line in process_output)
