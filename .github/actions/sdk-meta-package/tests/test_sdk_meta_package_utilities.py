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
from unittest.mock import Mock, patch

import sdk_meta_package_utilities as sdk_utils
import version_utilities


def test_update_pyproject_updates_dependencies_and_lock() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pyproject = root / "pyproject.toml"
        requirements = [
            f'"{package}>=1.0.0,<1.1.0"'
            for package in version_utilities.PACKAGES
            if package != "ansys-saf-desktop-installer"
        ]
        pyproject.write_text(
            f'[project]\nversion = "0.1.0"\ndependencies = [{", ".join(requirements)}]\n'
            '[project.optional-dependencies]\nall = ["ansys-saf-desktop-installer>=1.0.0,<1.1.0"]\n',
            encoding="utf-8",
        )
        latest = dict.fromkeys(version_utilities.PACKAGES, "1.0.0")
        latest["ansys-bdm-api"] = "0.6.1"
        latest["ansys-saf-desktop-installer"] = "1.0.1"
        with (
            patch.object(sdk_utils, "PYPROJECT_PATH", pyproject),
            patch.object(version_utilities, "PYPROJECT_PATH", pyproject),
            patch.object(sdk_utils, "get_latest_stable_versions", return_value=latest),
            patch.object(sdk_utils, "get_meta_package_version", return_value="0.2.0"),
            patch.object(sdk_utils, "generate_release_notes"),
            patch.object(sdk_utils, "run_uv_lock") as lock,
            patch.dict(os.environ, {}, clear=True),
        ):
            sdk_utils.update_pyproject(
                Mock(is_release_branch=False, version="0.1.0"),
                sdk_utils.UpdateType.AUTO,
            )

        content = pyproject.read_text(encoding="utf-8")
        assert 'version = "0.2.0"' in content
        assert "ansys-bdm-api==0.6.1" in content
        assert "ansys-saf-desktop-installer==1.0.1" in content
        lock.assert_called_once_with()


def test_update_pyproject_applies_strict_pinning_without_version_update() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pyproject = root / "pyproject.toml"
        requirements = [f'"{package}>=1.0.0,<1.1.0"' for package in version_utilities.PACKAGES]
        pyproject.write_text(
            f'[project]\nversion = "0.4.0"\ndependencies = [{", ".join(requirements)}]\n'
            "[project.optional-dependencies]\nall = []\n",
            encoding="utf-8",
        )
        latest = dict.fromkeys(version_utilities.PACKAGES, "1.0.0")
        with (
            patch.object(sdk_utils, "PYPROJECT_PATH", pyproject),
            patch.object(version_utilities, "PYPROJECT_PATH", pyproject),
            patch.object(sdk_utils, "get_latest_stable_versions", return_value=latest),
            patch.object(sdk_utils, "get_meta_package_version", return_value="0.4.0"),
            patch.object(sdk_utils, "generate_release_notes"),
            patch.object(sdk_utils, "run_uv_lock") as lock,
            patch.dict(os.environ, {}, clear=True),
        ):
            sdk_utils.update_pyproject(
                Mock(is_release_branch=False, version="0.4.0"),
                sdk_utils.UpdateType.AUTO,
            )

        content = pyproject.read_text(encoding="utf-8")
        assert 'version = "0.4.0"' in content
        assert "ansys-bdm-api==1.0.0" in content
        assert ">=" not in content
        lock.assert_called_once_with()


def test_run_uv_lock() -> None:
    with patch.object(sdk_utils.subprocess, "run") as run:
        sdk_utils.run_uv_lock()
    run.assert_called_once_with(["uv", "lock"], check=True, cwd=sdk_utils.PYPROJECT_PATH.parent)


def test_update_pyproject_writes_changed_true_for_pinning_only_change() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pyproject = root / "pyproject.toml"
        requirements = [f'"{package}>=1.0.0,<1.1.0"' for package in version_utilities.PACKAGES]
        pyproject.write_text(
            f'[project]\nversion = "0.4.0"\ndependencies = [{", ".join(requirements)}]\n'
            "[project.optional-dependencies]\nall = []\n",
            encoding="utf-8",
        )
        latest = dict.fromkeys(version_utilities.PACKAGES, "1.0.0")
        outputs: dict[str, str] = {}
        with (
            patch.object(sdk_utils, "PYPROJECT_PATH", pyproject),
            patch.object(version_utilities, "PYPROJECT_PATH", pyproject),
            patch.object(sdk_utils, "get_latest_stable_versions", return_value=latest),
            patch.object(sdk_utils, "get_meta_package_version", return_value="0.4.0"),
            patch.object(sdk_utils, "generate_release_notes"),
            patch.object(sdk_utils, "run_uv_lock"),
            patch.object(sdk_utils, "write_github_output", side_effect=outputs.__setitem__),
            patch.dict(os.environ, {}, clear=True),
        ):
            sdk_utils.update_pyproject(
                Mock(is_release_branch=False, version="0.4.0"),
                sdk_utils.UpdateType.AUTO,
            )

        assert outputs["update_type"] == "no_update"
        assert outputs["changed"] == "true"


def test_update_pyproject_writes_changed_false_when_nothing_changes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pyproject = root / "pyproject.toml"
        requirements = [f'"{package}==1.0.0"' for package in version_utilities.PACKAGES]
        pyproject.write_text(
            f'[project]\nversion = "0.4.0"\ndependencies = [{", ".join(requirements)}]\n'
            "[project.optional-dependencies]\nall = []\n",
            encoding="utf-8",
        )
        latest = dict.fromkeys(version_utilities.PACKAGES, "1.0.0")
        outputs: dict[str, str] = {}
        with (
            patch.object(sdk_utils, "PYPROJECT_PATH", pyproject),
            patch.object(version_utilities, "PYPROJECT_PATH", pyproject),
            patch.object(sdk_utils, "get_latest_stable_versions", return_value=latest),
            patch.object(sdk_utils, "get_meta_package_version", return_value="0.4.0"),
            patch.object(sdk_utils, "generate_release_notes"),
            patch.object(sdk_utils, "run_uv_lock") as lock,
            patch.object(sdk_utils, "write_github_output", side_effect=outputs.__setitem__),
            patch.dict(os.environ, {}, clear=True),
        ):
            sdk_utils.update_pyproject(
                Mock(is_release_branch=False, version="0.4.0"),
                sdk_utils.UpdateType.AUTO,
            )

        assert outputs["update_type"] == "no_update"
        assert outputs["changed"] == "false"
        lock.assert_not_called()
