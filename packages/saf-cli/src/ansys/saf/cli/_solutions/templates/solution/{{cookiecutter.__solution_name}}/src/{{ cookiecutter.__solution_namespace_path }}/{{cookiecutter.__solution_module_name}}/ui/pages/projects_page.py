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

"""Frontend of the projects dashboard page.

The page is only registered when ansys-saf-projects-dashboard is installed. Otherwise, ``saf run --portal`` falls back to
the SAF Desktop Portal, then to the SAF Portal.
"""

import importlib.util
import os

import dash

PROJECTS_DASHBOARD_MODULE = "ansys_saf_projects_dashboard"
# Keep in sync with the desktop orchestrator, which opens this path when ``--portal`` uses the projects dashboard.
PROJECTS_DASHBOARD_PATH = os.getenv("SAF_DESKTOP_PROJECTS_DASHBOARD_PATH", "/projects")

if importlib.util.find_spec(PROJECTS_DASHBOARD_MODULE) is not None:
    dash.register_page(
        __name__,
        name="Projects",
        path=PROJECTS_DASHBOARD_PATH,
        order=-1,
        project_scoped=False,  # displayed without a project, outside the navigation tree of the steps
        projects_dashboard=True,  # used by page.py to find this page without importing this module
    )


def layout(theme: str = "light"):
    """Layout of the projects dashboard page, whose theme follows the color scheme of the app."""
    from ansys_saf_projects_dashboard import ProjectsDashboard

    return ProjectsDashboard(
        id="projects-dashboard",
        apiBaseUrl=os.getenv("GLOW_EXTERNAL_API_URL") or os.getenv("GLOW_API_URL"),
        solutionDescription="{{ cookiecutter.__solution_display_name }}: view and manage your projects.",
        themeMode=theme,
    )
