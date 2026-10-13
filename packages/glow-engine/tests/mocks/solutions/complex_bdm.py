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

from pydantic import BaseModel

from ansys.bdm.api import RecursiveDictionaryOfEntityHandles
from ansys.saf.glow.solution import (
    NO_ENTITY,
    EntityHandle,
    Solution,
    StepModel,
    StepsModel,
    StepSpec,
    long_running,
    transaction,
)


class MyFile(BaseModel):
    fh: EntityHandle = NO_ENTITY
    fh_nullable: EntityHandle | None = None
    fh_pair: tuple[EntityHandle, EntityHandle] = (NO_ENTITY, NO_ENTITY)


class MyOther(BaseModel):
    name: str = ""


class BdmStep(StepModel):
    files: list[MyFile] = []

    files_union: list[MyFile | MyOther] = []

    files_set: set[EntityHandle] = set()

    recursive_dictionary: RecursiveDictionaryOfEntityHandles = RecursiveDictionaryOfEntityHandles()

    def _create_file(self, index: int, name_format: str) -> EntityHandle:
        file_path = self.storage_scope.get_storage_root() / name_format.format(index=index)
        file_path.write_text(str(index))
        handle = self.storage_scope.store(file_path)
        return handle

    @transaction(
        self=StepSpec(
            upload=["files", "files_union", "files_set", "recursive_dictionary"],
            download=["files"],
        ),
    )
    @long_running
    def generate_files(self) -> None:
        """Generate files and store them in BDM."""
        files = self.files
        initial_length = len(files)
        files_union: list[MyFile | MyOther] = []
        files_set: set[EntityHandle] = set()

        for i in range(10):
            index = initial_length + i
            files.append(
                MyFile(
                    fh=self._create_file(index, "file_{index}.txt"),
                    fh_nullable=self._create_file(index, "nullable_file_{index}.txt") if i % 2 == 0 else None,
                    fh_pair=(
                        self._create_file(index, "left_file_{index}.txt"),
                        self._create_file(index, "right_file_{index}.txt"),
                    ),
                ),
            )

            if i % 2 == 0:
                entry = MyFile(fh=self._create_file(index, "union_file_{index}.txt"))
            else:
                entry = MyOther(name=str(i))
            files_union.append(entry)

            files_set.add(self._create_file(index, "set_file_{index}.txt"))

        recursive_dictionary = RecursiveDictionaryOfEntityHandles()
        recursive_dictionary["top"] = self._create_file(0, "recursive_top.txt")
        nested_dict = RecursiveDictionaryOfEntityHandles()
        nested_dict["nested"] = self._create_file(1, "recursive_nested.txt")
        recursive_dictionary["nested"] = nested_dict

        self.files = files
        self.files_union = files_union
        self.files_set = files_set
        self.recursive_dictionary = recursive_dictionary


class TheseSteps(StepsModel):
    bdm_step: BdmStep


class ComplexBdmSolution(Solution):
    display_name: str = "Bdm Solution"
    steps: TheseSteps
