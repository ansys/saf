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


class ProjectsFilter(Component):
    """A ProjectsFilter component.


Keyword arguments:

- value (dict; required)

    `value` is a dict with keys:

    - search (string; optional):
        Inclusive search input text for display name search.

    - dateCreatedFrom (string; optional):
        Inclusive lower bound on `date_created`.

    - dateCreatedTo (string; optional):
        Inclusive upper bound on `date_created`.

    - dateModifiedFrom (string; optional):
        Inclusive lower bound on `date_modified`.

    - dateModifiedTo (string; optional):
        Inclusive upper bound on `date_modified`."""
    _children_props: typing.List[str] = []
    _base_nodes = ['children']
    _namespace = 'ansys_saf_projects_dashboard'
    _type = 'ProjectsFilter'
    Value = TypedDict(
        "Value",
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
        value: typing.Optional["Value"] = None,
        onApply: typing.Optional[typing.Any] = None,
        onClear: typing.Optional[typing.Any] = None,
        **kwargs
    ):
        self._prop_names = ['value']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['value']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ['value']:
            if k not in args:
                raise TypeError(
                    'Required argument `' + k + '` was not specified.')

        super(ProjectsFilter, self).__init__(**args)

setattr(ProjectsFilter, "__init__", _explicitize_args(ProjectsFilter.__init__))
