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

"""Unit tests for the TransactionSupervisor component."""

# pyright: reportAttributeAccessIssue=false

from datetime import datetime
from unittest import mock

try:
    # dash >=3.2.0
    from dash import NoUpdate
except ImportError:
    # dash >=2.18.2, <3.2.0
    from dash._callback import NoUpdate  # pyright: ignore[reportPrivateImportUsage]

from dash.exceptions import PreventUpdate
from dash_extensions.enrich import dcc, html, no_update
import dash_mantine_components as dmc
import pytest

from ansys.solutions.dash_super_components.transaction_supervisor import (
    TRANSACTION_STATUS_BADGE_PROPERTIES,
    TransactionSupervisor,
)
from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors
from ansys.solutions.dash_super_components.utils.svg_icons import IconNames, create_base64_svg_src


@pytest.fixture
def fixed_epoch_time() -> float:
    """Provide a deterministic epoch timestamp for tests."""
    return 1704110400.0


def _method_info() -> dict[str, str]:
    return {
        "url": "http://test.com",
        "step_name": "test_step",
        "method_name": "test_method",
    }


def test_ids():
    """Verify id generation methods on TransactionSupervisor.ids."""
    supervisor = TransactionSupervisor(
        aio_id="dummy-id",
        url="http://test.com",
        step_name="test_step",
        method_name="test_method",
    )

    assert supervisor.aio_id == "dummy-id"

    assert supervisor.ids._method_info("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "method-info",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._method_info_persist("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "method-info-persist",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._started_time("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "started-time",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._stopped_time("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "stopped-time",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._elapsed_time_calculable("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "elapsed-time-calculable",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._method_status("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "method-status",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._supervision_active("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "supervision-active",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids.activate_monitoring("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "activate-monitoring",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._loader("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "loader",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids.transaction_status_badge("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "transaction-status-badge",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._interval("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "interval",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids.started_time_label("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "started-time-label",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids.elapsed_time_label("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "elapsed-time-label",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids.switch("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "switch",
        "aio_id": "dummy-id",
    }
    assert supervisor.ids._container("dummy-id") == {
        "component": "transaction-supervisor",
        "subcomponent": "container",
        "aio_id": "dummy-id",
    }


def test_transaction_supervisor_initialization_defaults():
    """Initialization uses defaults when custom values are not provided."""
    supervisor = TransactionSupervisor(
        url="http://test_default.com",
        step_name="test_step_default",
        method_name="test_method_default",
    )

    assert supervisor.aio_id
    _assert_component(
        supervisor,
        aio_id=supervisor.aio_id,
        url="http://test_default.com",
        step_name="test_step_default",
        method_name="test_method_default",
        title="Transaction Supervisor",
        show=True,
        width=400,
        font_size="14px",
        title_font_size="16px",
        orientation="horizontal",
    )


def test_transaction_supervisor_initialization_custom_values():
    """Custom initialization respects provided values."""
    supervisor = TransactionSupervisor(
        aio_id="test-id",
        url="http://test.com",
        step_name="test_step",
        method_name="test_method",
        title="Test Supervisor",
        show=False,
        width=500,
        font_size="16px",
        title_font_size="20px",
        orientation="vertical",
    )

    _assert_component(
        supervisor,
        aio_id="test-id",
        url="http://test.com",
        step_name="test_step",
        method_name="test_method",
        title="Test Supervisor",
        show=False,
        width=500,
        font_size="16px",
        title_font_size="20px",
        orientation="vertical",
    )


def test_show_supervision_card_callback():
    """show_supervision_card returns display style according to switch state."""
    assert TransactionSupervisor.show_supervision_card(True) == {"display": "inline-block"}
    assert TransactionSupervisor.show_supervision_card(False) == {"display": "none"}


def test_start_stop_supervision_callback():
    """start_stop_supervision toggles the interval and loader display."""
    assert TransactionSupervisor.start_stop_supervision(True) == (False, "show")
    assert TransactionSupervisor.start_stop_supervision(False) == (True, "hide")


def test_update_started_time_label_callback():
    """update_started_time_label displays started time or fallback."""
    with mock.patch("ansys.solutions.dash_super_components.transaction_supervisor.datetime") as mock_datetime:
        mock_datetime.fromtimestamp.return_value = datetime(2024, 1, 1, 13, 0)
        result = TransactionSupervisor.update_started_time_label(1704110400.0)
        mock_datetime.fromtimestamp.assert_called_once_with(1704110400.0)

    assert result == "2024-01-01 13:00:00"
    assert TransactionSupervisor.update_started_time_label(None) == "n/a"


@pytest.mark.parametrize(
    "method_status",
    ["run-required", "running", "completed", "failed"],
)
def test_display_method_status_in_badge_callback(method_status: str):
    """display_method_status_in_badge maps status text and badge color."""
    expected_color = TRANSACTION_STATUS_BADGE_PROPERTIES[method_status]["color"]
    assert TransactionSupervisor.display_method_status_in_badge(method_status) == (
        method_status,
        expected_color,
    )


@pytest.mark.parametrize(
    "elapsed_time_calculable",
    [True, False],
)
def test_update_elapsed_time_label_with_started_and_stopped_times(elapsed_time_calculable):
    """Elapsed time is computed from started and stopped timestamps."""
    result = TransactionSupervisor.update_elapsed_time_label(
        1,  # dummy
        1704110580.0,
        1704110400.0,
        elapsed_time_calculable,
    )
    assert result == "0:03:00"


def test_update_elapsed_time_label_with_running_transaction(fixed_epoch_time: float):
    """Elapsed time is computed from started timestamp and current time when trusted."""
    with mock.patch(
        "ansys.solutions.dash_super_components.transaction_supervisor.time.time",
        return_value=fixed_epoch_time,
    ):
        result = TransactionSupervisor.update_elapsed_time_label(
            1,  # dummy
            None,
            1704110340.0,
            True,
        )

    assert result == "0:01:00"


def test_update_elapsed_time_label_returns_na_when_untrusted_running():
    """Elapsed time is unavailable when started time is not trustworthy and no stop exists."""
    result = TransactionSupervisor.update_elapsed_time_label(
        1,  # dummy
        None,
        1704110340.0,
        False,
    )
    assert result == "n/a"


def test_update_elapsed_time_label_returns_na_when_no_started_time():
    """Elapsed time is unavailable when no started time exists, regardless of trust."""
    result = TransactionSupervisor.update_elapsed_time_label(
        1,  # dummy
        1704110580.0,
        None,
        True,
    )
    assert result == "n/a"


def test_activate_monitoring_from_external_trigger_raises_when_already_active():
    """Activation callback does not update state when supervision is already active."""
    with pytest.raises(PreventUpdate):
        TransactionSupervisor.activate_monitoring_from_external_trigger(True, True)


@pytest.mark.parametrize(
    "supervision_active",
    [True, False],
)
def test_activate_monitoring_from_external_trigger_raises_when_trigger_false(
    supervision_active: bool,
):
    """Activation callback does not update state when trigger is false."""
    with pytest.raises(PreventUpdate):
        TransactionSupervisor.activate_monitoring_from_external_trigger(False, supervision_active)


def test_activate_monitoring_from_external_trigger_sets_state(fixed_epoch_time: float):
    """Activation callback initializes supervision times and trust state."""
    with mock.patch(
        "ansys.solutions.dash_super_components.transaction_supervisor.time.time",
        return_value=fixed_epoch_time,
    ):
        (supervision_active, start_time, stop_time, elapsed_time_calculable) = (
            TransactionSupervisor.activate_monitoring_from_external_trigger(True, False)
        )

    assert supervision_active
    assert start_time == fixed_epoch_time
    assert stop_time is None
    assert elapsed_time_calculable


@pytest.mark.parametrize(
    (
        "previous_method_status",
        "previous_elapsed_time_calculable",
        "received_method_status",
        "new_method_status",
        "new_elapsed_time_calculable",
    ),
    [
        ("dummy", False, "dummy", no_update, no_update),
        ("dummy", False, "running", "running", True),
        ("dummy", True, "dummy", no_update, no_update),
        ("dummy", True, "running", "running", no_update),
        ("running", False, "running", no_update, True),
        ("running", False, "dummy", "dummy", no_update),
        ("running", True, "running", no_update, no_update),
        ("running", True, "dummy", "dummy", no_update),
    ],
)
def test_retrieve_method_status_and_update_elapsed_time_calculable(
    previous_method_status: str,
    previous_elapsed_time_calculable: bool,
    received_method_status: str,
    new_method_status: str | NoUpdate,
    new_elapsed_time_calculable: bool | NoUpdate,
):
    """Test all possible combinations of method status and trust data updates."""
    method_info = _method_info()

    with mock.patch(
        "ansys.solutions.dash_super_components.transaction_supervisor.GlowAPIRequest",
        autospec=True,
    ) as mocked_glow_api_request:
        glow_instance = mocked_glow_api_request.return_value
        glow_instance.get_transaction_method_status.return_value = received_method_status

        dummy_n_intervals = 1  # The actual value is irrelevant for this test

        (method_status_result, elapsed_time_calculable_result) = (
            TransactionSupervisor.retrieve_method_status_and_update_elapsed_time_calculable(
                dummy_n_intervals,
                method_info,
                previous_method_status,
                previous_elapsed_time_calculable,
            )
        )

    mocked_glow_api_request.assert_called_once_with(method_info["url"])
    glow_instance.get_transaction_method_status.assert_called_once_with(
        method_info["step_name"],
        method_info["method_name"],
    )
    assert method_status_result == new_method_status
    assert elapsed_time_calculable_result == new_elapsed_time_calculable


@pytest.mark.parametrize(
    "method_status",
    ["running", "completed"],
)
def test_control_supervision_based_on_method_status_resets_on_method_change(method_status: str):
    """Method info changes reset times, update persisted info and set active state from status."""
    method_info = _method_info()
    method_info_persist = {
        "url": "http://other.com",
        "step_name": "other_step",
        "method_name": "other_method",
    }

    (
        supervision_active_result,
        started_time_result,
        stopped_time_result,
        method_info_persist_result,
    ) = TransactionSupervisor.control_supervision_based_on_method_status(
        method_status=method_status,
        method_info=method_info,
        elapsed_time_calculable=False,
        current_stored_supervision_active=True,
        method_info_persist=method_info_persist,
    )

    expected_supervision_active = method_status == "running"
    assert supervision_active_result == expected_supervision_active
    assert started_time_result is None
    assert stopped_time_result is None
    assert method_info_persist_result == method_info


@pytest.mark.parametrize(
    "method_status",
    ["running", "completed"],
)
def test_control_supervision_based_on_method_status_resets_when_persist_missing(
    method_status: str,
):
    """Missing persisted method info is treated as method change and resets supervision state."""
    method_info = _method_info()

    (
        supervision_active_result,
        started_time_result,
        stopped_time_result,
        method_info_persist_result,
    ) = TransactionSupervisor.control_supervision_based_on_method_status(
        method_status=method_status,
        method_info=method_info,
        elapsed_time_calculable=False,
        current_stored_supervision_active=True,
        method_info_persist=None,  # type: ignore[arg-type] - testing missing persisted state
    )

    assert supervision_active_result is (method_status == "running")
    assert started_time_result is None
    assert stopped_time_result is None
    assert method_info_persist_result == method_info


@pytest.mark.parametrize(
    "elapsed_time_calculable",
    [True, False],
)
def test_control_supervision_based_on_method_status_activates_on_page_load_running(
    elapsed_time_calculable: bool,
):
    """Page load starts supervision only when method is currently running."""
    method_info = _method_info()

    (
        supervision_active_result,
        stared_time_result,
        stopped_time_result,
        method_info_persist_result,
    ) = TransactionSupervisor.control_supervision_based_on_method_status(
        method_status="running",
        method_info=method_info,
        elapsed_time_calculable=elapsed_time_calculable,
        current_stored_supervision_active=False,
        method_info_persist=method_info,
    )

    assert supervision_active_result
    assert stared_time_result == no_update
    assert stopped_time_result == no_update
    assert method_info_persist_result == no_update


@pytest.mark.parametrize(
    "elapsed_time_calculable",
    [True, False],
)
def test_control_supervision_based_on_method_status_page_load_not_running(
    elapsed_time_calculable: bool,
):
    """Page load does not update state when method is not running."""
    method_info = _method_info()

    with pytest.raises(PreventUpdate):
        TransactionSupervisor.control_supervision_based_on_method_status(
            method_status="completed",
            method_info=method_info,
            elapsed_time_calculable=elapsed_time_calculable,
            current_stored_supervision_active=False,
            method_info_persist=method_info,
        )


@pytest.mark.parametrize(
    "method_status",
    ["completed", "failed"],
)
def test_control_supervision_based_on_method_status_stops_and_sets_stopped_time(
    method_status: str,
    fixed_epoch_time: float,
):
    """Active supervision stores stopped time when terminal status is trusted."""
    method_info = _method_info()

    with mock.patch(
        "ansys.solutions.dash_super_components.transaction_supervisor.time.time",
        return_value=fixed_epoch_time,
    ):
        result = TransactionSupervisor.control_supervision_based_on_method_status(
            method_status=method_status,
            method_info=method_info,
            elapsed_time_calculable=True,
            current_stored_supervision_active=True,
            method_info_persist=method_info,
        )

    assert result == (False, no_update, fixed_epoch_time, no_update)


@pytest.mark.parametrize(
    "method_status",
    ["completed", "failed"],
)
def test_control_supervision_based_on_method_status_stops_without_stopped_time_when_untrusted(
    method_status: str,
):
    """Active supervision stops wo setting stopped time when elapsed_time_calculable is false."""
    method_info = _method_info()

    result = TransactionSupervisor.control_supervision_based_on_method_status(
        method_status=method_status,
        method_info=method_info,
        elapsed_time_calculable=False,
        current_stored_supervision_active=True,
        method_info_persist=method_info,
    )

    assert result == (False, no_update, no_update, no_update)


@pytest.mark.parametrize(
    "method_status",
    ["running", "run-required"],
)
@pytest.mark.parametrize(
    "elapsed_time_calculable",
    [True, False],
)
def test_control_supervision_based_on_method_status_keeps_non_finished_state(
    elapsed_time_calculable: bool, method_status: str
):
    """Active supervision with non-terminal status does not emit updates."""
    method_info = _method_info()

    with pytest.raises(PreventUpdate):
        TransactionSupervisor.control_supervision_based_on_method_status(
            method_status=method_status,
            method_info=method_info,
            elapsed_time_calculable=elapsed_time_calculable,
            current_stored_supervision_active=True,
            method_info_persist=method_info,
        )


def _assert_component(
    supervisor: TransactionSupervisor,
    *,
    aio_id: str,
    url: str,
    step_name: str,
    method_name: str,
    title: str,
    show: bool,
    width: int,
    font_size: str,
    title_font_size: str,
    orientation: str,
):
    assert isinstance(supervisor, html.Div)
    assert supervisor.children is not None
    assert len(supervisor.children) == 1

    inner_div = supervisor.children[0]
    assert isinstance(inner_div, html.Div)
    assert inner_div.children is not None
    assert len(inner_div.children) == 10

    method_info_store = inner_div.children[0]
    assert isinstance(method_info_store, dcc.Store)
    assert method_info_store.id == supervisor.ids._method_info(aio_id)
    assert method_info_store.storage_type == "memory"
    assert method_info_store.data == {
        "url": url,
        "step_name": step_name,
        "method_name": method_name,
    }

    method_info_persist_store = inner_div.children[1]
    assert isinstance(method_info_persist_store, dcc.Store)
    assert method_info_persist_store.id == supervisor.ids._method_info_persist(aio_id)
    assert method_info_persist_store.storage_type == "session"

    started_time_store = inner_div.children[2]
    assert isinstance(started_time_store, dcc.Store)
    assert started_time_store.id == supervisor.ids._started_time(aio_id)
    assert started_time_store.storage_type == "session"

    stopped_time_store = inner_div.children[3]
    assert isinstance(stopped_time_store, dcc.Store)
    assert stopped_time_store.id == supervisor.ids._stopped_time(aio_id)
    assert stopped_time_store.storage_type == "session"

    elapsed_time_calculable_store = inner_div.children[4]
    assert isinstance(elapsed_time_calculable_store, dcc.Store)
    assert elapsed_time_calculable_store.id == supervisor.ids._elapsed_time_calculable(aio_id)
    assert elapsed_time_calculable_store.storage_type == "memory"

    method_status_store = inner_div.children[5]
    assert isinstance(method_status_store, dcc.Store)
    assert method_status_store.id == supervisor.ids._method_status(aio_id)
    assert method_status_store.storage_type == "memory"

    supervision_active_store = inner_div.children[6]
    assert isinstance(supervision_active_store, dcc.Store)
    assert supervision_active_store.id == supervisor.ids._supervision_active(aio_id)
    assert supervision_active_store.storage_type == "memory"

    activate_monitoring_store = inner_div.children[7]
    assert isinstance(activate_monitoring_store, dcc.Store)
    assert activate_monitoring_store.id == supervisor.ids.activate_monitoring(aio_id)
    assert activate_monitoring_store.storage_type == "memory"

    interval_component = inner_div.children[8]
    assert isinstance(interval_component, dcc.Interval)
    assert interval_component.id == supervisor.ids._interval(aio_id)
    assert interval_component.interval == 1000
    assert interval_component.n_intervals == 0
    assert interval_component.disabled

    card = inner_div.children[9]
    assert isinstance(card, dmc.Card)
    assert card.withBorder
    assert card.shadow == "sm"
    assert card.radius == "md"
    assert card.w == width
    assert card.children is not None
    assert len(card.children) == 2

    top_section = card.children[0]
    assert isinstance(top_section, dmc.CardSection)
    assert top_section.withBorder
    assert top_section.inheritPadding
    assert top_section.py == "xs"

    group = top_section.children
    assert isinstance(group, dmc.Group)
    assert group.justify == "space-around"
    assert group.children is not None
    assert len(group.children) == 3

    title_div = group.children[0]
    assert isinstance(title_div, html.Div)
    assert title_div.children == title
    assert title_div.style == {"display": "inline-block", "fontSize": title_font_size}

    loader = group.children[1]
    assert isinstance(loader, dcc.Loading)
    assert loader.id == supervisor.ids._loader(aio_id)
    assert loader.display == "hide"
    assert loader.color == CommonColors.MANTINE_PRIMARY_COLOR

    switch_container = group.children[2]
    assert isinstance(switch_container, dmc.HoverCard)
    assert switch_container.withArrow
    assert switch_container.shadow == "md"
    assert switch_container.children is not None
    assert len(switch_container.children) == 2

    switch_target = switch_container.children[0]
    assert isinstance(switch_target, dmc.HoverCardTarget)
    switch = switch_target.children
    assert isinstance(switch, dmc.Switch)
    assert switch.id == supervisor.ids.switch(aio_id)
    assert switch.checked == show
    assert switch.size == "sm"
    expected_off_src = create_base64_svg_src(IconNames.MDI_HIDE, color="#000")
    expected_on_src = create_base64_svg_src(IconNames.MDI_SHOW, color="#000")
    expected_icon_style = {
        "display": "inline-block",
        "width": "16px",
        "height": "16px",
        "backgroundColor": "currentColor",
        "maskRepeat": "no-repeat",
        "maskPosition": "center",
        "maskSize": "contain",
        "WebkitMaskRepeat": "no-repeat",
        "WebkitMaskPosition": "center",
        "WebkitMaskSize": "contain",
    }
    expected_off_url_values = {
        f"url('{expected_off_src}')",
        f'url("{expected_off_src}")',
    }
    expected_on_url_values = {
        f"url('{expected_on_src}')",
        f'url("{expected_on_src}")',
    }
    assert isinstance(switch.offLabel, html.Span)
    assert switch.offLabel.style is not None
    for key, value in expected_icon_style.items():
        assert switch.offLabel.style.get(key) == value
    assert str(switch.offLabel.style.get("maskImage", "")) in expected_off_url_values
    assert str(switch.offLabel.style.get("WebkitMaskImage", "")) in expected_off_url_values

    assert isinstance(switch.onLabel, html.Span)
    assert switch.onLabel.style is not None
    for key, value in expected_icon_style.items():
        assert switch.onLabel.style.get(key) == value
    assert str(switch.onLabel.style.get("maskImage", "")) in expected_on_url_values
    assert str(switch.onLabel.style.get("WebkitMaskImage", "")) in expected_on_url_values

    switch_dropdown = switch_container.children[1]
    assert isinstance(switch_dropdown, dmc.HoverCardDropdown)
    switch_dropdown_text = switch_dropdown.children
    assert isinstance(switch_dropdown_text, dmc.Text)
    assert switch_dropdown_text.size == "sm"
    assert switch_dropdown_text.c == CommonColors.MANTINE_TEXT
    assert switch_dropdown_text.children == "Show/Hide monitoring panel."

    bottom_section = card.children[1]
    assert isinstance(bottom_section, html.Div)
    assert bottom_section.id == supervisor.ids._container(aio_id)
    assert bottom_section.style == {"display": "inline-block"}

    grid = bottom_section.children
    assert isinstance(grid, dmc.Grid)
    assert grid.gutter == "xs"
    assert grid.children is not None
    assert len(grid.children) == 3

    expected_span = "content" if orientation == "horizontal" else 12

    status_col = grid.children[0]
    assert isinstance(status_col, dmc.GridCol)
    assert status_col.span == expected_span

    status_col_div = status_col.children
    assert isinstance(status_col_div, html.Div)
    assert status_col_div.style == {"display": "inline-block"}
    assert status_col_div.children is not None
    assert len(status_col_div.children) == 2

    status_badge_title = status_col_div.children[0]
    assert isinstance(status_badge_title, html.Div)
    assert status_badge_title.children == "Transaction method status :"
    assert status_badge_title.style == {
        "display": "inline-block",
        "fontSize": font_size,
        "marginTop": "5px",
    }

    status_badge_div = status_col_div.children[1]
    assert isinstance(status_badge_div, html.Div)
    assert status_badge_div.style == {"marginLeft": "5px", "display": "inline-block"}

    status_badge = status_badge_div.children
    assert isinstance(status_badge, dmc.Badge)
    assert status_badge.id == supervisor.ids.transaction_status_badge(aio_id)
    assert status_badge.style == {"fontSize": font_size}
    assert not status_badge.children

    started_col = grid.children[1]
    assert isinstance(started_col, dmc.GridCol)
    assert started_col.span == expected_span

    started_time_row_div = started_col.children
    assert isinstance(started_time_row_div, html.Div)
    assert started_time_row_div.children is not None
    assert len(started_time_row_div.children) == 2
    started_time_title = started_time_row_div.children[0]
    assert isinstance(started_time_title, html.Div)
    assert started_time_title.children == "Started time :"
    assert started_time_title.style == {
        "display": "inline-block",
        "fontSize": font_size,
        "marginTop": "5px",
    }

    started_time_value = started_time_row_div.children[1]
    assert isinstance(started_time_value, html.Div)
    assert started_time_value.id == supervisor.ids.started_time_label(aio_id)
    assert not started_time_value.children
    assert started_time_value.style == {
        "display": "inline-block",
        "fontSize": font_size,
        "marginTop": "5px",
        "marginLeft": "5px",
    }
    elapsed_col = grid.children[2]
    assert isinstance(elapsed_col, dmc.GridCol)
    assert elapsed_col.span == expected_span

    elapsed_time_div = elapsed_col.children
    assert isinstance(elapsed_time_div, html.Div)
    assert elapsed_time_div.style == {"display": "inline-block"}
    assert elapsed_time_div.children is not None
    assert len(elapsed_time_div.children) == 2

    elapsed_time_title = elapsed_time_div.children[0]
    assert isinstance(elapsed_time_title, html.Div)
    assert elapsed_time_title.children == "Elapsed time :"
    assert elapsed_time_title.style == {
        "display": "inline-block",
        "fontSize": font_size,
        "marginTop": "5px",
    }
    elapsed_time_value = elapsed_time_div.children[1]
    assert isinstance(elapsed_time_value, html.Div)
    assert elapsed_time_value.id == supervisor.ids.elapsed_time_label(aio_id)
    assert not elapsed_time_value.children
    assert elapsed_time_value.style == {
        "display": "inline-block",
        "fontSize": font_size,
        "marginTop": "5px",
        "marginLeft": "5px",
    }
