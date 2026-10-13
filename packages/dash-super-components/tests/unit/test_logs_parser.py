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

"""Unit tests for logs parser module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from requests.exceptions import HTTPError, RequestException

from ansys.solutions.dash_super_components.utils.logs_parser import (
    PARSE_ERROR_MESSAGES,
    LogsParser,
    ParseStatus,
)


def test_logs_parser_initialization_with_string_path():
    """Test initialization with string file path."""
    path = "dummy.log"
    formatting_string = "%(asctime)s %(levelname)s %(message)s"

    parser = LogsParser(path, formatting_string)

    assert parser.log_file == path
    assert parser.log_format == formatting_string

    # Columns order should match the format string order
    assert isinstance(parser.columns, list)
    assert parser.columns == ["asctime", "levelname", "message"]

    # Verify pattern is a string containing regex for the placeholders
    assert isinstance(parser.pattern, str)
    assert parser.pattern == "(?P<asctime>[\\d-]+\\s[\\d:,]+)\\ (?P<levelname>\\w+)\\ (?P<message>.+)"


def test_logs_parser_initialization_with_path_object():
    """Test initialization with Path object."""
    path = Path("dummy.log")
    formatting_string = "%(asctime)s %(levelname)s %(message)s"

    parser = LogsParser(path, formatting_string)

    assert parser.log_file == path
    assert parser.log_format == formatting_string


def test_logs_parser_initialization_with_url():
    """Test initialization with URL."""
    url = "http://example.com/log.txt"
    formatting_string = "%(asctime)s %(levelname)s %(message)s"

    parser = LogsParser(url, formatting_string)

    assert parser.log_file == url
    assert parser.log_format == formatting_string


@pytest.mark.parametrize(
    ("formatting_string", "expected_columns", "expected_pattern"),
    [
        ("%(asctime)s", ["asctime"], "(?P<asctime>[\\d-]+\\s[\\d:,]+)"),
        (
            "%(created)f",
            ["created"],
            "(?P<created>[\\d.]+)",
        ),
        (
            "%(filename)s",
            ["filename"],
            "(?P<filename>[\\w.\\-]+)",
        ),
        ("%(funcName)s", ["funcName"], "(?P<funcName>[\\w.]+)"),
        ("%(levelname)s", ["levelname"], "(?P<levelname>\\w+)"),
        ("%(levelno)d", ["levelno"], "(?P<levelno>\\d+)"),
        ("%(lineno)d", ["lineno"], "(?P<lineno>\\d+)"),
        ("%(message)s", ["message"], "(?P<message>.+)"),
        ("%(module)s", ["module"], "(?P<module>[\\w.]+)"),
        (
            "%(msecs)d",
            ["msecs"],
            "(?P<msecs>\\d+)",
        ),
        ("%(name)s", ["name"], "(?P<name>[\\w.]+)"),
        ("%(pathname)s", ["pathname"], r"(?P<pathname>[\w.:/\\\-]+)"),
        (
            "%(process)d",
            ["process"],
            "(?P<process>\\d+)",
        ),
        ("%(processName)s", ["processName"], "(?P<processName>[\\w.\\-:]+)"),
        ("%(relativeCreated)d", ["relativeCreated"], "(?P<relativeCreated>[\\d.]+)"),
        (
            "%(thread)d",
            ["thread"],
            "(?P<thread>\\d+)",
        ),
        ("%(threadName)s", ["threadName"], "(?P<threadName>[\\w.]+)"),
        (
            "%(asctime)s %(levelname)s",
            ["asctime", "levelname"],
            "(?P<asctime>[\\d-]+\\s[\\d:,]+)\\ (?P<levelname>\\w+)",
        ),
        (
            "%(asctime)s - %(message)s",
            ["asctime", "message"],
            "(?P<asctime>[\\d-]+\\s[\\d:,]+)\\ \\-\\ (?P<message>.+)",
        ),
        (
            "%(msecs)d - %(message)s",
            ["msecs", "message"],
            "(?P<msecs>\\d+)\\ \\-\\ (?P<message>.+)",
        ),
        (
            "%(asctime)s %(lineno)d %(message)s",
            ["asctime", "lineno", "message"],
            "(?P<asctime>[\\d-]+\\s[\\d:,]+)\\ (?P<lineno>\\d+)\\ (?P<message>.+)",
        ),
    ],
)
def test_logs_parser_initialization_all_formatting_strings(
    formatting_string: str,
    expected_columns: list[str],
    expected_pattern: str,
):
    """Test initialization with all formatting strings."""
    parser = LogsParser("dummy.log", formatting_string)
    assert parser.log_file == "dummy.log"
    assert parser.log_format == formatting_string

    assert parser.columns == expected_columns

    assert parser.pattern == expected_pattern


def test_logs_parser_parse_file_path(monkeypatch: pytest.MonkeyPatch):
    """Test parsing log content from a file and ensure correct path is used."""
    log_content = "2025-11-17 12:00:00,123 INFO Hello world\n2025-11-17 12:01:00,456 ERROR Something failed"
    called_paths: list[Path] = []

    def mock_exists(self: Path) -> bool:
        called_paths.append(self)
        return True

    def mock_read_text(self: Path) -> str:
        called_paths.append(self)
        return log_content

    monkeypatch.setattr(Path, "exists", mock_exists)
    monkeypatch.setattr(Path, "read_text", mock_read_text)

    test_path = Path("dummy.log")
    parser = LogsParser(test_path, "%(asctime)s %(levelname)s %(message)s")
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SUCCESS_WITH_ROWS
    assert result.error is None
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.shape[0] == 2

    expected_data_frame = pd.DataFrame(
        {
            "asctime": ["2025-11-17 12:00:00,123", "2025-11-17 12:01:00,456"],
            "levelname": ["INFO", "ERROR"],
            "message": ["Hello world", "Something failed"],
        },
    )

    pd.testing.assert_frame_equal(result.data, expected_data_frame)

    # Check that exists and read_text were called for the correct path
    assert test_path in called_paths


def test_logs_parser_parse_file_string_path(monkeypatch: pytest.MonkeyPatch):
    """Test parsing log content from a path passed as a string."""
    log_content = "2025-11-17 12:00:00,123 INFO Hello world\n2025-11-17 12:01:00,456 ERROR Something failed"
    called_paths: list[Path] = []

    def mock_exists(self: Path) -> bool:
        called_paths.append(self)
        return True

    def mock_read_text(self: Path) -> str:
        called_paths.append(self)
        return log_content

    monkeypatch.setattr(Path, "exists", mock_exists)
    monkeypatch.setattr(Path, "read_text", mock_read_text)

    test_path = "dummy.log"
    parser = LogsParser(test_path, "%(asctime)s %(levelname)s %(message)s")
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SUCCESS_WITH_ROWS
    assert result.error is None
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.shape[0] == 2

    expected_data_frame = pd.DataFrame(
        {
            "asctime": ["2025-11-17 12:00:00,123", "2025-11-17 12:01:00,456"],
            "levelname": ["INFO", "ERROR"],
            "message": ["Hello world", "Something failed"],
        },
    )

    pd.testing.assert_frame_equal(result.data, expected_data_frame)

    # Check that exists and read_text were called for the correct path
    assert Path(test_path) in called_paths


def test_logs_parser_parse_url():
    """Test parsing log content from a URL."""
    log_content = "2025-11-17 12:00:00,123 INFO Hello world\n2025-11-17 12:01:00,456 ERROR Something failed"
    mock_response = MagicMock()
    mock_response.text = log_content
    mock_response.raise_for_status = MagicMock()

    with patch("ansys.solutions.dash_super_components.utils.logs_parser.requests.get") as mock_get:
        mock_get.return_value = mock_response

        url = "http://example.com/log.txt"
        parser = LogsParser(url, "%(asctime)s %(levelname)s %(message)s")
        result = parser.parse_with_status()

        mock_get.assert_called_once_with(url, timeout=10)

    assert result.status == ParseStatus.SUCCESS_WITH_ROWS
    assert result.error is None
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.shape[0] == 2

    expected_data_frame = pd.DataFrame(
        {
            "asctime": ["2025-11-17 12:00:00,123", "2025-11-17 12:01:00,456"],
            "levelname": ["INFO", "ERROR"],
            "message": ["Hello world", "Something failed"],
        },
    )

    pd.testing.assert_frame_equal(result.data, expected_data_frame)


def test_logs_parser_parse_empty_file(monkeypatch: pytest.MonkeyPatch):
    """Test parsing an empty log file."""
    monkeypatch.setattr(Path, "exists", lambda _: True)  # type: ignore
    monkeypatch.setattr(Path, "read_text", lambda _: "")  # type: ignore

    parser = LogsParser(Path("dummy.log"), "%(asctime)s %(levelname)s %(message)s")
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SUCCESS_EMPTY_FILE
    assert result.error is None
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.empty


def test_logs_parser_invalid_log_file_path():
    """Test handling of invalid log file path."""
    with pytest.raises(ValueError, match="log_file must be a string or Path object."):
        LogsParser(12345, "%(asctime)s %(levelname)s %(message)s")  # type: ignore - intentional


def test_logs_parser_nonexistent_file_path(monkeypatch: pytest.MonkeyPatch):
    """Test handling of nonexistent file path."""
    monkeypatch.setattr(Path, "exists", lambda self: False)  # type: ignore

    parser = LogsParser(Path("nonexistent.log"), "%(asctime)s %(levelname)s %(message)s")
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SOURCE_MISSING
    assert result.error == PARSE_ERROR_MESSAGES[ParseStatus.SOURCE_MISSING]
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.empty


def test_logs_parser_nonexistent_file_string_path(monkeypatch: pytest.MonkeyPatch):
    """Test handling of nonexistent file path passed as string."""
    monkeypatch.setattr(Path, "exists", lambda self: False)  # type: ignore

    parser = LogsParser("nonexistent.log", "%(asctime)s %(levelname)s %(message)s")
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SOURCE_MISSING
    assert result.error == PARSE_ERROR_MESSAGES[ParseStatus.SOURCE_MISSING]
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.empty


def test_logs_parser_url_request_error():
    """Test handling of request errors when parsing from URL."""
    with patch("ansys.solutions.dash_super_components.utils.logs_parser.requests.get") as mock_get:
        parser = LogsParser("http://example.com/log.txt", "%(asctime)s %(levelname)s %(message)s")

        mock_get.side_effect = RequestException("Connection error")

        result = parser.parse_with_status()

    assert result.status == ParseStatus.FAILURE
    assert result.error is not None
    assert result.error == "requests.exceptions.RequestException."
    assert result.data.empty


def test_logs_parser_url_http_404_returns_source_missing():
    """Test URL 404 handling maps to source-missing status."""
    http_error = HTTPError("Not found")
    http_error.response = MagicMock(status_code=404)

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = http_error

    with patch("ansys.solutions.dash_super_components.utils.logs_parser.requests.get") as mock_get:
        mock_get.return_value = mock_response
        parser = LogsParser("http://example.com/log.txt", "%(asctime)s %(levelname)s %(message)s")
        result = parser.parse_with_status()

    assert result.status == ParseStatus.SOURCE_MISSING
    assert result.error == PARSE_ERROR_MESSAGES[ParseStatus.SOURCE_MISSING]
    assert result.data.empty


def test_logs_parser_url_http_error_non_404_returns_failure():
    """Test non-404 HTTP errors are reported as failures."""
    http_error = HTTPError("Server error")
    http_error.response = MagicMock(status_code=500, reason="Internal Server Error")

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = http_error

    with patch("ansys.solutions.dash_super_components.utils.logs_parser.requests.get") as mock_get:
        mock_get.return_value = mock_response
        parser = LogsParser("http://example.com/log.txt", "%(asctime)s %(levelname)s %(message)s")
        result = parser.parse_with_status()

    assert result.status == ParseStatus.FAILURE
    assert result.error is not None
    assert result.error == "500 Server Error: Internal Server Error."
    assert result.data.empty


@pytest.mark.parametrize(
    ("log_content", "format_string", "expected_columns", "expected_data"),
    [
        (
            # test with only asctime
            "2025-11-17 12:00:00,123\n2025-11-17 12:01:00,456",
            "%(asctime)s",
            ["asctime"],
            [
                ["2025-11-17 12:00:00,123"],
                ["2025-11-17 12:01:00,456"],
            ],
        ),
        (
            # test with only created
            "1700304000.123\n1700304060.456",
            "%(created)f",
            ["created"],
            [
                ["1700304000.123"],
                ["1700304060.456"],
            ],
        ),
        (
            # test with only filename
            "app.log\nserver_file.log\nother-file.log",
            "%(filename)s",
            ["filename"],
            [
                ["app.log"],
                ["server_file.log"],
                ["other-file.log"],
            ],
        ),
        (
            # test with only funcName
            "my_function\nanother_function",
            "%(funcName)s",
            ["funcName"],
            [
                ["my_function"],
                ["another_function"],
            ],
        ),
        (
            # test with only levelname
            "INFO\nERROR",
            "%(levelname)s",
            ["levelname"],
            [
                ["INFO"],
                ["ERROR"],
            ],
        ),
        (
            # test with only levelno
            "20\n40",
            "%(levelno)d",
            ["levelno"],
            [
                ["20"],
                ["40"],
            ],
        ),
        (
            # test with only lineno
            "10\n20",
            "%(lineno)d",
            ["lineno"],
            [
                ["10"],
                ["20"],
            ],
        ),
        (
            # test with only message
            "Hello world\nSomething failed",
            "%(message)s",
            ["message"],
            [
                ["Hello world"],
                ["Something failed"],
            ],
        ),
        (
            # test with only module
            "main\nutils",
            "%(module)s",
            ["module"],
            [
                ["main"],
                ["utils"],
            ],
        ),
        (
            # test with only msecs
            "123\n456",
            "%(msecs)d",
            ["msecs"],
            [
                ["123"],
                ["456"],
            ],
        ),
        (
            # test with only name
            "root\nlogger",
            "%(name)s",
            ["name"],
            [
                ["root"],
                ["logger"],
            ],
        ),
        (
            # test with only pathname
            (
                "D:\\path\\to\\app.log\npath/to/server.log\n\\\\network\\share\\log.txt\npath"
                "/to-something-with-dashes/file.log"
            ),
            "%(pathname)s",
            ["pathname"],
            [
                ["D:\\path\\to\\app.log"],
                ["path/to/server.log"],
                ["\\\\network\\share\\log.txt"],
                ["path/to-something-with-dashes/file.log"],
            ],
        ),
        (
            # test with only process
            "12345\n67890",
            "%(process)d",
            ["process"],
            [
                ["12345"],
                ["67890"],
            ],
        ),
        (
            # test with only processName
            "MainProcess-1:1\nWorkerProcess-2:1",
            "%(processName)s",
            ["processName"],
            [
                ["MainProcess-1:1"],
                ["WorkerProcess-2:1"],
            ],
        ),
        (
            # test with only relativeCreated
            "1234.56\n7890.12\n2345",
            "%(relativeCreated)d",
            ["relativeCreated"],
            [
                ["1234.56"],
                ["7890.12"],
                ["2345"],
            ],
        ),
        (
            # test with only thread
            "1234\n5678",
            "%(thread)d",
            ["thread"],
            [
                ["1234"],
                ["5678"],
            ],
        ),
        (
            # test with only threadName
            "MainThread\nWorkerThread",
            "%(threadName)s",
            ["threadName"],
            [
                ["MainThread"],
                ["WorkerThread"],
            ],
        ),
        (
            # test with only taskName
            "MainTask\nWorkerTask",
            "%(taskName)s",
            ["taskName"],
            [
                ["MainTask"],
                ["WorkerTask"],
            ],
        ),
        (
            "2025-11-17 12:00:00,123 - INFO - 5 - Hello world - 24",
            "%(asctime)s - %(levelname)s - %(levelno)d - %(message)s - %(lineno)d",
            [
                "asctime",
                "levelname",
                "levelno",
                "message",
                "lineno",
            ],  # Columns order now matches the format string order
            [
                ["2025-11-17 12:00:00,123", "INFO", "5", "Hello world", "24"],
            ],
        ),
    ],
)
def test_logs_parser_parse_all_patterns(
    monkeypatch: pytest.MonkeyPatch,
    log_content: str,
    format_string: str,
    expected_columns: list[str],
    expected_data: list[list[str]],
):
    """Test parse_with_status with all supported patterns."""
    monkeypatch.setattr(Path, "exists", lambda self: True)  # type: ignore
    monkeypatch.setattr(Path, "read_text", lambda self: log_content)  # type: ignore

    parser = LogsParser(Path("dummy.log"), format_string)
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SUCCESS_WITH_ROWS
    assert result.error is None
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.shape[0] == len(expected_data)
    assert list(result.data.columns) == expected_columns
    assert result.data.values.tolist() == expected_data


def test_logs_parser_parse_no_matching_lines(monkeypatch: pytest.MonkeyPatch):
    """Test parse_with_status when no lines match the format."""
    monkeypatch.setattr(Path, "exists", lambda self: True)  # type: ignore
    monkeypatch.setattr(Path, "read_text", lambda self: "not a log line\nanother bad line")  # type: ignore

    parser = LogsParser(Path("dummy.log"), "%(asctime)s %(levelname)s %(message)s")
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SUCCESS_NO_MATCHING_ROWS
    assert result.error == PARSE_ERROR_MESSAGES[ParseStatus.SUCCESS_NO_MATCHING_ROWS]
    assert result.data.empty


def test_logs_parser_parse_missing_fields(monkeypatch: pytest.MonkeyPatch):
    """Test parse_with_status when some fields are missing in log lines."""
    monkeypatch.setattr(Path, "exists", lambda self: True)  # type: ignore
    monkeypatch.setattr(Path, "read_text", lambda self: "2025-11-17 12:00:00,123 INFO")  # type: ignore

    parser = LogsParser(Path("dummy.log"), "%(asctime)s %(levelname)s %(message)s")
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SUCCESS_NO_MATCHING_ROWS
    assert result.error == PARSE_ERROR_MESSAGES[ParseStatus.SUCCESS_NO_MATCHING_ROWS]
    assert result.data.empty


def test_logs_parser_mixed_matching_lines(monkeypatch: pytest.MonkeyPatch):
    """Test parse_with_status when some lines match and some don't."""
    log_content = (
        "2025-11-17 12:00:00,123 INFO Valid line\nInvalid line format\n2025-11-17 12:01:00,456 ERROR Another valid line"
    )
    monkeypatch.setattr(Path, "exists", lambda self: True)  # type: ignore
    monkeypatch.setattr(Path, "read_text", lambda self: log_content)  # type: ignore

    parser = LogsParser(Path("dummy.log"), "%(asctime)s %(levelname)s %(message)s")
    result = parser.parse_with_status()

    # Should only parse the two valid lines
    assert result.status == ParseStatus.SUCCESS_WITH_ROWS
    assert result.error is None
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.shape[0] == 2
    assert result.data.iloc[0]["message"] == "Valid line"
    assert result.data.iloc[1]["message"] == "Another valid line"


def test_logs_parser_column_order_matches_format_string(monkeypatch: pytest.MonkeyPatch):
    """Test that column order in result DataFrame matches the format string order."""
    # Use a format string where alphabetical order differs from appearance order
    format_string = "%(asctime)s - %(levelname)s - %(levelno)d - %(message)s - %(lineno)d"
    log_content = "2025-11-17 12:00:00,123 - INFO - 20 - Test message - 42"

    monkeypatch.setattr(Path, "exists", lambda self: True)  # type: ignore
    monkeypatch.setattr(Path, "read_text", lambda self: log_content)  # type: ignore

    parser = LogsParser(Path("dummy.log"), format_string)
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SUCCESS_WITH_ROWS
    assert result.error is None
    df = result.data

    # Verify columns are in the same order as they appear in the format string
    expected_column_order = ["asctime", "levelname", "levelno", "message", "lineno"]
    assert list(df.columns) == expected_column_order

    # Verify the data is correctly parsed in the right order
    assert df.iloc[0]["asctime"] == "2025-11-17 12:00:00,123"
    assert df.iloc[0]["levelname"] == "INFO"
    assert df.iloc[0]["levelno"] == "20"
    assert df.iloc[0]["message"] == "Test message"
    assert df.iloc[0]["lineno"] == "42"


def test_logs_parser_column_order_reverse_format(monkeypatch: pytest.MonkeyPatch):
    """Test column order with a reversed format string to ensure order is preserved."""
    # Reverse the typical order to verify column order follows format string
    format_string = "%(message)s - %(levelname)s - %(asctime)s"
    log_content = "Test message - INFO - 2025-11-17 12:00:00,123"

    monkeypatch.setattr(Path, "exists", lambda self: True)  # type: ignore
    monkeypatch.setattr(Path, "read_text", lambda self: log_content)  # type: ignore

    parser = LogsParser(Path("dummy.log"), format_string)
    result = parser.parse_with_status()

    assert result.status == ParseStatus.SUCCESS_WITH_ROWS
    assert result.error is None
    df = result.data

    # Columns should be in the order: message, levelname, asctime
    expected_column_order = ["message", "levelname", "asctime"]
    assert list(df.columns) == expected_column_order

    # Verify data is parsed correctly
    assert df.iloc[0]["message"] == "Test message"
    assert df.iloc[0]["levelname"] == "INFO"
    assert df.iloc[0]["asctime"] == "2025-11-17 12:00:00,123"
