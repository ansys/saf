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


"""Unit tests for the DualInputRangeSlider component."""

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false

from unittest import mock

try:
    # dash >=3.2.0
    from dash import NoUpdate
except ImportError:
    # dash >=2.18.2, <3.2.0
    from dash._callback import NoUpdate  # pyright: ignore[reportPrivateImportUsage]
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import html, no_update
import dash_mantine_components as dmc
import pytest

from ansys.solutions.dash_super_components.dual_input_range_slider import DualInputRangeSlider


def test_ids():
    """Verify ID generation for DualInputRangeSlider subcomponents."""
    aio_id = "dummy-id"
    slider = DualInputRangeSlider(min=0, max=100, aio_id=aio_id)
    assert slider.aio_id == aio_id

    assert slider.ids.slider(aio_id) == {
        "component": "dual-input-range-slider",
        "subcomponent": "slider",
        "aio_id": aio_id,
    }
    assert slider.ids.lower_bound_input(aio_id) == {
        "component": "dual-input-range-slider",
        "subcomponent": "lower-bound-input",
        "aio_id": aio_id,
    }
    assert slider.ids.upper_bound_input(aio_id) == {
        "component": "dual-input-range-slider",
        "subcomponent": "upper-bound-input",
        "aio_id": aio_id,
    }


def test_dual_input_range_slider_initialization():
    """Ensure DualInputRangeSlider initializes with correct default structure and props."""
    slider = DualInputRangeSlider(min=0, max=100)

    assert isinstance(slider, html.Div)

    assert slider.aio_id
    assert isinstance(slider.aio_id, str)

    assert slider.children is not None
    assert len(slider.children) == 1
    inner_div = slider.children[0]
    assert isinstance(inner_div, html.Div)

    assert inner_div.children is not None
    dmc_group = inner_div.children
    assert isinstance(dmc_group, dmc.Group)

    assert dmc_group.justify == "center"
    assert dmc_group.gap == "xs"

    assert dmc_group.children is not None
    assert len(dmc_group.children) == 3
    number_input = dmc_group.children[0]
    range_slider = dmc_group.children[1]
    upper_number_input = dmc_group.children[2]

    assert isinstance(number_input, dmc.NumberInput)
    assert number_input.id == slider.ids.lower_bound_input(slider.aio_id)
    assert number_input.label == "Min"
    assert number_input.value == 0  # default value is min
    assert number_input.min == 0
    assert number_input.max == 100
    assert number_input.step == 10
    assert number_input.decimalScale == 1
    assert number_input.variant == "filled"
    assert number_input.style == {"width": "15%"}
    assert number_input.debounce is True
    assert number_input.clampBehavior == "strict"

    assert isinstance(range_slider, dmc.RangeSlider)
    assert range_slider.id == slider.ids.slider(slider.aio_id)
    assert range_slider.value == [0, 100]  # default value is [min, max]
    assert range_slider.min == 0
    assert range_slider.max == 100
    assert range_slider.step == 10
    assert range_slider.style == {"width": "60%"}
    assert range_slider.minRange == 0

    assert isinstance(upper_number_input, dmc.NumberInput)
    assert upper_number_input.id == slider.ids.upper_bound_input(slider.aio_id)
    assert upper_number_input.label == "Max"
    assert upper_number_input.value == 100  # default value is max
    assert upper_number_input.min == 0
    assert upper_number_input.max == 100
    assert upper_number_input.step == 10
    assert upper_number_input.decimalScale == 1
    assert upper_number_input.variant == "filled"
    assert upper_number_input.style == {"width": "15%"}
    assert upper_number_input.debounce is True
    assert upper_number_input.clampBehavior == "strict"


def test_default_step():
    """Test that default step is max(max - min, 1.0) when not provided."""
    # Case 1: range = 100, so step should be (max - min) / 10 = 10
    slider1 = DualInputRangeSlider(min=0, max=100)

    range_slider1 = slider1.children[0].children.children[1]
    assert range_slider1.step == 10.0

    lower_input1 = slider1.children[0].children.children[0]
    assert lower_input1.step == 10.0

    upper_input1 = slider1.children[0].children.children[2]
    assert upper_input1.step == 10.0

    # Case 2: range = 0.5, so step should be (max - min) / 10 = 0.05
    slider2 = DualInputRangeSlider(min=0, max=0.5)

    range_slider2 = slider2.children[0].children.children[1]
    assert range_slider2.step == 0.05

    lower_input2 = slider2.children[0].children.children[0]
    assert lower_input2.step == 0.05

    upper_input2 = slider2.children[0].children.children[2]
    assert upper_input2.step == 0.05

    # Case 3: range = 1, so step should be (max - min) / 10 = 0.1
    slider3 = DualInputRangeSlider(min=0, max=1)

    range_slider3 = slider3.children[0].children.children[1]
    assert range_slider3.step == 0.1

    lower_input3 = slider3.children[0].children.children[0]
    assert lower_input3.step == 0.1

    upper_input3 = slider3.children[0].children.children[2]
    assert upper_input3.step == 0.1


def test_dual_input_range_slider_custom_parameters():
    """Validate that custom parameters are applied to the components."""
    custom_slider = DualInputRangeSlider(
        min=0,
        max=200,
        step=5,
        decimal_scale=2,
        value=[50, 150],
        slider_props={"style": {"width": "30%"}, "minRange": 10},
        lower_bound_input_props={"label": "Lower"},
        upper_bound_input_props={"label": "Upper"},
        aio_id="custom-slider",
    )

    assert custom_slider.aio_id == "custom-slider"

    slider = custom_slider.children[0].children.children[1]
    assert slider.min == 0
    assert slider.max == 200
    assert slider.step == 5
    assert slider.value == [50, 150]
    assert slider.style == {"width": "30%"}
    assert slider.minRange == 0  # controlled prop overrides custom prop

    lower_input = custom_slider.children[0].children.children[0]
    assert lower_input.label == "Lower"
    assert lower_input.min == 0
    assert lower_input.max == 200
    assert lower_input.step == 5
    assert lower_input.decimalScale == 2
    assert lower_input.value == 50

    upper_input = custom_slider.children[0].children.children[2]
    assert upper_input.label == "Upper"
    assert upper_input.min == 0
    assert upper_input.max == 200
    assert upper_input.step == 5
    assert upper_input.decimalScale == 2
    assert upper_input.value == 150


def test_dual_input_range_slider_partial_custom_parameters():
    """Validate partially provided custom parameters are merged with defaults."""
    partial_custom_slider = DualInputRangeSlider(
        min=10,
        max=90,
        step=10,
        value=[30, 70],
        lower_bound_input_props={"style": {"width": "10%"}},
        aio_id="partial-custom-slider",
    )

    assert partial_custom_slider.aio_id == "partial-custom-slider"

    slider = partial_custom_slider.children[0].children.children[1]
    assert slider.min == 10
    assert slider.max == 90
    assert slider.step == 10
    assert slider.value == [30, 70]
    assert slider.style == {"width": "60%"}
    assert slider.minRange == 0

    lower_input = partial_custom_slider.children[0].children.children[0]
    assert lower_input.label == "Min"
    assert lower_input.min == 10
    assert lower_input.max == 90
    assert lower_input.step == 10
    assert lower_input.decimalScale == 1
    assert lower_input.value == 30
    assert lower_input.style == {"width": "10%"}

    upper_input = partial_custom_slider.children[0].children.children[2]
    assert upper_input.label == "Max"
    assert upper_input.min == 10
    assert upper_input.max == 90
    assert upper_input.step == 10
    assert upper_input.decimalScale == 1
    assert upper_input.value == 70
    assert upper_input.style == {"width": "15%"}


def test_dual_input_range_slider_contradictory_custom_values():
    """Test that controlled props win while other custom props remain intact."""
    custom_slider_with_contradictory_values = DualInputRangeSlider(
        min=10,
        max=90,
        step=5,
        decimal_scale=2,
        value=[30, 70],
        lower_bound_input_props={
            "min": 0,
            "max": 100,
            "step": 4,
            "decimalScale": 3,
            "value": 20,
            "label": "Low",
            "clampBehavior": "blur",
            "debounce": 5,
        },
        upper_bound_input_props={
            "min": 1,
            "max": 110,
            "step": 3,
            "decimalScale": 4,
            "value": 80,
            "label": "High",
            "clampBehavior": "blur",
            "debounce": 5,
        },
        slider_props={
            "min": -10,
            "max": 120,
            "step": 2,
            "value": [21, 81],
            "minRange": 15,
            "marks": {0: "Start", 100: "End"},
        },
    )

    slider = custom_slider_with_contradictory_values.children[0].children.children[1]
    assert slider.min == 10
    assert slider.max == 90
    assert slider.step == 5
    assert slider.value == [30, 70]
    assert slider.minRange == 0
    assert slider.marks == {0: "Start", 100: "End"}  # non-controlled prop remains unchanged
    assert slider.style == {"width": "60%"}  # default style remains unchanged

    lower_input = custom_slider_with_contradictory_values.children[0].children.children[0]
    assert lower_input.min == 10
    assert lower_input.max == 90
    assert lower_input.step == 5
    assert lower_input.value == 30
    assert lower_input.decimalScale == 2
    assert lower_input.debounce is True  # controlled prop is always enforced
    assert lower_input.clampBehavior == "strict"  # controlled prop is always enforced
    assert lower_input.label == "Low"  # non-controlled prop remains unchanged
    assert lower_input.style == {"width": "15%"}  # default style remains unchanged
    assert lower_input.variant == "filled"  # default variant remains unchanged

    upper_input = custom_slider_with_contradictory_values.children[0].children.children[2]
    assert upper_input.min == 10
    assert upper_input.max == 90
    assert upper_input.step == 5
    assert upper_input.value == 70
    assert upper_input.decimalScale == 2
    assert upper_input.debounce is True  # controlled prop is always enforced
    assert upper_input.clampBehavior == "strict"  # controlled prop is always enforced
    assert upper_input.label == "High"  # non-controlled prop remains unchanged
    assert upper_input.style == {"width": "15%"}  # default style remains unchanged
    assert upper_input.variant == "filled"  # default variant remains unchanged


def test_min_max_required():
    """Test that min and max parameters are required."""
    with pytest.raises(ValueError, match="Both 'min' and 'max' parameters must be provided"):
        DualInputRangeSlider(min=None, max=100)  # type: ignore

    with pytest.raises(ValueError, match="Both 'min' and 'max' parameters must be provided"):
        DualInputRangeSlider(min=0, max=None)  # type: ignore

    with pytest.raises(ValueError, match="Both 'min' and 'max' parameters must be provided"):
        DualInputRangeSlider(min=None, max=None)  # type: ignore


def test_min_max_type_validation():
    """Test that min and max must be numeric types."""
    with pytest.raises(ValueError, match="'min' parameter must be a number"):
        DualInputRangeSlider(min="0", max=100)  # type: ignore

    with pytest.raises(ValueError, match="'max' parameter must be a number"):
        DualInputRangeSlider(min=0, max="100")  # type: ignore


def test_max_greater_than_min():
    """Test that max is strictly greater than min."""
    with pytest.raises(ValueError, match="'max' parameter must be greater than 'min' parameter"):
        DualInputRangeSlider(min=100, max=0)

    with pytest.raises(ValueError, match="'max' parameter must be greater than 'min' parameter"):
        DualInputRangeSlider(min=50, max=50)


def test_step_validation():
    """Test step parameter validation rules."""
    with pytest.raises(ValueError, match="'step' parameter must be a number"):
        DualInputRangeSlider(min=0, max=100, step="5")  # type: ignore

    with pytest.raises(ValueError, match="'step' parameter must be positive"):
        DualInputRangeSlider(min=0, max=100, step=0)

    with pytest.raises(ValueError, match="'step' parameter must be positive"):
        DualInputRangeSlider(min=0, max=100, step=-5)

    with pytest.raises(
        ValueError,
        match=("'step' parameter must be less than or equal to the range defined by 'min' and 'max'"),
    ):
        DualInputRangeSlider(min=0, max=100, step=150)


def test_decimal_scale_validation():
    """Test decimal_scale parameter validation."""
    with pytest.raises(ValueError, match="'decimal_scale' parameter must be an integer"):
        DualInputRangeSlider(min=0, max=100, decimal_scale=1.5)  # type: ignore

    with pytest.raises(ValueError, match="'decimal_scale' parameter must be an integer"):
        DualInputRangeSlider(min=0, max=100, decimal_scale="1")  # type: ignore

    with pytest.raises(ValueError, match="'decimal_scale' parameter must be non-negative"):
        DualInputRangeSlider(min=0, max=100, decimal_scale=-1)


def test_value_validation():
    """Test value parameter validation rules and edge cases."""
    with pytest.raises(ValueError, match="'value' parameter must be a list of two elements"):
        DualInputRangeSlider(min=0, max=100, value=[25])  # type: ignore

    with pytest.raises(ValueError, match="'value' parameter must be a list of two elements"):
        DualInputRangeSlider(min=0, max=100, value=[25, 50, 75])  # type: ignore

    with pytest.raises(ValueError, match="'value' parameter must be a list of numbers"):
        DualInputRangeSlider(min=0, max=100, value=["25", "75"])  # type: ignore

    with pytest.raises(
        ValueError,
        match=("'value' parameter elements must each be within the range defined by 'min' and 'max'."),
    ):
        DualInputRangeSlider(min=0, max=100, value=[-10, 50])

    with pytest.raises(
        ValueError,
        match=("'value' parameter elements must each be within the range defined by 'min' and 'max'."),
    ):
        DualInputRangeSlider(min=0, max=100, value=[25, 150])

    with pytest.raises(
        ValueError,
        match=("The first element of the 'value' parameter must be less than or equal to the second element."),
    ):
        DualInputRangeSlider(min=0, max=100, value=[75, 25])


def test_default_value_computation():
    """Test that default value is [min, max] when not provided."""
    slider = DualInputRangeSlider(min=10, max=90)

    range_slider = slider.children[0].children.children[1]
    assert range_slider.value == [10, 90]

    lower_input = slider.children[0].children.children[0]
    assert lower_input.value == 10

    upper_input = slider.children[0].children.children[2]
    assert upper_input.value == 90


def test_default_decimal_scale():
    """Test that default decimal_scale is 1 when not provided."""
    slider = DualInputRangeSlider(min=0, max=100)

    lower_input = slider.children[0].children.children[0]
    assert lower_input.decimalScale == 1

    upper_input = slider.children[0].children.children[2]
    assert upper_input.decimalScale == 1


@pytest.mark.parametrize(
    (
        "trigger_id",
        "lower_bound_value",
        "upper_bound_value",
        "slider_value",
        "expected",
    ),
    [
        (
            DualInputRangeSlider.ids.lower_bound_input("test"),
            30,
            75,
            [25, 75],
            ([30, 75], no_update, 75),
        ),
        (
            DualInputRangeSlider.ids.lower_bound_input("test"),
            80,  # higher than current upper bound
            75,
            [25, 75],
            ([80, 80], no_update, 80),  # upper bound is shifted to respect minRange=0
        ),
        (
            DualInputRangeSlider.ids.lower_bound_input("test"),
            75,  # equal to current upper bound
            75,
            [25, 75],
            ([75, 75], no_update, 75),  # edge case - regular update and "shift" case are identical
        ),
        (
            DualInputRangeSlider.ids.upper_bound_input("test"),
            25,
            80,
            [25, 75],
            ([25, 80], 25, no_update),
        ),
        (
            DualInputRangeSlider.ids.upper_bound_input("test"),
            25,
            20,  # lower than current lower bound
            [25, 75],
            ([20, 20], 20, no_update),  # lower bound is shifted to respect minRange=0
        ),
        (
            DualInputRangeSlider.ids.upper_bound_input("test"),
            25,
            25,  # equal to current lower bound
            [25, 75],
            ([25, 25], 25, no_update),  # edge case - regular update and "shift" case are identical
        ),
        (
            DualInputRangeSlider.ids.slider("test"),
            25,
            75,
            [25, 80],
            (no_update, 25, 80),
        ),
        (
            DualInputRangeSlider.ids.slider("test"),
            25,
            75,
            [25, 70],
            (no_update, 25, 70),
        ),
        (
            DualInputRangeSlider.ids.slider("test"),
            25,
            75,
            [20, 75],
            (no_update, 20, 75),
        ),
        # String inputs (debounce=True can deliver values as str)
        (
            DualInputRangeSlider.ids.lower_bound_input("test"),
            "30",  # valid numeric string
            75,
            [25, 75],
            ([30.0, 75], no_update, 75),
        ),
        (
            DualInputRangeSlider.ids.upper_bound_input("test"),
            25,
            "80",  # valid numeric string
            [25, 75],
            ([25, 80.0], 25, no_update),
        ),
        # Invalid (non-parseable) string inputs — e.g. user cleared the field
        (
            DualInputRangeSlider.ids.lower_bound_input("test"),
            "",  # empty string: float("") raises ValueError, fall back to slider_value[0]
            75,
            [25, 75],
            ([25, 75], 25, 75),  # lower bound reset to current slider[0], upper bound unchanged
        ),
        (
            DualInputRangeSlider.ids.upper_bound_input("test"),
            25,
            "",  # empty string: float("") raises ValueError, fall back to slider_value[1]
            [25, 75],
            ([25, 75], 25, 75),  # upper bound reset to current slider[1], lower bound unchanged
        ),
        (
            DualInputRangeSlider.ids.lower_bound_input("test"),
            None,  # None: float(None) raises TypeError, fall back to slider_value[0]
            75,
            [25, 75],
            ([25, 75], 25, 75),  # lower bound reset to current slider[0], upper bound unchanged
        ),
        (
            DualInputRangeSlider.ids.upper_bound_input("test"),
            25,
            None,  # None: float(None) raises TypeError, fall back to slider_value[1]
            [25, 75],
            ([25, 75], 25, 75),  # upper bound reset to current slider[1], lower bound unchanged
        ),
    ],
)
def test_update_slider_or_inputs_values_success(
    callback_context_mock: mock.MagicMock,
    trigger_id: dict[str, str],
    lower_bound_value: float | str,
    upper_bound_value: float | str,
    slider_value: list[float],
    expected: tuple[list[float] | NoUpdate, float | NoUpdate, float | NoUpdate],
):
    """Parametrized test for value updates triggered by slider or inputs."""
    slider_id_input = DualInputRangeSlider.ids.slider("test")
    lower_bound_id_input = DualInputRangeSlider.ids.lower_bound_input("test")
    upper_bound_id_input = DualInputRangeSlider.ids.upper_bound_input("test")
    callback_context_mock.triggered_id = trigger_id

    new_values = DualInputRangeSlider.update_slider_or_inputs_values(
        slider_value,
        lower_bound_value,
        upper_bound_value,
        slider_id_input,
        lower_bound_id_input,
        upper_bound_id_input,
    )
    assert new_values == expected


def test_update_slider_or_inputs_values_unknown_trigger(callback_context_mock: mock.MagicMock):
    """Ensure unknown triggers raise PreventUpdate."""
    slider_id_input = DualInputRangeSlider.ids.slider("test")
    lower_bound_id_input = DualInputRangeSlider.ids.lower_bound_input("test")
    upper_bound_id_input = DualInputRangeSlider.ids.upper_bound_input("test")
    slider_value_base = [25, 75]
    lower_bound_value_base = 25
    upper_bound_value_base = 75

    # Test unknown trigger
    callback_context_mock.triggered_id = {
        "component": "Unknown",
        "subcomponent": "unknown",
        "aio_id": "test",
    }
    with pytest.raises(PreventUpdate):
        DualInputRangeSlider.update_slider_or_inputs_values(
            slider_value_base,  # type: ignore
            lower_bound_value_base,
            upper_bound_value_base,
            slider_id_input,
            lower_bound_id_input,
            upper_bound_id_input,
        )


def test_update_slider_or_inputs_values_no_trigger(callback_context_mock: mock.MagicMock):
    """Ensure lack of trigger raises PreventUpdate."""
    slider_id_input = DualInputRangeSlider.ids.slider("test")
    lower_bound_id_input = DualInputRangeSlider.ids.lower_bound_input("test")
    upper_bound_id_input = DualInputRangeSlider.ids.upper_bound_input("test")
    slider_value_base = [25, 75]
    lower_bound_value_base = 25
    upper_bound_value_base = 75

    # Test no trigger
    callback_context_mock.triggered_id = None
    with pytest.raises(PreventUpdate):
        DualInputRangeSlider.update_slider_or_inputs_values(
            slider_value_base,  # type: ignore
            lower_bound_value_base,
            upper_bound_value_base,
            slider_id_input,
            lower_bound_id_input,
            upper_bound_id_input,
        )
