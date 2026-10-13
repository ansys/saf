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


"""Unit tests for the InputRowArray component."""

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false

from typing import Any, cast

from dash.exceptions import PreventUpdate
from dash_extensions.enrich import dcc, html
import dash_mantine_components as dmc
import pytest

from ansys.solutions.dash_super_components.input_row_array import (
    InputRowArray,
)
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_base64_svg_src,
)

EXPECTED_ADD_BUTTON_SRC = create_base64_svg_src(IconNames.MATERIAL_ADD, "#000")
EXPECTED_DELETE_BUTTON_SRC = create_base64_svg_src(IconNames.MATERIAL_REMOVE, "#000")


@pytest.fixture
def input_items_defaults() -> list[dict[str, Any]]:
    """Fixture for items definition with only default properties."""
    return [
        {
            "id": "text_input",
            "type": "TextInput",
            "properties": {},
        },
        {
            "id": "number_input",
            "type": "NumberInput",
            "properties": {},
        },
        {
            "id": "select_input",
            "type": "Select",
            "properties": {"data": ["Option 1", "Option 2"]},
        },
    ]


@pytest.fixture
def input_items() -> list[dict[str, Any]]:
    """Fixture for items definition with custom properties."""
    return [
        {
            "id": "text_input",
            "type": "TextInput",
            "properties": {
                "label": "Text Input",
                "placeholder": "Enter text here",
                "style": {"width": "50%"},
            },
        },
        {
            "id": "number_input",
            "type": "NumberInput",
            "properties": {
                "label": "Number Input",
                "placeholder": "Enter number here",
                "style": {"width": "40%"},
            },
        },
        {
            "id": "select_input",
            "type": "Select",
            "properties": {
                "label": "Select Input",
                "data": ["Option 1", "Option 2"],
                "style": {"width": "30%"},
            },
        },
    ]


def test_ids(input_items: list[dict[str, Any]]):
    """Verify ids produced by InputRowArray."""
    aio_id = "dummy-id"
    component = InputRowArray(items=input_items, aio_id=aio_id)
    assert component.aio_id == aio_id

    assert component.ids.add_button(aio_id) == {
        "component": "input-row-array",
        "subcomponent": "add-button",
        "aio_id": aio_id,
    }
    assert component.ids.delete_button(aio_id) == {
        "component": "input-row-array",
        "subcomponent": "delete-button",
        "aio_id": aio_id,
    }
    assert component.ids._storage(aio_id) == {
        "component": "input-row-array",
        "subcomponent": "storage",
        "aio_id": aio_id,
    }
    assert component.ids.rows(aio_id) == {
        "component": "input-row-array",
        "subcomponent": "rows",
        "aio_id": aio_id,
    }
    assert component.ids.input(aio_id, "text_input", 0) == {
        "component": "input-row-array",
        "subcomponent": "input",
        "aio_id": aio_id,
        "identifier": "text_input",
        "row_index": 0,
    }
    assert component.ids.input(aio_id, "number_input", 1) == {
        "component": "input-row-array",
        "subcomponent": "input",
        "aio_id": aio_id,
        "identifier": "number_input",
        "row_index": 1,
    }
    assert component.ids.input(aio_id, "number_input") == {
        "component": "input-row-array",
        "subcomponent": "input",
        "aio_id": aio_id,
        "identifier": "number_input",
        "row_index": 0,
    }


def test_input_row_array_initialization_enable_multiple_rows_defaults(
    input_items_defaults: list[dict[str, Any]],
):
    """Initialization with multiple rows enabled using default item properties."""
    component = InputRowArray(
        input_items_defaults,
        enable_multiple_rows=True,
        aio_id="test-aio-id",
    )
    assert component
    assert isinstance(component, html.Div)
    assert component.children is not None
    assert len(component.children) == 3

    # Test add and delete buttons
    buttons = component.children[0]
    _assert_buttons(buttons, cast("InputRowArray.InputRowArrayIds", component.ids))

    # Test content
    rows_container = component.children[1]
    _assert_initial_rows(
        rows_container,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items_defaults,
        expected_full_width=False,
    )

    # Test storage initialization
    storage = component.children[-1]
    _assert_storage(
        storage,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items_defaults,
        enable_multiple_rows=True,
    )


def test_input_row_array_initialization_enable_multiple_rows_custom_properties(
    input_items: list[dict[str, Any]],
):
    """Initialization with multiple rows enabled using custom properties."""
    component = InputRowArray(input_items, enable_multiple_rows=True, aio_id="test-aio-id")
    assert component
    assert isinstance(component, html.Div)
    assert component.children is not None
    assert len(component.children) == 3

    # Test add and delete buttons
    buttons = component.children[0]
    _assert_buttons(buttons, cast("InputRowArray.InputRowArrayIds", component.ids))

    # Test content
    rows_container = component.children[1]
    _assert_initial_rows(
        rows_container,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items,
        expected_full_width=False,
    )

    # Test storage initialization
    storage = component.children[-1]
    _assert_storage(
        storage,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items,
        enable_multiple_rows=True,
    )


def test_input_row_array_initialization_not_enable_multiple_rows_defaults(
    input_items_defaults: list[dict[str, Any]],
):
    """Initialization without multiple rows using default properties."""
    component = InputRowArray(input_items_defaults, aio_id="test-aio-id")
    assert component
    assert isinstance(component, html.Div)
    assert component.children is not None
    assert len(component.children) == 2

    # Test content
    rows_container = component.children[0]
    _assert_initial_rows(
        rows_container,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items_defaults,
        expected_full_width=False,
    )

    # Test storage initialization
    storage = component.children[-1]
    _assert_storage(
        storage,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items_defaults,
        enable_multiple_rows=False,
    )


def test_input_row_array_initialization_not_enable_multiple_rows_custom_properties(
    input_items: list[dict[str, Any]],
):
    """Initialization without multiple rows using custom properties."""
    component = InputRowArray(input_items, aio_id="test-aio-id")
    assert component
    assert isinstance(component, html.Div)
    assert component.children is not None
    assert len(component.children) == 2

    # Test content
    rows_container = component.children[0]
    _assert_initial_rows(
        rows_container,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items,
        expected_full_width=False,
    )


def test_input_row_array_initialization_full_width(
    input_items_defaults: list[dict[str, Any]],
):
    """Initialization can opt into full-width row behavior."""
    component = InputRowArray(
        input_items_defaults,
        enable_multiple_rows=True,
        aio_id="test-aio-id",
        full_width=True,
    )
    assert component
    assert isinstance(component, html.Div)
    assert component.children is not None

    rows_container = component.children[1]
    _assert_initial_rows(
        rows_container,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items_defaults,
        expected_full_width=True,
    )

    # Test storage initialization
    storage = component.children[-1]
    _assert_storage(
        storage,
        cast("InputRowArray.InputRowArrayIds", component.ids),
        input_items_defaults,
        enable_multiple_rows=True,
    )


def test_input_row_array_initialization_undefined_component_type():
    """Test initialization with an undefined component type."""
    items_with_invalid_item_type = [
        {
            "id": "text_input",
            "type": "PasswordInput",  # Unsupported type for InputRowArray
            "properties": {
                "label": "Text Input",
                "placeholder": "Enter text here",
                "style": {"width": "50%"},
            },
        }
    ]
    with pytest.raises(ValueError, match="Unsupported item type: PasswordInput"):
        InputRowArray(items_with_invalid_item_type, aio_id="test-aio-id")


def test_add_row(input_items: list[dict[str, Any]]):
    """Adding a row appends a new row."""
    # Setup initial state
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": True,
        "items": input_items,
    }
    initial_rows = [dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=0))]

    new_rows = InputRowArray.add_row(1, initial_rows, initial_storage)  # type: ignore

    assert len(new_rows) == 2
    assert new_rows[0] == initial_rows[0]
    _assert_row(new_rows[1], input_items, row_index=1)  # type: ignore


def test_add_multiple_rows(input_items: list[dict[str, Any]]):
    """Adding multiple rows appends rows with increasing row indexes."""
    # Setup initial state
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": True,
        "items": input_items,
    }
    initial_rows = [dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=0))]

    # Add three rows
    rows = initial_rows
    for _ in range(3):
        rows = InputRowArray.add_row(1, rows, initial_storage)  # type: ignore

    assert len(rows) == 4
    for row_index, row in enumerate(rows):
        if row_index == 0:
            assert row == initial_rows[0]
        else:
            _assert_row(row, input_items, row_index)  # type: ignore


def test_add_row_prevent_update_when_not_clicked(input_items: list[dict[str, Any]]):
    """add_row raises PreventUpdate when button has not been clicked."""
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": True,
        "items": input_items,
    }
    initial_rows = [dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=0))]

    with pytest.raises(PreventUpdate):
        InputRowArray.add_row(0, initial_rows, initial_storage)  # type: ignore


def test_add_row_prevent_update_multiple_rows_not_enabled(input_items: list[dict[str, Any]]):
    """add_row raises PreventUpdate when multiple rows disabled."""
    # Setup initial state with multiple rows disabled
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": False,
        "items": input_items,
    }
    initial_rows = [dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=0))]

    # Call the add_row function directly and expect PreventUpdate
    with pytest.raises(PreventUpdate):
        InputRowArray.add_row(1, initial_rows, initial_storage)  # type: ignore


def test_delete_row(input_items: list[dict[str, Any]]):
    """Deleting a row removes the last row when more than one exists."""
    # Setup initial state with two rows
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": True,
        "items": input_items,
    }
    initial_rows = [
        dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=0)),
        dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=1)),
    ]

    new_rows = InputRowArray.delete_row(1, initial_rows, initial_storage)  # type: ignore

    assert len(new_rows) == 1
    assert new_rows[0] == initial_rows[0]


def test_delete_row_prevent_update_multiple_rows_not_enabled(
    input_items: list[dict[str, Any]],
):
    """delete_row raises PreventUpdate when multiple rows disabled."""
    # Setup initial state with multiple rows disabled
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": False,
        "items": input_items,
    }
    initial_rows = [dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=0))]

    # Call the delete_row function directly and expect PreventUpdate
    with pytest.raises(PreventUpdate):
        InputRowArray.delete_row(1, initial_rows, initial_storage)  # type: ignore


def test_delete_last_row_prevent_update(input_items: list[dict[str, Any]]):
    """delete_row raises PreventUpdate when attempting to delete the last row."""
    # Setup initial state with one row
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": True,
        "items": input_items,
    }
    initial_rows = [dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=0))]

    with pytest.raises(PreventUpdate):
        InputRowArray.delete_row(1, initial_rows, initial_storage)  # type: ignore


def test_delete_row_prevent_update_when_no_rows_present(input_items: list[dict[str, Any]]):
    """delete_row raises PreventUpdate when no rows present."""
    # Setup initial state with no rows
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": True,
        "items": input_items,
    }
    initial_rows = []

    with pytest.raises(PreventUpdate):
        InputRowArray.delete_row(1, initial_rows, initial_storage)


def test_delete_row_prevent_update_when_not_clicked(input_items: list[dict[str, Any]]):
    """delete_row raises PreventUpdate when button has not been clicked."""
    initial_storage: dict[str, Any] = {
        "aio_id": "test",
        "enable_multiple_rows": True,
        "items": input_items,
    }
    initial_rows = [
        dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=0)),
        dmc.Group(InputRowArray.generate_components(input_items, "test", row_index=1)),
    ]

    with pytest.raises(PreventUpdate):
        InputRowArray.delete_row(0, initial_rows, initial_storage)  # type: ignore


def test_toggle_delete_button_enabled_state_changes_with_rows():
    """toggle_delete_button disables delete for one row and enables for multiple rows."""
    storage: dict[str, Any] = {
        "enable_multiple_rows": True,
    }

    one_row = [dmc.Group()]
    two_rows = [dmc.Group(), dmc.Group()]

    assert InputRowArray.toggle_delete_button(one_row, storage)
    assert not InputRowArray.toggle_delete_button(two_rows, storage)


def test_toggle_delete_button_prevent_update_when_multiple_rows_disabled():
    """toggle_delete_button raises PreventUpdate when multiple rows are disabled."""
    storage: dict[str, Any] = {
        "enable_multiple_rows": False,
    }

    with pytest.raises(PreventUpdate):
        InputRowArray.toggle_delete_button([dmc.Group()], storage)


def _assert_buttons(buttons_container: html.Div, ids: InputRowArray.InputRowArrayIds):
    assert not buttons_container.grow
    assert buttons_container.gap == "xs"
    assert buttons_container.justify == "right"
    assert buttons_container.align == "center"
    assert buttons_container.children is not None
    assert len(buttons_container.children) == 2

    add_button = buttons_container.children[0]
    assert isinstance(add_button, dmc.ActionIcon)
    assert add_button.size == "md"
    assert add_button.variant == "filled"
    assert not hasattr(add_button, "color")
    assert add_button.id == ids.add_button("test-aio-id")
    add_button_icon = add_button.children
    assert isinstance(add_button_icon, html.Span)
    assert add_button_icon.style is not None
    assert add_button_icon.style.get("backgroundColor") == "currentColor"
    assert add_button_icon.style.get("width") == "20px"
    assert add_button_icon.style.get("height") == "20px"
    expected_add_url_values = {
        f"url('{EXPECTED_ADD_BUTTON_SRC}')",
        f'url("{EXPECTED_ADD_BUTTON_SRC}")',
    }
    assert str(add_button_icon.style.get("maskImage", "")) in expected_add_url_values
    assert str(add_button_icon.style.get("WebkitMaskImage", "")) in expected_add_url_values

    delete_button = buttons_container.children[1]
    assert isinstance(delete_button, dmc.ActionIcon)
    assert delete_button.size == "md"
    assert delete_button.variant == "filled"
    assert not hasattr(delete_button, "color")
    assert delete_button.id == ids.delete_button("test-aio-id")
    delete_button_icon = delete_button.children
    assert isinstance(delete_button_icon, html.Span)
    assert delete_button_icon.style is not None
    assert delete_button_icon.style.get("backgroundColor") == "currentColor"
    assert delete_button_icon.style.get("width") == "20px"
    assert delete_button_icon.style.get("height") == "20px"
    expected_delete_url_values = {
        f"url('{EXPECTED_DELETE_BUTTON_SRC}')",
        f'url("{EXPECTED_DELETE_BUTTON_SRC}")',
    }
    assert str(delete_button_icon.style.get("maskImage", "")) in expected_delete_url_values
    assert str(delete_button_icon.style.get("WebkitMaskImage", "")) in expected_delete_url_values


def _assert_initial_rows(
    rows_container: html.Div,
    ids: InputRowArray.InputRowArrayIds,
    items: list[dict[str, Any]],
    expected_full_width: bool,
):
    assert isinstance(rows_container, html.Div)
    assert rows_container.id == ids.rows("test-aio-id")
    expected_style = {"width": "100%"} if expected_full_width else {"display": "inline-block"}
    assert rows_container.style == expected_style
    assert rows_container.children is not None
    assert len(rows_container.children) == 1

    first_row = rows_container.children[0]
    _assert_row(first_row, items, row_index=0, aio_id="test-aio-id")


def _assert_row(row: dmc.Group, items: list[dict[str, Any]], row_index: int, aio_id: str = "test"):
    assert isinstance(row, dmc.Group)
    assert row.grow
    assert row.gap == "xs"
    assert row.justify == "center"
    assert row.align == "center"
    assert row.children is not None
    assert len(row.children) == 3  # Three components as per input_items

    for i, item in enumerate(items):
        item_in_row = row.children[i]
        assert item_in_row.id == InputRowArray.ids.input(aio_id, item["id"], row_index)
        for prop_key, prop_value in item["properties"].items():
            assert str(getattr(item_in_row, prop_key)) == str(prop_value)
        if item["type"] == "TextInput":
            _assert_text_input_item(item, item_in_row)
        elif item["type"] == "NumberInput":
            assert isinstance(item_in_row, dmc.NumberInput)
            _assert_number_input_item(item, item_in_row)
        elif item["type"] == "Select":
            _assert_select_item(item, item_in_row)


def _assert_text_input_item(item: dict[str, Any], item_in_row: dmc.TextInput):
    assert isinstance(item_in_row, dmc.TextInput)

    _assert_default_properties_for_text_input(item, item_in_row)


def _assert_number_input_item(item: dict[str, Any], item_in_row: dmc.NumberInput):
    assert isinstance(item_in_row, dmc.NumberInput)
    _assert_default_properties_for_number_input(item, item_in_row)


def _assert_select_item(item: dict[str, Any], item_in_row: dmc.Select):
    assert isinstance(item_in_row, dmc.Select)
    _assert_default_properties_for_select(item, item_in_row)


def _assert_default_properties_for_text_input(item: dict[str, Any], item_in_row: dmc.TextInput):
    _assert_common_default_properties(item, item_in_row)


def _assert_default_properties_for_number_input(item: dict[str, Any], item_in_row: dmc.NumberInput):
    _assert_common_default_properties(item, item_in_row)


def _assert_default_properties_for_select(item: dict[str, Any], item_in_row: dmc.Select):
    _assert_common_default_properties(item, item_in_row)


def _assert_common_default_properties(
    item: dict[str, Any],
    item_in_row: dmc.Select | dmc.TextInput | dmc.NumberInput,
):
    if "label" not in item["properties"]:
        assert item_in_row.label == "Field"
    if "placeholder" not in item["properties"]:
        assert item_in_row.placeholder == "Enter your data."
    if "required" not in item["properties"]:
        assert item_in_row.required
    if "disabled" not in item["properties"]:
        assert not item_in_row.disabled
    if "style" not in item["properties"]:
        assert item_in_row.style == {"width": "100%"}


def _assert_storage(
    storage: dcc.Store,
    ids: InputRowArray.InputRowArrayIds,
    items: list[dict[str, Any]],
    enable_multiple_rows: bool = False,
):
    assert isinstance(storage, dcc.Store)
    assert storage.id == ids._storage("test-aio-id")
    assert storage.data["enable_multiple_rows"] == enable_multiple_rows
    assert storage.data["items"] == items
    assert storage.storage_type == "memory"
