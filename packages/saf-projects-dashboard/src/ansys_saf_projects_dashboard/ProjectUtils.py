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

import typing  # noqa: F401

from dash.development.base_component import Component, _explicitize_args
from typing_extensions import Literal, NotRequired, TypedDict  # noqa: F401

ComponentSingleType = typing.Union[str, int, float, Component, None]
ComponentType = typing.Union[
    ComponentSingleType,
    typing.Sequence[ComponentSingleType],
]

NumberType = typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]


class ProjectUtils(Component):
    """A ProjectUtils component.


    Keyword arguments:

    - src (string; optional)"""

    _children_props: typing.List[str] = []
    _base_nodes = ["children"]
    _namespace = "ansys_saf_projects_dashboard"
    _type = "ProjectUtils"

    def __init__(self, src: typing.Optional[str] = None, **kwargs):
        self._prop_names = ["src"]
        self._valid_wildcard_attributes = []
        self.available_properties = ["src"]
        self.available_wildcard_properties = []
        _explicit_args = kwargs.pop("_explicit_args")
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(ProjectUtils, self).__init__(**args)


setattr(ProjectUtils, "__init__", _explicitize_args(ProjectUtils.__init__))
