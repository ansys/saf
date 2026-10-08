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
import re

import pytest

from ansys.saf.glow._config.const import LOCALHOST_HOSTS
from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.hps import GetHpsJobIdsType
from ansys.saf.testing.network import get_docker_gateway_ip, get_local_ip
from ansys.saf.testing.pim.process import PimProcess
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, NoGrpcCertificates, ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.use_instances,
]

DOCKER_GATEWAY_IP = get_docker_gateway_ip() if platform.system() == "Linux" else "127.0.0.1"
EXPECTED_SECURE_FLAGS = {
    "custom_grpc_product_secure": {
        "insecure": "--transport-mode=insecure",
        "wnua": "--transport-mode=WNUA",
        "uds": "--transport-mode=UDS --uds-dir=/tmp --uds-id={uds_id}",
        "mtls": "--transport-mode=MTLS --certs-dir={certs_dir}",
    },
    "custom_grpc_product_secure_2": {
        "insecure": "-transport insecure",
        "wnua": "-transport wnua",
        "uds": "-transport uds",
        "mtls": "-transport mtls",
    },
    "custom_grpc_product_secure_mtls": {
        "insecure": "--transport-mode=insecure",
        "wnua": "--transport-mode=WNUA --certs-dir={certs_dir}",
        "uds": "--transport-mode=MTLS --certs-dir={certs_dir}",
        "mtls": "--transport-mode=MTLS --certs-dir={certs_dir}",
    },
}


@pytest.mark.parametrize(
    "custom_product",
    ["custom_grpc_product_secure", "custom_grpc_product_secure_2", "custom_grpc_product_secure_mtls"],
)
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host", "enable_insecure_product"),
    [
        ("Desktop", None, None, False),  # product_binding_host defaults to localhost in secure products
        ("Desktop", get_local_ip(), get_local_ip(), False),
        ("Desktop", None, "0.0.0.0", True),
        pytest.param(
            "DockerCompose",
            "host.docker.internal",
            DOCKER_GATEWAY_IP,
            False,
            marks=pytest.mark.use_containerized,
        ),
        pytest.param("DockerCompose", "host.docker.internal", "0.0.0.0", True, marks=pytest.mark.use_containerized),
    ],
    ids=["desktop_wnua_or_uds", "desktop_mtls", "desktop_insecure", "dockercompose_mtls", "dockercompose_insecure"],
    indirect=True,
)
def test_grpc_product_with_secure_channel_hps(
    deployment_type: TestDeployment,
    function_project: ProjectFixture[EndToEndSolution],
    session_glow: GlowBaseProcess[EndToEndSolution],
    product_host: str | None,
    product_binding_host: str | None,
    enable_insecure_product: bool,
    get_hps_job_ids: GetHpsJobIdsType,
    get_hps_job_output: Callable[[str], list[str]],
    certificates_directory: Path,
    custom_product: str,
):
    """When using HPS as instance management system, secure gRPC channels between GLOW and the product can be
    established for any OS and binding host."""
    product_host = product_host or "localhost"
    certs_dir = certificates_directory if deployment_type == TestDeployment.Desktop else "/certs"

    job_name = f"{custom_product.replace('_', '-')}-1-GLOW-Instance"
    old_job_ids = get_hps_job_ids(job_name, "all", [])

    step = function_project.project.steps.custom_grpc_shared_instance_step
    getattr(step, f"initialize_{custom_product}_instance")().wait()
    getattr(step, f"shutdown_{custom_product}_instance")()

    job_ids = get_hps_job_ids(job_name, "all", old_job_ids)
    assert len(job_ids) == 1
    job_output = "\n".join(get_hps_job_output(job_ids[0]))

    # THEN: In every scenario, assert log lines from product server, GLOW healthcheck and product client
    if enable_insecure_product:
        secure_flags = EXPECTED_SECURE_FLAGS[custom_product]["insecure"]
        assert (f"No grpc certificates found for remote, falling back to secure_flags='{secure_flags}'") in job_output
        assert session_glow.text_in_output(
            [
                f"Health check: creating insecure grpc channel with uri={product_host}:",
                "and localhost as default authority",
            ],
        )
        assert session_glow.text_in_output("Connecting to MockProduct using: insecure")
    elif product_binding_host and product_binding_host not in LOCALHOST_HOSTS:
        secure_flags = EXPECTED_SECURE_FLAGS[custom_product]["mtls"].format(certs_dir=certificates_directory)
        assert f"Secure flags found for remote: secure_flags='{secure_flags}'" in job_output
        assert session_glow.text_in_output(
            [f"Health check: creating secure grpc channel with uri={product_host}:", f"and certificates={certs_dir}"],
        )
        assert session_glow.text_in_output("Connecting to MockProduct using: mtls")
    elif platform.system() == "Windows":
        secure_flags = EXPECTED_SECURE_FLAGS[custom_product]["wnua"]
        assert f"Secure flags found for local windows: secure_flags='{secure_flags}'" in job_output
        assert session_glow.text_in_output([f"Health check: creating secure grpc channel with uri={product_host}:"])
        assert session_glow.text_in_output("Connecting to MockProduct using: wnua")
    else:
        if custom_product in ["custom_grpc_product_secure", "custom_grpc_product_secure_mtls"]:
            task_id_match = re.search(r"task_id:\s*(\S+)", job_output)
            assert task_id_match
            task_id = task_id_match.group(1)
            uds_id = f"glow-{task_id}"
        else:
            mock_port_match = re.search(r"'MOCK_PORT':\s*'(\d+)'", job_output)
            assert mock_port_match
            mock_port = mock_port_match.group(1)
            uds_id = mock_port
        if custom_product == "custom_grpc_product_secure_mtls":
            secure_flags = EXPECTED_SECURE_FLAGS[custom_product]["uds"].format(certs_dir=certificates_directory)
        else:
            secure_flags = EXPECTED_SECURE_FLAGS[custom_product]["uds"].format(uds_id=uds_id)
        assert f"Secure flags found for local linux: secure_flags='{secure_flags}'" in job_output
        if custom_product != "custom_grpc_product_secure_mtls":
            assert session_glow.text_in_output(
                f"Health check: creating secure grpc channel with uri=unix:/tmp/mockproduct-{uds_id}.sock",
            )
            assert session_glow.text_in_output("Connecting to MockProduct using: uds")


@pytest.fixture(scope="class")
def unset_grpc_certificates(session_glow: GlowBaseProcess[EndToEndSolution]) -> YieldFixture[None]:
    session_glow.change_configuration(NoGrpcCertificates)
    yield
    session_glow.configure_default_execution()


@pytest.mark.usefixtures("unset_grpc_certificates")
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
class TestGrpcMtlsFallback:
    @pytest.mark.parametrize(
        ("deployment_type", "product_host", "product_binding_host"),
        [
            ("Desktop", get_local_ip(), get_local_ip()),
            pytest.param(
                "DockerCompose",
                "host.docker.internal",
                DOCKER_GATEWAY_IP,
                marks=pytest.mark.use_containerized,
            ),
        ],
        ids=["desktop_fallback", "dockercompose_fallback"],
        indirect=True,
    )
    def test_healthcheck_fallsback_to_insecure_when_missing_grpc_certificates(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        product_host: str,
    ):
        """In the case of MTLS with missing certificates, GLOW fallsback to insecure mode. However, this will make the
        connection with the product to fail."""
        step = function_project.project.steps.custom_grpc_shared_instance_step
        with pytest.raises(InternalSolutionException):
            step.initialize_custom_grpc_product_secure_instance().wait()

        # Only asserting GLOW side. Asserting also that the product was launched using MTLS and certificates is not
        # trivial. The HPS job is deleted immediately after the healthcheck fails.
        assert session_glow.text_in_output(
            [f"Health check: creating insecure grpc channel with uri={product_host}:", "without certificates"],
        )

    @pytest.mark.parametrize(
        ("deployment_type", "product_host", "product_binding_host"),
        [
            ("Desktop", None, None),  # product_binding_host defaults to localhost in secure products
            ("Desktop", get_local_ip(), get_local_ip()),
            pytest.param(
                "DockerCompose",
                "host.docker.internal",
                DOCKER_GATEWAY_IP,
                marks=pytest.mark.use_containerized,
            ),
        ],
        ids=["desktop_local_mtls", "desktop_remote_mtls", "dockercompose_mtls"],
        indirect=True,
    )
    @pytest.mark.parametrize("enable_insecure_product", [True], indirect=True)
    def test_mtls_fallsback_to_insecure_when_missing_grpc_certificates(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        product_host: str,
        get_hps_job_ids: GetHpsJobIdsType,
        get_hps_job_output: Callable[[str], list[str]],
    ):
        """When using HPS as instance management system, secure gRPC channels between GLOW and the product can be
        established for any OS and binding host."""
        product_host = product_host or "localhost"
        job_name = "custom-grpc-product-secure-mtls-1-GLOW-Instance"
        old_job_ids = get_hps_job_ids(job_name, "all", [])

        step = function_project.project.steps.custom_grpc_shared_instance_step
        step.initialize_custom_grpc_product_secure_mtls_instance().wait()
        step.shutdown_custom_grpc_product_secure_mtls_instance()

        job_ids = get_hps_job_ids(job_name, "all", old_job_ids)
        assert len(job_ids) == 1
        job_output = "\n".join(get_hps_job_output(job_ids[0]))

        # THEN: In every scenario, assert log lines from product server, GLOW healthcheck and product client
        secure_flags = "--transport-mode=insecure"
        assert (
            f"No grpc certificates found for {'localhost' if product_host == 'localhost' else 'remote'},"
            + f" falling back to secure_flags='{secure_flags}'"
        ) in job_output
        assert session_glow.text_in_output(
            [
                f"Health check: creating insecure grpc channel with uri={product_host}:",
                "and localhost as default authority",
            ],
        )
        assert session_glow.text_in_output("Connecting to MockProduct using: insecure")


@pytest.mark.parametrize(
    "custom_product",
    ["custom_grpc_product_secure", "custom_grpc_product_secure_2", "custom_grpc_product_secure_mtls"],
)
@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host"),
    [
        ("Desktop", None, None),  # product_binding_host defaults to localhost in secure products
        ("Desktop", None, "0.0.0.0"),
        pytest.param("DockerCompose", "host.docker.internal", "0.0.0.0", marks=pytest.mark.use_containerized),
    ],
    ids=["desktop_wnua_or_insecure", "desktop_insecure", "dockercompose_insecure"],
    indirect=True,
)
def test_grpc_product_with_secure_channel_pim(
    function_project: ProjectFixture[EndToEndSolution],
    session_glow: GlowBaseProcess[EndToEndSolution],
    product_host: str | None,
    product_binding_host: str | None,
    session_pim: PimProcess,
    custom_product: str,
):
    """When using PIM Light Server as instance management system, secure gRPC channels between GLOW and the product are
    only supported for Windows and localhost bindings."""
    product_host = product_host or "127.0.0.1"
    binding_host = product_binding_host or "localhost"
    step = function_project.project.steps.custom_grpc_shared_instance_step
    getattr(step, f"initialize_{custom_product}_instance")().wait()
    getattr(step, f"shutdown_{custom_product}_instance")()

    # THEN: In every scenario, assert log lines from product server, GLOW healthcheck and product client
    if platform.system() == "Windows" and binding_host in LOCALHOST_HOSTS:
        expected_args = (
            "--host,localhost,--version,1,--transport-mode=WNUA"
            if custom_product == "custom_grpc_product_secure"
            else "--version,1,-transport,wnua"
        )
        assert session_pim.find_msg_in_output(expected_args)
    else:
        expected_args = (
            f"--host,{binding_host},--version,1,--transport-mode=insecure"
            if custom_product == "custom_grpc_product_secure"
            else "--version,1,-transport,insecure"
        )
        assert session_pim.find_msg_in_output(expected_args)
    # Healtcheck and Client logs are insecure in all scenarios for now, because there is no reliable way to know
    # whether the product was launched with WNUA or not.
    assert session_glow.text_in_output(
        [
            f"Health check: creating insecure grpc channel with uri={product_host}:",
        ],
    )
    assert session_glow.text_in_output("Connecting to MockProduct using: insecure")
