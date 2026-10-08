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

"""E2E tests verifying that GLOW operates correctly when a solution is loaded from a
custom (non-ansys.solutions) Python namespace via the GLOW_SOLUTION_DEFINITION and
GLOW_UI_MODULE environment variables.

Each test starts its own GLOW process via the ``run_glow`` fixture (function-scoped),
following the same pattern used in :mod:`test_solution_autodiscovery`.  Two namespace
variants are exercised:

* **ansys**  the canonical ``ansys.solutions.*`` namespace.
* **custom**  an arbitrary third-party namespace (``my_namespace.platform.my_solution``).
"""

from collections.abc import Callable
import os
from pathlib import Path
import shutil
import sys
from unittest import mock

import pytest

from ansys.saf.glow._utilities.solution_modules import (
    _AUTODISCOVERY_ENV_VARS_ERROR,  # pyright: ignore[reportPrivateUsage]
)
from ansys.saf.glow.client import Client
from ansys.saf.testing.solution.end_to_end import GlowDesktopProcess
from tests.conftest import MOCKS_DIR
from tests.mocks.solution_with_ui_in_ansys.solution.definition import MySolution

# Destination path parts (relative to src/) for each namespace under test.
# GLOW_SOLUTION_DEFINITION and GLOW_UI_MODULE values are derived at runtime as
# "<base>.solution.definition" and "<base>.ui.app" respectively.
_SOLUTION_NAMESPACES: dict[str, tuple[str, ...]] = {
    "ansys": ("ansys", "solutions", "solution_with_ui_in_ansys"),
    "custom": ("my_namespace", "platform", "my_solution"),
}


def _setup_namespace_solution(tmp_path: Path, namespace: str) -> tuple[str, str, Path, Path]:
    """Copy ``solution_with_ui_in_ansys`` into the target namespace directory.

    The ``GLOW_SOLUTION_DEFINITION`` and ``GLOW_UI_MODULE`` values follow the
    standard GLOW layout: ``<base>.solution.definition`` and ``<base>.ui.app``
    where ``<base>`` is derived from the destination path parts.

    Returns
    -------
    tuple[str, str, Path, Path]
        ``(definition_module, ui_module, src_dir, dest)`` where ``src_dir``
        is the directory to add to ``PYTHONPATH`` and ``dest`` is the copied
        solution directory passed to ``run_glow``.
    """
    dest_parts = _SOLUTION_NAMESPACES[namespace]
    base = ".".join(dest_parts)
    definition_module = f"{base}.solution.definition"
    ui_module = f"{base}.ui.app"
    src_dir = tmp_path / "src"
    dest = src_dir / Path(*dest_parts)
    shutil.copytree(MOCKS_DIR / "solution_with_ui_in_ansys", dest)
    return definition_module, ui_module, src_dir, dest


@pytest.mark.parametrize("namespace", list(_SOLUTION_NAMESPACES), ids=list(_SOLUTION_NAMESPACES))
def test_custom_namespace_server_is_healthy(
    namespace: str,
    run_glow: Callable[..., GlowDesktopProcess[MySolution]],
    tmp_path: Path,
) -> None:
    """Server started with GLOW_SOLUTION_DEFINITION pointing to a custom namespace must report healthy.

    This covers both the canonical ``ansys.solutions.*`` namespace and an
    arbitrary third-party namespace, verifying that the env-var-driven module
    loading path works end-to-end.
    """
    definition_module, ui_module, src_dir, dest = _setup_namespace_solution(tmp_path, namespace)

    with mock.patch.dict(
        os.environ,
        {
            "PYTHONPATH": os.pathsep.join(sys.path + [str(src_dir)]),
            "GLOW_SOLUTION_DEFINITION": definition_module,
            "GLOW_UI_MODULE": ui_module,
        },
    ):
        proc = run_glow(MySolution, dest, use_automatic_solution_locator=True)  # type: ignore[call-arg]

    assert proc.healthy


@pytest.mark.parametrize("namespace", list(_SOLUTION_NAMESPACES), ids=list(_SOLUTION_NAMESPACES))
def test_custom_namespace_can_run_transaction(
    namespace: str,
    run_glow: Callable[..., GlowDesktopProcess[MySolution]],
    get_glow_client: Callable[[GlowDesktopProcess[MySolution]], Client[MySolution]],
    tmp_path: Path,
) -> None:
    """Creating a project and running a transaction must succeed for a custom-namespace solution.

    This verifies the full client-server round-trip: the solution is loaded,
    a project is created via the GLOW client SDK, a transaction is executed,
    and the result is validated.
    """
    definition_module, ui_module, src_dir, dest = _setup_namespace_solution(tmp_path, namespace)

    with mock.patch.dict(
        os.environ,
        {
            "PYTHONPATH": os.pathsep.join(sys.path + [str(src_dir)]),
            "GLOW_SOLUTION_DEFINITION": definition_module,
            "GLOW_UI_MODULE": ui_module,
        },
    ):
        proc = run_glow(MySolution, dest, use_automatic_solution_locator=True)  # type: ignore[call-arg]

    client = get_glow_client(proc)  # type: ignore[call-arg]
    project = client.create_project("custom_namespace_test")
    project.steps.my_step.field_1 = 3.0
    project.steps.my_step.field_2 = 4.0
    project.steps.my_step.sum_fields()
    assert project.steps.my_step.result == 7.0


def test_server_fails_without_env_vars_and_no_ansys_solutions(
    run_glow: Callable[..., GlowDesktopProcess[MySolution]],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Server must be unhealthy and surface a clear error when neither
    ``GLOW_SOLUTION_DEFINITION`` nor ``ansys.solutions`` is available.

    Follows the same pattern as ``test_saf_run_solution_autodiscovery_with_multiple_solutions``:
    ``run_glow`` with ``use_automatic_solution_locator=True``, then assert
    ``not proc.healthy`` and check ``caplog.text`` for the expected message.

    ``run_glow`` starts GLOW via the CLI (``glow api``), which now converts
    ``_ANSYS_SOLUTIONS_NOT_FOUND_ERROR`` to ``_AUTODISCOVERY_ENV_VARS_ERROR`` — the same
    user-friendly message surfaced by the uvicorn path.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    with mock.patch.dict(os.environ, {"PYTHONPATH": str(src_dir)}):
        # Ensure autodiscovery env vars are absent within this block.
        os.environ.pop("GLOW_SOLUTION_DEFINITION", None)
        os.environ.pop("GLOW_UI_MODULE", None)
        proc = run_glow(MySolution, tmp_path, use_automatic_solution_locator=True)  # type: ignore[call-arg]

    assert not proc.healthy
    assert _AUTODISCOVERY_ENV_VARS_ERROR in caplog.text
