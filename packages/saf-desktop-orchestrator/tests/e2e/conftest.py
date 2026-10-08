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
from importlib.util import find_spec
import logging
import os
from pathlib import Path
import sysconfig
from typing import Protocol
import venv
from zipfile import ZipFile

import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.desktop.orchestrator._orchestration.launcher import PROJECTS_DASHBOARD_MODULE
from ansys.saf.desktop.orchestrator._utilities.ip_utilities import get_local_ip
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.process import Process
from tests.e2e.app_starter_process import SolutionAppStarter
from tests.e2e.orchestrator_process import OrchestratorProcess
from tests.generate_grpc_certificates import (
    create_ca_certificate,
    create_client_certificate,
    generate_private_key,
    generate_server_certificates,
    save_certificate,
    save_private_key,
)

logger = logging.getLogger(__name__)


# ================================================== [Solutions] ================================================== #


MINIMAL_SOLUTION_WITH_DASH_UI = "tests.mocks.solutions.solution_with_minimal_dash_ui"
MINIMAL_PIM_SOLUTION = "tests.mocks.solutions.minimal_pim_solution"
MINIMAL_STREAMLIT_SOLUTION = "tests.mocks.solutions.minimal_streamlit_solution"
MINIMAL_COMPLETE_SOLUTION = "tests.mocks.solutions.minimal_complete_solution"
MINIMAL_DASH_UI_CUSTOM_SPLASH_SOLUTION = "tests.mocks.solutions.solution_with_minimal_dash_ui_custom_splash"


# ================================================== [Starter] ================================================== #


@pytest.fixture
def archived_solution() -> Path:
    archive = Path(__file__).parent.parent / "mocks" / "solution_with_minimal_dash_ui.saf"
    assert archive.is_file()
    return archive


@pytest.fixture
def solution_app_starter(
    archived_solution: Path,
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Generator[SolutionAppStarter, None, None]:
    compressed = False if not hasattr(request, "param") else bool(request.param)
    if not compressed:
        with ZipFile(archived_solution, "r") as archive:
            archive.extractall(tmp_path)

    sas_process = SolutionAppStarter(archived_solution if compressed else tmp_path)
    try:
        sas_process.start()
        yield sas_process
    finally:
        sas_process.stop()


@pytest.fixture
def isolated_desktop_portal_python(tmp_path: Path) -> tuple[Path, Path]:
    return _create_isolated_desktop_portal_python(tmp_path)


def _create_isolated_desktop_portal_python(tmp_path: Path) -> tuple[Path, Path]:
    isolated_venv = tmp_path / "desktop-portal-venv"
    venv.EnvBuilder(with_pip=False).create(isolated_venv)

    bootstrap_directory = tmp_path / "python-bootstrap"
    bootstrap_directory.mkdir()
    site_packages = Path(sysconfig.get_paths()["purelib"])
    (bootstrap_directory / "sitecustomize.py").write_text(
        "import site\n"
        f"site.addsitedir({str(site_packages)!r})\n"
        "import sys\n"
        "sys.modules['ansys_saf_projects_dashboard'] = None\n",
    )

    executable = isolated_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return executable, bootstrap_directory


@pytest.fixture
def portal_backend(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> tuple[str, dict[str, str], Path | None]:
    backend = str(request.param)
    environment = os.environ.copy()

    if backend == "projects-dashboard":
        if find_spec(PROJECTS_DASHBOARD_MODULE) is None:
            pytest.skip("Install ansys-saf-projects-dashboard to exercise dashboard mode.")
        return backend, environment, None

    if backend == "desktop-portal":
        if find_spec("ansys.saf.desktop.portal") is None:
            pytest.skip("Install ansys-saf-desktop-portal to exercise desktop portal mode.")
        executable, bootstrap_directory = _create_isolated_desktop_portal_python(tmp_path)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(bootstrap_directory), environment.get("PYTHONPATH", "")],
        )
        return backend, environment, executable

    if backend == "no-portal":
        return backend, environment, None

    raise ValueError(f"Unknown portal backend: {backend}")


# ================================================== [Orchestrator] ================================================== #


class OrchestrateSolution(Protocol):
    def __call__(
        self,
        args: list[str] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        wait_for_healthy: bool = True,
        healthy_retries: int = 240,
        pythonw: bool = False,
        bg: bool = True,
        python_exec: Path | None = None,
    ) -> OrchestratorProcess: ...


@pytest.fixture
def stop_orchestrator_after_yield(request: pytest.FixtureRequest) -> bool:
    # Use request.param if provided, otherwise use a default value
    return request.param if hasattr(request, "param") else True


@pytest.fixture
def orchestrate_solution(stop_orchestrator_after_yield: bool) -> YieldFixture[OrchestrateSolution]:

    procs: list[OrchestratorProcess] = []

    def _orchestrate_solution(
        args: list[str] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        wait_for_healthy: bool = True,
        healthy_retries: int = 240,
        pythonw: bool = False,
        bg: bool = True,
        python_exec: Path | None = None,
    ) -> OrchestratorProcess:

        @retry(stop=stop_after_attempt(healthy_retries), wait=wait_fixed(0.5))
        def find_final_orchestrator_startup_message(p: Process):
            if not p.find_msg_in_output("INFO - Additional services:"):
                raise TryAgain

        p = OrchestratorProcess(
            args if args is not None else [],
            cwd=cwd,
            env=env,
            health_check=find_final_orchestrator_startup_message if wait_for_healthy else None,
            use_pythonw=pythonw,
            bg=bg,
            python_exec=python_exec,
        )
        procs.append(p)
        p.start()
        return p

    yield _orchestrate_solution

    if stop_orchestrator_after_yield:
        for p in procs:
            p.stop()


# ================================================== [GRPC] ================================================== #


@pytest.fixture(scope="session")
def certificates_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create server and client certificates signed by a local CA. The validity is one day."""

    output_dir = tmp_path_factory.mktemp("certs-")

    servers = [
        f"localhost,127.0.0.1,{get_local_ip()}",
    ]

    days = 1
    client_common_name = "client"

    output_dir.mkdir(exist_ok=True)

    # Generate CA key and certificate for self-signing
    ca_key = generate_private_key()
    ca_cert = create_ca_certificate(ca_key, days)

    save_private_key(ca_key, output_dir / "ca.key")
    save_certificate(ca_cert, output_dir / "ca.crt")

    # Generate server certificates
    generate_server_certificates(ca_cert, ca_key, servers, days, output_dir.as_posix())

    # Generate client key and certificate
    client_key = generate_private_key()
    client_cert = create_client_certificate(client_key, ca_cert, ca_key, client_common_name, days)

    save_private_key(client_key, output_dir / "client.key")
    save_certificate(client_cert, output_dir / "client.crt")

    return output_dir
