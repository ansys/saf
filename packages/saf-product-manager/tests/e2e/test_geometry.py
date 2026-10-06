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

from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.product_manager._utilities.const import LOCALHOSTS
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.hps import GetHpsJobIdsType
from ansys.saf.testing.network import get_local_ip
from ansys.saf.testing.pim.process import PimProcess
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import GeometryVersionConfiguration, GlowBaseProcess, ProjectFixture
from tests.e2e.conftest import (
    DOCKER_GATEWAY_IP,
    GEOMETRY_251_ERROR_MSGS,
    get_geometry_expected_msg,
)
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)]


@pytest.fixture(scope="module", autouse=True)
def cleanup_session_glow(session_glow: GlowBaseProcess[EndToEndSolution]) -> YieldFixture[None]:
    yield
    session_glow.configure_default_execution()


@pytest.fixture(scope="class")
def configure_geometry_env_vars(
    ansys_release: str,
    session_glow: GlowBaseProcess[EndToEndSolution],
) -> None:
    session_glow.change_configuration(GeometryVersionConfiguration, version=ansys_release)


@pytest.fixture(scope="class")
def launch_geometry(
    class_project: ProjectFixture[EndToEndSolution],
    session_glow: GlowBaseProcess[EndToEndSolution],
    ansys_release: str,
    configure_geometry_env_vars: None,
) -> YieldFixture[list[str]]:
    step = class_project.project.steps.geometry_instance_step
    step.version = ansys_release

    # deprecation warning only appears after launching the Geometry Service.
    method = step.launch_geometry()

    if platform.system() != "Linux" or ansys_release != "251":
        method.wait()
        assert method.get_state().status.value == "completed"
        step.refresh_availability()
        assert step.geometry_available
        step.extrude_slot()
    else:
        with pytest.raises(InternalSolutionException):
            method.wait()

    yield session_glow.api_output.copy()

    if platform.system() != "Linux" or ansys_release != "251":
        step.close_geometry()
        assert not step.geometry_available


@pytest.mark.use_geometry
@pytest.mark.usefixtures("launch_geometry")
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION, "261"], indirect=True)
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
class TestGeometry:
    def test_geometry_workflow(
        self,
        ansys_release: str,
        launch_geometry: list[str],
        function_class_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test a basic workflow with Geometry.
        """
        if platform.system() == "Linux" and ansys_release == "251":
            assert any(msg in "\n".join(launch_geometry) for msg in GEOMETRY_251_ERROR_MSGS)
            return

        # GIVEN: launched Geometry instance with a created design
        step = function_class_project.project.steps.geometry_instance_step
        step.refresh_availability()
        assert step.geometry_available

        # THEN: the instance behaves as expected
        faces = step.body_faces
        edges = step.body_edges
        assert faces == 6
        assert edges == 12

        # THEN: the instance can be accessed from different transaction methods
        step.get_active_design()
        assert step.active_design_name == "ExtrudeSlot"

    def test_geometry_state_reinitialized(
        self,
        ansys_release: str,
        launch_geometry: list[str],
        function_class_project: ProjectFixture[EndToEndSolution],
        restart_product_instance_system: Callable[..., None],
    ):
        """
        Test that a Geometry product instance can be restored after the Product Instance System is restarted.
        """
        if platform.system() == "Linux" and ansys_release == "251":
            assert any(msg in "\n".join(launch_geometry) for msg in GEOMETRY_251_ERROR_MSGS)
            return

        # GIVEN: launched Geometry instance with a created design
        step = function_class_project.project.steps.geometry_instance_step
        step.refresh_availability()
        assert step.geometry_available

        # WHEN: Restarting PIS
        restart_product_instance_system()

        # THEN: The instance remains usable and can be closed to end the workflow.
        step.active_design_name = ""
        step.get_active_design()
        assert step.active_design_name == "ExtrudeSlot"

    def test_geometry_client_cleanup(
        self,
        ansys_release: str,
        launch_geometry: list[str],
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_class_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that the Geometry client is cleaned up after every transaction.
        """
        if platform.system() == "Linux" and ansys_release == "251":
            assert any(msg in "\n".join(launch_geometry) for msg in GEOMETRY_251_ERROR_MSGS)
            return

        # GIVEN: launched Geometry instance with a created design
        step = function_class_project.project.steps.geometry_instance_step
        step.refresh_availability()
        assert step.geometry_available

        # WHEN: Launching multiple transactions that use the instance and spawn Modeler (Geometry) clients
        for _ in range(3):
            step.log_message()

        glow_log_lines = 0
        geometry_log_lines = 0
        for line in session_glow.api_output:
            if "=GLOW API]- Simulates error message from Geometry." in line:
                glow_log_lines += 1
            if "geometry_instance_step - log_message - Simulates error message from Geometry." in line:
                geometry_log_lines += 1

        # THEN: the log only appears once per run.
        assert glow_log_lines == 3
        assert geometry_log_lines == 3


@pytest.mark.use_geometry
@pytest.mark.usefixtures("configure_geometry_env_vars")
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION, "261"], indirect=True)
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
    ids=["desktop_wnua_or_uds", "desktop_mtls", "desktop_insecure", "dockercompose_mtls", "dockercompose_insecure"],
    indirect=True,
)
def test_secure_geometry_on_hps(
    ansys_release: str,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    deployment_type: TestDeployment,
    product_binding_host: str | None,
    enable_insecure_product: bool,
    get_hps_job_ids: GetHpsJobIdsType,
    get_hps_job_output: Callable[[str], list[str]],
    certificates_directory: Path,
):
    """Test secure geometry connection."""
    job_name = f"geometry-secure-{ansys_release}-GLOW-Instance"
    old_job_ids = get_hps_job_ids(job_name, "all", [])

    step = function_project.project.steps.geometry_instance_step
    step.version = ansys_release

    method = step.launch_geometry()

    if platform.system() == "Linux" and ansys_release == "251":
        with pytest.raises(InternalSolutionException):
            method.wait()
        return

    method.wait()
    assert method.get_state().status.value == "completed"
    step.refresh_availability()
    assert step.geometry_available
    step.close_geometry()
    assert not step.geometry_available

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
            assert get_geometry_expected_msg(ansys_release, "insecure", bind_host) in job_output
            assert session_glow.text_in_output(
                ["WARNING", "geometry_manager", "Using an insecure gRPC connection."],
                "api",
            )
        else:
            assert (
                f"Secure flags found for remote: secure_flags='--transport-mode=MTLS --certs-dir={certificates_directory}'"  # noqa: E501
                in job_output
            )
            assert get_geometry_expected_msg(ansys_release, "mTLS", bind_host) in job_output
            certs_dir = "/certs" if deployment_type == TestDeployment.DockerCompose else certificates_directory
            assert session_glow.text_in_output(
                [
                    "INFO",
                    "geometry_manager",
                    f"MTLS secure flags found, creating MTLS channel with certificates from {certs_dir}",
                ],
                "api",
            )
    elif platform.system() == "Linux":
        assert (
            "Secure flags found for local linux: secure_flags='--transport-mode=UDS --uds-dir=/tmp --uds-id=glow-"
            in job_output
        )
        assert get_geometry_expected_msg(ansys_release, "UDS", bind_host) in job_output
        assert session_glow.text_in_output(
            [
                "INFO",
                "geometry_manager",
                "UDS secure flags found, creating UDS channel with uds_dir=/tmp and uds_id=glow-",
            ],
            "api",
        )
    else:
        assert "Secure flags found for local windows: secure_flags='--transport-mode=WNUA'" in job_output
        assert get_geometry_expected_msg(ansys_release, "WNUA", bind_host) in job_output
        assert session_glow.text_in_output(
            ["INFO", "geometry_manager", "WNUA secure flag found, creating secure channel."],
            "api",
        )


@pytest.mark.use_geometry
@pytest.mark.usefixtures("configure_geometry_env_vars")
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION, "261"], indirect=True)
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
def test_secure_geometry_on_pim(
    ansys_release: str,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    product_binding_host: str | None,
    session_pim: PimProcess,
):
    """Test secure geometry connection."""
    step = function_project.project.steps.geometry_instance_step
    step.version = ansys_release

    method = step.launch_geometry()

    if platform.system() == "Linux" and ansys_release == "251":
        with pytest.raises(InternalSolutionException):
            method.wait()
        return

    method.wait()
    assert method.get_state().status.value == "completed"
    step.refresh_availability()
    assert step.geometry_available
    step.close_geometry()
    assert not step.geometry_available

    if platform.system() == "Windows" and not product_binding_host:
        assert session_pim.find_msg_in_output("--transport-mode=WNUA")
        assert session_pim.find_msg_in_output(get_geometry_expected_msg(ansys_release, "WNUA", "127.0.0.1"))
    else:
        bind_host = product_binding_host or "localhost"
        assert session_pim.find_msg_in_output("--transport-mode=insecure")
        assert session_pim.find_msg_in_output(get_geometry_expected_msg(ansys_release, "insecure", bind_host))
    # GLOW logs show insecure in all scenarios for now, because there is no reliable way to know
    # whether the product was launched with WNUA or not.
    assert session_glow.text_in_output(["WARNING", "geometry_manager", "Using an insecure gRPC connection."], "api")
