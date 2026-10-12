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
from collections.abc import Callable
from pathlib import Path
import platform
import uuid

import pytest

from ansys.saf.glow.client import Client, InternalSolutionException
from ansys.saf.product_manager._utilities.const import LOCALHOSTS
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.network import get_local_ip
from ansys.saf.testing.pim.process import PimProcess
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.e2e.conftest import DOCKER_GATEWAY_IP, kill_mechanical
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_mechanical,
    pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True),
]

STEP_NAME = "mechanical-instance-step"
INSTANCE_NAME = "mechanical-instance"


@pytest.fixture(scope="class")
def launch_mechanical(
    class_project: ProjectFixture[EndToEndSolution],
    ansys_release: str,
) -> YieldFixture[None]:
    step = class_project.project.steps.mechanical_instance_step

    step.version = ansys_release
    step.launch_mechanical().wait()

    storage_scope = class_project.project.storage_scope
    with Path("./tests/e2e/inputs/example_01_geometry.agdb").open("rb") as f:
        step.example_file = storage_scope.store_stream(f.read(), Path("example_01_geometry.agdb"))
    step.upload_example_file_to_mechanical()

    yield

    mechanical_port = step.mechanical_port()
    step.close_mechanical()
    kill_mechanical(mechanical_port)


@pytest.mark.usefixtures("launch_mechanical")
@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host"),
    [
        ("Desktop", None, None),
        ("DockerCompose", "host.docker.internal", DOCKER_GATEWAY_IP),
    ],
    ids=[
        "desktop_secure",
        "dockercompose_secure",
    ],
    indirect=True,
)
class TestMechanical:
    def test_mechanical_workflow(self, function_class_project: ProjectFixture[EndToEndSolution]):
        """
        Test that Mechanical product instance managers are working as expected on a complete product workflow.
        """
        # GIVEN: Mechanical instance launched and with an example file downloaded
        step = function_class_project.project.steps.mechanical_instance_step
        step.refresh_availability()
        assert step.mechanical_available

        # WHEN: Running simulation example
        # (copied from https://examples.mechanical.docs.pyansys.com/examples/00_basic/example_01_simple_structural_solve.html#)
        step.initialize_variable_workflow()
        step.run_script().wait()
        step.export_working_dir_file_list()

        # THEN: all files are copied into the product space via save_state
        out_file_names = sorted([Path(f).name for f in step.working_files])
        expected_file_names = sorted(
            [
                "CAERep.xml",
                "CAERepOutput.xml",
                "ds.dat",
                "example_01_geometry.agdb",
                "MatML.xml",
                "file.aapresults",
                "file.cnd",
                "file.mntr",
                "file.rst",
                "file0.PCS",
                "file0.err",
                "solve.out",
            ],
        )
        assert out_file_names == expected_file_names

        # THEN: Results are OK and out file is downloaded from working dir to project space
        step.download_output_solve()
        assert "RUN COMPLETED" in function_class_project.project.storage_scope.get_text(step.output_handle)

    def test_mechanical_state_reinitialized(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_class_project: ProjectFixture[EndToEndSolution],
        restart_product_instance_system: Callable[..., None],
    ):
        """
        Test that Mechanical instances are resilient to Product Instance System (PIM, HPS) restarts.
        """
        # GIVEN: Mechanical instance launched and with an example file downloaded
        step = function_class_project.project.steps.mechanical_instance_step
        step.refresh_availability()
        assert step.mechanical_available

        # WHEN: Start the simulation transactions and restart the instance in the middle
        # (copied from https://examples.mechanical.docs.pyansys.com/examples/00_basic/example_01_simple_structural_solve.html#)
        step.initialize_variable_workflow()
        step.export_working_dir_file_list()
        working_files = step.working_files
        example_file = [file for file in working_files if "example_01_geometry.agdb" in file]
        assert example_file

        # WHEN: Restarting PIS
        mechanical_port = step.mechanical_port()
        restart_product_instance_system()
        kill_mechanical(mechanical_port)

        # THEN: the files in the working directory of pymechanical are restored
        step.export_working_dir_file_list()
        new_working_files = step.working_files
        new_example_file = [file for file in new_working_files if "example_01_geometry.agdb" in file]
        assert new_example_file
        assert example_file[0] != new_example_file[0]

        # THEN: the internal state of pymechanical is not restored and fails to load variable
        with pytest.raises(InternalSolutionException):
            step.run_script().wait()
        assert session_glow.text_in_output("name 'part_file_path' is not defined")

    def test_mechanical_transfer_files_working_directory(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that files can be uploaded to and downloaded from the Mechanical working directory (product space).
        """
        # GIVEN: Mechanical instance launched and with an example file downloaded
        step = function_class_project.project.steps.mechanical_instance_step
        step.refresh_availability()
        assert step.mechanical_available

        # WHEN: Running transaction that uploads file to product space using pymechanical upload method
        step.upload_files()
        # THEN: The file uploaded with pymechanical is not in the solution space
        assert function_class_project.project.storage_scope.get_cached(step.test_file).exists()

        # THEN: The file uploaded with pymechanical is in Mechanical's working directory
        step.export_working_dir_file_list()
        mechanical_working_files = step.working_files
        test_file = [file for file in mechanical_working_files if "test_file" in file]
        assert test_file
        test_file = Path(test_file[0])
        assert test_file.name == "test_file.txt"

        # WHEN: Running transaction that downloads file from product space using pymechanical
        random_text = str(uuid.uuid4())
        test_file.write_text(random_text)
        step.download_files()

        # THEN: the file is located in the solution as it was downloaded to the method space
        assert function_class_project.project.storage_scope.get_text(step.test_file) == random_text

    def test_mechanical_client_cleanup(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_class_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that the Mechanical client is cleaned up after every transaction.
        """
        # GIVEN: Mechanical instance launched and with an example file downloaded
        step = function_class_project.project.steps.mechanical_instance_step
        step.refresh_availability()
        assert step.mechanical_available

        # WHEN: Launching multiple transactions that use the instance and will spawn Mechanical clients
        for _ in range(3):
            step.log_message()

        mechanical_log_lines = 0
        glow_log_lines = 0
        for line in session_glow.api_output:
            if "mechanical - log_warning - Simulates warning message from mechanical." in line:
                mechanical_log_lines += 1
            if "=GLOW API]- Simulates warning message from mechanical." in line:
                glow_log_lines += 1

        # THEN: the log only appears once per run.
        assert mechanical_log_lines == 3
        assert glow_log_lines == 3

    def test_concurrent_shared_instances(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
        ansys_release: str,
    ):
        """
        Test that Mechanical supports two instances run con concurrent GLOW processes.
        """
        # GIVEN: Mechanical instance launched and with an example file downloaded
        step_a = function_class_project.project.steps.mechanical_instance_step
        step_a.refresh_availability()
        assert step_a.mechanical_available

        # Setup second project and launch a second Mechanical instance
        with ProjectFixture(session_glow, function_client) as second_project:
            step_b = second_project.project.steps.mechanical_instance_step
            step_b.version = ansys_release
            step_b.launch_mechanical().wait()
            storage_scope = second_project.project.storage_scope
            with Path("./tests/e2e/inputs/example_01_geometry.agdb").open("rb") as f:
                step_b.example_file = storage_scope.store_stream(f.read(), Path("example_01_geometry.agdb"))
            step_b.upload_example_file_to_mechanical()

            # Use both instances with regular and longrunning transactions, make sure
            # steps execution is not synchronized between both projects, so
            # avoid pattern: call f1 in project1, call f1 in project2, call f2 in project1, call f2 in project2, etc.
            step_a.initialize_variable_workflow()
            method_a = step_a.run_script()
            step_b.initialize_variable_workflow()
            step_b.run_script().wait()
            step_b.download_output_solve()
            method_a.wait()
            step_a.download_output_solve()

            assert "RUN COMPLETED" in function_class_project.project.storage_scope.get_text(step_a.output_handle)
            assert "RUN COMPLETED" in second_project.project.storage_scope.get_text(step_b.output_handle)

            # shutdown second Mechanical instance
            mechanical_port = step_b.mechanical_port()
            step_b.close_mechanical()
            kill_mechanical(mechanical_port)


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host", "enable_insecure_product"),
    [
        ("Desktop", None, None, False),  # product_binding_host defaults to localhost in secure products
        ("Desktop", get_local_ip(), get_local_ip(), False),
        ("Desktop", None, "0.0.0.0", True),
        ("DockerCompose", "host.docker.internal", DOCKER_GATEWAY_IP, False),
        ("DockerCompose", "host.docker.internal", "0.0.0.0", True),
    ],
    ids=[
        "desktop_wnua_or_mtls",
        "desktop_mtls",
        "desktop_insecure",
        "dockercompose_mtls",
        "dockercompose_insecure",
    ],
    indirect=True,
)
def test_secure_mechanical_on_hps(
    ansys_release: str,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    deployment_type: TestDeployment,
    product_binding_host: str | None,
    enable_insecure_product: bool,
    certificates_directory: Path,
):
    """Test secure mechanical connection."""
    step = function_project.project.steps.mechanical_instance_step
    step.version = ansys_release

    bind_host = product_binding_host or "localhost"
    method = step.launch_mechanical()
    method.wait(timeout=180)
    step.close_mechanical()

    # Due to a bug between Mechanical and HPS, the console_output is available through the UI
    # but not through the HPS Client.
    # Hence, all asserts regarding the flags passed to Mechanical and Mechanical's output cannot be done.
    # Left here as a reference in case the bug it's solved.
    if bind_host not in LOCALHOSTS:
        if enable_insecure_product:
            # Job output should contain:
            # Info: Starting the grpc server at port : 48703 (Insecure:0.0.0.0:certs)
            # Initialize() started
            # Initialize() done
            # Info: Started the grpc server at port : 48703 (Insecure:0.0.0.0:certs)
            assert session_glow.text_in_output(
                [
                    "WARNING",
                    "mechanical_manager",
                    "Using an insecure gRPC connection",
                ],
                "api",
            )

        else:
            # Job output should contain:
            # Info: Starting the grpc server at port : 48703 (Mtls:172.30.61.216:/tmp/pytest-of-pierre/pytest-3/certs-0)
            # Initialize() started
            # Initialize() done
            # Info: Started the grpc server at port : 48703 (Mtls:172.30.61.216:/tmp/pytest-of-pierre/pytest-3/certs-0)
            certs_dir = "/certs" if deployment_type == TestDeployment.DockerCompose else certificates_directory
            assert session_glow.text_in_output(
                [
                    "INFO",
                    "mechanical_manager",
                    f"MTLS secure flags found, creating MTLS channel with certificates from {certs_dir}",
                ],
                "api",
            )
    elif platform.system() == "Linux":
        # Job output should contain:
        # Info: Starting the grpc server at port : 48703 (Mtls:localhost:/tmp/pytest-of-pierre/pytest-3/certs-0)
        # Initialize() started
        # Initialize() done
        # Info: Started the grpc server at port : 48703 (Mtls:localhost:/tmp/pytest-of-pierre/pytest-3/certs-0)
        certs_dir = "/certs" if deployment_type == TestDeployment.DockerCompose else certificates_directory
        assert session_glow.text_in_output(
            [
                "INFO",
                "mechanical_manager",
                f"MTLS secure flags found, creating MTLS channel with certificates from {certs_dir}",
            ],
            "api",
        )
    else:
        # Job output should contain:
        # Info: Starting the grpc server at port : 48703 (Wnua:localhost)
        # Initialize() started
        # Initialize() done
        # Info: Started the grpc server at port : 48703 (Wnua:localhost)
        assert session_glow.text_in_output(
            ["INFO", "mechanical_manager", "WNUA secure flag found, creating secure channel."],
            "api",
        )


@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host"),
    [
        ("Desktop", None, None),  # product_binding_host defaults to localhost in secure products
        ("Desktop", None, "0.0.0.0"),
        ("DockerCompose", "host.docker.internal", "0.0.0.0"),
    ],
    ids=["desktop_wnua_or_insecure", "desktop_insecure", "dockercompose_insecure"],
    indirect=True,
)
def test_secure_mechanical_on_pim(
    ansys_release: str,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    product_binding_host: str | None,
    session_pim: PimProcess,
):
    """Test secure mechanical connection."""
    step = function_project.project.steps.mechanical_instance_step
    step.version = ansys_release
    bind_host = product_binding_host or "localhost"

    method = step.launch_mechanical()
    method.wait(timeout=60)
    step.close_mechanical()

    if platform.system() == "Windows" and not product_binding_host:
        assert session_pim.find_msg_in_output(
            f"Arguments: -DSAPPLET,-B,-GRPC,.*,--GRPC-HOST,{bind_host},--transport-mode,WNUA",
            regex=True,
        )
        assert session_pim.find_msg_in_output("Wnua:127.0.0.1")
    else:
        assert session_pim.find_msg_in_output(
            f"Arguments: -DSAPPLET,-B,-GRPC,.*,--GRPC-HOST,{bind_host},--transport-mode,insecure",
            regex=True,
        )
        assert session_pim.find_msg_in_output(f"Insecure:{bind_host}")
    assert session_glow.text_in_output(["WARNING", "mechanical_manager", "Using an insecure gRPC connection."], "api")
