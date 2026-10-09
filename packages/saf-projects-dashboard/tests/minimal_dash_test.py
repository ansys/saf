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

"""Minimal test of ProjectsDashboard in a Dash app."""

from dash import Dash, html

import ansys_saf_projects_dashboard

app = Dash(__name__)

app.layout = html.Div(
    [
        html.H1("ProjectsDashboard Test"),
        ansys_saf_projects_dashboard.ProjectsDashboard(id="test-dashboard"),
    ],
)

if __name__ == "__main__":
    print("Starting minimal Dash app with ProjectsDashboard...")
    print("Open http://127.0.0.1:8050 in your browser")
    app.run(debug=True, port=8050)
