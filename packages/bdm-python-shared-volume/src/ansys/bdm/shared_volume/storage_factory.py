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

from ansys.bdm.api import (
    IAsyncStorageScope,
    IStorageScope,
    IStorageScopeFactory,
)
from ansys.bdm.shared_volume.async_storage_scope import AsyncStorageScope
from ansys.bdm.shared_volume.entity_tracker import EntityTracker
from ansys.bdm.shared_volume.storage_configuration import (
    SharedFilesystemConfiguration,
)
from ansys.bdm.shared_volume.storage_scope import StorageScope


class StorageScopeFactory(IStorageScopeFactory):
    def __init__(self, config: SharedFilesystemConfiguration) -> None:
        self._config = config

    def _create_entity_tracker(self, context: str, template_vars: dict[str, str]) -> EntityTracker:
        return EntityTracker(context, self._config.render_template_vars(template_vars))

    def create_storage_scope(self, context: str, template_vars: dict[str, str]) -> IStorageScope:
        return StorageScope(self._create_entity_tracker(context, template_vars))

    async def create_async_storage_scope(self, context: str, template_vars: dict[str, str]) -> IAsyncStorageScope:
        return AsyncStorageScope(self._create_entity_tracker(context, template_vars))
