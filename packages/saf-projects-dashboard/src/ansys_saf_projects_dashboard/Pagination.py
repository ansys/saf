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

# ruff: noqa
# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal  # noqa: F401
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


class Pagination(Component):
    """A Pagination component.


    Keyword arguments:

    - currentPage (number; required)

    - pageSize (number; required)

    - totalPages (number; required)

    - totalProjects (number; required)"""

    _children_props: typing.List[str] = []
    _base_nodes = ["children"]
    _namespace = "ansys_saf_projects_dashboard"
    _type = "Pagination"

    def __init__(
        self,
        currentPage: typing.Optional[NumberType] = None,
        pageSize: typing.Optional[NumberType] = None,
        totalProjects: typing.Optional[NumberType] = None,
        totalPages: typing.Optional[NumberType] = None,
        onPageChange: typing.Optional[typing.Any] = None,
        onPageSizeChange: typing.Optional[typing.Any] = None,
        **kwargs,
    ):
        self._prop_names = ["currentPage", "pageSize", "totalPages", "totalProjects"]
        self._valid_wildcard_attributes = []
        self.available_properties = ["currentPage", "pageSize", "totalPages", "totalProjects"]
        self.available_wildcard_properties = []
        _explicit_args = kwargs.pop("_explicit_args")
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ["currentPage", "pageSize", "totalPages", "totalProjects"]:
            if k not in args:
                raise TypeError("Required argument `" + k + "` was not specified.")

        super(Pagination, self).__init__(**args)


setattr(Pagination, "__init__", _explicitize_args(Pagination.__init__))
