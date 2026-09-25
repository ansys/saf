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

from collections.abc import Callable
import json
import logging
from pathlib import Path
import string
from types import MethodType
from typing import Any, ClassVar, get_type_hints
from urllib.parse import urlparse, urlunparse

from ansys.bdm.api import EntityHandle, IStorageScope
from ansys.iam.oidc import OidcClient, UserInfo
from fastapi.encoders import jsonable_encoder
import httpx2
from pydantic import BaseModel

from ansys.saf.glow._bdm.datarepo import DataRepository
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.blob_managers import AssetManager, HpsBlobManager
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow._core.gql_helper import perform_update_via_graphql
from ansys.saf.glow._core.live_files import LiveFile, TransactionLiveFile
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._core.step_spec import StepSpec
from ansys.saf.glow._hps_auth.hps_authenticator import create_hps_authenticator
from ansys.saf.glow._hps_parametric_studies.base import (
    DynamicHpsParametricStudyProject,
    DynamicHpsProject,
    DynamicHpsSimpleProject,
    HpsParametricStudyProjectBase,
    HpsSimpleProjectBase,
)
from ansys.saf.glow._server.exceptions import InternalError, MalformedSolutionError
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part, url_part_to_python_identifier

logger = logging.getLogger(__name__)


class MethodURLParts(BaseModel):
    scheme: str
    netloc: str
    project_name: str
    step_name: str
    method_name: str


VALID_URL_CHARACTERS = string.ascii_lowercase + string.digits + "-"


class Transaction:
    def __init__(
        self,
        step_model: "TransactionStepModel",
        http_client: httpx2.Client,
        oidc_client: OidcClient,
        asset_manager: AssetManager,
        access_token: str | None,
    ) -> None:
        self._step_model = step_model
        self._http_client = http_client
        self._oidc_client = oidc_client
        self._asset_manager = asset_manager
        self._access_token = access_token
        self._user_info: UserInfo | None = None

    def upload(self, field_names: list[str]) -> None:
        self._step_model.upload_fields(field_names)

    def raise_event(self, message: Any, stream_name: str | None = None) -> None:
        if stream_name and any(char for char in stream_name if char not in VALID_URL_CHARACTERS):
            raise RuntimeError(f"Invalid {stream_name=}. Valid characters: {','.join(VALID_URL_CHARACTERS)}.")
        url_parts = self._step_model.get_method_url_parts()
        if not stream_name:
            stream_name = url_parts.method_name
        path = f"events/{url_parts.project_name}/steps/{url_parts.step_name}/streams/{stream_name}"
        url = urlunparse([url_parts.scheme, url_parts.netloc, path, "", "", ""])
        logger.debug(f"Sending event {message=} to {url=}")
        try:
            json = jsonable_encoder(message)
        except Exception:
            raise RuntimeError(f"Object of type {type(message)} is not JSON serializable") from None

        self._http_client.post(url, json=json)

    def get_asset_entity_handle(self, asset_relative_path: str) -> EntityHandle:
        url_parts = self._step_model.get_method_url_parts()
        step_name = url_part_to_python_identifier(url_parts.step_name)
        return self._asset_manager.get_entity_handle(step_name=step_name, asset_relative_path=asset_relative_path)

    @property
    def user_info(self) -> UserInfo:
        if self._access_token is None:
            return UserInfo()
        if self._user_info is None:
            self._user_info = self._oidc_client.get_user_info(self._access_token, from_issuer=True)
        return self._user_info

    def get_user_info(self, fields: list[str] | None = None) -> UserInfo:
        if self._access_token is None:
            return UserInfo()
        return self._oidc_client.get_user_info(self._access_token, fields)

    @property
    def access_token(self) -> str | None:
        return self._access_token


class TransactionStepModel:
    def __init__(
        self,
        step_url: str,
        step_spec: StepSpec,
        step_method: Callable[[Any], None],
        step_type: type[StepModel],
        http_client: httpx2.Client,
        settings: Settings,
        project_files_dir: Path,
        storage_scope: IStorageScope,
        graphql_client: GqlClientConnectionPool,
        oidc_client: OidcClient,
        asset_manager: AssetManager,
        access_token: str | None,
        data_repository: DataRepository | None,
        hps_blob_manager: HpsBlobManager,
    ) -> None:
        """A step with limited access to the original step.

        This object downloads and uploads fields that are needed for the execution
        of the supplied step method.

        The transaction step model is passed to the supplied step method as an argument so that the
        method can only get and set the fields that are explicitly stated in the ``@transaction``
        decorator.

        Parameters
        ----------
        step_url: str
            The URL of the step.

        step_spec: StepSpec
            The step specification describing the state of the fields.

        step_method: Callable
            The original step method on which the step container is injected.

        step_type: type[StepModel]
            The original type of the step which is substituted by the step container.

        http_client: httpx2.Client
            The HTTP client used to communicate with the server.

        settings: Settings
            The settings of the application.

        storage_scope: IStorageScope
            The storage scope of the step.

        data_repository: DataRepository | None
            The data repository used to store and retrieve files.
        """
        self._step_spec = step_spec
        self._step_url = step_url
        self._step_method = step_method
        self._step_type = step_type
        self._download_fields = self._step_spec.download
        self._upload_fields = self._step_spec.upload
        self._transaction = Transaction(
            self,
            http_client=http_client,
            oidc_client=oidc_client,
            asset_manager=asset_manager,
            access_token=access_token,
        )
        self._http_client = http_client
        self._settings = settings
        self._project_files_dir = Path(project_files_dir)
        self._storage_scope = storage_scope
        self._data_repository = data_repository
        self._graphql_client = graphql_client
        self._hps_blob_manager = hps_blob_manager
        self._access_token = access_token
        self._live_files: list[TransactionLiveFile] = []

        # Assign default step field attribute to this object.
        step_model = step_type()
        for field_name in self._download_fields + self._upload_fields:
            self._assign_step_value(step_model, field_name)
        for var_name, var_type in get_type_hints(step_type).items():
            if hasattr(var_type, "__origin__") and var_type.__origin__ == ClassVar:
                self._assign_step_value(step_model, var_name)
        self._assign_step_method(step_model)

    def get_method_url_parts(self) -> MethodURLParts:
        method_url = f"{self._step_url}:{python_identifier_to_url_part(self._step_method.__name__)}"

        parsed_url = urlparse(method_url)
        path_parts = parsed_url.path.strip("/").split("/")
        project_name = f"{path_parts[0]}/{path_parts[1]}"
        step_name, method_name = path_parts[3].split(":")

        return MethodURLParts(
            scheme=parsed_url.scheme,
            netloc=parsed_url.netloc,
            project_name=project_name,
            step_name=step_name,
            method_name=method_name,
        )

    def _assign_step_value(self, step_model: StepModel, field_name: str):
        """Assign default field values to this transaction step model
        so that the field can be used only in the case of an
        upload."""
        field_value = getattr(step_model, field_name)
        if isinstance(field_value, LiveFile):
            transaction_live_file = TransactionLiveFile(str(field_value), self._project_files_dir)
            self._live_files.append(transaction_live_file)
            field_value = transaction_live_file
        elif isinstance(field_value, HpsParametricStudyProjectBase):
            hps_authenticator = create_hps_authenticator(self._settings, self._access_token)
            field_value = DynamicHpsParametricStudyProject(field_value, self._hps_blob_manager, hps_authenticator)
        elif isinstance(field_value, HpsSimpleProjectBase):
            hps_authenticator = create_hps_authenticator(self._settings, self._access_token)
            field_value = DynamicHpsSimpleProject(field_value, self._hps_blob_manager, hps_authenticator)
        setattr(self, field_name, field_value)

    def release_live_file_locks(self) -> None:
        """Release any single-writer locks held by the live file fields of this transaction."""
        for live_file in self._live_files:
            live_file.release_lock()

    def _assign_step_method(self, step_model: StepModel):
        step_methods = {
            attribute
            for attribute in dir(step_model)
            if not attribute.startswith("__")
            and attribute not in ("storage_scope", "data_repository", "hps_blob_manager")
            and callable(getattr(step_model, attribute))  # ignore builtins starting with __
        }
        transaction_methods = step_model.get_transaction_method_names()
        internal_methods = step_methods.difference(transaction_methods)
        for internal_method in internal_methods:
            method_value = getattr(step_model, internal_method)
            if hasattr(method_value, "__func__"):
                setattr(self, internal_method, MethodType(method_value.__func__, self))

    def __getattr__(self, key: str):
        """Override the default ``AttributeError`` to hide the fact
        that users are manipulating a ``TransactionStepModel`` instead
        of a ``Step``."""
        try:
            return super().__getattribute__(key)
        except AttributeError:
            raise MalformedSolutionError(
                f"invalid attribute '{key}' in {self._step_type.__name__}.{self._step_method.__name__}. "
                "Please make sure that the field is declared in the step and in the transaction decorating the method.",
            ) from None

    def download(self):
        """Download fields."""
        try:
            response = self._http_client.get(self._step_url, params={"fields": ",".join(self._download_fields)})
            response.raise_for_status()
            persisted_field_values = response.json()
            step_model = self._step_type.model_validate_json(json.dumps(persisted_field_values))
            for field_name in self._download_fields:
                # Retrieve persisted values from the step model to get the proper types.
                logger.debug(f"Downloading {field_name}")
                self._assign_step_value(step_model, field_name)
        except Exception as ex:
            # We don't want client errors thrown by the step proxy to be thrown as end user errors.
            raise InternalError(str(ex)) from None

    def upload_fields(self, field_names: list[str]):
        fields: dict[str, Any] = {}
        for field_name in field_names:
            if field_name not in self._upload_fields:
                raise MalformedSolutionError(
                    f"'{field_name}' cannot be uploaded: "
                    "it is not marked as 'upload' in the StepSpec of the transaction.",
                )
            logger.debug(f"Uploading {field_name}")
            field_value = getattr(self, field_name)
            if isinstance(field_value, DynamicHpsProject):
                fields[field_name] = jsonable_encoder(field_value.persisted_project)
            else:
                fields[field_name] = jsonable_encoder(field_value)

        url_parts = self.get_method_url_parts()
        project_id = url_parts.project_name.split("/")[1]
        step_name = url_part_to_python_identifier(url_parts.step_name)

        perform_update_via_graphql(
            graphql_client=self._graphql_client,
            step_type=self._step_type,
            step_name=step_name,
            json_field_data=fields,
            project_id=project_id,
            fetch_field_value=lambda field_name: getattr(self, field_name),
            exception_mapper=lambda m: MalformedSolutionError(
                f"Uploading during the execution of {self._step_method.__name__}:\n{m}",
            ),
        )

    def upload(self):
        """Upload fields."""
        self.upload_fields(self._upload_fields)

    @property
    def transaction(self) -> Transaction:
        return self._transaction

    @property
    def storage_scope(self) -> IStorageScope:
        return self._storage_scope

    @property
    def data_repository(self) -> DataRepository:
        if not self._data_repository:
            raise InternalError("Data repository is disabled.")
        return self._data_repository
