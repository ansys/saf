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

from dataclasses import dataclass, field
import os
from pathlib import Path
import platform
import tempfile
from typing import Any
import uuid

from pydantic import PostgresDsn
import yaml

from ansys.saf.testing._common.network import get_random_free_port
from ansys.saf.glow.client import Deployment  # pyright: ignore[reportMissingImports]


@dataclass
class EnvVars:
    env_vars: dict[str, str | None] = field(default_factory=dict[str, str | None])
    only_api: list[str] = field(default_factory=list[str])
    only_ui: list[str] = field(default_factory=list[str])


@dataclass
class Ports:
    api: list[str] = field(default_factory=list[str])
    ui: list[str] = field(default_factory=list[str])


@dataclass
class Volumes:
    common: list[str] = field(default_factory=list[str])


class BaseGlowConfiguration:
    config_type: str = "base_glow_configuration"

    def __init__(self, deployment_type: Deployment) -> None:
        self._deployment_type: Deployment = deployment_type
        self._override_file: Path | None = None
        self._backup_envs: dict[str, str] = {}

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars()

    @property
    def volumes_to_mount(self) -> Volumes:
        return Volumes()

    @property
    def ports_to_expose(self) -> Ports:
        return Ports()

    def setup(self, env: dict[str, str] | None = None, compose_override_file: Path | None = None) -> None:
        if self._deployment_type == Deployment.Desktop:
            assert env is not None
            self._desktop_setup(env)
        elif self._deployment_type == Deployment.MultiContainer:
            assert compose_override_file
            self._docker_setup(compose_override_file)
        else:
            raise NotImplementedError("Deployment not implemented")

    def _desktop_setup(self, env: dict[str, str]) -> None:
        for env_var_name, env_var_value in self.env_vars_to_configure.env_vars.items():
            if env_var_name in env:
                self._backup_envs[env_var_name] = env[env_var_name]
            if env_var_value is None:
                env.pop(env_var_name, None)
            else:
                env[env_var_name] = env_var_value

    def _docker_setup(self, compose_override_file: Path) -> None:
        self._override_file = compose_override_file
        compose_override_content = {
            "services": {
                "my-solution-api": {
                    "environment": {
                        env_var_name: env_var_value if env_var_value is not None else "!reset null"
                        for env_var_name, env_var_value in self.env_vars_to_configure.env_vars.items()
                        if env_var_name not in self.env_vars_to_configure.only_ui
                    },
                    "volumes": self.volumes_to_mount.common,
                    "ports": self.ports_to_expose.api,
                },
                "my-solution-ui": {
                    "environment": {
                        env_var_name: env_var_value if env_var_value is not None else "!reset null"
                        for env_var_name, env_var_value in self.env_vars_to_configure.env_vars.items()
                        if env_var_name not in self.env_vars_to_configure.only_api
                    },
                    "volumes": self.volumes_to_mount.common,
                    "ports": self.ports_to_expose.ui,
                },
            },
        }
        write_docker_compose_file(compose_override_content, compose_override_file)

    def teardown(self, env: dict[str, str] | None = None) -> None:
        if self._deployment_type == Deployment.Desktop:
            assert env is not None
            self._desktop_teardown(env)
        elif self._deployment_type == Deployment.MultiContainer:
            self._docker_teardown()
        else:
            raise NotImplementedError("Deployment not implemented")

    def _desktop_teardown(self, env: dict[str, str]) -> None:
        for env_var_name in self.env_vars_to_configure.env_vars:
            env.pop(env_var_name, None)
        for env_var_name, env_var_value in self._backup_envs.items():
            env[env_var_name] = env_var_value

    def _docker_teardown(self) -> None:
        if self._override_file:
            self._override_file.unlink(missing_ok=True)


def write_docker_compose_file(content: dict[Any, Any], file: Path):
    with file.open("w") as f:
        yaml.dump(content, f, default_style=None, default_flow_style=False)

    # I did not find a clean way to write the !reset tag without quotes right away
    needs_rewrite: bool = False
    lines = file.open("r").readlines()
    for i, line in enumerate(lines):
        if "!reset" in line:
            needs_rewrite = True
            lines[i] = line.replace("'", "")

    if needs_rewrite:
        with file.open("w") as f:
            f.writelines(lines)


# =================================================== [LOGGING] =================================================== #


class LoggingConfiguration(BaseGlowConfiguration):
    """Configure the location of the YAML logging configuration files for each service."""

    config_type = "logging_configuration"

    def __init__(self, deployment_type: Deployment, tag: str = ""):
        super().__init__(deployment_type)
        self._glow_logging_config_files_folder: Path = Path("tests") / "mocks" / "logging_configs"
        assert self._glow_logging_config_files_folder.is_dir()
        assert list(self._glow_logging_config_files_folder.glob("*.yaml"))
        self.tag = tag
        self._temp_config_folder = Path(tempfile.gettempdir()) / f"glow_logs_{uuid.uuid4()}"
        self._temp_config_folder.mkdir(parents=True, exist_ok=True)
        self._configs_dir = (
            self._temp_config_folder.resolve() if self._deployment_type == Deployment.Desktop else Path("/tmp_configs")
        )

    def teardown(self, env: dict[str, str] | None = None) -> None:
        super().teardown(env=env)
        # Delete the logging configuration files from the root/temp_config folder
        for file in self._temp_config_folder.glob("*.yaml"):
            file.unlink(missing_ok=True)
        self._temp_config_folder.rmdir()


class DefaultLoggingConfig(LoggingConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"GLOW_LOG_CONFIG": None, "GLOW_METHOD_LOG_CONFIG": None, "GLOW_UI_LOG_CONFIG": None},
            only_api=["GLOW_LOG_CONFIG", "GLOW_METHOD_LOG_CONFIG"],
            only_ui=["GLOW_UI_LOG_CONFIG"],
        )


class EnvVarLoggingConfig(LoggingConfiguration):
    def __init__(self, deployment_type: Deployment):
        super().__init__(deployment_type, tag=" [ENV VAR CONFIG USED]")
        for file in self._glow_logging_config_files_folder.glob("*.yaml"):
            if file.name.endswith("_to_file.yaml") or file.name.endswith("_old.yaml"):
                continue
            config_dict = yaml.safe_load(file.open("r"))
            config_dict["formatters"]["streamFormat"]["format"] += self.tag
            yaml.safe_dump(config_dict, (self._temp_config_folder / file.name).open("w"))

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_LOG_CONFIG": str(self._configs_dir / "api_server_config.yaml"),
                "GLOW_METHOD_LOG_CONFIG": str(self._configs_dir / "method_runner_config.yaml"),
                "GLOW_UI_LOG_CONFIG": str(self._configs_dir / "ui_server_config.yaml"),
            },
            only_api=["GLOW_LOG_CONFIG", "GLOW_METHOD_LOG_CONFIG"],
            only_ui=["GLOW_UI_LOG_CONFIG"],
        )

    @property
    def volumes_to_mount(self) -> Volumes:
        return Volumes(common=[f"{self._temp_config_folder.resolve().as_posix()}:/tmp_configs"])


class EnvVarLoggingToFileConfig(LoggingConfiguration):
    def __init__(self, deployment_type: Deployment):
        super().__init__(deployment_type, tag=" [ENV VAR CONFIG TO FILE USED]")
        for file in self._glow_logging_config_files_folder.glob("*.yaml"):
            if not file.name.endswith("_to_file.yaml"):
                continue
            config_dict = yaml.safe_load(file.open("r"))
            config_dict["formatters"]["fileFormat"]["format"] += self.tag
            yaml.safe_dump(config_dict, (self._temp_config_folder / file.name).open("w"))

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_LOG_CONFIG": str(self._configs_dir / "api_server_config_to_file.yaml"),
                "GLOW_METHOD_LOG_CONFIG": str(self._configs_dir / "method_runner_config_to_file.yaml"),
                "GLOW_UI_LOG_CONFIG": str(self._configs_dir / "ui_server_config_to_file.yaml"),
            },
            only_api=["GLOW_LOG_CONFIG", "GLOW_METHOD_LOG_CONFIG"],
            only_ui=["GLOW_UI_LOG_CONFIG"],
        )

    @property
    def volumes_to_mount(self) -> Volumes:
        return Volumes(common=[f"{self._temp_config_folder.resolve().as_posix()}:/tmp_configs"])


# ================================================== [DEPLOYMENT] ==================================================== #


class DeploymentConfiguration(BaseGlowConfiguration):
    config_type = "deployment_configuration"


class DefaultDeploymentConfiguration(DeploymentConfiguration): ...


class DesktopDeploymentConfiguration(DeploymentConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_DEPLOYMENT": "Desktop"})


class DockerDeploymentConfiguration(DeploymentConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_DEPLOYMENT": Deployment.MultiContainer.value})


# ==================================================== [DEBUG] ==================================================== #


class DebugConfiguration(BaseGlowConfiguration):
    """
    Configure debug mode, optionally specifying the port. The setting to keep transaction files is also included
    in this configuration, since that behavior is also linked to debug mode.
    """

    config_type = "debug_configuration"

    def __init__(
        self,
        deployment_type: Deployment,
        keep_transaction_files: bool | None = None,
        debug_port: int | None = -1,
    ):
        # Default debug_port to -1 since debugpy causes many issues in CI runners
        super().__init__(deployment_type)
        self.debug_port = debug_port
        self.keep_transaction_files = keep_transaction_files


class DefaultDebug(DebugConfiguration): ...


class EnvVarDebug(DebugConfiguration):
    def __init__(
        self,
        deployment_type: Deployment,
        keep_transaction_files: bool | None = None,
        debug_port: int | None = -1,
    ):
        super().__init__(deployment_type, keep_transaction_files, debug_port or get_random_free_port())

    @property
    def env_vars_to_configure(self) -> EnvVars:
        env_vars = EnvVars(
            env_vars={
                "GLOW_DEBUG": "True",
                "GLOW_KEEP_TRANSACTION_FILES": "True" if self.keep_transaction_files else None,
                "GLOW_DEBUG_API_PORT": str(self.debug_port),
            },
            only_api=["GLOW_KEEP_TRANSACTION_FILES", "GLOW_DEBUG_API_PORT"],
        )
        return env_vars

    @property
    def ports_to_expose(self) -> Ports:
        if self.debug_port == -1:
            return Ports()
        return Ports(api=[f"{self.debug_port}:{self.debug_port}"])


class EnvVarNoDebug(DebugConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_DEBUG": "False",
                "GLOW_KEEP_TRANSACTION_FILES": "True" if self.keep_transaction_files else None,
            },
            only_api=["GLOW_KEEP_TRANSACTION_FILES"],
        )


# =============================================== [API HOT RELOAD] =================================================== #


class ApiHotReloadConfiguration(BaseGlowConfiguration):
    """Configure the API server to use hot reload mode."""

    config_type = "api_hot_reload_configuration"

    def __init__(self, deployment_type: Deployment, hot_reload_monitoring_dir: Path | None = None) -> None:
        super().__init__(deployment_type)
        self._hot_reload_monitoring_dir = hot_reload_monitoring_dir


class DisableApiHotReload(ApiHotReloadConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_API_HOT_RELOAD": "False"}, only_api=["GLOW_API_HOT_RELOAD"])


class EnableApiHotReload(ApiHotReloadConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_API_HOT_RELOAD": "True"}, only_api=["GLOW_API_HOT_RELOAD"])


class UnconfigureApiHotReload(ApiHotReloadConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_API_HOT_RELOAD": None}, only_api=["GLOW_API_HOT_RELOAD"])


class EnableApiHotReloadWithExplictDirectory(ApiHotReloadConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._hot_reload_monitoring_dir is not None, "hot_reload_monitoring_dir must be set"
        return EnvVars(
            env_vars={
                "GLOW_API_HOT_RELOAD": "True",
                "GLOW_API_HOT_RELOAD_MONITORING_DIR": str(self._hot_reload_monitoring_dir),
            },
            only_api=["GLOW_API_HOT_RELOAD", "GLOW_API_HOT_RELOAD_MONITORING_DIR"],
        )


# ================================================== [UI DEBUG] ================================================== #


class UIDebugConfiguration(BaseGlowConfiguration):
    """Configure UI debug mode, optionally specifying the port."""

    config_type = "ui_debug_configuration"

    def __init__(self, deployment_type: Deployment, debug_port: int | None = -1) -> None:
        # Default debug_port to -1 since debugpy causes many issues in CI runners
        super().__init__(deployment_type)
        self.debug_port = debug_port


class EnvVarUIDebug(UIDebugConfiguration):
    def __init__(self, deployment_type: Deployment, debug_port: int | None = -1) -> None:
        super().__init__(deployment_type, debug_port or get_random_free_port())

    @property
    def env_vars_to_configure(self) -> EnvVars:
        env_vars = EnvVars(
            env_vars={
                "GLOW_UI_PYTHON_DEBUGGING": "True",
                "GLOW_DEBUG_UI_PORT": str(self.debug_port),
            },
            only_ui=["GLOW_UI_PYTHON_DEBUGGING", "GLOW_DEBUG_UI_PORT"],
        )
        return env_vars

    @property
    def ports_to_expose(self) -> Ports:
        if self.debug_port == -1:
            return Ports()
        return Ports(ui=[f"{self.debug_port}:{self.debug_port}"])


class EnvVarUINoDebug(UIDebugConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_UI_PYTHON_DEBUGGING": "False"}, only_ui=["GLOW_UI_PYTHON_DEBUGGING"])


class DefaultUIDebug(UIDebugConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_UI_PYTHON_DEBUGGING": None}, only_ui=["GLOW_UI_PYTHON_DEBUGGING"])


# ================================================= [LOG LEVEL] ================================================= #

# FIXME: Due to the implementation of GlowProcess, it's not possible to test the loglevel set above INFO
# (e.g., WARNING, ERROR, CRITICAL) without enabling debug mode. The reason for this limitation is that we
# rely on INFO log messages to parse the completion of startup, extract the path of the container log files,
# and obtain port information from each container for the final GLOW health check.


class LogLevelConfiguration(BaseGlowConfiguration):
    """Configure default loglevel. Some configurations also alter debug mode, as debug mode also defines loglevel."""

    config_type = "log_level_configuration"

    def __init__(self, deployment_type: Deployment) -> None:
        super().__init__(deployment_type)
        self.log_level: str
        self.debug: bool


class DefaultLogLevel(LogLevelConfiguration):
    def __init__(self, deployment_type: Deployment) -> None:
        super().__init__(deployment_type)
        self.log_level = "INFO"
        self.debug = False

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_LOGGING_LEVEL": None})


class EnvVarDebugLogLevel(LogLevelConfiguration):
    def __init__(self, deployment_type: Deployment) -> None:
        super().__init__(deployment_type)
        self.log_level = "DEBUG"
        self.debug = False

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_LOGGING_LEVEL": "DEBUG"})


class EnvVarErrorLogLevelWithDebugMode(LogLevelConfiguration):
    def __init__(self, deployment_type: Deployment) -> None:
        super().__init__(deployment_type)
        self.log_level = "ERROR"
        self.debug = True

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_DEBUG": "True", "GLOW_LOGGING_LEVEL": "ERROR"})


# ================================================= [TRACING] ================================================= #


class OpenTelemetryConfiguration(BaseGlowConfiguration):
    """Configure the OpenTelemetry endpoint."""

    config_type = "otlp_configuration"


class OTELconsole(OpenTelemetryConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"OTEL_EXPORTER_OTLP_ENDPOINT": "console"})


class NoOTEL(OpenTelemetryConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"OTEL_EXPORTER_OTLP_ENDPOINT": None})


# ================================================= [TRACING] ================================================= #


class HpsAuthConfiguration(BaseGlowConfiguration):
    """Configure the HPS Auth system."""

    config_type = "hps_auth_configuration"


class HpsMissingAuth(HpsAuthConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_HPS_CLIENT_ID": None,
                "GLOW_HPS_KC_REALM": None,
                "GLOW_HPS_KC_RELATIVE_PATH": None,
                "GLOW_HPS_USERNAME": None,
                "GLOW_HPS_PASSWORD": None,
            },
        )


class HpsUserPswdAuth(HpsAuthConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_HPS_CLIENT_ID": None,
                "GLOW_HPS_KC_REALM": None,
                "GLOW_HPS_KC_RELATIVE_PATH": None,
                "GLOW_HPS_USERNAME": "repadmin",
                "GLOW_HPS_PASSWORD": "repadmin",
            },
        )


class HpsKeyCloakAuth(HpsAuthConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_HPS_CLIENT_ID": "rep-jms-web",
                "GLOW_HPS_KC_REALM": "rep",
                "GLOW_HPS_KC_RELATIVE_PATH": "auth",
                "GLOW_HPS_USERNAME": None,
                "GLOW_HPS_PASSWORD": None,
            },
        )


class HpsTokenPassThroughAuth(HpsAuthConfiguration):
    def __init__(self, deployment_type: Deployment, hps_host: str | None = None):
        super().__init__(deployment_type)
        self._hps_host = hps_host or "localhost"

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_HPS_CLIENT_ID": "rep-impersonation",
                "GLOW_HPS_KC_REALM": "rep",
                "GLOW_HPS_KC_RELATIVE_PATH": "auth",
                "GLOW_AUTH_ISSUER_URL": f"https://{self._hps_host}:8443/hps/auth/realms/rep",
                "GLOW_AUTH_DISABLED": "False",
                "GLOW_AUTH_CLIENT_ID": "rep-jms-web",
                "GLOW_HPS_HOST": f"{self._hps_host}",
                "GLOW_HPS_PORT": "8443",
            },
        )


# ================================================= [TRANSACTIONS] ================================================= #


class MethodExecutionDirConfiguration(BaseGlowConfiguration):
    """
    Configure a custom transaction method execution directory. No effect implemented for DockerDeployment since we use
    this option already with the /transactions folder.
    """

    config_type = "method_dir_configuration"

    def __init__(self, deployment_type: Deployment, method_custom_dir: Path | None = None):
        super().__init__(deployment_type)
        self.method_custom_dir = method_custom_dir

    def _docker_setup(self, compose_override_file: Path) -> None:
        pass

    def _docker_teardown(self) -> None:
        pass


class CustomMethodExecutionDirectory(MethodExecutionDirConfiguration):
    def __init__(self, deployment_type: Deployment, tmp_path: Path):
        method_custom_dir = tmp_path / str(uuid.uuid4())
        method_custom_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(deployment_type, method_custom_dir)

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_METHOD_EXECUTION_DIRECTORY": str(self.method_custom_dir)})


class DefaultMethodExecutionDirectory(MethodExecutionDirConfiguration):
    def __init__(self, deployment_type: Deployment, tmp_path: Path | None = None):
        super().__init__(deployment_type)

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_METHOD_EXECUTION_DIRECTORY": None})


# ============================================= [Instance System] ================================================= #


class InstanceSystemEnvVarConfig(BaseGlowConfiguration):
    """Configure the instance system through the environment."""

    config_type = "instance_system_configuration"

    def __init__(
        self,
        deployment_type: Deployment,
        pim_port: int | None = None,
        pim_socket_path: Path | None = None,
        pim_host: str = "localhost",
        certs_dir: Path | None = None,
    ):
        super().__init__(deployment_type)
        self._pim_port = pim_port
        self._pim_socket_path = pim_socket_path
        self._pim_host = pim_host
        self._certs_dir = certs_dir

    def _docker_setup(self, compose_override_file: Path) -> None:
        pass  # FIXME: why?

    def _docker_teardown(self) -> None:
        pass  # FIXME: why?


class InsecurePIMEnvVarConfig(InstanceSystemEnvVarConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        # no socket path nor certificates.
        assert self._pim_port
        assert self._pim_host
        return EnvVars(
            env_vars={
                "GLOW_PRODUCT_INSTANCE_SYSTEM": "PIM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST": self._pim_host,
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT": str(self._pim_port),
            },
            only_api=[
                "GLOW_PRODUCT_INSTANCE_SYSTEM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT",
            ],
        )


class SocketPlusPortsPIMEnvVarConfig(InstanceSystemEnvVarConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._pim_port
        assert self._pim_host
        assert self._pim_socket_path
        return EnvVars(
            env_vars={
                "GLOW_PRODUCT_INSTANCE_SYSTEM": "PIM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST": self._pim_host,
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT": str(self._pim_port),
                "GLOW_PIM_SOCKET_PATH": self._pim_socket_path.as_posix(),
            },
            only_api=[
                "GLOW_PRODUCT_INSTANCE_SYSTEM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT",
            ],
        )


class WithCertificatesPIMEnvVarConfig(InstanceSystemEnvVarConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._pim_port
        assert self._pim_host
        assert self._certs_dir
        return EnvVars(
            env_vars={
                "GLOW_PRODUCT_INSTANCE_SYSTEM": "PIM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST": self._pim_host,
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT": str(self._pim_port),
                "ANSYS_GRPC_CERTIFICATES": self._certs_dir.as_posix(),
            },
            only_api=[
                "GLOW_PRODUCT_INSTANCE_SYSTEM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT",
                "ANSYS_GRPC_CERTIFICATES",
            ],
        )


class HostStringSystemEnvVarConfig(InstanceSystemEnvVarConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        if platform.system() == "Windows":
            assert self._pim_port
            return EnvVars(
                env_vars={
                    "GLOW_PRODUCT_INSTANCE_SYSTEM": "PIM",
                    "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST": "localhost",
                    "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT": str(self._pim_port),
                },
                only_api=[
                    "GLOW_PRODUCT_INSTANCE_SYSTEM",
                    "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST",
                    "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT",
                ],
            )
        else:
            assert self._pim_socket_path
            return EnvVars(
                env_vars={
                    "GLOW_PRODUCT_INSTANCE_SYSTEM": "PIM",
                    "GLOW_PIM_SOCKET_PATH": self._pim_socket_path.as_posix(),
                },
            )


class HpsParametricSystemEnvVarConfig(InstanceSystemEnvVarConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_PRODUCT_INSTANCE_SYSTEM": None,
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST": None,
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT": None,
                "GLOW_HPS_HOST": "127.0.0.1",
                "GLOW_HPS_PORT": "8443",
            },
            only_api=[
                "GLOW_PRODUCT_INSTANCE_SYSTEM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT",
            ],
        )


class HpsParametricSystemNoEnvVarConfig(InstanceSystemEnvVarConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_PRODUCT_INSTANCE_SYSTEM": None,
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST": None,
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT": None,
                "GLOW_HPS_HOST": None,
                "GLOW_HPS_PORT": None,
                "GLOW_HPS_USERNAME": None,
                "GLOW_HPS_PASSWORD": None,
            },
            only_api=[
                "GLOW_PRODUCT_INSTANCE_SYSTEM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT",
            ],
        )


class PimWithHpsParametricSystemEnvVarConfig(InstanceSystemEnvVarConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        env_vars = EnvVars(
            env_vars={
                "GLOW_PRODUCT_INSTANCE_SYSTEM": "PIM",
                "GLOW_HPS_HOST": "127.0.0.1",
                "GLOW_HPS_PORT": "8443",
            },
        )
        # Current testing infrastructure, using instance_system_type fixture, does not allow to be running both PIM and
        # HPS at the same time. Therefore, since the tests that use this config only check that HPS parametric study
        # works fine while instance system is configured to be PIM, we will use fake PIM ports/sockets.
        if platform.system() == "Windows":
            env_vars.env_vars.update(
                {
                    "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST": "127.0.0.1",
                    "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT": "5555",
                    "GLOW_PIM_SOCKET_PATH": None,
                },
            )
            env_vars.only_api = [
                "GLOW_PRODUCT_INSTANCE_SYSTEM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT",
                "GLOW_PIM_SOCKET_PATH",
            ]
        else:
            env_vars.env_vars.update(
                {
                    "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST": None,
                    "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT": None,
                    "GLOW_PIM_SOCKET_PATH": "/tmp/pim_socket.sock",
                },
            )
            env_vars.only_api = [
                "GLOW_PRODUCT_INSTANCE_SYSTEM",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST",
                "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT",
                "GLOW_PIM_SOCKET_PATH",
            ]
        return env_vars


class UnconfiguredSystemEnvVarConfig(InstanceSystemEnvVarConfig): ...


# ================================================== [DATABASE] ================================================== #


class DatabaseConfiguration(BaseGlowConfiguration):
    """Configure database. Optionally specifying location"""

    config_type = "db_configuration"

    def __init__(self, deployment_type: Deployment, db_location: Path | PostgresDsn | None = None) -> None:
        super().__init__(deployment_type)
        self._db_location = db_location


class DefaultDBConfig(DatabaseConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_DATABASE_TYPE": None,
                "GLOW_DATABASE_LOCATION": None,
            },
            only_api=["GLOW_DATABASE_TYPE", "GLOW_DATABASE_LOCATION"],
        )


class SQLiteConfig(DatabaseConfiguration):
    def __init__(self, deployment_type: Deployment, db_location: Path | None = None) -> None:
        super().__init__(deployment_type, db_location)

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_DATABASE_TYPE": "sqlite",
                "GLOW_DATABASE_LOCATION": str(self._db_location) if self._db_location else None,
            },
            only_api=["GLOW_DATABASE_TYPE", "GLOW_DATABASE_LOCATION"],
        )


class PostgreSQLConfig(DatabaseConfiguration):
    def __init__(self, deployment_type: Deployment, db_location: PostgresDsn | None = None) -> None:
        super().__init__(deployment_type, db_location)

    @property
    def env_vars_to_configure(self) -> EnvVars:
        if not self._db_location and self._deployment_type == Deployment.Desktop:
            raise RuntimeError("In desktop, if postgresql is used, location is mandatory to be specified.")
        return EnvVars(
            env_vars={
                "GLOW_DATABASE_TYPE": "postgresql",
                "GLOW_DATABASE_LOCATION": str(self._db_location)
                or "postgresql://glow:glow@my-solution-database:5432/postgres",
            },
            only_api=["GLOW_DATABASE_TYPE", "GLOW_DATABASE_LOCATION"],
        )


# ============================================ [PROJECT FILES DIRECTORY] ============================================ #


class ProjectFilesConfiguration(BaseGlowConfiguration):
    """Override default project files directory."""

    config_type = "project_files_configuration"

    def __init__(
        self,
        deployment_type: Deployment,
        project_files_dir: Path | None = None,
        container_project_files_dir: Path | None = None,
        is_product_system_different_platform: bool = False,
    ) -> None:
        super().__init__(deployment_type)
        self.project_files_dir = project_files_dir
        self._container_project_files_dir = container_project_files_dir
        self._is_product_system_different_platform = is_product_system_different_platform


class DefaultProjectFilesConfig(ProjectFilesConfiguration):
    """'Default' configuration set for testing purposes via conftest files. It is not truly default for Docker."""

    @property
    def env_vars_to_configure(self) -> EnvVars:
        if self._deployment_type == Deployment.Desktop:
            return EnvVars(
                env_vars={
                    "GLOW_PROJECT_FILES_DIRECTORY": None,
                },
                only_api=["GLOW_PROJECT_FILES_DIRECTORY"],
            )
        else:
            assert self.project_files_dir
            env_vars = EnvVars(
                env_vars={
                    "GLOW_PROJECT_FILES_DIRECTORY": "/projects",
                    "GLOW_UI_PROJECT_FILES_DIRECTORY": "/projects",
                },
                only_api=["GLOW_PROJECT_FILES_DIRECTORY"],
                only_ui=["GLOW_UI_PROJECT_FILES_DIRECTORY"],
            )
            if self._is_product_system_different_platform:
                env_vars.env_vars["GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY"] = (
                    self.project_files_dir.as_posix()
                )
                env_vars.only_api.append("GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY")
            return env_vars

    @property
    def volumes_to_mount(self) -> Volumes:
        assert self.project_files_dir
        return Volumes(common=[f"{self.project_files_dir.as_posix()}:/projects"])


class CustomProjectFilesConfig(ProjectFilesConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self.project_files_dir
        if self._deployment_type == Deployment.Desktop:
            return EnvVars(
                env_vars={
                    "GLOW_PROJECT_FILES_DIRECTORY": self.project_files_dir.as_posix(),
                },
                only_api=["GLOW_PROJECT_FILES_DIRECTORY"],
            )
        else:
            assert self._container_project_files_dir
            env_vars = EnvVars(
                env_vars={
                    "GLOW_PROJECT_FILES_DIRECTORY": self._container_project_files_dir.as_posix(),
                    "GLOW_UI_PROJECT_FILES_DIRECTORY": self._container_project_files_dir.as_posix(),
                },
                only_api=["GLOW_PROJECT_FILES_DIRECTORY"],
                only_ui=["GLOW_UI_PROJECT_FILES_DIRECTORY"],
            )
            if self._is_product_system_different_platform:
                env_vars.env_vars["GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY"] = (
                    self.project_files_dir.as_posix()
                )
                env_vars.only_api.append("GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY")
            return env_vars

    @property
    def volumes_to_mount(self) -> Volumes:
        assert self.project_files_dir
        assert self._container_project_files_dir
        return Volumes(common=[f"{self.project_files_dir.as_posix()}:{self._container_project_files_dir.as_posix()}"])


# ================================================ [DATA REPOSITORY] ================================================ #


class DataRepositoryConfiguration(BaseGlowConfiguration):
    """Configure Data Repository. Only for Desktop"""

    config_type = "data_repo_configuration"
    data_repo_type: str | None = None

    def __init__(
        self,
        deployment_type: Deployment,
        temp_upload_root: str | None = None,
        minerva_settings: dict[str, str] | None = None,
    ) -> None:
        super().__init__(deployment_type)
        self._temp_upload_root = temp_upload_root or ""
        self._minerva_settings = minerva_settings or {}


class DefaultDataRepoConfiguration(DataRepositoryConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_DATA_REPOSITORY_TYPE": None}, only_api=["GLOW_DATA_REPOSITORY_TYPE"])


class FileSystemDataRepoConfiguration(DataRepositoryConfiguration):
    data_repo_type = "FileSystem"

    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                "GLOW_DATA_REPOSITORY_TYPE": "FileSystem",
                "GLOW_DATA_REPOSITORY_UPLOAD_ROOT": self._temp_upload_root,
            },
            only_api=["GLOW_DATA_REPOSITORY_TYPE", "GLOW_DATA_REPOSITORY_UPLOAD_ROOT"],
        )

    def _docker_setup(self, compose_override_file: Path) -> None:
        raise ValueError("DataRepository not supported for MultiContainer deployment.")

    def _docker_teardown(self) -> None:
        raise ValueError("DataRepository not supported for MultiContainer deployment.")


class MinervaDataRepoConfiguration(DataRepositoryConfiguration):
    data_repo_type = "Minerva"

    @property
    def env_vars_to_configure(self) -> EnvVars:
        env_vars = EnvVars(
            env_vars={
                "GLOW_DATA_REPOSITORY_TYPE": "Minerva",
                "GLOW_DATA_REPOSITORY_UPLOAD_ROOT": self._temp_upload_root,
            },
            only_api=["GLOW_DATA_REPOSITORY_TYPE", "GLOW_DATA_REPOSITORY_UPLOAD_ROOT"],
        )
        env_vars.env_vars.update(self._minerva_settings)
        env_vars.only_api.extend(self._minerva_settings.keys())
        return env_vars

    def _docker_setup(self, compose_override_file: Path) -> None:
        raise ValueError("DataRepository not supported for MultiContainer deployment.")

    def _docker_teardown(self) -> None:
        raise ValueError("DataRepository not supported for MultiContainer deployment.")


# ================================================ [BDM GC] ================================================ #


class GarbageCollectionConfiguration(BaseGlowConfiguration):
    """Configure the API server to enable or disable BDM garbage collection."""

    config_type = "garbage_collection_configuration"


class DisableGarbageCollection(GarbageCollectionConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_BDM_GC_DISABLED": "True"}, only_api=["GLOW_BDM_GC_DISABLED"])


class EnableGarbageCollection(GarbageCollectionConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_BDM_GC_DISABLED": None}, only_api=["GLOW_BDM_GC_DISABLED"])


# ================================================ [SOLUTION CONFIG] ================================================ #


class SolutionConfigConfiguration(BaseGlowConfiguration):
    """Configure the API server to enable or disable overwrite of SolutionConfiguration."""

    config_type = "solution_config_configuration"


class EnableOverwriteSolutionConfig(SolutionConfigConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_OVERWRITE_SOLUTION_CONFIG": "True"}, only_api=["GLOW_OVERWRITE_SOLUTION_CONFIG"])


class DisableOverwriteSolutionConfig(SolutionConfigConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(env_vars={"GLOW_OVERWRITE_SOLUTION_CONFIG": None}, only_api=["GLOW_OVERWRITE_SOLUTION_CONFIG"])


# ========================================== [AUTH VALIDATION CONFIG] ================================================ #


class SolutionAuthConfiguration(BaseGlowConfiguration):
    config_type = "solution_auth_configuration"

    def __init__(
        self,
        deployment_type: Deployment,
        idp_server: str | None = None,
    ) -> None:
        super().__init__(deployment_type)
        self._idp_server = idp_server


class DefaultSolutionAuthConfiguration(SolutionAuthConfiguration): ...


class EnableAuthValidationConfiguration(SolutionAuthConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._idp_server
        return EnvVars(
            env_vars={
                "GLOW_AUTH_ISSUER_URL": self._idp_server,
                "GLOW_AUTH_DISABLED": "False",
                "GLOW_AUTH_CLIENT_ID": "rep-jms-web",
            },
        )


class DisableAuthValidationConfiguration(SolutionAuthConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._idp_server
        return EnvVars(
            env_vars={
                "GLOW_AUTH_ISSUER_URL": self._idp_server,
                "GLOW_AUTH_DISABLED": "True",
                "GLOW_AUTH_CLIENT_ID": "rep-jms-web",
            },
        )


class InvalidAuthValidationConfiguration(SolutionAuthConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={
                # Enabling auth without proper issuer url and client id will raise an error
                "GLOW_AUTH_DISABLED": "False",
            },
        )


# =========================================== [AUTOMATIC SCHEMA UPGRADE] ============================================ #


class AutomaticProjectMigrationConfig(BaseGlowConfiguration):
    config_type = "automatic_project_migration_configuration"


class DefaultAutomaticProjectMigrationConfig(AutomaticProjectMigrationConfig): ...


class EnableAutomaticProjectMigrationConfig(AutomaticProjectMigrationConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION": "True"},
            only_api=["GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION"],
        )


class DisableAutomaticProjectMigrationConfig(AutomaticProjectMigrationConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION": "False"},
            only_api=["GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION"],
        )


# ================================================ [HPS CLIENT TTL] ================================================== #


class HPSClientTTLConfiguration(BaseGlowConfiguration):
    config_type = "hps_client_cache_ttl_configuration"

    def __init__(self, deployment_type: Deployment, cache_ttl_seconds: float | None = None) -> None:
        super().__init__(deployment_type)
        self._cache_ttl_seconds = cache_ttl_seconds


class DefaultHPSClientTTLConfiguration(HPSClientTTLConfiguration): ...


class CustomHPSClientTTLConfiguration(HPSClientTTLConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._cache_ttl_seconds is not None
        return EnvVars(
            env_vars={"TEST_HPS_CLIENT_CACHE_TTL_SECONDS": str(self._cache_ttl_seconds)},
            only_api=["TEST_HPS_CLIENT_CACHE_TTL_SECONDS"],
        )


# =============================================== [gRPC certificates] ================================================ #


class GrpcCertificatesConfig(BaseGlowConfiguration):
    config_type = "grpc_certificates_configuration"

    def __init__(self, deployment_type: Deployment, certs_dir: Path | None = None) -> None:
        super().__init__(deployment_type)
        self._certs_dir = certs_dir


class WithGrpcCertificates(GrpcCertificatesConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._certs_dir
        certs_dir = self._certs_dir.as_posix() if self._deployment_type == Deployment.Desktop else "/certs"
        return EnvVars(
            env_vars={"ANSYS_GRPC_CERTIFICATES": certs_dir},
            only_api=["ANSYS_GRPC_CERTIFICATES"],
        )

    @property
    def volumes_to_mount(self) -> Volumes:
        assert self._certs_dir
        return Volumes(common=[f"{self._certs_dir.as_posix()}:/certs:ro"])


class NoGrpcCertificates(GrpcCertificatesConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        return EnvVars(
            env_vars={"ANSYS_GRPC_CERTIFICATES": None},
            only_api=["ANSYS_GRPC_CERTIFICATES"],
        )


# ================================================= [AEDT] ================================================= #


class AEDTConfiguration(BaseGlowConfiguration):
    """Configure the local AEDT installation."""

    config_type = "aedt_configuration"

    def __init__(self, deployment_type: Deployment, version: str = "") -> None:
        super().__init__(deployment_type)
        self._version = version


class NoAEDTConfiguration(AEDTConfiguration): ...


class AEDTVersionConfiguration(AEDTConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        if self._deployment_type == Deployment.Desktop:
            return EnvVars()
        else:
            aedt_local_dir = os.environ[f"ANSYSEM_ROOT{self._version}"]
            assert Path(aedt_local_dir).is_dir()
            return EnvVars(
                env_vars={
                    f"ANSYSEM_ROOT{self._version}": aedt_local_dir,
                },
                only_api=[f"ANSYSEM_ROOT{self._version}"],
            )

    @property
    def volumes_to_mount(self) -> Volumes:
        aedt_local_dir = os.environ[f"ANSYSEM_ROOT{self._version}"]
        return Volumes(common=[f"{aedt_local_dir}:{aedt_local_dir}"])


# ================================================== [GEOMETRY] ================================================= #


class GeometryConfiguration(BaseGlowConfiguration):
    """Configure the local Geometry installation."""

    config_type = "geometry_configuration"

    def __init__(self, deployment_type: Deployment, version: str = "") -> None:
        super().__init__(deployment_type)
        self._version = version


class NoGeometryConfiguration(GeometryConfiguration): ...


class GeometryVersionConfiguration(GeometryConfiguration):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        if self._deployment_type == Deployment.Desktop:
            return EnvVars()
        else:
            geometry_local_dir = os.environ.get(f"GEOMETRY_ROOT{self._version}", "")
            # Don't assert for geometry_local_dir existence. In hybrid deployments where the product is not running in
            # the same environment as pytest, this path is only reachable from the product environment.
            # In the case of 251 on Linux, it's not even supported. We expect the transaction to fail.
            return EnvVars(
                env_vars={
                    f"GEOMETRY_ROOT{self._version}": geometry_local_dir,
                },
                only_api=[f"GEOMETRY_ROOT{self._version}"],
            )


# =============================================== [Product host] ================================================ #


class ProductHostConfig(BaseGlowConfiguration):
    config_type = "product_host_configuration"

    def __init__(self, deployment_type: Deployment, product_host: str | None = None) -> None:
        super().__init__(deployment_type)
        self._product_host = product_host


class DefaultProductHost(ProductHostConfig): ...


class WithProductHost(ProductHostConfig):
    @property
    def env_vars_to_configure(self) -> EnvVars:
        assert self._product_host
        return EnvVars(env_vars={"GLOW_PRODUCT_HOST": self._product_host}, only_api=["GLOW_PRODUCT_HOST"])
