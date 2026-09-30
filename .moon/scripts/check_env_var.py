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
import sys

if len(sys.argv) < 2:
    print("Error: No environment variable name provided to check.")
    sys.exit(1)

var_name = sys.argv[1]

if var_name not in os.environ or not os.environ[var_name].strip():
    print(f"Error: Environment variable '{var_name}' is not defined or is empty!")
    sys.exit(1)

print(f"Success: '{var_name}' is defined.")
sys.exit(0)
