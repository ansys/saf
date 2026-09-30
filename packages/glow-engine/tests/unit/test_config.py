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

import importlib
import os
from pathlib import Path
import platform
import re
from typing import Any
from unittest import mock

from ansys.saf.testing.platform_specific import linux_only, windows_only
from pydantic import PostgresDsn, ValidationError
from pydantic_core import MultiHostUrl
import pytest
from pytest_mock import MockerFixture

from ansys.saf.glow._config.const import (
    ANSYS_GRPC_CERTIFICATES,
    GLOW_API_HOST,
    GLOW_API_KEY,
    GLOW_API_KEY_FILE,
    GLOW_DATABASE_LOCATION,
    GLOW_HPS_HOST,
    GLOW_HPS_PORT,
    GLOW_MCP_TRANSPORT_MODE,
    GLOW_PIM_SOCKET_PATH,
    GLOW_PRODUCT_INSTANCE_SYSTEM,
    GLOW_PRODUCT_INSTANCE_SYSTEM_HOST,
    GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM,
    GLOW_PRODUCT_INSTANCE_SYSTEM_PORT,
    GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY,
    GLOW_UI_HOST,
    DatabaseType,
    Deployment,
    ExecutorType,
    ProductInstanceSystemType,
)
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._utilities.path_parser import parse_platform_specific_absolute_path
from tests.mocks.solutions.minimal_solution import MinimalSolution


@pytest.fixture(autouse=True)
def clean_env():
    # Tested functions internally set environment variables such as GLOW_SOLUTION_NAME, _URL, _HOST, _PORT...
    # Clean it up between tests
    with mock.patch.dict(os.environ, os.environ.copy()):
        yield


def test_default_settings(monkeypatch: pytest.MonkeyPatch):
    for env_var in os.environ:
        if env_var.startswith("GLOW_"):
            monkeypatch.delenv(env_var)

    settings = Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")
    expected_settings = {
        "glow_deployment": Deployment.Desktop,
        "glow_debug": False,
        "glow_ui_python_debugging": False,
        "glow_api_host": "127.0.0.1",
        "glow_api_number_of_workers": None,
        "glow_api_port": 5432,
        "glow_auth_client_id": None,
        "glow_auth_disabled": True,
        "glow_auth_issuer_url": None,
        "glow_auth_required_roles": None,
        "glow_api_key": None,
        "glow_api_key_file": None,
        "glow_solution_definition": "tests.mocks.solutions.minimal_solution",
        "glow_ui_host": "127.0.0.1",
        "glow_ui_port": 5433,
        "glow_product_instance_system_host": "127.0.0.1",
        "glow_product_instance_system_port": None,
        "glow_product_host": None,
        "glow_ui_module": None,
        "glow_ui_project_files_directory": None,
        "glow_debug_api_port": None,
        "glow_debug_ui_port": None,
        "glow_log_config": None,
        "glow_ui_log_config": None,
        "glow_method_log_config": None,
        "glow_logging_level": None,
        "glow_project_files_directory": None,
        "otel_exporter_otlp_endpoint": None,
        "glow_database_type": DatabaseType.Sqlite,
        "glow_database_location": None,
        "glow_product_instance_system": ProductInstanceSystemType.PIM,
        "glow_product_instance_system_platform": None,
        "glow_product_instance_system_project_files_directory": None,
        "glow_hps_client_id": "rep-jms-web",
        "glow_auth_service_account_client_id": None,
        "glow_auth_service_account_client_secret": None,
        "glow_hps_host": "127.0.0.1",
        "glow_hps_password": "",
        "glow_hps_port": None,
        "glow_hps_username": "",
        "glow_cors_origins": None,
        "glow_data_repository_type": None,
        "glow_data_repository_upload_root": "/Data",
        "glow_api_hot_reload": True,
        "glow_bdm_gc_disabled": False,
        "glow_enable_automatic_project_migration": False,
        "glow_long_running_executor_type": ExecutorType.Process,
        "ansys_grpc_certificates": None,
        "glow_pim_socket_path": None,
        "glow_api_hot_reload_monitoring_dir": None,
        "glow_external_api_url": None,
        "glow_ws_event_poll_interval": 1.0,
        "glow_method_cleanup_child_procs": True,
        "glow_mcp_disabled": True,
        "glow_mcp_transport_mode": "http",
        "glow_mcp_path": "/sse",
    }
    assert settings.model_dump() == expected_settings
    assert settings.computed_database_location == settings.computed_solution_appdata_directory / "glow.db"
    assert settings.computed_definition_module == importlib.import_module("tests.mocks.solutions.minimal_solution")
    assert settings.computed_solution_name == "MinimalSolution"
    assert settings.computed_solution_type == MinimalSolution
    assert settings.computed_project_files_directory == settings.computed_solution_appdata_directory / "project_files"
    assert (
        settings.computed_ui_project_files_directory == settings.computed_solution_appdata_directory / "project_files"
    )
    assert (
        settings.computed_solution_appdata_directory
        == settings.glow_appdata_directory() / settings.computed_solution_name
    )
    assert settings.computed_glow_product_instance_system_host == ""
    assert settings.computed_glow_product_instance_system_port is None
    assert settings.computed_glow_hps_host == ""
    assert settings.computed_glow_hps_port is None


def test_settings_api_key_from_env_var(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_API_KEY, "my-secret-api-key")

    settings = Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")

    assert settings.glow_api_key == "my-secret-api-key"
    assert settings.glow_api_key_file is None
    assert settings.computed_api_key == "my-secret-api-key"


def test_settings_api_key_from_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    api_key_file = tmp_path / "glow_api_key"
    api_key_file.write_text("my-secret-api-key\n", encoding="utf-8")
    monkeypatch.setenv(GLOW_API_KEY_FILE, api_key_file.as_posix())

    settings = Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")

    assert settings.glow_api_key is None
    assert settings.glow_api_key_file == api_key_file.resolve()
    assert settings.computed_api_key == "my-secret-api-key"


def test_settings_api_key_from_file_strips_trailing_spaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    api_key_file = tmp_path / "glow_api_key"
    api_key_file.write_text("my-secret-api-key   \n", encoding="utf-8")
    monkeypatch.setenv(GLOW_API_KEY_FILE, api_key_file.as_posix())

    settings = Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")

    assert settings.glow_api_key is None
    assert settings.glow_api_key_file == api_key_file.resolve()
    assert settings.computed_api_key == "my-secret-api-key"


def test_settings_api_key_rejects_conflicting_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    api_key_file = tmp_path / "glow_api_key"
    api_key_file.write_text("my-secret-api-key", encoding="utf-8")
    monkeypatch.setenv(GLOW_API_KEY, "another-secret")
    monkeypatch.setenv(GLOW_API_KEY_FILE, api_key_file.as_posix())

    expected_error = (
        "1 validation error for Settings\n"
        "  Value error, Conflicting API key configuration detected: configure either "
        f"{GLOW_API_KEY} or {GLOW_API_KEY_FILE}, but not both."
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")


def test_settings_api_key_file_must_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    missing_api_key_file = tmp_path / "missing_glow_api_key"
    monkeypatch.setenv(GLOW_API_KEY_FILE, missing_api_key_file.as_posix())

    expected_error = (
        "1 validation error for Settings\n"
        f"  Value error, The system cannot find the API key file '{missing_api_key_file}'."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")


def test_settings_api_key_file_must_be_absolute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    relative_api_key_file = tmp_path / "relative_glow_api_key"
    monkeypatch.setenv(GLOW_API_KEY_FILE, relative_api_key_file.relative_to(tmp_path).as_posix())

    expected_error = (
        "1 validation error for Settings\n"
        f"  Value error, The API key file path must be absolute: '{relative_api_key_file.relative_to(tmp_path)}'."
    )
    with pytest.raises(ValueError, match=expected_error):
        Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")


def test_settings_api_key_file_read_error_is_handled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    api_key_file = tmp_path / "glow_api_key"
    api_key_file.write_text("my-secret-api-key", encoding="utf-8")
    monkeypatch.setenv(GLOW_API_KEY_FILE, api_key_file.as_posix())

    with mock.patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
        expected_error = (
            "1 validation error for Settings\n"
            f"  Value error, Failed to read API key file '{api_key_file}': Permission denied"
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")


@pytest.mark.parametrize(
    ("debug_mode", "expected_value"),
    [
        ("True", True),
        ("False", False),
    ],
)
def test_valid_debug_configuration(debug_mode: str, expected_value: bool, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_DEBUG", debug_mode)
    monkeypatch.setenv("GLOW_UI_PYTHON_DEBUGGING", debug_mode)
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_debug == expected_value
    assert settings.glow_ui_python_debugging == expected_value

    monkeypatch.undo()


@pytest.mark.parametrize(
    ("env_var"),
    [
        ("GLOW_DEBUG"),
        ("GLOW_UI_PYTHON_DEBUGGING"),
    ],
)
def test_invalid_debug_configuration(env_var: str, monkeypatch: pytest.MonkeyPatch):
    expected_error = f"1 validation error for Settings\n{env_var.lower()}\n  Input should be a valid boolean"
    monkeypatch.setenv(env_var, "InvalidValue")
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
        )
    monkeypatch.undo()


def test_settings_invalid_logging_level():
    expected_error = (
        "1 validation error for Settings\n"
        "glow_logging_level\n"
        "  Input should be 'DEBUG', 'INFO', 'WARNING', 'ERROR' or 'CRITICAL'"
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
            glow_logging_level="FAKE_LEVEL",  # pyright: ignore[reportArgumentType]
        )


def test_settings_invalid_database_type():
    expected_error = "1 validation error for Settings\nglow_database_type\n  Input should be 'sqlite' or 'postgresql'"
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
            glow_database_type="FAKE_DB_TYPE",  # pyright: ignore[reportArgumentType]
        )


def test_settings_valid_database_location_path_for_sqlite(tmp_path: Path):
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
        glow_database_location=tmp_path / "my_db.db",
    )
    assert settings.glow_database_location == tmp_path / "my_db.db"
    assert settings.computed_database_location == tmp_path / "my_db.db"


def test_settings_invalid_database_location_path_for_sqlite():
    expected_error = (
        "1 validation error for Settings\n  Value error, The system cannot find directory for the Sqlite DB file"
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
            glow_database_location=Path("__my_invalid_path__/my_db.db"),
        )


def test_settings_invalid_database_location_for_sqlite():
    expected_error = (
        "1 validation error for Settings\n"
        "  Value error, Invalid database location for Sqlite database:"
        " 'postgres://my_user:my_pass@my_host:8888/my_db'. Expected a file path."
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
            glow_database_location=PostgresDsn("postgres://my_user:my_pass@my_host:8888/my_db"),
        )


def test_settings_database_location_for_postgresql_using_postgresdsn():
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
        glow_database_type=DatabaseType.PostgreSql,
        glow_database_location=PostgresDsn("postgres://my_user:my_pass@my_host:8888/my_db"),
    )
    assert isinstance(settings.computed_database_location, PostgresDsn)
    assert isinstance(settings.glow_database_location, PostgresDsn)
    assert settings.glow_database_location.unicode_string() == "postgres://my_user:my_pass@my_host:8888/my_db"
    assert settings.computed_database_location.unicode_string() == "postgres://my_user:my_pass@my_host:8888/my_db"


def test_settings_database_location_for_postgresql_using_multihosturl():
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
        glow_database_type=DatabaseType.PostgreSql,
        glow_database_location=MultiHostUrl(
            "postgres://my_user:my_pass@my_host:8888/my_db",
        ),  # pyright: ignore[reportArgumentType]
    )
    assert isinstance(settings.computed_database_location, PostgresDsn)
    assert isinstance(settings.glow_database_location, PostgresDsn)
    assert settings.glow_database_location.unicode_string() == "postgres://my_user:my_pass@my_host:8888/my_db"
    assert settings.computed_database_location.unicode_string() == "postgres://my_user:my_pass@my_host:8888/my_db"


def test_settings_string_database_location_for_postgresql():
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
        glow_database_type=DatabaseType.PostgreSql,
        glow_database_location="postgres://my_user:my_pass@my_host:8888/my_db",  # pyright: ignore[reportArgumentType]
    )
    assert isinstance(settings.computed_database_location, PostgresDsn)
    assert isinstance(settings.glow_database_location, PostgresDsn)
    assert settings.glow_database_location.unicode_string() == "postgres://my_user:my_pass@my_host:8888/my_db"
    assert settings.computed_database_location.unicode_string() == "postgres://my_user:my_pass@my_host:8888/my_db"


def test_settings_database_location_for_postgresql_via_env_var(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_DATABASE_LOCATION, "postgres://my_user:my_pass@my_host:8888/my_db")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
        glow_database_type=DatabaseType.PostgreSql,
    )
    assert isinstance(settings.computed_database_location, PostgresDsn)
    assert isinstance(settings.glow_database_location, PostgresDsn)
    assert settings.glow_database_location.unicode_string() == "postgres://my_user:my_pass@my_host:8888/my_db"
    assert settings.computed_database_location.unicode_string() == "postgres://my_user:my_pass@my_host:8888/my_db"


def test_settings_no_database_location_for_postgresql():
    expected_error = (
        "1 validation error for Settings\n"
        "  Value error, Invalid database location for PostgreSql database: 'None'. Expected a PostgresDsn."
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
            glow_database_type=DatabaseType.PostgreSql,
        )


def test_settings_invalid_database_location_for_postgresql():
    db_path = Path("my_db.db")
    expected_error = (
        "1 validation error for Settings\n"
        f"  Value error, Invalid database location for PostgreSql database: '{str(db_path)}'. Expected a PostgresDsn."
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
            glow_database_type=DatabaseType.PostgreSql,
            glow_database_location=db_path,
        )


def test_settings_host_as_str(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "my_pim_container")
    monkeypatch.setenv(GLOW_API_HOST, "my_api_container")
    monkeypatch.setenv(GLOW_UI_HOST, "my_ui_container")
    monkeypatch.setenv(ANSYS_GRPC_CERTIFICATES, "certs")

    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_product_instance_system_host == "my_pim_container"
    assert settings.glow_api_host == "my_api_container"
    assert settings.glow_ui_host == "my_ui_container"


def test_computed_hps_configuration_with_pim(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.setenv(GLOW_HPS_HOST, "localhost")
    monkeypatch.setenv(GLOW_HPS_PORT, "8443")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_hps_host == "localhost"
    assert settings.glow_hps_port == 8443
    assert settings.computed_glow_hps_host == "localhost"
    assert settings.computed_glow_hps_port == 8443


def test_computed_hps_configuration_with_hps(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "HPS")
    monkeypatch.setenv(GLOW_HPS_HOST, "localhost")
    monkeypatch.setenv(GLOW_HPS_PORT, "8443")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_hps_host == "localhost"
    assert settings.glow_hps_port == 8443
    assert settings.computed_glow_hps_host == "localhost"
    assert settings.computed_glow_hps_port == 8443


def test_computed_hps_configuration_with_pim_and_hps_for_job_submission_unconfigured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    if platform.system() == "Windows":
        monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "localhost")
        monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "8443")
    else:
        monkeypatch.setenv(GLOW_PIM_SOCKET_PATH, "/tmp/pim.sock")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_hps_host == "127.0.0.1"
    assert settings.glow_hps_port is None
    assert settings.computed_glow_hps_host == ""
    assert settings.computed_glow_hps_port is None


def test_computed_hps_configuration_with_hps_and_hps_for_job_submission_unconfigured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "HPS")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "localhost")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "8443")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_hps_host == "127.0.0.1"
    assert settings.glow_hps_port is None
    assert settings.computed_glow_hps_host == "localhost"
    assert settings.computed_glow_hps_port == 8443


def test_computed_product_instance_system_configuration_with_pim(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.setenv(GLOW_HPS_HOST, "localhost")
    monkeypatch.setenv(GLOW_HPS_PORT, "8443")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_hps_host == "localhost"
    assert settings.glow_hps_port == 8443
    assert settings.glow_product_instance_system_host == "127.0.0.1"
    assert settings.glow_product_instance_system_port is None
    assert settings.computed_glow_product_instance_system_host == ""
    assert settings.computed_glow_product_instance_system_port is None


def test_computed_product_instance_system_configuration_with_hps(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "HPS")
    monkeypatch.setenv(GLOW_HPS_HOST, "localhost")
    monkeypatch.setenv(GLOW_HPS_PORT, "8443")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_hps_host == "localhost"
    assert settings.glow_hps_port == 8443
    assert settings.glow_product_instance_system_host == "127.0.0.1"
    assert settings.glow_product_instance_system_port is None
    assert settings.computed_glow_product_instance_system_host == "localhost"
    assert settings.computed_glow_product_instance_system_port == 8443


def test_computed_configurations_when_no_configuration_with_pim(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_hps_host == "127.0.0.1"
    assert settings.glow_hps_port is None
    assert settings.computed_glow_hps_host == ""
    assert settings.computed_glow_hps_port is None
    assert settings.glow_product_instance_system_host == "127.0.0.1"
    assert settings.glow_product_instance_system_port is None
    assert settings.computed_glow_product_instance_system_host == ""
    assert settings.computed_glow_product_instance_system_port is None


def test_computed_configurations_when_no_configuration_with_hps(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "HPS")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_hps_host == "127.0.0.1"
    assert settings.glow_hps_port is None
    assert settings.computed_glow_hps_host == ""
    assert settings.computed_glow_hps_port is None
    assert settings.glow_product_instance_system_host == "127.0.0.1"
    assert settings.glow_product_instance_system_port is None
    assert settings.computed_glow_product_instance_system_host == ""
    assert settings.computed_glow_product_instance_system_port is None


def test_invalid_product_platform(monkeypatch: pytest.MonkeyPatch):
    wrong_platform = "ubuntu"
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM, wrong_platform)
    expected_error = (
        "1 validation error for Settings\nglow_product_instance_system_platform\n  Input should be 'Windows' or 'Linux'"
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
        )


def test_product_files_directory_without_platform(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY, "C:/my_dir")
    expected_error = (
        "1 validation error for Settings\n"
        "  Value error, Project files directory in product instance system "
        "is configured but not the product instance system platform."
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
        )


def test_product_files_directory_relative(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM, "Linux")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY, "my_dir/")
    expected_error = (
        "1 validation error for Settings\n  Value error, Project files directory should be an absolute path: my_dir"
    )
    with pytest.raises(ValidationError, match=expected_error):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
        )


def test_default_appdata_path_resolved_on_access(mocker: MockerFixture):
    path_resolve_mock = mocker.spy(Path, "resolve")
    settings = Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")
    path_resolve_mock.assert_not_called()
    assert isinstance(settings.computed_solution_appdata_directory, Path)
    path_resolve_mock.assert_called_once()


@pytest.mark.parametrize(
    "setting_name",
    [
        "glow_project_files_directory",
        "glow_ui_project_files_directory",
        "glow_log_config",
        "glow_ui_log_config",
        "glow_method_log_config",
    ],
)
def test_configured_paths_resolved_on_validation(mocker: MockerFixture, setting_name: str, tmp_path: Path):
    path_resolve_mock = mocker.spy(Path, "resolve")
    kwargs: Any = {"glow_solution_definition": "tests.mocks.solutions.minimal_solution", setting_name: tmp_path}
    path_resolve_mock.assert_not_called()
    settings = Settings(**kwargs)
    path_resolve_mock.assert_called_once()
    assert getattr(settings, setting_name) == tmp_path


def test_sqlite_path_resolved_on_access(mocker: MockerFixture, tmp_path: Path):
    path_resolve_mock = mocker.spy(Path, "resolve")
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
        glow_database_location=tmp_path,
    )
    path_resolve_mock.assert_not_called()
    assert isinstance(settings.computed_database_location, Path)
    path_resolve_mock.assert_called_once()


def test_product_instances_path_not_resolved(mocker: MockerFixture, tmp_path: Path):
    product_platform = platform.system()
    product_project_files_dir = str(tmp_path)

    path_resolve_mock = mocker.spy(Path, "resolve")
    Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
        glow_product_instance_system_project_files_directory=product_project_files_dir,
        glow_product_instance_system_platform=product_platform,  # pyright: ignore[reportArgumentType]
    )
    parse_platform_specific_absolute_path(product_project_files_dir, product_platform)
    path_resolve_mock.assert_not_called()


def test_external_pim_without_certs(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "192.111.111.111")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.delenv(ANSYS_GRPC_CERTIFICATES, raising=False)
    expected_error = (
        "1 validation error for Settings\n  Value error, Missing Ansys gRPC certificates directory "
        "(ANSYS_GRPC_CERTIFICATES) for non-localhost connections to PIM Light Server."
    )
    with pytest.raises(ValidationError, match=re.escape(expected_error)):
        Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")


def test_external_pim_with_certs_dir_without_files(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "192.111.111.111")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.setenv(ANSYS_GRPC_CERTIFICATES, "certs")

    expected_error = (
        "1 validation error for Settings\n  Value error, Missing required TLS file(s) for mutual TLS: "
        "certs/client.crt, certs/client.key, certs/ca.crt"
    )
    with pytest.raises(ValidationError, match=re.escape(expected_error)):
        Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")


def test_external_pim_with_certs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    (certs_dir / "client.crt").touch()
    (certs_dir / "client.key").touch()
    (certs_dir / "ca.crt").touch()

    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "192.111.111.111")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.setenv(ANSYS_GRPC_CERTIFICATES, certs_dir.as_posix())

    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_product_instance_system_host == "192.111.111.111"
    assert settings.glow_product_instance_system_port == 5555
    assert settings.ansys_grpc_certificates == certs_dir
    assert settings.glow_product_instance_system == ProductInstanceSystemType.PIM
    assert settings.computed_glow_product_instance_system_uri == "192.111.111.111:5555"


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_local_pim_grpc_certificates_not_required(monkeypatch: pytest.MonkeyPatch, host: str):
    """Test that GRPC certificates are not required for localhost PIM connections."""
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    if platform.system() != "Windows":
        monkeypatch.setenv(GLOW_PIM_SOCKET_PATH, "/tmp/pim.sock")
    else:
        monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, host)
        monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.delenv(ANSYS_GRPC_CERTIFICATES, raising=False)

    # This should not raise an exception since localhost doesn't require certificates
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    if platform.system() == "Windows":
        assert settings.computed_glow_product_instance_system_host == host
        assert settings.computed_glow_product_instance_system_port == 5555
        assert settings.computed_glow_product_instance_system_uri == f"{host}:5555"
    else:
        assert settings.computed_glow_product_instance_system_host == ""
        assert settings.computed_glow_product_instance_system_port is None
        assert settings.computed_glow_product_instance_system_uri == "unix:/tmp/pim.sock"
    assert settings.ansys_grpc_certificates is None


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "192.111.111.111"])
def test_hps_system_grpc_certificates_not_validated(monkeypatch: pytest.MonkeyPatch, host: str):
    """Test that GRPC certificates validation is skipped for HPS systems, no matter the host value."""
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, host)
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "HPS")
    monkeypatch.delenv(ANSYS_GRPC_CERTIFICATES, raising=False)

    # This should not raise an exception since validation is skipped for HPS
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_product_instance_system_host == host
    assert settings.glow_product_instance_system_port == 5555
    assert settings.glow_product_instance_system == ProductInstanceSystemType.HPS
    assert settings.computed_glow_product_instance_system_uri == f"https://{host}:5555/hps"


def test_external_pim_with_partial_certs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Test that missing some certificate files raises an error."""
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    # Only create client.crt, missing client.key and ca.crt
    (certs_dir / "client.crt").touch()

    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "192.111.111.111")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.setenv(ANSYS_GRPC_CERTIFICATES, certs_dir.as_posix())

    expected_error = (
        "1 validation error for Settings\n  Value error, Missing required TLS file(s) for mutual TLS: "
        f"{(certs_dir / 'client.key').as_posix()}, {(certs_dir / 'ca.crt').as_posix()}"
    )
    with pytest.raises(ValidationError, match=re.escape(expected_error)):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
        )


def test_pim_without_port_grpc_certificates_not_validated(monkeypatch: pytest.MonkeyPatch):
    """Test that GRPC certificates validation is skipped when no port is configured."""
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "192.111.111.111")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.delenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, raising=False)
    monkeypatch.delenv(ANSYS_GRPC_CERTIFICATES, raising=False)

    # This should not raise an exception since no port means no validation
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.computed_glow_product_instance_system_host == ""
    assert settings.computed_glow_product_instance_system_port is None
    assert settings.computed_glow_product_instance_system_uri is None


@linux_only()
@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_local_pim_linux_without_socket(monkeypatch: pytest.MonkeyPatch, host: str):
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, host)
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.delenv(GLOW_PIM_SOCKET_PATH, raising=False)

    expected_error = (
        f"1 validation error for Settings\n  Value error, Missing socket path ({GLOW_PIM_SOCKET_PATH}) "
        "for localhost connections on Linux."
    )
    with pytest.raises(ValidationError, match=re.escape(expected_error)):
        Settings(glow_solution_definition="tests.mocks.solutions.minimal_solution")


@linux_only()
def test_local_pim_linux_with_socket_path_only(monkeypatch: pytest.MonkeyPatch):
    """Test that providing only socket path for localhost PIM on Linux works correctly."""
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.setenv(GLOW_PIM_SOCKET_PATH, "/tmp/pim.sock")
    monkeypatch.delenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, raising=False)
    monkeypatch.delenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, raising=False)

    # This should work correctly
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.glow_pim_socket_path == Path("/tmp/pim.sock")
    assert settings.computed_glow_product_instance_system_host == ""  # default value
    assert settings.computed_glow_product_instance_system_port is None  # default value
    assert settings.computed_glow_product_instance_system_uri == "unix:/tmp/pim.sock"


@linux_only()
@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_local_pim_linux_with_socket_and_host_port_error(monkeypatch: pytest.MonkeyPatch, host: str):
    """Test that providing both socket path and host/port for localhost PIM on Linux raises an error."""
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, host)
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.setenv(GLOW_PIM_SOCKET_PATH, "/tmp/pim.sock")

    expected_error = (
        "1 validation error for Settings\n"
        f"  Value error, Conflicting PIM configuration detected: both socket path ({GLOW_PIM_SOCKET_PATH}) and "
        f"host/port ({GLOW_PRODUCT_INSTANCE_SYSTEM_HOST}/{GLOW_PRODUCT_INSTANCE_SYSTEM_PORT}) "
        f"are provided. For localhost connections on Linux, please use only {GLOW_PIM_SOCKET_PATH}."
    )
    with pytest.raises(ValidationError, match=re.escape(expected_error)):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
        )


@windows_only()
@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_pim_unix_socket_validation_skipped_on_windows(monkeypatch: pytest.MonkeyPatch, host: str):
    """Test that Unix socket path validation is skipped on Windows."""
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, host)
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.delenv(GLOW_PIM_SOCKET_PATH, raising=False)

    # This should not raise an exception since validation is skipped on Windows
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.computed_glow_product_instance_system_host == host
    assert settings.computed_glow_product_instance_system_port == 5555
    assert settings.computed_glow_product_instance_system_uri == f"{host}:5555"


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "192.111.111.111"])
def test_hps_system_unix_socket_validation_skipped(monkeypatch: pytest.MonkeyPatch, host: str):
    """Test that Unix socket path validation is skipped for HPS systems."""
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, host)
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "HPS")
    monkeypatch.delenv(GLOW_PIM_SOCKET_PATH, raising=False)

    # This should not raise an exception since validation is skipped for HPS
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.computed_glow_product_instance_system_host == host
    assert settings.computed_glow_product_instance_system_port == 5555
    assert settings.computed_glow_product_instance_system_uri == f"https://{host}:5555/hps"
    assert settings.glow_product_instance_system == ProductInstanceSystemType.HPS


@linux_only()
def test_external_pim_linux_socket_validation_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that Unix socket path validation is skipped for external (non-localhost) PIM connections."""
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST, "192.111.111.111")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT, "5555")
    monkeypatch.setenv(GLOW_PRODUCT_INSTANCE_SYSTEM, "PIM")
    monkeypatch.delenv(GLOW_PIM_SOCKET_PATH, raising=False)
    # Need certificates for external PIM
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    (certs_dir / "client.crt").touch()
    (certs_dir / "client.key").touch()
    (certs_dir / "ca.crt").touch()
    monkeypatch.setenv(ANSYS_GRPC_CERTIFICATES, certs_dir.as_posix())

    # This should not raise an exception since socket validation is skipped for external connections
    settings = Settings(
        glow_solution_definition="tests.mocks.solutions.minimal_solution",
    )
    assert settings.computed_glow_product_instance_system_host == "192.111.111.111"
    assert settings.computed_glow_product_instance_system_port == 5555
    assert settings.computed_glow_product_instance_system_uri == "192.111.111.111:5555"
    assert settings.ansys_grpc_certificates == certs_dir
    assert settings.glow_pim_socket_path is None


def test_mcp_invalid_transport_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GLOW_MCP_TRANSPORT_MODE, "non-valid-transport-mode")
    with pytest.raises(ValidationError, match="Input should be 'http', 'streamable-http' or 'sse'"):
        Settings(
            glow_solution_definition="tests.mocks.solutions.minimal_solution",
        )
