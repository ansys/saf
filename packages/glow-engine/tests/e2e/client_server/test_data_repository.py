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

from collections.abc import Callable, Generator
import datetime
import logging
from pathlib import Path
import re
import shutil
import time
import uuid
import xml.etree.ElementTree as ET

import httpx2
import pytest

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.solution.end_to_end import (
    DataRepositoryConfiguration,
    DefaultDataRepoConfiguration,
    EnvVarDebug,
    FileSystemDataRepoConfiguration,
    GlowDesktopProcess,
    MinervaDataRepoConfiguration,
    ProjectFixture,
)
from tests.conftest import E2E_TESTS_DIR
from tests.mocks.solutions.data_repository import (
    DataRepositorySolution,
    DataRepositoryStep,
)

pytestmark = pytest.mark.parametrize("solution_type", [DataRepositorySolution], indirect=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@pytest.fixture(scope="class")
def temp_upload_root() -> str:
    return f"/Data/SAF/glow_tests_{str(uuid.uuid4())}"


@pytest.fixture(scope="module")
def random_string() -> Callable[[], str]:
    def _random_string() -> str:
        return str(uuid.uuid4())

    return _random_string


@pytest.fixture(scope="class")
def ensure_minerva_cli(data_repo_configuration: str, class_project: ProjectFixture[DataRepositorySolution]):
    if (
        data_repo_configuration == "Minerva"
        and not class_project.project.steps.data_repository_step.ensure_minerva_cli()
    ):
        pytest.skip("Install Ansys Minerva CLI to run Minerva-based tests.")


@pytest.fixture(scope="class")
def data_repo_configuration(
    session_glow: GlowDesktopProcess[DataRepositorySolution],
    request: pytest.FixtureRequest,
    temp_upload_root: str,
    minerva_settings: dict[str, str],
) -> Generator[str, None, None]:
    """Sets up the logging configuration. Needs to be indirectly parametrized"""
    selected_data_repo = "Default" if not request.param else request.param

    data_repo_configs: dict[str, type[DataRepositoryConfiguration]] = {
        "Default": DefaultDataRepoConfiguration,
        "FileSystem": FileSystemDataRepoConfiguration,
        "Minerva": MinervaDataRepoConfiguration,
    }
    selected_config = data_repo_configs[selected_data_repo]
    session_glow.change_configuration(EnvVarDebug, restart=False)
    session_glow.change_configuration(
        selected_config,
        temp_upload_root=temp_upload_root,
        minerva_settings=minerva_settings,
    )

    mp = pytest.MonkeyPatch()
    # also needed in the client
    if selected_config.data_repo_type:
        mp.setenv("GLOW_DATA_REPOSITORY_TYPE", selected_config.data_repo_type)
    else:
        mp.delenv("GLOW_DATA_REPOSITORY_TYPE", raising=False)

    if selected_data_repo == "Minerva":
        # also needed in the client
        for key, value in minerva_settings.items():
            mp.setenv(key, value)

    yield selected_data_repo

    mp.undo()


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowDesktopProcess[DataRepositorySolution]) -> YieldFixture[None]:
    yield
    session_glow.configure_default_execution()


@pytest.fixture
def local_minerva_working_dir(
    function_project: ProjectFixture[DataRepositorySolution],
    session_glow: GlowDesktopProcess[DataRepositorySolution],
):
    return session_glow.project_files_directory / function_project.project_id / "minerva"


@pytest.fixture
def data_project_directory_name(function_project: ProjectFixture[DataRepositorySolution]) -> str:
    data_project_dir_name = f"{function_project.project.project_display_name} ({function_project.project_id})"
    return data_project_dir_name


@pytest.mark.parametrize(
    "data_repo_configuration",
    [
        "FileSystem",
        pytest.param("Minerva", marks=pytest.mark.use_minerva),
    ],
    indirect=True,
)
@pytest.mark.usefixtures("data_repo_configuration", "ensure_minerva_cli")
class TestDataRepository:
    def test_data_repo_project_directory_name(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_project_directory_name: str,
    ):
        """Test that the project directory name under Data/ includes the project
        display name and the project id.
        """
        step = function_project.project.steps.data_repository_step
        step.upload_blob_to_data_repo()
        storage_scope = function_project.project.storage_scope
        assert data_project_directory_name in str(storage_scope.get_cached(step.data_repo_handle))

    def test_data_repo_upload_root_directory_can_be_specified(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        temp_upload_root: str,
    ):
        """Test that the root dir in the data repository can be configured via env var."""
        step = function_project.project.steps.data_repository_step

        # Ensure env var is set.
        assert step.get_env_var(var_name="GLOW_DATA_REPOSITORY_UPLOAD_ROOT") == temp_upload_root

        step.upload_blob_to_data_repo()
        assert temp_upload_root in function_project.project.storage_scope.get_cached(step.data_repo_handle).as_posix()

    def test_blob_can_be_stored_and_fetched_from_transaction(
        self,
        request: pytest.FixtureRequest,
        data_repo_configuration: str,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
    ):
        """Test that a blob can be uploaded and downloaded within a transaction
        from a data repository.
        """
        if data_repo_configuration == "Minerva":
            request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
                pytest.mark.xfail(reason="See https://github.com/ansys/saf/issues/162."),
            )

        step = function_project.project.steps.data_repository_step

        content = random_string()
        step.upload_blob_to_data_repo(content=content)
        assert step.fetch_blob_content_from_data_repo() == content

    def test_blob_can_be_stored_from_transaction_and_fetched_from_client(
        self,
        request: pytest.FixtureRequest,
        data_repo_configuration: str,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
    ):
        """Test that a blob can be uploaded from a transaction to a data repository
        and accessed from the client.
        """
        if data_repo_configuration == "Minerva":
            request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
                pytest.mark.xfail(reason="See https://github.com/ansys/saf/issues/162."),
            )

        step = function_project.project.steps.data_repository_step
        content = random_string()

        step.upload_blob_to_data_repo(content=content)
        assert function_project.project.storage_scope.get_cached(step.data_repo_handle).read_text() == content

    def test_fetched_blob_lifetime(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
        session_glow: GlowDesktopProcess[DataRepositorySolution],
    ):
        """Test that the cache and cache content will exist for the duration of the GLOW project."""
        step = function_project.project.steps.data_repository_step

        content = random_string()
        step.upload_blob_to_data_repo(content=content)

        session_glow.restart()

        cached_file = function_project.project.storage_scope.get_cached(step.data_repo_handle)
        session_glow.restart()
        assert cached_file.read_text() == content

        function_project.delete()

        assert not cached_file.is_file()

    def test_upload_blob_to_data_repo_using_default_target_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_project_directory_name: str,
        temp_upload_root: str,
        random_string: Callable[[], str],
    ):
        """Test that uploading blob without giving a target path uses a default value provided by the
        original entity.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()
        file_relative_path = f"dir/{random_string()}.txt"

        assert step.data_repo_handle == NO_ENTITY
        step.upload_blob_to_data_repo(content=content, file_path=file_relative_path)
        fetched = function_project.project.storage_scope.get_cached(step.data_repo_handle)
        assert fetched.read_text() == content
        assert f"{temp_upload_root}/{data_project_directory_name}/{file_relative_path}" in fetched.as_posix()

    def test_upload_blob_to_data_repo_using_relative_target_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_project_directory_name: str,
        temp_upload_root: str,
        random_string: Callable[[], str],
    ):
        """Test that uploading blob using a relative target path creates a file at the
        data repo root / project_id / relative path.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()
        folder_name = random_string()

        assert step.data_repo_handle == NO_ENTITY
        step.upload_blob_to_data_repo(target_path=f"{folder_name}/data.txt", content=content)
        path = function_project.project.storage_scope.get_cached(step.data_repo_handle)
        assert path.read_text() == content
        assert f"{temp_upload_root}/{data_project_directory_name}/{folder_name}/data.txt" in path.as_posix()

    def test_upload_blob_to_data_repo_using_absolute_target_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        temp_upload_root: str,
        random_string: Callable[[], str],
    ):
        """Test that uploading blob using an absolute target path creates a file at the
        data repo root / path.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()

        assert step.data_repo_handle == NO_ENTITY
        unique_file_name = f"{random_string()}.txt"
        step.upload_blob_to_data_repo(target_path=f"{temp_upload_root}/{unique_file_name}", content=content)
        scope = function_project.project.storage_scope
        path = scope.get_cached(step.data_repo_handle)
        assert path.read_text() == content
        assert f"{temp_upload_root}/{unique_file_name}" in path.as_posix()

    def test_upload_same_blob_multiple_times_within_transaction(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        request: pytest.FixtureRequest,
        random_string: Callable[[], str],
    ):
        """Test that the same blob can be uploaded multiple times and it does not generate
        new versions at the data repository.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()

        if data_repo_configuration == "Minerva":
            request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
                pytest.mark.xfail(
                    reason="Minerva bug: https://tfs.ansys.com:8443/tfs/ANSYS_Development/Portfolio/_workitems/edit/1188721/.",
                ),
            )

        step.upload_same_blob_twice_to_data_repo(content=content)
        assert step.fetch_blob_content_from_data_repo(minerva_path="data.txt", version="001") == content
        assert step.fetch_blob_content_from_data_repo(minerva_path="data.txt", version="001.001") == content
        assert step.get_data_repository_entity_handle(minerva_path="data.txt", version="001.002") == NO_ENTITY

    def test_upload_same_content_multiple_times_different_transactions(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        random_string: Callable[[], str],
        request: pytest.FixtureRequest,
    ):
        """Test that uploading the same content at same path multiple times generates new versions at the data
        repository.
        """
        step = function_project.project.steps.data_repository_step

        uploaded_entity_v1 = step.upload_blob_to_data_repo()
        uploaded_entity_v2 = step.upload_blob_to_data_repo()
        downloaded_entity_v1 = step.get_data_repository_entity_handle(minerva_path="data.txt", version="001.001")
        downloaded_entity_v2 = step.get_data_repository_entity_handle(minerva_path="data.txt")
        downloaded_entity_v3 = step.get_data_repository_entity_handle(minerva_path="data.txt", version="001")
        if data_repo_configuration == "Minerva":
            # With the second upload, Minerva updates version 001 with a new id, and creates a version 001.001
            # with the old id
            assert uploaded_entity_v1 != uploaded_entity_v2
            assert uploaded_entity_v1 == downloaded_entity_v1
            assert uploaded_entity_v2 == downloaded_entity_v2
            assert uploaded_entity_v2 == downloaded_entity_v3
        else:
            # FileSystem's entity handles are only differentiated by the version in their opaque identifier.
            # That's why upload returns the dotted version (e.g. 001.002). Otherwise, all uploads of the same
            # file would return the same entity handle. When reuploading the same path and content, the returned
            # entity handle is the same. Getting an entity handle without specifying a version get version 001.
            assert uploaded_entity_v1 == uploaded_entity_v2
            assert uploaded_entity_v1 == downloaded_entity_v1
            assert uploaded_entity_v2 != downloaded_entity_v2
            assert downloaded_entity_v2 == downloaded_entity_v3
            return

        request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
            pytest.mark.xfail(
                reason="Bug updating a file to Minerva multiple times.",
            ),
        )

        new_content = random_string()
        step.upload_blob_to_data_repo(content=new_content)
        assert function_project.project.storage_scope.get_cached(step.data_repo_handle).read_text() == new_content

    def test_upload_new_file_does_not_modify_identifier_of_previous_file(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        request: pytest.FixtureRequest,
    ):
        """Test that posterior uploads do not affect previous uploads and their identifiers."""
        if data_repo_configuration == "Minerva":
            request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
                pytest.mark.xfail(
                    reason="Minerva bug: https://tfs.ansys.com:8443/tfs/ANSYS_Development/Portfolio/_workitems/edit/1207372.",
                ),
            )

        step = function_project.project.steps.data_repository_step

        file_name = "my_data.txt"
        uploaded_entity = step.upload_blob_to_data_repo(target_path=file_name)
        assert uploaded_entity == step.get_data_repository_entity_handle(minerva_path=file_name, version="001.001")

        other_file_name = "my_data_2.txt"
        other_uploaded_entity = step.upload_blob_to_data_repo(target_path=other_file_name)
        assert uploaded_entity == step.get_data_repository_entity_handle(minerva_path=file_name, version="001.001")
        assert other_uploaded_entity == step.get_data_repository_entity_handle(
            minerva_path=other_file_name,
            version="001.001",
        )

    # Parameterization makes it slow, but downloading sequentially different versions
    # in the same place makes minerva cli hanging forever...
    @pytest.mark.parametrize("version", ["001", "001.001", "001.002", "001.003", None])
    def test_upload_multiple_versions_within_transaction_and_download_versions(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        version: str | None,
        random_string: Callable[[], str],
        request: pytest.FixtureRequest,
        data_repo_configuration: str,
    ):
        """
        Test that re-uploading the same file with different content within a transaction generate different versions at
        the data repository. These versions can be then fetched from the client or within a transaction.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()
        assert step.data_repo_handle == NO_ENTITY

        step.upload_blob_multiple_times_to_data_repo(num_times=3, base_content=content)

        if version in ["001", "001.003"] or version is None:
            if data_repo_configuration == "Minerva":
                request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
                    pytest.mark.xfail(
                        reason="Minerva bug: Bug updating a file to Minerva multiple times",
                    ),
                )
            expected_content = f"{content} v3"
        else:
            expected_content = f"{content} v{version[-1]}"
        assert step.fetch_blob_content_from_data_repo(version=version) == expected_content

        assert (
            function_project.project.storage_scope.get_text(step.get_data_repository_entity_handle(version=version))
            == expected_content
        )

    # Parameterization makes it slow, but downloading sequentially different versions
    # in the same place makes minerva cli hanging forever...
    @pytest.mark.parametrize("version", ["001", "001.001", "001.002", "001.003", None])
    def test_upload_multiple_versions_from_client_and_download_versions(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        version: str | None,
        random_string: Callable[[], str],
        request: pytest.FixtureRequest,
        data_repo_configuration: str,
    ):
        """
        Test that re-uploading the same file with different content in different transactions generate different
        versions at the data repository. These versions can be then fetched from the client or within a transaction.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()
        assert step.data_repo_handle == NO_ENTITY

        num_times = 3
        for i in range(1, num_times + 1):
            # sleep required by Minerva bug:
            # https://tfs.ansys.com:8443/tfs/ANSYS_Development/Portfolio/_workitems/edit/1188721
            time.sleep(2)
            step.upload_blob_to_data_repo(content=f"{content} v{i}")

        if version in ["001", "001.003"] or version is None:
            expected_content = f"{content} v{num_times}"
            if data_repo_configuration == "Minerva":
                request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
                    pytest.mark.xfail(
                        reason="Minerva bug: Bug updating a file to Minerva multiple times.",
                    ),
                )
        else:
            expected_content = f"{content} v{version[-1]}"
        assert step.fetch_blob_content_from_data_repo(version=version) == expected_content

        assert (
            function_project.project.storage_scope.get_text(
                step.get_data_repository_entity_handle(version=version),
            )
            == expected_content
        )

    def test_upload_directory_to_data_repo_using_default_target_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_project_directory_name: str,
        random_string: Callable[[], str],
    ):
        """Test that uploading a directory without giving a target path uses a default value provided by the
        original entity.
        """
        step = function_project.project.steps.data_repository_step
        original_dir = random_string()

        assert step.data_repo_handle == NO_ENTITY
        step.upload_small_directory_to_data_repo(root_folder_name=original_dir)

        expected_files = {"my_another_file.txt", "my_file1.txt"}

        scope = function_project.project.storage_scope
        for child in scope.get_children(step.data_repo_handle):
            expected_files.remove(str(child.original_name))
            file_path = scope.get_cached(child)
            assert f"{data_project_directory_name}/{original_dir}/{child.original_name}" in file_path.as_posix()

        assert not expected_files

    def test_upload_directory_to_data_repo_using_relative_target_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_project_directory_name: str,
        random_string: Callable[[], str],
    ):
        """Test that uploading a directory using a relative target path creates a file at the
        data repo root / Data / project_id / relative path.
        """
        step = function_project.project.steps.data_repository_step
        source_dir = random_string()
        target_dir = random_string()

        assert step.data_repo_handle == NO_ENTITY

        step.upload_small_directory_to_data_repo(root_folder_name=source_dir, target_path=f"{target_dir}")

        expected_files = {"my_another_file.txt", "my_file1.txt"}

        scope = function_project.project.storage_scope
        for child in scope.get_children(step.data_repo_handle):
            file_path = scope.get_cached(child).as_posix()
            expected_files.remove(str(child.original_name))
            assert f"{data_project_directory_name}/{target_dir}/{child.original_name}" in file_path
            assert source_dir not in file_path

        assert not expected_files

    def test_upload_directory_to_data_repo_using_absolute_target_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        temp_upload_root: str,
        data_project_directory_name: str,
        random_string: Callable[[], str],
    ):
        """Test that uploading a directory using an absolute target path creates a file at the
        data repo root / path.
        """
        step = function_project.project.steps.data_repository_step
        source_dir = random_string()
        target_dir = random_string()

        assert step.data_repo_handle == NO_ENTITY

        step.upload_small_directory_to_data_repo(
            root_folder_name=source_dir,
            target_path=f"{temp_upload_root}/{target_dir}",
        )

        expected_files = {"my_another_file.txt", "my_file1.txt"}

        scope = function_project.project.storage_scope
        for child in scope.get_children(step.data_repo_handle):
            file_path = scope.get_cached(child).as_posix()
            expected_files.remove(str(child.original_name))
            assert f"{target_dir}/{child.original_name}" in file_path
            assert data_project_directory_name not in file_path
            assert source_dir not in file_path

        assert not expected_files

    def test_fetch_blob_content_from_data_repo_using_relative_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
    ):
        """Test that a file can be pulled from the data repository using a relative path."""
        step = function_project.project.steps.data_repository_step
        content = random_string()

        file_name = f"{random_string()}.txt"

        step.upload_blob_to_data_repo(target_path=f"folder/{file_name}", content=content)
        assert step.fetch_blob_content_from_data_repo(minerva_path=f"folder/{file_name}") == content

    def test_fetch_blob_content_from_data_repo_using_absolute_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        temp_upload_root: str,
        random_string: Callable[[], str],
    ):
        """Test that a file can be pulled from the data repository using an absolute path."""
        step = function_project.project.steps.data_repository_step
        content = random_string()

        unique_path = f"{temp_upload_root}/{random_string()}/data.txt"
        step.upload_blob_to_data_repo(target_path=unique_path, content=content)
        assert step.fetch_blob_content_from_data_repo(minerva_path=unique_path) == content

    def test_fetch_nonexisting_blob_from_data_repo_returns_no_entity(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
    ):
        """Test that pulling an inexistent file from the data repository returns a NO_ENTITY handle."""
        step = function_project.project.steps.data_repository_step
        assert step.return_get_entity_handle(minerva_path=random_string()) == NO_ENTITY

    def test_fetch_children_from_data_repo_directory(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
    ):
        """Test that given a handle to a directory in the data repository, its children (files and directories) can be
        retrieved.
        """
        step = function_project.project.steps.data_repository_step
        folder_name = random_string()

        step.upload_directory_to_data_repo(root_folder_name=folder_name)
        method_children = step.fetch_children_from_data_repo_directory(minerva_path=folder_name)
        client_children = function_project.project.storage_scope.get_children(step.data_repo_handle)
        assert method_children == client_children
        assert sorted([child.original_name for child in method_children if child.original_name]) == sorted(
            [
                "my_file1.txt",
                "my_file2.txt",
                "subdir",
                "empty_subdir",
                "nested_empty_subdir",
                "nested_subdir_same_name",
            ],
        )

    def test_get_parent(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
    ):
        """Test that given a handle to a file or directory in the data repository, its parent can be retrieved."""
        step = function_project.project.steps.data_repository_step
        folder_name = random_string()

        step.upload_directory_to_data_repo(root_folder_name=folder_name)
        method_parent = step.fetch_parent_from_data_repo_directory(minerva_path=f"{folder_name}/my_file1.txt")
        file_handle = step.fetch_child_from_data_repo_handle()
        client_parent = function_project.project.storage_scope.get_parent(file_handle)
        assert method_parent
        assert method_parent.original_name == folder_name
        assert method_parent == client_parent

    @pytest.mark.parametrize("root_dir", ["/", "/Data", "/Data/"])
    def test_get_handle_for_root_dir(self, root_dir: str, function_project: ProjectFixture[DataRepositorySolution]):
        """Test that the handle for the absolute root dir in Minerva ("/Data") cannot be retrieved and returns
        NO_ENTITY.
        """
        step = function_project.project.steps.data_repository_step
        assert step.get_data_repository_entity_handle(minerva_path=root_dir) == NO_ENTITY

    def test_fetch_data_from_data_repo(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
        tmp_path: Path,
    ):
        """Test that a project can access the contents of data stored in Minerva using the methods provided by BDM:
        path, text, bytes, stream.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()
        copied_file = tmp_path / f"{random_string()}.txt"

        step.upload_blob_to_data_repo(content=content)
        assert step.fetch_cached_from_data_repo_handle().read_text() == content
        assert step.fetch_text_from_data_repo_handle() == content
        assert step.fetch_bytes_from_data_repo_handle() == bytes(content, "utf-8")
        assert step.fetch_stream_from_data_repo_handle() == content
        scope = function_project.project.storage_scope
        file_handle = step.get_data_repository_entity_handle()
        cached_file = scope.get_cached(file_handle)
        assert cached_file.read_text() == content
        assert scope.get_text(file_handle) == content
        assert scope.get_bytes(file_handle) == bytes(content, "utf-8")
        assert scope.get_stream(file_handle).readall().decode() == content

        scope.get_copy(file_handle, copied_file)
        assert cached_file != copied_file
        assert copied_file.read_text() == content

    def test_access_data_from_other_projects(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_project_directory_name: str,
        temp_upload_root: str,
        random_string: Callable[[], str],
        create_project: Callable[[], ProjectFixture[DataRepositorySolution]],
    ):
        """
        - Test that a project can fetch and upload into the data of other projects, solutions, apps...
        because all projects have access to all files in Minerva.
        - Test that a project can fetch a file before it has uploaded anything.
        """
        second_project = create_project()

        step_a = function_project.project.steps.data_repository_step
        content_from_a = random_string()
        file_from_a = f"{random_string()}.txt"
        project_a_subdirectory = data_project_directory_name

        step_b = second_project.project.steps.data_repository_step
        content_from_b = random_string()
        file_from_b = f"{random_string()}.txt"

        with pytest.raises(InternalSolutionException, match="accessing storage using NO_ENTITY handle"):
            step_a.fetch_blob_content_from_data_repo(minerva_path=file_from_a)

        # A second project uploads a file into the project A directory
        step_b.upload_blob_to_data_repo(
            content=content_from_b,
            target_path=f"{temp_upload_root}/{project_a_subdirectory}/{file_from_b}",
        )
        # project A can fetch a file before it has uploaded anything.
        assert step_a.fetch_blob_content_from_data_repo(minerva_path=file_from_b) == content_from_b

        # Similarly, a second project can fetch a file from the first project directory
        step_a.upload_blob_to_data_repo(content=content_from_a, target_path=file_from_a)
        assert (
            step_b.fetch_blob_content_from_data_repo(
                minerva_path=f"{temp_upload_root}/{project_a_subdirectory}/{file_from_a}",
            )
            == content_from_a
        )

    @pytest.mark.parametrize("clean_local_repo", [True, False])
    def test_upload_blob_into_existing_dir(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        local_minerva_working_dir: Path,
        data_project_directory_name: str,
        temp_upload_root: str,
        clean_local_repo: bool,
        random_string: Callable[[], str],
    ):
        """Test that trying to upload a file to the path of an existing directory raises an exception."""
        step = function_project.project.steps.data_repository_step
        target_path = random_string()

        step.upload_directory_to_data_repo(target_path=target_path)
        if clean_local_repo:
            shutil.rmtree(local_minerva_working_dir / temp_upload_root[1:])

        with pytest.raises(
            InternalSolutionException,
            match=f"Directory already exists at "
            f"{temp_upload_root}/{re.escape(data_project_directory_name)}/{target_path}",
        ):
            step.upload_blob_to_data_repo(target_path=target_path)

    @pytest.mark.parametrize("clean_local_repo", [True, False])
    def test_upload_directory_into_existing_blob(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        local_minerva_working_dir: Path,
        data_project_directory_name: str,
        temp_upload_root: str,
        clean_local_repo: bool,
        random_string: Callable[[], str],
    ):
        """Test that trying to upload a directory to the path of an existing file raises an exception."""
        step = function_project.project.steps.data_repository_step
        target_path = random_string()

        step.upload_blob_to_data_repo(target_path=target_path)
        if clean_local_repo:
            shutil.rmtree(local_minerva_working_dir / temp_upload_root[1:])
        with pytest.raises(
            InternalSolutionException,
            match=f"File exists at {temp_upload_root}/{re.escape(data_project_directory_name)}/{target_path}",
        ):
            step.upload_directory_to_data_repo(target_path=target_path)

    @pytest.mark.timeout(250, func_only=True)
    @pytest.mark.parametrize("freeze", [False, True])
    @pytest.mark.parametrize("blob_type", ["file", "folder"])
    def test_upload_blob_and_read_from_file(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        random_string: Callable[[], str],
        blob_type: str,
        freeze: bool,
        data_repo_configuration: str,
        request: pytest.FixtureRequest,
    ):
        """
        Workflow intended to demonstrate bug #2217
        """
        if data_repo_configuration == "Minerva" and blob_type == "folder":
            request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
                pytest.mark.xfail(
                    reason="folder-Minerva parametrization causes a timeout.",
                ),
            )

        step = function_project.project.steps.data_repository_step
        blob_name = f"{random_string()}.txt" if blob_type == "file" else random_string()
        content = random_string()

        logger.info(f"Uploading blob to {blob_name}")
        if blob_type == "file":
            handle = step.upload_blob_to_data_repo(file_path=blob_name, content=content)
        else:
            handle = step.upload_directory_to_data_repo(root_folder_name=blob_name, file_1_content=content)

        storage_scope = function_project.project.storage_scope
        logger.info("Getting data repo handle will trigger the freeze.")
        if freeze:
            storage_scope.get_cached(handle)

        logger.info("Fetching target file content.")
        if blob_type == "file":
            assert step.fetch_blob_content_from_data_repo(minerva_path=blob_name) == content
        else:
            assert step.fetch_blob_content_from_data_repo(minerva_path=f"{blob_name}/my_file1.txt") == content

    @pytest.mark.timeout(300, func_only=True)
    def test_upload_directory_into_existing_directory(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        local_minerva_working_dir: Path,
        temp_upload_root: str,
        data_project_directory_name: str,
        random_string: Callable[[], str],
        data_repo_configuration: str,
        request: pytest.FixtureRequest,
    ):
        """Test that uploading a directory into an existing directory individually updates or creates every file
        and directory within it.
        """
        if data_repo_configuration == "Minerva":
            request.node.add_marker(  # pyright: ignore[reportUnknownMemberType]
                pytest.mark.xfail(
                    reason="Timeout due to bug #2217.",
                ),
            )

        step = function_project.project.steps.data_repository_step
        folder_name = random_string()

        expected_files = set(
            {
                f"/{folder_name}/empty_subdir",
                f"/{folder_name}/my_file1.txt",
                f"/{folder_name}/my_file2.txt",
                f"/{folder_name}/nested_empty_subdir",
                f"/{folder_name}/nested_empty_subdir/empty_subdir_2",
                f"/{folder_name}/nested_subdir_same_name",
                f"/{folder_name}/nested_subdir_same_name/{folder_name}",
                f"/{folder_name}/nested_subdir_same_name/{folder_name}/my_file4.txt",
                f"/{folder_name}/nested_subdir_same_name/{folder_name}/my_file5.txt",
                f"/{folder_name}/subdir",
                f"/{folder_name}/subdir/my_file3.txt",
            },
        )

        logger.info(f"Uploading directory to {folder_name}")
        step.upload_directory_to_data_repo(root_folder_name=folder_name)

        storage_scope = function_project.project.storage_scope
        logger.info("Getting data repo handle.")
        directory_path = storage_scope.get_cached(step.data_repo_handle)
        logger.info(f"{directory_path} cached.")
        actual_files = set({p.as_posix().split(data_project_directory_name)[-1] for p in directory_path.rglob("*")})
        assert actual_files == expected_files
        assert (directory_path / "my_file1.txt").read_text() == "file1"
        assert (directory_path / "my_file2.txt").read_text() == "file2"

        logger.info("Removing local cache.")
        shutil.rmtree(local_minerva_working_dir / temp_upload_root[1:])

        logger.info("Fetching target file content.")
        file_content_before = step.fetch_blob_content_from_data_repo(minerva_path=f"{folder_name}/my_file1.txt")

        logger.info(f"Uploading smaller directory to {folder_name}.")
        step.upload_small_directory_to_data_repo(root_folder_name=folder_name)

        logger.info("Fetching target file content.")
        assert file_content_before != step.fetch_blob_content_from_data_repo(minerva_path=f"{folder_name}/my_file1.txt")

        expected_files.add(f"/{folder_name}/my_another_file.txt")

        logger.info("Getting data repo handle.")
        directory_path = storage_scope.get_cached(step.data_repo_handle)
        logger.info(f"{directory_path} cached.")
        actual_files = set({p.as_posix().split(data_project_directory_name)[-1] for p in directory_path.rglob("*")})
        assert actual_files == expected_files
        assert (directory_path / "my_file1.txt").read_text() == "my_file1"
        assert (directory_path / "my_file2.txt").read_text() == "file2"

    def generate_xml_search_by_name(self, name_pattern: str, path_pattern: str) -> str:
        # Create the root element
        item = ET.Element("Item")
        item.set("type", "Ans_Data")
        item.set("action", "get")

        # Add the filtering elements
        name = ET.SubElement(item, "name")
        name.set("condition", "like")
        name.text = name_pattern
        path = ET.SubElement(item, "path")
        path.set("condition", "like")
        path.text = path_pattern

        xml_string = ET.tostring(item, encoding="unicode")
        return xml_string

    def test_query_using_existing_files(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        data_project_directory_name: str,
        random_string: Callable[[], str],
    ):
        """Test that a query can be made to retrieve files based on their metadata, such as name and path."""
        step = function_project.project.steps.data_repository_step

        if data_repo_configuration == "Minerva":
            folder_name = random_string()
            query_str = self.generate_xml_search_by_name("my_file*", f"*{data_project_directory_name}*")
        else:
            # Queries are mocked using the FileSystem data repository. Using a fixed name.
            folder_name = "folder"
            query_str = "folder_files_query_placeholder"

        step.upload_directory_to_data_repo(root_folder_name=folder_name)

        entities = step.get_entities_based_on_query(value=query_str)

        for file_path in [
            f"{folder_name}/my_file1.txt",
            f"{folder_name}/my_file2.txt",
            f"{folder_name}/subdir/my_file3.txt",
            f"{folder_name}/nested_subdir_same_name/{folder_name}/my_file4.txt",
            f"{folder_name}/nested_subdir_same_name/{folder_name}/my_file5.txt",
        ]:
            expected_entity = step.get_data_repository_entity_handle(minerva_path=file_path)
            assert expected_entity in entities
            entities.remove(expected_entity)

        assert not entities

    def test_query_using_existing_directory(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        data_project_directory_name: str,
        random_string: Callable[[], str],
    ):
        """Test that a query can be made to retrieve directories based on their metadata, such as name and path."""
        step = function_project.project.steps.data_repository_step
        if data_repo_configuration == "Minerva":
            folder_name = random_string()
            query_str = self.generate_xml_search_by_name("empty_subdir_*", f"*{data_project_directory_name}*")
        else:
            folder_name = "folder"
            query_str = "folder_dir_query_placeholder"

        step.upload_directory_to_data_repo(root_folder_name=folder_name)
        entities = step.get_entities_based_on_query(value=query_str)
        assert len(entities) == 1

        file_path = f"{folder_name}/nested_empty_subdir/empty_subdir_2"
        expected_entity = step.get_data_repository_entity_handle(minerva_path=file_path)
        assert expected_entity == entities[0]

    def test_query_using_non_existent_filename(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        temp_upload_root: str,
    ):
        """Test that a query that looks for metadata that no file or directory in the data repository fulfills returns
        an empty list.
        """
        step = function_project.project.steps.data_repository_step
        step.upload_directory_to_data_repo()

        query_str = self.generate_xml_search_by_name(f"{uuid.uuid4()}*", f"{temp_upload_root}*")
        assert not step.get_entities_based_on_query(value=query_str)

    def test_invalid_query(self, function_project: ProjectFixture[DataRepositorySolution]):
        """Test that a query with invalid syntax returns an empty list."""
        step = function_project.project.steps.data_repository_step
        assert not step.get_entities_based_on_query(value="?¿?¿$***invalid<>query")

    def test_filesystem_query_without_field(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
    ):
        """
        Test that queries in FileSystem don't work if
        the query field is not specified in the solution configuration.
        """
        if data_repo_configuration == "Minerva":
            pytest.skip("Test does not apply to Minerva.")

        step = function_project.project.steps.data_repository_step
        file_name = "my_data.txt"
        step.upload_blob_to_data_repo(target_path=file_name)

        # test query works normally
        query_str = "my_data_query_placeholder"
        entities = step.get_entities_based_on_query(value=query_str)
        expected_entity = step.get_data_repository_entity_handle(minerva_path="my_data.txt")
        assert expected_entity in entities

        # but fails if filesystem_data_repository_query_map is None
        with pytest.raises(
            InternalSolutionException,
            match="Solution configuration must include a 'filesystem_data_repository_query_map' field",
        ):
            step.get_entities_based_on_query_without_query_map(value=query_str)

    def test_filesystem_query_file_not_found(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
    ):
        """Test that queries in FileSystem don't work if the hardcoded file result does not exist."""
        if data_repo_configuration == "Minerva":
            pytest.skip("Test does not apply to Minerva.")

        step = function_project.project.steps.data_repository_step

        query_str = "file_not_found_query_placeholder"
        with pytest.raises(InternalSolutionException, match="Could not create ItemResult. File does not exist:"):
            step.get_entities_based_on_query(value=query_str)

    def generate_custom_metadata(self, file: str) -> tuple[str, str]:
        section = ET.Element("section")

        # fields in the same info file
        file_element = ET.SubElement(section, "file")
        file_element.set("role", "subject")
        file_element.set("src", file)
        file_element.set("creator", "test")
        file_element.set("appVersion", "test_version")

        # extra fields with random property
        text_element = ET.SubElement(section, "text")
        property_name = f"p_name_{str(uuid.uuid4())}"
        text_element.set("name", property_name)
        property_value = f"p_value_{str(uuid.uuid4())}"
        text_element.set("value", property_value)
        xml_string = ET.tostring(section, encoding="unicode")

        return property_name, xml_string

    def generate_xml_search_by_metadata_str(self, metadata_pattern: str, version: str | None = None) -> str:
        item = ET.Element("Item")
        item.set("type", "Ans_Data")
        item.set("action", "get")
        # queryType and queryDate required to be able to find older versions
        item.set("queryType", "Latest")
        item.set("queryDate", datetime.datetime.now().strftime("%Y-%m-%dT23:59:59"))
        if version:
            # workaround because I couldn't find a query that would return several versions of the same file
            version_item = ET.SubElement(item, "major_rev")
            version_item.set("condition", "like")
            version_item.text = version
        parameter_doc = ET.SubElement(item, "parameter_doc")
        parameter_item = ET.SubElement(parameter_doc, "Item")
        parameter_item.set("type", "ans_ParameterDocument")
        keyed_name = ET.SubElement(parameter_item, "document")
        keyed_name.set("condition", "like")
        keyed_name.text = metadata_pattern
        xml_string = ET.tostring(item, encoding="unicode")

        return xml_string

    def assert_entity_link_with_metadata(
        self,
        step: DataRepositoryStep,
        property_name: str,
        entity: EntityHandle,
        version: str | None = None,
    ):
        query_str = self.generate_xml_search_by_metadata_str(f"*{property_name}*", version=version)
        linked_entities = step.get_entities_based_on_query(value=query_str)
        return entity in linked_entities

    def validate_filesystem_metadata(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        remote_path: str,
        version: str,
        property_name: str | None = None,
    ) -> bool:
        data_repo_path = function_project.project_files_dir.parent / "filesystem"
        version_str = f"{version}_default" if version == "001" else version
        metadata_path = data_repo_path / remote_path / f"{version_str}.metadata"
        if not metadata_path.is_file():
            return False
        if property_name:
            return property_name in metadata_path.read_text()
        return True

    def test_upload_file_with_associated_metadata_and_relative_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        random_string: Callable[[], str],
    ):
        """Test that a file can be uploaded with metadata using a relative path."""
        step = function_project.project.steps.data_repository_step
        content = random_string()
        file_name = "my_data.txt"

        property_name, metadata_str = self.generate_custom_metadata(file_name)
        uploaded_entity = step.upload_blob_to_data_repo(
            content=content,
            target_path=file_name,
            metadata=metadata_str,
        )

        if data_repo_configuration == "Minerva":
            # version 001.001 is not created for Minerva
            assert self.assert_entity_link_with_metadata(step, property_name, uploaded_entity)
        else:
            remote_path = uploaded_entity.opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
            assert self.validate_filesystem_metadata(function_project, remote_path, "001", property_name)
            assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.001") == content
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.001", property_name)

        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001") == content

    def test_upload_file_with_associated_metadata_and_absolute_path(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        temp_upload_root: str,
        random_string: Callable[[], str],
    ):
        """Test that a file can be uploaded with metadata using an absolute path."""
        step = function_project.project.steps.data_repository_step
        content = random_string()

        file_name = "my_data.txt"
        target_path = f"{temp_upload_root}/{file_name}"
        property_name, metadata_str = self.generate_custom_metadata(file_name)
        uploaded_entity = step.upload_blob_to_data_repo(
            content=content,
            target_path=target_path,
            metadata=metadata_str,
        )

        if data_repo_configuration == "Minerva":
            # version 001.001 is not created for Minerva
            assert self.assert_entity_link_with_metadata(step, property_name, uploaded_entity)
        else:
            remote_path = uploaded_entity.opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
            assert self.validate_filesystem_metadata(function_project, remote_path, "001", property_name)
            assert step.fetch_blob_content_from_data_repo(minerva_path=target_path, version="001.001") == content
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.001", property_name)

        assert step.fetch_blob_content_from_data_repo(minerva_path=target_path, version="001") == content

    def test_upload_different_file_after_upload_with_metadata(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        random_string: Callable[[], str],
    ):
        """Test that uploading a file with metadata does not block posterior uploads, and that the latter are not
        affected by the previous metadata.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()

        file_name = "my_data.txt"
        # Generate new content for every file, otherwise it will be linked with the metadata due to Minerva's design:
        # https://tfs.ansys.com:8443/tfs/ANSYS_Development/Portfolio/_workitems/edit/1207948
        property_name, metadata_str = self.generate_custom_metadata(file_name)
        step.upload_blob_to_data_repo(content=content, target_path=file_name, metadata=metadata_str)

        other_file_name = "my_data_2.txt"
        other_content = random_string()
        other_entity = step.upload_blob_to_data_repo(content=other_content, target_path=other_file_name)
        # can't use entity returned by first upload call due to bug in Minerva:
        # https://tfs.ansys.com:8443/tfs/ANSYS_Development/Portfolio/_workitems/edit/1207372
        entity = step.get_data_repository_entity_handle(minerva_path=file_name)

        if data_repo_configuration == "Minerva":
            # version 001.001 is not created for Minerva
            assert self.assert_entity_link_with_metadata(step, property_name, entity)
            assert not self.assert_entity_link_with_metadata(step, property_name, other_entity)
        else:
            remote_path = entity.opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
            other_remote_path = other_entity.opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
            assert self.validate_filesystem_metadata(function_project, remote_path, "001", property_name)
            assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.001") == content
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.001", property_name)
            assert not self.validate_filesystem_metadata(function_project, other_remote_path, "001")
            assert (
                step.fetch_blob_content_from_data_repo(minerva_path=other_file_name, version="001.001") == other_content
            )
            assert not self.validate_filesystem_metadata(function_project, other_remote_path, "001.001")

        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001") == content
        assert step.fetch_blob_content_from_data_repo(minerva_path=other_file_name, version="001") == other_content

    def test_reupload_same_file_with_new_content_and_without_metadata(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        random_string: Callable[[], str],
    ):
        """Test that when uploading the same file with new content and without metadata, Minerva keeps the link of the
        old version with the old metadata and the new version is not linked with anything.
        """
        step = function_project.project.steps.data_repository_step
        content = random_string()

        file_name = "my_data.txt"
        property_name, metadata_str = self.generate_custom_metadata(file_name)
        uploaded_entity_v1 = step.upload_blob_to_data_repo(
            content=content,
            target_path=file_name,
            metadata=metadata_str,
        )
        content_v2 = random_string()
        uploaded_entity_v2 = step.upload_blob_to_data_repo(content=content_v2, target_path=file_name)

        if data_repo_configuration == "Minerva":
            assert not self.assert_entity_link_with_metadata(step, property_name, uploaded_entity_v2)
            assert self.assert_entity_link_with_metadata(step, property_name, uploaded_entity_v1, version="001.001")
            entity_001002 = step.get_data_repository_entity_handle(minerva_path=file_name, version="001.002")
            assert not self.assert_entity_link_with_metadata(step, property_name, entity_001002, version="001.002")
        else:
            remote_path = uploaded_entity_v1.opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
            assert not self.validate_filesystem_metadata(function_project, remote_path, "001")
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.001", property_name)
            assert not self.validate_filesystem_metadata(function_project, remote_path, "001.002")

        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name) == content_v2
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001") == content_v2
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.001") == content
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.002") == content_v2

    def test_reupload_same_file_with_new_content_and_same_metadata(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        random_string: Callable[[], str],
    ):
        """Test that when uploading the same file with new content and the same metadata, Minerva links both versions
        of the file with the same metadata.
        """
        step = function_project.project.steps.data_repository_step

        file_name = "my_data.txt"
        property_name, metadata_str = self.generate_custom_metadata(file_name)
        content = random_string()
        uploaded_entity_v1 = step.upload_blob_to_data_repo(
            content=content,
            target_path=file_name,
            metadata=metadata_str,
        )

        content_v2 = random_string()
        uploaded_entity_v2 = step.upload_blob_to_data_repo(
            content=content_v2,
            target_path=file_name,
            metadata=metadata_str,
        )

        if data_repo_configuration == "Minerva":
            assert self.assert_entity_link_with_metadata(step, property_name, uploaded_entity_v2)
            assert self.assert_entity_link_with_metadata(step, property_name, uploaded_entity_v1, version="001.001")
            entity_001002 = step.get_data_repository_entity_handle(minerva_path=file_name, version="001.002")
            assert self.assert_entity_link_with_metadata(step, property_name, entity_001002, version="001.002")
        else:
            remote_path = uploaded_entity_v1.opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
            assert self.validate_filesystem_metadata(function_project, remote_path, "001", property_name)
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.001", property_name)
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.002", property_name)
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001") == content_v2
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.001") == content
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.002") == content_v2

    def test_reupload_same_file_with_new_content_and_new_metadata(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        random_string: Callable[[], str],
    ):
        """Test that when uploading the same file with new content and new metadata, Minerva links the new metadata to
        the new version, and keeps the old version linked with the old metadata.
        """
        step = function_project.project.steps.data_repository_step

        file_name = "my_data.txt"
        content = random_string()
        property_name, metadata_str = self.generate_custom_metadata(file_name)
        uploaded_entity_v1 = step.upload_blob_to_data_repo(
            content=content,
            target_path=file_name,
            metadata=metadata_str,
        )

        content_v2 = random_string()
        property_name_v2, metadata_str_v2 = self.generate_custom_metadata(file_name)
        uploaded_entity_v2 = step.upload_blob_to_data_repo(
            content=content_v2,
            target_path=file_name,
            metadata=metadata_str_v2,
        )

        if data_repo_configuration == "Minerva":
            assert not self.assert_entity_link_with_metadata(step, property_name, uploaded_entity_v2)
            assert self.assert_entity_link_with_metadata(step, property_name_v2, uploaded_entity_v2)
            assert self.assert_entity_link_with_metadata(step, property_name, uploaded_entity_v1, version="001.001")
            assert not self.assert_entity_link_with_metadata(
                step,
                property_name_v2,
                uploaded_entity_v1,
                version="001.001",
            )
            entity_001002 = step.get_data_repository_entity_handle(minerva_path=file_name, version="001.002")
            assert not self.assert_entity_link_with_metadata(step, property_name, entity_001002, version="001.002")
            assert self.assert_entity_link_with_metadata(step, property_name_v2, entity_001002, version="001.002")
        else:
            remote_path = uploaded_entity_v1.opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
            assert self.validate_filesystem_metadata(function_project, remote_path, "001", property_name_v2)
            assert not self.validate_filesystem_metadata(function_project, remote_path, "001", property_name)
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.001", property_name)
            assert not self.validate_filesystem_metadata(
                function_project,
                remote_path,
                "001.001",
                property_name_v2,
            )
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.002", property_name_v2)
            assert not self.validate_filesystem_metadata(function_project, remote_path, "001.002", property_name)

        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001") == content_v2
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.001") == content
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.002") == content_v2

    def test_reupload_same_file_with_same_content_and_new_metadata(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        data_repo_configuration: str,
        random_string: Callable[[], str],
    ):
        """Test that when uploading the same file with new metadata, Minerva links the new metadata to version 001 and
        generates a new identical version 001.001 with the same new metadata. The previous metadata is not
        linked to any version. A version 001.002 is not generated.
        """
        step = function_project.project.steps.data_repository_step

        file_name = "my_data.txt"
        property_name, metadata_str = self.generate_custom_metadata(file_name)
        content = random_string()
        uploaded_entity_v1 = step.upload_blob_to_data_repo(
            content=content,
            target_path=file_name,
            metadata=metadata_str,
        )

        property_name_v2, metadata_str_v2 = self.generate_custom_metadata(file_name)
        uploaded_entity_v2 = step.upload_blob_to_data_repo(
            content=content,
            target_path=file_name,
            metadata=metadata_str_v2,
        )

        if data_repo_configuration == "Minerva":
            assert not self.assert_entity_link_with_metadata(step, property_name, uploaded_entity_v1)
            assert not self.assert_entity_link_with_metadata(step, property_name_v2, uploaded_entity_v1)
            assert not self.assert_entity_link_with_metadata(step, property_name, uploaded_entity_v2)
            assert self.assert_entity_link_with_metadata(step, property_name_v2, uploaded_entity_v2)
        else:
            remote_path = uploaded_entity_v1.opaque_identifier.split("?version=")[0].removeprefix("datarepo//")
            assert self.validate_filesystem_metadata(function_project, remote_path, "001", property_name_v2)
            assert not self.validate_filesystem_metadata(function_project, remote_path, "001", property_name)
            assert self.validate_filesystem_metadata(function_project, remote_path, "001.001", property_name_v2)
            assert not self.validate_filesystem_metadata(function_project, remote_path, "001.001", property_name)
            assert not self.validate_filesystem_metadata(function_project, remote_path, "001.002")

        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001") == content
        assert step.fetch_blob_content_from_data_repo(minerva_path=file_name, version="001.001") == content
        assert step.get_data_repository_entity_handle(minerva_path=file_name, version="001.002") == NO_ENTITY

    def test_upload_directory_with_associated_metadata_raises_error(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
    ):
        """Test that uploading a directory with metadata raises an exception."""
        step = function_project.project.steps.data_repository_step

        dir_name = "my_directory"
        with pytest.raises(InternalSolutionException, match="Can't upload metadata for a directory."):
            step.upload_small_directory_to_data_repo(target_path=dir_name, metadata="test metadata")

    def test_access_data_repo_entity_handle_from_rest_api(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
    ):
        """Test that EntityHandle stored within the data repository storage scope
        can be accessed using the /blobs/entity-name endpoint.
        """
        step = function_project.project.steps.data_repository_step
        step.upload_blob_to_data_repo()
        entity_url = step.get_entity_url("data_repo_handle")
        response = httpx2.get(entity_url, timeout=90)
        assert response.text == "hello world!"


@pytest.mark.parametrize(
    "data_repo_configuration",
    [
        pytest.param("Minerva", marks=pytest.mark.use_minerva),
    ],
    indirect=True,
)
@pytest.mark.usefixtures("data_repo_configuration")
class TestImpersonation:
    """Test minerva impersonation feature.
    To make those test working, a new user named "test" must be created in minerva:
    Administration > Users > create new user
    (check logon enabled)

    On the server where minerva is running, the SAFServer.cer file within tests/e2e/minerva_oauth/ must be added to
    <minerva_install_dir>/OAuthServer/App_Data/Certificates/SAFServer.cer
    Then <minerva_install_dir>/OAuthServer/OAuth.config must be modified with
    a new <clientRegistry>:
    ``
    <clientRegistry id="SAFServer" enabled="true">
        <secrets>
          <secret type="JwtBearerAssertionServerSecret">
            <certificate filePath="App_Data/Certificates/SAFServer.cer">
            </certificate>
          </secret>
        </secrets>
        <allowedScopes>
          <scope name="Innovator">
          </scope>
        </allowedScopes>
        <allowedGrantTypes>
          <grantType name="impersonate">
          </grantType>
        </allowedGrantTypes>
        <tokenLifetime accessTokenLifetime="3600">
        </tokenLifetime>
      </clientRegistry>
    ``
    """

    @pytest.fixture(scope="class", autouse=True)
    def impersonation_config(
        self,
        minerva_settings: dict[str, str],
        session_glow: GlowDesktopProcess[DataRepositorySolution],
        temp_upload_root: str,
        session_idp_mock_server: str,
    ):
        minerva_settings["GLOW_AUTH_ISSUER_URL"] = session_idp_mock_server
        minerva_settings["ANS_MINERVA_AUTH__CERTCONFIG"] = str(E2E_TESTS_DIR / "minerva_oauth" / "oauth.config")
        session_glow.change_configuration(EnvVarDebug, restart=False)
        session_glow.change_configuration(
            MinervaDataRepoConfiguration,
            temp_upload_root=temp_upload_root,
            minerva_settings=minerva_settings,
        )
        yield
        session_glow.configure_default_execution()

    def test_no_auth_header_does_not_impersonate(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
    ):
        """Test that using minerva data repository without auth header does not use
        impersonation.
        """
        step = function_project.project.steps.data_repository_step
        assert step.upload_blob_to_data_repo() != NO_ENTITY

    def test_use_impersonation_wrong_user(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        session_idp_mock_server: str,
    ):
        """Test that using minerva data repository with auth header
        makes use of the impersonation.
        """
        function_project.client.http_client.headers["Authorization"] = "Bearer fake_jwt_token"
        # using an unknown user, simply to trigger an error and see that impersonation is used
        # unlike the no_auth_header above test
        r = httpx2.patch(f"{session_idp_mock_server}/admin", json={"user": "unknown"})
        r.raise_for_status()
        step = function_project.project.steps.data_repository_step
        with pytest.raises(InternalSolutionException, match="Invalid username"):
            step.upload_blob_to_data_repo()

    def test_use_impersonation_existing_user(
        self,
        function_project: ProjectFixture[DataRepositorySolution],
        session_idp_mock_server: str,
    ):
        """Test that using minerva data repository with auth header
        impersonates minerva with username from user info.
        """
        function_project.client.http_client.headers["Authorization"] = "Bearer fake_jwt_token"
        r = httpx2.patch(f"{session_idp_mock_server}/admin", json={"user": "test"})
        r.raise_for_status()
        step = function_project.project.steps.data_repository_step
        assert step.upload_blob_to_data_repo() != NO_ENTITY


@pytest.fixture
def fake_impersonation_config(
    request: pytest.FixtureRequest,
    minerva_settings: dict[str, str],
    session_glow: GlowDesktopProcess[DataRepositorySolution],
    temp_upload_root: str,
    tmp_path: Path,
):
    # We don't actually need Minerva or Minerva CLI for the followingtests.
    minerva_cli = tmp_path / "minerva_cli"
    minerva_cli.touch()
    minerva_settings["ANS_MINERVA_CLI"] = minerva_cli.as_posix()
    new_config = getattr(request, "param", {})
    minerva_settings.update(new_config)
    _ = session_glow.change_configuration(EnvVarDebug, restart=False)
    _ = session_glow.change_configuration(
        MinervaDataRepoConfiguration,
        temp_upload_root=temp_upload_root,
        minerva_settings=minerva_settings,
    )
    yield new_config
    session_glow.configure_default_execution()


@pytest.mark.parametrize(
    "fake_impersonation_config",
    [
        {
            "ANS_MINERVA_AUTH__CERTCONFIG": str(E2E_TESTS_DIR / "minerva_oauth" / "oauth.config"),
        },
    ],
    indirect=True,
)
def test_minerva_impersonation_auth_unconfigured(
    dummy_jwt_token: str,
    session_glow: GlowDesktopProcess[DataRepositorySolution],
    function_project: ProjectFixture[DataRepositorySolution],
    fake_impersonation_config: dict[str, str | None],  # pyright: ignore[reportUnusedParameter]
):
    """Test that user from access token is used for Minerva impersonation even if GLOW is not configured with any AUTH
    env var.
    """
    # No header token
    step = function_project.project.steps.data_repository_step
    with pytest.raises(InternalSolutionException):
        _ = step.upload_blob_to_data_repo()
    assert session_glow.text_in_output("No authorization header was included in the request.", "api")
    assert not session_glow.text_in_output("Logging to minerva by impersonating user: admin.", "api")

    # With header token, but no auth configured
    function_project.client.http_client.headers["Authorization"] = f"Bearer {dummy_jwt_token}"
    step = function_project.project.steps.data_repository_step
    with pytest.raises(InternalSolutionException):
        _ = step.upload_blob_to_data_repo()
    assert session_glow.text_in_output("The validation of the access token was skipped.", "api")
    assert session_glow.text_in_output("User info obtained from decoded token.", "api")
    assert session_glow.text_in_output("Logging to minerva by impersonating user: admin.", "api")


@pytest.mark.parametrize(
    "fake_impersonation_config",
    [
        {
            "ANS_MINERVA_AUTH__CERTCONFIG": None,
        },
        {
            "ANS_MINERVA_AUTH__CERTCONFIG": str(E2E_TESTS_DIR / "minerva_oauth" / "fake_oauth.config"),
        },
        {
            "ANS_MINERVA_AUTH__CERTCONFIG": str(E2E_TESTS_DIR / "minerva_oauth" / "oauth.config"),
            "ANS_MINERVA_AUTH__DATABASE": None,
        },
    ],
    ids=["no_certconfig", "wrong_certconfig", "no_database"],
    indirect=True,
)
def test_minerva_impersonation_missing_or_misconfigured_env_var_errors(
    dummy_jwt_token: str,
    function_project: ProjectFixture[DataRepositorySolution],
    fake_impersonation_config: dict[str, str | None],
):
    """Test the errors that are raised when impersonation environment variables are missing or misconfigured."""
    # With header token, but no auth configured
    function_project.client.http_client.headers["Authorization"] = f"Bearer {dummy_jwt_token}"
    step = function_project.project.steps.data_repository_step
    if "ANS_MINERVA_AUTH__DATABASE" in fake_impersonation_config:
        error_msg = "The environment variable 'ANS_MINERVA_AUTH__DATABASE' must be defined when using impersonation."
    elif fake_impersonation_config["ANS_MINERVA_AUTH__CERTCONFIG"] is None:
        error_msg = "The environment variable 'ANS_MINERVA_AUTH__CERTCONFIG' must be defined when using impersonation."
    else:
        error_msg = "The OAuth certificate configuration file specified in ANS_MINERVA_AUTH__CERTCONFIG does not exist"
    with pytest.raises(InternalSolutionException, match=error_msg):
        _ = step.upload_blob_to_data_repo()
