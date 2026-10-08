# Copyright (C) 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
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

"""Minimal test to verify ansys_saf_projects_dashboard component works with Dash."""

import ansys_saf_projects_dashboard

# Print component info
print(f"Package name: {ansys_saf_projects_dashboard.package_name}")
print(f"Version: {ansys_saf_projects_dashboard.__version__}")

# Check the component class
comp = ansys_saf_projects_dashboard.ProjectsDashboard
print(f"\nComponent: {comp}")
print(f"Component _type: {getattr(comp, '_type', 'N/A')}")
print(f"Component _namespace: {getattr(comp, '_namespace', 'N/A')}")

# Check _js_dist
js_dist = getattr(comp, "_js_dist", [])
print(f"\n_js_dist entries: {len(js_dist)}")
for entry in js_dist:
    print(f"  - {entry}")

# Try creating an instance
instance = ansys_saf_projects_dashboard.ProjectsDashboard(id="test-dashboard")
print(f"\nCreated instance: {instance}")
print(f"Instance type: {instance.type if hasattr(instance, 'type') else 'N/A'}")
print(f"Instance to_plotly_json: {instance.to_plotly_json()}")
