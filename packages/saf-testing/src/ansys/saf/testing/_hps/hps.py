# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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
import json
from enum import Enum
from pathlib import Path
import platform
import shutil
from typing import Any

import pytest

from ansys.saf.testing._hps.process.hps_deployment_process import HpsDeploymentProcess
from ansys.saf.testing._hps.process.hps_scaler_process import HpsScalerProcess
from ansys.saf.testing._hps.scripts.hps_installer import HPS_DEPLOYMENTS_DIRECTORY, get_hps_external_name
from ansys.saf.testing._pytest.pytest import is_marker_within_collected_tests
from ansys.saf.testing._solution.const import TestProductInstanceSystemType

KEYCLOAK_CONFIG_FILE = HPS_DEPLOYMENTS_DIRECTORY / "config" / "keycloak" / "realm.json"
KEYCLOAK_CONFIG_BACKUP_FILE = KEYCLOAK_CONFIG_FILE.with_suffix(".bak")
TRAEFIK_TLS_SETUP_FILE = HPS_DEPLOYMENTS_DIRECTORY / "config" / "traefik" / "dynamic" / "tls_setup.yml"
TRAEFIK_TLS_SETUP_BACKUP_FILE = TRAEFIK_TLS_SETUP_FILE.with_suffix(".bak")


@pytest.fixture(scope="session")
def external_hps_deployment(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--ext-hps"))


@pytest.fixture(scope="session")
def external_hps_scaler(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--ext-hps-scaler"))


@pytest.fixture(scope="session")
def is_hps_requested(request: pytest.FixtureRequest, external_hps_deployment: bool) -> bool:
    """Regardless of the external_hps_deployment option, this fixture still needs a Linux check to prevent Windows runs
    from requesting HPS."""
    if platform.system() == "Linux":
        return "not use_hps" not in request.config.option.markexpr
    else:
        return external_hps_deployment


@pytest.fixture(scope="session")
def should_hps_be_launched(request: pytest.FixtureRequest) -> bool:
    return is_marker_within_collected_tests(request.session.items, "use_hps")


@pytest.fixture(scope="session")
def is_hps_enabled(
    is_hps_requested: bool,
    is_docker_enabled: bool,
    num_pytest_workers: int,
    should_hps_be_launched: bool,
    external_hps_deployment: bool,
) -> bool:
    return (
        is_hps_requested
        and num_pytest_workers <= 1
        and should_hps_be_launched
        and (is_docker_enabled or external_hps_deployment)
    )


@pytest.fixture(scope="session")
def configure_hps_deployment_keycloak(request: pytest.FixtureRequest) -> Generator[dict[str, Any]]:
    """Modify HPS' keycloak configuration."""
    custom_config = getattr(request, "param", {})
    if not custom_config:
        yield custom_config
        return

    shutil.copy(KEYCLOAK_CONFIG_FILE, KEYCLOAK_CONFIG_BACKUP_FILE)
    try:
        keycloak_config = json.loads(KEYCLOAK_CONFIG_FILE.read_text())
        keycloak_config.update(custom_config)
        with KEYCLOAK_CONFIG_FILE.open("w") as f:
            json.dump(keycloak_config, f, indent=4)
        yield custom_config
    finally:
        if not KEYCLOAK_CONFIG_BACKUP_FILE.is_file():
            raise FileNotFoundError("Backup of Keycloak configuration file not found. Configuration cannot be undone.")
        shutil.copy(KEYCLOAK_CONFIG_BACKUP_FILE, KEYCLOAK_CONFIG_FILE)


@pytest.fixture(scope="session")
def configure_hps_deployment_traefik_tls_setup(request: pytest.FixtureRequest) -> Generator[str]:
    """Modify HPS traefik TLS setup by replacing the default server certificate with a custom one.
    The request parameter should be the name of the custom certificate file to use (without the .crt or .key extension),
    which must be located under HPS_DEPLOYMENT/config/certificates/."""
    custom_cert_filename = getattr(request, "param", "")
    if not custom_cert_filename:
        yield custom_cert_filename
        return

    shutil.copy(TRAEFIK_TLS_SETUP_FILE, TRAEFIK_TLS_SETUP_BACKUP_FILE)
    try:
        tls_setup_content = TRAEFIK_TLS_SETUP_FILE.read_text()
        new_tls_setup = tls_setup_content.replace("server_docker.localhost", custom_cert_filename)
        TRAEFIK_TLS_SETUP_FILE.write_text(new_tls_setup)
        yield custom_cert_filename
    finally:
        if not TRAEFIK_TLS_SETUP_BACKUP_FILE.is_file():
            raise FileNotFoundError(
                "Backup of Traefik TLS setup configuration file not found. Configuration cannot be undone.",
            )
        shutil.copy(TRAEFIK_TLS_SETUP_BACKUP_FILE, TRAEFIK_TLS_SETUP_FILE)


@pytest.fixture(scope="class")
def restore_default_hps_deployment(deployment_type: Enum) -> Generator[None, None, None]:
    # Needed because fixtures such as configure_hps_deployment_keycloak are not undone unless they are reparameterized
    # by another test.
    yield
    need_restart = False
    if KEYCLOAK_CONFIG_BACKUP_FILE.is_file():
        shutil.copy(KEYCLOAK_CONFIG_BACKUP_FILE, KEYCLOAK_CONFIG_FILE)
        need_restart = True
    if TRAEFIK_TLS_SETUP_BACKUP_FILE.is_file():
        shutil.copy(TRAEFIK_TLS_SETUP_BACKUP_FILE, TRAEFIK_TLS_SETUP_FILE)
        need_restart = True
    if need_restart:
        HpsDeploymentProcess.restart(deployment_type)


@pytest.fixture(scope="session")
def hps_deployment(
    is_hps_enabled: bool,
    deployment_type: Enum,
    external_hps_deployment: bool,
    configure_hps_deployment_keycloak: dict[str, Any],
    configure_hps_deployment_traefik_tls_setup: str,
) -> Generator[None, None, None]:
    # Don't skip or fail tests here. This fixture is used in other fixtures that are parametrized and not all
    # options end up using this fixture. For example: fixture used for PIM and HPS. If we skip here
    # because docker is not enabled, it will also skip PIM tests.
    if not is_hps_enabled or external_hps_deployment:
        yield
        return
    try:
        HpsDeploymentProcess.run(deployment_type)
        yield
    finally:
        HpsDeploymentProcess.stop()


@pytest.fixture(scope="session")
def hps_scaler(
    request: pytest.FixtureRequest,
    is_hps_enabled: bool,
    hps_deployment: None,
    instance_system_type: TestProductInstanceSystemType | None,
    deployment_type: Enum,
    external_hps_scaler: bool,
    product_host: str | None,
    product_binding_host: str | None,
    certificates_directory: Path,
    enable_insecure_product: bool,
) -> Generator[HpsScalerProcess | None, None, None]:

    # Don't skip or fail tests here. This fixture is used in other fixtures that are parametrized and not all
    # options end up using this fixture. For example: fixture used for PIM and HPS. If we skip here
    # because docker is not enabled, it will also skip PIM tests.
    if not is_hps_enabled or external_hps_scaler:
        yield
        return

    # If an HPS job requires a SAF Product virtual environment, a fixture named
    # 'python_in_saf_product_environment' should be defined. This fixture must return
    # a tuple: (saf_product_environment, python_in_saf_product_environment), where
    # 'python_in_saf_product_environment' is the path to the Python executable in that environment.
    # If the fixture is not defined, both values will default to None.
    try:
        saf_product_environment, python_in_saf_product_environment = request.getfixturevalue(
            "python_in_saf_product_environment",
        )
    except pytest.FixtureLookupError:
        saf_product_environment = None
        python_in_saf_product_environment = None

    scaler_process = HpsScalerProcess(
        deployment_type=deployment_type,
        python_in_saf_product_environment=python_in_saf_product_environment,
        saf_product_environment=saf_product_environment,
        product_host=product_host,
        product_binding_host=product_binding_host,
        certificates_directory=certificates_directory,
        enable_insecure_product=enable_insecure_product,
    )
    try:
        scaler_process.start()
        yield scaler_process
    finally:
        scaler_process.stop()


@pytest.fixture(scope="session")
def hps_port(
    is_hps_enabled: bool,
    hps_scaler: None,
) -> int | None:
    # Don't skip or fail tests here. This fixture is used in other fixtures that are parametrized and not all
    # options end up using this fixture. For example: fixture used for PIM and HPS. If we skip here
    # because docker is not enabled, it will also skip PIM tests.
    if is_hps_enabled:
        return 8443
    else:
        return None


@pytest.fixture(scope="session")
def hps_host(deployment_type: Enum) -> str:
    return get_hps_external_name(deployment_type.value)
