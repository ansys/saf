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

import asyncio
from collections.abc import Callable
from concurrent.futures import Executor
import logging
import logging.config
from pathlib import Path
from typing import Any
from unittest import mock

import httpx2
import pytest
import pytest_mock

from ansys.saf.glow._access.principal import ON_BEHALF_OF_HEADER
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow._executor.method_runner import MethodRunner, ProcessMethodRunner, ThreadMethodRunner
from ansys.saf.glow._server.method_url import MethodUrl
from ansys.saf.glow._telemetry.instrumentor import Instrumentor
from tests.mocks.solutions import minimal_solution

solution = minimal_solution
_FAKE_TRANSACTION_URL = MethodUrl("http://my_host:my_port/projects/project_fake/steps/step_fake:transaction_fake")


@pytest.fixture
def mock_method_runner_internals(mocker: pytest_mock.MockerFixture, request: pytest.FixtureRequest) -> None:
    runner_cls = request.param
    mocker.patch.object(runner_cls, "_run_method")
    mocker.patch.object(runner_cls, "_set_method_state")
    mocker.patch.object(runner_cls, "_get_transaction_step_method")
    mocker.patch.object(runner_cls, "_raise_method_event")
    mocker.patch.object(runner_cls, "_init_data_repository")
    mocker.patch.object(runner_cls, "_init_hps_blob_manager")
    mocker.patch.object(
        runner_cls,
        "_create_method_storage_scope",
        new=lambda self: setattr(self, "_multiplexor_method_storage_scope", None),  # type: ignore
    )


def _create_process_method_runner(
    settings: Settings,
    access_token: str | None = None,
    user_id: str | None = None,
) -> ProcessMethodRunner:
    return ProcessMethodRunner(
        project_id="project_fake",
        solution=None,  # pyright: ignore[reportArgumentType]
        method_url=_FAKE_TRANSACTION_URL,
        settings=settings,
        instance_system_factory=None,  # pyright: ignore[reportArgumentType]
        multiplexor_storage_factory=None,  # pyright: ignore[reportArgumentType]
        oidc_client=None,  # pyright: ignore[reportArgumentType]
        access_token=access_token,
        user_id=user_id,
    )


def _create_thread_method_runner(
    settings: Settings,
    access_token: str | None = None,
    user_id: str | None = None,
) -> ThreadMethodRunner:
    http_client = httpx2.Client(headers={"shared-volume": "true"})
    graphql_client = GqlClientConnectionPool("fake_url")
    return ThreadMethodRunner(
        project_id="project_fake",
        solution=None,  # pyright: ignore[reportArgumentType]
        method_url=_FAKE_TRANSACTION_URL,
        settings=settings,
        instance_system_factory=None,  # pyright: ignore[reportArgumentType]
        http_client=http_client,
        graphql_client=graphql_client,  # pyright: ignore[reportArgumentType]
        multiplexor_storage_factory=None,  # pyright: ignore[reportArgumentType]
        oidc_client=None,  # pyright: ignore[reportArgumentType]
        access_token=access_token,
        user_id=user_id,
    )


async def _invoke_with_mocked_executor(runner: MethodRunner, run_method_return: list[int] | None) -> None:
    runner.run_method = mock.Mock(return_value=run_method_return)

    async def fake_run_in_executor(
        executor: Executor,
        fn: Callable[[], Any],
    ):  # pyright: ignore[reportUnknownParameterType]
        return fn()  # pyright: ignore[reportUnknownVariableType]

    with mock.patch.object(asyncio.get_running_loop(), "run_in_executor", side_effect=fake_run_in_executor):
        await runner.invoke(
            crud=mock.AsyncMock(),  # pyright: ignore[reportArgumentType]
            background_tasks=mock.Mock(),  # pyright: ignore[reportArgumentType]
        )


@pytest.mark.parametrize(
    "settings",
    [
        {
            "glow_method_log_config": Path(__file__).parent.parent
            / "mocks"
            / "logging_configs"
            / "method_runner_config_to_file.yaml",
        },
    ],
    ids=["with_method_log_file"],
    indirect=True,
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
def test_process_method_runner_sets_correct_log_file(settings: Settings, mocker: pytest_mock.MockerFixture):
    logging_info_mock = mocker.patch.object(logging.Logger, "info")
    mocker.patch.object(logging.config, "dictConfig")
    mocker.patch.object(Instrumentor, "_instance", return_value=None, new_callable=mock.PropertyMock)

    method_runner = _create_process_method_runner(settings)
    method_runner.run_method()

    log_line = [
        args[0][0] for args in logging_info_mock.call_args_list if "GLOW METHOD RUNNER logging to" in args[0][0]
    ]
    log_path = Path(log_line[0].split("logging to ")[-1].strip())
    assert log_path.stem.startswith("log_transaction_fake")


@pytest.mark.parametrize(
    (
        "settings",
        "access_token",
        "expected_http_header",
        "expected_http_header_value",
        "expected_gql_attr",
        "expected_gql_value",
    ),
    [
        (
            {"glow_api_key": "configured-api-key"},
            "incoming-user-token",
            "x-api-key",
            "configured-api-key",
            "api_key",
            "configured-api-key",
        ),
        (
            {"glow_api_key": None},
            "incoming-user-token",
            "Authorization",
            "Bearer incoming-user-token",
            "access_token",
            "incoming-user-token",
        ),
        ({"glow_api_key": None}, None, None, None, None, None),
    ],
    ids=["api_key_over_access_token", "access_token_used_without_api_key", "no_auth_token"],
    indirect=["settings"],
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
def test_process_method_runner_prefers_api_key_for_internal_requests(
    settings: Settings,
    access_token: str | None,
    expected_http_header: str | None,
    expected_http_header_value: str | None,
    expected_gql_attr: str | None,
    expected_gql_value: str | None,
):
    runner = _create_process_method_runner(settings, access_token=access_token)
    if expected_http_header:
        assert runner.http_client.headers.get(expected_http_header) == expected_http_header_value
    else:
        assert runner.http_client.headers.get("x-api-key") is None
        assert runner.http_client.headers.get("Authorization") is None
    if expected_gql_attr:
        assert getattr(runner.graphql_client, expected_gql_attr) == expected_gql_value
    else:
        assert runner.graphql_client.api_key is None
        assert runner.graphql_client.access_token is None


@pytest.mark.parametrize(
    (
        "settings",
        "access_token",
        "expected_http_header",
        "expected_http_header_value",
        "expected_gql_attr",
        "expected_gql_value",
    ),
    [
        (
            {"glow_api_key": "configured-api-key"},
            "incoming-user-token",
            "x-api-key",
            "configured-api-key",
            "api_key",
            "configured-api-key",
        ),
        (
            {"glow_api_key": None},
            "incoming-user-token",
            "Authorization",
            "Bearer incoming-user-token",
            "access_token",
            "incoming-user-token",
        ),
        ({"glow_api_key": None}, None, None, None, None, None),
    ],
    ids=["api_key_over_access_token", "access_token_used_without_api_key", "no_auth_token"],
    indirect=["settings"],
)
@pytest.mark.parametrize("mock_method_runner_internals", [ThreadMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
def test_thread_method_runner_prefers_api_key_for_internal_requests(
    settings: Settings,
    access_token: str | None,
    expected_http_header: str | None,
    expected_http_header_value: str | None,
    expected_gql_attr: str | None,
    expected_gql_value: str | None,
):
    runner = _create_thread_method_runner(settings, access_token=access_token)
    if expected_http_header:
        assert runner.http_client.headers.get(expected_http_header) == expected_http_header_value
    else:
        assert runner.http_client.headers.get("x-api-key") is None
        assert runner.http_client.headers.get("Authorization") is None
    if expected_gql_attr:
        assert getattr(runner.graphql_client, expected_gql_attr) == expected_gql_value
    else:
        assert runner.graphql_client.api_key is None
        assert runner.graphql_client.access_token is None


@pytest.mark.parametrize(
    ("settings", "user_id", "expected_header"),
    [
        ({"glow_api_key": "configured-api-key"}, "alice", "alice"),
        ({"glow_api_key": "configured-api-key"}, None, None),
        ({"glow_api_key": None}, "alice", None),
    ],
    ids=["api_key_with_user", "api_key_without_user", "no_api_key"],
    indirect=["settings"],
)
@pytest.mark.parametrize("runner_cls", [ProcessMethodRunner, ThreadMethodRunner])
def test_runner_sends_on_behalf_of_header(
    settings: Settings,
    runner_cls: type[MethodRunner],
    user_id: str | None,
    expected_header: str | None,
    mocker: pytest_mock.MockerFixture,
):
    for name in (
        "_run_method",
        "_set_method_state",
        "_get_transaction_step_method",
        "_raise_method_event",
        "_init_data_repository",
        "_init_hps_blob_manager",
    ):
        mocker.patch.object(runner_cls, name)
    mocker.patch.object(
        runner_cls,
        "_create_method_storage_scope",
        new=lambda self: setattr(self, "_multiplexor_method_storage_scope", None),  # type: ignore
    )
    runner = (
        _create_process_method_runner(settings, access_token="incoming-user-token", user_id=user_id)
        if runner_cls is ProcessMethodRunner
        else _create_thread_method_runner(settings, access_token="incoming-user-token", user_id=user_id)
    )

    assert runner.http_client.headers.get(ON_BEHALF_OF_HEADER) == expected_header
    if expected_header:
        assert runner.http_client.headers.get("x-api-key") == "configured-api-key"
        assert runner.graphql_client.on_behalf_of == expected_header


@pytest.mark.parametrize("mock_method_runner_internals", [ThreadMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
def test_thread_method_runner_run_method_returns_none(settings: Settings):
    runner = _create_thread_method_runner(settings)
    result = runner.run_method()
    assert result is None


@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
def test_process_method_runner_run_method_returns_child_pids(settings: Settings, mocker: pytest_mock.MockerFixture):
    fake_children = [mock.Mock(pid=111), mock.Mock(pid=222)]

    mock_process_cls = mocker.patch("psutil.Process")
    mock_process_cls.return_value.children.return_value = fake_children
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")

    runner = _create_process_method_runner(settings)
    result = runner.run_method()

    assert result == [111, 222]
    expected_log_message = (
        "Tracking child PIDs at end of transaction: %s. Will allow them to terminate gracefully before forcing cleanup."
    )
    mock_logger.debug.assert_any_call(expected_log_message, [111, 222])


@pytest.mark.parametrize(
    "settings",
    [{"glow_method_cleanup_child_procs": True}],
    ids=["cleanup_enabled"],
    indirect=True,
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
async def test_invoke_calls_kill_pids_when_cleanup_enabled_and_alive_pids_returned(
    settings: Settings,
    mocker: pytest_mock.MockerFixture,
):
    runner = _create_process_method_runner(settings)

    mock_kill = mocker.patch("ansys.saf.glow._executor.method_runner.kill_pids")
    mock_pid_exists = mocker.patch("ansys.saf.glow._executor.method_runner.psutil.pid_exists", return_value=True)
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")
    await _invoke_with_mocked_executor(runner, run_method_return=[100, 200])

    mock_pid_exists.assert_has_calls([mock.call(100), mock.call(200)])
    mock_kill.assert_called_once_with([100, 200], timeout=1.0)
    mock_logger.info.assert_called_once_with(
        "Cleaning up child process(es) still alive after transaction: %s",
        [100, 200],
    )
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "settings",
    [{"glow_method_cleanup_child_procs": True}],
    ids=["cleanup_enabled"],
    indirect=True,
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
async def test_invoke_does_not_kill_pids_when_cleanup_enabled_and_no_alive_pids(
    settings: Settings,
    mocker: pytest_mock.MockerFixture,
):
    runner = _create_process_method_runner(settings)

    mock_kill = mocker.patch("ansys.saf.glow._executor.method_runner.kill_pids")
    mock_pid_exists = mocker.patch("ansys.saf.glow._executor.method_runner.psutil.pid_exists", return_value=False)
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")
    await _invoke_with_mocked_executor(runner, run_method_return=[100, 200])

    mock_pid_exists.assert_has_calls([mock.call(100), mock.call(200)])
    mock_kill.assert_not_called()
    mock_logger.info.assert_not_called()
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "settings",
    [{"glow_method_cleanup_child_procs": True}],
    ids=["cleanup_enabled"],
    indirect=True,
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
async def test_invoke_only_kills_alive_pids_when_mix_of_alive_and_dead(
    settings: Settings,
    mocker: pytest_mock.MockerFixture,
):
    runner = _create_process_method_runner(settings)

    mock_kill = mocker.patch("ansys.saf.glow._executor.method_runner.kill_pids")
    mock_pid_exists = mocker.patch(
        "ansys.saf.glow._executor.method_runner.psutil.pid_exists",
        side_effect=lambda pid: pid != 100,  # pyright: ignore[reportUnknownLambdaType]
    )
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")
    await _invoke_with_mocked_executor(runner, run_method_return=[100, 200, 300])

    mock_kill.assert_called_once_with([200, 300], timeout=1.0)
    mock_pid_exists.assert_has_calls([mock.call(100), mock.call(200), mock.call(300)])
    mock_logger.info.assert_called_once_with(
        "Cleaning up child process(es) still alive after transaction: %s",
        [200, 300],
    )
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "settings",
    [{"glow_method_cleanup_child_procs": False}],
    ids=["cleanup_disabled"],
    indirect=True,
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
async def test_invoke_logs_warning_when_cleanup_disabled_and_pids_alive(
    settings: Settings,
    mocker: pytest_mock.MockerFixture,
):
    runner = _create_process_method_runner(settings)

    mock_kill = mocker.patch("ansys.saf.glow._executor.method_runner.kill_pids")
    mock_pid_exists = mocker.patch("ansys.saf.glow._executor.method_runner.psutil.pid_exists", return_value=True)
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")
    await _invoke_with_mocked_executor(runner, run_method_return=[100, 200])

    mock_pid_exists.assert_has_calls([mock.call(100), mock.call(200)])
    mock_kill.assert_not_called()
    mock_logger.info.assert_not_called()
    mock_logger.warning.assert_called_once_with(
        "Child process cleanup is disabled. PIDs still alive after transaction: %s",
        [100, 200],
    )


@pytest.mark.parametrize(
    "settings",
    [{"glow_method_cleanup_child_procs": False}],
    ids=["cleanup_disabled"],
    indirect=True,
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
async def test_invoke_no_warning_when_cleanup_disabled_and_no_pids_alive(
    settings: Settings,
    mocker: pytest_mock.MockerFixture,
):
    runner = _create_process_method_runner(settings)

    mock_kill = mocker.patch("ansys.saf.glow._executor.method_runner.kill_pids")
    mock_pid_exists = mocker.patch("ansys.saf.glow._executor.method_runner.psutil.pid_exists", return_value=False)
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")
    await _invoke_with_mocked_executor(runner, run_method_return=[100, 200])

    mock_pid_exists.assert_has_calls([mock.call(100), mock.call(200)])
    mock_kill.assert_not_called()
    mock_logger.info.assert_not_called()
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "settings",
    [{"glow_method_cleanup_child_procs": True}],
    ids=["cleanup_enabled"],
    indirect=True,
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
async def test_invoke_skips_cleanup_when_run_method_returns_none(settings: Settings, mocker: pytest_mock.MockerFixture):
    runner = _create_process_method_runner(settings)

    mock_kill = mocker.patch("ansys.saf.glow._executor.method_runner.kill_pids")
    mock_pid_exists = mocker.patch("ansys.saf.glow._executor.method_runner.psutil.pid_exists")
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")
    await _invoke_with_mocked_executor(runner, run_method_return=None)

    mock_pid_exists.assert_not_called()
    mock_kill.assert_not_called()
    mock_logger.info.assert_not_called()
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "settings",
    [{"glow_method_cleanup_child_procs": True}],
    ids=["cleanup_enabled"],
    indirect=True,
)
@pytest.mark.parametrize("mock_method_runner_internals", [ProcessMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
async def test_invoke_skips_cleanup_when_run_method_returns_empty_list(
    settings: Settings,
    mocker: pytest_mock.MockerFixture,
):
    runner = _create_process_method_runner(settings)

    mock_kill = mocker.patch("ansys.saf.glow._executor.method_runner.kill_pids")
    mock_pid_exists = mocker.patch("ansys.saf.glow._executor.method_runner.psutil.pid_exists")
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")
    await _invoke_with_mocked_executor(runner, run_method_return=[])

    mock_pid_exists.assert_not_called()
    mock_kill.assert_not_called()
    mock_logger.info.assert_not_called()
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize("mock_method_runner_internals", [ThreadMethodRunner], indirect=True)
@pytest.mark.usefixtures("mock_method_runner_internals")
async def test_thread_method_runner_invoke_skips_cleanup(settings: Settings, mocker: pytest_mock.MockerFixture):
    runner = _create_thread_method_runner(settings)

    mock_kill = mocker.patch("ansys.saf.glow._executor.method_runner.kill_pids")
    mock_pid_exists = mocker.patch("ansys.saf.glow._executor.method_runner.psutil.pid_exists")
    mock_logger = mocker.patch("ansys.saf.glow._executor.method_runner.logger")
    await _invoke_with_mocked_executor(runner, run_method_return=None)

    mock_pid_exists.assert_not_called()
    mock_kill.assert_not_called()
    mock_logger.info.assert_not_called()
    mock_logger.warning.assert_not_called()
