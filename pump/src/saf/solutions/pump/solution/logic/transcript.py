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

"""Capture of the Fluent console transcript for display in the UI."""

from collections import deque
from collections.abc import Callable
from types import TracebackType
import threading
from typing import Any

from saf.solutions.pump.solution.logic.constants import (
    LOG_FLUSH_INTERVAL_SECONDS,
    LOG_TAIL_LINES,
)

LogCallback = Callable[[list[str]], None]
"""Called with the transcript lines produced since the previous call."""


class TranscriptForwarder:
    """Collect Fluent transcript lines and publish them in batches.

    PyFluent delivers the transcript on a background streaming thread, one callback per
    console line. Publishing each line individually would mean one HTTP request per line,
    so lines are buffered and flushed on a timer instead.

    The forwarder also keeps the tail of the transcript, which the step persists so that the
    log survives a page reload.

    Parameters
    ----------
    emit : LogCallback or None
        Called with each batch of new lines. ``None`` disables publishing, which keeps the
        solve logic usable without a transaction behind it.
    interval : float
        Seconds between flushes.
    tail_lines : int
        Number of lines retained by :attr:`text`.

    Examples
    --------
    >>> with TranscriptForwarder(publish) as transcript:  # doctest: +SKIP
    ...     transcript.attach(solver)
    ...     solver.settings.solution.run_calculation.iterate(iter_count=50)
    """

    def __init__(
        self,
        emit: LogCallback | None,
        interval: float = LOG_FLUSH_INTERVAL_SECONDS,
        tail_lines: int = LOG_TAIL_LINES,
    ) -> None:
        self._emit = emit
        self._interval = interval
        self._lock = threading.Lock()
        self._pending: list[str] = []
        self._tail: deque[str] = deque(maxlen=tail_lines)
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None

    @property
    def text(self) -> str:
        """The retained tail of the transcript, as a single string."""
        with self._lock:
            return "\n".join(self._tail)

    def append(self, chunk: str) -> None:
        """Buffer one transcript chunk.

        Parameters
        ----------
        chunk : str
            Text handed over by PyFluent. It may span several lines.
        """
        lines = [line for line in chunk.splitlines() if line.strip()]
        if not lines:
            return
        with self._lock:
            self._pending.extend(lines)
            self._tail.extend(lines)

    def attach(self, solver: Any) -> None:
        """Subscribe to the transcript of a Fluent session.

        Parameters
        ----------
        solver : Any
            A PyFluent solver session.
        """
        solver.transcript.register_callback(self.append)

    def flush(self) -> None:
        """Publish the lines buffered so far."""
        with self._lock:
            batch, self._pending = self._pending, []
        if batch and self._emit is not None:
            self._emit(batch)

    def __enter__(self) -> "TranscriptForwarder":
        """Start the flush timer."""
        self._worker = threading.Thread(target=self._run, name="fluent-transcript", daemon=True)
        self._worker.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop the flush timer and publish whatever is left."""
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=self._interval * 2)
            self._worker = None
        self.flush()

    def _run(self) -> None:
        """Flush at a fixed interval until the context is left."""
        while not self._stop.wait(self._interval):
            self.flush()
