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

"""
Projects Dashboard - Usage Example

This example demonstrates how to integrate the ProjectsDashboard
Dash component into a Dash application with dcc.Upload for file import.

Run with: python usage.py
Then open: http://127.0.0.1:8050
"""

import os

from dash import Dash, Input, Output, callback, html

import ansys_saf_projects_dashboard

app = Dash(__name__)

api_base_url = os.getenv("GLOW_API_URL")

app.layout = html.Div(
    [
        # Header
        html.H1("Projects Dashboard Demo", style={"textAlign": "center"}),
        # Projects Dashboard component
        ansys_saf_projects_dashboard.ProjectsDashboard(
            id="projects-dashboard",
            apiBaseUrl=api_base_url,
        ),
        # Action result output
        html.Div(
            [
                html.H4("Action Log"),
                html.Div(
                    id="action-output",
                    style={
                        "padding": "10px",
                        "backgroundColor": "#f5f5f5",
                        "borderRadius": "4px",
                        "minHeight": "50px",
                    },
                ),
            ],
            style={"maxWidth": "1200px", "margin": "20px auto"},
        ),
        # Projects count
        html.Div(
            [
                html.Span(id="project-count", style={"fontWeight": "bold"}),
            ],
            style={"textAlign": "center", "margin": "20px"},
        ),
    ]
)


# Track action results
@callback(
    Output("action-output", "children"),
    Input("projects-dashboard", "actionResult"),
    prevent_initial_call=True,
)
def display_action_result(action_result):
    """Display the result of CRUD actions."""
    if action_result is None:
        return "No actions yet..."

    action = action_result.get("action", "unknown")
    success = action_result.get("success", False)
    message = action_result.get("message", "")
    project_id = action_result.get("projectId", "")
    timestamp = action_result.get("timestamp", 0)

    # Format timestamp
    from datetime import datetime

    time_str = datetime.fromtimestamp(timestamp / 1000).strftime("%H:%M:%S") if timestamp else ""

    if success:
        return html.Div(
            [
                html.Span(f"[{time_str}] ", style={"color": "#666"}),
                html.Span("✅ ", style={"fontSize": "1.2em"}),
                html.Strong(f"{action.upper()}: "),
                html.Span(message or project_id or "Success"),
            ],
            style={"color": "#155724"},
        )
    else:
        return html.Div(
            [
                html.Span(f"[{time_str}] ", style={"color": "#666"}),
                html.Span("❌ ", style={"fontSize": "1.2em"}),
                html.Strong(f"{action.upper()} FAILED: "),
                html.Span(message or "Unknown error"),
            ],
            style={"color": "#721c24"},
        )


# Monitor projects list changes
@callback(
    Output("project-count", "children"),
    Input("projects-dashboard", "projects"),
)
def update_project_count(projects):
    """Update the project count display."""
    count = len(projects) if projects else 0
    return f"📊 Total projects: {count}"


if __name__ == "__main__":
    print("=" * 50)
    print("Projects Dashboard Demo")
    print("=" * 50)
    print("Open http://127.0.0.1:8050 in your browser")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    app.run(debug=True)
