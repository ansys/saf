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

import importlib
import json
import logging
import os
from pathlib import Path
import platform
import sys
from typing import Any
from uuid import uuid4

import httpx2
import yaml

from ansys.saf.desktop.orchestrator._config.schema import (
    DEPLOYMENT_DESKTOP,
    GLOW_API_HOST,
    GLOW_API_PORT,
    GLOW_API_URL,
    GLOW_CORS_ORIGINS,
    GLOW_DEPLOYMENT,
    GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION,
    GLOW_LOG_CONFIG,
    GLOW_METHOD_LOG_CONFIG,
    GLOW_PORTAL_URL,
    GLOW_PRODUCT_INSTANCE_SYSTEM_HOST,
    GLOW_PRODUCT_INSTANCE_SYSTEM_PORT,
    GLOW_SOLUTION_DEFINITION,
    GLOW_UI_HOST,
    GLOW_UI_LOG_CONFIG,
    GLOW_UI_PORT,
    GLOW_WS_EVENTS_ADDR,
    LOCALHOST_IP,
    OTEL_DASHBOARD_PORT,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_HEADERS,
    PIM_LOCALHOSTS,
    PORTAL_UI_HOST,
    PORTAL_UI_PORT,
    PROJECTS_DASHBOARD_PATH,
    SAF_DESKTOP_PROJECTS_DASHBOARD_PATH,
    Settings,
)
from ansys.saf.desktop.orchestrator._orchestration.additional_service_process import AdditionalServiceProcess
from ansys.saf.desktop.orchestrator._orchestration.orchestrator import Orchestrator
from ansys.saf.desktop.orchestrator._orchestration.otel_process import OtelProcess
from ansys.saf.desktop.orchestrator._orchestration.pim_process import PimProcess
from ansys.saf.desktop.orchestrator._orchestration.process import ServiceProcess
from ansys.saf.desktop.orchestrator._orchestration.python_process import PythonProcess
from ansys.saf.desktop.orchestrator._orchestration.service_info import ServiceInfo
from ansys.saf.desktop.orchestrator._orchestration.solution_ui_framework import SolutionUIFramework
from ansys.saf.desktop.orchestrator._telemetry.utilities import get_config_file
from ansys.saf.desktop.orchestrator._utilities.directories import find_product_instance_configs_dir
from ansys.saf.desktop.orchestrator._utilities.ip_utilities import get_random_free_port, try_response
from ansys.saf.glow.cli import run_api
from ansys.saf.product_configuration.manager.configurations_manager import ProductInstanceConfigurationsManager

logger = logging.getLogger(__name__)

PROJECTS_DASHBOARD_MODULE = "ansys_saf_projects_dashboard"


def _has_projects_dashboard() -> bool:
    return importlib.util.find_spec(PROJECTS_DASHBOARD_MODULE) is not None  # type: ignore[union-attr]


def _get_or_assign_port(env_var_name: str) -> int:
    return int(os.getenv(env_var_name, get_random_free_port()))


def _get_or_assign_host(env_var_name: str) -> str:
    return os.getenv(env_var_name, LOCALHOST_IP)


def _get_or_assign_url(env_var_name: str) -> str:
    return os.getenv(env_var_name, f"http://{LOCALHOST_IP}:{get_random_free_port()}")


class Launcher:
    def __init__(
        self,
        settings: Settings,
        solution_module_name: str,
        definition_module_name: str,
        with_pim: bool,
        with_ui: bool,
        ui_framework: SolutionUIFramework,
        with_portal: bool,
        env_file: Path | None,
        enable_automatic_project_migration: bool,
        log_to_files: bool = False,
    ) -> None:
        """Launches all the services (api, ui, pim, and portal) needed by the solutions."""
        self._orchestrator = Orchestrator()
        self._settings = settings
        self._with_pim = with_pim
        self._with_ui = with_ui
        self._ui_framework = ui_framework
        self._solution_module_name = solution_module_name
        self._definition_module_name = definition_module_name
        self._with_portal = with_portal
        self._use_projects_dashboard = (
            with_portal and with_ui and ui_framework != SolutionUIFramework.streamlit and _has_projects_dashboard()
        )
        self._env_file = env_file
        self._enable_automatic_project_migration = enable_automatic_project_migration
        self._log_to_files = log_to_files
        self._otlp_api_key = str(uuid4())

        # Finding the right hosts has no side effect. So, we are doing it even if services are not needed.
        self._hosts: dict[str, str] = {
            "solution_api": _get_or_assign_host(GLOW_API_HOST),
            "solution_ui": _get_or_assign_host(GLOW_UI_HOST),
            "portal_ui": _get_or_assign_host(PORTAL_UI_HOST),
            "pim": _get_or_assign_host(GLOW_PRODUCT_INSTANCE_SYSTEM_HOST),
        }

        # Find free ports in advance. It allows us to have all the information for launching the services beforehand.
        # Non-negligible race condition until we use them, though.
        self._ports: dict[str, int] = {"solution_api": _get_or_assign_port(GLOW_API_PORT)}
        if not log_to_files:
            self._ports["otel"] = _get_or_assign_port(OTEL_DASHBOARD_PORT)
            otlp_endpoint = _get_or_assign_url(OTEL_EXPORTER_OTLP_ENDPOINT)
            self._urls = {
                "otel_exporter": otlp_endpoint,
            }
        if self._with_portal and not self._use_projects_dashboard:
            self._ports["portal_ui"] = _get_or_assign_port(PORTAL_UI_PORT)
        if self._with_ui:
            self._ports["solution_ui"] = _get_or_assign_port(GLOW_UI_PORT)
        if self._with_pim:
            if platform.system() == "Windows" or self._hosts["pim"] not in PIM_LOCALHOSTS:
                # If linux + localhost, we use a unix domain socket instead.
                self._ports["pim"] = _get_or_assign_port(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT)
            if (
                platform.system() == "Linux"
                and self._hosts["pim"] in PIM_LOCALHOSTS
                and os.getenv(GLOW_PRODUCT_INSTANCE_SYSTEM_PORT)
            ):
                logger.warning(
                    "PIM on Linux with a localhost IP can only be run with UDS. Ignoring the environment variable "
                    f"{GLOW_PRODUCT_INSTANCE_SYSTEM_PORT}.",
                )

        self._additional_services_ports: dict[str, int] = {}
        self._socket_path: Path | None = None

    @property
    def use_projects_dashboard(self) -> bool:
        return self._use_projects_dashboard

    @property
    def projects_dashboard_path(self) -> str:
        """Path appended to the solution UI URL when ``--portal`` uses Projects Dashboard.

        Override with ``SAF_DESKTOP_PROJECTS_DASHBOARD_PATH`` (default: ``/projects``).
        """
        return os.getenv(SAF_DESKTOP_PROJECTS_DASHBOARD_PATH, PROJECTS_DASHBOARD_PATH)

    def start_pim(self) -> None:
        solution_module = importlib.import_module(self._definition_module_name)
        instance_config_mgr = ProductInstanceConfigurationsManager()
        if custom_configs_dir := find_product_instance_configs_dir(solution_module):
            instance_config_mgr.load_configurations(custom_configs_dir)
        configurations = instance_config_mgr.list_configurations()
        # PIM Light Server doesn't support OTLP, so we always log to file to avoid spamming the console output.
        pim_log_file = self._settings.computed_solution_appdata_directory / "pim_light_server.log"
        pim_process = PimProcess(
            configurations,
            self._ports.get("pim"),
            ip=self._hosts["pim"],
            health_check_timeout=self._settings.saf_desktop_health_check_timeout,
            log_file=pim_log_file,
        )
        self._socket_path = pim_process.socket_path
        self._orchestrator.start_service("PIM", pim_process, allow_window=False)

    def start_otel(self) -> None:
        otel_process = OtelProcess(
            dashboard_port=self._ports["otel"],
            otlp_url=self._urls["otel_exporter"],
            health_check_timeout=self._settings.saf_desktop_health_check_timeout,
            api_key=self._otlp_api_key,
        )
        self._orchestrator.start_service("OTEL", otel_process, allow_window=False)

    def _configure_solution_api_environment(self) -> dict[str, str]:
        api_env = os.environ.copy()
        api_env[GLOW_DEPLOYMENT] = DEPLOYMENT_DESKTOP

        if "solution_ui" in self._ports:
            # keeping this http as it's always the case in desktop mode.
            ui_origin = f"http://{self._hosts['solution_ui']}:{self._ports['solution_ui']}"
            existing_origins: list[str] = json.loads(api_env[GLOW_CORS_ORIGINS]) if GLOW_CORS_ORIGINS in api_env else []
            api_env[GLOW_CORS_ORIGINS] = json.dumps(list(dict.fromkeys([ui_origin, *existing_origins])))

        if self._with_pim:
            if pim_port := self._ports.get("pim"):
                api_env["GLOW_PRODUCT_INSTANCE_SYSTEM_HOST"] = self._hosts["pim"]
                api_env["GLOW_PRODUCT_INSTANCE_SYSTEM_PORT"] = str(pim_port)
            elif self._socket_path:
                api_env["GLOW_PIM_SOCKET_PATH"] = self._socket_path.as_posix()
            else:
                raise RuntimeError("PIM enabled, but port nor socket are defined.")

        if self._log_to_files:
            api_env[GLOW_LOG_CONFIG] = str(get_config_file("api_server", self._definition_module_name))
            api_env[GLOW_METHOD_LOG_CONFIG] = str(
                get_config_file("method_runner", self._definition_module_name),
            )
        else:
            api_env[OTEL_EXPORTER_OTLP_ENDPOINT] = self._urls["otel_exporter"]
            api_env[OTEL_EXPORTER_OTLP_HEADERS] = f"x-otlp-api-key={self._otlp_api_key}"

        if self._enable_automatic_project_migration:
            api_env[GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION] = str(True)
        return api_env

    def start_solution_api(self) -> None:
        api_kwargs: dict[str, Any] = {
            "host": self._hosts["solution_api"],
            "port": self._ports["solution_api"],
            "definition_module": self._definition_module_name,
        }
        if self._env_file:
            api_kwargs["env_file"] = self._env_file.resolve()
        api_env = self._configure_solution_api_environment()
        api_process = PythonProcess(
            run_api,
            api_kwargs,
            port=api_kwargs["port"],
            ip=api_kwargs["host"],
            health_check_timeout=self._settings.saf_desktop_health_check_timeout,
            env=api_env,
        )
        self._orchestrator.start_service("API", api_process)

    def _configure_solution_ui_environment(self) -> dict[str, str]:
        ui_env = os.environ.copy()
        ui_env[GLOW_DEPLOYMENT] = DEPLOYMENT_DESKTOP
        ui_env[GLOW_UI_PORT] = str(self._ports["solution_ui"])
        ui_env[GLOW_UI_HOST] = self._hosts["solution_ui"]
        ui_env[GLOW_API_URL] = f"http://{self._hosts['solution_api']}:{self._ports['solution_api']}"
        if os.getenv(GLOW_WS_EVENTS_ADDR) is None:
            ui_env[GLOW_WS_EVENTS_ADDR] = f"ws://{self._hosts['solution_api']}:{self._ports['solution_api']}"

        if self._with_portal:
            if self._use_projects_dashboard:
                ui_env[GLOW_PORTAL_URL] = (
                    f"http://{self._hosts['solution_ui']}:{self._ports['solution_ui']}{self.projects_dashboard_path}"
                )
            else:
                ui_env[GLOW_PORTAL_URL] = f"http://{self._hosts['portal_ui']}:{self._ports['portal_ui']}"

        if self._log_to_files:
            ui_env[GLOW_UI_LOG_CONFIG] = str(get_config_file("ui_server", self._definition_module_name))
        else:
            ui_env[OTEL_EXPORTER_OTLP_ENDPOINT] = self._urls["otel_exporter"]
            ui_env[OTEL_EXPORTER_OTLP_HEADERS] = f"x-otlp-api-key={self._otlp_api_key}"

        return ui_env

    def start_solution_ui(self) -> None:
        """Starts the solution UI service using a generic approach."""
        args = [sys.executable, "-m", self._solution_module_name, "ui"]
        if self._env_file:
            args.extend(["--env-file", str(self._env_file.resolve())])
        ui_env = self._configure_solution_ui_environment()
        self._start_solution_ui_service(args, self._orchestrator, health_route="/health", ui_env=ui_env)

    def _start_solution_ui_service(
        self,
        args: list[str],
        orchestrator: Orchestrator,
        health_route: str = "",
        ui_env: dict[str, str] | None = None,
    ) -> None:
        """Common method to start the solution UI service with given arguments."""
        ui_process = ServiceProcess(
            args,
            port=self._ports["solution_ui"],
            ip=self._hosts["solution_ui"],
            env=ui_env,
            health_route=health_route,
            health_check_timeout=self._settings.saf_desktop_health_check_timeout,
        )
        orchestrator.start_service("UI", ui_process)

    def _configure_portal_ui_environment(self) -> dict[str, str]:
        portal_env = os.environ.copy()
        portal_env.setdefault(GLOW_SOLUTION_DEFINITION, self._definition_module_name)
        if not self._log_to_files:
            portal_env[OTEL_EXPORTER_OTLP_ENDPOINT] = self._urls["otel_exporter"]
            portal_env[OTEL_EXPORTER_OTLP_HEADERS] = f"x-otlp-api-key={self._otlp_api_key}"

        return portal_env

    def start_portal(self, additional_ui_params: str = "") -> None:
        # Portal is not a mandatory service defined as dependency in the orchestrator.
        try:
            from ansys.saf.desktop.portal.server.run_portal_server import (  # pyright: ignore
                run_portal,  # pyright: ignore[reportUnknownVariableType]
            )
        except ModuleNotFoundError as ex:
            # fallback to the old portal for backward compatibility.
            try:
                from ansys.saf.portal.desktop.server.run_portal_server import (  # pyright: ignore[reportMissingImports]
                    run_portal,  # pyright: ignore[reportUnknownVariableType]
                )
            except ModuleNotFoundError:
                raise ModuleNotFoundError(
                    "The package 'ansys-saf-desktop-portal' is not installed or could not be found.",
                ) from ex

        portal_kwargs: dict[str, Any] = {
            "host": self._hosts["portal_ui"],
            "port": self._ports["portal_ui"],
            "ui_url": f"http://{self._hosts['solution_ui']}:{self._ports['solution_ui']}/{additional_ui_params}",
            "api_url": f"http://{self._hosts['solution_api']}:{self._ports['solution_api']}",
            "api_version": self._settings.portal_api_version,
        }

        portal_env = self._configure_portal_ui_environment()
        portal_process = PythonProcess(
            run_portal,  # pyright: ignore[reportUnknownArgumentType]
            portal_kwargs,
            port=portal_kwargs["port"],
            ip=portal_kwargs["host"],
            health_route=f"/api/{portal_kwargs['api_version']}/health",
            health_check_timeout=self._settings.saf_desktop_health_check_timeout,
            env=portal_env,
        )
        self._orchestrator.start_service("PORTAL", portal_process)

    def wait_for_healthy(self, service_types: list[str] | None = None) -> None:
        self._orchestrator.healthy(service_types)

    def get_project(
        self,
        project_name: str,
    ) -> str:
        return f"{self.get_service_info('UI').address}/{project_name}"

    def stop(self) -> None:
        try:
            service = self._orchestrator.try_get_service("API")
            if service is not None:
                api_address = service.address
                if try_response(f"{api_address}/health"):
                    with httpx2.Client(timeout=30) as http_client:
                        http_client.post(f"{api_address}/desktop:exit").raise_for_status()
        except Exception:
            msg = (
                "Solution API failed to exit cleanly. "
                "Long-running transactions and product instances were terminated instead of shutting down gracefully."
            )
            logger.warning(msg)
        finally:
            self._orchestrator.stop()

    def get_service_info(self, service_type: str) -> ServiceInfo:
        return self._orchestrator.get_service(service_type)

    def start_additional_services(self, services_file_path: Path) -> dict[str, ServiceInfo]:
        additional_services = self._load_additional_services(services_file_path)
        service_info: dict[str, ServiceInfo] = {}
        if additional_services:
            for service_spec in additional_services:
                port = get_random_free_port()
                if self._validate_service_spec(service_spec):
                    name = service_spec["name"].upper()
                    health_check: dict[str, str] = service_spec["health_check"]
                    command_line = service_spec["command_line_template"].split()
                    if command_line[0] == "python":
                        command_line[0] = sys.executable
                    command_line = [arg.replace("$PORT", str(port)) for arg in command_line]
                    command_line = " ".join(command_line)
                    logger.info(f"- Starting {name}...")
                    try:
                        self._additional_services_ports[name] = port
                        service_process = AdditionalServiceProcess(
                            name=name,
                            command_line_template=command_line,
                            health_check=health_check,
                            health_check_timeout=self._settings.saf_desktop_health_check_timeout,
                            port=port,
                        )
                        service_info[name] = self._orchestrator.start_service(name, service_process)
                    except Exception as e:
                        logger.error(f"Failed to start service '{name}': {str(e)}")

        return service_info

    def _load_additional_services(self, config_path: Path) -> Any | None:
        try:
            with config_path.open("r") as file:
                config = yaml.safe_load(file)
            return config
        except FileNotFoundError:
            logger.warning(f"The file {config_path} was not found.")
            return None
        except yaml.YAMLError as exc:
            logger.warning(f"Error parsing YAML file at {config_path}: {exc}")
            return None

    def _validate_service_spec(self, service_spec: dict[str, Any]) -> bool:
        if not isinstance(service_spec, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            logger.error(f"Service specification is not a dictionary: {service_spec!r}")
            return False
        if "name" not in service_spec:
            logger.error("Missing 'name' key in service specification.")
            return False
        if "health_check" not in service_spec or not isinstance(service_spec["health_check"], dict):
            logger.error(
                f"Missing or invalid 'health_check' key for service '{service_spec.get('name', '<unknown>')}'.",
            )
            return False
        if "command_line_template" not in service_spec:
            logger.error(f"Missing 'command_line_template' key for service '{service_spec.get('name', '<unknown>')}'.")
            return False
        return True
