# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
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

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import branch
import pytest


def test_branch_parses_release_branch() -> None:
    environment = {
        "GITHUB_REF_NAME": "release/v1.2.3/saf-sdk",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "IS_FOR_PYPI_RELEASE": "true",
    }
    with patch.dict(os.environ, environment, clear=True):
        result = branch.Branch()

    assert result.is_release_branch is True
    assert result.version == "1.2.3"


def test_branch_reads_version_from_pyproject_for_non_release_branch() -> None:
    environment = {
        "GITHUB_REF_NAME": "main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "IS_FOR_PYPI_RELEASE": "true",
    }
    with tempfile.TemporaryDirectory() as directory:
        pyproject_path = Path(directory) / "pyproject.toml"
        pyproject_path.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(branch, "PYPROJECT_PATH", pyproject_path),
        ):
            result = branch.Branch()

    assert result.is_release_branch is False
    assert result.version == "1.2.3"


def test_branch_rejects_release_branch_outside_workflow_dispatch() -> None:
    environment = {
        "GITHUB_REF_NAME": "release/v1.2.3/saf-sdk",
        "GITHUB_EVENT_NAME": "push",
        "IS_FOR_PYPI_RELEASE": "false",
    }
    with (
        patch.dict(os.environ, environment, clear=True),
        pytest.raises(
            ValueError,
            match="^Release branch is only allowed on workflow dispatch, but got push$",
        ),
    ):
        branch.Branch()


def test_branch_rejects_pypi_release_from_non_release_branch() -> None:
    environment = {
        "GITHUB_REF_NAME": "feature/update-sdk",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "IS_FOR_PYPI_RELEASE": "true",
    }
    with (
        patch.dict(os.environ, environment, clear=True),
        pytest.raises(
            ValueError,
            match=r"^PyPI release is only allowed on main or release branches\.$",
        ),
    ):
        branch.Branch()


def test_branch_properties_are_read_only() -> None:
    environment = {
        "GITHUB_REF_NAME": "release/v1.2.3/saf-sdk",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "IS_FOR_PYPI_RELEASE": "false",
    }
    with patch.dict(os.environ, environment, clear=True):
        result = branch.Branch()

    with pytest.raises(AttributeError):
        result.is_release_branch = False
    with pytest.raises(AttributeError):
        result.version = "2.0.0"
