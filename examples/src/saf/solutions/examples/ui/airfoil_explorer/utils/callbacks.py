# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Reusable callback factory functions for common UI patterns."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dash_extensions.enrich import no_update


def create_button_disable_callbacks(
    _button_id: str,
    _completion_output_id: str,
) -> tuple[Callable[..., bool | type[no_update]], Callable[..., bool | type[no_update]]]:
    """Create a pair of callbacks for button disable/enable pattern.

    This factory returns two callback functions:
    1. Disable button immediately on click
    2. Re-enable button when transaction completes (figure updates and loading stops)

    Args:
        _button_id: The ID of the button component (for documentation only).
        _completion_output_id: The ID of the output component that signals completion
                               (for documentation only).

    Returns:
        Tuple of (disable_on_click_callback, re_enable_on_completion_callback).

        Both callbacks must be decorated with @callback before use:
        - Disable callback: Outputs to `{button_id}.disabled`, inputs from `n_clicks` and `disabled` state.
        - Re-enable callback: Outputs to `{button_id}.disabled`, inputs from `{completion_output_id}.figure` or
          `{completion_output_id}.src` and `{completion_output_id}.loading_state`.

    Example:
        >>> disable_cb, enable_cb = create_button_disable_callbacks(
        ...     "generate-button", "result-figure"
        ... )
        >>>
        >>> @callback(
        ...     Output("generate-button", "disabled"),
        ...     Input("generate-button", "n_clicks"),
        ...     State("generate-button", "disabled"),
        ...     prevent_initial_call=True,
        ... )
        >>> def disable_on_click(n_clicks, currently_disabled):
        ...     return disable_cb(n_clicks, currently_disabled)
    """

    def disable_on_click(n_clicks: int | None, currently_disabled: bool) -> bool | type[no_update]:
        """Disable the button immediately when clicked."""
        if n_clicks and not currently_disabled:
            return True
        return no_update

    def re_enable_on_completion(
        _completion_value: dict[str, Any] | str | None,
        loading_state: dict[str, Any] | None,
        currently_disabled: bool,
    ) -> bool | type[no_update]:
        """Re-enable the button when the transaction completes.

        Args:
            _completion_value: The completion signal value (figure dict or image src string).
            loading_state: Loading state from the component.
            currently_disabled: Current disabled state of the button.
        """
        if currently_disabled:
            if loading_state and loading_state.get("is_loading"):
                return True
            return False
        return no_update

    return disable_on_click, re_enable_on_completion
