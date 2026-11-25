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
from pathlib import Path
import re
import subprocess
from typing import cast
import uuid

from dotenv import dotenv_values
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_element_and_click,
    wait_for_expected_property,
)
from tests.e2e.conftest import (
    InstallSolution,
    NewSolution,
    add_hps_extra_to_solution,
    check_solution_launched_correctly,
    check_ui_is_functional,
    configure_docker_extra_packages,
    configure_hps_solution,
    configure_solution_to_store_result_in_file,
)


def check_otel(
    selenium_webdriver: WebDriver,
) -> None:
    otel_url = "http://127.0.0.1:18888"
    selenium_webdriver.get(otel_url)
    wait_for_element(selenium_webdriver, "blazor-error-ui", timeout=10)
    assert not selenium_webdriver.find_elements(By.XPATH, "//*[contains(text(), 'Telemetry endpoint is unsecured')]")


def get_solution_container_ports(env_path: Path) -> tuple[str | None, str | None]:
    """Return the API and UI container host ports defined in a solution deployment .env file"""
    env_vars = dotenv_values(env_path)
    api_port = env_vars.get("GLOW_API_CONTAINER_PORT")
    ui_port = env_vars.get("GLOW_UI_CONTAINER_PORT")

    if not api_port or not ui_port:
        raise ValueError(
            "GLOW_API_CONTAINER_PORT and GLOW_UI_CONTAINER_PORT must be set in the .env file of the solution.",
        )
    return api_port, ui_port


def _update_compose_environment(env_path: Path, values: dict[str, str]) -> None:
    lines = env_path.read_text().splitlines()
    updated: set[str] = set()
    for index, line in enumerate(lines):
        key, separator, _ = line.partition("=")
        if separator and key in values:
            lines[index] = f"{key}={values[key]}"
            updated.add(key)
    lines.extend(f"{key}={value}" for key, value in values.items() if key not in updated)
    env_path.write_text("\n".join(lines) + "\n")


def _run_docker_command(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


@pytest.fixture
def deployment_ui_path_prefix(request: pytest.FixtureRequest) -> str:
    """Path prefix under which the solution UI is served, as done behind a reverse proxy."""
    return getattr(request, "param", "")


@pytest.fixture
def setup_deployment(
    request: pytest.FixtureRequest,
    new_solution: NewSolution,
    install_solution: InstallSolution,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    session_solution_namespace: str,
    deployment_ui_path_prefix: str,
) -> Generator[tuple[str | None, str | None], None, None]:
    """Creates a new solution, starts Docker Compose, yields ports, then tears down."""

    # Create a new solution
    param = cast("tuple[bool, str] | str", request.param)
    result_via_file, deployment_type = param if isinstance(param, tuple) else (False, param)
    solution_name = "my_solution"
    new_solution(
        ["--solution-name", solution_name, "--namespace", session_solution_namespace],
        input_str="\n\n",
        cwd=tmp_path,
    )
    solution_dir = tmp_path / solution_name
    configure_docker_extra_packages(solution_dir)
    compose_file = Path(solution_dir / "deployments" / deployment_type / "compose.yaml")
    env_path = solution_dir / "deployments" / deployment_type / ".env"

    if not compose_file.exists():
        raise FileNotFoundError(f"Docker Compose file not found: {compose_file}")

    if deployment_ui_path_prefix:
        env_path.write_text(
            re.sub(
                r"^GLOW_UI_PATH_PREFIX=.*$",
                f"GLOW_UI_PATH_PREFIX={deployment_ui_path_prefix}",
                env_path.read_text(),
                flags=re.MULTILINE,
            ),
        )

    if result_via_file:
        monkeypatch.setenv("MACHINE_IP", "host.docker.internal")
        configure_solution_to_store_result_in_file(solution_dir, solution_name, session_solution_namespace)
        if deployment_type == "standalone-with-hps":
            # Install the selected groups before adding the HPS extra.
            install_solution([solution_name, "-d", "desktop"])
            add_hps_extra_to_solution(solution_dir, solution_name)
    elif deployment_type == "standalone-with-hps":
        # ensure that HPS hostname is reachable from the solution container
        monkeypatch.setenv("MACHINE_IP", "host.docker.internal")
        # Install the selected groups before configuring HPS.
        install_solution([solution_name, "-d", "desktop"])
        configure_hps_solution(solution_dir, solution_name, session_solution_namespace)

    # Start containers using Docker Compose
    compose_dir = compose_file.parent
    subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "--build", "-d"], check=True, cwd=compose_dir)
    api_port, ui_port = get_solution_container_ports(env_path)
    try:
        yield api_port, ui_port
    finally:
        # Teardown: Stop and remove containers, networks and volumes.
        subprocess.run(["docker", "compose", "-f", str(compose_file), "down", "-v"], check=True, cwd=compose_dir)


@pytest.mark.parametrize("deployment_type", ["DockerCompose"], indirect=True)
@pytest.mark.usefixtures("deployment_type")
@pytest.mark.parametrize("setup_deployment", ["standalone"], indirect=True)
def test_solution_standalone_deployment(
    setup_deployment: tuple[str, str],
    selenium_webdriver: WebDriver,
    tmp_path: Path,
):
    """
    Test that the containerized deployment is working correctly and the solution produces expected results.
    """

    api_port, ui_port = setup_deployment
    compose = tmp_path / "my_solution" / "deployments" / "standalone" / "compose.yaml"
    for service in ("api", "ui"):
        subprocess.run(
            ["docker", "compose", "-f", str(compose), "exec", "-T", service, "uv", "lock", "--check", "--offline"],
            check=True,
            capture_output=True,
            text=True,
        )
    project_ui_url = check_solution_launched_correctly(api_port, ui_port)
    check_ui_is_functional(selenium_webdriver, project_ui_url=project_ui_url)
    check_otel(selenium_webdriver)


@pytest.mark.parametrize("deployment_type", ["DockerCompose"], indirect=True)
@pytest.mark.usefixtures("deployment_type")
def test_uv_solution_compose_variants_build_and_start(
    new_solution: NewSolution,
    tmp_path: Path,
):
    """Build and start every generated Compose variant from the same UV-locked solution."""
    solution_name = "uv_compose_smoke"
    new_solution(
        ["--solution-name", solution_name, "--namespace", "saf.solutions"],
        input_str="\n\n",
        cwd=tmp_path,
    )
    solution_root = tmp_path / solution_name
    configure_docker_extra_packages(solution_root)

    standalone_dir = solution_root / "deployments" / "standalone"
    standalone_env = standalone_dir / ".env"
    app_name = str(dotenv_values(standalone_env)["APP_NAME"])
    app_image_version = str(dotenv_values(standalone_env)["APP_IMAGE_VERSION"])
    api_port = "18080"
    ui_port = "18081"

    variants = [
        ("standalone", False, False),
        ("standalone-with-hps", True, False),
        ("distributed-deployment-template", True, True),
        ("external", False, False),
    ]
    for variant, needs_external_network, needs_database_override in variants:
        deployment_dir = solution_root / "deployments" / variant
        compose_file = deployment_dir / "compose.yaml"
        external_network = f"{app_name}-{uuid.uuid4().hex[:8]}"
        env_values = {
            "GLOW_API_CONTAINER_PORT": api_port,
            "GLOW_UI_CONTAINER_PORT": ui_port,
            "EXT_NETWORK_NAME": external_network,
            "DOMAIN_NAME": "example.invalid",
            "TRAEFIK_PORT": "443",
            "PG_HOST": "postgresql",
            "PG_PORT": "5432",
            "PG_USER": "glow",
            "PG_PASSWORD": "glow",
            "APPDATA": "/tmp",
            "GLOW_HPS_HOST": "127.0.0.1",
            "GLOW_HPS_PORT": "8443",
            "GLOW_HPS_USERNAME": "glow",
            "GLOW_HPS_PASSWORD": "glow",
        }
        _update_compose_environment(deployment_dir / ".env", env_values)

        compose_command = ["docker", "compose", "-f", str(compose_file)]
        if needs_database_override:
            override_file = deployment_dir / "compose.smoke-override.yaml"
            override_file.write_text(
                "services:\n"
                "  postgresql:\n"
                "    image: postgres:16.0\n"
                "    environment:\n"
                "      POSTGRES_USER: glow\n"
                "      POSTGRES_PASSWORD: glow\n"
                f"      POSTGRES_DB: db_{app_name}\n"
                "    healthcheck:\n"
                '      test: ["CMD-SHELL", "pg_isready -U glow"]\n'
                "      interval: 5s\n"
                "      retries: 20\n"
                "    networks:\n"
                "      - external-network\n"
                "  api:\n"
                "    depends_on:\n"
                "      postgresql:\n"
                "        condition: service_healthy\n",
            )
            compose_command.extend(["-f", str(override_file)])

        network_created = False
        try:
            if variant == "external":
                for service in ("api", "ui"):
                    image = f"{app_name}-{service}"
                    _run_docker_command(
                        ["docker", "image", "tag", image, f"{image}:{app_image_version}"],
                        deployment_dir,
                    )
                up_command = [*compose_command, "up", "--detach", "--wait", "--wait-timeout", "300"]
            else:
                up_command = [*compose_command, "up", "--detach", "--build", "--wait", "--wait-timeout", "300"]
            if needs_external_network:
                _run_docker_command(["docker", "network", "create", external_network], deployment_dir)
                network_created = True
            _run_docker_command(up_command, deployment_dir)

            for service in ("api", "ui"):
                _run_docker_command(
                    [
                        *compose_command,
                        "exec",
                        "--no-TTY",
                        service,
                        "uv",
                        "lock",
                        "--check",
                        "--offline",
                    ],
                    deployment_dir,
                )
        finally:
            _run_docker_command(
                [*compose_command, "down", "--volumes", "--remove-orphans"],
                deployment_dir,
            )
            if network_created:
                _run_docker_command(["docker", "network", "rm", external_network], deployment_dir)


@pytest.mark.parametrize("deployment_type", ["DockerCompose"], indirect=True)
@pytest.mark.usefixtures("deployment_type")
@pytest.mark.parametrize("deployment_ui_path_prefix", ["/my-solution/"], indirect=True)
@pytest.mark.parametrize("setup_deployment", ["standalone"], indirect=True)
def test_solution_standalone_deployment_with_ui_path_prefix(
    setup_deployment: tuple[str, str],
    deployment_ui_path_prefix: str,
    selenium_webdriver: WebDriver,
):
    """
    Test that the solution UI works when served under a path prefix, as done in distributed deployments where
    GLOW_UI_PATH_PREFIX is set. Regression test: pages used to render the 404 content because the prefix was
    neither stripped from nor prepended to the routes.
    """
    api_port, ui_port = setup_deployment
    ui_path_prefix = deployment_ui_path_prefix.rstrip("/")
    project_ui_url = check_solution_launched_correctly(api_port, ui_port, ui_path_prefix=ui_path_prefix)
    check_ui_is_functional(selenium_webdriver, project_ui_url=project_ui_url, ui_path_prefix=ui_path_prefix)

    wait_for_element_and_click(selenium_webdriver, "//*[contains(text(), 'Second Step')]", element_type=By.XPATH)
    wait_for_element(
        selenium_webdriver,
        "//*[contains(text(), 'This page is empty for now.')]",
        element_type=By.XPATH,
    )
    assert selenium_webdriver.current_url.startswith(
        f"http://127.0.0.1:{ui_port}{ui_path_prefix}/projects/",
    )

    selenium_webdriver.refresh()
    wait_for_element(
        selenium_webdriver,
        "//*[contains(text(), 'This page is empty for now.')]",
        element_type=By.XPATH,
    )

    wait_for_element_and_click(selenium_webdriver, "//*[contains(text(), 'First Step')]", element_type=By.XPATH)
    wait_for_element(selenium_webdriver, "result")
    assert selenium_webdriver.current_url == f"{project_ui_url}/first-step"


@pytest.mark.parametrize("deployment_type", ["DockerCompose"], indirect=True)
@pytest.mark.usefixtures("deployment_type")
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize("setup_deployment", ["standalone-with-hps"], indirect=True)
def test_solution_standalone_deployment_with_hps(
    hps_scaler: None,
    setup_deployment: tuple[str, str],
    selenium_webdriver: WebDriver,
):
    """
    Test that the containerized deployment with HPS is working correctly and the solution produces expected results.
    """

    api_port, ui_port = setup_deployment
    project_ui_url = check_solution_launched_correctly(api_port, ui_port)
    check_ui_is_functional(selenium_webdriver, project_ui_url=project_ui_url, timeout=180)
    check_otel(selenium_webdriver)


@pytest.mark.parametrize("deployment_type", ["DockerCompose"], indirect=True)
@pytest.mark.usefixtures("deployment_type")
@pytest.mark.parametrize(
    "setup_deployment",
    [(True, "standalone")],
    indirect=True,
)
def test_solution_standalone_deployment_using_get_data_with_url_substitution(
    setup_deployment: tuple[str, str],
    selenium_webdriver: WebDriver,
):
    """
    Test that get_data client method functions correctly in on-prem deployment
    """
    _run_solution_in_standalone_deployment_using_get_data_with_url_substitution(
        setup_deployment,
        selenium_webdriver,
    )


@pytest.mark.parametrize("deployment_type", ["DockerCompose"], indirect=True)
@pytest.mark.usefixtures("deployment_type")
@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.usefixtures("instance_system_type")
@pytest.mark.parametrize("setup_deployment", [(True, "standalone-with-hps")], indirect=True)
def test_solution_standalone_hps_deployment_using_get_data_with_url_substitution(
    hps_scaler: None,
    setup_deployment: tuple[str, str],
    selenium_webdriver: WebDriver,
):
    """
    Test that get_data client method functions correctly in on-prem deployment
    """
    _run_solution_in_standalone_deployment_using_get_data_with_url_substitution(
        setup_deployment,
        selenium_webdriver,
    )


def _run_solution_in_standalone_deployment_using_get_data_with_url_substitution(
    setup_deployment: tuple[str, str],
    selenium_webdriver: WebDriver,
):
    api_port, ui_port = setup_deployment
    project_ui_url = check_solution_launched_correctly(api_port, ui_port)
    check_ui_is_functional(selenium_webdriver, project_ui_url=project_ui_url)

    wait_for_element_and_click(selenium_webdriver, "fetch-from-file")
    # this is a simple file fetch so 10 seconds is enough time
    wait_for_expected_property(selenium_webdriver, "file-result", "value", "7.0", 10)
