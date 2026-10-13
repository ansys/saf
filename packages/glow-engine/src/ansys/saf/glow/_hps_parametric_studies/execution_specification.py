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

from collections.abc import Callable, Mapping, Sequence
import copy
import inspect
from pathlib import Path
import tempfile
from types import ModuleType
from typing import Any

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._core.get_step_resource_directory import get_step_resource_directory
from ansys.saf.glow._executor.local import transaction_local
from ansys.saf.glow._hps_parametric_studies.api import HpsParametricStudyProject, HpsSimpleProject
from ansys.saf.glow._hps_parametric_studies.base import (
    HpsInputDirectory,
    HpsInputDirectorySpecification,
    HpsInputFile,
    HpsInputFileSpecification,
    HpsOutputDirectorySpecification,
    HpsOutputFileSpecification,
)
from ansys.saf.glow._hps_parametric_studies.study_definition import (
    ResourceRequirements,  # TODO: move out of here or create interface! It's bringing HPS dependencies, while
    # the rest of study_definition imports are deliberately conditional in this file.
)
from ansys.saf.glow._utilities.compute_source_root import compute_source_root
from ansys.saf.product_configuration.interfaces import Software


class HpsExecutionSpecification:
    """Specification of a HPS job or parametric study.

    Parameters
    ----------

    function: Callable[..., Any] | str
        The function to be executed in the HPS job or parametric study or a string referring to a function.
        The string is of the form ``<module_name>.<function_name>``

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

    module: ModuleType | Path, optional
        The module that needs to be transferred to HPS to ensure that the function can be executed.
        The module must include ``function``.
        By default the source code transferred to HPS for execution is the content of the ``scripts`` directory located
        in the directory containing the step definition module
        that contains the transaction method that calls ``execute``.
        If ``module`` is a ``Path`` object then it should refer to a file or directory in the solution source tree
        where the path is relative to the root of the solution source tree.
        For example if you want to ensure the directory
        ``<your solution>/src/ansys/solutions/fastcar/simulation`` is transferred to HPS then you can pass
        ``Path("ansys/solutions/fastcar/simulation")`` as the ``module`` argument.

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
    """

    def __init__(
        self,
        function: Callable[..., Any] | str,
        output_parameters: dict[str, type | HpsOutputFileSpecification | HpsOutputDirectorySpecification],
        module: ModuleType | Path | None = None,
        max_execution_time: float = 604800,  # default to 1 week
        resource_requirements: ResourceRequirements | None = None,
        dependencies: list[str] | None = None,
        python_version: str | None = None,
        products: list[Software] | None = None,
        use_ansys_python: bool = False,
        hps_server_url: str | None = None,
    ):
        self._function = function
        self._module = module

        self._start_method_arguments: dict[str, Any] = {
            "output_parameters": output_parameters,
            "max_execution_time": max_execution_time,
            "resource_requirements": resource_requirements,
            "dependencies": dependencies,
            "python_version": python_version,
            "products": products,
            "use_ansys_python": use_ansys_python,
            "hps_server_url": hps_server_url,
            "use_product_environment": False,
            "use_latest_python": python_version is None,
        }

    def execute(self, **kwargs: Any) -> HpsSimpleProject:
        """Execute the specified function with the provided arguments.

        Parameters
        ----------
        **kwargs : Any
            The arguments to pass to the function.
            Arguments of the types ``Path``, ``EntityHandle```, ``HpsInputFileSpecification``
            and ``HpsInputDirectorySpecification``
            are treated as input files or directories. The referenced files and directories
            are transferred to HPS for job execution.  ``Path`` values are then passed to the
            job function referencing the files and directories in the HPS execution environment.
            All other arguments are passed unchanged to the job function.
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            start_method_args = copy.deepcopy(self._start_method_arguments)
            self._extend_dictionary_with_script(kwargs, kwargs, temp_dir)
            start_method_args["input_values"] = kwargs
            return HpsSimpleProject.start_hps_job(**start_method_args)

    def execute_parametric_study(self, **kwargs: Any) -> HpsParametricStudyProject:
        """Execute a parametric study with the specified function and arguments.

        Parameters
        ----------
        **kwargs : Any
            The arguments to pass to the function.
            Arguments of the types ``Path`` ``EntityHandle```, ``HpsInputFileSpecification``
            and ``HpsInputDirectorySpecification``
            are treated as input files or directories. The referenced files and directories
            are transferred to HPS for job execution.  ``Path`` values are then passed to the
            job function referencing the files and directories in the HPS execution environment.
            All other arguments must be list values. These lists must of the same length.
            Each combination of list values is used to create a design point for the parametric study.

        """
        common_input_files: dict[str, HpsInputFile | HpsInputDirectory] = {}
        input_parameter_values: Mapping[str, Sequence[Any]] = {}

        for k, v in kwargs.items():
            if self._is_input_file_reference(v):
                common_input_files[k] = v
            elif isinstance(v, list | tuple):
                input_parameter_values[k] = v
            else:
                raise ValueError(
                    f"Parameter '{k}' has value '{v}' of type '{type(v)}' which is not valid. "
                    "For parametric studies the parameter values must be either a list, tuple, "
                    "Path, EntityHandle, HpsInputFileSpecification "
                    "or HpsInputDirectorySpecification",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            start_method_args = copy.deepcopy(self._start_method_arguments)
            start_method_args["common_input_files"] = self._extend_dictionary_with_script(
                common_input_files,
                kwargs,
                temp_dir,
            )
            start_method_args["input_parameter_values"] = input_parameter_values
            return HpsParametricStudyProject.start_hps_parametric_study(**start_method_args)

    def _is_input_file_reference(self, value: Any) -> bool:
        return isinstance(
            value,
            Path | EntityHandle | HpsInputFileSpecification | HpsInputDirectorySpecification,
        )

    def _extend_dictionary_with_script(
        self,
        dictionary: dict[str, Any],
        kwargs: dict[str, Any],
        temp_dir: str,
    ) -> dict[str, Any]:
        dictionary["script"] = self._create_script(kwargs, temp_dir)
        dictionary["module"] = self._create_module_specification()
        return dictionary

    def _create_script(self, input_arguments: dict[str, Any], temp_dir: str):
        if callable(self._function):
            function_module = inspect.getmodule(self._function)

            if function_module is None:
                raise ValueError("Function module could not be determined.")
            function_python_module_reference = function_module.__name__
            function_python_reference = f"{function_python_module_reference}.{self._function.__name__}"
        else:
            # IMPORTANT: when the function is passed as a string then
            # then we must assume that the function is not importable into the GLOW API server
            # so we don't process here by importing it!!
            function_python_reference = self._function
            function_python_module_reference = ".".join(self._function.split(".")[:-1])

        function_arguments = ",\n                ".join(
            (
                f"{k}=Path({self._hps_side_parameter_value(k)})"
                if self._is_input_file_reference(v)
                else f"{k}={self._hps_side_parameter_value(k)}"
            )
            for k, v in input_arguments.items()
        )

        script_contents = f"""
import inspect
from pathlib import Path
from ansys.saf.glow.hps_execution import HpsExecution
import {function_python_module_reference}

class FunctionExecution(HpsExecution):
    def execute(self):
        sig = inspect.signature({function_python_reference})
        if "context" in sig.parameters:
            return {function_python_reference}(
                context=self.context,
                {function_arguments})
        else:
            return {function_python_reference}(
                {function_arguments})
        """
        script_path = Path(temp_dir) / "script.py"
        script_path.write_text(script_contents)
        return script_path

    @classmethod
    def _hps_side_parameter_value(cls, k: str) -> str:
        return f"self.context.input_parameters['{k}']"

    @classmethod
    def _compute_evalution_path_for_module(cls, module: ModuleType) -> str:
        return "/".join(module.__name__.split("."))

    def _create_module_specification(self):
        if self._module is None:
            src_root = compute_source_root(transaction_local.settings.computed_definition_module)
            module_path = get_step_resource_directory(transaction_local.step_type, "scripts")
            evaluation_path = module_path.relative_to(src_root).as_posix()
        elif isinstance(self._module, Path):
            # IMPORTANT: when the self._module is passed as a path then
            # then we must assume that the self._module is not importable into the GLOW API server
            # so we don't process here by importing it!!
            src_root = compute_source_root(transaction_local.settings.computed_definition_module)
            module_path = src_root / self._module
            if not module_path.exists():
                raise ValueError(
                    f"Module file path {module_path} does not exist. "
                    f"Solution source root is {src_root}. Supplied module path is {self._module}.",
                )
            evaluation_path = (self._module).as_posix()
        elif self._module.__file__ is None:
            spec = self._module.__spec__
            if spec is None:
                raise ValueError("module spec could not be determined.")
            search_locations = spec.submodule_search_locations
            if search_locations is None or len(search_locations) == 0:
                raise ValueError("submodule search locations could not be determined.")
            module_path = Path(search_locations[-1])
            evaluation_path = self._compute_evalution_path_for_module(self._module)
        else:
            module_path = Path(self._module.__file__)
            if module_path.name == "__init__.py":
                module_path = module_path.parent
                evaluation_path = self._compute_evalution_path_for_module(self._module)
            else:
                evaluation_path = self._compute_evalution_path_for_module(self._module) + ".py"

        return self._create_input_specification(module_path, evaluation_path)

    def _create_input_specification(self, module_path: Path, evaluation_path: str):
        if module_path.is_dir():
            module_specification = HpsInputDirectorySpecification(module_path, evaluation_path)
        else:
            module_specification = HpsInputFileSpecification(module_path, evaluation_path)
        return module_specification
