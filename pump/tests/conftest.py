# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from pathlib import Path

from dotenv import load_dotenv
import pytest

# =================================================== [Variables] =================================================== #

# Get absolute path to tests directory
tests_directory = Path(__file__).parent.absolute()

# Get absolute path to project directory
project_directory = Path(__file__).parent.parent.absolute()

# =================================================== [Functions] =================================================== #


def _set_default_glow_env(project_directory: Path) -> None:
    env_file = project_directory / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)

    os.environ.setdefault(
        "GLOW_SOLUTION_DEFINITION",
        "saf.solutions.pump.solution.definition",
    )
    os.environ.setdefault(
        "GLOW_UI_MODULE",
        "saf.solutions.pump.ui.app",
    )


def pytest_configure(config) -> None:
    _set_default_glow_env(project_directory)
    config.addinivalue_line("markers", "fluent: test requires a local Ansys Fluent installation")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--run-fluent`` command line flag.

    Parameters
    ----------
    parser : pytest.Parser
        Parser used by pytest to collect command line options.
    """
    parser.addoption(
        "--run-fluent",
        action="store_true",
        default=False,
        help="Run the tests that require a local Ansys Fluent installation.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip the tests marked ``fluent`` unless ``--run-fluent`` was passed.

    Parameters
    ----------
    config : pytest.Config
        Active pytest configuration.
    items : list of pytest.Item
        Collected test items, modified in place.
    """
    if config.getoption("--run-fluent"):
        return
    skip_fluent = pytest.mark.skip(reason="Requires a local Fluent installation; pass --run-fluent to enable.")
    for item in items:
        if "fluent" in item.keywords:
            item.add_marker(skip_fluent)
