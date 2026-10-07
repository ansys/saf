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

"""
Benchmark Test Application for ProjectsDashboard Component.

This creates a minimal Dash app for performance benchmarking.
Supports configurable project counts for load testing.

Usage:
    python -m tests.performance.benchmark_dash_app --projects 50 --port 8050
"""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
from typing import Optional

# Try to import Dash components
try:
    from dash import Dash, Input, Output, callback, html
    from projects_dashboard import ProjectsDashboard

    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False


def generate_mock_projects(count: int) -> list[dict]:
    """Generate mock project data for benchmarking."""
    return [
        {
            "name": f"project_{i:04d}",
            "display_name": f"Benchmark Project {i}",
            "description": f"Mock project for performance testing #{i}. " * 3,
            "solution_id": f"sol_{i:04d}",
            "created_date": f"2025-01-{(i % 28) + 1:02d}T10:00:00Z",
            "modified_date": f"2025-06-{(i % 28) + 1:02d}T15:30:00Z",
            "owner": f"user{i % 10}",
            "status": ["active", "archived", "draft"][i % 3],
        }
        for i in range(1, count + 1)
    ]


class MockAPIServer(BaseHTTPRequestHandler):
    """Simple mock API server for project data."""

    project_count = 50  # Default project count

    def log_message(self, format, *args):
        """Suppress request logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/projects" or self.path.startswith("/projects?"):
            projects = generate_mock_projects(self.project_count)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(projects).encode())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def start_mock_api(port: int = 8051, project_count: int = 50):
    """Start mock API server in a background thread."""
    MockAPIServer.project_count = project_count
    server = HTTPServer(("127.0.0.1", port), MockAPIServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def create_benchmark_app(
    project_count: int = 50,
    api_url: str = "http://127.0.0.1:8051",
) -> Optional["Dash"]:
    """
    Create a Dash app for benchmarking the ProjectsDashboard component.

    Args:
        project_count: Number of mock projects to generate
        api_url: Base URL for the mock API server

    Returns:
        Dash application instance
    """
    if not DASH_AVAILABLE:
        print("Error: Dash and projects_dashboard must be installed")
        print("Install with: pip install dash && pip install -e projects_dashboard/")
        return None

    app = Dash(
        __name__,
        title=f"Dashboard Benchmark - {project_count} Projects",
        suppress_callback_exceptions=True,
    )

    app.layout = html.Div(
        [
            html.H1(f"ProjectsDashboard Benchmark ({project_count} projects)", className="benchmark-title"),
            html.Div(id="performance-marker", **{"data-benchmark-start": "true"}),
            ProjectsDashboard(
                id="benchmark-dashboard",
                apiBaseUrl=api_url,
            ),
            html.Div(id="performance-end-marker", **{"data-benchmark-end": "true"}),
        ],
        id="benchmark-container",
        className="benchmark-app",
    )

    return app


def main():
    """Run the benchmark application."""
    parser = argparse.ArgumentParser(description="Run ProjectsDashboard benchmark app")
    parser.add_argument("--projects", type=int, default=50, help="Number of mock projects")
    parser.add_argument("--port", type=int, default=8050, help="Dash app port")
    parser.add_argument("--api-port", type=int, default=8051, help="Mock API server port")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    args = parser.parse_args()

    print(f"Starting mock API server on port {args.api_port} with {args.projects} projects...")
    start_mock_api(args.api_port, args.projects)

    api_url = f"http://127.0.0.1:{args.api_port}"
    print(f"API available at: {api_url}/projects")

    app = create_benchmark_app(args.projects, api_url)
    if app:
        print(f"\nStarting Dash benchmark app on http://127.0.0.1:{args.port}")
        print(f"Configuration: {args.projects} projects")
        print("Press Ctrl+C to stop\n")
        app.run(host="127.0.0.1", port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
