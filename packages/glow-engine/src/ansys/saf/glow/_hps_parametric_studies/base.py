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

from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

# IMPORTANT: Keep HPS dependencies out of here. These classes are imported in core.
from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow._core.blob_managers import HpsBlobManager
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator
from ansys.saf.glow._hps_parametric_studies.serialization import encode_string_for_hps

HpsParameterValue = str | int | float | bool
HpsParameterValueType = type[str] | type[int] | type[float] | type[bool]
HpsInputFileSource = Path | EntityHandle
HpsInputDirectorySource = EntityHandle | Path
HpsOutputFileReturnType = type[EntityHandle]


T = TypeVar("T")


class HpsJobValidationError(Exception):
    """An exception raised when a HPS job is invalid and cannot be started."""


class HpsProjectNotStartedError(Exception):
    """An exception raised when a HPS project is accessed before being started."""


class HpsInputSourceSpecification(Generic[T]):
    """A base class for HPS input source specifications.

    This class is used to define the source of an input file or directory in a HPS job or parametric study."""

    def __init__(self, source: T, evaluation_path: str | None = None) -> None:
        if evaluation_path is not None and not isinstance(
            evaluation_path,
            str,
        ):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise RuntimeError(f"The evaluation_path argument of {self.__class__.__name__} must be None or a string.")
        self._source = source
        self._evaluation_path = evaluation_path

    @property
    def source(self) -> T:
        """The source of the input file or directory."""
        return self._source

    @property
    def evaluation_path(self) -> str | None:
        """The relative path for the input file or directory when it is copied into the
        current working directory of an HPS job. A `None` value indicates the default
        behaviour of copying the file or directory into the current working directory with
        the same name as the source."""
        return self._evaluation_path


class HpsInputFileSpecification(HpsInputSourceSpecification[HpsInputFileSource]):
    """The specification of a file which will be used as input for a HPS job or parametric study.

    Parameters
    ----------

    source : Path
        The source of the file.
    evaluation_path : str | None, optional
        The relative path for the file when it is copied into the current working directory of a HPS job.
        The default behaviour (indicated by argument ``None`` value) is to copy the file into the current
        working directory with same filename as the source file"""


HpsInputFile = HpsInputFileSpecification | HpsInputFileSource


class HpsInputDirectorySpecification(HpsInputSourceSpecification[HpsInputDirectorySource]):
    """The specification of a directory which will be used as input for a HPS job or parametric study.

    Parameters
    ----------

    source : EntityHandle | Path
        The source of the directory.
    evaluation_path : str | None, optional
        The relative path for the directory when it is copied into the current working directory of a HPS job.
        The default behaviour (indicated by argument ``None`` value) is to copy the directory into the current
        working directory with same filename as the source directory"""

    def __init__(self, source: HpsInputDirectorySource, evaluation_path: str | None = None) -> None:
        self._check_input_is_directory(source)
        super().__init__(source, evaluation_path)

    def _check_input_is_directory(self, source: HpsInputDirectorySource) -> None:
        if (
            isinstance(source, Path)
            and source.is_dir()
            or (isinstance(source, EntityHandle) and source != NO_ENTITY and not source.is_blob)
        ):
            return
        source_str = f"Path({source})" if isinstance(source, Path) else f"EntityHandle({source.original_name})"
        raise RuntimeError(
            "The source of HpsInputDirectorySpecification must be a directory, but got "
            f"{source_str} which does not refer to a directory.",
        )


HpsInputDirectory = HpsInputDirectorySpecification | HpsInputDirectorySource


class HpsOutputSourceSpecification:
    """A base class for HPS output source specifications.

    This class is used to define the specification of an output file or directory in a HPS job or parametric study."""

    def __init__(
        self,
        evaluation_path: str | None = None,
        monitor: bool = False,
        collect_interval: int = 0,
    ) -> None:
        if evaluation_path is not None and not isinstance(
            evaluation_path,
            str,
        ):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise RuntimeError(f"The evaluation_path argument of {self.__class__.__name__} must be None or a string.")
        if collect_interval < 0:
            raise RuntimeError(
                f"The collect_interval argument of {self.__class__.__name__} must be a non-negative integer.",
            )
        self._evaluation_path = evaluation_path
        self._monitor = monitor
        self._collect_interval = collect_interval

    @property
    def evaluation_path(self) -> str | None:
        """The relative path for the output in the current working directory of a successfully completed HPS job.
        A `None` value indicates the default behaviour of expecting the output in the current working directory
        with the same name as the output key."""
        return self._evaluation_path

    @property
    def monitor(self) -> bool:
        """Whether the output is monitored for changes by HPS."""
        return self._monitor

    @property
    def collect_interval(self) -> int:
        """Collection frequency for the output, specified in seconds."""
        return self._collect_interval


class HpsOutputFileSpecification(HpsOutputSourceSpecification):
    """The specification of a file which will be generated by a HPS job.

    Parameters
    ----------

    evaluation_path : str | None, optional
        The relative path for the file in the current working directory of a successfully completed HPS job.
        The default behaviour (indicated by argument ``None`` value) is to expect the file in the current
        working directory of a successfully completed HPS job with the file's key as its filename.
        The file's key is the key of the entry containing the ``HpsOutputFileSpecification`` object in the
        dictionary passed as an ``output_parameters`` argument to
        :py:meth:`~ansys.saf.glow.solution.hps.HpsSimpleProject.start_hps_job` or
        :py:meth:`~ansys.saf.glow.solution.hps.HpsParametricStudyProject.start_hps_parametric_study`.

    monitor : bool, optional
        This flag determines whether the file is monitored for changes by HPS. The default is False.

    collect_interval : int, optional
        Collection frequency for the file, specified in seconds. The default is 0.
    """

    def __init__(
        self,
        evaluation_path: str | None = None,
        monitor: bool = False,
        collect_interval: int = 0,
    ) -> None:
        super().__init__(
            evaluation_path=evaluation_path,
            monitor=monitor,
            collect_interval=collect_interval,
        )


class HpsOutputDirectorySpecification(HpsOutputSourceSpecification):
    """The specification of a directory which will be generated by a HPS job.

    Parameters
    ----------

    evaluation_path : str | None, optional
        The relative path for the directory in the current working directory of a successfully completed HPS job.
        The default behaviour (indicated by argument ``None`` value) is to expect the directory in the current
        working directory of a successfully completed HPS job with the directory's key as its name.
        The directory's key is the key of the entry containing the ``HpsOutputDirectorySpecification`` object in the
        dictionary passed as an ``output_parameters`` argument to
        :py:meth:`~ansys.saf.glow.solution.hps.HpsSimpleProject.start_hps_job` or
        :py:meth:`~ansys.saf.glow.solution.hps.HpsParametricStudyProject.start_hps_parametric_study`.

    monitor : bool, optional
        This flag determines whether the directory is monitored for changes by HPS. The default is False.

    collect_interval : int, optional
        Collection frequency for the directory, specified in seconds. The default is 0.
    """

    def __init__(
        self,
        evaluation_path: str | None = None,
        monitor: bool = False,
        collect_interval: int = 0,
    ) -> None:
        super().__init__(
            evaluation_path=evaluation_path,
            monitor=monitor,
            collect_interval=collect_interval,
        )


HpsOutputSpecification = HpsOutputFileSpecification | HpsOutputDirectorySpecification


class HpsJobEvaluationStatus(Enum):
    """The states of a HPS Job."""

    PENDING = "pending"
    """The job is waiting for an evaluator to evaluate the job."""
    PROLOG = "prolog"
    """The job is being prepared for evaluation."""
    RUNNING = "running"
    """The job is being evaluated."""
    EVALUATED = "evaluated"
    """The job has been successfully evaluated."""
    FAILED = "failed"
    """The job evaluation failed."""
    ABORTED = "aborted"
    """The job evaluation was aborted."""
    TIMEOUT = "timeout"
    """The job evaluation timed out."""


class IHpsJobStatus(Protocol):
    """The status of a HPS job."""

    @property
    def evaluation_status(self) -> HpsJobEvaluationStatus:
        """The evaluation state of the job."""
        ...


class HpsDesignPointSelection:
    """A selector of design points in a :py:class:`~ansys.saf.glow.solution.hps.HpsParametricStudyProject`.
    The ``required_design_points``, ``eval_status`` and ``parameter_filter`` arguments, when present, combine to
    define a base set of design points. This base set can then be sorted via the ``sort`` argument.
    The base set is then further restricted by the ``limit`` and ``offset`` arguments.

    Parameters
    ----------

    required_design_points : list[int] | None, optional
        Specifies the indices of the design points to be included in the selection.
        Default is None which means all design points are included.

    eval_status : HpsJobEvaluationStatus | list[HpsJobEvaluationStatus] | None, optional
        Specifies the evaluation status of the design points to be included in the selection.
        if a list is provided then design points with any of the specified statuses are included.
        Default is None which means all design points are included.

    limit : int | None, optional
        Specifies the maximum number of design points to be included in the selection.
        Default is None which means all design points are included.

    offset : int | None, optional
        Specifies the number of design points to skip before including design points in the selection.
        Default is None which means no design points are skipped.

    sort : str | list[str] | None, optional
        Specifies the keys of the parameters to sort the design points by.
        Default is None which means the design points are only sorted by the order passed to
        :py:meth:`~ansys.saf.glow.solution.hps.HpsParametricStudyProject.start_hps_parametric_study`.

    parameter_filter : dict[str, str | int | float | list[str | int | float]] | None, optional
        Specified a filter based on parameter values. Default is None which means all design points are included.

        An entry key string relates a parameter to the entry value to form a filter. The entries in the dictionary
        are combined to filter the design points. A design point must meet the criteria of all
        dictionary entries to be included.

        The values of the dictionary are either parameter values or lists of parameter values.
        Parameter values are either strings, integers or floats.
        The keys are either the
        name of a parameter or a string of the form ``<parameter_name>.<operator>``. Valid operator substrings are:

        * ``=`` - equal to
        * ``ne`` - not equal to
        * ``lt`` - less than
        * ``le`` - less than or equal to
        * ``gt`` - greater than
        * ``ge`` - greater than or equal to
        * ``in`` - in a list of values
        * ``contains`` - contains value as substring

        If the name of the parameter is used alone in the key then the relationship is "equal to" if the
        value is not a list and "in" if the value is a list.

        For example an entry with key ``"temperature.gt"`` and value ``100`` would only include design points
        where the temperature parameter is greater than 100.
    """

    def __init__(
        self,
        required_design_points: list[int] | None = None,
        eval_status: HpsJobEvaluationStatus | list[HpsJobEvaluationStatus] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort: str | list[str] | None = None,
        parameter_filter: dict[str, str | int | float | list[str | int | float]] | None = None,
    ) -> None:
        self._required_design_points = required_design_points
        self._eval_status = (
            None if eval_status is None else (eval_status if isinstance(eval_status, list) else [eval_status])
        )
        self._limit = limit
        self._offset = offset
        self._sort = None if sort is None else (sort if isinstance(sort, list) else [sort])
        self._parameter_filter = parameter_filter

    def validate(self, parameters: list[str]) -> None:
        if self._sort is not None:
            for sort in self._sort:
                if sort not in parameters:
                    raise RuntimeError(
                        f"{sort} is present in the selection sort "
                        "argument but is not the name of a parameter. "
                        f"Available parameters are: {', '.join(parameters)}.",
                    )
        if self._parameter_filter is not None:
            for parameter_filter in self._parameter_filter:
                filter_part = parameter_filter.split(".")[0]
                if filter_part not in parameters:
                    raise RuntimeError(
                        f"{filter_part} is present in the selection filter "
                        "argument but is not the name of a parameter. "
                        f"Available parameters are: {', '.join(parameters)}.",
                    )

    def _process_filter_value(self, value: str | float) -> str:
        if isinstance(value, str):
            return f'"{encode_string_for_hps(value)}"'
        return f"{value}"

    def _process_filter_item(self, key: str, value: str | float | list[str | int | float]) -> str:
        key_parts = key.split(".")
        if len(key_parts) > 1:
            if key_parts[-1] == "=":
                key = ".".join(key_parts[:-1])
            elif key_parts[-1] == "in":
                raise NotImplementedError("The 'in' operator is not supported by HPS.")

        if isinstance(value, list):
            value = [self._process_filter_value(v) for v in value]
        else:
            value = self._process_filter_value(value)

        return f"{key}={value}"

    def get_jobs_query_arguments(self, fields: list[str]) -> dict[str, HpsParameterValue | Sequence[HpsParameterValue]]:
        args: dict[str, HpsParameterValue | Sequence[HpsParameterValue]] = {}
        if self._eval_status is not None:
            args["eval_status"] = [s.value for s in self._eval_status]
        if self._limit is not None:
            args["limit"] = self._limit
        if self._offset is not None:
            args["offset"] = self._offset

        # TODO - support reverse order using '-'
        sort = [] if self._sort is None else [f"values.{parameter}" for parameter in self._sort]
        sort.append("values.index")
        args["sort"] = sort

        parameter_filter = (
            []
            if self._parameter_filter is None
            else [f"{self._process_filter_item(key, value)}" for key, value in self._parameter_filter.items()]
        )

        if self._required_design_points is not None:
            # not sure how to implement this correctly
            # something like: parameter_filter.append(f"index.in={self._required_design_points}")
            # should work but doesn't
            raise NotImplementedError("The required_design_points filter is not supported by HPS.")

        if parameter_filter:
            args["values"] = parameter_filter

        args["fields"] = fields

        return args


class HpsQueue(BaseModel):
    """A queue of an HPS compute resource set."""

    name: str


class HpsComputeResourceSet(BaseModel):
    """A compute resource set in HPS."""

    name: str
    queues: list[HpsQueue]


class HpsProject(BaseModel):
    """A reference to a project in HPS."""

    hps_project_identifier: str = ""
    hps_server_url: str | None = None
    client_id: str | None = None
    file_parameters_using_handles: list[str] = []
    pickled_parameters: list[str] = []

    @property
    def ui_url(self) -> str:
        """The URL of the project in the HPS UI."""
        raise RuntimeError("This property is not available")

    @property
    def finished(self) -> bool:
        """Whether all the jobs in the project are evaluated, failed, timed-out or
        aborted, that is no job is pending or running."""
        raise RuntimeError("This property is not available")

    @property
    def exists(self) -> bool:
        """Whether the project exists in HPS."""
        raise RuntimeError("This property is not available")

    @staticmethod
    def get_compute_resource_sets(
        hps_server_url: str | None = None,
        client_id: str | None = None,
    ) -> list[HpsComputeResourceSet]:
        """Get available compute resource sets in HPS."""
        raise RuntimeError("This method is not available")


class HpsSimpleProjectBase(HpsProject):
    """A reference to a single job project in HPS."""


class HpsParametricStudyProjectBase(HpsProject):
    """A reference to a parametric study project in HPS."""


class IHpsParametricStudyProject(Protocol):
    def get_status_of_design_points(
        self,
        design_points: HpsDesignPointSelection | None = None,
    ) -> list[IHpsJobStatus]: ...

    def get_attribute(
        self,
        attribute_name: str,
    ) -> list[Any]: ...

    def fetch_values_of_parameters(
        self,
        parameter_names: list[str],
        design_points: HpsDesignPointSelection | None = None,
    ) -> list[list[Any]]: ...

    @property
    def ui_url(self) -> str: ...

    @property
    def finished(self) -> bool: ...

    @property
    def exists(self) -> bool: ...


class IHpsSystemInformation(Protocol):
    @staticmethod
    def get_compute_resource_sets(
        hps_server_url: str | None = None,
        client_id: str | None = None,
    ) -> list[HpsComputeResourceSet]:
        raise RuntimeError("This method is not available")


class DynamicHpsProject:
    def __init__(
        self,
        persisted_project: HpsProject,
        hps_blob_manager: HpsBlobManager,
        hps_authenticator: IHpsAuthenticator,
    ) -> None:
        self._persisted_project = persisted_project
        self._hps_blob_manager = hps_blob_manager
        self._hps_authenticator = hps_authenticator

    def __eq__(self, value: object) -> bool:
        if isinstance(value, DynamicHpsProject):
            return self.persisted_project == value.persisted_project
        return self.persisted_project == value

    @property
    def persisted_project(self) -> HpsProject:
        return self._persisted_project

    def _get_project(self) -> IHpsParametricStudyProject:
        # deliberate conditional import because REP/HPS is an optional dependency
        from ansys.saf.glow._hps_parametric_studies.project_impl import HpsParametricStudyProjectImpl

        if not self._persisted_project.hps_project_identifier:
            raise HpsProjectNotStartedError("The HPS project has not been started.")
        return HpsParametricStudyProjectImpl(
            self._persisted_project,
            self._hps_blob_manager,
            self._hps_authenticator,
        )

    @property
    def ui_url(self) -> str:
        return self._get_project().ui_url

    @property
    def hps_project_identifier(self) -> str:
        return self.persisted_project.hps_project_identifier

    @property
    def pickled_parameters(self) -> list[str]:
        return self.persisted_project.pickled_parameters

    @property
    def hps_server_url(self) -> str | None:
        return self.persisted_project.hps_server_url

    @property
    def client_id(self) -> str | None:
        return self.persisted_project.client_id

    @property
    def finished(self) -> bool:
        return self._get_project().finished

    @property
    def exists(self) -> bool:
        return self._get_project().exists

    @staticmethod
    def get_compute_resource_sets(
        hps_server_url: str | None = None,
        client_id: str | None = None,
    ) -> list[HpsComputeResourceSet]:
        # deliberate conditional import because REP/HPS is an optional dependency
        from ansys.saf.glow._hps_parametric_studies.system_info_impl import HpsSystemInformationImpl

        return HpsSystemInformationImpl.get_compute_resource_sets(
            hps_server_url=hps_server_url,
            client_id=client_id,
        )


class DynamicHpsParametricStudyProject(DynamicHpsProject):
    def get_status_of_design_points(self, design_points: HpsDesignPointSelection | None = None) -> list[IHpsJobStatus]:
        return self._get_project().get_status_of_design_points(design_points)

    def fetch_values_of_parameters(
        self,
        parameter_names: list[str],
        design_points: HpsDesignPointSelection | None = None,
    ) -> list[list[Any]]:
        values = self._get_project().fetch_values_of_parameters(parameter_names, design_points)
        result: list[list[Any]] = []
        for value in values:
            parameter_values: list[Any] = []
            for v in value:
                parameter_values.append(v)
            result.append(parameter_values)
        return result

    def fetch_values_of_parameter(
        self,
        parameter_name: str,
        design_points: HpsDesignPointSelection | None = None,
    ) -> list[Any]:
        return self.fetch_values_of_parameters([parameter_name], design_points)[0]

    def __getattr__(self, name: str) -> list[Any]:
        attrs = self._get_project().get_attribute(name)
        result: list[Any] = []
        for attr in attrs:
            result.append(attr)
        return result


class DynamicHpsSimpleProject(DynamicHpsProject):
    @property
    def status(self) -> IHpsJobStatus:
        return self._get_project().get_status_of_design_points()[0]

    def __getattr__(self, name: str) -> Any:
        attr = self._get_project().get_attribute(name)[0]
        return attr
