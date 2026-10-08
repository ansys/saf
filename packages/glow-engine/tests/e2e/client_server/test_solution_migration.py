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

from collections.abc import Callable
from io import BytesIO
import json
from pathlib import Path
import shutil
from typing import TypeVar
import zipfile

import pytest

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import FieldState, Solution
from ansys.saf.testing.solution.end_to_end import (
    EnableAutomaticProjectMigrationConfig,
    GlowBaseProcess,
    LogContainerManager,
    ProjectFixture,
)
from tests.mocks.solutions import (
    modify_add_field_with_migration,
    modify_add_step_with_migration,
    modify_apply_migration_to_solution_with_migration,
    modify_display_name_with_migration,
    modify_field_default_value_based_on_another_field_with_migration,
    modify_field_type_incompatible_with_migration,
    modify_field_validator_incompatible_with_migration,
    modify_original_including_migrations,
    modify_remove_field_with_migration,
    modify_remove_step_with_migration,
    modify_with_failing_migration,
    modify_with_migration_and_validation,
    modify_with_migration_and_validation_check_order,
    modify_with_three_migrations_missing_first,
    modify_with_two_migrations,
)

T = TypeVar("T", bound=Solution)

pytestmark = pytest.mark.parametrize(
    "solution_type",
    [modify_original_including_migrations.OriginalSolution],
    indirect=True,
)


def _upgrade_or_import_project(
    source: str,
    glow_client: Client[T],
    project_id: str,
    safx_path: Path,
):
    project = (
        glow_client.upgrade_project(f"projects/{project_id}")
        if source == "db"
        else glow_client.import_project(safx_path, "MySolution")
    )
    return project


Orig = TypeVar("Orig", bound=Solution)
Mod = TypeVar("Mod", bound=Solution)


@pytest.fixture(params=["db", "import"])
def project_migrator(
    request: pytest.FixtureRequest,
    function_project: ProjectFixture[Orig],
    run_glow: Callable[[type[Mod], Path], GlowBaseProcess[Mod]],
    tmp_solutions_dir: dict[type[Mod], Path],
    get_glow_client: Callable[[GlowBaseProcess[Mod]], Client[Mod]],
    safx_path: Path,
) -> Callable[[type[Mod], bool], Mod]:
    def _project_migrator(mod: type[Mod], automatic_project_migration: bool = False) -> Mod:
        glow_proc = run_glow(mod, tmp_solutions_dir[mod])
        if automatic_project_migration:
            glow_proc.change_configuration(EnableAutomaticProjectMigrationConfig)
        assert glow_proc is not None
        glow_client = get_glow_client(glow_proc)
        project = _upgrade_or_import_project(
            request.param,
            glow_client,
            function_project.project_id,
            safx_path,
        )

        return project

    return _project_migrator


class TestSolutionMigrations:
    def test_solution_display_name_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_display_name_with_migration.OriginalSolution]],
            modify_display_name_with_migration.OriginalSolution,
        ],
        tmp_path: Path,
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version that has a
        different display name through a migration transformation.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.solution_schema["properties"]["display_name"]["default"] == "Original"

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_display_name_with_migration.OriginalSolution)

        # THEN: the project is updated to the newer solution version and has the new display name
        project.export(tmp_path)
        exported_project = tmp_path / f"{project.project_display_name}.safx"
        assert exported_project.is_file()
        with zipfile.ZipFile(BytesIO(exported_project.read_bytes()), "r") as archive:
            sap_file = [f for f in archive.namelist() if f.endswith(".sap")][0]
            project_info = json.loads(archive.read(sap_file))
        assert project_info["solution"]["version"] == 3
        assert project_info["solution"]["display_name"] == "NotOriginal"

    def test_add_field_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_add_field_with_migration.OriginalSolution]],
            modify_add_field_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version that includes a
        new field through a migration transformation.
        """
        # GIVEN: a project of an initial version of a solution
        assert not hasattr(function_project.project.steps.second_step, "extra_value")

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_add_field_with_migration.OriginalSolution)

        # THEN: the project is updated to the newer solution version including the new field
        assert project.steps.second_step.extra_value == "my_value"
        assert project.steps.second_step.state["extra_value"] == FieldState.UPTODATE

    def test_remove_field_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_remove_field_with_migration.OriginalSolution]],
            modify_remove_field_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version that removed and
        old field through a migration transformation.
        """
        # GIVEN: a project of an initial version of a solution
        assert getattr(function_project.project.steps.first_step, "unused_value", None) == 0.5

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_remove_field_with_migration.OriginalSolution)

        # THEN: the project is updated to the newer solution version without the old field
        assert getattr(project.steps.first_step, "unused_value", None) is None

    def test_add_step_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_add_step_with_migration.OriginalSolution]],
            modify_add_step_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version that adds a new
        step through a migration transformation.
        """
        # GIVEN: a project of an initial version of a solution
        assert not hasattr(function_project.project.steps, "third_step")

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_add_step_with_migration.OriginalSolution)

        # THEN: the project is updated to the newer solution version including the new step
        assert project.steps.third_step.x == 88
        assert project.steps.third_step.state["x"] == FieldState.OUTOFDATE

    def test_remove_step_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_remove_step_with_migration.OriginalSolution]],
            modify_remove_step_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version that removes an old
        step through a migration transformation.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.project.steps.second_step.x == 88
        assert function_project.project.steps.second_step.state["x"] == FieldState.UPTODATE

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_remove_step_with_migration.OriginalSolution)

        # THEN: the project is updated to the newer solution version without the old step
        assert getattr(project.steps, "second_step", None) is None

    def test_modify_field_default_value_based_on_another_field_with_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_field_default_value_based_on_another_field_with_migration.OriginalSolution]],
            modify_field_default_value_based_on_another_field_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version that modifies the
        default value of a field based on another step field through a migration transformation.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.project.steps.first_step.x == 88

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_field_default_value_based_on_another_field_with_migration.OriginalSolution)

        # THEN: the project is updated to the newer solution version and the field has a new default
        assert project.steps.first_step.x == 89

    def test_modify_incompatible_field_type_with_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_field_type_incompatible_with_migration.OriginalSolution]],
            modify_field_type_incompatible_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version that modifies the
        type of a step field to an incompatible type through a migration transformation.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.project.steps.first_step.my_string == "my_string"

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_field_type_incompatible_with_migration.OriginalSolution)

        # THEN: the project is updated to the newer solution version and the field is of the new type
        assert project.steps.first_step.my_string == 5

    def test_modify_field_default_to_pass_validator_with_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_field_validator_incompatible_with_migration.OriginalSolution]],
            modify_field_validator_incompatible_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version that modifies the
        default value of a step field in order to pass a new field validator through a migration transformation.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.project.steps.first_step.unused_value == 0.5

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_field_validator_incompatible_with_migration.OriginalSolution)

        # THEN: the project is updated to the newer solution version and the field has the new default
        #       that passes the validator
        assert project.steps.first_step.unused_value == 2

    def test_update_solution_version_with_two_migrations(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_with_two_migrations.OriginalSolution]],
            modify_with_two_migrations.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version through
        several consecutive migration transformations.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.project.steps.first_step.x == 88
        assert function_project.project.steps.first_step.my_string == "my_string"
        assert not hasattr(function_project.project.steps.first_step, "is_new_field")

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_with_two_migrations.OriginalSolution)

        # THEN: the project is updated to the newer solution version including the changes of both migrations
        assert project.steps.first_step.x == 100
        assert project.steps.first_step.my_string == 5
        assert project.steps.first_step.is_new_field

    def test_update_solution_version_creates_project_files_dir(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_add_step_with_migration.OriginalSolution]],
            modify_add_step_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism creates the project files directory if it does not exist so that
        it can be used in the migration transformations.
        """
        # GIVEN: a project of an initial version of a solution without project files directory
        if function_project.project_files_dir.is_dir():
            shutil.rmtree(function_project.project_files_dir)

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_add_step_with_migration.OriginalSolution)

        # THEN: the project files directory now exists
        assert project._project_files_dir.is_dir()  # type: ignore

    def test_upgrade_solution_version_with_failing_migration_preserves_project_files_dir(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        run_glow: Callable[
            [type[modify_with_failing_migration.OriginalSolution], Path],
            GlowBaseProcess[modify_with_failing_migration.OriginalSolution],
        ],
        tmp_solutions_dir: dict[type[modify_with_failing_migration.OriginalSolution], Path],
        get_glow_client: Callable[
            [GlowBaseProcess[modify_with_failing_migration.OriginalSolution]],
            Client[modify_with_failing_migration.OriginalSolution],
        ],
    ):
        """Test that the solution migration mechanism preserves the original contents of the project files directory
        when a migration transformation fails.
        """
        # GIVEN: a project of an initial version of a solution having a file in its project directory
        new_file = function_project.project_files_dir / "new_file.txt"
        new_file.touch()

        # WHEN: failing to upgrade to a newer version of the solution
        glow_proc = run_glow(
            modify_with_failing_migration.OriginalSolution,
            tmp_solutions_dir[modify_with_failing_migration.OriginalSolution],
        )
        glow_client = get_glow_client(glow_proc)
        response = glow_client.http_client.post(
            f"{glow_proc.base_api_url}/projects/{function_project.project_id}:upgrade",
        )
        assert response.status_code == 422
        assert (
            "Could not migrate: migration transformation MigrateWithError failed with error: 'File not found'"
            in response.text
        )

        # THEN: The project directory is preserved in the original state
        assert new_file.is_file()

    def test_get_original_solution_project_with_updated_compatible_solution(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        run_glow: Callable[
            [type[modify_display_name_with_migration.OriginalSolution], Path],
            GlowBaseProcess[modify_display_name_with_migration.OriginalSolution],
        ],
        get_glow_client: Callable[
            [GlowBaseProcess[modify_display_name_with_migration.OriginalSolution]],
            Client[modify_display_name_with_migration.OriginalSolution],
        ],
        tmp_solutions_dir: dict[type[modify_display_name_with_migration.OriginalSolution], Path],
    ):
        """Test that GETTING a project of an older solution version from a more up-to-date solution version that
        includes migration transformations fails even if both versions are compatible according to the Solution class
        validators.
        """
        # GIVEN: a project of an initial version of a solution
        # WHEN: GETTING the project from an updated solution without upgrading/importing
        glow_proc = run_glow(
            modify_display_name_with_migration.OriginalSolution,
            tmp_solutions_dir[modify_display_name_with_migration.OriginalSolution],
        )
        glow_client = get_glow_client(glow_proc)
        response = glow_client.http_client.get(f"{glow_proc.base_api_url}/projects/{function_project.project_id}")

        # THEN: A 422 UnprocessableEntityError is raised
        assert response.status_code == 422

    def test_steps_works_after_migration(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_add_step_with_migration.OriginalSolution]],
            modify_add_step_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution resulting from the migration process can be used."""
        # GIVEN: a project of an initial version of a solution
        assert not hasattr(function_project.project.steps, "third_step")

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_add_step_with_migration.OriginalSolution)

        # THEN: and the project can be used
        step = project.steps.first_step
        step.copy_x_to_string()
        assert step.my_string == "88"
        step = project.steps.third_step
        step.generate_random_int()
        assert 0 <= step.x <= 99

    @pytest.mark.parametrize("source", ["db", "import"])
    @pytest.mark.parametrize(
        "automatic_project_migration",
        [True, False],
        ids=["automatic_project_migration_enabled", "automatic_project_migration_disabled"],
    )
    def test_update_solution_through_migration_and_validation(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        run_glow: Callable[
            [type[modify_with_migration_and_validation.OriginalSolution], Path],
            GlowBaseProcess[modify_with_migration_and_validation.OriginalSolution],
        ],
        get_glow_client: Callable[
            [GlowBaseProcess[modify_with_migration_and_validation.OriginalSolution]],
            Client[modify_with_migration_and_validation.OriginalSolution],
        ],
        safx_path: Path,
        source: str,
        automatic_project_migration: bool,
        tmp_solutions_dir: dict[type[modify_with_migration_and_validation.OriginalSolution], Path],
    ):
        """
        Test that the project migration mechanism allows the migration of an initial project through the
        migration transformations and the Solution class automatic migration in a single call to the API.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.project.steps.first_step.my_string == "my_string"
        assert function_project.project.steps.first_step.x == 88

        # WHEN: migrating it to a newer version of the solution
        glow_proc = run_glow(
            modify_with_migration_and_validation.OriginalSolution,
            tmp_solutions_dir[modify_with_migration_and_validation.OriginalSolution],
        )
        if automatic_project_migration:
            glow_proc.change_configuration(EnableAutomaticProjectMigrationConfig)
        glow_client = get_glow_client(glow_proc)
        if source == "db":
            response = glow_client.http_client.post(
                f"{glow_proc.base_api_url}/projects/{function_project.project_id}:upgrade",
            )
        else:
            with safx_path.open("rb") as f:
                response = glow_client.http_client.post(
                    f"{glow_proc.base_api_url}/projects:import",
                    files={"safx_file": f},
                    data={"display_name": "My Solution"},
                )
        if automatic_project_migration:
            # THEN: the project is updated to the newer solution version and all the changes have
            #       been applied by either a migration or the Solution class validation
            assert response.status_code == 200
            project_info = response.json()
            project = glow_client.get_project(project_info["name"])
            assert project.steps.first_step.my_string == 88
            assert project.steps.first_step.extra_int == 50
        else:
            # THEN: the process fails because auto matic schema upgrade is disabled and there is an extra field in the
            #       new solution definition
            assert response.status_code == 422
            assert "Step 'first_step' is missing fields ['extra_int'], and contains extra fields []" in response.text

    @pytest.mark.parametrize("source", ["db", "import"])
    def test_update_solution_through_migration_and_validation_migrations_are_first(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        run_glow: Callable[
            [type[modify_with_migration_and_validation_check_order.OriginalSolution], Path],
            GlowBaseProcess[modify_with_migration_and_validation_check_order.OriginalSolution],
        ],
        get_glow_client: Callable[
            [GlowBaseProcess[modify_with_migration_and_validation_check_order.OriginalSolution]],
            Client[modify_with_migration_and_validation_check_order.OriginalSolution],
        ],
        safx_path: Path,
        source: str,
        tmp_solutions_dir: dict[type[modify_with_migration_and_validation_check_order.OriginalSolution], Path],
    ):
        """Test that the solution migration mechanism allows the update of an initial solution through the
        migration transformations and the Solution class validators (in this order) in a single call to the API.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.project.steps.first_step.my_string == "my_string"
        assert function_project.project.steps.first_step.x == 88

        # WHEN: migrating it to a newer version of the solution
        glow_proc = run_glow(
            modify_with_migration_and_validation_check_order.OriginalSolution,
            tmp_solutions_dir[modify_with_migration_and_validation_check_order.OriginalSolution],
        )
        glow_client = get_glow_client(glow_proc)
        # THEN: the process fails because migration transformations are applied first and field extra_int is not yet
        # defined
        if source == "db":
            response = glow_client.http_client.post(
                f"{glow_proc.base_api_url}/projects/{function_project.project_id}:upgrade",
            )
        else:
            with safx_path.open("rb") as f:
                response = glow_client.http_client.post(
                    f"{glow_proc.base_api_url}/projects:import",
                    files={"safx_file": f},
                    data={"display_name": "My Solution"},
                )
        assert response.status_code == 422
        assert (
            "Could not migrate: migration transformation MigrateFieldType failed with error: ''extra_int''"
            in response.text
        )

    @pytest.mark.parametrize("source", ["db", "import"])
    def test_update_solution_with_too_old_version(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        run_glow: Callable[
            [type[modify_with_three_migrations_missing_first.OriginalSolution], Path],
            GlowBaseProcess[modify_with_three_migrations_missing_first.OriginalSolution],
        ],
        get_glow_client: Callable[
            [GlowBaseProcess[modify_with_three_migrations_missing_first.OriginalSolution]],
            Client[modify_with_three_migrations_missing_first.OriginalSolution],
        ],
        safx_path: Path,
        source: str,
        tmp_solutions_dir: dict[type[modify_with_three_migrations_missing_first.OriginalSolution], Path],
    ):
        # GIVEN: a project of an initial version of a solution
        # WHEN: migrating it to a newer version of the solution
        glow_proc = run_glow(
            modify_with_three_migrations_missing_first.OriginalSolution,
            tmp_solutions_dir[modify_with_three_migrations_missing_first.OriginalSolution],
        )
        glow_client = get_glow_client(glow_proc)
        # THEN: the process fails because no migration transformation applies to the version of the solution to update
        if source == "db":
            response = glow_client.http_client.post(
                f"{glow_proc.base_api_url}/projects/{function_project.project_id}:upgrade",
            )
        else:
            with safx_path.open("rb") as f:
                response = glow_client.http_client.post(
                    f"{glow_proc.base_api_url}/projects:import",
                    files={"safx_file": f},
                    data={"display_name": "My Solution"},
                )
        assert response.status_code == 500
        assert (
            "The solution definition is invalid: the solution version of the project (2) is lower than the lowest "
            "migratable version (3)"
        ) in response.text

    def test_update_solution_that_has_migrations(
        self,
        function_project: ProjectFixture[modify_original_including_migrations.OriginalSolution],
        project_migrator: Callable[
            [type[modify_apply_migration_to_solution_with_migration.OriginalSolution]],
            modify_apply_migration_to_solution_with_migration.OriginalSolution,
        ],
    ):
        """Test that the solution migration mechanism allows a migration to a newer solution version through
        several consecutive migration transformations.
        """
        # GIVEN: a project of an initial version of a solution
        assert function_project.project.steps.first_step.unused_value == 0.5

        # WHEN: migrating it to a newer version of the solution
        project = project_migrator(modify_apply_migration_to_solution_with_migration.OriginalSolution)

        # The migrations field of the solution to update was overwritten by the latest solution definition,
        # and only the migration from version 2 to 3 was applied
        new_file = function_project.project_files_dir.parent / project.project_id / "new_file.py"
        assert not new_file.is_file()
        assert project.steps.first_step.unused_value == 2

    @pytest.mark.parametrize(
        "automatic_project_migration",
        [True, False],
        ids=["automatic_project_migration_enabled", "automatic_project_migration_disabled"],
    )
    def test_log_warning_when_using_migrations_with_automatic_project_migration_enabled(
        self,
        project_migrator: Callable[
            [type[modify_display_name_with_migration.OriginalSolution], bool],
            modify_display_name_with_migration.OriginalSolution,
        ],
        session_log_manager: LogContainerManager,
        automatic_project_migration: bool,
    ):
        """Test that the solution migration mechanism logs a warning when running a migration if
        GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION is enabled.
        """
        # GIVEN: a project of an initial version of a solution
        # WHEN: migrating it to a newer version of the solution with GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION enabled
        #       and using migrations.
        project_migrator(modify_display_name_with_migration.OriginalSolution, automatic_project_migration)

        # THEN: the expected log line is shown.
        expected_log_line = "Applying a migration transformation while automatic project migration is enabled."
        log_lines = session_log_manager.containers["Desktop_glow_proc_api_1"].output
        log_line_found = any(expected_log_line in line for line in log_lines)
        if automatic_project_migration:
            assert log_line_found
        else:
            assert not log_line_found
