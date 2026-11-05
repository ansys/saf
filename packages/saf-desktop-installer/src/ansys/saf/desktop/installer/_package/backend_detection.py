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

"""Detect the dependency backend used by a SAF solution."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import tomllib
from typing import Any, cast


class SolutionBackend(StrEnum):
    """Supported solution dependency backends."""

    UV = "uv"
    POETRY = "poetry"


class SolutionBackendError(ValueError):
    """Raised when a solution backend cannot be identified unambiguously."""


@dataclass(frozen=True)
class SolutionBackendInfo:
    """Backend and expected lockfile for a solution."""

    backend: SolutionBackend
    lockfile_path: Path


def detect_solution_backend(solution_root_dir: Path) -> SolutionBackendInfo:
    """Detect a solution's backend from its pyproject metadata and lockfiles."""
    root_dir = Path(solution_root_dir)
    pyproject_path = root_dir / "pyproject.toml"
    if not pyproject_path.is_file():
        raise FileNotFoundError(f"pyproject.toml not found in solution root directory '{root_dir}'.")

    try:
        with pyproject_path.open("rb") as pyproject_file:
            configuration: dict[str, Any] = tomllib.load(pyproject_file)
    except tomllib.TOMLDecodeError as error:
        raise SolutionBackendError(f"Unable to parse '{pyproject_path}': {error}") from error

    tool = _get_table(configuration, "tool", pyproject_path)
    build_system = _get_optional_table(configuration, "build-system", pyproject_path)
    build_system = _get_optional_table(configuration, "build-system", pyproject_path)
    poetry = _get_optional_table(tool, "poetry", pyproject_path)
    uv = _get_optional_table(tool, "uv", pyproject_path)

    uv_lockfile = root_dir / "uv.lock"
    poetry_lockfile = root_dir / "poetry.lock"
    has_uv_metadata = uv is not None or uv_lockfile.is_file()
    has_poetry_metadata = (
        poetry is not None or poetry_lockfile.is_file() or _uses_poetry_build_backend(build_system)
    )
    has_mixed_metadata = has_uv_metadata and has_poetry_metadata

    if has_mixed_metadata:
        raise SolutionBackendError(
            f"Both UV and Poetry project metadata were found in '{pyproject_path}'. "
            "A solution must use exactly one dependency-management backend.",
        )
    if has_uv_metadata:
        return SolutionBackendInfo(SolutionBackend.UV, uv_lockfile)
    if has_poetry_metadata:
        return SolutionBackendInfo(SolutionBackend.POETRY, poetry_lockfile)
    raise SolutionBackendError(
        f"Unable to identify a supported dependency backend in '{pyproject_path}'. "
        "Expected UV metadata ([tool.uv] or uv.lock) or Poetry metadata "
        "([tool.poetry], poetry.lock, or the Poetry build backend).",
    )


def _get_table(configuration: dict[str, Any], key: str, pyproject_path: Path) -> dict[str, Any]:
    value = configuration.get(key, {})
    if not isinstance(value, dict):
        raise SolutionBackendError(f"'{key}' must be a table in '{pyproject_path}'.")
    return cast("dict[str, Any]", value)


def _get_optional_table(
    configuration: dict[str, Any],
    key: str,
    pyproject_path: Path,
) -> dict[str, Any] | None:
    if key not in configuration:
        return None
    value = configuration[key]
    if not isinstance(value, dict):
        raise SolutionBackendError(f"'{key}' must be a table in '{pyproject_path}'.")
    return cast("dict[str, Any]", value)


def _uses_poetry_build_backend(build_system: dict[str, Any] | None) -> bool:
    if build_system is None:
        return False
    return build_system.get("build-backend") == "poetry.core.masonry.api"
