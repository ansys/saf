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

# /// script
# dependencies = [
#   "tomlkit==0.15.1",
#   "requests==2.32.2",
#   "packaging==26.3",
#   "pydantic==2.12.5",
#   "pytest>=8",
# ]
# ///

"""Executable test runner for the SDK meta-package action."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).parent), *sys.argv[1:]]))
