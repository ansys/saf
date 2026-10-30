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

"""The project access REST API and live access stream."""

from collections.abc import Callable, Iterator
from typing import Any

from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
import pytest
from pytest_mock import MockerFixture
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.testclient import WebSocketTestSession

from ansys.iam.oidc import DEFAULT_SUBPROTOCOL_PREFIX, encode_base64_token
from ansys.saf.glow._config.const import DatabaseType
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._repository.relational import RelationalSession
from tests.mocks.solutions import instances
from tests.unit.access.conftest import SUPER_ADMIN_ROLE
from tests.unit.conftest import build_mock_app

solution = instances
pytestmark = pytest.mark.parametrize(
    "mock_module_settings",
    [{"glow_database_type": DatabaseType.Sqlite}],
    indirect=True,
)

STEP_URL = "instance-step"
UNKNOWN_REQUEST_ID = "no-such-request"


class Api:
    """A test client bundled with the headers of a few users."""

    def __init__(self, client: TestClient, as_user: Callable[..., dict[str, str]]) -> None:
        self.client = client
        self.alice = as_user(client, "alice")
        self.bob = as_user(client, "bob")
        self.carol = as_user(client, "carol")
        self.admin = as_user(client, "root", [SUPER_ADMIN_ROLE])
        self.no_identity = as_user(client, None)

    def create_project(self, headers: dict[str, str]) -> str:
        response = self.client.post("/projects", json={"display_name": "p"}, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["name"].removeprefix("projects/")

    def share(self, pid: str, user_id: str, headers: dict[str, str]) -> None:
        response = self.client.post(f"/projects/{pid}/access/members", json={"user_id": user_id}, headers=headers)
        assert response.status_code == 200, response.text

    def request(self, method: str, url: str, headers: dict[str, str], **kwargs: Any) -> Any:
        return self.client.request(method, url, headers=headers, **kwargs)

    def access(self, pid: str, headers: dict[str, str]) -> dict[str, Any]:
        response = self.client.get(f"/projects/{pid}/access", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
def api(access_settings: Settings, as_user: Callable[..., dict[str, str]]) -> Iterator[Api]:
    access_settings.glow_project_access_poll_interval = 0.05
    app = build_mock_app(access_settings, instances)
    with TestClient(app) as client:
        yield Api(client, as_user)


def _subprotocols(headers: dict[str, str]) -> list[str]:
    token = headers["Authorization"].removeprefix("Bearer ")
    return [f"{DEFAULT_SUBPROTOCOL_PREFIX}{encode_base64_token(token)}"]


def _receive_until_closed(websocket: WebSocketTestSession) -> None:
    while True:
        websocket.receive_json()


# --------------------------------------------------------------------------------------------------------------------
# Disabled


def test_access_routes_404_when_disabled(access_settings: Settings, as_user: Callable[..., dict[str, str]]):
    access_settings.glow_project_access_control_enabled = False
    app = build_mock_app(access_settings, instances)
    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any("/access" in path or "write-requests" in path or "methods:fail-stuck" in path for path in paths)
    assert "/access/me" not in paths
    with TestClient(app) as client:
        headers = as_user(client, "alice")
        for method, url in (
            ("get", "/access/me"),
            ("get", "/access/audit"),
            ("get", "/projects/x/access"),
            ("post", "/projects/x/access/members"),
            ("post", "/projects/x/lock:acquire"),
            ("post", "/projects/x/write-requests"),
            ("post", "/projects/x/methods:fail-stuck"),
        ):
            response = getattr(client, method)(url, headers=headers)
            assert response.status_code == 404, f"{method} {url}: {response.status_code}"
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/events/projects/x/access", _subprotocols(headers)),
        ):
            ...


# --------------------------------------------------------------------------------------------------------------------
# Identity and reads


def test_me(api: Api):
    assert api.client.get("/access/me", headers=api.alice).json() == {"user_id": "alice", "is_super_admin": False}
    assert api.client.get("/access/me", headers=api.admin).json() == {"user_id": "root", "is_super_admin": True}
    assert api.client.get("/access/me", headers=api.no_identity).json() == {"user_id": None, "is_super_admin": False}


def test_get_access(api: Api):
    pid = api.create_project(api.alice)
    access = api.access(pid, api.alice)
    assert access["owner_id"] == "alice"
    assert access["holder_id"] == "alice"
    assert access["can_write"] is True
    assert access["my_role"] == "owner"
    assert api.access(pid, api.admin)["my_role"] is None
    assert api.client.get(f"/projects/{pid}/access", headers=api.carol).status_code == 404


# --------------------------------------------------------------------------------------------------------------------
# Members and ownership


def test_share_and_unshare(api: Api):
    pid = api.create_project(api.alice)
    response = api.client.post(f"/projects/{pid}/access/members", json={"user_id": "bob"}, headers=api.alice)
    assert response.status_code == 200
    assert {m["user_id"]: m["role"] for m in response.json()["members"]} == {"alice": "owner", "bob": "viewer"}
    assert api.access(pid, api.bob)["my_role"] == "viewer"
    # denials: a viewer cannot share, a stranger gets 404
    assert api.client.post(f"/projects/{pid}/access/members", json={"user_id": "x"}, headers=api.bob).status_code == 403
    assert (
        api.client.post(f"/projects/{pid}/access/members", json={"user_id": "x"}, headers=api.carol).status_code == 404
    )

    assert api.client.delete(f"/projects/{pid}/access/members/bob", headers=api.bob).status_code == 403
    response = api.client.delete(f"/projects/{pid}/access/members/bob", headers=api.alice)
    assert response.status_code == 200
    assert [m["user_id"] for m in response.json()["members"]] == ["alice"]
    assert api.client.get(f"/projects/{pid}/access", headers=api.bob).status_code == 404


def test_transfer_ownership(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    assert (
        api.client.post(
            f"/projects/{pid}/access:transfer-ownership", json={"user_id": "bob"}, headers=api.bob
        ).status_code
        == 403
    )
    assert (
        api.client.post(
            f"/projects/{pid}/access:transfer-ownership", json={"user_id": "carol"}, headers=api.alice
        ).status_code
        == 409
    )
    response = api.client.post(f"/projects/{pid}/access:transfer-ownership", json={"user_id": "bob"}, headers=api.alice)
    assert response.status_code == 200
    assert response.json()["owner_id"] == "bob"
    assert response.json()["my_role"] == "viewer"


def test_assign_owner(api: Api):
    pid = api.create_project(api.alice)
    url = f"/projects/{pid}/access:assign-owner"
    assert api.client.post(url, json={"user_id": "carol"}, headers=api.alice).status_code == 403
    assert api.client.post(url, json={"user_id": "carol"}, headers=api.carol).status_code == 404
    response = api.client.post(url, json={"user_id": "carol"}, headers=api.admin)
    assert response.status_code == 200, response.text
    assert response.json()["owner_id"] == "carol"
    assert api.client.get(f"/projects/{pid}/access", headers=api.carol).status_code == 200


# --------------------------------------------------------------------------------------------------------------------
# Lock


def test_release_and_acquire(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    assert api.client.post(f"/projects/{pid}/lock:release", headers=api.bob).status_code == 403
    assert api.client.post(f"/projects/{pid}/lock:acquire", headers=api.bob).status_code == 409
    released = api.client.post(f"/projects/{pid}/lock:release", headers=api.alice)
    assert released.status_code == 200
    assert released.json()["holder_id"] is None
    acquired = api.client.post(f"/projects/{pid}/lock:acquire", headers=api.bob)
    assert acquired.status_code == 200
    assert acquired.json()["can_write"] is True
    assert api.client.post(f"/projects/{pid}/lock:acquire", headers=api.carol).status_code == 404


def test_take_over(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    api.client.post(f"/projects/{pid}/lock:release", headers=api.alice)
    api.client.post(f"/projects/{pid}/lock:acquire", headers=api.bob)
    assert api.client.post(f"/projects/{pid}/lock:take-over", headers=api.bob).status_code == 403
    response = api.client.post(f"/projects/{pid}/lock:take-over", headers=api.alice)
    assert response.status_code == 200
    assert response.json()["holder_id"] == "alice"


def test_force_release(api: Api):
    pid = api.create_project(api.alice)
    assert api.client.post(f"/projects/{pid}/lock:force-release", headers=api.alice).status_code == 403
    assert api.client.post(f"/projects/{pid}/lock:force-release", headers=api.carol).status_code == 404
    response = api.client.post(f"/projects/{pid}/lock:force-release", headers=api.admin)
    assert response.status_code == 200, response.text
    assert response.json()["holder_id"] is None
    audit = api.client.get("/access/audit", params={"project_id": pid}, headers=api.admin)
    assert [entry["action"] for entry in audit.json()] == ["lock_force_released"]


def test_lock_move_refused_while_a_transaction_runs(api: Api, mocker: MockerFixture):
    pid = api.create_project(api.alice)
    mocker.patch.object(RelationalSession, "get_running_methods", return_value=["instance-step.method"])
    assert api.client.post(f"/projects/{pid}/lock:release", headers=api.alice).status_code == 409


# --------------------------------------------------------------------------------------------------------------------
# Write requests


def test_request_approve_flow(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    r = api.client.post(f"/projects/{pid}/write-requests", headers=api.bob)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert r.json()["requester_id"] == "bob"
    assert api.client.post(f"/projects/{pid}/write-requests", headers=api.bob).status_code == 409
    assert api.client.post(f"/projects/{pid}/write-requests", headers=api.carol).status_code == 404
    assert api.client.post(f"/projects/{pid}/write-requests/{rid}:approve", headers=api.bob).status_code == 403
    a = api.client.post(f"/projects/{pid}/write-requests/{rid}:approve", headers=api.alice).json()
    assert a["holder_id"] == "bob"
    assert api.client.get(f"/projects/{pid}/access", headers=api.alice).json()["can_write"] is False


def test_request_deny_flow(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    rid = api.client.post(f"/projects/{pid}/write-requests", headers=api.bob).json()["id"]
    assert api.access(pid, api.alice)["pending_requests"][0]["id"] == rid
    assert api.client.post(f"/projects/{pid}/write-requests/{rid}:deny", headers=api.bob).status_code == 403
    denied = api.client.post(f"/projects/{pid}/write-requests/{rid}:deny", headers=api.alice)
    assert denied.status_code == 200
    assert denied.json()["holder_id"] == "alice"
    assert denied.json()["pending_requests"] == []
    assert api.client.post(f"/projects/{pid}/write-requests/{rid}:deny", headers=api.alice).status_code == 409
    assert (
        api.client.post(f"/projects/{pid}/write-requests/{UNKNOWN_REQUEST_ID}:deny", headers=api.alice).status_code
        == 404
    )


def test_request_withdraw_flow(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    rid = api.client.post(f"/projects/{pid}/write-requests", headers=api.bob).json()["id"]
    assert api.client.post(f"/projects/{pid}/write-requests/{rid}:withdraw", headers=api.alice).status_code == 403
    withdrawn = api.client.post(f"/projects/{pid}/write-requests/{rid}:withdraw", headers=api.bob)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["pending_requests"] == []


# --------------------------------------------------------------------------------------------------------------------
# Maintenance


def test_fail_stuck_methods(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    url = f"/projects/{pid}/methods:fail-stuck"
    assert api.client.post(url, headers=api.bob).status_code == 403
    assert api.client.post(url, headers=api.carol).status_code == 404
    assert api.client.post(url, headers=api.alice).json() == {"failed": []}
    assert api.client.post(url, headers=api.admin).json() == {"failed": []}


def test_audit_is_super_admin_only(api: Api):
    pid = api.create_project(api.alice)
    assert api.client.get("/access/audit", headers=api.alice).status_code == 403
    assert api.client.get("/access/audit", params={"project_id": pid}, headers=api.alice).status_code == 403
    api.client.post(f"/projects/{pid}/access:assign-owner", json={"user_id": "bob"}, headers=api.admin)
    response = api.client.get("/access/audit", params={"page": 1, "page_size": 10}, headers=api.admin)
    assert response.status_code == 200
    entries = response.json()
    assert [(e["project_id"], e["action"], e["actor_id"]) for e in entries] == [(pid, "owner_assigned", "root")]
    assert api.client.get("/access/audit", params={"page": 0}, headers=api.admin).status_code == 422


# --------------------------------------------------------------------------------------------------------------------
# Live access stream


def test_ws_access_stream_pushes_on_change(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    with api.client.websocket_connect(f"/events/projects/{pid}/access", _subprotocols(api.bob)) as websocket:
        first = websocket.receive_json()
        assert first["project_id"] == pid
        assert first["holder_id"] == "alice"
        assert first["my_role"] == "viewer"
        released = api.client.post(f"/projects/{pid}/lock:release", headers=api.alice).json()
        second = websocket.receive_json()
        assert second["version"] == first["version"] + 1 == released["version"]
        assert second["holder_id"] is None
        acquired = api.client.post(f"/projects/{pid}/lock:acquire", headers=api.bob).json()
        third = websocket.receive_json()
        assert third["version"] == second["version"] + 1 == acquired["version"]
        assert third["can_write"] is True


def test_ws_access_stream_closes_when_unshared(api: Api):
    pid = api.create_project(api.alice)
    api.share(pid, "bob", api.alice)
    with api.client.websocket_connect(f"/events/projects/{pid}/access", _subprotocols(api.bob)) as websocket:
        websocket.receive_json()
        assert api.client.delete(f"/projects/{pid}/access/members/bob", headers=api.alice).status_code == 200
        with pytest.raises(WebSocketDisconnect) as closed:
            _receive_until_closed(websocket)
    assert closed.value.code == WS_1008_POLICY_VIOLATION


def test_ws_access_stream_refuses_non_members(api: Api):
    pid = api.create_project(api.alice)
    for target in (f"/events/projects/{pid}/access", f"/events/projects/{'z' * 24}/access"):
        for headers in (api.carol, api.admin):
            with (
                pytest.raises(WebSocketDisconnect) as refused,
                api.client.websocket_connect(target, _subprotocols(headers)),
            ):
                ...
            assert refused.value.code == WS_1008_POLICY_VIOLATION
