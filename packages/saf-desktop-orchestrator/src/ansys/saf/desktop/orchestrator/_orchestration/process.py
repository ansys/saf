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

import contextlib
from io import TextIOWrapper  # noqa: TC003
import logging
import os
from pathlib import Path
import platform
import socket
import subprocess  # nosec B404
import sys
from time import sleep
from typing import TYPE_CHECKING, Any

import grpc  # pyright: ignore[reportMissingTypeStubs]
from grpc_health.v1 import (  # pyright: ignore[reportMissingTypeStubs]
    health_pb2,
    health_pb2_grpc,
)
import httpx2
import psutil

from ansys.saf.desktop.orchestrator._config.schema import (
    DEFAULT_SAF_DESKTOP_HEALTH_CHECK_TIMEOUT,
    HEALTH_CHECK_INTERVAL,
    LOCALHOST_IP,
)
from ansys.saf.desktop.orchestrator._utilities.ip_utilities import (
    get_local_ip,
    get_random_free_port,
    resolve_ip,
    wait_for_response,
)
from ansys.saf.desktop.orchestrator._utilities.process import kill_proc_tree

# see
# https://mypy.readthedocs.io/en/stable/runtime_troubles.html#using-classes-that-are-generic-in-stubs-but-not-at-runtime
# for the logic here
if TYPE_CHECKING:
    SubprocessType = subprocess.Popen[bytes]  # this is only processed by pyright
else:
    SubprocessType = subprocess.Popen  # this is not seen by pyright but will be executed at runtime
logger = logging.getLogger(__name__)


class ServiceProcess:
    def __init__(
        self,
        args: list[str],
        port: int | None = None,
        ip: str = "localhost",
        env: dict[str, str] | None = None,
        health_route: str = "/health",
        health_check_timeout: int = DEFAULT_SAF_DESKTOP_HEALTH_CHECK_TIMEOUT,
        cwd: Path | None = None,
        log_file: Path | None = None,
    ) -> None:
        self._env = env if env is not None else os.environ.copy()
        self._args = args
        self._is_windows = platform.system() == "Windows"
        self._process: SubprocessType | None = None
        self._port = port if port is not None else get_random_free_port()
        self._ip = ip or get_local_ip()
        self._health_route = health_route
        self._health_check_timeout = health_check_timeout
        self._health_check_retries = int(self._health_check_timeout / HEALTH_CHECK_INTERVAL)
        self._cwd = cwd
        self._log_file = log_file

        self._log_file_handle: TextIOWrapper | None = None

    @property
    def process(self) -> SubprocessType | None:
        return self._process

    def run(self, additional_args: list[str] | None = None, allow_window: bool = True) -> None:
        """Start the service."""
        args = self._args + (additional_args or [])
        logger.debug("starting process " + " ".join(args))

        kwargs: dict[str, Any] = {
            "args": args,
            "env": self._env,
            "cwd": self._cwd,
        }
        if self._log_file:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_file_handle = self._log_file.open("w")
            kwargs["stdout"] = self._log_file_handle
            kwargs["stderr"] = self._log_file_handle
            kwargs["stdin"] = subprocess.DEVNULL

        if self._is_windows:
            creationflags = (  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                subprocess.CREATE_NEW_PROCESS_GROUP  # pyright: ignore[reportAttributeAccessIssue]
            )
            if not allow_window:
                creationflags |= (  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                    subprocess.CREATE_NO_WINDOW  # pyright: ignore[reportAttributeAccessIssue]
                )
            kwargs["creationflags"] = creationflags
            kwargs["bufsize"] = 1
            if self._log_file is None and sys.executable.endswith("pythonw.exe"):
                # pythonw doesn't have stdin/stdout/stderr which makes some libraries to crash when printing something..
                # Redirecting the output (subprocess.PIPE) doesn't work either as it will eventually fill the buffer and
                # block the process. So we redirect to DEVNULL which is not ideal but at least it works.
                kwargs["stdout"] = subprocess.DEVNULL
                kwargs["stderr"] = subprocess.DEVNULL
                kwargs["stdin"] = subprocess.DEVNULL
        else:
            kwargs["preexec_fn"] = os.setsid  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
            kwargs["shell"] = False
        self._process = subprocess.Popen(**kwargs)  # pyright: ignore[reportAttributeAccessIssue]  # nosec B603

    def stop(self) -> None:
        """Stop the service."""
        if self._process is None:
            return
        parent: psutil.Process | None = None
        try:
            parent = psutil.Process(self._process.pid)
        except psutil.NoSuchProcess:
            parent = None

        if parent is not None:
            logger.debug(f"Killing process '{self._process.args}' with pid: '{self._process.pid}'")
            kill_proc_tree(parent.pid)
        # Remove 'ResourceWarning: subprocess XXXX is still running'.
        self._process.wait()
        if self._log_file_handle:
            self._log_file_handle.close()
            self._log_file_handle = None

    def wait_for_healthy(self):
        ip = resolve_ip(self._ip)
        wait_for_response(
            f"http://{ip}:{self._port}{self._health_route}",
            tries=self._health_check_retries,
            interval=HEALTH_CHECK_INTERVAL,
        )

    def _http_health_check(self, _name: str) -> bool:
        tries = self._health_check_retries
        while tries > 0:
            response: httpx2.Response | None = None
            with contextlib.suppress(
                httpx2.ConnectError,
                httpx2.WriteError,
                httpx2.RemoteProtocolError,
                httpx2.TimeoutException,
            ):
                response = httpx2.get(f"http://{LOCALHOST_IP}:{self._port}{self._health_route}")
            if response and response.status_code == 200:
                logger.debug(f"Successfully connected to the healthy {_name} service")
                return True
            sleep(HEALTH_CHECK_INTERVAL)
            tries = tries - 1
        logger.warning(f"Unable to connect to healthy service {_name} after startup")
        return False

    def _tcp_health_check(self, _name: str) -> bool:
        tries = self._health_check_retries
        while tries > 0:
            try:
                # Create a socket object
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    # Attempt to connect to the host and port
                    sock.connect((self._ip, self._port))
                    logger.debug(f"Successfully connected to the healthy {_name} service")
                    return True
            except OSError:
                ...
            finally:
                sleep(HEALTH_CHECK_INTERVAL)
                tries = tries - 1
        logger.warning(f"Unable to connect to healthy service {_name} after startup")
        return False

    def _create_grpc_channel(self, socket_path: Path | None = None, certs_dir: Path | None = None) -> grpc.Channel:
        if certs_dir:
            creds = grpc.ssl_channel_credentials(  # type: ignore
                root_certificates=(certs_dir / "ca.crt").read_bytes(),
                private_key=(certs_dir / "client.key").read_bytes(),
                certificate_chain=(certs_dir / "client.crt").read_bytes(),
            )
            return grpc.secure_channel(f"{self._ip}:{self._port}{self._health_route}", creds)  # type: ignore
        elif socket_path:
            target = f"unix:{socket_path}"
            options = (("grpc.default_authority", "localhost"),)
            return grpc.insecure_channel(target=target, options=options)  # type: ignore
        else:
            options = (("grpc.default_authority", "localhost"),)
            return grpc.insecure_channel(f"{self._ip}:{self._port}{self._health_route}", options=options)  # type: ignore

    def _grpc_health_check(self, _name: str, socket_path: Path | None = None, certs_dir: Path | None = None) -> bool:
        status = health_pb2.HealthCheckResponse.NOT_SERVING
        tries = self._health_check_retries
        while tries > 0:
            with self._create_grpc_channel(socket_path=socket_path, certs_dir=certs_dir) as channel:  # type: ignore
                request = health_pb2.HealthCheckRequest()
                stub = health_pb2_grpc.HealthStub(channel)  # type: ignore
                try:
                    resp = stub.Check(request)  # type: ignore
                    status = resp.status  # type: ignore
                    if status == health_pb2.HealthCheckResponse.SERVING:
                        logger.debug(f"Successfully connected to the healthy {_name} service")
                        return True
                except grpc.RpcError:
                    ...  # pim gRPC server not ready yet.
                finally:
                    sleep(HEALTH_CHECK_INTERVAL)
                    tries = tries - 1

        logger.warning(f"Unable to connect to healthy service {_name} after startup")
        return False

    @property
    def port(self) -> int:
        """Return the port integer for the port served by the service.

        Returns
        -------
        str
            the port serviced by this service
        """
        return self._port

    @property
    def url(self) -> str:
        """return the URL string for the port served by the service
        Returns
        -------
        str
            the URL string for the port served by the service
        """
        return f"http://{self._ip}:{self._port}"
