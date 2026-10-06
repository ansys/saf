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
import importlib
import inspect
import logging
import os
from pathlib import Path
import platform
import shutil
from typing import TypeVar
from unittest import mock

import psutil
import pytest

from ansys.saf.glow.solution import Solution
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.network import get_docker_gateway_ip
from ansys.saf.testing.solution.end_to_end import (
    AEDTVersionConfiguration,
    DefaultProductHost,
    GlowBaseProcess,
    WithProductHost,
)
from tests.conftest import IGNORE_PYC_FILES
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Solution)
ROOTDIR = Path.cwd()
SOLUTIONS_DIR = ROOTDIR / "tests" / "mocks"


# =================================================== [Global setup] ================================================ #


@pytest.fixture(autouse=True)
def autouse_test_log_management(test_log_management: None) -> None:
    # Properly add test_name to the logs and clear output before each test.
    ...


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
def check_session_glow_health(  # noqa: UP047
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
def tmp_solutions_dir(tmp_path_factory: pytest.TempPathFactory) -> dict[type[T], Path]:  # type: ignore
    """
    Each solution is placed in a temporary separate directory with the format ansys.solutions.$SOLUTION_NAME,
    to imitate the behaviour of a real solution.
    Includes copying method assets, product configs, instance managers, etc.
    TODO: Do on-demand when solutions are required.
    """
    solutions = [solution_dir for solution_dir in SOLUTIONS_DIR.iterdir() if solution_dir.name.startswith("solution_")]

    solutions_dirs: dict[type[T], Path] = {}
    for i, solution in enumerate(solutions):
        # Copy solution
        solution_name = solution.name if solution.is_dir() else solution.stem
        root_dir = tmp_path_factory.getbasetemp() / f"my_solution_{i}" / "src"
        dest_solution_dir = root_dir / "ansys" / "solutions" / solution_name
        dest_solution_dir.parent.mkdir(exist_ok=True, parents=True)
        shutil.copytree(solution, dest_solution_dir, dirs_exist_ok=True, ignore=IGNORE_PYC_FILES)

        # Fix imports from ``tests.mocks`` to ``ansys.solutions.solution_end_to_end``
        for f in dest_solution_dir.rglob("*"):
            if not f.is_file() or f.suffix != ".py":
                continue
            f.write_text(
                f.read_text().replace(f"from tests.mocks.{solution_name}", f"from ansys.solutions.{solution_name}"),
            )
            f.write_text(f.read_text().replace("from tests.mocks", f"from ansys.solutions.{solution_name}"))

        if solution_class := _find_solution_class(f"tests.mocks.{solution_name}.solution.definition"):
            solutions_dirs[solution_class] = dest_solution_dir
        else:
            print(f"Invalid solution {solution.name}. Not copying.")

    return solutions_dirs


@pytest.fixture(scope="session")
def solution_type(  # noqa: UP047
    tmp_solutions_dir: dict[type[T], Path],
    request: pytest.FixtureRequest,
) -> tuple[type[T] | type[Solution], Path] | None:
    if not hasattr(request, "param"):
        return None
    return (request.param, tmp_solutions_dir[request.param])


# =================================================== [Networking] ===================================


DOCKER_GATEWAY_IP = get_docker_gateway_ip() if platform.system() == "Linux" else "127.0.0.1"


# =================================================== [Flagships] ===================================


@pytest.fixture(scope="session")
def ansys_release(request: pytest.FixtureRequest) -> str:
    selected_option = str(request.config.getoption("--flagship-versions"))
    if selected_option not in ["latest", "previous", "both"]:
        raise ValueError("Accepted values for --flagship-versions are 'latest', 'previous', 'both'.")

    selected_release = request.param if hasattr(request, "param") else LATEST_VERSION

    versions = {"latest": [LATEST_VERSION], "previous": [PREVIOUS_VERSION], "both": [LATEST_VERSION, PREVIOUS_VERSION]}

    if selected_release not in versions[selected_option] and selected_release in [LATEST_VERSION, PREVIOUS_VERSION]:
        # allow for testing versions outside [LATEST_VERSION, PREVIOUS_VERSION]
        pytest.skip(f"Version {selected_release} not selected.")

    return selected_release


@pytest.fixture(scope="module")
def configure_aedt_installation_dir(
    session_glow: GlowBaseProcess[EndToEndSolution],
    ansys_release: str,
) -> Generator[None, None, None]:
    session_glow.change_configuration(AEDTVersionConfiguration, version=ansys_release)
    yield
    session_glow.configure_default_execution()


def kill_mechanical(port: int) -> None:
    # Mechanical procs is sometimes left in a zombie state which prevents future Mechanical procs of
    # launching correctly.
    for proc in psutil.process_iter(["cmdline"]):  # pyright: ignore[reportUnknownMemberType]
        cmdline = proc.info["cmdline"]
        if not cmdline:
            continue
        try:
            if f"-GRPC {port}" in " ".join(cmdline):
                proc.kill()
        except psutil.NoSuchProcess:
            pass


GEOMETRY_251_ERROR_MSGS = [
    "Ansys Geometry version 251 cannot be found",  # if it's not even installed
    "Only Windows platform is supported for Geometry version 251.",  # if it's installed (e.g., private binaries)
]


def get_geometry_expected_msg(ansys_release: str, transport_mode: str, bind_host: str) -> str:
    if platform.system() == "Windows":
        if transport_mode == "WNUA":
            if ansys_release == "251":
                return f"Server started. Listening on endpoint: {bind_host}:"
            else:
                return f"Server will listen with WNUA security on: {bind_host}:"
        elif transport_mode == "insecure":
            if ansys_release == "251":
                return f"Server started. Listening on endpoint: {bind_host}:"
            else:
                return f"Server will listen with insecure channel on: {bind_host}:"
        else:
            raise RuntimeError(f"Unknown transport mode: {transport_mode}")
    else:
        if transport_mode == "UDS":
            return "ApiServer: listening on UNIX socket: /tmp/"
        elif transport_mode == "mTLS":
            return f"Server will listen with mutual TLS on: {bind_host}:"
        elif transport_mode == "insecure":
            return f"Server will listen with insecure channel on: {bind_host}:"
        else:
            raise RuntimeError(f"Unknown transport mode: {transport_mode}")


@pytest.fixture(scope="class")
def configure_product_host(session_glow: GlowBaseProcess[EndToEndSolution], product_host: str | None) -> None:
    if product_host:
        session_glow.change_configuration(WithProductHost, product_host=product_host)
    else:
        session_glow.change_configuration(DefaultProductHost)
