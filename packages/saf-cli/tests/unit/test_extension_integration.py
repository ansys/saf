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

from click.testing import CliRunner
import pytest
import pytest_mock

from ansys.saf.cli.integrations.solutions_manager import main


@pytest.mark.parametrize(("args", "expected_exit_code"), [([], 2), (["--help"], 0)])
def test_no_command_provided(args: list[str], expected_exit_code: int):
    """Test that running the CLI without a command shows help."""
    runner = CliRunner()
    result = runner.invoke(main, args)

    assert result.exit_code == expected_exit_code
    assert "Solutions Manager Integration CLI" in result.output
    assert "Usage:" in result.output


def test_wrong_api_call():
    """Test that running the CLI with an unknown command fails."""
    runner = CliRunner()
    result = runner.invoke(main, ["unknown-command"])

    assert result.exit_code == 2
    assert "No such command" in result.output


@pytest.mark.parametrize(
    ("mock_return_value", "expected_output"),
    [
        (True, "Credentials are valid!"),
        (False, "Invalid credentials."),
    ],
)
def test_validate_credentials(
    mocker: pytest_mock.MockFixture,
    mock_return_value: bool,
    expected_output: str,
):
    """Test credential validation."""
    mock_validate = mocker.patch("ansys.saf.cli.integrations.solutions_manager.validate_credentials")
    mock_validate.return_value = mock_return_value

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "validate-credentials",
            "--source",
            '{"url": "https://pypi.org/simple/"}',
            "--username",
            "test_user",
            "--password",
            "test_password",
        ],
    )

    assert result.exit_code == 0
    assert expected_output in result.output


def test_validate_with_missing_args():
    """Test validation command with missing password argument."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "validate-credentials",
            "--source",
            '{"url": "https://pypi.org/simple/"}',
            "--username",
            "test_user",
        ],
    )

    assert result.exit_code == 2
    assert "Missing option" in result.output
    assert "--password" in result.output


def test_set_env_var(mocker: pytest_mock.MockFixture):
    """Test setting environment variable."""
    mock_set_env = mocker.patch("ansys.saf.cli.integrations.solutions_manager.set_user_level_environment_variable")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "set-env-var",
            "--key",
            "TEST_ENV_VAR",
            "--value",
            "TEST_TOKEN",
        ],
    )

    mock_set_env.assert_called_once_with("TEST_ENV_VAR", "TEST_TOKEN")
    assert result.exit_code == 0
    assert "Environment variable 'TEST_ENV_VAR' set successfully!" in result.output


def test_set_env_var_with_missing_args():
    """Test set-env-var command with missing value argument."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "set-env-var",
            "--key",
            "TEST_ENV_VAR",
        ],
    )

    assert result.exit_code == 2
    assert "Missing option" in result.output
    assert "--value" in result.output


def test_validate_credentials_with_exception(mocker: pytest_mock.MockFixture):
    """Test credential validation when an exception occurs."""
    mock_validate = mocker.patch("ansys.saf.cli.integrations.solutions_manager.validate_credentials")
    mock_validate.side_effect = Exception("Connection error")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "validate-credentials",
            "--source",
            '{"url": "https://pypi.org/simple/"}',
            "--username",
            "test_user",
            "--password",
            "test_password",
        ],
    )

    assert result.exit_code == 1
    assert "Error: Connection error" in result.output


def test_set_env_var_with_exception(mocker: pytest_mock.MockFixture):
    """Test setting environment variable when an exception occurs."""
    mock_set_env = mocker.patch("ansys.saf.cli.integrations.solutions_manager.set_user_level_environment_variable")
    mock_set_env.side_effect = Exception("Permission denied")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "set-env-var",
            "--key",
            "TEST_ENV_VAR",
            "--value",
            "TEST_TOKEN",
        ],
    )

    assert result.exit_code == 1
    assert "Error: Permission denied" in result.output


def test_validate_credentials_with_invalid_json():
    """Test credential validation with invalid JSON source."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "validate-credentials",
            "--source",
            "invalid-json",
            "--username",
            "test_user",
            "--password",
            "test_password",
        ],
    )

    assert result.exit_code == 1
    assert "Error:" in result.output
