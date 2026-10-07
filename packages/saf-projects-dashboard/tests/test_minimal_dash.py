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

"""Minimal test to verify ansys_saf_projects_dashboard works in a simple Dash app."""

from dash import Dash, html

import ansys_saf_projects_dashboard

app = Dash(__name__)

app.layout = html.Div(
    [
        html.H1("Test ProjectsDashboard"),
        ansys_saf_projects_dashboard.ProjectsDashboard(id="test-dashboard"),
    ],
)

if __name__ == "__main__":
    print("Starting minimal Dash app on http://127.0.0.1:8050")
    print("Check the browser console for errors")
    app.run(debug=True, port=8050)
