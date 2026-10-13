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
from typing import TypeVar

from fastapi import status
import httpx2
import pytest

from ansys.saf.glow.solution import Solution
from ansys.saf.testing.solution.end_to_end import (
    DefaultDebug,
    DefaultUIDebug,
    EnvVarDebug,
    EnvVarUIDebug,
    GlowDesktopProcess,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_second_end_to_end.solution.definition import SecondSolution

pytestmark = [pytest.mark.use_ui, pytest.mark.parametrize("ui_enabled", [True], indirect=True)]

T = TypeVar("T", bound=Solution)


def verify_diff_glow_processes(
    glow_proc_1: GlowDesktopProcess[T],
    glow_proc_2: GlowDesktopProcess[T],
    expected_solution_names: list[str],
    debug_mode: bool,
):
    # process IDs
    assert glow_proc_1.api_process
    assert glow_proc_2.api_process
    assert glow_proc_1.api_process.pid != glow_proc_2.api_process.pid
    assert glow_proc_1.ui_process
    assert glow_proc_2.ui_process
    assert glow_proc_1.ui_process.pid != glow_proc_2.ui_process.pid

    # solution name
    solution_name_1 = httpx2.get(f"{glow_proc_1.base_api_url}/schema").json()["title"]
    solution_name_2 = httpx2.get(f"{glow_proc_2.base_api_url}/schema").json()["title"]
    assert solution_name_1 == expected_solution_names[0]
    assert solution_name_2 == expected_solution_names[1]

    # ports
    assert glow_proc_1.solution_api_port != glow_proc_2.solution_api_port
    assert glow_proc_1.solution_ui_port != glow_proc_2.solution_ui_port

    # debugpy port
    if debug_mode:
        assert glow_proc_1.debugpy_port != glow_proc_2.debugpy_port
        assert glow_proc_1.ui_debugpy_port != glow_proc_2.ui_debugpy_port


def verify_create_glow_projects(
    glow_proc_1: GlowDesktopProcess[T],
    glow_proc_2: GlowDesktopProcess[T],
    same_solution: bool,
    random_project_name: Callable[[], str],
):
    project_display_name_1 = random_project_name()
    project_display_name_2 = random_project_name()
    response_1 = httpx2.post(f"{glow_proc_1.base_api_url}/projects", json={"display_name": project_display_name_1})
    response_2 = httpx2.post(f"{glow_proc_2.base_api_url}/projects", json={"display_name": project_display_name_2})

    assert response_1.status_code == status.HTTP_200_OK
    project_1 = response_1.json()
    assert response_2.status_code == status.HTTP_200_OK
    project_2 = response_2.json()
    projects_after_1 = httpx2.get(f"{glow_proc_1.base_api_url}/projects").json()["projects"]
    projects_after_2 = httpx2.get(f"{glow_proc_2.base_api_url}/projects").json()["projects"]

    if same_solution:
        assert project_1 in projects_after_1
        assert project_1 in projects_after_2
        assert project_2 in projects_after_1
        assert project_2 in projects_after_2
    else:
        assert project_1 in projects_after_1
        assert project_1 not in projects_after_2
        assert project_2 in projects_after_2
        assert project_2 not in projects_after_1


def get_solution_second_end_to_end(glow_process: GlowDesktopProcess[T], same_solution: bool) -> type[T]:
    if same_solution:
        return glow_process.solution_type
    else:
        return [
            solution_type
            for solution_type in [EndToEndSolution, SecondSolution]
            if solution_type != glow_process.solution_type
        ][0]  # pyright: ignore[reportReturnType]


@pytest.mark.parametrize("same_solution", [True, False])
class TestConcurrency:
    @pytest.mark.parametrize("debug_mode", [True, False])
    def test_two_glow_processes(
        self,
        same_solution: bool,
        debug_mode: bool,
        run_glow: Callable[..., GlowDesktopProcess[T]],
        tmp_solutions_dir: dict[type[T], Path],
        random_project_name: Callable[[], str],
    ):
        """
        Test that GLOW supports concurrent instances.
        """
        # GIVEN - A running GLOW process, with DEBUG enabled/disabled

        first_glow_process = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], prevent_start=True)  # type: ignore
        first_glow_process.change_configuration(
            EnvVarDebug if debug_mode else DefaultDebug,
            restart=False,
            debug_port=None,
        )
        first_glow_process.change_configuration(
            EnvVarUIDebug if debug_mode else DefaultUIDebug,
            restart=False,
            debug_port=None,
        )
        first_glow_process.start()
        assert first_glow_process.healthy

        # WHEN - Trying to run a second GLOW process, with the same or different solution
        solution_second_end_to_end = get_solution_second_end_to_end(first_glow_process, same_solution)
        second_glow_process = run_glow(
            solution_second_end_to_end,
            tmp_solutions_dir[solution_second_end_to_end],
            prevent_start=True,
        )
        second_glow_process.change_configuration(
            EnvVarDebug if debug_mode else DefaultDebug,
            restart=False,
            debug_port=None,
        )
        second_glow_process.change_configuration(
            EnvVarUIDebug if debug_mode else DefaultUIDebug,
            restart=False,
            debug_port=None,
        )
        second_glow_process.start()
        assert second_glow_process.healthy

        # THEN - Both processes run successfully
        verify_diff_glow_processes(
            first_glow_process,
            second_glow_process,
            [first_glow_process.solution_name, second_glow_process.solution_name],
            debug_mode,
        )

        # WHEN - Creating a project in each process
        # THEN - Each project is created correctly and each process only lists the correct ones
        verify_create_glow_projects(first_glow_process, second_glow_process, same_solution, random_project_name)

    def test_two_glow_processes_same_ports(
        self,
        same_solution: bool,
        run_glow: Callable[[type[T], Path], GlowDesktopProcess[T]],
        tmp_solutions_dir: dict[type[T], Path],
    ):
        """
        Test that GLOW throws an error when attempting to use the same API / UI ports for separate instances.
        """
        # GIVEN - A running GLOW process
        first_glow_process = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution])  # type: ignore
        assert first_glow_process.healthy

        # WHEN - Trying to run a second GLOW process, with the same or different solution
        #        using the same API/UI ports
        solution_second_end_to_end = get_solution_second_end_to_end(first_glow_process, same_solution)
        second_glow_process = run_glow(  # type: ignore
            solution_second_end_to_end,
            tmp_solutions_dir[solution_second_end_to_end],
            solution_api_port=first_glow_process.solution_api_port,  # type: ignore
            solution_ui_port=first_glow_process.solution_ui_port,  # type: ignore
        )

        # THEN - Second GLOW process fails to run
        assert second_glow_process.text_in_output(  # type: ignore
            f"error while attempting to bind on address ('127.0.0.1', {first_glow_process.solution_api_port})",
            "api",  # type: ignore
        )
        if platform.system() != "Windows":
            # Dash doesn't raise an error in Windows when same port is used.
            # See https://community.plotly.com/t/two-apps-using-same-port-do-not-raise-any-error/40406
            assert second_glow_process.text_in_output(  # type: ignore
                f"Port {first_glow_process.solution_ui_port} is in use by another program.",
                "ui",  # type: ignore
            )

    def test_two_glow_processes_same_debugpy_port(
        self,
        same_solution: bool,
        run_glow: Callable[..., GlowDesktopProcess[T]],
        tmp_solutions_dir: dict[type[T], Path],
    ):
        """
        Test that GLOW throws an error when attempting to use the same debugpy port for separate instances.
        """
        # GIVEN - A running GLOW process with its own DEBUG and GLOW_DEBUG_API_PORT
        first_glow_process = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], prevent_start=True)  # type: ignore
        first_glow_process.change_configuration(EnvVarDebug, restart=False, debug_port=None)
        first_glow_process.change_configuration(EnvVarUIDebug, restart=False, debug_port=None)
        first_glow_process.start()

        assert first_glow_process.healthy

        debugpy_port = first_glow_process.debugpy_port
        ui_debugpy_port = first_glow_process.ui_debugpy_port

        # WHEN - Trying to run a second GLOW process, with the same or different solution, using the same debugpy ports
        solution_second_end_to_end = get_solution_second_end_to_end(first_glow_process, same_solution)
        second_glow_process = run_glow(
            solution_second_end_to_end,
            tmp_solutions_dir[solution_second_end_to_end],
            prevent_start=True,
        )
        second_glow_process.change_configuration(EnvVarDebug, restart=False, debug_port=debugpy_port)
        second_glow_process.change_configuration(EnvVarUIDebug, restart=False, debug_port=ui_debugpy_port)
        second_glow_process.start()

        # THEN - Second GLOW process fails to run
        assert second_glow_process.text_in_output("Can't listen for client connections", "api")
        assert second_glow_process.text_in_output("Can't listen for client connections", "ui")
