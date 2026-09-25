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
import tempfile
from typing import Annotated, Any, cast

from ansys.optislang.core import (  # pyright: ignore[reportMissingTypeStubs]
    Optislang,
    logging,
    utils,
)
from ansys.optislang.core.communication_channels import CommunicationChannel  # pyright: ignore[reportMissingTypeStubs]
from ansys.optislang.core.errors import (  # pyright: ignore[reportMissingTypeStubs]
    OslServerLicensingError,
    OslServerStartError,
)
from ansys.optislang.core.tcp.osl_server import (  # pyright: ignore[reportMissingTypeStubs]
    TcpOslServer,  # noqa: TC002
)
import click
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

from ansys.saf.product_configuration._utils.timeout_utilities import get_timeout_from_environment
from ansys.saf.product_configuration.wrappers.types import TransportMode

app = FastAPI()

CONNECTION_MODE_LOCAL_DOMAIN = "LOCAL_DOMAIN"
CONNECTION_MODE_TCP = "TCP"
SAF_OPTISLANG_TIMEOUT = "SAF_OPTISLANG_TIMEOUT"
DEFAULT_SAF_OPTISLANG_TIMEOUT = 300


class OptislangWrapperErrorCodes:
    LICENSE_ERROR = 1
    SERVER_START_ERROR = 2


ERROR_MESSAGE_FORMAT = (
    "Unable to start optiSLang {osl_version}: {error}. Please try again later or contact your IT administrator."
)
LICENSE_ERROR_MESSAGE = "No available licenses at this time"
OSL_SERVER_START_ERROR_MESSAGE = "OptiSLang server error"


class OptislangInstance:
    def __init__(self):
        """Creating a new OptislangInstance instance. All attributes default to None."""
        self._osl: Optislang | None = None
        self._osl_working_directory: str | None = None
        self._connection_mode: str | None = None
        self._local_server_id: str | None = None
        self._osl_port: int | None = None
        self._osl_host: str | None = None
        self.osl_log_path: Path | None = None

    @property
    def port(self) -> int | None:
        return self._osl_port

    @property
    def host(self) -> str | None:
        return self._osl_host

    @property
    def local_server_id(self) -> str | None:
        return self._local_server_id

    @property
    def connection_mode(self) -> str | None:
        return self._connection_mode

    def get_connection_info(self) -> dict[str, Any]:
        if self._connection_mode == CONNECTION_MODE_TCP:
            if self._osl_host is None or self._osl_port is None:
                raise HTTPException(status_code=500, detail="TCP connection information is not available")
            return {
                "connection_mode": self._connection_mode,
                "host": self._osl_host,
                "port": self._osl_port,
            }

        if self._local_server_id is None:
            raise HTTPException(status_code=500, detail="Local connection information is not available")

        return {
            "connection_mode": self._connection_mode or CONNECTION_MODE_LOCAL_DOMAIN,
            "local_server_id": self._local_server_id,
        }

    def _move_project_and_input_files_to_temp_working_dir(
        self,
        source_project_file: Path,
        source_input_file_paths: list[Path],
    ) -> Path:
        if not self._osl_working_directory:
            raise RuntimeError("Instance working directory not initialized.")

        destination_project_file = Path(self._osl_working_directory) / source_project_file.name
        shutil.copyfile(source_project_file, destination_project_file)

        destination_input_files_folder = Path(self._osl_working_directory) / "Input_Files"
        destination_input_files_folder.mkdir(parents=True, exist_ok=True)

        for source_input_file in source_input_file_paths:
            destination_input_file = destination_input_files_folder / source_input_file.name
            shutil.copy(source_input_file, destination_input_file)

        return destination_project_file

    def start(
        self,
        project_path: Path,
        project_properties_file: Path,
        input_files: list[Path],
        osl_version: int,
        loglevel: str,
        connection_mode: str,
        log_file_path: Path | None,
    ) -> None:
        if self._osl is None:
            executable_file = utils.get_osl_exec(osl_version)
            if not executable_file:
                raise HTTPException(status_code=500, detail="OptiSLang executable not found")
            self._osl_working_directory = tempfile.mkdtemp()

            if log_file_path:
                self.osl_log_path = log_file_path
            else:
                self.osl_log_path = Path(self._osl_working_directory) / "optiSLang.log"

            self.osl_log_path.touch(exist_ok=True)  # Create empty file

            dest_project_file = self._move_project_and_input_files_to_temp_working_dir(project_path, input_files)

            if connection_mode not in (CONNECTION_MODE_LOCAL_DOMAIN, CONNECTION_MODE_TCP):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Invalid connection_mode '{connection_mode}'. Expected one of: "
                        f"{CONNECTION_MODE_LOCAL_DOMAIN}, {CONNECTION_MODE_TCP}"
                    ),
                )

            communication_channel = CommunicationChannel.LOCAL_DOMAIN
            server_address = None
            if connection_mode == CONNECTION_MODE_TCP:
                communication_channel = CommunicationChannel.TCP
                server_address = "0.0.0.0"  # noqa: S104

            self._osl = Optislang(
                project_path=dest_project_file,
                executable=executable_file[1],
                loglevel=loglevel,
                reset=True,
                auto_relocate=True,
                shutdown_on_finished=False,
                import_project_properties_file=project_properties_file,
                ini_timeout=get_timeout_from_environment(SAF_OPTISLANG_TIMEOUT, DEFAULT_SAF_OPTISLANG_TIMEOUT),
                env_vars={"PYTHONPATH": ""},
                communication_channel=communication_channel,
                server_address=server_address,
            )
            # Configure logging
            osl_logger = logging.OslLogger(
                loglevel=loglevel,
                log_to_file=True,
                logfile_name=self.osl_log_path.as_posix(),
                log_to_stdout=True,
            )
            self._osl.__logger = osl_logger.add_instance_logger(self._osl.name, self._osl, loglevel)  # type: ignore
            self._osl.log.info("Start analysis")
            osl_server = cast("TcpOslServer", self._osl.osl_server)
            self._connection_mode = connection_mode
            if communication_channel == CommunicationChannel.TCP:
                self._osl_host = osl_server.get_host()
                self._osl_port = osl_server.get_port()
                self._local_server_id = None
            else:
                self._local_server_id = osl_server.local_server_id
                self._osl_host = None
                self._osl_port = None

    def close_optislang(self):
        if self._osl:
            self._osl.shutdown(force=True)
            self._osl.dispose()

        self._osl = None
        self._connection_mode = None
        self._local_server_id = None
        self._osl_port = None
        self._osl_host = None

    def shutdown(self):
        if self._osl:
            self.close_optislang()

        if self._osl_working_directory:
            shutil.rmtree(self._osl_working_directory, ignore_errors=True)
        self._osl_working_directory = None


_optislang_instance: OptislangInstance | None = None


def get_global_optislang_instance() -> OptislangInstance:
    global _optislang_instance
    if _optislang_instance is None:
        _optislang_instance = OptislangInstance()
    return _optislang_instance


GlobalOptislangInstanceDep = Annotated[OptislangInstance, Depends(get_global_optislang_instance)]


@app.exception_handler(OslServerLicensingError)
async def license_exception_handler(request: Request, exc: OslServerLicensingError):

    content = await request.json()
    osl_version = content.get("osl_version")
    osl_version = str(osl_version) if osl_version is not None else ""

    message = ERROR_MESSAGE_FORMAT.format(osl_version=osl_version, error=LICENSE_ERROR_MESSAGE)

    return JSONResponse(
        status_code=500,
        content={
            "message": message,
            "error_code": OptislangWrapperErrorCodes.LICENSE_ERROR,
        },
    )


@app.exception_handler(OslServerStartError)
async def server_start_exception_handler(request: Request, exc: OslServerStartError):

    content = await request.json()
    osl_version = content.get("osl_version")
    osl_version = str(osl_version) if osl_version is not None else ""

    message = ERROR_MESSAGE_FORMAT.format(osl_version=osl_version, error=OSL_SERVER_START_ERROR_MESSAGE)
    return JSONResponse(
        status_code=500,
        content={
            "message": message,
            "error_code": OptislangWrapperErrorCodes.SERVER_START_ERROR,
        },
    )


@app.post("/start")
async def start_instance(
    optislang_instance: GlobalOptislangInstanceDep,
    project_path: Path = Body(...),  # noqa: B008, FAST002
    project_properties_file: Path = Body(...),  # noqa: B008, FAST002
    input_files: list[Path] = Body(...),  # noqa: B008, FAST002
    osl_version: int = Body(...),  # noqa: FAST002
    loglevel: str = Body(...),  # noqa: FAST002
    connection_mode: str = Body(default=CONNECTION_MODE_LOCAL_DOMAIN),  # noqa: FAST002
    log_file_path: Path | None = Body(default=None),  # noqa: B008, FAST002
):
    optislang_instance.start(
        project_path,
        project_properties_file,
        input_files,
        osl_version,
        loglevel,
        connection_mode,
        log_file_path,
    )
    return optislang_instance.get_connection_info()


@app.post("/close-optislang")
async def close_optislang(optislang_instance: GlobalOptislangInstanceDep):
    optislang_instance.close_optislang()


@app.post("/shutdown")
async def shutdown(optislang_instance: GlobalOptislangInstanceDep):
    optislang_instance.shutdown()


@app.get("/connection")
async def get_connection(optislang_instance: GlobalOptislangInstanceDep):
    return optislang_instance.get_connection_info()


@app.get("/logs", response_class=PlainTextResponse)
async def get_logs(optislang_instance: GlobalOptislangInstanceDep):
    if optislang_instance.osl_log_path is None:
        raise HTTPException(status_code=500, detail="Logs are not available")
    if not optislang_instance.osl_log_path.exists():
        raise HTTPException(status_code=500, detail="Log file does not exist")
    logs = optislang_instance.osl_log_path.read_text()
    return logs


@app.get("/health")
async def health():
    return "healthy"


@click.command()
@click.option("--port", type=int, required=True, help="Port to bind.")
@click.option("--host", type=str, required=True, help="Host to bind.")
@click.option(
    "--transport-mode",
    default=TransportMode.INSECURE,
    type=click.Choice(TransportMode, case_sensitive=False),  # pyright: ignore[reportArgumentType]
    help="Transport mode placeholder accepted for compatibility with secure flags.",
)
def main(port: int, host: str, transport_mode: TransportMode):
    del transport_mode
    uvicorn.run(app, host=host, port=port)  # type: ignore


if __name__ == "__main__":
    main()
