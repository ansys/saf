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
import contextlib
from pathlib import Path
from typing import Any

import pytest

from ansys.saf.testing.platform_specific import windows_only
from tests.e2e.conftest import (
    BuildSolution,
    InstallSolution,
    SetupSolution,
    check_built_solution_files,
    find_msg_in_output,
    only_for_ci,
)


@pytest.fixture
def mock_long_paths_disabled() -> Callable[[], contextlib.AbstractContextManager[None]]:
    import winreg  # type: ignore  # conditional (Windows only)

    registry_path = "SYSTEM\\CurrentControlSet\\Control\\FileSystem"

    @contextlib.contextmanager
    def _cm():
        old_registry_value: Any = None
        try:
            with winreg.OpenKey(  # type: ignore
                winreg.HKEY_LOCAL_MACHINE,  # type: ignore
                registry_path,
                0,
                winreg.KEY_ALL_ACCESS,  # type: ignore
            ) as reg_key:  # type: ignore
                old_registry_value = winreg.QueryValueEx(reg_key, "LongPathsEnabled")[0]  # type: ignore
                winreg.SetValueEx(reg_key, "LongPathsEnabled", 0, winreg.REG_DWORD, 0)  # type: ignore
        except FileNotFoundError:
            # Key or value not present; proceed as if already disabled
            pass
        try:
            yield
        finally:
            if old_registry_value is not None:
                with winreg.OpenKey(  # type: ignore
                    winreg.HKEY_LOCAL_MACHINE,  # type: ignore
                    registry_path,
                    0,
                    winreg.KEY_ALL_ACCESS,  # type: ignore
                ) as reg_key:  # type: ignore
                    winreg.SetValueEx(  # type: ignore
                        reg_key,
                        "LongPathsEnabled",
                        0,
                        winreg.REG_DWORD,  # type: ignore
                        old_registry_value,  # type: ignore
                    )

    return _cm


@only_for_ci(reason="We don't want to mess the registry of the developers' machines.")
@windows_only()
@pytest.mark.usefixtures("check_gtk_launch_and_xvfb_are_installed")
def test_long_paths_disabled(
    tmp_path: Path,
    solution_root_dir: Path,
    setup_solution: SetupSolution,
    build_solution: BuildSolution,
    install_solution: InstallSolution,
    mock_long_paths_disabled: Callable[[], contextlib.AbstractContextManager[None]],
):
    """
    Test solution installer fails early if Long Paths are not enabled in Windows.
    """
    solution_venv_python_exec, _, _, _ = setup_solution(solution_root_dir)
    build_solution([], solution_venv_python_exec, solution_root_dir)
    check_built_solution_files(solution_root_dir)

    # Only disable Long Paths during the install phase, otherwise setup_solution can fail.
    with mock_long_paths_disabled():
        installation_output = install_solution(
            solution_root_dir,
            tmp_path,
            expected_return_code=1,
        )
    assert find_msg_in_output("- Windows Long Path enabled: False", installation_output)
    assert find_msg_in_output(
        "[ERROR] Windows Long Paths is not enabled. Follow the instructions at ",
        installation_output,
    )
    assert not (tmp_path / "Ansys Inc" / "SAF Solutions").is_dir()
