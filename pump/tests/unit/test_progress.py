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

from saf.solutions.pump.solution.logic.constants import SETUP_STAGES, SOLVE_STAGES
from saf.solutions.pump.solution.logic.progress import stage_label


def test_stage_label_returns_first_stage_at_zero():
    assert stage_label(SETUP_STAGES, 0.0) == "Launching Fluent"


def test_stage_label_returns_the_stage_whose_threshold_was_last_crossed():
    # 0.35 "Rendering mesh" and 0.55 "Configuring model" are adjacent, so straddling 0.55 proves the
    # label tracks the last threshold crossed rather than the nearest one.
    assert stage_label(SETUP_STAGES, 0.50) == "Rendering mesh"
    assert stage_label(SETUP_STAGES, 0.55) == "Configuring model"
    assert stage_label(SETUP_STAGES, 0.60) == "Configuring model"


def test_stage_label_returns_last_stage_at_one():
    assert stage_label(SOLVE_STAGES, 1.0) == "Saving results"


def test_stage_label_clamps_negative_fraction_to_first_stage():
    assert stage_label(SOLVE_STAGES, -0.5) == "Launching Fluent"
