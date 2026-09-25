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

from enum import Enum
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import cast

from ansys.bdm.api import NO_ENTITY, EntityHandle
from pydantic import Field

from ansys.saf.glow._hps_parametric_studies.api import (
    NO_HPS_SIMPLE_PROJECT,
    NO_HPS_STUDY_PROJECT,
)
from ansys.saf.glow._hps_parametric_studies.base import HpsDesignPointSelection
from ansys.saf.glow.solution import (
    Solution,
    StepModel,
    StepsModel,
    StepSpec,
    long_running,
    transaction,
)
from ansys.saf.glow.solution.hps import (
    HpsExecutionSpecification,
    HpsInputDirectorySpecification,
    HpsInputFileSpecification,
    HpsJobEvaluationStatus,
    HpsOutputDirectorySpecification,
    HpsOutputFileSpecification,
    HpsParametricStudyProject,
    HpsSimpleProject,
)
from tests.mocks.solution_with_hps_python_script.method_assets import data_transfer_script
from tests.mocks.solution_with_hps_python_script.method_assets.data_transfer_script import AddInput, AddOutput


class FileJobStep(StepModel):
    """simple HPS job which uses files to get data in and out of the job"""

    class State(Enum):
        """states in which the step can exist."""

        Calculating = "calculating"
        ResultAvailable = "result-available"
        ResultNotAvailable = "result-not-available"

    step_state: State = Field(default=State.ResultNotAvailable, strict=False)

    file_path: str = ""
    result_file_content: str = ""
    input_file: EntityHandle = NO_ENTITY
    add_script: EntityHandle = NO_ENTITY
    result_handle: EntityHandle = NO_ENTITY
    return_type: str = "EntityHandle"
    hps_project: HpsSimpleProject = NO_HPS_SIMPLE_PROJECT
    time_to_generate_the_output_file: float = 0.0
    collect_interval: int = 0
    inputs_outputs_result: str = ""

    @transaction(
        self=StepSpec(
            upload=["hps_project", "step_state"],
            download=[
                "input_file",
                "add_script",
                "time_to_generate_the_output_file",
                "collect_interval",
                "return_type",
            ],
        ),
    )
    def start_job(self) -> None:
        """Compute the sum of two numbers."""
        self.hps_project = HpsSimpleProject.start_hps_job(
            input_values={
                "script": self.add_script,
                "custom_input_file": self.input_file,
                "time_to_generate_the_output_file": self.time_to_generate_the_output_file,
            },
            output_parameters={
                "result": HpsOutputFileSpecification(
                    collect_interval=self.collect_interval,
                ),
            },
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )
        self.step_state = FileJobStep.State.Calculating

    @transaction(
        self=StepSpec(
            upload=["hps_project", "step_state"],
            download=[
                "input_file",
                "add_script",
                "time_to_generate_the_output_file",
                "collect_interval",
                "return_type",
            ],
        ),
    )
    @long_running
    def start_job_with_custom_hps_params(self) -> None:
        self.hps_project = HpsSimpleProject.start_hps_job(
            input_values={
                "script": self.add_script,
                "custom_input_file": self.input_file,
                "time_to_generate_the_output_file": self.time_to_generate_the_output_file,
            },
            output_parameters={
                "result": HpsOutputFileSpecification(
                    collect_interval=self.collect_interval,
                ),
            },
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
            hps_server_url="https://localhost:8443/hps",
            client_id="rep-jms-web",
        )
        self.step_state = FileJobStep.State.Calculating

    @transaction(
        self=StepSpec(
            upload=["hps_project", "step_state"],
        ),
    )
    @long_running
    def start_job_with_input_and_output_sources(self) -> None:
        self.hps_project = HpsSimpleProject.start_hps_job(
            input_values={
                "script": self.transaction.get_asset_entity_handle("input_and_output_sources.py"),
                "input_dir": HpsInputDirectorySpecification(self.transaction.get_asset_entity_handle("asset_dir")),
                "input_dir_eval_path": HpsInputDirectorySpecification(
                    self.transaction.get_asset_entity_handle("another_asset_dir"),
                    evaluation_path="subdir/sub",
                ),
                "input_zip": HpsInputFileSpecification(self.transaction.get_asset_entity_handle("asset_dir.zip")),
                "input_zip_eval_path": HpsInputFileSpecification(
                    self.transaction.get_asset_entity_handle("asset_dir.zip"),
                    evaluation_path="input_zip_dir/asset_dir.zip",
                ),
            },
            output_parameters={
                "input_dir_txt": str,
                "input_dir_eval_path_txt": str,
                "input_zip_txt": str,
                "output_dir": HpsOutputDirectorySpecification(),
                "output_dir_eval_path": HpsOutputDirectorySpecification(evaluation_path="output_sub_dir"),
                "output_zip": HpsOutputFileSpecification(),
                "output_zip_eval": HpsOutputFileSpecification(
                    evaluation_path="output_zip_dir_eval/output.zip",
                ),
            },
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )
        self.step_state = FileJobStep.State.Calculating

    @transaction(self=StepSpec(upload=["step_state"], download=["hps_project"]))
    def query_hps(self) -> None:
        """Query the parameter study and update results."""
        was_finished = self.hps_project.finished
        status = self.hps_project.status
        if status.evaluation_status == HpsJobEvaluationStatus.EVALUATED:
            self.step_state = FileJobStep.State.ResultAvailable
        elif status.evaluation_status in [
            HpsJobEvaluationStatus.FAILED,
            HpsJobEvaluationStatus.ABORTED,
            HpsJobEvaluationStatus.TIMEOUT,
        ]:
            self.step_state = FileJobStep.State.ResultNotAvailable
        else:
            self.step_state = FileJobStep.State.Calculating

        if self.step_state == FileJobStep.State.Calculating:
            assert not was_finished
        else:
            assert self.hps_project.finished

    @transaction(self=StepSpec(upload=["result_file_content", "result_handle"], download=["step_state", "hps_project"]))
    def fetch_file(self) -> None:
        """Upload the result file."""
        if self.step_state != FileJobStep.State.ResultAvailable:
            raise RuntimeError("result not available")
        self.result_handle = cast("EntityHandle", self.hps_project.result)  # type: ignore
        self.result_file_content = self.storage_scope.get_text(self.result_handle)

    @transaction(self=StepSpec(upload=["result_file_content"], download=["step_state", "hps_project"]))
    def fetch_file_bytes(self) -> None:
        """Upload the result file content from the file bytes."""
        if self.step_state != FileJobStep.State.ResultAvailable:
            raise RuntimeError("result not available")
        result_handle = cast("EntityHandle", self.hps_project.result)  # type: ignore
        self.result_file_content = self.storage_scope.get_bytes(result_handle).decode("utf-8")

    @transaction(self=StepSpec(upload=["result_file_content"], download=["hps_project"]))
    def fetch_file_before_job_completion(self) -> None:
        """Upload the result file during the job execution."""
        self.result_file_content = ""
        result_handle = cast("EntityHandle", self.hps_project.result)  # type: ignore
        if result_handle is not None:  # type: ignore
            self.result_file_content = self.storage_scope.get_text(result_handle)

    @transaction(self=StepSpec(upload=["result_file_content"], download=["step_state", "hps_project"]))
    def get_cached_file_content(self) -> None:
        """Upload the result file content from the cached handle."""
        if self.step_state != FileJobStep.State.ResultAvailable:
            raise RuntimeError("result not available")
        result_handle = cast("EntityHandle", self.hps_project.result)  # type: ignore
        cached = self.storage_scope.get_cached(result_handle)
        self.result_file_content = cached.read_text()

    @transaction(self=StepSpec(download=["step_state", "hps_project", "file_path"]))
    def get_copy_from_handle(self) -> None:
        """Make a copy out of the result file handle."""
        if self.step_state != FileJobStep.State.ResultAvailable:
            raise RuntimeError("result not available")
        result_handle = cast("EntityHandle", self.hps_project.result)  # type: ignore
        self.storage_scope.get_copy(result_handle, Path(self.file_path))

    @transaction(self=StepSpec(upload=["result_file_content"], download=["result_handle"]))
    def retrieve_content_from_handle(self) -> None:
        self.result_file_content = self.storage_scope.get_text(self.result_handle)

    @transaction(self=StepSpec())
    def is_glow_src_readable(self) -> bool:
        import inspect

        try:
            inspect.getsource(StepSpec)
        except OSError:
            return False
        else:
            return True

    @transaction(
        self=StepSpec(
            download=["hps_project", "step_state"],
            upload=["inputs_outputs_result"],
        ),
    )
    def get_inputs_outputs_job_result(self) -> None:
        if self.step_state != FileJobStep.State.ResultAvailable:
            raise RuntimeError("result not available")

        input_outputs_dict: dict[str, str] = {}

        input_outputs_dict["input_dir_txt"] = self.hps_project.input_dir_txt  # type: ignore
        input_outputs_dict["input_dir_eval_path_txt"] = self.hps_project.input_dir_eval_path_txt  # type: ignore
        input_outputs_dict["input_zip_txt"] = self.hps_project.input_zip_txt  # type: ignore

        output_dir_handle = cast("EntityHandle", self.hps_project.output_dir)  # type: ignore
        output_file = self.storage_scope.get_cached(output_dir_handle) / "output_file.txt"
        input_outputs_dict["output_dir_txt"] = output_file.read_text()

        output_dir_eval_path_handle = cast("EntityHandle", self.hps_project.output_dir_eval_path)  # type: ignore
        output_eval_file = self.storage_scope.get_cached(output_dir_eval_path_handle) / "sub" / "sub_file.txt"
        input_outputs_dict["output_dir_eval_path_txt"] = output_eval_file.read_text()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_zip_handle = cast("EntityHandle", self.hps_project.output_zip)  # type: ignore
            output_zip = self.storage_scope.get_cached(output_zip_handle)
            shutil.unpack_archive(output_zip, format="zip", extract_dir=tmp_dir)
            input_outputs_dict["output_zip_txt"] = (Path(tmp_dir) / "dir_a" / "dir_b" / "my_file.txt").read_text()

            output_zip_eval_handle = cast("EntityHandle", self.hps_project.output_zip_eval)  # type: ignore
            output_zip_eval = self.storage_scope.get_cached(output_zip_eval_handle)
            shutil.unpack_archive(output_zip_eval, extract_dir=tmp_dir)
            input_outputs_dict["output_zip_eval_txt"] = (Path(tmp_dir) / "dir_test" / "my_other_file.txt").read_text()

        self.inputs_outputs_result = json.dumps(input_outputs_dict)


class DataTransferStep(StepModel):
    hps_simple_project: HpsSimpleProject = NO_HPS_SIMPLE_PROJECT
    result_value: int = 0
    result_positive: bool = False

    @transaction(self=StepSpec(upload=["hps_simple_project"]))
    def start_job(self) -> None:
        self.hps_simple_project = HpsSimpleProject.start_hps_job(
            input_values={
                "script": HpsInputFileSpecification(
                    source=Path(data_transfer_script.__file__),
                    evaluation_path="ansys/solutions/solution_with_hps_python_script/method_assets/data_transfer_script.py",
                ),
                "input": AddInput(4, 6),
            },
            output_parameters={"output": AddOutput},
        )

    @transaction(self=StepSpec(upload=["result_value", "result_positive"], download=["hps_simple_project"]))
    def fetch_result(self) -> None:
        while not self.hps_simple_project.finished:
            time.sleep(1)

        assert self.hps_simple_project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED

        self.result_value = self.hps_simple_project.output.result  # type: ignore
        self.result_positive = self.hps_simple_project.output.positive  # type: ignore


class SimpleSympyStep(StepModel):
    n: int = 0
    result: str = ""
    spec_name: str = ""

    @transaction(self=StepSpec(upload=["result"], download=["n", "spec_name"]))
    def compute_series(self) -> None:
        if self.spec_name == "single module":
            execution_spec = HpsExecutionSpecification(
                function="ansys.solutions.solution_with_hps_python_script.method_assets.simple_use_sympy.compute_series",
                module=Path("ansys/solutions/solution_with_hps_python_script/method_assets/simple_use_sympy.py"),
                output_parameters={"result": str},
                dependencies=["sympy==1.12.1"],
            )
        elif self.spec_name == "multiple submodules":
            execution_spec = HpsExecutionSpecification(
                function="ansys.solutions.solution_with_hps_python_script.method_assets.multiple_modules.outer.compute_series",
                module=Path("ansys/solutions/solution_with_hps_python_script/method_assets/multiple_modules"),
                output_parameters={"result": str},
                dependencies=["sympy==1.12.1"],
            )
        else:
            raise RuntimeError(f"spec_name {self.spec_name} not recognized")

        hps_project = execution_spec.execute(n=self.n)

        while not hps_project.finished:
            time.sleep(5)

        assert hps_project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
        self.result = hps_project.result  # type: ignore


class SimpleSubtractStep(StepModel):
    n: int = 0
    result: int = 0
    spec_name: str = ""

    @transaction(self=StepSpec(upload=["result"], download=["n", "spec_name"]))
    def subtract(self) -> None:
        # Here we dynamically import and use type ignore
        # because the solution source code is moved as part of the
        # test setup.  In production the imports are expected
        # to be located at the top of source files.

        if self.spec_name == "default":
            from ansys.solutions.solution_with_hps_python_script.scripts.single_module import subtract  # type: ignore

            execution_spec = HpsExecutionSpecification(
                function=subtract,  # type: ignore
                output_parameters={"result": int},
            )
        elif self.spec_name == "single module":
            from ansys.solutions.solution_with_hps_python_script.scripts import single_module  # type: ignore

            execution_spec = HpsExecutionSpecification(
                function=single_module.subtract,  # type: ignore
                module=single_module,  # type: ignore
                output_parameters={"result": int},
            )
        elif self.spec_name == "multiple submodules":
            from ansys.solutions.solution_with_hps_python_script.scripts import multiple_modules  # type: ignore
            from ansys.solutions.solution_with_hps_python_script.scripts.multiple_modules import outer  # type: ignore

            execution_spec = HpsExecutionSpecification(
                function=outer.subtract,  # type: ignore
                module=multiple_modules,  # type: ignore
                output_parameters={"result": int},
            )
        else:
            raise RuntimeError(f"spec_name {self.spec_name} not recognized")

        hps_project = execution_spec.execute(n=self.n)

        for _ in range(60 * 30):
            if hps_project.finished:
                break
            time.sleep(1)
        assert hps_project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
        self.result = hps_project.result  # type: ignore


class SimpleParametricStudy(StepModel):
    hps_project: HpsParametricStudyProject = NO_HPS_STUDY_PROJECT

    @transaction(self=StepSpec(upload=["hps_project"]))
    def start_study(self) -> None:
        from ansys.solutions.solution_with_hps_python_script.scripts.subtract_via_file import (  # type: ignore
            NestedString,  # type: ignore
            subtract_via_file,  # type: ignore
        )

        execution_spec = HpsExecutionSpecification(
            function=subtract_via_file,  # type: ignore
            output_parameters={
                "add": int,
                "subtract": HpsOutputFileSpecification("result.txt"),
                "multiply": HpsOutputDirectorySpecification("results"),
                "concat": NestedString,
            },
        )

        a_txt = self.storage_scope.get_storage_root() / "a.txt"
        a_txt.write_text("5")
        suffix_dir = self.storage_scope.get_storage_root() / "suffix_dir"
        suffix_dir.mkdir()
        (suffix_dir / "suffix.txt").write_text("SUFFIX")
        prefix_dir = self.storage_scope.get_storage_root() / "prefix_dir"
        prefix_dir.mkdir()
        (prefix_dir / "prefix.txt").write_text("PREFIX")
        prefix_dir_handle = self.storage_scope.store(prefix_dir)

        self.hps_project = execution_spec.execute_parametric_study(
            a=a_txt,
            b=[1, 2],
            prefix_dir=prefix_dir_handle,
            suffix_dir=suffix_dir,
            nested_string=[NestedString("abc"), NestedString("xyz")],
        )

    @transaction(self=StepSpec(download=["hps_project"]))
    def monitor_study(self) -> None:
        for _ in range(60 * 30):
            if self.hps_project.finished:
                break
            time.sleep(1)

        assert all(
            status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
            for status in self.hps_project.get_status_of_design_points()
        )

        assert self.hps_project.add == [6, 7]  # type: ignore
        assert [x.nested_string for x in self.hps_project.concat] == ["PREFIXabcSUFFIX", "PREFIXxyzSUFFIX"]  # type: ignore
        file_entity_handles = cast("list[EntityHandle]", self.hps_project.subtract)  # type: ignore
        file_content = [self.storage_scope.get_text(f) for f in file_entity_handles]
        assert file_content == ["4", "3"]
        dir_entity_handles = cast("list[EntityHandle]", self.hps_project.multiply)  # type: ignore
        dir_content = [(self.storage_scope.get_cached(d) / "r.txt").read_text() for d in dir_entity_handles]
        assert dir_content == ["5", "10"], f"{dir_content} != ['5', '10']"


class StringResultParametricStep(StepModel):
    matching_results: list[int] = []

    @transaction(self=StepSpec(upload=["matching_results"]))
    def run_study(self) -> None:
        from ansys.solutions.solution_with_hps_python_script.scripts.echo_string import (  # type: ignore
            echo_string,  # type: ignore
        )

        execution_spec = HpsExecutionSpecification(
            function=echo_string,  # type: ignore
            output_parameters={"result": str},
        )

        hps_project = execution_spec.execute_parametric_study(
            input_value=["first-1", "second-2", "third-3"],
        )

        attempts = 1

        while not hps_project.finished and attempts < 120:
            time.sleep(5)
            attempts += 1

        assert all(
            status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
            for status in hps_project.get_status_of_design_points()
        )

        self.matching_results = hps_project.fetch_values_of_parameter(
            "index",
            HpsDesignPointSelection(parameter_filter={"result": "second-2"}),
        )


class HpsProjectCollectionsStep(StepModel):

    input_file: EntityHandle = NO_ENTITY
    add_script: EntityHandle = NO_ENTITY
    time_to_generate_the_output_file: float = 0.0
    collect_interval: int = 0

    simple_projects: list[HpsSimpleProject] = []
    study_projects: list[HpsParametricStudyProject] = []
    simple_projects_by_name: dict[str, HpsSimpleProject] = {}
    study_projects_by_name: dict[str, HpsParametricStudyProject] = {}

    @transaction(
        self=StepSpec(
            upload=["simple_projects", "simple_projects_by_name"],
            download=[
                "input_file",
                "add_script",
                "time_to_generate_the_output_file",
                "collect_interval",
            ],
        ),
    )
    def start_n_simple_jobs(self, num_projects: int, list_or_dict: str) -> None:
        if list_or_dict not in ["list", "dict"]:
            raise ValueError("list_or_dict must be either 'list' or 'dict'")
        if num_projects <= 0:
            raise ValueError("num_projects must be a positive integer")

        for _ in range(num_projects):
            hps_project = HpsSimpleProject.start_hps_job(
                input_values={
                    "script": self.add_script,
                    "custom_input_file": self.input_file,
                    "time_to_generate_the_output_file": self.time_to_generate_the_output_file,
                },
                output_parameters={
                    "result": HpsOutputFileSpecification(
                        collect_interval=self.collect_interval,
                    ),
                },
                # we're assuming that under test the HPS evaluator will be using the same
                # version of python as the GLOW engine process
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                use_product_environment=False,
            )
            if list_or_dict == "list":
                self.simple_projects.append(hps_project)
            else:
                self.simple_projects_by_name[f"simple_project_{len(self.simple_projects_by_name) + 1}"] = hps_project

    @transaction(self=StepSpec(download=["simple_projects", "simple_projects_by_name"]))
    def wait_for_hps_projects_to_finish(self, list_or_dict: str) -> None:
        if list_or_dict not in ["list", "dict"]:
            raise ValueError("list_or_dict must be either 'list' or 'dict'")
        elif list_or_dict == "list":
            hps_projects = self.simple_projects
        else:
            hps_projects = list(self.simple_projects_by_name.values())

        max_iterations = 300
        iterations = 0
        while not all(project.finished for project in hps_projects):
            time.sleep(1)
            iterations += 1
            if iterations >= max_iterations:
                raise TimeoutError("HPS projects did not finish within the maximum allowed iterations")

    @transaction(self=StepSpec(download=["simple_projects", "simple_projects_by_name"]))
    def fetch_files(self, list_or_dict: str) -> list[str]:
        if list_or_dict not in ["list", "dict"]:
            raise ValueError("list_or_dict must be either 'list' or 'dict'")
        elif list_or_dict == "list":
            hps_projects = self.simple_projects
        else:
            hps_projects = list(self.simple_projects_by_name.values())

        output: list[str] = []
        for hps_project in hps_projects:
            result_handle = cast("EntityHandle", hps_project.result)  # type: ignore
            output.append(self.storage_scope.get_text(result_handle))
        return output


class Steps(StepsModel):
    file_job_step: FileJobStep
    data_transfer_step: DataTransferStep
    simple_sympy_step: SimpleSympyStep
    simple_subtract_step: SimpleSubtractStep
    simple_parametric_study: SimpleParametricStudy
    string_result_parametric_step: StringResultParametricStep
    hps_project_collections_step: HpsProjectCollectionsStep


class ParametricStudySolution(Solution):
    display_name: str = "parametric-study"
    steps: Steps
