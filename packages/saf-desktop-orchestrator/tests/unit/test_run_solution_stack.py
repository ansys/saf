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
from concurrent.futures import ThreadPoolExecutor
import functools
import os
from pathlib import Path
import platform
import re
import sys
from typing import Any
from unittest.mock import MagicMock

import httpx2
from pydantic import ValidationError
import pytest
from pytest_mock import MockerFixture

from ansys.saf.desktop.orchestrator._config.schema import (
    GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION,
    GLOW_PRODUCT_INSTANCE_SYSTEM,
    GLOW_WS_EVENTS_ADDR,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_HEADERS,
    SAF_DESKTOP_LOG_TO_FILES,
)
from ansys.saf.desktop.orchestrator._orchestration.exceptions import (
    CantCreateProjectError,
    SameDisplayNameProjectException,
)
from ansys.saf.desktop.orchestrator._orchestration.launcher import PROJECTS_DASHBOARD_MODULE
from ansys.saf.desktop.orchestrator._orchestration.orchestrator import Orchestrator
from ansys.saf.desktop.orchestrator._orchestration.otel_process import OtelProcess
from ansys.saf.desktop.orchestrator._orchestration.process import ServiceProcess
from ansys.saf.desktop.orchestrator._orchestration.python_process import PythonProcess
from ansys.saf.desktop.orchestrator._orchestration.pywebview_events import set_custom_pywebview_icon
from ansys.saf.desktop.orchestrator._orchestration.run_solution_stack import run_solution_stack
from ansys.saf.desktop.orchestrator._utilities.splash_screen import SplashScreen
from ansys.saf.glow.cli import run_api
from ansys.saf.glow.client import AnalysisResultModel
from ansys.saf.testing.common import YieldFixture
from tests.mocks.solutions_main import minimal_main

SOLUTION_NAME = "My Solution"
SOLUTION_MAIN_MODULE = "tests.mocks.solutions_main.minimal_main"


@pytest.fixture
def input_project_display_name(request: pytest.FixtureRequest) -> str:
    return "" if not hasattr(request, "param") else str(request.param)


@pytest.fixture
def project_exists_in_db(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def multiple_exists(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def fails_to_create(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def ui_module(request: pytest.FixtureRequest) -> str:
    return "mock_ui_module" if not hasattr(request, "param") else str(request.param)


@pytest.fixture
def invalid_solution(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def no_ui(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def streamlit_ui(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def portal(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def projects_dashboard_installed(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def with_pim(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def with_hps_as_pims(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> bool:
    hps_as_pims = False if not hasattr(request, "param") else bool(request.param)
    if hps_as_pims:
        monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "HPS")
    return hps_as_pims


@pytest.fixture
def add_services(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def browser(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def log_to_files(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def env_file(request: pytest.FixtureRequest, tmp_path: Path) -> Path | None:
    return (tmp_path / ".env") if bool(getattr(request, "param", False)) else None


@pytest.fixture
def reset_env_after_test() -> YieldFixture[None]:
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def enable_automatic_project_migration(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def pre_load(request: pytest.FixtureRequest) -> bool:
    return False if not hasattr(request, "param") else bool(request.param)


@pytest.fixture
def check_service_env_vars(
    mocker: MockerFixture,
    no_ui: bool,
    portal: bool,
    projects_dashboard_installed: bool,
    enable_automatic_project_migration: bool,
    log_to_files: bool,
) -> YieldFixture[None]:
    python_proc_spy = mocker.spy(PythonProcess, "__init__")
    service_proc_spy = mocker.spy(ServiceProcess, "__init__")
    otel_proc_spy = mocker.spy(OtelProcess, "__init__")
    yield

    if python_proc_spy.call_args and python_proc_spy.call_args[0][1] == run_api:
        if log_to_files:
            otel_proc_spy.assert_not_called()
        else:
            assert (
                otel_proc_spy.call_args[1]["otlp_url"]
                == python_proc_spy.call_args[1]["env"][OTEL_EXPORTER_OTLP_ENDPOINT]
            )
            assert otel_proc_spy.call_args[1]["api_key"] == python_proc_spy.call_args[1]["env"][
                OTEL_EXPORTER_OTLP_HEADERS
            ].removeprefix("x-otlp-api-key=")
        if enable_automatic_project_migration:
            assert python_proc_spy.call_args[1]["env"][GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION] == "True"
        else:
            assert GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION not in python_proc_spy.call_args[1]["env"]

    if (
        not no_ui
        and service_proc_spy.call_args
        and "ui" in service_proc_spy.call_args[0][1]
        and GLOW_WS_EVENTS_ADDR in service_proc_spy.call_args[1]["env"]
    ):
        if log_to_files:
            otel_proc_spy.assert_not_called()
        else:
            assert (
                otel_proc_spy.call_args[1]["otlp_url"]
                == service_proc_spy.call_args[1]["env"][OTEL_EXPORTER_OTLP_ENDPOINT]
            )
            assert otel_proc_spy.call_args[1]["api_key"] == python_proc_spy.call_args[1]["env"][
                OTEL_EXPORTER_OTLP_HEADERS
            ].removeprefix("x-otlp-api-key=")

    if portal and python_proc_spy.call_args and not projects_dashboard_installed:
        run_portal_mock = sys.modules["ansys.saf.desktop.portal.server.run_portal_server"].run_portal
        if python_proc_spy.call_args[0][1] == run_portal_mock:
            assert (
                otel_proc_spy.call_args[1]["otlp_url"]
                == python_proc_spy.call_args[1]["env"][OTEL_EXPORTER_OTLP_ENDPOINT]
            )


@pytest.fixture
def mock_orchestrator(  # noqa: C901
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    input_project_display_name: str,
    project_exists_in_db: bool,
    multiple_exists: bool,
    fails_to_create: bool,
    ui_module: str,
    with_pim: bool,
    invalid_solution: bool,
    tmp_path: Path,
    projects_dashboard_installed: bool,
    check_service_env_vars: None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    monkeypatch.setenv("SAF_DESKTOP_TEST_ENV", "True")
    monkeypatch.setenv("APPDATA", tmp_path.as_posix())
    monkeypatch.setenv("XDG_DATA_HOME", tmp_path.as_posix())

    class MockHttpClient(httpx2.Client):
        def get(self, url: str, params: dict[str, Any] | None = None) -> httpx2.Response:  # pyright: ignore[reportIncompatibleMethodOverride]
            if url.endswith("/projects"):
                if project_exists_in_db:
                    projects = {
                        "projects": [{"name": "projects/existing_id", "display_name": input_project_display_name}],
                        "page": 1,
                        "page_size": 10,
                        "total_pages": 1,
                        "total_projects": 1,
                    }
                    if multiple_exists:
                        projects["projects"] *= 2
                    return httpx2.Response(200, json=projects, request=httpx2.Request("GET", url))
                return httpx2.Response(
                    200,
                    json={
                        "projects": [],
                        "page": 1,
                        "page_size": 10,
                        "total_pages": 1,
                        "total_projects": 0,
                    },
                    request=httpx2.Request("GET", url),
                )
            elif url.endswith("/schema"):
                return httpx2.Response(
                    200,
                    json={"properties": {"display_name": {"default": SOLUTION_NAME}}},
                    request=httpx2.Request("GET", url),
                )
            elif url.endswith("/health"):
                return httpx2.Response(200, request=httpx2.Request("GET", url))
            else:
                raise Exception(f"Unexpected URL: {url}")

        def post(  # pyright: ignore[reportIncompatibleMethodOverride]
            self,
            url: str,
            json: dict[str, Any] | None = None,
            timeout: int = 5,
        ) -> httpx2.Response:
            if url.endswith("/desktop:exit"):
                return httpx2.Response(200, request=httpx2.Request("POST", url))
            elif url.endswith("/projects"):
                if fails_to_create:
                    return httpx2.Response(
                        500,
                        json={"error": "Failed to create project"},
                        request=httpx2.Request("POST", url),
                    )
                return httpx2.Response(
                    200,
                    json={"name": "projects/new_id", "display_name": "random_display_name"},
                    request=httpx2.Request("POST", url),
                )
            else:
                raise Exception(f"Unexpected URL: {url}")

    mocker.patch(
        "ansys.saf.glow.cli.run_analysis",
        return_value=AnalysisResultModel(
            valid=not invalid_solution,
            uses_shared_product_instances=with_pim,
            ui_module=ui_module,
            solution_module=minimal_main.__name__,
            solution_name=SOLUTION_NAME,
            error="mock error" if invalid_solution else "",
        ),
    )

    mocker.patch.object(ServiceProcess, "run")
    mocker.patch.object(PythonProcess, "run")
    mocker.patch.object(ThreadPoolExecutor, "shutdown")
    mocker.patch("ansys.saf.desktop.orchestrator._orchestration.launcher.Launcher.wait_for_healthy")
    mocker.patch("ansys.saf.desktop.orchestrator._orchestration.streamlit_launcher.StreamlitLauncher._get_ui_app_path")
    mocker.patch("ansys.saf.desktop.orchestrator._orchestration.run_solution_stack.httpx2.Client", MockHttpClient)
    mock_webview_create = mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.run_solution_stack.webview.create_window",
    )
    mock_webview_start = mocker.patch("ansys.saf.desktop.orchestrator._orchestration.run_solution_stack.webview.start")
    mock_webbrowser_open = mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.run_solution_stack.webbrowser.open",
    )
    aspire_mock = MagicMock()
    aspire_mock.__path__ = [str(tmp_path)]
    mocker.patch.dict(
        sys.modules,
        {
            "ansys.saf.desktop.portal": MagicMock(),
            "ansys.saf.desktop.portal.server": MagicMock(),
            "ansys.saf.desktop.portal.server.run_portal_server": MagicMock(),
            "ansys.saf.portal": MagicMock(),
            "ansys.saf.portal.desktop": MagicMock(),
            "ansys.saf.portal.desktop.server": MagicMock(),
            "ansys.saf.portal.desktop.server.run_portal_server": MagicMock(),
            "ansys.saf.pim_light_server": MagicMock(),
            "ansys.saf.pim_light_server.locate": MagicMock(),
            "ansys.saf.aspire": aspire_mock,
        },
    )
    monkeypatch.setattr("ansys.saf.aspire", aspire_mock, raising=False)

    def _mock_find_spec(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "ansys.saf.aspire":
            return True
        if name == PROJECTS_DASHBOARD_MODULE and projects_dashboard_installed:
            return MagicMock()
        return None

    mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.run_solution_stack.importlib.util.find_spec",
        side_effect=_mock_find_spec,
    )
    mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.launcher.importlib.util.find_spec",
        side_effect=_mock_find_spec,
    )

    return mock_webview_create, mock_webview_start, mock_webbrowser_open


@pytest.fixture
def verify_user_msgs(
    capsys: pytest.CaptureFixture[str],
    project_exists_in_db: bool,
    input_project_display_name: str,
    no_ui: bool,
    ui_module: str,
    streamlit_ui: bool,
    portal: bool,
    projects_dashboard_installed: bool,
    with_pim: bool,
    with_hps_as_pims: bool,
    add_services: bool,
    env_file: Path | None,
    log_to_files: bool,
) -> Callable[[], str]:

    def _verify_user_msgs() -> str:
        # not sure why the printed messages are in the stderr within pytest,
        # but they are displayed properly in stdout in the real world.
        printed_msgs = capsys.readouterr().err

        # Information is shown to the user
        assert f"Solution: {SOLUTION_NAME}" in printed_msgs

        expected_api_url = re.compile(r"Solution API: http://127.0.0.1:\d+/docs")
        assert re.search(expected_api_url, printed_msgs)

        ui_url = ""
        if portal:
            expected_solution_ui_url = re.compile(r"Solution UI: http://127.0.0.1:\d+")
            assert re.search(expected_solution_ui_url, printed_msgs)

            expected_project_info = "Project: no project created or selected"
            assert re.search(expected_project_info, printed_msgs)

            if projects_dashboard_installed:
                assert re.search("SAF Portal: not launched", printed_msgs)
                solution_ui_match = re.search(r"Solution UI: (http://127\.0\.0\.1:\d+)", printed_msgs)
                assert solution_ui_match
                ui_url = f"{solution_ui_match.group(1)}/projects"
                expected_projects_dashboard = re.compile(
                    r"Projects Dashboard: http://127\.0\.0\.1:\d+/projects",
                )
                assert re.search(expected_projects_dashboard, printed_msgs)
            else:
                expected_portal_url = re.compile(r"SAF Portal: http://127.0.0.1:\d+")
                ui_url_match = re.search(expected_portal_url, printed_msgs)
                assert ui_url_match

                ui_url = ui_url_match.group().split("SAF Portal: ")[1]
        else:
            expected_project_id = "projects/new_id" if not project_exists_in_db else "projects/existing_id"
            expected_project_info = (
                f"Project: \n- display name: {input_project_display_name}\n- name: {expected_project_id}"
            )
            if not input_project_display_name:
                expected_project_info = re.compile(
                    rf"Project: \n- display name: my-project-[0-9a-f]{{5}}\n- name: {expected_project_id}",
                )
            assert re.search(expected_project_info, printed_msgs)

            if not no_ui and (ui_module or streamlit_ui):
                args = f"/{expected_project_id}" if not streamlit_ui else rf"/\?project_id={expected_project_id}"
                expected_solution_ui_info = re.compile(rf"Solution UI: http://127.0.0.1:\d+{args}")
                ui_url_match = re.search(expected_solution_ui_info, printed_msgs)
                assert ui_url_match

                ui_url = ui_url_match.group().split("Solution UI: ")[1]

            expected_portal_url = "SAF Portal: not launched"
            assert re.search(expected_portal_url, printed_msgs)

        expected_otel_url = (
            re.compile(r"OTEL Dashboard: http://127.0.0.1:\d+") if not log_to_files else "OTEL Dashboard: not launched"
        )
        assert re.search(expected_otel_url, printed_msgs)

        expected_pim_url = "PIM Light Server: not launched"
        if with_pim and not with_hps_as_pims:
            expected_pim_url = (
                re.compile(r"PIM Light Server: http://127.0.0.1:\d+")
                if platform.system() == "Windows"
                else re.compile(r"PIM Light Server: unix:/.*/pim-.*\.sock")
            )
        assert re.search(expected_pim_url, printed_msgs)

        if add_services:
            expected_message = re.compile(r"Additional services:\n")
            assert re.search(expected_message, printed_msgs)
            expected_http_services_url = re.compile(r"HTTP_SERVICE: http://localhost:\d+")
            assert re.search(expected_http_services_url, printed_msgs)
            expected_grpc_services_url = re.compile(r"GRPC_SERVICE: http://localhost:\d+")
            assert re.search(expected_grpc_services_url, printed_msgs)
        else:
            expected_message = "Additional services: not launched"
            assert re.search(expected_message, printed_msgs)

        if env_file:
            assert f"Environment variables loaded from {env_file.resolve()}" in printed_msgs
        else:
            assert "Environment variables loaded from" not in printed_msgs

        return ui_url

    return _verify_user_msgs


@pytest.fixture
def verify_user_ui(
    ui_module: str,
    no_ui: bool,
    streamlit_ui: bool,
    browser: bool,
    pre_load: bool,
) -> Callable[[MagicMock, MagicMock, MagicMock, str], None]:

    def _verify_user_ui(
        mock_webview_create: MagicMock,
        mock_webview_start: MagicMock,
        mock_webbrowser_open: MagicMock,
        ui_url: str,
    ) -> None:
        using_webview = (
            ((ui_module and not no_ui) or (streamlit_ui and not no_ui))
            and not browser
            and platform.system() == "Windows"
        )

        if pre_load:
            if using_webview:
                mock_webview_create.assert_called_once_with(
                    SOLUTION_NAME,
                    ui_url,
                    text_select=True,
                    min_size=(1200, 800),
                    confirm_close=True,
                )
            else:
                mock_webview_create.assert_not_called()

            mock_webview_start.assert_not_called()
            mock_webbrowser_open.assert_not_called()
        elif using_webview:
            mock_webview_create.assert_called_once_with(
                SOLUTION_NAME,
                ui_url,
                text_select=True,
                min_size=(1200, 800),
                confirm_close=True,
            )
            mock_webview_start.assert_called_once()
            mock_webbrowser_open.assert_not_called()
        elif (
            ((ui_module and not no_ui) or (streamlit_ui and not no_ui))
            and not browser
            and platform.system() == "Linux"
            or ((ui_module and not no_ui) or (streamlit_ui and not no_ui))
            and browser
        ):
            mock_webview_create.assert_not_called()
            mock_webview_start.assert_not_called()
            mock_webbrowser_open.assert_called_once_with(ui_url)
        else:
            mock_webview_create.assert_not_called()
            mock_webview_start.assert_not_called()
            mock_webbrowser_open.assert_not_called()

    return _verify_user_ui


def test_run_solution_stack_without_solution_main_module_name():
    with pytest.raises(TypeError, match="missing 1 required positional argument: 'solution_main_module_name'"):
        run_solution_stack()  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize("invalid_solution", [True], indirect=True)
@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_with_invalid_solution():
    with pytest.raises(RuntimeError, match="mock error"):
        run_solution_stack(SOLUTION_MAIN_MODULE)


@pytest.mark.parametrize("ui_module", ["", "test"], ids=["solution-without-ui", "solution-with-ui"], indirect=True)
def test_run_solution_stack(
    mocker: MockerFixture,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_start_splash = mocker.patch.object(SplashScreen, "start_splash")
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE)

    if platform.system() == "Windows":
        # No matter if UI module is present, the splash screen should be displayed on Windows.
        mock_start_splash.assert_called_once()
    else:
        # On non-Windows platforms, the splash screen should not be displayed.
        mock_start_splash.assert_not_called()

    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


def test_run_solution_stack_registers_event_to_load_pywebview_custom_icon(
    mocker: MockerFixture,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    partial_spy = mocker.patch(
        "ansys.saf.desktop.orchestrator._orchestration.run_solution_stack.partial",
        wraps=functools.partial,
    )
    run_solution_stack(SOLUTION_MAIN_MODULE)
    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)

    # Couldn't find a way of asserting that set_custom_pywebview_icon has been registered as an event or that
    # it has been triggered. Instead, we assert that functools.partial has been called with set_custom_pywebview_icon as
    # the first argument, which is how the event handler is registered. The details of what set_custom_pywebview_icon
    # does are tested in test_pywebview_events.py.
    if platform.system() == "Windows":
        partial_spy.assert_called_once()
        args = partial_spy.call_args[0]
        assert args[0] is set_custom_pywebview_icon
        assert args[2] == SOLUTION_MAIN_MODULE
    else:
        partial_spy.assert_not_called()


@pytest.mark.parametrize("pre_load", [True], indirect=True)
def test_run_solution_stack_in_pre_load_mode(
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    mocker: MockerFixture,
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
    pre_load: bool,
):
    mock_start_splash = mocker.patch.object(SplashScreen, "start_splash")
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, pre_load=pre_load)

    # enabling preload should prevent the splash screen from being displayed.
    mock_start_splash.assert_not_called()

    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.parametrize("ui_module", ["", "test"], ids=["solution-without-ui", "solution-with-ui"], indirect=True)
@pytest.mark.parametrize("no_ui", [True], indirect=True)
def test_run_solution_stack_no_ui(
    no_ui: bool,
    mocker: MockerFixture,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_start_splash = mocker.patch.object(SplashScreen, "start_splash")

    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, no_ui=no_ui)

    # No matter if UI module is present, no-ui should prevent the splash screen from being displayed.
    mock_start_splash.assert_not_called()

    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.parametrize("portal", [False, True], ids=["without-portal", "with-portal"], indirect=True)
@pytest.mark.parametrize("browser", [True], indirect=True)
def test_run_solution_stack_with_browser(
    portal: bool,
    browser: bool,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, portal=portal, browser=browser)
    portal_or_project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, portal_or_project_ui_url)


@pytest.mark.parametrize("browser", [True], indirect=True)
@pytest.mark.parametrize(
    ("ui_module", "no_ui"),
    [
        ("", False),
        ("test", True),
    ],
    ids=["solution-without-ui", "no-ui"],
    indirect=True,
)
@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_with_browser_without_ui(no_ui: bool, browser: bool):
    with pytest.raises(ValueError, match="Portal and/or Browser cannot be enabled if the solution UI is disabled."):
        run_solution_stack(SOLUTION_MAIN_MODULE, no_ui=no_ui, browser=browser)


@pytest.mark.parametrize("portal", [True], indirect=True)
@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
@pytest.mark.parametrize("browser", [False, True], ids=["no-browser", "with-browser"], indirect=True)
def test_run_solution_stack_with_portal_projects_dashboard(
    portal: bool,
    projects_dashboard_installed: bool,
    browser: bool,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, portal=portal, browser=browser)
    projects_dashboard_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, projects_dashboard_url)


@pytest.mark.parametrize("portal", [True], indirect=True)
@pytest.mark.parametrize("browser", [False, True], ids=["no-browser", "with-browser"], indirect=True)
def test_run_solution_stack_with_portal(
    portal: bool,
    browser: bool,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, portal=portal, browser=browser)
    portal_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, portal_ui_url)


@pytest.mark.parametrize("portal", [True], indirect=True)
@pytest.mark.parametrize(
    ("ui_module", "no_ui"),
    [
        ("", False),
        ("test", True),
    ],
    ids=["solution-without-ui", "no-ui"],
    indirect=True,
)
@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_with_portal_without_ui(portal: bool, no_ui: bool):
    with pytest.raises(ValueError, match="Portal and/or Browser cannot be enabled if the solution UI is disabled."):
        run_solution_stack(SOLUTION_MAIN_MODULE, portal=portal, no_ui=no_ui)


@pytest.mark.parametrize("portal", [True], indirect=True)
@pytest.mark.parametrize("input_project_display_name", ["custom_project"], indirect=True)
@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_with_portal_and_input_project_display_name(portal: bool, input_project_display_name: str):
    with pytest.raises(ValueError, match="A project display name cannot be specified when portal is enabled."):
        run_solution_stack(SOLUTION_MAIN_MODULE, portal=portal, input_project_display_name=input_project_display_name)


@pytest.mark.parametrize("project_exists_in_db", [False, True], ids=["new-project", "existing-project"], indirect=True)
@pytest.mark.parametrize("input_project_display_name", ["custom_project"], indirect=True)
def test_run_solution_stack_with_input_project(
    input_project_display_name: str,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, input_project_display_name=input_project_display_name)
    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.parametrize("input_project_display_name", ["custom_project"], indirect=True)
@pytest.mark.parametrize("fails_to_create", [True], indirect=True)
@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_with_input_project_fails_to_create(input_project_display_name: str):
    with pytest.raises(CantCreateProjectError, match="Project `custom_project` could not be created."):
        run_solution_stack(SOLUTION_MAIN_MODULE, input_project_display_name=input_project_display_name)


@pytest.mark.parametrize("input_project_display_name", ["custom_project"], indirect=True)
@pytest.mark.parametrize("project_exists_in_db", [True], indirect=True)
@pytest.mark.parametrize("multiple_exists", [True], indirect=True)
@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_with_input_project_fails_to_retrieve(input_project_display_name: str):
    with pytest.raises(
        SameDisplayNameProjectException,
        match="Multiple projects found with display name custom_project.",
    ):
        run_solution_stack(SOLUTION_MAIN_MODULE, input_project_display_name=input_project_display_name)


@pytest.mark.parametrize("streamlit_ui", [True], indirect=True)
@pytest.mark.parametrize(
    ("ui_module", "portal", "browser"),
    [
        ("test", False, False),
        ("", False, False),
        ("test", True, False),
        ("test", False, True),
    ],
    ids=["default", "solution-without-ui", "with-portal", "with-browser"],
    indirect=True,
)
def test_run_solution_stack_with_streamlit(
    streamlit_ui: bool,
    portal: bool,
    browser: bool,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(
        SOLUTION_MAIN_MODULE,
        portal=portal,
        browser=browser,
        streamlit_ui=streamlit_ui,
    )
    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.parametrize("streamlit_ui", [True], indirect=True)
@pytest.mark.parametrize("no_ui", [True], indirect=True)
@pytest.mark.parametrize(
    ("portal", "browser"),
    [
        (True, False),
        (False, True),
    ],
    ids=["with-portal", "with-browser"],
    indirect=True,
)
@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_with_streamlit_with_no_ui(
    streamlit_ui: bool,
    no_ui: bool,
    portal: bool,
    browser: bool,
):
    with pytest.raises(ValueError, match="Portal and/or Browser cannot be enabled if the solution UI is disabled."):
        run_solution_stack(
            SOLUTION_MAIN_MODULE,
            no_ui=no_ui,
            streamlit_ui=streamlit_ui,
            portal=portal,
            browser=browser,
        )


@pytest.mark.parametrize("with_pim", [True], indirect=True)
def test_run_solution_stack_with_pim(
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE)
    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.parametrize("log_to_files", [True, False], indirect=True)
def test_run_solution_stack_log_to_files(
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
    log_to_files: bool,
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, log_to_files=log_to_files)
    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.parametrize("add_services", [True], indirect=True)
def test_run_solution_stack_with_additional_services(
    monkeypatch: pytest.MonkeyPatch,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    services_file = Path(__file__).parent.parent / "integration" / "additional_services" / "additional_services.yaml"
    assert services_file.is_file()
    monkeypatch.setenv("SAF_DEFINITION_PATH", services_file.as_posix())
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE)
    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.parametrize("env_file", [True], indirect=True)
@pytest.mark.parametrize("add_services", [True], indirect=True)
@pytest.mark.usefixtures("reset_env_after_test")
def test_run_solution_stack_with_env_file(
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
    tmp_path: Path,
):
    services_file = Path(__file__).parent.parent / "integration" / "additional_services" / "additional_services.yaml"
    assert services_file.is_file()
    (tmp_path / ".env").write_text(f"SAF_DEFINITION_PATH={services_file.as_posix()}")
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, env_file=tmp_path / ".env")
    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.parametrize("portal", [True, False], indirect=True)
@pytest.mark.parametrize("with_pim", [True], indirect=True)
@pytest.mark.parametrize("add_services", [True], indirect=True)
@pytest.mark.parametrize("streamlit_ui", [False, True], indirect=True)
def test_run_solution_stack_does_not_set_global_env_vars(
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
    monkeypatch: pytest.MonkeyPatch,
    portal: bool,
    streamlit_ui: bool,
):
    # run solution stack does not set global env vars that are later passed to the launched services
    # test launching all possible services: API, UI (dash / streamlit), Portal, PIM, additional services and OTEL.
    services_file = Path(__file__).parent.parent / "integration" / "additional_services" / "additional_services.yaml"
    assert services_file.is_file()
    monkeypatch.setenv("SAF_DEFINITION_PATH", services_file.as_posix())
    env = os.environ.copy()
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE, portal=portal, streamlit_ui=streamlit_ui)
    portal_or_project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, portal_or_project_ui_url)
    assert env == os.environ.copy()


@pytest.mark.parametrize("portal", [True], indirect=True)
@pytest.mark.parametrize("with_pim", [True], indirect=True)
@pytest.mark.parametrize("add_services", [True], indirect=True)
@pytest.mark.usefixtures("reset_env_after_test")
@pytest.mark.parametrize(
    "no_proxy_value",
    [
        None,
        "",
        "localhost,fake.value",
        "fake.value,::1",
        "::1,127.0.0.1,localhost",
        "localhost,fake.value,::1",
        ",,,",
        "  corp.internal , localhost , , ::1  ",
        "LOCALHOST,127.0.0.1",
        "localhost:8080,fake.value:3128",
        "10.0.0.0/8,*.internal",
    ],
)
def test_run_solution_stack_services_inherit_no_proxy_loopback_addresses(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    portal: bool,
    add_services: bool,
    no_proxy_value: str | None,
):
    services_file = Path(__file__).parent.parent / "integration" / "additional_services" / "additional_services.yaml"
    assert services_file.is_file()
    monkeypatch.setenv("SAF_DEFINITION_PATH", services_file.as_posix())
    if no_proxy_value is None:
        monkeypatch.delenv("NO_PROXY", raising=False)
        if platform.system() == "Linux":
            monkeypatch.delenv("no_proxy", raising=False)
    else:
        monkeypatch.setenv("NO_PROXY", no_proxy_value)
        if platform.system() == "Linux":
            monkeypatch.setenv("no_proxy", no_proxy_value)

    start_service_spy = mocker.spy(Orchestrator, "start_service")

    run_solution_stack(SOLUTION_MAIN_MODULE, portal=portal)

    expected_service_types = {"API", "UI", "PORTAL", "PIM", "OTEL", "HTTP_SERVICE", "GRPC_SERVICE"}
    service_envs: dict[str, dict[str, str]] = {}
    for call in start_service_spy.call_args_list:
        service_type = call.args[1]
        service_process = call.args[2]
        if service_type in expected_service_types:
            service_envs[service_type] = service_process._env  # pyright: ignore[reportPrivateUsage]

    assert service_envs.keys() == expected_service_types

    for env in service_envs.values():
        assert "NO_PROXY" in env
        no_proxy_entries = {entry.strip() for entry in env["NO_PROXY"].split(",") if entry.strip()}
        assert {"localhost", "127.0.0.1", "::1"}.issubset(no_proxy_entries)
        if platform.system() == "Linux":
            assert "no_proxy" in env
            no_proxy_lower_entries = {entry.strip() for entry in env["no_proxy"].split(",") if entry.strip()}
            assert {"localhost", "127.0.0.1", "::1"}.issubset(no_proxy_lower_entries)


@pytest.mark.parametrize("enable_automatic_project_migration", [True, False], indirect=True, ids=["enable", "disable"])
@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_with_automatic_project_migration(enable_automatic_project_migration: bool):
    run_solution_stack(
        SOLUTION_MAIN_MODULE,
        enable_automatic_project_migration=enable_automatic_project_migration,
    )


@pytest.mark.parametrize("log_to_files", [True], indirect=True)
def test_run_solution_stack_log_to_files_with_otel_in_dotenv(
    log_to_files: bool,
    tmp_path: Path,
):
    (tmp_path / ".env").write_text(f"{OTEL_EXPORTER_OTLP_ENDPOINT}='something'")
    with pytest.raises(
        ValidationError,
        match="The env var 'OTEL_EXPORTER_OTLP_ENDPOINT' is defined but it is not compatible with logging to files.",
    ):
        run_solution_stack(SOLUTION_MAIN_MODULE, env_file=tmp_path / ".env", log_to_files=log_to_files)


@pytest.mark.parametrize("log_to_files", [True], indirect=True)
def test_run_solution_stack_log_to_files_with_otel_env_var(
    log_to_files: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(OTEL_EXPORTER_OTLP_ENDPOINT, "something")
    with pytest.raises(
        ValidationError,
        match="The env var 'OTEL_EXPORTER_OTLP_ENDPOINT' is defined but it is not compatible with logging to files.",
    ):
        run_solution_stack(SOLUTION_MAIN_MODULE, log_to_files=log_to_files)


@pytest.mark.parametrize("log_to_files", [True], indirect=True)
def test_run_solution_stack_log_to_files_overwrites_env_var_and_conflicts_with_otel_env_var(
    log_to_files: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(SAF_DESKTOP_LOG_TO_FILES, "False")
    monkeypatch.setenv(OTEL_EXPORTER_OTLP_ENDPOINT, "something")
    with pytest.raises(
        ValidationError,
        match="The env var 'OTEL_EXPORTER_OTLP_ENDPOINT' is defined but it is not compatible with logging to files.",
    ):
        run_solution_stack(SOLUTION_MAIN_MODULE, log_to_files=log_to_files)


@pytest.mark.usefixtures("mock_orchestrator")
@pytest.mark.parametrize("with_hps_as_pims", [True], indirect=True)
@pytest.mark.parametrize("with_pim", [True], indirect=True)
def test_run_solution_stack_with_hps_as_product_instance_system(
    mock_orchestrator: tuple[MagicMock, MagicMock, MagicMock],
    verify_user_msgs: Callable[[], str],
    verify_user_ui: Callable[[MagicMock, MagicMock, MagicMock, str], None],
):
    mock_webview_create, mock_webview_start, mock_webbrowser_open = mock_orchestrator
    run_solution_stack(SOLUTION_MAIN_MODULE)
    project_ui_url = verify_user_msgs()
    verify_user_ui(mock_webview_create, mock_webview_start, mock_webbrowser_open, project_ui_url)


@pytest.mark.usefixtures("mock_orchestrator")
def test_run_solution_stack_does_not_override_ws_events_addr_from_env_var(
    monkeypatch: pytest.MonkeyPatch,
):
    custom_addr = "ws://custom-host:9999"
    monkeypatch.setenv(GLOW_WS_EVENTS_ADDR, custom_addr)
    run_solution_stack(SOLUTION_MAIN_MODULE)
    assert (
        ServiceProcess.__init__.call_args[1]["env"][GLOW_WS_EVENTS_ADDR]  # pyright: ignore[reportFunctionMemberAccess]
        == custom_addr
    )


@pytest.mark.usefixtures("mock_orchestrator", "reset_env_after_test")
def test_run_solution_stack_does_not_override_ws_events_addr_from_dotenv(
    tmp_path: Path,
):
    custom_addr = "ws://custom-host:9999"
    env_file = tmp_path / ".env"
    env_file.write_text(f"{GLOW_WS_EVENTS_ADDR}={custom_addr}")
    run_solution_stack(SOLUTION_MAIN_MODULE, env_file=env_file)
    assert (
        ServiceProcess.__init__.call_args[1]["env"][GLOW_WS_EVENTS_ADDR]  # pyright: ignore[reportFunctionMemberAccess]
        == custom_addr
    )
