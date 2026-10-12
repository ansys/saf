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
from tests.mocks.solution_without_metadata_json.solution_with_method_assets_without_metadata_json import (
    SolutionAssetsWithoutMetadata,
)

pytestmark = pytest.mark.parametrize("solution_type", [SolutionAssetsWithoutMetadata], indirect=True)


def test_always_decrypted_asset(function_project: ProjectFixture[SolutionAssetsWithoutMetadata]):
    function_project.project.steps.step_with_assets.retrieve_always_decrypted_assets()
    assert function_project.project.steps.step_with_assets.content_of_asset == "always decrypted"


def test_decrypted_for_debug_asset(function_project: ProjectFixture[SolutionAssetsWithoutMetadata]):
    function_project.project.steps.step_with_assets.retrieve_decrypted_for_debug_assets()
    assert function_project.project.steps.step_with_assets.content_of_asset == "decrypted for debug from beginning"


def test_asset_dir(function_project: ProjectFixture[SolutionAssetsWithoutMetadata]):
    function_project.project.steps.step_with_assets.retrieve_asset_dir()
    content = function_project.project.steps.step_with_assets.content_of_asset
    assert content.rstrip() == "decrypted"
