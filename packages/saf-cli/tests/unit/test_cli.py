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

from collections.abc import Generator
import importlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from pydantic import ValidationError
import pytest
import pytest_mock
import tomlkit

from ansys.saf.cli._cli.main import saf
from ansys.saf.cli._config.const import (
    DEFAULT_SOLUTION_DISPLAY_NAME,
    DEFAULT_SOLUTION_NAME,
    DEFAULT_SOLUTION_NAMESPACE,
    DEFAULT_STEP_NAME,
    DEFAULT_UI_FRAMEWORK,
    GLOW_API_PORT,
    GLOW_DEBUG,
    GLOW_LOGGING_LEVEL,
    GLOW_SOLUTION_DEFINITION,
    GLOW_UI_DEBUG,
    GLOW_UI_MODULE,
    GLOW_UI_PORT,
    PORTAL_UI_PORT,
    SAF_CLI_EXTERNAL_URL,
    SAF_DESKTOP_LOG_TO_FILES,
)
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._solutions.plugins import SafTemplate
from ansys.saf.cli._utilities.solution_modules import get_solution_venv_bin_dir
from tests.conftest import _generate_plugin, get_template_path, get_template_plugin_path

CLI_COMMANDS_FOR_A_SOLUTION = ["add-step", "archive", "build", "execute", "install", "run"]


@pytest.fixture
def mocked_solution() -> Generator[tuple[SolutionRegistry, str], None, None]:
    stored_solution = SolutionRegistry(
        name="mocked_solution",
        root_dir=Path("mocked_solution"),
        display_name="Mocked Solution",
    )
    solution_module = "ansys.solutions.mocked_solution.main"
    with patch("ansys.saf.cli._cli.main._resolve_input_solution") as mock_get_module:
        mock_get_module.return_value = (stored_solution, solution_module)
        yield (stored_solution, solution_module)


@pytest.fixture
def mocked_stored_solution(mocked_solution: tuple[SolutionRegistry, str]) -> SolutionRegistry:
    return mocked_solution[0]


@pytest.fixture
def mocked_solution_module(mocked_solution: tuple[SolutionRegistry, str]) -> str:
    return mocked_solution[1]


@pytest.fixture
def mocked_solution_dir(mocked_stored_solution: SolutionRegistry) -> Generator[Path, None, None]:
    mocked_stored_solution.root_dir.mkdir(parents=True, exist_ok=True)
    yield mocked_stored_solution.root_dir
    shutil.rmtree(mocked_stored_solution.root_dir, ignore_errors=True)


@pytest.fixture
def mocked_solution_env(mocked_solution_dir: Path, mocked_solution_module: str) -> dict[str, str]:
    solution_env = os.environ.copy()
    solution_env.pop("VIRTUAL_ENV", None)
    solution_env["PATH"] = os.pathsep.join(
        [str(get_solution_venv_bin_dir(mocked_solution_dir)), solution_env.get("PATH", "")],
    )
    solution_module_root = mocked_solution_module.removesuffix(".main")
    solution_env[GLOW_SOLUTION_DEFINITION] = f"{solution_module_root}.solution.definition"
    solution_env[GLOW_UI_MODULE] = f"{solution_module_root}.ui.app"
    # The value of the environment variable PYTEST_CURRENT_TEST changes after this fixture is executed and
    # before CliRunner.invoke(...) is called.
    solution_env["PYTEST_CURRENT_TEST"] = solution_env["PYTEST_CURRENT_TEST"].replace(" (setup)", " (call)")
    return solution_env


@pytest.fixture
def mocked_add_step() -> Generator[MagicMock, None, None]:
    with patch("ansys.saf.cli._cli.main.add_step_to_solution") as mock_add_step:
        yield mock_add_step


@pytest.fixture
def mocked_step_name_exists() -> Generator[MagicMock, None, None]:
    with patch("ansys.saf.cli._cli.main.step_name_exists", return_value=False) as mock_step_name_exists:
        yield mock_step_name_exists


@pytest.fixture
def mocked_archiver() -> Generator[MagicMock, None, None]:
    with patch("ansys.saf.cli._cli.main.archive_solution") as mock_archive_solution:
        yield mock_archive_solution


@pytest.fixture
def mocked_setup_environment() -> Generator[MagicMock, None, None]:
    with patch("ansys.saf.cli._cli.main.setup_environment") as mock_setup_environment:
        yield mock_setup_environment


@pytest.fixture
def mocked_subprocess() -> Generator[MagicMock, None, None]:
    with patch("subprocess.run") as mock_subprocess:
        yield mock_subprocess


@pytest.fixture
def mocked_python_exec() -> Generator[Path, None, None]:
    python_exec = Path.cwd() / "fake_python_exec"
    with patch("ansys.saf.cli._cli.main.get_exec_from_solution_venv") as mock_python_exec:
        mock_python_exec.return_value = python_exec
        yield python_exec


@pytest.fixture
def mocked_executable_abs_path() -> Generator[str, None, None]:
    with patch("ansys.saf.cli._cli.main._get_executable_absolute_path") as mock_exec_abs_path:
        yield mock_exec_abs_path


def _run_and_assert_glow_derivation(
    command: list[str],
    runner: CliRunner,
    mocked_subprocess: MagicMock,
    mocked_solution_module: str,
    mocked_solution_env: dict[str, str],
) -> None:
    """Helper function to test GLOW_SOLUTION_DEFINITION and GLOW_UI_MODULE derivation when missing from .env."""
    solution_module_root = mocked_solution_module.removesuffix(".main")
    expected_solution_definition = f"{solution_module_root}.solution.definition"
    expected_ui_module = f"{solution_module_root}.ui.app"

    # Remove GLOW vars from expected env (they should be added by fallback logic)
    mocked_solution_env.pop(GLOW_SOLUTION_DEFINITION, None)
    mocked_solution_env.pop(GLOW_UI_MODULE, None)
    mocked_solution_env[GLOW_SOLUTION_DEFINITION] = expected_solution_definition
    mocked_solution_env[GLOW_UI_MODULE] = expected_ui_module

    # Run the command
    result = runner.invoke(saf, command)
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify the env vars were derived and set correctly
    passed_env = mocked_subprocess.call_args.kwargs["env"]
    assert passed_env[GLOW_SOLUTION_DEFINITION] == expected_solution_definition
    assert passed_env[GLOW_UI_MODULE] == expected_ui_module


def test_saf_archive_default_options(mocked_stored_solution: SolutionRegistry, mocked_archiver: MagicMock):
    runner = CliRunner()
    result = runner.invoke(saf, ["archive"])
    mocked_archiver.assert_called_once_with(
        solution_root_dir=mocked_stored_solution.root_dir,
        archive_name=mocked_stored_solution.name,
        archive_path=None,
        archive_extension=None,
    )
    assert result.exit_code == 0


def test_saf_archive_with_archive_name(mocked_stored_solution: SolutionRegistry, mocked_archiver: MagicMock):
    runner = CliRunner()
    result = runner.invoke(saf, ["archive", "--filename", "mock-archive"])
    mocked_archiver.assert_called_once_with(
        solution_root_dir=mocked_stored_solution.root_dir,
        archive_name="mock-archive",
        archive_path=None,
        archive_extension=None,
    )
    assert result.exit_code == 0


def test_saf_archive_with_archive_path(mocked_stored_solution: SolutionRegistry, mocked_archiver: MagicMock):
    runner = CliRunner()
    result = runner.invoke(saf, ["archive", "--path", "mock-path"])
    mocked_archiver.assert_called_once_with(
        solution_root_dir=mocked_stored_solution.root_dir,
        archive_name=mocked_stored_solution.name,
        archive_path=Path("mock-path"),
        archive_extension=None,
    )
    assert result.exit_code == 0


def test_saf_archive_with_custom_extension(mocked_stored_solution: SolutionRegistry, mocked_archiver: MagicMock):
    runner = CliRunner()
    result = runner.invoke(saf, ["archive", "--extension", "mock-ext"])
    mocked_archiver.assert_called_once_with(
        solution_root_dir=mocked_stored_solution.root_dir,
        archive_name=mocked_stored_solution.name,
        archive_path=None,
        archive_extension="mock-ext",
    )
    assert result.exit_code == 0


@pytest.mark.usefixtures("mocked_stored_solution")
def test_saf_archive_handles_exception(mocked_archiver: MagicMock):
    mocked_archiver.side_effect = RuntimeError("mocked exception")
    runner = CliRunner()
    result = runner.invoke(saf, ["archive"])
    assert "RuntimeError: mocked exception" in result.output
    assert result.exit_code == 1


def test_saf_build(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
):
    runner = CliRunner()
    result = runner.invoke(saf, ["build"])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.installer",
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


@pytest.mark.usefixtures("mocked_stored_solution")
def test_saf_build_handles_exception(mocker: pytest_mock.MockFixture):
    mock_python_exec = mocker.patch("ansys.saf.cli._cli.main.get_exec_from_solution_venv")
    mock_python_exec.side_effect = FileNotFoundError("Mock Error")

    runner = CliRunner()
    result = runner.invoke(saf, ["build"])
    assert "FileNotFoundError: Mock Error" in result.output
    assert result.exit_code == 1


def test_saf_build_handles_subprocess_error(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
):
    # Configure subprocess.run to raise CalledProcessError (return code != 0)
    # https://docs.python.org/3/library/subprocess.html#using-the-subprocess-module
    mocked_subprocess.side_effect = subprocess.CalledProcessError(returncode=1, cmd="mocked_command")

    runner = CliRunner()
    result = runner.invoke(saf, ["build"])
    assert result.exit_code == 1
    assert "Command 'mocked_command' returned non-zero exit status 1." in result.output
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.installer",
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


@pytest.mark.parametrize(
    "flag",
    [
        "--display-console-window",
        "--encrypt",
        "--no-executable",
        "--obfuscate",
        "--offline-package",
        "--exclude-python",
        "--no-glow",
    ],
)
def test_saf_build_with_flags(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    flag: str,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["build", flag])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.installer",
            flag,
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


@pytest.mark.parametrize(
    "string_option",
    [
        "--encryption-file",
        "--encryption-key",
        "--python-version",
        "--solution-entry-point",
        "--github-token",
        "--solution-ui-framework",
    ],
)
def test_saf_build_with_string_options(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    string_option: str,
):
    runner = CliRunner()
    option_string = "option_string"
    result = runner.invoke(saf, ["build", string_option, option_string])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.installer",
            string_option,
            option_string,
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


def test_saf_build_with_env_file_absolute_path(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    tmp_path: Path,
):
    env_file = tmp_path / ".env"
    env_file.touch()
    runner = CliRunner()
    result = runner.invoke(saf, ["build", "--env-file", str(env_file)])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.installer",
            "--env-file",
            env_file.resolve().as_posix(),
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


def test_saf_build_with_env_file_relative_path(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.touch()
    runner = CliRunner()
    result = runner.invoke(saf, ["build", "--env-file", env_file.name])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.installer",
            "--env-file",
            env_file.resolve().as_posix(),
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


def test_saf_doc():
    """
    Test ``saf doc`` launches a webbrowser with the index page of the documentation linked by SAF_CLI_EXTERNAL_URL
    """
    with patch("webbrowser.open") as webbrowser_open:
        runner = CliRunner()
        result = runner.invoke(saf, ["doc"])
        index_path = str(webbrowser_open.call_args_list[0][0][0])
        assert index_path == SAF_CLI_EXTERNAL_URL
        assert result.exit_code == 0


def test_saf_doc_handles_exception(mocker: pytest_mock.MockFixture):
    webbrowser_open = mocker.patch("webbrowser.open")
    webbrowser_open.side_effect = Exception("Mock Error")

    runner = CliRunner()
    result = runner.invoke(saf, ["doc"])
    assert "Exception: Mock Error" in result.output
    assert result.exit_code == 1


def test_saf_run(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_solution_env: dict[str, str],
):
    runner = CliRunner()
    result = runner.invoke(saf, ["run"])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


@pytest.mark.usefixtures("mocked_solution_module")
def test_saf_run_handles_exception(mocker: pytest_mock.MockFixture):
    mock_python_exec = mocker.patch("ansys.saf.cli._cli.main.get_exec_from_solution_venv")
    mock_python_exec.side_effect = FileNotFoundError("Mock Error")

    runner = CliRunner()
    result = runner.invoke(saf, ["run"])
    assert "FileNotFoundError: Mock Error" in result.output
    assert result.exit_code == 1


def test_saf_run_handles_subprocess_error(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_solution_env: dict[str, str],
):
    # Configure subprocess.run to raise CalledProcessError (return code != 0)
    # https://docs.python.org/3/library/subprocess.html#using-the-subprocess-module
    mocked_subprocess.side_effect = subprocess.CalledProcessError(returncode=1, cmd="mocked_command")

    runner = CliRunner()
    result = runner.invoke(saf, ["run"])
    assert result.exit_code == 1
    assert "Command 'mocked_command' returned non-zero exit status 1." in result.output
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


@pytest.mark.parametrize(
    "flag",
    ["--portal", "--no-ui", "--browser", "--streamlit-ui", "--no-automatic-project-migration"],
)
def test_saf_run_with_flags(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_solution_env: dict[str, str],
    flag: str,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["run", flag])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
            flag,
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


def test_saf_run_with_project(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
):
    runner = CliRunner()
    result = runner.invoke(saf, ["run", "--project", "my_project"])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
            "--project-display-name",
            "my_project",
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


def test_saf_run_with_env_file_absolute_path(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    tmp_path: Path,
):
    env_file = tmp_path / ".custom_env"
    env_file.touch()
    runner = CliRunner()
    result = runner.invoke(saf, ["run", "--env-file", str(env_file)])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
            "--env-file",
            env_file.resolve().as_posix(),
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


def test_saf_run_with_env_file_relative_path(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    env_file_name = Path(".custom_env")
    env_file_name.touch()
    runner = CliRunner()
    result = runner.invoke(saf, ["run", "--env-file", str(env_file_name)])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
            "--env-file",
            env_file_name.resolve().as_posix(),
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


def test_saf_run_sets_runtime_modules_from_env_file(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    tmp_path: Path,
):
    env_file = tmp_path / ".custom_env"
    env_file.write_text(
        "GLOW_SOLUTION_DEFINITION=custom.solution.definition\nGLOW_UI_MODULE=custom.ui.app\n",
    )
    mocked_solution_env[GLOW_SOLUTION_DEFINITION] = "custom.solution.definition"
    mocked_solution_env[GLOW_UI_MODULE] = "custom.ui.app"

    runner = CliRunner()
    result = runner.invoke(saf, ["run", "--env-file", str(env_file)])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
            "--env-file",
            env_file.resolve().as_posix(),
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


def test_saf_run_with_non_existent_env_file(mocked_subprocess: MagicMock):
    runner = CliRunner()
    result = runner.invoke(saf, ["run", "--env-file", ".custom_env"])
    assert result.exit_code == 2
    mocked_subprocess.assert_not_called()


@pytest.mark.parametrize("loglevel", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_saf_run_with_glow_loglevel(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    loglevel: str,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["run", "--loglevel", loglevel])
    assert result.exit_code == 0
    mocked_solution_env[GLOW_LOGGING_LEVEL] = loglevel
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


@pytest.mark.parametrize(
    ("option", "env_var"),
    [
        ("--debug", GLOW_DEBUG),
        ("--ui-debugger", GLOW_UI_DEBUG),
    ],
)
def test_saf_run_with_debugs(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    option: str,
    env_var: str,
):
    runner = CliRunner()
    cmd = ["run", option]
    result = runner.invoke(saf, cmd)
    assert result.exit_code == 0
    mocked_solution_env[env_var] = "True"
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


@pytest.mark.parametrize(
    ("option", "env_var"),
    [
        ("--portal-ui-port", PORTAL_UI_PORT),
        ("--solution-api-port", GLOW_API_PORT),
        ("--solution-ui-port", GLOW_UI_PORT),
    ],
)
def test_saf_run_with_ports(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    option: str,
    env_var: str,
):
    port = "1234"
    runner = CliRunner()
    cmd = ["run", option, port]
    result = runner.invoke(saf, cmd)
    assert result.exit_code == 0
    mocked_solution_env[env_var] = port
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


def test_saf_run_with_log_to_files_from_cli(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
):
    runner = CliRunner()
    cmd = ["run", "--log-to-files"]
    result = runner.invoke(saf, cmd)
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
            "--log-to-files",
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


def test_saf_run_with_log_to_files_from_env(
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_solution_module: str,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    runner = CliRunner()
    cmd = ["run"]
    monkeypatch.setenv(SAF_DESKTOP_LOG_TO_FILES, "True")
    result = runner.invoke(saf, cmd)
    assert result.exit_code == 0
    mocked_solution_env[SAF_DESKTOP_LOG_TO_FILES] = "True"
    mocked_subprocess.assert_called_once_with(
        [
            mocked_python_exec.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            mocked_solution_module,
            "--log-to-files",
        ],
        env=mocked_solution_env,
        cwd=mocked_stored_solution.root_dir,
        check=True,
    )


def test_saf_solutions_without_solutions(mocker: pytest_mock.MockFixture):
    # when there is no valid solution stored in the database
    mocker.patch(
        "ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solutions_grouped_by_name",
        return_value={},
    )

    # and we list the current solutions
    runner = CliRunner()
    result = runner.invoke(saf, ["solutions"])
    assert result.exit_code == 0

    # a message informs the user that there are no solutions
    assert result.output == "No solutions found.\n"


def test_saf_solutions_with_one_solution(tmp_path: Path, mocker: pytest_mock.MockFixture):
    # when there is one solution stored in the database
    solution_path = tmp_path / "my_path" / "my-solution"
    solution_path.mkdir(parents=True)
    solutions = {
        "my-solution": [SolutionRegistry(name="my-solution", root_dir=solution_path, display_name="My Solution")],
    }
    mocker.patch(
        "ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solutions_grouped_by_name",
        return_value=solutions,
    )

    # and we list the current solutions
    runner = CliRunner()
    result = runner.invoke(saf, ["solutions"])
    assert result.exit_code == 0

    # a single solution is listed in the output
    expected_output = f"my-solution\n    Root directory: {solution_path}\n    Display Name: My Solution\n\n"
    assert result.output == expected_output


def test_saf_solutions_with_two_solutions_with_different_name(tmp_path: Path, mocker: pytest_mock.MockFixture):
    # when there are two solution stored in the database with different name
    solution_path_1 = tmp_path / "my_path" / "my-solution"
    solution_path_1.mkdir(parents=True)
    solution_path_2 = tmp_path / "my_path" / "my-solution-2"
    solution_path_2.mkdir(parents=True)
    solutions = {
        "my-solution": [SolutionRegistry(name="my-solution", root_dir=solution_path_1, display_name="My Solution")],
        "my-solution-2": [
            SolutionRegistry(name="my-solution-2", root_dir=solution_path_2, display_name="My Solution 2"),
        ],
    }
    mocker.patch(
        "ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solutions_grouped_by_name",
        return_value=solutions,
    )

    # and we list the current solutions
    runner = CliRunner()
    result = runner.invoke(saf, ["solutions"])
    assert result.exit_code == 0

    # the two solutions are listed under their respective names
    expected_output = (
        "my-solution\n"
        f"    Root directory: {solution_path_1}\n"
        "    Display Name: My Solution\n\n"
        "my-solution-2\n"
        f"    Root directory: {solution_path_2}\n"
        "    Display Name: My Solution 2\n\n"
    )
    assert result.output == expected_output


def test_saf_solutions_with_two_solutions_with_same_name_but_different_path(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
):
    # when there are two solution stored in the database with the same name but different path
    solution_path_1 = tmp_path / "my_path" / "my-solution"
    solution_path_1.mkdir(parents=True)
    solution_path_2 = tmp_path / "my_second_path" / "my-solution"
    solution_path_2.mkdir(parents=True)
    solutions = {
        "my-solution": [
            SolutionRegistry(name="my-solution", root_dir=solution_path_1, display_name="My Solution"),
            SolutionRegistry(name="my-solution", root_dir=solution_path_2, display_name="My Solution 2"),
        ],
    }
    mocker.patch(
        "ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solutions_grouped_by_name",
        return_value=solutions,
    )

    # and we list the current solutions
    runner = CliRunner()
    result = runner.invoke(saf, ["solutions"])
    assert result.exit_code == 0

    # the two solutions are listed under a single name
    expected_output = (
        "my-solution\n"
        f"    Root directory: {solution_path_1}\n"
        "    Display Name: My Solution\n\n"
        f"    Root directory: {solution_path_2}\n"
        "    Display Name: My Solution 2\n\n"
    )
    assert result.output == expected_output


def test_saf_solutions_handles_exception(mocker: pytest_mock.MockFixture):
    mocked_get_solutions = mocker.patch(
        "ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solutions_grouped_by_name",
    )
    mocked_get_solutions.side_effect = Exception("Error")

    runner = CliRunner()
    result = runner.invoke(saf, ["solutions"])
    assert "Exception: Error" in result.output
    assert result.exit_code == 1


def test_saf_new_with_solution_name(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my-custom-solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_with_solution_name_and_solution_display_name(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name and a solution display name
    solution_name = "my-custom-solution"
    solution_display_name = "My Custom Solution"
    result = runner.invoke(
        saf,
        ["new", "--solution-name", solution_name, "--solution-display-name", solution_display_name],
        input="\n\n",
    )
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        "dash",
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_with_solution_name_and_solution_display_name_no_ui(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name and a solution display name
    solution_name = "my-custom-solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "none"
    result = runner.invoke(
        saf,
        [
            "new",
            "--solution-name",
            solution_name,
            "--solution-display-name",
            solution_display_name,
            "--ui-framework",
            ui_framework,
        ],
        input="\n",
    )
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_with_solution_name_and_solution_display_name_dash_ui(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name and a solution display name
    solution_name = "my-custom-solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "dash"
    result = runner.invoke(
        saf,
        [
            "new",
            "--solution-name",
            solution_name,
            "--solution-display-name",
            solution_display_name,
            "--ui-framework",
            ui_framework,
        ],
        input="\n",
    )
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_with_solution_name_and_no_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name and a solution display name
    solution_name = "my-custom-solution"
    solution_display_name = "My Solution"
    ui_framework = "none"
    result = runner.invoke(saf, ["new", "--solution-name", solution_name, "--ui-framework", ui_framework], input="\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_with_solution_name_and_dash_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name and a solution display name
    solution_name = "my-custom-solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new", "--solution-name", solution_name, "--ui-framework", ui_framework], input="\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_with_solution_display_name(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name and a solution display name
    solution_name = "my_solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new", "--solution-display-name", solution_display_name], input="\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_with_solution_display_name_and_no_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name and a solution display name
    solution_name = "my_solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "none"
    result = runner.invoke(
        saf,
        ["new", "--solution-display-name", solution_display_name, "--ui-framework", ui_framework],
        input="\n\n",
    )
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_with_solution_display_name_and_dash_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name and a solution display name
    solution_name = "my_solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "dash"
    result = runner.invoke(
        saf,
        ["new", "--solution-display-name", solution_display_name, "--ui-framework", ui_framework],
        input="\n\n",
    )
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_with_no_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my_solution"
    solution_display_name = "My Solution"
    ui_framework = "none"
    result = runner.invoke(saf, ["new", "--ui-framework", ui_framework], input="\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_with_dash_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my_solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new", "--ui-framework", ui_framework], input="\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_prompt_all_defaults(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my_solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input="\n\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_prompt_custom_solution_name(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my-custom-solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_prompt_custom_solution_name_and_solution_display_name(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my-custom-solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n{solution_display_name}\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_prompt_custom_solution_name_and_solution_display_name_and_no_ui(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my-custom-solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "none"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n{solution_display_name}\n{ui_framework}\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_prompt_custom_solution_name_and_solution_display_name_and_dash_ui(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my-custom-solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n{solution_display_name}\n{ui_framework}\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_prompt_custom_solution_name_and_no_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my-custom-solution"
    solution_display_name = "My Solution"
    ui_framework = "none"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n\n{ui_framework}\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_prompt_custom_solution_name_and_dash_ui(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my-custom-solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n\n{ui_framework}\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_prompt_custom_solution_display_name(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my_solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"\n{solution_display_name}\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_prompt_custom_solution_display_name_and_no_ui(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my_solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "none"
    result = runner.invoke(saf, ["new"], input=f"\n{solution_display_name}\n{ui_framework}\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_prompt_custom_solution_display_name_and_dash_ui(
    tmp_path_as_working_dir: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my_solution"
    solution_display_name = "My Custom Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"\n{solution_display_name}\n{ui_framework}\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_prompt_no_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my_solution"
    solution_display_name = "My Solution"
    ui_framework = "none"
    result = runner.invoke(saf, ["new"], input=f"\n\n{ui_framework}\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_prompt_dash_ui(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name
    solution_name = "my_solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"\n\n{ui_framework}\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


def test_saf_new_with_invalid_solution_name(mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name that is invalid
    solution_name = "my_/solution"
    result = runner.invoke(saf, ["new", "--solution-name", solution_name], input="\n\n\n")
    assert "Value error, Solution name contains invalid characters" in result.output
    assert result.exit_code == 1
    # create_solution is not called
    mocked_create_solution.assert_not_called()
    # and the solution is not stored in the database
    mocked_store.assert_not_called()


def test_saf_new_with_valid_namespace_root(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    solution_name = "my_solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    namespace = "org.project_module"

    result = runner.invoke(
        saf,
        ["new", "--namespace", namespace],
        input="\n\n\n",
    )

    assert result.exit_code == 0
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        namespace,
    )
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(name=solution_name, root_dir=expected_solution_path, display_name=solution_display_name),
    )


@pytest.mark.parametrize(
    ("namespace", "expected_error"),
    [
        ("MyOrg.project", "must be lowercase"),
        ("my-org.project", "can contain only lowercase letters, numbers, and underscores"),
        ("my/org.project", "can contain only lowercase letters, numbers, and underscores"),
        ("my org.project", "can contain only lowercase letters, numbers, and underscores"),
        (".myorg.project", "must not start or end with a dot"),
        ("myorg.project.", "must not start or end with a dot"),
        ("myorg..project", "must not contain empty segments"),
        ("123org.project", "must start with a letter or underscore"),
        ("org.class", "is a Python keyword and is not allowed"),
    ],
)
def test_saf_new_with_invalid_namespace_root(
    mocker: pytest_mock.MockFixture,
    namespace: str,
    expected_error: str,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    result = runner.invoke(
        saf,
        ["new", "--namespace", namespace],
    )

    assert result.exit_code == 2
    assert expected_error in result.output
    mocked_create_solution.assert_not_called()
    mocked_store.assert_not_called()


def test_saf_new_with_existing_solution_name_in_cwd(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with two identical solution names
    solution_name = "my-solution"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new", "--solution-name", solution_name], input="\n\n\n")
    assert result.exit_code == 0
    mocked_create_solution.assert_called_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    expected_solution_path = tmp_path_as_working_dir / solution_name
    expected_solution_path.mkdir()
    # the second call fails
    result = runner.invoke(saf, ["new", "--solution-name", solution_name], input="\n\n\n")
    assert result.exit_code == 1
    assert f"A file or directory already exists at {expected_solution_path}" in result.output
    # but create_solution was called with the right arguments
    mocked_create_solution.assert_called_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the database was only stored once
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_leaves_user_info_untouched(tmp_path_as_working_dir: Path, mocker: pytest_mock.MockFixture):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    # when running new with a solution name that includes heteregenous style
    solution_name = "My-custOm_Sölution for TESTS !!"
    solution_display_name = "My Solution"
    ui_framework = "dash"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n\n\n\n")
    assert result.exit_code == 0
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        solution_name,
        solution_display_name,
        ui_framework,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # and the solution is correctly stored in the database
    expected_solution_path = tmp_path_as_working_dir / solution_name
    mocked_store.assert_called_once_with(
        SolutionRegistry(
            name=solution_name,
            root_dir=expected_solution_path,
            display_name=solution_display_name,
        ),
    )


def test_saf_new_invalid_db_raise_error(database_path: Path):
    database_path.write_text(
        '{"solutions": [{"name":"my_solution","wrong_field":"D:/ansysdev/saf-cli/my_solution","display_name":"My Solution"}]}',  # noqa: E501
    )
    runner = CliRunner()
    solution_name = "solution"
    result = runner.invoke(saf, ["new"], input=f"{solution_name}\n\n\n\n")
    assert result.exit_code == 1
    assert "The solution database is invalid." in result.output
    assert "You may need to delete it from " in result.output


def test_saf_new_invalid_db_does_not_create_solution(mocker: pytest_mock.MockFixture, database_path: Path):
    database_path.write_text(
        '{"solutions": [{"name":"my_solution","wrong_field":"D:/ansysdev/saf-cli/my_solution","display_name":"My Solution"}]}',  # noqa: E501
    )
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")

    runner = CliRunner()
    solution_name = "solution"
    runner.invoke(saf, ["new"], input=f"{solution_name}\n\n\n\n")
    mocked_store.assert_not_called()
    mocked_create_solution.assert_not_called()


@pytest.mark.usefixtures("tmp_path_as_working_dir")
def test_saf_new_removes_scaffolded_solution_on_db_error(mocker: pytest_mock.MockFixture):
    def _create_scaffolded_dir(
        solution_name: str,
        solution_display_name: str,
        ui_framework: str,
        namespace: str,
    ) -> None:
        (Path.cwd() / solution_name).mkdir()

    def _raise_exception_on_store(solution: SolutionRegistry) -> None:
        assert (Path.cwd() / DEFAULT_SOLUTION_NAME).is_dir()
        raise Exception("Database error")

    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    mocked_store.side_effect = _raise_exception_on_store
    mocked_create_solution = mocker.patch("ansys.saf.cli._cli.main.create_solution")
    mocked_create_solution.side_effect = _create_scaffolded_dir

    runner = CliRunner()
    # when running new and an exception happens when registering the solution in the DB
    result = runner.invoke(saf, ["new"], input="\n\n\n\n")
    assert "Error: Database error" in result.output
    assert result.exit_code == 1
    # create_solution is called with the right arguments
    mocked_create_solution.assert_called_once_with(
        DEFAULT_SOLUTION_NAME,
        DEFAULT_SOLUTION_DISPLAY_NAME,
        DEFAULT_UI_FRAMEWORK,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    # db registration is attempted
    mocked_store.assert_called_once()
    # and the solution is scaffolded but deleted afterwards
    assert not (Path.cwd() / DEFAULT_SOLUTION_NAME).exists()


@pytest.mark.parametrize("command", CLI_COMMANDS_FOR_A_SOLUTION)
@pytest.mark.usefixtures(
    "mocked_subprocess",
    "mocked_python_exec",
    "mocked_add_step",
    "mocked_step_name_exists",
    "mocked_archiver",
    "mocked_executable_abs_path",
    "mocked_setup_environment",
)
def test_saf_resolves_solution_arg_using_registered_solution_names(
    command: str,
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    solution_main_file = tmp_path / "my-solution" / "src" / "ansys" / "solutions" / "my_solution" / "main.py"
    solution_main_file.parent.mkdir(parents=True)
    solution_main_file.touch()
    solutions = [SolutionRegistry(name="my-solution", root_dir=tmp_path / "my-solution", display_name="My Solution")]
    mocker.patch(
        "ansys.saf.cli._utilities.solution_modules.SolutionDatabaseManager.get_solutions_by_name",
        return_value=solutions,
    )
    mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solution_by_root_dir", return_value=solutions[0])

    runner = CliRunner()
    result = runner.invoke(
        saf,
        [command, "my-solution"] + (["fake_bin"] if command == "execute" else []),
        input="\n\n\n",
    )
    assert result.exit_code == 0
    mocked_store.assert_not_called()


@pytest.mark.parametrize("command", CLI_COMMANDS_FOR_A_SOLUTION)
@pytest.mark.usefixtures(
    "mocked_subprocess",
    "mocked_python_exec",
    "mocked_add_step",
    "mocked_step_name_exists",
    "mocked_archiver",
    "mocked_executable_abs_path",
    "mocked_setup_environment",
    "tmp_path_as_working_dir",
)
def test_saf_resolves_solution_arg_using_relative_path_and_registers_it_in_the_database(
    command: str,
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    solution_main_file = tmp_path / "my-solution" / "src" / "ansys" / "solutions" / "my_solution" / "main.py"
    solution_main_file.parent.mkdir(parents=True)
    solution_main_file.touch()
    mocker.patch(
        "ansys.saf.cli._utilities.solution_modules.SolutionDatabaseManager.get_solutions_by_name",
        return_value=[],
    )
    mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solution_by_root_dir", return_value=None)

    runner = CliRunner()
    result = runner.invoke(
        saf,
        [command, "./my-solution"] + (["fake_bin"] if command == "execute" else []),
        input="\n\n\n",
    )
    assert result.exit_code == 0
    mocked_store.assert_called_once_with(
        SolutionRegistry(name="my-solution", root_dir=tmp_path / "my-solution", display_name="My Solution"),
    )


@pytest.mark.parametrize("command", CLI_COMMANDS_FOR_A_SOLUTION)
@pytest.mark.usefixtures(
    "mocked_subprocess",
    "mocked_python_exec",
    "mocked_add_step",
    "mocked_step_name_exists",
    "mocked_archiver",
    "mocked_executable_abs_path",
    "mocked_setup_environment",
)
def test_saf_resolves_solution_arg_using_absolute_path_and_registers_it_in_the_database(
    command: str,
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    solution_main_file = tmp_path / "my-solution" / "src" / "ansys" / "solutions" / "my_solution" / "main.py"
    solution_main_file.parent.mkdir(parents=True)
    solution_main_file.touch()
    mocker.patch(
        "ansys.saf.cli._utilities.solution_modules.SolutionDatabaseManager.get_solutions_by_name",
        return_value=[],
    )
    mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solution_by_root_dir", return_value=None)

    runner = CliRunner()
    result = runner.invoke(
        saf,
        [command, (tmp_path / "my-solution").as_posix()] + (["fake_bin"] if command == "execute" else []),
        input="\n\n\n",
    )
    assert result.exit_code == 0
    mocked_store.assert_called_once_with(
        SolutionRegistry(name="my-solution", root_dir=tmp_path / "my-solution", display_name="My Solution"),
    )


@pytest.mark.parametrize("command", CLI_COMMANDS_FOR_A_SOLUTION)
@pytest.mark.parametrize("tmp_path_as_working_dir", ["my-solution"], indirect=True)
@pytest.mark.usefixtures(
    "mocked_subprocess",
    "mocked_python_exec",
    "mocked_add_step",
    "mocked_step_name_exists",
    "mocked_archiver",
    "mocked_executable_abs_path",
    "mocked_setup_environment",
    "tmp_path_as_working_dir",
)
def test_saf_resolves_solution_arg_using_cwd_and_registers_it_in_the_database(
    command: str,
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
):
    mocked_store = mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.store_solution")
    solution_main_file = tmp_path / "my-solution" / "src" / "ansys" / "solutions" / "my_solution" / "main.py"
    solution_main_file.parent.mkdir(parents=True)
    solution_main_file.touch()
    mocker.patch(
        "ansys.saf.cli._utilities.solution_modules.SolutionDatabaseManager.get_solutions_by_name",
        return_value=[],
    )
    mocker.patch("ansys.saf.cli._cli.main.SolutionDatabaseManager.get_solution_by_root_dir", return_value=None)

    runner = CliRunner()
    result = runner.invoke(saf, [command] + (["fake_bin"] if command == "execute" else []), input="\n\n\n")
    assert result.exit_code == 0
    mocked_store.assert_called_once_with(
        SolutionRegistry(name="my-solution", root_dir=tmp_path / "my-solution", display_name="My Solution"),
    )


def test_saf_install(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocker: pytest_mock.MockFixture,
):
    mocked_setup_environment = mocker.patch("ansys.saf.cli._cli.main.setup_environment")

    runner = CliRunner()
    result = runner.invoke(saf, ["install"])
    assert result.exit_code == 0

    mocked_setup_environment.assert_called_once_with(
        solution_root_dir=mocked_stored_solution.root_dir,
        solution_main_module_name=mocked_solution_module,
        dependency_groups=None,
        workspace_clear=None,
        env_file=None,
    )


@pytest.mark.usefixtures("mocked_stored_solution")
def test_saf_install_handles_exception(mocker: pytest_mock.MockFixture):
    mocked_setup_environment = mocker.patch("ansys.saf.cli._cli.main.setup_environment")
    mocked_setup_environment.side_effect = Exception("Error")

    runner = CliRunner()
    result = runner.invoke(saf, ["install"])
    assert "Exception: Error" in result.output
    assert result.exit_code == 1


@pytest.mark.parametrize("dependency_groups_input", ["all", "desktop,ui"])
def test_saf_install_with_dependency_groups(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocker: pytest_mock.MockFixture,
    dependency_groups_input: str,
):
    mocked_setup_environment = mocker.patch("ansys.saf.cli._cli.main.setup_environment")

    runner = CliRunner()
    result = runner.invoke(saf, ["install", "-d", dependency_groups_input])
    assert result.exit_code == 0

    expected_dependecy_groups = dependency_groups_input.split(",")
    mocked_setup_environment.assert_called_once_with(
        solution_root_dir=mocked_stored_solution.root_dir,
        solution_main_module_name=mocked_solution_module,
        dependency_groups=expected_dependecy_groups,
        workspace_clear=None,
        env_file=None,
    )


@pytest.mark.parametrize("clear_type", ["-f", "-F"])
def test_saf_install_with_clear(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocker: pytest_mock.MockFixture,
    clear_type: str,
):
    mocked_setup_environment = mocker.patch("ansys.saf.cli._cli.main.setup_environment")

    runner = CliRunner()
    result = runner.invoke(saf, ["install", clear_type])
    assert result.exit_code == 0

    expected_workspace_clear = "hard" if clear_type == "-F" else "soft" if clear_type == "-f" else "none"
    mocked_setup_environment.assert_called_once_with(
        solution_root_dir=mocked_stored_solution.root_dir,
        solution_main_module_name=mocked_solution_module,
        dependency_groups=None,
        workspace_clear=expected_workspace_clear,
        env_file=None,
    )


@pytest.mark.parametrize("ui_framework", ["dash", "none"])
def test_add_step(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    mocked_step_name_exists: MagicMock,
    ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    result = runner.invoke(
        saf,
        ["add-step", "--step-name", "my_step", "--ui-framework", ui_framework, "--template", "calculator-step"],
    )
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        "my_step",
        ui_framework,
        default_saf_step_template,
    )
    mocked_step_name_exists.assert_called_once_with(
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        "my_step",
    )


@pytest.mark.parametrize("ui_framework", ["dash", "none"])
def test_add_step_existing_step_name_via_flag(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    mocked_step_name_exists: MagicMock,
    ui_framework: str,
):
    mocked_step_name_exists.return_value = True
    runner = CliRunner()
    result = runner.invoke(
        saf,
        ["add-step", "--step-name", "my_step", "--ui-framework", ui_framework, "--template", "calculator-step"],
    )
    assert result.exit_code == 1
    assert "Error: Step name 'my_step' is already taken in solution 'mocked_solution'" in result.output
    mocked_step_name_exists.assert_called_once_with(
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        "my_step",
    )
    mocked_add_step.assert_not_called()


@pytest.mark.parametrize("ui_framework", ["dash", "none"])
def test_add_step_existing_step_name_via_prompt(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    mocked_step_name_exists: MagicMock,
    ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    mocked_step_name_exists.side_effect = [True, False]
    runner = CliRunner()
    result = runner.invoke(
        saf,
        ["add-step", "--ui-framework", ui_framework, "--template", "calculator-step"],
        input="\n\n",
    )
    assert result.exit_code == 0
    assert (
        f"A step with name '{DEFAULT_STEP_NAME}' already exists in solution '{mocked_stored_solution.name}'."
        in result.output
    )
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        DEFAULT_STEP_NAME,
        ui_framework,
        default_saf_step_template,
    )
    assert mocked_step_name_exists.call_count == 2


@pytest.mark.usefixtures("mocked_stored_solution", "mocked_step_name_exists")
def test_add_step_handles_exception(mocked_add_step: MagicMock):
    mocked_add_step.side_effect = Exception("Mock Error")

    runner = CliRunner()
    result = runner.invoke(saf, ["add-step"], input="\n\n\n")
    assert "Exception: Mock Error" in result.output
    assert result.exit_code == 1


@pytest.mark.usefixtures("mocked_stored_solution")
def test_add_step_no_plugin(mocker: pytest_mock.MockFixture):
    mocker.patch("ansys.saf.cli._solutions.plugins.entry_points", return_value=[])

    runner = CliRunner()
    result = runner.invoke(saf, ["add-step"], input="\n\n\n")
    assert "No template plugins found." in result.output
    assert result.exit_code == 1


@pytest.mark.usefixtures("mocked_stored_solution")
def test_add_step_invalid_template(mocker: pytest_mock.MockFixture):
    mocker.patch(
        "ansys.saf.cli._solutions.plugins.SafTemplate.model_validate",
        side_effect=ValidationError.from_exception_data(
            "SafTemplate",
            [{"type": "missing", "loc": ("field",), "input": {}}],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(saf, ["add-step"], input="\n\n\n")
    assert result.exit_code == 1
    assert "1 validation error for SafTemplate" in result.output
    assert "Template 'calculator-step' in plugin module 'ansys.saf.templates' is invalid" in result.output


@pytest.mark.usefixtures("mocked_stored_solution")
def test_add_step_template_is_not_step(mocker: pytest_mock.MockFixture):
    mock_ep = MagicMock()
    mock_ep.type = "not_a_step"

    mocker.patch("ansys.saf.cli._cli.main.resolve_template", return_value=mock_ep)

    runner = CliRunner()
    result = runner.invoke(saf, ["add-step"], input="\n\n\n")
    assert "Template 'calculator-step' is of type 'not_a_step', expected 'step'" in result.output
    assert result.exit_code == 1


@pytest.mark.usefixtures("mocked_stored_solution")
@pytest.mark.usefixtures("install_custom_template_plugin_empty_toml")
def test_add_step_no_templates_in_required_plugin(mocker: pytest_mock.MockFixture):
    mocker.patch("ansys.saf.cli._solutions.plugins.tomlkit.loads", return_value={})

    runner = CliRunner()
    result = runner.invoke(saf, ["add-step", "--template", "second-step"], input="\n\n")
    assert "Could not find a valid template for template name 'second-step'." in result.output
    assert result.exit_code == 1


@pytest.mark.usefixtures("install_custom_template_plugin_empty_toml", "mocked_step_name_exists")
def test_add_step_no_templates_in_another_plugin(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    default_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["add-step"], input="\n\n\n")
    assert "Could not find a valid template for template name 'calculator-step'." not in result.output
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        DEFAULT_STEP_NAME,
        "dash",
        default_saf_step_template,
    )


@pytest.mark.usefixtures("mocked_stored_solution")
@pytest.mark.usefixtures("install_custom_template_plugin_no_toml")
def test_add_step_no_templates_toml_in_required_plugin():
    runner = CliRunner()
    result = runner.invoke(saf, ["add-step", "--template", "second-step"], input="\n\n")
    assert "Could not find a valid template for template name 'second-step'." in result.output
    assert result.exit_code == 1


@pytest.mark.usefixtures("install_custom_template_plugin_no_toml", "mocked_step_name_exists")
def test_add_step_no_templates_toml_in_another_plugin(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    default_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["add-step"], input="\n\n\n")
    assert "Could not find a valid template for template name 'calculator-step'." not in result.output
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        DEFAULT_STEP_NAME,
        "dash",
        default_saf_step_template,
    )


@pytest.mark.usefixtures("mocked_stored_solution", "mocked_solution_module")
def test_add_step_no_solution_definition(mocked_stored_solution: SolutionRegistry):
    runner = CliRunner()
    result = runner.invoke(saf, ["add-step"], input="\n\n\n")
    assert f"Solution source directory not found at {mocked_stored_solution.root_dir / 'src'}" in result.output
    assert result.exit_code == 1


@pytest.mark.usefixtures("install_custom_template_plugin", "mocked_step_name_exists")
@pytest.mark.parametrize("ui_framework", ["dash", "none"])
def test_add_step_with_default_step_name(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    ui_framework: str,
    custom_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["add-step", "--ui-framework", ui_framework, "--template", "second-step"], input="\n")
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        DEFAULT_STEP_NAME,
        ui_framework,
        custom_saf_step_template,
    )


@pytest.mark.usefixtures("install_custom_template_plugin", "mocked_step_name_exists")
def test_add_step_with_default_ui_framework(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    custom_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    step_name = "my_step"
    assert step_name != DEFAULT_STEP_NAME
    result = runner.invoke(saf, ["add-step", "--step-name", step_name, "--template", "second-step"], input="\n")
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        step_name,
        DEFAULT_UI_FRAMEWORK,
        custom_saf_step_template,
    )


@pytest.mark.usefixtures("install_custom_template_plugin", "mocked_step_name_exists")
def test_add_step_with_default_step_name_and_ui(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    custom_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["add-step", "--template", "second-step"], input="\n\n")
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
        custom_saf_step_template,
    )


def test_generated_plugin_is_importable_in_new_namespace_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockFixture,
):
    module_name = "test_namespace_cache_plugin"
    qualified_name = f"ansys.saf.{module_name}"
    monkeypatch.syspath_prepend(str(tmp_path))
    assert importlib.util.find_spec(qualified_name) is None  # pyright: ignore[reportAttributeAccessIssue]
    plugin_path = tmp_path / "ansys" / "saf" / module_name
    mocker.patch("tests.conftest.get_template_plugin_path", return_value=plugin_path)

    _generate_plugin(module_name)

    try:
        plugin_module = importlib.import_module(qualified_name)
        assert plugin_module.get_plugin_path() == plugin_path
    finally:
        sys.modules.pop(qualified_name, None)


def test_list_registered_templates_no_plugin(mocker: pytest_mock.MockFixture):
    mocker.patch("ansys.saf.cli._solutions.plugins.entry_points", return_value=[])

    runner = CliRunner()
    result = runner.invoke(saf, ["templates"])
    assert result.exit_code == 1
    expected_output = "No template plugins found.\n"
    assert expected_output in result.output


@pytest.mark.usefixtures("install_custom_template_plugin_no_toml")
@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "not_verbose"])
def test_list_registered_templates_no_templates_toml_in_plugin(verbose: bool):
    runner = CliRunner()
    result = runner.invoke(saf, ["templates"] + (["--verbose"] if verbose else []))
    assert result.exit_code == 0
    if verbose:
        expected_output = [
            "Templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n"
            f"        location: {get_template_path('templates', 'calculator')}\n\n",
            "Error in plugin module 'ansys.saf.test_custom_templates_no_toml':\n"
            "1 validation error for SafPlugin\n"
            "  Value error, Config file 'templates.toml' not found for plugin module "
            "'ansys.saf.test_custom_templates_no_toml'",
        ]
    else:
        expected_output = [
            "Templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n\n",
            "Warning: 1 template plugin(s) could not be loaded. Use --verbose flag for more details.\n",
        ]
    assert all(block in result.output for block in expected_output)


@pytest.mark.usefixtures("install_custom_template_plugin_empty_toml")
@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "not_verbose"])
def test_list_registered_templates_no_templates_in_templates_toml(verbose: bool):
    runner = CliRunner()
    result = runner.invoke(saf, ["templates"] + (["--verbose"] if verbose else []))
    assert result.exit_code == 0
    if verbose:
        expected_output = [
            "Templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n"
            f"        location: {get_template_path('templates', 'calculator')}\n\n",
            "1 validation error for SafPlugin\n"
            "  Value error, No templates in templates configuration file for plugin module "
            "'ansys.saf.test_custom_templates_empty_toml'",
        ]
    else:
        expected_output = [
            "Templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n\n",
            "Warning: 1 template plugin(s) could not be loaded. Use --verbose flag for more details.\n",
        ]
    assert all(block in result.output for block in expected_output)


@pytest.mark.usefixtures("install_custom_template_plugin_same_name_step")
@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "not_verbose"])
def test_list_registered_templates_same_name_templates_in_required_plugin(verbose: bool):
    runner = CliRunner()
    result = runner.invoke(saf, ["templates"] + (["--verbose"] if verbose else []))
    assert result.exit_code == 0
    if verbose:
        expected_output = [
            "Templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n"
            f"        location: {get_template_path('templates', 'calculator')}\n\n",
            "1 validation error for SafPlugin\n"
            "  Value error, Error loading config file 'templates.toml' for plugin module "
            "'ansys.saf.test_custom_templates_same_name_step' at location "
            f"{get_template_plugin_path('test_custom_templates_same_name_step') / 'templates.toml'}: "
            'Key "several-deps-step" already exists',
        ]
    else:
        expected_output = [
            "Templates in ansys.saf.templates\n",
            "    calculator-step (step): a step that performs calculator operations\n\n",
            "Warning: 1 template plugin(s) could not be loaded. Use --verbose flag for more details.\n",
        ]
    assert all(block in result.output for block in expected_output)


@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "not_verbose"])
def test_list_registered_templates_invalid_template(mocker: pytest_mock.MockFixture, verbose: bool):
    mocker.patch(
        "ansys.saf.cli._solutions.plugins.SafTemplate.model_validate",
        side_effect=ValidationError.from_exception_data(
            "SafTemplate",
            [{"type": "missing", "loc": ("field",), "input": {}}],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(saf, ["templates"] + (["--verbose"] if verbose else []))
    assert result.exit_code == 0
    if verbose:
        expected_output = "Error in template 'calculator-step':\n1 validation error for SafTemplate\n"
    else:
        expected_output = "Warning: \\d+ template\\(s\\) could not be loaded. Use --verbose flag for more details.\n"
    assert re.search(expected_output, result.output)


@pytest.mark.usefixtures("install_custom_template_plugin")
@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "not_verbose"])
def test_list_registered_templates(verbose: bool):
    runner = CliRunner()
    result = runner.invoke(saf, ["templates"] + (["--verbose"] if verbose else []))
    assert result.exit_code == 0
    if verbose:
        expected_output = [
            "Templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n"
            f"        location: {get_template_path('templates', 'calculator')}\n\n",
            "Templates in ansys.saf.test_custom_templates\n"
            "    several-deps-step (step): a step that performs custom calculator operations\n"
            f"        location: {get_template_path('test_custom_templates', 'several_deps_step')}\n"
            "        main dependencies:\n"
            "          - humanize: ^4.15.0\n"
            "          - msgpack: {'version': '^1.0.0', 'allow-prereleases': True}\n\n"
            "    second-step (step): a step that is second to another step\n"
            f"        location: {get_template_path('test_custom_templates', 'second_step')}\n\n",
        ]
    else:
        expected_output = [
            "Templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n\n",
            "Templates in ansys.saf.test_custom_templates\n"
            "    several-deps-step (step): a step that performs custom calculator operations\n\n"
            "    second-step (step): a step that is second to another step\n\n",
        ]
    assert all(block in result.output for block in expected_output)


@pytest.mark.usefixtures("install_custom_template_plugin")
@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "not_verbose"])
def test_list_registered_templates_only_steps(verbose: bool):
    runner = CliRunner()
    result = runner.invoke(saf, ["templates", "--steps"] + (["--verbose"] if verbose else []))
    assert result.exit_code == 0
    if verbose:
        expected_output = [
            "Step templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n"
            f"        location: {get_template_path('templates', 'calculator')}\n\n",
            "Step templates in ansys.saf.test_custom_templates\n"
            "    several-deps-step (step): a step that performs custom calculator operations\n"
            f"        location: {get_template_path('test_custom_templates', 'several_deps_step')}\n"
            "        main dependencies:\n"
            "          - humanize: ^4.15.0\n"
            "          - msgpack: {'version': '^1.0.0', 'allow-prereleases': True}\n\n"
            "    second-step (step): a step that is second to another step\n"
            f"        location: {get_template_path('test_custom_templates', 'second_step')}\n\n",
        ]
    else:
        expected_output = [
            "Step templates in ansys.saf.templates\n"
            "    calculator-step (step): a step that performs calculator operations\n\n",
            "Step templates in ansys.saf.test_custom_templates\n"
            "    several-deps-step (step): a step that performs custom calculator operations\n\n"
            "    second-step (step): a step that is second to another step\n\n",
        ]
    assert all(block in result.output for block in expected_output)


@pytest.mark.usefixtures("install_custom_template_plugin")
@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "not_verbose"])
def test_list_registered_templates_only_solutions(verbose: bool):
    runner = CliRunner()
    result = runner.invoke(saf, ["templates", "--solutions"] + (["--verbose"] if verbose else []))
    assert result.exit_code == 0

    expected_output = (
        "Solution templates in ansys.saf.templates\nSolution templates in ansys.saf.test_custom_templates\n"
    )
    assert expected_output in result.output


@pytest.mark.usefixtures("mocked_step_name_exists")
def test_add_step_with_no_option(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    default_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["add-step"], input="\n\n\n")
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
        default_saf_step_template,
    )


@pytest.mark.parametrize("ui_framework", ["dash", "none"])
@pytest.mark.usefixtures("mocked_step_name_exists")
def test_add_step_with_default_step_name_and_template_name(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    result = runner.invoke(saf, ["add-step", "--ui-framework", ui_framework], input="\n\n")
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        DEFAULT_STEP_NAME,
        ui_framework,
        default_saf_step_template,
    )


@pytest.mark.usefixtures("mocked_step_name_exists")
def test_add_step_with_default_ui_and_template_name(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    default_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    step_name = "my_step"
    assert step_name != DEFAULT_STEP_NAME
    result = runner.invoke(saf, ["add-step", "--step-name", step_name], input="\n\n")
    assert result.exit_code == 0
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        step_name,
        DEFAULT_UI_FRAMEWORK,
        default_saf_step_template,
    )


@pytest.mark.parametrize("ui_framework", ["dash", "none"])
@pytest.mark.usefixtures("mocked_step_name_exists")
def test_add_step_with_default_template_name(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    runner = CliRunner()
    step_name = "my_step"
    assert step_name != DEFAULT_STEP_NAME
    result = runner.invoke(saf, ["add-step", "--step-name", step_name, "--ui-framework", ui_framework], input="\n")
    assert result.exit_code == 0, result.output
    mocked_add_step.assert_called_once_with(
        mocked_stored_solution.name,
        mocked_stored_solution.root_dir,
        mocked_solution_module.split("solutions.")[-1].split(".main")[0],
        step_name,
        ui_framework,
        default_saf_step_template,
    )


@pytest.mark.parametrize("solution_argument", ["", "mocked_solution"])
def test_saf_execute(
    mocked_subprocess: MagicMock,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    mocked_executable_abs_path: MagicMock,
    solution_argument: str,
):
    mocked_executable_abs_path.return_value = Path("fake_binary_abs_path")

    runner = CliRunner()
    cmd = ["execute"] + ([solution_argument] if solution_argument else []) + ["python --version"]
    result = runner.invoke(saf, cmd)
    assert result.exit_code == 0

    mocked_subprocess.assert_called_once_with(
        [
            "fake_binary_abs_path",
            "--version",
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


def test_saf_execute_loads_solution_env(
    mocked_subprocess: MagicMock,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_dir: Path,
    mocked_solution_env: dict[str, str],
    mocked_executable_abs_path: MagicMock,
):
    mocked_executable_abs_path.return_value = Path("fake_binary_abs_path")

    (mocked_solution_dir / ".env").write_text("MY_ENV_VAR=mocked_value\n")
    mocked_solution_env["MY_ENV_VAR"] = "mocked_value"

    runner = CliRunner()
    result = runner.invoke(saf, ["execute", "mocked_solution", "python -c 'import sys; print(sys.path)'"])
    assert result.exit_code == 0
    assert f"Environment variables loaded from {(mocked_solution_dir / '.env').resolve()}" in result.output
    mocked_subprocess.assert_called_once_with(
        [
            "fake_binary_abs_path",
            "-c",
            "import sys; print(sys.path)",
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


def test_saf_execute_with_env_file(
    tmp_path: Path,
    mocked_subprocess: MagicMock,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_dir: Path,
    mocked_solution_env: dict[str, str],
    mocked_executable_abs_path: MagicMock,
):
    mocked_executable_abs_path.return_value = Path("fake_binary_abs_path")

    # keep solution's env file to check that it's ignored if --env-file is used
    (mocked_solution_dir / ".env").write_text("MY_ENV_VAR=mocked_value\n")

    env_file = tmp_path / "env_file.env"
    env_file.write_text("MY_ENV_VAR_2=mocked_value_2\n")
    mocked_solution_env["MY_ENV_VAR_2"] = "mocked_value_2"

    runner = CliRunner()
    result = runner.invoke(
        saf,
        ["execute", "mocked_solution", "python -c 'import sys; print(sys.path)'", "--env-file", env_file.as_posix()],
    )
    assert result.exit_code == 0
    assert f"Environment variables loaded from {env_file.resolve()}" in result.output
    mocked_subprocess.assert_called_once_with(
        [
            "fake_binary_abs_path",
            "-c",
            "import sys; print(sys.path)",
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


def test_saf_execute_with_quoted_command(
    mocked_subprocess: MagicMock,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    mocked_executable_abs_path: MagicMock,
):
    mocked_executable_abs_path.return_value = Path("fake_binary_abs_path")

    runner = CliRunner()
    result = runner.invoke(saf, ["execute", "mocked_solution", "python -c 'import sys; print(sys.path)'"])
    assert result.exit_code == 0
    mocked_subprocess.assert_called_once_with(
        [
            "fake_binary_abs_path",
            "-c",
            "import sys; print(sys.path)",
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


@pytest.mark.parametrize(("path_type", "expected_exit_code"), [("dir", 0), ("file", 2), (None, 2)])
def test_saf_execute_with_cwd(
    mocked_subprocess: MagicMock,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    mocked_executable_abs_path: MagicMock,
    path_type: str,
    expected_exit_code: int,
):
    mocked_executable_abs_path.return_value = Path("fake_binary_abs_path")

    runner = CliRunner()
    if path_type == "dir":
        cwd = mocked_stored_solution.root_dir.parent
    elif path_type == "file":
        cwd = mocked_stored_solution.root_dir / ".env"
    else:
        cwd = mocked_stored_solution.root_dir / "non_existent_path"
    result = runner.invoke(saf, ["execute", "mocked_solution", "python --version", "--cwd", str(cwd)])
    assert result.exit_code == expected_exit_code
    if path_type == "dir":
        mocked_subprocess.assert_called_once_with(
            [
                "fake_binary_abs_path",
                "--version",
            ],
            cwd=mocked_stored_solution.root_dir.parent,
            env=mocked_solution_env,
            check=True,
        )
    else:
        cwd_str = str(cwd).replace("\\", "\\\\") if platform.system() == "Windows" else str(cwd)
        expected_error_message = f"Error: Invalid value for '--cwd': Directory '{cwd_str}' does not exist."
        assert expected_error_message in result.output


@pytest.mark.usefixtures("mocked_solution_dir")
def test_saf_execute_non_existent_binary():
    runner = CliRunner()
    result = runner.invoke(saf, ["execute", "mocked_solution", "not_python --version"])
    assert result.exit_code == 1
    expected_error_message = "Error: Executable 'not_python' not found in solution 'mocked_solution'."
    assert expected_error_message in result.output


@pytest.mark.usefixtures("mocked_solution_dir")
def test_saf_execute_non_existent_env_file(tmp_path: Path, mocked_executable_abs_path: MagicMock):
    mocked_executable_abs_path.return_value = Path("fake_binary_abs_path")
    env_file = tmp_path / "non_existent_env_file.env"

    runner = CliRunner()
    result = runner.invoke(
        saf,
        ["execute", "mocked_solution", "python -c 'import sys; print(sys.path)'", "--env-file", env_file.as_posix()],
    )
    assert result.exit_code == 2
    expected_error_message = f"Invalid value for '--env-file': Path '{env_file.as_posix()}' does not exist."
    assert expected_error_message in result.output


def test_saf_execute_handles_subprocess_error(
    mocked_subprocess: MagicMock,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_env: dict[str, str],
    mocked_executable_abs_path: MagicMock,
):
    # Configure subprocess.run to raise CalledProcessError (return code != 0)
    # https://docs.python.org/3/library/subprocess.html#using-the-subprocess-module
    mocked_subprocess.side_effect = subprocess.CalledProcessError(returncode=1, cmd="mocked_command")
    mocked_executable_abs_path.return_value = Path("fake_binary_abs_path")

    runner = CliRunner()
    result = runner.invoke(saf, ["execute", "python --version"])
    assert result.exit_code == 1
    assert "Command 'mocked_command' returned non-zero exit status 1." in result.output
    mocked_subprocess.assert_called_once_with(
        [
            "fake_binary_abs_path",
            "--version",
        ],
        cwd=mocked_stored_solution.root_dir,
        env=mocked_solution_env,
        check=True,
    )


@pytest.mark.parametrize("command", CLI_COMMANDS_FOR_A_SOLUTION)
@pytest.mark.usefixtures(
    "mocked_subprocess",
    "mocked_python_exec",
    "mocked_add_step",
    "mocked_step_name_exists",
    "mocked_archiver",
    "mocked_executable_abs_path",
    "mocked_setup_environment",
)
def test_saf_commands_outside_virtual_environment(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    mocked_stored_solution: SolutionRegistry,
):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    runner = CliRunner()
    result = runner.invoke(
        saf,
        [command, mocked_stored_solution.name] + (["fake_bin"] if command == "execute" else []),
        input="\n\n\n",
    )
    assert result.exit_code == 0
    assert "VIRTUAL_ENV" not in os.environ


def test_saf_version():
    runner = CliRunner()
    result = runner.invoke(saf, ["--version"])
    assert result.exit_code == 0
    pyproject_data = tomlkit.loads((Path(__file__).parent.parent.parent / "pyproject.toml").read_bytes()).unwrap()
    expected_version = pyproject_data["project"]["version"]
    assert result.output.strip() == expected_version


def test_saf_version_uses_importlib_to_retrieve_installed_version(mocker: pytest_mock.MockFixture):
    mocker.patch("importlib.metadata.version", return_value="Mock version")
    runner = CliRunner()
    result = runner.invoke(saf, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == "Mock version"


def test_saf_version_handles_error(mocker: pytest_mock.MockFixture):
    mocker.patch("importlib.metadata.version", side_effect=Exception("Mock Error"))
    runner = CliRunner()
    result = runner.invoke(saf, ["--version"])
    assert "Exception: Mock Error" in result.output
    assert result.exit_code == 1


def test_saf_without_command_nor_option_displays_help():
    runner = CliRunner()
    no_cmd_nor_option_result = runner.invoke(saf)
    help_result = runner.invoke(saf, ["--help"])
    assert no_cmd_nor_option_result.exit_code == 0
    assert no_cmd_nor_option_result.output == help_result.output


def test_saf_version_after_command_raises_error():
    # --version is not passed as an option to the rest of commands. Similarly, saf --help and saf command --help
    # display different information.
    runner = CliRunner()
    result = runner.invoke(saf, ["solutions", "--version"])
    assert result.exit_code == 2
    assert result.output.startswith("Usage: saf solutions [OPTIONS]\nTry 'saf solutions --help' for help.\n\n")
    assert "Error: No such option" in result.output
    assert "--version" in result.output


def test_saf_command_after_version_is_ignored():
    # command is ignored since --version is a boolean flag and after printing version, the proc exits.
    runner = CliRunner()
    result = runner.invoke(saf, ["--version", "solutions"])
    assert result.exit_code == 0
    pyproject_data = tomlkit.loads((Path(__file__).parent.parent.parent / "pyproject.toml").read_bytes()).unwrap()
    expected_version = pyproject_data["project"]["version"]
    assert result.output.strip() == expected_version


def test_saf_new_with_extra_argument_raises_error_without_prompting():
    runner = CliRunner()
    result = runner.invoke(saf, ["new", "extra-argument"])
    assert result.exit_code == 2
    assert result.output == (
        "Usage: saf new [OPTIONS]\nTry 'saf new --help' for help.\n\n"
        "Error: Got unexpected extra argument (extra-argument)\n"
    )


def test_saf_new_with_extra_option_raises_error_without_prompting():
    runner = CliRunner()
    result = runner.invoke(saf, ["new", "--extra-option"], input="\n\n\n")
    assert result.exit_code == 2
    assert result.output.startswith("Usage: saf new [OPTIONS]\nTry 'saf new --help' for help.\n\n")
    assert "Error: No such option" in result.output
    assert "--extra-option" in result.output
    assert "What is" not in result.output


@pytest.mark.parametrize("ui_framework", ["dash", "none"])
@pytest.mark.usefixtures("mocked_step_name_exists")
def test_add_step_uses_backup_manager_as_context_manager(
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_add_step: MagicMock,
    ui_framework: str,
    default_saf_step_template: SafTemplate,
    mocker: pytest_mock.MockFixture,
):
    """Verify BackupManager is used as a context manager in the add-step CLI handler."""
    mock_enter = mocker.patch(
        "ansys.saf.cli._cli.main.BackupManager.__enter__",
        return_value=mocker.MagicMock(),
    )
    mock_exit = mocker.patch(
        "ansys.saf.cli._cli.main.BackupManager.__exit__",
        return_value=False,
    )

    runner = CliRunner()
    result = runner.invoke(
        saf,
        ["add-step", "--step-name", "my_step", "--ui-framework", ui_framework, "--template", "calculator-step"],
    )

    assert result.exit_code == 0
    mock_enter.assert_called_once()
    mock_exit.assert_called_once()


@pytest.mark.usefixtures("mocked_stored_solution", "mocked_step_name_exists")
def test_add_step_backup_manager_exit_called_on_exception(
    mocked_add_step: MagicMock,
    mocker: pytest_mock.MockFixture,
):
    """Verify BackupManager.__exit__ is always called even when add_step_to_solution raises."""
    mocked_add_step.side_effect = RuntimeError("step failed")
    mock_exit = mocker.patch(
        "ansys.saf.cli._cli.main.BackupManager.__exit__",
        return_value=False,
    )

    runner = CliRunner()
    result = runner.invoke(saf, ["add-step", "--step-name", "my_step"], input="\n\n")

    assert result.exit_code == 1
    mock_exit.assert_called_once()


@pytest.mark.parametrize(
    "command",
    [
        ["build"],
        ["run"],
        ["execute", "mocked_solution", "python --version"],
    ],
)
def test_saf_derives_glow_modules_when_not_in_env_file(
    command: list[str],
    mocked_subprocess: MagicMock,
    mocked_python_exec: Path,
    mocked_stored_solution: SolutionRegistry,
    mocked_solution_module: str,
    mocked_solution_env: dict[str, str],
    mocked_executable_abs_path: MagicMock,
    tmp_path: Path,
):
    mocked_executable_abs_path.return_value = Path("fake_binary_abs_path")

    env_file = tmp_path / ".env"
    env_file.write_text("OTHER_VAR=value\n")

    full_command = command + ["--env-file", str(env_file)]

    _run_and_assert_glow_derivation(
        command=full_command,
        runner=CliRunner(),
        mocked_subprocess=mocked_subprocess,
        mocked_solution_module=mocked_solution_module,
        mocked_solution_env=mocked_solution_env,
    )
