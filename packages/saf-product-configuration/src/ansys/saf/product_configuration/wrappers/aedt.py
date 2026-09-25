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

import multiprocessing
import os
import warnings

import click
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import uvicorn

from ansys.saf.product_configuration.wrappers.types import TransportMode

# This wrapper manages pyAEDT sessions launched by PIM/HPS. It supports two modes:
#
# Local mode (grpc_local=True):
# - On a new session petition, return 2 available ports (GET /)
# - Client requests a local Desktop session (POST /get_or_create_local_session)
# - The wrapper creates the Desktop instance in its own process, avoiding env var conflicts
# - Client confirms the session is running (POST /confirm_session_running)
#
# Remote mode (grpc_local=False):
# - Launch service manager (POST /start_service_manager)
# - On a new session petition, return 2 available ports (GET /)
# - Client uses those 2 ports to establish the connection via common_rpc and confirms to the
#   wrapper that it was successful (POST /confirm_session_running)
#
# All PyAEDT imports are done inside functions, so we don't need pyaedt for running our tests
#
# WARNING: Any change to this wrapper code or its dependencies MUST be committed with an increment
# to the wrapper version in ``ansys.saf.product_configuration.wrappers.versions``. The wrapper
# version MUST always correspond to the wrapper committed at the same time.

ANSYS_GRPC_CERTIFICATES = "ANSYS_GRPC_CERTIFICATES"


_selected_version: str = "261"
_product_host: str = "0.0.0.0"  # noqa: S104
_transport_mode: TransportMode = TransportMode.INSECURE


app = FastAPI()


class ConfirmSessionRunningRequest(BaseModel):
    """Request payload for confirming a running AEDT session."""

    session_rpyc_port: int = -1
    session_grpc_port: int = -1


class CreateLocalSessionRequest(BaseModel):
    """Request payload for creating a local AEDT session."""

    session_running: bool = False
    session_grpc_port: int = -1


class State(BaseModel):
    """Current state exposed by the AEDT wrapper service."""

    service_manager_running: bool = False
    service_manager_port: int = -1
    session_running: bool = False
    session_rpyc_port: int = -1
    session_grpc_port: int = -1
    transport_mode: TransportMode = TransportMode.INSECURE


class DataModel:
    state: State = State()


def _run_service_manager(host: str, port: int, version: str, transport_mode: TransportMode):

    from ansys.aedt.core.common_rpc import pyaedt_service_manager  # pyright: ignore[reportMissingTypeStubs]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        from ansys.aedt.core.generic.settings import settings  # pyright: ignore[reportMissingTypeStubs]

    os.environ["AEDT_HOST"] = host
    settings.grpc_local = False
    settings.grpc_secure_mode = transport_mode == TransportMode.MTLS
    pyaedt_service_manager(port=port, aedt_version=version)


@app.post("/start_service_manager")
async def start_service_manager():
    if _transport_mode in [TransportMode.WNUA, TransportMode.UDS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"remote session creation is not supported in {_transport_mode} mode",
        )

    from ansys.aedt.core.desktop import _find_free_port  # pyright: ignore[reportMissingTypeStubs, reportPrivateUsage]

    if DataModel.state.service_manager_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="service manager already running",
        )
    port = _find_free_port()
    multiprocessing.Process(
        target=_run_service_manager,
        args=[_product_host, port, _selected_version, _transport_mode],
    ).start()
    DataModel.state.service_manager_running = True
    DataModel.state.service_manager_port = port


@app.post("/get_or_create_local_session")
async def get_or_create_local_session(payload: CreateLocalSessionRequest):
    if _transport_mode == TransportMode.MTLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="local session creation is not supported in MTLS mode",
        )

    import ansys.aedt.core  # pyright: ignore[reportMissingTypeStubs]
    from ansys.aedt.core import Desktop  # pyright: ignore[reportMissingTypeStubs]

    ansys.aedt.core.settings.grpc_local = True
    ansys.aedt.core.settings.grpc_secure_mode = _transport_mode in [TransportMode.WNUA, TransportMode.UDS]

    # Ensure pyAEDT uses the configured transport mode, not one inferred from env vars:
    # remove ANSYS_GRPC_CERTIFICATES so pyAEDT doesn't override to MTLS.
    saved_certs = os.environ.pop(ANSYS_GRPC_CERTIFICATES, None)
    try:
        Desktop(
            version=_selected_version,
            non_graphical=True,
            new_desktop=not payload.session_running,
            port=payload.session_grpc_port,
        )
    finally:
        if saved_certs is not None:
            os.environ[ANSYS_GRPC_CERTIFICATES] = saved_certs


@app.get("/")
async def get_state():
    from ansys.aedt.core.desktop import _find_free_port  # pyright: ignore[reportMissingTypeStubs, reportPrivateUsage]

    if DataModel.state.session_running:
        return DataModel.state
    else:
        return State(
            service_manager_running=DataModel.state.service_manager_running,
            session_running=DataModel.state.session_running,
            service_manager_port=DataModel.state.service_manager_port,
            session_rpyc_port=_find_free_port(),
            session_grpc_port=_find_free_port(),
            transport_mode=_transport_mode,
        )


@app.post("/confirm_session_running")
async def confirm_session_running(payload: ConfirmSessionRunningRequest):
    if DataModel.state.session_running:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session already running")
    DataModel.state.session_rpyc_port = payload.session_rpyc_port
    DataModel.state.session_grpc_port = payload.session_grpc_port
    DataModel.state.session_running = True
    DataModel.state.transport_mode = _transport_mode


@app.get("/health")
async def health():
    return "healthy"


@click.command()
@click.option("--port", type=int, required=True, help="Port to bind.")
@click.option("--host", type=str, required=True, help="Host to bind.")
@click.option("--version", type=str, required=True, help="AEDT version, in 3-digit format, e.g., 251 for 2025R1.")
@click.option(
    "--transport-mode",
    required=True,
    type=click.Choice(TransportMode, case_sensitive=False),  # pyright: ignore[reportArgumentType]
    help="Transport mode to be used.",
)
@click.option(
    "--certs-dir",
    type=str,
    default=None,
    envvar="ANSYS_GRPC_CERTIFICATES",
    help="Directory path for certificate files (default: env var ANSYS_GRPC_CERTIFICATES)",
)
def main(port: int, host: str, version: str, transport_mode: TransportMode, certs_dir: str | None):
    global _selected_version
    global _product_host
    global _transport_mode
    _selected_version = version
    _product_host = host
    _transport_mode = transport_mode
    if certs_dir is not None:
        os.environ["ANSYS_GRPC_CERTIFICATES"] = certs_dir
    uvicorn.run(app, host=host, port=port)  # pyright: ignore[reportUnknownMemberType]


if __name__ == "__main__":
    main()
