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

import time

import pytest

from ansys.bdm.api import NO_ENTITY
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solutions.bdm_benchmark import BdmBenchmarkSolution

pytestmark = pytest.mark.parametrize("solution_type", [BdmBenchmarkSolution], indirect=True)

CHUNK_SIZE = 100
NUMBER_OF_CHUNKS = 10
ITERATIONS = 10


def test_can_initialiatize_and_update_list_of_handles(function_project: ProjectFixture[BdmBenchmarkSolution]):
    step = function_project.project.steps.bdm_step
    assert len(step.list_handles) == 0

    step.initialize_list_handles(size=10)
    assert len(step.list_handles) == 10
    assert all(handle == NO_ENTITY for handle in step.list_handles)

    content: list[str | None] = [None] * 10
    step.modify_list_handles(start=2, end=7)
    assert len(step.list_handles) == 10
    storage_scope = function_project.project.storage_scope
    list_handles = step.list_handles
    for i in range(2):
        assert list_handles[i] == NO_ENTITY
    for i in range(2, 7):
        assert list_handles[i] != NO_ENTITY
        content[i] = storage_scope.get_text(list_handles[i])
    for i in range(7, 10):
        assert list_handles[i] == NO_ENTITY

    step.modify_list_handles(start=6, end=9)
    assert len(step.list_handles) == 10
    storage_scope = function_project.project.storage_scope
    list_handles = step.list_handles
    for i in range(2):
        assert list_handles[i] == NO_ENTITY
    for i in range(2, 6):
        assert list_handles[i] != NO_ENTITY
        assert content[i] == storage_scope.get_text(list_handles[i])
    for i in range(6, 9):
        assert list_handles[i] != NO_ENTITY
    assert list_handles[9] == NO_ENTITY


@pytest.mark.skip(reason="this is a benchmark and not a test for determining correctness")
def test_benchmark_gc(function_project: ProjectFixture[BdmBenchmarkSolution]):
    step = function_project.project.steps.bdm_step
    step.initialize_list_handles(size=CHUNK_SIZE * NUMBER_OF_CHUNKS)

    start_time = time.time()
    for _ in range(ITERATIONS):
        for chunk in range(NUMBER_OF_CHUNKS):
            start = chunk * CHUNK_SIZE
            end = start + CHUNK_SIZE
            step.modify_list_handles(start=start, end=end)
    end_time = time.time()
    elapsed_time = end_time - start_time
    assert elapsed_time < 1
