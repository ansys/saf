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

import os
from pathlib import Path
import platform
import subprocess
import sys
from unittest import mock

import click
import pytest
import pytest_mock
import requests

from ansys.saf.cli._solutions.environment import (
    InstallError,
    _check_private_sources,  # pyright: ignore[reportPrivateUsage]
    _run_poetry_install,  # pyright: ignore[reportPrivateUsage]
    setup_environment,
)
from ansys.saf.testing.common import find_exec_in_venv

PYPROJECT_CONTENT_BASE = """
[build-system-requirements]
build-system-version = "1.7.1"

[tool.poetry.dependencies]
python = ">=3.11,<3.15"
"""

PYPROJECT_CONTENT = (
    PYPROJECT_CONTENT_BASE
    + """\n
[tool.poetry.group.desktop]
optional = true
[tool.poetry.group.desktop.dependencies]
ansys-saf-desktop-orchestrator = "^1.0.0"

[tool.poetry.group.ui]
optional = true
[tool.poetry.group.ui.dependencies]
dash = "^2.6"
"""
)

PYPROJECT_CONTENT_WITHOUT_DESKTOP_AND_UI = (
    PYPROJECT_CONTENT_BASE
    + """\n
[tool.poetry.group.custom_group_one]
optional = true
[tool.poetry.group.custom_group_one.dependencies]
sphinx = "^6.2.1"

[tool.poetry.group.custom_group_two]
optional = true
[tool.poetry.group.custom_group_two.dependencies]
pytest = "^8.2.2"
"""
)

PYPROJECT_CONTENT_WITHOUT_BUILD_SYSTEM_REQUIREMENTS = PYPROJECT_CONTENT.replace(
    '[build-system-requirements]\nbuild-system-version = "1.7.1"',
    "",
)

PYPROJECT_CONTENT_WITHOUT_BUILD_SYSTEM_VERSION = PYPROJECT_CONTENT.replace('build-system-version = "1.7.1"', "")

PYPROJECT_CONTENT_WITHOUT_PYTHON_DEPENDENCY = PYPROJECT_CONTENT.replace('python = ">=3.11,<3.15"', "")

PYPROJECT_CONTENT_WITH_WRONG_PYTHON_DEPENDENCY = PYPROJECT_CONTENT.replace('python = ">=3.11,<3.15"', 'python = "test"')

PYPROJECT_CONTENT_WITH_PRIVATE_REPOS = (
    PYPROJECT_CONTENT
    + """\n
[[tool.poetry.source]]
name = "my-private-pypi"
url = "https://url-for-my-private-pypi"
priority = "supplemental"
"""
)

ENV_CONTENT_WITH_PRIVATE_REPOS_CREDENTIALS_USERNAME = """
POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME=my-username
"""

ENV_CONTENT_WITH_PRIVATE_REPOS_CREDENTIALS_PASSWORD = """
POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD=my-token
"""

PYPROJECT_CONTENT_WITH_POETRY_2X = PYPROJECT_CONTENT.replace(
    'build-system-version = "1.7.1"',
    'build-system-version = "2.1.0"',
)

SOLUTION_MAIN_MODULE_NAME = "ansys.solutions.fake_solution.main"


def _patch_http_get_to_return_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(*args: object, **kwargs: object) -> requests.Response:
        r = requests.Response()
        r.status_code = 404
        return r

    monkeypatch.setattr(requests, "get", mock_get)  # type: ignore


@pytest.fixture
def subprocess_mock(mocker: pytest_mock.MockFixture) -> pytest_mock.MockType:
    subprocess_mock = mocker.patch("subprocess.run")
    subprocess_mock.return_value = subprocess.CalledProcessError(returncode=0, cmd="")
    return subprocess_mock


@pytest.fixture
def mock_is_file(mocker: pytest_mock.MockFixture) -> None:
    mock_is_file = mocker.patch("pathlib.Path.is_file")
    mock_is_file.return_value = True


@pytest.fixture
def poetry_version(request: pytest.FixtureRequest) -> str:
    return getattr(request, "param", "1.7.1")


@pytest.fixture
def poetry_venv_poetry_exec(tmp_path: Path) -> Path:
    return find_exec_in_venv(tmp_path / ".poetry", "poetry", verify=False)


@pytest.fixture
def poetry_venv_python_exec(tmp_path: Path) -> Path:
    return find_exec_in_venv(tmp_path / ".poetry", "python", verify=False)


@pytest.fixture
def solution_venv_poetry_exec(tmp_path: Path) -> Path:
    return find_exec_in_venv(tmp_path, "poetry", verify=False)


@pytest.fixture
def solution_venv_python_exec(tmp_path: Path) -> Path:
    return find_exec_in_venv(tmp_path, "python", verify=False)


@pytest.fixture
def solution_poetry_cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".poetry" / ".cache"


@pytest.fixture
def dotnet_call() -> mock._Call:  # pyright: ignore[reportPrivateUsage]
    return mock.call(
        '\n        set -xe         && wget https://dot.net/v1/dotnet-install.sh         && chmod +x dotnet-install.sh         && ./dotnet-install.sh --install-dir /home/$USER/.dotnet --version 8.0.8 --runtime aspnetcore         && grep -qxF "DOTNET_ROOT=/home/$USER/.dotnet" /home/$USER/.bash_profile         || echo DOTNET_ROOT=/home/$USER/.dotnet >> /home/$USER/.bash_profile         && grep -qxF "PATH=\\$PATH:/home/$USER/.dotnet" /home/$USER/.bash_profile         || echo "PATH=\\$PATH:/home/$USER/.dotnet" >> /home/$USER/.bash_profile         && echo "\nsource /home/$USER/.bash_profile" >> ./.venv/bin/activate         && rm dotnet-install.sh\n        ',  # noqa: E501
        check=True,
        shell=True,
    )


@pytest.fixture
def expected_calls(
    poetry_venv_poetry_exec: Path,
    poetry_venv_python_exec: Path,
    solution_venv_poetry_exec: Path,
    solution_venv_python_exec: Path,
    solution_poetry_cache_dir: Path,
    poetry_version: str,
    dotnet_call: mock._Call,  # pyright: ignore[reportPrivateUsage]
) -> list[mock._Call]:  # pyright: ignore[reportPrivateUsage]
    expected_calls = [
        mock.call([sys.executable, "-m", "venv", ".venv"], check=True),
        mock.call([sys.executable, "-m", "venv", ".poetry/.venv"], check=True),
        mock.call(
            [poetry_venv_python_exec.as_posix(), "-m", "pip", "install", f"poetry=={poetry_version}"],
            check=False,
            capture_output=True,
            text=True,
        ),
        mock.call(
            [
                solution_venv_poetry_exec.as_posix(),
                "config",
                "cache-dir",
                solution_poetry_cache_dir.as_posix(),
                "--local",
            ],
            check=True,
        ),
    ]
    if poetry_version.startswith("1."):
        expected_calls.append(
            mock.call(
                [poetry_venv_python_exec.as_posix(), "-m", "pip", "install", "virtualenv==20.30.0"],
                check=False,
                capture_output=True,
                text=True,
            ),
        )
    if platform.system() == "Linux":
        expected_calls += [
            # it's installed twice, before installing .venv and installing .poetry/.venv
            mock.call([sys.executable, "-m", "pip", "install", "virtualenv"], check=True),
            mock.call([sys.executable, "-m", "pip", "install", "virtualenv"], check=True),
            mock.call(
                ["ln", "-sf", poetry_venv_poetry_exec.as_posix(), solution_venv_poetry_exec.as_posix()],
                check=True,
            ),
            dotnet_call,
        ]
    else:
        expected_calls.append(
            mock.call(
                [
                    "powershell",
                    "-Command",
                    "New-Item",
                    "-ItemType",
                    "HardLink",
                    "-Path",
                    f"'{solution_venv_poetry_exec.as_posix()}'",
                    "-Target",
                    f"'{poetry_venv_poetry_exec.as_posix()}'",
                ],
                check=True,
            ),
        )
    expected_calls.append(
        mock.call(
            [solution_venv_python_exec.as_posix(), "-c", f"import {SOLUTION_MAIN_MODULE_NAME}"],
            check=True,
            stderr=-1,
            text=True,
        ),
    )

    return expected_calls


def test_setup_environment_without_pyproject_toml(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(FileNotFoundError, match="No such file or directory: 'pyproject.toml'"):
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    assert not capsys.readouterr().out
    subprocess_mock.assert_not_called()


def test_setup_environment_without_build_system_requirements(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITHOUT_BUILD_SYSTEM_REQUIREMENTS)

    with pytest.raises(RuntimeError, match="No build system version found in the configuration file."):
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    assert not capsys.readouterr().out
    subprocess_mock.assert_not_called()


def test_setup_environment_without_build_system_version(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITHOUT_BUILD_SYSTEM_VERSION)

    with pytest.raises(RuntimeError, match="No build system version found in the configuration file."):
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    assert not capsys.readouterr().out
    subprocess_mock.assert_not_called()


def test_setup_environment_without_python_dependency(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITHOUT_PYTHON_DEPENDENCY)

    with pytest.raises(RuntimeError, match="Python dependency not specified in pyproject."):
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    assert not capsys.readouterr().out
    subprocess_mock.assert_not_called()


def test_setup_environment_with_wrong_python_dependency(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITH_WRONG_PYTHON_DEPENDENCY)

    with pytest.raises(Exception, match="Unable to interpret python version specification."):
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    assert not capsys.readouterr().out
    subprocess_mock.assert_not_called()


def test_setup_environment_with_invalid_clear_method(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError, match="Invalid workspace clear option: invalid"):
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME, workspace_clear="invalid")
    assert not capsys.readouterr().out
    subprocess_mock.assert_not_called()


@pytest.mark.usefixtures("mock_is_file")
def test_setup_environment_default_params(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
    expected_calls: list[mock._Call],  # pyright: ignore[reportPrivateUsage]
    poetry_venv_poetry_exec: Path,
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT)

    working_dir = Path.cwd()
    setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    printed_msgs = capsys.readouterr().out
    assert "You are all set!" in printed_msgs
    expected_calls.append(
        mock.call(
            [poetry_venv_poetry_exec.as_posix(), "install", "--with", "desktop,ui"],
            check=True,
            text=True,
            stderr=subprocess.PIPE,
        ),
    )
    for call in expected_calls:
        print(f"Expected call: {call}")
    for call in subprocess_mock.call_args_list:
        print(f"Actual call: {call}")
    assert len(subprocess_mock.call_args_list) == len(expected_calls)
    assert all(call in expected_calls for call in subprocess_mock.call_args_list)
    assert Path.cwd() == working_dir


@pytest.mark.usefixtures("mock_is_file")
def test_setup_environment_default_params_and_pyproject_no_ui_and_desktop(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
    expected_calls: list[mock._Call],  # pyright: ignore[reportPrivateUsage]
    poetry_venv_poetry_exec: Path,
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITHOUT_DESKTOP_AND_UI)

    working_dir = Path.cwd()
    setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    printed_msgs = capsys.readouterr().out
    assert "You are all set!" in printed_msgs
    expected_calls.append(
        mock.call(
            [poetry_venv_poetry_exec.as_posix(), "install"],
            check=True,
            text=True,
            stderr=subprocess.PIPE,
        ),
    )
    assert len(subprocess_mock.call_args_list) == len(expected_calls)
    assert all(call in expected_calls for call in subprocess_mock.call_args_list)
    assert Path.cwd() == working_dir


def test_setup_environment_switches_back_cwd_on_exception(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_dir = Path.cwd()
    with pytest.raises(FileNotFoundError, match="No such file or directory: 'pyproject.toml'"):
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    assert not capsys.readouterr().out
    subprocess_mock.assert_not_called()
    assert Path.cwd() == working_dir


@pytest.mark.usefixtures("mock_is_file")
@pytest.mark.parametrize(
    "dependencies",
    [["all"], ["desktop"], ["desktop", "ui"]],
    ids=["all", "desktop", "desktop,ui"],
)
def test_setup_environment_with_dependencies(
    dependencies: list[str],
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
    poetry_venv_poetry_exec: Path,
    expected_calls: list[mock._Call],  # pyright: ignore[reportPrivateUsage]
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT)

    setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME, dependencies)
    printed_msgs = capsys.readouterr().out
    assert "You are all set!" in printed_msgs

    if dependencies == ["all"]:
        expected_calls += [
            mock.call(
                [poetry_venv_poetry_exec.as_posix(), "install", "--with", "desktop,ui"],
                check=True,
                text=True,
                stderr=subprocess.PIPE,
            ),
        ]
    elif dependencies == ["desktop"]:
        expected_calls.pop()
        expected_calls += [
            mock.call(
                [poetry_venv_poetry_exec.as_posix(), "install", "--with", "desktop"],
                check=True,
                text=True,
                stderr=subprocess.PIPE,
            ),
        ]
    elif dependencies == ["desktop", "ui"]:
        expected_calls += [
            mock.call(
                [poetry_venv_poetry_exec.as_posix(), "install", "--with", "desktop,ui"],
                check=True,
                text=True,
                stderr=subprocess.PIPE,
            ),
        ]
    else:
        raise ValueError(f"Unexpected dependencies: {dependencies}")

    assert len(subprocess_mock.call_args_list) == len(expected_calls)
    assert all(call in expected_calls for call in subprocess_mock.call_args_list)


def test_setup_environment_with_invalid_dependencies(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT)

    with pytest.raises(ValueError, match="Invalid dependency group: fake_group"):
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME, ["fake_group"])
    printed_msgs = capsys.readouterr().out
    assert not printed_msgs
    subprocess_mock.assert_not_called()


@pytest.mark.usefixtures("mock_is_file")
def test_setup_environment_with_private_repositories_without_username(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mocker: pytest_mock.MockFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that missing username triggers interactive credential prompt and user provides credentials."""

    def mock_environ_get(key: str, altvalue: str | None = None) -> str | None:
        if key == "POETRY_CERTIFICATES_MY_PRIVATE_PYPI_CERT":
            return "false"
        return None

    mocker.patch("os.environ.get", side_effect=mock_environ_get)

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITH_PRIVATE_REPOS)

    env_file = tmp_path / ".env"
    env_file.write_text(ENV_CONTENT_WITH_PRIVATE_REPOS_CREDENTIALS_PASSWORD)

    mocker.patch("click.prompt", side_effect=["test-user", "test-token"])

    mock_set_user_env = mocker.patch(
        "ansys.saf.cli._solutions.environment.set_user_level_environment_variable",
    )

    _patch_http_get_to_return_404(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME, env_file=env_file)

    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    stdout_output = captured.out

    assert f"Environment variables loaded from {env_file.resolve()}" in stdout_output
    assert "Missing credentials for private PyPI source: my-private-pypi" in stdout_output
    assert "URL: https://url-for-my-private-pypi" in stdout_output
    assert "Validating credentials" in stdout_output
    assert "Successfully configured credentials for my-private-pypi" in stdout_output
    assert "IMPORTANT: Environment variables have been updated." in stdout_output
    assert "Please restart your terminal/IDE for the changes to take effect:" in stdout_output
    assert "Then run the install command again to continue with the setup." in stdout_output

    expected_env_calls = [
        mock.call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME", "test-user"),
        mock.call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD", "test-token"),
    ]

    assert mock_set_user_env.call_count == 2
    for expected_call in expected_env_calls:
        assert expected_call in mock_set_user_env.call_args_list


@pytest.mark.usefixtures("mock_is_file")
def test_setup_environment_with_private_repositories_without_token(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockFixture,
) -> None:
    """Test that missing token triggers interactive credential prompt and user provides credentials."""

    def mock_environ_get(key: str, altvalue: str | None = None) -> str | None:
        if key == "POETRY_CERTIFICATES_MY_PRIVATE_PYPI_CERT":
            return "false"
        return None

    mocker.patch("os.environ.get", side_effect=mock_environ_get)

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITH_PRIVATE_REPOS)

    env_file = tmp_path / ".env"
    env_file.write_text(ENV_CONTENT_WITH_PRIVATE_REPOS_CREDENTIALS_USERNAME)

    mocker.patch("click.prompt", side_effect=["test-user", "test-token"])

    mock_set_user_env = mocker.patch(
        "ansys.saf.cli._solutions.environment.set_user_level_environment_variable",
    )

    _patch_http_get_to_return_404(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME, env_file=env_file)

    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    stdout_output = captured.out

    assert f"Environment variables loaded from {env_file.resolve()}" in stdout_output
    assert "Missing credentials for private PyPI source: my-private-pypi" in stdout_output
    assert "URL: https://url-for-my-private-pypi" in stdout_output
    assert "Validating credentials" in stdout_output
    assert "Successfully configured credentials for my-private-pypi" in stdout_output
    assert "IMPORTANT: Environment variables have been updated." in stdout_output
    assert "Please restart your terminal/IDE for the changes to take effect:" in stdout_output
    assert "Then run the install command again to continue with the setup." in stdout_output

    expected_env_calls = [
        mock.call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME", "test-user"),
        mock.call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD", "test-token"),
    ]

    assert mock_set_user_env.call_count == 2
    for expected_call in expected_env_calls:
        assert expected_call in mock_set_user_env.call_args_list


@pytest.mark.usefixtures("mock_is_file")
def test_setup_environment_with_private_repositories_with_token(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    expected_calls: list[mock._Call],  # pyright: ignore[reportPrivateUsage]
    poetry_venv_poetry_exec: Path,
) -> None:
    """Test that valid credentials are used without prompting."""
    monkeypatch.delenv("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME", raising=False)
    monkeypatch.delenv("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD", raising=False)

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITH_PRIVATE_REPOS)

    env_file = tmp_path / ".env"
    env_file.write_text(
        ENV_CONTENT_WITH_PRIVATE_REPOS_CREDENTIALS_USERNAME + ENV_CONTENT_WITH_PRIVATE_REPOS_CREDENTIALS_PASSWORD,
    )

    subprocess_mock.return_value = subprocess.CompletedProcess(args="", returncode=0, stdout="", stderr="")

    _patch_http_get_to_return_404(monkeypatch)

    setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME, env_file=env_file)

    printed_msgs = capsys.readouterr().out

    assert f"Environment variables loaded from {env_file.resolve()}" in printed_msgs
    assert "Validating credentials for my-private-pypi" in printed_msgs
    assert "Credentials for my-private-pypi are valid" in printed_msgs
    assert "You are all set!" in printed_msgs

    expected_calls += [
        mock.call(
            [poetry_venv_poetry_exec.as_posix(), "install", "--with", "desktop,ui"],
            check=True,
            text=True,
            stderr=subprocess.PIPE,
        ),
    ]
    assert len(subprocess_mock.call_args_list) == len(expected_calls)
    assert all(call in expected_calls for call in subprocess_mock.call_args_list)


@pytest.mark.usefixtures("mock_is_file")
def test_setup_environment_reuse_existing_venv(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
    dotnet_call: mock._Call,  # pyright: ignore[reportPrivateUsage],
    poetry_venv_poetry_exec: Path,
    solution_venv_python_exec: Path,
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT)

    (tmp_path / ".venv").mkdir()
    setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    printed_msgs = capsys.readouterr().out
    assert "You are all set!" in printed_msgs

    # only 1 call to install the new group
    expected_calls = [
        mock.call(
            [poetry_venv_poetry_exec.as_posix(), "install", "--with", "desktop,ui"],
            check=True,
            text=True,
            stderr=subprocess.PIPE,
        ),
        mock.call(
            [solution_venv_python_exec.as_posix(), "-c", f"import {SOLUTION_MAIN_MODULE_NAME}"],
            check=True,
            stderr=-1,
            text=True,
        ),
    ]
    if platform.system() == "Linux":
        expected_calls += [dotnet_call]

    assert len(subprocess_mock.call_args_list) == len(expected_calls)
    assert all(call in expected_calls for call in subprocess_mock.call_args_list)


@pytest.mark.usefixtures("mock_is_file")
@pytest.mark.parametrize("workspace_clear", ["hard", "soft"])
def test_setup_environment_existing_venv_clear(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
    workspace_clear: str,
    expected_calls: list[mock._Call],  # pyright: ignore[reportPrivateUsage]
    poetry_venv_poetry_exec: Path,
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT)

    (tmp_path / ".venv").mkdir()
    (tmp_path / ".poetry" / ".venv").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".poetry" / ".cache").mkdir(parents=True, exist_ok=True)
    (tmp_path / "poetry.lock").touch()

    setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME, workspace_clear=workspace_clear)
    printed_msgs = capsys.readouterr().out
    assert "Delete existing virtual environment '.venv'" in printed_msgs
    assert "Delete existing poetry virtual environment" in printed_msgs
    assert "Delete existing poetry virtual environment" in printed_msgs
    if workspace_clear == "soft":
        assert "Skip deleting poetry lock file" in printed_msgs
    else:
        assert "Delete existing poetry lock file" in printed_msgs
    assert "You are all set!" in printed_msgs
    expected_calls.append(
        mock.call(
            [poetry_venv_poetry_exec.as_posix(), "install", "--with", "desktop,ui"],
            check=True,
            text=True,
            stderr=subprocess.PIPE,
        ),
    )
    assert len(subprocess_mock.call_args_list) == len(expected_calls)
    assert all(call in expected_calls for call in subprocess_mock.call_args_list)


@pytest.mark.usefixtures("mock_is_file")
@pytest.mark.parametrize("poetry_version", ["2.1.0"], indirect=True)
@pytest.mark.parametrize(
    "export_plugin_required",
    [True, False],
    ids=["export_plugin_required", "export_plugin_not_required"],
)
def test_setup_environment_poetry_2x(
    tmp_path: Path,
    subprocess_mock: pytest_mock.MockType,
    capsys: pytest.CaptureFixture[str],
    expected_calls: list[mock._Call],  # pyright: ignore[reportPrivateUsage]
    poetry_venv_poetry_exec: Path,
    poetry_venv_python_exec: Path,
    export_plugin_required: bool,
    mocker: pytest_mock.MockFixture,
    poetry_version: str,
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT_WITH_POETRY_2X)

    if export_plugin_required:
        mocker.patch(
            "ansys.saf.cli._solutions.environment._check_poetry_plugin_export_is_required",
            return_value=True,
        )
        expected_calls.append(
            mock.call(
                [poetry_venv_python_exec.as_posix(), "-m", "pip", "install", "poetry-plugin-export>=1.8"],
                check=False,
                capture_output=True,
                text=True,
            ),
        )
    elif poetry_version.startswith("2."):
        expected_calls.append(
            mock.call(
                [poetry_venv_python_exec.as_posix(), "-m", "pip", "show", "poetry-plugin-export"],
                capture_output=True,
                text=True,
            ),
        )

    working_dir = Path.cwd()
    setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    printed_msgs = capsys.readouterr().out
    assert "You are all set!" in printed_msgs
    expected_calls.append(
        mock.call(
            [poetry_venv_poetry_exec.as_posix(), "install", "--with", "desktop,ui"],
            check=True,
            text=True,
            stderr=subprocess.PIPE,
        ),
    )
    assert len(subprocess_mock.call_args_list) == len(expected_calls)
    assert all(call in expected_calls for call in subprocess_mock.call_args_list)
    assert Path.cwd() == working_dir


@pytest.mark.usefixtures("mock_is_file", "subprocess_mock", "poetry_version")
def test_setup_environment_outside_virtual_environment(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(PYPROJECT_CONTENT)

    setup_environment(tmp_path, SOLUTION_MAIN_MODULE_NAME)
    printed_msgs = capsys.readouterr().out
    assert "You are all set!" in printed_msgs
    assert "VIRTUAL_ENV" not in os.environ


def test_check_private_sources_missing_credentials(
    mocker: pytest_mock.MockFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test prompting when no credentials exist"""
    configuration = {
        "tool": {
            "poetry": {
                "source": [
                    {
                        "name": "my-private-pypi",
                        "url": "https://url-for-my-private-pypi",
                    },
                ],
            },
        },
    }

    def mock_environ_get(key: str, altvalue: str | None = None) -> str | None:
        if key == "POETRY_CERTIFICATES_MY_PRIVATE_PYPI_CERT":
            return "false"
        return None

    mocker.patch("os.environ.get", side_effect=mock_environ_get)

    mocker.patch("click.prompt", side_effect=["test-user", "test-token"])

    mock_validate = mocker.patch("ansys.saf.cli._solutions.environment.validate_credentials")
    mock_validate.return_value = True

    mock_set_env = mocker.patch("ansys.saf.cli._solutions.environment.set_user_level_environment_variable")

    with pytest.raises(SystemExit, match="0"):
        _check_private_sources(configuration)

    mock_set_env.assert_any_call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME", "test-user")
    mock_set_env.assert_any_call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD", "test-token")

    mock_validate.assert_called_once_with(
        {"name": "my-private-pypi", "url": "https://url-for-my-private-pypi"},
        "test-user",
        "test-token",
        certificate=None,
        verify=False,
    )
    printed_msgs = capsys.readouterr().out
    assert "Missing credentials for private PyPI source: my-private-pypi" in printed_msgs
    assert "Successfully configured credentials for my-private-pypi" in printed_msgs
    assert "IMPORTANT: Environment variables have been updated." in printed_msgs
    assert "Please restart your terminal/IDE for the changes to take effect:" in printed_msgs
    assert "Then run the install command again to continue with the setup." in printed_msgs


def test_check_private_sources_updates_invalid_credentials_with_valid_input(
    mocker: pytest_mock.MockFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that invalid existing credentials are detected and new ones are prompted for."""
    configuration = {
        "tool": {
            "poetry": {
                "source": [
                    {
                        "name": "my-private-pypi",
                        "url": "https://url-for-my-private-pypi",
                    },
                ],
            },
        },
    }

    def mock_environ_get(key: str, altvalue: str | None = None) -> str | None:
        if key == "POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME":  # noqa: SIM116
            return "invalid-user"
        elif key == "POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD":
            return "invalid-token"
        elif key == "POETRY_CERTIFICATES_MY_PRIVATE_PYPI_CERT":
            return "false"

    mocker.patch("os.environ.get", side_effect=mock_environ_get)

    mock_validate = mocker.patch("ansys.saf.cli._solutions.environment.validate_credentials")
    mock_validate.side_effect = [False, True]  # First call fails, second succeeds

    mocker.patch("click.prompt", side_effect=["new-valid-user", "new-valid-token"])

    mock_set_env = mocker.patch("ansys.saf.cli._solutions.environment.set_user_level_environment_variable")

    with pytest.raises(SystemExit, match="0"):
        _check_private_sources(configuration)

    assert mock_validate.call_count == 2

    mock_set_env.assert_any_call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME", "new-valid-user")
    mock_set_env.assert_any_call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD", "new-valid-token")

    captured = capsys.readouterr()
    stdout_output = captured.out
    stderr_output = captured.err

    assert "Invalid credentials for my-private-pypi" in stderr_output
    assert "Validating credentials for my-private-pypi" in stdout_output
    assert "Successfully configured credentials for my-private-pypi" in stdout_output
    assert "IMPORTANT: Environment variables have been updated." in stdout_output
    assert "Please restart your terminal/IDE for the changes to take effect:" in stdout_output
    assert "Then run the install command again to continue with the setup." in stdout_output


def test_check_private_sources_valid_existing_credentials(
    mocker: pytest_mock.MockFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test skipping prompt when valid credentials exist"""
    configuration = {
        "tool": {
            "poetry": {
                "source": [
                    {
                        "name": "my-private-pypi",
                        "url": "https://url-for-my-private-pypi",
                    },
                ],
            },
        },
    }

    # Mock environment to have existing valid credentials
    def mock_environ_get(key: str, altvalue: str | None = None) -> str | None:
        if key == "POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME":  # noqa: SIM116
            return "valid-user"
        elif key == "POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD":
            return "valid-token"
        elif key == "POETRY_CERTIFICATES_MY_PRIVATE_PYPI_CERT":
            return "false"
        return None

    mocker.patch("os.environ.get", side_effect=mock_environ_get)

    # Mock credential validation to succeed for existing credentials
    mock_validate = mocker.patch("ansys.saf.cli._solutions.environment.validate_credentials")
    mock_validate.return_value = True

    # Mock prompt to ensure it's not called
    mock_prompt = mocker.patch("click.prompt")

    # Mock environment variable setting to ensure it's not called
    mock_set_env = mocker.patch("ansys.saf.cli._solutions.environment.set_user_level_environment_variable")

    # Call the function directly
    _check_private_sources(configuration)

    # Verify that prompt was not called (credentials already exist and are valid)
    mock_prompt.assert_not_called()

    # Verify that environment variables were not set (already exist)
    mock_set_env.assert_not_called()

    # Verify validation was called once for existing credentials
    mock_validate.assert_called_once_with(
        {"name": "my-private-pypi", "url": "https://url-for-my-private-pypi"},
        "valid-user",
        "valid-token",
        certificate=None,
        verify=False,
    )

    # Check output messages
    printed_msgs = capsys.readouterr().out
    assert "Validating credentials for my-private-pypi" in printed_msgs
    assert "Credentials for my-private-pypi are valid" in printed_msgs
    # Should not see prompting messages
    assert "Missing credentials for private PyPI source: my-private-pypi" not in printed_msgs


def test_check_private_sources_user_cancellation(
    mocker: pytest_mock.MockFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test graceful exit when user cancels credential prompt after various scenarios"""
    configuration = {
        "tool": {
            "poetry": {
                "source": [
                    {
                        "name": "my-private-pypi",
                        "url": "https://url-for-my-private-pypi",
                    },
                ],
            },
        },
    }

    def mock_environ_get(key: str, altvalue: str | None = None) -> str | None:
        if key == "POETRY_CERTIFICATES_MY_PRIVATE_PYPI_CERT":
            return "false"
        return None

    mocker.patch("os.environ.get", side_effect=mock_environ_get)

    mocker.patch(
        "ansys.saf.cli._solutions.environment._read_certificate_from_environment_variable",
        return_value=(None, True),
    )

    # Mock credential validation to simulate different scenarios:
    # 1st call: validation fails (invalid credentials provided by user)
    # 2nd call: validation fails again (user tries different invalid credentials)
    # After 2nd failure, user cancels (click.Abort)
    mock_validate = mocker.patch("ansys.saf.cli._solutions.environment.validate_credentials")
    mock_validate.side_effect = [False, False]  # Two failed validation attempts

    # Mock user input sequence:
    # 1st attempt: provides invalid credentials
    # 2nd attempt: provides different invalid credentials
    # 3rd attempt: user cancels (click.Abort)
    mocker.patch(
        "click.prompt",
        side_effect=[
            "invalid-user1",
            "invalid-token1",  # First invalid attempt
            "invalid-user2",
            "invalid-token2",  # Second invalid attempt
            click.Abort(),  # User cancels on third attempt
        ],
    )

    mock_set_env = mocker.patch("ansys.saf.cli._solutions.environment.set_user_level_environment_variable")

    with pytest.raises(
        InstallError,
        match="Setup cancelled\\. Install will fail without valid credentials for my\\-private\\-pypi",
    ):
        _check_private_sources(configuration)

    assert mock_validate.call_count == 2, "Should have validated credentials twice before cancellation"

    assert mock_set_env.call_count == 0, "Environment variables should not be set for invalid credentials"

    expected_validation_calls = [
        mock.call(
            {"name": "my-private-pypi", "url": "https://url-for-my-private-pypi"},
            "invalid-user1",
            "invalid-token1",
            certificate=None,
            verify=False,
        ),
        mock.call(
            {"name": "my-private-pypi", "url": "https://url-for-my-private-pypi"},
            "invalid-user2",
            "invalid-token2",
            certificate=None,
            verify=False,
        ),
    ]

    assert mock_validate.call_args_list == expected_validation_calls

    captured = capsys.readouterr()
    stdout_output = captured.out
    stderr_output = captured.err

    assert stdout_output.count("Missing credentials for private PyPI source: my-private-pypi") >= 2
    assert stdout_output.count("Validating credentials") == 2

    assert stderr_output.count("Invalid credentials. Please check your username and password/token and try again.") == 2


def test_check_private_sources_loop_exit_paths(
    mocker: pytest_mock.MockFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test all possible exit paths from the while loop to prevent infinite loops"""
    configuration = {
        "tool": {
            "poetry": {
                "source": [
                    {
                        "name": "my-private-pypi",
                        "url": "https://url-for-my-private-pypi",
                    },
                ],
            },
        },
    }

    # Test Path 1: Immediate success with existing valid credentials
    def mock_environ_get_valid(key: str, altvalue: str | None = None) -> str | None:
        if key == "POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME":  # noqa: SIM116
            return "valid-user"
        elif key == "POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD":
            return "valid-token"
        elif key == "POETRY_CERTIFICATES_MY_PRIVATE_PYPI_CERT":
            return "false"
        return None

    mocker.patch("os.environ.get", side_effect=mock_environ_get_valid)
    mock_validate = mocker.patch("ansys.saf.cli._solutions.environment.validate_credentials")
    mock_validate.return_value = True  # Validation succeeds immediately
    mock_prompt = mocker.patch("click.prompt")
    mock_set_env = mocker.patch("ansys.saf.cli._solutions.environment.set_user_level_environment_variable")

    # Should exit immediately without prompting
    _check_private_sources(configuration)

    assert mock_validate.call_count == 1
    assert mock_prompt.call_count == 0  # No prompting needed
    assert mock_set_env.call_count == 0  # No env setting needed (already exist and valid)

    mock_validate.reset_mock()
    mock_prompt.reset_mock()
    mock_set_env.reset_mock()

    # Test Path 2: Success after one failed attempt
    def mock_environ_get_with_cert(key: str, altvalue: str | None = None) -> str | None:
        if key == "POETRY_CERTIFICATES_MY_PRIVATE_PYPI_CERT":
            return "false"
        return None  # No existing credentials

    mocker.patch("os.environ.get", side_effect=mock_environ_get_with_cert)

    mock_validate.side_effect = [False, True]  # Fail first, succeed second
    mock_prompt.side_effect = ["user1", "token1", "user2", "token2"]

    with pytest.raises(SystemExit, match="0"):
        _check_private_sources(configuration)

    assert mock_validate.call_count == 2  # Two validation attempts
    assert mock_prompt.call_count == 4  # Two sets of username/password prompts
    assert mock_set_env.call_count == 2  # Environment variables set only for successful attempt

    expected_env_calls = [
        mock.call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME", "user2"),
        mock.call("POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD", "token2"),
    ]

    for expected_call in expected_env_calls:
        assert expected_call in mock_set_env.call_args_list

    mock_validate.reset_mock()
    mock_prompt.reset_mock()
    mock_set_env.reset_mock()

    # Test Path 3: User cancels immediately when no credentials exist
    mocker.patch("os.environ.get", side_effect=mock_environ_get_with_cert)

    mock_prompt.side_effect = [click.Abort()]  # User cancels immediately

    with pytest.raises((SystemExit, InstallError)):
        _check_private_sources(configuration)

    assert mock_validate.call_count == 0  # No validation (user canceled before providing credentials)
    assert mock_set_env.call_count == 0  # No env setting (user canceled)

    mock_validate.reset_mock()
    mock_prompt.reset_mock()
    mock_set_env.reset_mock()

    # Test Path 4: User cancels after providing invalid credentials
    mocker.patch("os.environ.get", side_effect=mock_environ_get_with_cert)

    mock_validate.side_effect = [False]  # First validation fails
    mock_prompt.side_effect = ["invalid-user", "invalid-token", click.Abort()]  # Provide invalid creds, then cancel

    with pytest.raises((SystemExit, InstallError)):
        _check_private_sources(configuration)

    assert mock_validate.call_count == 1  # One validation attempt
    assert mock_prompt.call_count == 3  # Username, password, then cancellation
    assert mock_set_env.call_count == 0  # No env setting (credentials were invalid)


@pytest.mark.parametrize(
    ("stderr_message", "expected_match"),
    [
        ("401 Client Error: Unauthorized for url: https://example.com", r"Poetry install failed"),
        ("Authorization error: invalid token", r"Poetry install failed"),
        ("Some other poetry error", r"Poetry install failed with an unexpected error\. Some other poetry error"),
    ],
    ids=["401_client_error", "authorization_error", "generic_error"],
)
def test_authorization_error_captured_and_set_to_stderr(
    mocker: pytest_mock.MockFixture,
    tmp_path: Path,
    stderr_message: str,
    expected_match: str,
) -> None:
    """Ensure that authorization errors from the poetry subprocess
    are properly captured and raised as exceptions."""
    fake_poetry = tmp_path / "fake_poetry.py"
    fake_poetry.write_text(
        f'import sys\nprint("{stderr_message}", file=sys.stderr)\nsys.exit(1)\n',
    )

    mocker.patch(
        "ansys.saf.cli._solutions.environment.POETRY_POETRY_EXEC",
        new=Path(sys.executable),
    )

    with pytest.raises(Exception, match=expected_match):
        _run_poetry_install([str(fake_poetry)])
