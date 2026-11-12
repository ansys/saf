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
import subprocess

import pytest
import pytest_mock

from ansys.saf.desktop.installer.__main__ import _load_filtered_dotenv, package_solution
from ansys.saf.desktop.installer._package.config import InstallerConfig
from ansys.saf.desktop.installer._package.solution import SolutionInfo


@pytest.fixture
def mock_installer_calls(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("ansys.saf.desktop.installer.__main__.initial_cleanup")
    mocker.patch("ansys.saf.desktop.installer.__main__.setup_solution_folder")
    mocker.patch("ansys.saf.desktop.installer.__main__.build_executable_installer")


@pytest.mark.usefixtures("mock_installer_calls")
@pytest.mark.parametrize("offline_package", [False, True])
def test_uv_packaging_skips_poetry_preparation(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    caplog: pytest.LogCaptureFixture,
    offline_package: bool,
) -> None:
    """UV builds do not warn about or prepare Poetry, online or offline."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "solution"\n\n[tool.uv]\n', encoding="utf-8")
    check_plugin = mocker.patch("ansys.saf.desktop.installer.__main__.check_poetry_plugin_export_is_required")
    poetry_python = mocker.patch("ansys.saf.desktop.installer.__main__._get_poetry_venv_python_exec")

    package_solution(SolutionInfo(tmp_path), InstallerConfig(offline_package=offline_package, no_executable=True))

    check_plugin.assert_not_called()
    poetry_python.assert_not_called()
    assert "Poetry-based solutions are deprecated" not in caplog.text


@pytest.mark.usefixtures("mock_installer_calls")
@pytest.mark.parametrize("offline_package", [False, True])
def test_poetry_packaging_warns_and_checks_plugin_only_offline(
    solution_root_dir: Path,
    mocker: pytest_mock.MockerFixture,
    caplog: pytest.LogCaptureFixture,
    offline_package: bool,
) -> None:
    """Poetry builds warn about deprecation and check the export plugin only offline."""
    check_plugin = mocker.patch(
        "ansys.saf.desktop.installer.__main__.check_poetry_plugin_export_is_required",
        return_value=False,
    )
    install_plugin = mocker.patch("ansys.saf.desktop.installer.__main__.subprocess.check_output")

    package_solution(
        SolutionInfo(solution_root_dir),
        InstallerConfig(offline_package=offline_package, no_executable=True),
    )

    assert "Poetry-based solutions are deprecated" in caplog.text
    if offline_package:
        check_plugin.assert_called_once_with(True)
    else:
        check_plugin.assert_not_called()
    install_plugin.assert_not_called()


@pytest.mark.usefixtures("mock_installer_calls")
@pytest.mark.parametrize("fails", [False, True])
def test_poetry_offline_packaging_installs_required_plugin(
    solution_root_dir: Path,
    mocker: pytest_mock.MockerFixture,
    fails: bool,
) -> None:
    """Install a required Poetry export plugin and surface installation failures."""
    mocker.patch("ansys.saf.desktop.installer.__main__.check_poetry_plugin_export_is_required", return_value=True)
    python = Path("poetry-python")
    mocker.patch("ansys.saf.desktop.installer.__main__._get_poetry_venv_python_exec", return_value=python)
    command = [python, "-m", "pip", "install", "poetry-plugin-export>=1.8"]
    install_plugin = mocker.patch("ansys.saf.desktop.installer.__main__.subprocess.check_output")
    if fails:
        install_plugin.side_effect = subprocess.CalledProcessError(1, command)

    config = InstallerConfig(offline_package=True, no_executable=True)
    if fails:
        with pytest.raises(RuntimeError, match="Failed to install poetry-plugin-export"):
            package_solution(SolutionInfo(solution_root_dir), config)
    else:
        package_solution(SolutionInfo(solution_root_dir), config)
    install_plugin.assert_called_once_with(command)


@pytest.mark.usefixtures("mock_installer_calls", "mock_solution_display_name")
def test_env_file_in_solution_root_dir(solution_root_dir: Path, mocker: pytest_mock.MockerFixture):
    env_file = solution_root_dir / ".env"
    env_file.write_text("POETRY_HTTP_BASIC_MOCK=mock")
    solution_info = SolutionInfo(solution_root_dir)
    config = InstallerConfig()

    mocker.patch.dict(os.environ, {})
    assert "POETRY_HTTP_BASIC_MOCK" not in os.environ
    package_solution(solution_info, config)
    assert os.environ["POETRY_HTTP_BASIC_MOCK"] == "mock"


def test_load_uv_index_credentials_from_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "UV_INDEX_INTERNAL_USERNAME=build-user\nUV_INDEX_INTERNAL_PASSWORD=build-token\nUNRELATED_SETTING=ignored\n",
        encoding="utf-8",
    )
    env: dict[str, str] = {}

    _load_filtered_dotenv(env_file, env)

    assert env == {
        "UV_INDEX_INTERNAL_USERNAME": "build-user",
        "UV_INDEX_INTERNAL_PASSWORD": "build-token",
    }


@pytest.mark.usefixtures("mock_installer_calls", "mock_solution_display_name")
@pytest.mark.parametrize("relative_path", [True, False])
def test_passing_env_file(
    solution_root_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
    relative_path: bool,
):
    env_file = solution_root_dir / "custom_dir" / ".env"
    env_file.parent.mkdir()
    env_file.write_text("POETRY_HTTP_BASIC_MOCK=mock")
    (solution_root_dir / ".env").unlink(missing_ok=True)

    solution_info = SolutionInfo(solution_root_dir)
    if relative_path:
        monkeypatch.chdir(solution_root_dir)
    config = InstallerConfig(env_file=env_file.relative_to(solution_root_dir) if relative_path else env_file.resolve())

    mocker.patch.dict(os.environ, {})
    assert "POETRY_HTTP_BASIC_MOCK" not in os.environ
    package_solution(solution_info, config)
    assert os.environ["POETRY_HTTP_BASIC_MOCK"] == "mock"


@pytest.mark.usefixtures("mock_installer_calls", "mock_solution_display_name")
def test_passing_env_file_has_priority_over_solution_root_dir(
    solution_root_dir: Path,
    mocker: pytest_mock.MockerFixture,
):
    env_file = solution_root_dir / "custom_dir" / ".env"
    env_file.parent.mkdir()
    env_file.write_text("POETRY_HTTP_BASIC_MOCK=mock")
    env_file_2 = solution_root_dir / ".env"
    env_file_2.write_text("POETRY_HTTP_BASIC_MOCK_2=mock")

    solution_info = SolutionInfo(solution_root_dir)
    config = InstallerConfig(env_file=env_file)

    mocker.patch.dict(os.environ, {})
    assert "POETRY_HTTP_BASIC_MOCK" not in os.environ
    assert "POETRY_HTTP_BASIC_MOCK_2" not in os.environ
    package_solution(solution_info, config)
    assert os.environ["POETRY_HTTP_BASIC_MOCK"] == "mock"
    assert "POETRY_HTTP_BASIC_MOCK_2" not in os.environ


@pytest.mark.usefixtures("mock_installer_calls", "mock_solution_display_name")
def test_non_related_env_vars_are_ignored(solution_root_dir: Path, mocker: pytest_mock.MockerFixture):
    env_file = solution_root_dir / ".env"
    env_file.write_text("POETRY_HTTP_BASIC_MOCK=mock\nMY_OTHER_ENV_VAR=mock")
    solution_info = SolutionInfo(solution_root_dir)
    config = InstallerConfig()

    mocker.patch.dict(os.environ, {})
    assert "POETRY_HTTP_BASIC_MOCK" not in os.environ
    assert "MY_OTHER_ENV_VAR" not in os.environ
    package_solution(solution_info, config)
    assert os.environ["POETRY_HTTP_BASIC_MOCK"] == "mock"
    assert "MY_OTHER_ENV_VAR" not in os.environ
