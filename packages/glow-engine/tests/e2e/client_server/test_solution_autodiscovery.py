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
from ansys.saf.testing.solution.end_to_end import GlowDesktopProcess, get_solution_root_dir
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_second_end_to_end.solution.definition import SecondSolution

T = TypeVar("T", bound=Solution)


def test_saf_run_solution_autodiscovery(
    run_glow: Callable[[type[T], Path], GlowDesktopProcess[T]],
    tmp_solutions_dir: dict[type[T], Path],
):
    """
    Test that the solution autodiscovery finds the entrypoint given the solution src path.
    """
    solution_src_dir = get_solution_root_dir(tmp_solutions_dir[EndToEndSolution]) / "src"  # type: ignore

    with mock.patch.dict(
        os.environ,
        {"PYTHONPATH": os.pathsep.join(sys.path + [str(solution_src_dir)])},
    ):
        proc = run_glow(  # type: ignore
            EndToEndSolution,
            tmp_solutions_dir[EndToEndSolution],  # type: ignore
            use_automatic_solution_locator=True,  # type: ignore
        )
        assert proc.healthy  # type: ignore


def test_saf_run_solution_autodiscovery_with_multiple_solutions(
    run_glow: Callable[[type[T], Path], GlowDesktopProcess[T]],
    tmp_solutions_dir: dict[type[T], Path],
    caplog: pytest.LogCaptureFixture,
):
    """
    Test that the solution autodiscovery raises an Exception given multiple solutions entrypoints in path.
    """
    solutions_src_dir = [
        get_solution_root_dir(tmp_solutions_dir[EndToEndSolution]) / "src",  # type: ignore
        get_solution_root_dir(tmp_solutions_dir[SecondSolution]) / "src",  # type: ignore
    ]

    with mock.patch.dict(
        os.environ,
        {"PYTHONPATH": os.pathsep.join(sys.path + [str(solution_src_dir) for solution_src_dir in solutions_src_dir])},
    ):
        proc = run_glow(  # type: ignore
            EndToEndSolution,
            tmp_solutions_dir[EndToEndSolution],  # type: ignore
            use_automatic_solution_locator=True,  # type: ignore
        )
        assert not proc.healthy  # type: ignore
        expected_error_msg = (
            "Error: Detected multiple solution entry points in ansys.solutions module. "
            "Use the '--solution' option to specify the solution entry point module that should be utilized."
        )
        assert expected_error_msg in caplog.text
