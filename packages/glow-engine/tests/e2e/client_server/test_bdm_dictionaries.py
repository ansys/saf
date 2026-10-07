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
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.solution import EntityHandle, RecursiveDictionaryOfEntityHandles
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solutions.bdm_dictionaries import BdmDictionariesSolution

pytestmark = pytest.mark.parametrize("solution_type", [BdmDictionariesSolution], indirect=True)


class TestBdmDictionaries:
    def _verify_entities_dict(self, entities_dict: RecursiveDictionaryOfEntityHandles, only_txt: bool = False) -> None:
        assert isinstance(entities_dict, dict)
        assert isinstance(entities_dict["root_file.txt"], EntityHandle)
        if only_txt:
            assert "subdir1" not in entities_dict
        else:
            subdir1 = entities_dict["subdir1"]
            assert isinstance(subdir1, dict)
            assert isinstance(subdir1["level1_file.json"], EntityHandle)

    def test_bdm_manually_create_dict_in_transaction(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
    ):
        """Test that a RecursiveDictionaryOfEntityHandles can be manually created within a transaction method
        by creating entity handles and organizing them into nested dictionaries.
        Test that simple dict-based syntax also works, even if static type checkers raise errors.
        """
        step = function_project.project.steps.bdm_dicts_step
        assert step.my_entities == {}

        # using correct syntax
        step.manually_create_entities_dict()
        self._verify_entities_dict(step.my_entities)

        # using simple syntax
        step.manually_create_entities_dict_simple_syntax()
        self._verify_entities_dict(step.my_entities_simple_syntax)

    def test_bdm_manually_create_dict_in_client(self, function_project: ProjectFixture[BdmDictionariesSolution]):
        """Test that a RecursiveDictionaryOfEntityHandles can be manually created from the client side
        by storing files and organizing the resulting entity handles into nested dictionaries.
        Test that simple dict-based syntax also works, even if static type checkers raise errors.
        """
        step = function_project.project.steps.bdm_dicts_step
        assert step.my_entities == {}
        root_dir = function_project.project.storage_scope.get_storage_root()
        txt_file = root_dir / "root_file.txt"
        txt_file.write_text("This is a file in the root directory")
        json_subdir_file = root_dir / "level1_file.json"
        json_subdir_file.write_text('{"key": "value"}')

        txt_file_handle = function_project.project.storage_scope.store(txt_file)
        json_file_handle = function_project.project.storage_scope.store(json_subdir_file)

        # using correct syntax
        my_dict = RecursiveDictionaryOfEntityHandles()
        my_dict["root_file.txt"] = txt_file_handle
        my_subdir_1 = RecursiveDictionaryOfEntityHandles()
        my_subdir_1["level1_file.json"] = json_file_handle
        my_dict["subdir1"] = my_subdir_1
        step.my_entities = my_dict
        self._verify_entities_dict(step.my_entities)

        # using simple syntax
        step.my_entities_simple_syntax = {
            "root_file.txt": txt_file_handle,
            "subdir1": {
                "level1_file.json": json_file_handle,
            },  # pyright: ignore[reportAttributeAccessIssue]
        }
        self._verify_entities_dict(step.my_entities_simple_syntax)

    @pytest.mark.parametrize(
        "method_name",
        ["upload_directory_to_entities_dict", "upload_directory_to_entities_dict_lr"],
    )
    def test_bdm_store_to_dictionary_in_transaction(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
        method_name: str,
    ):
        """Test that entire directory structures can be uploaded to a RecursiveDictionaryOfEntityHandles
        from within transaction methods, with optional glob pattern filtering.
        """
        step = function_project.project.steps.bdm_dicts_step
        assert step.my_entities == {}

        # all files
        method = getattr(step, method_name)
        method().wait() if method_name == "upload_directory_to_entities_dict_lr" else method()
        self._verify_entities_dict(step.my_entities)

        # only .txt files
        (
            method(glob="**/*.txt").wait()
            if method_name == "upload_directory_to_entities_dict_lr"
            else method(glob="**/*.txt")
        )
        self._verify_entities_dict(step.my_entities, only_txt=True)

        # glob that doesn't return files
        (
            method(glob="**/*.png").wait()
            if method_name == "upload_directory_to_entities_dict_lr"
            else method(glob="**/*.png")
        )
        assert step.my_entities == {}

    def test_bdm_store_to_dictionary_in_client(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
    ):
        """Test that entire directory structures can be uploaded to a RecursiveDictionaryOfEntityHandles
        from the client side using store_to_dictionary, with optional glob pattern filtering.
        """
        step = function_project.project.steps.bdm_dicts_step
        assert step.my_entities == {}
        root_dir = function_project.project.storage_scope.get_storage_root()
        txt_file = root_dir / "root_file.txt"
        txt_file.write_text("This is a file in the root directory")
        json_subdir_file = root_dir / "subdir1" / "level1_file.json"
        json_subdir_file.parent.mkdir()
        json_subdir_file.write_text('{"key": "value"}')

        # all files
        step.my_entities = function_project.project.storage_scope.store_to_dictionary(root_dir)
        self._verify_entities_dict(step.my_entities)

        # only .txt files
        step.my_entities = function_project.project.storage_scope.store_to_dictionary(root_dir, glob="**/*.txt")
        self._verify_entities_dict(step.my_entities, only_txt=True)

        # glob that doesn't return files
        step.my_entities = function_project.project.storage_scope.store_to_dictionary(root_dir, glob="**/*.png")
        assert step.my_entities == {}

    def _verify_paths_copied(self, paths: list[Path], only_txt: bool = False) -> None:
        if only_txt:
            assert [Path("root_file.txt")] == paths
        else:
            assert sorted([Path("root_file.txt"), Path("subdir1"), Path("subdir1/level1_file.json")]) == sorted(paths)

    def test_bdm_entities_from_dictionary_can_be_used_independently(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
    ):
        """
        Test that entities stored within a recursive dictionary
        can be used independently as any other entity handle.
        """
        step = function_project.project.steps.bdm_dicts_step
        assert step.my_entities == {}

        step.upload_directory_to_entities_dict()

        root_file = step.my_entities["root_file.txt"]
        assert isinstance(root_file, EntityHandle)
        root_file_path = function_project.project.storage_scope.get_cached(root_file)
        assert root_file_path.name == "root_file.txt"
        assert root_file_path.parent.name.startswith("method_")
        assert function_project.project.storage_scope.get_text(root_file) == "This is a file in the root directory"

    @pytest.mark.parametrize("dict_source", ["manually_create_entities_dict", "upload_directory_to_entities_dict"])
    @pytest.mark.parametrize(
        "method_name",
        ["download_directory_from_entities_dict", "download_directory_from_entities_dict_lr"],
    )
    def test_bdm_get_copy_from_dictionary_in_transaction(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
        dict_source: str,
        method_name: str,
    ):
        """Test that files and directories can be downloaded from a RecursiveDictionaryOfEntityHandles
        within transaction methods, with optional glob pattern filtering to select specific files.
        """
        step = function_project.project.steps.bdm_dicts_step

        getattr(step, dict_source)()
        method = getattr(step, method_name)

        # all files
        paths = method().wait() if method_name == "download_directory_from_entities_dict_lr" else method()
        self._verify_paths_copied(paths)

        # only .txt files
        paths = (
            method(glob="**/*.txt").wait()
            if method_name == "download_directory_from_entities_dict_lr"
            else method(glob="**/*.txt")
        )
        self._verify_paths_copied(paths, only_txt=True)

        # glob that doesn't return files
        paths = (
            method(glob="**/*.png").wait()
            if method_name == "download_directory_from_entities_dict_lr"
            else method(glob="**/*.png")
        )
        assert paths == []

    @pytest.mark.parametrize("dict_source", ["manually_create_entities_dict", "upload_directory_to_entities_dict"])
    def test_bdm_get_copy_from_dictionary_in_client(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
        dict_source: str,
    ):
        """Test that files and directories can be downloaded from a RecursiveDictionaryOfEntityHandles
        from the client side using get_copy_from_dictionary, with optional glob pattern filtering.
        """
        step = function_project.project.steps.bdm_dicts_step

        getattr(step, dict_source)()

        root_dir = function_project.project.storage_scope.get_storage_root()

        # all files
        output_1 = root_dir / "all_files"
        function_project.project.storage_scope.get_copy_from_dictionary(output_1, step.my_entities)
        self._verify_paths_copied([path.relative_to(output_1) for path in output_1.rglob("*")])

        # only .txt files
        output_2 = root_dir / "only_txt_files"
        function_project.project.storage_scope.get_copy_from_dictionary(output_2, step.my_entities, "**/*.txt")
        self._verify_paths_copied([path.relative_to(output_2) for path in output_2.rglob("*")], only_txt=True)

        # glob that doesn't return files
        output_3 = root_dir / "only_png_files"
        function_project.project.storage_scope.get_copy_from_dictionary(output_3, step.my_entities, "**/*.png")
        assert list(output_3.rglob("*")) == []

    def test_bdm_get_copy_from_dictionary_built_with_simple_syntax(
        self,
        function_project: ProjectFixture[BdmDictionariesSolution],
    ):
        """Test that files and directories can be downloaded from a RecursiveDictionaryOfEntityHandles
        that is defined and was built using simple dict-based syntax.
        """
        step = function_project.project.steps.bdm_dicts_step

        step.manually_create_entities_dict_simple_syntax()

        # get copy to client
        output_dir = function_project.project.storage_scope.get_storage_root() / "output"
        function_project.project.storage_scope.get_copy_from_dictionary(output_dir, step.my_entities_simple_syntax)
        self._verify_paths_copied([path.relative_to(output_dir) for path in output_dir.rglob("*")])

        # get copy to transaction
        paths = step.download_directory_from_entities_dict_simple_syntax()
        self._verify_paths_copied(paths)

    def test_bdm_dictionaries_can_be_manipulated(self, function_project: ProjectFixture[BdmDictionariesSolution]):
        """Test that solutions can manipulate existing RecursiveDictionaryOfEntityHandles, for example reducing it
        to a subset, which is a valid RecursiveDictionaryOfEntityHandles due to its recursive nature.
        """
        step = function_project.project.steps.bdm_dicts_step
        assert step.my_entities == {}

        step.upload_directory_to_entities_dict()

        entities_dict = step.my_entities
        subdict = entities_dict["subdir1"]
        assert isinstance(subdict, dict)
        step.my_entities = subdict

        paths = step.download_directory_from_entities_dict()
        assert paths == [Path("level1_file.json")]

    def test_bdm_dictionaries_are_correctly_garbage_collected(
        self,
        function_project_without_context_mgr: ProjectFixture[BdmDictionariesSolution],
    ):
        """Test that the BDM GC system can recover files left unreference when RecursiveDictionaryOfEntityHandles
        objects are manipulated inside and outside transactions.
        """

        def extract_path_from_dictionary(dictionary: RecursiveDictionaryOfEntityHandles, pathway: list[str]) -> Path:
            value: None | RecursiveDictionaryOfEntityHandles | EntityHandle = dictionary
            for key in pathway:
                assert isinstance(value, dict), f"cannot look up {key} within {pathway} as previous value is not a dict"
                value = value[key]

            assert isinstance(value, EntityHandle), f"{pathway} does not refer to an EntityHandle object"

            with function_project_without_context_mgr.project.get_storage_scope() as scope:
                p = scope.get_cached(value)
            assert p.is_file(), f"entity handle at {pathway} does not refer to a file"
            return p

        @retry(stop=stop_after_attempt(40), wait=wait_fixed(0.5))
        def check_for_deletion(paths: list[Path]) -> None:
            if any(p.exists() for p in paths):
                raise TryAgain

        step = function_project_without_context_mgr.project.steps.bdm_dicts_step

        def extract_paths_from_dictionary_field(pathways: list[list[str]]) -> list[Path]:
            return [extract_path_from_dictionary(step.my_entities, pathway) for pathway in pathways]

        # GIVEN - empty step
        assert step.my_entities == {}

        # WHEN - populating the dictionary field using filesystem
        step.upload_directory_to_entities_dict()

        # THEN - files exist on filesystem
        paths = extract_paths_from_dictionary_field([["root_file.txt"], ["subdir1", "level1_file.json"]])

        # WHEN - assigning an empty dictionary to the dictionary field
        step.my_entities = RecursiveDictionaryOfEntityHandles()

        # THEN - previous files are deleted from filesystem
        check_for_deletion(paths)

        # WHEN - populating the dictionary field using filesystem again
        step.upload_directory_to_entities_dict()

        # THEN - files exist on filesystem
        paths = extract_paths_from_dictionary_field([["root_file.txt"], ["subdir1", "level1_file.json"]])

        # WHEN - pruning the dictionary field to a sub-dictionary
        entities_dict = step.my_entities
        subdict = entities_dict["subdir1"]
        assert isinstance(subdict, dict)
        step.my_entities = subdict

        # THEN - the pruned file is removed from filesystem
        check_for_deletion([paths[0]])

        # AND - the remaining referenced file still exists
        paths[1].is_file()

        # WHEN - assigning an empty dictionary to the dictionary field again using a glob that doesn't match anything
        step.upload_directory_to_entities_dict(glob="*.png")

        # THEN - the remaining file is deleted
        check_for_deletion([paths[1]])

        # WHEN - populating the dictionary field using filesystem again with a glob that returns a subset (one file)
        step.upload_directory_to_entities_dict(glob="*.txt")

        # THEN - the file exists on the file system
        extract_paths_from_dictionary_field([["root_file.txt"]])
