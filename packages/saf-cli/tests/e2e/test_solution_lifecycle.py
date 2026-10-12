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

from collections.abc import Callable
from pathlib import Path
import platform
import random
import tempfile

from dotenv import set_key
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_NAMESPACE
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._utilities.conversion import to_module_name
from ansys.saf.testing.network import get_random_free_port
from tests.e2e.conftest import (
    BuildSolution,
    InstallSolution,
    InstallSolutionExecutable,
    ListSolutions,
    NewSolution,
    RunInstalledSolution,
    RunSolution,
    add_extra_packages_to_solution,
    check_api_is_functional,
    check_expected_messages,
    check_solution_launched_correctly,
    check_ui_is_functional,
    get_shortcut_path,
    is_solution_registered,
    verify_generated_solution,
)
from tests.e2e.saf_process import SAFProcess
from tests.outcome_checks import check_built_solution_files, verify_installation

HOME_ENV_VAR = "PUBLIC" if platform.system() == "Windows" else "HOME"


# Don't use session_solution since the point of this test is to cover the whole lifecycle within it.
@pytest.mark.usefixtures("check_gtk_launch_and_xvfb_are_installed")
def test_solution_lifecycle(
    install_solution: InstallSolution,
    tmp_path: Path,
    list_solutions: ListSolutions,
    new_solution: NewSolution,
    run_solution: RunSolution,
    build_solution: BuildSolution,
    install_solution_executable: InstallSolutionExecutable,
    monkeypatch: pytest.MonkeyPatch,
    run_installed_solution: RunInstalledSolution,
    get_selenium_webdriver: Callable[[], WebDriver],
):
    """Test that a solution created, packaged and installed using the saf-cli can be run from the Desktop shortcut."""
    # GIVEN: Custom input parameters for a solution that does not yet exist.
    solution_id = str(random.randint(0, 1000)).zfill(4)
    solution_name = f"sol{solution_id}"
    solution_path = tmp_path / solution_name
    expected_solution_module_name = to_module_name(solution_name)
    solution_display_name = f"Sol{solution_id}"
    ui_framework = "dash"
    solution_namespace = random.choice([DEFAULT_SOLUTION_NAMESPACE, "ansys.solutions", "myorg.apps"])

    assert not is_solution_registered(list_solutions(), solution_path)
    assert not solution_path.is_dir()

    # WHEN: A solution is created with the saf-cli ``run`` command.
    new_solution(
        input_str=f"{solution_name}\n{solution_display_name}\n{ui_framework}\n{solution_namespace}\n",
        cwd=tmp_path,
    )

    # THEN: The solution is registered.
    verify_generated_solution(
        list_solutions(),
        tmp_path,
        solution_name,
        expected_solution_module_name,
        solution_display_name,
        ui_framework,
        solution_namespace,
    )

    # defining ports in the .env file so that services can be checked when using shortcut's pythonw
    env_file_path = tmp_path / solution_name / ".env"
    glow_api_port = str(get_random_free_port())
    glow_ui_port = str(get_random_free_port())
    portal_ui_port = str(get_random_free_port())
    set_key(env_file_path, "GLOW_API_PORT", glow_api_port)
    set_key(env_file_path, "GLOW_UI_PORT", glow_ui_port)
    set_key(env_file_path, "PORTAL_UI_PORT", portal_ui_port)

    # WHEN: The solution is installed with the saf-cli ``install`` command.
    dependency_groups: str = "desktop,ui,doc,build"
    install_solution([solution_name, "-d", dependency_groups])
    add_extra_packages_to_solution(solution_name, solution_path)

    # THEN: The desired dependency groups are installed and solution can run.
    verify_installation(
        solution_path,
        solution_namespace=solution_namespace,
        installed_groups=[str(group) for group in dependency_groups.split(",")],  # list[LiteralString] to list[str]
        check_poetry_cache=True,
        solution_name=solution_name,
    )
    p = run_solution([solution_name])
    assert isinstance(p, SAFProcess)
    # User gets expected messages
    check_expected_messages(p, solution_display_name)
    # Services are functional
    check_api_is_functional(p)
    check_ui_is_functional(get_selenium_webdriver(), p)
    p.stop()

    # WHEN: The solution is packaged with the saf-cli ``build`` command.
    p = build_solution([solution_name])
    # THEN: The installer is created.
    check_built_solution_files(
        SolutionRegistry(
            name=solution_name,
            root_dir=solution_path,
            display_name=solution_display_name,
        ),
        solution_namespace=solution_namespace,
        expect_private_wheels=True,  # added by add_extra_packages_to_solution
    )

    with monkeypatch.context() as mp:
        # use tempfile instead of pytest's fixture to get a shorter path and avoid long path issues
        # on Windows.
        solution_installation_path = tempfile.mkdtemp(prefix="saf-cli-test")
        temp_desktop_path = tmp_path / "home" / "Desktop"
        temp_desktop_path.mkdir(parents=True, exist_ok=True)
        mp.setenv(HOME_ENV_VAR, temp_desktop_path.parent.resolve().as_posix())

        # WHEN: The packaged solution is installed by executing the installer.
        installation_output = install_solution_executable(
            solution_path,
            Path(solution_installation_path),
            solution_display_name,
        )
        # THEN: The solution files are deployed and the Desktop shortcut is created
        shortcut_path = get_shortcut_path(solution_display_name)
        assert shortcut_path.is_file()
        assert any("Execution time:" in line for line in installation_output)

    # WHEN: The desktop shortcut is executed.
    run_installed_solution(shortcut_path)
    # THEN: The solution runs successfully and is healthy.
    project_ui_url = check_solution_launched_correctly(glow_api_port, glow_ui_port, portal_ui_port)
    check_ui_is_functional(get_selenium_webdriver(), project_ui_url=project_ui_url)
