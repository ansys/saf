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

"""Check how Dash and DashProxy register component resources."""

from dash import Dash, html
from dash_extensions.enrich import DashProxy, MultiplexerTransform, NoOutputTransform, TriggerTransform

import ansys_saf_projects_dashboard

# Test 1: Standard Dash
print("=== Standard Dash ===")
app1 = Dash(__name__)
app1.layout = html.Div([ansys_saf_projects_dashboard.ProjectsDashboard(id="test")])

with app1.server.test_request_context():
    html_content = app1.index()
    if "ansys_saf_projects_dashboard" in html_content:
        print("  FOUND ansys_saf_projects_dashboard in HTML")
    else:
        print("  NOT FOUND in HTML")

# Test 2: DashProxy
print("\n=== DashProxy ===")
app2 = DashProxy(
    __name__,
    serve_locally=True,
    suppress_callback_exceptions=True,
    transforms=[NoOutputTransform(), TriggerTransform(), MultiplexerTransform()],
)
app2.layout = html.Div([ansys_saf_projects_dashboard.ProjectsDashboard(id="test")])

with app2.server.test_request_context():
    html_content = app2.index()
    if "ansys_saf_projects_dashboard" in html_content:
        print("  FOUND ansys_saf_projects_dashboard in HTML")
        import re

        scripts = re.findall(r'<script[^>]*src="[^"]*ansys_saf_projects_dashboard[^"]*"[^>]*>', html_content)
        for s in scripts:
            print(f"  {s}")
    else:
        print("  NOT FOUND in HTML")

# Check get_dist for DashProxy
print("\nget_dist for DashProxy:")
try:
    dist = app2.get_dist("ansys_saf_projects_dashboard")
    print(f"  {dist}")
except Exception as e:
    print(f"  Error: {e}")
