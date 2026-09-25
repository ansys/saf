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

import os
from pathlib import Path
import platform
import subprocess  # nosec B404
import tempfile
import time
from typing import Annotated
import uuid

import click
from fastapi import Body, Depends, FastAPI, HTTPException
import uvicorn

from ansys.saf.product_configuration._utils.procs import kill_proc_tree
from ansys.saf.product_configuration.wrappers.types import TransportMode

# WARNING: Any change to this wrapper code or its dependencies MUST be committed with an increment
# to the wrapper version in ``ansys.saf.product_configuration.wrappers.versions``. The wrapper
# version MUST always correspond to the wrapper committed at the same time.


SAF_FLUENT_WRAPPER_TIMEOUT = "SAF_FLUENT_WRAPPER_TIMEOUT"
DEFAULT_TIMEOUT = 100


class FluentInstance:
    def __init__(
        self,
        host: str,
        version: str,
        mode: str,
        geometry: str,
        precision: str,
        transport_mode: TransportMode,
        certs_dir: str | None = None,
    ):
        self._version = version
        self._mode = mode
        self._geometry = geometry
        self._precision = precision
        self._transport_mode = transport_mode
        self._certs_dir = certs_dir
        self._host = host

        self._timeout = int(os.environ.get(SAF_FLUENT_WRAPPER_TIMEOUT, DEFAULT_TIMEOUT))

        self._fluent: subprocess.Popen[bytes] | None = None
        self._fluent_address: str | None = None
        self._cleanup_file: Path | None = None

    @property
    def port(self) -> int | None:
        if self._fluent_address is None:
            return None

        host, separator, port = self._fluent_address.rpartition(":")
        if not separator or not host or ":" in host or not port.isdigit():
            return None

        return int(port)

    def _find_fluent_bin(self) -> str:
        ansys_path = os.getenv(f"AWP_ROOT{self._version}")
        if ansys_path:
            if platform.system() == "Windows":
                fluent_bin_path = Path(ansys_path) / "fluent" / "ntbin" / "win64" / "fluent.exe"
            else:
                fluent_bin_path = Path(ansys_path) / "fluent" / "bin" / "fluent"
            if fluent_bin_path.is_file():
                return str(fluent_bin_path)
        raise RuntimeError(f"Ansys Fluent version {self._version} cannot be found")

    def _find_cleanup_file(self, working_dir: Path, existing_files: list[Path]) -> None:
        self._cleanup_file = None
        num_tries = 0
        while not self._cleanup_file and num_tries < self._timeout:
            for file in working_dir.iterdir():
                if file.name.startswith("cleanup-fluent-") and file not in existing_files:
                    self._cleanup_file = Path(file)
                    break
            num_tries += 1
            time.sleep(1)
        if not self._cleanup_file:
            raise RuntimeError("Couldn't find Fluent's clean-up file.")

    def get_fluent_pids(self) -> list[int]:
        fluent_pids: list[int] = []
        for line in self._cleanup_file.read_text().splitlines():  # pyright: ignore[reportOptionalMemberAccess]
            if platform.system() == "Windows" and "%KILL_CMD%" in line:
                fluent_pids.append(int(line.split("%KILL_CMD% ")[1].split(")")[0]))
            elif platform.system() == "Linux" and "kill -9 " in line:
                fluent_pids.append(int(line.split("kill -9 ")[1].split(";")[0]))
        if not fluent_pids:
            raise RuntimeError("Couldn't find Fluent PIDs.")
        return fluent_pids

    def _find_fluent_address(self, server_info_file_path: Path) -> None:
        num_tries = 0
        while not server_info_file_path.is_file() and num_tries < self._timeout:
            num_tries += 1
            time.sleep(1)
        if not server_info_file_path.is_file():
            raise RuntimeError("Couldn't find Fluent's server_info file.")

        server_info_lines = server_info_file_path.read_text().splitlines()
        if not server_info_lines or not server_info_lines[0].strip():
            raise RuntimeError("Couldn't find Fluent's address in server_info file.")

        self._fluent_address = server_info_lines[0].strip()

    def _build_cmd(
        self,
        server_info_file_path: Path,
        transport_mode: TransportMode,
        certs_dir: str | None,
    ) -> list[str]:
        no_ui_arg = "hidden" if platform.system() == "Windows" else "g"

        fluent_bin = self._find_fluent_bin()
        cmd = [
            fluent_bin,
            # Start the GRPC server. File path must be without quotes, otherwise when shell=False,
            # Fluent throws unbound variable error on Linux.
            f"-sifile={server_info_file_path.as_posix()}",
            f"-{no_ui_arg}",  # Don't show GUI
        ]

        match transport_mode:
            case TransportMode.INSECURE:
                cmd.append("-grpc-allow-remote-host")
                cmd.append("-grpc-insecure-mode")
            case TransportMode.MTLS:
                if not certs_dir:
                    raise RuntimeError("certs-dir must be provided when transport-mode is MTLS")
                cmd.append("-grpc-allow-remote-host")
                # File path must be without quotes, otherwise with shell=False, Fluent tries to build the path
                # as "/certs_dir_path"/server.key and it fails to find the files.
                cmd.append(f"-grpc-certs-folder={Path(certs_dir).as_posix()}")
            case TransportMode.UDS:
                # UDS doesn't require to set any flag. Fluent generates a random unix socket path automatically.
                pass
            case TransportMode.WNUA:
                # WNUA doesn't require to set any flag. Fluent always sets host to 127.0.0.1 in the sifile
                self._host = "127.0.0.1"
            case _:
                raise RuntimeError(f"Unknown transport mode: {transport_mode}")

        if self._mode == "meshing":
            cmd.append("-meshing")
        geometry_plus_precision = f"{self._geometry}dp" if self._precision == "double" else f"{self._geometry}sp"
        # TODO: we don't check for invalid combinations of mode/version/precision
        cmd.append(geometry_plus_precision)

        return cmd

    def _get_env_for_fluent(self) -> dict[str, str]:
        fluent_env = os.environ.copy()
        # Address where the GRPC server is bind to. Ignored if "-grpc-allow-remote-host" is not set (WNUA, UDS modes)
        fluent_env["REMOTING_SERVER_ADDRESS"] = self._host
        # For the port, we let Fluent automatically find it.
        return fluent_env

    def _get_server_info_file_path(self, working_dir: Path) -> Path:
        # It has to be within the working_dir (GLOW's product space) in order to be able to read the password from the
        # product manager and connect to it, which is required in >=25R2.
        return working_dir / f"sifile-{str(uuid.uuid4())}.txt"

    def initialize(self, working_dir: Path) -> None:
        if self._fluent:
            return

        fluent_env = self._get_env_for_fluent()

        server_info_file_path = self._get_server_info_file_path(working_dir)

        # Save existing files in the working dir to discard them later
        # when we are looking for the cleanup file.
        # In GLOW we use the same directory for all instance executions within a project,
        # so files are accumulated.
        existing_files = list(working_dir.iterdir())

        cmd = self._build_cmd(server_info_file_path, self._transport_mode, self._certs_dir)
        self._launch(cmd, cwd=working_dir, env=fluent_env)

        self._find_cleanup_file(working_dir, existing_files)
        # In secure managers, the manager doesn't call this wrapper endpoint to receive the port and instead
        # directly parse the sifile to extract port and password. However, we still have this method here
        # since it also works as a healthcheck, to not let the manager try to find the file until it's ready.
        self._find_fluent_address(server_info_file_path)

    def _launch(self, cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
        self._fluent = subprocess.Popen(cmd, cwd=cwd, env=env)  # nosec B603

    def shutdown(self):
        if self._cleanup_file:
            # The cleanup file deletes fluent's pids and then itself
            if platform.system() == "Linux":
                # script doesn't have proper shebang at the top. From testing, it seems that it requires bash to run.
                # Using sh instead, fails to execute the if/else blocks.
                subprocess.check_output(["bash", self._cleanup_file.as_posix()])  # nosec B603 B607
            else:
                try:
                    # Silence error due to the BAT file deleting itself. Raise the rest.
                    subprocess.check_output([self._cleanup_file.as_posix()], stderr=subprocess.STDOUT, text=True)  # nosec B603
                except subprocess.CalledProcessError as e:
                    if "The batch file cannot be found." not in e.output:
                        raise
        if self._fluent:
            kill_proc_tree(self._fluent.pid, include_parent=True)
        self._fluent = None
        self._fluent_address = None
        self._cleanup_file = None


def get_global_fluent_instance() -> FluentInstance:
    return _FLUENT_INSTANCE


GlobalFluentInstanceDep = Annotated[FluentInstance, Depends(get_global_fluent_instance)]

app = FastAPI()


@app.post("/start")
async def start_instance(
    fluent_instance: GlobalFluentInstanceDep,
    working_dir: Annotated[str | None, Body(..., embed=True)] = None,
):
    fluent_instance.initialize(Path(working_dir or tempfile.mkdtemp()))


@app.get("/")
async def get_instance_port(fluent_instance: GlobalFluentInstanceDep):
    if fluent_instance.port is None:
        raise HTTPException(status_code=500, detail="Port is not available")
    return {"port": fluent_instance.port}


@app.post("/shutdown")
async def shutdown(fluent_instance: GlobalFluentInstanceDep):
    fluent_instance.shutdown()


@app.get("/health")
async def health():
    return "healthy"


@click.command()
@click.option("--port", type=int, required=True, help="Port to bind.")
@click.option("--host", type=str, required=True, help="Host to bind.")
@click.option("--version", type=str, required=True, help="Fluent version, in 3-digit format, e.g., 251 for 2025R1.")
@click.option("--mode", type=click.Choice(["solver", "meshing"]), required=True, help="Fluent mode: solver, meshing.")
@click.option("--geometry", type=click.Choice(["2d", "3d"]), required=True, help="Fluent geometry: 2d, 3d.")
@click.option(
    "--precision",
    type=click.Choice(["double", "single"]),
    required=True,
    help="Fluent precision: single, double.",
)
@click.option(
    "--transport-mode",
    default=TransportMode.INSECURE,  # for retrocompatibility. secure configs always set transport mode
    type=click.Choice(TransportMode, case_sensitive=False),  # pyright: ignore[reportArgumentType]
    help="Transport mode to be used",
)
@click.option(
    "--certs-dir",
    type=str,
    default=None,
    envvar="ANSYS_GRPC_CERTIFICATES",
    help="Directory path for certificate files (default: env var ANSYS_GRPC_CERTIFICATES)",
)
def main(
    port: int,
    host: str,
    version: str,
    mode: str,
    geometry: str,
    precision: str,
    transport_mode: TransportMode,
    certs_dir: str | None,
):
    global _FLUENT_INSTANCE
    _FLUENT_INSTANCE = FluentInstance(
        host=host,
        version=version,
        mode=mode,
        geometry=geometry,
        precision=precision,
        transport_mode=transport_mode,
        certs_dir=certs_dir,
    )
    try:
        uvicorn.run(app, host=host, port=port)  # type: ignore
    finally:
        _FLUENT_INSTANCE.shutdown()


if __name__ == "__main__":
    main()
