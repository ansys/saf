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
from pathlib import Path

import pytest

from ansys.saf.testing.solution.end_to_end import (
    GlowBaseProcess,
    HpsMissingAuth,
    HpsUserPswdAuth,
)
from tests.mocks.solution_with_hps_python_script.hps_parametric_study import ParametricStudySolution
from tests.mocks.solutions import (
    modify_file_add_entity_handle_for_directory,
    modify_file_add_entity_handle_in_sub_directory,
    modify_file_combine_migration_and_automatic_upgrade,
    modify_file_extract_from_entity_handle,
    modify_file_original,
    modify_file_set_entity_handle_to_no_entity,
)

pytestmark = pytest.mark.parametrize("solution_type", [modify_file_original.OriginalSolution], indirect=True)


@pytest.fixture(scope="class")
def enable_hps_auth(session_glow: GlowBaseProcess[ParametricStudySolution]) -> Generator[None, None, None]:
    session_glow.change_configuration(HpsUserPswdAuth)
    yield
    session_glow.change_configuration(HpsMissingAuth)


def _assert_contains_no_files(entity: Path) -> None:
    assert entity.exists()
    assert not entity.is_file()

    for i in entity.iterdir():
        _assert_contains_no_files(i)


class TestFileMigrations:
    def test_get_path_from_entity_handle(
        self,
        project_initializer_and_migrator: Callable[
            [
                type[modify_file_extract_from_entity_handle.OriginalSolution],
                Callable[[modify_file_original.OriginalSolution], None],
            ],
            modify_file_extract_from_entity_handle.OriginalSolution,
        ],
    ):
        """
        Test that the ``MigrationContext`` ``get_path_from_entity_handle``
        method returns the path to a file referenced by an entity handle.
        """

        def initializer(original_solution: modify_file_original.OriginalSolution):
            original_solution.steps.first_step.initialize()

        migrated_project = project_initializer_and_migrator(
            modify_file_extract_from_entity_handle.OriginalSolution,
            initializer,
        )

        assert migrated_project.steps.first_step.extracted_file_content == "new file content"

    def test_migration_to_entity_handle_with_relative_path(
        self,
        project_migrator: Callable[
            [type[modify_file_add_entity_handle_in_sub_directory.OriginalSolution]],
            modify_file_add_entity_handle_in_sub_directory.OriginalSolution,
        ],
    ):
        """
        Test that the ``MigrationContext`` ``create_entity_handle``
        can create a handle that will resolve to a file inside a subdirectory
        with a specific name.
        """
        migrated_project = project_migrator(modify_file_add_entity_handle_in_sub_directory.OriginalSolution)
        file = migrated_project.storage_scope.get_cached(migrated_project.steps.first_step.file_entity_handle)
        assert file.read_text() == "new file content"
        assert file.name == "xyz.txt"
        assert file.parent.name == "a"

    def test_migration_to_directory_entity_handle(
        self,
        project_migrator: Callable[
            [type[modify_file_add_entity_handle_for_directory.OriginalSolution]],
            modify_file_add_entity_handle_for_directory.OriginalSolution,
        ],
    ):
        """
        Test that the ``MigrationContext`` ``create_entity_handle``
        can create a handle that refers to a directory.
        """
        migrated_project = project_migrator(modify_file_add_entity_handle_for_directory.OriginalSolution)
        directory = migrated_project.storage_scope.get_cached(migrated_project.steps.first_step.directory_entity_handle)
        assert directory.is_dir()
        assert directory.name == "subdir"
        assert (directory / "new_file.txt").read_text() == "new file content"

    def test_garbage_collection_of_migration_results(
        self,
        project_initializer_and_migrator: Callable[
            [
                type[modify_file_set_entity_handle_to_no_entity.OriginalSolution],
                Callable[[modify_file_original.OriginalSolution], None],
            ],
            modify_file_set_entity_handle_to_no_entity.OriginalSolution,
        ],
    ):
        """
        Test that the import and upgrade operations remove entities that are no longer referenced
        by entity handle fields after project migration.
        """

        # this test assumes that the shared file system system is in use
        # so that get_cached will return a Path that is the source storage location of
        # an entity
        def initializer(original_solution: modify_file_original.OriginalSolution):
            original_solution.steps.first_step.initialize()

        project = project_initializer_and_migrator(
            modify_file_set_entity_handle_to_no_entity.OriginalSolution,
            initializer,
        )

        _assert_contains_no_files(project.storage_scope.get_storage_root().parent)

    @pytest.mark.parametrize(
        "automatic_project_migration",
        [True, False],
        ids=["automatic_project_migration_enabled", "automatic_project_migration_disabled"],
    )
    def test_file_migration_combined_with_automatic_upgrade(
        self,
        project_initializer_and_migrator: Callable[
            [
                type[modify_file_combine_migration_and_automatic_upgrade.OriginalSolution],
                Callable[[modify_file_original.OriginalSolution], None],
                bool,
                int,
                str,
            ],
            modify_file_combine_migration_and_automatic_upgrade.OriginalSolution,
        ],
        automatic_project_migration: bool,
    ):
        """
        Test that the project migration mechanism allows the migration of an initial project through the
        migration transformations and the Solution class automatic migration in a single call to the API.
        """

        def initializer(original_solution: modify_file_original.OriginalSolution):
            original_solution.steps.first_step.initialize()

        if automatic_project_migration:
            migrated_project = project_initializer_and_migrator(
                modify_file_combine_migration_and_automatic_upgrade.OriginalSolution,
                initializer,
                automatic_project_migration,
                200,
                "",
            )
            assert migrated_project.steps.first_step.extracted_file_content == "new file content"
            assert migrated_project.steps.first_step.extra_int == 89
        else:
            expected_error_message = "Step 'first_step' is missing fields ['extra_int'], and contains extra fields []"
            project_initializer_and_migrator(
                modify_file_combine_migration_and_automatic_upgrade.OriginalSolution,
                initializer,
                automatic_project_migration,
                422,
                expected_error_message,
            )
