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

import threading
from unittest.mock import MagicMock

from saf.solutions.pump.solution.logic.transcript import TranscriptForwarder


def test_append_splits_a_multi_line_chunk():
    batches: list[list[str]] = []
    forwarder = TranscriptForwarder(batches.append)
    forwarder.append("iter  continuity\n   1  1.0e-02")
    forwarder.flush()
    assert batches == [["iter  continuity", "   1  1.0e-02"]]


def test_append_drops_blank_lines():
    # Fluent pads its console output; blank lines would waste the bounded buffer.
    forwarder = TranscriptForwarder(None)
    forwarder.append("\n   \nreal line\n")
    assert forwarder.text == "real line"


def test_flush_publishes_each_line_only_once():
    batches: list[list[str]] = []
    forwarder = TranscriptForwarder(batches.append)
    forwarder.append("first")
    forwarder.flush()
    forwarder.append("second")
    forwarder.flush()
    assert batches == [["first"], ["second"]]


def test_flush_is_silent_when_nothing_was_buffered():
    emit = MagicMock()
    TranscriptForwarder(emit).flush()
    emit.assert_not_called()


def test_text_keeps_only_the_tail():
    # A long run prints far more than the field should ever hold.
    forwarder = TranscriptForwarder(None, tail_lines=3)
    for index in range(10):
        forwarder.append(f"line {index}")
    assert forwarder.text == "line 7\nline 8\nline 9"


def test_text_survives_a_flush():
    # The buffer is drained on flush, but the tail is what gets persisted at the end.
    forwarder = TranscriptForwarder(lambda lines: None)
    forwarder.append("kept")
    forwarder.flush()
    assert forwarder.text == "kept"


def test_attach_subscribes_to_the_solver_transcript():
    solver = MagicMock()
    forwarder = TranscriptForwarder(None)
    forwarder.attach(solver)
    solver.transcript.register_callback.assert_called_once_with(forwarder.append)


def test_context_manager_flushes_on_exit():
    batches: list[list[str]] = []
    with TranscriptForwarder(batches.append, interval=0.01) as forwarder:
        forwarder.append("late line")
    assert batches[-1] == ["late line"]


def test_context_manager_stops_its_worker_thread():
    with TranscriptForwarder(None, interval=0.01):
        pass
    assert not any(thread.name == "fluent-transcript" for thread in threading.enumerate())


def test_emit_is_optional():
    # Running the logic outside a transaction must not require a publisher.
    with TranscriptForwarder(None, interval=0.01) as forwarder:
        forwarder.append("no listener")
    assert forwarder.text == "no listener"
