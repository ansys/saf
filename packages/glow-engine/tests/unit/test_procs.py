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
import contextlib
import signal
import subprocess
import sys

import psutil
import pytest
import pytest_mock

from ansys.saf.glow._utilities.procs import kill_pids
from ansys.saf.testing.platform_specific import linux_only

_SLEEPER_SCRIPT = "import time; time.sleep(30)"


@pytest.fixture
def spawn_proc() -> Generator[Callable[[str], subprocess.Popen[bytes]], None, None]:
    procs: list[subprocess.Popen[bytes]] = []

    def _spawn(script: str) -> subprocess.Popen[bytes]:
        p = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE)
        procs.append(p)
        return p

    yield _spawn

    for p in procs:
        with contextlib.suppress(psutil.NoSuchProcess):
            psutil.Process(p.pid).kill()
        p.wait(timeout=5)


def test_empty_pid_list():
    gone, alive = kill_pids([])

    assert gone == []
    assert alive == []


def test_single_proc_terminated(
    spawn_proc: Callable[[str], subprocess.Popen[bytes]],
    mocker: pytest_mock.MockerFixture,
):
    mock_logger = mocker.patch("ansys.saf.glow._utilities.procs.logger")

    proc = spawn_proc(_SLEEPER_SCRIPT)
    gone, alive = kill_pids([proc.pid])

    assert proc.pid in [p.pid for p in gone]
    assert alive == []
    mock_logger.debug.assert_called_with(f"Killing child process (pid: {proc.pid})")


def test_multiple_procs_terminated(
    spawn_proc: Callable[[str], subprocess.Popen[bytes]],
    mocker: pytest_mock.MockerFixture,
):
    mock_logger = mocker.patch("ansys.saf.glow._utilities.procs.logger")

    procs = [spawn_proc(_SLEEPER_SCRIPT) for _ in range(3)]

    pids = [p.pid for p in procs]
    gone, alive = kill_pids(pids)

    gone_pids = [p.pid for p in gone]
    for pid in pids:
        assert pid in gone_pids
    assert alive == []
    for pid in pids:
        mock_logger.debug.assert_any_call(f"Killing child process (pid: {pid})")


def test_already_dead_proc(spawn_proc: Callable[[str], subprocess.Popen[bytes]], mocker: pytest_mock.MockerFixture):
    mock_logger = mocker.patch("ansys.saf.glow._utilities.procs.logger")

    proc = spawn_proc(_SLEEPER_SCRIPT)
    proc.terminate()
    proc.wait(timeout=2)

    gone, alive = kill_pids([proc.pid])

    assert gone == []
    assert alive == []
    mock_logger.debug.assert_not_called()


def test_mix_of_valid_and_already_dead_pids(
    spawn_proc: Callable[[str], subprocess.Popen[bytes]],
    mocker: pytest_mock.MockerFixture,
):
    mock_logger = mocker.patch("ansys.saf.glow._utilities.procs.logger")

    procs = [spawn_proc(_SLEEPER_SCRIPT) for _ in range(2)]
    proc_to_terminate = procs[0]
    proc_to_terminate.terminate()
    proc_to_terminate.wait(timeout=2)

    gone, alive = kill_pids([p.pid for p in procs])

    assert [procs[1].pid] == [p.pid for p in gone]
    assert alive == []
    mock_logger.debug.assert_called_with(f"Killing child process (pid: {procs[1].pid})")


def test_access_denied_logs_warning_and_skips_process(
    spawn_proc: Callable[[str], subprocess.Popen[bytes]],
    mocker: pytest_mock.MockerFixture,
):
    proc = spawn_proc(_SLEEPER_SCRIPT)

    mock_process_cls = mocker.patch("ansys.saf.glow._utilities.procs.psutil.Process")
    mock_proc = mock_process_cls.return_value
    mock_proc.pid = proc.pid
    mock_proc.send_signal.side_effect = psutil.AccessDenied(pid=proc.pid)

    mock_wait = mocker.patch("ansys.saf.glow._utilities.procs.psutil.wait_procs", return_value=([], []))

    mock_logger = mocker.patch("ansys.saf.glow._utilities.procs.logger")

    kill_pids([proc.pid])

    mock_wait.assert_called_once_with([], timeout=10.0)
    mock_logger.warning.assert_called_once_with("Access denied when trying to kill process %d", proc.pid)
    mock_logger.debug.assert_called_once_with(f"Killing child process (pid: {proc.pid})")


def test_timeout_configurable(
    spawn_proc: Callable[[str], subprocess.Popen[bytes]],
    mocker: pytest_mock.MockerFixture,
):
    spy_wait = mocker.spy(psutil, "wait_procs")
    mock_logger = mocker.patch("ansys.saf.glow._utilities.procs.logger")

    first_proc = spawn_proc(_SLEEPER_SCRIPT)
    kill_pids([first_proc.pid])
    spy_wait.assert_called_once()
    assert spy_wait.call_args.kwargs["timeout"] == 10.0
    mock_logger.debug.assert_called_with(f"Killing child process (pid: {first_proc.pid})")

    spy_wait.reset_mock()
    mock_logger.reset_mock()
    second_proc = spawn_proc(_SLEEPER_SCRIPT)
    kill_pids([second_proc.pid], timeout=5.0)
    spy_wait.assert_called_once()
    assert spy_wait.call_args.kwargs["timeout"] == 5.0
    mock_logger.debug.assert_called_with(f"Killing child process (pid: {second_proc.pid})")


@linux_only()
def test_signal_configurable(
    spawn_proc: Callable[[str], subprocess.Popen[bytes]],
    mocker: pytest_mock.MockerFixture,
):
    spy_send_signal = mocker.spy(psutil.Process, "send_signal")
    mock_logger = mocker.patch("ansys.saf.glow._utilities.procs.logger")

    first_proc = spawn_proc(_SLEEPER_SCRIPT)
    kill_pids([first_proc.pid])
    assert any(call.args[1] == signal.SIGTERM for call in spy_send_signal.call_args_list)
    mock_logger.debug.assert_called_with(f"Killing child process (pid: {first_proc.pid})")

    spy_send_signal.reset_mock()
    mock_logger.reset_mock()
    second_proc = spawn_proc(_SLEEPER_SCRIPT)
    kill_pids([second_proc.pid], sig=signal.SIGKILL)  # type: ignore
    assert any(call.args[1] == signal.SIGKILL for call in spy_send_signal.call_args_list)  # type: ignore
    mock_logger.debug.assert_called_with(f"Killing child process (pid: {second_proc.pid})")


@linux_only()
def test_proc_still_alive_when_signal_is_caught(
    spawn_proc: Callable[[str], subprocess.Popen[bytes]],
    mocker: pytest_mock.MockerFixture,
):
    mock_logger = mocker.patch("ansys.saf.glow._utilities.procs.logger")

    proc = spawn_proc(
        "import signal, sys, time; signal.signal(signal.SIGUSR1, lambda *_: None); "
        "sys.stdout.write('ready\\n'); sys.stdout.flush(); time.sleep(30)",
    )
    assert proc.stdout
    proc.stdout.readline()  # wait until the signal handler is installed
    gone, alive = kill_pids([proc.pid], sig=signal.SIGUSR1, timeout=0.5)  # type: ignore

    assert gone == []
    assert proc.pid in [p.pid for p in alive]
    mock_logger.debug.assert_called_with(f"Killing child process (pid: {proc.pid})")
