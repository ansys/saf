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

import pytest

from ansys.saf.glow._utilities.ip_utilities import port_is_free
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DefaultUIDebug,
    EnvVarUIDebug,
    EnvVarUINoDebug,
    GlowBaseProcess,
    UIDebugConfiguration,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_ui,
    pytest.mark.parametrize("ui_enabled", [True], indirect=True),
    pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    ),
]


@pytest.fixture(scope="class")
def ui_debug_mode(
    session_glow: GlowBaseProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param, debug_port=None)


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    "Always exit debug mode after the module is finished."
    yield
    session_glow.configure_default_execution()


@pytest.mark.parametrize(
    "ui_debug_mode",
    [
        DefaultUIDebug,
        EnvVarUIDebug,
        EnvVarUINoDebug,
    ],
    indirect=True,
)
def test_debug_port(session_glow: GlowBaseProcess[EndToEndSolution], ui_debug_mode: UIDebugConfiguration):
    """
    Test ui debug port is opened when UI is running on debug mode.

    Note: this test does nothing for Docker, since mapping the container debug port to a host port will result in the
    port being used regardless of whether debug mode was activated or not.
    """
    if isinstance(ui_debug_mode, DefaultUIDebug | EnvVarUINoDebug):
        assert not session_glow.ui_debugpy_port
        return

    # GLOW is successfully using a debugpy port and it's shown in the log
    assert session_glow.ui_debugpy_port

    # GLOW is using the expected port if configured
    # If no port is configured, GLOW will use the first free port starting from 5724
    if ui_debug_mode.debug_port:
        assert session_glow.ui_debugpy_port == ui_debug_mode.debug_port

    # Port is busy
    assert not port_is_free(session_glow.ui_debugpy_port)
