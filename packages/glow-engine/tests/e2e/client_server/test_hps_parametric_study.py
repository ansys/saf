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

from collections.abc import Callable, Generator
import json
import os
from pathlib import Path

from ansys.saf.testing.solution.end_to_end import (
    GlowBaseProcess,
    HpsKeyCloakAuth,
    HpsMissingAuth,
    HpsParametricSystemEnvVarConfig,
    HpsParametricSystemNoEnvVarConfig,
    HpsUserPswdAuth,
    ProjectFixture,
)
import httpx2
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import Client
from tests.e2e.conftest import PACKAGE_ROOT, interactive_authorization
from tests.mocks.solution_with_hps_python_script.hps_parametric_study import (
    FileJobStep,
    HpsProjectCollectionsStep,
    ParametricStudySolution,
)

pytestmark = [
    pytest.mark.parametrize("solution_type", [ParametricStudySolution], indirect=True),
    pytest.mark.use_batch_job,
]


EXPECTED_CONTENT = "result=7.0"


@pytest.fixture(scope="class")
def enable_hps_auth(session_glow: GlowBaseProcess[ParametricStudySolution]) -> Generator[None, None, None]:
    session_glow.change_configuration(HpsUserPswdAuth)
    yield
    session_glow.change_configuration(HpsMissingAuth)


@retry(
    stop=stop_after_attempt(60),
    wait=wait_fixed(1),
)
def wait_for_hps_filejob_to_run(file_job_step: FileJobStep) -> None:
    try:
        file_job_step.query_hps()
    except Exception:
        raise TryAgain from None


@retry(
    stop=stop_after_attempt(60),
    wait=wait_fixed(1),
)
def wait_for_hps_fetching_output_file(file_job_step: FileJobStep) -> FileJobStep.State:
    file_job_step.query_hps()
    file_job_step.fetch_file_before_job_completion()
    if file_job_step.step_state == FileJobStep.State.Calculating:
        raise TryAgain
    return file_job_step.step_state


@pytest.fixture(autouse=True)
def auto_setup_job_scripts(
    function_project: ProjectFixture[ParametricStudySolution],
) -> None:
    step = function_project.project.steps.file_job_step
    load_job_scripts(function_project.project, step)


def load_job_scripts(
    project: ParametricStudySolution,
    step: FileJobStep | HpsProjectCollectionsStep,
):
    storage_scope = project.storage_scope
    with Path(
        "./tests/mocks/solution_with_hps_python_script/method_assets/add_from_file_script.py",
    ).open("rb") as add_script:
        file = storage_scope.get_storage_root() / "custom_input.txt"
        file.write_text("3 4")
        step.input_file = storage_scope.store(file)
        step.add_script = storage_scope.store_stream(add_script.read(), Path("add_from_file_script.py"))


@retry(
    stop=stop_after_attempt(30),
    wait=wait_fixed(2.5),
)
def wait_for_hps_file_job_to_finish(file_job_step: FileJobStep) -> FileJobStep.State:
    file_job_step.query_hps()
    if file_job_step.step_state == FileJobStep.State.Calculating:
        raise TryAgain
    return file_job_step.step_state


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.usefixtures("enable_hps_auth")
class TestHpsParametricStudy:
    @pytest.fixture(scope="class", autouse=True)
    def set_hps_env_var_on_client(self, hps_port: int):
        mp = pytest.MonkeyPatch()
        mp.setenv("GLOW_HPS_USERNAME", "repadmin")
        mp.setenv("GLOW_HPS_PASSWORD", "repadmin")
        mp.setenv("GLOW_PRODUCT_INSTANCE_SYSTEM", "HPS")
        mp.setenv("GLOW_PRODUCT_INSTANCE_SYSTEM_HOST", "127.0.0.1")
        mp.setenv("GLOW_PRODUCT_INSTANCE_SYSTEM_PORT", str(hps_port))
        yield
        mp.undo()

    def test_running_simple_files_based_project_is_successful_and_generates_expected_result(
        self,
        function_project: ProjectFixture[ParametricStudySolution],
        tmp_path: Path,
    ):
        """
        Test that, when using custom HPS arguments (url, client, etc), the HpsReferenceFile
        access operations work properly, that the hps result entity handle can be streamed
        from the blob endpoint, and that it can be accessed from the client.
        """

        step = function_project.project.steps.file_job_step
        step.start_job()
        assert wait_for_hps_file_job_to_finish(step) == FileJobStep.State.ResultAvailable

        step.fetch_file()
        assert step.result_file_content == EXPECTED_CONTENT

        step.get_cached_file_content()
        assert step.result_file_content == EXPECTED_CONTENT

        copy_file_path = tmp_path / "my_file.txt"
        step.file_path = copy_file_path.as_posix()
        step.get_copy_from_handle()
        assert copy_file_path.read_text() == EXPECTED_CONTENT
        # verify that the hps project entity can be accessed from the blobs endpoint
        entity_url = step.get_entity_url("result_handle")
        response = httpx2.get(entity_url, timeout=90)
        assert response.text == EXPECTED_CONTENT
        # verify that the hps project entity can be accessed from the client
        scope = function_project.project.storage_scope
        assert scope.get_text(step.result_handle) == EXPECTED_CONTENT
        assert scope.get_cached(step.result_handle).read_text() == EXPECTED_CONTENT

    def test_fetching_output_file_during_evaluation(
        self,
        function_project: ProjectFixture[ParametricStudySolution],
    ):
        """
        Test that, when using custom HPS arguments (url, client, etc), the HpsReferenceFile
        access operations work properly.
        """
        """Test fetching output file during evaluation."""
        step = function_project.project.steps.file_job_step
        step.time_to_generate_the_output_file = 5
        step.collect_interval = 1
        step.start_job()
        step.query_hps()
        assert wait_for_hps_fetching_output_file(step) == FileJobStep.State.ResultAvailable
        step.fetch_file()
        assert step.result_file_content == EXPECTED_CONTENT
        # verify that the hps project entity can be accessed from the client
        scope = function_project.project.storage_scope
        assert scope.get_text(step.result_handle) == EXPECTED_CONTENT
        assert scope.get_cached(step.result_handle).read_text() == EXPECTED_CONTENT

    def test_parametric_job_with_compiled_glow(
        self,
        run_glow: Callable[..., GlowBaseProcess[ParametricStudySolution]],
        tmp_solutions_dir: dict[type[ParametricStudySolution], Path],
        get_glow_client: Callable[[GlowBaseProcess[ParametricStudySolution]], Client[ParametricStudySolution]],
        obfuscated_glow_source: Path,
        random_project_name: Callable[[], str],
    ):
        """
        Test that it is possible to run a parametric job on HPS when GLOW / dependencies are compiled.
        """
        # GIVEN: a project created with a compiled GLOW process
        deps = PACKAGE_ROOT / ".venv" / "Lib" / "site-packages"
        glow_and_deps = obfuscated_glow_source.as_posix() + os.pathsep + deps.as_posix()
        glow_process = run_glow(
            ParametricStudySolution,
            tmp_solutions_dir[ParametricStudySolution],
            obfuscated_glow_pythonpath=glow_and_deps,
        )
        assert glow_process.healthy
        with get_glow_client(glow_process) as client:
            project = client.create_project(random_project_name())
            step = project.steps.file_job_step
            load_job_scripts(project, step)

            # THEN: ensure GLOW is compiled
            assert not step.is_glow_src_readable()

            step.start_job()
            assert wait_for_hps_file_job_to_finish(step) == FileJobStep.State.ResultAvailable

            step.fetch_file()
            assert step.result_file_content == EXPECTED_CONTENT

    @pytest.mark.parametrize("list_or_dict", ["list", "dict"])
    def test_collecting_hps_projects_on_list_or_dict(
        self,
        function_project: ProjectFixture[ParametricStudySolution],
        list_or_dict: str,
    ):
        """
        Test that HPS projects can be grouped and stored in a list or flat dictionary.
        """
        num_projects = 2
        step = function_project.project.steps.hps_project_collections_step
        load_job_scripts(function_project.project, step)
        step.start_n_simple_jobs(num_projects=num_projects, list_or_dict=list_or_dict)
        if list_or_dict == "list":
            assert len(step.simple_projects) == num_projects
            for project in step.simple_projects:
                assert project.hps_project_identifier
        else:
            assert len(step.simple_projects_by_name) == num_projects
            for project in step.simple_projects_by_name.values():
                assert project.hps_project_identifier
        step.wait_for_hps_projects_to_finish(list_or_dict=list_or_dict)
        output_files = step.fetch_files(list_or_dict=list_or_dict)
        assert len(output_files) == num_projects
        for output_file in output_files:
            assert output_file == "result=7.0"


@pytest.fixture
def env_var_instance_system(
    session_glow: GlowBaseProcess[ParametricStudySolution],
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    session_glow.change_configuration(request.param)
    yield
    session_glow.change_configuration(HpsParametricSystemEnvVarConfig, restart=False)


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize(
    "env_var_instance_system",
    [HpsParametricSystemNoEnvVarConfig],
    indirect=True,
)
class TestHpsCustomParams:
    def test_hps_filejob_with_custom_params(
        self,
        session_glow: GlowBaseProcess[ParametricStudySolution],
        function_project: ProjectFixture[ParametricStudySolution],
        session_selenium_webdriver: WebDriver,
        env_var_instance_system: None,
    ):
        """
        Test that, when using custom HPS arguments (url, client, etc), the HpsReferenceFile
        access operations work properly.
        """
        # GIVEN: project with a running HPS project without any HPS env vars configured
        step = function_project.project.steps.file_job_step
        step.time_to_generate_the_output_file = 5
        step.collect_interval = 1
        # WHEN: starting an HPS job with the custom HPS params passed
        step.start_job_with_custom_hps_params()
        # THEN: Keycloak authentication works
        interactive_authorization(session_selenium_webdriver, session_glow)

        wait_for_hps_filejob_to_run(step)

        # THEN: the job is finished successfully
        assert wait_for_hps_fetching_output_file(step) == FileJobStep.State.ResultAvailable

        # THEN: the file text can be retrieved
        step.fetch_file()
        assert step.result_file_content == EXPECTED_CONTENT

        # THEN: the file bytes can be retrieved
        step.result_file_content = ""
        step.fetch_file_bytes()
        assert step.result_file_content == EXPECTED_CONTENT


@pytest.fixture
def hps_interactive_configuration(
    session_glow: GlowBaseProcess[ParametricStudySolution],
) -> Generator[None, None, None]:
    session_glow.change_configuration(HpsKeyCloakAuth, restart=False)
    yield
    session_glow.change_configuration(HpsMissingAuth)


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.usefixtures("hps_interactive_configuration")
@pytest.mark.parametrize(
    "env_var_instance_system",
    [HpsParametricSystemEnvVarConfig],
    indirect=True,
)
def test_hps_job_with_input_and_output_sources(
    session_glow: GlowBaseProcess[ParametricStudySolution],
    function_project: ProjectFixture[ParametricStudySolution],
    selenium_webdriver: WebDriver,
    env_var_instance_system: None,
):
    """
    Test uploading / downloading input / output files and directories to / from HPS.
    """
    # WHEN: running an HPS job that uploads / downloads files and directories
    step = function_project.project.steps.file_job_step
    step.start_job_with_input_and_output_sources()

    interactive_authorization(selenium_webdriver, session_glow)

    # THEN: the job finishes properly
    assert wait_for_hps_file_job_to_finish(step) == FileJobStep.State.ResultAvailable

    # WHEN: retrieving job results
    step.get_inputs_outputs_job_result()

    # THEN: input / output files and directories have been treated properly
    assert json.loads(step.inputs_outputs_result) == {
        "input_dir_txt": "This is an asset file",
        "input_dir_eval_path_txt": "This is another asset file",
        "input_zip_txt": "This is an input file",
        "output_dir_txt": "This is an output file!",
        "output_dir_eval_path_txt": "This is another output file!",
        "output_zip_txt": "Testing no eval path",
        "output_zip_eval_txt": "Testing with eval path",
    }
