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

"""Splash screen utilities for displaying a loading window during solution startup."""

from __future__ import annotations

import base64
import logging
import multiprocessing as mp
from multiprocessing import Queue
from multiprocessing.process import BaseProcess  # noqa: TC003
from pathlib import Path
import queue
import sys
import threading
import time

import webview  # pyright: ignore[reportMissingTypeStubs]

# By default, multiprocessing uses different start methods in Linux and Windows. Force the same in both.
# More info: https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods
ctx = mp.get_context("spawn")
logger = logging.getLogger(__name__)


class SplashHandle:
    """Handle returned by start_splash, holding the process and status queue."""

    def __init__(self, process: BaseProcess, status_queue: Queue[str]) -> None:
        self._process = process
        self._status_queue = status_queue

    def update_status(self, message: str) -> None:
        """Send a status message to the splash screen.

        Parameters
        ----------
        message : str
            The status text to display in the splash log.
        """
        self._status_queue.put_nowait(message)

    def stop(self) -> None:
        """Terminate the splash screen process and its entire process tree."""
        if self._process.is_alive() and self._process.pid is not None:
            self._process.terminate()
            self._process.join(timeout=5)


class SplashScreen:
    """Manage the lifecycle of a splash screen displayed during solution startup.

    The splash screen runs in a separate daemon process and receives status
    messages via a multiprocessing queue.

    Parameters
    ----------
    solution_main_module_name : str
        Fully qualified module name of the solution, used to locate a custom
        splash image.
    """

    def __init__(self, solution_main_module_name: str) -> None:
        self._solution_main_module_name = solution_main_module_name
        self._handle: SplashHandle | None = None
        # Resolved in the parent process before spawning; pickled onto self for the child.
        self._splash_png_path: Path | None = None

    def get_splash_png_path(self) -> Path:
        default_splash_png_path = Path(__file__).parent.parent / "_assets" / "splash.png"
        # Scan sys.path directly instead of using importlib to avoid import machinery delays.
        package_rel_path = Path(*self._solution_main_module_name.split(".")[:-1])
        for entry in sys.path:
            custom_splash_png_path = Path(entry) / package_rel_path / "ui" / "assets" / "orchestrator" / "splash.png"
            if custom_splash_png_path.is_file():
                return custom_splash_png_path
        return default_splash_png_path

    @property
    def splash_png_path(self) -> Path | None:
        return self._splash_png_path

    @property
    def is_active(self) -> bool:
        """Whether the splash screen process is currently running."""
        return self._handle is not None

    def _get_splash_png_div(self) -> str:
        # Always set by start_splash() before the child process calls this.
        png_path = self._splash_png_path
        png_data = base64.b64encode(png_path.read_bytes()).decode("ascii")  # pyright: ignore[reportOptionalMemberAccess]
        return f'<img src="data:image/png;base64,{png_data}" alt="splash" />'

    def _get_splash_html(self) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
<style>
    body {{
        margin: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #1e1e2f;
        height: 100vh;
        flex-direction: column;
    }}
    .spinner {{
        margin-top: 10px;
        margin-bottom: 16px;
        width: 36px;
        height: 36px;
        border: 4px solid rgba(255,255,255,0.2);
        border-top-color: #FCB618;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }}
    @keyframes spin {{
        to {{ transform: rotate(360deg); }}
    }}
    .log-container {{
        height: 66px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        width: 80%;
        max-width: 400px;
    }}
    .log-container::-webkit-scrollbar {{
        width: 4px;
    }}
    .log-container::-webkit-scrollbar-track {{
        background: transparent;
    }}
    .log-container::-webkit-scrollbar-thumb {{
        background: rgba(255,255,255,0.2);
        border-radius: 2px;
    }}
    .log-entry {{
        color: #ffffff;
        font-family: sans-serif;
        font-size: 13px;
        opacity: 0.5;
        text-align: center;
        padding: 2px 0;
        transition: opacity 0.3s ease;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex-shrink: 0;
    }}
    .log-entry:last-child {{
        opacity: 0.9;
    }}
</style>
</head>
<body>
    {self._get_splash_png_div()}
    <div class="spinner"></div>
    <div class="log-container" id="log"></div>
</body>
</html>"""  # pyright: ignore[reportPrivateUsage]

    def _show_splash(self, status_queue: Queue[str]) -> None:
        width = 640
        height = 480
        screen = webview.screens[0]  # pyright: ignore[reportUnknownVariableType]
        window = webview.create_window(  # pyright: ignore[reportUnknownMemberType]
            "Loading...",
            html=self._get_splash_html(),
            width=width,
            height=height,
            x=(screen.width - width) // 2,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            y=(screen.height - height) // 2,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            resizable=False,
            frameless=True,
            on_top=True,
        )

        def _wait_for_log_element() -> None:
            # Wait for ~1 second for the window DOM to be ready before polling the status queue.
            # Messages that arrive before this are queued and processed immediately after.
            for _ in range(20):
                result = window.evaluate_js("document.getElementById('log') !== null")  # type: ignore
                if result:
                    break
                time.sleep(0.05)

        def _poll_status() -> None:
            _wait_for_log_element()

            while True:
                try:
                    msg = status_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                except (OSError, EOFError):
                    break
                window.evaluate_js(  # type: ignore
                    "(() => {"
                    "  const log = document.getElementById('log');"
                    "  const entry = document.createElement('div');"
                    "  entry.className = 'log-entry';"
                    f"  entry.textContent = '{msg}';"
                    "  log.appendChild(entry);"
                    "  log.scrollTop = log.scrollHeight;"
                    "})()",
                )

        threading.Thread(target=_poll_status, daemon=True).start()
        webview.start()  # pyright: ignore[reportUnknownMemberType]

    def start_splash(self) -> None:
        """Start the splash screen in a separate daemon process.

        If the splash process cannot be created or started, the exception is
        logged and suppressed.
        """
        if self.is_active:
            return
        try:
            # Resolve in the parent process; the child receives it via pickle.
            self._splash_png_path = self.get_splash_png_path()
            status_queue: Queue[str] = mp.Queue()
            process = ctx.Process(
                target=self._show_splash,
                args=(status_queue,),
                daemon=True,
            )
            process.start()
            self._handle = SplashHandle(process, status_queue)
        except Exception as e:
            logger.error(f"Failed to start splash screen: {e}")

    def update_status(self, message: str) -> None:
        """Send a status message to the splash screen.

        Parameters
        ----------
        message : str
            The status text to display in the splash log.
        """
        # This method deliberately does not raise if ``start_splash`` was never
        # called, because in pre-load mode the splash screen is not started.
        if self.is_active:
            self._handle.update_status(message)  # pyright: ignore[reportOptionalMemberAccess]

    def stop_splash(self) -> None:
        """Stop the splash screen process if it is running."""
        # This method deliberately does not raise if ``start_splash`` was never
        # called, because in pre-load mode the splash screen is not started.
        if self.is_active:
            self._handle.stop()  # pyright: ignore[reportOptionalMemberAccess]
            self._handle = None
            logger.debug("Splash screen stopped.")
