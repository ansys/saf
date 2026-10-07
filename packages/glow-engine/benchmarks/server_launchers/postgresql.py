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

import os
from pathlib import Path
import sys
import tempfile

from benchmarks.server_launchers.postgresql_container import PostgresContainer
from benchmarks.server_launchers.run_and_capture_output import run_and_capture_output

from ansys.saf.glow._config.const import GLOW_DATABASE_LOCATION, GLOW_DATABASE_TYPE, GLOW_LOG_CONFIG

with tempfile.TemporaryDirectory() as tmp_dir, PostgresContainer(Path(tmp_dir)) as location:
    env = os.environ.copy()
    env[GLOW_DATABASE_TYPE] = "postgresql"
    env[GLOW_DATABASE_LOCATION] = location
    env[GLOW_LOG_CONFIG] = str(Path(__file__).parent / "logging_config.yaml")
    args = [
        sys.executable,
        "-m",
        "ansys.saf.glow.cli",
        "api",
        "--port",
        "56565",
        "--definition",
        "benchmarks.solutions.simple_solution",
    ]
    run_and_capture_output(args, env=env)
