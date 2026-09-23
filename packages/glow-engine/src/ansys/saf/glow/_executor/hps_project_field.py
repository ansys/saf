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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast, get_args, get_origin

from ansys.saf.glow._hps_parametric_studies.base import (
    DynamicHpsProject,
    HpsParametricStudyProjectBase,
    HpsProject,
    HpsSimpleProjectBase,
)
from ansys.saf.glow._server.exceptions import MalformedSolutionError

HpsProjectWrapperFactory = Callable[[HpsProject, str], DynamicHpsProject]


class HpsProjectFieldTransformer(Protocol):
    @property
    def contains_hps_projects(self) -> bool: ...

    def to_persisted(self, value: Any, context: str) -> Any: ...

    def to_dynamic(
        self,
        value: Any,
        context: str,
        wrapper_factory: HpsProjectWrapperFactory,
    ) -> Any: ...


class UnknownHpsProjectFieldTransformer:
    @property
    def contains_hps_projects(self) -> bool:
        return False

    def to_persisted(self, value: Any, context: str) -> Any:
        return value

    def to_dynamic(
        self,
        value: Any,
        context: str,
        wrapper_factory: HpsProjectWrapperFactory,
    ) -> Any:
        return value


@dataclass(frozen=True)
class HpsProjectTransformer:
    project_type: type[HpsProject]

    @property
    def contains_hps_projects(self) -> bool:
        return True

    def to_persisted(self, value: Any, context: str) -> HpsProject:
        if not isinstance(value, DynamicHpsProject):
            raise MalformedSolutionError(
                f"{context} contains an invalid HPS project handle. "
                "Use HpsSimpleProject.start_hps_job() or "
                "HpsParametricStudyProject.start_hps_parametric_study() to create it.",
            )
        persisted_project = value.persisted_project
        if not isinstance(persisted_project, self.project_type):
            raise MalformedSolutionError(f"{context} contains an invalid HPS project handle.")
        return persisted_project

    def to_dynamic(
        self,
        value: Any,
        context: str,
        wrapper_factory: HpsProjectWrapperFactory,
    ) -> DynamicHpsProject:
        if not isinstance(value, self.project_type):
            raise MalformedSolutionError(f"{context} contains an invalid persisted HPS project.")
        return wrapper_factory(value, context)


@dataclass(frozen=True)
class HpsProjectListTransformer:
    item_transformer: HpsProjectFieldTransformer

    @property
    def contains_hps_projects(self) -> bool:
        return True

    def to_persisted(self, value: Any, context: str) -> list[Any]:
        if not isinstance(value, list):
            raise MalformedSolutionError(f"{context} must be a list.")
        return [
            self.item_transformer.to_persisted(item, f"{context}[{index}]")
            for index, item in enumerate(cast("list[Any]", value))
        ]

    def to_dynamic(
        self,
        value: Any,
        context: str,
        wrapper_factory: HpsProjectWrapperFactory,
    ) -> list[Any]:
        if not isinstance(value, list):
            raise MalformedSolutionError(f"{context} must be a list.")
        return [
            self.item_transformer.to_dynamic(item, f"{context}[{index}]", wrapper_factory)
            for index, item in enumerate(cast("list[Any]", value))
        ]


@dataclass(frozen=True)
class HpsProjectDictionaryTransformer:
    value_transformer: HpsProjectFieldTransformer

    @property
    def contains_hps_projects(self) -> bool:
        return True

    def to_persisted(self, value: Any, context: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise MalformedSolutionError(f"{context} must be a dictionary.")
        return {
            key: self.value_transformer.to_persisted(item, f"{context}[{key!r}]")
            for key, item in cast("dict[str, Any]", value).items()
        }

    def to_dynamic(
        self,
        value: Any,
        context: str,
        wrapper_factory: HpsProjectWrapperFactory,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise MalformedSolutionError(f"{context} must be a dictionary.")
        return {
            key: self.value_transformer.to_dynamic(item, f"{context}[{key!r}]", wrapper_factory)
            for key, item in cast("dict[str, Any]", value).items()
        }


def _safe_issubclass(candidate: Any, classinfo: type | tuple[type, ...]) -> bool:
    try:
        return issubclass(candidate, classinfo)
    except TypeError:
        return False


class HpsProjectFieldTransformerBuilder:
    def build(self, annotation: Any) -> HpsProjectFieldTransformer:
        if _safe_issubclass(annotation, (HpsSimpleProjectBase, HpsParametricStudyProjectBase)):
            return HpsProjectTransformer(annotation)
        type_arguments = get_args(annotation)
        if get_origin(annotation) is list and len(type_arguments) == 1:
            item_transformer = self.build(type_arguments[0])
            if item_transformer.contains_hps_projects:
                return HpsProjectListTransformer(item_transformer)
        if get_origin(annotation) is dict and len(type_arguments) == 2 and type_arguments[0] is str:
            value_transformer = self.build(type_arguments[1])
            if value_transformer.contains_hps_projects:
                return HpsProjectDictionaryTransformer(value_transformer)
        return UnknownHpsProjectFieldTransformer()
