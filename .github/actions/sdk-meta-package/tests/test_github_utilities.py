# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import github_utilities


def test_write_github_output() -> None:
    with tempfile.TemporaryDirectory() as directory:
        output_path = Path(directory) / "github-output"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
            github_utilities.write_github_output("update-type", "minor")
        assert output_path.read_text(encoding="utf-8") == "update-type=minor\n"
