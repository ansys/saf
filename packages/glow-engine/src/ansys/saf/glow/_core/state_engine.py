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

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._core.field_state import FieldState

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ansys.saf.glow._core.dag import DependencyGraph
    from ansys.saf.glow._core.solution import Solution

logger = logging.getLogger(__name__)


def initialize_states(solution: Solution):
    """Initialize the state of all fields for all the steps. The rules
    are the following:

    - standard fields are UPTODATE by default.
    - fields with upstream dependencies are OUTOFDATE by default.
    - EntityHandle fields are OUTOFDATE by default.
    """
    for step_name, step in solution.get_steps_fields().items():
        step = getattr(solution.get_steps(), step_name)
        fields = [key for key in step.model_dump() if key != "state"]
        for field_name in fields:
            if solution.dag.has_ancestors(step_name, field_name) or type(getattr(step, field_name)) in [
                EntityHandle,
            ]:
                step.state[field_name] = FieldState.OUTOFDATE
            else:
                step.state[field_name] = FieldState.UPTODATE


def compute_downstream_steps(
    steps: Mapping[str, (dict[str, str] | list[str])],
    dag: DependencyGraph,
) -> list[tuple[str, str]]:
    """compute the set of steps and fields that are invalidated by the give steps"""
    invalidated: dict[str, set[str]] = {}
    nodes = dag.toplogical_sort()

    for step_name, fields in steps.items():
        fields = fields.keys() if isinstance(fields, dict) else fields
        for field_name in fields:
            if (step_name, field_name) in nodes:
                for descendant_step_name, descendant_field_name in dag.descendants(step_name, field_name):
                    if not (descendant_step_name in steps and descendant_field_name in steps[step_name]):
                        if descendant_step_name not in invalidated:
                            invalidated[descendant_step_name] = set()
                        invalidated[descendant_step_name].add(descendant_field_name)

    return [(step_name, field_name) for step_name, fields in invalidated.items() for field_name in fields]
