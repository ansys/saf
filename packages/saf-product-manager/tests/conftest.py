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
import shutil
import time
from typing import Any
import uuid
import warnings

import docker
import pytest

from ansys.saf.testing.docker import is_docker_installed_fun
from ansys.saf.testing.hps.process import HpsDeploymentProcess
from ansys.saf.testing.platform_specific import is_ci_run
from ansys.saf.testing.pytest import is_marker_within_collected_tests

IGNORE_PYC_FILES = shutil.ignore_patterns("*__pycache__*", "*.pyc*")
PYTEST_LOGS_DIR = "pytest_logs"


# =================================================== [Pytest params] =============================================== #


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--workflow-docker-id", action="store", help="Workflow docker id.")
    parser.addoption(
        "--flagship-versions",
        action="store",
        default="latest",
        help="Run flagship tests with the selected version(s). Available options: latest, previous, both.",
    )


# =================================================== [Pytest session configuration] ================================ #


def pytest_configure(config: pytest.Config) -> None:
    """This hook will be run once before the nodes are setup, and then once for each node (if in parallel)."""

    # PyMechanical tries to create directories in APPDATA just by importing it
    # (which happens when importing the solution and we do it in almost every test file)
    # This causes issues when collecting tests (due to concurrency in pytest?), so one worker
    # tries to create the dir when another one has just created it and raises an exception.
    # We import it here so the dir is created first and all future checks will see it created.
    # Same happens for PyMAPDL
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        import ansys.mapdl.core  # pyright: ignore
        import ansys.mechanical.core  # noqa: F401 # pyright: ignore

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
        # Only master cleans up images at the end
        try:
            _clean_solution_docker_resources(session.config.session_unique_id)  # type: ignore
            cleaned_solution_images = True
        except Exception as e:
            print(e)
            cleaned_solution_images = False

        try:
            _clean_hps_docker_resources(session.items, bool(session.config.getoption("--ext-hps")))
            cleaned_hps_containers = True
        except Exception as e:
            print(e)
            cleaned_hps_containers = False

        if not (cleaned_solution_images or cleaned_hps_containers):
            raise Exception("Failed to cleanup docker resources.")

        # Print log location for users
        log_dir = Path.cwd() / PYTEST_LOGS_DIR
        if log_dir.exists():
            print(f"\n{'=' * 80}")
            if is_ci_run():
                print("Test logs will be available as GitHub Actions job artifacts named 'pytest_logs_*'")
            else:
                print(f"Test logs have been exported to: {log_dir.absolute()}")
            print(f"{'=' * 80}\n")


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
