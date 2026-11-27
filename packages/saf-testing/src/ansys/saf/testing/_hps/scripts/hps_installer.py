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

from collections.abc import Iterable, Iterator
import contextlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

import click
import httpx2
import yaml

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

HPS_DEPLOYMENTS_VERSION = "v1.2.217"
DEST_ROOT_DIR = Path.cwd() / "hps_deployment" / HPS_DEPLOYMENTS_VERSION

HPS_DEPLOYMENTS_REPOSITORY = str(os.getenv("HPS_DEPLOYMENTS_REPOSITORY"))
HPS_DEPLOYMENTS_ARTIFACT_NAME = "docker-compose-customer.tar.gz"
HPS_DEPLOYMENTS_DIRECTORY = DEST_ROOT_DIR / HPS_DEPLOYMENTS_ARTIFACT_NAME.removesuffix(".tar.gz")
HPS_DEPLOYMENTS_COMPOSE = HPS_DEPLOYMENTS_DIRECTORY / "docker-compose.yaml"
HPS_DEPLOYMENTS_CONFIG = HPS_DEPLOYMENTS_DIRECTORY / ".env"

# Evaluator and scalers should be fetched from the rep-deployments release, they are verified to work together.
HPS_EVALUATOR_REPOSITORY = HPS_DEPLOYMENTS_REPOSITORY
HPS_EVALUATOR_VERSION = HPS_DEPLOYMENTS_VERSION
HPS_EVALUATOR_ARTIFACT_NAME = (
    "hps-evaluator-default.tgz" if platform.system() == "Linux" else "hps-evaluator-windows-signed.tgz"
)
HPS_EVALUATOR_EXECUTABLE_NAME = "hps-evaluator" if platform.system() == "Linux" else "hps-evaluator.exe"
HPS_EVALUATOR_DIRECTORY = DEST_ROOT_DIR / HPS_EVALUATOR_ARTIFACT_NAME.removesuffix(".tgz")
HPS_EVALUATOR_EXECUTABLE_PATH = HPS_EVALUATOR_DIRECTORY / HPS_EVALUATOR_EXECUTABLE_NAME

HPS_SCALING_REPOSITORY = HPS_DEPLOYMENTS_REPOSITORY
HPS_SCALING_VERSION = HPS_DEPLOYMENTS_VERSION
HPS_SCALING_ARTIFACT_NAME = (
    "hps-scaling-service-default.tgz" if platform.system() == "Linux" else "hps-scaling-service-windows-signed.tgz"
)
HPS_SCALING_EXECUTABLE_NAME = "hps-scaling-service-default" if platform.system() == "Linux" else "hps-scaling.exe"
HPS_SCALING_DIRECTORY = DEST_ROOT_DIR / HPS_SCALING_ARTIFACT_NAME.removesuffix(".tgz")
HPS_SCALING_EXECUTABLE_PATH = HPS_SCALING_DIRECTORY / HPS_SCALING_EXECUTABLE_NAME

HPS_SCALING_CONFIG_FILE = (
    Path("~/.ansys/rep/scaling/scaling_config.json").expanduser()
    if platform.system() == "Linux"
    else Path("~/AppData/Local/Ansys/REP/scaling/scaling_config.json").expanduser()
)

DEFAULT_DOTNET_ROOT = (
    Path("~/.dotnet/").expanduser() if platform.system() == "Linux" else Path("C:/Program Files/dotnet/")
)


@click.group()
def cli():
    pass


def _download_repo_release_artifact(repo: str, version: str, artifact_name: str):
    """Download the artifact of a repo release."""
    if Path(DEST_ROOT_DIR / artifact_name).is_file():
        print(f"Artifact {artifact_name} already exists in {DEST_ROOT_DIR}. Skipping download.")
        return

    print(f"Downloading {artifact_name} from release {version} of {repo}...")

    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    response = httpx2.get(
        f"https://api.github.com/repos/{repo}/releases/tags/{version}",
        headers=headers,
        follow_redirects=True,
    )
    response.raise_for_status()

    release_info = response.json()
    asset_candidates = [asset for asset in release_info["assets"] if asset["name"] == artifact_name]

    if not asset_candidates:
        raise Exception(f"Asset {artifact_name} not found in release {version}")

    selected_asset = asset_candidates[0]

    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/octet-stream"}
    response = httpx2.get(
        f"https://api.github.com/repos/{repo}/releases/assets/{selected_asset['id']}",
        headers=headers,
        follow_redirects=True,
    )
    response.raise_for_status()

    with Path(DEST_ROOT_DIR / artifact_name).open("wb") as file:
        file.write(response.content)


def _unpack_artifact(source_file_name: str, target_directory: Path):
    """Unpack an artifact."""
    if target_directory.is_dir():
        print(f"Cleaning up {target_directory}...")
        # ignore errors because after docker compose is launched, it creates root-owned files in the directory
        shutil.rmtree(target_directory, ignore_errors=True)

    print(f"Unpacking {source_file_name} to {target_directory}...")
    target_directory.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(DEST_ROOT_DIR / source_file_name, "r") as file:
        # healthy check to be sure that the content will generate a subdir with the expected name
        assert all(name.startswith(target_directory.name) for name in file.getnames()), (
            f"Expected files in the tar to be within a subdir named {target_directory.name}"
        )
        file.extractall(target_directory.parent, members=_safe_members(file))


def _safe_members(members: Iterable[tarfile.TarInfo]) -> Iterator[tarfile.TarInfo]:
    for member in members:
        member_path = Path(member.name)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise RuntimeError(f"Unsafe path in tar archive: {member.name}")
        yield member


def _assign_execution_rights(exe: Path):
    if platform.system() == "Linux":
        cmd = ["chmod", "+x", exe.as_posix()]
        subprocess.run(cmd, check=True)


def configuring_keycloak():  # noqa: C901
    print("Configuring HPS Keycloak...")

    # To use the HPS client with a refresh token, we need to replace the keycloak service with
    # the image keycloak-action-token:26.3.5.

    # Add environment variables related to this keycloak image
    keycloak_config_path = Path(__file__).parent / "keycloak" / ".env"
    print("Configuring HPS Deployment with new keycloak environment variables")
    with HPS_DEPLOYMENTS_CONFIG.open("a") as config:
        config.write("\n" + keycloak_config_path.read_text())

    # Build the new keycloak image
    keycloak_dockerfile = Path(__file__).parent / "keycloak" / "Dockerfile"
    cmd = ["docker", "build", "-t", "keycloak-action-token:26.3.5", "."]
    try:
        subprocess.run(cmd, cwd=keycloak_dockerfile.parent, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Could not build the new Keycloak image: {e}") from None

    # Update the keycloak service in the docker compose yaml.
    with HPS_DEPLOYMENTS_COMPOSE.open("r") as docker_compose_file:
        docker_compose_content = yaml.safe_load(docker_compose_file)
    keycloak_service_path = Path(__file__).parent / "keycloak" / "service.yaml"
    with keycloak_service_path.open("r") as keycloak_service_file:
        keycloak_service_content = yaml.safe_load(keycloak_service_file)
    docker_compose_content["services"].update(keycloak_service_content)
    with HPS_DEPLOYMENTS_COMPOSE.open("w", encoding="utf-8") as docker_compose_file:
        yaml.safe_dump(docker_compose_content, docker_compose_file, sort_keys=False, indent=2)

    keycloak_config = HPS_DEPLOYMENTS_DIRECTORY / "config" / "keycloak" / "realm.json"
    if not keycloak_config.is_file():
        raise RuntimeError(f"keycloak config doesn't exist at {keycloak_config}")

    with keycloak_config.open("r") as f:
        keycloak_config_data = json.load(f)

    # Add testing URI to valid redirect URIs.
    clients = keycloak_config_data["clients"]
    found = False
    for c in clients:
        if c["clientId"] == "rep-jms-web":
            if "http://localhost:*" not in c["redirectUris"]:
                c["redirectUris"].append("http://localhost:*")
            found = True
            break
    if not found:
        raise RuntimeError("invalid keycloak config. Couldn't find rep-jms-web client.")

    # The GLOW Client needs to have a token that also includes "rep-jms-web" as audience in order to be validated
    # properly when accessing GLOW's API. That is why we need to add a new protocol mapper to the KeyCloak
    # rep-impersonation client.
    found = False
    for c in clients:
        if c["clientId"] == "rep-impersonation":
            c["protocolMappers"].append(
                {
                    "name": "rep-jms-aud",
                    "id": "673d45eb-6d07-424f-8eac-3ccf765edac4",
                    "protocol": "openid-connect",
                    "protocolMapper": "oidc-audience-mapper",
                    "consentRequired": False,
                    "config": {
                        "included.client.audience": "rep-jms-web",
                        "access.token.claim": "true",
                        "id.token.claim": "true",
                        "introspection.token.claim": "true",
                        "lightweight.claim": "true",
                    },
                },
            )
            found = True
            break
    if not found:
        raise RuntimeError("invalid keycloak config. Couldn't find rep-impersonation client.")

    # Add the client role "manage-job-access-token" to enable the usage of action tokens.
    users = keycloak_config_data["users"]
    found = False
    for u in users:
        service_account_client_id = u.get("serviceAccountClientId", None)
        if service_account_client_id and service_account_client_id == "rep-impersonation":
            u["clientRoles"]["rep-impersonation"].append("manage-job-access-token")
            found = True
            break
    if not found:
        raise RuntimeError("invalid keycloak config. Couldn't find rep-impersonation client service account.")

    with keycloak_config.open("w") as f:
        json.dump(keycloak_config_data, f, indent=4)


def get_hps_external_name(deployment_type: str) -> str:
    if deployment_type == "MultiContainer":
        # When the solution is containerized, we cannot use "localhost" as it refers to the container itself.
        # However, we cannot use host.docker.internal neither as it's not resolvable outside the container
        # (HPS Web UI, HPS Scaling Service...).
        if platform.system() == "Windows":
            # We assume that the HPS Deployment is running on WSL and this method is called in the Windows host.
            result = subprocess.run(["wsl", "hostname", "-I"], capture_output=True, text=True)
            return result.stdout.split(" ")[0]
        else:
            # We assume that the HPS Deployment and this method are both running in the same in Linux/WSL environment.
            result = subprocess.run(["ip", "addr", "show", "eth0"], capture_output=True, text=True)
            for line in result.stdout.split("\n"):
                if "inet " in line:
                    ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                    if ip_match:
                        return ip_match.group(1)
        raise RuntimeError("Could not determine the external IP address for HPS Deployment.")
    else:
        # this is the default value by HPS
        return "localhost"


def configuring_hps_deployment(hps_external_name: str = ""):
    hps_deployment_config_backup = HPS_DEPLOYMENTS_CONFIG.with_suffix(".bak")
    if not hps_deployment_config_backup.is_file():
        print(f"Backing up {HPS_DEPLOYMENTS_CONFIG} to {hps_deployment_config_backup}...")
        shutil.copy(HPS_DEPLOYMENTS_CONFIG, hps_deployment_config_backup)

    if hps_external_name:
        print(f"Configuring HPS Deployment with external name {hps_external_name}")
        HPS_DEPLOYMENTS_CONFIG.write_text(
            hps_deployment_config_backup.read_text().replace(
                "EXTERNAL_NAME=localhost",
                f"EXTERNAL_NAME={hps_external_name}",
            ),
        )
    else:
        shutil.copy(hps_deployment_config_backup, HPS_DEPLOYMENTS_CONFIG)


def _get_dotnet_path() -> Path:
    dotnet_path = Path(os.getenv("DOTNET_ROOT", DEFAULT_DOTNET_ROOT)) / (
        "dotnet" if platform.system() == "Linux" else "dotnet.exe"
    )
    if not dotnet_path.is_file() and (dotnet := shutil.which("dotnet")):
        dotnet_path = Path(dotnet)
    return dotnet_path


def _add_local_python_as_hps_application(available_applications: list[dict[str, str]]):
    python_executable = Path(sys.executable)
    available_applications.append(
        {
            "name": "Python",
            "version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "install_path": python_executable.parent.as_posix(),
            "executable": python_executable.as_posix(),
        },
    )


def _add_mechanical_as_hps_application(available_applications: list[dict[str, str]]):
    for env_var_key, env_var_value in os.environ.items():
        if not env_var_key.startswith("AWP_ROOT"):
            continue
        version = env_var_key.removeprefix("AWP_ROOT")
        mechanical_subdirectory_executable_location = "aisol" if platform.system() == "Linux" else "aisol/bin/winx64"
        mechanical_executable_name = ".workbench" if platform.system() == "Linux" else "AnsysWBU.exe"
        install_path = Path(env_var_value) / Path(mechanical_subdirectory_executable_location)
        mechanical_executable = install_path / mechanical_executable_name
        if mechanical_executable.is_file():
            available_applications.append(
                {
                    "name": "Ansys Mechanical",
                    "version": f"20{version[:2]} R{version[-1]}",
                    "install_path": install_path.as_posix(),
                    "executable": mechanical_executable.as_posix(),
                },
            )


def _add_aedt_as_hps_application(available_applications: list[dict[str, str]]):
    for env_var_key, env_var_value in os.environ.items():
        if not env_var_key.startswith("ANSYSEM_ROOT"):
            continue
        version = env_var_key.removeprefix("ANSYSEM_ROOT")
        aedt_executable_name = "ansysedt" if platform.system() == "Linux" else "ansysedt.exe"
        aedt_executable_path = Path(env_var_value) / aedt_executable_name
        if aedt_executable_path.is_file():
            available_applications.append(
                {
                    "name": "Ansys Electronics Desktop",
                    "version": f"20{version[:2]} R{version[-1]}",
                    "install_path": aedt_executable_path.parent.as_posix(),
                    "executable": aedt_executable_path.as_posix(),
                },
            )


def _add_visor_as_hps_application(available_applications: list[dict[str, str]]):
    with contextlib.suppress(ImportError):  # Skip if not available
        # unused import to check that Visor is available as application in the environment
        import ansys.visor.viewer  # pyright: ignore[reportMissingImports]  # noqa: F401

        python_executable = Path(sys.executable)
        available_applications.append(
            {
                "name": "Visor Viewer",
                "version": "0",
                "install_path": python_executable.parent.as_posix(),
                "executable": python_executable.as_posix(),
            },
        )


def _add_saf_product_wrappers_as_hps_application(available_applications: list[dict[str, str]]):
    def _add_aedt_wrapper(python_executable: Path):
        from ansys.saf.product_configuration.wrappers.versions import AEDT_WRAPPER_VERSION

        available_applications.append(
            {
                "name": "Ansys SAF Product Wrapper [AEDT]",
                "version": AEDT_WRAPPER_VERSION,
                "install_path": python_executable.parent.as_posix(),
                "executable": python_executable.as_posix(),
            },
        )

    def _add_fluent_wrapper(python_executable: Path):
        from ansys.saf.product_configuration.wrappers.versions import FLUENT_WRAPPER_VERSION

        available_applications.append(
            {
                "name": "Ansys SAF Product Wrapper [Fluent]",
                "version": FLUENT_WRAPPER_VERSION,
                "install_path": python_executable.parent.as_posix(),
                "executable": python_executable.as_posix(),
            },
        )

    def _add_optislang_wrapper(python_executable: Path):
        from ansys.saf.product_configuration.wrappers.versions import OPTISLANG_WRAPPER_VERSION

        available_applications.append(
            {
                "name": "Ansys SAF Product Wrapper [optiSLang]",
                "version": OPTISLANG_WRAPPER_VERSION,
                "install_path": python_executable.parent.as_posix(),
                "executable": python_executable.as_posix(),
            },
        )

    python_executable = Path(sys.executable)
    for wrapper_func in [_add_aedt_wrapper, _add_fluent_wrapper, _add_optislang_wrapper]:
        with contextlib.suppress(ImportError):  # Product configuration is optional; skip if not available
            # we split it in individual adds because sometimes we may release saf-product-config
            # SP that only contain some of the wrappers.
            wrapper_func(python_executable)


def _add_saf_product_environment_as_hps_application(
    available_applications: list[dict[str, str]],
    python_in_saf_product_environment: None | Path = None,
):
    if python_in_saf_product_environment is not None:
        available_applications.append(
            {
                "name": "Ansys SAF Product Environment",
                "version": "0.0",
                "install_path": python_in_saf_product_environment.parent.as_posix(),
                "executable": python_in_saf_product_environment.as_posix(),
            },
        )


def _add_geometry_as_hps_application(available_applications: list[dict[str, str]]):
    for env_var_key, env_var_value in os.environ.items():
        if not env_var_key.startswith("GEOMETRY_ROOT"):
            continue
        version = env_var_key.removeprefix("GEOMETRY_ROOT")

        if platform.system() == "Windows":
            executable_path = Path(env_var_value) / "Presentation.ApiServerCoreService.exe"
            if not executable_path.is_file():
                # executable in older version (<=251)
                executable_path = Path(env_var_value) / "Presentation.ApiServerDMS.exe"
        else:
            geometry_dll_path = Path(env_var_value) / "Presentation.ApiServerCoreService.dll"
            if not geometry_dll_path.is_file():
                continue
            executable_path = _get_dotnet_path()
        if executable_path.is_file():
            available_applications.append(
                {
                    "name": "Ansys Geometry",
                    "version": f"20{version[:2]} R{version[-1]}",
                    "install_path": executable_path.parent.as_posix(),
                    "executable": executable_path.as_posix(),
                },
            )


def configuring_scalar(
    python_in_saf_product_environment: None | Path = None,
    hps_external_name: str = "",
):
    print("Configuring HPS Scaling...")
    if hps_external_name:
        print(f"    - Using external name {hps_external_name} for HPS Deployment.")

    generated_scaling_config = Path(__file__).parent / "scaling_config.json"
    # If the file already exists, the write configuration command fails
    generated_scaling_config.unlink(missing_ok=True)

    if not HPS_SCALING_EXECUTABLE_PATH.is_file():
        raise RuntimeError(f"scalar executable doesn't exist at {HPS_SCALING_EXECUTABLE_PATH}")

    _assign_execution_rights(HPS_SCALING_EXECUTABLE_PATH)

    subprocess.check_output(
        [
            HPS_SCALING_EXECUTABLE_PATH.as_posix(),
            "-v4",
            "--config",
            str(generated_scaling_config),
            "write",
            "-d",
            "local",
        ],
    )

    with generated_scaling_config.open("r") as f:
        scaling_config_data = json.load(f)

    _assign_execution_rights(HPS_EVALUATOR_EXECUTABLE_PATH)

    scaling_config_data["main_loop_interval"] = 5

    if hps_external_name:
        scaling_config_data["services"]["rep_url"] = f"https://{hps_external_name}:8443/hps"
        scaling_config_data["services"]["otel_exporter_url"] = f"https://{hps_external_name}:4317"
        scaling_config_data["services"]["monitor_url"] = f"grpcs://{hps_external_name}:8443"

    scaling_config_data["credentials"]["username"] = "repadmin"
    scaling_config_data["credentials"]["password"] = "repadmin"
    scaling_config_data["credentials"]["client_id"] = "rep-cli"

    scaling_config_data["compute_resource_sets"][0]["backend"]["shared_dir"] = tempfile.mkdtemp(prefix="hps_")
    scaling_config_data["compute_resource_sets"][0]["backend"]["evaluator_exe"] = str(HPS_EVALUATOR_EXECUTABLE_PATH)

    scaling_config_data["compute_resource_sets"][0]["available_resources"]["platform"] = platform.system().lower()
    # There is a bug when shutting down instances where the evaluator is not liberated even if the job is aborted,
    # thus we accumulate zombie instances until we reach this num_instances/cores maximum and then every future
    # test/job will fail due to no evaluator available. Reduce this number to 1-4 once the bug is fixed.
    scaling_config_data["compute_resource_sets"][0]["available_resources"]["num_cores"] = 100
    scaling_config_data["compute_resource_sets"][0]["available_resources"]["num_instances"] = 100

    available_applications = scaling_config_data["compute_resource_sets"][0]["available_applications"]

    # Add custom applications to HPS Scaling configuration
    _add_local_python_as_hps_application(available_applications)
    _add_mechanical_as_hps_application(available_applications)
    _add_aedt_as_hps_application(available_applications)
    _add_saf_product_wrappers_as_hps_application(available_applications)
    _add_saf_product_environment_as_hps_application(available_applications, python_in_saf_product_environment)
    _add_geometry_as_hps_application(available_applications)
    _add_visor_as_hps_application(available_applications)

    target_scaling_config = HPS_SCALING_CONFIG_FILE
    target_scaling_config.parent.mkdir(parents=True, exist_ok=True)
    print(f"Moving generated scaling config to {target_scaling_config}...")
    with target_scaling_config.open("w") as f:
        json.dump(scaling_config_data, f, indent=4)

    generated_scaling_config.unlink()


def update_postgres_image():
    """
    Update the postgres service image in the docker-compose.yaml file.
    The old image 'bitnami/postgresql:17' is no longer available, so we must use 'bitnamilegacy/postgresql:17' instead.

    TODO: Remove this function once HPS is upgraded to version 1.3.300 or later, where this workaround will no longer
    be necessary.
    """

    old_image = "bitnami/postgresql:17"
    new_image = "bitnamilegacy/postgresql:17"
    content = HPS_DEPLOYMENTS_COMPOSE.read_text()
    if f"image: {old_image}" in content:
        content = content.replace(f"image: {old_image}", f"image: {new_image}")
        HPS_DEPLOYMENTS_COMPOSE.write_text(content)


@cli.command()
def install_hps():
    """Install HPS."""
    DEST_ROOT_DIR.mkdir(parents=True, exist_ok=True)

    _download_repo_release_artifact(HPS_DEPLOYMENTS_REPOSITORY, HPS_DEPLOYMENTS_VERSION, HPS_DEPLOYMENTS_ARTIFACT_NAME)
    _download_repo_release_artifact(HPS_EVALUATOR_REPOSITORY, HPS_EVALUATOR_VERSION, HPS_EVALUATOR_ARTIFACT_NAME)
    _download_repo_release_artifact(HPS_SCALING_REPOSITORY, HPS_SCALING_VERSION, HPS_SCALING_ARTIFACT_NAME)

    _unpack_artifact(HPS_DEPLOYMENTS_ARTIFACT_NAME, HPS_DEPLOYMENTS_DIRECTORY)
    _unpack_artifact(HPS_EVALUATOR_ARTIFACT_NAME, HPS_EVALUATOR_DIRECTORY)
    _unpack_artifact(HPS_SCALING_ARTIFACT_NAME, HPS_SCALING_DIRECTORY)

    configuring_keycloak()
    configuring_hps_deployment()
    configuring_scalar()
    update_postgres_image()


@cli.command()
def configure_rep_scalar():
    """Configure rep scalar."""
    configuring_scalar()


@cli.command()
def login():
    """Login to GitHub container registry."""
    token = GITHUB_TOKEN or ""
    cmd = ["docker", "login", "ghcr.io", "-u", "USERNAME", "--password-stdin"]
    if platform.system() == "Windows":
        cmd = ["wsl"] + cmd
    try:
        subprocess.run(cmd, input=token, text=True, check=True)
        print("Docker login successful.")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print("Docker login failed.")


if __name__ == "__main__":
    cli()
