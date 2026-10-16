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

"""Shared input validation for the pump frozen-rotor transactions."""


def validate_range(name: str, value: float, bounds: tuple[float, float]) -> None:
    """Raise if ``value`` falls outside ``bounds``.

    Parameters
    ----------
    name : str
        Field name, used in the error message.
    value : float
        Value to check.
    bounds : tuple[float, float]
        Inclusive ``(lower, upper)`` bounds.

    Raises
    ------
    ValueError
        If ``value`` is outside the inclusive bounds.
    """
    lower, upper = bounds
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}, got {value}.")
