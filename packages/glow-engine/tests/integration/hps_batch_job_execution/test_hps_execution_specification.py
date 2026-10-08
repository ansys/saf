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

import sys
import time

import pytest

from ansys.saf.glow._hps_parametric_studies.base import HpsOutputDirectorySpecification, HpsOutputFileSpecification
from ansys.saf.glow.solution.hps import HpsExecutionSpecification, HpsJobEvaluationStatus
from ansys.saf.product_configuration.interfaces import Software as GlowSoftware
from tests.mocks.hps_scripts import echo_context as echo_context_module
from tests.mocks.hps_scripts.echo_context import echo_context
import tests.mocks.hps_scripts.module_with_init as module_with_init
from tests.mocks.hps_scripts.module_with_init import subtract as subtract_via_init
import tests.mocks.hps_scripts.multiple_submodules as modules
from tests.mocks.hps_scripts.multiple_submodules import outer as outer_module
import tests.mocks.hps_scripts.simple_subtract as simple_subtract

pytestmark = [pytest.mark.use_batch_job]


specifications = [
    HpsExecutionSpecification(
        function=simple_subtract.subtract,
        module=simple_subtract,
        output_parameters={"r": int},
    ),
    HpsExecutionSpecification(
        function=outer_module.subtract,
        module=modules,
        output_parameters={"r": int},
    ),
    HpsExecutionSpecification(
        function=subtract_via_init,
        module=module_with_init,
        output_parameters={"r": int},
    ),
]


@pytest.mark.parametrize(
    "execution_spec",
    specifications,
    ids=["simple module", "multiple submodules", "module with __init__"],
)
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.usefixtures("hps_authentication")
class TestHpsExecutionSpecification:
    def test_job_execution_via_execution_specification(self, execution_spec: HpsExecutionSpecification):
        hps_project = execution_spec.execute(a=4, b=6)

        while not hps_project.finished:
            time.sleep(5)

        assert hps_project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
        assert hps_project.r == -2  # type: ignore

    def test_parametric_study_execution_via_execution_specification(self, execution_spec: HpsExecutionSpecification):
        hps_project = execution_spec.execute_parametric_study(a=[4, 7], b=[9, 5])

        while not hps_project.finished:
            time.sleep(5)

        assert all(
            status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
            for status in hps_project.get_status_of_design_points()
        )
        assert hps_project.r == [-5, 2]  # type: ignore


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.usefixtures("hps_authentication")
def test_execution_context():
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    spec = HpsExecutionSpecification(
        function=echo_context,
        module=echo_context_module,
        output_parameters={
            "required_output_parameters": str,
            "required_output_files": str,
            "required_output_directories": str,
            "products": str,
            "myfile": HpsOutputFileSpecification("x.txt"),
            "my_output_dir": HpsOutputDirectorySpecification("expected_dir"),
        },
        python_version=python_version,
        products=[GlowSoftware("Ansys SAF Product Environment", "0.0")],
    )

    project = spec.execute()

    while not project.finished:
        time.sleep(2.5)

    assert project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED
    assert project.required_output_parameters == (  # type: ignore
        "products required_output_directories required_output_files required_output_parameters"
    )
    assert project.products == f"Python {python_version}  Ansys SAF Product Environment 0.0"  # type: ignore
    assert project.required_output_files == "myfile x.txt"  # type: ignore
    assert project.required_output_directories == "my_output_dir"  # type: ignore
