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
import random
import string
from typing import Any, Protocol, TypeVar, cast
import uuid

import httpx2
import pytest

from ansys.saf.testing._common.common import YieldFixture
from ansys.saf.testing._solution.const import TestDeployment
from ansys.saf.testing._solution.end_to_end._typing import ClientProtocol, SolutionProtocol
from ansys.saf.testing._solution.end_to_end.glow_execution_configurations import HpsTokenPassThroughAuth
from ansys.saf.testing._solution.end_to_end.glow_process import GlowBaseProcess
from ansys.saf.testing._solution.end_to_end.project_context import ProjectFixture

T = TypeVar("T", bound=SolutionProtocol)


class GlowClientFactory(Protocol):
    def __call__(self, glow_proc: GlowBaseProcess[Any], access_token: str | None = None) -> ClientProtocol[Any]: ...


# =================================================== [Client] =================================================== #


@pytest.fixture
def function_client(
    session_glow: GlowBaseProcess[T],
    get_glow_client: GlowClientFactory,
) -> YieldFixture[ClientProtocol[T]]:
    with get_glow_client(session_glow, None) as client:
        yield cast(ClientProtocol[T], client)


@pytest.fixture(scope="session")
def get_glow_client(
    deployment_type: TestDeployment,
) -> YieldFixture[GlowClientFactory]:
    """The python client to access the glow API from the given solution."""
    mp = pytest.MonkeyPatch()  # default fixture is function-scoped.

    def _glow_client(glow_proc: GlowBaseProcess[T], access_token: str | None = None) -> ClientProtocol[T]:
        # Careful! even if the deployment_type is DockerCompose, the client used here is initialized
        # in the pytest session. It's not a client within a container, such as what we do in test_dash_ui.
        # We are testing an external client communicating with a containerized API server.
        # Thus, we need to configure the deployment_type for this environment if we want something
        # beyond the default settings (e.g., Desktop).
        if deployment_type == TestDeployment.DockerCompose:
            mp.setenv("GLOW_DEPLOYMENT", TestDeployment.DockerCompose.value)
            mp.setenv("GLOW_UI_PROJECT_FILES_DIRECTORY", str(glow_proc.project_files_directory))
            mp.setenv("GLOW_PROJECT_FILES_DIRECTORY", f"{glow_proc.project_files_directory}")
            hps_auth_configuration = glow_proc.applied_configurations["hps_auth_configuration"]
            if isinstance(hps_auth_configuration, HpsTokenPassThroughAuth):
                env_vars = hps_auth_configuration.env_vars_to_configure.env_vars
                glow_auth_issuer_url = env_vars.get("GLOW_AUTH_ISSUER_URL") or ""
                mp.setenv("GLOW_AUTH_ISSUER_URL", glow_auth_issuer_url)

        # Keep GLOW an optional hidden dependency. We don't want to declare it to avoid a circular dependency
        # between GLOW and SAF-SDK Testing. Anyway, any project using this fixture for e2e testing a GLOW-based
        # Solution will already have GLOW as a dependency.
        from ansys.saf.glow.client import Client  # pyright: ignore[reportMissingImports, reportUnknownVariableType]

        client = Client(  # pyright: ignore[reportUnknownVariableType]
            glow_proc.solution_type,  # pyright: ignore[reportArgumentType]
            glow_proc.base_api_url,
            access_token=access_token,
        )
        return cast(ClientProtocol[T], client)

    yield _glow_client

    mp.undo()


# =================================================== [Project] =================================================== #


@pytest.fixture
def get_project_list() -> Callable[[str], list[dict[str, str]]]:
    def _get_project_list(base_api_url: str) -> list[dict[str, str]]:
        project_list_response = httpx2.get(f"{base_api_url}/projects")

        assert project_list_response.status_code == 200

        return project_list_response.json()

    return _get_project_list


@pytest.fixture(scope="session")
def random_project_name() -> Callable[[], str]:
    def _random_project_name() -> str:
        # New portal FE limits to 35 characters.
        return str(uuid.uuid4())[:30]

    return _random_project_name


@pytest.fixture
def random_project_display_name() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def random_project_id() -> Callable[[], str]:
    def _random_project_id() -> str:
        return "".join(random.choices(str(string.ascii_letters + string.digits), k=8))

    return _random_project_id


@pytest.fixture
def function_project(
    session_glow: GlowBaseProcess[T],
    function_client: ClientProtocol[T],
) -> YieldFixture[ProjectFixture[T]]:
    with ProjectFixture(session_glow, function_client) as project:
        yield project


@pytest.fixture
def create_project(
    session_glow: GlowBaseProcess[T],
    function_client: ClientProtocol[T],
) -> YieldFixture[Callable[[], ProjectFixture[T]]]:
    created_projects: list[ProjectFixture[T]] = []

    def _create_project():
        project = ProjectFixture(session_glow, function_client)
        created_projects.append(project)
        return project

    yield _create_project

    for project in created_projects:
        project.delete()


@pytest.fixture(scope="class")
def class_project_name(
    session_glow: GlowBaseProcess[T],
    get_glow_client: GlowClientFactory,
) -> YieldFixture[str]:
    # Create a project that will be used by all tests in the class. However, return the project name and let every
    # test retrieve it with its own function-scoped client using `function_class_project`` fixture.
    # Note that in case of reruns, the project state is not reset and it's the one left by the previous test run. This
    # can easily lead to subsequent failures if the test is not properly designed.
    with get_glow_client(session_glow) as client:
        project = ProjectFixture(session_glow, client)
        project_name = project.project_name
    try:
        yield project_name
    finally:
        # Recreate project_fixture, since session_glow object may have changed during the tests executed within
        # this class. For example, if a test is rerun and session_glow has new ports assigned.
        with get_glow_client(session_glow) as client:
            project = ProjectFixture(session_glow, client, project_name=project_name)
            project.delete()


@pytest.fixture(scope="class")
def class_project(
    class_project_name: str,
    session_glow: GlowBaseProcess[T],
    get_glow_client: GlowClientFactory,
) -> YieldFixture[ProjectFixture[T]]:
    # Only use this fixture in other class-scoped fixtures that initialize the project (e.g., launching the product).
    # Tests should use `function_class_project` instead.
    with get_glow_client(session_glow) as client:
        yield ProjectFixture(session_glow, client, project_name=class_project_name)


@pytest.fixture
def function_class_project(
    class_project_name: str,
    session_glow: GlowBaseProcess[T],
    get_glow_client: GlowClientFactory,
) -> YieldFixture[ProjectFixture[T]]:
    """Tests importing this fixture will have access to a class-scoped project with function-scoped client."""
    # The project fixture and the client injected are function-scoped to make sure it's recreated with the
    # correct ports in the case of test reruns. Nevertheless, the project itself is indeed class-scoped.
    with get_glow_client(session_glow) as client:
        yield ProjectFixture(session_glow, client, project_name=class_project_name)
