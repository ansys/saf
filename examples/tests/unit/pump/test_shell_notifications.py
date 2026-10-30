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

import inspect
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from ansys.saf.glow.solution import MethodStatus
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import no_update
import pytest

from saf.solutions.examples.ui.pages.pump import shell_notifications as toasts


def _undecorated(callback):
    """Return the function behind GLOW's callback decorator.

    The decorator turns the URL into a project proxy, which needs a running GLOW server; the
    tests hand a stand-in project directly instead. Under pytest, the GLOW testing plugin adds
    a context wrapper of its own that does not set ``__wrapped__``.
    """
    free_variables = callback.__code__.co_freevars
    if "decorated" in free_variables:
        callback = callback.__closure__[free_variables.index("decorated")].cell_contents
    return inspect.unwrap(callback)


mount_termination_listeners = _undecorated(toasts.mount_termination_listeners)
on_build_case_terminated = _undecorated(toasts.on_build_case_terminated)
on_run_simulation_terminated = _undecorated(toasts.on_run_simulation_terminated)


def _termination(status: MethodStatus, error: str | None = None) -> dict:
    return {"data": json.dumps({"status": status.value, "exception_message": error})}


def _step(scene_method: str, scene_status: MethodStatus = MethodStatus.Completed) -> SimpleNamespace:
    step = SimpleNamespace(get_long_running_method_state=lambda name: SimpleNamespace(status=scene_status))
    setattr(step, scene_method, MagicMock())
    return step


def _project(scene_status: MethodStatus = MethodStatus.Completed) -> SimpleNamespace:
    return SimpleNamespace(
        steps=SimpleNamespace(
            pump_model_setup_step=_step("prepare_scene", scene_status),
            pump_solve_step=_step("prepare_solved_scene", scene_status),
        )
    )


def _ids(notifications: list[dict]) -> list[tuple[str, str]]:
    return [(n["id"], n["action"]) for n in notifications]


def test_listener_slot_holds_the_container_and_the_mounted_project():
    rendered = str(toasts.listeners_slot())
    assert toasts.LISTENERS_CONTAINER_ID in rendered
    assert toasts.MOUNTED_PROJECT_STORE_ID in rendered


def test_shell_listeners_do_not_share_identifiers_with_the_pages():
    shell_ids = {
        toasts.BUILD_CASE_LISTENER_ID,
        toasts.PREPARE_SCENE_LISTENER_ID,
        toasts.RUN_SIMULATION_LISTENER_ID,
        toasts.PREPARE_SOLVED_SCENE_LISTENER_ID,
    }
    page_ids = {"build-case-ws", "prepare-scene-ws", "run-simulation-ws", "prepare-solved-scene-ws"}
    assert len(shell_ids) == 4
    assert not shell_ids & page_ids


def test_listeners_are_not_remounted_while_navigating_within_a_project():
    with pytest.raises(PreventUpdate):
        mount_termination_listeners("p1", "p1", _project())


def test_listeners_are_removed_when_no_project_is_open():
    assert mount_termination_listeners(None, "p1", _project()) == ([], None)


def test_listeners_are_mounted_for_a_newly_opened_project(monkeypatch):
    created = []
    monkeypatch.setattr(
        toasts.DashClient,
        "create_event_listener",
        lambda step, stream_name, id: created.append(id) or id,
    )
    listeners, mounted = mount_termination_listeners("p2", "p1", _project())
    assert mounted == "p2"
    assert listeners == created
    assert set(created) == {
        toasts.BUILD_CASE_LISTENER_ID,
        toasts.PREPARE_SCENE_LISTENER_ID,
        toasts.RUN_SIMULATION_LISTENER_ID,
        toasts.PREPARE_SOLVED_SCENE_LISTENER_ID,
    }


@pytest.mark.parametrize(
    ("callback", "step_name", "scene_method", "copy", "scene_copy"),
    [
        (
            on_build_case_terminated,
            "pump_model_setup_step",
            "prepare_scene",
            toasts.BUILD_CASE_NOTIFICATION,
            toasts.PREPARE_SCENE_NOTIFICATION,
        ),
        (
            on_run_simulation_terminated,
            "pump_solve_step",
            "prepare_solved_scene",
            toasts.RUN_SIMULATION_NOTIFICATION,
            toasts.PREPARE_SOLVED_SCENE_NOTIFICATION,
        ),
    ],
    ids=["build_case", "run_simulation"],
)
class TestRunTermination:
    def test_success_closes_the_toast_and_starts_the_scene_conversion(
        self, callback, step_name, scene_method, copy, scene_copy
    ):
        project = _project()
        notifications = callback(_termination(MethodStatus.Completed), project)
        assert _ids(notifications) == [(copy.notification_id, "update"), (scene_copy.notification_id, "show")]
        getattr(getattr(project.steps, step_name), scene_method).assert_called_once_with()

    def test_failure_closes_the_toast_without_converting_anything(
        self, callback, step_name, scene_method, copy, scene_copy
    ):
        project = _project()
        notifications = callback(_termination(MethodStatus.Failed, "Fluent crashed"), project)
        assert _ids(notifications) == [(copy.notification_id, "update")]
        assert notifications[0]["message"] == "Fluent crashed"
        getattr(getattr(project.steps, step_name), scene_method).assert_not_called()

    def test_a_conversion_already_running_is_not_started_twice(
        self, callback, step_name, scene_method, copy, scene_copy
    ):
        # Every open tab receives the termination; only the first one starts the conversion.
        project = _project(scene_status=MethodStatus.Running)
        notifications = callback(_termination(MethodStatus.Completed), project)
        assert (scene_copy.notification_id, "show") in _ids(notifications)
        getattr(getattr(project.steps, step_name), scene_method).assert_not_called()

    def test_messages_that_are_not_a_termination_leave_the_toast_alone(
        self, callback, step_name, scene_method, copy, scene_copy
    ):
        with pytest.raises(PreventUpdate):
            callback({"data": json.dumps({"stage": "Meshing", "fraction": 0.5})}, _project())


@pytest.mark.parametrize(
    ("callback", "copy"),
    [
        (toasts.on_prepare_scene_terminated, toasts.PREPARE_SCENE_NOTIFICATION),
        (toasts.on_prepare_solved_scene_terminated, toasts.PREPARE_SOLVED_SCENE_NOTIFICATION),
    ],
)
def test_scene_conversion_end_closes_its_toast(callback, copy):
    assert _ids(callback(_termination(MethodStatus.Completed))) == [(copy.notification_id, "update")]
    assert _ids(callback(_termination(MethodStatus.Failed))) == [(copy.notification_id, "update")]
    assert callback(None) is no_update
