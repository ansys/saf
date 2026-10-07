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

import logging
import os
from pathlib import Path
import time

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow._crud.solution_configuration_models import SolutionConfiguration
from ansys.saf.glow.solution import Solution, StepModel, StepsModel, StepSpec, transaction

logger = logging.getLogger(__name__)


class FileSystemQueryMapSolutionConfiguration(SolutionConfiguration):
    solution_schema_version: int = 1
    filesystem_data_repository_query_map: dict[str, list[tuple[str, str]]] = {
        "folder_files_query_placeholder": [
            ("folder/my_file1.txt", "001"),
            ("folder/my_file2.txt", "001"),
            ("folder/subdir/my_file3.txt", "001"),
            ("folder/nested_subdir_same_name/folder/my_file4.txt", "001"),
            ("folder/nested_subdir_same_name/folder/my_file5.txt", "001"),
        ],
        "folder_dir_query_placeholder": [("folder/nested_empty_subdir/empty_subdir_2", "001")],
        "file_not_found_query_placeholder": [("folder/not_my_file.txt", "001")],
        "my_data_query_placeholder": [("my_data.txt", "001")],
    }


class DataRepositoryStep(StepModel):
    """A step for testing purpose."""

    data_repo_content: str = ""
    data_repo_handle: EntityHandle = NO_ENTITY
    method_handle: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(upload=["data_repo_handle", "method_handle"]))
    def upload_blob_to_data_repo(
        self,
        content: str = "hello world!",
        target_path: str | None = None,
        metadata: str | None = None,
        file_path: str = "data.txt",
    ) -> EntityHandle:
        file = self.storage_scope.get_storage_root() / file_path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
        self.method_handle = self.storage_scope.store(file)
        self.data_repo_handle = self.data_repository.upload(self.method_handle, target_path, metadata)
        return self.data_repo_handle

    @transaction(self=StepSpec(upload=["data_repo_handle", "method_handle"]))
    def upload_directory_to_data_repo(
        self,
        target_path: str | None = None,
        root_folder_name: str = "folder",
        file_1_content: str = "file1",
    ) -> EntityHandle:
        folder = self.storage_scope.get_storage_root() / root_folder_name
        folder.mkdir(exist_ok=True, parents=True)
        (folder / "my_file1.txt").write_text(file_1_content)
        (folder / "my_file2.txt").write_text("file2")
        (folder / "subdir").mkdir(exist_ok=True, parents=True)
        (folder / "subdir" / "my_file3.txt").write_text("file3")
        (folder / "nested_subdir_same_name" / root_folder_name).mkdir(exist_ok=True, parents=True)
        (folder / "nested_subdir_same_name" / root_folder_name / "my_file4.txt").write_text("file4")
        (folder / "nested_subdir_same_name" / root_folder_name / "my_file5.txt").write_text("file5")
        (folder / "empty_subdir").mkdir(exist_ok=True, parents=True)
        (folder / "nested_empty_subdir" / "empty_subdir_2").mkdir(exist_ok=True, parents=True)
        self.method_handle = self.storage_scope.store(folder)
        self.data_repo_handle = self.data_repository.upload(self.method_handle, target_path)
        return self.data_repo_handle

    @transaction(self=StepSpec(upload=["data_repo_handle", "method_handle"]))
    def upload_small_directory_to_data_repo(
        self,
        target_path: str | None = None,
        metadata: str | None = None,
        root_folder_name: str = "folder",
    ) -> EntityHandle:
        folder = self.storage_scope.get_storage_root() / root_folder_name
        folder.mkdir(exist_ok=True, parents=True)
        (folder / "my_another_file.txt").write_text("another_file")
        (folder / "my_file1.txt").write_text("my_file1")
        self.method_handle = self.storage_scope.store(folder)
        self.data_repo_handle = self.data_repository.upload(self.method_handle, target_path, metadata)
        return self.data_repo_handle

    @transaction(self=StepSpec(upload=["data_repo_handle"]))
    def upload_blob_multiple_times_to_data_repo(
        self,
        base_content: str = "hello world!",
        num_times: int = 3,
        target_path: str = "data.txt",
    ) -> EntityHandle:
        for i in range(1, num_times + 1):
            file = self.storage_scope.get_storage_root() / f"data_{i}.txt"
            file.write_text(f"{base_content} v{i}")
            handle = self.storage_scope.store(file)
            time.sleep(2)  # minerva bug TFS: 1188721
            self.data_repo_handle = self.data_repository.upload(handle, target_path)
        return self.data_repo_handle

    @transaction(self=StepSpec())
    def upload_same_blob_twice_to_data_repo(
        self,
        content: str = "hello world!",
        target_path: str = "data.txt",
        metadata: str | None = None,
    ) -> None:
        file = self.storage_scope.get_storage_root() / "data.txt"
        file.write_text(content)
        handle = self.storage_scope.store(file)
        self.data_repository.upload(handle, target_path, metadata)
        self.data_repository.upload(handle, target_path, metadata)

    @transaction(self=StepSpec())
    def get_data_repository_entity_handle(
        self,
        minerva_path: str = "data.txt",
        version: str | None = None,
    ) -> EntityHandle:
        return self.data_repository.get_entity_handle(minerva_path, version)

    @transaction(self=StepSpec())
    def upload_no_entity_to_data_repo(self, target_path: str | None = None):
        self.data_repository.upload(NO_ENTITY, target_path)

    @transaction(self=StepSpec())
    def return_get_entity_handle(self, minerva_path: str = "data.txt") -> EntityHandle:
        return self.data_repository.get_entity_handle(minerva_path)

    @transaction(self=StepSpec())
    def fetch_blob_content_from_data_repo(self, minerva_path: str = "data.txt", version: str | None = None) -> str:
        handle = self.data_repository.get_entity_handle(minerva_path, version)
        return self.storage_scope.get_text(handle)

    @transaction(self=StepSpec())
    def fetch_children_from_data_repo_directory(self, minerva_path: str = "folder") -> list[EntityHandle]:
        handle = self.data_repository.get_entity_handle(minerva_path)
        return self.storage_scope.get_children(handle)

    @transaction(self=StepSpec(download=["data_repo_handle"]))
    def fetch_child_from_data_repo_handle(self, minerva_path: str = "my_file1.txt") -> EntityHandle:
        return self.storage_scope.get_child(self.data_repo_handle, minerva_path)

    @transaction(self=StepSpec(download=["data_repo_handle"]))
    def fetch_cached_from_data_repo_handle(self) -> Path:
        return self.storage_scope.get_cached(self.data_repo_handle)

    @transaction(self=StepSpec(download=["data_repo_handle"]))
    def fetch_text_from_data_repo_handle(self) -> str:
        return self.storage_scope.get_text(self.data_repo_handle)

    @transaction(self=StepSpec(download=["data_repo_handle"]))
    def fetch_bytes_from_data_repo_handle(self) -> bytes:
        return self.storage_scope.get_bytes(self.data_repo_handle)

    @transaction(self=StepSpec(download=["data_repo_handle"]))
    def fetch_stream_from_data_repo_handle(self) -> str:
        stream_bytes = self.storage_scope.get_stream(self.data_repo_handle).readall()
        return stream_bytes.decode()

    @transaction(self=StepSpec())
    def fetch_parent_from_data_repo_directory(self, minerva_path: str = "folder/my_file1.txt") -> EntityHandle | None:
        handle = self.data_repository.get_entity_handle(minerva_path)
        return self.storage_scope.get_parent(handle)

    @transaction(self=StepSpec(upload=["data_repo_content"]))
    def fetch_nonexisting_item_from_data_repo(self) -> EntityHandle:
        return self.data_repository.get_entity_handle("non-existing")

    @transaction(self=StepSpec())
    def get_entities_based_on_query(self, value: str) -> list[EntityHandle]:
        return self.data_repository.query(value)

    @transaction(self=StepSpec())
    def get_entities_based_on_query_without_query_map(self, value: str) -> None:
        self.data_repository._data_repo_scope._filesystem_data_repository_query_map = None  # type: ignore
        self.data_repository.query(value)

    @transaction(self=StepSpec())
    def get_env_var(self, var_name: str) -> str:
        return os.environ.get(var_name, "")

    @transaction(self=StepSpec())
    def ensure_minerva_cli(self) -> bool:
        return bool(os.environ.get("ANS_MINERVA_CLI")) and Path(os.environ["ANS_MINERVA_CLI"]).exists()


class Steps(StepsModel):
    data_repository_step: DataRepositoryStep


class DataRepositorySolution(Solution):
    display_name: str = "DataRepository"
    steps: Steps
    solution_configuration: FileSystemQueryMapSolutionConfiguration = FileSystemQueryMapSolutionConfiguration()
