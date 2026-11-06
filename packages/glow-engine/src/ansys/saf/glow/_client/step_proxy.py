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

import json
from pathlib import Path
from typing import Any, get_type_hints
from urllib.parse import quote

from fastapi.encoders import jsonable_encoder
import httpx2
from pydantic import TypeAdapter

from ansys.saf.glow._core.client_exceptions import BadRequestException, NotFoundException, check
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow._core.gql_helper import perform_update_via_graphql
from ansys.saf.glow._core.live_files import LiveFileProxy
from ansys.saf.glow._core.long_running import LongRunning
from ansys.saf.glow._core.method_status import MethodState
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._core.transaction import build_pydantic_model_from_transaction_parameters
from ansys.saf.glow._hps_parametric_studies.base import HpsProject
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part, url_part_to_python_identifier


class StepProxy:
    def __init__(
        self,
        project_url: str,
        external_project_url: str,
        step_name: str,
        step_model_type: type[StepModel],
        http_client: httpx2.Client,
        project_id: str,
        project_files_dir: Path,
        graphql_client: GqlClientConnectionPool,
    ) -> None:
        step_id = python_identifier_to_url_part(step_name)
        # use object.__setattr__ to avoid infinity recursion.
        object.__setattr__(self, "_project_url", project_url)
        object.__setattr__(self, "_external_project_url", external_project_url)
        object.__setattr__(self, "_url", f"{project_url}/steps/{step_id}")
        object.__setattr__(self, "_external_url", f"{external_project_url}/steps/{step_id}")
        object.__setattr__(self, "_step_model_type", step_model_type)
        object.__setattr__(self, "_step_name", step_name)
        object.__setattr__(self, "_http_client", http_client)
        object.__setattr__(self, "_project_id", project_id)
        object.__setattr__(self, "_project_files_dir", project_files_dir)
        object.__setattr__(self, "_graphql_client", graphql_client)

    def __str__(self):
        return self._step_model_type.__name__

    def _is_field_type(self, field_name: str, field_type: str) -> bool:
        if not hasattr(self._step_model_type.model_fields[field_name].annotation, "__name__"):
            # most likely a typing.Dict or something not of interest
            return False
        field_type_name = self._step_model_type.model_fields[field_name].annotation.__name__
        return field_type_name == field_type

    def _convert_server_value_into_client_value(self, name: str, json_fields: Any) -> Any:
        if self._is_field_type(name, "LiveFile"):
            return LiveFileProxy(
                value=json_fields[name],
                project_files_dir=self._project_files_dir / self._project_id,
            )
        if self._is_field_type(name, "HpsSimpleProject") or self._is_field_type(name, "HpsParametricStudyProject"):
            return HpsProject(**json_fields[name])
        field_value = self._get_field_value(name, json_fields)
        return field_value

    def __getattr__(self, name: str) -> Any:
        model_fields = self._step_model_type.model_fields
        if name in model_fields:
            r = self._http_client.get(self._url, params={"fields": name})
            check(r)
            json_fields = r.json()
            return self._convert_server_value_into_client_value(name, json_fields)
        elif name in self._step_model_type.get_transaction_method_names():

            def step_method(*args: Any | None, **kwargs: Any | None) -> LongRunning[Any] | None:
                if args:
                    # Prohibit usage of positional argument for now, as it is quite difficult to filter out
                    # parameters that are passed by glow itself (instance, stepmodel, etc...)
                    raise SyntaxError("Positional arguments are not supported. Use keyword arguments instead.")
                method_id = python_identifier_to_url_part(name)
                method_url = f"{self._url}:{method_id}"
                method = getattr(self._step_model_type, name)
                dynamic_model, _ = build_pydantic_model_from_transaction_parameters(method)
                response = self._http_client.post(
                    method_url,
                    json=jsonable_encoder(dynamic_model.model_validate(kwargs).model_dump()),
                )
                check(response)
                return_type = get_type_hints(method).get("return")
                if name in self._step_model_type.get_long_running_method_names():
                    return LongRunning(
                        self._step_model_type,
                        self._step_name,
                        name,
                        method_url,
                        self._http_client,
                        return_type,
                    )

                result = response.json()
                if return_type:
                    # Cast response using pydantic
                    return TypeAdapter(return_type).validate_python(result)

                return result

            return step_method

        attribute = self._step_model_type.__dict__.get(name)
        if attribute and callable(attribute):
            raise AttributeError(
                f"'{self}.{name}' has no '@transaction' decorator and therefore cannot be called.\n"
                f"Possible methods are: {', '.join(self._step_model_type.get_transaction_method_names())}.",
            )

        raise AttributeError(
            f"'{self}' object has no attribute '{name}'.\nAvailable attributes are: {', '.join(model_fields.keys())}.",
        )

    def to_dict(self, fields: list[str] | None = None):
        """Convert the step to a dictionary.

        If fields are specified, return only a subset of the full step
        dictionary with the given fields.
        """
        if fields:
            model_fields = self._step_model_type.model_fields
            if any(field not in model_fields for field in fields):
                raise AttributeError(
                    f"At least one of the provided field names is not a '{self}' step field.\n"
                    f"Available fields are: {', '.join(model_fields.keys())}.",
                )
            response = self._http_client.get(self._url, params={"fields": ",".join(fields)})
        else:
            response = self._http_client.get(self._url)
        check(response)
        return response.json()

    def from_dict(self, fields: dict[str, Any]):
        json_data = {name: jsonable_encoder(value) for name, value in fields.items()}
        url_parts = self._url.split("/")
        step_name = url_part_to_python_identifier(url_parts[-1])
        project_id = url_parts[-3]
        perform_update_via_graphql(
            graphql_client=self._graphql_client,
            step_type=self._step_model_type,
            step_name=step_name,
            json_field_data=json_data,
            project_id=project_id,
            fetch_field_value=lambda field_name: fields[field_name],
            exception_mapper=lambda m: BadRequestException(m),
        )

    def get_long_running_method_state(self, method_name: str) -> MethodState:
        if method_name not in self._step_model_type.get_long_running_method_names():
            raise NotFoundException(f"{method_name} is not a long running method on {self._step_name}")
        return self.get_method_state(method_name)

    def get_method_state(self, method_name: str) -> MethodState:
        if method_name not in self._step_model_type.get_transaction_method_names():
            raise NotFoundException(f"{method_name} is not a method on {self._step_name}")
        method_url = self._get_method_url(method_name)
        r = self._http_client.get(method_url)
        check(r)
        return MethodState.model_validate(r.json())

    def _get_method_url(self, method_name: str) -> str:
        method_id = python_identifier_to_url_part(method_name)
        return f"{self._url}:{method_id}"

    def _get_field_value(self, field_name: str, json_fields: dict[str, Any]) -> Any:
        """Return the value of a field in its original type."""
        model = self._step_model_type.model_validate_json(json.dumps(json_fields))
        typed_field_value = getattr(model, field_name)
        return typed_field_value

    def _patch_fields(self, fields: dict[str, Any]) -> None:
        model_fields = self._step_model_type.model_fields
        invalid_fields = [name for name in fields if name not in model_fields]

        if invalid_fields:
            raise AttributeError(
                f"'{self}' has no field(s) '{', '.join(invalid_fields)}'. "
                f"Available fields are: {', '.join(model_fields.keys())}.",
            )

        self.from_dict(fields)

    def __setattr__(self, name: str, value: Any) -> None:
        self._patch_fields({name: value})

    def set_fields(self, fields: dict[str, Any]) -> None:
        self._patch_fields(fields)

    def get_fields(self, field_names: list[str] | None = None) -> dict[str, Any]:
        json_fields = self.to_dict(field_names)
        return {name: self._convert_server_value_into_client_value(name, json_fields) for name in json_fields}

    def get_entity_url(self, entity_field_name: str) -> str:
        entity_url_part = python_identifier_to_url_part(entity_field_name)
        return f"{self._external_url}/blobs/{entity_url_part}"

    def get_data(
        self,
        datapath: str = "",
        substitute_file_handles_with_urls: bool = False,
        substitute_directory_handles_as_dictionaries: bool = False,
    ) -> dict[str, Any]:
        segments = datapath.split("/")
        escaped_path = "/".join([quote(segment) for segment in segments])
        params = {
            "files-as-urls": str(substitute_file_handles_with_urls).lower(),
            "directories-as-dictionaries": str(substitute_directory_handles_as_dictionaries).lower(),
        }
        r = self._http_client.get(f"{self._url}/data/{escaped_path}", params=params)
        check(r)
        return r.json()
