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

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from ansys.saf.desktop.orchestrator._orchestration.pywebview_events import set_custom_pywebview_icon
from ansys.saf.testing.platform_specific import linux_only, windows_only

SOLUTION_WITH_ICON = "tests.mocks.solutions.minimal_complete_solution"
SOLUTION_WITHOUT_ICON = "tests.mocks.solutions_main.minimal_main"


@pytest.fixture
def mock_window() -> MagicMock:
    window = MagicMock()
    window.native.Handle.ToInt64.return_value = 12345
    return window


@linux_only()
def test_returns_false_on_non_windows(mock_window: MagicMock, mocker: MockerFixture) -> None:
    result = set_custom_pywebview_icon(mock_window, SOLUTION_WITH_ICON)
    assert result is False


@windows_only()
def test_returns_false_when_no_icon_found(mock_window: MagicMock, mocker: MockerFixture) -> None:
    result = set_custom_pywebview_icon(mock_window, SOLUTION_WITHOUT_ICON)
    assert result is False


@windows_only()
def test_returns_true_when_icon_set_successfully(mock_window: MagicMock, mocker: MockerFixture) -> None:
    mock_user32 = MagicMock()
    mocker.patch("ansys.saf.desktop.orchestrator._orchestration.pywebview_events.ctypes.windll.user32", mock_user32)

    result = set_custom_pywebview_icon(mock_window, SOLUTION_WITH_ICON)
    assert result is True

    mock_user32.LoadImageW.assert_called_once()
    assert mock_user32.SendMessageW.call_count == 2
    # Verify icon_small (0) and icon_big (1) messages with WM_SETICON (0x0080)
    calls = mock_user32.SendMessageW.call_args_list
    assert calls[0].args[1] == 0x0080  # wm_seticon
    assert calls[0].args[2] == 0  # icon_small
    assert calls[1].args[1] == 0x0080  # wm_seticon
    assert calls[1].args[2] == 1  # icon_big


@windows_only()
def test_returns_false_when_win32_api_raises_error(mock_window: MagicMock, mocker: MockerFixture) -> None:
    # mock the first Win32 API call to avoid running any real statement that could affect the pytest process
    mock_window.native.Handle.ToInt64.side_effect = Exception("Win32 error")
    result = set_custom_pywebview_icon(mock_window, SOLUTION_WITH_ICON)
    assert result is False
