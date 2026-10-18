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

import pytest

from saf.solutions.pump.solution.logic.validation import validate_range


def test_validate_range_accepts_value_inside_bounds():
    validate_range("impeller_speed_rpm", 1450.0, (100.0, 3000.0))


def test_validate_range_accepts_values_on_the_bounds():
    validate_range("impeller_speed_rpm", 100.0, (100.0, 3000.0))
    validate_range("impeller_speed_rpm", 3000.0, (100.0, 3000.0))


def test_validate_range_rejects_value_below_lower_bound():
    with pytest.raises(ValueError, match="impeller_speed_rpm must be between 100.0 and 3000.0, got 99.0"):
        validate_range("impeller_speed_rpm", 99.0, (100.0, 3000.0))


def test_validate_range_rejects_value_above_upper_bound():
    with pytest.raises(ValueError, match="must be between"):
        validate_range("iteration_count", 5001, (1, 5000))
