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

from pathlib import Path
import re

import httpx2
import pytest

from ansys.bdm.api import InvalidContextError
from ansys.saf.glow._server.exceptions import INTERNAL_ERROR_MESSAGE
from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DebugConfiguration,
    DefaultDebug,
    EnvVarDebug,
    GlowBaseProcess,
    ProjectFixture,
)
from tests.mocks.solution_with_method_assets.bdm_method_assets import SolutionBdmAssets, StepWithAssets

pytestmark = pytest.mark.parametrize("solution_type", [SolutionBdmAssets], indirect=True)


@pytest.fixture
def debug_mode(
    session_glow: GlowBaseProcess[SolutionBdmAssets],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param)


@pytest.fixture
def assets_step(function_project: ProjectFixture[SolutionBdmAssets]) -> StepWithAssets:
    return function_project.project.steps.step_with_assets


@pytest.mark.parametrize(
    ("asset_path", "expected_content"),
    [
        ("asset_always_decrypted.txt", "always decrypted"),
        ("dir/asset_decrypted.txt", "always decrypted"),
        ("decrypted_dir/decrypted_asset.txt", "decrypted content"),
    ],
)
def test_get_text(assets_step: StepWithAssets, asset_path: str, expected_content: str):
    """
    Test that get_text can be used to retrieve the asset files.
    """
    assert assets_step.get_text_asset(asset_path=asset_path).rstrip() == expected_content


@pytest.mark.parametrize("debug_mode", [EnvVarDebug, DefaultDebug], indirect=True)
def test_get_text_of_encrypted_file_without_transaction_utilities(
    assets_step: StepWithAssets,
    debug_mode: DebugConfiguration,
):
    """
    Test that get_text on an encrypted asset file raises an error when transaction utilities is not present.
    """
    expected_error_message = (
        INTERNAL_ERROR_MESSAGE
        if isinstance(debug_mode, DefaultDebug)
        else re.escape("No module named 'ansys.translation_utilities'") + ".*"
    )
    with pytest.raises(InternalSolutionException, match=expected_error_message):
        assets_step.get_text_asset(asset_path="dir/asset_encrypted.txt")


@pytest.mark.parametrize(
    ("asset_path", "expected_content"),
    [
        ("asset_always_decrypted.txt", "always decrypted"),
        ("dir/asset_decrypted.txt", "always decrypted"),
        ("decrypted_dir/decrypted_asset.txt", "decrypted content"),
    ],
)
def test_read_text_from_get_cached(assets_step: StepWithAssets, asset_path: str, expected_content: str):
    """
    Test that get_cached() can be used to read text from the asset files.
    """
    assert assets_step.read_text_from_cached(asset_path=asset_path).rstrip() == expected_content


@pytest.mark.parametrize(
    ("asset_dir", "child_name", "expected_content"),
    [
        ("decrypted_dir", "decrypted_asset.txt", "decrypted content"),
    ],
)
def test_read_text_from_get_cached_dir(
    assets_step: StepWithAssets,
    asset_dir: str,
    child_name: str,
    expected_content: str,
):
    """
    Test that get_cached() used on asset directory can be used to read text from children asset files.
    """
    assert (
        assets_step.read_text_from_cached_dir(asset_dir=asset_dir, child_name=child_name).rstrip() == expected_content
    )


@pytest.mark.parametrize(
    ("asset_path", "expected_content"),
    [
        ("asset_always_decrypted.txt", b"always decrypted"),
        ("dir/asset_decrypted.txt", b"always decrypted"),
        ("decrypted_dir/decrypted_asset.txt", b"decrypted content"),
    ],
)
def test_get_bytes(assets_step: StepWithAssets, asset_path: str, expected_content: bytes):
    """
    Test that get_bytes() can be used to read bytes from the asset files.
    """
    assert assets_step.get_bytes_asset(asset_path=asset_path).rstrip() == expected_content


@pytest.mark.parametrize(
    ("asset_path", "expected_content"),
    [
        ("asset_always_decrypted.txt", b"always decrypted"),
        ("dir/asset_decrypted.txt", b"always decrypted"),
        ("decrypted_dir/decrypted_asset.txt", b"decrypted content"),
    ],
)
def test_get_stream(assets_step: StepWithAssets, asset_path: str, expected_content: bytes):
    """
    Test that get_stream() can be used to read the content from the asset files.
    """
    assert assets_step.get_stream_asset(asset_path=asset_path).rstrip() == expected_content


@pytest.mark.parametrize(
    ("asset_path", "expected_content"),
    [
        ("asset_always_decrypted.txt", "always decrypted"),
        ("dir/asset_decrypted.txt", "always decrypted"),
        ("decrypted_dir/decrypted_asset.txt", "decrypted content"),
    ],
)
def test_get_copy(assets_step: StepWithAssets, asset_path: str, expected_content: bytes, tmp_path: Path):
    """
    Test that get_copy() can be used to copy the content from the asset files to a given destination.
    """
    destination = tmp_path / asset_path
    assets_step.get_copy_asset(asset_path=asset_path, destination=destination.as_posix())
    assert destination.exists()
    assert destination.read_text().rstrip() == expected_content


@pytest.mark.parametrize(
    ("asset_path", "expected_files"),
    [
        ("decrypted_dir", ["decrypted_asset.txt"]),
    ],
)
def test_get_copy_dir(assets_step: StepWithAssets, asset_path: str, expected_files: list[str], tmp_path: Path):
    """
    Test that get_copy() can be used to copy the asset directory to a given destination.
    """
    destination = tmp_path / asset_path
    assets_step.get_copy_asset(asset_path=asset_path, destination=destination.as_posix())
    assert destination.exists()
    assert sorted([path.name for path in destination.rglob("*")]) == sorted(expected_files)


@pytest.mark.parametrize(
    ("asset_dir", "child_name"),
    [
        ("dir", "asset_decrypted.txt"),
        ("dir", "asset_encrypted.txt"),
        ("decrypted_dir", "decrypted_asset.txt"),
    ],
)
def test_get_child(assets_step: StepWithAssets, asset_dir: str, child_name: str):
    """
    Test that get_child() can be used to get a child from an asset directory.
    """
    child_handle = assets_step.get_child_asset(asset_dir=asset_dir, child_name=child_name)
    assert child_handle.original_name == child_name


@pytest.mark.parametrize(
    ("asset_dir", "expected_files"),
    [
        ("dir", ["asset_decrypted.txt", "asset_encrypted.txt"]),
        ("decrypted_dir", ["decrypted_asset.txt"]),
    ],
)
def test_get_children(assets_step: StepWithAssets, asset_dir: str, expected_files: list[str]):
    """
    Test that get_children() can be used to list direct children from an asset directory.
    """
    child_handles = assets_step.get_children_asset(asset_dir=asset_dir)
    for handle in child_handles:
        assert handle.original_name in expected_files


@pytest.mark.parametrize(
    ("asset_path"),
    [
        ("dir/asset_decrypted.txt"),
        ("dir/asset_encrypted.txt"),
        ("decrypted_dir/decrypted_asset.txt"),
    ],
)
def test_get_parent(assets_step: StepWithAssets, asset_path: str):
    """
    Test that get_parent() can be used to get the parent from an asset file.
    """
    parent_handle = assets_step.get_parent_asset(asset_path=asset_path)
    assert parent_handle.original_name == asset_path.split("/")[0]  # type: ignore


@pytest.mark.parametrize(
    ("asset_path"),
    [
        ("dir"),
        ("decrypted_dir"),
        ("asset_always_decrypted.txt"),
        ("asset_encrypted.txt"),
    ],
)
def test_get_parent_root_assets(assets_step: StepWithAssets, asset_path: str):
    """
    Test that get_parent() on a root file or root folder returns None.
    """
    parent_handle = assets_step.get_parent_asset(asset_path=asset_path)
    assert parent_handle is None


def test_missing_asset(assets_step: StepWithAssets):
    """
    Test that get_entity_handle() on a missing file raises an error.
    """
    with pytest.raises(InternalSolutionException):
        assets_step.get_missing_asset()


def test_get_children_file_asset(assets_step: StepWithAssets):
    """
    Test that get_children() on an asset file raises an error.
    """
    with pytest.raises(InternalSolutionException):
        assets_step.get_children_asset(asset_dir="asset_always_decrypted.txt")


def test_get_asset_entity_access_from_client_raise_error(
    function_project: ProjectFixture[SolutionBdmAssets],
    assets_step: StepWithAssets,
):
    """
    Test that an asset entity handle cannot be resolved from the client.
    """
    handle = assets_step.get_asset_entity(asset_path="asset_always_decrypted.txt")
    with pytest.raises(
        InvalidContextError,
        match="The entity handle 'asset_always_decrypted.txt' cannot be resolved from this context.",
    ):
        function_project.project.storage_scope.get_text(handle)


def test_cannot_access_asset_entity_handle_from_data_repo_using_blobs_endpoint(
    assets_step: StepWithAssets,
):
    """
    Test that an asset entity handle cannot be resolved from the http blobs endpoint.
    """
    assets_step.store_asset_entity()
    entity_url = assets_step.get_entity_url("asset_entity")
    response = httpx2.get(entity_url)
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "The entity handle 'asset_always_decrypted.txt' cannot be resolved from this context."
    )


def test_python_module_assets_can_be_dynamically_imported_and_executed(assets_step: StepWithAssets):
    """
    Test that Python module assets can be dynamically imported and executed in a transaction method.
    """
    assert assets_step.run_python_code_from_asset(first_arg=1, second_arg=2) == 3
