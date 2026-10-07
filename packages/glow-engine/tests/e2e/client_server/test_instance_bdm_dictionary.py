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

from pathlib import Path

import pytest

from ansys.saf.glow.solution import EntityHandle, RecursiveDictionaryOfEntityHandles
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solutions.bdm_dictionaries import BdmDictionariesSolution

pytestmark = pytest.mark.parametrize("solution_type", [BdmDictionariesSolution], indirect=True)


@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
class TestInstanceBdmDictionaries:
    def _verify_paths_copied(self, paths: list[Path], only_txt: bool = False) -> None:
        if only_txt:
            assert [Path("root_file.txt")] == paths
        else:
            assert sorted([Path("root_file.txt"), Path("subdir1"), Path("subdir1/level1_file.json")]) == sorted(paths)

    def _verify_entities_dict(self, entities_dict: RecursiveDictionaryOfEntityHandles, only_txt: bool = False) -> None:
        assert isinstance(entities_dict, dict)
        assert isinstance(entities_dict["root_file.txt"], EntityHandle)
        if only_txt:
            assert "subdir1" not in entities_dict
        else:
            subdir1 = entities_dict["subdir1"]
            assert isinstance(subdir1, dict)
            assert isinstance(subdir1["level1_file.json"], EntityHandle)

    def test_bdm_store_to_dict_and_get_copy_in_product_storage_scope(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
    ):
        """Test that RecursiveDictionaryOfEntityHandles can be used with product storage scopes to upload
        and download directories between the product instance filesystem and the transaction/client.
        """
        step = function_project.project.steps.bdm_dicts_step
        step.launch_product()

        # create in transaction and copy to product
        step.upload_directory_to_entities_dict()
        paths = step.download_directory_into_product_space()
        self._verify_paths_copied(paths)

        # create in product and copy to client
        step.my_entities = RecursiveDictionaryOfEntityHandles()
        step.upload_directory_from_product_space()
        self._verify_entities_dict(step.my_entities)
        output_dir = function_project.project.storage_scope.get_storage_root() / "output_product"
        function_project.project.storage_scope.get_copy_from_dictionary(output_dir, step.my_entities)
        self._verify_paths_copied([path.relative_to(output_dir) for path in output_dir.rglob("*")])

        step.shutdown_product()

    def test_bdm_build_dictionary_from_multiple_systems_and_get_copy_in_any_of_them(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
    ):
        """Test that a RecursiveDictionaryOfEntityHandles can contain entity handles from multiple storage systems
        (transaction, client, product) and files from all systems can be downloaded together then in any of those
        scopes.
        """
        step = function_project.project.steps.bdm_dicts_step

        # initialize entities dict with files from first system (transaction)
        step.upload_directory_to_entities_dict()

        # extend entities dict with files from another system (client)
        extra_file = function_project.project.storage_scope.get_storage_root() / "input" / "client_system_file.txt"
        extra_file.parent.mkdir()
        extra_file.write_text("This is a file in another system")

        # Doesn't work.
        step.my_entities["client_system"] = function_project.project.storage_scope.store_to_dictionary(
            extra_file.parent,
        )
        assert "client_system" not in step.my_entities
        # workaround in the meantime
        entities_dict = step.my_entities
        entities_dict["client_system"] = function_project.project.storage_scope.store_to_dictionary(extra_file.parent)
        step.my_entities = entities_dict

        # extend entities dict with files from another system (product)
        step.launch_product()
        step.extend_directory_from_product_space()

        expected_paths = [
            Path("root_file.txt"),
            Path("subdir1"),
            Path("subdir1/level1_file.json"),
            Path("client_system"),
            Path("client_system/client_system_file.txt"),
            Path("product_system"),
            Path("product_system/product_system_file.txt"),
        ]
        # copy files from all systems in client
        output_dir = function_project.project.storage_scope.get_storage_root() / "output_multi_system"
        function_project.project.storage_scope.get_copy_from_dictionary(output_dir, step.my_entities)
        assert sorted([path.relative_to(output_dir) for path in output_dir.rglob("*")]) == sorted(expected_paths)

        # copy files from all systems in transaction
        paths = step.download_directory_from_entities_dict()
        assert sorted(paths) == sorted(expected_paths)

        # copy files from all systems in product
        paths = step.download_directory_into_product_space()
        assert sorted(paths) == sorted(expected_paths)

        step.shutdown_product()
