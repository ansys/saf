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

from collections.abc import Generator
from pathlib import Path
import platform
import tempfile
from typing import Any
from unittest.mock import patch

import pytest
from starlette import status

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._server.exceptions import INTERNAL_ERROR_MESSAGE
from tests.conftest import MOCKS_DIR
import tests.mocks.solution_with_method_assets.bdm_method_assets as solution_assets
from tests.unit.routes.conftest import ProjectFixture

solution = solution_assets


@pytest.fixture
def method_tmpdir(tmp_path: Path) -> Generator[Path, None, None]:
    with patch.object(tempfile, "mkdtemp") as mock:
        method_dir = tmp_path / "method_dir"
        method_dir.mkdir()
        mock.return_value = str(method_dir)
        yield method_dir


@pytest.fixture
def asset_cache_dir(project_fixture: ProjectFixture) -> Path:
    return project_fixture.project_files_dir / ".asset_cache"


def run_method(project_fixture: ProjectFixture, method_name: str, body: Any | None = None) -> Any:
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/step-with-assets"
    method_url = f"{step_url}:{method_name}"
    response = project_fixture.client.post(method_url, json=body)
    return response.json()


def test_cached_asset_removed(project_fixture: ProjectFixture, asset_cache_dir: Path):
    assert not asset_cache_dir.exists()
    run_method(project_fixture, "get-cached-asset", {"asset_path": "dir"})
    assert len(list(asset_cache_dir.rglob("*"))) == 0


@pytest.mark.parametrize(
    ("asset_path", "content"),
    [
        ("asset_always_decrypted.txt", "always decrypted"),
        ("dir/asset_decrypted.txt", "always decrypted"),
    ],
)
def test_get_text(project_fixture: ProjectFixture, asset_path: str, content: str):
    response = run_method(project_fixture, "get-text-asset", {"asset_path": asset_path})
    assert response.rstrip() == content


@pytest.mark.usefixtures("settings")
@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (
            {"glow_debug": "True"},
            "No module named 'ansys.translation_utilities'",
        ),
        (
            {"glow_debug": None},
            "The solution encountered an internal error and was unable to complete the request",
        ),
    ],
    ids=["debug", "not-debug"],
    indirect=["settings", "settings"],
)
def test_errors_when_retrieving_encrypted_assets(project_fixture: ProjectFixture, settings: Settings, message: str):
    # GIVEN - method end point to retrieve an encrypted asset
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/step-with-assets"
    url = f"{step_url}:get-text-asset"

    # WHEN - invoking the end point
    response = project_fixture.client.post(url, json={"asset_path": "asset_encrypted.txt"})

    # THEN - an error is returned because the asset cannot be decrypted
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert message in response.json()["detail"]


@pytest.mark.parametrize(
    ("asset_path", "content"),
    [
        ("asset_always_decrypted.txt", "always decrypted"),
        ("dir/asset_decrypted.txt", "always decrypted"),
    ],
)
def test_get_bytes(project_fixture: ProjectFixture, asset_path: str, content: str):
    response = run_method(project_fixture, "get-bytes-asset", {"asset_path": asset_path})
    assert response.rstrip() == content


@pytest.mark.parametrize(
    ("asset_path", "content"),
    [
        ("asset_always_decrypted.txt", "always decrypted"),
        ("dir/asset_decrypted.txt", "always decrypted"),
    ],
)
def test_get_stream(project_fixture: ProjectFixture, asset_path: str, content: str):
    response = run_method(project_fixture, "get-stream-asset", {"asset_path": asset_path})
    assert response.rstrip() == content


@pytest.mark.parametrize(
    ("asset_name", "is_cached"),
    [
        ("asset_always_decrypted.txt", False),
        ("dir/asset_decrypted.txt", False),
    ],
)
def test_get_cached(
    project_fixture: ProjectFixture,
    asset_cache_dir: Path,
    asset_name: str,
    is_cached: bool,
):
    response = run_method(project_fixture, "get-cached-asset", {"asset_path": asset_name})
    asset_path = Path(response)
    if is_cached:
        assert asset_path.as_posix().startswith(asset_cache_dir.as_posix())
        assert asset_path.as_posix().endswith(asset_name)
        assert not asset_path.exists()  # file has been removed after transaction
    else:
        expected_path = MOCKS_DIR / "solution_with_method_assets" / "method_assets" / asset_name
        assert asset_path == expected_path


@pytest.mark.parametrize(
    ("asset_name", "is_cached", "expected_files"),
    [
        ("decrypted_dir", False, ["decrypted_asset.txt"]),
    ],
)
def test_get_cached_dir(
    project_fixture: ProjectFixture,
    asset_cache_dir: Path,
    asset_name: str,
    is_cached: bool,
    expected_files: list[str],
):
    filepaths = run_method(project_fixture, "get-cached-dir", {"asset_path": asset_name})
    if is_cached:
        assert len(expected_files) == 2
        for filepath in filepaths:
            assert filepath.startswith(asset_cache_dir.as_posix())
            assert Path(filepath).name in expected_files
    else:
        assert len(expected_files) == 1
        for filepath in filepaths:
            assert Path(filepath).name in expected_files
            assert Path(filepath) == (
                MOCKS_DIR / "solution_with_method_assets" / "method_assets" / "decrypted_dir" / "decrypted_asset.txt"
            )


@pytest.mark.parametrize(
    ("asset_path", "content"),
    [
        ("asset_always_decrypted.txt", "always decrypted"),
        ("dir/asset_decrypted.txt", "always decrypted"),
    ],
)
def test_get_copy(project_fixture: ProjectFixture, tmp_path: Path, asset_path: str, content: str):
    run_method(
        project_fixture,
        "get-copy-asset",
        {"asset_path": asset_path, "destination": (tmp_path / asset_path).as_posix()},
    )
    assert (tmp_path / asset_path).read_text().rstrip() == content


@pytest.mark.parametrize(
    ("asset_path", "expected_files"),
    [
        ("decrypted_dir", ["decrypted_asset.txt"]),
    ],
)
def test_get_copy_dir(project_fixture: ProjectFixture, tmp_path: Path, asset_path: str, expected_files: list[str]):
    run_method(
        project_fixture,
        "get-copy-asset",
        {"asset_path": asset_path, "destination": (tmp_path / asset_path).as_posix()},
    )
    assert {path.name for path in (tmp_path / asset_path).rglob("*")} == set(expected_files)


@pytest.mark.parametrize(
    ("asset_dir", "child_name"),
    [
        ("dir", "asset_decrypted.txt"),
        ("decrypted_dir", "decrypted_asset.txt"),
    ],
)
def test_get_child(project_fixture: ProjectFixture, asset_dir: str, child_name: str):
    handle = run_method(
        project_fixture,
        "get-child-asset",
        {"asset_dir": asset_dir, "child_name": child_name},
    )
    handle = EntityHandle.model_validate(handle)
    assert handle.original_name == child_name


@pytest.mark.parametrize(
    ("asset_dir", "expected_files"),
    [
        ("dir", ["asset_decrypted.txt", "asset_encrypted.txt"]),
        ("decrypted_dir", ["decrypted_asset.txt"]),
    ],
)
def test_get_children(project_fixture: ProjectFixture, asset_dir: str, expected_files: list[str]):
    handles = run_method(
        project_fixture,
        "get-children-asset",
        {"asset_dir": asset_dir},
    )
    assert len(handles) == len(expected_files)
    for handle in handles:
        handle = EntityHandle.model_validate(handle)
        assert handle.original_name in expected_files


@pytest.mark.parametrize(
    ("asset_path"),
    [
        ("dir/asset_decrypted.txt"),
        ("dir/asset_encrypted.txt"),
        ("decrypted_dir/decrypted_asset.txt"),
    ],
)
def test_get_parent(project_fixture: ProjectFixture, asset_path: str):
    handle = run_method(
        project_fixture,
        "get-parent-asset",
        {"asset_path": asset_path},
    )
    handle = EntityHandle.model_validate(handle)
    assert handle.original_name == asset_path.split("/")[0]


@pytest.mark.parametrize(
    ("asset_path"),
    [
        ("dir"),
        ("decrypted_dir"),
        ("asset_always_decrypted.txt"),
        ("asset_encrypted.txt"),
    ],
)
def test_get_parent_root_asset(project_fixture: ProjectFixture, asset_path: str):
    handle = run_method(
        project_fixture,
        "get-parent-asset",
        {"asset_path": asset_path},
    )
    assert handle is None


def test_cannot_access_asset_entity_handle_from_data_repo_using_blobs_endpoint(
    project_fixture: ProjectFixture,
):
    run_method(
        project_fixture,
        "store-asset-entity",
    )
    project_name = project_fixture.properties["name"]
    step_url = f"{project_name}/steps/step-with-assets"
    response = project_fixture.client.get(f"{step_url}/blobs/asset-entity")
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "The entity handle 'asset_always_decrypted.txt' cannot be resolved from this context."
    )


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_get_missing_asset(project_fixture: ProjectFixture, settings: Settings):
    response = run_method(project_fixture, "get-missing-asset")
    if settings.glow_debug:
        assert "'missing.txt' asset file not found" in response["detail"]
    else:
        assert INTERNAL_ERROR_MESSAGE in response["detail"]


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_get_children_file_asset(project_fixture: ProjectFixture, settings: Settings):
    response = run_method(
        project_fixture,
        "get-children-asset",
        {"asset_dir": "asset_always_decrypted.txt"},
    )
    if settings.glow_debug:
        if platform.system() == "Windows":
            assert "The directory name is invalid" in response["detail"]
        else:
            assert "Not a directory" in response["detail"]

    else:
        assert INTERNAL_ERROR_MESSAGE in response["detail"]


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_get_bytes_directory(project_fixture: ProjectFixture, settings: Settings):
    response = run_method(
        project_fixture,
        "get-bytes-asset",
        {"asset_path": "dir"},
    )
    if settings.glow_debug:
        assert "Cannot create bytes for directory" in response["detail"]
    else:
        assert INTERNAL_ERROR_MESSAGE in response["detail"]


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_get_text_directory(project_fixture: ProjectFixture, settings: Settings):
    response = run_method(
        project_fixture,
        "get-text-asset",
        {"asset_path": "dir"},
    )
    if settings.glow_debug:
        assert "Cannot create bytes for directory" in response["detail"]
    else:
        assert INTERNAL_ERROR_MESSAGE in response["detail"]


@pytest.mark.parametrize("settings", [{"glow_debug": "True"}, {}], ids=["debug", "no_debug"], indirect=["settings"])
def test_get_stream_directory(project_fixture: ProjectFixture, settings: Settings):
    response = run_method(
        project_fixture,
        "get-stream-asset",
        {"asset_path": "decrypted_dir"},
    )
    if settings.glow_debug:
        assert "Cannot create stream for directory" in response["detail"]
    else:
        assert INTERNAL_ERROR_MESSAGE in response["detail"]
