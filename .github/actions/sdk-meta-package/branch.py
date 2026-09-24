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

# /// script
# dependencies = [
#   "tomlkit==0.15.1",
# ]
# ///

import os
import re

from constants import PYPROJECT_PATH
import tomlkit


class Branch:
    """A validated SDK meta-package branch, indicating whether it is a release branch and its version."""

    def _get_meta_package_version_from_pyproject(self) -> str:
        """Read the current meta-package version from ``pyproject.toml``.

        Returns
        -------
        str
            The version declared in the project metadata.
        """
        document = tomlkit.parse(PYPROJECT_PATH.read_text(encoding="utf-8"))
        project = document["project"]
        return project["version"]

    def __init__(self) -> None:
        """Initialize branch information from GitHub Actions environment variables.

        Raises
        ------
        ValueError
            If a release branch is used outside a workflow dispatch event, or
            if a PyPI release is requested from a branch other than ``main``.
        """
        branch_name = os.environ.get("GITHUB_REF_NAME", "local")
        event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
        is_for_pypi_release = os.environ.get("IS_FOR_PYPI_RELEASE", "false") == "true"

        match = re.fullmatch(r"release/v(?P<version>\d+\.\d+\.\d+)/saf-sdk", branch_name)
        if match:
            if event_name != "workflow_dispatch":
                raise ValueError(f"Release branch is only allowed on workflow dispatch, but got {event_name}")
            is_release_branch = True
            version = match["version"]
        else:
            if is_for_pypi_release and branch_name != "main":
                raise ValueError("PyPI release is only allowed on main or release branches.")
            is_release_branch = False
            version = self._get_meta_package_version_from_pyproject()
        self._is_release_branch = is_release_branch
        self._version = version

    @property
    def is_release_branch(self) -> bool:
        """Return whether the current branch is an SDK release branch."""
        return self._is_release_branch

    @property
    def version(self) -> str:
        """Return the SDK version associated with the current branch."""
        return self._version
