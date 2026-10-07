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

from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
import itertools
import json
import logging
import mimetypes
import ntpath
from pathlib import Path
import posixpath
import shutil
import tempfile
from typing import Any, Protocol, cast
import uuid

from ansys.hps.client.jms import (  # pyright: ignore[reportMissingTypeStubs]
    BoolParameterDefinition,
    File,
    FloatParameterDefinition,
    IntParameterDefinition,
    JmsApi,
    Job,
    JobDefinition,
    ParameterMapping,
    Project,
    ProjectApi,
    ResourceRequirements,
    Software,
    StringParameterDefinition,
    SuccessCriteria,
    TaskDefinition,
)
from ansys.hps.client.jms.resource.parameter_definition import (  # pyright: ignore[reportMissingTypeStubs]
    ParameterDefinition,
)

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._core.blob_managers import HpsBlobManager
from ansys.saf.glow._executor.local import transaction_local
from ansys.saf.glow._hps_auth.hps_authenticator import create_hps_authenticator
from ansys.saf.glow._hps_parametric_studies.base import (
    HpsInputDirectory,
    HpsInputDirectorySpecification,
    HpsInputFile,
    HpsInputFileSpecification,
    HpsJobValidationError,
    HpsOutputDirectorySpecification,
    HpsOutputFileSpecification,
    HpsOutputSourceSpecification,
    HpsOutputSpecification,
)
from ansys.saf.glow._hps_parametric_studies.exec_python import EXEC_PYTHON_CONTENT
from ansys.saf.glow._hps_parametric_studies.inner_exec_python import INNER_EXEC_PYTHON_CONTENT
from ansys.saf.glow._hps_parametric_studies.serialization import encode_data_for_hps, encode_string_for_hps
from ansys.saf.glow._hps_parametric_studies.system import HpsParametricStudySystem
from ansys.saf.glow.hps_execution_str import HPS_EXECUTION_CONTENT
from ansys.saf.product_configuration.interfaces import Software as GlowSoftware

logger = logging.getLogger(__name__)

HpsConcreteInputFileSource = Path
HpsConcreteInputDirectorySource = EntityHandle | Path


class PythonSourceSpecification:
    def __init__(
        self,
        use_product_environment: bool | None,
        use_ansys_python: bool,
        python_version: str | None,
        product_environment_version: str | None,
        use_latest_python: bool,
    ) -> None:
        self._use_product_environment = use_product_environment
        self._use_ansys_python = use_ansys_python
        self._python_version = python_version
        self._product_environment_version = product_environment_version
        self._use_latest_python = use_latest_python

    @property
    def use_product_environment(self):
        return self._use_product_environment

    @property
    def use_ansys_python(self):
        return self._use_ansys_python

    @property
    def python_version(self):
        return self._python_version

    @property
    def product_environment_version(self):
        return self._product_environment_version

    @property
    def use_latest_python(self):
        return self._use_latest_python


class HpsConcreteInputFileSpecification(Protocol):
    @property
    def source(self) -> HpsConcreteInputFileSource: ...

    @property
    def evaluation_path(self) -> str | None: ...


HpsConcreteInputFile = HpsConcreteInputFileSource | HpsConcreteInputFileSpecification


class HpsConcreteInputDirectorySpecification(Protocol):
    @property
    def source(self) -> HpsConcreteInputDirectorySource: ...

    @property
    def evaluation_path(self) -> str | None: ...


HpsConcreteInputDirectory = HpsConcreteInputDirectorySource | HpsConcreteInputDirectorySpecification
HpsConcreteInputSource = HpsConcreteInputFile | HpsConcreteInputDirectory


class HpsParameterType(ABC):
    @property
    @abstractmethod
    def record_pickled(self) -> bool:
        raise NotImplementedError()

    @property
    @abstractmethod
    def parameter_definition_type(self) -> type[ParameterDefinition]:
        raise NotImplementedError()

    @abstractmethod
    def encode_for_hps(self, value: Any) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def encode_for_input_txt(self, value: Any) -> str:
        raise NotImplementedError()


class HpsBuiltinParameterType(HpsParameterType):
    def __init__(self, type_: type[ParameterDefinition]) -> None:
        self._type = type_

    @property
    def record_pickled(self) -> bool:
        return False

    @property
    def parameter_definition_type(self) -> type[ParameterDefinition]:
        return self._type

    def encode_for_hps(self, value: Any) -> Any:
        return value

    def encode_for_input_txt(self, value: Any) -> str:
        return str(value)


class HpsStringParameterType(HpsBuiltinParameterType):
    def __init__(self) -> None:
        super().__init__(StringParameterDefinition)

    def encode_for_hps(self, value: Any) -> Any:
        return encode_string_for_hps(value)

    def encode_for_input_txt(self, value: Any) -> str:
        return f"'{encode_string_for_hps(value)}'"


class HpsPickledParameterType(HpsParameterType):
    @property
    def record_pickled(self) -> bool:
        return True

    @property
    def parameter_definition_type(self) -> type[ParameterDefinition]:
        return StringParameterDefinition

    def encode_for_hps(self, value: Any) -> Any:
        return encode_data_for_hps(value)

    def encode_for_input_txt(self, value: Any) -> str:
        return self.encode_for_hps(value)


class HpsParametricStudyDefinition:
    _INDEX_RESERVED_PARAMETER_NAME = "index"

    _type_to_parameter_type: dict[type, HpsParameterType] = {
        float: HpsBuiltinParameterType(FloatParameterDefinition),
        int: HpsBuiltinParameterType(IntParameterDefinition),
        bool: HpsBuiltinParameterType(BoolParameterDefinition),
        str: HpsStringParameterType(),
    }

    def __init__(
        self,
        hps_server_url: str | None = None,
        client_id: str | None = None,
        name: str | None = None,
    ) -> None:
        # instantiate hps_authenticator to avoid letting HpsParametricStudySystem create a new one in every call to
        # get_hps_client, which would result in not reusing cached HPS clients.
        self._hps_auth_args: dict[str, Any] = {
            "hps_authenticator": create_hps_authenticator(transaction_local.settings, transaction_local.access_token),
            "hps_server_url": hps_server_url,
            "client_id": client_id,
        }

        self._given_job_name = name
        self._project_name = self._given_job_name or f"GLOW Parameter Study-{self.__class__.__name__}-{uuid.uuid4()}"
        project_specification = Project(name=self._project_name, priority=1, active=True)
        with self._get_jms_api() as jms_api:
            self._project = jms_api.create_project(project_specification)
        self._project_id = str(self._project.id)
        self._output_parameters: None | Mapping[str, type | HpsOutputSpecification] = None

        self._parameters: list[ParameterDefinition] = []
        self._parameter_mappings: list[ParameterMapping] = []
        self._file_ids: dict[str, str] = {}
        self._input_files: list[File] = []
        self._output_files: list[File] = []
        self._files: list[File] = []
        self._job_definition: JobDefinition | None = None
        self._input_parameter_names: list[str] = []
        self._inner_script_file: File | None = None

        self._use_product_environment = True
        self._python_version = "3.11"
        self._product_environment_version = "0.0"
        self._dependencies: list[str] = []
        self._products: list[GlowSoftware] = []
        self._use_ansys_python: bool = False
        self._file_parameters_using_handles: list[str] = []
        self._pickled_parameters: list[str] = []
        self._directory_input_names: list[str] = []
        self._use_latest_python: bool = False

    @contextmanager
    def get_project_api(self) -> Generator[ProjectApi]:
        with HpsParametricStudySystem.get_hps_client(**self._hps_auth_args) as hps_client:
            yield ProjectApi(hps_client, self._project_id)

    @contextmanager
    def _get_jms_api(self) -> Generator[JmsApi]:
        with HpsParametricStudySystem.get_hps_client(**self._hps_auth_args) as hps_client:
            yield JmsApi(hps_client)

    @classmethod
    def _construct_hps_parameter_type(cls, type_: type) -> HpsParameterType:
        return cls._type_to_parameter_type.get(type_, HpsPickledParameterType())

    @classmethod
    def _encode_parameter_value_for_hps(cls, value: Any) -> Any:
        parameter_type = cls._construct_hps_parameter_type_for_value(value)
        return parameter_type.encode_for_hps(value)

    @classmethod
    def _encode_parameter_value_for_input_txt(cls, value: Any) -> str:
        parameter_type = cls._construct_hps_parameter_type_for_value(value)
        return parameter_type.encode_for_input_txt(value)

    @classmethod
    def _construct_hps_parameter_type_for_value(cls, value: Any):
        type_ = cast("type", type(value))  # pyright: ignore[reportUnnecessaryCast]
        parameter_type = cls._construct_hps_parameter_type(type_)
        return parameter_type

    @property
    def pickled_parameters(self) -> list[str]:
        return self._pickled_parameters

    @property
    def output_parameters(self) -> Mapping[str, type | HpsOutputSpecification]:
        if self._output_parameters is None:
            raise RuntimeError("output parameters not set")
        return self._output_parameters

    @property
    def project(self) -> Project:
        return self._project

    @property
    def hps_project_identifier(self) -> str:
        return self._project.id

    # the following properties default to values correct for python
    @property
    def input_true(self) -> str:
        return "True"

    @property
    def output_true(self) -> str:
        return "True"

    @property
    def input_false(self) -> str:
        return "False"

    @property
    def output_false(self) -> str:
        return "False"

    @property
    def _inner_script_file_resolved(self) -> File:
        if self._inner_script_file is None:
            raise RuntimeError("Inner script file has not been created and registered")
        return self._inner_script_file

    @property
    def python_version(self) -> str:
        return self._python_version

    @property
    def input_tokenizer(self) -> str:
        return "="

    @property
    def output_tokenizer(self) -> str:
        return "="

    @property
    def input_string_quote(self) -> str:
        return "'"

    @property
    def output_string_quote(self) -> str:
        return "'"

    @property
    def parameter_input_file(self) -> str:
        return "input"

    @property
    def parameter_output_file(self) -> str:
        return "output.txt"

    @property
    def mandatory_input_files(self) -> list[str]:
        return ["script"]

    @property
    def supports_input_file_parameters(self) -> bool:
        return True

    @property
    def supports_input_parameterization(self) -> bool:
        return True

    @property
    def supports_output_parameterization(self) -> bool:
        return True

    @property
    def software_requirements(self) -> list[GlowSoftware]:
        python_version = None if self._use_latest_python else self._python_version
        if self._use_product_environment:
            python_source = GlowSoftware(
                name="Ansys SAF Product Environment",
                version=self._product_environment_version,
            )
        elif self._use_ansys_python:
            python_source = GlowSoftware(name="Ansys Python", version=python_version)
        else:
            python_source = GlowSoftware(name="Python", version=python_version)

        requirements = [python_source]
        requirements.extend(self._products)
        return requirements

    @property
    def file_parameters_using_handles(self) -> list[str]:
        return self._file_parameters_using_handles

    @classmethod
    def _check_output_parameters(cls, output_parameters: Any) -> None:
        if isinstance(output_parameters, dict):  # noqa: SIM102
            if all(  # noqa: SIM102
                isinstance(k, str)
                for k in output_parameters  # pyright: ignore[reportUnknownVariableType]
            ):
                if all(
                    isinstance(v, HpsOutputSpecification | type)
                    for v in output_parameters.values()  # pyright: ignore[reportUnknownVariableType]
                ):
                    return
        raise RuntimeError(
            "output_parameters must be a dictionary with string keys "
            "and values which are either a type, an HpsOutputFileSpecification "
            "or an HpsOutputDirectorySpecification.",
        )

    @classmethod
    def _check_common_input_files(cls, common_input_files: Any, input_error_message_override: str | None) -> None:
        if isinstance(common_input_files, dict):  # noqa: SIM102
            if all(  # noqa: SIM102
                isinstance(k, str)
                for k in common_input_files  # pyright: ignore[reportUnknownVariableType]
            ):
                # the value types are checked in add_study_to_project
                if all(
                    isinstance(
                        value,
                        Path | HpsInputFileSpecification | HpsInputDirectorySpecification | EntityHandle,
                    )
                    for value in common_input_files.values()  # pyright: ignore[reportUnknownVariableType]
                ):
                    if all(
                        isinstance(value.source, Path | EntityHandle)  # pyright: ignore[reportUnnecessaryIsInstance]
                        for value in common_input_files.values()  # pyright: ignore[reportUnknownVariableType]
                        if isinstance(value, HpsInputFileSpecification)
                    ) and all(
                        isinstance(value.source, EntityHandle | Path)  # pyright: ignore[reportUnnecessaryIsInstance]
                        for value in common_input_files.values()  # pyright: ignore[reportUnknownVariableType]
                        if isinstance(value, HpsInputDirectorySpecification)
                    ):
                        return
                    raise RuntimeError(
                        "The source argument of HpsInputFileSpecification must be "
                        "a Path or EntityHandle. "
                        "The source argument of HpsInputDirectorySpecification must be "
                        "an EntityHandle or Path.",
                    )
        raise RuntimeError(
            (
                "common_input_files must be a dictionary with string keys and Path, "
                "HpsInputFileSpecification, "
                "HpsInputDirectorySpecification or EntityHandle values."
                if input_error_message_override is None
                else input_error_message_override
            ),
        )

    @classmethod
    def _check_input_parameter_values(
        cls,
        input_parameter_values: Any,
        input_error_message_override: str | None,
    ) -> None:
        if isinstance(input_parameter_values, Iterable) and not isinstance(input_parameter_values, str | list | dict):
            # the assumption here is that the input_parameter_values here
            # is too expensive to check
            # checking is done in add_study_to_project
            return
        if isinstance(input_parameter_values, dict):  # noqa: SIM102
            if all(  # noqa: SIM102
                isinstance(k, str)
                for k in input_parameter_values  # pyright: ignore[reportUnknownVariableType]
            ):
                if all(
                    isinstance(v, list)
                    for v in input_parameter_values.values()  # pyright: ignore[reportUnknownVariableType]
                ):
                    return
        raise RuntimeError(
            (
                "input_parameter_values_must_be an iterable or a dictionary with string keys and list values."
                if input_error_message_override is None
                else input_error_message_override
            ),
        )

    def _create_file_specification(
        self,
        name: str,
        evaluation_path: str,
        src: str | None = None,
        collect: bool = False,
        collect_interval: int = 0,
    ) -> File:
        # we check that the path is not absolute on both platforms because we don't
        # know where the HPS job will actually run.
        if posixpath.isabs(evaluation_path) or ntpath.isabs(evaluation_path):
            raise RuntimeError(f"The evaluation path of file {name} must be relative, but it is '{evaluation_path}'.")
        mime_type, _ = mimetypes.guess_type(evaluation_path)
        return File(
            name=name,
            evaluation_path=evaluation_path,
            type="text/plain" if mime_type is None else mime_type,
            src=cast("str", src),  # HPS code defaults to None but isn't typed like that :-(
            collect=collect,
            collect_interval=collect_interval,
        )

    def _create_parameter(
        self,
        tokenizer: str,
        string_quote: str,
        true_string: str,
        false_string: str,
        name: str,
        type_: type,
        parameter_file_id: str,
    ):
        hps_parameter_type = self._construct_hps_parameter_type(type_)
        parameter_definition_type = hps_parameter_type.parameter_definition_type
        parameter = parameter_definition_type(name=name)
        with self.get_project_api() as project_api:
            parameter = project_api.create_parameter_definitions([parameter])[0]
            self._parameters.append(parameter)

            if type_ is str:
                parameter_mapping = ParameterMapping(
                    key_string=name,
                    tokenizer=tokenizer,
                    string_quote=string_quote,
                    parameter_definition_id=parameter.id,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
                    file_id=parameter_file_id,
                )
            else:
                parameter_mapping = ParameterMapping(
                    key_string=name,
                    tokenizer=tokenizer,
                    parameter_definition_id=parameter.id,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
                    file_id=parameter_file_id,
                    true_string=true_string,
                    false_string=false_string,
                )
            parameter_mapping = project_api.create_parameter_mappings([parameter_mapping])[0]
        self._parameter_mappings.append(parameter_mapping)

    def _create_output_parameters(
        self,
        output_parameters: Mapping[str, type | HpsOutputSpecification],
    ):
        for output_parameter_name, output_parameter_type in output_parameters.items():
            if not isinstance(output_parameter_type, HpsOutputSpecification):
                self._create_parameter(
                    tokenizer=self.output_tokenizer,
                    string_quote=self.output_string_quote,
                    true_string=self.output_true,
                    false_string=self.output_false,
                    name=output_parameter_name,
                    type_=output_parameter_type,
                    parameter_file_id=self._file_ids[self.parameter_output_file],
                )

    def _create_input_parameter(self, name: str, value: Any):
        self._create_parameter(
            tokenizer=self.input_tokenizer,
            string_quote=self.input_string_quote,
            true_string=self.input_true,
            false_string=self.input_false,
            name=name,
            type_=cast("type", type(value)),  # pyright: ignore[reportUnnecessaryCast]
            parameter_file_id=self._file_ids[self.parameter_input_file],
        )
        self._input_parameter_names.append(name)

    def _parameter_required_for_input_file(self, input_file_name: str) -> bool:
        if input_file_name in self.mandatory_input_files:
            return False
        if self.supports_input_file_parameters:
            return True
        raise RuntimeError(
            f"{self.__class__.__name__} does not support custom file inputs such as {input_file_name}. "
            f"Valid input files are: {', '.join(self.mandatory_input_files)}",
        )

    def _create_input_parameters(
        self,
        design_point: Mapping[str, Any],
        common_input_files: list[str],
    ):
        if self.supports_input_parameterization:
            self._create_input_parameter(name=self._INDEX_RESERVED_PARAMETER_NAME, value=0)
        for input_name, input_value in design_point.items():
            self._create_input_parameter(name=input_name, value=input_value)
        for input_name in common_input_files:
            if self._parameter_required_for_input_file(input_name):
                self._create_input_parameter(name=input_name, value="a string")

    def _register_existing_file(self, file: File) -> None:
        self._files.append(file)
        self._file_ids[file.name] = file.id
        logger.debug(f"added file {file.name} with id {file.id}")

    def _create_file(self, file: File) -> File:
        with self.get_project_api() as project_api:
            file = project_api.create_files([file])[0]
        self._register_existing_file(file)
        return file

    def _create_input_file_from_bytes(self, name: str, file_name: str, content: bytes) -> None:
        with tempfile.TemporaryDirectory() as tmpdirname:
            tempdir = Path(tmpdirname)
            file = tempdir / file_name
            file.write_bytes(content)
            self._create_input_file(name, file_name, file.as_posix())

    def _create_input_file_from_source(
        self,
        common_input_name: str,
        common_input_value: HpsConcreteInputSource,
        evaluation_path: str | None = None,
    ) -> None:
        logger.debug(f"processing common input {common_input_name} - type {type(common_input_value)}")
        if isinstance(common_input_value, Path):
            self._create_input_from_path(common_input_name, common_input_value, evaluation_path)
        elif isinstance(common_input_value, HpsInputFileSpecification):
            if evaluation_path is not None:
                raise RuntimeError("given evaluation path and input file specification")
            common_input_value = cast("HpsConcreteInputFileSpecification", common_input_value)
            self._create_input_file_from_source(
                common_input_name,
                common_input_value.source,
                common_input_value.evaluation_path,
            )
        elif isinstance(common_input_value, HpsInputDirectorySpecification):
            if evaluation_path is not None:
                raise RuntimeError("given evaluation path and input directory specification")
            common_input_value = cast("HpsConcreteInputDirectorySpecification", common_input_value)
            self._create_input_directory_file(
                input_name=common_input_name,
                evaluation_path=common_input_value.evaluation_path,
                input_directory=common_input_value,
            )
            self._file_parameters_using_handles.append(common_input_name)
        elif isinstance(common_input_value, EntityHandle):
            self._create_input_from_entity_handle(common_input_name, common_input_value, evaluation_path)
        else:
            raise RuntimeError("unexpected value in common_input_files")

    def _create_input_from_path(
        self,
        common_input_name: str,
        common_input_value: Path,
        evaluation_path: str | None,
    ):
        if common_input_value.is_file():
            self._create_input_file(
                common_input_name,
                common_input_value.name if evaluation_path is None else evaluation_path,
                common_input_value.as_posix(),
            )
        else:
            self._create_input_directory_file(
                input_name=common_input_name,
                evaluation_path=evaluation_path,
                input_directory=HpsInputDirectorySpecification(
                    source=common_input_value,
                    evaluation_path=evaluation_path,
                ),
            )
            self._file_parameters_using_handles.append(common_input_name)

    def _create_input_from_entity_handle(
        self,
        common_input_name: str,
        common_input_value: EntityHandle,
        evaluation_path: str | None,
    ):
        if not evaluation_path and not common_input_value.original_name:
            raise RuntimeError("Either an evaluation path or the file handle original_name must be provided.")
        file_eval_path = evaluation_path or common_input_value.original_name

        cached_file_path = self._hps_blob_manager.multiplexor.get_cached(common_input_value).as_posix()
        if common_input_value.is_blob:
            self._create_input_file(
                common_input_name,
                file_eval_path,  # pyright: ignore[reportArgumentType]
                cached_file_path,
            )
        else:
            self._create_input_directory_file(
                input_name=common_input_name,
                evaluation_path=file_eval_path,  # pyright: ignore[reportArgumentType]
                input_directory=HpsInputDirectorySpecification(
                    source=common_input_value,
                    evaluation_path=file_eval_path,  # pyright: ignore[reportArgumentType]
                ),
            )
        self._file_parameters_using_handles.append(common_input_name)

    def _create_input_directory_file(
        self,
        input_name: str,
        evaluation_path: str | None,
        input_directory: HpsConcreteInputDirectorySpecification,
    ) -> None:
        root_dir = input_directory.source
        if isinstance(root_dir, EntityHandle):
            root_dir = self._hps_blob_manager.multiplexor.get_cached(root_dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_name = root_dir.name if evaluation_path is None else Path(evaluation_path).name
            zip_path = shutil.make_archive(
                base_name=(Path(tmpdir) / zip_name).as_posix(),
                format="zip",
                root_dir=str(root_dir),
                base_dir=".",
            )
            self._create_input_file(
                input_name,
                Path(zip_path).name.rstrip(".zip") if evaluation_path is None else evaluation_path,
                zip_path,
            )
            self._directory_input_names.append(input_name)

    def _check_input_file_evaluation_overlap(self, other_files: list[File], other_file_type: str) -> None:
        for file in self._input_files:
            for other_file in other_files:
                if file != other_file and file.evaluation_path == other_file.evaluation_path:
                    raise RuntimeError(
                        f"The evaluation path '{file.evaluation_path}' of the input file {file.name} "
                        f"is the same as the evaluation path of the {other_file_type}, {other_file.name}.",
                    )

    def _check_output_file_evaluation_overlap(self, other_files: list[File], other_file_type: str) -> None:
        for file in self._output_files:
            for other_file in other_files:
                if file != other_file and file.evaluation_path == other_file.evaluation_path:
                    raise RuntimeError(
                        f"The evaluation path '{file.evaluation_path}' of the output file {file.name} "
                        f"is the same as the evaluation path of the {other_file_type}, {other_file.name}.",
                    )

    def _create_input_files(
        self,
        common_input_files: dict[str, HpsConcreteInputSource],
    ) -> None:
        for common_input_name, common_input_value in common_input_files.items():
            self._create_input_file_from_source(common_input_name, common_input_value)

    def _get_evaluation_path(
        self,
        output_parameter_name: str,
        output_parameter_type: HpsOutputSpecification,
    ) -> str:
        evaluation_path = (
            output_parameter_name
            if output_parameter_type.evaluation_path is None
            else output_parameter_type.evaluation_path
        )

        if isinstance(output_parameter_type, HpsOutputDirectorySpecification):
            # HPS monitors the zip file, not the directory
            return f"{evaluation_path}.zip"

        return evaluation_path

    def _compute_pickled_parameters(
        self,
        first_design_point: Mapping[str, Any],
        output_parameters: Mapping[str, type | HpsOutputSpecification],
    ) -> None:
        self._pickled_parameters = [
            name
            for name, value in first_design_point.items()
            if self._construct_hps_parameter_type_for_value(value).record_pickled
        ] + [
            name
            for name, type_ in output_parameters.items()
            if not isinstance(type_, HpsOutputSpecification)
            and self._construct_hps_parameter_type(type_).record_pickled
        ]

    def _create_files(
        self,
        common_input_files: dict[str, HpsConcreteInputSource],
        output_parameters: Mapping[str, type | HpsOutputSpecification],
        first_design_point: Mapping[str, Any],
    ):
        # TODO - add support for files that are inputs per design point i.e are not common

        self._compute_pickled_parameters(first_design_point, output_parameters)

        for output_parameter_name, output_parameter_type in output_parameters.items():
            if isinstance(output_parameter_type, HpsOutputSpecification):
                evaluation_path = self._get_evaluation_path(
                    output_parameter_name,
                    output_parameter_type,
                )
                self._output_files.append(
                    self._create_file(
                        self._create_file_specification(
                            name=output_parameter_name,
                            evaluation_path=evaluation_path,
                            collect=True,
                            collect_interval=output_parameter_type.collect_interval,
                        ),
                    ),
                )
                if isinstance(output_parameter_type, HpsOutputDirectorySpecification):
                    output_parameter_name = output_parameter_name.rstrip(".zip")
                self._file_parameters_using_handles.append(output_parameter_name)

        self._check_output_file_evaluation_overlap(self._output_files, "output file")

        self._create_input_files(common_input_files)
        self._check_input_file_evaluation_overlap(self._input_files, "input file")

        if self.supports_input_parameterization and self.parameter_input_file not in common_input_files:
            custom_input_files = list(set(common_input_files.keys()) - set(self.mandatory_input_files))
            self._create_initial_input_parameter_values_file(first_design_point, custom_input_files)

        if self.supports_output_parameterization:
            if self.parameter_output_file in output_parameters:
                raise RuntimeError(f"The key '{self.parameter_output_file}' is used for a built-in output file.")
            output_parameter_file = self._create_file(
                self._create_file_specification(
                    name=self.parameter_output_file,
                    evaluation_path=self.parameter_output_file,
                    collect=True,
                ),
            )
            self._output_files.append(output_parameter_file)
            if self.parameter_output_file not in self._file_ids:
                raise RuntimeError(f"{self.parameter_output_file} missing from output files")

        self._inner_script_file = self._create_inner_script_file()
        self._check_input_file_evaluation_overlap([self._inner_script_file], "input file created by GLOW")
        self._register_existing_file(self._inner_script_file)
        self._create_asset_files(list(common_input_files.keys()))

        missing_input_files = list(set(self.mandatory_input_files) - set(common_input_files.keys()))

        if missing_input_files:
            if len(missing_input_files) == 1:
                raise RuntimeError(
                    f"The key '{missing_input_files[0]}' is missing from the input files dictionary argument.",
                )
            keys = {'", "'.join(missing_input_files)}
            raise RuntimeError(f'The keys "{keys}" are missing from the input files dictionary argument.')
        self._check_input_file_evaluation_overlap(self._input_files, "input file created by GLOW")

    def _create_task_and_job_definitions(
        self,
        max_execution_time: float,
        hps_resource_requirements: ResourceRequirements | None = None,
    ):
        if hps_resource_requirements is None:
            hps_resource_requirements = ResourceRequirements(
                num_cores=1,  # cores seem to be mandatory even if typed as optional
            )

        logger.debug(f"resource requirements for parameter study= {hps_resource_requirements}")

        for f in self._input_files:
            logger.debug(f"input file id={f.id} name={f.name} evaluation path={f.evaluation_path}")
        for f in self._output_files:
            logger.debug(f"output file id={f.id} name={f.name} evaluation path={f.evaluation_path} collect={f.collect}")

        r = [f"{s.name} {s.version}" for s in self.software_requirements]
        logger.info(f"software requirements = {r}")

        task_def = TaskDefinition(
            name=self._project_name,
            software_requirements=[
                (
                    Software(name=software.name)
                    if software.version is None
                    else Software(name=software.name, version=software.version)
                )
                for software in self.software_requirements
            ],
            resource_requirements=hps_resource_requirements,
            max_execution_time=max_execution_time,
            execution_level=0,
            num_trials=1,
            input_file_ids=[f.id for f in self._input_files],
            output_file_ids=[f.id for f in self._output_files],
            use_execution_script=True,
            execution_script_id=self._inner_script_file_resolved.id,
            success_criteria=SuccessCriteria(return_code=0),
            execution_context={},
        )

        with self.get_project_api() as project_api:
            task_def = project_api.create_task_definitions([task_def])[0]
            analyze_results = project_api.analyze_task_definition(task_def.id)
            analytics = analyze_results.analytics
            if analytics is None:
                raise RuntimeError("No analytics returned from analyze_task_definition.")
            if analytics.number_matching == 0:
                message = "No available resources match the requirements.\n"
                for field_name, field_info in analytics.model_fields.items():  # pyright: ignore[reportDeprecated]
                    if field_name != "number_matching":
                        message += (
                            f"{field_info.title} = {getattr(analytics, field_name)} : {field_info.description}.\n"
                        )
                raise HpsJobValidationError(message)

            # Create job_definition in project
            job_def = JobDefinition(
                name=self._given_job_name or f"GLOW Design Point Evaluation-{self.__class__.__name__}-{uuid.uuid4()}",
                active=True,
            )
            job_def.task_definition_ids = [task_def.id]
            for p in self._parameters:
                logger.debug(
                    f"parameter mapping id={p.id} name={p.name}",  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
                )
            job_def.parameter_definition_ids = [
                pd.id  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
                for pd in self._parameters
            ]
            for pm in self._parameter_mappings:
                logger.debug(
                    f"parameter mapping id={pm.id} file id={pm.file_id} parameter id = {pm.parameter_definition_id}",
                )
            job_def.parameter_mapping_ids = [pm.id for pm in self._parameter_mappings]

            self._job_definition = project_api.create_job_definitions([job_def])[0]

    def _create_job(
        self,
        index: int,
        common_input_files: dict[str, HpsConcreteInputSource],
        first_design_point: Mapping[str, Any],
        design_point: Mapping[str, Any],
    ):
        if self._job_definition is None:
            raise RuntimeError("job definition has not been created")

        for name, first_value in first_design_point.items():
            value = design_point.get(name)
            if value is None:
                raise RuntimeError(f"input parameter {name} missing from input parameters at index {index}")

            if type(self._construct_hps_parameter_type_for_value(value)) is not type(
                self._construct_hps_parameter_type_for_value(first_value),
            ):
                raise RuntimeError(
                    f"input parameter {name} has value '{value}' ({type(value).__name__}) "
                    f"at index {index} which is not compatible "
                    f"with the value of {name} in the first design point "
                    f"which is '{first_value}' ({type(first_value).__name__})",
                )

        if len(design_point) != len(first_design_point):
            raise RuntimeError(
                f"the design point at index {index} has {len(design_point) - len(first_design_point)} more entries "
                "than the first design point",
            )

        values = {
            name: self._encode_parameter_value_for_hps(value)
            for name, value in design_point.items()
            if name in self._input_parameter_names
        }
        values[self._INDEX_RESERVED_PARAMETER_NAME] = index

        for name in common_input_files:
            if self._parameter_required_for_input_file(name):
                values[name] = f"__SAF_GLOW_PLACEHOLDER:{name}__"

        with self.get_project_api() as project_api:
            project_api.create_jobs(
                [
                    Job(
                        name=f"Job.{index}",
                        values=values,
                        eval_status="pending",
                        job_definition_id=self._job_definition.id,
                    ),
                ],
            )

    def _check_parameter_names(self, dictionaries: list[Mapping[str, Any] | dict[str, Any]]) -> None:
        all_keys = sorted(itertools.chain(*(d.keys() for d in dictionaries)))
        for key, group in itertools.groupby(all_keys):
            num = len(list(group))
            if num != 1:
                raise RuntimeError(f"found {num} parameters called {key}")
            name: str = self._inner_script_file_resolved.name
            if key in [self._INDEX_RESERVED_PARAMETER_NAME, name]:
                raise RuntimeError(f"the reserved name '{key}' has been used as the name of a parameter")

    def _convert_dictionary_of_lists_to_generator_of_dictionaries(
        self,
        input_parameter_values: Mapping[str, Sequence[Any]],
    ) -> Iterator[Mapping[str, Any]]:
        input_names = list(input_parameter_values.keys())
        for input_name in input_names:
            if len(input_parameter_values[input_name]) != len(input_parameter_values[input_names[0]]):
                raise RuntimeError(
                    f"found {len(input_parameter_values[input_name])} values for input parameter {input_name} but "
                    f"{len(input_parameter_values[input_names[0]])} values for input parameter {input_names[0]}",
                )
        input_values = zip(*[input_parameter_values[key] for key in input_names], strict=False)
        return ({input_names[i]: design_point[i] for i in range(len(input_names))} for design_point in input_values)

    def _build_definitions(
        self,
        max_execution_time: float,
        common_input_files: dict[str, HpsConcreteInputSource],
        output_parameters: Mapping[str, type | HpsOutputSpecification],
        resource_requirements: ResourceRequirements | None = None,
        first_design_point: Mapping[str, Any] | None = None,
    ) -> None:
        if first_design_point is None:
            first_design_point = {}
        self._create_files(
            common_input_files,
            output_parameters,
            first_design_point,
        )
        self._create_output_parameters(output_parameters)
        self._check_parameter_names([first_design_point, output_parameters, common_input_files])
        self._create_input_parameters(first_design_point, list(common_input_files.keys()))
        self._create_task_and_job_definitions(max_execution_time, resource_requirements)

    def _attempt_to_add_study_to_project(
        self,
        max_execution_time: float,
        common_input_files: dict[str, HpsConcreteInputSource],
        input_parameter_values: Iterator[Mapping[str, Any]] | Mapping[str, Sequence[Any]],
        output_parameters: Mapping[str, type | HpsOutputSpecification],
        python_source: PythonSourceSpecification,
        resource_requirements: ResourceRequirements | None = None,
        dependencies: list[str] | None = None,
        products: list[GlowSoftware] | None = None,
    ) -> None:
        self._validate_and_process_extra_arguments(python_source, dependencies, products)

        if isinstance(input_parameter_values, dict):
            design_point_generator = self._convert_dictionary_of_lists_to_generator_of_dictionaries(
                input_parameter_values,  # pyright: ignore[reportUnknownArgumentType]
            )
        else:
            design_point_generator = cast("Iterator[Mapping[str, Any]]", input_parameter_values)

        first_design_point = None
        for index, design_point in enumerate(design_point_generator):
            if first_design_point is None:
                self._build_definitions(
                    max_execution_time,
                    common_input_files,
                    output_parameters,
                    resource_requirements,
                    design_point,
                )
                first_design_point = design_point

            self._create_job(index, common_input_files, first_design_point, design_point)

        if first_design_point is None:
            # project consists of one job and inputs are only files
            self._build_definitions(max_execution_time, common_input_files, output_parameters, resource_requirements)
            self._create_job(0, common_input_files, {}, {})

    def _create_input_file_from_content(self, file_name: str, content: str, evaluation_path: str = "") -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            file = Path(directory_name) / file_name
            file.write_text(content)
            self._create_input_file(
                file.stem,
                evaluation_path or file.name,
                str(file),
            )

    def split_simple_input_values(
        self,
        input_values: dict[str, Any],
    ) -> tuple[dict[str, HpsInputFile | HpsInputDirectory], dict[str, list[Any]]]:
        input_sources: dict[str, HpsInputFile | HpsInputDirectory] = {}
        input_parameters: dict[str, list[Any]] = {}
        if not isinstance(input_values, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise RuntimeError("input_values must be a dictionary.")
        for input_key, input_value in input_values.items():
            if isinstance(
                input_value,
                Path | HpsInputFileSpecification | HpsInputDirectorySpecification | EntityHandle,
            ):
                if (
                    isinstance(input_value, Path)
                    and input_value.is_dir()
                    or isinstance(input_value, EntityHandle)
                    and not input_value.is_blob
                ):
                    input_sources[input_key] = cast("HpsInputDirectory", input_value)
                else:
                    input_sources[input_key] = cast("HpsInputFile", input_value)
            else:
                input_parameters[input_key] = [input_value]
        return input_sources, input_parameters

    def add_study_to_project(
        self,
        max_execution_time: float,
        common_input_files: dict[str, HpsInputFile | HpsInputDirectory],
        input_parameter_values: Iterator[Mapping[str, Any]] | Mapping[str, Sequence[Any]],
        output_parameters: Mapping[str, type | HpsOutputSpecification],
        hps_blob_manager: HpsBlobManager,
        python_source: PythonSourceSpecification,
        resource_requirements: ResourceRequirements | None = None,
        input_error_message_override: str | None = None,
        dependencies: list[str] | None = None,
        products: list[GlowSoftware] | None = None,
    ) -> None:
        self._check_common_input_files(common_input_files, input_error_message_override)
        self._check_input_parameter_values(input_parameter_values, input_error_message_override)
        self._check_output_parameters(output_parameters)
        self._output_parameters = output_parameters
        self._hps_blob_manager = hps_blob_manager
        self._file_parameters_using_handles = []
        try:
            self._attempt_to_add_study_to_project(
                max_execution_time,
                cast("dict[str, HpsConcreteInputSource]", common_input_files),
                input_parameter_values,
                output_parameters,
                python_source,
                resource_requirements,
                dependencies,
                products,
            )
        except:
            with self._get_jms_api() as jms_api:
                jms_api.delete_project(self._project)  # pyright: ignore[reportUnknownMemberType]
            raise

    def _validate_and_process_extra_arguments(
        self,
        python_source: PythonSourceSpecification,
        dependencies: list[str] | None = None,
        products: list[GlowSoftware] | None = None,
    ) -> None:
        self._process_dependencies_argument(dependencies)
        self._use_product_environment = (
            python_source.use_product_environment
            if python_source.use_product_environment is not None
            else not self._dependencies
        )
        self._use_ansys_python = python_source.use_ansys_python
        if self._dependencies and self._use_product_environment:
            raise RuntimeError(
                "You cannot use the product environment and specify "
                "dependencies (additional packages cannot be added to the product environment).",
            )
        if python_source.python_version and self._use_product_environment:
            raise RuntimeError(
                "You cannot use the product environment and specify "
                "a python version. Setting the 'product_environment_version' argument allows you to "
                "select the python interpreter deployed in a specific product environment.",
            )
        if self._use_ansys_python and self._use_product_environment:
            raise RuntimeError(
                "You cannot use the product environment with Ansys Python. "
                "Setting the 'product_environment_version' argument allows you to "
                "select the Python interpreter deployed in a specific product environment.",
            )
        if python_source.python_version and python_source.use_latest_python:
            raise RuntimeError("You cannot specify both python_version and use_latest_python.")

        if python_source.product_environment_version and not self._use_product_environment:
            raise RuntimeError("You cannot specify the product environment version when not using product environment.")

        self._python_version = python_source.python_version or self._python_version
        self._use_latest_python = python_source.use_latest_python
        self._product_environment_version = (
            python_source.product_environment_version or self._product_environment_version
        )
        self._process_products_argument(products)

    def _process_dependencies_argument(self, dependencies: list[str] | None = None) -> None:
        self._dependencies = dependencies or self._dependencies
        if not isinstance(self._dependencies, list) or not all(  # pyright: ignore[reportUnnecessaryIsInstance]
            isinstance(dependency, str)  # pyright: ignore[reportUnnecessaryIsInstance]
            for dependency in self._dependencies
        ):
            raise RuntimeError("The dependencies argument must be a list of strings.")

    def _process_products_argument(self, products: list[GlowSoftware] | None = None) -> None:
        self._products = products or self._products
        if not all(
            isinstance(product, GlowSoftware)  # pyright: ignore[reportUnnecessaryIsInstance]
            for product in self._products
        ):
            raise RuntimeError("The products argument must be a list of software.")

    def _create_input_file(self, name: str, evaluation_path: str, src: str) -> None:
        # assume any clash is caused by file supplied as a parameter to the create project method
        if any(f.name == name for f in self._input_files):
            raise RuntimeError(f"The key '{name}' is used for a built-in input file.")
        self._input_files.append(
            self._create_file(
                self._create_file_specification(
                    name=name,
                    evaluation_path=evaluation_path,
                    src=src,
                ),
            ),
        )

    def _create_file_from_content(self, file_name: str, content: str) -> Path:
        file = Path(tempfile.mkdtemp(prefix="ansys_glow_")) / file_name
        file.write_text(content)
        return file

    def _create_inner_script_file(self) -> File:
        asset = self._create_file_from_content("exec_python.py", EXEC_PYTHON_CONTENT)
        with self.get_project_api() as project_api:
            return project_api.create_files(
                [
                    self._create_file_specification(
                        name="inner_script_file",
                        evaluation_path=asset.name,
                        src=str(asset),
                    ),
                ],
            )[0]

    def _create_asset_files(self, input_file_keys: list[str]) -> None:
        self._create_input_file_from_content("inner_exec_python.py", INNER_EXEC_PYTHON_CONTENT)
        if self._dependencies:
            self._create_input_file_from_content("requirements.txt", "\n".join(self._dependencies))

        context = {
            "required_output_parameters": [
                parameter_name
                for parameter_name, parameter_type in self.output_parameters.items()
                if not isinstance(parameter_type, HpsOutputSourceSpecification)
            ],
            "required_output_files": {
                parameter_name: parameter_type.evaluation_path
                for parameter_name, parameter_type in self.output_parameters.items()
                if isinstance(parameter_type, HpsOutputFileSpecification)
            },
            "required_output_directories": {
                parameter_name: parameter_type.evaluation_path
                for parameter_name, parameter_type in self.output_parameters.items()
                if isinstance(parameter_type, HpsOutputDirectorySpecification)
            },
            "directory_inputs": self._directory_input_names,
            "pickled_parameters": self._pickled_parameters,
            "input_file_keys": input_file_keys,
        }

        self._create_input_file_from_content("inner_context.json", json.dumps(context))
        self._create_input_file_from_content(
            "execution.py",
            HPS_EXECUTION_CONTENT,
            evaluation_path="ansys/saf/glow/hps_execution.py",
        )

    def _create_initial_input_parameter_values_file(
        self,
        first_design_point: Mapping[str, Any],
        custom_files: list[str],
    ) -> None:
        content = ""
        for name, value in first_design_point.items():
            content += f"{name}={self._encode_parameter_value_for_input_txt(value)}\n"
        for name in custom_files:
            content += (
                f"{name}=''\n"  # this be substituted first with a placeholder and then by the actual path to the file
            )

        self._create_input_file_from_content("input.txt", content)
