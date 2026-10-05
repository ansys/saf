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

from pathlib import Path
import platform
import subprocess
import sys
import tomllib
from typing import Any

import pytest
import pytest_mock

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_NAMESPACE, SOLUTION_TEMPLATE_PATH, SOLUTIONS_PRIVATE_PYPI_URL
from ansys.saf.cli._solutions.scaffolding import create_solution
from ansys.saf.cli._utilities.conversion import namespace_to_path, namespace_to_pkg_name
from tests.outcome_checks import check_agents_file, check_scaffolded_solution_files


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize("namespace", [DEFAULT_SOLUTION_NAMESPACE, "mycompany.solutions"])
def test_create_solution_sets_proper_cookiecutter_args(
    tmp_path: Path,
    mock_appdata: Path,
    mocker: pytest_mock.MockFixture,
    namespace: str,
):
    solution_name = "my_Solution Without-ui"  # spaces, upper case, hyphens and underscores are allowed
    solution_display_name = "My solution without-UI"
    ui_framework = "my_ui_framework"

    expected_solution_module_name = "my_solution_without_ui"
    expected_solution_package_name = "my-solution-without-ui"
    expected_solution_definition_class_name = "MySolutionWithoutUiSolution"
    expected_version = "0.0.0"
    expected_docker_name = "my-solution-without-ui_0-0-0"
    saf_executable = Path(sys.executable).parent / ("saf.cmd" if platform.system() == "Windows" else "saf")
    expected_saf_cli_version = subprocess.check_output([saf_executable, "--version"], text=True).strip()

    mock_cookiecutter = mocker.patch("ansys.saf.cli._solutions.scaffolding.cookiecutter")

    create_solution(solution_name, solution_display_name, ui_framework, namespace)

    mock_cookiecutter.assert_called_once_with(
        SOLUTION_TEMPLATE_PATH.as_posix(),
        output_dir=tmp_path.as_posix(),
        no_input=True,
        extra_context={
            "__solution_name": solution_name,
            "__solution_display_name": solution_display_name,
            "__ui_framework": ui_framework,
            "__solution_module_name": expected_solution_module_name,
            "__solution_definition_class_name": expected_solution_definition_class_name,
            "__solution_package_name": expected_solution_package_name,
            "__solution_namespace": namespace,
            "__solution_namespace_path": namespace_to_path(namespace),
            "__version": expected_version,
            "__docker_name": expected_docker_name,
            "__pkg_name": f"{namespace_to_pkg_name(namespace)}-{expected_solution_package_name}",
            "__pkg_namespace": f"{namespace}.{expected_solution_module_name}",
            "__pkg_path": f"{namespace_to_path(namespace)}/{expected_solution_module_name}",
            "__repository_url": "",
            "__appdata_directory": mock_appdata.as_posix(),
            "__python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "__saf_cli_version": expected_saf_cli_version,
            "__solutions_private_pypi_url": SOLUTIONS_PRIVATE_PYPI_URL,
        },
    )


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize("ui_framework", ["dash", "none"])
@pytest.mark.parametrize("namespace", [DEFAULT_SOLUTION_NAMESPACE, "mycompany.solutions"])
def test_create_solution(tmp_path: Path, ui_framework: str, namespace: str):
    solution_name = "my_Solution Without-ui"  # spaces, upper case, hyphens and underscores are allowed
    solution_display_name = "My solution without-UI"

    expected_solution_module_name = "my_solution_without_ui"
    expected_solution_package_name = "my-solution-without-ui"
    expected_solution_definition_class_name = "MySolutionWithoutUiSolution"
    expected_version = "0.0.0"
    expected_docker_name = "my-solution-without-ui_0-0-0"
    saf_executable = Path(sys.executable).parent / ("saf.cmd" if platform.system() == "Windows" else "saf")
    expected_saf_cli_version = subprocess.check_output([saf_executable, "--version"], text=True).strip()

    create_solution(solution_name, solution_display_name, ui_framework, namespace)

    # files are OK
    check_scaffolded_solution_files(tmp_path, solution_name, expected_solution_module_name, ui_framework, namespace)

    check_agents_file(
        tmp_path,
        solution_name,
        expected_solution_module_name,
        solution_display_name,
        expected_solution_definition_class_name,
        ui_framework,
    )

    # Check content of definition file
    namespace_path = namespace_to_path(namespace)
    solution_definition_file = (
        tmp_path / solution_name / "src" / namespace_path / expected_solution_module_name / "solution" / "definition.py"
    )
    solution_definition_content = solution_definition_file.read_text()
    assert f"class {expected_solution_definition_class_name}(Solution):" in solution_definition_content
    assert f'display_name: str = "{solution_display_name}"' in solution_definition_content

    # Check content of Dash app file
    if ui_framework == "dash":
        app_file = tmp_path / solution_name / "src" / namespace_path / expected_solution_module_name / "ui" / "app.py"
        app_content = app_file.read_text()
        assert "use_pages=True," in app_content
    else:
        ui_module = tmp_path / solution_name / "src" / namespace_path / expected_solution_module_name / "ui"
        assert not ui_module.exists()

    # Check content of pyproject.toml
    pyproject_file = tmp_path / solution_name / "pyproject.toml"
    pyproject_content = pyproject_file.read_text()
    assert f'name = "{namespace_to_pkg_name(namespace)}-{expected_solution_package_name}"' in pyproject_content
    assert f'version = "{expected_version}"' in pyproject_content
    assert f'[saf-cli-version]\nsaf-cli-version = "{expected_saf_cli_version}"'

    # Check content of docker-compose.yaml and .env
    for configuration in [
        "standalone",
        "standalone-with-hps",
        "distributed-deployment-template",
    ]:
        deployment_dir = tmp_path / solution_name / "deployments" / configuration

        # APP_NAME in .env should be set to the docker name
        env_content = (deployment_dir / ".env").read_text()
        assert f"APP_NAME={expected_docker_name}" in env_content

        docker_compose_content = (deployment_dir / "compose.yaml").read_text()
        # compose project name uses the APP_NAME env var
        assert "name: ${APP_NAME}" in docker_compose_content
        # service names are now generic (no docker-name prefix)
        if configuration != "distributed-deployment-template":
            assert "postgresql:" in docker_compose_content
        assert "  api:" in docker_compose_content
        if ui_framework != "none":
            assert "  ui:" in docker_compose_content
        else:
            assert "  ui:" not in docker_compose_content


def _scaffold_pyproject(tmp_path: Path, ui_framework: str) -> dict[str, Any]:
    """Scaffold a solution in the working directory and return its parsed pyproject.toml."""
    create_solution("dashboard_dependency_solution", "Dashboard Dependency Solution", ui_framework, "saf_cli_tests")
    return tomllib.loads((tmp_path / "dashboard_dependency_solution" / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.mark.usefixtures("tmp_path_as_working_dir", "mock_appdata")
def test_dash_solution_depends_on_projects_dashboard(tmp_path: Path):
    """Install the projects dashboard with the UI of a Dash solution, from the private feed only."""
    poetry = _scaffold_pyproject(tmp_path, "dash")["tool"]["poetry"]
    dependency = poetry["group"]["ui"]["dependencies"]["ansys-saf-projects-dashboard"]
    assert dependency["source"] == "solutions-private-pypi"
    assert dependency["allow-prereleases"] is True
    sources = {source["name"]: source for source in poetry["source"]}
    assert sources["solutions-private-pypi"]["priority"] == "explicit"
    assert sources["solutions-private-pypi"]["url"] == SOLUTIONS_PRIVATE_PYPI_URL


@pytest.mark.usefixtures("tmp_path_as_working_dir", "mock_appdata")
def test_solution_without_ui_does_not_depend_on_projects_dashboard(tmp_path: Path):
    """Do not add the projects dashboard nor the private feed to a solution without UI."""
    poetry = _scaffold_pyproject(tmp_path, "none")["tool"]["poetry"]
    assert "ui" not in poetry.get("group", {})
    assert "solutions-private-pypi" not in {source["name"] for source in poetry["source"]}
