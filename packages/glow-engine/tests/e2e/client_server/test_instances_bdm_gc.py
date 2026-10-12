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

from collections.abc import Generator

import pytest

from ansys.saf.testing.solution.end_to_end import EnvVarDebugLogLevel, GlowBaseProcess, ProjectFixture
from tests.e2e.client_server.test_bdm_gc import assert_bdm_locks_count
from tests.mocks.solutions.bdm_solution import BdmSolution

pytestmark = pytest.mark.parametrize("solution_type", [BdmSolution], indirect=True)


@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
class TestInstanceBdmLocks:
    @pytest.fixture(scope="class", autouse=True)
    def set_logging_level_to_debug(self, session_glow: GlowBaseProcess[BdmSolution]) -> Generator[None, None, None]:
        session_glow.change_configuration(EnvVarDebugLogLevel)
        yield
        session_glow.configure_default_execution()

    def test_launching_and_using_bdm_shared_product_instance(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        """Test that launching and using a BDM shared product instance creates and removes BDM locks as expected. Even
        if the transaction doesn't define entity handles in its step spec or params, instance managers typically use
        BDM internally for storing the product state.
        """
        session_glow.clear_output()
        function_project.project.steps.bdm_step.launch_product()
        assert_bdm_locks_count(session_glow, 1)

        session_glow.clear_output()
        function_project.project.steps.bdm_step.close_product()
        assert_bdm_locks_count(session_glow, 1)
