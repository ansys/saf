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


"""Banner that shows the write-lock state of a project and lets the user act on it."""

import os
from typing import TYPE_CHECKING, Any
import uuid

from dash import ctx
from dash.development.base_component import Component
from dash.exceptions import PreventUpdate

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )
from dash_extensions.enrich import (
    ALL,
    MATCH,
    Input,
    Output,
    State,
    callback,
    dcc,
    html,
)
import dash_mantine_components as dmc

from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds

if TYPE_CHECKING:
    from ansys.saf.glow.client import ProjectAccess

_COMPONENT = "project-access-banner"

_RELEASE = "release"
_START_EDITING = "start-editing"
_REQUEST = "request"
_WITHDRAW = "withdraw"
_TAKE_OVER = "take-over"
_APPROVE = "approve"
_DENY = "deny"

# DashClient method run by each action; the ones in _REQUEST_ACTIONS act on a write request.
_CLIENT_METHODS = {
    _RELEASE: "release_lock",
    _START_EDITING: "acquire_lock",
    _REQUEST: "request_write_access",
    _WITHDRAW: "withdraw_request",
    _TAKE_OVER: "take_over_lock",
    _APPROVE: "approve_request",
    _DENY: "deny_request",
}
_REQUEST_ACTIONS = (_WITHDRAW, _APPROVE, _DENY)

_BUTTON_LABELS = {
    _RELEASE: "Release",
    _START_EDITING: "Start editing",
    _REQUEST: "Request write access",
    _WITHDRAW: "Withdraw",
    _TAKE_OVER: "Take over",
    _APPROVE: "Approve",
    _DENY: "Deny",
}


class _BannerIds(AIOIds):
    """Provides IDs for the subcomponents of :class:`ProjectAccessBanner`."""

    @classmethod
    def listener(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
        """Return the ID for the access WebSocket listener."""
        return cls.make_id_dict(_COMPONENT, "listener", aio_id)

    @classmethod
    def content(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
        """Return the ID for the container that holds the rendered banner."""
        return cls.make_id_dict(_COMPONENT, "content", aio_id)

    @classmethod
    def error(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
        """Return the ID for the container that holds the last action error."""
        return cls.make_id_dict(_COMPONENT, "error", aio_id)

    @classmethod
    def project_id(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
        """Return the ID for the store that holds the project identifier."""
        return cls.make_id_dict(_COMPONENT, "project-id", aio_id)

    @classmethod
    def button(
        cls,
        aio_id: str | _Wildcard,
        action: str | _Wildcard,
        request_id: str | _Wildcard = "",
    ) -> dict[str, Any]:
        """Return the ID for an action button.

        Parameters
        ----------
        aio_id : str or _Wildcard
            The component's unique identifier.
        action : str or _Wildcard
            The action of the button: ``"release"``, ``"start-editing"``, ``"request"``,
            ``"withdraw"``, ``"take-over"``, ``"approve"`` or ``"deny"``.
        request_id : str or _Wildcard, optional
            The identifier of the write request the button acts on, if any.

        Returns
        -------
        dict[str, Any]
            The unique ID dictionary for the button.
        """
        return {**cls.make_id_dict(_COMPONENT, "button", aio_id), "action": action, "request_id": request_id}


def _user_label(user_id: str, names: dict[str, str]) -> str:
    name = names.get(user_id)
    return name if name else f"unknown user ({user_id[:8]}…)"


def _button(aio_id: str, action: str, request_id: str = "") -> dmc.Button:
    props: dict[str, Any] = {}
    if action in (_DENY, _TAKE_OVER):
        props["color"] = "red"
    return dmc.Button(
        _BUTTON_LABELS[action],
        id=_BannerIds.button(aio_id, action, request_id),
        size="xs",
        variant="light" if action in (_DENY, _WITHDRAW, _RELEASE) else "filled",
        **props,
    )


def _status_row(text: str, buttons: list[Component]) -> dmc.Group:
    return dmc.Group([dmc.Text(text, size="sm"), *buttons], gap="sm")


def render_banner(
    access: "ProjectAccess | None",
    names: dict[str, str],
    me: str,
    aio_id: str = "",
) -> list[Component]:
    """Render the banner for the access state of a project.

    Parameters
    ----------
    access : ProjectAccess or None
        The access state, or ``None`` if project access control is not enabled (nothing is rendered).
    names : dict[str, str]
        Display name of each known user id.
    me : str
        The user id of the current user.
    aio_id : str, optional
        The ``aio_id`` of the :class:`ProjectAccessBanner` the buttons belong to.

    Returns
    -------
    list[Component]
        The components to display (an empty list if ``access`` is ``None``).
    """
    if access is None:
        return []

    is_owner = access.my_role == "owner" or access.owner_id == me
    holder_is_me = access.holder_id == me
    my_request = next((r for r in access.pending_requests if r.requester_id == me), None)

    rows: list[Component] = []
    if holder_is_me:
        rows.append(_status_row("You are editing this project.", [_button(aio_id, _RELEASE)]))
        color = "green"
    elif access.holder_id is None:
        rows.append(_status_row("Nobody is editing this project.", [_button(aio_id, _START_EDITING)]))
        color = "gray"
    else:
        holder_name = _user_label(access.holder_id, names)
        buttons = _my_request_buttons(aio_id, my_request)
        if is_owner:
            buttons.append(_button(aio_id, _TAKE_OVER))
        rows.append(_status_row(f"Read-only — {holder_name} is editing.", buttons))
        color = "yellow"

    if holder_is_me or is_owner:
        for request in access.pending_requests:
            if request.requester_id == me:
                continue
            rows.append(
                _status_row(
                    f"{_user_label(request.requester_id, names)} requests write access",
                    [_button(aio_id, _APPROVE, request.id), _button(aio_id, _DENY, request.id)],
                ),
            )

    return [dmc.Alert(rows, color=color, p="xs")]


def _my_request_buttons(aio_id: str, my_request: Any) -> list[Component]:
    if my_request is None:
        return [_button(aio_id, _REQUEST)]
    return [dmc.Text("Write access requested", size="sm", fw=500), _button(aio_id, _WITHDRAW, my_request.id)]


def _error_message(ex: Exception) -> str:
    response = getattr(ex, "response", None)
    if response is not None:
        try:
            detail = response.json().get("detail")
            if detail:
                return str(detail)
        except Exception:  # noqa: S110
            pass
    return str(ex) or type(ex).__name__


def _access_control_enabled() -> bool:
    """Whether the GLOW API has project access control on.

    The banner reads the same environment variable the API uses. When it is off (or unset), no websocket is opened,
    so the component stays empty instead of failing to connect to a route that is not mounted.
    """
    return os.environ.get("GLOW_PROJECT_ACCESS_CONTROL_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class ProjectAccessBanner(html.Div):
    """
    A Dash component that shows who may edit a project and lets the user act on the write lock.

    ProjectAccessBanner is based on the Dash All-in-One (AIO) component pattern. It listens to the
    access stream of a project (``DashClient.create_access_listener``) and re-renders itself each
    time the access state changes. Depending on the state, it offers to start editing, release the
    write lock, request or withdraw a write request, take over the lock (owner) and approve or deny
    the requests of other users (owner or lock holder). Nothing is rendered when project access
    control is not enabled.

    To decide in your own callbacks whether the current user may modify the project, read
    ``can_write`` from the access state, for example::

        can_write = DashClient.get_project_access(project_id).can_write

    (``DashClient.get_project_access`` returns ``None`` if project access control is not enabled.)

    .. warning::

        This component requires a SAF-based solution with access to the GLOW API and the
        ``GLOW_WS_EVENTS_ADDR`` environment variable. ``ansys.saf.glow.client`` is imported lazily,
        as this package does not depend on ``ansys-saf-glow-engine``.

    Parameters
    ----------
    project_id : str
        The identifier of the project.
    aio_id : str, optional
        Unique identifier for this component instance. A UUID is generated if not provided.
    """

    ids = _BannerIds

    def __init__(self, project_id: str, aio_id: str | None = None):
        from ansys.saf.glow.client import DashClient

        if aio_id is None:
            aio_id = str(uuid.uuid4())

        self.aio_id = aio_id

        children: list[Component] = [
            dcc.Store(id=self.ids.project_id(aio_id), storage_type="memory", data=project_id),
            html.Div(id=self.ids.content(aio_id)),
            html.Div(id=self.ids.error(aio_id), style={"color": "var(--mantine-color-red-6)"}),
        ]
        if _access_control_enabled():
            children.insert(0, DashClient.create_access_listener(project_id, id=self.ids.listener(aio_id)))

        super().__init__(children)

    @staticmethod
    @callback(
        Output(ids.content(MATCH), "children"),
        Input(ids.listener(MATCH), "message"),
        State(ids.listener(MATCH), "id"),
    )
    def render(message: dict[str, Any] | None, listener_id: dict[str, Any]) -> list[Component]:
        """Re-render the banner when a new access state is received."""
        if not message or not message.get("data"):
            raise PreventUpdate

        from ansys.saf.glow.client import DashClient, ProjectAccess

        access = ProjectAccess.model_validate_json(message["data"])
        me = DashClient._access_request("GET", "/access/me").json()["user_id"]  # pyright: ignore[reportPrivateUsage]
        user_ids = {request.requester_id for request in access.pending_requests}
        user_ids.update(member.user_id for member in access.members)
        if access.holder_id:
            user_ids.add(access.holder_id)
        names = DashClient.display_names(sorted(user_ids))

        return render_banner(access, names, me, listener_id["aio_id"])

    @staticmethod
    @callback(
        Output(ids.error(MATCH), "children"),
        Input(ids.button(MATCH, ALL, ALL), "n_clicks"),
        State(ids.project_id(MATCH), "data"),
        prevent_initial_call=True,
    )
    def act(n_clicks: list[int | None], project_id: str) -> str:
        """Run the action of the clicked button. The new state comes back through the access stream."""
        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or not ctx.triggered or not ctx.triggered[0]["value"]:
            raise PreventUpdate

        from ansys.saf.glow.client import DashClient

        action: str = triggered["action"]
        request_id: str = triggered["request_id"]
        method_name = _CLIENT_METHODS.get(action)
        if method_name is None:
            raise PreventUpdate
        method = getattr(DashClient, method_name)
        try:
            if action in _REQUEST_ACTIONS:
                method(project_id, request_id)
            else:
                method(project_id)
        except Exception as ex:
            return _error_message(ex)
        return ""
