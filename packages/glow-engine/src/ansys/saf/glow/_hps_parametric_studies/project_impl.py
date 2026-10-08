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
import json
import logging
from typing import Any

from ansys.hps.client.jms import (  # pyright: ignore[reportMissingTypeStubs]
    File,
    Job,
)

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._core.blob_managers import HpsBlobManager
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator
from ansys.saf.glow._hps_parametric_studies.api import (
    HpsDesignPointSelection,
    IHpsJobStatus,
)
from ansys.saf.glow._hps_parametric_studies.base import HpsJobEvaluationStatus, HpsProject, IHpsParametricStudyProject
from ansys.saf.glow._hps_parametric_studies.project_wrapper import HpsProjectWrapper
from ansys.saf.glow._hps_parametric_studies.serialization import decode_data_from_hps, decode_string_from_hps
from ansys.saf.glow._hps_parametric_studies.system import HpsParametricStudySystem

logger = logging.getLogger(__name__)


class HpsJobStatus(IHpsJobStatus):
    def __init__(self, job: Job) -> None:
        self._job = job

    @property
    def evaluation_status(self) -> HpsJobEvaluationStatus:
        return HpsJobEvaluationStatus(self._job.eval_status)


class HpsParametricStudyProjectImpl(HpsProjectWrapper, IHpsParametricStudyProject):
    def __init__(
        self,
        persisted_project: HpsProject,
        hps_blob_manager: HpsBlobManager,
        hps_authenticator: IHpsAuthenticator,
    ) -> None:
        super().__init__(persisted_project, hps_authenticator)
        self._parameter_names: list[str] | None = None
        self._hps_blob_manager = hps_blob_manager

    def _get_parameter_names(self) -> list[str]:
        # assume that the set of parameters doesn't change
        if self._parameter_names is None:
            with self._get_project_api() as project_api:
                self._parameter_names = [
                    p.name  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
                    for p in project_api.get_parameter_definitions()  # pyright: ignore[reportUnknownMemberType]
                ]
        return self._parameter_names

    def _get_jobs(self, attribute_names: list[str], design_points: HpsDesignPointSelection | None = None) -> list[Job]:
        fields = {f"values.{name}" if name in self._get_parameter_names() else "file_ids" for name in attribute_names}
        return self._raw_get_jobs(list(fields), design_points)

    def _raw_get_jobs(self, fields: list[str], design_points: HpsDesignPointSelection | None = None) -> list[Job]:
        if design_points is None:
            design_points = HpsDesignPointSelection()
        else:
            design_points.validate(self._get_parameter_names())
        args = design_points.get_jobs_query_arguments(fields)
        with self._get_project_api() as project_api:
            return project_api.get_jobs(**args)  # pyright: ignore[reportUnknownMemberType, reportArgumentType]

    def _get_job_file(self, job: Job, file_name: str) -> EntityHandle:
        file = self._try_get_job_file(job, file_name)
        if file is None:
            raise RuntimeError(f"HPS job (id={job.id}) does not have file {file_name}")
        return file

    def _try_get_hps_job_file(self, job: Job, file_name: str) -> File | None:
        file_ids: list[str] = job.file_ids
        with self._get_project_api() as project_api:
            files: list[File] = project_api.get_files(id=file_ids)  # pyright: ignore[reportUnknownMemberType]
        for file in files:
            if file.name == file_name and file.size:
                return file
        return None

    def _try_get_job_file(self, job: Job, file_name: str) -> EntityHandle | None:
        file = self._try_get_hps_job_file(job, file_name)
        if file is None:
            return None
        else:
            is_a_job_directory = False
            if self._is_declared_directory(file.name):
                is_a_job_directory = True
            return self._hps_blob_manager.get_entity_handle(
                hps_project_identifier=self._hps_project_identifier,
                file_id=file.id,
                hps_server_url=self._hps_server_url,
                client_id=self._client_id,
                is_an_output_dir=is_a_job_directory,
            )

    def _get_file_names(self) -> Generator[str]:
        with self._get_project_api() as project_api:
            return (f.name for f in project_api.get_files())  # pyright: ignore[reportUnknownMemberType]

    def _decode_parameter_value_from_hps(self, parameter_name: str, parameter_value: Any) -> Any:
        if parameter_name in self._pickled_parameters:
            if not isinstance(parameter_value, str):
                raise RuntimeError(f"Expected pickled parameter {parameter_name} to be a string")
            return decode_data_from_hps(parameter_value)
        if isinstance(parameter_value, str):
            return decode_string_from_hps(parameter_value)
        return parameter_value

    def _get_attribute_values_of_jobs(
        self,
        jobs: list[Job],
        attribute_name: str,
    ) -> list[Any]:
        if not jobs:
            return []
        if attribute_name in self._get_parameter_names():
            return [
                self._decode_parameter_value_from_hps(
                    attribute_name,
                    job.values.get(attribute_name),  # pyright: ignore[reportUnknownMemberType]
                )
                for job in jobs
            ]
        if self._is_attribute_name_a_job_file(attribute_name):
            return [self._try_get_job_file(job, attribute_name) for job in jobs]

        raise AttributeError(f"HPS project does not have parameter or file corresponding to {attribute_name}")

    def _is_attribute_name_a_job_file(self, attribute_name: str) -> bool:
        file_names = list(self._get_file_names())
        if attribute_name in file_names:
            return True
        if self._is_declared_directory(attribute_name):
            with self._get_project_api() as project_api:
                files = project_api.get_files()  # pyright: ignore[reportUnknownMemberType]
            return any(
                file.name == f"{attribute_name}.zip" or file.evaluation_path.endswith(f"{attribute_name}.zip")
                for file in files
            )
        return False

    def _is_declared_directory(self, attribute_name: str) -> bool:
        with self._get_project_api() as project_api:
            context_file = project_api.get_files(  # pyright: ignore[reportUnknownMemberType]
                evaluation_path="inner_context.json",
                content=True,
            )[0]

        context_data = json.loads(context_file.content)  # pyright: ignore[reportArgumentType]

        return (
            attribute_name in context_data["required_output_directories"]
            or attribute_name in context_data["directory_inputs"]
        )

    def get_status_of_design_points(self, design_points: HpsDesignPointSelection | None = None) -> list[IHpsJobStatus]:
        result: list[IHpsJobStatus] = [HpsJobStatus(job) for job in self._raw_get_jobs(["eval_status"], design_points)]
        logger.debug(f"get_status_of_design_points {result=}")
        return result

    def fetch_values_of_parameters(
        self,
        parameter_names: list[str],
        design_points: HpsDesignPointSelection | None = None,
    ) -> list[list[Any]]:
        jobs = self._get_jobs(parameter_names, design_points)  # TODO: use design_points...
        return [self._get_attribute_values_of_jobs(jobs, attribute_name) for attribute_name in parameter_names]

    def get_attribute(self, attribute_name: str) -> list[Any]:
        jobs = self._get_jobs([attribute_name])
        return self._get_attribute_values_of_jobs(jobs, attribute_name)

    @property
    def ui_url(self) -> str:
        hps_server_url = HpsParametricStudySystem.get_hps_server_url()
        hps_server_url = hps_server_url.replace("127.0.0.1", "localhost")  # why?
        return f"{hps_server_url}/#/projects/{self._hps_project_identifier}/jobs"

    @property
    def finished(self) -> bool:
        return all(
            s.evaluation_status
            in [
                HpsJobEvaluationStatus.ABORTED,
                HpsJobEvaluationStatus.EVALUATED,
                HpsJobEvaluationStatus.FAILED,
                HpsJobEvaluationStatus.TIMEOUT,
            ]
            for s in self.get_status_of_design_points()
        )
