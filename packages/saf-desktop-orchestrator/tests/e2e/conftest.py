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
import logging
from pathlib import Path
from typing import Protocol
from zipfile import ZipFile

import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

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

"""
Remaining gaps in projects-dashboard and desktop-portal support.

The main routing paths are now covered: the dashboard E2E checks /projects responds, and the isolated-venv desktop-portal E2E checks the portal starts when dashboard discovery is suppressed. The remaining gaps are:

- UI workflows: Both tests check service availability, but neither uses Selenium to create/select a project through its UI. The proxy test skips its legacy-portal UI workflow in dashboard mode.
- Dashboard path override: No E2E test sets SAF_DESKTOP_PROJECTS_DASHBOARD_PATH and verifies the configured route responds. Unit coverage exists for path normalization.
- Legacy portal custom port: The custom-port E2E exercises the dashboard branch when the package is installed. It does not verify PORTAL_UI_PORT in the isolated desktop-portal fallback environment.
- Fallback variants: There’s no E2E for --portal with Streamlit, or for the legacy ansys.saf.portal package fallback; the isolated test covers the newer ansys.saf.desktop.portal.
- Mode combinations: Pre-load and pythonw are tested in the normal environment, but don’t explicitly verify dashboard routing; the isolated desktop-portal case doesn’t cover pythonw.
- UI environment contract: E2E doesn’t inspect the solution UI’s GLOW_PORTAL_URL or CORS environment directly; those are currently verified by unit tests.

Relevant tests: test_orchestrator_process.py, test_otlp.py, and test_verbosity.py.
"""

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
