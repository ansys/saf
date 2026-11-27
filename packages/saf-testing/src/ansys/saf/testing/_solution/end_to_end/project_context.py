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

import contextlib
from pathlib import Path
from typing import Any, Generic, TypeVar
import uuid

import httpx2

from ansys.saf.glow.client import Deployment  # pyright: ignore[reportMissingImports]
from ansys.saf.testing._solution.end_to_end._typing import ClientProtocol, SolutionProtocol
from ansys.saf.testing._solution.end_to_end.glow_process import GlowBaseProcess

T = TypeVar("T", bound=SolutionProtocol)


class ProjectFixture(Generic[T]):
    def __init__(
        self,
        solution_proc: GlowBaseProcess[T],
        glow_client: ClientProtocol[T],
        display_name: str | None = None,
        safx_path: Path | None = None,
        project_name: str | None = None,
        suppress_errors_on_deletion: bool = True,
    ) -> None:
        """A project fixture used to create project.
        The project has therefore a scope limited to the test function.
        """
        self._client = glow_client
        self._solution_proc = solution_proc
        self._suppress_errors_on_deletion = suppress_errors_on_deletion

        if not display_name:
            display_name = str(uuid.uuid4())

        if safx_path:
            self._project: T = self._client.import_project(safx_path, display_name)
        elif project_name:
            self._project: T = self._client.get_project(project_name)
        else:
            self._project: T = self._client.create_project(display_name)

        self._solution_schema = self._client.get_schema()
        self._solution_name = self._solution_schema["title"]
        self._project_id = self._project.url.split("/")[-1]
        self._project_name = f"projects/{self._project_id}"

    @property
    def client(self) -> ClientProtocol[T]:
        return self._client

    @property
    def project(self) -> T:
        return self._project

    @property
    def project_files_dir(self) -> Path:
        return self._solution_proc.project_files_directory / self._project_id

    @property
    def url(self) -> str:
        return self._project.url

    @property
    def ui_url(self) -> str:
        if not self._ui_url:
            raise RuntimeError("UI not initialized.")
        return self.url.replace(self.api_url, self._ui_url)

    @property
    def display_name(self) -> str:
        return self._project.project_display_name

    @property
    def project_name(self) -> str:
        return self._project_name

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def solution_name(self) -> str:
        return self._solution_name

    @property
    def solution_schema(self) -> dict[str, Any]:
        return self._solution_schema

    @property
    def api_url(self) -> str:
        return self._solution_proc.base_api_url

    @property
    def _ui_url(self) -> str | None:
        return self._solution_proc.base_ui_url

    def _get_local_path(self, glow_system_path: str) -> Path:
        if self._solution_proc.deployment_type == Deployment.MultiContainer:
            return self.project_files_dir / glow_system_path.replace(f"/projects/{self.project_id}/", "")
        else:
            return Path(glow_system_path)

    def rename_project(self, target_name: str) -> None:
        httpx2.patch(
            f"{self.api_url}/projects/{self.project_id}",
            json={"display_name": target_name},
        ).raise_for_status()

    def get_instance(self, step_name: str, instance_name: str) -> dict[str, Any]:
        step_name = step_name.replace("_", "-")
        instance_name = instance_name.replace("_", "-")
        response = httpx2.get(
            f"{self.api_url}/projects/{self.project_id}/steps/{step_name}/instances/{instance_name}",
        )
        response.raise_for_status()
        return response.json()

    def get_instance_dir(self, step_name: str, instance_name: str) -> Path:
        response = self.get_instance(step_name, instance_name)
        return self._get_local_path(response["state_directory_path_on_instance"])

    def delete(self):
        self._project.delete()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):  # type: ignore
        # Avoid teardown errors when something goes wrong.
        # Projects are stored on a temporary directory anyway, they will be eventually cleared.
        if self._suppress_errors_on_deletion:
            with contextlib.suppress(Exception):
                self.delete()
        else:
            self.delete()
