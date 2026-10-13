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

"""Detect and describe dependency backends used by SAF solutions."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import tomllib
from typing import Any, cast


class SolutionBackend(StrEnum):
    """Supported dependency-management backends for SAF solutions."""

    UV = "uv"
    POETRY = "poetry"


class SolutionBackendError(ValueError):
    """Raised when a solution dependency backend cannot be classified or parsed."""


@dataclass(frozen=True)
class SolutionBackendInfo:
    """Parsed solution metadata used to select a dependency backend."""

    root_dir: Path
    backend: SolutionBackend
    lockfile_path: Path
    project_name: str | None
    project_version: str | None
    requires_python: str | None
    dependency_groups: tuple[str, ...]

    @property
    def uses_deprecated_backend(self) -> bool:
        """Return whether the solution uses the deprecated Poetry backend."""
        return self.backend is SolutionBackend.POETRY


def parse_solution_backend(solution_root_dir: Path) -> SolutionBackendInfo:
    """Parse a solution ``pyproject.toml`` and identify its backend.

    Parameters
    ----------
    solution_root_dir : pathlib.Path
        Root directory containing the solution's ``pyproject.toml``.

    Returns
    -------
    SolutionBackendInfo
        Parsed solution metadata and the selected dependency backend.

    Raises
    ------
    FileNotFoundError
        If the solution does not contain ``pyproject.toml``.
    SolutionBackendError
        If the TOML is invalid, the backend is ambiguous, or no supported
        backend can be identified.
    """
    root_dir = Path(solution_root_dir)
    pyproject_path = root_dir / "pyproject.toml"
    if not pyproject_path.is_file():
        raise FileNotFoundError(f"pyproject.toml not found in solution root directory '{root_dir}'.")

    try:
        with pyproject_path.open("rb") as pyproject_file:
            configuration = tomllib.load(pyproject_file)
    except tomllib.TOMLDecodeError as error:
        raise SolutionBackendError(f"Unable to parse '{pyproject_path}': {error}") from error

    tool = _get_table(configuration, "tool", pyproject_path)
    project = _get_optional_table(configuration, "project", pyproject_path)
    build_system = _get_optional_table(configuration, "build-system", pyproject_path)
    poetry = _get_optional_table(tool, "poetry", pyproject_path)
    uv = _get_optional_table(tool, "uv", pyproject_path)

    uv_lockfile_path = root_dir / "uv.lock"
    poetry_lockfile_path = root_dir / "poetry.lock"
    has_uv_metadata = uv is not None or uv_lockfile_path.is_file()
    has_poetry_metadata = (
        poetry is not None or poetry_lockfile_path.is_file() or _uses_poetry_build_backend(build_system)
    )
    has_mixed_metadata = has_uv_metadata and has_poetry_metadata

    if has_mixed_metadata:
        raise SolutionBackendError(
            f"Both UV and Poetry project metadata were found in '{pyproject_path}'. "
            "A solution must use exactly one dependency-management backend.",
        )
    if has_uv_metadata:
        return _build_uv_project(root_dir, project, configuration, uv_lockfile_path, pyproject_path)
    if has_poetry_metadata:
        return _build_poetry_project(
            root_dir,
            poetry,
            project,
            configuration,
            poetry_lockfile_path,
            pyproject_path,
        )

    raise SolutionBackendError(
        f"Unable to identify a supported dependency-management backend in '{pyproject_path}'. "
        "Expected a PEP 621 [project] with uv.lock or [tool.uv], "
        "or Poetry metadata ([tool.poetry], poetry.lock, or the Poetry build backend).",
    )


def _build_uv_project(
    root_dir: Path,
    project: dict[str, Any] | None,
    configuration: dict[str, Any],
    lockfile_path: Path,
    pyproject_path: Path,
) -> SolutionBackendInfo:
    if project is None:
        raise SolutionBackendError(f"Missing [project] metadata in '{pyproject_path}'.")

    dependency_groups_value = configuration.get("dependency-groups", {})
    if not isinstance(dependency_groups_value, dict):
        raise SolutionBackendError(f"'dependency-groups' must be a table in '{pyproject_path}'.")
    dependency_groups = cast(dict[str, Any], dependency_groups_value)

    return SolutionBackendInfo(
        root_dir=root_dir,
        backend=SolutionBackend.UV,
        lockfile_path=lockfile_path,
        project_name=_get_optional_string(project, "name", pyproject_path),
        project_version=_get_optional_string(project, "version", pyproject_path),
        requires_python=_get_optional_string(project, "requires-python", pyproject_path),
        dependency_groups=tuple(dependency_groups),
    )


def _build_poetry_project(
    root_dir: Path,
    poetry: dict[str, Any] | None,
    project: dict[str, Any] | None,
    configuration: dict[str, Any],
    lockfile_path: Path,
    pyproject_path: Path,
) -> SolutionBackendInfo:
    if poetry is None and project is None:
        raise SolutionBackendError(f"Missing Poetry project metadata in '{pyproject_path}'.")

    requires_python = _get_poetry_python_requirement(poetry, project, pyproject_path)
    group_names = _get_poetry_group_names(poetry, configuration, pyproject_path)

    project_name = _get_optional_string(project, "name", pyproject_path) if project is not None else None
    project_version = _get_optional_string(project, "version", pyproject_path) if project is not None else None
    if poetry is not None:
        project_name = project_name or _get_optional_string(poetry, "name", pyproject_path)
        project_version = project_version or _get_optional_string(poetry, "version", pyproject_path)

    return SolutionBackendInfo(
        root_dir=root_dir,
        backend=SolutionBackend.POETRY,
        lockfile_path=lockfile_path,
        project_name=project_name,
        project_version=project_version,
        requires_python=requires_python,
        dependency_groups=group_names,
    )


def _get_poetry_python_requirement(
    poetry: dict[str, Any] | None,
    project: dict[str, Any] | None,
    pyproject_path: Path,
) -> str | None:
    requires_python = _get_optional_string(project, "requires-python", pyproject_path) if project is not None else None
    if poetry is None:
        return requires_python

    dependencies_value = poetry.get("dependencies", {})
    if not isinstance(dependencies_value, dict):
        raise SolutionBackendError(f"'tool.poetry.dependencies' must be a table in '{pyproject_path}'.")
    dependencies = cast(dict[str, Any], dependencies_value)
    python_requirement: object = dependencies.get("python")
    if isinstance(python_requirement, dict):
        python_requirement = cast(dict[str, Any], python_requirement).get("version")
    if python_requirement is not None and not isinstance(python_requirement, str):
        raise SolutionBackendError(
            f"'tool.poetry.dependencies.python' must be a string or table with a version in '{pyproject_path}'.",
        )
    return requires_python or python_requirement


def _get_poetry_group_names(
    poetry: dict[str, Any] | None,
    configuration: dict[str, Any],
    pyproject_path: Path,
) -> tuple[str, ...]:
    poetry_groups: dict[str, Any] = {}
    if poetry is not None:
        groups_value = poetry.get("group", {})
        if not isinstance(groups_value, dict):
            raise SolutionBackendError(f"'tool.poetry.group' must be a table in '{pyproject_path}'.")
        poetry_groups = cast(dict[str, Any], groups_value)

    dependency_groups_value = configuration.get("dependency-groups", {})
    if not isinstance(dependency_groups_value, dict):
        raise SolutionBackendError(f"'dependency-groups' must be a table in '{pyproject_path}'.")
    dependency_groups = cast(dict[str, Any], dependency_groups_value)
    return tuple(dict.fromkeys((*poetry_groups, *dependency_groups)))


def _get_table(configuration: dict[str, Any], key: str, pyproject_path: Path) -> dict[str, Any]:
    value = configuration.get(key, {})
    if not isinstance(value, dict):
        raise SolutionBackendError(f"'{key}' must be a table in '{pyproject_path}'.")
    return cast(dict[str, Any], value)


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
    return cast(dict[str, Any], value)


def _get_optional_string(configuration: dict[str, Any], key: str, pyproject_path: Path) -> str | None:
    value = configuration.get(key)
    if value is not None and not isinstance(value, str):
        raise SolutionBackendError(f"'{key}' must be a string in '{pyproject_path}'.")
    return value


def _uses_poetry_build_backend(build_system: dict[str, Any] | None) -> bool:
    if build_system is None:
        return False
    return build_system.get("build-backend") == "poetry.core.masonry.api"
