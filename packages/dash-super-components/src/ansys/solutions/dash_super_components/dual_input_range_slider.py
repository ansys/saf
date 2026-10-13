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


"""Provides a Dash component combining a range slider with number inputs for upper/lower limits."""

import copy
from typing import Any
import uuid

try:
    # dash >=3.2.0
    from dash import NoUpdate
except ImportError:
    # dash >=2.18.2, <3.2.0
    from dash._callback import NoUpdate  # pyright: ignore[reportPrivateImportUsage]
from dash.exceptions import PreventUpdate

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )
from dash_extensions.enrich import (
    MATCH,
    Input,
    Output,
    State,
    callback,
    callback_context,
    html,
    no_update,
)
import dash_mantine_components as dmc

from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds


class DualInputRangeSlider(html.Div):
    """
    A Dash component combining a range slider with two number inputs for precise range control.

    DualInputRangeSlider is based on the Dash All-in-One (AIO) component pattern. It provides
    a bidirectional interface: dragging the slider updates both number inputs, and typing into
    either input updates the slider. When a new lower bound would exceed the current upper
    bound (or vice versa), the other bound is automatically adjusted to maintain validity.

    Parameters
    ----------
    min : int or float
        The minimum value of the slider.
    max : int or float
        The maximum value of the slider. Must be greater than ``min``.
    step : int or float, optional
        Step size for the slider and number inputs. Must be positive and
        ``<= (max - min)``. Default is ``(max - min) / 10.0``.
    decimal_scale : int, optional
        Number of decimal places displayed in the number inputs. Must be
        non-negative. Default is ``1``.
    value : list of float, optional
        Initial ``[lower, upper]`` values. Both must lie in ``[min, max]`` with
        ``lower <= upper``. Defaults to ``[min, max]``.
    slider_props : dict, optional
        Additional properties forwarded to :class:`dmc.RangeSlider`. The keys
        ``min``, ``max``, ``step``, ``value``, and ``minRange`` are controlled by
        the component and will be overridden. Default style: ``{"width": "20%"}``.
    lower_bound_input_props : dict, optional
        Additional properties forwarded to the lower bound :class:`dmc.NumberInput`.
        The keys ``min``, ``max``, ``step``, ``value``, ``decimalScale``, ``debounce``,
        and ``clampBehavior`` are controlled by the component and will be overridden.
        Default: label ``"Min"``, variant ``"filled"``, style ``{"width": "15%"}``.
    upper_bound_input_props : dict, optional
        Additional properties forwarded to the upper bound :class:`dmc.NumberInput`.
        The keys ``min``, ``max``, ``step``, ``value``, ``decimalScale``, ``debounce``,
        and ``clampBehavior`` are controlled by the component and will be overridden.
        Default: label ``"Max"``, variant ``"filled"``, style ``{"width": "15%"}``.
    aio_id : str, optional
        Unique identifier for this component instance. A UUID is generated when
        not provided.
    """

    class DualInputRangeSliderIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`DualInputRangeSlider`."""

        @classmethod
        def slider(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the slider component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the slider subcomponent.
            """
            return cls.make_id_dict("dual-input-range-slider", "slider", aio_id)

        @classmethod
        def lower_bound_input(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the lower bound input component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the lower bound input subcomponent.
            """
            return cls.make_id_dict("dual-input-range-slider", "lower-bound-input", aio_id)

        @classmethod
        def upper_bound_input(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the upper bound input component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the upper bound input subcomponent.
            """
            return cls.make_id_dict("dual-input-range-slider", "upper-bound-input", aio_id)

    ids = DualInputRangeSliderIds

    def __init__(
        self,
        min: float,  # noqa: A002 - min is the conventional name for this parameter in DMC
        max: float,  # noqa: A002 - max is the conventional name for this parameter in DMC
        step: float | None = None,
        decimal_scale: int | None = None,
        value: list[float] | None = None,
        slider_props: dict[str, Any] | None = None,
        lower_bound_input_props: dict[str, Any] | None = None,
        upper_bound_input_props: dict[str, Any] | None = None,
        aio_id: str | None = None,
    ):
        # First, check if the mandatory inputs min and max are valid as the defaults calculation
        # is based on them
        self._check_mandatory_inputs(min, max)

        # Set default values for the optional inputs if not given
        if slider_props is None:
            slider_props = {}
        if lower_bound_input_props is None:
            lower_bound_input_props = {}
        if upper_bound_input_props is None:
            upper_bound_input_props = {}
        if aio_id is None:
            aio_id = str(uuid.uuid4())
        if value is None:
            value = [min, max]
        if decimal_scale is None:
            decimal_scale = 1
        if step is None:
            step = (max - min) / 10.0

        # check if the optional inputs and defaults are valid
        self._check_optional_inputs_and_defaults(
            checked_min=min,
            checked_max=max,
            step=step,
            decimal_scale=decimal_scale,
            value=value,
        )

        self._slider_props = copy.deepcopy(slider_props)
        self._lower_bound_input_props = copy.deepcopy(lower_bound_input_props)
        self._upper_bound_input_props = copy.deepcopy(upper_bound_input_props)
        self._min = min
        self._max = max
        self._step = step
        self._value = value
        self._decimal_scale = decimal_scale
        self.aio_id = aio_id

        default_slider_props: dict[str, Any] = {
            "style": {"width": "60%"},
        }

        controlled_slider_props: dict[str, Any] = {
            "value": self._value,
            "min": self._min,
            "max": self._max,
            "step": self._step,
            "minRange": 0,  # Ensure that lower bound<=upper bound, overwrite dmc default behavior
        }
        self._populate_with_defaults(self._slider_props, default_slider_props)
        self._enforce_controlled_props(self._slider_props, controlled_slider_props)

        default_lower_bound_input_props: dict[str, Any] = {
            "label": "Min",
            "variant": "filled",
            "style": {"width": "15%"},
        }

        controlled_lower_bound_input_props: dict[str, Any] = {
            "value": self._value[0],
            "min": self._min,
            "max": self._max,
            "step": self._step,
            "decimalScale": self._decimal_scale,
            "debounce": True,  # Avoids unnecessary callback calls while typing
            "clampBehavior": "strict",  # Prevents user from entering values outside of [min, max]
        }
        self._populate_with_defaults(self._lower_bound_input_props, default_lower_bound_input_props)
        self._enforce_controlled_props(self._lower_bound_input_props, controlled_lower_bound_input_props)

        default_upper_bound_input_props: dict[str, Any] = {
            "label": "Max",
            "variant": "filled",
            "style": {"width": "15%"},
        }

        controlled_upper_bound_input_props: dict[str, Any] = {
            "value": self._value[1],
            "min": self._min,
            "max": self._max,
            "step": self._step,
            "decimalScale": self._decimal_scale,
            "debounce": True,  # Avoids unnecessary callback calls while typing
            "clampBehavior": "strict",  # Prevents user from entering values outside of [min, max]
        }
        self._populate_with_defaults(self._upper_bound_input_props, default_upper_bound_input_props)
        self._enforce_controlled_props(self._upper_bound_input_props, controlled_upper_bound_input_props)

        super().__init__(
            [
                html.Div(
                    dmc.Group(
                        [
                            dmc.NumberInput(
                                id=self.ids.lower_bound_input(self.aio_id),
                                **self._lower_bound_input_props,
                            ),
                            dmc.RangeSlider(
                                id=self.ids.slider(self.aio_id),
                                **self._slider_props,
                            ),
                            dmc.NumberInput(
                                id=self.ids.upper_bound_input(self.aio_id),
                                **self._upper_bound_input_props,
                            ),
                        ],
                        justify="center",
                        gap="xs",
                    ),
                ),
            ],
        )

    def _check_mandatory_inputs(
        self,
        input_min: float,
        input_max: float,
    ) -> None:
        if input_max is None or input_min is None:  # type: ignore - deliberately checking input value types
            raise ValueError("Both 'min' and 'max' parameters must be provided.")

        if not isinstance(input_min, int | float):  # type: ignore - deliberately checking input value types
            raise ValueError("'min' parameter must be a number.")

        if not isinstance(input_max, int | float):  # type: ignore - deliberately checking input value types
            raise ValueError("'max' parameter must be a number.")

        if input_max <= input_min:
            raise ValueError("'max' parameter must be greater than 'min' parameter.")

    def _check_optional_inputs_and_defaults(
        self,
        checked_min: float,
        checked_max: float,
        step: float,
        decimal_scale: int,
        value: list[int | float],
    ) -> None:
        self._check_step(checked_min, checked_max, step)
        self._check_decimal_scale(decimal_scale)
        self._check_value(checked_min, checked_max, value)

    def _check_step(self, checked_min: float, checked_max: float, step: float) -> None:
        if not isinstance(step, int | float):  # type: ignore - deliberately checking input value types
            raise ValueError("'step' parameter must be a number.")
        if step <= 0:
            raise ValueError("'step' parameter must be positive.")
        if step > (checked_max - checked_min):
            raise ValueError("'step' parameter must be less than or equal to the range defined by 'min' and 'max'.")

    def _check_decimal_scale(self, decimal_scale: int) -> None:
        if not isinstance(decimal_scale, int):  # type: ignore - checking inputs
            raise ValueError("'decimal_scale' parameter must be an integer.")
        if decimal_scale < 0:
            raise ValueError("'decimal_scale' parameter must be non-negative.")

    def _check_value(self, checked_min: float, checked_max: float, value: list[int | float]) -> None:
        if len(value) != 2:
            raise ValueError("'value' parameter must be a list of two elements.")
        if not all(isinstance(v, int | float) for v in value):  # type: ignore - checking inputs
            raise ValueError("'value' parameter must be a list of numbers.")
        if not (checked_min <= value[0] <= checked_max) or not (checked_min <= value[1] <= checked_max):
            raise ValueError(
                "'value' parameter elements must each be within the range defined by 'min' and 'max'.",
            )
        if value[0] > value[1]:
            raise ValueError(
                "The first element of the 'value' parameter must be less than or equal to the second element."
            )

    def _populate_with_defaults(self, properties: dict[str, Any], default_properties: dict[str, Any]) -> None:
        for key, val in default_properties.items():
            if key not in properties:
                properties[key] = val

    def _enforce_controlled_props(self, properties: dict[str, Any], controlled_properties: dict[str, Any]) -> None:
        for key, val in controlled_properties.items():
            properties[key] = val

    @staticmethod
    @callback(
        Output(ids.slider(MATCH), "value"),
        Output(ids.lower_bound_input(MATCH), "value"),
        Output(ids.upper_bound_input(MATCH), "value"),
        Input(ids.slider(MATCH), "value"),
        Input(ids.lower_bound_input(MATCH), "value"),
        Input(ids.upper_bound_input(MATCH), "value"),
        State(ids.slider(MATCH), "id"),
        State(ids.lower_bound_input(MATCH), "id"),
        State(ids.upper_bound_input(MATCH), "id"),
    )
    def update_slider_or_inputs_values(
        slider_value: list[float | int],
        lower_bound_value: float | str,
        upper_bound_value: float | str,
        slider_id: dict[str, Any],
        lower_bound_id: dict[str, Any],
        upper_bound_id: dict[str, Any],
    ) -> tuple[list[float] | NoUpdate, float | NoUpdate, float | NoUpdate]:
        """Update slider or inputs values."""
        ctx = callback_context
        if not ctx.triggered_id:  # type: ignore - Dash typing issue
            raise PreventUpdate

        trigger_id: dict[str, Any] = ctx.triggered_id  # type: ignore - Dash typing issue
        if trigger_id == slider_id:
            return no_update, slider_value[0], slider_value[1]
        elif trigger_id == lower_bound_id:
            # make sure that minRange=0 is respected (i.e., lower bound <= upper bound)
            # if not respected, shift upper bound (comparable to RangeSlider behavior)
            lower_bound_value_update = no_update
            try:
                lower_bound_value = float(lower_bound_value)
            except (ValueError, TypeError):
                lower_bound_value = slider_value[0]
                lower_bound_value_update = slider_value[0]
            valid_upper_bound_value = max(lower_bound_value, slider_value[1])
            return (
                [lower_bound_value, valid_upper_bound_value],
                lower_bound_value_update,
                valid_upper_bound_value,
            )
        elif trigger_id == upper_bound_id:
            # make sure that minRange=0 is respected (i.e., lower bound <= upper bound)
            # if not respected, shift lower bound (comparable to RangeSlider behavior)
            upper_bound_value_update = no_update
            try:
                upper_bound_value = float(upper_bound_value)
            except (ValueError, TypeError):
                upper_bound_value = slider_value[1]
                upper_bound_value_update = slider_value[1]
            valid_lower_bound_value = min(upper_bound_value, slider_value[0])
            return (
                [valid_lower_bound_value, upper_bound_value],
                valid_lower_bound_value,
                upper_bound_value_update,
            )
        else:
            raise PreventUpdate
