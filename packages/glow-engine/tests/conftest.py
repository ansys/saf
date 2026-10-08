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

import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
import uuid

import docker
import jwt
import pytest

from ansys.saf.testing.common import find_exec_in_venv
from ansys.saf.testing.docker import is_docker_installed_fun
from ansys.saf.testing.hps.process import HpsDeploymentProcess
from ansys.saf.testing.platform_specific import is_ci_run
from ansys.saf.testing.pytest import is_marker_within_collected_tests

IGNORE_PYC_FILES = shutil.ignore_patterns("*__pycache__*", "*.pyc*")
PYTEST_LOGS_DIR = "pytest_logs"
TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
MOCKS_DIR = TESTS_DIR / "mocks"
SOLUTIONS_MOCKS_DIR = MOCKS_DIR / "solutions"
E2E_TESTS_DIR = TESTS_DIR / "e2e"


# =================================================== [Pytest parameters] ========================================== #


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--workflow-docker-id", action="store", help="Workflow docker id.")


# =================================================== [Pytest session configuration] ================================ #


def pytest_configure(config: pytest.Config) -> None:
    """This hook will be run once before the nodes are setup, and then once for each node (if in parallel)."""

    if not hasattr(config, "workerinput"):
        # Runs once in master before xdist workers are initialized
        if config.getoption("--workflow-docker-id"):
            workflow_docker_id = config.getoption("--workflow-docker-id")
        else:
            workflow_docker_id = str(uuid.uuid4())
        config.session_unique_id = workflow_docker_id  # type: ignore
    else:
        # Runs on every xdist worker
        config.session_unique_id = config.workerinput["session_unique_id"]  # type: ignore


def pytest_configure_node(node: pytest.Collector | pytest.Item) -> None:
    node.workerinput["session_unique_id"] = node.config.session_unique_id  # type: ignore


def pytest_sessionfinish(session: pytest.Session, exitstatus: pytest.ExitCode) -> None:
    # This is executed even when doing ctrl-c in the session.
    if not hasattr(session.config, "workerinput"):
        cleanup_errors: list[str] = []

        # Only master cleans up images at the end
        try:
            _clean_solution_docker_resources(session.config.session_unique_id)  # type: ignore
        except Exception as e:
            cleanup_errors.append(f"Failed to cleanup solution docker resources: {e}")

        try:
            _clean_hps_docker_resources(session.items, bool(session.config.getoption("--ext-hps")))
        except Exception as e:
            cleanup_errors.append(f"Failed to cleanup HPS docker resources: {e}")

        # Print log location for users
        log_dir = Path.cwd() / PYTEST_LOGS_DIR
        if log_dir.exists():
            print(f"\n{'=' * 80}")
            if is_ci_run():
                print("Test logs will be available as GitHub Actions job artifacts named 'pytest_logs_*'")
            else:
                print(f"Test logs have been exported to: {log_dir.absolute()}")
            print(f"{'=' * 80}\n")

        if cleanup_errors:
            raise Exception("\n".join(cleanup_errors))


def _clean_solution_docker_resources(session_unique_id: str) -> None:  # noqa: C901
    # TODO: this is going to leave networks, volumes and non-solution containers such as postgresql
    if not is_docker_installed_fun():
        return

    with docker.APIClient() as client:
        not_removed = []

        # Delete created images
        session_images: Any = client.images(filters={"reference": f"*{session_unique_id}*"})  # type: ignore

        for image in session_images:  # type: ignore
            tries = 100
            running_containers = []

            while tries >= 0:
                running_containers = client.containers(filters={"ancestor": image["Id"]}, all=True)  # type: ignore
                if not running_containers:
                    break
                for container in running_containers:  # type: ignore
                    client.remove_container(container["Id"], v=True, force=True)  # type: ignore
                tries -= 1
                time.sleep(0.1)

            if running_containers:
                print(f"Containers still running when trying to remove image {image['Id']}: {running_containers}")
                not_removed.append(image)  # type: ignore
                continue

            client.remove_image(image["Id"], force=True)  # type: ignore

        # Delete other running containers from non-solution images, e.g., postgresql
        tries = 100
        running_containers = []
        while tries >= 0:
            # (by default, it finds substring in name)
            running_containers = client.containers(filters={"name": session_unique_id}, all=True)  # type: ignore
            if not running_containers:
                break
            for container in running_containers:  # type: ignore
                client.remove_container(container["Id"], v=True, force=True)  # type: ignore
            tries -= 1
            time.sleep(0.1)
        if running_containers:
            print(f"Containers still running when trying to remove them: {running_containers}")
            not_removed += running_containers  # type: ignore

        # Delete networks (by default, it finds substring in name)
        for network in client.networks(filters={"name": session_unique_id}):  # type: ignore
            try:
                client.remove_network(network["Id"])  # type: ignore
            except Exception:
                print(f"Failed to remove network: {network}")
                not_removed.append(network)  # type: ignore
                continue

        # Delete volumes (by default, it finds substring in name)
        # returns a dict such as:
        # {"Volumes": [], ...}, even if no volume is found
        # And volumes have names instead of ids
        for volume in client.volumes(filters={"name": session_unique_id})["Volumes"]:  # type: ignore
            try:
                client.remove_volume(volume["Name"], force=True)  # type: ignore
            except Exception:
                print(f"Failed to remove volume: {volume}")
                not_removed.append(volume)  # type: ignore
                continue

        if not_removed:
            raise Exception(f"Failed to remove docker resources: {not_removed}.")


def _clean_hps_docker_resources(items: list[pytest.Item], external_hps_deployment: bool) -> None:
    if not is_docker_installed_fun() or not is_marker_within_collected_tests(items, "use_hps"):
        return
    if not external_hps_deployment and HpsDeploymentProcess.compose_file.is_file():
        HpsDeploymentProcess.stop()


# =================================================== [HPS] ======================================================== #


@pytest.fixture(scope="session")
def python_in_saf_product_environment(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    # FIXME: this should be done only for the tests that need it, not for the entire session

    print("Creating virtual environment, simulating SAF Product Environment...")
    saf_product_environment = tmp_path_factory.mktemp("saf_product_environment")
    saf_product_environment_version_dir = saf_product_environment / "0.1.0"
    saf_product_environment_version_dir.mkdir(parents=True, exist_ok=True)

    subprocess.check_output([sys.executable, "-m", "venv", ".venv"], cwd=saf_product_environment_version_dir)
    python_in_saf_product_environment = find_exec_in_venv(saf_product_environment_version_dir, "python")
    subprocess.check_output([python_in_saf_product_environment, "-m", "pip", "install", "--upgrade", "pip"])

    subprocess.check_output([python_in_saf_product_environment, "-m", "pip", "install", "uv==0.7.3"])

    # install sympy as a standin for a real product. HPS tests will assume sympy is in the VM and can be used.
    subprocess.check_output([python_in_saf_product_environment, "-m", "pip", "install", "sympy==1.12.1"])

    return saf_product_environment, python_in_saf_product_environment


# ================================================= [Auth tokens] =================================================== #


@pytest.fixture
def dummy_jwt_token() -> str:
    payload = {
        "iss": "glow_tests",
        "sid": "fake_session_id",
        "exp": datetime.datetime.now() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.now(),
        "preferred_username": "admin",
        "email": "admin@glow.com",
        "roles": ["admin"],
        "groups": ["admin"],
    }
    return jwt.encode(payload, "my_secret_key", algorithm="HS256")


@pytest.fixture
def dummy_jwt_token_with_incompatible_info() -> str:
    payload = {
        "iss": "glow_tests",
        "sid": "fake_session_id",
        "exp": datetime.datetime.now() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.now(),
        "preferred_username": "admin",
        "email": "admin@glow.com",
        "roles": {"admin": "whatever_value"},
        "groups": ["admin"],
    }
    return jwt.encode(payload, "my_secret_key", algorithm="HS256")


@pytest.fixture
def dummy_jwt_token_with_partial_info() -> str:
    payload = {
        "iss": "glow_tests",
        "sid": "fake_session_id",
        "exp": datetime.datetime.now() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.now(),
        "preferred_username": "admin",
        "email": "admin@glow.com",
        "my_extra_field": 45,
    }
    return jwt.encode(payload, "my_secret_key", algorithm="HS256")
