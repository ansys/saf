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
import os
from pathlib import Path
import platform
import shutil
from typing import TypeVar

import pytest
import yaml

from ansys.saf.testing._common.common import YieldFixture
from ansys.saf.testing._common.network import get_random_free_port
from ansys.saf.testing._pim.process.pim_process import PimProcess
from ansys.saf.glow.client import Deployment  # pyright: ignore[reportMissingImports]
from ansys.saf.testing._solution.const import TestProductInstanceSystemType
from ansys.saf.testing._solution.end_to_end._typing import SolutionProtocol
from ansys.saf.testing._solution.end_to_end.glow_process import (
    GlowBaseProcess,
    GlowDesktopProcess,
    GlowDockerProcess,
    GlowProductionProcess,
)
from ansys.saf.testing._solution.end_to_end.log_manager import LogContainerManager, ServiceType

T = TypeVar("T", bound=SolutionProtocol)

IGNORE_PYC_FILES = shutil.ignore_patterns("*__pycache__*", "*.pyc*")
PYTEST_LOGS_DIR = "pytest_logs"
SESSION_GLOW_API_CONTAINER_NAME = "session_glow_api"
SESSION_GLOW_UI_CONTAINER_NAME = "session_glow_ui"
SESSION_PIM_CONTAINER_NAME = "session_pim"
DEFAULT_GLOW_API_NUMBER_OF_WORKERS = 4
GLOW_PROC_CONTAINER_NAME_PATTERN = "glow_proc"
GLOW_PROC_PROD_CONTAINER_NAME_PATTERN = "glow_prod_proc"


# ================================================= [Reruns] =================================================== #


@pytest.fixture
def rerun_restart(session_glow: GlowBaseProcess[T] | None, request: pytest.FixtureRequest):
    if not session_glow:
        return
    test_name: str = request.node.name  # type: ignore
    # Try to find new ports. This benefits the following situations:
    # - if the previous start failed due to ports being used
    # - if the previous process was OK, but ports haven't been freed yet
    # - if the previous start failed for any other reason before being able to parse ports from its output
    # This also prevents masquerading the real test errors with a restart error.
    # IMPORTANT: This restart will not trigger fixtures that depend on session_glow, and reruns only re-execute
    # function-scoped fixtures. Therefore, module-scoped and class-scoped fixtures will not be re-executed and whatever
    # they returned will still reuse legacy state from session-glow. For example, if we had a session_client, it would
    # internally use the old API url instead of the new one. In tests, always use function-scoped GLOW clients
    # and project fixtures.
    if getattr(request.node, "execution_count", 0) > 1:  # type: ignore
        session_glow.restart(log_tag=f"Rerunning test {test_name}.", keep_ports=False)
    elif not session_glow.healthy:
        session_glow.restart(log_tag=f"Glow not healthy during test {test_name} setup.", keep_ports=False)


# ================================================= [Logging] =================================================== #


@pytest.fixture(scope="session")
def session_log_manager(worker_id: str) -> YieldFixture[LogContainerManager]:
    # Always export logs to pytest_logs/ directory at the root
    root_log_dir = Path.cwd() / PYTEST_LOGS_DIR / f"{worker_id}_logs"
    log_manager = LogContainerManager(root_log_dir)
    yield log_manager
    log_manager.copy_and_return_logs("Session finish")


@pytest.fixture
def test_log_management(
    request: pytest.FixtureRequest,
    session_log_manager: LogContainerManager,
    session_glow: GlowBaseProcess[T] | None,
    rerun_restart: None,
):
    # If the user doesn't explicitly use this fixture, logs will be generated in the same way but they will not add
    # the corresponding test_name tag.
    test_name = str(request.node.name)  # type: ignore
    session_log_manager.set_current_test(test_name)
    # Clean slate for tests so that text_in_output() is always relevant.
    if session_glow:
        session_glow.clear_output()
    yield
    session_log_manager.copy_and_return_logs(test_name)


# =========================================== [GLOW configuration] =============================================== #


@pytest.fixture(scope="session")
def ui_enabled(request: pytest.FixtureRequest) -> bool:
    # TODO: convert to session_glow.enable_ui()
    ui_enabled = request.param if hasattr(request, "param") else False
    return ui_enabled


@pytest.fixture(scope="session")
def max_number_of_workers(request: pytest.FixtureRequest) -> int:
    return getattr(request, "param", DEFAULT_GLOW_API_NUMBER_OF_WORKERS)


@pytest.fixture(scope="session")
def shutdown_api_server_first(request: pytest.FixtureRequest) -> bool | None:
    return getattr(request, "param", None)


@pytest.fixture(scope="session")
def debug_mode_override(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--debug-mode"))


# =================================================== [GLOW] =================================================== #


@pytest.fixture(scope="session")
def session_glow(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    worker_id: str,
    # start of custom fixtures
    solution_type: tuple[type[T], Path] | None,  # entrypoint, to be defined and parametrized by the user
    session_log_manager: LogContainerManager,
    deployment_type: Deployment,
    instance_system_type: TestProductInstanceSystemType | None,
    hps_port: int | None,
    session_pim: PimProcess | None,
    pim_port: int | None,
    pim_socket_path: Path | None,
    ui_enabled: bool,
    debug_mode_override: bool,
    max_number_of_workers: int,
    certificates_directory: Path,
    shutdown_api_server_first: bool | None,
) -> YieldFixture[GlowBaseProcess[T] | None]:
    if not solution_type:
        # just to be compatible with autouse session fixtures (logging, reruns...) that depend on session_glow
        # but there are tests that use those fixtures that don't use session_glow and instead use run_glow for example.
        yield None
        return

    solution_class, solution_dir = solution_type
    if solution_dir.is_file():
        definition_file = solution_dir
        solution_dir = definition_file.parent
    else:
        definition_file = None
    solution_name = solution_class.__name__

    session_unique_id = str(getattr(request.config, "session_unique_id", ""))  # type: ignore

    glow_server_process = _run_glow(
        tmp_path_factory=tmp_path_factory,
        instance_system_type=instance_system_type,
        hps_port=hps_port,
        pim_port=pim_port,
        pim_socket_path=pim_socket_path,
        deployment_type=deployment_type,
        session_unique_id=session_unique_id,
        worker_id=worker_id,
        ui_enabled=ui_enabled,
        solution_name=solution_name,
        solution_type=solution_class,
        solution_dir=solution_dir,
        definition_file=definition_file,
        solution_api_port=None,
        solution_ui_port=None,
        use_automatic_solution_locator=False,
        prevent_start=False,
        debug_mode_override=debug_mode_override,
        max_number_of_workers=max_number_of_workers,
        certificates_directory=certificates_directory,
        shutdown_api_server_first=shutdown_api_server_first,
    )

    # We could configure these within the glow object init but it is clearer to keep the logic on the conftest file.
    containers = [
        session_log_manager.add_log_container(
            glow_server_process.get_api_output,
            f"{deployment_type.name}_{SESSION_GLOW_API_CONTAINER_NAME}",
            ServiceType.API,
        ),
    ]
    if ui_enabled:
        ui_container = session_log_manager.add_log_container(
            glow_server_process.get_ui_output,
            f"{deployment_type.name}_{SESSION_GLOW_UI_CONTAINER_NAME}",
            ServiceType.UI,
        )
        containers.append(ui_container)
    if session_pim:
        # PIM not always instantiated.
        session_log_manager.add_log_container(session_pim.get_pim_output, SESSION_PIM_CONTAINER_NAME, ServiceType.Other)

    glow_server_process.attach_log_containers(containers)

    yield glow_server_process

    glow_server_process.stop()


@pytest.fixture
def run_glow(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    worker_id: str,
    # start of custom fixtures
    session_log_manager: LogContainerManager,
    deployment_type: Deployment,
    instance_system_type: TestProductInstanceSystemType | None,
    hps_port: int | None,
    session_pim: PimProcess | None,
    pim_port: int | None,
    pim_socket_path: Path | None,
    ui_enabled: bool,
    debug_mode_override: bool,
    max_number_of_workers: int,
    certificates_directory: Path,
    shutdown_api_server_first: bool | None,
) -> YieldFixture[Callable[[type[T], Path], GlowBaseProcess[T]]]:
    glow_server_processes: list[GlowBaseProcess[T]] = []

    def _run_glow_process(
        solution_class: type[T],
        solution_dir: Path,
        ui_enabled: bool = ui_enabled,
        solution_api_port: int | None = None,
        solution_ui_port: int | None = None,
        use_automatic_solution_locator: bool = False,
        prevent_start: bool = False,
        obfuscated_glow_pythonpath: str | None = None,
        cwd: Path | None = None,
    ) -> GlowBaseProcess[T]:
        if solution_dir.is_file():
            definition_file = solution_dir
            solution_dir = definition_file.parent
        else:
            definition_file = None

        solution_name = solution_class.__name__

        session_unique_id = str(getattr(request.config, "session_unique_id", ""))  # type: ignore

        glow_server_process = _run_glow(
            tmp_path_factory=tmp_path_factory,
            instance_system_type=instance_system_type,
            hps_port=hps_port,
            pim_port=pim_port,
            pim_socket_path=pim_socket_path,
            deployment_type=deployment_type,
            session_unique_id=session_unique_id,
            worker_id=worker_id,
            ui_enabled=ui_enabled,
            solution_name=solution_name,
            solution_type=solution_class,
            solution_dir=solution_dir,
            definition_file=definition_file,
            solution_api_port=solution_api_port,
            solution_ui_port=solution_ui_port,
            use_automatic_solution_locator=use_automatic_solution_locator,
            prevent_start=prevent_start,
            debug_mode_override=debug_mode_override,
            obfuscated_glow_pythonpath=obfuscated_glow_pythonpath,
            cwd=cwd,
            certificates_directory=certificates_directory,
            max_number_of_workers=max_number_of_workers,
            shutdown_api_server_first=shutdown_api_server_first,
        )

        glow_server_processes.append(glow_server_process)

        containers = [
            session_log_manager.add_log_container(
                glow_server_process.get_api_output,
                f"{deployment_type.name}_{GLOW_PROC_CONTAINER_NAME_PATTERN}_api_{len(glow_server_processes)}",
                ServiceType.API,
            ),
        ]

        if ui_enabled:
            ui_container = session_log_manager.add_log_container(
                glow_server_process.get_ui_output,
                f"{deployment_type.name}_{GLOW_PROC_CONTAINER_NAME_PATTERN}_ui_{len(glow_server_processes)}",
                ServiceType.UI,
            )
            containers.append(ui_container)
        if session_pim:
            session_log_manager.add_log_container(
                session_pim.get_pim_output,
                SESSION_PIM_CONTAINER_NAME,
                ServiceType.Other,
            )

        glow_server_process.attach_log_containers(containers)

        return glow_server_process

    yield _run_glow_process

    session_log_manager.clear_processes(name_pattern=GLOW_PROC_CONTAINER_NAME_PATTERN)

    for glow_server_process in glow_server_processes:
        glow_server_process.stop()


def _run_glow(
    tmp_path_factory: pytest.TempPathFactory,
    instance_system_type: TestProductInstanceSystemType | None,
    hps_port: int | None,
    pim_port: int | None,
    pim_socket_path: Path | None,
    deployment_type: Deployment,
    session_unique_id: str,
    worker_id: str,
    ui_enabled: bool,
    solution_name: str,
    solution_type: type[T],
    solution_dir: Path,
    definition_file: Path | None,
    solution_api_port: int | None = None,
    solution_ui_port: int | None = None,
    use_automatic_solution_locator: bool = False,
    prevent_start: bool = False,
    debug_mode_override: bool = False,
    obfuscated_glow_pythonpath: str | None = None,
    cwd: Path | None = None,
    max_number_of_workers: int = 1,
    certificates_directory: Path | None = None,
    shutdown_api_server_first: bool | None = None,
) -> GlowBaseProcess[T]:
    solution_api_port = solution_api_port if solution_api_port else get_random_free_port()
    if deployment_type == Deployment.Desktop:
        glow_server_process = _get_glow_desktop_process(
            instance_system_type=instance_system_type,
            hps_port=hps_port,
            pim_port=pim_port,
            pim_socket_path=pim_socket_path,
            ui_enabled=ui_enabled,
            solution_name=solution_name,
            solution_type=solution_type,
            solution_dir=solution_dir,
            definition_file=definition_file,
            solution_api_port=solution_api_port,
            solution_ui_port=solution_ui_port,
            use_automatic_solution_locator=use_automatic_solution_locator,
            debug_mode_override=debug_mode_override,
            obfuscated_glow_pythonpath=obfuscated_glow_pythonpath,
            cwd=cwd,
            certificates_directory=certificates_directory,
            shutdown_api_server_first=shutdown_api_server_first,
        )
    elif deployment_type == Deployment.MultiContainer:
        if obfuscated_glow_pythonpath:
            pytest.fail(reason="GLOW src obfuscation not supported for DockerDeployment.")
        if shutdown_api_server_first is not None:
            pytest.skip(
                reason="shutdown_api_server_first with non-NULL value is not supported by DockerDeployment "
                "because it uses docker compose down which decides the order of shutdown.",
            )
        glow_server_process = _get_glow_docker_process(
            tmp_path_factory=tmp_path_factory,
            instance_system_type=instance_system_type,
            hps_port=hps_port,
            pim_port=pim_port,
            session_unique_id=session_unique_id,
            worker_id=worker_id,
            ui_enabled=ui_enabled,
            solution_type=solution_type,
            solution_dir=solution_dir,
            solution_api_port=solution_api_port,
            debug_mode_override=debug_mode_override,
            max_number_of_workers=max_number_of_workers,
            certificates_directory=certificates_directory,
        )
    else:
        pytest.fail(f"Deployment type {deployment_type} not recognized.")

    if not prevent_start:
        try:
            glow_server_process.start()
        except Exception:
            # Otherwise, it may leave running containers, volumes and networks when using docker
            glow_server_process.stop()
            raise

    return glow_server_process


def _get_glow_desktop_process(
    instance_system_type: TestProductInstanceSystemType | None,
    hps_port: int | None,
    pim_port: int | None,
    pim_socket_path: Path | None,
    ui_enabled: bool,
    solution_name: str,
    solution_type: type[T],
    solution_dir: Path,
    definition_file: Path | None,
    solution_api_port: int,
    solution_ui_port: int | None,
    use_automatic_solution_locator: bool,
    debug_mode_override: bool,
    obfuscated_glow_pythonpath: str | None,
    cwd: Path | None = None,
    certificates_directory: Path | None = None,
    shutdown_api_server_first: bool | None = None,
) -> GlowDesktopProcess[T]:
    # TODO: convert to glow_execution_configuration that is applied by default
    env = os.environ.copy()
    if instance_system_type == TestProductInstanceSystemType.HPS and hps_port:
        env["GLOW_PRODUCT_INSTANCE_SYSTEM"] = "HPS"
        env["GLOW_PRODUCT_INSTANCE_SYSTEM_HOST"] = "127.0.0.1"
        env["GLOW_PRODUCT_INSTANCE_SYSTEM_PORT"] = str(hps_port)
    elif instance_system_type == TestProductInstanceSystemType.PIM and pim_port:
        env["GLOW_PRODUCT_INSTANCE_SYSTEM"] = "PIM"
        env["GLOW_PRODUCT_INSTANCE_SYSTEM_HOST"] = "127.0.0.1"
        env["GLOW_PRODUCT_INSTANCE_SYSTEM_PORT"] = str(pim_port)
    elif instance_system_type == TestProductInstanceSystemType.PIM and pim_socket_path:
        env["GLOW_PRODUCT_INSTANCE_SYSTEM"] = "PIM"
        env["GLOW_PIM_SOCKET_PATH"] = pim_socket_path.as_posix()
    elif instance_system_type == TestProductInstanceSystemType._MOCK:  # pyright: ignore[reportPrivateUsage]
        env["GLOW_PRODUCT_INSTANCE_SYSTEM"] = "_MOCK"
    elif instance_system_type:
        raise RuntimeError(
            f"Invalid product system config: {instance_system_type=}, {hps_port=}, {pim_port=}, {pim_socket_path=}",
        )

    return GlowDesktopProcess(
        solution_name,
        solution_type,
        solution_dir=solution_dir,
        definition_file=definition_file,
        ui_enabled=ui_enabled,
        solution_api_port=solution_api_port,
        solution_ui_port=solution_ui_port,
        use_automatic_solution_locator=use_automatic_solution_locator,
        debug_mode_override=debug_mode_override,
        obfuscated_glow_pythonpath=obfuscated_glow_pythonpath,
        cwd=cwd,
        env=env,
        certificates_directory=certificates_directory,
        shutdown_api_server_first=shutdown_api_server_first,
    )


def _get_glow_docker_process(
    tmp_path_factory: pytest.TempPathFactory,
    instance_system_type: TestProductInstanceSystemType | None,
    hps_port: int | None,
    pim_port: int | None,
    session_unique_id: str,
    worker_id: str,
    ui_enabled: bool,
    solution_type: type[T],
    solution_dir: Path,
    solution_api_port: int,
    debug_mode_override: bool,
    use_root_path: bool = False,
    max_number_of_workers: int = 1,
    certificates_directory: Path | None = None,
) -> GlowDockerProcess[T]:
    # Relying only in numbered will not generated unique subdirectory names between pytest processes,
    # even if the entire path is unique in each case. We need unique directories because
    # docker-compose uses that to generate the container names, volumes and networks.
    if not session_unique_id:
        raise RuntimeError("session_unique_id is required to generate unique docker container names.")
    tmp_dir = tmp_path_factory.mktemp(basename=f"glow-e2e-{session_unique_id}-{worker_id}")

    # Bring the solution src
    solution_src = tmp_dir / "src"
    assert solution_dir.is_dir()
    solution_dest_dir = solution_src / "ansys" / "solutions" / solution_dir.name
    shutil.copytree(solution_dir, solution_dest_dir, dirs_exist_ok=True, ignore=IGNORE_PYC_FILES)

    # Copy Dockerfile
    dockerfile_orig_file = Path(__file__).parent / "container" / "Dockerfile"
    dockerfile_dest_file = tmp_dir / "Dockerfile"
    assert dockerfile_orig_file.is_file()
    shutil.copy(dockerfile_orig_file, tmp_dir)

    # Copy docker-compose file
    docker_compose_orig_file = Path(__file__).parent / "container" / "docker-compose.yaml"
    assert docker_compose_orig_file.is_file()
    shutil.copy(docker_compose_orig_file, tmp_dir)
    docker_compose_dest_file = tmp_dir / "docker-compose.yaml"

    local_src_dir = Path().cwd() / "src"
    if not local_src_dir.is_dir():
        # could happen in test environments where everything is pip installed.
        docker_compose_dest_file.write_text(
            docker_compose_dest_file.read_text().replace("      - ${LIBRARY_SRC_DIR}:/library/src/\n", ""),
        )

    # Configure .env, assuming that pytest will direct us to the local venv
    pytest_path = list(pytest.__path__)
    assert pytest_path
    local_venv_libs_dir = Path(pytest_path[0]).parent
    env_file = tmp_dir / ".env"
    env_file.write_text(
        f"LOCAL_PY_LIBS={local_venv_libs_dir.as_posix()}\n"
        f"LIBRARY_SRC_DIR={local_src_dir.as_posix()}\n"  # will not be used if local_src_dir doesn't exist
        f"SOLUTION_SRC_DIR={solution_src.as_posix()}\n"
        f"GLOW_API_NUMBER_OF_WORKERS={max_number_of_workers}\n",
    )

    # Set correct python version in Dockerfile
    dockerfile_content = dockerfile_dest_file.read_text()
    major_version, minor_version, _ = platform.python_version_tuple()
    dockerfile_content = dockerfile_content.replace(
        "FROM python:3.11-slim AS e2e_solution",
        f"FROM python:{major_version}.{minor_version}-slim AS e2e_solution",
    )
    dockerfile_dest_file.write_text(dockerfile_content)

    # Set unique image names
    # This will force to build new images in every pytest session
    docker_compose_content = docker_compose_dest_file.read_text()
    docker_compose_content = docker_compose_content.replace(
        "image: my-solution-e2e",
        f"image: my-solution-e2e-{session_unique_id}",
    )

    # Extend command in case Uvicorn's --root-path is required
    if use_root_path:
        docker_compose_content = docker_compose_content.replace(
            'command: "--host 0.0.0.0 --port 50000"',
            'command: "--host 0.0.0.0 --port 50000 --root-path /api"',
        )
    docker_compose_dest_file.write_text(docker_compose_content)

    base_override_file: Path | None = None

    transactions_tmp_dir = tmp_path_factory.mktemp(basename="glow_transactions")
    projects_tmp_dir = tmp_path_factory.mktemp(basename="glow_projects")

    base_override_file = _override_docker_compose_file(
        tmp_dir,
        solution_api_port,
        instance_system_type,
        hps_port,
        pim_port,
        transactions_tmp_dir,
    )

    return GlowDockerProcess(
        docker_compose_dest_file,
        solution_type,
        ui_enabled=ui_enabled,
        base_override_file=base_override_file,
        api_host_port=solution_api_port,
        transactions_tmp_dir=transactions_tmp_dir,
        projects_tmp_dir=projects_tmp_dir,
        debug_mode_override=debug_mode_override,
        product_system=instance_system_type,
        certificates_directory=certificates_directory,
    )


def _override_docker_compose_file(
    docker_solution_dir: Path,
    api_host_port: int,
    product_system: TestProductInstanceSystemType | None,
    hps_port: int | None,
    pim_port: int | None,
    transactions_tmp_dir: Path,
) -> Path:
    """
    For misc configurations that are not modified during tests, hence not worthy of a dynamic glow exec configurations.
    """
    product_platform = platform.system()
    compose_override_content = {
        "services": {
            "my-solution-api": {
                "extra_hosts": ["host.docker.internal:host-gateway"],
                "environment": ["XDG_DATA_HOME=/tmp"],
                "volumes": [f"{transactions_tmp_dir.as_posix()}:/transactions"],
            },
            "my-solution-ui": {
                "extra_hosts": ["host.docker.internal:host-gateway"],
                "environment": [
                    f"GLOW_WS_EVENTS_ADDR=ws://127.0.0.1:{api_host_port}",
                    f"GLOW_EXTERNAL_API_URL=http://127.0.0.1:{api_host_port}",
                    "GLOW_PORTAL_URL=http://127.0.0.1:12345",  # non functional but triggers UI changes
                ],
            },
        },
    }

    # TODO: If more flexibility for Product Instance System is needed, move to a configure_product_instance_system()
    # method in GlowBaseProcess classes.
    if product_system:
        product_system_port = hps_port if product_system.value == "HPS" else pim_port
        compose_override_content["services"]["my-solution-api"]["environment"].extend(
            [
                f"GLOW_PRODUCT_INSTANCE_SYSTEM={str(product_system.value)}",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST=host.docker.internal",
                f"GLOW_PRODUCT_INSTANCE_SYSTEM_PORT={str(product_system_port)}",
                f"GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM={product_platform}",
            ],
        )
        if product_system.value == "PIM":
            compose_override_content["services"]["my-solution-api"]["environment"].append(
                "GLOW_PRODUCT_HOST=host.docker.internal",
            )

    if product_platform == "Linux":
        compose_override_content["services"]["my-solution-api"]["user"] = f"{os.getuid()}:{os.getgid()}"  # type: ignore

    override_prefix = product_system.value if product_system else "no_product"
    compose_override_file = docker_solution_dir / f"docker-compose.{override_prefix}_system_override.yaml"
    compose_override_file.touch()
    with compose_override_file.open("w") as f:
        yaml.dump(compose_override_content, f, default_flow_style=False)

    return compose_override_file


# TODO: merge into run_glow() with a production_servers: bool parameter.
@pytest.fixture
def run_glow_production(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    worker_id: str,
    # start of custom fixtures
    session_log_manager: LogContainerManager,
    deployment_type: Deployment,
    instance_system_type: TestProductInstanceSystemType | None,
    hps_port: int | None,
    session_pim: PimProcess | None,
    pim_port: int | None,
    pim_socket_path: Path | None,
    ui_enabled: bool,
    debug_mode_override: bool,
    max_number_of_workers: int,
    certificates_directory: Path,
    shutdown_api_server_first: bool | None,
) -> YieldFixture[Callable[[type[T], Path], GlowBaseProcess[T]]]:
    glow_server_processes: list[GlowBaseProcess[T]] = []

    def _run_glow_process(
        solution_class: type[T],
        solution_dir: Path,
        ui_enabled: bool = ui_enabled,
        solution_api_port: int | None = None,
        solution_ui_port: int | None = None,
        env_file: Path | None = None,
        use_automatic_solution_locator: bool = False,
        use_root_path: bool = False,
        cwd: Path | None = None,
    ) -> GlowBaseProcess[T]:
        if solution_dir.is_file():
            definition_file = solution_dir
            solution_dir = definition_file.parent
            ui_app_file = None
        else:
            definition_file = solution_dir / "solution" / "definition.py"
            ui_app_file = solution_dir / "ui" / "app.py"
        solution_name = solution_class.__name__

        session_unique_id = str(getattr(request.config, "session_unique_id", ""))  # type: ignore

        if deployment_type == Deployment.Desktop:
            glow_server_process = GlowProductionProcess(
                solution_name,
                solution_dir,
                solution_class,
                definition_file,
                ui_app_file,
                ui_enabled=ui_enabled,
                solution_api_port=solution_api_port,
                solution_ui_port=solution_ui_port,
                env_file=env_file,
                use_automatic_solution_locator=use_automatic_solution_locator,
                use_root_path=use_root_path,
                cwd=cwd,
                certificates_directory=certificates_directory,
            )
        elif deployment_type == Deployment.MultiContainer:
            solution_api_port = solution_api_port if solution_api_port else get_random_free_port()
            glow_server_process = _get_glow_docker_process(
                tmp_path_factory=tmp_path_factory,
                instance_system_type=instance_system_type,
                hps_port=hps_port,
                pim_port=pim_port,
                session_unique_id=session_unique_id,
                worker_id=worker_id,
                ui_enabled=ui_enabled,
                solution_type=solution_class,
                solution_dir=solution_dir,
                solution_api_port=solution_api_port,
                debug_mode_override=debug_mode_override,
                use_root_path=use_root_path,
                certificates_directory=certificates_directory,
                max_number_of_workers=max_number_of_workers,
            )
        else:
            pytest.fail(f"Deployment type {deployment_type} not recognized.")

        glow_server_processes.append(glow_server_process)

        containers = [
            session_log_manager.add_log_container(
                glow_server_process.get_api_output,
                f"{deployment_type.name}_{GLOW_PROC_PROD_CONTAINER_NAME_PATTERN}_api_{len(glow_server_processes)}",
                ServiceType.API,
            ),
        ]

        if ui_enabled:
            ui_container = session_log_manager.add_log_container(
                glow_server_process.get_ui_output,
                f"{deployment_type.name}_{GLOW_PROC_PROD_CONTAINER_NAME_PATTERN}_ui_{len(glow_server_processes)}",
                ServiceType.UI,
            )
            containers.append(ui_container)
        if session_pim:
            session_log_manager.add_log_container(
                session_pim.get_pim_output,
                SESSION_PIM_CONTAINER_NAME,
                ServiceType.Other,
            )

        glow_server_process.attach_log_containers(containers)

        glow_server_process.start()

        return glow_server_process

    yield _run_glow_process

    for glow_server_process in glow_server_processes:
        glow_server_process.stop()
