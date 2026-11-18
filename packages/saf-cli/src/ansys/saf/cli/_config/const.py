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

# Env vars from other SAF components used to configure them through the CLI options
from pathlib import Path

GLOW_DEBUG = "GLOW_DEBUG"
GLOW_LOGGING_LEVEL = "GLOW_LOGGING_LEVEL"
PORTAL_UI_PORT = "PORTAL_UI_PORT"
GLOW_API_PORT = "GLOW_API_PORT"
GLOW_UI_PORT = "GLOW_UI_PORT"
GLOW_UI_DEBUG = "GLOW_UI_PYTHON_DEBUGGING"
GLOW_SOLUTION_DEFINITION = "GLOW_SOLUTION_DEFINITION"
GLOW_UI_MODULE = "GLOW_UI_MODULE"

# Env vars for solution scaffolding
_root_path = Path(__file__).resolve().parent.parent
SOLUTION_TEMPLATE_PATH = _root_path / "_solutions" / "templates" / "solution"
DEFAULT_SOLUTION_NAME = "my_solution"
DEFAULT_SOLUTION_DISPLAY_NAME = "My Solution"
DEFAULT_UI_FRAMEWORK = "dash"
UI_FRAMEWORKS = ["dash", "none"]
DEFAULT_STEP_NAME = "my_new_step"
DEFAULT_TEMPLATE_NAME = "calculator-step"
DEFAULT_SOLUTION_NAMESPACE = "saf.solutions"

# Env vars for solution installation
WORKSPACE_CLEAR_OPTIONS = ["hard", "soft"]

# Others
SAF_CLI_EXTERNAL_URL = "https://ansys.github.io/saf-cli-documentation"
SAF_DESKTOP_LOG_TO_FILES = "SAF_DESKTOP_LOG_TO_FILES"
