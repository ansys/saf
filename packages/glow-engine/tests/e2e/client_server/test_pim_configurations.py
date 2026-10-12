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

import pytest

from ansys.saf.glow.client import Client
from ansys.saf.testing.network import get_local_ip
from ansys.saf.testing.platform_specific import linux_only
from ansys.saf.testing.solution.end_to_end import (
    GlowDesktopProcess,
    HostStringSystemEnvVarConfig,
    InsecurePIMEnvVarConfig,
    NoGrpcCertificates,
    SocketPlusPortsPIMEnvVarConfig,
    WithCertificatesPIMEnvVarConfig,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution


@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
def test_glow_product_instance_system_host_str(
    run_glow: Callable[..., GlowDesktopProcess[EndToEndSolution]],
    get_glow_client: Callable[[GlowDesktopProcess[EndToEndSolution]], Client[EndToEndSolution]],
    random_project_name: Callable[[], str],
    pim_port: int | None,
    pim_socket_path: Path | None,
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
):
    """
    Test that the variable GLOW_PRODUCT_INSTANCE_SYSTEM_HOST accepts the string localhost as a valid address.
    """
    glow_proc = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], prevent_start=True)
    glow_proc.change_configuration(HostStringSystemEnvVarConfig, pim_port=pim_port, pim_socket_path=pim_socket_path)
    glow_process_client = get_glow_client(glow_proc)
    project = glow_process_client.create_project(random_project_name())
    step = project.steps.custom_grpc_shared_instance_step
    step.initialize_custom_grpc_product_instance().wait()
    step.shutdown_custom_grpc_product_instance()


@linux_only()
def test_local_pim_linux_without_socket_raises_error(
    run_glow: Callable[..., GlowDesktopProcess[EndToEndSolution]],
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
):
    """
    Test that configuring GLOW to connect to a local PIM Light Server without socket raises an
    error in Linux.
    """
    glow_proc = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], prevent_start=True)
    glow_proc.change_configuration(InsecurePIMEnvVarConfig, pim_port=48572, pim_host="127.0.0.1")
    assert not glow_proc.healthy
    expected_error_msg = "Value error, Missing socket path (GLOW_PIM_SOCKET_PATH) for localhost connections on Linux."
    assert glow_proc.text_in_output(expected_error_msg, "api")


@linux_only()
def test_local_pim_linux_with_socket_and_host_port_raises_error(
    run_glow: Callable[..., GlowDesktopProcess[EndToEndSolution]],
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
):
    """
    Test that configuring GLOW to connect to a local PIM Light Server with both socket and host/port raises an
    error in Linux.
    """
    glow_proc = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], prevent_start=True)
    glow_proc.change_configuration(
        SocketPlusPortsPIMEnvVarConfig,
        pim_port=48572,
        pim_socket_path=Path("/tmp/fake.sock"),
    )
    assert not glow_proc.healthy
    expected_error_msg = (
        "Value error, Conflicting PIM configuration detected: both socket path (GLOW_PIM_SOCKET_PATH) and host/port "
        "(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST/GLOW_PRODUCT_INSTANCE_SYSTEM_PORT) are provided. For localhost connections "
        "on Linux, please use only GLOW_PIM_SOCKET_PATH."
    )
    assert glow_proc.text_in_output(expected_error_msg, "api")


def test_external_pim_with_no_certs_raises_error(
    run_glow: Callable[..., GlowDesktopProcess[EndToEndSolution]],
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
):
    """
    Test that configuring GLOW to connect to an external PIM Light Server with mutual TLS but without configuring
    certificate files raises an error.
    """
    glow_proc = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], prevent_start=True)
    glow_proc.change_configuration(NoGrpcCertificates, restart=False)
    glow_proc.change_configuration(
        InsecurePIMEnvVarConfig,
        pim_port=48572,
        pim_host=get_local_ip(),
    )
    assert not glow_proc.healthy
    expected_error_msg = (
        "Value error, Missing Ansys gRPC certificates directory (ANSYS_GRPC_CERTIFICATES) for "
        "non-localhost connections to PIM Light Server."
    )
    assert glow_proc.text_in_output(expected_error_msg, "api")


def test_external_pim_with_partial_certs_raises_error(
    tmp_path: Path,
    run_glow: Callable[..., GlowDesktopProcess[EndToEndSolution]],
    tmp_solutions_dir: dict[type[EndToEndSolution], Path],
):
    """
    Test that configuring GLOW to connect to an external PIM Light Server with mutual TLS but with missing
    certificate files raises an error.
    """
    glow_proc = run_glow(EndToEndSolution, tmp_solutions_dir[EndToEndSolution], prevent_start=True)
    glow_proc.change_configuration(
        WithCertificatesPIMEnvVarConfig,
        pim_port=48572,
        pim_host=get_local_ip(),
        certs_dir=tmp_path,
    )
    assert not glow_proc.healthy
    expected_error_msg = (
        f"Value error, Missing required TLS file(s) for mutual TLS: {(tmp_path / 'client.crt').as_posix()}, "
        f"{(tmp_path / 'client.key').as_posix()}, {(tmp_path / 'ca.crt').as_posix()}"
    )
    assert glow_proc.text_in_output(expected_error_msg, "api")
