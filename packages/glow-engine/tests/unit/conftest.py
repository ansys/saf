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
from contextlib import AbstractContextManager, contextmanager
import copy
from datetime import datetime, timedelta, tzinfo
import importlib
from io import BytesIO
import json
import os
from pathlib import Path
from types import ModuleType
from typing import Any, TypeVar
import zipfile

from dash import Dash  # pyright: ignore[reportMissingTypeStubs]
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from pytest_mock import MockerFixture

from ansys.bdm.api import IReadStorageScope, IStorageScope
from ansys.saf.glow._bdm.hps_scope import HpsSubsidiarySystemStorageScopeFactory
from ansys.saf.glow._bdm.multiplexor import HPS_BDM_SYSTEM_NAME, BdmMultiplexor
from ansys.saf.glow._bdm.storage_contexts import METHOD_CONTEXT
from ansys.saf.glow._bdm.storage_factory import create_shared_storage_factory
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, ROOT, SHORTID
from ansys.saf.glow._config.const import DatabaseType, ExecutorType
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.blob_managers import HpsBlobManager
from ansys.saf.glow._core.field_state import FieldState
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._hps_auth.hps_authenticator import NullHpsAuthenticator
from ansys.saf.glow._server.dependencies import get_settings
from ansys.saf.glow._server.models import ProjectModel
from ansys.saf.glow._server.server import create_app
from ansys.saf.glow._server.solution import SolutionService
from ansys.saf.glow._ui.server import create_app as create_dash_app
from ansys.saf.testing.database import PostgresqlServerInfo
from tests.mocks.pim.mock_multiple_version_pim import MockPimMultipleVersionClient, MockPimMultipleVersionClientFactory
from tests.mocks.pim.mock_pim import MockProductInstanceSystem
from tests.mocks.pim.mock_version_pim import MockPimVersionClient, MockPimVersionClientFactory
from tests.unit.contruct_migration_context import get_construct_migration_context
from tests.unit.test_hps_bdm_scope import HPS_SERVER_URL

MOCK_APP_STARTUP_TIMEOUT = 10


T = TypeVar("T", bound=Solution)


@pytest.fixture(autouse=True)
def is_environment_clean():
    # Unit tests are prone to leave a dirty environment. Raise alarm if it happens so we can early fix it.
    # FIXME: env vars can leak from non-unit tests too, ignore them at the moment.
    existing_glow_env_vars = [env_var for env_var in os.environ if env_var.startswith("GLOW_")]
    yield
    assert not {
        env_var: value
        for env_var, value in os.environ.items()
        if env_var.startswith("GLOW_") and env_var not in existing_glow_env_vars
    }


@pytest.fixture(autouse=True)
def mock_appdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    appdata = tmp_path / "appdata"
    appdata.mkdir(exist_ok=True, parents=True)
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("XDG_DATA_HOME", str(appdata))
    return appdata


@pytest.fixture
def mock_product_instance_system() -> MockProductInstanceSystem:
    client = MockProductInstanceSystem()
    return client


@pytest.fixture
def mock_pim_version_client() -> MockPimVersionClient:
    client = MockPimVersionClient()
    return client


@pytest.fixture
def mock_pim_version_client_factory() -> MockPimVersionClientFactory:
    return MockPimVersionClientFactory()


@pytest.fixture
def mock_pim_multiple_version_client() -> MockPimMultipleVersionClient:
    client = MockPimMultipleVersionClient()
    return client


@pytest.fixture
def mock_pim_multiple_version_client_factory() -> MockPimMultipleVersionClientFactory:
    return MockPimMultipleVersionClientFactory()


@pytest.fixture(scope="module")
def mock_module_settings(
    request: pytest.FixtureRequest,
    get_temp_postgresql_database_module: Callable[[], PostgresqlServerInfo],
) -> Settings:
    settings = Settings(
        glow_solution_definition=request.module.solution.__name__,  # type: ignore
        glow_long_running_executor_type=ExecutorType.Thread,
    )
    if hasattr(request, "param"):
        # allow customisation of settings through parameterization
        settings = settings.model_copy(update=request.param)
        if settings.glow_database_type == DatabaseType.PostgreSql:
            settings.glow_database_location = get_temp_postgresql_database_module().url
    return settings


@pytest.fixture
async def settings(
    request: pytest.FixtureRequest,
    mock_module_settings: Settings,
    get_temp_postgresql_database: Callable[[], PostgresqlServerInfo],
):
    settings = mock_module_settings.model_copy()
    if hasattr(request, "param"):
        # allow customisation of settings through parameterization
        settings = settings.model_copy(update=request.param)
        if settings.glow_database_type == DatabaseType.PostgreSql:
            # if the test requires a new DB, by default, same DB is shared for all tests within a module.
            # for sqlite, DB is automatically isolated since GLOW creates a new DB file in appdata,
            # and appdata is different for every test.
            settings.glow_database_location = get_temp_postgresql_database().url
    return settings


def build_mock_app(settings: Settings, definition_module: ModuleType | None = None) -> FastAPI:
    if definition_module:
        settings = settings.model_copy()
        settings.glow_solution_definition = definition_module.__name__
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def build_mock_dash_app(monkeypatch: pytest.MonkeyPatch) -> Dash:
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "http://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_WS_EVENTS_ADDR", "ws://127.0.0.1:5432")
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "tests.mocks.solution_with_ui.solution.definition")
    monkeypatch.setenv("GLOW_UI_MODULE", "tests.mocks.solution_with_ui.ui.app")

    settings = Settings.model_validate({})

    # Reload UI module to ensure a fresh app is created. This prevents Flask's complain about the before_request
    # ``validate_authorization_header`` method being set multiple times.
    assert settings.glow_ui_module
    ui_module = importlib.import_module(settings.glow_ui_module)
    importlib.reload(ui_module)

    ui_app = create_dash_app(settings)
    return ui_app


@pytest.fixture
def primary_bdm_scope(tmp_path: Path) -> Generator[IStorageScope]:
    project_dir = tmp_path / "project_files" / "abcdefghijklmnopqrstuvwx"
    project_dir.mkdir(parents=True, exist_ok=True)
    storage_factory = create_shared_storage_factory()
    with storage_factory.create_storage_scope(
        METHOD_CONTEXT,
        {
            "ROOT": str(project_dir.parent),
            "PROJECT_ID": str(project_dir.name),
            "SHORTID": "12345678",
        },
    ) as primary:
        yield primary


@pytest.fixture
def subsystem_scope(tmp_path: Path) -> Generator[IStorageScope]:
    sub_dir = tmp_path / "sub" / "abcdefghijklmnopqrstuvwx"
    sub_dir.mkdir(parents=True, exist_ok=True)
    storage_factory = create_shared_storage_factory()
    with storage_factory.create_storage_scope(
        METHOD_CONTEXT,
        {
            "ROOT": str(sub_dir.parent),
            "PROJECT_ID": str(sub_dir.name),
            "SHORTID": "12345678",
        },
    ) as subsystem:
        yield subsystem


@pytest.fixture
def multiplexor(primary_bdm_scope: IStorageScope, subsystem_scope: IReadStorageScope) -> BdmMultiplexor:
    return BdmMultiplexor(primary_bdm_scope, {"subsystem": subsystem_scope})


@pytest.fixture
def hps_subsystem_scope(tmp_path: Path) -> Generator[IReadStorageScope, None, None]:
    root_dir = tmp_path / ".hps_cache"
    storage_factory = HpsSubsidiarySystemStorageScopeFactory(NullHpsAuthenticator(), HPS_SERVER_URL)
    with storage_factory.create_storage_scope(
        METHOD_CONTEXT,
        {
            ROOT: str(root_dir),
            PROJECT_ID: "bdm_project_id",
            SHORTID: "bdm_shortid",
        },
    ) as scope:
        yield scope


@pytest.fixture
def multiplexor_with_hps(primary_bdm_scope: IStorageScope, hps_subsystem_scope: IReadStorageScope) -> BdmMultiplexor:
    return BdmMultiplexor(primary_bdm_scope, {HPS_BDM_SYSTEM_NAME: hps_subsystem_scope})


@pytest.fixture
def hps_blob_manager(multiplexor_with_hps: BdmMultiplexor) -> HpsBlobManager:
    return HpsBlobManager(multiplexor_with_hps)


def get_project(client: TestClient, project_name: str) -> Any:
    exported_project = client.get(f"{project_name}:export").content
    with zipfile.ZipFile(BytesIO(exported_project), "r") as archive:
        sap_file = [f for f in archive.namelist() if f.endswith(".sap")][0]
        return json.loads(archive.read(sap_file))


@pytest.fixture
def solution_service(request: pytest.FixtureRequest) -> SolutionService:
    service = SolutionService(request.param)
    service.build_and_validate()
    return service


@pytest.fixture
def with_migration(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture
def solution_to_update(with_migration: bool) -> dict[str, Any]:
    solution_to_update: dict[str, Any] = {
        "display_name": "project",
        "date_created": "2025-06-10T20:50:14.860709",
        "date_modified": "2025-06-10T20:50:14.860709",
        "name": "projects/1234",
        "method_states": {},
        "instances": {},
        "bdm_locks": [],
        "schema_version": 1,
        "solution": {
            "display_name": "Original",
            "version": 1,
            "steps": {
                "first_step": {
                    "state": {
                        "x": FieldState.UPTODATE,
                        "my_string": FieldState.UPTODATE,
                        "unused_value": FieldState.UPTODATE,
                        "str_int": FieldState.UPTODATE,
                    },
                    "x": 88,
                    "my_string": "my_string",
                    "unused_value": 0.5,
                    "str_int": "1",
                },
                "second_step": {
                    "state": {"x": FieldState.UPTODATE, "my_string": FieldState.UPTODATE},
                    "x": 88,
                    "my_string": "my_string",
                },
            },
        },
        "solution_name": "OriginalSolution",
    }
    if with_migration:
        solution_to_update["solution"]["version"] = 2
        solution_to_update["solution"]["migrations"] = [{"version": 1, "migration_transformation": {}}]
        solution_to_update["solution"]["steps"]["first_step"]["unexpected_int"] = 100
        solution_to_update["solution"]["steps"]["first_step"]["state"]["unexpected_int"] = FieldState.UPTODATE
    return solution_to_update


def validate_project_model(
    solution_type: type[T],
    solution_to_update: dict[str, Any],
    solution_service: SolutionService,
    project_files_dir: Path,
    automatic_project_migration: bool = False,
    mode: str = "upgrade",
) -> ProjectModel[T]:
    return ProjectModel[solution_type].model_validate(
        copy.deepcopy(solution_to_update),
        context={
            "mode": mode,
            "default_solution": solution_service.default_instance,
            "migration_context_constructor": get_construct_migration_context(project_files_dir),
            "automatic_project_migration": automatic_project_migration,
        },
    )


@pytest.fixture
def mock_datetime_on_relational(
    mocker: MockerFixture,
) -> Callable[[], AbstractContextManager[None]]:
    @contextmanager
    def _mock_datetime() -> Generator[None, None, None]:
        original_datetime = datetime

        class MockedDatetime(datetime):
            @classmethod
            def now(cls, tz: tzinfo | None = None) -> datetime:
                return original_datetime.now(tz) - timedelta(days=2)

        mocker.patch("ansys.saf.glow._repository.relational.datetime", MockedDatetime)

        try:
            yield
        finally:
            mocker.patch("ansys.saf.glow._repository.relational.datetime", original_datetime)

    return _mock_datetime
