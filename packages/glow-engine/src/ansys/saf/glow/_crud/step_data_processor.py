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

from contextlib import suppress
from typing import Any, cast, final
from urllib.parse import quote

from pydantic import ValidationError

from ansys.bdm.api import EntityHandle, IAsyncStorageScope
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._server.exceptions import MalformedSolutionError
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part


@final
class StepDataProcessor:
    def __init__(
        self,
        settings: Settings,
        storage_scope: IAsyncStorageScope,
        project_id: str,
        step_name: str,
        substitute_urls: bool,
        dict_for_dir: bool,
    ) -> None:
        self._settings = settings
        self._storage_scope = storage_scope
        self._project_id = project_id
        self._step_name = step_name
        self._substitute_urls = substitute_urls
        self._dict_for_dir = dict_for_dir

    async def process_step_data_value(
        self,
        field_value: Any,
        datapath: str,
    ) -> Any:
        if not self._substitute_urls and not self._dict_for_dir:
            return field_value

        if not isinstance(field_value, EntityHandle):
            with suppress(ValidationError):
                # try converting field_value to entity handle
                field_value = EntityHandle.model_validate(field_value)

        if isinstance(field_value, EntityHandle):
            result = await self._process_entity_handle(field_value, datapath)
            if result is not None:
                return result

        if isinstance(field_value, list):
            return [
                await self.process_step_data_value(item, f"{datapath}/{index}")
                for index, item in enumerate(  # pyright: ignore[reportUnknownVariableType]
                    field_value,  # pyright: ignore[reportUnknownArgumentType]
                )
            ]

        if isinstance(field_value, dict) and all(
            isinstance(key, str)
            for key in field_value  # pyright: ignore[reportUnknownVariableType]
        ):
            return {  # pyright: ignore[reportUnknownVariableType]
                key: await self.process_step_data_value(
                    item,
                    str.format("{datapath}/{key}", datapath=datapath, key=self._escape_key(cast("str", key))),
                )
                for key, item in field_value.items()  # pyright: ignore[reportUnknownVariableType]
            }

        return field_value  # pyright: ignore[reportUnknownVariableType]

    async def _process_entity_handle(self, field_value: EntityHandle, datapath: str) -> Any:
        if field_value.is_blob and self._substitute_urls:
            url_step_name = python_identifier_to_url_part(self._step_name)
            if datapath.startswith("/"):
                datapath = datapath[1:]
            return (
                f"{self._settings.computed_external_api_url}/projects/{self._project_id}"
                + f"/steps/{url_step_name}/blobs/{quote(datapath)}"
            )
        if not field_value.is_blob and self._dict_for_dir:
            d = {}
            async for child in self._storage_scope.get_children(field_value):
                # the following code assumes that the original_name is never None for child entity handles
                # and there are no duplicate original names among the children
                # In the BDM system it might be possible for a BDM sub-system to generate such entity handles.
                # Right now we don't have any such BDM sub-systems.  The solution developer is responsible for
                # ensuring that the get_data function is not applied to such sub-systems hence the use of
                # MalformedSolutionError here.
                key = child.original_name
                if key is None:
                    raise MalformedSolutionError(
                        f"child entity handle with no original name at {datapath} in {self._step_name}",
                    )
                if key in d:
                    raise MalformedSolutionError(
                        "more than one child entity handle with the same "
                        + f"original name {key} at {datapath} in {self._step_name}",
                    )
                d[key] = await self.process_step_data_value(child, f"{datapath}/{self._escape_key(key)}")
            return d  # pyright: ignore[reportUnknownVariableType]
        return None

    def _escape_key(self, key: str) -> str:
        return key.replace("\\", "\\\\").replace("/", "\\/")

    def unescape_segment(self, segment: str) -> tuple[bool, str]:
        unescaped = ""
        pending = False
        for char in segment:
            if pending:
                unescaped += char
                pending = False
            elif char == "\\":
                pending = True
            else:
                unescaped += char
        return pending, unescaped
