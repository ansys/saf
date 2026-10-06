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

import pytest

from ansys.saf.glow.client import Client
from ansys.saf.product_manager._utilities.const import INSECURE_GRPC_MSG, LOCALHOSTS
from ansys.saf.testing.hps import GetHpsJobIdsType
from ansys.saf.testing.network import get_local_ip
from ansys.saf.testing.pim.process import PimProcess
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import (
    GlowBaseProcess,
    ProjectFixture,
)
from tests.e2e.conftest import DOCKER_GATEWAY_IP
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.usefixtures("configure_aedt_installation_dir"),
]


BOX_ORIGIN_LIST = [
    [0.0, 0.0, 0.0],
    [20.0, 1.2, 2.5],
    [10.3, 2.5, 7.4],
    [3.3, 4.4, 5.5],
    [6.6, 7.7, 8.8],
    [2.2, 1.1, 9.9],
]
BOX_DIMENSION_LIST = [
    # Third dimension must be 0.0
    [5.0, 5.0, 0.0],
    [7.5, 5.6, 0.0],
    [1.2, 56.3, 0.0],
    [3.3, 26.3, 0.0],
    [12.2, 6.3, 0.0],
    [4.2, 1.0, 0.0],
]
TOLERANCE = 1e-3


def add_rectangle_from_list(object_index: int, project_fixture: ProjectFixture[EndToEndSolution]) -> None:
    step = project_fixture.project.steps.maxwell_2d_verification_step
    step.origin = BOX_ORIGIN_LIST[object_index]
    step.dimension = BOX_DIMENSION_LIST[object_index][:2]
    step.add_rectangle()


def verify_objects_dimensions(
    expected_objects: list[list[float]],
    project_fixture: ProjectFixture[EndToEndSolution],
) -> None:
    step = project_fixture.project.steps.maxwell_2d_verification_step
    step.upload_object_dimension_from_aedt().wait()
    object_dimension_list = step.object_dimension_list

    for expected_object in expected_objects:
        assert pytest.approx(expected_object, TOLERANCE) in object_dimension_list  # type: ignore


@pytest.fixture(scope="class")
def launch_maxwell2d(class_project: ProjectFixture[EndToEndSolution], ansys_release: str):
    step = class_project.project.steps.maxwell_2d_verification_step
    aedt_version_input = ansys_release
    # Launch AEDT
    step.aedt_version = aedt_version_input
    step.initialize_maxwell_2d_instance().wait(timeout=180)
    yield

    step.exit_aedt()


@pytest.mark.use_aedt
@pytest.mark.usefixtures("launch_maxwell2d")
@pytest.mark.parametrize(
    "instance_system_type",
    [
        pytest.param("PIM", marks=pytest.mark.use_pim),
        pytest.param("HPS", marks=pytest.mark.use_hps),
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    [
        "Desktop",
        pytest.param(
            "DockerCompose",
            marks=pytest.mark.xfail(reason="pyaedt rpyc not working with docker"),
        ),
    ],
    indirect=True,
)
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True)
class TestMaxwell2D:
    def test_maxwell_2d_workflow(self, function_class_project: ProjectFixture[EndToEndSolution], ansys_release: str):
        """
        Test a basic workflow with Maxwell2D.
        """
        # GIVEN: Maxwell2D instance launched
        step = function_class_project.project.steps.maxwell_2d_verification_step
        step.refresh_availability()
        assert step.m2d_available

        # We verify the version of AEDT is correct.
        step.upload_aedt_version_from_aedt().wait()
        assert step.aedt_version == f"ANSYSEM_ROOT{ansys_release}"

        # Create some objects
        add_rectangle_from_list(0, function_class_project)
        verify_objects_dimensions(BOX_DIMENSION_LIST[:1], function_class_project)

        # A project can be manually saved and loaded
        assert step.save_project()
        assert step.export_variables()

        # Saved files in project
        scope = function_class_project.project.storage_scope
        assert scope.get_cached(step.aedt_project_file).exists()
        assert scope.get_cached(step.aedt_variables_file).exists()

        # Add another rectangle. This will be saved automatically in the project that is kept by the manager, but
        # it should be ignored if we load another project.
        add_rectangle_from_list(1, function_class_project)
        verify_objects_dimensions(BOX_DIMENSION_LIST[:2], function_class_project)
        assert step.load_project()

        verify_objects_dimensions(BOX_DIMENSION_LIST[:1], function_class_project)

    def test_maxwell_2d_state_reinitialized(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        restart_product_instance_system: Callable[..., None],
        ansys_release: str,
    ):
        """
        Test that a Maxwell2D product instance can be restored after the Product Instance System is restarted.
        """
        # GIVEN: Maxwell2D instance launched
        step = function_class_project.project.steps.maxwell_2d_verification_step
        step.refresh_availability()
        assert step.m2d_available

        # We verify the version of AEDT is correct.
        step.upload_aedt_version_from_aedt().wait()
        assert step.aedt_version == f"ANSYSEM_ROOT{ansys_release}"

        # The project contains some objects
        step.upload_object_dimension_from_aedt().wait()
        object_dimension_list = step.object_dimension_list
        if not object_dimension_list:
            # in case test_maxwell_2d_workflow wasn't executed before
            add_rectangle_from_list(0, function_class_project)
            step.upload_object_dimension_from_aedt().wait()
            object_dimension_list = step.object_dimension_list

        # WHEN: Restarting PIS

        restart_product_instance_system()

        # THEN: The instance remains usable and can be closed to end the workflow.
        verify_objects_dimensions(object_dimension_list, function_class_project)

    def test_concurrent_shared_instances(
        self,
        function_class_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
        ansys_release: str,
    ):
        """
        Test concurrent shared Maxwell2D instances.

        Initial PoCs of AEDT in on-prem deployments shown that a single product client process
        couldn't handle connections to multiple product instances, unless the transaction
        was marked as longrunning (so the client would be created in a separated method proc).
        """
        # GIVEN: Maxwell2D instance launched
        step = function_class_project.project.steps.maxwell_2d_verification_step
        step.refresh_availability()
        assert step.m2d_available

        # We verify the version of AEDT is correct.
        step.upload_aedt_version_from_aedt().wait()
        assert step.aedt_version == f"ANSYSEM_ROOT{ansys_release}"

        # The project already contains some objects
        step.upload_object_dimension_from_aedt().wait()
        object_dimension_list = step.object_dimension_list
        if not object_dimension_list:
            # in case test_maxwell_2d_workflow wasn't executed before
            add_rectangle_from_list(0, function_class_project)
            step.upload_object_dimension_from_aedt().wait()
            object_dimension_list = step.object_dimension_list

        # Setup second project and launch a second Maxwell2D instance
        with ProjectFixture(session_glow, function_client) as second_project:
            step_b = second_project.project.steps.maxwell_2d_verification_step
            step_b.aedt_version = ansys_release
            step_b.initialize_maxwell_2d_instance().wait()

            # Use both instances with regular and longrunning transactions, make sure
            # steps execution is not synchronized between both projects, so
            # avoid pattern: call f1 in project1, call f1 in project2, call f2 in project1, call f2 in project2, etc.
            add_rectangle_from_list(3, function_class_project)
            add_rectangle_from_list(1, second_project)
            add_rectangle_from_list(4, function_class_project)
            verify_objects_dimensions([BOX_DIMENSION_LIST[i] for i in [0, 3, 4]], function_class_project)
            verify_objects_dimensions(BOX_DIMENSION_LIST[1:2], second_project)
            add_rectangle_from_list(5, function_class_project)
            verify_objects_dimensions([BOX_DIMENSION_LIST[i] for i in [0, 3, 4, 5]], function_class_project)
            add_rectangle_from_list(0, second_project)
            verify_objects_dimensions(BOX_DIMENSION_LIST[:2], second_project)

            # shutdown product from additional instance
            step_b.exit_aedt()


@pytest.mark.use_aedt
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host", "enable_insecure_product"),
    [
        ("Desktop", None, None, False),  # product_binding_host defaults to localhost in secure products
        ("Desktop", get_local_ip(), get_local_ip(), False),
        ("Desktop", None, "0.0.0.0", True),
        ("Desktop", get_local_ip(), "0.0.0.0", True),
        pytest.param(
            "DockerCompose",
            "host.docker.internal",
            DOCKER_GATEWAY_IP,
            False,
            marks=pytest.mark.xfail(reason="pyaedt rpyc not working with docker"),
        ),
        pytest.param(
            "DockerCompose",
            "host.docker.internal",
            "0.0.0.0",
            True,
            marks=pytest.mark.xfail(reason="pyaedt rpyc not working with docker"),
        ),
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
class TestMaxwell2DSecureHPS:
    def test_secure_maxwell_2d_on_hps(
        self,
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
    ):
        """Test secure Maxwell 2D connection."""
        job_name = f"aedt-{ansys_release}-GLOW-Instance"
        old_job_ids = get_hps_job_ids(job_name, "all", [])

        step = function_project.project.steps.maxwell_2d_verification_step
        step.aedt_version = ansys_release

        step.initialize_maxwell_2d_instance().wait(timeout=180)
        step.exit_aedt()

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
                assert session_glow.text_in_output(
                    ["WARNING", "_aedt_managers", INSECURE_GRPC_MSG],
                    "api",
                )
            else:
                assert (
                    f"Secure flags found for remote: secure_flags='--transport-mode=MTLS --certs-dir={certificates_directory}'"  # noqa: E501
                    in job_output
                )
                certs_dir = "/certs" if deployment_type == TestDeployment.DockerCompose else certificates_directory
                assert session_glow.text_in_output(
                    [
                        "INFO",
                        "_aedt_managers",
                        f"MTLS secure flags found, creating MTLS channel with certificates from {certs_dir}",
                    ],
                    "api",
                )
        elif platform.system() == "Linux":
            assert "Secure flags found for local linux: secure_flags='--transport-mode=UDS'" in job_output
            assert session_glow.text_in_output(
                [
                    "INFO",
                    "_aedt_managers",
                    "UDS secure flag found, creating secure channel.",
                ],
                "api",
            )
        else:
            assert "Secure flags found for local windows: secure_flags='--transport-mode=WNUA'" in job_output
            assert session_glow.text_in_output(
                ["INFO", "_aedt_managers", "WNUA secure flag found, creating secure channel."],
                "api",
            )


@pytest.mark.use_aedt
@pytest.mark.usefixtures("configure_product_host")
@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host"),
    [
        ("Desktop", None, None),  # product_binding_host defaults to localhost in secure products
        ("Desktop", None, "0.0.0.0"),
        ("Desktop", get_local_ip(), "0.0.0.0"),
        pytest.param(
            "DockerCompose",
            "host.docker.internal",
            "0.0.0.0",
            marks=pytest.mark.xfail(reason="pyaedt rpyc not working with docker"),
        ),
    ],
    ids=["desktop_wnua_or_insecure", "desktop_localhost_insecure", "desktop_insecure", "dockercompose_insecure"],
    indirect=True,
)
class TestMaxwell2DSecurePIM:
    def test_secure_maxwell_2d_on_pim(
        self,
        ansys_release: str,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
        product_host: str | None,
        product_binding_host: str | None,
        session_pim: PimProcess,
    ):
        """Test secure Maxwell 2D connection."""
        step = function_project.project.steps.maxwell_2d_verification_step
        step.aedt_version = ansys_release

        bind_host = product_binding_host or "localhost"

        step.initialize_maxwell_2d_instance().wait(timeout=180)
        if not product_host and bind_host in LOCALHOSTS and platform.system() == "Windows":
            assert session_pim.find_msg_in_output("--transport-mode=WNUA")
            assert session_pim.find_msg_in_output(
                "Launching AEDT server with gRPC transport mode: TransportMode.WNUA",
            )
            assert not session_glow.text_in_output(["WARNING", "_aedt_managers", INSECURE_GRPC_MSG], "api")
        else:
            assert session_pim.find_msg_in_output("--transport-mode=insecure")
            assert session_pim.find_msg_in_output(
                "Launching AEDT server with gRPC transport mode: TransportMode.INSECURE",
            )
            assert session_glow.text_in_output(["WARNING", "_aedt_managers", INSECURE_GRPC_MSG], "api")

        step.exit_aedt()
