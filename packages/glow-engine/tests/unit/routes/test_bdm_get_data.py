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

from urllib.parse import quote

from fastapi import status
import pytest

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._config.settings import Settings
from tests.mocks.solutions import bdm_solution
from tests.unit.routes.conftest import ProjectFixture

solution = bdm_solution


@pytest.mark.parametrize(
    ("datapath", "lookup", "method", "expected_content", "directories_as_dictionaries"),
    [
        ("", ["directory", "subtop", "leaf.txt"], "store-directory-in-entity-handle", "hello world!", True),
        ("directory", ["subtop", "leaf.txt"], "store-directory-in-entity-handle", "hello world!", True),
        (
            "my_entities/a\\b a\\\\b a\\\\/b",  # keys are "ab a\b a\" then "b"
            [],
            "store-handle-in-nested-dictionary-with-key-containing-characters-requiring-backslash-escape",
            "stored nested with back slash escaped key",
            False,
        ),
        (
            "dict_handles/a\\\\\\/b",  # key is a\/b
            [],
            "store-handle-in-dictionary-with-key-containing-characters-requiring-backslash-escape",
            "stored with back slash escaped key",
            False,
        ),
        (
            "dict_handles/ ()+[]{}%*<>?-_",
            [],
            "store-handle-in-dictionary-with-key-containing-characters-requiring-url-escape",
            "stored with escaped key",
            False,
        ),
        ("result", [], "store-result", "hello world!", False),
        ("list_handles/0", [], "store-list-handles", "list_handles.txt", False),
        ("dict_handles/dict_handle", [], "store-dict-handles", "dict_handles.txt", False),
        (
            "dict_handles/a\\/b\\/c",  # key is "a/b/c"
            [],
            "store-handle-in-dictionary-with-key-containing-multiple-forward-slashes",
            "stored with complex key",
            False,
        ),
        ("directory/subtop/leaf.txt", [], "store-directory-in-entity-handle", "hello world!", False),
        ("sub/sub_handle", [], "store-sub-model", "sub", False),
        ("sub/inner_sub/inner_sub_handle", [], "store-sub-model", "inner_sub", False),
        (
            "my_entities/root_file.txt",
            [],
            "manually-create-entities-dict",
            "This is a file in the root directory",
            False,
        ),
        ("my_entities/subdir1/level1_file.json", [], "manually-create-entities-dict", '{"key": "value"}', False),
        (
            "",
            ["result"],
            "store-result",
            "hello world!",
            False,
        ),
        (
            "",
            ["list_handles", 0],
            "store-list-handles",
            "list_handles.txt",
            False,
        ),
        (
            "",
            ["dict_handles", "dict_handle"],
            "store-dict-handles",
            "dict_handles.txt",
            False,
        ),
        (
            "",
            ["sub", "sub_handle"],
            "store-sub-model",
            "sub",
            False,
        ),
        (
            "",
            ["sub", "inner_sub", "inner_sub_handle"],
            "store-sub-model",
            "inner_sub",
            False,
        ),
        (
            "",
            ["my_entities", "root_file.txt"],
            "manually-create-entities-dict",
            "This is a file in the root directory",
            False,
        ),
        (
            "",
            ["my_entities", "subdir1", "level1_file.json"],
            "manually-create-entities-dict",
            '{"key": "value"}',
            False,
        ),
        (
            "",
            ["dict_handles", "a/b/c"],
            "store-handle-in-dictionary-with-key-containing-multiple-forward-slashes",
            "stored with complex key",
            False,
        ),
        (
            "sub",
            ["sub_handle"],
            "store-sub-model",
            "sub",
            False,
        ),
        (
            "sub",
            ["inner_sub", "inner_sub_handle"],
            "store-sub-model",
            "inner_sub",
            False,
        ),
        (
            "",
            ["dict_handles", " ()+[]{}%*<>?-_"],
            "store-handle-in-dictionary-with-key-containing-characters-requiring-url-escape",
            "stored with escaped key",
            False,
        ),
        (
            "",
            ["my_entities", "ab a\\b a\\", "b"],
            "store-handle-in-nested-dictionary-with-key-containing-characters-requiring-backslash-escape",
            "stored nested with back slash escaped key",
            False,
        ),
        (
            "",
            ["dict_handles", "a\\/b"],
            "store-handle-in-dictionary-with-key-containing-characters-requiring-backslash-escape",
            "stored with back slash escaped key",
            False,
        ),
    ],
)
def test_get_data_with_url_substitution(
    project_fixture: ProjectFixture,
    settings: Settings,
    method: str,
    datapath: str,
    lookup: list[str],
    expected_content: str,
    directories_as_dictionaries: bool,
):
    # GIVEN - step with nested entity handles pointing at files with known content
    project_name = project_fixture.properties["name"]
    method_url = f"{project_name}/steps/bdm-step:{method}"
    project_fixture.client.post(method_url).raise_for_status()

    # WHEN - getting the data with URLs substituted for entity handles
    url = f"{project_name}/steps/bdm-step/data/{quote(datapath)}?files-as-urls=true"
    if directories_as_dictionaries:
        url += "&directories-as-dictionaries=true"
    response = project_fixture.client.get(url)

    # THEN - a URL is located at the expected place
    response.raise_for_status()
    raw_content_url = response.json()

    for key in lookup:
        raw_content_url = raw_content_url[key]
    assert isinstance(raw_content_url, str)

    # AND - the url is prefixed as expected
    url_prefix = f"{settings.computed_external_api_url}/"
    assert raw_content_url.startswith(url_prefix)

    # WHEN - retrieving the content using the URL
    content_url = raw_content_url.replace(url_prefix, "", 1)
    response = project_fixture.client.get(content_url)

    # THEN - the content is as expected
    response.raise_for_status()
    assert response.text == expected_content


def test_get_data_with_substitution_does_not_affect_fields_that_are_not_entity_handles(
    project_fixture: ProjectFixture,
):
    # GIVEN - step with nested entity handles pointing at files with known content
    project_name = project_fixture.properties["name"]
    method_url = f"{project_name}/steps/bdm-step:store-sub-model"
    project_fixture.client.post(method_url).raise_for_status()

    # WHEN - getting the step with URLs substituted for entity handles
    url = f"{project_name}/steps/bdm-step/data/?files-as-urls=true"
    response = project_fixture.client.get(url)

    # THEN - the step data is returned as expected
    response.raise_for_status()
    step_data = response.json()
    sub = step_data["sub"]
    assert sub["i"] == 1
    innersub = sub["inner_sub"]
    assert innersub["s"] == "inner"


def test_get_data_with_substitution_does_not_substitute_urls_for_handles_referring_to_directories(
    project_fixture: ProjectFixture,
):
    # GIVEN - step with a directory entity handle
    project_name = project_fixture.properties["name"]
    method_url = f"{project_name}/steps/bdm-step:store-directory-in-entity-handle"
    project_fixture.client.post(method_url).raise_for_status()

    # WHEN - getting the step with URLs substituted for entity handles
    url = f"{project_name}/steps/bdm-step/data/?files-as-urls=true"
    response = project_fixture.client.get(url)

    # THEN - the step data is returned as expected
    response.raise_for_status()
    step_data = response.json()
    raw_directory_handle = step_data["directory"]
    directory_handle = EntityHandle.model_validate(raw_directory_handle)
    assert directory_handle.is_blob is False


def test_get_data_without_substitution_does_not_substitute_urls_for_handles_inside_directories(
    project_fixture: ProjectFixture,
):
    # GIVEN - step with a directory entity handle
    project_name = project_fixture.properties["name"]
    method_url = f"{project_name}/steps/bdm-step:store-directory-in-entity-handle"
    project_fixture.client.post(method_url).raise_for_status()

    # WHEN - getting the step with directories as dictionaries
    url = f"{project_name}/steps/bdm-step/data/directory?directories-as-dictionaries=true"
    response = project_fixture.client.get(url)

    # THEN - the step data is returned as expected, entity handles are not substituted
    response.raise_for_status()
    step_data = response.json()
    raw_file_handle = step_data["subtop"]["leaf.txt"]
    file_handle = EntityHandle.model_validate(raw_file_handle)
    assert file_handle.is_blob


def test_get_data_does_substitute_url_for_handle_which_returns_404_when_initially_containing_no_entity(
    project_fixture: ProjectFixture,
    settings: Settings,
):
    # GIVEN - step with entity handle containing NO_ENTITY
    project_name = project_fixture.properties["name"]

    # WHEN - getting the data for the field with URLs substituted for entity handles
    url = f"{project_name}/steps/bdm-step/data/result?files-as-urls=true"
    response = project_fixture.client.get(url)

    # THEN - the result URL is a string value
    response.raise_for_status()
    raw_content_url = response.json()
    assert isinstance(raw_content_url, str)

    # AND - the url is prefixed as expected
    url_prefix = f"{settings.computed_external_api_url}/"
    assert raw_content_url.startswith(url_prefix)

    # WHEN - retrieving the content using the URL
    content_url = raw_content_url.replace(url_prefix, "", 1)
    response = project_fixture.client.get(content_url)

    # THEN - a 404 is returned as the entity handle contains NO_ENTITY
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # WHEN - populating the entity handle by executing the method
    method_url = f"{project_name}/steps/bdm-step:store-result"
    project_fixture.client.post(method_url).raise_for_status()

    # AND - retrieving the content using the URL
    response = project_fixture.client.get(content_url)

    # THEN - the content is as expected
    response.raise_for_status()
    assert response.text == "hello world!"
