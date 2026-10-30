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

"""End-to-end scenario of per-project access control with two users, alice and bob.

The mock IdP issues tokens whose ``sub`` claim is the requested username, and GLOW runs with authentication validation
and project access control enabled.
"""

from collections.abc import Callable, Generator
from typing import Any

import httpx2
import pytest
from tenacity import TryAgain, retry, stop_after_delay, wait_fixed

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.solution.end_to_end import EnableAuthValidationConfiguration, GlowBaseProcess
from tests.e2e.conftest import EnableProjectAccessControlConfiguration
from tests.mocks.solutions.transactions import TransactionsSolution

pytestmark = pytest.mark.parametrize("solution_type", [TransactionsSolution], indirect=True)

LOCKED = 423


@pytest.fixture(scope="module")
def access_control_enabled(
    session_glow: GlowBaseProcess[TransactionsSolution],
    session_idp_mock_server: str,
) -> Generator[None, None, None]:
    session_glow.change_configuration(
        EnableAuthValidationConfiguration, restart=False, idp_server=session_idp_mock_server
    )
    session_glow.change_configuration(EnableProjectAccessControlConfiguration)
    yield
    session_glow.configure_default_execution()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@retry(stop=stop_after_delay(30), wait=wait_fixed(0.5), reraise=True)
def wait_for_method_completion(method_url: str, headers: dict[str, str]) -> None:
    response = httpx2.get(method_url, headers=headers)
    response.raise_for_status()
    status = response.json()["status"]
    if status == MethodStatus.Failed:
        pytest.fail(f"Method failed: {response.text}")
    if status != MethodStatus.Completed:
        raise TryAgain


def _access(project_url: str, headers: dict[str, str]) -> dict[str, Any]:
    response = httpx2.get(f"{project_url}/access", headers=headers)
    response.raise_for_status()
    return response.json()


def test_alice_and_bob_share_a_project(
    access_control_enabled: None,
    session_glow: GlowBaseProcess[TransactionsSolution],
    get_glow_client: Callable[..., Client[TransactionsSolution]],
    get_user_access_token: Callable[[str], str],
    random_project_display_name: str,
):
    alice = _bearer(get_user_access_token("alice"))
    bob = _bearer(get_user_access_token("bob"))

    # GIVEN: alice creates a project: she owns it and holds the write lock
    with get_glow_client(session_glow, get_user_access_token("alice")) as alice_client:
        project = alice_client.create_project(random_project_display_name)
        project_url = project.url
        step_url = f"{project_url}/steps/transaction-step"
        method_url = f"{step_url}:one-second-async"

        state = _access(project_url, alice)
        assert state["owner_id"] == "alice"
        assert state["holder_id"] == "alice"
        assert state["can_write"] is True

        # bob is a stranger, so the project does not exist for him
        assert httpx2.get(project_url, headers=bob).status_code == 404

        # WHEN: alice shares the project with bob
        response = httpx2.post(f"{project_url}/access/members", json={"user_id": "bob"}, headers=alice)
        assert response.status_code == 200, response.text

        # THEN: bob can read it but not write: his transaction is refused with 423 and the holder id
        assert httpx2.get(project_url, headers=bob).status_code == 200
        response = httpx2.post(method_url, headers=bob)
        assert response.status_code == LOCKED, response.text
        assert response.json()["detail"]["holder_id"] == "alice"
        bob_state = _access(project_url, bob)
        assert bob_state["my_role"] == "viewer"
        assert bob_state["can_write"] is False

        # WHEN: bob requests write access and alice approves
        response = httpx2.post(f"{project_url}/write-requests", headers=bob)
        assert response.status_code == 200, response.text
        request_id = response.json()["id"]
        response = httpx2.post(f"{project_url}/write-requests/{request_id}:approve", headers=alice)
        assert response.status_code == 200, response.text
        assert response.json()["holder_id"] == "bob"

        # THEN: bob's transaction runs to completion, and alice cannot write meanwhile
        response = httpx2.post(method_url, headers=bob)
        assert response.status_code == 200, response.text
        response = httpx2.patch(step_url, json={"x": 5}, headers=alice)
        assert response.status_code == LOCKED, response.text
        assert response.json()["detail"]["holder_id"] == "bob"
        wait_for_method_completion(method_url, bob)

        # WHEN: the transaction is over, alice (the owner) takes the lock back
        response = httpx2.post(f"{project_url}/lock:take-over", headers=alice)
        assert response.status_code == 200, response.text

        # THEN: she writes again and bob can't
        assert response.json()["holder_id"] == "alice"
        response = httpx2.patch(step_url, json={"x": 5}, headers=alice)
        assert response.status_code == 200, response.text
        response = httpx2.patch(step_url, json={"x": 6}, headers=bob)
        assert response.status_code == LOCKED, response.text
        assert _access(project_url, alice)["holder_id"] == "alice"
