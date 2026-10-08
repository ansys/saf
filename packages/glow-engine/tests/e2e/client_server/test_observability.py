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
import json
import time

import httpx2
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import NotFoundException
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, OTELconsole, ProjectFixture
from tests.mocks.solutions.minimal_solution import MinimalSolution

pytestmark = pytest.mark.parametrize("solution_type", [MinimalSolution], indirect=True)


@pytest.fixture(scope="module")
def export_otlp_to_console(session_glow: GlowBaseProcess[MinimalSolution]) -> Generator[None, None, None]:
    session_glow.change_configuration(OTELconsole)
    yield
    session_glow.configure_default_execution()


@pytest.mark.usefixtures("export_otlp_to_console")
def test_metrics_registered_and_exported(session_glow: GlowBaseProcess[MinimalSolution]):
    httpx2.get(f"{session_glow.base_api_url}/projects").raise_for_status()

    found_metrics = False
    num_tries = 0
    while not found_metrics and num_tries < 120:
        # Metrics are periodically exported. By default, PeriodicExportingMetricReader has an interval of 60 seconds
        found_metrics = any("resource_metrics" in line for line in session_glow.api_output)
        num_tries += 1
        time.sleep(1)
    assert found_metrics

    api_output = "".join([line.strip() for line in session_glow.api_output[1:]])
    if api_output[0] != "{":  # weirdly, sometimes the output seems to be truncated and missing the initial {
        api_output = "{" + api_output
    otlp_content = json.loads("[" + api_output.replace("}{", "}, {") + "]")
    metrics = [otlp_msg for otlp_msg in otlp_content if "resource_metrics" in otlp_msg][0]

    # find custom GLOW metrics and the request done in each one
    glow_metrics = [
        metric for metric in metrics["resource_metrics"][0]["scope_metrics"] if metric["scope"]["name"] == "GLOW API"
    ]
    assert glow_metrics

    status_code_metric = [
        metric for metric in glow_metrics[0]["metrics"] if metric["name"] == "http.server.status_code"
    ]
    assert status_code_metric
    assert [
        data_point
        for data_point in status_code_metric[0]["data"]["data_points"]
        if data_point["attributes"]["path"] == "/projects"
    ]

    duration_metric = [metric for metric in glow_metrics[0]["metrics"] if metric["name"] == "http.server.duration"]
    assert duration_metric
    assert [
        data_point
        for data_point in duration_metric[0]["data"]["data_points"]
        if data_point["attributes"]["path"] == "/projects"
    ]


@retry(stop=stop_after_attempt(50), wait=wait_fixed(0.2))
def _find_error(session_glow: GlowBaseProcess[MinimalSolution]) -> None:
    if not session_glow.text_in_output('"severity_text": "ERROR"', "api"):
        raise TryAgain


@pytest.mark.usefixtures("export_otlp_to_console")
def test_glow_error_exported(
    session_glow: GlowBaseProcess[MinimalSolution],
    function_project: ProjectFixture[MinimalSolution],
):
    """Test that raised exception are properly propagated to otel traces."""
    with pytest.raises(NotFoundException):
        _ = function_project.client.get_project("wrong_id").project_display_name
    _find_error(session_glow)
    assert session_glow.text_in_output('"body": "404: Not Found"', "api")
    assert session_glow.text_in_output('"exception.message": "404: Not Found"', "api")
    assert session_glow.text_in_output('"exception.type": "starlette.exceptions.HTTPException"', "api")
    assert session_glow.text_in_output('"exception.stacktrace": "Traceback (most recent call last):', "api")
