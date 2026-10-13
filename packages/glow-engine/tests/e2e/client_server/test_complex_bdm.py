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

import pytest

from ansys.bdm.api import EntityHandle, RecursiveDictionaryOfEntityHandles
from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solutions.complex_bdm import ComplexBdmSolution, MyFile, MyOther

pytestmark = pytest.mark.parametrize("solution_type", [ComplexBdmSolution], indirect=True)


def _check_file(i: int, handle: EntityHandle | RecursiveDictionaryOfEntityHandles, project: ComplexBdmSolution) -> None:
    assert isinstance(handle, EntityHandle)
    content = project.storage_scope.get_cached(handle).read_text()
    assert content == str(i)


def test_entity_handles_can_be_stored_within_the_models_in_a_list_of_models(
    function_project: ProjectFixture[ComplexBdmSolution],
):
    """
    Test that entity handles can be stored within the models in a list of models
    specifically ensuring that the entities are not garbage collected prematurely.
    """
    project = function_project.project
    step = project.steps.bdm_step

    step.generate_files().wait(60)

    assert step.get_method_state("generate_files").status == MethodStatus.Completed
    assert len(step.files) == 10
    for i, my_file in enumerate(step.files):
        _check_file(i, my_file.fh, project)
        _check_file(i, my_file.fh_pair[0], project)
        _check_file(i, my_file.fh_pair[1], project)

        if my_file.fh_nullable is None:
            assert i % 2 == 1
        else:
            _check_file(i, my_file.fh_nullable, project)
            assert i % 2 == 0

    for i, entry in enumerate(step.files_union):
        if i % 2 == 0:
            assert isinstance(entry, MyFile)
            _check_file(i, entry.fh, project)
        else:
            assert isinstance(entry, MyOther)
            assert entry.name == str(i)

    assert len(step.files_set) == 10
    for i in range(10):
        assert (
            sum(1 for handle in step.files_set if project.storage_scope.get_cached(handle).read_text() == str(i)) == 1
        )

    _check_file(0, step.recursive_dictionary["top"], project)
    nested = step.recursive_dictionary["nested"]
    assert isinstance(nested, dict)
    _check_file(1, nested["nested"], project)
