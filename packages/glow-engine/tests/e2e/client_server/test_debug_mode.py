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
from contextlib import contextmanager
import logging
from pathlib import Path
import shutil
import signal
from typing import Any, TypeVar

import pytest
from tenacity import RetryError, TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow._utilities.ip_utilities import port_is_free
from ansys.saf.glow.client import Client, NotFoundException
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.platform_specific import xfail_for_ci_on_windows
from ansys.saf.testing.solution.end_to_end import (
    ApiHotReloadConfiguration,
    BaseGlowConfiguration,
    DebugConfiguration,
    DefaultDebug,
    DisableApiHotReload,
    EnableApiHotReload,
    EnableApiHotReloadWithExplictDirectory,
    EnvVarDebug,
    EnvVarNoDebug,
    GlowBaseProcess,
    GlowDesktopProcess,
    ProjectFixture,
    UnconfigureApiHotReload,
    get_solution_root_dir,
)
from tests.e2e.conftest import EnableMCPConfiguration
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    LOGGING_DEBUG_TESTING_STRING,
)

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)

T = TypeVar("T", bound=Solution)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="class")
def debug_mode(
    session_glow: GlowBaseProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param)


@pytest.fixture(scope="class")
def debug_mode_with_debugpy(
    session_glow: GlowBaseProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param, debug_port=None)


@pytest.fixture(scope="class")
def api_hot_reload_mode(
    session_glow: GlowDesktopProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    # When Hot Reload is enabled, Uvicorn looks for changes in the files within the CWD, so we need to adjust
    # the GLOW API's CWD to the solution directory. The change will be reverted once the module finishes.
    session_glow.set_cwd(session_glow.solution_dir)
    return session_glow.change_configuration(request.param)


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    "Always exit debug and api_hot_reload modes after the module is finished."
    yield
    session_glow.configure_default_execution(restart=False)
    if isinstance(session_glow, GlowDesktopProcess):
        session_glow.set_cwd(Path.cwd())
    session_glow.restart()


@pytest.mark.parametrize(
    "debug_mode_with_debugpy",
    [
        DefaultDebug,
        EnvVarDebug,
        EnvVarNoDebug,
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestDebugModeWithDebugpy:
    def test_debug_port(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        debug_mode_with_debugpy: DebugConfiguration,
    ):
        """
        Test Debug port is opened when GLOW is running in debug mode.
        """
        if isinstance(debug_mode_with_debugpy, DefaultDebug | EnvVarNoDebug):
            assert not session_glow.debugpy_port
            return

        # GLOW is successfully using a debugpy port and it's shown in the log
        assert session_glow.debugpy_port

        # GLOW is using the expected port if configured
        # If no port is configured, GLOW will use the first free port starting from 5724
        if debug_mode_with_debugpy.debug_port:
            assert session_glow.debugpy_port == debug_mode_with_debugpy.debug_port

        # Port is busy
        assert not port_is_free(session_glow.debugpy_port)


@pytest.mark.parametrize(
    "debug_mode",
    [
        DefaultDebug,
        EnvVarDebug,
        EnvVarNoDebug,
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestDebugMode:
    def test_log_debug_message(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
        debug_mode: DebugConfiguration,
    ):
        """
        Test loglevel is lowered to DEBUG when GLOW is running in debug mode.
        """
        step = function_project.project.steps.transaction_verification_step
        step.log_some_debug()

        # WHEN: Processing log file for API server
        if not isinstance(debug_mode, DefaultDebug | EnvVarNoDebug):
            assert session_glow.text_in_output(LOGGING_DEBUG_TESTING_STRING)
        else:
            assert not session_glow.text_in_output(LOGGING_DEBUG_TESTING_STRING)

    def test_normal_debug_api_log_content(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
        debug_mode: DebugConfiguration,
    ):
        """
        Test that expected debug-relate log entries are present in debug mode.
        """
        # do something that we know it triggers a debug message
        function_project.project.steps.transaction_verification_step.field_1 = 3
        normal_debug_content = "Invalidating descendant fields..."

        if not isinstance(debug_mode, DefaultDebug | EnvVarNoDebug):
            assert session_glow.text_in_output(normal_debug_content)
        else:
            assert not session_glow.text_in_output(normal_debug_content)

    def test_stack_trace_only_on_debug(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        debug_mode: DebugConfiguration,
        function_client: Client[EndToEndSolution],
    ):
        """
        Test stack traces are only shown on debug mode.
        """
        # GIVEN: Doing an erroneous request to the API server
        project = function_client.get_project("fake_project_id")
        with pytest.raises(NotFoundException):
            project.steps.transaction_verification_step.field_1 = 2

        # THEN: Traceback only appears in the log if DEBUG is enabled
        normal_debug_content = "Traceback"
        if not isinstance(debug_mode, DefaultDebug | EnvVarNoDebug):
            assert session_glow.text_in_output(normal_debug_content)
        else:
            assert not session_glow.text_in_output(normal_debug_content)


def backup_code(source_file: Path, code: str, tmp_path: Path) -> YieldFixture[None]:
    assert source_file.is_file()
    assert code in source_file.read_text()
    source_file_backup = tmp_path / source_file.with_suffix(".backup").name
    shutil.copyfile(source_file, source_file_backup)

    yield

    if source_file_backup.is_file():
        shutil.copyfile(source_file_backup, source_file)


@pytest.fixture
def backup_transaction_step(
    session_glow: GlowDesktopProcess[EndToEndSolution],
    tmp_path: Path,
) -> YieldFixture[None]:
    transaction_step_file = session_glow.solution_dir / "solution" / "transaction_verification_step.py"
    code = "def copy_field_1_to_field_2(self) -> None:\n        self.field_2 = self.field_1"
    yield from backup_code(transaction_step_file, code, tmp_path)


@pytest.fixture
def backup_ui_page(
    session_glow: GlowDesktopProcess[EndToEndSolution],
    tmp_path: Path,
) -> YieldFixture[None]:
    page_file = session_glow.solution_dir / "ui" / "first_page.py"
    code = "We are in First Page"
    yield from backup_code(page_file, code, tmp_path)


def modify_solution_api_code(session_glow: GlowBaseProcess[EndToEndSolution]) -> None:
    # modify solution source code to add +5 to every sum
    transaction_step_file = session_glow.solution_dir / "solution" / "transaction_verification_step.py"
    assert transaction_step_file.is_file()
    transaction_step_file.write_text(
        transaction_step_file.read_text().replace(
            "def copy_field_1_to_field_2(self) -> None:\n        self.field_2 = self.field_1",
            "def copy_field_1_to_field_2(self) -> None:\n        self.field_2 = 5 + self.field_1",
        ),
    )


def modify_solution_ui_code(session_glow: GlowBaseProcess[EndToEndSolution]) -> None:
    # modify solution UI source code
    ui_file = session_glow.solution_dir / "ui" / "first_page.py"
    assert ui_file.is_file()
    ui_file.write_text(
        ui_file.read_text().replace(
            "We are in First Page",
            "We are in Very First Page",
        ),
    )


@retry(stop=stop_after_attempt(60), wait=wait_fixed(1))
def uvicorn_detects_change(session_glow: GlowBaseProcess[EndToEndSolution], file_name: str) -> int:
    reload_log_msg_idx: int | None = None
    for idx, line in enumerate(session_glow.api_output):
        if "detected changes in" in line and file_name in line:
            reload_log_msg_idx = idx
            break
    if reload_log_msg_idx is None:
        raise TryAgain
    return reload_log_msg_idx


@retry(stop=stop_after_attempt(240), wait=wait_fixed(1))
def uvicorn_reloads(session_glow: GlowBaseProcess[EndToEndSolution], reload_log_msg_idx: int) -> bool:
    # This message appears multiple times, we only care if it appears after the statreload message
    api_server_launched: bool = False
    for line in session_glow.api_output[reload_log_msg_idx:]:
        if "Application startup complete." in line:
            api_server_launched = True
            break
    if not api_server_launched:
        raise TryAgain
    return True


@contextmanager
def suppress_signal(signal_to_supress: signal.Signals) -> Generator[None, None, None]:
    original_handler: Any | None = None
    try:
        original_handler = signal.getsignal(signal_to_supress)
        signal.signal(signal_to_supress, signal.SIG_IGN)
        yield
    finally:
        if original_handler is not None:
            signal.signal(signal_to_supress, original_handler)


@xfail_for_ci_on_windows(reason="TODO: Enable E2E Hot API reload test in Windows for CI.")
@pytest.mark.parametrize(
    ("debug_mode", "api_hot_reload_mode"),
    [
        (EnvVarDebug, EnableApiHotReload),
        (EnvVarDebug, DisableApiHotReload),
        (EnvVarDebug, UnconfigureApiHotReload),
        (EnvVarNoDebug, EnableApiHotReload),
    ],
    indirect=True,
)
@pytest.mark.parametrize("deployment_type", ["Desktop"], indirect=True)
class TestApiHotReloadMode:
    @pytest.mark.usefixtures("backup_transaction_step")
    def test_api_hot_reload_enabled(
        self,
        debug_mode: DebugConfiguration,
        api_hot_reload_mode: ApiHotReloadConfiguration,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that API hot reload is only enabled when debug and api_hot_reload are properly configured. When enabled,
        changes in the definition (e.g., step fields, transactions) should be reflected without manually restarting
        the API server.
        """

        # When uvicorn reloads it also sends a KeyboardInterrupt signal that is reraised from the subprocess to the
        # pytest process and kills the pytest session. We use this contextmanager to suppress the signal temporarily.
        # See: https://github.com/encode/uvicorn/issues/2294 and https://github.com/fastapi/fastapi/discussions/11617
        with suppress_signal(signal.SIGINT):
            modify_solution_api_code(session_glow)

            if isinstance(debug_mode, EnvVarNoDebug) or isinstance(api_hot_reload_mode, DisableApiHotReload):
                with pytest.raises(RetryError):
                    uvicorn_detects_change(session_glow, "transaction_verification_step.py")
            else:
                # Uvicorn detects the change and restarts the service
                reload_log_msg_idx = uvicorn_detects_change(session_glow, "transaction_verification_step.py")
                assert reload_log_msg_idx
                assert uvicorn_reloads(session_glow, reload_log_msg_idx)

        # Call transaction and verify that it's adding +5 to every result if API hot reload is enabled, otherwise 0
        assert function_project.project.steps.transaction_verification_step.field_1 == 0
        assert function_project.project.steps.transaction_verification_step.field_2 == 0
        function_project.project.steps.transaction_verification_step.copy_field_1_to_field_2()
        expected_result = (
            0 if isinstance(debug_mode, EnvVarNoDebug) or isinstance(api_hot_reload_mode, DisableApiHotReload) else 5
        )
        assert function_project.project.steps.transaction_verification_step.field_2 == expected_result

    @pytest.mark.usefixtures("backup_ui_page")
    def test_api_hot_reload_not_triggered_by_changes_in_ui_files(
        self,
        debug_mode: DebugConfiguration,
        api_hot_reload_mode: ApiHotReloadConfiguration,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that API hot reload is not triggered by changes in the UI no matter what the debug mode is.
        """

        # When uvicorn reloads it also sends a KeyboardInterrupt signal that is reraised from the subprocess to the
        # pytest process and kills the pytest session. We use this contextmanager to suppress the signal temporarily.
        # See: https://github.com/encode/uvicorn/issues/2294 and https://github.com/fastapi/fastapi/discussions/11617
        with suppress_signal(signal.SIGINT):
            modify_solution_ui_code(session_glow)

            with pytest.raises(RetryError):
                uvicorn_detects_change(session_glow, "first_page.py")


@pytest.fixture
def debug_mode_plus_hot_reload_plus_whole_solution_reload_directory(
    session_glow: GlowBaseProcess[EndToEndSolution],
    tmp_solutions_dir: dict[type[T], Path],
) -> BaseGlowConfiguration:
    solution_src_dir = get_solution_root_dir(tmp_solutions_dir[EndToEndSolution]) / "src"  # type: ignore
    session_glow.change_configuration(EnvVarDebug, restart=False)
    return session_glow.change_configuration(
        EnableApiHotReloadWithExplictDirectory,
        hot_reload_monitoring_dir=solution_src_dir,
    )  # type: ignore


def test_glow_api_hot_reload_monitoring_dir(
    session_glow: GlowBaseProcess[EndToEndSolution],
    debug_mode_plus_hot_reload_plus_whole_solution_reload_directory: BaseGlowConfiguration,
):
    """
    Test that API hot reload is triggered by changes in files within the directory referenced by
    GLOW_API_HOT_RELOAD_MONITORING_DIR.
    """

    # When uvicorn reloads it also sends a KeyboardInterrupt signal that is reraised from the subprocess to the
    # pytest process and kills the pytest session. We use this contextmanager to suppress the signal temporarily.
    # See: https://github.com/encode/uvicorn/issues/2294 and https://github.com/fastapi/fastapi/discussions/11617
    with suppress_signal(signal.SIGINT):
        modify_solution_ui_code(session_glow)

        assert uvicorn_detects_change(session_glow, "first_page.py")


@pytest.fixture
def debug_mode_plus_hot_reload_plus_mcp_server(session_glow: GlowBaseProcess[EndToEndSolution]) -> None:
    session_glow.change_configuration(EnvVarDebug, restart=False)
    session_glow.change_configuration(EnableApiHotReload, restart=False)
    session_glow.change_configuration(EnableMCPConfiguration)


@xfail_for_ci_on_windows(reason="TODO: Enable E2E Hot API reload test in Windows for CI.")
@pytest.mark.usefixtures("debug_mode_plus_hot_reload_plus_mcp_server", "backup_transaction_step")
def test_glow_api_hot_reload_when_mcp_enabled(session_glow: GlowBaseProcess[EndToEndSolution]):
    """
    Test that API hot reload is triggered and relaunches entire app including MCP routes.
    """

    # When uvicorn reloads it also sends a KeyboardInterrupt signal that is reraised from the subprocess to the
    # pytest process and kills the pytest session. We use this contextmanager to suppress the signal temporarily.
    # See: https://github.com/encode/uvicorn/issues/2294 and https://github.com/fastapi/fastapi/discussions/11617
    with suppress_signal(signal.SIGINT):
        modify_solution_api_code(session_glow)

        reload_log_msg_idx = uvicorn_detects_change(session_glow, "transaction_verification_step.py")
        assert reload_log_msg_idx
        assert any("MCP mounted at path /sse" in line for line in session_glow.api_output[:reload_log_msg_idx])
        assert uvicorn_reloads(session_glow, reload_log_msg_idx)
        assert any("MCP mounted at path /sse" in line for line in session_glow.api_output[reload_log_msg_idx:])
