# Copyright (C) 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# ruff: noqa
# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component, _explicitize_args
try:
    from dash.types import NumberType  # noqa: F401
except ImportError:
    # Backwards compatibility for dash<=4.1.0
    if typing.TYPE_CHECKING:
        raise
    NumberType = typing.Union[  # noqa: F401
        typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex
    ]

ComponentSingleType = typing.Union[str, int, float, Component, None]
ComponentType = typing.Union[
    ComponentSingleType,
    typing.Sequence[ComponentSingleType],
]


class ProjectsList(Component):
    """A ProjectsList component.


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
    _type = 'ProjectsList'
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

        super(ProjectsList, self).__init__(**args)

setattr(ProjectsList, "__init__", _explicitize_args(ProjectsList.__init__))
