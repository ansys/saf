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

import tomlkit

from tests.e2e.conftest import GetSAFVersion


def test_saf_version(get_saf_version: GetSAFVersion):
    """
    Test ``saf version`` returns the version of the installed SAF CLI, that matches the one in the pyproject.toml file.
    """
    pyproject_data = tomlkit.loads((Path(__file__).parent.parent.parent / "pyproject.toml").read_bytes()).unwrap()
    expected_version = pyproject_data["project"]["version"]
    assert get_saf_version().find_msg_in_output(expected_version)
