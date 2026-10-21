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

from ansys.saf.glow._config.settings import Settings
from tests.mocks.solutions import minimal_solution
from tests.unit.conftest import build_mock_app

solution = minimal_solution


def test_access_control_requires_auth(settings: Settings):
    settings.glow_project_access_control_enabled = True
    settings.glow_auth_disabled = True
    with pytest.raises(RuntimeError, match="GLOW_PROJECT_ACCESS_CONTROL_ENABLED requires authentication"):
        build_mock_app(settings)


def test_access_control_defaults(settings: Settings):
    assert settings.glow_project_access_control_enabled is False
    assert settings.glow_project_lock_idle_timeout == 28800
    assert settings.glow_project_stuck_method_timeout == 86400
    assert settings.glow_auth_roles_claim == "resource_access.{client_id}.roles"
    assert settings.glow_ui_user_directory == "none"
    assert settings.computed_super_admin_roles == frozenset()


def test_computed_super_admin_roles(settings: Settings):
    settings.glow_auth_super_admin_roles = " admin , root,"
    assert settings.computed_super_admin_roles == frozenset({"admin", "root"})
