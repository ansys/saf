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

from collections.abc import Generator

import pytest
from tenacity import TryAgain, retry, stop_after_attempt, stop_after_delay, wait_fixed

from ansys.bdm.api import NO_ENTITY
from ansys.saf.testing.solution.end_to_end import EnvVarDebugLogLevel, GlowBaseProcess, ProjectFixture
from tests.mocks.solutions.bdm_recursive_solution import BdmSolution, RecursiveThing

pytestmark = pytest.mark.parametrize("solution_type", [BdmSolution], indirect=True)


@retry(stop=stop_after_delay(10), wait=wait_fixed(0.1))
def assert_bdm_locks_count(session_glow: GlowBaseProcess[BdmSolution], expected_count: int):
    added_locks = len([line for line in session_glow.api_output if "Adding BDM lock" in line])
    removed_locks = len([line for line in session_glow.api_output if "Removing BDM lock" in line])
    if added_locks != expected_count or removed_locks != expected_count:
        raise TryAgain
    assert added_locks == expected_count
    assert removed_locks == expected_count


@retry(
    stop=stop_after_attempt(20),
    wait=wait_fixed(0.1),
)
def wait_for_gc_contains_file(
    function_project: ProjectFixture[BdmSolution],
    filename: str,
    count: int,
) -> bool:
    if len(list(function_project.project_files_dir.rglob(filename))) != count:
        raise TryAgain
    return True


@retry(
    stop=stop_after_attempt(20),
    wait=wait_fixed(0.1),
)
def wait_for_gc_cleaning_all_files(function_project: ProjectFixture[BdmSolution]) -> bool:
    # gc is not immediate since it is a background task
    if len([file for file in function_project.project_files_dir.rglob("*") if file.is_file()]) != 0:
        raise TryAgain
    return True


@pytest.fixture(scope="module", autouse=True)
def set_logging_level_to_debug(session_glow: GlowBaseProcess[BdmSolution]) -> Generator[None, None, None]:
    session_glow.change_configuration(EnvVarDebugLogLevel)
    yield
    session_glow.configure_default_execution()


def test_transaction_with_entity_handles_in_step_spec_upload_or_download(
    function_project: ProjectFixture[BdmSolution],
    session_glow: GlowBaseProcess[BdmSolution],
):
    """Test that if a transaction method uploads or downloads entity handles as specified in the step spec,
    BDM locks are created for the duration of the transaction.
    """
    session_glow.clear_output()
    function_project.project.steps.bdm_step.upload_recursive_thing()
    assert_bdm_locks_count(session_glow, 2)  # upload, so 2 locks (1 for transaction, 1 for upload)

    session_glow.clear_output()
    function_project.project.steps.bdm_step.download_child_from_recursive_thing()
    assert_bdm_locks_count(session_glow, 1)  # no upload, so only 1 lock for the transaction


def test_bdm_gc_store_entity_handle_recursive_model_assign_empty_cleans_files(
    function_project: ProjectFixture[BdmSolution],
):
    """
    Test that assigning NO_ENTITY to child entity handles within recursive model,
    makes the garbage collection clearing all files referenced by the entity handles.
    """
    step = function_project.project.steps.bdm_step
    # WHEN: running a transaction storing a recursive model containing entity handles
    step.upload_recursive_thing()
    assert wait_for_gc_contains_file(function_project, "parent.txt", 1)
    assert wait_for_gc_contains_file(function_project, "child.txt", 1)
    # WHEN: a child entity handle is set to NO_ENTITY
    modified_child = step.recursive_thing
    modified_child.children[0].handle = NO_ENTITY
    step.recursive_thing = modified_child
    # THEN: garbage collection should remove initial file
    assert wait_for_gc_contains_file(function_project, "parent.txt", 1)
    assert wait_for_gc_contains_file(function_project, "child.txt", 0)
    # WHEN: the recursive model is reset
    step.recursive_thing = RecursiveThing()
    # THEN: garbage collection should remove all files
    assert wait_for_gc_cleaning_all_files(function_project)
