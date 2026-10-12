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

from ansys.saf.glow.client import Client, InternalSolutionException
from ansys.saf.testing.solution.end_to_end import EnvVarDebug, GlowBaseProcess
from tests.mocks.solutions.set_env_vars import AStep, SetEnvVarsSolution


@pytest.fixture
def glow_with_debug(
    tmp_path: Path,
    run_glow: Callable[[type[SetEnvVarsSolution], Path], GlowBaseProcess[SetEnvVarsSolution]],
    tmp_solutions_dir: dict[type[SetEnvVarsSolution], Path],
    get_glow_client: Callable[[GlowBaseProcess[SetEnvVarsSolution]], Client[SetEnvVarsSolution]],
) -> AStep:
    glow_proc = run_glow(SetEnvVarsSolution, tmp_solutions_dir[SetEnvVarsSolution], cwd=tmp_path)  # type: ignore
    glow_proc.change_configuration(EnvVarDebug)  # type: ignore
    glow_client = get_glow_client(glow_proc)  # type: ignore
    project = glow_client.create_project("test project")
    step = project.steps.a_step
    return step


def assert_hps_system_unconfigured(step: AStep):
    expected_error_msg = (
        "No HPS system is configured. Set the environment variable GLOW_HPS_PORT and optionally GLOW_HPS_HOST, "
        "or pass the hps_server_url argument when starting the job."
    )
    with pytest.raises(InternalSolutionException, match=expected_error_msg):
        step.check_hps_system()


def assert_hps_system_configured(step: AStep):
    # Transaction fails  because we didn't launch HPS. But we can see that the it creates the Client and tries to
    # communicate with it as expected.
    expected_error_msgs = [
        "HTTPSConnectionPool(host='localhost', port=8443): Max retries exceeded with url",
        "Client(url=hps_server_url, username=self._hps_user, password=self._hps_pwd)",
    ]
    with pytest.raises(InternalSolutionException) as e:
        step.check_hps_system()
    for msg in expected_error_msgs:
        assert msg in str(e.value)


def test_configuring_env_vars_in_sync_transaction(glow_with_debug: AStep):
    """Test that a sync transaction can set env vars in the Method Runner environment and future requests to the API
    server are reactive to it, since sync transactions are executed in the same process as the API server."""

    # GIVEN: Transaction that uses HPS and fails to do so because env vars are not configured.
    assert_hps_system_unconfigured(glow_with_debug)

    # WHEN: Configuring those env vars using another transaction and USER and PASSWORD for auth
    glow_with_debug.set_env_vars()

    # THEN: Transaction correctly tries to communicate HPS
    assert_hps_system_configured(glow_with_debug)


def test_configuring_env_vars_in_longrunning_transaction_does_not_work(glow_with_debug: AStep):
    """Test that a long running transaction can set env vars in the Method Runner environment and future requests
    to the API server ignore it, since long running transactions are executed in a different process than the API
    server."""
    # GIVEN: Transaction that uses HPS and fails to do so because env vars are not configured.
    assert_hps_system_unconfigured(glow_with_debug)

    # WHEN: Configuring those env vars using another long running transaction and USER and PASSWORD for auth
    glow_with_debug.set_env_vars_lr().wait()

    # THEN: Transaction that uses HPS and fails to do so because env vars are not configured.
    assert_hps_system_unconfigured(glow_with_debug)
