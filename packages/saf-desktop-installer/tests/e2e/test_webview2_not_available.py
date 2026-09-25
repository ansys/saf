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
def mock_webview2_uninstalled() -> Callable[[], contextlib.AbstractContextManager[None]]:
    import winreg  # type: ignore

    targets = [  # type: ignore
        (
            winreg.HKEY_CURRENT_USER,  # type: ignore
            "Software\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,  # type: ignore
            "SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,  # type: ignore
            "SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        ),
    ]

    @contextlib.contextmanager
    def _cm():
        saved_values = {}
        for root, key in targets:  # type: ignore
            try:
                with winreg.OpenKey(root, key, 0, winreg.KEY_ALL_ACCESS) as reg_key:  # type: ignore
                    saved_values[(root, key)] = winreg.QueryValueEx(reg_key, "pv")[0]  # type: ignore
                    winreg.SetValueEx(reg_key, "pv", 0, winreg.REG_SZ, "")  # type: ignore
            except FileNotFoundError:
                # If key doesn't exist, we leave it absent (still means not installed)
                saved_values[(root, key)] = None
        try:
            yield
        finally:
            for (root, key), value in saved_values.items():  # type: ignore
                if value is None:
                    continue
                with winreg.OpenKey(root, key, 0, winreg.KEY_ALL_ACCESS) as reg_key:  # type: ignore
                    winreg.SetValueEx(reg_key, "pv", 0, winreg.REG_SZ, value)  # type: ignore

    return _cm


@only_for_ci(reason="We don't want to mess the registry of the developers' machines.")
@windows_only()
@pytest.mark.usefixtures("check_gtk_launch_and_xvfb_are_installed")
def test_webview2_not_available(
    tmp_path: Path,
    solution_root_dir: Path,
    setup_solution: SetupSolution,
    build_solution: BuildSolution,
    install_solution: InstallSolution,
    mock_webview2_uninstalled: Callable[[], contextlib.AbstractContextManager[None]],
):
    """
    Test solution installer fails early if WebView2 is not available in Windows.
    """
    solution_venv_python_exec, _, _, _ = setup_solution(solution_root_dir)
    build_solution([], solution_venv_python_exec, solution_root_dir)
    check_built_solution_files(solution_root_dir)

    # Only simulate WebView2 absence during installation
    with mock_webview2_uninstalled():
        installation_output = install_solution(
            solution_root_dir,
            tmp_path,
            expected_return_code=1,
        )
    assert find_msg_in_output("- Microsoft Edge WebView2 Runtime: Not installed", installation_output)
    assert find_msg_in_output(
        "[ERROR] Microsoft Edge WebView2 Runtime is not installed. Please install it from ",
        installation_output,
    )
    assert not (tmp_path / "Ansys Inc" / "SAF Solutions").is_dir()
