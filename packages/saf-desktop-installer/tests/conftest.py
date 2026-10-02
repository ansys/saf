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
import re
import shutil
from typing import cast

import pytest
import pytest_mock
from selenium.webdriver.chrome.webdriver import WebDriver

MOCKED_SOLUTION_DIR = (Path(__file__).parent / "mocks").resolve()
DEFAULT_MOCK_SOLUTION_NAME = "my-solution-dash"
DEFAULT_MOCK_SOLUTION_DISPLAY_NAME = "My Solution Dash"
CUSTOM_PACKAGE_FOR_TEST_2_WHEEL_NAMES: dict[str, str] = {
    "Windows": "custom_package_for_test_2-0.0.1-py3-none-win_amd64.whl",
    "Linux": "custom_package_for_test_2-0.0.1-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
}


@pytest.fixture
def mock_solution_display_name(mocker: pytest_mock.MockFixture) -> None:
    # to avoid having glow-engine as test dependency
    mocker.patch(
        "ansys.saf.desktop.installer._package.solution.get_solution_display_name",
        return_value=DEFAULT_MOCK_SOLUTION_DISPLAY_NAME,
    )


@pytest.fixture
def solution_root_dir(tmp_path: Path, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Path:
    solution_name = getattr(request, "param", DEFAULT_MOCK_SOLUTION_NAME)
    orig_solution_root_dir = MOCKED_SOLUTION_DIR / solution_name
    dist_solution_root_dir = tmp_path / solution_name
    shutil.copytree(orig_solution_root_dir, dist_solution_root_dir)
    monkeypatch.syspath_prepend(dist_solution_root_dir / "src")  # pyright: ignore[reportUnknownMemberType]
    return dist_solution_root_dir


def check_installer_gui_is_using_local_bootstrap_css(selenium_webdriver: WebDriver) -> None:
    # check that the GUI is using the bundled bootstrap CSS from local assets, not from an external CDN
    stylesheets = cast(
        "list[str]",
        selenium_webdriver.execute_script(  # pyright: ignore[reportUnknownMemberType]
            "return Array.from(document.querySelectorAll('link[rel=\"stylesheet\"]')).map(element => element.href)",
        ),
    )
    assert len(stylesheets) == 1
    assert re.match(r"http://(localhost|127\.0\.0\.1):\d+/assets/bootstrap\.min\.css(\?.*)?$", stylesheets[0])
