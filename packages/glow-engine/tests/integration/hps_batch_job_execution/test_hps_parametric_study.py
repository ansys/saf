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
import re
import sys
import time
from typing import Any, cast

from ansys.hps.client import Client  # pyright: ignore[reportMissingTypeStubs]
from ansys.hps.client.jms import JmsApi, Project  # pyright: ignore[reportMissingTypeStubs]
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow._core.blob_managers import HpsBlobManager
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator
from ansys.saf.glow._hps_parametric_studies.base import DynamicHpsParametricStudyProject, DynamicHpsSimpleProject
from ansys.saf.glow._hps_parametric_studies.system import HpsParametricStudySystem
from ansys.saf.glow.solution.hps import (
    NO_HPS_SIMPLE_PROJECT,
    NO_HPS_STUDY_PROJECT,
    HpsInputDirectorySpecification,
    HpsInputFileSpecification,
    HpsJobEvaluationStatus,
    HpsOutputDirectorySpecification,
    HpsOutputFileSpecification,
    HpsParametricStudyProject,
    HpsProjectNotStartedError,
    HpsSimpleProject,
)
from ansys.saf.product_configuration.interfaces import Software as GlowSoftware
import tests.mocks.solution_with_hps_python_script.hps_parametric_study as hps_parametric_study_module

METHOD_ASSETS = Path(hps_parametric_study_module.__file__).parent / "method_assets"
pytestmark = [pytest.mark.use_batch_job]


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.usefixtures("hps_authentication")
class TestHpsParametricStudy:
    def test_running_script_that_raises_exception_results_in_failed_status(self):
        hps_project = HpsSimpleProject.start_hps_job(
            input_values={"script": METHOD_ASSETS / "divide_script.py", "x": 6.0, "y": 0.0},
            output_parameters={"result": float},
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )

        attempts = 0
        while (
            hps_project.status.evaluation_status
            in [HpsJobEvaluationStatus.PENDING, HpsJobEvaluationStatus.PROLOG, HpsJobEvaluationStatus.RUNNING]
            and attempts < 28
        ):
            time.sleep(2.5)
            attempts += 1

        assert hps_project.status.evaluation_status == HpsJobEvaluationStatus.FAILED
        assert hps_project.finished

    def test_accessing_a_non_existent_parameter_raises_exception(self):
        hps_project = HpsSimpleProject.start_hps_job(
            input_values={"script": METHOD_ASSETS / "add_script.py", "x": 6.0, "y": 99.0},
            output_parameters={"result": float},
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )

        attempts = 0
        while (
            hps_project.status.evaluation_status
            in [HpsJobEvaluationStatus.PENDING, HpsJobEvaluationStatus.PROLOG, HpsJobEvaluationStatus.RUNNING]
            and attempts < 28
        ):
            time.sleep(2.5)
            attempts += 1

        with pytest.raises(AttributeError, match="HPS project does not have parameter or file corresponding to z"):
            # use assert here to avoid B018 Found useless expression.
            # It is unclear how to combine noqa and type: ignore
            assert hps_project.z  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    def test_launch_two_jobs_with_same_name_creates_different_projects(self):
        @retry(stop=stop_after_attempt(100), wait=wait_fixed(0.5))
        def get_existing_projects_by_name(hps_client: Client, custom_name: str) -> list[Project]:
            projects_list: list[Project] = JmsApi(hps_client).get_project_by_name(
                custom_name,
                last_created=False,
            )  # pyright: ignore[reportAssignmentType]
            if len(projects_list) == 0:
                raise TryAgain
            return projects_list

        custom_name = "custom_hps_project"
        HpsSimpleProject.start_hps_job(
            input_values={"script": METHOD_ASSETS / "divide_script.py", "x": 6.0, "y": 0.0},
            output_parameters={"result": float},
            name=custom_name,
        )

        HpsSimpleProject.start_hps_job(
            input_values={"script": METHOD_ASSETS / "divide_script.py", "x": 6.0, "y": 0.0},
            output_parameters={"result": float},
            name=custom_name,
        )

        with HpsParametricStudySystem.get_hps_client() as hps_client:
            existing_projects = get_existing_projects_by_name(hps_client, custom_name)

        assert len(existing_projects) == 2
        assert existing_projects[0].name == existing_projects[1].name
        assert existing_projects[0].id != existing_projects[1].id

    def test_starting_a_job_with_a_missing_input_file_raises_exception(self):
        with pytest.raises(
            RuntimeError,
            match="The key 'script' is missing from the input files dictionary argument.",
        ):
            HpsSimpleProject.start_hps_job(
                input_values={"x": 99.0, "y": 0.0},
                output_parameters={"result": float},
                # we're assuming that under test the HPS evaluator will be using the same
                # version of python as the GLOW engine process
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                use_product_environment=False,
            )

    @pytest.mark.skip(
        reason="this works if the delete code is enabled in "
        "HpsParametricStudyDefinition but the delete is way too slow...",
    )
    def test_starting_a_job_with_incorrect_arguments_does_not_create_a_project(self):
        def get_number_of_existing_projects(hps_client: Client) -> int:
            return len(JmsApi(hps_client).get_projects())  # pyright: ignore[reportUnknownMemberType]

        with HpsParametricStudySystem.get_hps_client() as hps_client:
            number_of_existing_projects = get_number_of_existing_projects(hps_client)
        with pytest.raises(RuntimeError):  # message checked in another test
            HpsSimpleProject.start_hps_job(
                input_values={"script": METHOD_ASSETS / "divide_script.py", "x": {"a": 1.0}, "y": 0.0},
                output_parameters={"result": float},
                # we're assuming that under test the HPS evaluator will be using the same
                # version of python as the GLOW engine process
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                use_product_environment=False,
            )
        with HpsParametricStudySystem.get_hps_client() as hps_client:
            assert get_number_of_existing_projects(hps_client) == number_of_existing_projects

    def test_starting_a_job_with_input_parameters_of_different_lengths_raises_exception(self):
        with pytest.raises(
            RuntimeError,
            match="found 6 values for input parameter y but 3 values for input parameter x",
        ):
            HpsParametricStudyProject.start_hps_parametric_study(
                common_input_files={"script": METHOD_ASSETS / "divide_script.py"},
                input_parameter_values={"x": [3.0, 4.0, 5.0], "y": [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]},
                output_parameters={"result": float},
                # we're assuming that under test the HPS evaluator will be using the same
                # version of python as the GLOW engine process
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                use_product_environment=False,
            )

    def test_starting_a_job_with_input_parameters_of_inconsistent_types_raises_exception(self):
        with pytest.raises(
            RuntimeError,
            match=re.escape(
                "input parameter x has value 'a' (str) at index 3 which is not compatible with "
                "the value of x in the first design point which is '3.0' (float)",
            ),
        ):
            HpsParametricStudyProject.start_hps_parametric_study(
                common_input_files={"script": METHOD_ASSETS / "divide_script.py"},
                input_parameter_values={"x": [3.0, 4.0, 5.0, "a", "b", "c"], "y": [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]},
                output_parameters={"result": float},
                # we're assuming that under test the HPS evaluator will be using the same
                # version of python as the GLOW engine process
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                use_product_environment=False,
            )

    def test_running_job_with_boolean_integer_and_string_input_and_output_parameters(self):
        project = HpsSimpleProject.start_hps_job(
            input_values={
                "bool_in": False,
                "int_in": 1,
                "str_in": "foobar",
                "script": METHOD_ASSETS / "other_types_script.py",
            },
            output_parameters={"bool_out": bool, "int_out": int, "str_out": str},
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )

        attempts = 0
        while not project.finished and attempts < 60:
            time.sleep(2.5)
            attempts += 1

        assert project.finished
        assert project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
        assert project.bool_out  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        assert project.int_out == -1  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        assert project.str_out == "FOOBAR"  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    @pytest.mark.parametrize("input_dict", [{}, {"x": 1}, {"x": '?.|*"\\\u0000'}, {"x": [1, 2, 3]}, {"x": {"y": 1}}])
    def test_running_job_with_serialized_empty_dict_input_and_output_parameters(self, input_dict: dict[str, Any]):
        project = HpsSimpleProject.start_hps_job(
            input_values={
                "s": json.dumps(input_dict),
                "script": METHOD_ASSETS / "echo.py",
            },
            output_parameters={"result": str},
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )

        attempts = 0
        while not project.finished and attempts < 60:
            time.sleep(2.5)
            attempts += 1

        assert project.finished
        assert project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
        assert project.s == json.dumps(  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            input_dict,
        )
        assert project.result == json.dumps(  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            input_dict,
        )

    def test_string_parsing(self):
        values = ["a", " "]  # these don't appear to work : "%", ".", "*", "/", "(", ")"
        project = HpsParametricStudyProject.start_hps_parametric_study(
            common_input_files={"script": METHOD_ASSETS / "echo.py"},
            input_parameter_values={"s": values},
            output_parameters={"result": str},
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )

        attempts = 0
        while not project.finished and attempts < 60:
            time.sleep(2.5)
            attempts += 1

        assert project.finished
        assert project.result == values  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    def test_execution_context(self):
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        project = HpsSimpleProject.start_hps_job(
            input_values={"script": METHOD_ASSETS / "echo_context.py"},
            output_parameters={
                "required_output_parameters": str,
                "required_output_files": str,
                "required_output_directories": str,
                "products": str,
                "myfile": HpsOutputFileSpecification("x.txt"),
                "my_output_dir": HpsOutputDirectorySpecification("expected_dir"),
            },
            python_version=python_version,
            use_product_environment=False,
            products=[GlowSoftware("Ansys SAF Product Environment", "0.0")],
        )

        attempts = 0
        while not project.finished and attempts < 60:
            time.sleep(2.5)
            attempts += 1

        assert project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
        assert (
            project.required_output_parameters  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            == ("products required_output_directories required_output_files required_output_parameters")
        )
        assert (
            project.products  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            == f"Python {python_version.replace('.', 'DOT')}  Ansys SAF Product Environment 0DOT0"
        )
        assert (
            project.required_output_files  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            == "myfile xDOTtxt"
        )
        assert (
            project.required_output_directories  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            == "my_output_dir"
        )

    def test_no_simple_project(self, hps_blob_manager: HpsBlobManager, hps_authentication: IHpsAuthenticator):
        project = HpsSimpleProject.start_hps_job(
            input_values={"script": METHOD_ASSETS / "echo_context.py"},
            output_parameters={},
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )

        assert project != NO_HPS_SIMPLE_PROJECT
        serialized = cast("DynamicHpsSimpleProject", project).persisted_project.model_dump_json()
        deserialized = HpsSimpleProject.model_validate_json(serialized)
        assert project == deserialized
        assert deserialized != NO_HPS_SIMPLE_PROJECT
        dynamic_deserialized = DynamicHpsSimpleProject(deserialized, hps_blob_manager, hps_authentication)
        assert dynamic_deserialized != NO_HPS_SIMPLE_PROJECT
        assert project.exists
        assert dynamic_deserialized.exists
        with pytest.raises(HpsProjectNotStartedError, match="The HPS project has not been started."):
            _ = DynamicHpsSimpleProject(NO_HPS_SIMPLE_PROJECT, hps_blob_manager, hps_authentication).exists

    def test_no_study_project(self, hps_blob_manager: HpsBlobManager, hps_authentication: IHpsAuthenticator):
        project = HpsParametricStudyProject.start_hps_parametric_study(
            common_input_files={"script": METHOD_ASSETS / "echo.py"},
            input_parameter_values={"s": [1, 2]},
            output_parameters={"result": str},
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )

        assert project != NO_HPS_STUDY_PROJECT
        serialized = cast("DynamicHpsParametricStudyProject", project).persisted_project.model_dump_json()
        deserialized = HpsParametricStudyProject.model_validate_json(serialized)
        assert project == deserialized
        assert deserialized != NO_HPS_STUDY_PROJECT
        dynamic_deserialized = DynamicHpsParametricStudyProject(deserialized, hps_blob_manager, hps_authentication)
        assert dynamic_deserialized != NO_HPS_STUDY_PROJECT
        assert project.exists
        assert dynamic_deserialized.exists
        with pytest.raises(HpsProjectNotStartedError, match="The HPS project has not been started."):
            _ = DynamicHpsParametricStudyProject(NO_HPS_SIMPLE_PROJECT, hps_blob_manager, hps_authentication).exists

    def test_project_with_specified_input_paths(self):
        project = HpsSimpleProject.start_hps_job(
            input_values={
                "script": METHOD_ASSETS / "echo_input_sources.py",
                "test_input_file": HpsInputFileSpecification(
                    METHOD_ASSETS / "echo.py",
                    evaluation_path="abc/edf/x.txt",
                ),
                "test_input_dir": HpsInputDirectorySpecification(
                    METHOD_ASSETS / "asset_dir",
                    evaluation_path="input_directory/sub_dir",
                ),
                "another_input_dir": HpsInputDirectorySpecification(METHOD_ASSETS / "another_asset_dir"),
            },
            output_parameters={
                "result": str,
                "asset_content": str,
                "another_asset_content": str,
            },
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
        )
        attempts = 0
        while not project.finished and attempts < 60:
            time.sleep(2.5)
            attempts += 1

        assert project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
        assert (
            project.result  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            == "abcSLASHedfSLASHxDOTtxt"
        )
        assert (
            project.asset_content  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            == "This is an asset file"
        )
        assert (
            project.another_asset_content  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            == "This is another asset file"
        )


HPS_SERVER_URL = "https://localhost:8443/hps"
HPS_CLIENT_ID = "rep-jms-web"


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.usefixtures("hps_auth_for_custom_url")
class TestHpsCustomServerUrl:
    def test_hps_simple_project_running_on_custom_url_works(self):
        hps_project = HpsSimpleProject.start_hps_job(
            input_values={"script": METHOD_ASSETS / "add_script.py", "x": 6.0, "y": 5.0},
            output_parameters={"result": float},
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
            hps_server_url=HPS_SERVER_URL,
            client_id=HPS_CLIENT_ID,
        )
        assert hps_project.get_compute_resource_sets(
            hps_server_url=HPS_SERVER_URL,
            client_id=HPS_CLIENT_ID,
        )

        attempts = 0
        while (
            hps_project.status.evaluation_status
            in [HpsJobEvaluationStatus.PENDING, HpsJobEvaluationStatus.PROLOG, HpsJobEvaluationStatus.RUNNING]
            and attempts < 28
        ):
            time.sleep(2.5)
            attempts += 1

        assert hps_project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
        assert hps_project.hps_server_url == HPS_SERVER_URL
        assert hps_project.client_id == HPS_CLIENT_ID

    def test_hps_simple_project_without_url_host_port_raises_exception(self):
        with pytest.raises(RuntimeError, match="No HPS system is configured."):
            HpsSimpleProject.start_hps_job(
                input_values={"script": METHOD_ASSETS / "add_script.py", "x": 6.0, "y": 5.0},
                output_parameters={"result": float},
                # we're assuming that under test the HPS evaluator will be using the same
                # version of python as the GLOW engine process
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                use_product_environment=False,
                hps_server_url=None,
            )

    def test_hps_parametric_project_running_on_custom_url_works(self):
        hps_project = HpsParametricStudyProject.start_hps_parametric_study(
            common_input_files={"script": METHOD_ASSETS / "divide_script.py"},
            input_parameter_values={"x": [3.0, 4.0, 5.0], "y": [5.0, 6.0, 7.0]},
            output_parameters={"result": float},
            # we're assuming that under test the HPS evaluator will be using the same
            # version of python as the GLOW engine process
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            use_product_environment=False,
            hps_server_url=HPS_SERVER_URL,
            client_id=HPS_CLIENT_ID,
        )
        assert hps_project.get_compute_resource_sets(
            hps_server_url=HPS_SERVER_URL,
            client_id=HPS_CLIENT_ID,
        )

        attempts = 0
        while not hps_project.finished and attempts < 60:
            time.sleep(2.5)
            attempts += 1

        assert hps_project.finished
        assert hps_project.hps_server_url == HPS_SERVER_URL
        assert hps_project.client_id == HPS_CLIENT_ID

    def test_hps_parametric_project_without_url_host_port_raises_exception(self):
        with pytest.raises(RuntimeError, match="No HPS system is configured."):
            HpsParametricStudyProject.start_hps_parametric_study(
                common_input_files={"script": METHOD_ASSETS / "divide_script.py"},
                input_parameter_values={"x": [3.0, 4.0, 5.0], "y": [5.0, 6.0, 7.0]},
                output_parameters={"result": float},
                # we're assuming that under test the HPS evaluator will be using the same
                # version of python as the GLOW engine process
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                use_product_environment=False,
            )
