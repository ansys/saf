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

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest
import pytest_mock

from ansys.saf.desktop.orchestrator._config.schema import (
    GLOW_CORS_ORIGINS,
    GLOW_PORTAL_URL,
    GLOW_SOLUTION_DEFINITION,
    GLOW_WS_EVENTS_ADDR,
    PROJECTS_DASHBOARD_PATH,
    SAF_DESKTOP_PROJECTS_DASHBOARD_PATH,
    Settings,
)
from ansys.saf.desktop.orchestrator._orchestration.launcher import Launcher
from ansys.saf.desktop.orchestrator._orchestration.solution_ui_framework import SolutionUIFramework
from ansys.saf.testing.platform_specific import windows_only


def test_start_solution_ui(mocker: pytest_mock.MockerFixture):
    mock_start_solution_ui_service = mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.Launcher._start_solution_ui_service",
    )

    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )

    # Act
    launcher.start_solution_ui()

    # Assert
    mock_start_solution_ui_service.assert_called_once()


def test_get_project_streamlit(mocker: pytest_mock.MockerFixture):
    mock_get_service_info = mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.Launcher.get_service_info",
    )

    # Arrange
    mock_service_info = MagicMock()
    mock_service_info.address = "http://localhost:8501"
    mock_get_service_info.return_value = mock_service_info

    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.streamlit,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )

    project_name = "test_project"

    # Act
    project_url = launcher.get_project(project_name)

    # Assert
    mock_get_service_info.assert_called_once_with("UI")
    assert project_url == "http://localhost:8501/test_project"


@pytest.fixture
def no_projects_dashboard(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.importlib.util.find_spec",
        return_value=None,
    )


@pytest.fixture
def no_optional_packages(mocker: pytest_mock.MockerFixture) -> None:
    # A None entry in sys.modules makes the import raise ModuleNotFoundError.
    mocker.patch.dict(
        sys.modules,
        {
            "ansys.saf.desktop.portal.server.run_portal_server": None,
            "ansys.saf.portal.desktop.server.run_portal_server": None,
            "ansys.saf.pim_light_server.locate": None,
            "ansys.saf.aspire": None,
        },
    )


@pytest.mark.usefixtures("no_projects_dashboard", "no_optional_packages")
def test_missing_portal_raise_module_not_found():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )

    with pytest.raises(
        ModuleNotFoundError,
        match="The package 'ansys-saf-desktop-portal' is not installed or could not be found.",
    ):
        launcher.start_portal()


@pytest.mark.usefixtures("no_projects_dashboard", "no_optional_packages")
def test_start_portal_fallback_to_old_portal(mocker: pytest_mock.MockerFixture):
    import tests.mocks.mock_portal

    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )
    mocker.patch.dict(
        sys.modules,
        {
            "ansys.saf.portal": MagicMock(),
            "ansys.saf.portal.desktop": MagicMock(),
            "ansys.saf.portal.desktop.server": MagicMock(),
            "ansys.saf.portal.desktop.server.run_portal_server": tests.mocks.mock_portal,
        },
    )
    mock_python_proc = mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.PythonProcess",
    )

    launcher.start_portal()
    assert mock_python_proc.call_args[0][0] == tests.mocks.mock_portal.run_portal


@pytest.mark.usefixtures("no_projects_dashboard")
def test_start_portal_use_new_portal(mocker: pytest_mock.MockerFixture):
    import tests.mocks.mock_portal

    settings = Settings(saf_desktop_solution_name="solution", portal_api_version="v2")
    launcher = Launcher(
        settings,
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )
    mocker.patch.dict(
        sys.modules,
        {
            "ansys.saf.desktop.portal": MagicMock(),
            "ansys.saf.desktop.portal.server": MagicMock(),
            "ansys.saf.desktop.portal.server.run_portal_server": tests.mocks.mock_portal,
        },
    )
    mock_python_proc = mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.PythonProcess",
    )

    launcher.start_portal()
    portal_process_args = mock_python_proc.call_args
    assert portal_process_args.args[0] == tests.mocks.mock_portal.run_portal
    assert portal_process_args.args[1]["api_version"] == "v2"
    assert portal_process_args.kwargs["health_route"] == "/api/v2/health"


@pytest.mark.usefixtures("cleanup_awp_root_env_vars", "no_optional_packages")
def test_missing_pim_light_server_raise_module_not_found():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="tests.mocks.solutions.minimal_pim_solution.solution.definition",
        with_pim=True,
        with_ui=False,
        ui_framework=SolutionUIFramework.no_ui,
        with_portal=False,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )

    with pytest.raises(
        ModuleNotFoundError,
        match="The package 'ansys-saf-pim-light-server' is not installed or could not be found.",
    ):
        launcher.start_pim()


@windows_only()
@pytest.mark.usefixtures("cleanup_awp_root_env_vars", "no_optional_packages")
def test_pim_light_server_from_unified_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
):
    # When: a fake pim light server is in AWP_ROOT
    pim_dir = tmp_path / "pim" / "ansys" / "instancemanagement" / "light"
    pim_exe = pim_dir / "Ansys.InstanceManagement.Light.exe"
    pim_dir.mkdir(parents=True, exist_ok=True)
    pim_exe.touch()
    monkeypatch.setenv("AWP_ROOT191", tmp_path.as_posix())
    from ansys.saf.desktop.orchestrator._orchestration.launcher import PimProcess

    mock_pim_proc = mocker.spy(
        PimProcess,
        "_build_cmd_args",
    )
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="tests.mocks.solutions.minimal_pim_solution.solution.definition",
        with_pim=True,
        with_ui=False,
        ui_framework=SolutionUIFramework.no_ui,
        with_portal=False,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )

    # And launching pim light server
    with pytest.raises(OSError):  # noqa: PT011
        # then it fails to be started because the fake executable is not a real pim light server
        launcher.start_pim()
    # but the pim executable from the unified installation is used
    assert mock_pim_proc.spy_return[0] == pim_exe.as_posix()


@pytest.mark.usefixtures("no_optional_packages")
def test_missing_aspire_raise_module_not_found():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="tests.mocks.solutions.minimal_pim_solution.solution.definition",
        with_pim=False,
        with_ui=False,
        ui_framework=SolutionUIFramework.no_ui,
        with_portal=False,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )

    with pytest.raises(
        ModuleNotFoundError,
        match="The package 'ansys-saf-aspire' is not installed or could not be found.",
    ):
        launcher.start_otel()


def test_configure_solution_ui_environment_sets_ws_events_addr_when_not_set(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(GLOW_WS_EVENTS_ADDR, raising=False)
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=False,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    ui_env = launcher._configure_solution_ui_environment()  # pyright: ignore[reportPrivateUsage]
    host = launcher._hosts["solution_api"]  # pyright: ignore[reportPrivateUsage]
    port = launcher._ports["solution_api"]  # pyright: ignore[reportPrivateUsage]
    assert ui_env[GLOW_WS_EVENTS_ADDR] == f"ws://{host}:{port}"


@pytest.mark.usefixtures("no_projects_dashboard")
def test_launcher_use_projects_dashboard_false_without_package():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    assert not launcher.use_projects_dashboard


@pytest.mark.parametrize("finder_error", [ModuleNotFoundError, ValueError])
def test_launcher_use_projects_dashboard_false_when_discovery_fails(
    mocker: pytest_mock.MockerFixture,
    finder_error: type[Exception],
):
    mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.importlib.util.find_spec",
        side_effect=finder_error("dashboard package is unavailable"),
    )
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    assert not launcher.use_projects_dashboard


def test_launcher_use_projects_dashboard_false_without_ui():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=False,
        ui_framework=SolutionUIFramework.no_ui,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    assert not launcher.use_projects_dashboard


def test_launcher_use_projects_dashboard_false_with_streamlit(mocker: pytest_mock.MockerFixture):
    mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.importlib.util.find_spec",
        return_value=MagicMock(),
    )
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.streamlit,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    assert not launcher.use_projects_dashboard


def test_launcher_use_projects_dashboard_true(mocker: pytest_mock.MockerFixture):
    mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.importlib.util.find_spec",
        return_value=MagicMock(),
    )
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    assert launcher.use_projects_dashboard


def test_projects_dashboard_module_name_is_correct():
    from ansys.saf.desktop.orchestrator._orchestration.launcher import PROJECTS_DASHBOARD_MODULE

    assert PROJECTS_DASHBOARD_MODULE == "ansys_saf_projects_dashboard"


def test_configure_solution_ui_environment_sets_projects_dashboard_portal_url(mocker: pytest_mock.MockerFixture):
    mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.importlib.util.find_spec",
        return_value=MagicMock(),
    )
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    ui_env = launcher._configure_solution_ui_environment()  # pyright: ignore[reportPrivateUsage]
    ui_host = launcher._hosts["solution_ui"]  # pyright: ignore[reportPrivateUsage]
    ui_port = launcher._ports["solution_ui"]  # pyright: ignore[reportPrivateUsage]
    assert ui_env[GLOW_PORTAL_URL] == f"http://{ui_host}:{ui_port}{PROJECTS_DASHBOARD_PATH}"
    assert "portal_ui" not in launcher._ports  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("configured_path", "expected_path"),
    [("/custom/", "/custom"), ("custom", "/custom"), ("", "/projects")],
)
def test_launcher_projects_dashboard_path_from_env(
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
    configured_path: str,
    expected_path: str,
):
    mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.importlib.util.find_spec",
        return_value=MagicMock(),
    )
    monkeypatch.setenv(SAF_DESKTOP_PROJECTS_DASHBOARD_PATH, configured_path)
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    assert launcher.projects_dashboard_path == expected_path
    ui_env = launcher._configure_solution_ui_environment()  # pyright: ignore[reportPrivateUsage]
    ui_host = launcher._hosts["solution_ui"]  # pyright: ignore[reportPrivateUsage]
    ui_port = launcher._ports["solution_ui"]  # pyright: ignore[reportPrivateUsage]
    assert ui_env[GLOW_PORTAL_URL] == f"http://{ui_host}:{ui_port}{expected_path}"


def test_configure_portal_ui_environment_sets_solution_definition_when_not_in_env(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(GLOW_SOLUTION_DEFINITION, raising=False)
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "my.definition.module",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=True,
    )
    portal_env = launcher._configure_portal_ui_environment()  # pyright: ignore[reportPrivateUsage]
    assert portal_env[GLOW_SOLUTION_DEFINITION] == "my.definition.module"


def test_configure_portal_ui_environment_keeps_solution_definition_when_already_in_env(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(GLOW_SOLUTION_DEFINITION, "env.definition.module")
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "my.definition.module",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=True,
    )
    portal_env = launcher._configure_portal_ui_environment()  # pyright: ignore[reportPrivateUsage]
    assert portal_env[GLOW_SOLUTION_DEFINITION] == "env.definition.module"


def test_configure_solution_api_environment_sets_cors_origin_when_ui_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(GLOW_CORS_ORIGINS, raising=False)
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=False,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    api_env = launcher._configure_solution_api_environment()  # pyright: ignore[reportPrivateUsage]
    ui_host = launcher._hosts["solution_ui"]  # pyright: ignore[reportPrivateUsage]
    ui_port = launcher._ports["solution_ui"]  # pyright: ignore[reportPrivateUsage]
    assert json.loads(api_env[GLOW_CORS_ORIGINS]) == [f"http://{ui_host}:{ui_port}"]


def test_configure_solution_api_environment_merges_cors_origin_with_existing_env(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(GLOW_CORS_ORIGINS, json.dumps(["https://example.com"]))
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=True,
        ui_framework=SolutionUIFramework.dash,
        with_portal=False,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    api_env = launcher._configure_solution_api_environment()  # pyright: ignore[reportPrivateUsage]
    ui_host = launcher._hosts["solution_ui"]  # pyright: ignore[reportPrivateUsage]
    ui_port = launcher._ports["solution_ui"]  # pyright: ignore[reportPrivateUsage]
    assert json.loads(api_env[GLOW_CORS_ORIGINS]) == [f"http://{ui_host}:{ui_port}", "https://example.com"]


def test_configure_solution_api_environment_omits_cors_origin_when_no_ui(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(GLOW_CORS_ORIGINS, raising=False)
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        "solution",
        "definition",
        with_pim=False,
        with_ui=False,
        ui_framework=SolutionUIFramework.no_ui,
        with_portal=False,
        env_file=None,
        enable_automatic_project_migration=False,
    )
    api_env = launcher._configure_solution_api_environment()  # pyright: ignore[reportPrivateUsage]
    assert GLOW_CORS_ORIGINS not in api_env
