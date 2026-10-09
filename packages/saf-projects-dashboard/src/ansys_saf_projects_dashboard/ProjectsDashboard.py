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

# ruff: noqa
# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component, _explicitize_args

ComponentSingleType = typing.Union[str, int, float, Component, None]
ComponentType = typing.Union[
    ComponentSingleType,
    typing.Sequence[ComponentSingleType],
]

NumberType = typing.Union[
    typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex
]


class ProjectsDashboard(Component):
    """A ProjectsDashboard component.


Keyword arguments:

- id (string; optional):
    Unique ID to identify this component in Dash callbacks.

- actionResult (dict; optional):
    Result of the last action performed (for callback tracking).
    Updated after each CRUD operation completes.

    `actionResult` is a dict with keys:

    - action (a value equal to: 'create', 'update', 'delete', 'import', 'export', 'upgrade', 'list'; required):
        The type of action performed.

    - projectId (string; optional):
        The project ID involved in the action (if applicable).

    - success (boolean; required):
        Whether the action was successful.

    - message (string; optional):
        Human-readable message describing the result.

    - timestamp (number; required):
        Timestamp of the action (milliseconds since epoch).

- apiBaseUrl (string; optional):
    Base URL for the GLOW API backend. If provided, API calls will use
    this URL (e.g., \"http://127.0.0.1:5678\"). If not provided, uses
    relative URLs which require a Flask proxy to forward requests.

- currentPage (number; optional):
    1-based index of the currently displayed page. Defaults to 1.

- error (string; optional):
    Current error message, if any.

- filters (dict; optional):
    Applied date-range filters forwarded to GLOW `GET /projects`.
    Updated when the user clicks Apply or Clear all in the filter bar.

    `filters` is a dict with keys:

    - search (string; optional):
        Inclusive search input text for display name search.

    - dateCreatedFrom (string; optional):
        Inclusive lower bound on `date_created`.

    - dateCreatedTo (string; optional):
        Inclusive upper bound on `date_created`.

    - dateModifiedFrom (string; optional):
        Inclusive lower bound on `date_modified`.

    - dateModifiedTo (string; optional):
        Inclusive upper bound on `date_modified`.

- loading (boolean; optional):
    Whether the component is currently loading data.

- notification (dict; optional):
    Current notification message to display.

    `notification` is a dict with keys:

    - message (string; required):
        The notification message text.

    - type (a value equal to: 'error', 'success', 'info', 'warning'; required):
        Notification type for styling.

- pageSize (number; optional):
    Number of projects displayed per page. Defaults to 10. Allowed
    values surfaced in the UI: 5, 10, 20, 50.

- pendingDeleteId (string; optional):
    ID of project pending deletion (for confirmation modal).

- projectIconUrl (string; optional):
    URL for the default project icon displayed on project cards. If
    provided, this URL is used as the `<img src>` for every card that
    does not supply its own per-project `icon` field. If omitted, a
    bundled inline SVG icon is rendered instead (zero HTTP requests).

- projects (list of dicts; optional):
    List of projects currently loaded. Updated automatically when
    projects are loaded, created, updated, or deleted.

    `projects` is a list of dicts with keys:

    - name (string; required):
        The URI path identifying the project resource (e.g.,
        \"projects/2ztdlpa2\").

    - display_name (string; required):
        The project name displayed to the user.

    - description (string; optional):
        Optional project description.

    - date_created (string; optional):
        Date and time of creation (ISO 8601 format).

    - date_modified (string; optional):
        Date and time of last modification (ISO 8601 format).

    - icon (string; optional):
        URL for the project icon (per-project custom icon from the
        API).

- selectedProject (dict; optional):
    Currently selected project for editing. Set when user clicks Edit
    on a project card.

    `selectedProject` is a dict with keys:

    - name (string; required):
        The URI path identifying the project resource (e.g.,
        \"projects/2ztdlpa2\").

    - display_name (string; required):
        The project name displayed to the user.

    - description (string; optional):
        Optional project description.

    - date_created (string; optional):
        Date and time of creation (ISO 8601 format).

    - date_modified (string; optional):
        Date and time of last modification (ISO 8601 format).

    - icon (string; optional):
        URL for the project icon (per-project custom icon from the
        API).

- showCreateForm (boolean; optional):
    Whether the create project form is currently shown.

- showUpgradeSnackbar (boolean; optional):
    Whether to show the upgrade snackbar.

- solutionDescription (string; optional):
    Description text for the solution displayed in the header. If
    omitted, defaults to \"Here is the description of the
    solution...\".

- solutionImageUrl (string; optional):
    URL for the solution application image displayed in the header.
    Typically points to a Dash-served asset (e.g.,
    \"/assets/application.svg\"). If omitted or fails to load, a
    bundled inline SVG is rendered instead.

- themeMode (a value equal to: 'light', 'dark'; optional):
    Theme Mode for the dashboard: \"light\" or \"dark\". When provided
    externally (e.g., from DMC MantineProvider), the component uses
    this value and hides its own theme toggle button.

- totalPages (number; optional):
    Total number of pages available on the server for the current
    `pageSize`. Set automatically after each project load so Python
    callbacks can read it.

- totalProjects (number; optional):
    Total number of projects available on the server. Set
    automatically after each project load so Python callbacks can read
    it.

- upgradeProjectId (string; optional):
    ID of project pending upgrade."""
    _children_props: typing.List[str] = []
    _base_nodes = ['children']
    _namespace = 'ansys_saf_projects_dashboard'
    _type = 'ProjectsDashboard'
    Projects = TypedDict(
        "Projects",
            {
            "name": str,
            "display_name": str,
            "description": NotRequired[str],
            "date_created": NotRequired[str],
            "date_modified": NotRequired[str],
            "icon": NotRequired[str]
        }
    )

    SelectedProject = TypedDict(
        "SelectedProject",
            {
            "name": str,
            "display_name": str,
            "description": NotRequired[str],
            "date_created": NotRequired[str],
            "date_modified": NotRequired[str],
            "icon": NotRequired[str]
        }
    )

    Notification = TypedDict(
        "Notification",
            {
            "message": str,
            "type": Literal["error", "success", "info", "warning"]
        }
    )

    ActionResult = TypedDict(
        "ActionResult",
            {
            "action": Literal["create", "update", "delete", "import", "export", "upgrade", "list"],
            "projectId": NotRequired[str],
            "success": bool,
            "message": NotRequired[str],
            "timestamp": NumberType
        }
    )

    Filters = TypedDict(
        "Filters",
            {
            "search": NotRequired[str],
            "dateCreatedFrom": NotRequired[str],
            "dateCreatedTo": NotRequired[str],
            "dateModifiedFrom": NotRequired[str],
            "dateModifiedTo": NotRequired[str]
        }
    )


    def __init__(
        self,
        apiBaseUrl: typing.Optional[str] = None,
        projectIconUrl: typing.Optional[str] = None,
        solutionImageUrl: typing.Optional[str] = None,
        solutionDescription: typing.Optional[str] = None,
        projects: typing.Optional[typing.Sequence["Projects"]] = None,
        loading: typing.Optional[bool] = None,
        error: typing.Optional[str] = None,
        selectedProject: typing.Optional["SelectedProject"] = None,
        showCreateForm: typing.Optional[bool] = None,
        notification: typing.Optional["Notification"] = None,
        actionResult: typing.Optional["ActionResult"] = None,
        pendingDeleteId: typing.Optional[str] = None,
        showUpgradeSnackbar: typing.Optional[bool] = None,
        upgradeProjectId: typing.Optional[str] = None,
        themeMode: typing.Optional[Literal["light", "dark"]] = None,
        currentPage: typing.Optional[NumberType] = None,
        pageSize: typing.Optional[NumberType] = None,
        totalProjects: typing.Optional[NumberType] = None,
        totalPages: typing.Optional[NumberType] = None,
        filters: typing.Optional["Filters"] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'actionResult', 'apiBaseUrl', 'currentPage', 'error', 'filters', 'loading', 'notification', 'pageSize', 'pendingDeleteId', 'projectIconUrl', 'projects', 'selectedProject', 'showCreateForm', 'showUpgradeSnackbar', 'solutionDescription', 'solutionImageUrl', 'themeMode', 'totalPages', 'totalProjects', 'upgradeProjectId']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'actionResult', 'apiBaseUrl', 'currentPage', 'error', 'filters', 'loading', 'notification', 'pageSize', 'pendingDeleteId', 'projectIconUrl', 'projects', 'selectedProject', 'showCreateForm', 'showUpgradeSnackbar', 'solutionDescription', 'solutionImageUrl', 'themeMode', 'totalPages', 'totalProjects', 'upgradeProjectId']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(ProjectsDashboard, self).__init__(**args)

setattr(ProjectsDashboard, "__init__", _explicitize_args(ProjectsDashboard.__init__))
