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

from abc import ABC, abstractmethod
from collections.abc import Generator
import json
import logging
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from threading import Thread
import time
from typing import IO, Any, Generic, TypeVar

import httpx2
import psutil
from pydantic import PostgresDsn

from ansys.saf.testing._common.network import get_random_free_port
from ansys.saf.testing._database.psql_container_manager import PostgresqlServerInfo
from ansys.saf.glow.client import Deployment  # pyright: ignore[reportMissingImports]
from ansys.saf.testing._solution.const import TestProductInstanceSystemType
from ansys.saf.testing._solution.end_to_end._typing import SolutionProtocol
from ansys.saf.testing._solution.end_to_end.glow_execution_configurations import (
    BaseGlowConfiguration,
    DebugConfiguration,
    DefaultLogLevel,
    DefaultProjectFilesConfig,
    EnvVarDebug,
    HpsUserPswdAuth,
    MethodExecutionDirConfiguration,
    ProjectFilesConfiguration,
    UIDebugConfiguration,
    WithGrpcCertificates,
)
from ansys.saf.testing._solution.end_to_end.log_manager import LogContainer

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=SolutionProtocol)
SERVER_MODES = {"api": "API", "ui": "UI"}
DEFAULT_CONFIGURATIONS = [
    DefaultLogLevel,  # check if attrs are accessed
    HpsUserPswdAuth,  # TODO: change to non
    DefaultProjectFilesConfig,  # TODO: rename
    # By default, set Grpc certificates. They are not used if not needed. Their existence in the GLOW server
    # doesn't determine the transport mode used neither by PIM or the gRPC products.
    WithGrpcCertificates,
]


def get_solution_root_dir(solution_dir: Path) -> Path:
    solution_root_dir = solution_dir.parent.parent.parent.parent
    assert (solution_root_dir / "src").is_dir()
    return solution_root_dir


def _get_env_value_from_file(env_file: Path, env_var_name: str) -> str | None:
    for line in env_file.read_text().splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if stripped_line.startswith(f"{env_var_name}="):
            return stripped_line.removeprefix(f"{env_var_name}=").strip('"').strip("'")

    return None


class GlowBaseInstance(ABC):
    @abstractmethod
    def __init__(self) -> None:
        self._healthy: bool = False

    @property
    def healthy(self) -> bool:
        self._health_check()
        return self._healthy

    @abstractmethod
    def _health_check(self) -> None:
        raise NotImplementedError()


class GlowBaseProcess(ABC, Generic[T]):
    _log_containers: list[LogContainer]

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def solution_name(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def solution_type(self) -> type[T]:
        raise NotImplementedError()

    @property
    @abstractmethod
    def solution_dir(self) -> Path:
        raise NotImplementedError()

    @property
    @abstractmethod
    def deployment_type(self) -> Deployment:
        raise NotImplementedError()

    @property
    @abstractmethod
    def applied_configurations(self) -> dict[str, BaseGlowConfiguration]:
        raise NotImplementedError()

    @abstractmethod
    def configure_default_execution(self, restart: bool = True) -> None:
        raise NotImplementedError()

    @abstractmethod
    def change_configuration(
        self,
        configuration: type[BaseGlowConfiguration],
        restart: bool = True,
        **kwargs: Any,
    ) -> BaseGlowConfiguration:
        raise NotImplementedError()

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def restart(self, wait_seconds: int = 5, log_tag: str = "", keep_ports: bool = True) -> None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def healthy(self) -> bool:
        raise NotImplementedError()

    @property
    @abstractmethod
    def base_api_url(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def solution_api_port(self) -> int:
        raise NotImplementedError()

    @property
    @abstractmethod
    def base_ui_url(self) -> str | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def solution_ui_port(self) -> int | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def project_files_directory(self) -> Path:
        raise NotImplementedError()

    @property
    @abstractmethod
    def transactions_directory(self) -> Path:
        raise NotImplementedError()

    @property
    @abstractmethod
    def debugpy_port(self) -> int | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def ui_debugpy_port(self) -> int | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def api_process(self) -> subprocess.Popen[bytes] | str | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def ui_process(self) -> subprocess.Popen[bytes] | str | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def api_output(self) -> list[str]:
        raise NotImplementedError()

    def get_api_output(self) -> list[str]:
        return self.api_output

    @property
    @abstractmethod
    def ui_output(self) -> list[str]:
        raise NotImplementedError()

    def get_ui_output(self) -> list[str]:
        return self.ui_output

    @property
    @abstractmethod
    def process_output(self) -> dict[str, list[str]]:
        raise NotImplementedError()

    @property
    @abstractmethod
    def console_output(self) -> dict[str, list[str]]:
        raise NotImplementedError()

    @property
    @abstractmethod
    def startup_errors(self) -> list[str]:
        raise NotImplementedError()

    @property
    @abstractmethod
    def debug_mode_override(self) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def clear_output(self) -> None:
        raise NotImplementedError()

    def text_in_output(
        self,
        content: str | list[str],
        service: str | None = None,
        console: bool = False,
        timeout: int = 10,
    ) -> bool:
        """Returns True if every string in content is found on the same console line."""

        api_output = self.process_output["api"] if not console else self.console_output["api"]
        ui_output = self.process_output["ui"] if not console else self.console_output["ui"]
        if not service:
            output = api_output + ui_output
        elif service == "api" and self.api_process:
            output = api_output
        elif service == "ui" and self.ui_process:
            output = ui_output
        else:
            return False

        sleep_interval = 0.1
        max_tries = int(timeout / sleep_interval)
        n = 0
        while n < max_tries:
            if self._find_content(content, output):
                return True
            else:
                time.sleep(sleep_interval)
                n += 1

        return False

    def _get_process_port(self, process_port: int | None = None) -> int:
        return process_port if process_port is not None else get_random_free_port()

    def attach_log_containers(self, containers: list[LogContainer]) -> None:
        self._log_containers = containers

    def _catch_up_logs_before_clear(self, log_tag: str) -> None:
        # Call at the beginning of methods that will erase the output so that every line is persisted.
        for container in self._log_containers:
            container.copy_and_return_lines(log_tag)
            container.reset_copy_count()

    @staticmethod
    def _find_content(content: str | list[str], output: list[str]) -> bool:
        """Returns True if at least one log entry contains EVERY str in the content list."""
        if isinstance(content, str):
            content = [content]
        return any(all(string in line for string in content) for line in output)


# =================================================== [DESKTOP] =================================================== #


class GlowDesktopInstance(GlowBaseInstance):
    """
    Usage notes:
    - If an error occurs during any stage of the process (start, stop, etc),
    append them to self.startup_errors and log self.process_output. This
    information is not available through other means.
    - Always utilize this class within a fixture that manages its teardown,
    which should include calling stop() and (optionally) keep_container_logs().
    """

    def __init__(
        self,
        solution_name: str,
        solution_dir: Path,
        process_port: int | None = None,
        solution_api_port: int | None = None,
        use_automatic_solution_locator: bool = False,
        env_file: Path | None = None,
        obfuscated_glow_pythonpath: str | None = None,
        args: list[str] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.project_display_name: str | None = None
        self.solution_api_port = solution_api_port
        self.solution_name = solution_name
        self.solution_dir = solution_dir
        self._use_automatic_solution_locator = use_automatic_solution_locator
        self.server_mode = ""
        self._define_port(process_port)
        self.env_file = env_file
        self._args = args
        self.process: subprocess.Popen[bytes] | None = None
        self._output: list[str] = []
        self.debugpy_port: int | None = None
        self._obfuscated_glow_pythonpath: str | None = obfuscated_glow_pythonpath
        self._cwd = cwd or Path.cwd()
        self._env = env or os.environ.copy()

        # We keep track of startup error for debugging purposes. We only raise them after the attempt has been logged.
        self.startup_errors: list[str] = []

    @property
    def output(self) -> list[str]:
        log_file: Path | None = None
        for line in self._output:
            if " logging to " in line:
                log_file = Path(line.split(" logging to ")[1].strip())
                break
        if log_file and log_file.is_file():
            return log_file.read_text().splitlines()
        else:
            return self._output

    @property
    def console_output(self) -> list[str]:
        # Needed because output may return the content of the log file, instead of the process' output.
        # This is not desired for example when checking that warnings appear in the main console output.
        return self._output

    @property
    def otlp_enabled(self) -> bool:
        # adding resource prefix to check that this line is instrumentalized.
        # Otherwise, we could see it due to the default logging level being affected by pytest
        # (e.g., INFO instead of WARNING), but it would not be shown to a user executing GLOW in a real environment.
        expected_log_line = (
            f"resource.service.name=GLOW {self.server_mode}]- "
            f"Telemetry enabled, using OTLP logging configuration for GLOW {self.server_mode}"
        )
        return expected_log_line in "\n".join(self.output)

    def read_process_output(self, out: IO[bytes]):
        for line in iter(out.readline, b""):
            self._output.append(line.decode("utf8"))

    def _extend_env(self) -> None:
        if self._obfuscated_glow_pythonpath:
            self._env["PYTHONPATH"] = self._obfuscated_glow_pythonpath

    def _extract_command(self) -> list[str]:
        command = [
            sys.executable,
            "-m",
            "ansys.saf.glow.cli",
            self.server_mode.lower(),
        ]

        if self.env_file:
            command.extend(["--env-file", str(self.env_file)])
        for ext in [".py", ".pyc"]:
            if (
                not self._use_automatic_solution_locator
                and self.solution_dir
                and (self.solution_dir / "main.py").with_suffix(ext).is_file()
            ):
                command.extend(["--solution", str((self.solution_dir / "main.py").with_suffix(ext))])
        if self.process_port:
            command.extend(["--port", str(self.process_port)])
        if self.server_mode == SERVER_MODES["ui"]:
            command.extend(["--api-server-url", f"http://127.0.0.1:{self.solution_api_port}"])
            # Set a dummy portal url, as some UI tests require
            # "Back to projects" button to appear.
            command.extend(["--portal-ui-url", "http://127.0.0.1:12345"])
        if self._args:
            command.extend(self._args)
        return command

    def start(self) -> None:
        self.startup_errors = []
        command = self._extract_command()
        self._extend_env()

        self._output.clear()
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=self._env,
            cwd=self._cwd,
        )
        t = Thread(target=self.read_process_output, args=(self.process.stdout,))
        # thread dies with the process
        t.daemon = True
        t.start()

        # Wait for GLOW process to start up, so logs can be parsed from its process_output
        # Only doing health check is not enough since in case of trying to use an existing port by another solution,
        # the health check would return OK despite the solution failing to launch.
        self._wait_for_startup_complete()

        self.process_port = self._get_port_from_process_output(f"Running GLOW {self.server_mode} server on")
        self.debugpy_port = self._get_port_from_process_output(
            f"#### {self.server_mode} server listening for debug on port",
            regex_pattern=r"port: \d+\b",
            port_separator=" ",
            bypass_error=True,  # TODO: know when we expect to parse this port
        )

        self._health_check()

        if self.startup_errors:
            self._healthy = False

    def _health_check(self) -> None:
        tries = 0
        max_tries = 250
        is_not_healthy = True
        while tries < max_tries and is_not_healthy:
            try:
                response = httpx2.get(
                    f"http://127.0.0.1:{self.process_port}/health",
                    headers={"accept": "application/json"},
                )
                if response.status_code == 200:
                    is_not_healthy = False
            except Exception:
                time.sleep(0.1)
                tries += 1
        if is_not_healthy:
            logger.error(self.output)
            self.startup_errors.append(
                f"GLOW {self.server_mode} startup was not successful. {self.server_mode} server is NOT healthy.",
            )
            self._healthy = False
        else:
            self._healthy = True

    def stop(self) -> None:
        """Stop the service"""
        if self.process is None:
            return

        parent: psutil.Process | None = None
        try:
            parent = psutil.Process(self.process.pid)
        except psutil.NoSuchProcess:
            parent = None

        if parent is not None:
            for child in parent.children(recursive=True):
                self._terminate(child)
            self._terminate(parent, timeout=60)
            self.process = None

    def _terminate(self, process: psutil.Process, timeout: int = 0) -> None:
        try:
            process.terminate()
            if timeout > 0:
                process.wait(timeout)
        except psutil.NoSuchProcess:
            pass

    def restart(self) -> None:
        self.stop()
        self.start()

    def _wait_for_startup_complete(self) -> None:
        startup_sentence = f"Running GLOW {self.server_mode} server on"
        binding_error = (
            "only one usage of each socket address" if platform.system() == "Windows" else "address already in use"
        )
        startup_complete = False
        n = 0
        max_tries = 400
        while not startup_complete and n < max_tries:
            for log_line in self.output:
                if startup_sentence in log_line:
                    startup_complete = True
                if binding_error in log_line.lower():
                    # if the error comes from debugpy, it has initial uppercase. otherwise, it's all lowercase.
                    logger.error(self.output)
                    self.startup_errors.append(
                        f"GLOW {self.server_mode} startup was not successful. Port already in use.",
                    )
                    return
            time.sleep(0.25)
            n += 1
        if not startup_complete:
            logger.error(self.output)
            self.startup_errors.append(
                f"GLOW {self.server_mode} startup was not successful. "
                "Could not find statement about process completed.",
            )
        return

    def _define_port(self, process_port: int | None = None) -> None:
        # Return next free port always as GLOW
        # doesn't look for a free port in case
        # the default one is not free
        self.process_port = process_port if process_port is not None else get_random_free_port()

    def _get_port_from_process_output(
        self,
        line_filter: str,
        regex_pattern: str = r"http://127\.0\.0\.1:\d+\b",
        port_separator: str = ":",
        bypass_error: bool = False,
    ) -> int | None:
        # we are adding the prefixes to make sure that the log line is instrumentalized.
        # Otherwise, we could see it due to the default logging level being affected by pytest
        # (e.g., INFO instead of WARNING), but it would not be shown to a user executing GLOW in a real environment.
        if not self.otlp_enabled:
            line_filter = f"resource.service.name=GLOW {self.server_mode}]- {line_filter}"
        else:
            line_filter = f'"body": "{line_filter}'

        for line in self.output:
            if line_filter in line:
                url_match = re.search(regex_pattern, line)
                if url_match:
                    url_match = url_match.group()
                    port = int(url_match.split(port_separator)[-1].rstrip("/"))
                    return port
        if not bypass_error:
            logger.error(self.output)
            self.startup_errors.append(f"GLOW {self.server_mode} startup was not successful. Could not find port.")
        return None

    def _convert_path_to_module(self, filepath: str) -> str:
        """Take an absolute path, extract the solution package path and return the solution main module."""
        ansys_solution_folder = "/ansys/solutions/"
        try:
            ansys_index = filepath.rindex(ansys_solution_folder)
        except ValueError:
            raise Exception(f"The directories {ansys_solution_folder} could not be found in {filepath}.") from None
        # now translate /ansys/solutions/x/main.py to ansys.solutions.x.main
        main_module = filepath[ansys_index + 1 :].replace("/", ".")[:-3]
        return main_module

    def clear_output(self) -> None:
        self._output.clear()


class GlowApiInstance(GlowDesktopInstance):
    def __init__(
        self,
        solution_name: str,
        solution_dir: Path,
        env_file: Path | None = None,
        process_port: int | None = None,
        use_automatic_solution_locator: bool = False,
        definition_file: Path | None = None,
        args: list[str] | None = None,
        obfuscated_glow_pythonpath: str | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        super().__init__(
            solution_name=solution_name,
            solution_dir=solution_dir,
            env_file=env_file,
            process_port=process_port,
            use_automatic_solution_locator=use_automatic_solution_locator,
            obfuscated_glow_pythonpath=obfuscated_glow_pythonpath,
            args=args,
            cwd=cwd,
            env=env,
        )
        self.server_mode = SERVER_MODES["api"]
        self.definition_file = definition_file

    def _extract_command(self) -> list[str]:
        command = super()._extract_command()
        if not self._use_automatic_solution_locator and self.definition_file:
            command.extend(["--definition", str(self.definition_file)])
        return command


class GlowUiInstance(GlowDesktopInstance):
    def __init__(
        self,
        solution_name: str,
        solution_api_port: int,
        solution_dir: Path,
        process_port: int | None = None,
        env_file: Path | None = None,
        use_automatic_solution_locator: bool = False,
        args: list[str] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        super().__init__(
            solution_name=solution_name,
            solution_dir=solution_dir,
            process_port=process_port,
            solution_api_port=solution_api_port,
            env_file=env_file,
            use_automatic_solution_locator=use_automatic_solution_locator,
            args=args,
            cwd=cwd,
            env=env,
        )
        self.server_mode = SERVER_MODES["ui"]


class GlowDesktopProcess(GlowBaseProcess[T]):
    def __init__(
        self,
        solution_name: str,
        solution_type: type[T],
        solution_dir: Path,
        definition_file: Path | None = None,
        ui_enabled: bool = False,
        solution_api_port: int | None = None,
        solution_ui_port: int | None = None,
        use_automatic_solution_locator: bool = False,
        env_file: Path | None = None,
        debug_mode_override: bool = False,
        obfuscated_glow_pythonpath: str | None = None,
        solution_api_args: list[str] | None = None,
        solution_ui_args: list[str] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        certificates_directory: Path | None = None,
        shutdown_api_server_first: bool | None = None,
    ) -> None:
        self._solution_name = solution_name
        self._solution_dir = solution_dir
        self.definition_file = definition_file
        self._solution_type = solution_type
        self.ui_enabled = ui_enabled
        self.use_automatic_solution_locator = use_automatic_solution_locator
        self.env_file = env_file
        self.project_display_name: str | None = None
        self.glow_instances: list[GlowDesktopInstance] = []
        self._debug_mode_override: bool = debug_mode_override
        self._solution_api_args = solution_api_args
        self._solution_ui_args = solution_ui_args
        self._obfuscated_glow_pythonpath = obfuscated_glow_pythonpath
        self._cwd = cwd or Path.cwd()
        self._certificates_directory = certificates_directory
        self._shutdown_api_server_first = shutdown_api_server_first

        # Configure glow execution
        self._env = env or os.environ.copy()
        self._applied_configurations: dict[str, BaseGlowConfiguration] = {}
        self.configure_default_execution(restart=False)

        # Initialize instances
        self.glow_api_process: GlowApiInstance | GlowProductionApiInstance | None = None
        self.glow_ui_process: GlowUiInstance | GlowProductionUiInstance | None = None

        self._initialize_instances(solution_api_port, solution_ui_port)

    @property
    def deployment_type(self) -> Deployment:
        return Deployment.Desktop

    @property
    def solution_name(self) -> str:
        return self._solution_name

    @property
    def solution_dir(self) -> Path:
        return self._solution_dir

    @property
    def solution_type(self) -> type[T]:
        return self._solution_type

    @property
    def healthy(self) -> bool:
        healthy = False
        if self.glow_api_process:
            healthy = self.glow_api_process.healthy
            if self.glow_ui_process:
                healthy = healthy and self.glow_ui_process.healthy
        return healthy

    @property
    def startup_errors(self) -> list[str]:
        startup_errors: list[str] = []
        if self.glow_api_process:
            startup_errors.extend(self.glow_api_process.startup_errors)
        if self.glow_ui_process:
            startup_errors.extend(self.glow_ui_process.startup_errors)
        return startup_errors

    @property
    def process_output(self) -> dict[str, list[str]]:
        return {"api": self.api_output, "ui": self.ui_output}

    @property
    def console_output(self) -> dict[str, list[str]]:
        return {
            "api": self.glow_api_process.console_output if self.glow_api_process else [],
            "ui": self.glow_ui_process.console_output if self.glow_ui_process else [],
        }

    @property
    def api_output(self) -> list[str]:
        return self.glow_api_process.output if self.glow_api_process else []

    @property
    def ui_output(self) -> list[str]:
        return self.glow_ui_process.output if self.glow_ui_process else []

    @property
    def project_files_directory(self) -> Path:
        if env_glow_project_files_dir := self._env.get("GLOW_PROJECT_FILES_DIRECTORY"):
            return Path(env_glow_project_files_dir)
        elif self.env_file:
            if env_glow_project_files_dir := _get_env_value_from_file(self.env_file, "GLOW_PROJECT_FILES_DIRECTORY"):
                return Path(env_glow_project_files_dir)
        elif (self._cwd / ".env").is_file():
            env_file = self._cwd / ".env"
            if env_glow_project_files_dir := _get_env_value_from_file(env_file, "GLOW_PROJECT_FILES_DIRECTORY"):
                return Path(env_glow_project_files_dir)
        return Path(os.environ["APPDATA"]) / "ansys" / "glow" / self.solution_name / "project_files"

    @property
    def solution_api_port(self) -> int:
        if not self.glow_api_process or not self.glow_api_process.process_port:
            raise RuntimeError("Solution API not running.")
        return self.glow_api_process.process_port

    @property
    def solution_ui_port(self) -> int | None:
        if self.glow_ui_process:
            return self.glow_ui_process.process_port

    @property
    def debugpy_port(self) -> int | None:
        if self.glow_api_process:
            return self.glow_api_process.debugpy_port

    @property
    def ui_debugpy_port(self) -> int | None:
        if self.glow_ui_process:
            return self.glow_ui_process.debugpy_port

    @property
    def api_process(self) -> subprocess.Popen[bytes] | None:
        if self.glow_api_process:
            return self.glow_api_process.process

    @property
    def ui_process(self) -> subprocess.Popen[bytes] | None:
        if self.glow_ui_process:
            return self.glow_ui_process.process

    @property
    def base_api_url(self) -> str:
        return f"http://127.0.0.1:{self.solution_api_port}"

    @property
    def base_ui_url(self) -> str:
        return f"http://127.0.0.1:{self.solution_ui_port}"

    @property
    def transactions_directory(self) -> Path:
        config: MethodExecutionDirConfiguration | None = self._applied_configurations.get(
            "method_dir_configuration",
        )  # pyright: ignore[reportAssignmentType]
        if not config or not config.method_custom_dir:
            raise ValueError("Method execution directory is not configured. Defaults to tmp_dir.")
        return config.method_custom_dir

    @property
    def debug_mode_override(self) -> bool:
        return self._debug_mode_override

    @property
    def applied_configurations(self) -> dict[str, BaseGlowConfiguration]:
        return self._applied_configurations

    def _initialize_ui(self, ui_port: int | None) -> None:
        self.glow_ui_process = GlowUiInstance(
            solution_name=self.solution_name,
            solution_dir=self.solution_dir,
            env_file=self.env_file,
            process_port=ui_port,
            solution_api_port=self.glow_api_process.process_port,  # type: ignore
            args=self._solution_ui_args,
            cwd=self._cwd,
            env=self._env,
        )
        self.glow_instances.append(self.glow_ui_process)

    def _initialize_instances(self, api_port: int | None, ui_port: int | None) -> None:
        self.glow_api_process = GlowApiInstance(
            solution_name=self.solution_name,
            solution_dir=self.solution_dir,
            env_file=self.env_file,
            process_port=api_port,
            use_automatic_solution_locator=self.use_automatic_solution_locator,
            definition_file=self.definition_file,
            obfuscated_glow_pythonpath=self._obfuscated_glow_pythonpath,
            args=self._solution_api_args,
            cwd=self._cwd,
            env=self._env,
        )
        self.glow_instances.append(self.glow_api_process)

        if self.ui_enabled:
            self._initialize_ui(ui_port)

    def configure_default_execution(self, restart: bool = True) -> None:
        for config in self._applied_configurations.values():
            config.teardown(self._env)
        self._applied_configurations.clear()

        configs_to_apply = DEFAULT_CONFIGURATIONS.copy()
        if self.debug_mode_override:
            configs_to_apply.append(EnvVarDebug)  # pyright: ignore[reportArgumentType]
        for config in configs_to_apply:
            kwargs: Any = {}
            if config == WithGrpcCertificates:
                kwargs["certs_dir"] = self._certificates_directory
            self._applied_configurations[config.config_type] = config(self.deployment_type, **kwargs)
            self._applied_configurations[config.config_type].setup(self._env)

        if restart:
            self.restart()

    def change_configuration(
        self,
        configuration: type[BaseGlowConfiguration],
        restart: bool = True,
        **kwargs: Any,
    ) -> BaseGlowConfiguration:
        if configuration.config_type in self._applied_configurations:
            self._applied_configurations[configuration.config_type].teardown(self._env)
        self._applied_configurations[configuration.config_type] = configuration(self.deployment_type, **kwargs)
        self._applied_configurations[configuration.config_type].setup(self._env)
        if restart:
            self.restart()
        return self._applied_configurations[configuration.config_type]

    def set_cwd(self, cwd: Path) -> None:
        self._cwd = cwd

    def start(self) -> None:
        for glow_process in self.glow_instances:
            glow_process.start()

    def _stop_in_order(self, first: GlowDesktopInstance, second: GlowDesktopInstance) -> None:
        first.stop()
        second.stop()

    def stop(self) -> None:
        if self._shutdown_api_server_first is None or self.glow_ui_process is None or self.glow_api_process is None:
            for glow_process in self.glow_instances:
                glow_process.stop()
        else:
            if self._shutdown_api_server_first:
                self._stop_in_order(self.glow_api_process, self.glow_ui_process)
            else:
                self._stop_in_order(self.glow_ui_process, self.glow_api_process)

    def restart(self, wait_seconds: int = 5, log_tag: str = "session restart", keep_ports: bool = True) -> None:
        self.stop()
        time.sleep(wait_seconds)

        self._catch_up_logs_before_clear(log_tag)

        self.glow_instances.clear()

        # By default, we try to keep the same ports. Otherwise, when we restart GLOW within a test, we wouldn't be able
        # to keep using the same function project, which has a client that tries to work with the previous ports.
        self._initialize_instances(
            self.solution_api_port if keep_ports else None,
            self.solution_ui_port if keep_ports else None,
        )
        for glow_instance in self.glow_instances:
            glow_instance.start()

    def clear_output(self) -> None:
        # Useful if we want to make sure that a test has caused a specific output
        self._catch_up_logs_before_clear("Clearing output.")
        if self.glow_api_process:
            self.glow_api_process.clear_output()
        if self.glow_ui_process:
            self.glow_ui_process.clear_output()


class GlowProductionApiInstance(GlowApiInstance):
    def __init__(
        self,
        solution_name: str,
        solution_dir: Path,
        definition_file: Path,
        process_port: int | None = None,
        env_file: Path | None = None,
        use_automatic_solution_locator: bool = False,
        use_root_path: bool = False,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        super().__init__(
            solution_name=solution_name,
            solution_dir=solution_dir,
            env_file=env_file,
            process_port=process_port,
            use_automatic_solution_locator=use_automatic_solution_locator,
            definition_file=definition_file,
            cwd=cwd,
        )
        self._use_root_path = use_root_path

    def _extract_command(self):
        command = ["uvicorn", "ansys.saf.glow.api:app"]
        command.extend(["--port", str(self.process_port)])
        if self._use_root_path:
            command.extend(["--root-path", "/api"])
        return command

    def start(self) -> None:
        if not self.env_file:
            if not self._use_automatic_solution_locator and self.definition_file:
                self._env["GLOW_SOLUTION_DEFINITION"] = self._convert_path_to_module(self.definition_file.as_posix())
            self._env["GLOW_API_PORT"] = str(self.process_port)
        super().start()


class GlowProductionUiInstance(GlowUiInstance):
    def __init__(
        self,
        solution_name: str,
        solution_api_port: int,
        solution_dir: Path,
        definition_file: Path,
        ui_app_file: Path | None,
        process_port: int | None = None,
        env_file: Path | None = None,
        use_automatic_solution_locator: bool = False,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        super().__init__(
            solution_name=solution_name,
            solution_dir=solution_dir,
            process_port=process_port,
            solution_api_port=solution_api_port,
            use_automatic_solution_locator=use_automatic_solution_locator,
            env_file=env_file,
            cwd=cwd,
        )
        self._definition_file = definition_file
        self._ui_app_file = ui_app_file

    def _extract_command(self):
        command = ["waitress-serve"]
        if self.process_port:
            command.extend(["--port", str(self.process_port)])
        command.extend(["ansys.saf.glow.ui:app"])
        return command

    def start(self) -> None:
        if not self.env_file:
            if not self._use_automatic_solution_locator and self._definition_file and self._ui_app_file:
                self._env["GLOW_SOLUTION_DEFINITION"] = self._convert_path_to_module(self._definition_file.as_posix())
                self._env["GLOW_UI_MODULE"] = self._convert_path_to_module(self._ui_app_file.as_posix())
            self._env["GLOW_API_URL"] = f"http://127.0.0.1:{self.solution_api_port}"
            self._env["GLOW_UI_PORT"] = str(self.process_port)
        super().start()


class GlowProductionProcess(GlowDesktopProcess[T]):
    def __init__(
        self,
        solution_name: str,
        solution_dir: Path,
        solution_type: type[T],
        definition_file: Path,
        ui_app_file: Path | None,
        ui_enabled: bool = False,
        solution_api_port: int | None = None,
        solution_ui_port: int | None = None,
        env_file: Path | None = None,
        use_automatic_solution_locator: bool = False,
        use_root_path: bool = False,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        certificates_directory: Path | None = None,
    ) -> None:
        self._use_root_path = use_root_path
        self._ui_app_file = ui_app_file
        super().__init__(
            solution_name=solution_name,
            solution_dir=solution_dir,
            solution_type=solution_type,
            definition_file=definition_file,
            ui_enabled=ui_enabled,
            solution_api_port=solution_api_port,
            solution_ui_port=solution_ui_port,
            env_file=env_file,
            use_automatic_solution_locator=use_automatic_solution_locator,
            cwd=cwd,
            env=env,
            certificates_directory=certificates_directory,
        )

    def _initialize_ui(self, ui_port: int | None) -> None:
        self.glow_ui_process = GlowProductionUiInstance(
            solution_name=self.solution_name,
            solution_api_port=self.glow_api_process.process_port,  # type: ignore
            solution_dir=self.solution_dir,
            definition_file=self.definition_file,  # pyright: ignore[reportArgumentType]
            ui_app_file=self._ui_app_file,
            process_port=ui_port,
            env_file=self.env_file,
            use_automatic_solution_locator=self.use_automatic_solution_locator,
            cwd=self._cwd,
            env=self._env,
        )
        self.glow_instances.append(self.glow_ui_process)

    def _initialize_instances(self, api_port: int | None, ui_port: int | None) -> None:
        self.glow_api_process = GlowProductionApiInstance(
            solution_name=self.solution_name,
            solution_dir=self.solution_dir,
            definition_file=self.definition_file,  # pyright: ignore[reportArgumentType]
            process_port=api_port,
            env_file=self.env_file,
            use_automatic_solution_locator=self.use_automatic_solution_locator,
            use_root_path=self._use_root_path,
            cwd=self._cwd,
            env=self._env,
        )
        self.glow_instances.append(self.glow_api_process)

        if self.ui_enabled:
            self._initialize_ui(ui_port)


# =================================================== [DOCKER] =================================================== #
# We may want to abstract away a GLOW process handler that sets the basic information for any deployment.


class GlowDockerInstance(GlowBaseInstance):
    def __init__(self, host_port: int, service: str, docker_compose_file: Path) -> None:
        self._host_port = host_port
        self._container_id: str = ""
        self._service = service
        self._docker_compose_file: Path = docker_compose_file
        super().__init__()
        self._output: list[str] = []

    @property
    def base_service_url(self) -> str:
        return f"http://127.0.0.1:{self._host_port}"

    @property
    def process(self) -> str:
        return self._container_id

    def define_container_id(self) -> None:
        cmd = ["docker", "compose", "-f", self._docker_compose_file.as_posix(), "ps", "--format", "json"]
        try:
            output = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except subprocess.CalledProcessError as err:
            logger.exception(err.output.splitlines())
            raise

        containers_data = output.splitlines()
        for container_data in containers_data:
            # When invoked from Windows, p.stdout starts with '\n',
            # which when split leads to an empty value
            if container_data and container_data != " ":
                try:
                    container_data_json: dict[str, Any] | list[dict[str, Any]] = json.loads(container_data)
                except Exception:
                    print(f"Failed to parse as JSON: {container_data}")
                    continue
                if isinstance(container_data_json, dict):
                    # in some cases, all containers are in a single json struct
                    # and in others, each container is an independent json struct.
                    # unify as a list in all cases.
                    container_data_list: list[dict[str, Any]] = [container_data_json]
                else:
                    container_data_list = container_data_json
                for service_data in container_data_list:
                    if self._service in service_data["Service"]:
                        self._container_id = service_data["ID"]
                        self._thread_output()
                        return
        if not self._container_id:
            raise Exception(f"Didn't find container ID in output: {output}")

    def read_process_output(self, stream: Generator[bytes, None, None]):
        for line in stream:
            self._output.append(line.decode("utf8"))

    def _thread_output(self):
        # conditional import to keep docker as optional and be able to use this desktop-only GlowBaseProcess without it.
        import docker

        with docker.APIClient() as client:
            logs_generator = client.logs(self._container_id, stream=True)
            t = Thread(target=self.read_process_output, args=(logs_generator,), daemon=True)
            t.start()

    @property
    def output(self) -> list[str]:
        return self._output

    @property
    def console_output(self) -> list[str]:
        return self._output

    def _health_check(self) -> None:
        tries = 0
        max_tries = 100

        while tries < max_tries and not self._healthy:
            try:
                response = httpx2.get(f"{self.base_service_url}/health", headers={"accept": "application/json"})
                if response.status_code == 200:
                    self._healthy = True
            except Exception:
                time.sleep(0.1)
                tries += 1

    @property
    def transactions_data_volume(self) -> Path:
        # conditional import to keep docker as optional and be able to use this desktop-only GlowBaseProcess without it.
        import docker

        with docker.APIClient() as client:
            container_data: Any = client.inspect_container(  # type: ignore
                self._container_id,
            )
            for mount in container_data["Mounts"]:  # pyright: ignore[reportUnknownVariableType]
                if mount["Destination"] == "/transactions":
                    return Path(mount["Source"])  # pyright: ignore[reportUnknownArgumentType]
            raise Exception(f"Didn't find transactions volume for container: {container_data}")

    def clear_output(self) -> None:
        self._output.clear()


class GlowDockerProcess(GlowBaseProcess[T]):
    def __init__(
        self,
        docker_compose_file: Path,
        solution_type: type[T],
        ui_enabled: bool = False,
        base_override_file: Path | None = None,
        api_host_port: int | None = None,
        ui_host_port: int | None = None,
        transactions_tmp_dir: Path | None = None,
        projects_tmp_dir: Path | None = None,
        debug_mode_override: bool = False,
        product_system: TestProductInstanceSystemType | None = None,
        certificates_directory: Path | None = None,
    ) -> None:
        self.api_port = self._define_port(api_host_port)
        self.ui_port = self._define_port(ui_host_port)

        self._solution_dir = docker_compose_file.parent
        self._solution_type = solution_type

        self.docker_compose_file = docker_compose_file

        self._transactions_tmp_dir = transactions_tmp_dir
        self._projects_tmp_dir = projects_tmp_dir

        self._ui_enabled = ui_enabled
        self._debug_mode_override = debug_mode_override
        self._product_system = product_system
        self._certificates_directory = certificates_directory

        # Configure glow execution
        self._applied_configurations: dict[str, BaseGlowConfiguration] = {}
        self.configure_default_execution(restart=False)

        if base_override_file:
            self._base_override_file = base_override_file

        self._containers = {
            "api": GlowDockerInstance(self.api_port, "api", self.docker_compose_file),
        }

        if self._ui_enabled:
            self._containers["ui"] = GlowDockerInstance(self.ui_port, "ui", self.docker_compose_file)

    @property
    def deployment_type(self) -> Deployment:
        return Deployment.MultiContainer

    @property
    def is_product_system_configured(self) -> bool:
        return self._product_system is not None

    @property
    def solution_name(self) -> str:
        return "EndToEndSolution"

    @property
    def solution_dir(self) -> Path:
        return self._solution_dir

    @property
    def solution_type(self) -> type[T]:
        return self._solution_type

    @property
    def healthy(self) -> bool:
        health = True
        for container in self._containers.values():
            health &= container.healthy
        return health

    @property
    def debugpy_port(self) -> int | None:
        debug_config: DebugConfiguration | None = self._applied_configurations.get(
            "debug_configuration",
        )  # pyright: ignore[reportAssignmentType]
        return debug_config.debug_port if debug_config else None

    @property
    def ui_debugpy_port(self) -> int | None:
        ui_debug_config: UIDebugConfiguration | None = self._applied_configurations.get(
            "ui_debug_configuration",
        )  # pyright: ignore[reportAssignmentType]
        return ui_debug_config.debug_port if ui_debug_config else None

    @property
    def base_api_url(self) -> str:
        return self._containers["api"].base_service_url

    @property
    def solution_api_port(self) -> int:
        return self.api_port

    @property
    def base_ui_url(self) -> str | None:
        return self._containers["ui"].base_service_url if self._ui_enabled else None

    @property
    def solution_ui_port(self) -> int | None:
        return self.ui_port if self._ui_enabled else None

    @property
    def api_process(self) -> str:
        return self._containers["api"].process

    @property
    def ui_process(self) -> str | None:
        return self._containers["ui"].process if self._ui_enabled else None

    @property
    def api_output(self) -> list[str]:
        return self._containers["api"].output

    @property
    def ui_output(self) -> list[str]:
        return self._containers["ui"].output if self._ui_enabled else []

    @property
    def process_output(self) -> dict[str, list[str]]:
        return {"api": self.api_output, "ui": self.ui_output}

    @property
    def console_output(self) -> dict[str, list[str]]:
        return {"api": self._containers["api"].console_output, "ui": self._containers["ui"].console_output}

    @property
    def project_files_directory(self) -> Path:
        config: ProjectFilesConfiguration | None = self._applied_configurations.get(
            "project_files_configuration",
        )  # pyright: ignore[reportAssignmentType]
        if not config or not config.project_files_dir:
            raise ValueError("Project files directory is not configured.")
        return config.project_files_dir

    @property
    def transactions_directory(self) -> Path:
        if self._transactions_tmp_dir:
            return self._transactions_tmp_dir
        else:
            return self._containers["api"].transactions_data_volume

    @property
    def base_override_file(self) -> Path | None:
        return self._base_override_file

    @property
    def debug_mode_override(self) -> bool:
        return self._debug_mode_override

    @property
    def applied_configurations(self) -> dict[str, BaseGlowConfiguration]:
        return self._applied_configurations

    def _define_port(self, process_port: int | None = None) -> int:
        return process_port if process_port is not None else get_random_free_port()

    def _extend_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["GLOW_DOCKER_API_PORT"] = str(self.api_port)
        env["GLOW_DOCKER_UI_PORT"] = str(self.ui_port)

        # WSLENV is the environment variable that allows sharing environment variables
        # between Windows and WSL since build 17063
        if platform.system() == "Windows":
            env["WSLENV"] = "%WSLENV%:GLOW_DOCKER_API_PORT:GLOW_DOCKER_UI_PORT"
        return env

    def _extract_command(self) -> list[str]:
        command = [
            "docker",
            "compose",
            "-f",
            self.docker_compose_file.as_posix(),
        ]

        if self.base_override_file:
            command.extend(["-f", self.base_override_file.as_posix()])

        for config_override_file in self.solution_dir.iterdir():
            if config_override_file.name.startswith("glow_config_") and config_override_file.suffix == ".yaml":
                command.extend(["-f", config_override_file.as_posix()])

        return command

    def _extract_up_command(self) -> list[str]:
        command = self._extract_command()
        command.extend(["up", "--detach", "--wait", "my-solution-database", "my-solution-api"])
        if self._ui_enabled:
            command.extend(["my-solution-ui"])
        return command

    def _extract_logs_command(self) -> list[str]:
        command = self._extract_command()
        command.extend(["logs"])
        return command

    def configure_default_execution(self, restart: bool = True) -> None:
        for config in self._applied_configurations.values():
            config.teardown()
        self._applied_configurations.clear()

        configs_to_apply = DEFAULT_CONFIGURATIONS.copy()
        if self.debug_mode_override:
            configs_to_apply.append(EnvVarDebug)  # pyright: ignore[reportArgumentType]
        for config in configs_to_apply:
            kwargs: Any = {}
            if config == DefaultProjectFilesConfig:
                kwargs = {
                    "project_files_dir": self._projects_tmp_dir,
                    "is_product_system_different_platform": self.is_product_system_configured,
                }
            elif config == WithGrpcCertificates:
                kwargs["certs_dir"] = self._certificates_directory
            self._applied_configurations[config.config_type] = config(self.deployment_type, **kwargs)
            self._applied_configurations[config.config_type].setup(
                compose_override_file=self.solution_dir / f"glow_config_{config.config_type}.yaml",
            )

        if restart:
            self.restart()

    def change_configuration(
        self,
        configuration: type[BaseGlowConfiguration],
        restart: bool = True,
        **kwargs: Any,
    ) -> BaseGlowConfiguration:
        if configuration.config_type in self._applied_configurations:
            self._applied_configurations[configuration.config_type].teardown()
        self._applied_configurations[configuration.config_type] = configuration(self.deployment_type, **kwargs)
        self._applied_configurations[configuration.config_type].setup(
            compose_override_file=self.solution_dir / f"glow_config_{configuration.config_type}.yaml",
        )
        if restart:
            self.restart()
        return self._applied_configurations[configuration.config_type]

    def start(self) -> None:
        cmd = self._extract_up_command()
        env = self._extend_env()

        try:
            subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as err:
            print("Failed to start GLOW Docker containers:")
            for line in err.output.splitlines():
                logger.error(line.strip())
            print("Container logs for debugging:")
            container_logs = subprocess.check_output(
                self._extract_logs_command(),
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            for line in container_logs.splitlines():
                logger.error(line.strip())
            raise

        assert self.healthy

        for container in self._containers:
            self._containers[container].define_container_id()

    @property
    def startup_errors(self) -> list[str]:
        startup_errors: list[str] = []
        # TODO: implement
        return startup_errors

    def stop(self, clean_volumes: bool = True) -> None:
        cmd = self._extract_command()
        cmd.append("down")
        if clean_volumes:
            cmd.append("-v")

        try:
            subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except subprocess.CalledProcessError as err:
            logger.exception(err.output.splitlines())
            raise

    def restart(self, wait_seconds: int = 10, log_tag: str = "session restart", keep_ports: bool = True) -> None:
        # Logs will be cleared when stopping the container
        self._catch_up_logs_before_clear(log_tag)

        # We want to keep projects data between restarts
        self.stop(clean_volumes=False)
        time.sleep(wait_seconds)
        self.start()

    @property
    def postgresql_server(self) -> PostgresqlServerInfo:
        cmd = self._extract_command()
        cmd.append("ps")
        try:
            output = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except subprocess.CalledProcessError as err:
            logger.exception(err.output.splitlines())
            raise
        container_name: str | None = None
        for line in output.splitlines():
            if "-my-solution-database-" in line:
                # expected format: NAME IMAGE ...
                container_name = line.split("postgres:16.0")[0].strip()
        assert container_name
        return PostgresqlServerInfo(
            PostgresDsn("postgresql://glow:glow@my-solution-database:5432/postgres"),
            container_name,
        )

    def clear_output(self) -> None:
        self._catch_up_logs_before_clear("Clearing output.")
        for container in self._containers.values():
            container.clear_output()
