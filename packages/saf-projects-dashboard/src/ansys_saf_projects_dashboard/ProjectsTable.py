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


class ProjectsTable(Component):
    """A ProjectsTable component.


Keyword arguments:

- favoriteIds (list of strings; required):
    Array of project IDs that are favorited.

- projectIconUrl (string; optional):
    Optional URL for the default project icon (solution-level
    override).

- projects (list of dicts; required):
    Array of projects to display.

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
        API)."""
    _children_props: typing.List[str] = []
    _base_nodes = ['children']
    _namespace = 'ansys_saf_projects_dashboard'
    _type = 'ProjectsTable'
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


    def __init__(
        self,
        projects: typing.Optional[typing.Sequence["Projects"]] = None,
        projectIconUrl: typing.Optional[str] = None,
        onEdit: typing.Optional[typing.Any] = None,
        onDelete: typing.Optional[typing.Any] = None,
        onExport: typing.Optional[typing.Any] = None,
        onCardClick: typing.Optional[typing.Any] = None,
        onFavoriteToggle: typing.Optional[typing.Any] = None,
        onInfo: typing.Optional[typing.Any] = None,
        favoriteIds: typing.Optional[typing.Sequence[str]] = None,
        **kwargs
    ):
        self._prop_names = ['favoriteIds', 'projectIconUrl', 'projects']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['favoriteIds', 'projectIconUrl', 'projects']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ['favoriteIds', 'projects']:
            if k not in args:
                raise TypeError(
                    'Required argument `' + k + '` was not specified.')

        super(ProjectsTable, self).__init__(**args)

setattr(ProjectsTable, "__init__", _explicitize_args(ProjectsTable.__init__))
