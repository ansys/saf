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

import httpx2
import pytest

from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solutions.bdm_solution import BdmSolution

pytestmark = pytest.mark.parametrize("solution_type", [BdmSolution], indirect=True)


@pytest.mark.parametrize(
    ("datapath", "lookup", "method", "expected_content", "directories_as_dictionaries"),
    [
        ("", ["directory", "subtop", "leaf.txt"], "store_directory_in_entity_handle", "hello world!", True),
        ("directory", ["subtop", "leaf.txt"], "store_directory_in_entity_handle", "hello world!", True),
        (
            "my_entities/a\\b a\\\\b a\\\\/b",  # keys are "ab a\b a\" then "b"
            [],
            "store_handle_in_nested_dictionary_with_key_containing_characters_requiring_backslash_escape",
            "stored nested with back slash escaped key",
            False,
        ),
        (
            "dict_handles/a\\\\\\/b",  # key is a\/b
            [],
            "store_handle_in_dictionary_with_key_containing_characters_requiring_backslash_escape",
            "stored with back slash escaped key",
            False,
        ),
        (
            "dict_handles/ ()+[]{}%*<>?-_",
            [],
            "store_handle_in_dictionary_with_key_containing_characters_requiring_url_escape",
            "stored with escaped key",
            False,
        ),
        ("result", [], "store_result", "hello world!", False),
        ("list_handles/0", [], "store_list_handles", "list_handles.txt", False),
        ("dict_handles/dict_handle", [], "store_dict_handles", "dict_handles.txt", False),
        (
            "dict_handles/a\\/b\\/c",  # key is "a/b/c"
            [],
            "store_handle_in_dictionary_with_key_containing_multiple_forward_slashes",
            "stored with complex key",
            False,
        ),
        ("directory/subtop/leaf.txt", [], "store_directory_in_entity_handle", "hello world!", False),
        ("sub/sub_handle", [], "store_sub_model", "sub", False),
        ("sub/inner_sub/inner_sub_handle", [], "store_sub_model", "inner_sub", False),
        (
            "my_entities/root_file.txt",
            [],
            "manually_create_entities_dict",
            "This is a file in the root directory",
            False,
        ),
        ("my_entities/subdir1/level1_file.json", [], "manually_create_entities_dict", '{"key": "value"}', False),
        ("", ["result"], "store_result", "hello world!", False),
        ("", ["list_handles", 0], "store_list_handles", "list_handles.txt", False),
        ("", ["dict_handles", "dict_handle"], "store_dict_handles", "dict_handles.txt", False),
        ("", ["sub", "sub_handle"], "store_sub_model", "sub", False),
        ("", ["sub", "inner_sub", "inner_sub_handle"], "store_sub_model", "inner_sub", False),
        (
            "",
            ["my_entities", "root_file.txt"],
            "manually_create_entities_dict",
            "This is a file in the root directory",
            False,
        ),
        (
            "",
            ["my_entities", "subdir1", "level1_file.json"],
            "manually_create_entities_dict",
            '{"key": "value"}',
            False,
        ),
        (
            "",
            ["dict_handles", "a/b/c"],
            "store_handle_in_dictionary_with_key_containing_multiple_forward_slashes",
            "stored with complex key",
            False,
        ),
        ("sub", ["sub_handle"], "store_sub_model", "sub", False),
        ("sub", ["inner_sub", "inner_sub_handle"], "store_sub_model", "inner_sub", False),
        (
            "",
            ["dict_handles", " ()+[]{}%*<>?-_"],
            "store_handle_in_dictionary_with_key_containing_characters_requiring_url_escape",
            "stored with escaped key",
            False,
        ),
        (
            "",
            ["my_entities", "ab a\\b a\\", "b"],
            "store_handle_in_nested_dictionary_with_key_containing_characters_requiring_backslash_escape",
            "stored nested with back slash escaped key",
            False,
        ),
        (
            "",
            ["dict_handles", "a\\/b"],
            "store_handle_in_dictionary_with_key_containing_characters_requiring_backslash_escape",
            "stored with back slash escaped key",
            False,
        ),
    ],
)
def test_get_data_with_url_substitution(
    function_project: ProjectFixture[BdmSolution],
    method: str,
    datapath: str,
    lookup: list[str],
    expected_content: str,
    directories_as_dictionaries: bool,
):
    """
    Test that the get_data method returns the expected data given various
    values for its parameters when substitute_file_handles_with_urls is True.
    """
    # GIVEN _ step with nested entity handles pointing at files with known content
    project = function_project.project
    step = project.steps.bdm_step
    getattr(step, method)()

    # WHEN _ getting the data with URLs substituted for entity handles
    content_url = step.get_data(
        datapath,
        substitute_file_handles_with_urls=True,
        substitute_directory_handles_as_dictionaries=directories_as_dictionaries,
    )

    # THEN _ a URL is located at the expected place
    for key in lookup:
        content_url = content_url[key]
    assert isinstance(content_url, str)

    # WHEN _ retrieving the content using the URL
    response = httpx2.get(content_url, timeout=90)

    # THEN _ the content is as expected
    response.raise_for_status()
    assert response.text == expected_content
