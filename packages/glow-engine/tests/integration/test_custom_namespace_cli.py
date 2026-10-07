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

"""Integration tests verifying that a GLOW server starts correctly when the solution lives in a
custom (non-ansys.solutions) Python namespace, configured via the GLOW_SOLUTION_DEFINITION and
GLOW_UI_MODULE environment variables."""

import os
from pathlib import Path
import shutil
import sys

import httpx2
import pytest

from ansys.saf.glow._utilities.ip_utilities import get_random_free_port
from ansys.saf.glow._utilities.solution_modules import (
    _AUTODISCOVERY_ENV_VARS_ERROR,  # pyright: ignore[reportPrivateUsage]
)
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.process import Process
from tests.conftest import MOCKS_DIR
from tests.integration.conftest import BasicGlowProcess

_SOLUTION_NAMESPACES: dict[str, tuple[str, ...]] = {
    "ansys": ("ansys", "solutions", "solution_with_ui_in_ansys"),
    "custom": ("my_namespace", "platform", "my_solution"),
}


def _setup_solution(root_path: Path, namespace: str) -> tuple[str, str]:
    """Copy ``solution_with_ui_in_ansys`` into the target namespace directory.

    The ``GLOW_SOLUTION_DEFINITION`` and ``GLOW_UI_MODULE`` values follow the
    standard GLOW layout: ``<base>.solution.definition`` and ``<base>.ui.app``
    where ``<base>`` is derived from the destination path parts.

    Returns the ``(definition_module, ui_module)`` strings for that namespace.
    """
    dest_parts = _SOLUTION_NAMESPACES[namespace]
    base = ".".join(dest_parts)
    definition_module = f"{base}.solution.definition"
    ui_module = f"{base}.ui.app"
    dest = root_path / "src" / Path(*dest_parts)
    shutil.copytree(MOCKS_DIR / "solution_with_ui_in_ansys", dest)
    return definition_module, ui_module


@pytest.fixture(
    scope="module",
    params=[
        pytest.param(("cli", "ansys"), id="cli-ansys"),
        pytest.param(("cli", "custom"), id="cli-custom"),
        pytest.param(("uvicorn", "ansys"), id="uvicorn-ansys"),
        pytest.param(("uvicorn", "custom"), id="uvicorn-custom"),
    ],
)
def glow_process(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> YieldFixture[BasicGlowProcess]:
    """Start a GLOW API server for every combination of launch mode and solution namespace.

    Combinations:

    * ``cli-ansys``   - ``glow api --definition`` with an ``ansys.solutions.*`` module
    * ``cli-custom``  - ``glow api --definition`` with a custom-namespace module
    * ``uvicorn-ansys`` - direct uvicorn with ``GLOW_SOLUTION_DEFINITION`` set to ``ansys.solutions.*``
    * ``uvicorn-custom`` - direct uvicorn with ``GLOW_SOLUTION_DEFINITION`` set to a custom namespace
    """
    launch_mode, namespace = request.param
    root = Path(tmp_path_factory.mktemp(f"{namespace}_{launch_mode}"))
    definition_module, ui_module = _setup_solution(root, namespace)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    env["GLOW_SOLUTION_DEFINITION"] = definition_module
    # GLOW_UI_MODULE must be explicit so the autodiscovery factory is not called.
    env["GLOW_UI_MODULE"] = ui_module

    match launch_mode:
        case "cli":
            args = [sys.executable, "-m", "ansys.saf.glow.cli", "api", "--definition", definition_module]
        case "uvicorn":
            args = [sys.executable, "-m", "uvicorn", "ansys.saf.glow.api:app"]
        case _:
            raise ValueError(f"Unsupported launch mode: {launch_mode!r}")

    proc = BasicGlowProcess.run(args, cwd=root, env=env)
    yield proc
    proc.stop()


def test_custom_namespace_server_is_healthy(glow_process: BasicGlowProcess) -> None:
    """A GLOW server launched with a solution in a custom namespace must respond healthy.

    This covers both the ``glow api --definition`` CLI path and the direct
    ``uvicorn ansys.saf.glow.api:app`` path, each parameterised by the
    ``glow_process`` fixture.
    """
    glow_process.wait_for_healthy()
    response = httpx2.get(f"http://localhost:{glow_process.port}/health")
    assert response.status_code == 200


def test_custom_namespace_can_create_project(glow_process: BasicGlowProcess) -> None:
    """Project creation must succeed, confirming the custom namespace solution was loaded correctly."""
    glow_process.wait_for_healthy()
    response = httpx2.post(
        f"http://localhost:{glow_process.port}/projects",
        json={"display_name": "test_custom_namespace"},
    )
    assert response.status_code == 200


@pytest.fixture(scope="module", params=["cli", "uvicorn"])
def glow_process_no_env(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Process:
    """Launch a server with NO env vars and NO ansys.solutions in PYTHONPATH.

    The process is expected to fail immediately.  Using ``bg=False`` so the
    fixture blocks until the process exits and captures the full output.
    """
    root = Path(tmp_path_factory.mktemp(f"no_env_{request.param}"))

    env = os.environ.copy()
    env.pop("GLOW_SOLUTION_DEFINITION", None)
    env.pop("GLOW_UI_MODULE", None)
    # Replace PYTHONPATH with an empty directory so that ansys.solutions is not findable.
    env["PYTHONPATH"] = str(root)

    match request.param:
        case "cli":
            # No --definition and no --solution → autodiscovery path in CLI
            args = [sys.executable, "-m", "ansys.saf.glow.cli", "api"]
        case "uvicorn":
            # Direct uvicorn import → Settings created at module import time
            port = get_random_free_port()
            args = [sys.executable, "-m", "uvicorn", "ansys.saf.glow.api:app", "--port", str(port)]
        case _:
            raise ValueError(f"Unsupported launch mode: {request.param!r}")

    proc = Process(args, env=env, cwd=root, bg=False)
    proc.start()  # blocks until the (failing) process exits
    return proc


def test_server_fails_when_no_env_vars_and_ansys_solutions_unavailable(
    glow_process_no_env: Process,
) -> None:
    """Server must exit with a non-zero code and surface a clear error message when neither
    GLOW_SOLUTION_DEFINITION nor ansys.solutions is available.
    """
    assert glow_process_no_env.return_code != 0, (
        f"Process was expected to fail but exited with code 0.\nOutput:\n{glow_process_no_env.output}"
    )
    assert glow_process_no_env.find_msg_in_output(_AUTODISCOVERY_ENV_VARS_ERROR) is not None, (
        f"Expected error message {_AUTODISCOVERY_ENV_VARS_ERROR!r} not found in process output:\n"
        f"{glow_process_no_env.output}"
    )
