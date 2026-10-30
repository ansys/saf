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

"""Unit tests for the ProjectAccessBanner component."""

# pyright: reportAttributeAccessIssue=false

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest import mock

from dash.development.base_component import Component
from dash.exceptions import PreventUpdate
import pytest

from ansys.solutions.dash_super_components.project_access_banner import (
    ProjectAccessBanner,
    render_banner,
)

pytest.importorskip("ansys.saf.glow.client")

from ansys.saf.glow._access.schemas import (
    ProjectMemberInfo,
    ProjectRole,
    WriteRequestStatus,
)
from ansys.saf.glow.client import (
    ProjectAccess,
    WriteRequestInfo,
)

ME = "11111111-me"
OWNER = "22222222-owner"
OTHER = "33333333-other"
MODULE = "ansys.solutions.dash_super_components.project_access_banner"
AID = "banner"
NAMES = {ME: "Me", OWNER: "Olivia", OTHER: "Otto"}


def _request(request_id: str, requester_id: str) -> WriteRequestInfo:
    return WriteRequestInfo(
        id=request_id,
        requester_id=requester_id,
        status=WriteRequestStatus.pending,
        created_at=datetime.now(UTC),
    )


def _access(
    holder_id: str | None,
    my_role: ProjectRole = ProjectRole.viewer,
    pending: list[WriteRequestInfo] | None = None,
    owner_id: str = OWNER,
) -> ProjectAccess:
    return ProjectAccess(
        project_id="p1",
        owner_id=owner_id,
        members=[ProjectMemberInfo(user_id=owner_id, role=ProjectRole.owner)],
        holder_id=holder_id,
        lock_acquired_at=None,
        last_write_at=None,
        version=1,
        pending_requests=pending or [],
        my_role=my_role,
        can_write=holder_id == ME,
        is_orphan=False,
    )


def _walk(components: Any) -> Iterator[Any]:
    if isinstance(components, (list, tuple)):
        for component in components:
            yield from _walk(component)
        return
    yield components
    if isinstance(components, Component):
        yield from _walk(getattr(components, "children", None))


def _texts(components: Any) -> list[str]:
    return [node for node in _walk(components) if isinstance(node, str)]


def _buttons(components: Any) -> list[dict[str, Any]]:
    return [
        node.id
        for node in _walk(components)
        if isinstance(node, Component) and isinstance(getattr(node, "id", None), dict) and "action" in node.id
    ]


def _actions(components: Any) -> list[str]:
    return [button["action"] for button in _buttons(components)]


def test_renders_nothing_when_disabled():
    assert render_banner(None, NAMES, ME, AID) == []


def test_holder_is_me():
    components = render_banner(_access(ME), NAMES, ME, AID)

    assert "You are editing this project." in _texts(components)
    assert _actions(components) == ["release"]
    assert _buttons(components)[0]["aio_id"] == AID


def test_holder_is_me_with_pending_requests():
    access = _access(ME, pending=[_request("r1", OTHER), _request("r2", OWNER)])

    components = render_banner(access, NAMES, ME, AID)
    texts = _texts(components)

    assert "Otto requests write access" in texts
    assert "Olivia requests write access" in texts
    buttons = _buttons(components)
    assert [(b["action"], b["request_id"]) for b in buttons] == [
        ("release", ""),
        ("approve", "r1"),
        ("deny", "r1"),
        ("approve", "r2"),
        ("deny", "r2"),
    ]


def test_lock_free():
    components = render_banner(_access(None), NAMES, ME, AID)

    assert "Nobody is editing this project." in _texts(components)
    assert _actions(components) == ["start-editing"]


def test_lock_free_shows_pending_requests_to_owner():
    access = _access(None, my_role=ProjectRole.owner, pending=[_request("r1", OTHER)], owner_id=ME)

    components = render_banner(access, NAMES, ME, AID)

    assert "Otto requests write access" in _texts(components)
    assert _actions(components) == ["start-editing", "approve", "deny"]


def test_someone_else_holds_without_request():
    components = render_banner(_access(OTHER), NAMES, ME, AID)

    assert "Read-only — Otto is editing." in _texts(components)
    assert _actions(components) == ["request"]


def test_someone_else_holds_with_my_request():
    access = _access(OTHER, pending=[_request("r1", ME)])

    components = render_banner(access, NAMES, ME, AID)

    assert "Read-only — Otto is editing." in _texts(components)
    assert "Write access requested" in _texts(components)
    buttons = _buttons(components)
    assert [(b["action"], b["request_id"]) for b in buttons] == [("withdraw", "r1")]


def test_someone_else_holds_owner_can_take_over():
    access = _access(OTHER, my_role=ProjectRole.owner, owner_id=ME)

    components = render_banner(access, NAMES, ME, AID)

    assert _actions(components) == ["request", "take-over"]


def test_owner_decides_on_requests_of_others_while_someone_else_holds():
    access = _access(
        OTHER,
        my_role=ProjectRole.owner,
        pending=[_request("r1", OWNER)],
        owner_id=ME,
    )

    components = render_banner(access, NAMES, ME, AID)

    assert "Olivia requests write access" in _texts(components)
    assert _actions(components) == ["request", "take-over", "approve", "deny"]


def test_non_owner_does_not_see_requests_of_others():
    access = _access(OTHER, pending=[_request("r1", OWNER)])

    components = render_banner(access, NAMES, ME, AID)

    assert not any("requests write access" in text for text in _texts(components))
    assert _actions(components) == ["request"]


def test_unknown_user_label():
    stranger = "abcdef1234567890"

    components = render_banner(_access(stranger), NAMES, ME, AID)

    assert "Read-only — unknown user (abcdef12…) is editing." in _texts(components)


def test_layout_contains_listener_and_containers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_WS_EVENTS_ADDR", "localhost:1234")

    banner = ProjectAccessBanner("p1", aio_id=AID)

    ids = [node.id for node in _walk(banner) if isinstance(node, Component) and getattr(node, "id", None)]
    assert ProjectAccessBanner.ids.listener(AID) in ids
    assert ProjectAccessBanner.ids.content(AID) in ids
    assert ProjectAccessBanner.ids.error(AID) in ids
    assert banner.aio_id == AID


def _click(action: str, request_id: str = "") -> mock.MagicMock:
    triggered_id = ProjectAccessBanner.ids.button(AID, action, request_id)
    fake_ctx = mock.MagicMock()
    fake_ctx.triggered_id = triggered_id
    fake_ctx.triggered = [{"prop_id": "x.n_clicks", "value": 1}]
    return fake_ctx


@pytest.mark.parametrize(
    ("action", "method", "args"),
    [
        ("release", "release_lock", ("p1",)),
        ("start-editing", "acquire_lock", ("p1",)),
        ("request", "request_write_access", ("p1",)),
        ("take-over", "take_over_lock", ("p1",)),
        ("withdraw", "withdraw_request", ("p1", "r1")),
        ("approve", "approve_request", ("p1", "r1")),
        ("deny", "deny_request", ("p1", "r1")),
    ],
)
def test_button_calls_matching_dash_client_method(action: str, method: str, args: tuple[str, ...]):
    with (
        mock.patch(f"{MODULE}.ctx", _click(action, "r1" if len(args) > 1 else "")),
        mock.patch(f"ansys.saf.glow.client.DashClient.{method}") as client_method,
    ):
        result = ProjectAccessBanner.act([1], "p1")

    client_method.assert_called_once_with(*args)
    assert result == ""


def test_button_error_is_displayed():
    with (
        mock.patch(f"{MODULE}.ctx", _click("release")),
        mock.patch("ansys.saf.glow.client.DashClient.release_lock", side_effect=RuntimeError("boom")),
    ):
        assert ProjectAccessBanner.act([1], "p1") == "boom"


def test_button_without_click_prevents_update():
    fake_ctx = _click("release")
    fake_ctx.triggered = [{"prop_id": "x.n_clicks", "value": None}]
    with mock.patch(f"{MODULE}.ctx", fake_ctx), pytest.raises(PreventUpdate):
        ProjectAccessBanner.act([None], "p1")


def test_render_callback_renders_message():
    access = _access(OTHER, pending=[_request("r1", ME)])
    me_response = mock.MagicMock()
    me_response.json.return_value = {"user_id": ME, "is_super_admin": False}
    with (
        mock.patch("ansys.saf.glow.client.DashClient._access_request", return_value=me_response),
        mock.patch("ansys.saf.glow.client.DashClient.display_names", return_value=NAMES) as display_names,
    ):
        components = ProjectAccessBanner.render(
            {"data": access.model_dump_json()},
            ProjectAccessBanner.ids.listener(AID),
        )

    assert set(display_names.call_args.args[0]) == {OWNER, OTHER, ME}
    assert "Read-only — Otto is editing." in _texts(components)
    assert _actions(components) == ["withdraw"]


def test_render_callback_without_message_prevents_update():
    with pytest.raises(PreventUpdate):
        ProjectAccessBanner.render(None, ProjectAccessBanner.ids.listener(AID))
