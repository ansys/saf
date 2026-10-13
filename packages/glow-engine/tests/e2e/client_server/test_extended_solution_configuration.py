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
import json
from pathlib import Path
import sqlite3

import httpx2
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import BadRequestException, InternalSolutionException
from ansys.saf.testing.solution.end_to_end import (
    EnableOverwriteSolutionConfig,
    EnvVarDebug,
    GlowBaseProcess,
    ProjectFixture,
)
from tests.mocks.solutions.extended_solution_configuration import (
    ExtendedSolutionConfiguration,
    ExtendedSolutionConfigurationSolution,
)

pytestmark = pytest.mark.parametrize("solution_type", [ExtendedSolutionConfigurationSolution], indirect=True)


@pytest.fixture
def set_default_solution_configuration(
    session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
) -> Generator[None, None, None]:
    httpx2.put(
        f"{session_glow.base_api_url}/solution-configuration",
        json=ExtendedSolutionConfiguration().model_dump(),
    ).raise_for_status()
    yield
    httpx2.put(
        f"{session_glow.base_api_url}/solution-configuration",
        json=ExtendedSolutionConfiguration().model_dump(),
    ).raise_for_status()


class TestExtendedSolutionConfiguration:
    @pytest.mark.usefixtures("set_default_solution_configuration")
    def test_solution_config_read_and_write_using_rest_api(
        self,
        session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
    ):
        """Test that the extended solution configuration written by the solution developer can be read and modified
        using REST API. Modifications are persisted across application restarts.
        """
        response = httpx2.get(f"{session_glow.base_api_url}/solution-configuration")
        response.raise_for_status()
        assert response.json() == ExtendedSolutionConfiguration().model_dump()

        httpx2.put(
            f"{session_glow.base_api_url}/solution-configuration",
            json={
                "my_field": 5,
            },
        ).raise_for_status()

        response = httpx2.get(f"{session_glow.base_api_url}/solution-configuration")
        response.raise_for_status()
        assert (
            response.json()
            == ExtendedSolutionConfiguration(
                my_field=5,
            ).model_dump()
        )

        session_glow.restart()
        response = httpx2.get(f"{session_glow.base_api_url}/solution-configuration")
        assert (
            response.json()
            == ExtendedSolutionConfiguration(
                my_field=5,
            ).model_dump()
        )

    @pytest.mark.usefixtures("set_default_solution_configuration")
    def test_read_solution_config_from_within_transaction(
        self,
        session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
        function_project: ProjectFixture[ExtendedSolutionConfigurationSolution],
    ):
        """Test that the extended solution configuration written by the solution developer can be accessed within a
        transaction when added as parameter with the proper type.
        """
        step = function_project.project.steps.extended_solution_configuration_step

        transaction_output = step.read_extended_solution_configuration()
        assert transaction_output == ("ExtendedSolutionConfiguration", 0)

        httpx2.put(
            f"{session_glow.base_api_url}/solution-configuration",
            json={
                "my_field": 5,
            },
        ).raise_for_status()

        transaction_output = step.read_extended_solution_configuration()
        assert transaction_output == ("ExtendedSolutionConfiguration", 5)

    @pytest.mark.usefixtures("set_default_solution_configuration")
    def test_read_solution_config_from_client(
        self,
        session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
        function_project: ProjectFixture[ExtendedSolutionConfigurationSolution],
    ):
        """Test that the extended solution configuration written by the solution developer can be accessed from the
        client.
        """
        assert function_project.project.solution_configuration.__class__.__name__ == "ExtendedSolutionConfiguration"
        assert function_project.project.solution_configuration == ExtendedSolutionConfiguration()

        httpx2.put(
            f"{session_glow.base_api_url}/solution-configuration",
            json={
                "my_field": 5,
            },
        ).raise_for_status()

        assert function_project.project.solution_configuration.my_field == 5

    def test_read_solution_config_from_within_transaction_ignores_updates_during_transaction(
        self,
        tmp_path: Path,
        session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
        function_project: ProjectFixture[ExtendedSolutionConfigurationSolution],
    ):
        """Test that if the solution configuration is changed while a transaction that reads it is running, the
        transaction will not be affected by the change. The returned solution configuration is loaded at the beginning
        of a transaction and remains unchanged throughout it.
        """

        @retry(stop=stop_after_attempt(100), wait=wait_fixed(0.3))
        def wait_for_long_running_method(signal_file: Path):
            inside_transaction = signal_file.read_text() == "inside transaction"
            if not inside_transaction:
                raise TryAgain

        step = function_project.project.steps.extended_solution_configuration_step
        signal_file = tmp_path / "signal.txt"
        signal_file.touch()
        # WHEN: executing a long running method that reads the solution_configuration
        signal_file_method = step.wait_for_signal_file(signal_file=signal_file)
        # AND: making sure it is actually running
        wait_for_long_running_method(signal_file)
        # AND: modify the solution configuration during the long running and send signal to transaction to read it
        httpx2.put(
            f"{session_glow.base_api_url}/solution-configuration",
            json={
                "my_field": 5,
            },
        ).raise_for_status()
        signal_file.write_text("stop")
        # THEN: transaction ends and the values retrieved were not affected by the modification
        solution_configuration = signal_file_method.wait()
        assert solution_configuration == ExtendedSolutionConfiguration().model_dump()

    @pytest.mark.usefixtures("set_default_solution_configuration")
    def test_write_solution_config_from_within_transaction_does_nothing(
        self,
        function_project: ProjectFixture[ExtendedSolutionConfigurationSolution],
    ):
        """Test that the solution configuration accessed within a transaction is read-only. Trying to modify it does
        nothing.
        """
        step = function_project.project.steps.extended_solution_configuration_step

        _, my_field = step.read_extended_solution_configuration()
        assert my_field == 0
        step.change_solution_configuration(my_field=5)
        _, my_field = step.read_extended_solution_configuration()
        assert my_field == 0

    @pytest.mark.usefixtures("set_default_solution_configuration")
    def test_solution_config_schema_read(
        self,
        session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
    ):
        """Test that the solution configuration schema can be retrieved using the REST API."""
        expected_schema = ExtendedSolutionConfiguration.model_json_schema()
        response = httpx2.get(f"{session_glow.base_api_url}/solution-configuration/schema")
        response.raise_for_status()
        assert response.json() == expected_schema


@pytest.fixture
def change_solution_configuration(
    request: pytest.FixtureRequest,
    set_default_solution_configuration: None,
    session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
) -> Generator[str, None, None]:
    sqlite_db = session_glow.project_files_directory.parent / "glow.db"
    assert sqlite_db.is_file()

    modification_type = request.param
    new_config = ExtendedSolutionConfiguration().model_dump()
    if modification_type == "change_glow_version":
        new_config["glow_schema_version"] = 10
    elif modification_type == "change_solution_version":
        new_config["solution_schema_version"] = 10
    elif modification_type == "change_field_type":
        new_config["my_field"] = "hello"
    elif modification_type == "add_field":
        # so, stored config had one field less
        del new_config["my_field"]
    elif modification_type == "delete_field":
        # so, stored config had one extra field
        new_config["my_field_2"] = "hello"
    elif modification_type == "change_default_value":
        # so, stored value is different than new default
        new_config["my_field"] = new_config["my_field"] + 1
    new_config_str = json.dumps(new_config)

    with sqlite3.connect(str(sqlite_db)) as conn:
        conn.execute("""UPDATE solution_configuration SET configuration = ? WHERE id = 0""", (new_config_str,))
    session_glow.change_configuration(EnvVarDebug)

    yield modification_type

    with sqlite3.connect(str(sqlite_db)) as conn:
        conn.execute(
            """UPDATE solution_configuration SET configuration = ? WHERE id = 0""",
            (ExtendedSolutionConfiguration().model_dump_json(),),
        )
    session_glow.configure_default_execution()


def get_solution_config_from_db(session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution]):
    sqlite_db = session_glow.project_files_directory.parent / "glow.db"
    assert sqlite_db.is_file()
    with sqlite3.connect(str(sqlite_db)) as conn:
        results = conn.execute("""SELECT configuration FROM solution_configuration WHERE id = 0""")
        return json.loads(results.fetchone()[0])


@pytest.fixture
def revert_glow_configuration(
    session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
) -> Generator[None, None, None]:
    yield
    session_glow.configure_default_execution()


class TestUpgradeSolutionConfiguration:
    @pytest.mark.parametrize(
        "change_solution_configuration",
        ["change_glow_version", "change_solution_version", "change_field_type", "delete_field"],
        indirect=True,
    )
    @pytest.mark.usefixtures("revert_glow_configuration")
    def test_handle_breaking_changes_using_env_var(
        self,
        change_solution_configuration: str,
        function_project: ProjectFixture[ExtendedSolutionConfigurationSolution],
        session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
    ):
        """Test that some modifications of the solution configuration are considered breaking change and they
        raise an error when trying to access or modify it (either via rest aPI, transaction or client).
        Examples: changing glow_schema_version, changing solution_schema_version,
        changing field type to something incompatible, removing field.

        After setting the GLOW_OVERWRITE_SOLUTION_CONFIG env var, stored config is automatically replaced with new
        one and errors disappear.
        """
        # GIVEN: GLOW with incompatible solution configuration stored in DB
        stored_solution_config = get_solution_config_from_db(session_glow)
        if change_solution_configuration == "change_glow_version":
            assert stored_solution_config["glow_schema_version"] != ExtendedSolutionConfiguration().glow_schema_version
        elif change_solution_configuration == "change_solution_version":
            assert (
                stored_solution_config["solution_schema_version"]
                != ExtendedSolutionConfiguration().solution_schema_version
            )
        elif change_solution_configuration == "change_field_type":
            assert isinstance(stored_solution_config["my_field"], str)
            assert isinstance(ExtendedSolutionConfiguration().my_field, int)
        elif change_solution_configuration == "delete_field":
            assert "my_field_2" in stored_solution_config
            assert not hasattr(ExtendedSolutionConfiguration(), "my_field_2")
        else:
            pytest.fail("Wrong fixture configuration.")

        step = function_project.project.steps.extended_solution_configuration_step

        # WHEN: trying to read or modify solution configuration via transaction, REST API or Client API
        # THEN: raises exception
        exception_string = (
            "Client error '422 Unprocessable Content|Entity' for url "
            f"'http://localhost:{session_glow.solution_api_port}/solution-configuration'"
        )
        with pytest.raises(InternalSolutionException, match=exception_string):
            step.read_extended_solution_configuration()

        exception_string = (
            "Client error '422 Unprocessable Content|Entity' for url "
            f"'http://127.0.0.1:{session_glow.solution_api_port}/solution-configuration'"
        )
        with pytest.raises(httpx2.HTTPStatusError, match=exception_string):
            httpx2.put(
                f"{session_glow.base_api_url}/solution-configuration",
                json={
                    "my_field": 5,
                },
            ).raise_for_status()

        exception_string = "1 validation error for ExtendedSolutionConfiguration"
        with pytest.raises(BadRequestException, match="1 validation error for ExtendedSolutionConfiguration"):
            function_project.project.solution_configuration  # noqa: B018

        # WHEN: setting GLOW_OVERWRITE_SOLUTION_CONFIG env var
        session_glow.change_configuration(EnableOverwriteSolutionConfig)

        # THEN: all operations are OK
        _, my_field = step.read_extended_solution_configuration()
        assert my_field == 0

        httpx2.put(
            f"{session_glow.base_api_url}/solution-configuration",
            json={
                "my_field": 5,
            },
        ).raise_for_status()

        assert function_project.project.solution_configuration.my_field == 5

    @pytest.mark.parametrize("change_solution_configuration", ["add_field", "change_default_value"], indirect=True)
    def test_allow_non_breaking_changes(
        self,
        change_solution_configuration: str,
        function_project: ProjectFixture[ExtendedSolutionConfigurationSolution],
        session_glow: GlowBaseProcess[ExtendedSolutionConfigurationSolution],
    ):
        """Test that some modifications of the solution configuration are automatically handled without requiring to
        set the GLOW_OVERWRITE_SOLUTION_CONFIG env var. Examples: adding fields, changing default values. Note that
        changing the default value does not update the value stored in the DB. Default values are only used for
        initialization.
        """
        stored_solution_config = get_solution_config_from_db(session_glow)
        if change_solution_configuration == "add_field":
            assert "my_field" not in stored_solution_config
            assert hasattr(ExtendedSolutionConfiguration(), "my_field")
        elif change_solution_configuration == "change_default_value":
            assert stored_solution_config["my_field"] != ExtendedSolutionConfiguration().my_field
        else:
            pytest.fail("Wrong fixture configuration.")

        # GIVEN: GLOW with a different but compatible solution configuration stored in DB
        step = function_project.project.steps.extended_solution_configuration_step

        # WHEN: trying to read or modify solution configuration via transaction, REST API or Client API
        # THEN: all operations are OK
        _, my_field = step.read_extended_solution_configuration()
        expected_value = ExtendedSolutionConfiguration().my_field
        if change_solution_configuration == "change_default_value":
            expected_value += 1
        assert my_field == expected_value

        httpx2.put(
            f"{session_glow.base_api_url}/solution-configuration",
            json={
                "my_field": 5,
            },
        ).raise_for_status()

        assert function_project.project.solution_configuration.my_field == 5
