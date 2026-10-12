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

from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
from typing import Any, TypeVar

import httpx2

from ansys.bdm.api import IStorageScope
from ansys.saf.glow._client.step_proxy import StepProxy
from ansys.saf.glow._client.storagescope import ClientStorageScope
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.client_exceptions import ConflictException, NotFoundException, check
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._crud.solution_configuration_models import SolutionConfiguration
from ansys.saf.glow._utilities.requests import build_params_for_hps_auth_request

T = TypeVar("T")


class ProjectProxy:
    def __init__(
        self,
        name: str,
        solution_type: type[Solution],
        url: str,
        external_url: str,
        http_client: httpx2.Client,
        project_files_dir: Path,
        graphql_client: GqlClientConnectionPool,
        settings: Settings,
        access_token: str | None = None,
        context_mgr_used: bool = False,
    ) -> None:
        self._name = name
        self._solution_type = solution_type
        self._url = url
        self._external_url = external_url
        self._api_url = self._url.removesuffix(name).rstrip("/")
        self._http_client = http_client
        self._project_files_dir = project_files_dir
        self._graphql_client = graphql_client
        self._settings = settings
        self._access_token = access_token
        self._context_mgr_used = context_mgr_used
        self._context_mgr_storage_scope: IStorageScope | None = None
        self._deleted = False

    class StepsProxy:
        def __init__(
            self,
            solution_type: type[Solution],
            url: str,
            external_url: str,
            http_client: httpx2.Client,
            project_files_dir: Path,
            graphql_client: GqlClientConnectionPool,
            access_token: str | None = None,
        ) -> None:
            self._solution_type = solution_type
            self._url = url
            self._external_url = external_url
            self._http_client = http_client
            self._project_files_dir = project_files_dir
            self._graphql_client = graphql_client
            self._access_token = access_token

        def __getattr__(self, name: str) -> Any:
            step_model_type = self._solution_type.get_steps_fields().get(name)
            if step_model_type:
                return StepProxy(
                    project_url=self._url,
                    external_project_url=self._external_url,
                    step_name=name,
                    step_model_type=step_model_type,
                    http_client=self._http_client,
                    project_files_dir=self._project_files_dir,
                    graphql_client=self._graphql_client,
                )
            else:
                step_names = self._solution_type.get_steps_fields().keys()
                raise AttributeError(
                    f"'{name}' is not a valid step name. Possible values are: {', '.join(step_names)}.",
                )

    @property
    def steps(self):
        return ProjectProxy.StepsProxy(
            solution_type=self._solution_type,
            url=self._url,
            external_url=self._external_url,
            http_client=self._http_client,
            project_files_dir=self._project_files_dir,
            graphql_client=self._graphql_client,
            access_token=self._access_token,
        )

    @property
    def url(self) -> str:
        return self._url

    @property
    def project_id(self) -> str:
        return self._name.removeprefix("projects/")

    @property
    def project_name(self) -> str:
        return self._name

    @property
    def project_display_name(self) -> str:
        r = self._http_client.get(self._url)
        check(r)
        data = r.json()
        display_name = data["display_name"]
        return display_name

    @property
    def project_description(self) -> str:
        r = self._http_client.get(self._url)
        check(r)
        data = r.json()
        description = data["description"]
        return description

    @property
    def solution_configuration(self) -> SolutionConfiguration:
        solution_configuration = self._solution_type.model_fields.get("solution_configuration")
        if not solution_configuration or not solution_configuration.annotation:
            raise RuntimeError("The solution does not have solution_configuration field defined.")
        response = self._http_client.get(f"{self._api_url}/solution-configuration")
        check(response)
        return solution_configuration.annotation.model_validate(response.json())

    def _create_storage_scope(self) -> ClientStorageScope:
        try:
            fs_datarepo_query_map = getattr(self.solution_configuration, "filesystem_data_repository_query_map", None)
        except RuntimeError:
            fs_datarepo_query_map = None
        return ClientStorageScope(
            root_directory=str(self._project_files_dir),
            http_client=self._http_client,
            project_url=self._url,
            project_display_name=self.project_display_name,
            settings=self._settings,
            access_token=self._access_token,
            filesystem_data_repository_query_map=fs_datarepo_query_map,
        )

    @contextmanager
    def get_storage_scope(self) -> Generator[IStorageScope, None, None]:
        if self._context_mgr_used:
            raise ValueError(
                "'get_storage_scope' cannot be used when the project is created using a context manager. "
                "Use the property 'storage_scope' instead.",
            )
        with self._create_storage_scope() as client:
            yield client

    @property
    def storage_scope(self) -> IStorageScope:
        if not self._context_mgr_used:
            raise ValueError(
                "'storage_scope' cannot be used when the project is created without a context manager. "
                "Use 'get_storage_scope' instead.",
            )
        if self._context_mgr_storage_scope is None:
            self._context_mgr_storage_scope = self._create_storage_scope().__enter__()
        return self._context_mgr_storage_scope

    @property
    def date_created(self) -> str:
        r = self._http_client.get(self._url)
        check(r)
        data = r.json()
        return data["date_created"]

    @property
    def date_modified(self) -> str:
        r = self._http_client.get(self._url)
        check(r)
        data = r.json()
        return data["date_modified"]

    def delete(self) -> None:
        r = self._http_client.delete(self._url)
        check(r)
        self._deleted = True

    def get_step(self, required_step_type: type[T], step_name: str | None = None) -> T:
        if step_name is None:
            step_names = [
                step_name
                for step_name, step_type in self._solution_type.get_steps_fields().items()
                if step_type == required_step_type
            ]
            if len(step_names) == 0:
                raise NotFoundException(f"no step of type {required_step_type} exists in {self._solution_type}")
            if len(step_names) > 1:
                raise ConflictException(
                    f"More than one step of type {required_step_type} exists in {self._solution_type}. "
                    "Supply string 'step_name' argument to indicate which step is required",
                )
            step_name = step_names[0]
        return getattr(self.steps, step_name)

    def modify_info(
        self,
        display_name: str | None = None,
        description: str | None = None,
    ) -> None:
        """Modify project information.

        Leave a field as None to keep it unchanged. Set a field to an empty string to remove it.

        Parameters
        ----------
          display_name : str, optional
              The new display name.
          description : str, optional
              The new description.
        """
        if display_name is None and description is None:
            raise ValueError("At least one of 'display_name' or 'description' must be provided.")

        payload: dict[str, str] = {}
        if display_name is not None:
            payload["display_name"] = display_name
        if description is not None:
            payload["description"] = description

        response = self._http_client.patch(self._url, json=payload)
        check(response)

    def export(self, destination: Path) -> None:
        """Export the project into the specified directory as an
        archive file. The project file will be saved in.

        <destination>/<project_name>.safx.

        Parameters
        ----------
        destination: Path
            The path of the directory where the safx archive is exported.
        """
        url = f"{self._url}:export"
        response = self._http_client.get(url)
        check(response)
        safx_path = destination / f"{self.project_display_name}.safx"
        safx_path.write_bytes(response.content)

    def authenticate_hps(
        self,
        hps_server_url: str | None = None,
        client_id: str | None = None,
    ) -> None:
        """Authenticate into the configured HPS system.

        Parameters
        ----------
        hps_server_url: str, optional
            HPS endpoint that the HPS client will connect to.

        client_id: str, optional
            Client ID of the HPS system in OAuth.
        """
        # This only makes sense for Desktop deployments when requiring to launch
        # interactive authentication to acquire tokens. In all other scenarios,
        # HPS auth is transparent to the user and on-demand for every request.
        # However, this method should work for any scenario, so let's just pass
        # for non-desktop ones.
        if os.environ.get("GLOW_DEPLOYMENT", "Desktop") != "Desktop":
            return
        url = f"{self._api_url}/desktop:hps-auth-info"

        params = build_params_for_hps_auth_request(
            hps_server_url=hps_server_url,
            client_id=client_id,
        )

        response = self._http_client.get(url, params=params)
        check(response)
