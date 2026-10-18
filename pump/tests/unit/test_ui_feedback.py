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

import json

from ansys.saf.glow.solution import MethodStatus
from dash.exceptions import PreventUpdate
import pytest

from saf.solutions.pump.solution.logic.constants import LOG_TAIL_LINES
from saf.solutions.pump.ui.feedback import (
    NotificationCopy,
    StepEvent,
    append_lines,
    closing_notification,
    log_viewer,
    opening_notification,
    parse_event,
    progress_panel,
    require_click,
    scroll_to_bottom,
    split_log,
)

COPY = NotificationCopy(
    notification_id="test-notification",
    running_title="Running",
    success_title="Done",
    success_message="All good.",
    failure_title="Broken",
)


def _message(payload: dict) -> dict:
    """Wrap a payload the way the dash_extensions WebSocket component delivers it."""
    return {"data": json.dumps(payload)}


# ----------------------------------------------------------------------------------- parse_event ----


def test_parse_event_reads_a_progress_payload():
    event = parse_event(_message({"stage": "Iterating 40/200", "fraction": 0.5}))
    assert event.stage == "Iterating 40/200"
    assert event.fraction == pytest.approx(0.5)
    assert event.status is None


def test_parse_event_reads_a_method_state_payload():
    event = parse_event(_message({"status": MethodStatus.Completed.value}))
    assert event.succeeded
    assert event.finished
    assert event.stage is None


def test_parse_event_carries_the_failure_message():
    event = parse_event(_message({"status": MethodStatus.Failed.value, "exception_message": "no licence"}))
    assert event.failed
    assert event.error == "no licence"


def test_parse_event_of_a_running_state_is_not_finished():
    assert not parse_event(_message({"status": MethodStatus.Running.value})).finished


def test_parse_event_reads_a_transcript_payload():
    event = parse_event(_message({"lines": ["iter  continuity", "   1  1.0e-02"]}))
    assert event.lines == ["iter  continuity", "   1  1.0e-02"]
    assert event.stage is None
    assert event.status is None


def test_parse_event_tolerates_a_missing_message():
    assert parse_event(None) == StepEvent()


def test_parse_event_tolerates_malformed_json():
    # A stray frame must never take the page down.
    assert parse_event({"data": "not json"}) == StepEvent()


# ---------------------------------------------------------------------------------- notifications ----


def test_opening_notification_shows_a_pinned_loading_toast():
    notification = opening_notification(COPY)[0]
    assert notification["id"] == "test-notification"
    assert notification["action"] == "show"
    assert notification["loading"] is True
    assert notification["autoClose"] is False


def test_opening_notification_carries_no_progress_detail():
    # The progress bar lives under the button; the toast must not duplicate it.
    message = opening_notification(COPY)[0]["message"]
    assert "%" not in message


def test_closing_notification_turns_green_on_success():
    notification = closing_notification(COPY, StepEvent(status=MethodStatus.Completed))[0]
    assert notification["color"] == "green"
    assert notification["loading"] is False
    assert notification["autoClose"] == 4000


def test_closing_notification_surfaces_the_backend_error():
    event = StepEvent(status=MethodStatus.Failed, error="impeller_speed_rpm must be between 100 and 3000")
    notification = closing_notification(COPY, event)[0]
    assert notification["color"] == "red"
    assert notification["autoClose"] is False
    assert "impeller_speed_rpm" in notification["message"]


def test_closing_notification_falls_back_to_generic_failure_text():
    notification = closing_notification(COPY, StepEvent(status=MethodStatus.Failed))[0]
    assert "Ansys Fluent" in notification["message"]


@pytest.mark.parametrize(
    "event",
    [StepEvent(status=MethodStatus.Running), StepEvent(stage="Reading case", fraction=0.1), StepEvent()],
)
def test_closing_notification_leaves_a_live_toast_alone(event):
    # Only a terminal event may rewrite the toast, otherwise the run looks finished early.
    assert closing_notification(COPY, event) is None


# -------------------------------------------------------------------------------- progress panel ----


def test_progress_panel_shows_the_stage_and_bar():
    rendered = str(progress_panel("Post-processing", 0.9))
    assert "Post-processing" in rendered
    assert "90%" in rendered


def test_progress_panel_without_a_stage_falls_back_to_a_starting_label():
    assert "Starting" in str(progress_panel(None, 0.0))


def test_progress_panel_clamps_an_out_of_range_fraction():
    assert "100%" in str(progress_panel("Done", 1.4))


def test_progress_panel_is_empty_when_nothing_is_running():
    # Revisiting an idle page must not show a stale bar left over from the previous run.
    rendered = str(progress_panel("Post-processing", 0.9, running=False))
    assert "Post-processing" not in rendered
    assert "90%" not in rendered


# ------------------------------------------------------------------------------------ log viewer ----


def test_log_viewer_renders_the_lines_in_a_scrollable_viewport():
    rendered = str(log_viewer("log-viewport", ["first line", "second line"]))
    assert "first line" in rendered
    assert "second line" in rendered
    assert "log-viewport" in rendered


def test_log_viewer_explains_itself_when_there_is_no_output_yet():
    assert "No Fluent output yet" in str(log_viewer("log-viewport", []))


def test_append_lines_keeps_the_order():
    assert append_lines(["a"], ["b", "c"]) == ["a", "b", "c"]


def test_append_lines_tolerates_an_empty_buffer():
    assert append_lines(None, ["a"]) == ["a"]
    assert append_lines(["a"], None) == ["a"]


def test_append_lines_drops_the_oldest_lines_past_the_cap():
    # A long Fluent run prints far more than the browser should hold.
    lines = append_lines([f"line {index}" for index in range(LOG_TAIL_LINES)], ["newest"])
    assert len(lines) == LOG_TAIL_LINES
    assert lines[-1] == "newest"
    assert lines[0] == "line 1"


def test_split_log_round_trips_a_persisted_field():
    assert split_log("a\nb") == ["a", "b"]
    assert split_log("") == []
    assert split_log(None) == []


def test_scroll_to_bottom_targets_the_requested_viewport():
    source = scroll_to_bottom("run-simulation-log-viewport")
    assert "run-simulation-log-viewport" in source
    assert "scrollHeight" in source


# --------------------------------------------------------------------------------- require_click ----


@pytest.mark.parametrize("n_clicks", [None, 0])
def test_require_click_aborts_when_the_button_was_only_mounted(n_clicks):
    # Mounting a page fires its button callbacks; that must never start a Fluent run.
    with pytest.raises(PreventUpdate):
        require_click(n_clicks)


def test_require_click_lets_a_real_click_through():
    assert require_click(1) is None
