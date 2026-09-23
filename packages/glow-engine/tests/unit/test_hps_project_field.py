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
from typing import Any
from unittest.mock import MagicMock

import pytest

from ansys.saf.glow._core.blob_managers import HpsBlobManager
from ansys.saf.glow._executor.hps_project_field import HpsProjectFieldTransformerBuilder
from ansys.saf.glow._hps_auth.hps_authenticator import NullHpsAuthenticator
from ansys.saf.glow._hps_parametric_studies.api import HpsParametricStudyProject, HpsSimpleProject
from ansys.saf.glow._hps_parametric_studies.base import (
    DynamicHpsParametricStudyProject,
    DynamicHpsProject,
    DynamicHpsSimpleProject,
    HpsProject,
)
from ansys.saf.glow._server.exceptions import MalformedSolutionError

ProjectCase = tuple[
    type[HpsProject],
    type[DynamicHpsProject],
    type[HpsProject],
]

PROJECT_CASES: list[ProjectCase] = [
    (HpsSimpleProject, DynamicHpsSimpleProject, HpsParametricStudyProject),
    (HpsParametricStudyProject, DynamicHpsParametricStudyProject, HpsSimpleProject),
]


def _dynamic_project(project: HpsProject, dynamic_type: type[DynamicHpsProject]) -> DynamicHpsProject:
    return dynamic_type(project, MagicMock(spec=HpsBlobManager), NullHpsAuthenticator())


def _wrapper_factory(project: HpsProject, context: str) -> DynamicHpsProject:
    del context
    dynamic_type = (
        DynamicHpsParametricStudyProject
        if isinstance(project, HpsParametricStudyProject)
        else DynamicHpsSimpleProject
    )
    return _dynamic_project(project, dynamic_type)


@pytest.mark.parametrize(("project_type", "dynamic_type", "wrong_project_type"), PROJECT_CASES)
def test_scalar_hps_project_transforms_in_both_directions(
    project_type: type[HpsProject],
    dynamic_type: type[DynamicHpsProject],
    wrong_project_type: type[HpsProject],
):
    del wrong_project_type
    persisted_project = project_type(hps_project_identifier="project-id")
    dynamic_project = _dynamic_project(persisted_project, dynamic_type)
    transformer = HpsProjectFieldTransformerBuilder().build(project_type)
    wrapped_project = _dynamic_project(persisted_project, dynamic_type)
    wrapper_factory: Callable[[HpsProject, str], DynamicHpsProject] = MagicMock(return_value=wrapped_project)

    assert transformer.contains_hps_projects
    assert transformer.to_persisted(dynamic_project, "Field 'project'") == persisted_project
    assert transformer.to_dynamic(persisted_project, "Field 'project'", wrapper_factory) is wrapped_project
    wrapper_factory.assert_called_once_with(persisted_project, "Field 'project'")  # type: ignore[attr-defined]


@pytest.mark.parametrize(("project_type", "dynamic_type", "wrong_project_type"), PROJECT_CASES)
def test_scalar_hps_project_rejects_raw_project_on_upload(
    project_type: type[HpsProject],
    dynamic_type: type[DynamicHpsProject],
    wrong_project_type: type[HpsProject],
):
    del dynamic_type, wrong_project_type
    transformer = HpsProjectFieldTransformerBuilder().build(project_type)

    with pytest.raises(MalformedSolutionError, match="Field 'project'.*start_hps_job"):
        transformer.to_persisted(project_type(hps_project_identifier="raw"), "Field 'project'")


@pytest.mark.parametrize(("project_type", "dynamic_type", "wrong_project_type"), PROJECT_CASES)
def test_scalar_hps_project_rejects_wrong_subtype(
    project_type: type[HpsProject],
    dynamic_type: type[DynamicHpsProject],
    wrong_project_type: type[HpsProject],
):
    transformer = HpsProjectFieldTransformerBuilder().build(project_type)
    wrong_persisted_project = wrong_project_type(hps_project_identifier="wrong")
    wrong_dynamic_project = _dynamic_project(wrong_persisted_project, dynamic_type)

    with pytest.raises(MalformedSolutionError, match="Field 'project'.*invalid HPS project handle"):
        transformer.to_persisted(wrong_dynamic_project, "Field 'project'")

    with pytest.raises(MalformedSolutionError, match="Field 'project'.*invalid persisted HPS project"):
        transformer.to_dynamic(wrong_persisted_project, "Field 'project'", MagicMock())


@pytest.mark.parametrize(("project_type", "dynamic_type", "wrong_project_type"), PROJECT_CASES)
def test_scalar_hps_project_rejects_none(
    project_type: type[HpsProject],
    dynamic_type: type[DynamicHpsProject],
    wrong_project_type: type[HpsProject],
):
    del dynamic_type, wrong_project_type
    transformer = HpsProjectFieldTransformerBuilder().build(project_type)

    with pytest.raises(MalformedSolutionError, match="Field 'project'.*invalid HPS project handle"):
        transformer.to_persisted(None, "Field 'project'")

    with pytest.raises(MalformedSolutionError, match="Field 'project'.*invalid persisted HPS project"):
        transformer.to_dynamic(None, "Field 'project'", MagicMock())


def test_unknown_hps_project_field_transformer_passes_values_through():
    transformer = HpsProjectFieldTransformerBuilder().build(str)
    value = object()
    wrapper_factory: Callable[[HpsProject, str], DynamicHpsProject] = MagicMock()

    assert not transformer.contains_hps_projects
    assert transformer.to_persisted(value, "Field 'value'") is value
    assert transformer.to_dynamic(value, "Field 'value'", wrapper_factory) is value
    wrapper_factory.assert_not_called()  # type: ignore[attr-defined]


def test_hps_project_list_transforms_all_items():
    persisted_projects = [
        HpsSimpleProject(hps_project_identifier="first"),
        HpsSimpleProject(hps_project_identifier="second"),
    ]
    dynamic_projects = [_dynamic_project(project, DynamicHpsSimpleProject) for project in persisted_projects]
    transformer = HpsProjectFieldTransformerBuilder().build(list[HpsSimpleProject])

    assert transformer.contains_hps_projects
    assert transformer.to_persisted(dynamic_projects, "Field 'projects'") == persisted_projects
    restored = transformer.to_dynamic(persisted_projects, "Field 'projects'", _wrapper_factory)
    assert [project.persisted_project for project in restored] == persisted_projects


def test_hps_project_dictionary_preserves_keys_and_values():
    persisted_projects = {
        "first": HpsParametricStudyProject(hps_project_identifier="first"),
        "second": HpsParametricStudyProject(hps_project_identifier="second"),
    }
    dynamic_projects = {
        key: _dynamic_project(project, DynamicHpsParametricStudyProject)
        for key, project in persisted_projects.items()
    }
    transformer = HpsProjectFieldTransformerBuilder().build(dict[str, HpsParametricStudyProject])

    assert transformer.contains_hps_projects
    assert transformer.to_persisted(dynamic_projects, "Field 'projects'") == persisted_projects
    restored = transformer.to_dynamic(persisted_projects, "Field 'projects'", _wrapper_factory)
    assert list(restored) == ["first", "second"]
    assert {key: project.persisted_project for key, project in restored.items()} == persisted_projects


def test_nested_hps_project_dictionary_of_lists_transforms_recursively():
    persisted_projects = {
        "group_1": [
            HpsSimpleProject(hps_project_identifier="first"),
            HpsSimpleProject(hps_project_identifier="second"),
        ],
    }
    dynamic_projects = {
        key: [_dynamic_project(project, DynamicHpsSimpleProject) for project in projects]
        for key, projects in persisted_projects.items()
    }
    transformer = HpsProjectFieldTransformerBuilder().build(dict[str, list[HpsSimpleProject]])

    assert transformer.to_persisted(dynamic_projects, "Field 'groups'") == persisted_projects
    restored = transformer.to_dynamic(persisted_projects, "Field 'groups'", _wrapper_factory)
    assert [project.persisted_project for project in restored["group_1"]] == persisted_projects["group_1"]


def test_nested_hps_project_list_of_dictionaries_transforms_recursively():
    persisted_projects = [
        {"study": HpsParametricStudyProject(hps_project_identifier="study")},
    ]
    dynamic_projects = [
        {"study": _dynamic_project(persisted_projects[0]["study"], DynamicHpsParametricStudyProject)},
    ]
    transformer = HpsProjectFieldTransformerBuilder().build(list[dict[str, HpsParametricStudyProject]])

    assert transformer.to_persisted(dynamic_projects, "Field 'groups'") == persisted_projects
    restored = transformer.to_dynamic(persisted_projects, "Field 'groups'", _wrapper_factory)
    assert restored[0]["study"].persisted_project == persisted_projects[0]["study"]


@pytest.mark.parametrize(
    ("annotation", "empty_value"),
    [(list[HpsSimpleProject], []), (dict[str, HpsSimpleProject], {})],
)
def test_empty_hps_project_list_or_dictionary_is_preserved(annotation: Any, empty_value: Any):
    transformer = HpsProjectFieldTransformerBuilder().build(annotation)

    assert transformer.to_persisted(empty_value, "Field 'projects'") == empty_value
    assert transformer.to_dynamic(empty_value, "Field 'projects'", _wrapper_factory) == empty_value


@pytest.mark.parametrize(
    ("annotation", "wrong_value", "expected_message"),
    [
        (list[HpsSimpleProject], {}, "Field 'projects' must be a list"),
        (dict[str, HpsSimpleProject], [], "Field 'projects' must be a dictionary"),
    ],
)
def test_hps_project_list_or_dictionary_rejects_wrong_shape(
    annotation: Any,
    wrong_value: Any,
    expected_message: str,
):
    transformer = HpsProjectFieldTransformerBuilder().build(annotation)

    with pytest.raises(MalformedSolutionError, match=expected_message):
        transformer.to_persisted(wrong_value, "Field 'projects'")

    with pytest.raises(MalformedSolutionError, match=expected_message):
        transformer.to_dynamic(wrong_value, "Field 'projects'", _wrapper_factory)


def test_nested_hps_project_error_contains_exact_path():
    transformer = HpsProjectFieldTransformerBuilder().build(dict[str, list[HpsSimpleProject]])
    projects = {
        "group_1": [
            _dynamic_project(HpsSimpleProject(hps_project_identifier="first"), DynamicHpsSimpleProject),
            _dynamic_project(HpsSimpleProject(hps_project_identifier="second"), DynamicHpsSimpleProject),
            HpsSimpleProject(hps_project_identifier="raw"),
        ],
    }

    with pytest.raises(MalformedSolutionError, match=r"Field 'groups'\['group_1'\]\[2\].*start_hps_job"):
        transformer.to_persisted(projects, "Field 'groups'")


def test_nested_hps_project_download_rejects_wrong_subtype_with_exact_path():
    transformer = HpsProjectFieldTransformerBuilder().build(dict[str, list[HpsSimpleProject]])
    projects = {
        "group_1": [
            HpsSimpleProject(hps_project_identifier="simple"),
            HpsParametricStudyProject(hps_project_identifier="study"),
        ],
    }

    with pytest.raises(
        MalformedSolutionError,
        match=r"Field 'groups'\['group_1'\]\[1\].*invalid persisted HPS project",
    ):
        transformer.to_dynamic(projects, "Field 'groups'", _wrapper_factory)


def test_dictionary_with_non_string_keys_uses_unknown_transformer():
    transformer = HpsProjectFieldTransformerBuilder().build(dict[int, HpsSimpleProject])
    value = {1: HpsSimpleProject(hps_project_identifier="raw")}

    assert not transformer.contains_hps_projects
    assert transformer.to_persisted(value, "Field 'projects'") is value
    assert transformer.to_dynamic(value, "Field 'projects'", _wrapper_factory) is value
