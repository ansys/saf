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

import pytest
import requests
import version_utilities


def test_extract_package_name() -> None:
    assert version_utilities.extract_package_name("ansys_saf_glow_engine[dash]>=2.2.0") == "ansys_saf_glow_engine"
    assert version_utilities.extract_package_name("ansys-saf-desktop-installer") == "ansys-saf-desktop-installer"

    with pytest.raises(ValueError, match="^Unsupported requirement format: >=2.2.0$"):
        version_utilities.extract_package_name(">=2.2.0")


def test_extract_lower_bound() -> None:
    assert version_utilities.extract_lower_bound("ansys-saf-glow-engine>=2.2.0,<2.3.0") == "2.2.0"
    assert version_utilities.extract_lower_bound("ansys-saf-glow-engine==2.2.0") == "2.2.0"

    with pytest.raises(
        ValueError,
        match="^Unsupported requirement format: ansys-saf-glow-engine<2.3.0$",
    ):
        version_utilities.extract_lower_bound("ansys-saf-glow-engine<2.3.0")


def test_get_current_dependency_versions() -> None:
    with tempfile.TemporaryDirectory() as directory:
        pyproject = Path(directory) / "pyproject.toml"
        pyproject.write_text(
            '[project]\ndependencies = ["ansys-bdm-api>=0.5.0,<0.6.0", "requests>=2.0.0"]\n'
            '[project.optional-dependencies]\nall = ["ansys-saf-desktop-installer[all]>=0.13.0,<0.14.0"]\n',
            encoding="utf-8",
        )
        with patch.object(version_utilities, "PYPROJECT_PATH", pyproject):
            assert version_utilities.get_current_dependency_versions() == {
                "ansys-bdm-api": "0.5.0",
                "ansys-saf-desktop-installer": "0.13.0",
            }


def test_determine_update_type() -> None:
    current = {"package": "1.0.0"}
    assert (
        version_utilities.determine_update_type(version_utilities.UpdateType.AUTO, current, {"package": "1.0.0"})
        is version_utilities.UpdateType.NO_UPDATE
    )
    assert (
        version_utilities.determine_update_type(version_utilities.UpdateType.AUTO, current, {"package": "1.0.1"})
        is version_utilities.UpdateType.PATCH
    )
    assert (
        version_utilities.determine_update_type(version_utilities.UpdateType.AUTO, current, {"package": "1.1.0"})
        is version_utilities.UpdateType.MINOR
    )
    assert (
        version_utilities.determine_update_type(version_utilities.UpdateType.AUTO, current, {"package": "2.0.0"})
        is version_utilities.UpdateType.MAJOR
    )
    assert (
        version_utilities.determine_update_type(
            version_utilities.UpdateType.AUTO,
            {"minor": "1.0.0", "major": "1.0.0"},
            {"minor": "1.1.0", "major": "2.0.0"},
        )
        is version_utilities.UpdateType.MAJOR
    )


def test_bump_version() -> None:
    assert version_utilities.bump_version("1.2.3", version_utilities.UpdateType.PATCH) == "1.2.4"
    assert version_utilities.bump_version("1.2.3", version_utilities.UpdateType.MINOR) == "1.3.0"
    assert version_utilities.bump_version("1.2.3", version_utilities.UpdateType.MAJOR) == "2.0.0"
    assert version_utilities.bump_version("1.2.3", version_utilities.UpdateType.NO_UPDATE) == "1.2.3"


@pytest.mark.parametrize(("status_code", "expected"), [(200, True), (404, False)])
def test_release_branch_exists(status_code: int, expected: bool) -> None:
    response = Mock(status_code=status_code)
    environment = {"GITHUB_REPOSITORY": "ansys/saf", "GITHUB_TOKEN": "token"}
    with (
        patch.dict(os.environ, environment, clear=True),
        patch.object(version_utilities.requests, "get", return_value=response) as get,
    ):
        assert version_utilities.release_branch_exists("1.2.3") is expected

    get.assert_called_once_with(
        "https://api.github.com/repos/ansys/saf/branches/release/v1.2.3/saf-sdk",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer token",
        },
        timeout=10,
    )


def test_release_branch_exists_propagates_github_api_errors() -> None:
    response = Mock(status_code=500)
    response.raise_for_status.side_effect = requests.HTTPError("GitHub API failure")
    environment = {"GITHUB_REPOSITORY": "ansys/saf"}
    with (
        patch.dict(os.environ, environment, clear=True),
        patch.object(version_utilities.requests, "get", return_value=response),
        pytest.raises(requests.HTTPError),
    ):
        version_utilities.release_branch_exists("1.2.3")

    response.raise_for_status.assert_called_once_with()


@pytest.mark.parametrize(("releases", "expected"), [({"1.2.3": []}, True), ({}, False)])
def test_meta_package_release_exists(releases: dict[str, list[object]], expected: bool) -> None:
    response = Mock()
    response.json.return_value = {"releases": releases}
    with patch.object(version_utilities.requests, "get", return_value=response) as get:
        assert version_utilities.meta_package_release_exists("1.2.3") is expected

    get.assert_called_once_with("https://pypi.org/pypi/ansys-saf-sdk/json", timeout=10)
    response.raise_for_status.assert_called_once_with()


def test_meta_package_release_exists_returns_false_when_package_is_missing() -> None:
    response = Mock(status_code=404)
    with patch.object(version_utilities.requests, "get", return_value=response) as get:
        assert version_utilities.meta_package_release_exists("1.2.3") is False

    get.assert_called_once_with("https://pypi.org/pypi/ansys-saf-sdk/json", timeout=10)
    response.raise_for_status.assert_not_called()


def test_get_latest_stable_version_filters_releases() -> None:
    response = Mock()
    response.json.return_value = {
        "releases": {
            "1.0.0": [{"yanked": False}],
            "1.1.0rc1": [{"yanked": False}],
            "1.2.0": [{"yanked": True}],
            "1.1.0": [{"yanked": False}],
            "invalid": [{"yanked": False}],
        },
    }
    with patch.object(version_utilities.requests, "get", return_value=response) as get:
        assert version_utilities.get_latest_stable_version("example") == "1.1.0"
    get.assert_called_once_with("https://pypi.org/pypi/example/json", timeout=10)
    response.raise_for_status.assert_called_once_with()


def test_get_latest_stable_versions() -> None:
    with patch.object(version_utilities, "get_latest_stable_version", side_effect=["1.0.0", "2.0.0"]) as get:
        assert version_utilities.get_latest_stable_versions(["first", "second"]) == {
            "first": "1.0.0",
            "second": "2.0.0",
        }
    assert get.call_args_list[0].args == ("first",)
    assert get.call_args_list[1].args == ("second",)


def test_get_latest_stable_versions_uses_selected_versions() -> None:
    with (
        patch.dict(
            os.environ,
            {"USER_SELECTED_BDM_API_VERSION": "0.6.1"},
            clear=True,
        ),
        patch.object(
            version_utilities,
            "get_latest_stable_version",
            return_value="1.0.0",
        ) as get,
    ):
        assert version_utilities.get_latest_stable_versions(["ansys-bdm-api", "ansys-saf-desktop-orchestrator"]) == {
            "ansys-bdm-api": "0.6.1",
            "ansys-saf-desktop-orchestrator": "1.0.0",
        }

    get.assert_called_once_with("ansys-saf-desktop-orchestrator")


def test_build_updated_requirement_uses_selected_version_for_optional_dependency() -> None:
    with patch.dict(
        os.environ,
        {"USER_SELECTED_ANSYS_SAF_DESKTOP_INSTALLER_VERSION": "1.0.1"},
        clear=True,
    ):
        versions = version_utilities.get_latest_stable_versions(["ansys-saf-desktop-installer"])

    assert (
        version_utilities.build_updated_requirement("ansys-saf-desktop-installer[all]>=1.0.0,<1.1.0", versions)
        == "ansys-saf-desktop-installer[all]==1.0.1"
    )


def test_get_meta_package_version_when_not_published() -> None:
    response = Mock()
    response.status_code = 404
    response.raise_for_status.side_effect = version_utilities.requests.HTTPError(response=response)
    with patch.object(version_utilities.requests, "get", return_value=response):
        assert (
            version_utilities.get_meta_package_version(version_utilities.UpdateType.MINOR)
            == version_utilities.INITIAL_META_PACKAGE_VERSION
        )


def test_get_dependency_pinning_rejects_invalid_value() -> None:
    with (
        patch.dict(os.environ, {version_utilities.DEPENDENCY_PINNING_ENV_VAR: "invalid"}),
        pytest.raises(
            ValueError,
            match="^SAF_SDK_DEPENDENCY_PINNING must be one of: range, strict$",
        ),
    ):
        version_utilities.get_dependency_pinning()


def test_build_updated_requirement() -> None:
    versions = {"ansys-saf-glow-engine": "2.4.1"}
    assert (
        version_utilities.build_updated_requirement("ansys-saf-glow-engine[dash]>=2.2.0,<2.3.0", versions)
        == "ansys-saf-glow-engine[dash]==2.4.1"
    )
    assert version_utilities.build_updated_requirement("requests>=2.0.0", versions) == "requests>=2.0.0"

    with patch.dict(os.environ, {version_utilities.DEPENDENCY_PINNING_ENV_VAR: "range"}):
        assert (
            version_utilities.build_updated_requirement("ansys-saf-glow-engine[dash]>=2.2.0,<2.3.0", versions)
            == "ansys-saf-glow-engine[dash]>=2.4.1,<2.5.0"
        )


@pytest.mark.parametrize("update_type", ["major", "minor", "patch"])
def test_validate_user_selected_update_type_allows_non_release_branch(
    update_type: str,
) -> None:
    branch = Mock(is_release_branch=False, version="1.2.3")
    with (
        patch.dict(os.environ, {"USER_SELECTED_UPDATE_TYPE": update_type}),
        patch.object(version_utilities, "bump_version", return_value="1.2.3") as bump_version,
        patch.object(version_utilities, "release_branch_exists", return_value=False) as release_branch_exists,
        patch.object(
            version_utilities,
            "meta_package_release_exists",
            return_value=False,
        ) as meta_package_release_exists,
    ):
        assert version_utilities.validate_user_selected_update_type(branch) is version_utilities.UpdateType(update_type)

    bump_version.assert_called_once_with("1.2.3", version_utilities.UpdateType(update_type))
    release_branch_exists.assert_called_once_with("1.2.3")
    meta_package_release_exists.assert_called_once_with("1.2.3")


def test_validate_user_selected_update_type_allows_auto_without_existence_check_on_non_release_branch() -> None:
    branch = Mock(is_release_branch=False, version="1.2.3")
    with (
        patch.dict(os.environ, {"USER_SELECTED_UPDATE_TYPE": "auto"}),
        patch.object(version_utilities, "release_branch_exists") as release_branch_exists,
        patch.object(version_utilities, "meta_package_release_exists") as meta_package_release_exists,
    ):
        assert version_utilities.validate_user_selected_update_type(branch) is version_utilities.UpdateType.AUTO

    release_branch_exists.assert_not_called()
    meta_package_release_exists.assert_not_called()


def test_validate_user_selected_update_type_checks_auto_as_patch_on_release_branch() -> None:
    branch = Mock(is_release_branch=True, version="1.2.3")
    with (
        patch.dict(os.environ, {"USER_SELECTED_UPDATE_TYPE": "auto"}),
        patch.object(version_utilities, "release_branch_exists", return_value=False) as release_branch_exists,
        patch.object(
            version_utilities,
            "meta_package_release_exists",
            return_value=False,
        ) as meta_package_release_exists,
    ):
        assert version_utilities.validate_user_selected_update_type(branch) is version_utilities.UpdateType.AUTO

    release_branch_exists.assert_called_once_with("1.2.4")
    meta_package_release_exists.assert_called_once_with("1.2.4")


def test_validate_user_selected_update_type_allows_release_branch() -> None:
    branch = Mock(is_release_branch=True, version="1.2.3")
    with (
        patch.dict(os.environ, {"USER_SELECTED_UPDATE_TYPE": "patch"}),
        patch.object(version_utilities, "release_branch_exists", return_value=False) as release_branch_exists,
        patch.object(
            version_utilities,
            "meta_package_release_exists",
            return_value=False,
        ) as meta_package_release_exists,
    ):
        assert version_utilities.validate_user_selected_update_type(branch) is version_utilities.UpdateType.PATCH

    release_branch_exists.assert_called_once_with("1.2.4")
    meta_package_release_exists.assert_called_once_with("1.2.4")


@pytest.mark.parametrize("update_type", ["major", "minor"])
def test_validate_user_selected_update_type_rejects_non_patch_release_update_types(
    update_type: str,
) -> None:
    branch = Mock(is_release_branch=True, version="1.2.3")
    with (
        patch.dict(os.environ, {"USER_SELECTED_UPDATE_TYPE": update_type}),
        pytest.raises(
            ValueError,
            match=r"Valid values are \['auto', 'patch'\]",
        ),
    ):
        version_utilities.validate_user_selected_update_type(branch)


@pytest.mark.parametrize(("branch_exists", "pypi_release_exists"), [(True, False), (False, True)])
def test_validate_user_selected_update_type_rejects_existing_next_version(
    branch_exists: bool,
    pypi_release_exists: bool,
) -> None:
    branch = Mock(is_release_branch=True, version="1.2.3")
    with (
        patch.dict(os.environ, {"USER_SELECTED_UPDATE_TYPE": "patch"}),
        patch.object(version_utilities, "release_branch_exists", return_value=branch_exists),
        patch.object(
            version_utilities,
            "meta_package_release_exists",
            return_value=pypi_release_exists,
        ),
        pytest.raises(
            ValueError,
            match="^The next version 1.2.4 already exists as a branch or PyPI release\\.$",
        ),
    ):
        version_utilities.validate_user_selected_update_type(branch)
