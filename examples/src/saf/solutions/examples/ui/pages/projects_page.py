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

"""Frontend of the projects dashboard page.

The page is only registered when ansys-saf-projects-dashboard is installed.
Otherwise, ``saf run --portal`` falls back to the SAF Desktop Portal, then to the SAF Portal.
"""

import os
from types import ModuleType

import dash

# Import the component library when the module is loaded: Dash refuses component libraries imported in a callback.
try:
    import ansys_saf_projects_dashboard
    from ansys_saf_projects_dashboard import ProjectsDashboard
except ImportError:
    ansys_saf_projects_dashboard = None
    ProjectsDashboard = None

# Keep in sync with the desktop orchestrator, which opens this path when ``--portal`` uses the projects dashboard.
PROJECTS_DASHBOARD_PATH = os.getenv("SAF_DESKTOP_PROJECTS_DASHBOARD_PATH", "/projects")

_PROPTYPES_SCRIPT = "proptypes.js"
_FONTS = ("assets/fonts/SourceSans3.ttf", "assets/fonts/SourceCodePro.ttf")


def _fix_dashboard_resources(package: ModuleType) -> None:
    """Fix the scripts and fonts that ansys-saf-projects-dashboard 0.2.0 declares to Dash.

    Dash loads the scripts of a component library on every page, not only on the dashboard:

    - ``proptypes.js`` is declared as development only, but Dash still serves it, and it raises a
      ``TypeError`` in the browser console of every page.
    - The fonts of the dashboard styles are not declared, so Dash answers their requests with an error 500.

    Both changes are skipped once the package declares its resources correctly.
    """
    resources = package._js_dist
    resources[:] = [resource for resource in resources if resource.get("relative_package_path") != _PROPTYPES_SCRIPT]
    declared_paths = {resource.get("relative_package_path") for resource in resources}
    # Dynamic resources are served on request without adding a script tag to the pages.
    resources.extend(
        {"relative_package_path": font, "namespace": package._dash_namespace, "dynamic": True}
        for font in _FONTS
        if font not in declared_paths
    )


if ansys_saf_projects_dashboard is not None:
    _fix_dashboard_resources(ansys_saf_projects_dashboard)
    dash.register_page(
        __name__,
        name="Projects",
        path=PROJECTS_DASHBOARD_PATH,
        order=-1,
        project_scoped=False,  # displayed without a project, outside the navigation tree of the steps
        projects_dashboard=True,  # identifies this page in the page registry without importing this module
    )


def layout(theme: str = "light"):
    """Layout of the projects dashboard page, whose theme follows the color scheme of the app."""
    return ProjectsDashboard(
        id="projects-dashboard",
        apiBaseUrl=os.getenv("GLOW_EXTERNAL_API_URL") or os.getenv("GLOW_API_URL"),
        solutionDescription="Solution Examples: view and manage your projects.",
        themeMode=theme,
    )
