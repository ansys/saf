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

"""Progress feedback shared by the two long-running pages.

Both the Model Setup and the Operating Point page drive a Fluent session that runs for
minutes. Event streams carry the run to the browser: GLOW's termination stream, a progress
stream, a transcript stream and, for the solve, a convergence-history stream.

Responsibilities are split on purpose. The progress bar lives in exactly one place, under
the action button, while the notification is a plain status toast that survives navigation
to another page.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import json
from typing import Any

from ansys.saf.glow.solution import MethodState, MethodStatus
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import html
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from saf.solutions.compressor.solution.logic.constants import LOG_TAIL_LINES

_GENERIC_FAILURE_MESSAGE = (
    "The Fluent session did not complete. Check that Ansys Fluent is installed, licensed and "
    "reachable, then try again."
)

_RUNNING_MESSAGE = "Fluent is running. You can browse other pages while it works."

_LOG_PLACEHOLDER = "No Fluent output yet. The console appears here once a run starts."

_LOG_VIEWPORT_STYLE = {
    "height": "520px",
    "overflowY": "auto",
    "overflowX": "auto",
    "backgroundColor": "var(--mantine-color-dark-8)",
    "borderRadius": "var(--mantine-radius-sm)",
    "padding": "12px 16px",
}

_LOG_TEXT_STYLE = {
    "margin": 0,
    "fontFamily": "var(--mantine-font-family-monospace)",
    "fontSize": "12px",
    "lineHeight": 1.5,
    "color": "var(--mantine-color-gray-4)",
    "whiteSpace": "pre",
}


def require_click(n_clicks: int | None) -> None:
    """Abort the callback unless the button was actually pressed.

    ``prevent_initial_call`` only covers the very first load of the application. Every page
    here is mounted by the shell's routing callback, so a button's callback also fires the
    moment the button appears, with ``n_clicks`` still ``None``. Without this guard, opening
    a page would launch Fluent.

    Parameters
    ----------
    n_clicks : int or None
        The ``n_clicks`` property of the button that triggered the callback.

    Raises
    ------
    PreventUpdate
        When the callback fired because the button was mounted rather than clicked.
    """
    if not n_clicks:
        raise PreventUpdate


@dataclass(frozen=True)
class StepEvent:
    """A single message received on one of a step's event streams.

    Three payload shapes exist. GLOW publishes a :class:`MethodState` on the termination
    stream, and the step's own ``transaction.raise_event`` calls publish
    ``{"stage": ..., "fraction": ...}`` and ``{"lines": [...]}`` on the progress and
    transcript streams. At most one group of fields is therefore set on any given event.
    """

    status: MethodStatus | None = None
    stage: str | None = None
    fraction: float | None = None
    lines: list[str] | None = None
    history: list[dict[str, float]] | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        """Whether the event reports a successful completion."""
        return self.status == MethodStatus.Completed

    @property
    def failed(self) -> bool:
        """Whether the event reports a failure."""
        return self.status == MethodStatus.Failed

    @property
    def finished(self) -> bool:
        """Whether the event reports the end of the run, successful or not."""
        return self.succeeded or self.failed


@dataclass(frozen=True)
class NotificationCopy:
    """The wording of the notification that tracks one long-running method.

    The two message defaults describe a Fluent session, which is what most of the long-running
    work here is. A method that drives something else overrides them so that the toast never
    blames Fluent for a failure Fluent had no part in.
    """

    notification_id: str
    running_title: str
    success_title: str
    success_message: str
    failure_title: str
    running_message: str = _RUNNING_MESSAGE
    failure_message: str = _GENERIC_FAILURE_MESSAGE


def parse_event(message: dict[str, Any] | None) -> StepEvent:
    """Turn a raw WebSocket message into a :class:`StepEvent`.

    Parameters
    ----------
    message : dict or None
        The ``message`` property of a ``dash_extensions`` WebSocket component. Its ``data``
        entry holds the JSON text published on the stream.

    Returns
    -------
    StepEvent
        The decoded event. Unrecognised or malformed payloads yield an empty event rather
        than raising, so that a stray message cannot break the page.
    """
    if not message:
        return StepEvent()
    try:
        payload = json.loads(message["data"])
    except (KeyError, TypeError, ValueError):
        return StepEvent()
    if not isinstance(payload, dict):
        return StepEvent()
    if "status" in payload:
        state = MethodState.model_validate(payload)
        return StepEvent(status=state.status, error=state.exception_message)
    if "stage" in payload:
        return StepEvent(stage=str(payload["stage"]), fraction=float(payload.get("fraction", 0.0)))
    if "lines" in payload:
        return StepEvent(lines=[str(line) for line in payload["lines"]])
    if "history" in payload:
        return StepEvent(history=[dict(row) for row in payload["history"]])
    return StepEvent()


def opening_notification(copy: NotificationCopy) -> list[dict]:
    """Show the toast that tracks the run from start to finish.

    The toast deliberately carries no progress detail: it stays mounted while the user
    browses other pages, whereas the progress bar belongs to the page that owns the run.

    Parameters
    ----------
    copy : NotificationCopy
        Wording for this method.

    Returns
    -------
    list of dict
        Payload for ``NotificationContainer.sendNotifications``.
    """
    return [
        {
            "id": copy.notification_id,
            "action": "show",
            "title": copy.running_title,
            "message": copy.running_message,
            "loading": True,
            "autoClose": False,
            "withCloseButton": False,
        }
    ]


def closing_notification(copy: NotificationCopy, event: StepEvent) -> list[dict] | None:
    """Close the toast with the outcome of the run.

    Parameters
    ----------
    copy : NotificationCopy
        Wording for this method.
    event : StepEvent
        Event decoded by :func:`parse_event`.

    Returns
    -------
    list of dict or None
        Payload for ``NotificationContainer.sendNotifications``, or ``None`` when the run is
        still going and the toast must be left alone.
    """
    if event.succeeded:
        return [
            {
                "id": copy.notification_id,
                "action": "update",
                "title": copy.success_title,
                "message": copy.success_message,
                "color": "green",
                "icon": DashIconify(icon="carbon:checkmark-filled", width=20),
                "loading": False,
                "autoClose": 4000,
                "withCloseButton": True,
            }
        ]
    if event.failed:
        return [
            {
                "id": copy.notification_id,
                "action": "update",
                "title": copy.failure_title,
                "message": event.error or copy.failure_message,
                "color": "red",
                "icon": DashIconify(icon="carbon:warning-filled", width=20),
                "loading": False,
                "autoClose": False,
                "withCloseButton": True,
            }
        ]
    return None


def progress_panel(stage: str | None, fraction: float | None, running: bool = True) -> html.Div:
    """Render the one and only progress bar, which sits under the action button.

    Parameters
    ----------
    stage : str or None
        Label of the stage in flight.
    fraction : float or None
        Progress between 0 and 1.
    running : bool
        Whether the run is still going. A finished run keeps the bar static.

    Returns
    -------
    html.Div
        A labelled progress bar, or an empty div when there is nothing to report. No spinner:
        the button and the toast already carry one, and a third would be noise.
    """
    if not running:
        return html.Div()
    percent = _percent(fraction)
    return html.Div(
        [
            dmc.Space(h=20),
            dmc.Group(
                [
                    dmc.Text(stage or "Starting…", size="sm", fw=500),
                    dmc.Text(f"{percent:.0f}%", size="sm", c="dimmed"),
                ],
                justify="space-between",
            ),
            dmc.Space(h=8),
            dmc.Progress(value=percent, animated=True, striped=True, radius="xl", size="md"),
        ]
    )


def log_viewer(viewport_id: str, lines: Sequence[str]) -> html.Div:
    """Render the Fluent console, scrolled to the newest line.

    Parameters
    ----------
    viewport_id : str
        DOM id of the scrollable element. A clientside callback pins it to the bottom.
    lines : sequence of str
        Transcript lines, oldest first.

    Returns
    -------
    html.Div
        The scrollable console.
    """
    return html.Div(
        html.Pre("\n".join(lines) if lines else _LOG_PLACEHOLDER, style=_LOG_TEXT_STYLE),
        id=viewport_id,
        style=_LOG_VIEWPORT_STYLE,
    )


def append_lines(current: Sequence[str] | None, new: Sequence[str] | None) -> list[str]:
    """Append a batch of transcript lines, keeping the buffer bounded.

    Parameters
    ----------
    current : sequence of str or None
        Lines accumulated so far.
    new : sequence of str or None
        Lines from the latest event.

    Returns
    -------
    list of str
        The trimmed buffer.
    """
    combined = list(current or []) + list(new or [])
    return combined[-LOG_TAIL_LINES:]


def split_log(text: str | None) -> list[str]:
    """Turn a persisted ``log_text`` field back into a list of lines."""
    if not text:
        return []
    return text.splitlines()


def scroll_to_bottom(viewport_id: str) -> str:
    """Build the clientside callback that pins a log viewport to its newest line.

    Dash re-renders the whole console on every batch, which resets the scroll position to
    the top. This runs right after the re-render and puts it back at the bottom, so the user
    never has to scroll to follow the run.

    Parameters
    ----------
    viewport_id : str
        DOM id of the scrollable element.

    Returns
    -------
    str
        JavaScript source for ``clientside_callback``.
    """
    return f"""
    function(children) {{
        const viewport = document.getElementById("{viewport_id}");
        if (viewport) {{
            viewport.scrollTop = viewport.scrollHeight;
        }}
        return window.dash_clientside.no_update;
    }}
    """


def _percent(fraction: float | None) -> float:
    """Clamp a 0-1 progress fraction onto a 0-100 percentage."""
    if fraction is None:
        return 0.0
    return min(100.0, max(0.0, fraction * 100.0))
