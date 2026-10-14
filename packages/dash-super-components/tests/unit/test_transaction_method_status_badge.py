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

"""Unit tests for the TransactionMethodStatusBadge component."""

# pyright: reportAttributeAccessIssue=false

from collections.abc import Generator
from typing import Any
from unittest import mock

from dash.exceptions import PreventUpdate
from dash_extensions.enrich import dcc, html
import dash_mantine_components as dmc
import pytest

from ansys.solutions.dash_super_components.transaction_method_status_badge import (
    TransactionMethodStatusBadge,
)
from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors
from ansys.solutions.dash_super_components.utils.status_badge_properties import (
    TRANSACTION_STATUS_BADGE_PROPERTIES,
)
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_base64_svg_src,
)

EXPECTED_LABEL_PROPS_DEFAULT = {
    "style": {
        "display": "none",
        "fontSize": "15px",
        "textAlign": "left",
    },
}

EXPECTED_BADGE_PROPS_DEFAULT = {
    "children": "",
    "size": "lg",
    "radius": "xl",
    "fullWidth": True,
    "variant": "filled",
    "color": CommonColors.MANTINE_BODY,
    "leftSection": None,
}

EXPECTED_INTERVAL_PROPS_DEFAULT = {
    "interval": 5000,
    "disabled": True,
}

EXPECTED_BADGE_ICON_LOADING = create_base64_svg_src(IconNames.EOS_LOADING)


@pytest.fixture
def mock_glow_api_request() -> Generator[mock.MagicMock, None, None]:
    """Mock the GLOW API request class."""
    with mock.patch(
        "ansys.solutions.dash_super_components.transaction_method_status_badge.GlowAPIRequest",
        autospec=True,
    ) as mocked_glow_api_request:
        yield mocked_glow_api_request


def test_ids():
    """Test that all ID methods return the expected structure."""
    aio_id = "test-badge-id"

    assert TransactionMethodStatusBadge.ids._method_info(aio_id) == {
        "component": "transaction-method-status-badge",
        "subcomponent": "method-info",
        "aio_id": aio_id,
    }
    assert TransactionMethodStatusBadge.ids._auto_mode(aio_id) == {
        "component": "transaction-method-status-badge",
        "subcomponent": "auto-mode",
        "aio_id": aio_id,
    }
    assert TransactionMethodStatusBadge.ids._method_status(aio_id) == {
        "component": "transaction-method-status-badge",
        "subcomponent": "method-status",
        "aio_id": aio_id,
    }
    assert TransactionMethodStatusBadge.ids._interval(aio_id) == {
        "component": "transaction-method-status-badge",
        "subcomponent": "interval",
        "aio_id": aio_id,
    }
    assert TransactionMethodStatusBadge.ids._monitoring_active(aio_id) == {
        "component": "transaction-method-status-badge",
        "subcomponent": "monitoring-active",
        "aio_id": aio_id,
    }
    assert TransactionMethodStatusBadge.ids.activate_monitoring(aio_id) == {
        "component": "transaction-method-status-badge",
        "subcomponent": "activate-monitoring",
        "aio_id": aio_id,
    }
    assert TransactionMethodStatusBadge.ids.label(aio_id) == {
        "component": "transaction-method-status-badge",
        "subcomponent": "label",
        "aio_id": aio_id,
    }
    assert TransactionMethodStatusBadge.ids.status_badge(aio_id) == {
        "component": "transaction-method-status-badge",
        "subcomponent": "status-badge",
        "aio_id": aio_id,
    }


def test_ids_assignment():
    """Test that IDs are assigned correctly in the component instance."""
    aio_id = "test-badge-id"

    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        aio_id=aio_id,
    )
    assert badge.ids._method_info(aio_id) == TransactionMethodStatusBadge.ids._method_info(aio_id)
    assert badge.ids._auto_mode(aio_id) == TransactionMethodStatusBadge.ids._auto_mode(aio_id)
    assert badge.ids._method_status(aio_id) == TransactionMethodStatusBadge.ids._method_status(aio_id)
    assert badge.ids._interval(aio_id) == TransactionMethodStatusBadge.ids._interval(aio_id)
    assert badge.ids._monitoring_active(aio_id) == TransactionMethodStatusBadge.ids._monitoring_active(aio_id)
    assert badge.ids.activate_monitoring(aio_id) == TransactionMethodStatusBadge.ids.activate_monitoring(aio_id)
    assert badge.ids.label(aio_id) == TransactionMethodStatusBadge.ids.label(aio_id)
    assert badge.ids.status_badge(aio_id) == TransactionMethodStatusBadge.ids.status_badge(aio_id)


def test_initialization_autogenerated_id():
    """Test that ID is auto-generated when not provided."""
    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
    )

    assert badge is not None
    assert isinstance(badge, TransactionMethodStatusBadge)
    assert badge.aio_id is not None  # Should have an auto-generated ID
    assert isinstance(badge.aio_id, str)

    another_badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
    )
    assert another_badge.aio_id is not None

    assert badge.aio_id != another_badge.aio_id  # IDs should be unique


def test_initialization_defaults():
    """Test initialization with default values for optional parameters."""
    aio_id = "test-badge-defaults"

    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        aio_id=aio_id,
    )

    _assert_badge(
        current_aio_id=aio_id,
        badge=badge,
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        auto_mode=True,
        expected_badge_props=EXPECTED_BADGE_PROPS_DEFAULT,
        expected_label_props=EXPECTED_LABEL_PROPS_DEFAULT,
        expected_interval_props=EXPECTED_INTERVAL_PROPS_DEFAULT,
    )


@pytest.mark.parametrize("auto_mode", [True, False])
def test_initialization_auto_mode(auto_mode: bool):
    """Test that the auto mode value is stored correctly."""
    aio_id = f"test-badge-auto-mode-{auto_mode}"

    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        auto_mode=auto_mode,
        aio_id=aio_id,
    )

    _assert_badge(
        current_aio_id=aio_id,
        badge=badge,
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        auto_mode=auto_mode,
        expected_badge_props=EXPECTED_BADGE_PROPS_DEFAULT,
        expected_label_props=EXPECTED_LABEL_PROPS_DEFAULT,
        expected_interval_props=EXPECTED_INTERVAL_PROPS_DEFAULT,
    )


def test_initialization_full_custom_badge_properties():
    """Test initialization with custom badge properties."""
    aio_id = "test-badge-custom-badge"
    custom_badge_props = {
        "children": "Custom Status",  # This gets overridden by status name logic
        "size": "md",  # Override default
        "radius": "sm",  # Override default
        "variant": "filled",  # This gets overridden by status variant logic
        "color": "blue",  # This gets overridden by status color logic
        "autoContrast": True,  # Extra property not in defaults
        "darkHidden": False,  # Extra property not in defaults
    }

    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        badge_props=custom_badge_props,
        aio_id=aio_id,
    )

    expected_badge_props = {
        "children": "",  # controlled by component
        "size": "md",
        "radius": "sm",
        "fullWidth": True,
        "variant": "filled",  # controlled by component
        "color": CommonColors.MANTINE_BODY,  # controlled by component
        "leftSection": None,  # controlled by component
        "autoContrast": True,
        "darkHidden": False,
    }

    _assert_badge(
        current_aio_id=aio_id,
        badge=badge,
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        auto_mode=True,
        expected_badge_props=expected_badge_props,
        expected_label_props=EXPECTED_LABEL_PROPS_DEFAULT,
        expected_interval_props=EXPECTED_INTERVAL_PROPS_DEFAULT,
    )


def test_initialization_full_custom_label_properties():
    """Test initialization with custom label properties."""
    aio_id = "test-badge-custom-label"
    custom_label_props = {
        "children": "My Custom Label",
        "style": {  # override entire style dict
            "fontSize": "20px",  # property also exists in defaults
            "textAlign": "center",  # property also exists in defaults
            "color": "red",  # Extra style property not in defaults
            # Note: 'display' key is not set, should default to "block" because label_properties
            # is not empty
        },
    }

    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        label_props=custom_label_props,
        aio_id=aio_id,
    )

    # Expected properties: custom style is merged with defaults
    expected_label_props = {
        "children": "My Custom Label",
        "style": {
            "fontSize": "20px",  # from custom
            "textAlign": "center",  # from custom
            "color": "red",  # from custom (extra property)
            "display": "block",  # from defaults (because label_properties is not empty)
        },
    }

    _assert_badge(
        current_aio_id=aio_id,
        badge=badge,
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        auto_mode=True,
        expected_badge_props=EXPECTED_BADGE_PROPS_DEFAULT,
        expected_label_props=expected_label_props,
        expected_interval_props=EXPECTED_INTERVAL_PROPS_DEFAULT,
    )


def test_initialization_label_properties_empty_dict():
    """Test that empty label_properties dict results in hidden label."""
    aio_id = "test-badge-label-empty"

    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        label_props={},  # Empty dict
        aio_id=aio_id,
    )

    _assert_badge(
        current_aio_id=aio_id,
        badge=badge,
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        auto_mode=True,
        expected_badge_props=EXPECTED_BADGE_PROPS_DEFAULT,
        expected_label_props=EXPECTED_LABEL_PROPS_DEFAULT,
        expected_interval_props=EXPECTED_INTERVAL_PROPS_DEFAULT,
    )


def test_initialization_full_custom_interval_properties():
    """Test initialization with custom interval properties."""
    aio_id = "test-badge-custom-interval"
    custom_interval_props = {
        "interval": 1000,  # Override default
        "disabled": False,  # Will be overridden by monitoring logic
        "max_intervals": 10,  # Extra property not in defaults
    }

    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        interval_props=custom_interval_props,
        aio_id=aio_id,
    )

    expected_interval_props = {
        "interval": 1000,
        "disabled": True,
        "max_intervals": 10,
    }

    _assert_badge(
        current_aio_id=aio_id,
        badge=badge,
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        auto_mode=True,
        expected_badge_props=EXPECTED_BADGE_PROPS_DEFAULT,
        expected_label_props=EXPECTED_LABEL_PROPS_DEFAULT,
        expected_interval_props=expected_interval_props,
    )


def test_initialization_label_style_custom_display_overrides():
    """Test that user can explicitly override the display property in label style.

    This test verifies that when user explicitly provides a display property in the style,
    it takes precedence over the default logic.
    """
    aio_id = "test-badge-custom-display"
    custom_label_props = {
        "children": "Custom Label",
        "style": {
            "fontSize": "18px",
            "display": "flex",  # Explicitly set to flex (overrides default "block")
        },
    }

    badge = TransactionMethodStatusBadge(
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        label_props=custom_label_props,
        aio_id=aio_id,
    )

    expected_label_props = {
        "children": "Custom Label",
        "style": {
            "fontSize": "18px",  # from custom
            "textAlign": "left",  # from defaults
            "display": "flex",  # from custom (overrides default "block")
        },
    }

    _assert_badge(
        current_aio_id=aio_id,
        badge=badge,
        url="http://localhost:5000",
        step_name="test_step",
        method_name="test_method",
        auto_mode=True,
        expected_badge_props=EXPECTED_BADGE_PROPS_DEFAULT,
        expected_label_props=expected_label_props,
        expected_interval_props=EXPECTED_INTERVAL_PROPS_DEFAULT,
    )


@pytest.mark.parametrize("monitoring_active", [True, False])
def test_start_stop_monitoring(monitoring_active: bool):
    """Test start_stop_monitoring callback."""
    interval_disabled = TransactionMethodStatusBadge.start_stop_monitoring(
        monitoring_active,
    )

    assert interval_disabled == (not monitoring_active)


@pytest.mark.parametrize("activate", [True, False])
def test_activate_deactivate_monitoring_from_external_trigger(activate: bool):
    """Test external activation callback."""
    assert TransactionMethodStatusBadge.activate_deactivate_monitoring_from_external_trigger(activate) == activate


def test_retrieve_method_status_returns_new_value(mock_glow_api_request: mock.MagicMock):
    """Test that retrieve_method_status returns a changed status."""
    mock_glow_api_request.return_value.get_transaction_method_status.return_value = "running"

    method_info = {
        "url": "http://test.example.com:8080",
        "step_name": "my-step",
        "method_name": "my-method",
    }

    status = TransactionMethodStatusBadge.retrieve_method_status(
        1,  # dummy
        method_info,
        "completed",
    )

    assert status == "running"
    mock_glow_api_request.assert_called_once_with("http://test.example.com:8080")
    mock_glow_api_request.return_value.get_transaction_method_status.assert_called_once_with(
        "my-step",
        "my-method",
    )


def test_retrieve_method_status_raises_prevent_update_when_unchanged(
    mock_glow_api_request: mock.MagicMock,
):
    """Test that retrieve_method_status raises PreventUpdate for unchanged status."""
    mock_glow_api_request.return_value.get_transaction_method_status.return_value = "running"

    with pytest.raises(PreventUpdate):
        TransactionMethodStatusBadge.retrieve_method_status(
            1,  # dummy
            {
                "url": "http://localhost:5000",
                "step_name": "test_step",
                "method_name": "test_method",
            },
            "running",
        )


@pytest.mark.parametrize("monitoring_active", [True, False])
@pytest.mark.parametrize("method_status", ["running", "completed", "failed", "run-required"])
def test_update_badge_various_statuses(method_status: str, monitoring_active: bool):
    """Test update_badge callback for supported method statuses."""
    children, color, variant, left_section = TransactionMethodStatusBadge.update_badge(
        method_status=method_status,
        monitoring_active=monitoring_active,
    )

    assert children == method_status.upper()
    assert color == TRANSACTION_STATUS_BADGE_PROPERTIES[method_status]["color"]

    if monitoring_active:
        assert variant == "filled"
        assert isinstance(left_section, html.Img)
        assert left_section.src == EXPECTED_BADGE_ICON_LOADING
        assert left_section.style == {"height": "2em", "width": "auto"}
    else:
        assert variant == "outline"
        assert left_section is None


@pytest.mark.parametrize("status_case", ["RUNNING", "Running", "running"])
def test_update_badge_handles_status_case(status_case: str):
    """Test that update_badge handles method status case consistently."""
    children, color, _, _ = TransactionMethodStatusBadge.update_badge(
        method_status=status_case,
        monitoring_active=True,
    )

    assert children == "RUNNING"
    assert color == TRANSACTION_STATUS_BADGE_PROPERTIES["running"]["color"]


def test_update_badge_raises_prevent_update_when_method_status_not_set():
    """Test that update_badge ignores updates until method status is available."""
    with pytest.raises(PreventUpdate):
        TransactionMethodStatusBadge.update_badge(
            method_status=None,  # type: ignore - testing behavior when status is not set
            monitoring_active=False,
        )


@pytest.mark.parametrize(
    "method_status",
    [
        "running",
        "run-required",
        "completed",
        "failed",
    ],
)
@pytest.mark.parametrize(
    "current_monitoring_active",
    [True, False],
)
def test_control_monitoring_raises_prevent_update_when_auto_mode_off(
    method_status: str, current_monitoring_active: bool
):
    """Test manual mode behavior, where callback always raises PreventUpdate."""
    with pytest.raises(PreventUpdate):
        TransactionMethodStatusBadge.control_monitoring_based_on_method_status(
            method_status=method_status,
            current_monitoring_active=current_monitoring_active,
            auto_mode=False,
        )


def test_control_monitoring_in_auto_mode_activates_when_not_active_and_running():
    """Test activation when monitoring is inactive and method status is running."""
    monitoring_active = TransactionMethodStatusBadge.control_monitoring_based_on_method_status(
        method_status="running",
        current_monitoring_active=False,
        auto_mode=True,
    )

    assert monitoring_active is True


@pytest.mark.parametrize(
    "method_status",
    [
        "run-required",
        "completed",
        "failed",
    ],
)
def test_control_monitoring_in_auto_mode_does_not_activate_when_not_active_and_not_running(
    method_status: str,
):
    """Test that monitoring remains inactive when method is not running."""
    with pytest.raises(PreventUpdate):
        TransactionMethodStatusBadge.control_monitoring_based_on_method_status(
            method_status=method_status,
            current_monitoring_active=False,
            auto_mode=True,
        )


@pytest.mark.parametrize(
    "method_status",
    [
        "completed",
        "failed",
    ],
)
def test_control_monitoring_in_auto_mode_deactivates_when_active_and_method_finishes(
    method_status: str,
):
    """Test deactivation when monitoring is active and method status changes to completed."""
    new_monitoring_active = TransactionMethodStatusBadge.control_monitoring_based_on_method_status(
        method_status=method_status,
        current_monitoring_active=True,
        auto_mode=True,
    )

    assert new_monitoring_active is False


@pytest.mark.parametrize(
    "method_status",
    [
        "running",
        "run-required",
    ],
)
def test_control_monitoring_in_auto_mode_does_not_change_when_active_and_method_not_finished(
    method_status: str,
):
    """Test that monitoring remains active when method is running or requires run."""
    with pytest.raises(PreventUpdate):
        TransactionMethodStatusBadge.control_monitoring_based_on_method_status(
            method_status=method_status,
            current_monitoring_active=True,
            auto_mode=True,
        )


def _assert_badge(
    current_aio_id: str,
    badge: TransactionMethodStatusBadge,
    url: str,
    step_name: str,
    method_name: str,
    auto_mode: bool,
    expected_badge_props: dict[str, Any],
    expected_label_props: dict[str, Any],
    expected_interval_props: dict[str, Any],
):
    assert isinstance(badge, html.Div)
    assert badge.children is not None
    assert len(badge.children) == 7

    inner_div = badge.children[0]
    assert isinstance(inner_div, html.Div)
    assert inner_div.style == {
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "left",
    }
    assert inner_div.children is not None
    assert len(inner_div.children) == 2

    label_div = inner_div.children[0]
    assert label_div.id == badge.ids.label(current_aio_id)
    for key, value in expected_label_props.items():
        assert getattr(label_div, key) == value

    status_badge = inner_div.children[1]
    assert isinstance(status_badge, dmc.Badge)
    assert status_badge.id == badge.ids.status_badge(current_aio_id)
    for key, value in expected_badge_props.items():
        assert getattr(status_badge, key) == value

    interval = badge.children[1]
    assert isinstance(interval, dcc.Interval)
    assert interval.id == badge.ids._interval(current_aio_id)
    for key, value in expected_interval_props.items():
        assert getattr(interval, key) == value

    method_info_store = badge.children[2]
    assert isinstance(method_info_store, dcc.Store)
    assert method_info_store.id == badge.ids._method_info(current_aio_id)
    assert method_info_store.storage_type == "memory"
    assert method_info_store.data == {
        "url": url,
        "step_name": step_name,
        "method_name": method_name,
    }

    method_status_store = badge.children[3]
    assert isinstance(method_status_store, dcc.Store)
    assert method_status_store.id == badge.ids._method_status(current_aio_id)
    assert method_status_store.storage_type == "memory"
    assert getattr(method_status_store, "data", None) is None

    monitoring_active_store = badge.children[4]
    assert isinstance(monitoring_active_store, dcc.Store)
    assert monitoring_active_store.id == badge.ids._monitoring_active(current_aio_id)
    assert monitoring_active_store.storage_type == "memory"
    assert getattr(monitoring_active_store, "data", None) is None

    activate_monitoring_store = badge.children[5]
    assert isinstance(activate_monitoring_store, dcc.Store)
    assert activate_monitoring_store.id == badge.ids.activate_monitoring(current_aio_id)
    assert activate_monitoring_store.storage_type == "memory"
    assert getattr(activate_monitoring_store, "data", None) is None

    auto_mode_store = badge.children[6]
    assert isinstance(auto_mode_store, dcc.Store)
    assert auto_mode_store.id == badge.ids._auto_mode(current_aio_id)
    assert auto_mode_store.storage_type == "memory"
    assert auto_mode_store.data is auto_mode
