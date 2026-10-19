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

"""Unit tests for the LogsSupervisor component."""

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false

import copy
from pathlib import Path
from typing import Any, cast
from unittest import mock

try:
    # dash >=3.2.0
    from dash import NoUpdate
except ImportError:
    # dash >=2.18.2, <3.2.0
    from dash._callback import NoUpdate  # pyright: ignore[reportPrivateImportUsage]
from dash.exceptions import PreventUpdate
import dash_ag_grid as dag
from dash_extensions.enrich import dcc, html, no_update
import dash_mantine_components as dmc
import pandas as pd
import pytest

from ansys.solutions.dash_super_components.logs_supervisor import (
    FILTER_BUTTONS_PROPERTIES,
    PARSING_FAILED_NO_ROWS_MESSAGE,
    PLAIN_NO_ROWS_MESSAGE,
    SOURCE_MISSING_NO_ROWS_MESSAGE,
    SUPPORTED_LOGGING_FORMATTER_OPTIONS_AND_HEADERS,
    LogsSupervisor,
)
from ansys.solutions.dash_super_components.utils import config
from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors
from ansys.solutions.dash_super_components.utils.logs_parser import LogsParseResult, ParseStatus
from tests.conftest import as_json

EXPECTED_INFO_ICON_SRC = (
    "data:image/svg+xml;base64,CiAgICAgICAgICAgIDxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3Zn"
    "IiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAyNCAyNCI+CiAgICAgICAgICAgICAgICA8cGF0aCBmaW"
    "xsPSIjZmZmIiBkPSJNMTEgMTdoMnYtNmgtMnptMS04cS40MjUgMCAuNzEzLS4yODhUMTMgOHQtLjI4OC0uNzEyVDEyIDd0"
    "LS43MTIuMjg4VDExIDh0LjI4OC43MTNUMTIgOW0wIDEzcS0yLjA3NSAwLTMuOS0uNzg4dC0zLjE3NS0yLjEzN1QyLjc4OC"
    "AxNS45VDIgMTJ0Ljc4OC0zLjl0Mi4xMzctMy4xNzVUOC4xIDIuNzg4VDEyIDJ0My45Ljc4OHQzLjE3NSAyLjEzN1QyMS4y"
    "MTMgOC4xVDIyIDEydC0uNzg4IDMuOXQtMi4xMzcgMy4xNzV0LTMuMTc1IDIuMTM4VDEyIDIyIi8+CiAgICAgICAgICAgID"
    "wvc3ZnPgogICAgICAgIA=="
)


EXPECTED_WARNING_ICON_SRC = (
    "data:image/svg+xml;base64,CiAgICAgICAgICAgIDxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3Zn"
    "IiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iI2ZmZiIgZD0iTTEgMj"
    "FMMTIgMmwxMSAxOXptMTEtM3EuNDI1IDAgLjcxMy0uMjg4VDEzIDE3dC0uMjg4LS43MTJUMTIgMTZ0LS43MTIuMjg4VDEx"
    "IDE3dC4yODguNzEzVDEyIDE4bS0xLTNoMnYtNWgtMnoiLz4KICAgICAgICAgICAgPC9zdmc+CiAgICAgICAg"
)


EXPECTED_ERROR_ICON_SRC = (
    "data:image/svg+xml;base64,CiAgICAgICAgICAgIDxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3Zn"
    "IiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCA0OCA0OCI+PHBhdGggZmlsbD0iI2ZmZiIgZmlsbC1ydW"
    "xlPSJldmVub2RkIiBzdHJva2U9IiNmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3Vu"
    "ZCIgc3Ryb2tlLXdpZHRoPSI0IiBkPSJtNiAxMWw1LTVsMTMgMTNMMzcgNmw1IDVsLTEzIDEzbDEzIDEzbC01IDVsLTEzLT"
    "EzbC0xMyAxM2wtNS01bDEzLTEzeiIgY2xpcC1ydWxlPSJldmVub2RkIi8+PC9zdmc+CiAgICAgICAg"
)


EXPECTED_CRITICAL_ICON_SRC = (
    "data:image/svg+xml;base64,CiAgICAgICAgICAgIDxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3Zn"
    "IiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iI2ZmZiIgZD0iTTExID"
    "E1aDJ2MmgtMnptMC02aDJ2NWgtMnoiLz48cGF0aCBmaWxsPSIjZmZmIiBkPSJNMjAgOGgtMi44MWE2IDYgMCAwIDAtMS44"
    "Mi0xLjk2TDE3IDQuNDFMMTUuNTkgM2wtMi4xNyAyLjE3QTYgNiAwIDAgMCAxMiA1YTYgNiAwIDAgMC0xLjQxLjE3TDguND"
    "EgM0w3IDQuNDFsMS42MiAxLjYzQTYuMSA2LjEgMCAwIDAgNi44MSA4SDR2MmgyLjA5QTYuNiA2LjYgMCAwIDAgNiAxMXYx"
    "SDR2MmgydjFhNi42IDYuNiAwIDAgMCAuMDkgMUg0djJoMi44MWE1Ljk5IDUuOTkgMCAwIDAgMTAuMzggMEgyMHYtMmgtMi"
    "4wOWE2LjYgNi42IDAgMCAwIC4wOS0xdi0xaDJ2LTJoLTJ2LTFhNi42IDYuNiAwIDAgMC0uMDktMUgyMFptLTQgNHYzYTQg"
    "NCAwIDAgMS0uMDcuN2wtLjEuNjVsLS4zNy42NWEzLjk5MyAzLjk5MyAwIDAgMS02LjkyIDBsLS4zNy0uNjRsLS4xLS42NU"
    "E0LjMgNC4zIDAgMCAxIDggMTV2LTRhNCA0IDAgMCAxIC4wNy0uN2wuMS0uNjVsLjM3LS42NWE0LjEgNC4xIDAgMCAxIDEu"
    "MjEtMS4zMWwuNTctLjM5bC43NC0uMThBMy44IDMuOCAwIDAgMSAxMiA3YTQgNCAwIDAgMSAuOTUuMTJsLjY4LjE2bC42MS"
    "40MmEzLjkgMy45IDAgMCAxIDEuMjEgMS4zMWwuMzguNjVsLjEuNjVBNCA0IDAgMCAxIDE2IDExWiIvPgogICAgICAgICAg"
    "ICA8L3N2Zz4KICAgICAgICA="
)


EXPECTED_DEBUG_ICON_SRC = (
    "data:image/svg+xml;base64,CiAgICAgICAgICAgIDxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3Zn"
    "IiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iI2ZmZiIgZD0iTTExID"
    "E1aDJ2MmgtMnptMC02aDJ2NWgtMnoiLz48cGF0aCBmaWxsPSIjZmZmIiBkPSJNMjAgOGgtMi44MWE2IDYgMCAwIDAtMS44"
    "Mi0xLjk2TDE3IDQuNDFMMTUuNTkgM2wtMi4xNyAyLjE3QTYgNiAwIDAgMCAxMiA1YTYgNiAwIDAgMC0xLjQxLjE3TDguND"
    "EgM0w3IDQuNDFsMS42MiAxLjYzQTYuMSA2LjEgMCAwIDAgNi44MSA4SDR2MmgyLjA5QTYuNiA2LjYgMCAwIDAgNiAxMXYx"
    "SDR2MmgydjFhNi42IDYuNiAwIDAgMCAuMDkgMUg0djJoMi44MWE1Ljk5IDUuOTkgMCAwIDAgMTAuMzggMEgyMHYtMmgtMi"
    "4wOWE2LjYgNi42IDAgMCAwIC4wOS0xdi0xaDJ2LTJoLTJ2LTFhNi42IDYuNiAwIDAgMC0uMDktMUgyMFptLTQgNHYzYTQg"
    "NCAwIDAgMS0uMDcuN2wtLjEuNjVsLS4zNy42NWEzLjk5MyAzLjk5MyAwIDAgMS02LjkyIDBsLS4zNy0uNjRsLS4xLS42NU"
    "E0LjMgNC4zIDAgMCAxIDggMTV2LTRhNCA0IDAgMCAxIC4wNy0uN2wuMS0uNjVsLjM3LS42NWE0LjEgNC4xIDAgMCAxIDEu"
    "MjEtMS4zMWwuNTctLjM5bC43NC0uMThBMy44IDMuOCAwIDAgMSAxMiA3YTQgNCAwIDAgMSAuOTUuMTJsLjY4LjE2bC42MS"
    "40MmEzLjkgMy45IDAgMCAxIDEuMjEgMS4zMWwuMzguNjVsLjEuNjVBNCA0IDAgMCAxIDE2IDExWiIvPgogICAgICAgICAg"
    "ICA8L3N2Zz4KICAgICAgICA="
)


EXPECTED_PAUSE_ICON_SRC = (
    "data:image/svg+xml;base64,CiAgICAgICAgICAgIDxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3Zn"
    "IiB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCI+PHBhdGggZmlsbD0iIzg2OGU5NiIgZmlsbC"
    "1ydWxlPSJldmVub2RkIiBkPSJNNDQgMjRjMCAxMS4wNDYtOC45NTQgMjAtMjAgMjBTNCAzNS4wNDYgNCAyNFMxMi45NTQg"
    "NCAyNCA0czIwIDguOTU0IDIwIDIwbS0yNy43NzggNy43NzhhMSAxIDAgMCAxIDAtMS40MTRMMjIuNTg2IDI0bC02LjM2NC"
    "02LjM2NGExIDEgMCAwIDEgMS40MTQtMS40MTRMMjQgMjIuNTg2bDYuMzY0LTYuMzY0YTEgMSAwIDAgMSAxLjQxNCAxLjQx"
    "NEwyNS40MTQgMjRsNi4zNjQgNi4zNjRhMSAxIDAgMCAxLTEuNDE0IDEuNDE0TDI0IDI1LjQxNGwtNi4zNjQgNi4zNjRhMS"
    "AxIDAgMCAxLTEuNDE0IDAiIGNsaXAtcnVsZT0iZXZlbm9kZCIvPjwvc3ZnPgogICAgICAgIA=="
)


EXPECTED_PLAY_ICON_SRC = (
    "data:image/svg+xml;base64,CiAgICAgICAgICAgIDxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3Zn"
    "IiB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCI+PHBhdGggZmlsbD0iI2ZmZiIgZmlsbC1ydW"
    "xlPSJldmVub2RkIiBkPSJNMjQgNDRjMTEuMDQ2IDAgMjAtOC45NTQgMjAtMjBTMzUuMDQ2IDQgMjQgNFM0IDEyLjk1NCA0"
    "IDI0czguOTU0IDIwIDIwIDIwbTEwLjc0Mi0yNi4zM2ExIDEgMCAxIDAtMS40ODMtMS4zNEwyMS4yOCAyOS41NjdsLTYuNT"
    "ktNi4yOTFhMSAxIDAgMCAwLTEuMzgyIDEuNDQ2bDcuMzM0IDdsLjc0My43MWwuNjg5LS43NjJ6IiBjbGlwLXJ1bGU9ImV2"
    "ZW5vZGQiLz48L3N2Zz4KICAgICAgICA="
)


@pytest.fixture
def mock_logs_parser():
    """Mock LogsParser for testing."""
    with mock.patch(
        "ansys.solutions.dash_super_components.logs_supervisor.LogsParser",
    ) as mocked_parser:
        yield mocked_parser


@pytest.fixture
def sample_log_data() -> pd.DataFrame:
    """Sample log data for testing."""
    return pd.DataFrame(
        {
            "asctime": ["2024-01-01 10:00:00", "2024-01-01 10:01:00", "2024-01-01 10:02:00"],
            "levelname": ["INFO", "WARNING", "ERROR"],
            "module": ["module1", "module2", "module3"],
            "message": ["Test message 1", "Test message 2", "Test message 3"],
            "process": [
                1234,
                1235,
                1236,
            ],  # This field is not defined in LOGGING_FORMATTER_REPRESENTATION
        },
    )


@pytest.fixture
def sample_log_data_for_all_attributes() -> pd.DataFrame:
    """Sample log data for testing. Includes all possible logging attributes."""
    sample_log_data_for_all_attributes = {
        "asctime": ["2024-01-01 10:00:00", "2024-01-01 10:01:00", "2024-01-01 10:02:00"],
        "created": [1700000000.0, 1700000060.0, 1700000120.0],
        "filename": ["file1.py", "file2.py", "file3.py"],
        "funcName": ["func1", "func2", "func3"],
        "levelname": ["INFO", "WARNING", "ERROR"],
        "levelno": [20, 30, 40],
        "lineno": [10, 20, 30],
        "message": ["Test message 1", "Test message 2", "Test message 3"],
        "module": ["module1", "module2", "module3"],
        "msecs": [123, 456, 789],
        "name": ["logger1", "logger2", "logger3"],
        "pathname": ["/path/to/file1.py", "/path/to/file2.py", "/path/to/file3.py"],
        "process": [1234, 1235, 1236],
        "processName": ["Process1", "Process2", "Process3"],
        "relativeCreated": [1000.0, 2000.0, 3000.0],
        "thread": [140735224123456, 140735224123457, 140735224123458],
        "threadName": ["MainThread", "WorkerThread", "LoggerThread"],
        "taskName": ["MainTask", "WorkerTask", "LoggerTask"],
    }

    return pd.DataFrame(sample_log_data_for_all_attributes)


def test_ids():
    """Test that all ID methods return the expected structure."""
    aio_id = "dummy-id"

    supervisor = LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id=aio_id,
    )

    assert supervisor.aio_id == aio_id

    assert supervisor.ids.info_button(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "info-button",
        "aio_id": aio_id,
    }
    assert supervisor.ids.warning_button(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "warning-button",
        "aio_id": aio_id,
    }
    assert supervisor.ids.error_button(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "error-button",
        "aio_id": aio_id,
    }
    assert supervisor.ids.critical_button(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "critical-button",
        "aio_id": aio_id,
    }
    assert supervisor.ids.debug_button(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "debug-button",
        "aio_id": aio_id,
    }
    assert supervisor.ids._grid(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "grid",
        "aio_id": aio_id,
    }
    assert supervisor.ids._log_file_and_format(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "log-file-and-format",
        "aio_id": aio_id,
    }
    assert supervisor.ids._log_file_and_format_persist(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "log-file-and-format-persist",
        "aio_id": aio_id,
    }
    assert supervisor.ids._show_levels(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "show-levels",
        "aio_id": aio_id,
    }
    assert supervisor.ids._filter_model_store(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "filter-model-store",
        "aio_id": aio_id,
    }
    assert supervisor.ids._interval(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "interval",
        "aio_id": aio_id,
    }
    assert supervisor.ids._supervision_active(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "supervision-active",
        "aio_id": aio_id,
    }
    assert supervisor.ids.activate_monitoring(aio_id) == {
        "component": "logs-supervisor",
        "subcomponent": "activate-monitoring",
        "aio_id": aio_id,
    }


def test_initialization_autogenerated_id():
    """Test that ID is auto-generated when not provided."""
    supervisor = LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # ID should be auto-generated
    assert supervisor.aio_id is not None
    assert isinstance(supervisor.aio_id, str)
    assert len(supervisor.aio_id) > 0

    another_supervisor = LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
    )

    assert supervisor.aio_id != another_supervisor.aio_id  # IDs should be unique


def test_initialization_defaults():
    """Test initialization with default values.

    Actual grid rows and columns (data) are not asserted.
    """
    dummy_log_file = Path("/path/to/test.log")
    dummy_log_format = "%(asctime)s - %(levelname)s - %(message)s"
    supervisor = LogsSupervisor(
        log_file=dummy_log_file,
        log_format=dummy_log_format,
    )

    current_aio_id = supervisor.aio_id

    _assert_structure_except_rows_and_columns(
        current_aio_id,
        supervisor,
        str(dummy_log_file),
        dummy_log_format,
    )


def test_initialization_with_path_object():
    """Test initialization with Path object."""
    log_file = Path("/path/to/test.log")
    log_format = "%(asctime)s - %(levelname)s - %(module)s - %(message)s"

    supervisor = LogsSupervisor(
        log_file=log_file,
        log_format=log_format,
        aio_id="test-id",
    )
    _assert_structure_except_rows_and_columns("test-id", supervisor, str(log_file), log_format)


def test_initialization_with_string_path():
    """Test initialization with string path."""
    log_file = "/path/to/test.log"
    log_format = "%(asctime)s - %(levelname)s - %(module)s - %(message)s"

    supervisor = LogsSupervisor(
        log_file=log_file,
        log_format=log_format,
        aio_id="test-id",
    )

    _assert_structure_except_rows_and_columns("test-id", supervisor, log_file, log_format)


def test_default_grid_theme_uses_mantine_color_variables():
    """Test the default grid theme follows Mantine's light or dark color scheme."""
    supervisor = LogsSupervisor(
        log_file="test.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    grid = supervisor.children[0].children[2].children

    assert grid.dashGridOptions["theme"] == {
        "function": (
            "themeQuartz.withParams({ backgroundColor: 'var(--mantine-color-body, #fff)', "
            "foregroundColor: 'var(--mantine-color-text, #1a1b1e)' })"
        ),
    }


def test_initialization_with_url():
    """Test initialization with URL."""
    log_file = "http://example.com/test.log"
    log_format = "%(asctime)s - %(levelname)s - %(message)s"

    supervisor = LogsSupervisor(
        log_file=log_file,
        log_format=log_format,
        aio_id="test-id",
    )
    _assert_structure_except_rows_and_columns("test-id", supervisor, log_file, log_format)


def test_initialization_custom_interval():
    """Test initialization with custom interval."""
    supervisor = LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
        interval=5000,
    )

    # Find the Interval component in the component tree
    _assert_structure_except_rows_and_columns(
        "test-id",
        supervisor,
        "dummy_log.log",
        "%(asctime)s - %(levelname)s - %(message)s",
        5000,
    )


def test_initialization_grid_props_custom():
    """Test initialization with custom grid properties."""
    custom_props_input = {
        "style": {"width": "80%", "height": "500px"},
        "className": "custom-theme",
        "columnSize": "fitToWidth",
        "columnSizeOptions": {"keys": ["asctime"], "skipHeader": False},
        "defaultColDef": {"flex": 1, "minWidth": 100},
        "filterModel": {"levelname": {"filterType": "text", "type": "contains", "filter": "ERROR"}},
        "persistence": False,
        "persistence_type": "session",
        "persisted_props": ["columnState"],
    }

    custom_props_expected = copy.deepcopy(custom_props_input)

    supervisor = LogsSupervisor(
        log_file="test.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
        grid_props=custom_props_input,
    )

    _assert_structure_except_rows_and_columns(
        "test-id",
        supervisor,
        "test.log",
        "%(asctime)s - %(levelname)s - %(message)s",
        input_grid_props=custom_props_expected,
    )


def test_initialization_grid_props_custom_style_partial():
    """Test initialization with custom grid properties."""
    custom_props_input = {
        "style": {"width": "80%"},  # only width provided
        "className": "custom-theme",
        "columnSize": "fitToWidth",
        "columnSizeOptions": {"keys": ["asctime"], "skipHeader": False},
        "defaultColDef": {"flex": 1, "minWidth": 100},
        "filterModel": {"levelname": {"filterType": "text", "type": "contains", "filter": "ERROR"}},
        "persistence": False,
        "persisted_props": ["columnState"],
    }

    custom_props_expected = copy.deepcopy(custom_props_input)
    custom_props_expected["style"]["height"] = "200px"  # default height added

    supervisor = LogsSupervisor(
        log_file="test.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
        grid_props=custom_props_input,
    )

    _assert_structure_except_rows_and_columns(
        "test-id",
        supervisor,
        "test.log",
        "%(asctime)s - %(levelname)s - %(message)s",
        input_grid_props=custom_props_expected,
    )


def test_initialization_with_width():
    """Test initialization with custom grid properties."""
    custom_width = "80%"

    supervisor = LogsSupervisor(
        log_file="test.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
        width=custom_width,
    )

    _assert_structure_except_rows_and_columns(
        "test-id",
        supervisor,
        "test.log",
        "%(asctime)s - %(levelname)s - %(message)s",
        width=custom_width,
    )


@pytest.mark.parametrize(
    ("log_format", "expected_columns_defs"),
    [
        # Test each individual supported format specifier
        ("%(asctime)s", ["asctime"]),
        ("%(created)f", ["created"]),
        ("%(filename)s", ["filename"]),
        ("%(funcName)s", ["funcName"]),
        ("%(levelname)s", ["levelname"]),
        ("%(levelno)d", ["levelno"]),
        ("%(lineno)d", ["lineno"]),
        ("%(message)s", ["message"]),
        ("%(module)s", ["module"]),
        ("%(msecs)d", ["msecs"]),
        ("%(name)s", ["name"]),
        ("%(pathname)s", ["pathname"]),
        ("%(process)d", ["process"]),
        ("%(processName)s", ["processName"]),
        ("%(relativeCreated)d", ["relativeCreated"]),
        ("%(thread)d", ["thread"]),
        ("%(threadName)s", ["threadName"]),
        ("%(taskName)s", ["taskName"]),
        # Test combinations of supported format specifiers
        ("%(asctime)s - %(levelname)s - %(message)s", ["asctime", "levelname", "message"]),
        ("%(module)s - %(levelname)s", ["module", "levelname"]),
        ("%(filename)s:%(lineno)d - %(funcName)s()", ["filename", "lineno", "funcName"]),
        # Test unsupported format specifier is ignored
        ("dummy - which is not a specifier", []),  # no valid format specifiers
        (
            "%(asctime)s - dummy - %(levelname)s",
            ["asctime", "levelname"],
        ),  # only valid specifiers included
    ],
)
def test_initialization_column_defs_generation(
    sample_log_data_for_all_attributes: pd.DataFrame,
    log_format: str,
    expected_columns_defs: list[str],
):
    """Test that columnDefs are generated correctly from log format."""
    supervisor = LogsSupervisor(
        log_file="test.log",
        log_format=log_format,
        aio_id="test-id",
    )

    # Find the AgGrid component
    component_json = as_json(supervisor)
    ag_grid = _find_component_by_type(component_json, "AgGrid")

    assert ag_grid is not None
    column_defs = ag_grid["props"]["columnDefs"]

    # Verify columns are generated for each attribute in log_format
    # Only attributes in SUPPORTED_LOGGING_FORMATTER_OPTIONS_AND_HEADERS are included
    assert len(column_defs) == len(expected_columns_defs)
    actual_fields = [col["field"] for col in column_defs]
    assert actual_fields == expected_columns_defs


def test_initialization_row_data_not_prepopulated():
    """Test that grid rowData is not populated during initialization."""
    supervisor = LogsSupervisor(
        log_file="test.log",
        log_format="%(asctime)s - %(levelname)s - %(module)s - %(message)s - %(process)d",
        aio_id="test-id",
    )

    component_json = as_json(supervisor)
    ag_grid = _find_component_by_type(component_json, "AgGrid")

    assert ag_grid is not None
    assert "rowData" not in ag_grid["props"]
    assert ag_grid["props"]["dashGridOptions"]["noRowsOverlayComponentParams"] == {"message": PLAIN_NO_ROWS_MESSAGE}


def test_initialization_no_log_file_provided():
    """Test that initialization raises ValueError when no log file is provided."""
    with pytest.raises(ValueError, match="log_file must be provided."):
        LogsSupervisor(
            log_file="",
            log_format="%(asctime)s - %(levelname)s - %(message)s",
            aio_id="test-id",
        )

    with pytest.raises(ValueError, match="log_file must be provided."):
        LogsSupervisor(
            log_file=None,  # type: ignore - testing invalid input
            log_format="%(asctime)s - %(levelname)s - %(message)s",
            aio_id="test-id",
        )


def test_initialization_invalid_log_file_type():
    """Test that initialization raises TypeError when log_file is of invalid type."""
    with pytest.raises(TypeError, match="log_file must be a string or a Path object."):
        LogsSupervisor(
            log_file=123,  # type: ignore - testing invalid input
            log_format="%(asctime)s - %(levelname)s - %(message)s",
            aio_id="test-id",
        )

    with pytest.raises(TypeError, match="log_file must be a string or a Path object."):
        LogsSupervisor(
            log_file=5.67,  # type: ignore - testing invalid input
            log_format="%(asctime)s - %(levelname)s - %(message)s",
            aio_id="test-id",
        )


def test_initialization_no_log_format_provided():
    """Test that initialization raises ValueError when no log format is provided."""
    with pytest.raises(ValueError, match="log_format must be provided."):
        LogsSupervisor(
            log_file="dummy_log.log",
            log_format="",
            aio_id="test-id",
        )

    with pytest.raises(ValueError, match="log_format must be provided."):
        LogsSupervisor(
            log_file="dummy_log.log",
            log_format=None,  # type: ignore - testing invalid input
            aio_id="test-id",
        )


def test_initialization_show_error_notifications_store_default_true():
    """Test that show_error_notifications store defaults to True."""
    supervisor = LogsSupervisor(
        log_file="test.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    component_json = as_json(supervisor)
    stores = [
        child for child in component_json["props"]["children"][0]["props"]["children"] if child.get("type") == "Store"
    ]

    notification_store = next(
        store for store in stores if store["props"]["id"]["subcomponent"] == "show-error-notifications"
    )
    assert notification_store["props"]["data"] is True
    assert notification_store["props"]["storage_type"] == "memory"


def test_initialization_show_error_notifications_store_custom_false():
    """Test that show_error_notifications can be disabled."""
    supervisor = LogsSupervisor(
        log_file="test.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
        show_error_notifications=False,
    )

    component_json = as_json(supervisor)
    stores = [
        child for child in component_json["props"]["children"][0]["props"]["children"] if child.get("type") == "Store"
    ]

    notification_store = next(
        store for store in stores if store["props"]["id"]["subcomponent"] == "show-error-notifications"
    )
    assert notification_store["props"]["data"] is False
    assert notification_store["props"]["storage_type"] == "memory"


def test_filter_data_by_level_name_all_disabled(
    callback_context_mock: mock.MagicMock,
):
    """Test update_filter_buttons_variants_and_filter_model when all buttons should be disabled."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    show_levels = {
        "info": True,  # trigger info button such that all will be disabled after the click
        "warning": False,
        "error": False,
        "critical": False,
        "debug": False,
    }
    filter_model: dict[str, Any] = {
        "levelname": "this_needs_to_be_overwritten",
        "some_other_key": "this_value_should_remain",
    }
    info_button_id = LogsSupervisor.ids.info_button("test-id")
    warning_button_id = LogsSupervisor.ids.warning_button("test-id")
    error_button_id = LogsSupervisor.ids.error_button("test-id")
    critical_button_id = LogsSupervisor.ids.critical_button("test-id")
    debug_button_id = LogsSupervisor.ids.debug_button("test-id")
    callback_context_mock.triggered_id = info_button_id

    updated_show_levels, updated_filter_model = LogsSupervisor.filter_data_by_level_name(
        1,  # dummy
        0,  # dummy
        0,  # dummy
        0,  # dummy
        0,  # dummy
        copy.deepcopy(show_levels),
        copy.deepcopy(filter_model),
        info_button_id,
        warning_button_id,
        error_button_id,
        critical_button_id,
        debug_button_id,
    )

    # show_levels should now be all False
    assert updated_show_levels == {
        "info": False,
        "warning": False,
        "error": False,
        "critical": False,
        "debug": False,
    }

    expected_filter_model = {
        "levelname": {
            "filterType": "text",
            "operator": "AND",
            "conditions": [
                {
                    "filterType": "text",
                    "type": "notContains",
                    "filter": "info",
                },
                {
                    "filterType": "text",
                    "type": "notContains",
                    "filter": "warning",
                },
                {
                    "filterType": "text",
                    "type": "notContains",
                    "filter": "error",
                },
                {
                    "filterType": "text",
                    "type": "notContains",
                    "filter": "critical",
                },
                {
                    "filterType": "text",
                    "type": "notContains",
                    "filter": "debug",
                },
            ],
        },
        "some_other_key": "this_value_should_remain",
    }

    assert updated_filter_model == expected_filter_model


@pytest.mark.parametrize(
    ("initial_show_levels", "triggered_button"),
    [
        (
            {
                "info": False,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "info",
        ),
        (
            {
                "info": False,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "warning",
        ),
        (
            {
                "info": False,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "error",
        ),
        (
            {
                "info": False,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "critical",
        ),
        (
            {
                "info": False,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "debug",
        ),
        (
            {
                "info": False,
                "warning": True,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "info",
        ),
        (
            {
                "info": True,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "warning",
        ),
        (
            {
                "info": True,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "error",
        ),
        (
            {
                "info": True,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "critical",
        ),
        (
            {
                "info": True,
                "warning": False,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "debug",
        ),
        (
            {
                "info": False,
                "warning": True,
                "error": True,
                "critical": False,
                "debug": False,
            },
            "info",
        ),
        (
            {
                "info": True,
                "warning": False,
                "error": True,
                "critical": False,
                "debug": False,
            },
            "warning",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "error",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "critical",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": False,
                "critical": False,
                "debug": False,
            },
            "debug",
        ),
        (
            {
                "info": False,
                "warning": True,
                "error": True,
                "critical": True,
                "debug": False,
            },
            "info",
        ),
        (
            {
                "info": True,
                "warning": False,
                "error": True,
                "critical": True,
                "debug": False,
            },
            "warning",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": False,
                "critical": True,
                "debug": False,
            },
            "error",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": True,
                "critical": False,
                "debug": False,
            },
            "critical",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": True,
                "critical": False,
                "debug": False,
            },
            "debug",
        ),
        (
            {
                "info": False,
                "warning": True,
                "error": True,
                "critical": True,
                "debug": True,
            },
            "info",
        ),
        (
            {
                "info": True,
                "warning": False,
                "error": True,
                "critical": True,
                "debug": True,
            },
            "warning",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": False,
                "critical": True,
                "debug": True,
            },
            "error",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": True,
                "critical": False,
                "debug": True,
            },
            "critical",
        ),
        (
            {
                "info": True,
                "warning": True,
                "error": True,
                "critical": True,
                "debug": False,
            },
            "debug",
        ),
    ],
)
def test_filter_data_by_level_name_some_or_all_true(
    callback_context_mock: mock.MagicMock,
    initial_show_levels: dict[str, bool],
    triggered_button: str,
):
    """Test update_filter_buttons_variants_and_filter_model with various enabled/disabled combos."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    filter_model: dict[str, Any] = {
        "levelname": "this_needs_to_be_overwritten",
        "some_other_key": "this_value_should_remain",
    }
    info_button_id = LogsSupervisor.ids.info_button("test-id")
    warning_button_id = LogsSupervisor.ids.warning_button("test-id")
    error_button_id = LogsSupervisor.ids.error_button("test-id")
    critical_button_id = LogsSupervisor.ids.critical_button("test-id")
    debug_button_id = LogsSupervisor.ids.debug_button("test-id")
    button_id_map = {
        "info": info_button_id,
        "warning": warning_button_id,
        "error": error_button_id,
        "critical": critical_button_id,
        "debug": debug_button_id,
    }
    callback_context_mock.triggered_id = button_id_map[triggered_button]

    dummy_info_clicks = 1 if triggered_button == "info" else 0
    dummy_warning_clicks = 1 if triggered_button == "warning" else 0
    dummy_error_clicks = 1 if triggered_button == "error" else 0
    dummy_critical_clicks = 1 if triggered_button == "critical" else 0
    dummy_debug_clicks = 1 if triggered_button == "debug" else 0

    updated_show_levels, updated_filter_model = LogsSupervisor.filter_data_by_level_name(
        dummy_info_clicks,
        dummy_warning_clicks,
        dummy_error_clicks,
        dummy_critical_clicks,
        dummy_debug_clicks,
        copy.deepcopy(initial_show_levels),
        copy.deepcopy(filter_model),
        info_button_id,
        warning_button_id,
        error_button_id,
        critical_button_id,
        debug_button_id,
    )

    expected_show_levels = initial_show_levels.copy()
    # Toggle the clicked button
    expected_show_levels[triggered_button] = not initial_show_levels[triggered_button]
    assert updated_show_levels == expected_show_levels

    expected_filter_model = {
        "levelname": {
            "filterType": "text",
            "operator": "OR",
            "conditions": [],
        },
        "some_other_key": "this_value_should_remain",
    }

    if expected_show_levels["info"]:
        expected_filter_model["levelname"]["conditions"].append(
            {
                "filterType": "text",
                "type": "contains",
                "filter": "info",
            },
        )
    if expected_show_levels["warning"]:
        expected_filter_model["levelname"]["conditions"].append(
            {
                "filterType": "text",
                "type": "contains",
                "filter": "warning",
            },
        )
    if expected_show_levels["error"]:
        expected_filter_model["levelname"]["conditions"].append(
            {
                "filterType": "text",
                "type": "contains",
                "filter": "error",
            },
        )
    if expected_show_levels["critical"]:
        expected_filter_model["levelname"]["conditions"].append(
            {
                "filterType": "text",
                "type": "contains",
                "filter": "critical",
            },
        )
    if expected_show_levels["debug"]:
        expected_filter_model["levelname"]["conditions"].append(
            {
                "filterType": "text",
                "type": "contains",
                "filter": "debug",
            },
        )

    assert updated_filter_model == expected_filter_model


def test_filter_data_by_level_name_raises_prevent_update_when_no_triggered_id(
    callback_context_mock: mock.MagicMock,
):
    """Test filter_data_by_level_name raises PreventUpdate when ctx.triggered_id is None."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    # Set ctx.triggered_id to None
    callback_context_mock.triggered_id = None

    show_levels = {
        "info": True,
        "warning": True,
        "error": True,
        "critical": True,
        "debug": True,
    }
    filter_model: dict[str, Any] = {}

    info_button_id = LogsSupervisor.ids.info_button("test-id")
    warning_button_id = LogsSupervisor.ids.warning_button("test-id")
    error_button_id = LogsSupervisor.ids.error_button("test-id")
    critical_button_id = LogsSupervisor.ids.critical_button("test-id")
    debug_button_id = LogsSupervisor.ids.debug_button("test-id")

    with pytest.raises(PreventUpdate):
        LogsSupervisor.filter_data_by_level_name(
            0,  # dummy
            0,  # dummy
            0,  # dummy
            0,  # dummy
            0,  # dummy
            show_levels,
            filter_model,
            info_button_id,
            warning_button_id,
            error_button_id,
            critical_button_id,
            debug_button_id,
        )


def test_filter_data_by_level_name_unknown_trigger_does_not_toggle(
    callback_context_mock: mock.MagicMock,
):
    """Test filter_data_by_level_name returns unchanged show_levels when trigger is unknown."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    # Set ctx.triggered_id to an unknown component dict (not matching any button)
    callback_context_mock.triggered_id = {"component": "other-component", "aio_id": "test-id"}

    show_levels = {
        "info": True,
        "warning": True,
        "error": True,
        "critical": True,
        "debug": True,
    }
    filter_model: dict[str, Any] = {"some_other_key": "this_value_should_remain"}

    info_button_id = LogsSupervisor.ids.info_button("test-id")
    warning_button_id = LogsSupervisor.ids.warning_button("test-id")
    error_button_id = LogsSupervisor.ids.error_button("test-id")
    critical_button_id = LogsSupervisor.ids.critical_button("test-id")
    debug_button_id = LogsSupervisor.ids.debug_button("test-id")

    updated_show_levels, updated_filter_model = LogsSupervisor.filter_data_by_level_name(
        0,  # dummy
        0,  # dummy
        0,  # dummy
        0,  # dummy
        0,  # dummy
        copy.deepcopy(show_levels),
        copy.deepcopy(filter_model),
        info_button_id,
        warning_button_id,
        error_button_id,
        critical_button_id,
        debug_button_id,
    )

    # show_levels should remain unchanged (no button was toggled)
    assert updated_show_levels == show_levels
    # some_other_key should remain unchanged
    assert updated_filter_model["some_other_key"] == "this_value_should_remain"


@pytest.mark.parametrize(
    ("show_info", "show_warning", "show_error", "show_critical", "show_debug"),
    [
        (True, False, False, False, False),
        (False, True, False, False, False),
        (False, False, True, False, False),
        (False, False, False, True, False),
        (False, False, False, False, True),
        (True, True, False, False, False),
        (True, False, True, False, False),
        (False, False, False, False, False),
        (True, True, True, True, True),
    ],
)
def test_update_button_variants_from_show_levels(
    show_info: bool,
    show_warning: bool,
    show_error: bool,
    show_critical: bool,
    show_debug: bool,
):
    """Test update_button_variants_from_show_levels with mixed visibility states."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    show_levels = {
        "info": show_info,
        "warning": show_warning,
        "error": show_error,
        "critical": show_critical,
        "debug": show_debug,
    }

    result = LogsSupervisor.update_button_variants_from_show_levels(show_levels)

    expected_variants = {
        "info": "filled" if show_info else "outline",
        "warning": "filled" if show_warning else "outline",
        "error": "filled" if show_error else "outline",
        "critical": "filled" if show_critical else "outline",
        "debug": "filled" if show_debug else "outline",
    }

    # Callback returns pairs of (variant, icon component) in level order.
    assert result[0] == expected_variants["info"]
    assert isinstance(result[1], html.Span)
    assert str(result[1]) == str(
        FILTER_BUTTONS_PROPERTIES["info"]["icon"] if show_info else FILTER_BUTTONS_PROPERTIES["info"]["icon_disabled"]
    )

    assert result[2] == expected_variants["warning"]
    assert isinstance(result[3], html.Span)
    assert str(result[3]) == str(
        FILTER_BUTTONS_PROPERTIES["warning"]["icon"]
        if show_warning
        else FILTER_BUTTONS_PROPERTIES["warning"]["icon_disabled"]
    )

    assert result[4] == expected_variants["error"]
    assert isinstance(result[5], html.Span)
    assert str(result[5]) == str(
        FILTER_BUTTONS_PROPERTIES["error"]["icon"]
        if show_error
        else FILTER_BUTTONS_PROPERTIES["error"]["icon_disabled"]
    )

    assert result[6] == expected_variants["critical"]
    assert isinstance(result[7], html.Span)
    assert str(result[7]) == str(
        FILTER_BUTTONS_PROPERTIES["critical"]["icon"]
        if show_critical
        else FILTER_BUTTONS_PROPERTIES["critical"]["icon_disabled"]
    )

    assert result[8] == expected_variants["debug"]
    assert isinstance(result[9], html.Span)
    assert str(result[9]) == str(
        FILTER_BUTTONS_PROPERTIES["debug"]["icon"]
        if show_debug
        else FILTER_BUTTONS_PROPERTIES["debug"]["icon_disabled"]
    )


def test_initialize_show_levels_on_component_initialization_sets_defaults_when_none():
    """Initialize show levels with all levels enabled when store is not set yet."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    result = LogsSupervisor.initialize_show_levels_on_component_initialization(
        "dummy-grid-id",
        None,
    )

    assert result == {
        "info": True,
        "warning": True,
        "error": True,
        "critical": True,
        "debug": True,
    }


def test_initialize_show_levels_on_component_initialization_prevents_update_when_set():
    """Prevent update when show levels are already initialized."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    with pytest.raises(PreventUpdate):
        LogsSupervisor.initialize_show_levels_on_component_initialization(
            "dummy-grid-id",
            {
                "info": True,
                "warning": False,
                "error": True,
                "critical": False,
                "debug": True,
            },
        )


def test_initialize_grid_filter_model_from_store_no_file_change_and_existing_filter():
    """Use the stored filter model when the tracked file and format have not changed."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    # Store has some filter model
    filter_model_store = {
        "levelname": {"filterType": "text", "type": "contains", "filter": "WARNING"},
        "message": {"filterType": "text", "type": "contains", "filter": "timeout"},
    }
    # Grid has different filter model
    filter_model = {"levelname": {"filterType": "text", "type": "contains", "filter": "ERROR"}}

    log_file_and_format = {
        "log_file_path": "dummy.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    result = LogsSupervisor.initialize_grid_filter_model_from_store_and_reset_supervision_active_on_file_change(
        "dummy-grid-id",
        filter_model_store,
        filter_model,
        log_file_and_format,
        copy.deepcopy(log_file_and_format),
    )

    # Should return the store's filter model and keep other outputs unchanged
    assert result == (filter_model_store, no_update, no_update)


def test_initialize_grid_filter_model_from_store_prevents_update_when_same_and_no_file_change():
    """Raise PreventUpdate when no file change happened and models are already in sync."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    # Both store and grid have the same filter model
    same_filter = {"levelname": {"filterType": "text", "type": "contains", "filter": "ERROR"}}
    log_file_and_format = {
        "log_file_path": "dummy.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    with pytest.raises(PreventUpdate):
        LogsSupervisor.initialize_grid_filter_model_from_store_and_reset_supervision_active_on_file_change(
            "dummy-grid-id",
            same_filter,
            same_filter,
            log_file_and_format,
            copy.deepcopy(log_file_and_format),
        )


def test_initialize_grid_filter_model_from_store_resets_on_file_change_and_keeps_levelname_filter():
    """Reset non-level filters and supervision state when the tracked file changes."""
    LogsSupervisor(
        log_file="dummy.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    filter_model_store = {
        "levelname": {"filterType": "text", "type": "contains", "filter": "ERROR"},
        "message": {"filterType": "text", "type": "contains", "filter": "timeout"},
    }
    previous_file_and_format = {
        "log_file_path": "old.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    current_file_and_format = {
        "log_file_path": "new.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    result = LogsSupervisor.initialize_grid_filter_model_from_store_and_reset_supervision_active_on_file_change(
        "dummy-grid-id",
        filter_model_store,
        {"message": {"filterType": "text", "type": "contains", "filter": "other"}},
        current_file_and_format,
        previous_file_and_format,
    )

    assert result == (
        {"levelname": filter_model_store["levelname"]},
        current_file_and_format,
        False,
    )


def test_initialize_grid_filter_model_from_store_resets_to_empty_on_file_change_without_levelname():
    """Reset to an empty filter model when file changes and no levelname filter is stored."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    previous_file_and_format = {
        "log_file_path": "old.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    current_file_and_format = {
        "log_file_path": "new.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    result = LogsSupervisor.initialize_grid_filter_model_from_store_and_reset_supervision_active_on_file_change(
        "dummy-grid-id",
        {"message": {"filterType": "text", "type": "contains", "filter": "timeout"}},
        {"message": {"filterType": "text", "type": "contains", "filter": "other"}},
        current_file_and_format,
        previous_file_and_format,
    )

    assert result == ({}, current_file_and_format, False)


def test_initialize_grid_filter_model_from_store_resets_to_empty_on_file_change_when_store_none():
    """Reset to empty filter model when file changes and filter model store is None."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    previous_file_and_format = {
        "log_file_path": "old.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    current_file_and_format = {
        "log_file_path": "new.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    result = LogsSupervisor.initialize_grid_filter_model_from_store_and_reset_supervision_active_on_file_change(
        "dummy-grid-id",
        None,  # type: ignore[arg-type] - explicitly test missing store data
        {"message": {"filterType": "text", "type": "contains", "filter": "other"}},
        current_file_and_format,
        previous_file_and_format,
    )

    assert result == ({}, current_file_and_format, False)


def test_initialize_grid_filter_model_from_store_no_file_change_and_empty_store():
    """Use empty store model when unchanged file/format and store is initialized as empty dict."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    log_file_and_format = {
        "log_file_path": "dummy.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    result = LogsSupervisor.initialize_grid_filter_model_from_store_and_reset_supervision_active_on_file_change(
        "dummy-grid-id",
        {},
        {"message": {"filterType": "text", "type": "contains", "filter": "other"}},
        log_file_and_format,
        copy.deepcopy(log_file_and_format),
    )

    assert result == ({}, no_update, no_update)


def test_initialize_grid_filter_model_from_store_no_file_change_and_store_none():
    """Return empty filter model when unchanged file/format and store value is None."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    log_file_and_format = {
        "log_file_path": "dummy.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    result = LogsSupervisor.initialize_grid_filter_model_from_store_and_reset_supervision_active_on_file_change(
        "dummy-grid-id",
        None,  # type: ignore[arg-type] - explicitly test missing store data
        {"message": {"filterType": "text", "type": "contains", "filter": "other"}},
        log_file_and_format,
        copy.deepcopy(log_file_and_format),
    )

    assert result == ({}, no_update, no_update)


def test_store_grid_filter_model_updates_store():
    """Test store_grid_filter_model updates the store when grid filter changes."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    # Grid has new filter model
    filter_model = {
        "levelname": {"filterType": "text", "type": "contains", "filter": "ERROR"},
        "message": {"filterType": "text", "type": "startsWith", "filter": "Failed"},
    }
    # Store has different filter model
    filter_model_store = {"levelname": {"filterType": "text", "type": "contains", "filter": "WARNING"}}

    result = LogsSupervisor.store_grid_filter_model(
        filter_model,
        filter_model_store,
    )

    # Should return the new filter model to update the store
    assert result == filter_model


def test_store_grid_filter_model_prevents_update_when_same():
    """Test store_grid_filter_model raises PreventUpdate when models are the same."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    # Both grid and store have the same filter model
    same_filter = {
        "levelname": {"filterType": "text", "type": "contains", "filter": "ERROR"},
        "message": {"filterType": "text", "type": "contains", "filter": "timeout"},
    }

    with pytest.raises(PreventUpdate):
        LogsSupervisor.store_grid_filter_model(
            same_filter,
            same_filter,
        )


@pytest.mark.parametrize(
    ("activate_monitoring_data", "initial_active", "expected_active"),
    [
        (None, False, no_update),
        (True, False, True),
        (False, True, False),
        (True, True, no_update),
        (False, False, no_update),
    ],
)
def test_activate_monitoring_from_external_store(
    activate_monitoring_data: bool | None,
    initial_active: bool,
    expected_active: bool | NoUpdate,
):
    """Verify supervision state updates when external activation store data changes."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    if activate_monitoring_data is None:
        with pytest.raises(PreventUpdate):
            LogsSupervisor.activate_monitoring_from_external_store(
                activate_monitoring_data,
                initial_active,
            )
        return

    updated_active = LogsSupervisor.activate_monitoring_from_external_store(
        activate_monitoring_data,
        initial_active,
    )

    assert updated_active == expected_active


@pytest.mark.parametrize(
    ("activate_monitoring_checked", "initial_active", "expected_active"),
    [
        (True, False, True),
        (False, True, False),
        (True, True, no_update),
        (False, False, no_update),
    ],
)
def test_activate_monitoring_from_ui_switch(
    activate_monitoring_checked: bool,
    initial_active: bool,
    expected_active: bool | NoUpdate,
):
    """Verify supervision state updates when the internal switch is toggled."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    updated_active = LogsSupervisor.activate_monitoring_from_ui_switch(
        activate_monitoring_checked,
        initial_active,
    )

    assert updated_active == expected_active


@pytest.mark.parametrize(
    (
        "supervision_active",
        "initial_interval_disabled",
        "initial_activate_monitoring_checked",
        "expected_interval_disabled",
        "expected_activate_monitoring_checked",
    ),
    [
        (True, False, True, no_update, no_update),
        (True, False, False, no_update, True),
        (True, True, True, False, no_update),
        (True, True, False, False, True),
        (False, True, False, no_update, no_update),
        (False, True, True, no_update, False),
        (False, False, False, True, no_update),
        (False, False, True, True, False),
    ],
)
def test_start_stop_supervision(
    supervision_active: bool,
    initial_interval_disabled: bool,
    initial_activate_monitoring_checked: bool,
    expected_interval_disabled: bool | NoUpdate,
    expected_activate_monitoring_checked: bool | NoUpdate,
):
    """Verify activate_monitoring toggles interval and control states correctly."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    updated_interval_disabled, updated_activate_monitoring_checked = LogsSupervisor.start_stop_supervision(
        supervision_active,
        initial_interval_disabled,
        initial_activate_monitoring_checked,
    )

    assert updated_interval_disabled == expected_interval_disabled
    assert updated_activate_monitoring_checked == expected_activate_monitoring_checked


def test_start_stop_supervision_prevents_update_when_supervision_active_is_none():
    """Verify start_stop_supervision raises PreventUpdate when supervision_active is None."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    with pytest.raises(PreventUpdate):
        LogsSupervisor.start_stop_supervision(
            None,
            False,
            False,
        )


def test_update_grid_with_valid_data(
    sample_log_data: pd.DataFrame,
):
    """Test update_grid callback with valid data."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
    }

    with mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock:
        parse_mock.return_value = LogsParseResult(
            status=ParseStatus.SUCCESS_WITH_ROWS,
            data=sample_log_data,
            error=None,
        )

        new_row_data, new_grid_options = LogsSupervisor.update_grid(
            1,
            data,
            [],
            old_grid_options,
            True,
        )

    parse_mock.assert_called_once_with(data["log_file_path"], data["log_format"])
    assert new_row_data == sample_log_data.to_dict(orient="records")
    assert new_grid_options is no_update


def test_update_grid_with_none_interval():
    """Test update_grid callback still processes when n_intervals is None."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
    }

    sample_log_data = pd.DataFrame(
        {
            "asctime": ["2024-01-01 10:00:00"],
            "levelname": ["INFO"],
            "message": ["Test"],
        },
    )

    with mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock:
        parse_mock.return_value = LogsParseResult(
            status=ParseStatus.SUCCESS_WITH_ROWS,
            data=sample_log_data,
            error=None,
        )

        row_data, grid_options = LogsSupervisor.update_grid(
            None,  # type: ignore - deliberately passing None to validate behavior
            data,
            [],
            old_grid_options,
            True,
        )

    assert row_data == sample_log_data.to_dict(orient="records")
    assert grid_options is no_update


def test_update_grid_with_none_data():
    """Test update_grid callback when data is None."""
    with pytest.raises(PreventUpdate):
        LogsSupervisor.update_grid(
            1,
            None,  # type: ignore - deliberately passing None to test this case
            [],
            {},
            True,
        )


def test_update_grid_with_none_log_file_path():
    """Test update_grid callback when log_file_path is None."""
    LogsSupervisor(
        log_file="dummy_log.log",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        aio_id="test-id",
    )

    data = {
        "log_file_path": None,
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    with pytest.raises(PreventUpdate):
        LogsSupervisor.update_grid(1, data, [], {}, True)


def test_update_grid_parsing_fails_with_notification_enabled():
    """Test update_grid callback when parsing fails and notifications are enabled."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
    }

    with (
        mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock,
        mock.patch("ansys.solutions.dash_super_components.logs_supervisor.set_props") as set_props_mock,
    ):
        parse_result = LogsParseResult(
            status=ParseStatus.FAILURE,
            data=pd.DataFrame(),
            error="Parsing failed",
        )
        parse_mock.return_value = parse_result

        row_data, grid_options = LogsSupervisor.update_grid(
            1,
            data,
            [{"dummy": "old"}],
            old_grid_options,
            True,
        )

    assert row_data == []
    assert grid_options == {
        "noRowsOverlayComponentParams": {"message": PARSING_FAILED_NO_ROWS_MESSAGE},
    }

    expected_message = (
        "Failed to process log file. Error details: Parsing failed Please check the log file path and format."
    )
    expected_notification = {
        "title": "Error processing log file",
        "id": LogsSupervisor._error_notification_id(
            data["log_file_path"],
            data["log_format"],
            parse_result,
        ),
        "action": "show",
        "color": CommonColors.MANTINE_ERROR,
        "message": expected_message,
        "autoClose": False,
    }

    set_props_mock.assert_called_once_with(
        config._config.notification_container_id,
        {"sendNotifications": [expected_notification]},
    )


def test_update_grid_parsing_fails_with_notification_enabled_no_change_does_not_notify_again():
    """Test parse-failure notifications are not emitted when state is unchanged."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PARSING_FAILED_NO_ROWS_MESSAGE},
    }

    with (
        mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock,
        mock.patch("ansys.solutions.dash_super_components.logs_supervisor.set_props") as set_props_mock,
    ):
        parse_mock.return_value = LogsParseResult(
            status=ParseStatus.FAILURE,
            data=pd.DataFrame(),
            error="Parsing failed",
        )

        row_data, grid_options = LogsSupervisor.update_grid(
            1,
            data,
            [],
            old_grid_options,
            True,
        )

    assert row_data is no_update
    assert grid_options is no_update
    assert set_props_mock.call_count == 0


def test_update_grid_parsing_fails_with_notification_disabled():
    """Test update_grid callback when parsing fails and notifications are disabled."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
    }

    with (
        mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock,
        mock.patch("ansys.solutions.dash_super_components.logs_supervisor.set_props") as set_props_mock,
    ):
        parse_mock.return_value = LogsParseResult(
            status=ParseStatus.FAILURE,
            data=pd.DataFrame(),
            error="Parsing failed",
        )

        row_data, grid_options = LogsSupervisor.update_grid(
            1,
            data,
            [{"dummy": "old"}],
            old_grid_options,
            False,
        )

    assert row_data == []
    assert grid_options == {
        "noRowsOverlayComponentParams": {"message": PARSING_FAILED_NO_ROWS_MESSAGE},
    }
    assert set_props_mock.call_count == 0


def test_update_grid_source_missing_sets_source_missing_overlay():
    """Test update_grid callback when source is missing."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
    }

    with mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock:
        parse_mock.return_value = LogsParseResult(
            status=ParseStatus.SOURCE_MISSING,
            data=pd.DataFrame(),
            error="Log source is not available.",
        )

        row_data, grid_options = LogsSupervisor.update_grid(
            1,
            data,
            [{"dummy": "old"}],
            old_grid_options,
            True,
        )

    assert row_data == []
    assert grid_options == {
        "noRowsOverlayComponentParams": {"message": SOURCE_MISSING_NO_ROWS_MESSAGE},
    }


def test_update_grid_no_matching_rows_sets_parsing_failed_overlay():
    """Test update_grid callback when no rows match the format."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
    }

    with mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock:
        parse_mock.return_value = LogsParseResult(
            status=ParseStatus.SUCCESS_NO_MATCHING_ROWS,
            data=pd.DataFrame(),
            error="No matching rows found.",
        )

        row_data, grid_options = LogsSupervisor.update_grid(
            1,
            data,
            [{"dummy": "old"}],
            old_grid_options,
            False,
        )

    assert row_data == []
    assert grid_options == {
        "noRowsOverlayComponentParams": {"message": PARSING_FAILED_NO_ROWS_MESSAGE},
    }


def test_update_grid_no_matching_rows_with_notification_enabled_asserts_message_payload():
    """Test no-matching-rows notifications include expected message payload."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }
    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
    }

    with (
        mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock,
        mock.patch("ansys.solutions.dash_super_components.logs_supervisor.set_props") as set_props_mock,
    ):
        parse_result = LogsParseResult(
            status=ParseStatus.SUCCESS_NO_MATCHING_ROWS,
            data=pd.DataFrame(),
            error="No matching rows found.",
        )
        parse_mock.return_value = parse_result

        row_data, grid_options = LogsSupervisor.update_grid(
            1,
            data,
            [{"dummy": "old"}],
            old_grid_options,
            True,
        )

    assert row_data == []
    assert grid_options == {
        "noRowsOverlayComponentParams": {"message": PARSING_FAILED_NO_ROWS_MESSAGE},
    }

    expected_message = (
        "Failed to process log file. Error details: No matching rows found. Please check the log file path and format."
    )
    expected_notification = {
        "title": "Error processing log file",
        "id": LogsSupervisor._error_notification_id(
            data["log_file_path"],
            data["log_format"],
            parse_result,
        ),
        "action": "show",
        "color": CommonColors.MANTINE_ERROR,
        "message": expected_message,
        "autoClose": False,
    }

    set_props_mock.assert_called_once_with(
        config._config.notification_container_id,
        {"sendNotifications": [expected_notification]},
    )


def test_update_grid_data_unchanged(
    sample_log_data: pd.DataFrame,
):
    """Test update_grid callback when parsed data is unchanged."""
    data = {
        "log_file_path": "/path/to/test.log",
        "log_format": "%(asctime)s - %(levelname)s - %(message)s",
    }

    old_data = sample_log_data.to_dict(orient="records")
    old_grid_options = {
        "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
    }

    with mock.patch.object(LogsSupervisor, "_parse_logs_with_status") as parse_mock:
        parse_mock.return_value = LogsParseResult(
            status=ParseStatus.SUCCESS_WITH_ROWS,
            data=sample_log_data,
            error=None,
        )

        result = LogsSupervisor.update_grid(
            1,
            data,
            cast("list[dict[str, Any]]", old_data),
            old_grid_options,
            True,
        )

    assert result == (no_update, no_update)


def test_get_logging_formatter_representation():
    """Test get_logging_formatter_representation structure and contents."""
    expected_fields = [
        "asctime",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "taskName",
        "thread",
        "threadName",
    ]

    non_default_fields = [
        "levelname",
        "message",
        "levelno",
        "lineno",
        "msecs",
        "process",
        "relativeCreated",
        "thread",
        "pathname",
    ]

    default_fields = [field for field in expected_fields if field not in non_default_fields]

    # assert minimum structure and contents for all fields + defaults for default fields
    for field in expected_fields:
        field_representation = LogsSupervisor.get_logging_formatter_representation(field)
        assert isinstance(field_representation, dict)
        assert field_representation["field"] == field
        assert field_representation["tooltipField"] == field

        assert "headerName" in field_representation
        assert field_representation["headerName"] == SUPPORTED_LOGGING_FORMATTER_OPTIONS_AND_HEADERS[field]

        assert "cellStyle" in field_representation
        if field in default_fields:
            assert field_representation["cellStyle"] == {"textAlign": "left"}

        assert "flex" in field_representation
        if field in default_fields:
            assert field_representation["flex"] == 3

        assert "minWidth" in field_representation
        if field in default_fields:
            assert field_representation["minWidth"] == 120

    # assert specific contents for non-default fields
    for field in non_default_fields:
        field_representation = LogsSupervisor.get_logging_formatter_representation(field)

        if field == "levelname":
            assert field_representation["cellRenderer"] == "DMC_Badge_Level_Name"
            assert field_representation["filter"] == "agTextColumnFilter"
            assert (
                # explicit comparison to ensure the value is exactly True (not just truthy)
                field_representation["suppressHeaderMenuButton"] == True  # noqa: E712
            )  # manual filtering should be disabled for this column
            assert field_representation["filterParams"] == {
                "maxNumConditions": 5,
                "filterOptions": ["contains", "startsWith", "endsWith"],
                "defaultOption": "contains",
            }
            assert field_representation["cellRendererParams"] == {
                "variant": "filled",
                "radius": "xl",
                "size": "xs",
                "style": {"width": "60%"},
            }
            assert field_representation["flex"] == 2
            assert field_representation["cellStyle"] == {
                "textAlign": "center",
            }

        elif field == "message":
            assert field_representation["flex"] == 5
            assert field_representation["minWidth"] == 200

        elif (
            field == "levelno"
            or field == "lineno"
            or field == "msecs"
            or field == "process"
            or field == "relativeCreated"
            or field == "thread"
        ):
            assert field_representation["flex"] == 2
            assert field_representation["minWidth"] == 100

        elif field == "pathname":
            assert field_representation["flex"] == 4
            assert field_representation["minWidth"] == 150

        else:
            pytest.fail(f"Unexpected non-default field: {field}")


# Helper functions
def _assert_structure_except_rows_and_columns(
    current_aio_id: str,
    supervisor: LogsSupervisor,
    log_file: str,
    log_format: str,
    input_interval: int | None = None,
    input_grid_props: dict[str, Any] | None = None,
    width: str | int | None = None,
):
    expected_interval = input_interval if input_interval is not None else 3000
    expected_width = width if width is not None else "100%"

    assert isinstance(supervisor, html.Div)
    assert supervisor.children is not None
    assert len(supervisor.children) == 1

    inner_div = supervisor.children[0]
    assert inner_div.style == {
        "width": expected_width,
        "display": "flex",
        "margin": "auto",
        "flexDirection": "column",
    }

    # inner_div.children contains 11 components in this order:
    # 0: header
    # 1: spacer
    # 2: grid
    # 3: log_file_and_format_store
    # 4: log_file_and_format_persist_store
    # 5: show_levels_store
    # 6: filter_model_store
    # 7: supervision_active_store
    # 8: activate_monitoring_store
    # 9: show_error_notifications_store
    # 10: interval
    assert len(inner_div.children) == 11

    header_div = inner_div.children[0]
    assert isinstance(header_div, html.Div)
    _assert_header_div(current_aio_id, header_div)

    spacer_div = inner_div.children[1]
    assert isinstance(spacer_div, dmc.Space)
    assert spacer_div.h == 5

    grid_div = inner_div.children[2]
    assert isinstance(grid_div, html.Div)
    assert getattr(grid_div, "style", None) is None

    grid = grid_div.children
    assert isinstance(grid, dag.AgGrid)
    _assert_grid_except_rows_and_columns(current_aio_id, grid, input_grid_props)

    log_file_and_format_store = inner_div.children[3]
    assert isinstance(log_file_and_format_store, dcc.Store)
    _assert_log_file_and_format_store(current_aio_id, log_file_and_format_store, log_file, log_format)

    log_file_and_format_persist_store = inner_div.children[4]
    assert isinstance(log_file_and_format_persist_store, dcc.Store)
    _assert_log_file_and_format_persist_store(
        current_aio_id,
        log_file_and_format_persist_store,
        log_file,
        log_format,
    )

    show_levels_store = inner_div.children[5]
    assert isinstance(show_levels_store, dcc.Store)
    _assert_show_levels_store(current_aio_id, show_levels_store)

    filter_model_store = inner_div.children[6]
    assert isinstance(filter_model_store, dcc.Store)
    _assert_filter_model_store(current_aio_id, filter_model_store)

    supervision_active_store = inner_div.children[7]
    assert isinstance(supervision_active_store, dcc.Store)
    _assert_supervision_active_store(current_aio_id, supervision_active_store)

    activate_monitoring_store = inner_div.children[8]
    assert isinstance(activate_monitoring_store, dcc.Store)
    _assert_activate_monitoring_store(current_aio_id, activate_monitoring_store)

    show_error_notifications_store = inner_div.children[9]
    assert isinstance(show_error_notifications_store, dcc.Store)
    _assert_show_error_notifications_store(current_aio_id, show_error_notifications_store)

    interval_div = inner_div.children[10]
    assert isinstance(interval_div, dcc.Interval)
    _assert_interval(current_aio_id, interval_div, expected_interval)


def _assert_header_div(current_aio_id: str, header_div: html.Div):
    assert header_div.style == {
        "display": "flex",
        "flexDirection": "row",
        "alignItems": "center",
        "justifyContent": "space-between",
    }
    assert header_div.children is not None
    assert len(header_div.children) == 2

    buttons_div = header_div.children[0]
    assert isinstance(buttons_div, html.Div)
    _assert_buttons_div(current_aio_id, buttons_div)

    switch_div = header_div.children[1]
    assert isinstance(switch_div, html.Div)
    _assert_switch_div(current_aio_id, switch_div)


def _assert_buttons_div(current_aio_id: str, buttons_div: html.Div):
    assert buttons_div.style == {
        "display": "flex",
        "flexDirection": "row",
        "alignItems": "center",
    }

    buttons_title = buttons_div.children[0]
    assert isinstance(buttons_title, dmc.Text)
    assert buttons_title.children == "Log Level"
    assert buttons_title.style == {"fontSize": "18px"}

    buttons_group = buttons_div.children[1]
    assert isinstance(buttons_group, dmc.Group)
    _assert_buttons(current_aio_id, buttons_group)


def _assert_buttons(current_aio_id: str, buttons_group: dmc.Group):
    assert buttons_group.gap == "xs"
    assert buttons_group.justify == "left"
    assert buttons_group.style == {"marginLeft": "10px"}

    assert buttons_group.children is not None
    assert len(buttons_group.children) == len(FILTER_BUTTONS_PROPERTIES)

    info_button = buttons_group.children[0]
    assert isinstance(info_button, dmc.Button)
    _assert_button(
        info_button,
        LogsSupervisor.ids.info_button(current_aio_id),
        "INFO",
        FILTER_BUTTONS_PROPERTIES["info"]["color"],
        FILTER_BUTTONS_PROPERTIES["info"]["icon"],
    )

    warning_button = buttons_group.children[1]
    assert isinstance(warning_button, dmc.Button)
    _assert_button(
        warning_button,
        LogsSupervisor.ids.warning_button(current_aio_id),
        "WARNING",
        FILTER_BUTTONS_PROPERTIES["warning"]["color"],
        FILTER_BUTTONS_PROPERTIES["warning"]["icon"],
    )

    error_button = buttons_group.children[2]
    assert isinstance(error_button, dmc.Button)
    _assert_button(
        error_button,
        LogsSupervisor.ids.error_button(current_aio_id),
        "ERROR",
        FILTER_BUTTONS_PROPERTIES["error"]["color"],
        FILTER_BUTTONS_PROPERTIES["error"]["icon"],
    )

    critical_button = buttons_group.children[3]
    assert isinstance(critical_button, dmc.Button)
    _assert_button(
        critical_button,
        LogsSupervisor.ids.critical_button(current_aio_id),
        "CRITICAL",
        FILTER_BUTTONS_PROPERTIES["critical"]["color"],
        FILTER_BUTTONS_PROPERTIES["critical"]["icon"],
    )

    debug_button = buttons_group.children[4]
    assert isinstance(debug_button, dmc.Button)
    _assert_button(
        debug_button,
        LogsSupervisor.ids.debug_button(current_aio_id),
        "DEBUG",
        FILTER_BUTTONS_PROPERTIES["debug"]["color"],
        FILTER_BUTTONS_PROPERTIES["debug"]["icon"],
    )


def _assert_button(
    button: dmc.Button,
    expected_id: dict[str, str],
    expected_text: str,
    expected_icon_color: CommonColors,
    expected_icon: html.Span,
):
    assert button.children == expected_text
    assert button.id == expected_id
    assert button.color == expected_icon_color
    assert isinstance(button.leftSection, html.Span)
    assert str(button.leftSection) == str(expected_icon)
    assert button.size == "compact-xs"
    assert button.variant == "filled"
    assert button.styles == {
        "label": {"fontSize": "12px"},
        "icon": {"width": "12px", "height": "12px"},
    }


def _assert_switch_div(current_aio_id: str, switch_div: html.Div):
    assert switch_div.style == {
        "display": "flex",
        "flexDirection": "row",
        "alignItems": "center",
    }

    switch_hover_card = switch_div.children
    assert isinstance(switch_hover_card, dmc.HoverCard)
    assert switch_hover_card.withArrow
    assert switch_hover_card.shadow == "md"
    assert switch_hover_card.children is not None
    assert len(switch_hover_card.children) == 2

    switch_target = switch_hover_card.children[0]
    assert isinstance(switch_target, dmc.HoverCardTarget)

    switch = switch_target.children
    assert isinstance(switch, dmc.Switch)
    assert switch.id == LogsSupervisor.ids._activate_monitoring_switch(current_aio_id)
    assert not switch.checked
    assert switch.size == "sm"
    assert isinstance(switch.offLabel, html.Span)
    assert isinstance(switch.onLabel, html.Span)

    switch_dropdown = switch_hover_card.children[1]
    assert isinstance(switch_dropdown, dmc.HoverCardDropdown)
    assert isinstance(switch_dropdown.children, dmc.Text)
    assert switch_dropdown.children.children == "Enable/Disable logs monitoring."
    assert switch_dropdown.children.size == "sm"


def _assert_grid_except_rows_and_columns(
    current_aio_id: str,
    grid: dag.AgGrid,
    input_grid_props: dict[str, Any] | None = None,
):
    assert grid.id == LogsSupervisor.ids._grid(current_aio_id)

    if input_grid_props is None:
        input_grid_props = {}

    # assert style separately because it might have a default value even if the key exists in input
    input_style = input_grid_props.get("style", {"height": "200px"})
    assert grid.style == input_style

    expected_default_col_def = {
        "resizable": True,
        "sortable": True,
        "editable": False,
    }
    expected_default_col_def.update(input_grid_props.get("defaultColDef", {}))
    expected_default_col_def["filter"] = True
    assert grid.defaultColDef == expected_default_col_def
    assert grid.filterModel == input_grid_props.get("filterModel", {})
    assert getattr(grid, "className", "") == input_grid_props.get("className", "")
    assert grid.persistence == input_grid_props.get("persistence", True)
    assert grid.persisted_props == input_grid_props.get("persisted_props", ["columnState"])
    expected_dash_grid_options = {
        "suppressMovableColumns": True,
        "tooltipShowDelay": 500,
        "suppressScrollOnNewData": True,
        "theme": {
            "function": (
                "themeQuartz.withParams({ "
                "backgroundColor: 'var(--mantine-color-body, #fff)', "
                "foregroundColor: 'var(--mantine-color-text, #1a1b1e)' "
                "})"
            ),
        },
    }
    expected_dash_grid_options.update(input_grid_props.get("dashGridOptions", {}))
    expected_dash_grid_options.update(
        {
            "noRowsOverlayComponent": "DMC_NoRows_Overlay",
            "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
        },
    )
    assert grid.dashGridOptions == expected_dash_grid_options

    # assert all additional properties which do not have any default values
    for key in input_grid_props:
        if key not in [
            "style",
            "rowData",
            "columnDefs",
            "columnSize",
            "defaultColDef",
            "filterModel",
            "className",
            "persistence",
            "persisted_props",
            "persistence_type",
            "dashGridOptions",
        ]:
            assert getattr(grid, key) == input_grid_props[key]


def _assert_log_file_and_format_store(
    current_aio_id: str,
    store_div: dcc.Store,
    expected_log_file_path: str,
    expected_log_format: str,
):
    assert store_div.id == LogsSupervisor.ids._log_file_and_format(current_aio_id)
    assert store_div.data == {
        "log_file_path": expected_log_file_path,
        "log_format": expected_log_format,
    }
    assert store_div.storage_type == "memory"


def _assert_log_file_and_format_persist_store(
    current_aio_id: str,
    store_div: dcc.Store,
    expected_log_file_path: str,
    expected_log_format: str,
):
    assert store_div.id == LogsSupervisor.ids._log_file_and_format_persist(current_aio_id)
    store_data = getattr(store_div, "data", None)
    assert store_data is None
    assert store_div.storage_type == "session"


def _assert_show_levels_store(current_aio_id: str, store_div: dcc.Store):
    assert store_div.id == LogsSupervisor.ids._show_levels(current_aio_id)
    store_data = getattr(store_div, "data", None)
    assert store_data is None
    assert store_div.storage_type == "session"


def _assert_filter_model_store(current_aio_id: str, store_div: dcc.Store):
    assert store_div.id == LogsSupervisor.ids._filter_model_store(current_aio_id)
    store_data = getattr(store_div, "data", None)
    assert store_data is None
    assert store_div.storage_type == "session"


def _assert_supervision_active_store(
    current_aio_id: str,
    supervision_active_store: dcc.Store,
):
    assert supervision_active_store.id == LogsSupervisor.ids._supervision_active(
        current_aio_id,
    )
    assert supervision_active_store.storage_type == "session"
    assert getattr(supervision_active_store, "data", None) is None


def _assert_activate_monitoring_store(
    current_aio_id: str,
    activate_monitoring_store: dcc.Store,
):
    assert activate_monitoring_store.id == LogsSupervisor.ids.activate_monitoring(
        current_aio_id,
    )
    assert activate_monitoring_store.storage_type == "memory"
    assert getattr(activate_monitoring_store, "data", None) is None


def _assert_show_error_notifications_store(
    current_aio_id: str,
    show_error_notifications_store: dcc.Store,
):
    assert show_error_notifications_store.id == LogsSupervisor.ids._show_error_notifications(
        current_aio_id,
    )
    assert show_error_notifications_store.storage_type == "memory"
    assert show_error_notifications_store.data is True


def _assert_interval(current_aio_id: str, interval_div: dcc.Interval, interval: int):
    assert interval_div.id == LogsSupervisor.ids._interval(current_aio_id)
    assert interval_div.disabled
    assert interval_div.interval == interval


def _find_component_by_type(
    component: dict[str, Any],
    component_type: str,
) -> dict[str, Any] | None:
    """Recursively find a component by type in the component tree."""
    if isinstance(component, dict):
        if component.get("type") == component_type:
            return component

        # Search in props.children
        if "props" in component and "children" in component["props"]:
            children = component["props"]["children"]
            if isinstance(children, list):
                for child in children:
                    result = _find_component_by_type(child, component_type)
                    if result:
                        return result
            elif isinstance(children, dict):
                result = _find_component_by_type(children, component_type)
                if result:
                    return result

    return None
