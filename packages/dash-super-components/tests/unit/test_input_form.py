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

"""Unit tests for the InputForm component."""

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false

import copy
from typing import Any
import unittest.mock as mock

from dash.exceptions import PreventUpdate
from dash_extensions.enrich import dcc, html, no_update
import dash_mantine_components as dmc
import pytest

from ansys.solutions.dash_super_components import InputForm
from ansys.solutions.dash_super_components.input_form import (
    compute_final_column_widths,
    make_form,
    make_row,
)
from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors
from ansys.solutions.dash_super_components.utils.svg_icons import IconNames, create_base64_svg_src


def test_input_form_ids():
    """Test that the ids class method returns the expected structure."""
    test_id = "test-form-id"

    # Test label ID
    assert InputForm.ids.label(test_id, 0) == {
        "component": "input-form",
        "subcomponent": "label",
        "aio_id": test_id,
        "row_index": 0,
    }

    # Test help ID
    assert InputForm.ids.help(test_id, 1) == {
        "component": "input-form",
        "subcomponent": "help",
        "aio_id": test_id,
        "row_index": 1,
    }

    # Test unit ID
    assert InputForm.ids.unit(test_id, "custom-row") == {
        "component": "input-form",
        "subcomponent": "unit",
        "aio_id": test_id,
        "row_index": "custom-row",
    }

    # Test description ID
    assert InputForm.ids.description(test_id, 2) == {
        "component": "input-form",
        "subcomponent": "description",
        "aio_id": test_id,
        "row_index": 2,
    }

    # Test modal ID
    assert InputForm.ids.modal(test_id, 3) == {
        "component": "input-form",
        "subcomponent": "modal",
        "aio_id": test_id,
        "row_index": 3,
    }

    # Test field ID
    assert InputForm.ids.field(test_id, "NumberInput", "my-field", 0) == {
        "component": "input-form",
        "subcomponent": "field",
        "aio_id": test_id,
        "row_index": 0,
        "field_type": "NumberInput",
        "identifier": "my-field",
    }

    # Test field_div ID
    assert InputForm.ids.field_div(test_id, "TextInput", "another-field", 1) == {
        "component": "input-form",
        "subcomponent": "field-div",
        "aio_id": test_id,
        "row_index": 1,
        "field_type": "TextInput",
        "identifier": "another-field",
    }


def test_input_form_defaults():
    """Test InputForm with only the required parameters (items).

    This tests that the form can be created with just items and all other
    parameters use their defaults.
    """
    items = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "TextInput",
                    "id": "test_field",
                    "placeholder": "Enter text",
                },
            ],
        },
        {
            "label": "Number Field",
            "fields": [
                {
                    "type": "NumberInput",
                    "id": "number_field",
                },
                {
                    "type": "NumberInput",
                    "id": "number_field_2",
                },
                {
                    "type": "NumberInput",
                    "id": "number_field_3",
                },
            ],
        },
    ]

    items_input = copy.deepcopy(items)

    form = InputForm(items=items_input)

    # Assert public properties
    assert form.items == items
    assert form.title is None
    assert form.column_widths == {}
    assert form.columns == ["label", "fields", "unit", "description", "help"]
    assert form.column_names == []
    assert form.persistence is False
    assert form.persistence_type == "memory"

    # Assert id was auto-generated
    assert form.aio_id is not None
    assert isinstance(form.aio_id, str)
    assert len(form.aio_id) > 0


def test_input_form_with_persistence_enabled():
    """Test InputForm with global persistence=True stores the setting."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]

    form = InputForm(items=items, persistence=True)

    assert form.persistence is True
    assert form.persistence_type == "memory"  # default when not specified


def test_input_form_with_persistence_and_type():
    """Test InputForm with global persistence=True and persistence_type='session'."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]

    form = InputForm(items=items, persistence=True, persistence_type="session")

    assert form.persistence is True
    assert form.persistence_type == "session"


def test_input_form_persistence_passed_to_make_form():
    """Test that InputForm passes persistence and persistence_type to make_form."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]
    form_id = "test-persistence-form"

    mock_form_content = html.Div("Mocked form content")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        _ = InputForm(items=items, aio_id=form_id, persistence=True, persistence_type="session")

        mock_make_form.assert_called_once()
        call_args = mock_make_form.call_args
        assert call_args[0][5] is True  # persistence
        assert call_args[0][6] == "session"  # persistence_type


def test_input_form_persistence_false_passed_to_make_form():
    """Test that InputForm passes persistence=False (default) to make_form."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]
    form_id = "test-no-persistence-form"

    mock_form_content = html.Div("Mocked form content")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        _ = InputForm(items=items, aio_id=form_id)  # default: persistence=False

        mock_make_form.assert_called_once()
        call_args = mock_make_form.call_args
        assert call_args[0][5] is False  # persistence (default)
        assert call_args[0][6] == "memory"  # persistence_type (default)


def test_make_row_with_global_persistence_enabled():
    """Test that make_row applies global persistence=True to all fields."""
    form_id = "form1"
    item = {
        "fields": [
            {"type": "TextInput", "id": "field1"},
            {"type": "NumberInput", "id": "field2"},
        ]
    }
    columns = ["fields"]
    row_index = 0

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        True,
        "session",
    )

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        None,
        None,
        global_persistence=True,
        global_persistence_type="session",
    )


def test_make_row_field_level_persistence_overrides_global():
    """Test that field-level persistence=False overrides global persistence=True."""
    form_id = "form1"
    item = {
        "fields": [
            {"type": "TextInput", "id": "field1"},  # no override, uses global (True)
            {
                "type": "PasswordInput",
                "id": "password-field",
                "persistence": False,  # override: never persist
            },
        ]
    }
    columns = ["fields"]
    row_index = 0

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        True,  # global persistence = True
        "memory",
    )

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        None,
        None,
        global_persistence=True,
        global_persistence_type="memory",
    )


def test_make_row_global_persistence_false_does_not_persist_fields():
    """Test that make_row with global persistence=False sets persistence=False on fields."""
    form_id = "form1"
    item = {
        "fields": [
            {"type": "TextInput", "id": "field1"},
            {"type": "NumberInput", "id": "field2"},
        ]
    }
    columns = ["fields"]
    row_index = 0

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,  # global persistence = False (default)
        "memory",
    )

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        None,
        None,
        global_persistence=False,
        global_persistence_type="memory",
    )


def test_input_items_with_number_placeholder_conversion():
    """Test that number placeholders are converted to strings."""
    items = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "NumberInput",
                    "id": "test_field",
                    "placeholder": 42,
                },
                {
                    "type": "TextInput",
                    "id": "test_field",
                    "placeholder": 42,
                },
            ],
        },
    ]

    form = InputForm(items=items)

    # Check that the placeholder remains unchanged for NumberInput
    assert form.items[0]["fields"][0]["placeholder"] == 42
    # also check that the placeholder remains unchanged for TextInput
    assert form.items[0]["fields"][1]["placeholder"] == 42


def test_input_form_autogenerated_id():
    """Test that ID is auto-generated when not provided."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]

    form = InputForm(items=items)

    assert form.aio_id is not None
    assert isinstance(form.aio_id, str)


def test_input_form_with_custom_id():
    """Test InputForm with custom id."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]
    custom_id = "my-custom-form-id"

    form = InputForm(items=items, aio_id=custom_id)

    assert form.aio_id == custom_id


def test_input_form_with_title():
    """Test InputForm with a title."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]
    title = "My Custom Form"

    form = InputForm(items=items, title=title)

    assert form.title == title


def test_input_form_with_custom_columns():
    """Test InputForm with custom columns order."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]
    custom_columns = ["fields", "label", "description"]

    form = InputForm(items=items, columns=custom_columns)

    assert form.columns == custom_columns


def test_input_form_with_custom_column_names():
    """Test InputForm with custom column names."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]
    column_names = ["Parameter", "Value", "Info", "Units", "Details"]

    form = InputForm(items=items, column_names=column_names)

    assert form.column_names == column_names


def test_input_form_with_custom_column_widths():
    """Test InputForm with custom column widths."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]
    column_widths = {
        "label": 3,
        "unit": 2,
        "fields": 4,
        "description": 2,
        "help": 1,
    }

    form = InputForm(items=items, column_widths=column_widths)

    assert form.column_widths == column_widths


def test_input_form_with_partial_custom_column_widths():
    """Test InputForm with partially custom column widths."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]
    # Only override some widths
    partial_widths = {
        "label": 4,
        "fields": 6,
    }

    form = InputForm(items=items, column_widths=partial_widths)

    # The form stores what was passed
    assert form.column_widths == partial_widths


# ==== Tests for InputForm validation (columns definition) ====


def test_input_form_creation_with_empty_columns():
    """Test that InputForm raises error when columns list is empty."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]

    with pytest.raises(ValueError, match="Columns list cannot be empty"):
        InputForm(items=items, columns=[])


def test_input_form_creation_with_duplicate_columns():
    """Test that InputForm raises error when columns list has duplicates."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]

    with pytest.raises(ValueError, match="Duplicate column names are not allowed in columns list"):
        InputForm(items=items, columns=["fields", "label", "fields"])


def test_input_form_creation_with_unsupported_column():
    """Test that InputForm raises error when columns list has unsupported column names."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]

    with pytest.raises(ValueError, match="Unsupported column name: invalid_column"):
        InputForm(items=items, columns=["fields", "invalid_column"])


def test_input_form_creation_with_multiple_unsupported_columns():
    """Test that InputForm raises error when columns list has multiple unsupported column names."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]

    # Should fail on the first unsupported column
    with pytest.raises(ValueError, match="Unsupported column name"):
        InputForm(items=items, columns=["invalid1", "fields", "invalid2"])


def test_input_form_creation_with_valid_custom_columns():
    """Test that InputForm can be created with valid custom columns."""
    items = [{"fields": [{"type": "TextInput", "id": "field1"}]}]

    # Test with a subset of valid columns
    form1 = InputForm(items=items, columns=["fields", "label"])
    assert form1.columns == ["fields", "label"]

    # Test with all valid columns in different order
    form2 = InputForm(items=items, columns=["help", "description", "fields", "unit", "label"])
    assert form2.columns == ["help", "description", "fields", "unit", "label"]

    # Test with single column
    form3 = InputForm(items=items, columns=["fields"])
    assert form3.columns == ["fields"]


# ==== Tests for InputForm validation (items definition) ====


def test_input_form_creation_with_valid_items():
    """Test that InputForm can be created with valid items structure."""
    valid_items = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "TextInput",
                    "id": "test_field",
                    "placeholder": "Enter text",
                },
            ],
        },
    ]

    # Should not raise any errors
    form = InputForm(items=valid_items)
    assert form is not None
    assert isinstance(form, InputForm)


def test_input_form_creation_missing_fields_key():
    """Test that InputForm raises error when items are missing 'fields' key."""
    invalid_items = [
        {
            "label": "Test Field",
            # Missing 'fields' key
        },
    ]

    with pytest.raises(ValueError, match="Each item must have a fields key"):
        InputForm(items=invalid_items)


def test_input_form_creation_empty_fields():
    """Test that InputForm raises error when 'fields' is empty or None."""
    invalid_items_empty = [
        {
            "label": "Test Field",
            "fields": [],  # Empty fields
        },
    ]

    with pytest.raises(ValueError, match="Each item must have a fields key"):
        InputForm(items=invalid_items_empty)

    invalid_items_none = [
        {
            "label": "Test Field",
            "fields": None,  # None fields
        },
    ]

    with pytest.raises(ValueError, match="Each item must have a fields key"):
        InputForm(items=invalid_items_none)


def test_input_form_creation_missing_field_type():
    """Test that InputForm raises error when field is missing 'type' key."""
    invalid_items = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "id": "test_field",
                    # Missing 'type' key
                },
            ],
        },
    ]

    with pytest.raises(ValueError, match="Each field must have a type key"):
        InputForm(items=invalid_items)


def test_input_form_creation_missing_field_id():
    """Test that InputForm raises error when field is missing 'id' key."""
    invalid_items = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "TextInput",
                    # Missing 'id' key
                },
            ],
        },
    ]

    with pytest.raises(ValueError, match="Each field must have an id key"):
        InputForm(items=invalid_items)


def test_input_form_creation_empty_field_id():
    """Test that InputForm raises error when field id is empty."""
    invalid_items_empty_string = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "TextInput",
                    "id": "",  # Empty string
                },
            ],
        },
    ]

    with pytest.raises(
        ValueError,
        match="Field id must be a non-empty string",
    ):
        InputForm(items=invalid_items_empty_string)

    invalid_items_empty_dict = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "TextInput",
                    "id": {},  # Empty dict
                },
            ],
        },
    ]

    with pytest.raises(
        ValueError,
        match="Field id must be a non-empty string",
    ):
        InputForm(items=invalid_items_empty_dict)


def test_input_form_creation_invalid_field_id_type():
    """Test that InputForm raises error when field id is not a string or dict."""
    invalid_items_number = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "TextInput",
                    "id": 123,  # Number instead of string or dict
                },
            ],
        },
    ]

    with pytest.raises(
        ValueError,
        match="Field id must be a non-empty string",
    ):
        InputForm(items=invalid_items_number)

    invalid_items_list = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "TextInput",
                    "id": ["field1"],  # List instead of string or dict
                },
            ],
        },
    ]

    with pytest.raises(
        ValueError,
        match="Field id must be a non-empty string",
    ):
        InputForm(items=invalid_items_list)


def test_input_form_creation_unsupported_field_type():
    """Test that InputForm raises error when field type is not supported."""
    invalid_items = [
        {
            "label": "Test Field",
            "fields": [
                {
                    "type": "UnsupportedFieldType",
                    "id": "test_field",
                },
            ],
        },
    ]

    with pytest.raises(ValueError, match="Unsupported field type: UnsupportedFieldType"):
        InputForm(items=invalid_items)


def test_input_form_creation_with_all_supported_field_types():
    """Test that InputForm can be created with all supported field types."""
    items_with_all_types = [
        {
            "label": "All Field Types",
            "fields": [
                {"type": "NumberInput", "id": "number_field"},
                {"type": "TextInput", "id": "text_field"},
                {"type": "PasswordInput", "id": "password_field"},
                {"type": "Checkbox", "id": "checkbox_field"},
                {"type": "Select", "id": "select_field"},
                {"type": "MultiSelect", "id": "multiselect_field"},
                {"type": "Switch", "id": "switch_field"},
                {"type": "Slider", "id": "slider_field"},
            ],
        },
    ]

    # Should not raise any errors
    form = InputForm(items=items_with_all_types)
    assert form is not None
    assert isinstance(form, InputForm)


def test_input_form_creation_does_not_mutate_inputs():
    """Test that InputForm creation does not mutate the original items."""
    items = [
        {
            "label": "Numeric Field",
            "fields": [
                {
                    "type": "NumberInput",
                    "id": "number_field",
                    "placeholder": 123,  # Numeric placeholder
                },
            ],
        },
    ]

    items_copy = copy.deepcopy(items)
    form = InputForm(items=items_copy)

    # Check that InputForm creation does not mutate the input
    assert items_copy == items
    # The form should store the items as-is
    assert form.items == items


def test_input_form_creation_does_not_mutate_nested_field_style_inputs():
    """Test that InputForm creation does not mutate nested field style dictionaries."""
    items = [
        {
            "label": "Styled Text Field",
            "fields": [
                {
                    "type": "TextInput",
                    "id": "styled_text",
                    "style": {"backgroundColor": "red"},
                },
            ],
        },
    ]

    items_copy = copy.deepcopy(items)

    _ = InputForm(items=items_copy)

    # Ensure InputForm internals do not back-propagate default width into caller input.
    assert items_copy == items
    assert "width" not in items_copy[0]["fields"][0]["style"]


# ==== Tests for compute_final_column_widths function ====


@pytest.mark.parametrize(
    ("columns", "input_column_widths", "expected_output"),
    [
        # Test 1: All 5 columns with empty input - should return defaults
        (
            ["label", "unit", "fields", "description", "help"],
            {},
            {
                "label": 2,
                "unit": 1,
                "fields": 5,
                "description": 3,
                "help": 1,
            },
        ),
        # Test 2: All 5 columns with partial custom widths - should merge with defaults
        (
            ["label", "unit", "fields", "description", "help"],
            {"label": 4, "fields": 6},
            {
                "label": 4,
                "unit": 1,
                "fields": 6,
                "description": 3,
                "help": 1,
            },
        ),
        # Test 3: All 5 columns with all custom widths, sum 12 - should use custom values
        (
            ["label", "unit", "fields", "description", "help"],
            {
                "label": 3,
                "unit": 2,
                "fields": 4,
                "description": 2,
                "help": 1,
            },
            {
                "label": 3,
                "unit": 2,
                "fields": 4,
                "description": 2,
                "help": 1,
            },
        ),
        # Test 4: All 5 columns with all custom widths, sum not 12 - should use custom values
        (
            ["label", "unit", "fields", "description", "help"],
            {
                "label": 5,
                "unit": 2,
                "fields": 4,
                "description": 2,
                "help": 2,
            },
            {
                "label": 5,
                "unit": 2,
                "fields": 4,
                "description": 2,
                "help": 2,
            },
        ),
        # Test 5: Only 3 columns
        (
            ["label", "fields", "description"],
            {},
            {
                "label": 2,
                "fields": 5,
                "description": 3,
            },
        ),
        # Test 6: Only 1 column
        (
            ["fields"],
            {},
            {
                "fields": 5,
            },
        ),
        # Test 7: Custom columns order (different from default) with 3 columns
        (
            ["fields", "unit", "help"],
            {},
            {
                "unit": 1,
                "fields": 5,
                "help": 1,
            },
        ),
        # Test 8: 3 columns with partial custom widths
        (
            ["label", "fields", "description"],
            {"label": 4, "fields": 6},
            {
                "label": 4,
                "fields": 6,
                "description": 3,
            },
        ),
        # Test 9: no columns, no custom widths - should return empty dict
        (
            [],
            {},
            {},
        ),
        # Test 10: no columns, with custom widths - should return empty dict
        (
            [],
            {"label": 4, "fields": 6},
            {},
        ),
    ],
)
def test_compute_final_column_widths(
    columns: list[str],
    input_column_widths: dict[str, int],
    expected_output: dict[str, int],
):
    """Test the compute_final_column_widths function with various column/width configurations."""
    result = compute_final_column_widths(columns, input_column_widths)

    assert result == expected_output


def test_compute_final_column_widths_does_not_mutate_input():
    """Test that compute_final_column_widths does not mutate the input column_widths dict."""
    columns = ["label", "fields", "description"]
    input_widths = {
        "label": 3,
        "fields": 7,
    }  # only partial widths provided - result will merge in default value

    # Make a copy to verify later
    original_input = input_widths.copy()

    _ = compute_final_column_widths(columns, input_widths)

    # Input should not be mutated
    assert input_widths == original_input


def test_compute_final_column_widths_value_errors_with_unexpected_inputs():
    """Test that compute_final_column_widths raises ValueError with unexpected inputs."""
    # Test with invalid column names in input widths
    with pytest.raises(ValueError, match="Unsupported column name: invalid_column"):
        _ = compute_final_column_widths(["fields"], {"invalid_column": 1})

    # Test with invalid width values (non-integer or non-positive)
    with pytest.raises(ValueError, match="Column widths must be positive integers"):
        _ = compute_final_column_widths(["fields"], {"label": "invalid_width"})  # type: ignore

    with pytest.raises(ValueError, match="Column widths must be positive integers"):
        _ = compute_final_column_widths(["fields"], {"fields": 1.5})  # type: ignore

    with pytest.raises(ValueError, match="Column widths must be positive integers"):
        _ = compute_final_column_widths(["fields"], {"fields": 0})  # type: ignore

    with pytest.raises(ValueError, match="Column widths must be positive integers"):
        _ = compute_final_column_widths(["fields"], {"fields": -1})  # type: ignore


# ==== Tests for the make_row function ====

EXPECTED_DIV_STYLE_REGULAR = {"width": "100%"}
EXPECTED_DIV_STYLE_HIDDEN = {"width": "100%", "display": "none"}
DEFAULT_COLUMN_WIDTHS = {
    "label": 2,
    "unit": 1,
    "fields": 5,
    "description": 3,
    "help": 1,
}
HELP_ICON_SRC = create_base64_svg_src(IconNames.MATERIAL_HELP, "#000")


def test_make_row_only_fields_single_number_input_defaults():
    """Test making a row with only fields and number input."""
    form_id = "form1"
    item = {"fields": [{"type": "NumberInput", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_number_input_no_field_id():
    """Test making a row with only fields and number input."""
    form_id = "form1"
    item = {"fields": [{"type": "NumberInput"}]}
    columns = ["fields"]
    row_index = 1

    # note/bug: Even though there is a logic implemented to auto-assign field IDs,
    # the make_row function currently expects field IDs to be provided. Thus, this test will raise
    # an error.
    with pytest.raises(KeyError):
        _ = make_row(form_id, item, columns, {}, row_index, False, "memory")


def test_make_row_only_fields_single_number_input_hidden():
    """Test making a row with only fields and number input."""
    form_id = "form1"
    item = {"fields": [{"type": "NumberInput", "id": "field1", "hidden": True}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_number_input_with_row_id_and_full_column_widths_given():
    """Test making a row with only fields and number input."""
    form_id = "form1"
    row_id = "row-1"
    item = {"fields": [{"type": "NumberInput", "id": "field1"}], "id": row_id}
    columns = ["fields"]
    row_counter = 1  # The numeric counter
    # Extract the actual row_index that will be used (matching make_form logic)
    actual_row_index = item.get("id", row_counter)
    column_widths = {
        "label": 3,
        "unit": 2,
        "fields": 4,
        "description": 2,
        "help": 1,
    }

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        column_widths,
        actual_row_index,  # Pass the actual row_index, not row_counter
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_counter,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
        row_id=row_id,
        column_widths=column_widths,
    )


def test_make_row_only_fields_single_number_input_with_row_id_and_partial_column_widths_given():
    """Test making a row with only fields and number input."""
    form_id = "form1"
    row_id = "row-1"
    item = {"fields": [{"type": "NumberInput", "id": "field1"}], "id": row_id}
    columns = ["fields"]
    row_counter = 1
    # Extract the actual row_index that will be used (matching make_form logic)
    actual_row_index = item.get("id", row_counter)
    column_widths = {
        "fields": 3,
        "unit": 2,
        "help": 1,
    }

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        column_widths,
        actual_row_index,  # Pass the actual row_index, not row_counter
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_counter,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
        row_id=row_id,
        column_widths=column_widths,
    )


def test_make_row_only_fields_single_number_input_defaults_more_field_properties():
    """Test making a row with only fields and number input."""
    form_id = "form1"
    item = {
        "fields": [
            {
                "type": "NumberInput",
                "id": "field1",
                "min": 0,
                "max": 100,
                "step": 1,
                "style": {"color": "red"},
            },
        ],
    }
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_text_input_defaults():
    """Test making a row with only fields and text input."""
    form_id = "form1"
    item = {"fields": [{"type": "TextInput", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_password_input_defaults():
    """Test making a row with only fields and password input."""
    form_id = "form1"
    item = {"fields": [{"type": "PasswordInput", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_password_input_with_persistence():
    """Test making a row with only fields and password input."""
    form_id = "form1"
    item = {"fields": [{"type": "PasswordInput", "id": "field1", "persistence": False}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_checkbox_defaults():
    """Test making a row with only fields and checkbox."""
    form_id = "form1"
    item = {"fields": [{"type": "Checkbox", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_select_defaults():
    """Test making a row with only fields and select."""
    form_id = "form1"
    item = {"fields": [{"type": "Select", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_multi_select_defaults():
    """Test making a row with only fields and multi-select."""
    form_id = "form1"
    item = {"fields": [{"type": "MultiSelect", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_slider_defaults():
    """Test making a row with only fields and slider."""
    form_id = "form1"
    item = {"fields": [{"type": "Slider", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_single_switch_defaults():
    """Test making a row with only fields and switch."""
    form_id = "form1"
    item = {"fields": [{"type": "Switch", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_only_fields_multiple_inputs():
    """Test making a row with only fields multiple inputs."""
    form_id = "form1"
    item = {
        "fields": [
            {"type": "NumberInput", "id": "field1", "min": 0},
            {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
            {"type": "Checkbox", "id": "field3", "label": "Check me"},
        ],
    }
    columns = ["fields"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None  # Default title is None, no title provided in item
    expected_help_text = None  # No help text provided in item

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_help_and_fields_no_row_id_simple_text():
    """Test making a row with help and fields."""
    form_id = "form1"
    item = {
        "fields": [
            {"type": "NumberInput", "id": "field1", "min": 0},
            {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
        ],
        "help": "This is a help text",
    }
    columns = ["fields", "help"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None
    expected_help_text = "This is a help text"

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_help_text,
    )


def test_make_row_help_and_fields_complex_help():
    """Test making a row with help and fields."""
    help_content = [
        "This is line 1 of help text.",
        html.Div("This is a Div in help text."),
        dmc.Image(
            src="/assets/images/solution-workflow-sketch.png",
        ),
    ]
    form_id = "form1"
    item = {
        "fields": [
            {"type": "NumberInput", "id": "field1", "min": 0},
            {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
        ],
        "help": help_content,
    }
    columns = ["fields", "help"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        help_content,
    )


def test_make_row_all_props_with_row_id_and_column_widths():
    """Test making a row with all possible properties."""
    form_id = "form1"
    row_id = "row-1"
    item = {
        "fields": [
            {"type": "NumberInput", "id": "field1", "min": 0},
            {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
        ],
        "help": "This is a help text",
        "label": "Test Label",
        "unit": "Kgm^{2}s^{-3}A^{-1}",
        "description": "This is a description",
        "id": row_id,
    }
    columns = ["fields", "help", "label", "unit", "description"]
    column_widths = {
        "label": 4,
        "unit": 2,
        "fields": 6,
        "description": 2,
        "help": 1,
    }
    row_counter = 1
    # Extract the actual row_index that will be used (matching make_form logic)
    actual_row_index = item.get("id", row_counter)

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        copy.deepcopy(column_widths),
        actual_row_index,  # Pass actual_row_index
        False,
        "memory",
    )

    expected_modal_title = "Test Label"
    expected_modal_help_text = "This is a help text"

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_counter,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_modal_help_text,
        row_id=row_id,
        column_widths=column_widths,
    )


def test_make_row_all_props_no_row_id_and_column_widths():
    """Test making a row with all possible properties."""
    form_id = "form1"
    item = {
        "fields": [
            {"type": "NumberInput", "id": "field1", "min": 0},
            {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
        ],
        "help": "This is a help text",
        "label": "Test Label",
        "unit": "Kgm^{2}s^{-3}A^{-1}",
        "description": "This is a description",
    }
    columns = ["fields", "help", "label", "unit", "description"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = "Test Label"
    expected_modal_help_text = "This is a help text"

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_modal_help_text,
    )


def test_make_row_all_props_only_fields_in_item():
    """Test making a row with all possible properties."""
    form_id = "form1"
    item = {
        "fields": [
            {"type": "NumberInput", "id": "field1", "min": 0},
            {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
        ],
    }
    columns = ["fields", "help", "label", "unit", "description"]
    row_index = 1

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        DEFAULT_COLUMN_WIDTHS.copy(),
        row_index,
        False,
        "memory",
    )

    expected_modal_title = None
    expected_modal_help_text = None

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_index,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_modal_help_text,
    )


def test_make_row_all_props_change_order_of_columns():
    """Test making a row with all possible properties."""
    form_id = "form1"
    row_id = "row-1"
    item = {
        "fields": [
            {"type": "NumberInput", "id": "field1", "min": 0},
            {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
        ],
        "help": "This is a help text",
        "label": "Test Label",
        "unit": "Kgm^{2}s^{-3}A^{-1}",
        "description": "This is a description",
        "id": row_id,
    }
    columns = ["description", "unit", "label", "help", "fields"]
    column_widths = {
        "label": 4,
        "unit": 2,
        "fields": 6,
        "description": 2,
        "help": 1,
    }
    row_counter = 1
    # Extract the actual row_index that will be used (matching make_form logic)
    actual_row_index = item.get("id", row_counter)

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        copy.deepcopy(column_widths),
        actual_row_index,
        False,
        "memory",
    )

    expected_modal_title = "Test Label"
    expected_modal_help_text = "This is a help text"

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_counter,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_modal_help_text,
        row_id=row_id,
        column_widths=column_widths,
    )


def test_make_row_all_props_only_some_columns_selected():
    """Test making a row with all possible properties."""
    form_id = "form1"
    row_id = "row-1"
    item = {
        "fields": [
            {"type": "NumberInput", "id": "field1", "min": 0},
            {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
        ],
        "help": "This is a help text",
        "label": "Test Label",
        "unit": "Kgm^{2}s^{-3}A^{-1}",
        "description": "This is a description",
        "id": row_id,
    }
    columns = ["description", "unit", "fields"]
    column_widths = {
        "label": 4,
        "unit": 2,
        "fields": 6,
        "description": 2,
        "help": 1,
    }
    row_counter = 1
    # Extract the actual row_index that will be used (matching make_form logic)
    actual_row_index = item.get("id", row_counter)

    cells_result, modal_result = make_row(
        form_id,
        copy.deepcopy(item),
        copy.deepcopy(columns),
        copy.deepcopy(column_widths),
        actual_row_index,
        False,
        "memory",
    )

    expected_modal_title = "Test Label"  # Modal title is from label even if label column not included
    expected_modal_help_text = "This is a help text"  # Modal help text is from help even if help column not included

    _assert_cells_and_modal(
        form_id,
        item,
        columns,
        row_counter,
        cells_result,
        modal_result,
        expected_modal_title,
        expected_modal_help_text,
        row_id=row_id,
        column_widths=column_widths,
    )


def test_make_row_invalid_column():
    """Test making a row with an invalid column - should raise ValueError."""
    form_id = "form1"
    item = {"fields": [{"type": "NumberInput", "id": "field1"}]}
    columns = ["fields", "invalid_column"]
    row_index = 1

    with pytest.raises(ValueError, match="Unknown column: invalid_column"):
        make_row(
            form_id,
            copy.deepcopy(item),
            copy.deepcopy(columns),
            DEFAULT_COLUMN_WIDTHS.copy(),
            row_index,
            False,
            "memory",
        )


def test_make_row_invalid_field_type():
    """Test making a row with an invalid field type - should raise ValueError."""
    form_id = "form1"
    item = {"fields": [{"type": "InvalidInput", "id": "field1"}]}
    columns = ["fields"]
    row_index = 1

    with pytest.raises(ValueError, match="Unsupported field type: InvalidInput"):
        make_row(
            form_id,
            copy.deepcopy(item),
            copy.deepcopy(columns),
            DEFAULT_COLUMN_WIDTHS.copy(),
            row_index,
            False,
            "memory",
        )


# ==== Tests for the make_form function ====


def test_make_form_simple_single_row():
    """Test making a form with a simple single-row structure.

    This approach mocks both the make_row and compute_final_column_widths functions to
    avoid testing their internal implementations, focusing only on make_form's
    assembly logic.
    """
    form_id = "test-form"
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
                {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
            ],
            "label": "Test Row",
            "unit": "m",
            "description": "Test description",
            "help": "Test help text",
        },
    ]
    columns = ["label", "unit", "fields", "description", "help"]
    column_names = ["Parameter", "Unit", "Value", "Description", "Help"]
    column_widths = {
        "label": 3,
        "unit": 1,
        "fields": 4,
        "description": 3,
        "help": 1,
    }

    # Create mock return values for make_row
    mock_row_cells = [
        dmc.GridCol(dmc.Text("Mocked Label"), span=3),
        dmc.GridCol(dmc.Text("Mocked Unit"), span=1),
        dmc.GridCol(html.Div("Mocked Fields"), span=4),
        dmc.GridCol(dmc.Text("Mocked Description"), span=3),
        dmc.GridCol(dmc.ActionIcon(html.Img()), span=1),
    ]
    mock_modal = dmc.Modal(
        id={"type": "input-form-modal", "index": f"{form_id}-row-0-modal"},
        title="Mocked Modal Title",
        children="Mocked modal content",
    )

    with (
        mock.patch("ansys.solutions.dash_super_components.input_form.make_row") as mock_make_row,
        mock.patch(
            "ansys.solutions.dash_super_components.input_form.compute_final_column_widths",
        ) as mock_compute_final_column_widths,
    ):
        mock_make_row.return_value = (mock_row_cells, mock_modal)
        mock_compute_final_column_widths.return_value = column_widths

        result = make_form(form_id, items, columns, column_names, column_widths, False, "memory")

        # Verify compute_final_column_widths was called correctly
        mock_compute_final_column_widths.assert_called_once_with(columns, column_widths)

        # Verify make_row was called correctly
        mock_make_row.assert_called_once()
        call_args = mock_make_row.call_args

        # Check positional arguments
        assert call_args[0][0] == form_id
        assert call_args[0][1] == items[0]
        assert call_args[0][2] == columns
        assert call_args[0][3] == column_widths
        assert call_args[0][4] == 0  # row_index
        assert call_args[0][5] is False  # persistence (default)
        assert call_args[0][6] == "memory"  # persistence_type (default)

    _assert_form_structure(
        result,
        columns,
        column_names,
        column_widths,
        1,
        [mock_row_cells],
        [mock_modal],
    )


def test_make_form_simple_single_row_empty_column_names():
    """Test making a form with a simple single-row structure where column names are empty.

    This approach mocks both the make_row and compute_final_column_widths functions to
    avoid testing their internal implementations, focusing only on make_form's
    assembly logic.
    """
    form_id = "test-form"
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
                {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
            ],
            "label": "Test Row",
            "unit": "m",
            "description": "Test description",
            "help": "Test help text",
        },
    ]
    columns = ["label", "unit", "fields", "description", "help"]
    column_names: list[str] = []
    column_widths = {
        "label": 3,
        "unit": 1,
        "fields": 4,
        "description": 3,
        "help": 1,
    }

    # Create mock return values for make_row
    mock_row_cells = [
        dmc.GridCol(dmc.Text("Mocked Label"), span=3),
        dmc.GridCol(dmc.Text("Mocked Unit"), span=1),
        dmc.GridCol(html.Div("Mocked Fields"), span=4),
        dmc.GridCol(dmc.Text("Mocked Description"), span=3),
        dmc.GridCol(dmc.ActionIcon(html.Img()), span=1),
    ]
    mock_modal = dmc.Modal(
        id={"type": "input-form-modal", "index": f"{form_id}-row-0-modal"},
        title="Mocked Modal Title",
        children="Mocked modal content",
    )

    with (
        mock.patch("ansys.solutions.dash_super_components.input_form.make_row") as mock_make_row,
        mock.patch(
            "ansys.solutions.dash_super_components.input_form.compute_final_column_widths",
        ) as mock_compute_final_column_widths,
    ):
        mock_make_row.return_value = (mock_row_cells, mock_modal)
        mock_compute_final_column_widths.return_value = column_widths

        result = make_form(form_id, items, columns, column_names, column_widths, False, "memory")

        # Verify compute_final_column_widths was called correctly
        mock_compute_final_column_widths.assert_called_once_with(columns, column_widths)

        # Verify make_row was called correctly
        mock_make_row.assert_called_once()

    _assert_form_structure(
        result,
        columns,
        column_names,
        column_widths,
        1,
        [mock_row_cells],
        [mock_modal],
    )


def test_make_form_simple_single_row_empty_column_widths():
    """Test making a form with a simple single-row structure where column names are empty.

    This approach mocks both the make_row and compute_final_column_widths functions to
    avoid testing their internal implementations, focusing only on make_form's
    assembly logic.
    """
    form_id = "test-form"
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
                {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
            ],
            "label": "Test Row",
            "unit": "m",
            "description": "Test description",
            "help": "Test help text",
        },
    ]
    columns = ["label", "unit", "fields", "description", "help"]
    column_names: list[str] = []
    default_column_widths = {
        "label": 2,
        "unit": 1,
        "fields": 5,
        "description": 3,
        "help": 1,
    }

    # Create mock return values for make_row
    mock_row_cells = [
        dmc.GridCol(dmc.Text("Mocked Label"), span=3),
        dmc.GridCol(dmc.Text("Mocked Unit"), span=1),
        dmc.GridCol(html.Div("Mocked Fields"), span=4),
        dmc.GridCol(dmc.Text("Mocked Description"), span=3),
        dmc.GridCol(dmc.ActionIcon(html.Img()), span=1),
    ]
    mock_modal = dmc.Modal(
        id={"type": "input-form-modal", "index": f"{form_id}-row-0-modal"},
        title="Mocked Modal Title",
        children="Mocked modal content",
    )

    with (
        mock.patch("ansys.solutions.dash_super_components.input_form.make_row") as mock_make_row,
        mock.patch(
            "ansys.solutions.dash_super_components.input_form.compute_final_column_widths",
        ) as mock_compute_final_column_widths,
    ):
        mock_make_row.return_value = (mock_row_cells, mock_modal)
        mock_compute_final_column_widths.return_value = default_column_widths

        result = make_form(
            form_id,
            items,
            columns,
            column_names,
            custom_column_widths={},
            persistence=False,
            persistence_type="memory",
        )

        # Verify compute_final_column_widths was called correctly
        mock_compute_final_column_widths.assert_called_once_with(columns, {})

        # Verify make_row was called correctly
        mock_make_row.assert_called_once()

    _assert_form_structure(
        result,
        columns,
        column_names,
        default_column_widths,
        1,
        [mock_row_cells],
        [mock_modal],
    )


def test_make_form_simple_single_row_with_row_id():
    """Test making a form with a simple single-row structure.

    This approach mocks both the make_row and compute_final_column_widths functions to
    avoid testing their internal implementations, focusing only on make_form's
    assembly logic.
    """
    form_id = "test-form"
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
                {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
            ],
            "label": "Test Row",
            "unit": "m",
            "description": "Test description",
            "help": "Test help text",
            "id": "custom-row-id",
        },
    ]
    columns = ["label", "unit", "fields", "description", "help"]
    column_names = ["Parameter", "Unit", "Value", "Description", "Help"]
    column_widths = {
        "label": 3,
        "unit": 1,
        "fields": 4,
        "description": 3,
        "help": 1,
    }

    # Create mock return values for make_row
    mock_row_cells = [
        dmc.GridCol(dmc.Text("Mocked Label"), span=3),
        dmc.GridCol(dmc.Text("Mocked Unit"), span=1),
        dmc.GridCol(html.Div("Mocked Fields"), span=4),
        dmc.GridCol(dmc.Text("Mocked Description"), span=3),
        dmc.GridCol(dmc.ActionIcon(html.Img()), span=1),
    ]
    mock_modal = dmc.Modal(
        id={"type": "input-form-modal", "index": f"{form_id}-row-0-modal"},
        title="Mocked Modal Title",
        children="Mocked modal content",
    )

    with (
        mock.patch("ansys.solutions.dash_super_components.input_form.make_row") as mock_make_row,
        mock.patch(
            "ansys.solutions.dash_super_components.input_form.compute_final_column_widths",
        ) as mock_compute_final_column_widths,
    ):
        mock_make_row.return_value = (mock_row_cells, mock_modal)
        mock_compute_final_column_widths.return_value = column_widths

        _ = make_form(form_id, items, columns, column_names, column_widths, False, "memory")

        # Verify compute_final_column_widths was called correctly
        mock_compute_final_column_widths.assert_called_once_with(columns, column_widths)

        # Verify make_row was called correctly
        mock_make_row.assert_called_once()
        call_args = mock_make_row.call_args

        # Check positional arguments
        assert call_args[0][0] == form_id
        assert call_args[0][1] == items[0]
        assert call_args[0][2] == columns
        assert call_args[0][3] == column_widths
        # Since item has "id": "custom-row-id", that's what will be passed as row_index
        assert call_args[0][4] == "custom-row-id"  # row_index (from item["id"])
        assert call_args[0][5] is False  # persistence (default)
        assert call_args[0][6] == "memory"  # persistence_type (default)


def test_make_form_two_rows():
    """Test making a form with a two-row structure.

    This approach mocks both the make_row and compute_final_column_widths functions to
    avoid testing their internal implementations, focusing only on make_form's
    assembly logic.
    """
    form_id = "test-form"
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
                {"type": "TextInput", "id": "field2", "placeholder": "Enter text"},
            ],
            "label": "Test Row",
            "unit": "m",
            "description": "Test description",
            "help": "Test help text",
        },
        {
            "fields": [{"type": "Checkbox", "id": "field3", "label": "Check me"}],
            "label": "Second Row",
            "unit": "kg",
            "description": "Second description",
            "help": "Second help text",
        },
    ]
    columns = ["label", "unit", "fields", "description", "help"]
    column_names = ["Parameter", "Unit", "Value", "Description", "Help"]
    column_widths = {
        "label": 3,
        "unit": 1,
        "fields": 4,
        "description": 3,
        "help": 1,
    }

    # Create mock return values for make_row
    mock_row_cells_1 = [
        dmc.GridCol(dmc.Text("Mocked Label"), span=3),
        dmc.GridCol(dmc.Text("Mocked Unit"), span=1),
        dmc.GridCol(html.Div("Mocked Fields"), span=4),
        dmc.GridCol(dmc.Text("Mocked Description"), span=3),
        dmc.GridCol(dmc.ActionIcon(html.Img()), span=1),
    ]
    mock_row_cells_2 = [
        dmc.GridCol(dmc.Text("Mocked Label 2"), span=3),
        dmc.GridCol(dmc.Text("Mocked Unit 2"), span=1),
        dmc.GridCol(html.Div("Mocked Fields 2"), span=4),
        dmc.GridCol(dmc.Text("Mocked Description 2"), span=3),
        dmc.GridCol(dmc.ActionIcon(html.Img()), span=1),
    ]
    mock_modal_1 = dmc.Modal(
        id={"type": "input-form-modal", "index": f"{form_id}-row-0-modal"},
        title="Mocked Modal Title",
        children="Mocked modal content",
    )
    mock_modal_2 = dmc.Modal(
        id={"type": "input-form-modal", "index": f"{form_id}-row-1-modal"},
        title="Mocked Modal Title 2",
        children="Mocked modal content 2",
    )

    with (
        mock.patch("ansys.solutions.dash_super_components.input_form.make_row") as mock_make_row,
        mock.patch(
            "ansys.solutions.dash_super_components.input_form.compute_final_column_widths",
        ) as mock_compute_final_column_widths,
    ):
        mock_make_row.side_effect = [
            (mock_row_cells_1, mock_modal_1),
            (mock_row_cells_2, mock_modal_2),
        ]
        mock_compute_final_column_widths.return_value = column_widths

        result = make_form(form_id, items, columns, column_names, column_widths, False, "memory")

        # Verify compute_final_column_widths was called correctly
        mock_compute_final_column_widths.assert_called_once_with(columns, column_widths)

        # Verify make_row was called correctly
        assert mock_make_row.call_count == 2

    _assert_form_structure(
        result,
        columns,
        column_names,
        column_widths,
        2,
        [mock_row_cells_1, mock_row_cells_2],
        [mock_modal_1, mock_modal_2],
    )


def test_make_form_column_names_length_mismatch():
    """Test that make_form raises ValueError when column names length mismatches columns length."""
    form_id = "test-form"
    items = []
    columns = ["label", "unit", "fields"]
    column_names = ["Parameter", "Unit"]  # Length mismatch here

    with pytest.raises(ValueError, match="Length of column_names must match length of columns"):
        make_form(
            form_id,
            items,
            columns,
            column_names,
            custom_column_widths={},
            persistence=False,
            persistence_type="memory",
        )


# ==== Tests for the InputForm structure ====


def test_input_form_structure_with_title():
    """Test the InputForm Div structure with a title.

    This test mocks make_form to isolate InputForm's structure logic.
    """
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
            ],
            "label": "Test Row",
        },
    ]
    form_id = "test-form-id"
    title = "Test Form Title"

    # Mock the form content returned by make_form
    mock_form_content = html.Div("Mocked form content from make_form")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        form = InputForm(items=items, aio_id=form_id, title=title)

        # Verify make_form was called correctly
        mock_make_form.assert_called_once()
        call_args = mock_make_form.call_args
        assert call_args[0][0] == form_id  # form_id
        assert str(call_args[0][1]) == str(items)  # items
        assert call_args[0][2] == [
            "label",
            "fields",
            "unit",
            "description",
            "help",
        ]  # columns (default)
        assert call_args[0][3] == []  # column_names (default)
        assert call_args[0][4] == {}  # custom_column_widths (default)
        assert call_args[0][5] is False  # persistence (default)
        assert call_args[0][6] == "memory"  # persistence_type (default)

    _assert_input_form_outer_structure(form)

    layout = form.children

    # Assert layout is a Card - default for with_card is True
    card = layout
    _assert_card(card, card_props=None)

    # Card should contain Title and the mocked form contents since we pass a title
    div_with_title_and_content = layout.children  # type: ignore - we test this in the asserts
    _assert_title_and_content(title, mock_form_content, div_with_title_and_content)


def test_input_form_structure_without_title():
    """Test the InputForm Div structure without a title.

    This test mocks make_form to isolate InputForm's structure logic.
    """
    items = [
        {
            "fields": [
                {"type": "TextInput", "id": "field1"},
            ],
            "label": "Test Row",
        },
    ]
    form_id = "test-form-id"

    # Mock the form content returned by make_form
    mock_form_content = html.Div("Mocked form content from make_form")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        form = InputForm(items=items, aio_id=form_id)

    _assert_input_form_outer_structure(form)

    layout = form.children
    # Assert layout is a Card - default for with_card is True
    card = layout
    _assert_card(card, card_props=None)

    # Card should contain Title and the mocked form contents since we pass a title
    content = layout.children  # type: ignore - we test this in the asserts
    _assert_content_only(mock_form_content, content)


def test_input_form_structure_with_title_without_card():
    """Test the InputForm Div structure with a title but without a card.

    This test mocks make_form to isolate InputForm's structure logic.
    """
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
            ],
            "label": "Test Row",
        },
    ]
    form_id = "test-form-id"
    title = "Test Form Title"

    # Mock the form content returned by make_form
    mock_form_content = html.Div("Mocked form content from make_form")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        form = InputForm(items=items, aio_id=form_id, title=title, with_card=False)

    _assert_input_form_outer_structure(form)

    layout = form.children

    # Assert layout is not a card since with_card is False
    assert not isinstance(layout, dmc.Card)

    # Layout should contain Title and the mocked form contents since we pass a title
    # since we have no card, layout is a Div with title and content directly
    div_with_title_and_content = layout
    _assert_title_and_content(title, mock_form_content, div_with_title_and_content)  # type: ignore - we test this in the asserts


def test_input_form_structure_with_custom_columns():
    """Test the InputForm structure with custom columns.

    This test mocks make_form to verify that custom columns are passed correctly.
    """
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1"},
            ],
            "label": "Test Row",
            "description": "Test description",
        },
    ]
    form_id = "test-form-id"
    custom_columns = ["description", "fields", "label"]

    # Mock the form content returned by make_form
    mock_form_content = html.Div("Mocked form content")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        _ = InputForm(items=items, aio_id=form_id, columns=custom_columns)

        # Verify make_form was called correctly
        mock_make_form.assert_called_once()
        call_args = mock_make_form.call_args
        assert call_args[0][0] == form_id  # form_id
        assert str(call_args[0][1]) == str(items)  # items
        assert call_args[0][2] == custom_columns  # columns (custom)
        assert call_args[0][3] == []  # column_names (default)
        assert call_args[0][4] == {}  # custom_column_widths (default)
        assert call_args[0][5] is False  # persistence (default)
        assert call_args[0][6] == "memory"  # persistence_type (default)


def test_input_form_structure_with_column_names():
    """Test the InputForm structure with column names.

    This test mocks make_form to verify that column names are passed correctly.
    """
    items = [
        {
            "fields": [
                {"type": "TextInput", "id": "field1"},
            ],
        },
    ]
    form_id = "test-form-id"
    column_names = ["Parameter", "Value", "Help", "Unit", "Description"]

    # Mock the form content returned by make_form
    mock_form_content = html.Div("Mocked form content")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        _ = InputForm(items=items, aio_id=form_id, column_names=column_names)

        # Verify make_form was called correctly
        mock_make_form.assert_called_once()
        call_args = mock_make_form.call_args
        assert call_args[0][0] == form_id  # form_id
        assert str(call_args[0][1]) == str(items)  # items
        assert call_args[0][2] == [
            "label",
            "fields",
            "unit",
            "description",
            "help",
        ]  # columns (default)
        assert call_args[0][3] == column_names  # column_names (custom)
        assert call_args[0][4] == {}  # custom_column_widths (default)
        assert call_args[0][5] is False  # persistence (default)
        assert call_args[0][6] == "memory"  # persistence_type (default)


def test_input_form_structure_with_column_widths():
    """Test the InputForm structure with custom column widths.

    This test mocks make_form to verify that column widths are passed correctly.
    """
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1"},
            ],
        },
    ]
    form_id = "test-form-id"
    column_widths = {
        "label": 4,
        "unit": 2,
        "fields": 3,
        "description": 2,
        "help": 1,
    }

    # Mock the form content returned by make_form
    mock_form_content = html.Div("Mocked form content")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        _ = InputForm(items=items, aio_id=form_id, column_widths=column_widths)

        # Verify make_form was called correctly
        mock_make_form.assert_called_once()
        call_args = mock_make_form.call_args
        assert call_args[0][0] == form_id  # form_id
        assert str(call_args[0][1]) == str(items)  # items
        assert call_args[0][2] == [
            "label",
            "fields",
            "unit",
            "description",
            "help",
        ]  # columns (default)
        assert call_args[0][3] == []  # column_names (default)
        assert call_args[0][4] == column_widths  # custom_column_widths
        assert call_args[0][5] is False  # persistence (default)
        assert call_args[0][6] == "memory"  # persistence_type (default)


def test_input_form_structure_with_partial_card_props_and_partial_title_props():
    """Test the InputForm Div structure with a title, card properties and title properties.

    This test mocks make_form to isolate InputForm's structure logic.
    """
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
            ],
            "label": "Test Row",
        },
    ]
    form_id = "test-form-id"
    title = "Test Form Title"
    card_props = {
        "withBorder": False,  # overwrite default
        "shadow": "md",  # overwrite default
    }
    title_props = {
        "style": {"color": "blue"},  # overwrite default
    }

    # Mock the form content returned by make_form
    mock_form_content = html.Div("Mocked form content from make_form")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        form = InputForm(
            items=items,
            aio_id=form_id,
            title=title,
            card_props=card_props,
            title_props=title_props,
        )

    _assert_input_form_outer_structure(form)

    layout = form.children

    # Assert layout is a Card - default for with_card is True
    card = layout
    _assert_card(card, card_props=card_props)

    # Card should contain Title and the mocked form contents since we pass a title
    div_with_title_and_content = layout.children  # type: ignore - we test this in the asserts
    _assert_title_and_content(
        title,
        mock_form_content,
        div_with_title_and_content,
        title_props=title_props,
    )


def test_input_form_structure_with_full_card_props_and_full_title_props():
    """Test the InputForm Div structure with a title, card properties and title properties.

    This test mocks make_form to isolate InputForm's structure logic.
    """
    items = [
        {
            "fields": [
                {"type": "NumberInput", "id": "field1", "min": 0, "max": 100},
            ],
            "label": "Test Row",
        },
    ]
    form_id = "test-form-id"
    title = "Test Form Title"
    card_props = {
        "withBorder": False,  # overwrite default
        "shadow": "md",  # overwrite default
        "radius": "lg",  # overwrite default
        "padding": "lg",  # add an extra property here
    }
    title_props = {
        "hidden": True,  # add an extra property here
        "style": {"color": "blue"},  # overwrite default
    }

    # Mock the form content returned by make_form
    mock_form_content = html.Div("Mocked form content from make_form")

    with mock.patch("ansys.solutions.dash_super_components.input_form.make_form") as mock_make_form:
        mock_make_form.return_value = mock_form_content

        form = InputForm(
            items=items,
            aio_id=form_id,
            title=title,
            card_props=card_props,
            title_props=title_props,
        )

    _assert_input_form_outer_structure(form)

    layout = form.children

    # Assert layout is a Card - default for with_card is True
    card = layout
    _assert_card(card, card_props=card_props)

    # Card should contain Title and the mocked form contents since we pass a title
    div_with_title_and_content = layout.children  # type: ignore - we test this in the asserts
    _assert_title_and_content(
        title,
        mock_form_content,
        div_with_title_and_content,
        title_props=title_props,
    )


# ==== Tests for the validate_input callback ====


def test_validate_input_callback_valid_value_within_range():
    """Test validate_input callback with a valid value within min/max range."""
    value = 50.0
    vmax = 100.0
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)

    # Should return None (no error) for valid input
    assert result is None


def test_validate_input_callback_value_exceeds_max():
    """Test validate_input callback when value exceeds maximum."""
    value = 150.0
    vmax = 100.0
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)

    assert result == "Expect value to be less than 100.0."


def test_validate_input_callback_value_below_min():
    """Test validate_input callback when value is below minimum."""
    value = -10.0
    vmax = 100.0
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)

    assert result == "Expect value to be greater than 0.0."


def test_validate_input_callback_value_equals_max():
    """Test validate_input callback when value equals maximum (should be valid)."""
    value = 100.0
    vmax = 100.0
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)

    # Exactly at max should be valid (not greater than)
    assert result is None


def test_validate_input_callback_value_equals_min():
    """Test validate_input callback when value equals minimum (should be valid)."""
    value = 0.0
    vmax = 100.0
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)

    # Exactly at min should be valid (not less than)
    assert result is None


def test_validate_input_callback_no_max_constraint():
    """Test validate_input callback with no maximum constraint."""
    value = 999999.0
    vmax = None
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)

    # Should be valid since there's no max constraint
    assert result is None


def test_validate_input_callback_no_min_constraint():
    """Test validate_input callback with no minimum constraint."""
    value = -999999.0
    vmax = 100.0
    vmin = None

    result = InputForm.validate_input(value, vmax, vmin)

    # Should be valid since there's no min constraint
    assert result is None


def test_validate_input_callback_no_constraints():
    """Test validate_input callback with no min or max constraints."""
    value = 42.0
    vmax = None
    vmin = None

    result = InputForm.validate_input(value, vmax, vmin)

    # Should be valid since there are no constraints
    assert result is None


def test_validate_input_callback_invalid_value_string():
    """Test validate_input callback with a non-numeric string value.

    The callback has a try-except block that returns no_update for invalid values.
    """
    value = "not a number"
    vmax = 100.0
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)  # type: ignore - deliberately checking wrong type

    # Should return no_update for non-numeric values
    assert result == no_update


def test_validate_input_callback_invalid_value_none():
    """Test validate_input callback with None value.

    The callback has a try-except block that returns no_update for invalid values.
    """
    value = None
    vmax = 100.0
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)  # type: ignore - deliberately checking wrong type

    # Should return no_update for None value
    assert result == no_update


def test_validate_input_callback_string_numeric_value():
    """Test validate_input callback with string that can be converted to float."""
    value = "50.5"
    vmax = 100.0
    vmin = 0.0

    result = InputForm.validate_input(value, vmax, vmin)  # type: ignore - deliberately checking wrong type

    # String "50.5" can be converted to float, should be valid
    assert result is None


# ==== Tests for the display_help callback ====


def test_display_help_callback_toggle_modal_open():
    """Test display_help callback toggles a single modal from closed to open."""
    # Click the help button (modal is currently closed)
    n_clicks = 1
    opened = False

    result = InputForm.display_help(n_clicks, opened)

    # Modal should now be opened
    assert result is True


def test_display_help_callback_toggle_modal_close():
    """Test display_help callback toggles a single modal from open to closed."""
    # Click the help button (modal is currently open)
    n_clicks = 2
    opened = True

    result = InputForm.display_help(n_clicks, opened)

    # Modal should now be closed
    assert result is False


def test_display_help_callback_no_clicks():
    """Test display_help callback with no clicks raises PreventUpdate."""
    # No clicks yet
    n_clicks = 0
    opened = False

    with pytest.raises(PreventUpdate):
        InputForm.display_help(n_clicks, opened)


def test_display_help_callback_none_clicks():
    """Test display_help callback with None clicks raises PreventUpdate."""
    # Clicks is None (initial state)
    n_clicks = None
    opened = False

    with pytest.raises(PreventUpdate):
        InputForm.display_help(n_clicks, opened)  # type: ignore


def test_display_help_callback_multiple_toggles():
    """Test display_help callback toggling the same modal multiple times."""
    # First click - open
    n_clicks = 1
    opened = False
    result = InputForm.display_help(n_clicks, opened)
    assert result is True

    # Second click - close
    n_clicks = 2
    opened = True
    result = InputForm.display_help(n_clicks, opened)
    assert result is False

    # Third click - open again
    n_clicks = 3
    opened = False
    result = InputForm.display_help(n_clicks, opened)
    assert result is True


# ==== Assert helper functions for the make_row and make_form functions ====


def _assert_cells_and_modal(
    form_id: str,
    item: dict[str, Any],
    columns: list[str],
    row_counter: int,
    cells_result: list[dmc.GridCol],
    modal_result: dmc.Modal,
    expected_modal_title: str | None,
    expected_help_text: Any | None,
    row_id: str | None = None,
    column_widths: dict[str, int] | None = None,
    global_persistence: bool = False,
    global_persistence_type: str = "memory",
):
    row_index = row_id if row_id is not None else row_counter

    assert cells_result
    assert isinstance(cells_result, list)
    _assert_cells(
        cells_result,
        form_id,
        item,
        columns,
        row_index,
        column_widths=column_widths,
        global_persistence=global_persistence,
        global_persistence_type=global_persistence_type,
    )

    assert modal_result is not None
    assert isinstance(modal_result, dmc.Modal)

    _assert_modal(modal_result, form_id, row_index, expected_modal_title, expected_help_text)


def _assert_cells(
    cells: list[Any],
    form_id: str,
    item: dict[str, Any],
    columns: list[str],
    row_index: str | int,
    column_widths: dict[str, int] | None,
    global_persistence: bool = False,
    global_persistence_type: str = "memory",
):
    expected_number_of_cells = len(columns)
    assert len(cells) == expected_number_of_cells

    for i, column in enumerate(columns):
        cell = cells[i]

        assert isinstance(cell, dmc.GridCol)
        expected_span = (
            column_widths.get(column, DEFAULT_COLUMN_WIDTHS[column]) if column_widths else DEFAULT_COLUMN_WIDTHS[column]
        )
        assert cell.span == expected_span

        if column == "fields":
            _assert_fields_cell(
                form_id,
                cell,
                item["fields"],
                row_index,
                global_persistence=global_persistence,
                global_persistence_type=global_persistence_type,
            )

        elif column == "label":
            _assert_label_cell(form_id, row_index, cell, item.get("label"))

        elif column == "unit":
            _assert_unit_cell(form_id, row_index, cell, item.get("unit"))

        elif column == "description":
            _assert_description_cell(form_id, row_index, cell, item.get("description"))

        elif column == "help":
            _assert_help_cell(form_id, row_index, cell, item.get("help"))

        else:
            raise AssertionError(f"Unknown column type: {column}")


def _assert_fields_cell(
    form_id: str,
    cell: dmc.GridCol,
    reference_fields: list[dict[str, Any]],
    row_index: int | str,
    global_persistence: bool = False,
    global_persistence_type: str = "memory",
):
    cell_div = cell.children
    assert isinstance(cell_div, html.Div)
    assert cell_div.style == {
        "display": "flex",
        "flexDirection": "row",
        "justifyContent": "space-between",
        "alignItems": "center",
        "gap": "10px",
    }

    assert cell_div.children is not None
    input_field_divs = cell_div.children
    expected_number_of_input_fields = len(reference_fields)
    assert len(input_field_divs) == expected_number_of_input_fields

    for i, input_field_div in enumerate(input_field_divs):
        reference_field = reference_fields[i]

        _assert_input_field_div(
            form_id,
            input_field_div,
            reference_field,
            row_index,
            global_persistence=global_persistence,
            global_persistence_type=global_persistence_type,
        )


def _assert_input_field_div(
    form_id: str,
    input_field_div: html.Div,
    reference_field: dict[str, Any],
    row_index: int | str,
    global_persistence: bool = False,
    global_persistence_type: str = "memory",
):
    expected_field_type = reference_field["type"]
    input_field_id = reference_field["id"]
    expected_hidden = reference_field.get("hidden", False)
    # Determine expected persistence: field-level overrides global setting
    expected_persistence = reference_field.get("persistence", global_persistence)
    expected_persistence_type = reference_field.get("persistence_type", global_persistence_type)

    expected_div_id = InputForm.ids.field_div(form_id, expected_field_type, input_field_id, row_index)
    expected_div_style = EXPECTED_DIV_STYLE_HIDDEN if expected_hidden else EXPECTED_DIV_STYLE_REGULAR

    expected_field_id = InputForm.ids.field(form_id, expected_field_type, input_field_id, row_index)

    expected_field_style: dict[str, Any] = {} if "style" not in reference_field else reference_field["style"].copy()
    expected_field_style["width"] = "100%"

    assert isinstance(input_field_div, html.Div)
    assert input_field_div.id == expected_div_id
    assert input_field_div.style == expected_div_style

    assert input_field_div.children is not None
    input_field = input_field_div.children
    _assert_input_field_type(expected_field_type, input_field)

    assert input_field.persistence == expected_persistence
    if expected_persistence:
        assert input_field.persistence_type == expected_persistence_type
    assert input_field.style == expected_field_style
    assert input_field.id == expected_field_id

    # Check that other properties except type, hidden, persistence, style, and id match
    for prop, value in reference_field.items():
        if prop in ["type", "hidden"]:
            continue  # not properties of the input field
        if prop in ["persistence", "style", "id"]:
            continue  # Already checked these properties

        assert getattr(input_field, prop) == value


def _assert_input_field_type(expected_field_type: str, input_field: Any):
    if expected_field_type == "NumberInput":
        assert isinstance(input_field, dmc.NumberInput)
    elif expected_field_type == "TextInput":
        assert isinstance(input_field, dmc.TextInput)
    elif expected_field_type == "PasswordInput":
        assert isinstance(input_field, dmc.PasswordInput)
    elif expected_field_type == "Checkbox":
        assert isinstance(input_field, dmc.Checkbox)
    elif expected_field_type == "Select":
        assert isinstance(input_field, dmc.Select)
    elif expected_field_type == "MultiSelect":
        assert isinstance(input_field, dmc.MultiSelect)
    elif expected_field_type == "Switch":
        assert isinstance(input_field, dmc.Switch)
    elif expected_field_type == "Slider":
        assert isinstance(input_field, dmc.Slider)
    else:
        raise AssertionError(f"Unknown input field type: {expected_field_type}")


def _assert_label_cell(
    form_id: str,
    row_id: str | int,
    cell: dmc.GridCol,
    expected_label: str | None,
):
    assert cell.style == {
        "display": "flex",
        "alignItems": "center",
    }

    label = cell.children
    assert isinstance(label, dmc.Text)
    assert label.children == expected_label
    assert label.id == InputForm.ids.label(form_id, row_id)


def _assert_unit_cell(
    form_id: str,
    row_id: str | int,
    cell: dmc.GridCol,
    expected_unit: str | None,
):
    assert cell.style == {
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
    }

    unit = cell.children
    assert isinstance(unit, dmc.Text)
    assert unit.id == InputForm.ids.unit(form_id, row_id)
    unit_markdown = unit.children
    if expected_unit is None:
        assert unit_markdown is None
    else:
        assert isinstance(unit_markdown, dcc.Markdown)
        assert unit_markdown.mathjax
        assert unit_markdown.children == f"${expected_unit}$"


def _assert_description_cell(
    form_id: str,
    row_id: str | int,
    cell: dmc.GridCol,
    expected_description: str | None,
):
    assert cell.style == {
        "display": "flex",
        "alignItems": "center",
    }

    description = cell.children
    assert isinstance(description, dmc.Text)
    assert description.id == InputForm.ids.description(form_id, row_id)
    assert description.children == expected_description


def _assert_help_cell(form_id: str, row_index: int | str, cell: dmc.GridCol, expected_help: Any | None):
    assert cell.style == {
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
    }

    help_content = cell.children
    assert isinstance(help_content, dmc.ActionIcon)
    assert help_content.id == InputForm.ids.help(form_id, row_index)
    assert help_content.size == "xl"
    assert help_content.variant == "subtle"
    if expected_help is None:
        assert help_content.style == {
            "display": "flex",
            "visibility": "hidden",
            "textAlign": "center",
        }
    else:
        assert help_content.style == {
            "display": "flex",
            "visibility": "visible",
            "textAlign": "center",
        }
    help_icon = help_content.children
    assert isinstance(help_icon, html.Span)
    assert help_icon.style is not None
    assert help_icon.style.get("backgroundColor") == CommonColors.MANTINE_PRIMARY_COLOR
    assert help_icon.style.get("width") == "16px"
    assert help_icon.style.get("height") == "16px"
    expected_url_values = {
        f"url('{HELP_ICON_SRC}')",
        f'url("{HELP_ICON_SRC}")',
    }
    assert str(help_icon.style.get("maskImage", "")) in expected_url_values
    assert str(help_icon.style.get("WebkitMaskImage", "")) in expected_url_values


def _assert_modal(
    modal: dmc.Modal,
    form_id: str,
    row_index: int | str,
    expected_modal_title: str | None,
    expected_help: Any | None,
):
    """Assert that a modal has the expected properties."""
    expected_modal_id = InputForm.ids.modal(form_id, row_index)
    assert modal.id == expected_modal_id
    assert modal.title == expected_modal_title
    assert modal.zIndex == 10000
    assert modal.size == "50%"
    assert modal.centered
    assert str(modal.children) == str(
        expected_help,
    )  # comparing str representations to avoid issues with comparing actual component instances


def _assert_form_structure(
    form: html.Div,
    columns: list[str],
    column_names: list[str],
    column_widths: dict[str, int],
    number_of_rows: int,
    mock_row_cells: list[list[dmc.GridCol]],
    mock_modals: list[dmc.Modal],
):
    # Assert the outer structure
    assert isinstance(form, html.Div)
    assert getattr(form, "style", None) is None

    # Result should contain a Grid and modals
    assert isinstance(form.children, list)
    assert len(form.children) == 1 + number_of_rows  # 1 Grid + number_of_rows modals

    # First child should be the Grid
    grid = form.children[0]
    assert isinstance(grid, dmc.Grid)
    assert grid.gutter == "xs"
    assert not grid.grow

    # Grid should have header cells + mocked row cells
    assert grid.children is not None
    grid_cells = grid.children
    expected_header_cells = len(
        column_names,
    )  # no checking is done currently to ensure column_names length matches columns length
    expected_cells_per_row = len(columns)
    expected_total_cells = expected_header_cells + (number_of_rows * expected_cells_per_row)
    assert len(grid_cells) == expected_total_cells

    # Validate header cells
    for i, column_name in enumerate(column_names):
        header_cell = grid_cells[i]
        assert isinstance(header_cell, dmc.GridCol)
        column_key = columns[i]
        expected_span = column_widths.get(column_key, 1)
        assert header_cell.span == expected_span

        header_text = header_cell.children
        assert isinstance(header_text, dmc.Text)
        assert header_text.children == column_name
        assert header_text.fw == 700

    # Validate that the mocked row cells are in the grid
    for row_idx in range(number_of_rows):
        start_index = expected_header_cells + (row_idx * expected_cells_per_row)
        end_index = start_index + expected_cells_per_row
        row_cells = grid_cells[start_index:end_index]
        assert row_cells == mock_row_cells[row_idx]

    # Validate that the mocked modals are in the form
    for row_idx in range(number_of_rows):
        assert form.children[1 + row_idx] == mock_modals[row_idx]


# ==== Helper assertion methods for InputForm structure ====


def _assert_input_form_outer_structure(form: InputForm):
    assert isinstance(form, html.Div)

    assert getattr(form, "style", None) is None

    # Assert the structure: should have a Card or be a Div
    assert isinstance(form.children, dmc.Card | html.Div)


def _assert_card(card: Any, card_props: dict[str, Any] | None = None):
    assert isinstance(card, dmc.Card)

    if card_props is None:
        card_props = {}

    # assert default card props (might be overridden by card_props)
    assert card.withBorder == card_props.get("withBorder", True)
    assert card.shadow == card_props.get("shadow", "sm")
    assert card.radius == card_props.get("radius", "md")

    if card_props:
        for prop, value in card_props.items():
            assert getattr(card, prop) == value


def _assert_title_and_content(
    title: str,
    mock_form_content: html.Div,
    div_with_title_and_content: html.Div,
    title_props: dict[str, Any] | None = None,
):
    if title_props is None:
        title_props = {}

    assert isinstance(div_with_title_and_content, html.Div)
    assert div_with_title_and_content.children is not None
    assert len(div_with_title_and_content.children) == 4

    title_component = div_with_title_and_content.children[0]
    assert isinstance(title_component, html.P)
    assert title_component.children == title

    # assert title default props (might be overridden by title_props):
    assert title_component.style == title_props.get(
        "style",
        {
            "fontSize": "18px",
            "fontWeight": "bold",
        },
    )

    hr_component = div_with_title_and_content.children[1]
    assert isinstance(hr_component, html.Hr)
    assert hr_component.className == "my-2"

    break_component = div_with_title_and_content.children[2]
    assert isinstance(break_component, html.Br)

    form_content = div_with_title_and_content.children[3]
    assert form_content == mock_form_content


def _assert_content_only(mock_form_content: html.Div, content: html.Div):
    assert str(content) == str(mock_form_content)
