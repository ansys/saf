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


"""Test fixtures and helpers used across unit tests."""

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest import mock

from dash._callback_context import CallbackContext
import plotly
import pytest

tests_directory = Path(__file__).parent.absolute()

project_directory = Path(__file__).parent.parent.absolute()


def as_json(component: Any) -> dict[str, Any]:
    """Transform a Plotly Dash component to a browsable json object."""
    return json.loads(json.dumps(component, cls=plotly.utils.PlotlyJSONEncoder))


# A fixture to retrieve the current test name
@pytest.fixture
def test_name(request: pytest.FixtureRequest) -> str:
    """Return the name of the currently running test."""
    # Access the name of the currently running test
    return request.node.name  # type: ignore


def dump_structures(
    test_folder: str,
    test_name: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> str:
    """Dump the expected and actual structures to json files for easier comparison."""
    output_path = tests_directory / "outputs"
    expected_struct_path = output_path / "expected_structures" / test_folder / f"{test_name}_expected_structure.json"
    actual_struct_path = output_path / "actual_structures" / test_folder / f"{test_name}_actual_structure.json"

    expected_struct_path.parent.mkdir(parents=True, exist_ok=True)
    actual_struct_path.parent.mkdir(parents=True, exist_ok=True)

    with expected_struct_path.open("w") as f:
        json.dump(expected, f, indent=4)
    with actual_struct_path.open("w") as f:
        json.dump(actual, f, indent=4)

    return "Please check and compare the expected and actual structure files generated in tests/outputs."


# Global variable to store the callback context mock
# This is initialized in pytest_configure before any test module is imported
_callback_context_mock: mock.MagicMock | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest before any test module is imported.

    This hook runs before any test collection, allowing us to patch dash.callback_context
    at the original import path before any test modules import it. This approach is preferred
    over patching individual paths in each test.
    """
    global _callback_context_mock

    # Mock the callback context for all tests
    _callback_context_mock = mock.MagicMock(spec=CallbackContext)
    mock.patch("dash.callback_context", _callback_context_mock).start()
    mock.patch("dash.ctx", _callback_context_mock).start()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Clean up all started patches after the test session."""
    # not strictly necessary as all patches will be undone on process exit,
    # but good practice to clean up
    mock.patch.stopall()


@pytest.fixture
def callback_context_mock() -> Generator[mock.MagicMock, None, None]:
    """Function-scoped fixture that provides access to the global callback context mock.

    The mock is reset before and after each test to ensure test isolation.
    """
    global _callback_context_mock
    assert _callback_context_mock is not None, "Mock not initialized in pytest_configure"

    _callback_context_mock.reset_mock(return_value=True, side_effect=True)
    yield _callback_context_mock
    _callback_context_mock.reset_mock(return_value=True, side_effect=True)
