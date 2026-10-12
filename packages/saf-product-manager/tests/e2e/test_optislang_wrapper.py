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
from typing import Literal

import pytest

from ansys.saf.product_manager._utilities.const import LOCALHOSTS
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.hps import GetHpsJobIdsType
from ansys.saf.testing.network import get_local_ip
from ansys.saf.testing.pim.process import PimProcess
from ansys.saf.testing.solution.end_to_end import (
    GlowBaseProcess,
    ProjectFixture,
)
from tests.e2e.conftest import (
    DOCKER_GATEWAY_IP,
)
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

OPTISLANG_WRAPPER_NO_SECURE_FLAGS_WARNING = "No secure flags found for optiSLang wrapper. Falling back to insecure TCP."
OPTISLANG_WRAPPER_MTLS_WARNING = (
    "MTLS secure flag found for optiSLang wrapper but MTLS is not supported yet. Falling back to insecure TCP."
)
OPTISLANG_WRAPPER_INSECURE_WARNING = "Insecure flag found for optiSLang wrapper. Using TCP connection mode."
OPTISLANG_UNKNOWN_SECURE_FLAGS_WARNING = "Unknown secure flags"
OPTISLANG_WRAPPER_WARNING_MSGS = [
    OPTISLANG_WRAPPER_NO_SECURE_FLAGS_WARNING,
    OPTISLANG_WRAPPER_MTLS_WARNING,
    OPTISLANG_WRAPPER_INSECURE_WARNING,
    OPTISLANG_UNKNOWN_SECURE_FLAGS_WARNING,
]


def _assert_optislang_wrapper_warning(
    session_glow: GlowBaseProcess[EndToEndSolution],
    expected_warning: str | None,
) -> None:
    if expected_warning is None:
        assert not any(session_glow.text_in_output(msg, "api", timeout=0) for msg in OPTISLANG_WRAPPER_WARNING_MSGS)
        return

    assert session_glow.text_in_output(expected_warning, "api")
    assert not any(
        session_glow.text_in_output(msg, "api", timeout=0)
        for msg in OPTISLANG_WRAPPER_WARNING_MSGS
        if msg != expected_warning
    )


pytestmark = [pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)]


@pytest.fixture
def project_with_osl_inputs(
    function_project: ProjectFixture[EndToEndSolution],
    op_mode: Literal["temp_files", "stream_bytes"],
    ansys_release: str,
) -> YieldFixture[ProjectFixture[EndToEndSolution]]:
    step = function_project.project.steps.optislang_wrapper_step

    step.version = ansys_release
    step.op_mode = op_mode
    step.download_example_file()
    step.write_properties_file()
    step.write_input_files()

    yield function_project

    if step.instance_running:
        step.shutdown_optislang().wait()


@pytest.mark.use_optislang
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
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True)
class TestOptislang:
    @pytest.mark.parametrize("op_mode", ["temp_files", "stream_bytes"])
    def test_design_evaluation(self, project_with_osl_inputs: ProjectFixture[EndToEndSolution]):
        """Test that the new optislang manager can start an optislang project and evaluate a design."""
        step = project_with_osl_inputs.project.steps.optislang_wrapper_step

        step.start_osl_project().wait()
        step.evaluate_design()

        assert step.objective == "4196.46753"


@pytest.mark.use_optislang
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True)
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize(
    ("deployment_type", "product_host", "product_binding_host", "enable_insecure_product"),
    [
        ("Desktop", None, None, False),  # product_binding_host defaults to localhost in secure products
        ("Desktop", get_local_ip(), get_local_ip(), False),
        ("DockerCompose", "host.docker.internal", DOCKER_GATEWAY_IP, False),
        ("DockerCompose", "host.docker.internal", "0.0.0.0", True),
    ],
    ids=[
        "desktop_local_secure_mode",
        "desktop_remote",
        "dockercompose_remote",
        "dockercompose_remote_with_insecure_enabled",
    ],
    indirect=True,
)
@pytest.mark.parametrize("op_mode", ["stream_bytes"])
def test_optislang_wrapper_on_hps(
    session_glow: GlowBaseProcess[EndToEndSolution],
    project_with_osl_inputs: ProjectFixture[EndToEndSolution],
    ansys_release: str,
    product_host: str | None,
    product_binding_host: str | None,
    get_hps_job_ids: GetHpsJobIdsType,
    get_hps_job_output: Callable[[str], list[str]],
):
    """Test secure optiSLang wrapper connection on HPS."""
    job_name = f"optislang-wrapper-secure-{ansys_release}-GLOW-Instance"
    old_job_ids = get_hps_job_ids(job_name, "all", [])

    step = project_with_osl_inputs.project.steps.optislang_wrapper_step

    step.start_osl_project().wait()
    step.evaluate_design()
    assert step.objective == "4196.46753"
    step.shutdown_optislang().wait()

    job_ids = get_hps_job_ids(job_name, "all", old_job_ids)
    assert len(job_ids) == 1
    job_output = "\n".join(get_hps_job_output(job_ids[0]))

    bind_host = product_binding_host or "localhost"
    if bind_host in LOCALHOSTS:
        _assert_optislang_wrapper_warning(session_glow, expected_warning=None)
    elif "--transport-mode=MTLS" in job_output:
        _assert_optislang_wrapper_warning(session_glow, expected_warning=OPTISLANG_WRAPPER_MTLS_WARNING)
    elif "--transport-mode=insecure" in job_output:
        _assert_optislang_wrapper_warning(session_glow, expected_warning=OPTISLANG_WRAPPER_INSECURE_WARNING)
    elif "No grpc certificates found for remote" in job_output:
        _assert_optislang_wrapper_warning(session_glow, expected_warning=OPTISLANG_WRAPPER_NO_SECURE_FLAGS_WARNING)
    else:
        raise AssertionError("Could not infer secure flags from HPS job output for optiSLang wrapper.")


@pytest.mark.usefixtures("configure_product_host")
@pytest.mark.use_optislang
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True)
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
@pytest.mark.parametrize("op_mode", ["stream_bytes"])
def test_optislang_wrapper_on_pim(
    session_glow: GlowBaseProcess[EndToEndSolution],
    project_with_osl_inputs: ProjectFixture[EndToEndSolution],
    product_host: str | None,
    product_binding_host: str | None,
    session_pim: PimProcess,
):
    """Test secure optiSLang wrapper connection on PIM."""
    step = project_with_osl_inputs.project.steps.optislang_wrapper_step

    step.start_osl_project().wait()
    step.evaluate_design()
    assert step.objective == "4196.46753"
    step.shutdown_optislang().wait()

    # PIM currently reports "insecure" for secure products in service metadata.
    # The manager decides LOCAL_DOMAIN vs TCP based on resolved service host.
    # If product_host is None, GLOW defaults to localhost for Desktop PIM tests.
    effective_product_host = product_host or "localhost"
    if effective_product_host in LOCALHOSTS:
        assert not session_glow.text_in_output(
            OPTISLANG_WRAPPER_INSECURE_WARNING,
            "api",
            timeout=0,
        )
    else:
        assert session_glow.text_in_output(
            OPTISLANG_WRAPPER_INSECURE_WARNING,
            "api",
        )
