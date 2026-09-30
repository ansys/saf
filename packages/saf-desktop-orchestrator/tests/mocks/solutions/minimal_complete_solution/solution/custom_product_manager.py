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

from typing import Any
import uuid

from pydantic import BaseModel, Field

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    InstanceManager,
    ProductInstanceManager,
    RecoveryStateInfo,
)
from tests.mocks.solutions.minimal_complete_solution.custom_product_client import CustomProductClient

PRODUCT_NAME = "custom-product"
SERVICE_NAME = "http"


class SubProductInfo(BaseModel):
    sub_handle: EntityHandle = NO_ENTITY


class MockStateInfo(RecoveryStateInfo):
    project_file: EntityHandle = NO_ENTITY
    random_value: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_list_handles: list[EntityHandle] = []
    product_dict_handles: dict[str, EntityHandle] = {}
    product_sub_model: SubProductInfo = SubProductInfo()


class InternalCustomProductManagerImpl(InstanceManager[CustomProductClient, MockStateInfo]):
    PRODUCT_NAME = "custom-http-product"
    SERVICE_TYPE = "http"
    shutdown_state: str = "SHUTDOWN"

    def initialize(self, version: str | None = None):
        self.initialize_service(self.SERVICE_TYPE, version)
        self.recovery_state_info = MockStateInfo(
            project_file=NO_ENTITY,
            random_value=str(uuid.uuid4()),
        )

    @classmethod
    def get_product_name_implement(cls) -> str:
        return cls.PRODUCT_NAME

    def get_client_object_implement(self, hostname: str, port: int) -> CustomProductClient:
        return CustomProductClient(port, hostname)  # type: ignore

    def close_client_object_implement(self) -> None:
        self.instance.close()

    def _write_to_spy_file(self, content: str):
        spy_path = self._project_directory_path_on_solution / "spy.txt"
        with spy_path.open(mode="a") as f:
            f.write(content)

    def save_state_implement(self) -> None:
        self._write_to_spy_file("saving state...")
        project_file = self.manager_storage_scope.get_storage_root() / "project.txt"
        self.instance.store_given_absolute_path(str(project_file))
        self.recovery_state_info.random_value = str(uuid.uuid4())
        self.recovery_state_info.project_file = self.manager_storage_scope.store(project_file)

    def load_state_implement(self) -> None:
        self._write_to_spy_file("loading state...")
        project_file_path = self.product_storage_scope.get_cached(self.recovery_state_info.project_file)
        self.instance.restore_given_absolute_path(str(project_file_path))

    def shutdown_implement(self) -> None:
        self._write_to_spy_file("shutting instance down...")
        self.instance.the_property = self.shutdown_state


class CustomProductManager(
    ProductInstanceManager[CustomProductClient, MockStateInfo],
    instance_manager_impl_type=InternalCustomProductManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None):
        super().start(version=version)
