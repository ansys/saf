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
import pytest

from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestAssetFiles:
    @pytest.mark.parametrize(
        ("method_name", "expected_file_content"),
        [
            ("read_asset_file", "AssetFile1"),
            ("read_asset_file_with_special_chars", "ä, ö, ü, ß, â, ê, î, ô, û"),
        ],
        ids=[
            "1-asset",
            "special-chars",
        ],
    )
    def test_asset_file_content(
        self,
        method_name: str,
        expected_file_content: str,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that unencrypted asset files can be read from transaction methods.
        """
        step = function_project.project.steps.transaction_verification_step
        getattr(step, method_name)()
        assert step.text_content == expected_file_content
