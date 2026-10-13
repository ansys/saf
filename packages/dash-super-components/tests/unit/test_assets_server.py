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

"""Unit tests for assets_server module."""

from pathlib import Path
from unittest import mock

from dash_extensions.enrich import DashProxy
import pytest

from ansys.solutions.dash_super_components.utils.assets_server import (
    add_super_components_assets,
)


@pytest.fixture
def mock_dash_app():
    """Create a mock DashProxy application for testing."""
    app = DashProxy(__name__)
    return app


def test_function_modifies_flask_server():
    """Test that the function modifies the underlying Flask server."""
    app = DashProxy(__name__)

    # Get the initial number of routes
    initial_route_count = len(list(app.server.url_map.iter_rules()))

    # Add assets
    add_super_components_assets(app)

    # Get the new number of routes
    new_route_count = len(list(app.server.url_map.iter_rules()))

    # Should have added one new route
    assert new_route_count > initial_route_count


def test_add_super_components_assets_registers_route(mock_dash_app: DashProxy):
    """Test that add_super_components_assets registers the Flask route."""
    # Call the function to add assets
    add_super_components_assets(mock_dash_app)

    # Check that the route was registered
    rules = list(mock_dash_app.server.url_map.iter_rules())
    route_paths = [rule.rule for rule in rules]

    assert "/super-components/<path:filename>" in route_paths


def test_add_super_components_assets_registers_prefixed_route():
    """Test that add_super_components_assets uses requests_pathname_prefix when configured."""
    app = DashProxy(__name__, requests_pathname_prefix="/demo-prefix/")

    add_super_components_assets(app)

    route_paths = [rule.rule for rule in app.server.url_map.iter_rules()]
    assert "/demo-prefix/super-components/<path:filename>" in route_paths


def test_add_super_components_assets_multiple_calls(mock_dash_app: DashProxy):
    """Test that calling add_super_components_assets multiple times raises an error."""
    # First call
    add_super_components_assets(mock_dash_app)

    # Second call - Flask will raise an AssertionError because the endpoint is already registered
    with pytest.raises(AssertionError, match="View function mapping is overwriting an existing"):
        add_super_components_assets(mock_dash_app)


def test_endpoint_function_exists(mock_dash_app: DashProxy):
    """Test that the endpoint function is registered in the view functions."""
    add_super_components_assets(mock_dash_app)

    # Check that the view function exists
    assert "serve_super_components_assets" in mock_dash_app.server.view_functions


def test_endpoint_calls_send_from_directory(mock_dash_app: DashProxy):
    """Test that the endpoint calls send_from_directory with correct arguments."""
    from ansys.solutions.dash_super_components.utils import assets_server

    expected_assets_path = str(Path(assets_server.__file__).parent.parent / "assets")

    with mock.patch("ansys.solutions.dash_super_components.utils.assets_server.send_from_directory") as mock_send:
        # Set up the mock to return a valid response
        mock_return = mock.MagicMock()
        mock_send.return_value = mock_return

        # Add the assets route with the mocked send_from_directory
        add_super_components_assets(mock_dash_app)

        # Retrieve the registered view function and call it directly inside a request context
        view_func = mock_dash_app.server.view_functions.get("serve_super_components_assets")
        assert view_func is not None

        with mock_dash_app.server.test_request_context("/super-components/test.js"):
            result = view_func("test.js")

        # Verify send_from_directory was called with expected arguments
        mock_send.assert_called_once_with(expected_assets_path, "test.js")

        # Verify the returned value equals the mock's return value
        assert result is mock_return
