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

from pathlib import Path
import shutil

import pytest

from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.usefixtures("configure_aedt_installation_dir"),
]

AEDT_FILE_WITH_ANALYSIS_READY = Path(
    "./tests/mocks/solution_end_to_end/method_assets/Transformer_leakage_inductance.aedt",
)


@pytest.mark.use_aedt
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
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.xfail(reason="pyaedt rpyc not working with docker"))],
    indirect=True,
)
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True)
def test_minimal_aedt_bdm(function_project: ProjectFixture[EndToEndSolution], ansys_release: str):
    """
    Test that a Maxwell2D product can be initialized using a cached project file and perform several instance
    operations that create result files.
    """
    step = function_project.project.steps.maxwell_2d_verification_step
    project_file = function_project.project.storage_scope.get_storage_root() / "my_input_aedt_project.aedt"
    shutil.copy(AEDT_FILE_WITH_ANALYSIS_READY, project_file)
    step.aedt_project_file_input = function_project.project.storage_scope.store(project_file)

    step.aedt_version = ansys_release
    step.initialize_maxwell_2d_instance_with_project().wait()

    # We verify the version of AEDT is correct.
    step.upload_aedt_version_from_aedt().wait()
    assert step.aedt_version == f"ANSYSEM_ROOT{ansys_release}"

    assert step.health_check()
    assert step.run_analysis()

    step.exit_aedt()
