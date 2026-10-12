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
import compileall
import importlib
import inspect
import logging
import os
from pathlib import Path
import shutil
from typing import Any, TypeVar
from unittest import mock

import httpx2
from joserfc import jwt
from joserfc.jwk import OctKey
import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import Solution
from ansys.saf.testing._solution.end_to_end.glow_execution_configurations import EnvVars, Volumes
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.network import get_random_free_port
from ansys.saf.testing.process import Process
from ansys.saf.testing.selenium import wait_for_element, wait_for_element_and_click, wait_for_element_and_send_text
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import BaseGlowConfiguration, GlowBaseProcess, ProjectFixture
from tests.conftest import IGNORE_PYC_FILES, MOCKS_DIR, PACKAGE_ROOT, SOLUTIONS_MOCKS_DIR
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Solution)
STEPS_WITH_LOGGING_METHODS = {
    "transaction_verification_step": "transaction_verification_step",
}


# =================================================== [Global setup] ================================================ #


@pytest.fixture(autouse=True)
def autouse_test_log_management(test_log_management: None) -> None: ...


@pytest.fixture(autouse=True, scope="session")
def mock_appdata(tmp_path_factory: pytest.TempPathFactory) -> YieldFixture[Path]:
    # Set a different APPDATA, so each GLOW process works isolated and we
    # avoid concurrency problems between them (e.g., project handling)
    tmp_appdata_path_obj = tmp_path_factory.getbasetemp()
    tmp_appdata_path_str = str(tmp_appdata_path_obj)

    with mock.patch.dict(
        os.environ,
        {
            "APPDATA": tmp_appdata_path_str,
            "XDG_DATA_HOME": tmp_appdata_path_str,
        },
    ):
        yield tmp_appdata_path_obj


# ================================================= [Reruns] =================================================== #


@pytest.fixture(autouse=True)
def check_session_glow_health(
    session_glow: GlowBaseProcess[T] | None,
    rerun_restart: None,
    keep_container_logs_now: bool | None = None,
):
    """
    We want the fixtures that handle logging and re-runs to be executed for each test, even if GLOW is not healthy.
    In order to do that, we need to keep the fixtures going until this point.
    """
    if not session_glow:
        return
    if session_glow.healthy is False:
        for error in session_glow.startup_errors:
            logger.error(error)
        pytest.fail("Glow failed to startup or is not healthy.")


# =================================================== [Solutions] =================================================== #


def _get_obfuscated_solution_path(src_solution: Path) -> Path:
    solution_dir_parts = list(src_solution.parts)
    for i, part in enumerate(solution_dir_parts):
        if "my_solution" in part:
            solution_dir_parts[i] += "_obfuscated"
    return Path(*solution_dir_parts)


def _find_solution_class(module_str: str) -> type[T] | None:  # type: ignore
    try:
        solution_module = importlib.import_module(module_str)
        solution_class = [
            value
            for _, value in inspect.getmembers(
                solution_module,
                lambda x: inspect.isclass(x) and issubclass(x, Solution) and x != Solution,
            )
        ][0]
        return solution_class
    except Exception:
        return None


@pytest.fixture(autouse=True, scope="session")
def tmp_solutions_dir(tmp_path_factory: pytest.TempPathFactory) -> dict[type[T], Path]:  # type: ignore  # noqa: C901
    """
    Each solution is placed in a temporary separate directory with the format ansys.solutions.$SOLUTION_NAME,
    to imitate the behaviour of a real solution.
    Includes copying method assets, product configs, instance managers, etc.
    TODO: Do on-demand when solutions are required.
    """
    solutions = [solution_dir for solution_dir in MOCKS_DIR.iterdir() if solution_dir.name.startswith("solution_")]
    solutions.extend(
        [solution_file for solution_file in SOLUTIONS_MOCKS_DIR.iterdir() if solution_file.suffix == ".py"],
    )

    solutions_dirs: dict[type[T], Path] = {}
    for i, solution in enumerate(solutions):
        # Copy solution
        solution_name = solution.name if solution.is_dir() else solution.stem
        root_dir = tmp_path_factory.getbasetemp() / f"my_solution_{i}" / "src"
        dest_solution_dir = root_dir / "ansys" / "solutions" / solution_name
        dest_solution_dir.parent.mkdir(exist_ok=True, parents=True)
        if solution.is_dir():
            shutil.copytree(solution, dest_solution_dir, dirs_exist_ok=True, ignore=IGNORE_PYC_FILES)
        else:
            dest_solution_dir.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(solution, dest_solution_dir / solution.name)

        # Copy product-related files
        for dir_name in ["instance_managers", "mock_products", "pim", "product_instance_configs"]:
            orig_dir = MOCKS_DIR / dir_name
            assert orig_dir.is_dir()
            dest_dir = dest_solution_dir / orig_dir.name
            shutil.copytree(orig_dir, dest_dir, dirs_exist_ok=True, ignore=IGNORE_PYC_FILES)

        # Fix imports from ``tests.mocks`` to ``ansys.solutions.solution_end_to_end``
        for f in dest_solution_dir.rglob("*"):
            if not f.is_file() or f.suffix != ".py":
                continue
            f.write_text(
                f.read_text().replace(f"from tests.mocks.{solution_name}", f"from ansys.solutions.{solution_name}"),
            )
            f.write_text(f.read_text().replace("from tests.mocks", f"from ansys.solutions.{solution_name}"))

        # Solutions are structured in different ways, adjust to every scenario
        solution_found = False
        if solution.is_dir() and (solution / "solution" / "definition.py").exists():
            if solution_class := _find_solution_class(f"tests.mocks.{solution_name}.solution.definition"):
                # Solution dir with a main.py and a solution/definition.py
                solutions_dirs[solution_class] = dest_solution_dir
                solution_found = True
        elif solution.is_dir():
            py_files = [f for f in solution.iterdir() if f.suffix == ".py"]
            if len(py_files) == 1:
                if solution_class := _find_solution_class(f"tests.mocks.{solution_name}.{py_files[0].stem}"):
                    # Solution dir that only contains a definition file and probably method assets or instance files
                    solutions_dirs[solution_class] = dest_solution_dir / py_files[0].name
                    solution_found = True
            elif solution_name == "solution_with_method_assets":
                # Solution dir that contains many definition files that share the same method assets
                for py_file in solution.iterdir():
                    if py_file.is_file() and py_file.suffix == ".py":  # noqa: SIM102
                        if solution_class := _find_solution_class(f"tests.mocks.{solution_name}.{py_file.stem}"):
                            solutions_dirs[solution_class] = dest_solution_dir / py_file.name
                            solution_found = True
        elif solution.is_file():  # noqa: SIM102
            if solution_class := _find_solution_class(f"tests.mocks.solutions.{solution_name}"):
                # Just a definition file
                solutions_dirs[solution_class] = dest_solution_dir / solution.name
                solution_found = True
        if not solution_found:
            print(f"Invalid solution {solution.name}. Not copying.")

    return solutions_dirs


@pytest.fixture(scope="session", autouse=True)
def obfuscate_e2e_solution(tmp_solutions_dir: dict[type, Path]):
    # Create directory for the obfuscated SolutionEndToEnd.
    solution_dir = tmp_solutions_dir[EndToEndSolution]

    obfuscated_solution_dir = _get_obfuscated_solution_path(solution_dir)

    obfuscated_solution_dir.parent.mkdir(exist_ok=True, parents=True)

    # Copy files from SolutionEndToEnd.
    shutil.copytree(solution_dir, obfuscated_solution_dir, dirs_exist_ok=True, ignore=IGNORE_PYC_FILES)

    # Compile solution
    assert compileall.compile_dir(obfuscated_solution_dir, legacy=True, quiet=True)


@pytest.fixture(scope="session")
def use_obfuscated_solution(request: pytest.FixtureRequest):
    if not hasattr(request, "param"):
        return False
    else:
        return request.param


@pytest.fixture(scope="session")
def solution_type(
    # solution_type is the entrypoint of session_glow. Make sure mock_appdata is called before session_glow to avoid
    # launching GLOW with the incorrect APPDATA.
    mock_appdata: Path,
    tmp_solutions_dir: dict[type[T], Path],
    request: pytest.FixtureRequest,
    use_obfuscated_solution: bool,
) -> tuple[type[T] | type[Solution], Path] | None:
    if not hasattr(request, "param"):
        return None
    if use_obfuscated_solution:
        obfuscated_solution_path = _get_obfuscated_solution_path(tmp_solutions_dir[request.param])
        if not obfuscated_solution_path.is_dir():
            pytest.fail(f"Obfuscation for Solution {str(request.param)} is not supported")
        else:
            return (request.param, obfuscated_solution_path)
    else:
        return (request.param, tmp_solutions_dir[request.param])


@pytest.fixture(scope="session")
def obfuscated_glow_source(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """It is never used by session_glow. The path returned must be explicitly used with run_glow."""

    # Create directory for the obfuscated glow src.

    obfuscated_glow_source = tmp_path_factory.getbasetemp() / "obfuscated_glow" / "src"
    obfuscated_glow_dir = obfuscated_glow_source / "ansys" / "saf" / "glow"
    obfuscated_glow_dir.parent.mkdir(exist_ok=True, parents=True)

    # Copy files from src.
    shutil.copytree(
        PACKAGE_ROOT / "src" / "ansys" / "saf" / "glow",
        obfuscated_glow_dir,
        dirs_exist_ok=True,
        ignore=IGNORE_PYC_FILES,
    )

    # Compile GLOW and remove .py files.
    assert compileall.compile_dir(obfuscated_glow_dir, legacy=True, quiet=True)

    for file in obfuscated_glow_dir.rglob("*.py"):
        file.unlink()

    return obfuscated_glow_source


# =================================================== [Auth] =================================================== #


@retry(stop=stop_after_attempt(100), wait=wait_fixed(0.2))
def _check_idp_is_running(p: Process):
    if not p.find_msg_in_output("Uvicorn running on http://"):
        raise TryAgain


@pytest.fixture(scope="session")
def session_idp_mock_server() -> Generator[str, None, None]:
    port = get_random_free_port()
    proc = Process(
        ["uvicorn", "tests.mocks.idp:app", "--host", "0.0.0.0", "--port", str(port)],
        bg=True,
        health_check=_check_idp_is_running,
    )
    try:
        proc.start()
        yield f"http://localhost:{port}"
    finally:
        proc.stop()


def _get_access_token(
    session_idp_mock_server: str,
    deployment_type: TestDeployment,
    expiration_seconds: int | None = None,
) -> str:
    # Issuer is part of the token and it is part of its validation. The issuer is typically extracted from the
    # request URL, either when contacting the IDP mock server or when configuring the auth dependency in GLOW.
    # When in DockerCompose, we are creating the token from the pytest process (access through "localhost") and
    # validating it from the Solution API process (access through "host.docker.internal"), thus resulting in an
    # issuer conflict. In order to bypass this, we are telling the IDP mock server to return a token with the
    # issuer name set to whatever value we pass in the request.
    issuer_name = session_idp_mock_server
    if deployment_type == TestDeployment.DockerCompose:
        issuer_name = issuer_name.replace("localhost", "host.docker.internal")
    return str(
        httpx2.post(
            f"{session_idp_mock_server}/protocol/openid-connect/token",
            json={"issuer_name": issuer_name, "token_expiration_seconds": expiration_seconds},
        ).json()["access_token"],
    )


@pytest.fixture
def access_token(session_idp_mock_server: str, deployment_type: TestDeployment) -> str:
    return _get_access_token(session_idp_mock_server, deployment_type)


@pytest.fixture
def get_access_token(session_idp_mock_server: str, deployment_type: TestDeployment) -> Callable[[int | None], str]:
    def _internal_get_access_token(expiration_seconds: int | None = None) -> str:
        return _get_access_token(session_idp_mock_server, deployment_type, expiration_seconds)

    return _internal_get_access_token


@pytest.fixture
def invalid_access_token() -> str:
    header = {"alg": "HS256"}
    claims: dict[str, Any] = {
        "iss": "http://invalid_issuer",
        "aud": ["invalid_aud"],
        "preferred_username": "invalid_partial_user_info_from_token",
    }
    key = OctKey.import_key("8f5c0e8d9b3f7e2c1a4d6b9f3e2c8a5d")
    invalid_token = jwt.encode(header, claims, key)
    return invalid_token


@pytest.fixture
def authenticated_client(
    session_glow: GlowBaseProcess[T],
    access_token: str,
    get_glow_client: Callable[[GlowBaseProcess[T], str | None], Client[T]],
) -> YieldFixture[Client[T]]:
    with get_glow_client(session_glow, access_token) as client:
        yield client


@pytest.fixture
def wrong_token_client(
    session_glow: GlowBaseProcess[T],
    invalid_access_token: str,
    get_glow_client: Callable[[GlowBaseProcess[T], str | None], Client[T]],
) -> YieldFixture[Client[T]]:
    with get_glow_client(session_glow, invalid_access_token) as client:
        yield client


@pytest.fixture
def existing_project(
    authenticated_client: Client[T],
    random_project_display_name: str,
) -> T:
    # project is created making sure there are no auth errors. Tests will then check that proper authentication rules
    # are in place and valid tokens are passed when accessing it.
    return authenticated_client.create_project(random_project_display_name)


class GlowApiKeyConfiguration(BaseGlowConfiguration):
    config_type = "api_key"

    def __init__(self, deployment_type: TestDeployment, api_key: str | None = None, api_key_file: Path | None = None):
        super().__init__(deployment_type)
        self._api_key = api_key
        self._api_key_file = api_key_file


class SetGlowApiKeyConfiguration(GlowApiKeyConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._api_key
        return EnvVars(env_vars={"GLOW_API_KEY": self._api_key}, only_api=["GLOW_API_KEY"])


class SetGlowApiKeyFileConfiguration(GlowApiKeyConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        # for docker, in production, it's recommended to use docker secrets and point here to
        # /run/secrets/my_secret_data.
        assert self._api_key_file
        return EnvVars(env_vars={"GLOW_API_KEY_FILE": self._api_key_file.as_posix()}, only_api=["GLOW_API_KEY_FILE"])

    @property
    def volumes_to_mount(self) -> Volumes:
        assert self._api_key_file
        return Volumes(common=[f"{self._api_key_file.as_posix()}:{self._api_key_file.as_posix()}"])


# =================================================== [Project] =================================================== #


@pytest.fixture
def function_project_without_context_mgr(
    session_glow: GlowBaseProcess[T],
    get_glow_client: Callable[[GlowBaseProcess[T]], Client[T]],
) -> YieldFixture[ProjectFixture[T]]:
    function_client = get_glow_client(session_glow)
    with ProjectFixture(session_glow, function_client) as project:
        yield project


@pytest.fixture
def safx_path(session_glow: GlowBaseProcess[T], function_client: Client[T], tmp_path: Path) -> Path:
    with ProjectFixture(session_glow, function_client, display_name="project") as function_project:
        function_project.project.export(tmp_path)
    return tmp_path / "project.safx"


@pytest.fixture
def log_something(function_project: ProjectFixture[T]):
    for step in STEPS_WITH_LOGGING_METHODS:
        getattr(function_project.project.steps, step).log_some_info()  # type: ignore
        getattr(function_project.project.steps, step).log_an_error()  # type: ignore


# =================================================== [Log files] =================================================== #


@pytest.fixture
def get_api_log_file_content(mock_appdata: Path) -> Callable[[str], str]:
    def _get_api_log_file_content(solution_name: str) -> str:
        log_directory = mock_appdata / "ansys" / "glow" / solution_name / "logs" / "api_server"
        assert log_directory.is_dir()
        log_files = list(log_directory.glob("log_*.log"))
        assert log_files
        log_files.sort(key=os.path.getmtime)
        return log_files[-1].read_text()

    return _get_api_log_file_content


@pytest.fixture
def get_method_log_file_content(mock_appdata: Path) -> Callable[[str, str], str]:
    def _get_method_log_file_content(solution_name: str, method_name: str) -> str:
        log_directory = mock_appdata / "ansys" / "glow" / solution_name / "logs" / "long_running_methods"
        assert log_directory.is_dir()
        log_files = list(log_directory.glob(f"log_{method_name}_*.log"))
        assert log_files
        log_files.sort(key=os.path.getmtime)
        return log_files[-1].read_text()

    return _get_method_log_file_content


# ============================================= [HPS interactive auth] ============================================== #


def interactive_authorization(
    driver: WebDriver,
    glow_proc: GlowBaseProcess[T],
    auth_repetition: int = 1,
    attempts: int = 30,
):
    @retry(
        stop=stop_after_attempt(attempts),
        wait=wait_fixed(1),
    )
    def get_auth_ui_from_logs(log: list[str], auth_repetition: int) -> str:
        auth_url = None
        auth_log_url_message = "Opening the browser for authorization..."
        auth_line = [line for line in log if auth_log_url_message in line]
        if len(auth_line) == auth_repetition:
            auth_url = auth_line[-1].split(auth_log_url_message)[1].strip()
        if auth_url is None:
            raise TryAgain

        return auth_url

    # get authorization URL from logs
    auth_url = get_auth_ui_from_logs(glow_proc.api_output, auth_repetition)
    assert auth_url

    # access URL and authenticate
    driver.get(auth_url)
    # The session started in the browser with the interactive authentication outlives the provided tokens,
    # so the login window might not appear in subsequent interactive authentications. If this happens, a
    # message should appear saying that the authorization is successful.
    try:
        wait_for_element_and_send_text(driver, "username", "repadmin")
        wait_for_element_and_send_text(driver, "password", "repadmin")
        wait_for_element_and_click(driver, "kc-login")
    except TimeoutException:
        wait_for_element(
            driver,
            "//*[text()='Authorization successful! You can close this tab.']",
            element_type=By.XPATH,
        )


def hps_user_pwd_signin(driver: WebDriver, hps_server_url: str):
    driver.get(hps_server_url)
    wait_for_element_and_send_text(driver, "username", "repadmin")
    wait_for_element_and_send_text(driver, "password", "repadmin")
    wait_for_element_and_click(driver, "kc-login")
    wait_for_element(driver, "//button[@title='Show/Hide active projects']", element_type=By.XPATH)


# =================================================== [Minerva] ===================================


@pytest.fixture(scope="session")
def minerva_settings():
    minerva_url = os.getenv("ANS_MINERVA_URL")
    minerva_db = os.getenv("ANS_MINERVA_DB")
    return {
        "ANS_MINERVA_URL": minerva_url,
        "ANS_MINERVA_AUTH__DATABASE": minerva_db,
        "ANS_MINERVA_AUTH__PASSWORD": "minerva",
        "ANS_MINERVA_AUTH__USER": "admin",
        "ANS_MINERVA_AUTH__CERTCONFIG": "",
    }


# =================================================== [GLOW Configs] ===================================


class ExternalApiUrlConfiguration(BaseGlowConfiguration):
    config_type = "external_api_url"

    def __init__(self, deployment_type: TestDeployment, external_api_url: str | None = None):
        super().__init__(deployment_type)
        self._external_api_url = external_api_url


class SetExternalApiUrlConfiguration(ExternalApiUrlConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._external_api_url
        return EnvVars(env_vars={"GLOW_EXTERNAL_API_URL": self._external_api_url})


class ChildCleanupConfiguration(BaseGlowConfiguration):
    config_type = "child_cleanup"


class DisableChildCleanupConfiguration(ChildCleanupConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"GLOW_METHOD_CLEANUP_CHILD_PROCS": "False"},
            only_api=["GLOW_METHOD_CLEANUP_CHILD_PROCS"],
        )


class MCPConfiguration(BaseGlowConfiguration):
    config_type = "mcp"


class DisableMCPConfiguration(MCPConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"GLOW_MCP_DISABLED": "True"},
            only_api=["GLOW_MCP_DISABLED"],
        )


class EnableMCPConfiguration(MCPConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"GLOW_MCP_DISABLED": "False"},
            only_api=["GLOW_MCP_DISABLED"],
        )


class EnableMCPWithAuthConfiguration(MCPConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_MCP_DISABLED": "False",
                "GLOW_AUTH_DISABLED": "False",
                "GLOW_AUTH_ISSUER_URL": "https://my-issuer-url",
                "GLOW_AUTH_CLIENT_ID": "my-client-id",
            },
            only_api=["GLOW_MCP_DISABLED", "GLOW_AUTH_DISABLED", "GLOW_AUTH_ISSUER_URL", "GLOW_AUTH_CLIENT_ID"],
        )


class SSETransportMCPConfiguration(MCPConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"GLOW_MCP_DISABLED": "False", "GLOW_MCP_TRANSPORT_MODE": "sse"},
            only_api=["GLOW_MCP_DISABLED", "GLOW_MCP_TRANSPORT_MODE"],
        )


class CustomPathMCPConfiguration(MCPConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"GLOW_MCP_DISABLED": "False", "GLOW_MCP_PATH": "/custom-mcp-path"},
            only_api=["GLOW_MCP_DISABLED", "GLOW_MCP_PATH"],
        )
