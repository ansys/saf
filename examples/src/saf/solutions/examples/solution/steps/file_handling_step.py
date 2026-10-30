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

# ©2025, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.


"""Backend of the file handling step."""


from pathlib import Path

from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, transaction


class FileHandlingStep(StepModel):
    """File handling step model."""

    my_file_handle: EntityHandle = NO_ENTITY
    my_directory_handle: EntityHandle = NO_ENTITY
    my_uploaded_file_handle: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec(upload=["my_file_handle"]))
    def store_my_file_handle(self, text: str) -> None:
        """Store a file in the storage scope."""
        filepath = self.storage_scope.get_storage_root() / "my_file.txt"
        filepath.write_text(text)
        self.my_file_handle = self.storage_scope.store(filepath)

    @transaction(self=StepSpec())
    def access_and_use_method_asset_file(self) -> None:
        """Access an asset file in a transaction and send its content as an event."""
        asset_handle = self.transaction.get_asset_entity_handle("my_asset.txt")
        asset_content = self.storage_scope.get_text(asset_handle)
        self.transaction.raise_event(message=asset_content, stream_name="my-stream")

    @transaction(self=StepSpec(upload=["my_directory_handle"]))
    def store_my_directory_handle(self, relative_path: str, text: str):
        """Store a directory in the storage scope."""
        relative_path_stripped = str(Path(relative_path).parent).lstrip("\\/")
        dirpath = self.storage_scope.get_storage_root() / relative_path_stripped
        dirpath.mkdir(parents=True, exist_ok=True)
        file_name = Path(relative_path).name
        (dirpath / file_name).write_text(text)
        self.my_directory_handle = self.storage_scope.store(dirpath)
