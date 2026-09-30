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

from ansys.saf.glow.client import Client
from ansys.saf.product_manager._utilities.const import LOCALHOSTS
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.network import get_local_ip
from ansys.saf.testing.pim.process import PimProcess
from ansys.saf.testing.solution.const import TestDeployment, TestProductInstanceSystemType
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.e2e.conftest import DOCKER_GATEWAY_IP
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.use_mapdl,
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True),
]


@pytest.fixture(scope="class")
def launch_mapdl(
    class_project: ProjectFixture[EndToEndSolution],
    ansys_release: str,
) -> YieldFixture[None]:
    step = class_project.project.steps.mapdl_step

    step.version = ansys_release
    step.launch_mapdl().wait()

    step.prepare_env()
    step.setup_fe_model()

    yield

    step.close_mapdl()


@pytest.mark.usefixtures("launch_mapdl")
@pytest.mark.parametrize(
    "instance_system_type",
    [
        pytest.param("PIM", marks=pytest.mark.use_pim),
        pytest.param("HPS", marks=pytest.mark.use_hps),
    ],
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
class TestMapdl:
    def test_mapdl_workflow(self, function_class_project: ProjectFixture[EndToEndSolution]):
        """
        Test that MAPDL product instance managers are working as expected on a complete product workflow.
        """
        # GIVEN: launched Mapdl instance
        step = function_class_project.project.steps.mapdl_step
        step.refresh_availability()
        assert step.mapdl_available

        # WHEN: Running example, copied from
        # https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/2d_magnetostatic_solenoid-BodyFlux_Averaging.html#set-up-the-fe-model
        step.solve_model().wait()
        step.postprocessing()

        # THEN: simulation results are OK
        assert step.nodal_values

    def test_mapdl_state_reinitialized(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        restart_product_instance_system: Callable[..., None],
    ):
        """
        Test that MAPDL instances are resilient to Product Instance System (PIM, HPS) restarts.
        """

        # GIVEN: launched Mapdl instance
        step = function_class_project.project.steps.mapdl_step
        step.refresh_availability()
        assert step.mapdl_available
        if not step.solved:
            # Make the test valid even if the workflow test was not run before.
            step.solve_model().wait()

        # WHEN: Restarting PIS
        restart_product_instance_system()

        # THEN: The instance remains usable and can be closed to end the workflow.
        step.postprocessing()
        assert step.nodal_values
        # In case it becomes relevant: seems that MAPDL automatically stores/loads the db from a file called "file.db".
        # This may be logged: "Could not save MAPDL DB. This MAPDL version is not compatible with the Database module."

    def test_mapdl_transfer_files_working_directory(self, function_class_project: ProjectFixture[EndToEndSolution]):
        """
        Test that files can be uploaded to and downloaded from the mapdl working directory (product space).
        """
        # GIVEN: Mapdl instance launched
        step = function_class_project.project.steps.mapdl_step
        step.refresh_availability()
        assert step.mapdl_available

        # WHEN: Running transaction that uploads file to product space using pymapdl method
        step.upload_files()
        # THEN: File is also in MAPDL's working directory (it's the same as the product space)
        step.list_files()
        mapdl_working_files = step.files_in_working_dir
        assert "test_file.txt" in mapdl_working_files
        test_file = [file for file in mapdl_working_files if "test_file.txt" in file]
        assert test_file
        test_file = Path(step.working_dir) / test_file[0]

        # WHEN: Running transaction that downloads file from product space using pymapdl method
        random_text = str(uuid.uuid4())
        test_file.write_text(random_text)
        step.download_files()
        # THEN: File is downloaded to project dir
        assert function_class_project.project.storage_scope.get_text(step.test_file) == random_text

    def test_mapdl_client_cleanup(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
    ):
        """
        Test that the MAPDL client is cleaned up after every transaction.
        """
        # GIVEN: Mapdl instance launched
        step = function_class_project.project.steps.mapdl_step
        step.refresh_availability()
        assert step.mapdl_available

        # WHEN: Launching multiple transactions that use the instance and will spawn Mapdl clients
        for _ in range(3):
            step.log_message()

        mapdl_log_lines = 0
        glow_log_lines = 0
        for line in session_glow.api_output:
            if "mapdl_step - log_message - Simulates warning message from mapdl." in line:
                mapdl_log_lines += 1
            if "=GLOW API]- Simulates warning message from mapdl." in line:
                glow_log_lines += 1
        # THEN: Loggers keep accumulating so we expect every Mapdl log message to appear N times
        assert mapdl_log_lines > 3
        # and it's also handled by the GLOW loggers, although it only appears 1 per invoke in this case
        assert glow_log_lines == 3

    def test_concurrent_shared_instances(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
        instance_system_type: TestProductInstanceSystemType,
        request: pytest.FixtureRequest,
    ):
        """
        Test that MAPDL supports two instances run con concurrent GLOW processes.
        """
        if platform.system() == "Windows" and instance_system_type == TestProductInstanceSystemType.PIM:
            pytest.xfail(reason="Concurrent MAPDL in Windows using PIM does not work and times out. See issue #1006.")

        # GIVEN: launched Mapdl instance
        step_a = function_class_project.project.steps.mapdl_step
        step_a.refresh_availability()
        assert step_a.mapdl_available

        # Setup second project and launch a second Mapdl instance
        with ProjectFixture(session_glow, function_client) as second_project:
            step_b = second_project.project.steps.mapdl_step
            step_b.version = step_a.version
            step_b.launch_mapdl().wait()

            # Use both instances with regular and longrunning transactions, make sure
            # steps execution is not synchronized between both projects, so
            # avoid pattern: call f1 in project1, call f1 in project2, call f2 in project1, call f2 in project2, etc.
            step_a.prepare_env()
            step_a.setup_fe_model()
            step_b.prepare_env()
            method = step_a.solve_model()
            step_b.setup_fe_model()
            step_b.solve_model().wait()
            step_b.postprocessing()
            method.wait()
            step_a.postprocessing()
            assert step_a.nodal_values
            assert step_b.nodal_values

            # shutdown second Mapdl instance and project
            step_b.close_mapdl()


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
        "desktop_wnua_or_uds",
        "desktop_mtls",
        "desktop_insecure",
        "dockercompose_mtls",
        "dockercompose_insecure",
    ],
    indirect=True,
)
def test_secure_mapdl_on_hps(
    ansys_release: str,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    deployment_type: TestDeployment,
    product_binding_host: str | None,
    enable_insecure_product: bool,
    certificates_directory: Path,
):
    """Test secure mapdl connection."""
    step = function_project.project.steps.mapdl_step
    step.version = ansys_release

    bind_host = product_binding_host or "localhost"

    step.launch_mapdl().wait()
    step.close_mapdl()

    # Due to a bug between MAPDL and HPS, the console_output is available through the UI but not through the HPS Client.
    # Hence, all asserts regarding the flags passed to MAPDL and MAPDL's output cannot be done. Left here as a reference
    # in case the bug it's solved.
    if bind_host not in LOCALHOSTS:
        if enable_insecure_product:
            # Job output should contain:
            # - "No grpc certificates found for remote, falling back to secure_flags='-transport insecure -allowremote true'"  # noqa: E501
            # - ################################################
            #   #####    *INSECURE* GRPC SERVER STARTED    #####
            #   ################################################
            #   Transport Mode           : INSECURE
            #   Server Executable        : MapdlGrpc.Server
            #   Server listening on      : 0.0.0.0:53321
            #   Allow remote connections : True
            assert session_glow.text_in_output(
                ["WARNING", "mapdl_manager", "Using an insecure gRPC connection."],
                "api",
            )
        else:
            # Job output should contain:
            # - "Secure flags found for remote: secure_flags='-transport mtls -allowremote true'"
            # - ############################################
            #   #####    SECURE GRPC SERVER STARTED    #####
            #   ############################################
            #   Transport Mode           : MTLS
            #   Server Executable        : MapdlGrpc.Server
            #   Server listening on      : 0.0.0.0:53321
            #   Allow remote connections : True
            certs_dir = "/certs" if deployment_type == TestDeployment.DockerCompose else certificates_directory
            assert session_glow.text_in_output(
                [
                    "INFO",
                    "mapdl_manager",
                    f"MTLS secure flags found, creating MTLS channel with certificates from {certs_dir}",
                ],
                "api",
            )
    elif platform.system() == "Linux":
        # Job output should contain:
        # - "Secure flags found for local linux: secure_flags='-transport uds'"
        # - ############################################
        #   #####    SECURE GRPC SERVER STARTED    #####
        #   ############################################
        #   Transport Mode           : UDS
        #   Server Executable        : MapdlGrpc.Server
        #   Server listening on      : unix:/tmp/mapdl-37601.sock
        #   Allow remote connections : False
        assert session_glow.text_in_output(
            [
                "INFO",
                "mapdl_manager",
                "UDS secure flags found, creating UDS channel with uds_dir=/tmp and uds_id=",
            ],
            "api",
        )
    else:
        # Job output should contain:
        # - "Secure flags found for local windows: secure_flags='-transport wnua'" in job_output
        # In Windows, MAPDL output is in a different console and doesn't go to the HPS output.
        # Leaving expected output as reference.
        # - ############################################
        #   #####    SECURE GRPC SERVER STARTED    #####
        #   ############################################
        #   Transport Mode           : WNUA
        #   Server Executable        : MapdlGrpc.Server
        #   Server listening on      : 127.0.0.1:7000
        #   Allow remote connections : False
        assert session_glow.text_in_output(
            ["INFO", "mapdl_manager", "WNUA secure flag found, creating secure channel."],
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
def test_secure_mapdl_on_pim(
    ansys_release: str,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    product_binding_host: str | None,
    session_pim: PimProcess,
):
    """Test secure mapdl connection."""
    step = function_project.project.steps.mapdl_step
    step.version = ansys_release

    mapdl_port = step.launch_mapdl().wait()
    step.close_mapdl()

    # In Windows, MAPDL output is in a different console and doesn't go to the PIM output.
    # Leaving expected output as reference.
    if platform.system() == "Windows" and not product_binding_host:
        assert session_pim.find_msg_in_output("-transport,wnua")
        # MAPDL output should contain:
        # - ############################################
        #   #####    SECURE GRPC SERVER STARTED    #####
        #   ############################################
        #   Transport Mode           : WNUA
        #   Server Executable        : MapdlGrpc.Server
        #   Server listening on      : 127.0.0.1:7000
        #   Allow remote connections : False
    else:
        assert session_pim.find_msg_in_output("-transport,insecure,-allowremote,true")
        if platform.system() == "Linux":
            expected_msg = (
                " #####    *INSECURE* GRPC SERVER STARTED    #####\n"
                " ################################################\n"
                " Transport Mode           : INSECURE\n"
                " Server Executable        : MapdlGrpc.Server\n"
                f" Server listening on      : 0.0.0.0:{mapdl_port}\n"
                " Allow remote connections : True\n"
            )
            assert expected_msg in "\n".join(session_pim.output)
    # GLOW logs show insecure in all scenarios for now, because there is no reliable way to know
    # whether the product was launched with WNUA or not.
    assert session_glow.text_in_output(["WARNING", "mapdl_manager", "Using an insecure gRPC connection."], "api")
