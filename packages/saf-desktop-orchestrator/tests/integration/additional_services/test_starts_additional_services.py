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

from pathlib import Path

import pytest

from ansys.saf.desktop.orchestrator._config.schema import Settings
from ansys.saf.desktop.orchestrator._orchestration.launcher import Launcher
from ansys.saf.desktop.orchestrator._orchestration.process import ServiceProcess  # noqa: TC001
from ansys.saf.desktop.orchestrator._orchestration.solution_ui_framework import SolutionUIFramework
from tests.integration.orchestration.test_orchestrator import verify_pid_not_exists


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_starts_additional_services():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=True,
        with_ui=True,
        ui_framework=SolutionUIFramework.streamlit,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )
    services_info = launcher.start_additional_services(Path(__file__).parent.absolute() / "additional_services.yaml")
    assert services_info is not None
    for service_info in services_info:
        # Verify service being running and responding.
        service = services_info[service_info]
        process: ServiceProcess = service.process
        process.wait_for_healthy()
        assert process.process is not None
        assert isinstance(process.process.pid, int)
        process.stop()
        # Verify that the process is no longer running.
        verify_pid_not_exists(process.process.pid)


def test_starts_additional_services_yaml_path_not_exist():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=True,
        with_ui=True,
        ui_framework=SolutionUIFramework.streamlit,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )
    services_info = launcher.start_additional_services(Path("additional_services_spec.yaml"))
    assert not services_info


def test_starts_additional_services_incorrect_yaml_syntax():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=True,
        with_ui=True,
        ui_framework=SolutionUIFramework.streamlit,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )
    services_info = launcher.start_additional_services(
        Path(__file__).parent.absolute() / "additional_services_spec_incorrect_syntax.yaml",
    )
    assert not services_info


def test_starts_additional_services_incorrect_yaml_keys():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=True,
        with_ui=True,
        ui_framework=SolutionUIFramework.streamlit,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )
    services_info = launcher.start_additional_services(
        Path(__file__).parent.absolute() / "additional_services_spec_incorrect_keys.yaml",
    )
    assert not services_info


def test_starts_additional_services_yaml_file_not_present():
    launcher = Launcher(
        Settings(saf_desktop_solution_name="solution"),
        solution_module_name="solution",
        definition_module_name="definition",
        with_pim=True,
        with_ui=True,
        ui_framework=SolutionUIFramework.streamlit,
        with_portal=True,
        env_file=None,
        enable_automatic_project_migration=False,
        log_to_files=False,
    )
    services_info = launcher.start_additional_services(
        Path(__file__).parent.absolute() / "additional_services_spec_incorrect.yaml",
    )
    assert not services_info
