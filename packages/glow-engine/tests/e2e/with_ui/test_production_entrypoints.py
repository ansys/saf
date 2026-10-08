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
import os
from pathlib import Path
import sys
from typing import TypeVar
from unittest import mock

import pytest

from ansys.saf.glow.solution import Solution
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, get_solution_root_dir
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_second_end_to_end.solution.definition import SecondSolution

pytestmark = [pytest.mark.use_ui, pytest.mark.parametrize("ui_enabled", [True], indirect=True)]
T = TypeVar("T", bound=Solution)


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    # Don't create in pytest's CWD. Even if we unlink it at the end, that CWD is shared by all pytest workers
    # and it would affect their GLOW procs.
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GLOW_SOLUTION_DEFINITION='tests.mocks.solution_end_to_end.solution.definition'\n"
        "GLOW_UI_MODULE='tests.mocks.solution_end_to_end.ui.app'\n"
        "GLOW_API_PORT='5434'\n"
        "GLOW_UI_PORT='5435'\n",
    )
    return env_file


class TestProductionEntrypoints:
    @pytest.mark.parametrize(
        "deployment_type",
        ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
        indirect=True,
    )
    def test_api_and_ui(
        self,
        run_glow_production: Callable[[type[T], Path], GlowBaseProcess[T]],
        tmp_solutions_dir: dict[type[T], Path],
    ):
        """
        Test that the GLOW API and UI can be run directly using a production server.
        """
        # TODO: production servers always need the solution to be in in their sys.path.
        # We should move this to GlowProductionProcess, so we avoid this code duplication in every test.
        solution_src_dir = get_solution_root_dir(tmp_solutions_dir[EndToEndSolution]) / "src"  # type: ignore

        with mock.patch.dict(
            os.environ,
            {"PYTHONPATH": os.pathsep.join(sys.path + [str(solution_src_dir)])},
        ):
            glow_proc = run_glow_production(EndToEndSolution, tmp_solutions_dir[EndToEndSolution])  # type: ignore
            assert glow_proc.healthy

    def test_api_and_ui_using_solution_autodiscovery(
        self,
        run_glow_production: Callable[[type[T], Path], GlowBaseProcess[T]],
        tmp_solutions_dir: dict[type[T], Path],
    ):
        """
        Test that the GLOW API can be run directly using uvicorn and letting the solution autodiscovery work.
        """
        solution_src_dir = get_solution_root_dir(tmp_solutions_dir[EndToEndSolution]) / "src"  # type: ignore

        with mock.patch.dict(
            os.environ,
            {"PYTHONPATH": os.pathsep.join(sys.path + [str(solution_src_dir)])},
        ):
            glow_proc = run_glow_production(  # type: ignore
                EndToEndSolution,
                tmp_solutions_dir[EndToEndSolution],  # type: ignore
                use_automatic_solution_locator=True,  # type: ignore
            )
            assert glow_proc.healthy  # type: ignore
            assert glow_proc.glow_api_process._use_automatic_solution_locator  # type: ignore
            assert glow_proc.glow_ui_process._use_automatic_solution_locator  # type: ignore

    @pytest.mark.timeout(1500, func_only=True)
    def test_api_and_ui_using_solution_autodiscovery_with_multiple_solutions(
        self,
        run_glow_production: Callable[[type[T], Path], GlowBaseProcess[T]],
        tmp_solutions_dir: dict[type[T], Path],
        caplog: pytest.LogCaptureFixture,
    ):
        """
        Test that autodiscovery will fail if it finds multiple solutions when running glow with production servers.
        """
        solutions_src_dir = [
            get_solution_root_dir(tmp_solutions_dir[EndToEndSolution]) / "src",  # type: ignore
            get_solution_root_dir(tmp_solutions_dir[SecondSolution]) / "src",  # type: ignore
        ]

        with mock.patch.dict(
            os.environ,
            {
                "PYTHONPATH": os.pathsep.join(
                    sys.path + [str(solution_src_dir) for solution_src_dir in solutions_src_dir],
                ),
            },
        ):
            proc = run_glow_production(  # type: ignore
                EndToEndSolution,
                tmp_solutions_dir[EndToEndSolution],  # type: ignore
                use_automatic_solution_locator=True,  # type: ignore
            )
            assert not proc.glow_api_process.healthy  # type: ignore
            assert not proc.glow_ui_process.healthy  # type: ignore
            assert not proc.healthy  # type: ignore
            expected_error_msg = (
                "Error: Detected multiple solution entry points in ansys.solutions module. "
                "Use the '--solution' option to specify the solution entry point module that should be utilized."
            )
            assert expected_error_msg in caplog.text
