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

from typing import Any
from unittest.mock import patch

from grpc_health.v1 import (  # pyright: ignore[reportMissingTypeStubs]
    health_pb2,
)
import pytest
import pytest_mock

from ansys.saf.desktop.orchestrator._config.schema import (
    DEFAULT_SAF_DESKTOP_HEALTH_CHECK_TIMEOUT,
    HEALTH_CHECK_INTERVAL,
)
from ansys.saf.desktop.orchestrator._orchestration.additional_service_process import AdditionalServiceProcess
from ansys.saf.testing.platform_specific import skip_for_ci


def test_additional_service_process_wait_for_healthy_http():
    process = AdditionalServiceProcess(
        name="test_service",
        command_line_template="",
        health_check={"type": "HTTP", "route": "/health"},
        port=5678,
        ip="127.0.0.1",
    )
    with patch.object(process, "_http_health_check", return_value=True) as mock_http_health_check:
        process.wait_for_healthy()
        mock_http_health_check.assert_called_once_with("test_service")


def test_additional_service_process_wait_for_healthy_tcp():
    process = AdditionalServiceProcess(
        name="test_service",
        command_line_template="",
        health_check={"type": "TCP"},
        port=1234,
        ip="127.0.0.1",
    )
    with patch.object(process, "_tcp_health_check", return_value=True) as mock_tcp_health_check:
        process.wait_for_healthy()
        mock_tcp_health_check.assert_called_once_with("test_service")


def test_additional_service_process_wait_for_healthy_grpc():
    process = AdditionalServiceProcess(
        name="test_service",
        command_line_template="",
        health_check={"type": "GRPC"},
        port=5678,
        ip="127.0.0.1",
    )
    with patch.object(process, "_grpc_health_check", return_value=True) as mock_grpc_health_check:
        process.wait_for_healthy()
        mock_grpc_health_check.assert_called_once_with("test_service")


@skip_for_ci(reason="Test relying on timing is flaky in CI environments.")
@pytest.mark.parametrize(("service_type", "service_port"), [("HTTP", 5678), ("GRPC", 5678), ("TCP", 1234)])
@pytest.mark.parametrize(("health_timeout"), [None, 5])
def test_infinite_additional_service_process_with_custom_health_check_timeout(
    service_port: int,
    service_type: str,
    health_timeout: int | None,
    mocker: pytest_mock.MockerFixture,
):
    if service_type == "TCP":
        mock_health_check = mocker.patch(
            "src.ansys.saf.desktop.orchestrator._orchestration.process.socket.socket",
        )
        mock_health_check.return_value.__enter__.return_value.connect.side_effect = OSError("Connection failed")

    elif service_type == "HTTP":
        mock_health_check = mocker.patch(
            "src.ansys.saf.desktop.orchestrator._orchestration.process.httpx2.get",
        )
        mock_health_check.return_value.status_code = 404
    else:
        mock_health_check = mocker.patch(
            "src.ansys.saf.desktop.orchestrator._orchestration.process.health_pb2_grpc.HealthStub",
        )
        mock_health_check.return_value.Check.return_value.status = health_pb2.HealthCheckResponse.NOT_SERVING

    process_args: dict[str, Any] = {
        "name": "test_service",
        "command_line_template": "",
        "health_check": {"type": service_type, "route": "/health"},
        "port": service_port,
        "ip": "127.0.0.1",
    }

    if health_timeout:
        process_args["health_check_timeout"] = health_timeout

    process = AdditionalServiceProcess(**process_args)

    timeout_applied = health_timeout or DEFAULT_SAF_DESKTOP_HEALTH_CHECK_TIMEOUT
    expected_retries = timeout_applied / HEALTH_CHECK_INTERVAL

    process.wait_for_healthy()
    assert mock_health_check.call_count == expected_retries
