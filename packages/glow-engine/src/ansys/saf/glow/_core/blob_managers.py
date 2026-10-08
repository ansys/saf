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

from __future__ import annotations

from typing import TYPE_CHECKING

from ansys.saf.glow._bdm.hps_scope import HpsSubsidiarySystemStorageScope
from ansys.saf.glow._bdm.subsystem_names import HPS_BDM_SYSTEM_NAME, METHOD_ASSET_BDM_SYSTEM_NAME
from ansys.saf.glow._bdm.subsystem_scope import AssetSubsidiarySystemStorageScope

if TYPE_CHECKING:
    from ansys.bdm.api import EntityHandle
    from ansys.saf.glow._bdm.multiplexor import BdmMultiplexor


class AssetManager:
    def __init__(self, multiplexor: BdmMultiplexor):
        asset_scope = multiplexor.subsidiary_storage_scopes.get(METHOD_ASSET_BDM_SYSTEM_NAME)
        if asset_scope is None or not isinstance(asset_scope, AssetSubsidiarySystemStorageScope):
            raise ValueError("The asset subsidiary storage scope cannot be found in the bdm multiplexor.")
        self._asset_scope = asset_scope
        self._multiplexor = multiplexor

    def get_entity_handle(self, step_name: str, asset_relative_path: str) -> EntityHandle:
        asset_handle = self._asset_scope.get_entity_handle(step_name, asset_relative_path)
        return self._multiplexor.wrap_handle(METHOD_ASSET_BDM_SYSTEM_NAME, asset_handle)


class HpsBlobManager:
    def __init__(self, multiplexor: BdmMultiplexor):
        hps_storage_scope = multiplexor.subsidiary_storage_scopes.get(HPS_BDM_SYSTEM_NAME)
        if hps_storage_scope is None or not isinstance(hps_storage_scope, HpsSubsidiarySystemStorageScope):
            raise RuntimeError("The HPS subsidiary storage scope cannot be found in the bdm multiplexor.")
        self._hps_storage_scope = hps_storage_scope
        self._multiplexor = multiplexor

    def get_entity_handle(
        self,
        hps_project_identifier: str = "UNKNOWN",
        file_id: str = "",
        hps_server_url: str | None = None,
        client_id: str | None = None,
        is_an_output_dir: bool = False,
    ) -> EntityHandle:
        hps_scope_handle = self._hps_storage_scope.get_entity_handle(
            hps_project_identifier=hps_project_identifier,
            file_id=file_id,
            hps_server_url=hps_server_url,
            client_id=client_id,
            is_an_output_dir=is_an_output_dir,
        )
        return self._multiplexor.wrap_handle(HPS_BDM_SYSTEM_NAME, hps_scope_handle)

    @property
    def multiplexor(self) -> BdmMultiplexor:
        return self._multiplexor
