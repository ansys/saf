# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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

from enum import Enum
import platform

import pytest

from ansys.saf.testing._solution.const import TestProductInstanceSystemType


@pytest.fixture(scope="session")
def deployment_type(
    is_docker_requested: bool,
    is_docker_installed: bool,
    request: pytest.FixtureRequest,
) -> Enum:
    from ansys.saf.glow.client import Deployment  # pyright: ignore[reportMissingImports]

    deployment = request.param if hasattr(request, "param") else "Desktop"
    if deployment != "Desktop":
        if not is_docker_requested:
            pytest.skip(f"Use --docker to enable {deployment} test.")
        if not is_docker_installed:
            pytest.fail(f"Install docker to enable {deployment} test.")
    return Deployment[deployment]


@pytest.fixture(scope="session")
def instance_system_type(
    request: pytest.FixtureRequest,
    is_docker_requested: bool,
    is_docker_installed: bool,
    is_hps_requested: bool,
    is_hps_enabled: bool,
    is_pim_enabled: bool,
    num_pytest_workers: int,
) -> TestProductInstanceSystemType | None:
    # a single place to parametrize the type of instance system and skip if not available.
    if not hasattr(request, "param") or not request.param:
        return None
    if request.param == "PIM" and not is_pim_enabled:
        pytest.skip("PIM tests disabled. Either add the 'use_pim' marker or remove 'not use_pim'.")
    if request.param == "HPS" and not is_hps_enabled:
        if not is_docker_requested and platform.system() == "Linux":
            # We don't care about this on Windows
            pytest.skip("Use --docker to enable HPS test.")
        if not is_hps_requested:
            pytest.skip("HPS tests disabled. Either add the 'use_hps' marker or remove 'not use_hps'.")
        if num_pytest_workers > 1:
            pytest.skip("Limit pytest to 1 worker (-n [0-1]) to run HPS test.")
        if not is_docker_installed:
            pytest.fail("Install docker to enable HPS test.")
    return TestProductInstanceSystemType[request.param]
