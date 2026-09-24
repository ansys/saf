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

import os
from pathlib import Path


def write_github_output(name: str, value: str) -> None:
    """Append a named output value to the GitHub Actions output file.

    Parameters
    ----------
    name : str
        Name of the output variable.
    value : str
        Value assigned to the output variable.

    Notes
    -----
    If ``GITHUB_OUTPUT`` is not set, no output is written. This allows the
    utility to run unchanged outside GitHub Actions.
    """
    github_output_path = os.environ.get("GITHUB_OUTPUT")
    if github_output_path:
        with Path(github_output_path).open("a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
