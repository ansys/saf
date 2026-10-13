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

# ruff: noqa: N999

import typing
from typing import Literal, NotRequired  # noqa: F401

from dash.development.base_component import Component, _explicitize_args
from typing_extensions import TypedDict

ComponentSingleType = typing.Union[str, int, float, Component, None]  # noqa: UP007
ComponentType = typing.Union[  # noqa: UP007
    ComponentSingleType,
    typing.Sequence[ComponentSingleType],
]

NumberType = typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]  # noqa: UP007


class ContextMenu(Component):
    """A ContextMenu component.


    Keyword arguments:

    - items (list of dicts; required)

        `items` is a list of dicts with keys:

        - label (string; required)

        - icon (string; required)

        - onClick (required)

        - className (string; optional)"""

    _children_props: list[str] = []
    _base_nodes = ["children"]
    _namespace = "ansys_saf_projects_dashboard"
    _type = "ContextMenu"
    Items = TypedDict("Items", {"label": str, "icon": str, "onClick": typing.Any, "className": NotRequired[str]})  # noqa: UP013

    def __init__(self, items: typing.Sequence["Items"] | None = None, **kwargs):
        self._prop_names = ["items"]
        self._valid_wildcard_attributes = []
        self.available_properties = ["items"]
        self.available_wildcard_properties = []
        _explicit_args = kwargs.pop("_explicit_args")
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ["items"]:
            if k not in args:
                raise TypeError("Required argument `" + k + "` was not specified.")

        super().__init__(**args)


ContextMenu.__init__ = _explicitize_args(ContextMenu.__init__)
