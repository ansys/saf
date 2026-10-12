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
from pathlib import Path

import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from ansys.saf.testing.selenium import wait_for_element
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DebugConfiguration,
    DefaultDebug,
    EnvVarDebug,
    EnvVarNoDebug,
    GlowBaseProcess,
    GlowDesktopProcess,
    ProjectFixture,
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
def debug_mode(
    session_glow: GlowBaseProcess[EndToEndSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param)


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    "Always exit debug mode after the module is finished."
    yield
    session_glow.configure_default_execution(restart=False)
    if isinstance(session_glow, GlowDesktopProcess):
        session_glow.set_cwd(Path.cwd())
    session_glow.restart()


@pytest.mark.parametrize(
    "debug_mode",
    [
        DefaultDebug,
        EnvVarDebug,
        EnvVarNoDebug,
    ],
    indirect=True,
)
def test_dash_debug_tools_present(
    session_glow: GlowBaseProcess[EndToEndSolution],
    debug_mode: DebugConfiguration,
    function_project: ProjectFixture[EndToEndSolution],
    session_selenium_webdriver: WebDriver,
    deployment_type: TestDeployment,
):
    """
    Test dash debug tools are only present in debug mode (with UI debug disabled).
    """
    assert "ui_debug_configuration" not in session_glow.applied_configurations

    session_selenium_webdriver.get(function_project.ui_url)
    if isinstance(debug_mode, DefaultDebug | EnvVarNoDebug) or deployment_type == TestDeployment.DockerCompose:
        with pytest.raises(TimeoutException):
            wait_for_element(
                session_selenium_webdriver,
                "dash-debug-menu__outer",
                element_type=By.CLASS_NAME,
                timeout=1,
            )
    else:
        wait_for_element(session_selenium_webdriver, "dash-debug-menu__outer", element_type=By.CLASS_NAME)
