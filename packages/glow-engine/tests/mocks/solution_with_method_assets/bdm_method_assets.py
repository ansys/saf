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

import importlib.util
from pathlib import Path

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    Solution,
    StepModel,
    StepsModel,
    StepSpec,
    transaction,
)


class StepWithAssets(StepModel):
    asset_entity: EntityHandle = NO_ENTITY

    @transaction(self=StepSpec())
    def get_asset_entity(self, asset_path: str) -> EntityHandle:
        return self.transaction.get_asset_entity_handle(asset_path)

    @transaction(self=StepSpec(upload=["asset_entity"]))
    def store_asset_entity(self) -> None:
        self.asset_entity = self.transaction.get_asset_entity_handle("asset_always_decrypted.txt")

    @transaction(self=StepSpec())
    def get_text_asset(self, asset_path: str) -> str:
        asset_handle = self.transaction.get_asset_entity_handle(asset_path)
        return self.storage_scope.get_text(asset_handle)

    @transaction(self=StepSpec())
    def get_stream_asset(self, asset_path: str) -> bytes:
        asset_handle = self.transaction.get_asset_entity_handle(asset_path)
        return self.storage_scope.get_stream(asset_handle).readall()

    @transaction(self=StepSpec())
    def get_bytes_asset(self, asset_path: str) -> bytes:
        asset_handle = self.transaction.get_asset_entity_handle(asset_path)
        return self.storage_scope.get_bytes(asset_handle)

    @transaction(self=StepSpec())
    def get_cached_asset(self, asset_path: str) -> str:
        asset_handle = self.transaction.get_asset_entity_handle(asset_path)
        return self.storage_scope.get_cached(asset_handle).as_posix()

    @transaction(self=StepSpec())
    def get_cached_dir(self, asset_path: str) -> list[str]:
        asset_handle = self.transaction.get_asset_entity_handle(asset_path)
        return [path.as_posix() for path in self.storage_scope.get_cached(asset_handle).rglob("*")]

    @transaction(self=StepSpec())
    def read_text_from_cached(self, asset_path: str) -> str:
        asset_handle = self.transaction.get_asset_entity_handle(asset_path)
        return self.storage_scope.get_cached(asset_handle).read_text()

    @transaction(self=StepSpec())
    def read_text_from_cached_dir(self, asset_dir: str, child_name: str) -> str:
        asset_handle = self.transaction.get_asset_entity_handle(asset_dir)
        dir_cached = self.storage_scope.get_cached(asset_handle)
        return (dir_cached / child_name).read_text()

    @transaction(self=StepSpec())
    def get_copy_asset(self, asset_path: str, destination: Path) -> None:
        asset_handle = self.transaction.get_asset_entity_handle(asset_path)
        return self.storage_scope.get_copy(asset_handle, destination)

    @transaction(self=StepSpec())
    def get_child_asset(self, asset_dir: str, child_name: str) -> EntityHandle:
        asset_handle = self.transaction.get_asset_entity_handle(asset_dir)
        return self.storage_scope.get_child(asset_handle, child_name)

    @transaction(self=StepSpec())
    def get_children_asset(self, asset_dir: str) -> list[EntityHandle]:
        asset_handle = self.transaction.get_asset_entity_handle(asset_dir)
        return self.storage_scope.get_children(asset_handle)

    @transaction(self=StepSpec())
    def get_parent_asset(self, asset_path: str) -> EntityHandle | None:
        asset_handle = self.transaction.get_asset_entity_handle(asset_path)
        return self.storage_scope.get_parent(asset_handle)

    # EXCEPTIONS
    @transaction(self=StepSpec())
    def get_missing_asset(self):
        self.transaction.get_asset_entity_handle("missing.txt")

    @transaction(self=StepSpec())
    def get_text_dir(self) -> str:
        asset_handle = self.transaction.get_asset_entity_handle("asset_always_decrypted.txt")
        return self.storage_scope.get_text(asset_handle)

    @transaction(self=StepSpec())
    def run_python_code_from_asset(self, first_arg: int, second_arg: int) -> int:
        asset_handle = self.transaction.get_asset_entity_handle("addition_module.py")

        spec = importlib.util.spec_from_file_location(
            "addition_module",
            self.storage_scope.get_cached(asset_handle).as_posix(),
        )
        if not spec or not spec.loader:
            raise ValueError("Failed to load addition_module")
        addition_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(addition_module)

        return addition_module.add_function(first_arg, second_arg)


class Steps(StepsModel):
    step_with_assets: StepWithAssets


class SolutionBdmAssets(Solution):
    display_name: str = "Bdm with assets"
    steps: Steps
