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

from collections.abc import Callable, Generator
import errno
from pathlib import Path
import socket
import time

import httpx2
import psutil
import pytest

from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DebugConfiguration,
    EnvVarDebug,
    EnvVarLoggingToFileConfig,
    GlowBaseProcess,
    ProjectFixture,
)
from tests.mocks.solutions.transactions import TransactionsSolution, TransactionStep

pytestmark = pytest.mark.parametrize("solution_type", [TransactionsSolution], indirect=True)


@pytest.fixture(scope="class")
def enable_debug_and_log_to_file(session_glow: GlowBaseProcess[TransactionsSolution]) -> Generator[None, None, None]:
    # Log to file so we can easily separate api logs and method logs.
    session_glow.change_configuration(EnvVarDebug, restart=False)
    session_glow.change_configuration(EnvVarLoggingToFileConfig)
    yield
    session_glow.configure_default_execution()


@pytest.mark.parametrize("long_running", [True, False])
@pytest.mark.usefixtures("enable_debug_and_log_to_file")
class TestMethodLogging:
    def test_method_logs_are_written_to_the_expected_location(
        self,
        function_project: ProjectFixture[TransactionsSolution],
        long_running: bool,
        get_api_log_file_content: Callable[[str], str],
        get_method_log_file_content: Callable[[str, str], str],
    ):
        # GIVEN - step with method that logs information
        step = function_project.project.steps.transaction_step

        # WHEN - executing the logging method
        if not long_running:
            step.log_information()
            log_file_content = get_api_log_file_content("TransactionsSolution")
        else:
            step.log_long_running_information().wait()
            log_file_content = get_method_log_file_content("TransactionsSolution", "log_long_running_information")

        # THEN - the log file contains the information logged by the method
        assert TransactionStep.INFORMATION_LOGGED_BY_LOG_METHOD in log_file_content

        # AND - the log file contains sensible trace ids (hoping its from the GLOW server)
        assert "[trace_id=0 span_id=0 resource.service.name=method] " not in log_file_content

    def test_method_exceptions_are_written_to_the_expected_location(
        self,
        function_project: ProjectFixture[TransactionsSolution],
        long_running: bool,
        get_api_log_file_content: Callable[[str], str],
        get_method_log_file_content: Callable[[str, str], str],
    ):
        # GIVEN - step with method that logs information
        step = function_project.project.steps.transaction_step

        # WHEN - executing a method that raises an exception and handling the exception
        exception_string = "Oops, something went wrong"
        if not long_running:
            with pytest.raises(InternalSolutionException, match=exception_string):
                step.raise_exception()
            log_file_content = get_api_log_file_content("TransactionsSolution")
        else:
            with pytest.raises(InternalSolutionException, match=exception_string):
                step.raise_exception_lr().wait()
            log_file_content = get_method_log_file_content(
                "TransactionsSolution",
                "raise_exception_lr",
            )

        # THEN - the exception is recorded in the log as an error
        assert any("ERROR" in line and exception_string in line for line in log_file_content.splitlines())

    def test_method_uploads_and_downloads_are_logged(
        self,
        function_project: ProjectFixture[TransactionsSolution],
        long_running: bool,
        get_api_log_file_content: Callable[[str], str],
        get_method_log_file_content: Callable[[str, str], str],
    ):
        # GIVEN - step with method that uploads and downloads fields
        step = function_project.project.steps.transaction_step

        # WHEN - executing the method
        if not long_running:
            step.download_x_upload_y()
            log_file_content = get_api_log_file_content("TransactionsSolution")
        else:
            step.long_running_download_x_upload_y().wait()
            log_file_content = get_method_log_file_content("TransactionsSolution", "long_running_download_x_upload_y")

        # THEN - the log contains information on the fields transferred by the method
        assert "Downloading x" in log_file_content
        assert "Uploading y" in log_file_content

    def test_long_running_methods_have_different_log_files(
        self,
        mock_appdata: Path,
        function_project: ProjectFixture[TransactionsSolution],
        long_running: bool,
    ):
        """
        Test that long running methods log to different files.
        """
        if not long_running:
            pytest.skip(reason="Test specifically designed for long_running transactions.")

        # GIVEN - no existing method logs
        method_logs_directory = (
            mock_appdata / "ansys" / "glow" / "TransactionsSolution" / "logs" / "long_running_methods"
        )
        for log_file in method_logs_directory.iterdir():
            log_file.unlink()

        # WHEN - running a couple of long running transactions
        step = function_project.project.steps.transaction_step
        step.long_running_download_x_upload_y().wait()
        step.long_running_download_x_upload_y().wait()

        # THEN - They have used different files for logging
        assert (
            len(
                [
                    log_file
                    for log_file in method_logs_directory.iterdir()
                    if log_file.name.startswith("log_long_running_download_x_upload_y")
                ],
            )
            == 2
        )


def _check_port_is_used(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            return True
        else:
            raise e
    finally:
        s.close()
    return False


def _find_debugpy_proc(port: int):
    # In linux, debupgy proc does NOT appear as a child proc of the GLOW API proc.
    # To avoid different implementations depending on the OS, we just
    # iterate the entire list of procs.
    for proc in psutil.process_iter():  # type: ignore
        try:
            proc_cmd = " ".join(proc.cmdline())
        except (psutil.ZombieProcess, psutil.AccessDenied, psutil.NoSuchProcess):
            continue
        if "debugpy" in proc_cmd and f"--port {port}" in proc_cmd:
            return proc


def wait_for_long_running_method_status(method_url: str, expected_method_status: str = "completed") -> bool:
    method_status = ""
    num_tries = 0
    while method_status != expected_method_status and num_tries < 10:
        method_status = httpx2.get(method_url).json()["status"]
        num_tries += 1
        time.sleep(1)
    return method_status == expected_method_status


@pytest.fixture(scope="class")
def debug_mode(session_glow: GlowBaseProcess[TransactionsSolution]) -> Generator[BaseGlowConfiguration, None, None]:
    debug_config = session_glow.change_configuration(EnvVarDebug, debug_port=None)  # None, since we want debugpy to run
    yield debug_config
    session_glow.configure_default_execution()


@pytest.mark.usefixtures("debug_mode")
class TestDebugpy:
    def test_debugpy_still_on_after_transaction(
        self,
        debug_mode: DebugConfiguration,
        function_project: ProjectFixture[TransactionsSolution],
    ):
        """
        Test debugpy works after calling a transaction
        """
        port = debug_mode.debug_port
        assert port

        # GIVEN - glow proc with debug enabled and debugpy port being in use
        assert _check_port_is_used(port)
        assert _find_debugpy_proc(port)

        # WHEN - running a transaction that finishes
        function_project.project.steps.transaction_step.download_x_upload_y()

        # THEN: debugpy port is still in use
        assert _check_port_is_used(port)
        assert _find_debugpy_proc(port)

    def test_debugpy_still_on_after_long_running_transaction(
        self,
        debug_mode: DebugConfiguration,
        function_project: ProjectFixture[TransactionsSolution],
    ):
        """
        Test debugpy works after calling a long_running transaction
        """
        port = debug_mode.debug_port
        assert port

        # GIVEN - glow proc with debug enabled and debugpy port being in use
        assert _check_port_is_used(port)
        assert _find_debugpy_proc(port)

        # WHEN - running a long running transaction that finishes
        function_project.project.steps.transaction_step.long_running_download_x_upload_y().wait()

        # THEN: debugpy port is still in use
        assert _check_port_is_used(port)
        assert _find_debugpy_proc(port)

    def test_debugpy_terminated_after_glow(
        self,
        debug_mode: DebugConfiguration,
        session_glow: GlowBaseProcess[TransactionsSolution],
    ):
        """
        Test debugpy proc is terminated by GLOW
        """
        port = debug_mode.debug_port
        assert port

        # GIVEN - glow proc with debug enabled and debugpy port being in use
        assert _check_port_is_used(port)
        assert _find_debugpy_proc(port)

        # WHEN - closing GLOW
        session_glow.stop()

        # THEN - debugpy proc is terminated
        # it may take some time to shutdown
        num_tries = 0
        port_in_use = True
        while num_tries < 10:
            port_in_use = _check_port_is_used(port)
            num_tries += 1
            time.sleep(1)
        assert not port_in_use
        assert not _find_debugpy_proc(port)

        # leave as it was
        session_glow.start()
