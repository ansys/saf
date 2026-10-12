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
from pathlib import Path
import platform
import tempfile

import pytest

from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.product_manager._utilities.const import LOCALHOSTS
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.hps import GetHpsJobIdsType
from ansys.saf.testing.network import get_local_ip
from ansys.saf.testing.pim.process import PimProcess
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    CustomProjectFilesConfig,
    GlowBaseProcess,
    GlowDockerProcess,
    ProjectFixture,
)
from tests.e2e.conftest import DOCKER_GATEWAY_IP
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.use_fluent,
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.usefixtures("custom_project_files_dir"),
    pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True),
]

STEP_NAME = "fluent-instance-step"
FLUENT_INSECURE_GRPC_WARNING = "WARNING:\nThe current Fluent session is using insecure gRPC mode"


@pytest.fixture(scope="module")
def custom_project_files_dir(session_glow: GlowBaseProcess[EndToEndSolution]) -> Generator[None, None, None]:
    """
    When using pytest's tmp_path, Fluent complains about write permissions. This does not happen if the
    solution is executed outside pytest. We simulate this by using a regular python tempdir instead of pytest's fixture.
    """
    project_files_dir = Path(tempfile.mkdtemp(prefix="glow_e2e_fluent_"))
    container_files_dir = Path("/projects")
    session_glow.change_configuration(
        CustomProjectFilesConfig,
        project_files_dir=project_files_dir,
        container_project_files_dir=container_files_dir,
        is_product_system_different_platform=(
            session_glow.is_product_system_configured if isinstance(session_glow, GlowDockerProcess) else False
        ),
    )
    yield
    session_glow.configure_default_execution()


@pytest.fixture(scope="class")
def step_with_launched_2ddp_solver(
    configure_product_host: None,
    class_project: ProjectFixture[EndToEndSolution],
    ansys_release: str,
) -> YieldFixture[None]:
    step = class_project.project.steps.fluent_instance_step
    step.version = ansys_release
    step.launch_fluent_2ddp_solver().wait()

    yield

    step.close_fluent_2ddp_solver()


@pytest.mark.usefixtures("step_with_launched_2ddp_solver", "configure_product_host")
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
        ("Desktop", get_local_ip(), "0.0.0.0"),  # insecure to cover PIM/HPS. We have tests for secure connection.
        ("DockerCompose", "host.docker.internal", DOCKER_GATEWAY_IP),
    ],
    ids=["desktop_insecure", "dockercompose_mtls"],
    indirect=True,
)
class TestFluent2DDPSolver:
    def test_fluent_solver(self, function_class_project: ProjectFixture[EndToEndSolution]):
        """
        Test that a solution can use a Fluent product instance via the manager classes Fluent2DDPSolverManager with
        any Product Instance System (PIM, HPS) and in any Deployment (Desktop, DockerCompose).
        """
        # GIVEN: launched Fluent instance
        step = function_class_project.project.steps.fluent_instance_step
        step.refresh_fluent_2ddp_solver_availability()
        assert step.fluent_available

        # Instance can be used
        step.use_fluent_2ddp_solver()


@pytest.fixture(scope="class")
def step_with_launched_3ddp_solver(
    configure_product_host: None,
    class_project: ProjectFixture[EndToEndSolution],
    ansys_release: str,
) -> YieldFixture[None]:
    step = class_project.project.steps.fluent_instance_step
    step.version = ansys_release
    step.launch_fluent_3ddp_solver().wait()

    yield

    step.close_fluent_3ddp_solver()


@pytest.mark.usefixtures("step_with_launched_3ddp_solver", "configure_product_host")
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
        ("Desktop", get_local_ip(), "0.0.0.0"),  # insecure to cover PIM/HPS. We have tests for secure connection.
        ("DockerCompose", "host.docker.internal", DOCKER_GATEWAY_IP),
    ],
    ids=["desktop_insecure", "dockercompose_mtls"],
    indirect=True,
)
class TestFluent3DDPSolver:
    def test_fluent_solver_workflow(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        deployment_type: TestDeployment,
    ):
        """
        Test that a solution can use a Fluent product instance via the manager classes Fluent3DDPSolverManager with
        any Product Instance System (PIM, HPS) and in any Deployment (Desktop, DockerCompose).
        """
        # GIVEN: launched Fluent instance
        step = function_class_project.project.steps.fluent_instance_step
        step.refresh_fluent_3ddp_solver_availability()
        assert step.fluent_available

        # WHEN: running an example from fluent documentation that is split between multiple transactions.
        step.import_mesh()
        output = step.run_simulation().wait()
        if deployment_type == TestDeployment.Desktop:
            simulation_output_abs_path = output["simulation_output"]
            max_temperature_file_abs_path = output["max_temperature_file"]
        else:
            simulation_output_rel_path = "/".join(str(output["simulation_output"]).split("/")[3:])
            simulation_output_abs_path = function_class_project.project_files_dir / simulation_output_rel_path
            max_temperature_file_rel_path = "/".join(str(output["max_temperature_file"]).split("/")[3:])
            max_temperature_file_abs_path = function_class_project.project_files_dir / max_temperature_file_rel_path

        assert simulation_output_abs_path.is_file()
        assert max_temperature_file_abs_path.is_file()

    def test_fluent_state_reinitialized(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        restart_product_instance_system: Callable[..., None],
    ):
        """
        Test that Fluent instances are resilient to Product Instance System (PIM, HPS) restarts.
        """
        # GIVEN: launched Fluent instance
        step = function_class_project.project.steps.fluent_instance_step
        step.refresh_fluent_3ddp_solver_availability()
        assert step.fluent_available

        # Fluent files (e.g., sifile, trn file) are in GLOW product space because we launch Fluent
        # using GLOW product space as working directory.
        working_dir = step.get_working_dir_solver()
        trn_files = [
            file for file in list(working_dir.rglob("*")) if file.name.startswith("fluent-") and file.suffix == ".trn"
        ]
        assert len(trn_files) == 1
        si_files = [
            file for file in list(working_dir.rglob("*")) if file.name.startswith("sifile-") and file.suffix == ".txt"
        ]
        assert len(si_files) == 1

        # WHEN: Start simulation example and then restart PIS
        step.import_mesh()
        restart_product_instance_system()

        # THEN: When re-initializing Fluent instance, trying to continue with the simulation
        # it fails to continue since the state is not restored
        method = step.run_simulation()
        with pytest.raises(InternalSolutionException):
            method.wait()

        # We now find 2 sifiles and trn files in GLOW product space, one for each Fluent execution
        working_dir = step.get_working_dir_solver()
        trn_files = [
            file for file in list(working_dir.rglob("*")) if file.name.startswith("fluent-") and file.suffix == ".trn"
        ]
        assert len(trn_files) == 2
        si_files = [
            file for file in list(working_dir.rglob("*")) if file.name.startswith("sifile-") and file.suffix == ".txt"
        ]
        assert len(si_files) == 2


@pytest.fixture(scope="class")
def step_with_launched_3ddp_meshing(
    configure_product_host: None,
    class_project: ProjectFixture[EndToEndSolution],
    ansys_release: str,
) -> YieldFixture[None]:
    step = class_project.project.steps.fluent_instance_step
    step.version = ansys_release
    step.launch_fluent_3ddp_meshing().wait()

    yield

    step.close_fluent_3ddp_meshing()


@pytest.mark.usefixtures("step_with_launched_3ddp_meshing", "configure_product_host")
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
        ("Desktop", get_local_ip(), "0.0.0.0"),  # insecure to cover PIM/HPS. We have tests for secure connection.
        ("DockerCompose", "host.docker.internal", DOCKER_GATEWAY_IP),
    ],
    ids=["desktop_insecure", "dockercompose_mtls"],
    indirect=True,
)
class TestFluent3DDPMeshing:
    def test_fluent_meshing_workflow(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that a solution can use a Fluent product instance via the manager classes Fluent3DDPMeshingManager with
        any Product Instance System (PIM, HPS) and in any Deployment (Desktop, DockerCompose).
        """
        # GIVEN: launched Fluent instance
        step = function_class_project.project.steps.fluent_instance_step
        step.refresh_fluent_3ddp_meshing_availability()
        assert step.fluent_available

        # WHEN: running an example from Fluent documentation that is split between multiple transactions.
        step.prepare_mesh()
        step.generate_mesh().wait()

        # THEN: files generated during the simulation are stored in GLOW product space
        working_dir = step.get_working_dir_meshing()
        mesh_files = [file.name for file in list(working_dir.rglob("*")) if file.is_file() and file.suffix == ".h5"]
        assert sorted(mesh_files) == sorted(
            ["ftm-wf-out-exhaust_system.msh.h5", "TaskObject16.msh.h5", "TaskObject23.msh.h5"],
        )


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host", "enable_insecure_product"),
    [
        ("Desktop", None, None, False),  # product_binding_host defaults to localhost in secure products
        ("Desktop", get_local_ip(), get_local_ip(), False),
        ("Desktop", None, "0.0.0.0", True),
        ("Desktop", get_local_ip(), "0.0.0.0", True),
        ("DockerCompose", "host.docker.internal", DOCKER_GATEWAY_IP, False),
        ("DockerCompose", "host.docker.internal", "0.0.0.0", True),
    ],
    ids=[
        "desktop_wnua_or_uds",
        "desktop_mtls",
        "desktop_localhost_insecure",
        "desktop_insecure",
        "dockercompose_mtls",
        "dockercompose_insecure",
    ],
    indirect=True,
)
@pytest.mark.parametrize("fluent_mode", ["3ddp_solver", "2ddp_solver", "3ddp_meshing"])
def test_secure_fluent_on_hps(
    ansys_release: str,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    deployment_type: TestDeployment,
    product_host: str | None,
    product_binding_host: str | None,
    enable_insecure_product: bool,
    get_hps_job_ids: GetHpsJobIdsType,
    get_hps_job_output: Callable[[str], list[str]],
    certificates_directory: Path,
    fluent_mode: str,
):
    """Test secure fluent connection."""
    job_name = f"fluent-{fluent_mode.replace('_', '-')}-secure-{ansys_release}-GLOW-Instance"
    old_job_ids = get_hps_job_ids(job_name, "all", [])

    step = function_project.project.steps.fluent_instance_step
    step.version = ansys_release

    method = getattr(step, f"launch_fluent_{fluent_mode}")()
    if not product_host and enable_insecure_product and deployment_type == TestDeployment.Desktop:
        with pytest.raises(InternalSolutionException):
            method.wait()
        assert session_glow.text_in_output("Insecure gRPC mode is not allowed when connecting to localhost.", "api")
        return

    method.wait()
    getattr(step, f"close_fluent_{fluent_mode}")()

    job_ids = get_hps_job_ids(job_name, "all", old_job_ids)
    assert len(job_ids) == 1
    job_output = "\n".join(get_hps_job_output(job_ids[0]))

    bind_host = product_binding_host or "localhost"
    if bind_host not in LOCALHOSTS:
        if enable_insecure_product:
            assert (
                "No grpc certificates found for remote, falling back to secure_flags='--transport-mode=insecure'"
                in job_output
            )
            assert FLUENT_INSECURE_GRPC_WARNING in job_output
            assert session_glow.text_in_output(
                ["WARNING", "fluent_manager", "Using an insecure gRPC connection."],
                "api",
            )
        else:
            assert (
                f"Secure flags found for remote: secure_flags='--transport-mode=MTLS --certs-dir={certificates_directory}'"  # noqa: E501
                in job_output
            )
            assert FLUENT_INSECURE_GRPC_WARNING not in job_output
            certs_dir = "/certs" if deployment_type == TestDeployment.DockerCompose else certificates_directory
            assert session_glow.text_in_output(
                [
                    "INFO",
                    "fluent_manager",
                    f"MTLS secure flags found, creating MTLS channel with certificates from {certs_dir}",
                ],
                "api",
            )
    elif platform.system() == "Linux":
        assert "Secure flags found for local linux: secure_flags='--transport-mode=UDS'" in job_output
        assert FLUENT_INSECURE_GRPC_WARNING not in job_output
        assert session_glow.text_in_output(
            [
                "INFO",
                "fluent_manager",
                "UDS secure flags found, creating UDS channel with socket_path=unix:/tmp/",
            ],
            "api",
        )
    else:
        assert "Secure flags found for local windows: secure_flags='--transport-mode=WNUA'" in job_output
        assert FLUENT_INSECURE_GRPC_WARNING not in job_output
        assert session_glow.text_in_output(
            ["INFO", "fluent_manager", "WNUA secure flag found, creating secure channel."],
            "api",
        )


@pytest.mark.usefixtures("configure_product_host")
@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host"),
    [
        ("Desktop", None, None),  # product_binding_host defaults to localhost in secure products
        ("Desktop", None, "0.0.0.0"),
        ("Desktop", get_local_ip(), "0.0.0.0"),
        ("DockerCompose", "host.docker.internal", "0.0.0.0"),
    ],
    ids=["desktop_wnua_or_insecure", "desktop_localhost_insecure", "desktop_insecure", "dockercompose_insecure"],
    indirect=True,
)
@pytest.mark.parametrize("fluent_mode", ["3ddp_solver", "2ddp_solver", "3ddp_meshing"])
class TestFluentSecurePIM:
    def test_secure_fluent_on_pim(
        self,
        ansys_release: str,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
        product_host: str | None,
        product_binding_host: str | None,
        session_pim: PimProcess,
        fluent_mode: str,
    ):
        """Test secure fluent connection."""
        step = function_project.project.steps.fluent_instance_step
        step.version = ansys_release

        bind_host = product_binding_host or "localhost"

        method = getattr(step, f"launch_fluent_{fluent_mode}")()
        if not product_host:
            with pytest.raises(InternalSolutionException):
                method.wait()
            if bind_host in LOCALHOSTS and platform.system() == "Windows":
                assert session_pim.find_msg_in_output("--transport-mode=WNUA")
                assert FLUENT_INSECURE_GRPC_WARNING not in "\n".join(session_pim.output)
            else:
                assert session_pim.find_msg_in_output("--transport-mode=insecure")
                assert FLUENT_INSECURE_GRPC_WARNING in "\n".join(session_pim.output)
            assert session_glow.text_in_output("Insecure gRPC mode is not allowed when connecting to localhost.", "api")
            return

        method.wait()
        getattr(step, f"close_fluent_{fluent_mode}")()

        assert session_pim.find_msg_in_output("--transport-mode=insecure")
        assert FLUENT_INSECURE_GRPC_WARNING in "\n".join(session_pim.output)
        assert session_glow.text_in_output(["WARNING", "fluent_manager", "Using an insecure gRPC connection."], "api")
