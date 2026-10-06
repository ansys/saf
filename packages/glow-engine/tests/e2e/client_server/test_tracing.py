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

from collections.abc import Generator
import time

import pytest

from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    EnvVarDebug,
    EnvVarUIDebug,
    GlowBaseProcess,
    OTELconsole,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


@pytest.fixture(scope="class", autouse=True)
def tracing_configuration(
    session_glow: GlowBaseProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param)


@pytest.fixture(scope="module", autouse=True)
def module_setup_and_teardown(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    "Need to return session_glow back to the default state."
    # not mandatory for enabling OTEL, but we use them to test that it is compatible
    # avoid restarts, configuration will be applied in tracing_configuration fixture
    session_glow.change_configuration(EnvVarDebug, restart=False)
    session_glow.change_configuration(EnvVarUIDebug, restart=False)

    yield

    session_glow.configure_default_execution()


@pytest.mark.parametrize("tracing_configuration", [OTELconsole], indirect=True)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestOtlpGlow:
    def test_traces_exported(self, session_glow: GlowBaseProcess[EndToEndSolution]):
        """
        Find an attribute that only appears in span messages. Example:
        {
            "name": "GET /health http send",
            "context": {
                "trace_id": "0xc2f7f4d52f4a3689573907958380d539",
                "span_id": "0x284576d613784bb7",
                "trace_state": "[]",
            },
            "kind": "SpanKind.INTERNAL",
            "parent_id": "0xd58c09a887884c39",
            "start_time": "2023-11-02T08:01:19.851809Z",
            "end_time": "2023-11-02T08:01:19.851809Z",
            "status": {
                "status_code": "UNSET",
            },
            "attributes": {
                "type": "http.response.body",
            },
            "events": [],
            "links": [],
            "resource": {
                "attributes": {
                    "telemetry.sdk.language": "python",
                    "telemetry.sdk.name": "opentelemetry",
                    "telemetry.sdk.version": "1.20.0",
                    "service.name": "GLOW API",
                    "service.version": "1.0.dev0",
                    "service.namespace": "ansys.saf.glow",
                },
                "schema_url": "",
            }
        }
        """
        found = False
        num_tries = 0
        while not found and num_tries < 100:
            found = session_glow.text_in_output('"kind": "SpanKind.INTERNAL"', "api")
            num_tries += 1
            time.sleep(0.1)
        assert found

    @pytest.mark.usefixtures("log_something")
    def test_logs_exported(self, session_glow: GlowBaseProcess[EndToEndSolution]):
        """
        Find an attribute that only appears in log messages. Example:
        {
            "body": "Running GLOW API server on http://127.0.0.1:55886",
            "severity_number": "<SeverityNumber.INFO: 9>",
            "severity_text": "INFO",
            "attributes": {
                "otelSpanID": "0",
                "otelTraceID": "0",
                "otelTraceSampled": false,
                "otelServiceName": "GLOW API",
            },
            "dropped_attributes": 0,
            "timestamp": "2023-11-02T08:01:19.113653Z",
            "trace_id": "0x00000000000000000000000000000000",
            "span_id": "0x0000000000000000",
            "trace_flags": 0,
            "resource": "BoundedAttributes({
                'telemetry.sdk.language': 'python',
                'telemetry.sdk.name': 'opentelemetry'
                 'telemetry.sdk.version': '1.20.0',
                 'service.name': 'GLOW API',
                 'service.version': '1.0.dev0',
                 'service.namespace': 'ansys.saf.glow'}, maxlen=None)"
        }
        """
        found = False
        num_tries = 0
        while not found and num_tries < 100:
            found = session_glow.text_in_output('"severity_text": "INFO"', "api")
            num_tries += 1
            time.sleep(0.1)
        assert found
