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

from collections.abc import Iterator, Mapping, Sequence
from typing import Any, cast

from ansys.saf.glow._executor.local import transaction_local
from ansys.saf.glow._hps_auth.hps_authenticator import create_hps_authenticator
from ansys.saf.glow._hps_parametric_studies.base import (
    DynamicHpsParametricStudyProject,
    DynamicHpsSimpleProject,
    HpsComputeResourceSet,
    HpsDesignPointSelection,
    HpsInputDirectory,
    HpsInputFile,
    HpsOutputDirectorySpecification,
    HpsOutputFileSpecification,
    HpsParametricStudyProjectBase,
    HpsSimpleProjectBase,
    IHpsJobStatus,
)
from ansys.saf.glow._hps_parametric_studies.study_definition import (
    PythonSourceSpecification,
    ResourceRequirements,  # TODO: move out of here or create interface! It's bringing HPS dependencies, while
    # the rest of study_definition imports are deliberately conditional in this file.
)
from ansys.saf.product_configuration.interfaces import Software


class HpsSimpleProject(HpsSimpleProjectBase):
    """A reference to a HPS project containing one job.

    Notes
    -----
        When instances of this class reference an HPS project
        they have attributes for the parameters and files of the job contained in the project.
        The names of these attributes are those used for these entities in HPS and passed to
        :py:class:`~ansys.saf.glow.solution.hps.HpsSimpleProject.start_hps_job`.
        For example if the job has a parameter named ``temperature`` then
        the instance will have an attribute named ``temperature`` which
        will return the value of the parameter.
    """

    @classmethod
    def start_hps_job(
        cls,
        input_values: dict[str, Any],
        output_parameters: Mapping[
            str,
            type | HpsOutputFileSpecification | HpsOutputDirectorySpecification,
        ],
        max_execution_time: float = 604800,  # default to one week
        name: str | None = None,
        resource_requirements: ResourceRequirements | None = None,
        dependencies: list[str] | None = None,
        use_product_environment: bool | None = None,
        python_version: str | None = None,
        product_environment_version: str | None = None,
        products: list[Software] | None = None,
        use_ansys_python: bool = False,
        hps_server_url: str | None = None,
        client_id: str | None = None,
        use_latest_python: bool = False,
    ) -> "HpsSimpleProject":
        """This method creates a new HPS project containing a job and returns a
        :py:class:`~ansys.saf.glow.solution.hps.HpsSimpleProject` object referring to that project.

        See |saf-docs-hps-job-submit-single-ref|_ for examples and further documentation of this method.

        To understand how the method supports the use of PyAnsys packages
        see |saf-docs-hps-job-dependencies-ref|_ on the SAF product environment.

        Parameters
        ----------
        input_values : dict[str, Any]

            This argument defines the initial input data of the job.
            Each key is the name of the parameter or file in HPS.

            For each :py:class:`~ansys.saf.glow.solution.hps.HpsInputFileSpecification`, ``Path`` or
            :py:class:`~ansys.bdm.api.EntityHandle` value a HPS file will be created.
            For :py:class:`~ansys.saf.glow.solution.hps.HpsInputDirectorySpecification` values a
            directory in HPS will be created.
            For all other types a HPS parameter will be created.

            Use the :py:class:`~ansys.saf.glow.solution.hps.HpsInputFileSpecification`
            class to define the file with an explicit path within
            the current working directory of a design point evaluation running in HPS. For ``Path`` and
            :py:class:`~ansys.bdm.api.EntityHandle`
            values the file is copied to the current working directory of a design point evaluation
            running in HPS and has the same file name as the source.

            This dictionary must contain an entry with key ``script`` which specifies an input file which is a
            python module that is run to evaluate a design point.
            See |saf-docs-hps-function-ref|_ (GLOW HPS Scripts) to understand the form of those scripts.

        output_parameters : dict[str, type | HpsOutputFileSpecification | HpsOutputDirectorySpecification]

            This argument specifies the required output parameters and files.
            Each item represents either an output parameter or an output file.
            Each key is the name of the parameter or file in HPS.
            :py:class:`~ansys.saf.glow.solution.hps.HpsOutputFileSpecification`
            values are used to represent output files
            (HPS parameters are not created for them).
            :py:class:`~ansys.saf.glow.solution.hps.HpsOutputDirectorySpecification`
            values are used to represent output directories.
            Python ``type`` values are used to represent HPS output parameters.

        max_execution_time: float, optional
            The maximum execution time of the job in seconds.
            The default is one week.

        resource_requirements: ResourceRequirements, optional
            The resource requirements the job. Uses HPS default values when
            values are not provided.

        dependencies: list[str], optional
            A list of
            `pip requirement specifier strings <https://pip.pypa.io/en/stable/reference/requirement-specifiers/#requirement-specifiers>`_
            indicating the python packages that are required to evaluate a design point.
            Use of this parameter will trigger the creation of a Python virtual environment for the job.
            The job will not use the SAF Product Environment virtual environment.
            Use the ``python_version`` parameter to specify the version of Python for the virtual environment.
            The ``dependencies`` argument does not determine what products and applications are available for
            design point evaluation, use the ``products`` argument for that purpose.
            See |saf-docs-hps-job-dependencies-ref|_ for details on specifying python package dependencies for jobs.

        use_product_environment: bool, optional
            Whether to use the SAF Product Environment virtual environment for the job.
            By default, the SAF Product Environment virtual environment is used if the ``dependencies``
            argument is not set or is empty.
            By default, the SAF Product Environment virtual environment is not used if the ``dependencies``
            argument is set to a non-empty list.

        python_version: str, optional
            The version of Python to use for the job when the SAF Product environment is not used.
            The string is of the form "major.minor" where major and minor are integers.
            The default value is "3.11".

        product_environment_version: str, optional
            The version of the SAF Product Environment to use for the job.
            The format of the version string of a SAF Product Environment has not yet been determined.

        products: list[Software], optional
            A list of products or applications required for the job.
            The list items must be of type :py:class:`~ansys.saf.product_configuration.interfaces.Software`.
            The default value is an empty list.
            The list should not contain entries for python or the SAF Product Environment.
            See |saf-docs-hps-job-specifiying-required-products-ref|_ for details on specifying product
            requirements for jobs.

        use_ansys_python: bool, optional
            Whether to use Ansys Python instead of Python for the job when the SAF Product environment is not used.
            The selected Ansys Python version is determined by python_version.
            The default value is False.

        hps_server_url: str, optional
            HPS endpoint that the HPS client will connect to.

        client_id: str, optional
            Client ID of the HPS system in Keycloak.

        Returns
        -------
        HpsSimpleProject
            A reference to a HPS project that can be stored in a GLOW step field.
        """
        # deliberate conditional import because REP/HPS is an optional dependency
        from ansys.saf.glow._hps_parametric_studies.study_definition import HpsParametricStudyDefinition

        study_builder = HpsParametricStudyDefinition(
            hps_server_url=hps_server_url,
            client_id=client_id,
            name=name,
        )
        common_input_files, input_parameter_values = study_builder.split_simple_input_values(input_values)
        python_source = PythonSourceSpecification(
            use_product_environment=use_product_environment,
            use_ansys_python=use_ansys_python,
            python_version=python_version,
            product_environment_version=product_environment_version,
            use_latest_python=use_latest_python,
        )
        study_builder.add_study_to_project(
            max_execution_time=max_execution_time,
            common_input_files=common_input_files,
            input_parameter_values=input_parameter_values,
            output_parameters=output_parameters,
            hps_blob_manager=transaction_local.hps_blob_manager,
            resource_requirements=resource_requirements,
            input_error_message_override="input_values must be a dictionary with string keys",
            dependencies=dependencies,
            products=products,
            python_source=python_source,
        )
        hps_authenticator = create_hps_authenticator(transaction_local.settings, transaction_local.access_token)
        return cast(
            "HpsSimpleProject",
            DynamicHpsSimpleProject(
                HpsSimpleProject(
                    hps_project_identifier=study_builder.hps_project_identifier,
                    hps_server_url=hps_server_url,
                    client_id=client_id,
                    file_parameters_using_handles=study_builder.file_parameters_using_handles,
                    pickled_parameters=study_builder.pickled_parameters,
                ),
                hps_blob_manager=transaction_local.hps_blob_manager,
                hps_authenticator=hps_authenticator,
            ),
        )

    @property
    def status(self) -> IHpsJobStatus:
        """Get the status of the job in the project."""
        raise RuntimeError("This property is not available.")

    @staticmethod
    def get_compute_resource_sets(
        hps_server_url: str | None = None,
        client_id: str | None = None,
    ) -> list[HpsComputeResourceSet]:
        """Get available compute resource sets in HPS.

        Parameters
        ----------
        hps_server_url: str, optional
            HPS endpoint that the HPS client will connect to.

        client_id: str, optional
            Client ID of the HPS system in Keycloak.

        Returns
        -------
        list[HpsComputeResourceSet]
            A list of objects that represent the available resources to execute an HPS job.
        """
        return DynamicHpsSimpleProject.get_compute_resource_sets(
            hps_server_url=hps_server_url,
            client_id=client_id,
        )


class HpsParametricStudyProject(HpsParametricStudyProjectBase):
    """A reference to a parametric study project in HPS.

    Notes
    -----
        When instances of this class reference an HPS project
        they have attributes for the parameters and files of the project.
        The names of these attributes are those used for these entities in HPS and passed to
        :py:class:`~ansys.saf.glow.solution.hps.HpsParametricStudyProject.start_hps_parametric_study`.
        The values of the attributes are lists of values for the parameters or files across the design points.
        The ordering of the lists corresponds to the ordering of the input parameters values passed to
        :py:class:`~ansys.saf.glow.solution.hps.HpsParametricStudyProject.start_hps_parametric_study`.

        For parameters the attributes will return a list of ``str``, ``int``, ``float`` or ``bool`` values.
        An output parameter value will be ``None`` if a given design point has not successfully evaluated.
        A file value will be ``None`` if the file does not exist in HPS.

        For example if the project has a parameter named ``temperature`` then
        the instance will have an attribute named ``temperature`` which
        will return a list of values of the parameter across the design points in the project.
    """

    @classmethod
    def start_hps_parametric_study(
        cls,
        common_input_files: dict[str, HpsInputFile | HpsInputDirectory],
        input_parameter_values: Iterator[Mapping[str, Any]] | Mapping[str, Sequence[Any]],
        output_parameters: Mapping[
            str,
            type | HpsOutputFileSpecification | HpsOutputDirectorySpecification,
        ],
        max_execution_time: float = 604800,
        name: str | None = None,
        resource_requirements: ResourceRequirements | None = None,
        dependencies: list[str] | None = None,
        use_product_environment: bool | None = None,
        python_version: str | None = None,
        product_environment_version: str | None = None,
        products: list[Software] | None = None,
        use_ansys_python: bool = False,
        hps_server_url: str | None = None,
        client_id: str | None = None,
        use_latest_python: bool = False,
    ) -> "HpsParametricStudyProject":
        # fmt: off
        """This method creates a new HPS project containing a parametric study and returns
        a :py:class:`~ansys.saf.glow.solution.hps.HpsParametricStudyProject` object referring to the project.

        See |saf-docs-hps-parametric-study-ref|_ for examples of calling this method.

        To understand how the method supports the use of PyAnsys packages
        see |saf-docs-hps-job-dependencies-ref|_ on the SAF product environment.
        The parametric study API is identical to the job API in this aspect: 'job'
        is equivalent to 'design point evaluation'
        and :py:meth:`~ansys.saf.glow.solution.hps.HpsSimpleProject.start_hps_job` is equivalent to
        ``start_hps_parametric_study``.

        Parameters
        ----------

        common_input_files :
    dict[str, HpsInputFileSpecification | HpsInputDirectorySpecification | Path]

            This dictionary contains references to files that are common to all design
            points.
            Use the :py:class:`~ansys.saf.glow.solution.hps.HpsInputFileSpecification` and
            :py:class:`~ansys.saf.glow.solution.hps.HpsInputDirectorySpecification`
            classes to define the file or directory with an explicit path within
            the current working directory of a design point evaluation running in HPS. For ``Path`` and
            :py:class:`~ansys.bdm.api.EntityHandle`
            values the file is copied to the current working directory of a design point evaluation
            running in HPS and has the same file name as the source.

            This dictionary must contain an entry with key ``script`` which specifies an input file which is a
            python module that is run to evaluate a design point.
            See |saf-docs-hps-function-ref|_ (GLOW HPS Scripts) to understand the form of those scripts.
            The parametric study API is identical to the job API in this aspect:
            'job' is equivalent to 'design point evaluation'
            and :py:meth:`~ansys.saf.glow.solution.hps.HpsSimpleProject.start_hps_job` is equivalent to
            ``start_hps_parametric_study``.

        input_parameter_values : Iterator[dict[str,Any]]|dict[str,list[Any]]

            This argument defines the initial input design point data of the study.
            The argument is either an iterator that returns a stream of dictionaries of
            input values or a dictionary of lists of values. The keys to the
            dictionaries are arbitrary input parameter names. In the case of iterator
            each iteration defines a design point and the keys should be the same on
            every iteration. In the other case (a simple dictionary) the dictionary's
            values are lists where the lists should have the same lengths. The set of
            list items with the same index defines a design point.

        output_parameters : dict[str, type | HpsOutputFileSpecification | HpsOutputDirectorySpecification]

            This argument specifies the required output parameters, files and directories.
            Each item represents either an output parameter, an output file or an output directory.
            The key is the name of the parameter, file or directory in HPS.
            :py:class:`~ansys.saf.glow.solution.hps.HpsOutputFileSpecification`
            values are used to represent output files and
            :py:class:`~ansys.saf.glow.solution.hps.HpsOutputDirectorySpecification`
            values are used to represent output directories,
            (HPS parameters are not created for them).
            Python ``type`` values are used to represent HPS output parameters.

        max_execution_time: float, optional
            The maximum execution time of each job in seconds.
            The default is one week.

        resource_requirements: ResourceRequirements, optional
            The resource requirements of each job. Uses HPS default values when
            values are not provided.

        dependencies: list[str], optional
            A list of
            `pip requirement specifier strings <https://pip.pypa.io/en/stable/reference/requirement-specifiers/#requirement-specifiers>`_
            indicating the python packages that are required to evaluate a design point.
            Use of this parameter will trigger the creation of a Python virtual environment for each design point and
            the design point evaluation
            will not use the SAF Product Environment virtual environment.
            Use the ``python_version`` parameter to specify the version of Python for the virtual environment.
            The ``dependencies`` argument does not determine what products and applications
            are available for design point evaluation, use the ``products`` argument for that purpose.
            See |saf-docs-hps-job-dependencies-ref|_ for details on specifying python package dependencies for jobs
            (the parametric study API is identical to the job API in this aspect:
            'job' is equivalent to 'design point evaluation')

        use_product_environment: bool, optional
            Whether to use the SAF Product Environment virtual environment for design point evaluation.
            By default, the SAF Product Environment virtual environment is used if the ``dependencies``
            argument is not set or is empty.
            By default, the SAF Product Environment virtual environment is not used if the ``dependencies``
            argument is set to a non-empty list.

        python_version: str, optional
            The version of Python to use for design point evaluation when the SAF Product environment is not used.
            The string is of the form "major.minor" where major and minor are integers.
            The default value is "3.11".

        product_environment_version: str, optional
            The version of the SAF Product Environment to use for design point evaluation.
            The format of the version string of a SAF Product Environment has not yet been determined.

        products: list[Software], optional
            A list of products or applications required for design point evaluation.
            The list items must be of type :py:class:`~ansys.saf.product_configuration.interfaces.Software`.
            The default value is an empty list.
            The list should not contain entries for python or the SAF Product Environment.
            See |saf-docs-hps-job-specifiying-required-products-ref|_ for details on specifying product
            requirements for jobs (the parametric study API is identical to the job API in this aspect:
            'job' is equivalent to 'design point evaluation').

        use_ansys_python: bool, optional
            Whether to use Ansys Python instead of Python for the job when the SAF Product environment is not used.
            The selected Ansys Python version is determined by python_version.
            The default value is False.

        hps_server_url: str, optional
            HPS endpoint that the HPS client will connect to.

        client_id: str, optional
            Client ID of the HPS system in the OAuth system.

        Returns
        -------
        HpsParametricStudyProject
            A serializable reference to the created project."""
        # fmt: on
        # deliberate conditional import because REP/HPS is an optional dependency
        from ansys.saf.glow._hps_parametric_studies.study_definition import HpsParametricStudyDefinition

        study_builder = HpsParametricStudyDefinition(
            hps_server_url=hps_server_url,
            client_id=client_id,
            name=name,
        )
        python_source = PythonSourceSpecification(
            use_product_environment=use_product_environment,
            use_ansys_python=use_ansys_python,
            python_version=python_version,
            product_environment_version=product_environment_version,
            use_latest_python=use_latest_python,
        )
        study_builder.add_study_to_project(
            max_execution_time,
            common_input_files,
            input_parameter_values,
            cast(
                "dict[str, type | HpsOutputFileSpecification | HpsOutputDirectorySpecification]",
                output_parameters,
            ),
            transaction_local.hps_blob_manager,
            resource_requirements=resource_requirements,
            python_source=python_source,
            dependencies=dependencies,
            products=products,
        )
        hps_authenticator = create_hps_authenticator(transaction_local.settings, transaction_local.access_token)
        return cast(
            "HpsParametricStudyProject",
            DynamicHpsParametricStudyProject(
                HpsParametricStudyProject(
                    hps_project_identifier=study_builder.hps_project_identifier,
                    hps_server_url=hps_server_url,
                    client_id=client_id,
                    file_parameters_using_handles=study_builder.file_parameters_using_handles,
                    pickled_parameters=study_builder.pickled_parameters,
                ),
                hps_blob_manager=transaction_local.hps_blob_manager,
                hps_authenticator=hps_authenticator,
            ),
        )

    def get_status_of_design_points(self, design_points: HpsDesignPointSelection | None = None) -> list[IHpsJobStatus]:
        """Get the status of the design points in the study. The order of the returned value is the order of the
        design points supplied to ``HpsParametricStudyDefinition.add_study_to_project``."""
        raise RuntimeError("This method is not available.")

    def fetch_values_of_parameter(
        self,
        parameter_name: str,
        design_points: HpsDesignPointSelection | None = None,
    ) -> list[Any]:
        """A method that returns the values of a given named parameter or the references to instances of a
        given named file across a set of design points.
        If you wish to fetch more than one parameter or file use the ``fetch_values_of_parameters`` method.

        Parameters
        ==========

        parameter_name: str

            The parameter or file to be fetched.
            The string ``index`` can be used which represents the index of the design point in
            the input parameter set.

        design_points : HpsDesignPointSelection, optional
            The set of design points for which parameter values or files are to be fetched. The ordering of the list
            returned by fetch corresponds to the ordering defined by ``design_points``. If ``design_points`` is not
            set all design points are returned and the ordering corresponds
            to the ordering used to create the project.

        Returns
        =======
        list[Any]
            The values of a given named parameter or the references to instances of a given named file across the design
            point ordering specified by
            ``design_points``. If a file has been requested then the returned list will contain
            :py:class:`~ansys.bdm.api.EntityHandle`
            objects where files exist or ``None`` where they do not.
            If a parameter has been requested then the returned
            list will contain ``None`` values for design points which have not successfully evaluated.
        """
        raise RuntimeError("This method is not available.")

    def fetch_values_of_parameters(
        self,
        parameter_names: list[str],
        design_points: HpsDesignPointSelection | None = None,
    ) -> list[list[Any]]:
        """A method that returns the values of a set of named parameters or files across a set of design points.
        The files values are returned as :py:class:`~ansys.bdm.api.EntityHandle` objects.

        Parameters
        ==========

        parameter_names: list[str]

            The parameters or files that are to be fetched.
            The string ``index`` can be included which represents the index of the design point in
            the input parameter set.

        design_points : HpsDesignPointSelection, optional
            The set of design points for which parameter values are to be fetched. The ordering of
            the list returned by fetch
            corresponds to the ordering defined by design_points. If design_points is not set all
            design points are returned
            and the ordering corresponds to the ordering used to create the project.

        Returns
        =======

        list[Any]

            A list of lists of values of the requested files or parameters. Each item in the returned list
            corresponds to parameter or file names at the same index in ``parameter_names``. Each sublist
            contains values for the named parameter or file.
            The order of the sublists corresponds to the design point ordering specified by
            ``design_points``. Where the sublist corresponds to a file the sublist will contain
            :py:class:`~ansys.bdm.api.EntityHandle`
            objects where files exist or ``None`` where they do not.
            Where the sublist corresponds to a parameter the sublist will contain ``None`` values for
            design points which have not successfully evaluated.

        """
        raise RuntimeError("This method is not available.")

    @staticmethod
    def get_compute_resource_sets(
        hps_server_url: str | None = None,
        client_id: str | None = None,
    ) -> list[HpsComputeResourceSet]:
        """Get available compute resource sets in HPS.

        Parameters
        ----------
        hps_server_url: str, optional
            HPS endpoint that the HPS client will connect to.

        client_id: str, optional
            Client ID of the HPS system in Keycloak.

        Returns
        -------
        list[HpsComputeResourceSet]
            A list of objects that represent the available resources to execute an HPS job.
        """
        return DynamicHpsParametricStudyProject.get_compute_resource_sets(
            hps_server_url=hps_server_url,
            client_id=client_id,
        )


NO_HPS_SIMPLE_PROJECT = HpsSimpleProject(
    hps_project_identifier="",
    hps_server_url=None,
    client_id=None,
)
"""HpsSimpleProject
    A placeholder for a reference to a HPS Project containing a single job.
    This value does not refer to a an existing project."""

NO_HPS_STUDY_PROJECT = HpsParametricStudyProject(
    hps_project_identifier="",
    hps_server_url=None,
    client_id=None,
)
"""HpsParametricStudyProject
    A placeholder for a reference to a HPS Project containing a parametric study.
    This value does not refer to a an existing project."""
