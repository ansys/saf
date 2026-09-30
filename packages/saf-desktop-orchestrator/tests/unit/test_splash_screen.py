# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Generator
import multiprocessing
from pathlib import Path
import platform
import time
from typing import cast
from unittest.mock import Mock

import pytest
import webview  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.desktop.orchestrator._utilities.splash_screen import SplashHandle, SplashScreen


class TestSplashHandle:
    def test_update_status(self):
        """Test that update_status sends a message to the status queue."""
        status_queue: multiprocessing.Queue[str] = multiprocessing.Queue()
        process: multiprocessing.Process = cast("multiprocessing.Process", multiprocessing.current_process())
        handle = SplashHandle(process, status_queue)
        handle.update_status("Test message")
        assert status_queue.get(timeout=1) == "Test message"

    def test_stop(self):
        """Test that stop terminates the process."""
        process = multiprocessing.get_context("spawn").Process(target=time.sleep, args=(10,))
        process.start()
        handle = SplashHandle(process, multiprocessing.Queue())
        handle.stop()
        assert not process.is_alive()


@pytest.fixture
def custom_splash_png(tmp_path: Path) -> Path:
    """Create a custom splash PNG file in tmp_path and return its path."""
    custom_png_path = tmp_path / "ui" / "assets" / "orchestrator" / "splash.png"
    custom_png_path.parent.mkdir(parents=True)
    custom_png_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header
    return custom_png_path


@pytest.fixture
def mock_sys_path_with_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Add tmp_path to sys.path and create a fake module file there."""
    (tmp_path / "dummy_solution_main_module.py").write_text("# fake module")
    monkeypatch.syspath_prepend(str(tmp_path))  # pyright: ignore[reportUnknownMemberType]


@pytest.fixture
def splash_screen() -> Generator[SplashScreen, None, None]:
    """SplashScreen instance — module not on sys.path, so the default image is used."""
    splash_screen = SplashScreen("dummy_solution_main_module")
    yield splash_screen
    splash_screen.stop_splash()


@pytest.fixture
def splash_screen_custom_logo(
    mock_sys_path_with_module: None,
    custom_splash_png: Path,
) -> Generator[SplashScreen, None, None]:
    """SplashScreen instance with a custom splash image reachable via sys.path."""
    splash_screen = SplashScreen("dummy_solution_main_module")
    yield splash_screen
    splash_screen.stop_splash()


class TestSplashScreenWorkflow:
    def test_splash_screen_start_and_stop(self, splash_screen: SplashScreen):
        """
        Test that the splash screen starts and stops correctly when running a solution with a UI.
        """
        assert not splash_screen.is_active
        splash_screen.start_splash()
        assert splash_screen.is_active
        process = splash_screen._handle._process  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]
        assert process.is_alive()
        splash_screen.stop_splash()
        assert not splash_screen.is_active
        assert not process.is_alive()

    def test_splash_screen_start_multiple_times(self, splash_screen: SplashScreen):
        """
        Test that calling start_splash multiple times does not create multiple splash processes.
        """
        assert not splash_screen.is_active
        splash_screen.start_splash()
        assert splash_screen.is_active
        first_process = splash_screen._handle._process  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]
        splash_screen.start_splash()  # Should not start a new process
        assert splash_screen.is_active
        second_process = splash_screen._handle._process  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]
        assert first_process.pid == second_process.pid
        splash_screen.stop_splash()

    def test_splash_screen_update_status_without_start(self, splash_screen: SplashScreen):
        """
        Test that calling update_status without starting the splash screen does not raise an error.
        """
        assert not splash_screen.is_active
        splash_screen.update_status("Test status message")

    def test_splash_screen_update_status_with_start(self, splash_screen: SplashScreen):
        """
        Test that calling update_status sends a message to the splash screen when it is started.
        """
        splash_screen.start_splash()
        assert splash_screen.is_active
        status_queue = splash_screen._handle._status_queue  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]
        splash_screen.update_status("Test status message")
        assert status_queue.get(timeout=1) == "Test status message"
        splash_screen.stop_splash()

    def test_splash_screen_update_status_multiple_updates(self, splash_screen: SplashScreen):
        """
        Test that multiple calls to update_status send messages to the splash screen when it is started.
        """
        splash_screen.start_splash()
        assert splash_screen.is_active
        status_queue = splash_screen._handle._status_queue  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]
        messages = ["Status message 1", "Status message 2", "Status message 3"]
        for msg in messages:
            splash_screen.update_status(msg)
        for msg in messages:
            assert status_queue.get(timeout=1) == msg
        splash_screen.stop_splash()

    def test_splash_screen_stop_without_start(self, splash_screen: SplashScreen):
        """
        Test that calling stop_splash without starting the splash screen does not raise an error.
        """
        splash_screen.stop_splash()

    def test_splash_screen_multiple_stops(self, splash_screen: SplashScreen):
        """
        Test that calling stop_splash multiple times does not raise an error.
        """
        splash_screen.start_splash()
        splash_screen.stop_splash()
        splash_screen.stop_splash()

    def test_splash_screen_start_failure(
        self,
        splash_screen: SplashScreen,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        Test that start_splash handles exceptions when starting the splash screen process.
        """
        mock_logger = Mock()
        monkeypatch.setattr(
            "ansys.saf.desktop.orchestrator._utilities.splash_screen.logger",
            mock_logger,
        )

        def mock_process_start(self: multiprocessing.Process) -> None:
            raise RuntimeError("Mocked process start failure")

        monkeypatch.setattr(
            "ansys.saf.desktop.orchestrator._utilities.splash_screen.ctx.Process.start",
            mock_process_start,
        )

        splash_screen.start_splash()

        assert splash_screen._handle is None  # pyright: ignore[reportPrivateUsage]
        mock_logger.error.assert_called_once_with("Failed to start splash screen: Mocked process start failure")


class TestSplashScreenContent:
    """Integration tests verifying the rendered DOM content of the splash window."""

    def test_splash_contains_default_png_image(self, splash_screen: SplashScreen):
        """Test that the splash window contains an img element with a base64-encoded PNG source."""
        expected_png_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "ansys"
            / "saf"
            / "desktop"
            / "orchestrator"
            / "_assets"
            / "splash.png"
        )
        assert splash_screen.get_splash_png_path() == expected_png_path

    def test_splash_contains_custom_png_image(
        self,
        splash_screen_custom_logo: SplashScreen,
        custom_splash_png: Path,
    ):
        """Test that the splash window contains a custom PNG image if available."""
        assert splash_screen_custom_logo.get_splash_png_path() == custom_splash_png

    def test_splash_png_path_default_when_module_found_but_no_custom_splash(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """Test that the default image is returned when the module exists on sys.path but has no custom splash."""
        (tmp_path / "dummy_solution_main_module.py").write_text("# fake module")
        monkeypatch.syspath_prepend(str(tmp_path))  # pyright: ignore[reportUnknownMemberType]
        splash_screen = SplashScreen("dummy_solution_main_module")
        default_splash_png_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "ansys"
            / "saf"
            / "desktop"
            / "orchestrator"
            / "_assets"
            / "splash.png"
        )
        assert splash_screen.get_splash_png_path() == default_splash_png_path

    def test_resolved_path_set_after_start_splash(self, splash_screen: SplashScreen):
        """Test that _splash_png_path is populated by start_splash before the child process runs."""
        assert splash_screen._splash_png_path is None  # pyright: ignore[reportPrivateUsage]
        splash_screen.start_splash()
        assert splash_screen._splash_png_path is not None  # pyright: ignore[reportPrivateUsage]
        assert splash_screen._splash_png_path.is_file()  # pyright: ignore[reportPrivateUsage]
        splash_screen.stop_splash()

    @pytest.mark.skipif(platform.system() == "Linux", reason="webview disabled temporarily on Linux")
    def test_splash_elements(self, splash_screen: SplashScreen):
        """Test that the splash window renders an img element with a base64 PNG source."""
        splash_screen._splash_png_path = splash_screen.get_splash_png_path()  # pyright: ignore[reportPrivateUsage]
        results: dict[str, object] = {}

        window = webview.create_window(  # pyright: ignore[reportUnknownMemberType]
            "Test",
            html=splash_screen._get_splash_html(),  # pyright: ignore[reportPrivateUsage]
            width=640,
            height=480,
            hidden=True,
        )

        def _inspect() -> None:
            time.sleep(1)
            results["img_src"] = window.evaluate_js(  # type: ignore
                "document.querySelector('img') ? document.querySelector('img').getAttribute('src') : null",
            )
            results["log_exists"] = window.evaluate_js(  # type: ignore
                "document.getElementById('log') !== null",
            )
            results["spinner_exists"] = window.evaluate_js(  # type: ignore
                "document.querySelector('.spinner') !== null",
            )
            window.destroy()  # type: ignore

        webview.start(_inspect)  # type: ignore

        assert isinstance(results["img_src"], str)
        assert results["img_src"].startswith("data:image/png;base64,")
        assert results["log_exists"] is True
        assert results["spinner_exists"] is True
