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

"""Tests for validate_path_component function."""

import pytest

from ansys.bdm.api.recursive_dictionary import validate_path_component


@pytest.mark.parametrize(
    "valid_name",
    [
        "file.txt",
        "myfile",
        "my-file",
        "my_file",
        "file123",
        "file.with.dots.txt",
        "file with spaces",
        " file_with_leading_space",
    ],
)
def test_valid_path_components(valid_name: str):
    """Test that valid path components pass validation."""
    validate_path_component(valid_name)


@pytest.mark.parametrize(
    ("invalid_name", "expected_message"),
    [
        ("", "Path component cannot be empty"),
        ("   ", "Path component cannot be empty"),
        (".", "Path component cannot be '.'"),
        ("..", "Path component cannot be '..'"),
        ("filename.", "cannot end with a dot or space"),
        ("filename ", "cannot end with a dot or space"),
        ("file<name", "contains invalid characters"),
        ("file>name", "contains invalid characters"),
        ("file:name", "contains invalid characters"),
        ('file"name', "contains invalid characters"),
        ("file/name", "contains invalid characters"),
        ("file\\name", "contains invalid characters"),
        ("file|name", "contains invalid characters"),
        ("file?name", "contains invalid characters"),
        ("file*name", "contains invalid characters"),
        ("file\x00name", "contains invalid characters"),  # null character
        ("file\x1fname", "contains invalid characters"),  # control character
    ],
)
def test_invalid_path_components(invalid_name: str, expected_message: str):
    """Test that invalid path components raises ValueError."""
    with pytest.raises(ValueError, match=expected_message):
        validate_path_component(invalid_name)
