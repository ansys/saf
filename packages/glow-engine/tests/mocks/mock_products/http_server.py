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
import tempfile

import click
from fastapi import FastAPI, HTTPException
import psutil

DEFAULT_PROPERTY_VALUE = "blue"
# Safe root directory for file operations in tests
SAFE_ROOT = Path(tempfile.gettempdir()).resolve()

app = FastAPI()


@app.get("/health", response_model=dict[str, int])
@app.get("/my_custom_health_route", response_model=dict[str, int])
def health_check():
    if not app.session["healthy"]:  # type: ignore
        raise HTTPException(status_code=500, detail="Not healthy.")
    return {"status": 1}


@app.post("/be_healthy")
def switch_to_healthy():
    app.session["healthy"] = True  # type: ignore


@app.post("/be_unhealthy")
def switch_to_unhealthy():
    app.session["healthy"] = False  # type: ignore


@app.get("/property", response_model=dict[str, str])
def get_property():
    return {"value": str(app.session["property"])}  # type: ignore


@app.post("/property")
def set_property(data: dict[str, str]):
    app.session["property"] = data["value"]  # type: ignore


@app.post("/property:store")
def store_given_absolute_path(data: dict[str, str]):
    # Normalize path using os.path.realpath to remove ".." and follow symlinks
    safe_path = os.path.realpath(data["value"])
    if not safe_path.startswith(str(SAFE_ROOT)):
        raise HTTPException(status_code=400, detail="Invalid path")
    Path(safe_path).parent.mkdir(parents=True, exist_ok=True)
    Path(safe_path).write_text(app.session["property"])  # type: ignore


@app.post("/property:restore")
def restore_given_absolute_path(data: dict[str, str]):
    # Normalize path using os.path.realpath to remove ".." and follow symlinks
    safe_path = os.path.realpath(data["value"])
    if not safe_path.startswith(str(SAFE_ROOT)):
        raise HTTPException(status_code=400, detail="Invalid path")
    app.session["property"] = Path(safe_path).read_text()  # type: ignore


@app.get("/version", response_model=dict[str, str])
def get_version():
    return {"value": str(app.session["version"])}  # type: ignore


@app.post("/harakiri")
def harakiri():
    proc = psutil.Process(os.getpid())
    proc.terminate()


@app.get("/get_pid", response_model=dict[str, int])
def get_pid():
    return {"value": os.getpid()}


@click.command()
@click.argument("port", type=int)
@click.option("--version", type=str, default="1")
def main(port: int, version: str):
    import uvicorn

    if version not in ["1", "2", "222"]:
        raise ValueError("Version must be one of '1', '2', or '222'.")

    # TODO: replace with correct fastapi-way of storing session data
    app.session = {  # type: ignore
        "property": DEFAULT_PROPERTY_VALUE,
        "version": version,
        "healthy": True,
    }

    uvicorn.run(app, host="0.0.0.0", port=port)  # type: ignore


if __name__ == "__main__":
    main()
