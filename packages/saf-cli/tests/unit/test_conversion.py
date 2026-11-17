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

from packaging.specifiers import SpecifierSet
import pytest

from ansys.saf.cli._utilities.conversion import namespace_to_pkg_name, poetry_constraint_to_pep440


@pytest.mark.parametrize(
    ("namespace", "expected_pkg_name"),
    [
        ("ansys.solutions", "ansys-solutions"),
        ("my_org.platform", "my-org-platform"),
        ("my_org.my_project.module", "my-org-my-project-module"),
    ],
)
def test_namespace_to_pkg_name(namespace: str, expected_pkg_name: str):
    assert namespace_to_pkg_name(namespace) == expected_pkg_name


@pytest.mark.parametrize(
    ("constraint", "allowed", "rejected"),
    [
        ("^1.2.3", ["1.2.3", "1.99"], ["1.2.2", "2.0"]),
        ("^0.2.3", ["0.2.3", "0.2.99"], ["0.2.2", "0.3"]),
        ("^0.0.3", ["0.0.3"], ["0.0.2", "0.0.4"]),
        ("^0.0", ["0.0", "0.0.99"], ["0.1"]),
        ("^0", ["0.0", "0.99"], ["1.0"]),
        ("^1!1.2.3", ["1!1.2.3", "1!1.99"], ["1.99", "1!2.0"]),
        ("~1", ["1.0", "1.99"], ["2.0"]),
        ("~1.2.3", ["1.2.3", "1.2.99"], ["1.2.2", "1.3"]),
        ("~2!1.2", ["2!1.2", "2!1.2.99"], ["1!1.2", "2!1.3"]),
        ("1.2.3", ["1.2.3"], ["1.2.2", "1.2.4"]),
        ("1.2.*", ["1.2", "1.2.99"], ["1.1", "1.3"]),
        (">=1.2,!=1.3,<2", ["1.2", "1.4"], ["1.1", "1.3", "2"]),
        ("*", ["0.0", "999"], []),
    ],
)
def test_poetry_constraint_preserves_version_bounds(constraint: str, allowed: list[str], rejected: list[str]):
    specifier = SpecifierSet(poetry_constraint_to_pep440(constraint))
    assert all(specifier.contains(version) for version in allowed)
    assert not any(specifier.contains(version) for version in rejected)


def test_poetry_union_constraint_is_not_silently_broadened():
    with pytest.raises(ValueError, match="Unsupported dependency version constraint"):
        poetry_constraint_to_pep440("^1.0 || ^3.0")
