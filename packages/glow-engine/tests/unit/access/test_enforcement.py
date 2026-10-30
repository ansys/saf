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

"""Enforcement of project access control on the existing REST, GraphQL and event routes."""

from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any
import uuid

from fastapi import WebSocketDisconnect
from fastapi.routing import APIWebSocketRoute, _IncludedRouter  # pyright: ignore[reportPrivateUsage]
from fastapi.testclient import TestClient
from httpx2 import Response
import pytest
from pytest_mock import MockerFixture
from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.status import WS_1008_POLICY_VIOLATION

from ansys.iam.oidc import DEFAULT_SUBPROTOCOL_PREFIX, encode_base64_token
from ansys.saf.glow._access.access_crud import AccessCrud
from ansys.saf.glow._access.principal import ON_BEHALF_OF_HEADER, Principal
from ansys.saf.glow._access.schemas import ProjectRole
from ansys.saf.glow._config.const import DatabaseType
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.method_status import MethodStatus
from ansys.saf.glow._crud.crud import Crud
from ansys.saf.glow._crud.project_builder import ProjectBuilder
from ansys.saf.glow._repository.sqlite_factory import SqliteSessionFactory
from ansys.saf.glow._server.dependencies import get_graphql_client, get_http_client, get_settings
from ansys.saf.glow._server.server import mount_mcp_app
from ansys.saf.glow._server.solution import SolutionService
from tests.mocks.solutions import instances
from tests.unit.access.conftest import SUPER_ADMIN_ROLE
from tests.unit.conftest import build_mock_app
from tests.unit.routes.gql_mock_client import TestClientGqlMock

solution = instances
pytestmark = pytest.mark.parametrize(
    "mock_module_settings",
    [{"glow_database_type": DatabaseType.Sqlite}],
    indirect=True,
)

API_KEY = "configured-api-key"
ALICE = Principal(user_id="alice", is_super_admin=False, is_internal=False)
STEP_URL = "instance-step"
METHOD = f"{STEP_URL}:shutdown"
INSTANCE = f"{STEP_URL}/instances/x-y"
BLOB = f"{STEP_URL}/blobs/transfer-entity-handle"
STREAM = f"{STEP_URL}/streams/test-stream"
COMPLETED = {"status": "completed"}


@dataclass
class World:
    """An app with auth and access control on. alice owns a project and holds its lock, bob is a viewer."""

    client: TestClient
    internal_client: TestClient
    settings: Settings
    access: AccessCrud
    factory: SqliteSessionFactory
    solution_service: SolutionService
    headers_of: Callable[..., dict[str, str]]
    project_id: str
    alice: dict[str, str]
    bob: dict[str, str]
    carol: dict[str, str]
    admin: dict[str, str]

    @property
    def base(self) -> str:
        return f"/projects/{self.project_id}"

    async def new_orphan(self) -> str:
        async with self.factory.get_session(modification=True) as session:
            project = ProjectBuilder.build_project_model("orphan", self.solution_service)
            info = await session.build_project_in_database(project)
        return info.project_id

    async def bob_holds_the_lock(self) -> None:
        await self.access.release(self.project_id, ALICE)
        await self.access.acquire(self.project_id, Principal("bob", False, False))

    def create_project(self, headers: dict[str, str], name: str = "p") -> str:
        response = self.client.post("/projects", json={"display_name": name}, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["name"].removeprefix("projects/")


@pytest.fixture
def enforce_foreign_keys() -> Iterator[None]:
    """Make SQLite enforce foreign keys like PostgreSQL does (it ignores them unless asked).

    Applies to engines created while the fixture is active, so fixtures creating the app must depend on it.
    """

    def _enable(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(Engine, "connect", _enable)
    yield
    event.remove(Engine, "connect", _enable)


@pytest.fixture
async def world(
    enforce_foreign_keys: None,
    access_settings: Settings,
    as_user: Callable[..., dict[str, str]],
) -> AsyncGenerator[World]:
    access_settings.glow_api_key = API_KEY
    app = build_mock_app(access_settings, instances)
    service = SolutionService(instances)
    service.build_and_validate()
    factory = SqliteSessionFactory(access_settings, service)
    access = AccessCrud(factory, access_settings)
    with (
        TestClient(app) as client,
        TestClient(app, client=("127.0.0.1", 123)) as internal_client,
    ):
        env = World(
            client=client,
            internal_client=internal_client,
            settings=access_settings,
            access=access,
            factory=factory,
            solution_service=service,
            headers_of=lambda sub, roles=(): as_user(client, sub, roles),
            project_id="",
            alice=as_user(client, "alice"),
            bob=as_user(client, "bob"),
            carol=as_user(client, "carol"),
            admin=as_user(client, "root", [SUPER_ADMIN_ROLE]),
        )
        env.project_id = env.create_project(env.alice)
        await access.share(env.project_id, "bob", ALICE)
        yield env


def _concrete(path: str, project_id: str) -> str:
    path = path.replace("{project_id}", project_id)
    path = path.replace("{lock_id}", str(uuid.uuid4()))
    return re.sub(r"\{[^}]+\}", "x", path)


def _project_routes(app: Any) -> Iterator[tuple[str, str]]:
    for route in app.routes:
        routes: list[Any] = route.original_router.routes if isinstance(route, _IncludedRouter) else [route]
        for sub_route in routes:
            if isinstance(sub_route, APIWebSocketRoute) or "{project_id}" not in str(sub_route.path):
                continue
            for method in sub_route.methods:
                yield method.lower(), str(sub_route.path)


def _write_requests(base: str, events_base: str) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        ("patch", f"{base}/steps/{STEP_URL}", {"json": {}}),
        ("post", f"{base}/steps/{METHOD}", {}),
        ("patch", f"{base}/steps/{METHOD}", {"json": COMPLETED}),
        ("post", f"{base}/steps/{INSTANCE}", {"json": {}}),
        ("patch", f"{base}/steps/{INSTANCE}", {"json": {}}),
        ("delete", f"{base}/steps/{INSTANCE}", {}),
        ("put", f"{base}/steps/{BLOB}", {"files": {"upload_file": ("f.txt", b"x")}}),
        ("post", f"{events_base}/steps/{STREAM}", {"json": {}}),
        ("patch", base, {"json": {"description": "changed"}}),
        ("post", f"{base}:upgrade", {}),
        ("post", f"{base}/bdm-locks", {}),
        ("delete", f"{base}/bdm-locks/{uuid.uuid4()}", {}),
    ]


def _assert_locked(response: Response, holder_id: str | None) -> None:
    assert response.status_code == 423, response.text
    assert response.json()["detail"]["holder_id"] == holder_id


async def test_stranger_gets_404_on_every_project_route(world: World):
    tested: list[str] = []
    for method, path in _project_routes(world.client.app):
        url = _concrete(path, world.project_id)
        response = getattr(world.client, method)(url, headers=world.carol)
        assert response.status_code == 404, f"{method} {path}: {response.status_code} {response.text}"
        tested.append(f"{method} {path}")
    assert "get /projects/{project_id}:export" in tested
    assert "post /events/projects/{project_id}/steps/{step_id}/streams/{stream_name}" in tested
    assert len(tested) > 30


async def test_stranger_gets_404_on_unknown_and_known_projects_alike(world: World):
    known = world.client.get(f"{world.base}/steps/{STEP_URL}", headers=world.carol)
    unknown = world.client.get(f"/projects/{'z' * 24}/steps/{STEP_URL}", headers=world.carol)
    assert known.status_code == unknown.status_code == 404
    known_detail = known.json()["detail"].replace(world.project_id, "<id>")
    assert known_detail == unknown.json()["detail"].replace("z" * 24, "<id>")


async def test_viewer_reads_succeed(world: World):
    for url in (
        f"{world.base}",
        f"{world.base}/steps/{STEP_URL}",
        f"{world.base}/steps/{METHOD}",
        f"{world.base}:export",
    ):
        response = world.client.get(url, headers=world.bob)
        assert response.status_code == 200, f"{url}: {response.status_code} {response.text}"
    # the holder stores a blob, the viewer downloads it
    blob_url = f"{world.base}/steps/{BLOB}"
    uploaded = world.client.put(blob_url, files={"upload_file": ("hello.txt", b"hello")}, headers=world.alice)
    assert uploaded.status_code == 200, uploaded.text
    downloaded = world.client.get(blob_url, headers=world.bob)
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == b"hello"


async def test_viewer_writes_get_423(world: World):
    for method, url, kwargs in _write_requests(world.base, f"/events{world.base}"):
        response = getattr(world.client, method)(url, headers=world.bob, **kwargs)
        assert response.status_code == 423, f"{method} {url}: {response.status_code} {response.text}"
        assert response.json()["detail"]["holder_id"] == "alice"


async def test_holder_writes_are_not_blocked(world: World):
    response = world.client.patch(f"{world.base}", json={"description": "changed"}, headers=world.alice)
    assert response.status_code == 200, response.text
    response = world.client.patch(f"{world.base}/steps/{STEP_URL}", json={"color": "red"}, headers=world.alice)
    assert response.status_code == 200, response.text
    response = world.client.post(f"/events{world.base}/steps/{STREAM}", json={"a": 1}, headers=world.alice)
    assert response.status_code == 200, response.text


async def test_viewer_writes_get_423_when_nobody_holds_the_lock(world: World):
    await world.access.release(world.project_id, ALICE)
    response = world.client.patch(f"{world.base}", json={"description": "changed"}, headers=world.bob)
    _assert_locked(response, None)


def _mutation(project_id: str) -> dict[str, Any]:
    return {
        "query": (
            "mutation Update($project_id: String!, $steps: StepsJsonInput!) "
            "{ update_project_steps_with_json(project_id: $project_id, steps: $steps) { status error } }"
        ),
        "variables": {"project_id": project_id, "steps": {"instance_step": {"color": '"red"'}}},
    }


async def test_viewer_graphql_mutation_permission_denied(world: World):
    result = world.client.post("/graphql", json=_mutation(world.project_id), headers=world.bob).json()
    assert result["data"]["update_project_steps_with_json"]["status"] == "PERMISSION_DENIED"
    stranger = world.client.post("/graphql", json=_mutation(world.project_id), headers=world.carol).json()
    assert stranger["data"]["update_project_steps_with_json"]["status"] == "NOT_FOUND"
    holder = world.client.post("/graphql", json=_mutation(world.project_id), headers=world.alice).json()
    assert holder["data"]["update_project_steps_with_json"]["status"] == "SUCCESS"
    step = world.client.get(f"{world.base}/steps/{STEP_URL}", headers=world.alice).json()
    assert step["color"] == "red"


async def test_delete_owner_only(world: World):
    assert world.client.delete(world.base, headers=world.bob).status_code == 403
    assert world.client.delete(world.base, headers=world.carol).status_code == 404
    assert world.client.delete(world.base, headers=world.alice).status_code == 200
    assert world.client.get(world.base, headers=world.alice).status_code == 404


async def test_super_admin_can_delete(world: World):
    assert world.client.delete(world.base, headers=world.admin).status_code == 200


async def test_list_shows_only_member_projects_with_access_summary(world: World):
    bob_project = world.create_project(world.bob, "bobs")

    def listed(headers: dict[str, str]) -> dict[str, Any]:
        response = world.client.get("/projects", headers=headers)
        assert response.status_code == 200, response.text
        return {p["name"].removeprefix("projects/"): p["access"] for p in response.json()["projects"]}

    alice_list = listed(world.alice)
    assert alice_list == {
        world.project_id: {"owner_id": "alice", "holder_id": "alice", "my_role": "owner", "pending_request_count": 0},
    }
    bob_list = listed(world.bob)
    assert set(bob_list) == {world.project_id, bob_project}
    assert bob_list[world.project_id] == {
        "owner_id": "alice",
        "holder_id": "alice",
        "my_role": "viewer",
        "pending_request_count": 0,
    }
    assert bob_list[bob_project]["my_role"] == "owner"
    assert listed(world.carol) == {}


async def test_super_admin_lists_all_and_orphans_only(world: World):
    orphan = await world.new_orphan()
    response = world.client.get("/projects", headers=world.admin)
    assert response.status_code == 200
    projects = {p["name"].removeprefix("projects/"): p["access"] for p in response.json()["projects"]}
    assert set(projects) == {world.project_id, orphan}
    assert projects[world.project_id]["owner_id"] == "alice"
    assert projects[orphan]["owner_id"] is None

    response = world.client.get("/projects", params={"orphans_only": True}, headers=world.admin)
    assert [p["name"].removeprefix("projects/") for p in response.json()["projects"]] == [orphan]

    assert world.client.get("/projects", params={"orphans_only": True}, headers=world.alice).status_code == 403
    assert world.client.get(f"/projects/{orphan}", headers=world.admin).status_code == 200


async def test_list_without_user_id_lists_nothing(world: World):
    response = world.client.get("/projects", headers=world.headers_of(None))
    assert response.status_code == 200
    assert response.json()["projects"] == []


async def test_list_without_user_id_ignores_a_member_with_an_empty_id(world: World):
    # Defence in depth: the API refuses empty ids, but even if such a row existed, a caller without id lists nothing.
    async with world.factory.get_session(project_id=world.project_id, modification=True) as session:
        await session.upsert_member(world.project_id, "", ProjectRole.viewer)
    response = world.client.get("/projects", headers=world.headers_of(None))
    assert response.status_code == 200
    assert response.json()["projects"] == []
    assert response.json()["total_projects"] == 0


async def test_super_admin_cannot_read_steps_or_export(world: World):
    assert world.client.get(world.base, headers=world.admin).status_code == 200
    for url in (
        f"{world.base}/steps/{STEP_URL}",
        f"{world.base}/steps/{STEP_URL}/data/color",
        f"{world.base}/steps/{METHOD}",
        f"{world.base}:export",
    ):
        assert world.client.get(url, headers=world.admin).status_code == 404, url
    assert world.client.patch(f"{world.base}/steps/{STEP_URL}", json={}, headers=world.admin).status_code == 404
    assert world.client.get("/projects", headers=world.admin).status_code == 200


async def test_transaction_rejected_if_lock_moved_before_prepare(world: World, mocker: MockerFixture):
    original = Crud.get_modifying_project_lock

    @asynccontextmanager
    async def moving_lock(self: Crud, project_id: str) -> AsyncGenerator[None]:
        # Between the moment alice passed the access dependencies and the moment she takes the project lock,
        # bob takes the write lock (the lock is released and taken in a session of its own).
        async with self._session_factory.get_session(modification=True) as session:  # pyright: ignore[reportPrivateUsage]
            await session.set_lock_holder(project_id, "bob", datetime.now(UTC))
        async with original(self, project_id):
            yield None

    mocker.patch.object(Crud, "get_modifying_project_lock", moving_lock)
    response = world.client.post(f"{world.base}/steps/{METHOD}", headers=world.alice)
    _assert_locked(response, "bob")
    state = world.client.get(f"{world.base}/steps/{METHOD}", headers=world.bob).json()
    # the method was never prepared: it did not start, run or complete
    assert state["status"] == MethodStatus.RunRequired


async def test_holder_transaction_runs_and_keeps_the_lock(world: World):
    # The method runner calls back into the API through these clients, with the API key and the id of its initiator.
    overrides = world.client.app.dependency_overrides  # type: ignore
    overrides[get_http_client] = lambda: world.internal_client
    overrides[get_graphql_client] = lambda: TestClientGqlMock(client=world.internal_client)
    url = f"{world.base}/steps/{STEP_URL}:store-red-in-entity-handle"
    response = world.client.post(url, headers=world.alice)
    assert response.status_code == 200, response.text
    state = world.client.get(url, headers=world.alice).json()
    assert state["status"] == "completed", state
    access = await world.access.get_access(world.project_id, ALICE)
    assert access.holder_id == "alice"
    viewer = world.client.post(url, headers=world.bob)
    _assert_locked(viewer, "alice")


async def test_upgrade_keeps_owner_members_lock_and_requests(world: World, enforce_foreign_keys: None):
    # ``enforce_foreign_keys`` makes SQLite reject deleting the project row while access rows still reference it, as
    # PostgreSQL does. (SQLite alone accepts that, so without it this test could not catch such a regression.)
    request = await world.access.create_request(world.project_id, Principal("bob", False, False))
    before = await world.access.get_access(world.project_id, ALICE)

    response = world.client.post(f"{world.base}:upgrade", headers=world.alice)
    assert response.status_code == 200, response.text

    after = await world.access.get_access(world.project_id, ALICE)
    assert after.owner_id == "alice"
    assert after.holder_id == "alice"
    assert after.members == before.members
    assert [r.id for r in after.pending_requests] == [request.id]
    assert after.lock_acquired_at == before.lock_acquired_at
    assert world.client.get(f"{world.base}/steps/{STEP_URL}", headers=world.bob).status_code == 200


async def test_late_callback_from_previous_holder_is_rejected(world: World):
    await world.bob_holds_the_lock()
    headers = {"x-api-key": API_KEY, ON_BEHALF_OF_HEADER: "alice"}
    response = world.internal_client.patch(f"{world.base}/steps/{METHOD}", json=COMPLETED, headers=headers)
    _assert_locked(response, "bob")
    response = world.internal_client.post(f"/events{world.base}/steps/{STREAM}", json={}, headers=headers)
    _assert_locked(response, "bob")
    headers[ON_BEHALF_OF_HEADER] = "bob"
    response = world.internal_client.patch(f"{world.base}/steps/{METHOD}", json=COMPLETED, headers=headers)
    assert response.status_code == 200, response.text


async def test_internal_callback_without_user_allowed(world: World):
    headers = {"x-api-key": API_KEY}
    response = world.internal_client.patch(f"{world.base}/steps/{METHOD}", json=COMPLETED, headers=headers)
    assert response.status_code == 200, response.text
    await world.bob_holds_the_lock()
    response = world.internal_client.patch(f"{world.base}/steps/{METHOD}", json=COMPLETED, headers=headers)
    assert response.status_code == 200, response.text
    assert world.internal_client.get(f"{world.base}/steps/{STEP_URL}", headers=headers).status_code == 200


async def test_create_project_makes_creator_owner_and_holder(world: World):
    project_id = world.create_project(world.bob, "bobs")
    access = await world.access.get_access(project_id, Principal("bob", False, False))
    assert access.owner_id == "bob"
    assert access.holder_id == "bob"
    assert world.client.get(f"/projects/{project_id}", headers=world.alice).status_code == 404


def _subprotocols(token_headers: dict[str, str]) -> list[str]:
    token = token_headers["Authorization"].removeprefix("Bearer ")
    return [f"{DEFAULT_SUBPROTOCOL_PREFIX}{encode_base64_token(token)}"]


async def test_ws_events_stranger_closed_1008(world: World):
    url = f"/events{world.base}/steps/{STREAM}"
    unknown_url = f"/events/projects/{'z' * 24}/steps/{STREAM}"
    for target in (url, unknown_url):
        with (
            pytest.raises(WebSocketDisconnect) as stranger,
            world.client.websocket_connect(target, _subprotocols(world.carol)),
        ):
            ...
        assert stranger.value.code == WS_1008_POLICY_VIOLATION
    with (
        pytest.raises(WebSocketDisconnect) as admin,
        world.client.websocket_connect(url, _subprotocols(world.admin)),
    ):
        ...
    assert admin.value.code == WS_1008_POLICY_VIOLATION


async def test_ws_events_viewer_receives_events(world: World):
    url = f"/events{world.base}/steps/{STREAM}"
    with world.client.websocket_connect(url, _subprotocols(world.bob)) as websocket:
        assert world.client.post(url, json={"message": "hello"}, headers=world.alice).status_code == 200
        assert websocket.receive_json() == {"message": "hello"}


async def test_mcp_not_mounted_when_access_control_enabled(access_settings: Settings):
    access_settings.glow_mcp_disabled = False
    app = mount_mcp_app(build_mock_app(access_settings, instances), access_settings)
    assert all(getattr(route, "path", None) != access_settings.glow_mcp_path for route in app.routes)
    assert not any(getattr(route, "path", "").startswith(access_settings.glow_mcp_path) for route in app.routes)


@pytest.fixture
def open_client(settings: Settings) -> Iterator[TestClient]:
    app = build_mock_app(settings, instances)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client


async def test_feature_disabled_unchanged(open_client: TestClient):
    assert not open_client.app.dependency_overrides[get_settings]().glow_project_access_control_enabled  # type: ignore
    created = open_client.post("/projects", json={"display_name": "p"})
    assert created.status_code == 200
    assert created.json()["access"] is None
    base = f"/{created.json()['name']}"

    assert open_client.get(base).json()["access"] is None
    listed = open_client.get("/projects").json()["projects"]
    assert [p["access"] for p in listed] == [None]

    assert open_client.get(f"{base}/steps/{STEP_URL}").status_code == 200
    assert open_client.patch(f"{base}/steps/{STEP_URL}", json={"color": "red"}).status_code == 200
    assert open_client.patch(base, json={"description": "changed"}).status_code == 200
    assert open_client.post(f"/events{base}/steps/{STREAM}", json={}).status_code == 200
    assert open_client.get(f"{base}:export").status_code == 200
    assert open_client.get("/projects", params={"orphans_only": True}).status_code == 403
    assert open_client.delete(base).status_code == 200
