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
from io import TextIOWrapper
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any

import httpx2
import pytest
import pytest_mock
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.desktop.orchestrator._config.schema import (
    DEFAULT_SAF_DESKTOP_HEALTH_CHECK_TIMEOUT,
    HEALTH_CHECK_INTERVAL,
)
from ansys.saf.desktop.orchestrator._orchestration.pim_process import PimProcess
from ansys.saf.desktop.orchestrator._orchestration.process import ServiceProcess
from ansys.saf.desktop.orchestrator._utilities.ip_utilities import get_random_free_port
from ansys.saf.testing.platform_specific import windows_only


class TestServiceProcess:
    @pytest.fixture
    def health_check_timeout(self, request: pytest.FixtureRequest) -> int | None:
        return getattr(request, "param", None)

    @pytest.fixture
    def log_file(self, request: pytest.FixtureRequest, tmp_path: Path) -> Path | None:
        if not getattr(request, "param", False):
            return None
        return tmp_path / "service_process.log"

    @pytest.fixture
    def service_process(
        self,
        health_check_timeout: int | None,
        log_file: Path | None,
    ) -> Generator[ServiceProcess, None, None]:
        args = [
            sys.executable,
            "-m",
            "tests.integration.orchestration.simple_server",
            "--port",
            str(get_random_free_port()),
        ]

        process_args: dict[str, Any] = {}

        if health_check_timeout:
            process_args["health_check_timeout"] = health_check_timeout
        if log_file:
            process_args["log_file"] = log_file

        p = ServiceProcess(args, **process_args)
        yield p
        p.stop()

    def test_run(self, service_process: ServiceProcess):
        service_process.run()
        assert service_process.process is not None

    @pytest.mark.parametrize("log_file", [False, True], indirect=True)
    def test_run_with_log_file(
        self,
        mocker: pytest_mock.MockerFixture,
        service_process: ServiceProcess,
        log_file: Path | None,
    ):
        @retry(stop=stop_after_attempt(30), wait=wait_fixed(1))
        def _check_service_health(url: str):
            try:
                if not httpx2.get(url).status_code == 200:
                    raise TryAgain
            except Exception:
                raise TryAgain from None

        patch = mocker.spy(subprocess, "Popen")

        service_process.run()
        call_args = patch.call_args
        if log_file:
            assert isinstance(call_args.kwargs["stdout"], TextIOWrapper)
            assert isinstance(call_args.kwargs["stderr"], TextIOWrapper)
            assert call_args.kwargs["stdout"].name == call_args.kwargs["stderr"].name == str(log_file)
            assert call_args.kwargs["stdin"] == subprocess.DEVNULL
            assert isinstance(service_process._log_file_handle, TextIOWrapper)  # pyright: ignore[reportPrivateUsage]
        else:
            assert "stdout" not in call_args.kwargs
            assert "stdin" not in call_args.kwargs
            assert "stderr" not in call_args.kwargs
            assert service_process._log_file_handle is None  # pyright: ignore[reportPrivateUsage]

        service_port = call_args.kwargs["args"][-1]
        _check_service_health(f"http://127.0.0.1:{service_port}/health")
        if log_file:
            log_content = log_file.read_text()
            assert f"Uvicorn running on http://127.0.0.1:{service_port}" in log_content
            assert "GET /health HTTP/1.1" in log_content

        service_process.stop()
        if log_file:
            # file is not deleted on process stop and handle is closed
            assert log_file.is_file()
            assert service_process._log_file_handle is None  # pyright: ignore[reportPrivateUsage]

    def test_port(self, service_process: ServiceProcess):
        assert isinstance(service_process.port, int)

    def test_url(self, service_process: ServiceProcess):
        assert isinstance(service_process.url, str)

    def test_process_property(self, service_process: ServiceProcess):
        assert service_process.process is None

    def test_run_additional_args(self, service_process: ServiceProcess):
        additional_args = ["arg3", "arg4"]
        service_process.run(additional_args=additional_args)
        assert service_process.process is not None

    def test_stop_no_process(self, service_process: ServiceProcess):
        service_process.stop()
        assert service_process.process is None

    def test_port_property(self, service_process: ServiceProcess):
        assert isinstance(service_process.port, int)

    def test_url_property(self, service_process: ServiceProcess):
        assert isinstance(service_process.url, str)

    def test_run_allow_window(self, service_process: ServiceProcess):
        service_process.run(allow_window=False)
        assert service_process.process is not None

    @windows_only(reason="pythonw not available on Linux")
    @pytest.mark.parametrize("log_file", [False, True], indirect=True)
    def test_pythonw_run_subprocess_with_devnull_redirection(
        self,
        mocker: pytest_mock.MockerFixture,
        log_file: Path | None,
    ):
        patch = mocker.patch.object(sys, "executable", new="pythonw.exe")
        args = [
            "pythonw.exe",
            "-m",
            "tests.integration.orchestration.simple_server",
            "--port",
            str(0),
        ]

        service_process = ServiceProcess(args, log_file=log_file)
        patch = mocker.patch.object(subprocess, "Popen")
        service_process.run()
        patch.assert_called()
        call_args = patch.call_args
        if not log_file:
            assert call_args.kwargs["stdout"] == subprocess.DEVNULL
            assert call_args.kwargs["stdin"] == subprocess.DEVNULL
            assert call_args.kwargs["stderr"] == subprocess.DEVNULL
        else:
            assert isinstance(call_args.kwargs["stdout"], TextIOWrapper)
            assert isinstance(call_args.kwargs["stderr"], TextIOWrapper)
            assert call_args.kwargs["stdout"].name == call_args.kwargs["stderr"].name == str(log_file)
            assert call_args.kwargs["stdin"] == subprocess.DEVNULL

    @pytest.mark.parametrize(("health_check_timeout"), [None, 5], indirect=True)
    def test_infinite_process_with_custom_health_check_timeout(
        self,
        health_check_timeout: int | None,
        service_process: ServiceProcess,
        mocker: pytest_mock.MockerFixture,
    ):
        mock_health_check = mocker.patch(
            "src.ansys.saf.desktop.orchestrator._utilities.ip_utilities.httpx2.Client.get",
        )
        mock_health_check.return_value.status_code = 404

        service_process.run()

        timeout_applied = health_check_timeout or DEFAULT_SAF_DESKTOP_HEALTH_CHECK_TIMEOUT
        expected_retries = timeout_applied / HEALTH_CHECK_INTERVAL
        with pytest.raises(
            RuntimeError,
            match=re.escape(f"Error: unable to reach http://localhost:{service_process.port}/health"),
        ):
            service_process.wait_for_healthy()

        assert mock_health_check.call_count == expected_retries
        assert service_process.process is not None


@pytest.fixture
def awp_roots(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    versions = request.param
    paths: list[Path] = []
    for v in versions:
        value = tmp_path / f"v{v}"
        monkeypatch.setenv(f"AWP_ROOT{v}", str(value))
        paths.append(value)
    return paths


@pytest.fixture
def pim_exes(awp_roots: list[Path]) -> list[Path]:
    pim_exes: list[Path] = []
    for awp_root in awp_roots:
        pim_exe = awp_root / "pim" / "ansys" / "instancemanagement" / "light" / "Ansys.InstanceManagement.Light.exe"
        pim_exe.parent.mkdir(parents=True, exist_ok=True)
        pim_exe.touch()
        pim_exes.append(pim_exe)
    return pim_exes


@pytest.mark.parametrize("awp_roots", [["292"]], indirect=True)
@pytest.mark.usefixtures("cleanup_awp_root_env_vars", "awp_roots")
def test_find_unified_pim_install(pim_exes: list[Path]):
    pim_path = PimProcess.find_unified_pim_installation()
    assert len(pim_exes) == 1
    if platform.system() == "Windows":
        assert pim_path is not None
        assert pim_path.exists()
        assert pim_path == pim_exes[0]
    else:
        assert pim_path is None


@pytest.mark.usefixtures("cleanup_awp_root_env_vars")
def test_unified_pim_install_returns_none_without_awp_root():
    pim_path = PimProcess.find_unified_pim_installation()
    assert pim_path is None


@pytest.mark.parametrize("awp_roots", [["292", "301", "302"], ["261", "262", "263"]], indirect=True)
@pytest.mark.usefixtures("cleanup_awp_root_env_vars")
def test_find_unified_pim_install_latest_version_with_pim(awp_roots: list[Path], pim_exes: list[Path]):
    assert len(pim_exes) == 3
    pim_path = PimProcess.find_unified_pim_installation()
    if platform.system() == "Windows":
        assert pim_path is not None
        assert pim_path.is_relative_to(awp_roots[-1])
    else:
        assert pim_path is None


@pytest.mark.parametrize("awp_roots", [["292", "301", "302"]], indirect=True)
@pytest.mark.usefixtures("cleanup_awp_root_env_vars")
def test_find_unified_pim_install_ignores_latest_version_without_pim(
    pim_exes: list[Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    latest_awp_root = tmp_path / "v303"
    monkeypatch.setenv("AWP_ROOT303", str(latest_awp_root))
    assert len(pim_exes) == 3
    pim_path = PimProcess.find_unified_pim_installation()
    if platform.system() == "Windows":
        assert pim_path is not None
        assert not pim_path.is_relative_to(latest_awp_root)
    else:
        assert pim_path is None
