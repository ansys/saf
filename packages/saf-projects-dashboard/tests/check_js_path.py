# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.

# SPDX-License-Identifier: Apache-2.0
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

"""Check where Dash looks for JS files."""

import os

import ansys_saf_projects_dashboard

# Check where Dash would look for JS files
print("ansys_saf_projects_dashboard.__file__:", ansys_saf_projects_dashboard.__file__)
print()

# The _js_dist path is relative to the module that defines _js_dist
# Since we import from .ansys_saf_projects_dashboard, let's check where that is
import ansys_saf_projects_dashboard.ansys_saf_projects_dashboard as inner  # noqa: E402

print("inner.__file__:", inner.__file__)
print()

# Check if JS exists relative to inner module
inner_dir = os.path.dirname(inner.__file__)  # noqa: PTH120
js_path = os.path.join(inner_dir, "ansys_saf_projects_dashboard.js")  # noqa: PTH118
print("JS expected at:", js_path)
print("JS exists:", os.path.exists(js_path))  # noqa: PTH110
