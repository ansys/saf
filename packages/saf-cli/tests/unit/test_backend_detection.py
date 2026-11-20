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

"""Test dependency backend detection for SAF solutions."""

from pathlib import Path
import re

import pytest

from ansys.saf.cli._solutions.backend_detection import (
    SolutionBackend,
    SolutionBackendError,
    parse_solution_backend,
)


def _write_pyproject(solution_root_dir: Path, content: str) -> None:
    (solution_root_dir / "pyproject.toml").write_text(content, encoding="utf-8")


def test_parse_uv_solution(tmp_path: Path) -> None:
    """Parse a UV project with a lockfile and expose its project metadata."""
    _write_pyproject(
        tmp_path,
        """
[project]
name = "ansys-saf-solution"
version = "0.1.0"
requires-python = ">=3.11,<3.15"

[dependency-groups]
desktop = ["ansys-saf-desktop-orchestrator>=1.0"]
ui = ["dash>=3.0"]
""",
    )
    (tmp_path / "uv.lock").touch()

    project = parse_solution_backend(tmp_path)

    assert project.backend is SolutionBackend.UV
    assert project.lockfile_path == tmp_path / "uv.lock"
    assert project.project_name == "ansys-saf-solution"
    assert project.project_version == "0.1.0"
    assert project.requires_python == ">=3.11,<3.15"
    assert project.dependency_groups == ("desktop", "ui")
    assert not project.uses_deprecated_backend


def test_parse_uv_solution_with_tool_uv_without_lockfile(tmp_path: Path) -> None:
    """Recognize a UV project from its metadata when the lockfile is absent."""
    _write_pyproject(
        tmp_path,
        """
[project]
name = "ansys-saf-solution"
version = "0.1.0"

[tool.uv]
package = true
""",
    )

    project = parse_solution_backend(tmp_path)

    assert project.backend is SolutionBackend.UV
    assert project.lockfile_path == tmp_path / "uv.lock"


def test_parse_uv_solution_with_empty_tool_uv_table(tmp_path: Path) -> None:
    """Recognize a UV project when the tool.uv table is empty."""
    _write_pyproject(
        tmp_path,
        """
[project]
name = "ansys-saf-solution"
version = "0.1.0"

[tool.uv]
""",
    )

    project = parse_solution_backend(tmp_path)

    assert project.backend is SolutionBackend.UV


def test_parse_poetry_solution(tmp_path: Path) -> None:
    """Parse a Poetry project with a lockfile and expose its legacy metadata."""
    _write_pyproject(
        tmp_path,
        """
[tool.poetry]
name = "ansys-saf-solution"
version = "0.1.0"

[tool.poetry.dependencies]
python = ">=3.11,<3.15"

[tool.poetry.group.ui]
optional = true

[tool.poetry.group.tests]
optional = true
""",
    )
    (tmp_path / "poetry.lock").touch()

    project = parse_solution_backend(tmp_path)

    assert project.backend is SolutionBackend.POETRY
    assert project.lockfile_path == tmp_path / "poetry.lock"
    assert project.project_name == "ansys-saf-solution"
    assert project.project_version == "0.1.0"
    assert project.requires_python == ">=3.11,<3.15"
    assert project.dependency_groups == ("ui", "tests")
    assert project.uses_deprecated_backend


def test_parse_poetry_solution_without_lockfile(tmp_path: Path) -> None:
    """Recognize a Poetry project and infer its expected lockfile path."""
    _write_pyproject(
        tmp_path,
        """
[tool.poetry]
name = "ansys-saf-solution"
version = "0.1.0"
""",
    )

    project = parse_solution_backend(tmp_path)

    assert project.backend is SolutionBackend.POETRY
    assert project.lockfile_path == tmp_path / "poetry.lock"


def test_parse_poetry_pep621_project(tmp_path: Path) -> None:
    """Recognize a Poetry 2 project that stores metadata in the PEP 621 project table."""
    _write_pyproject(
        tmp_path,
        """
[project]
name = "ansys-saf-solution"
version = "0.1.0"
requires-python = ">=3.11,<3.15"
dependencies = ["requests>=2"]

[dependency-groups]
ui = ["dash>=3.0"]

[build-system]
requires = ["poetry-core>=2.0.0"]
build-backend = "poetry.core.masonry.api"
""",
    )

    project = parse_solution_backend(tmp_path)

    assert project.backend is SolutionBackend.POETRY
    assert project.lockfile_path == tmp_path / "poetry.lock"
    assert project.project_name == "ansys-saf-solution"
    assert project.project_version == "0.1.0"
    assert project.requires_python == ">=3.11,<3.15"
    assert project.dependency_groups == ("ui",)
    assert project.uses_deprecated_backend


def test_parse_poetry_pep621_project_with_dynamic_metadata(tmp_path: Path) -> None:
    """Use Poetry metadata as a fallback for PEP 621 fields declared dynamically."""
    _write_pyproject(
        tmp_path,
        """
[project]
name = "ansys-saf-solution"
dynamic = ["version", "dependencies"]

[tool.poetry]
version = "0.1.0"

[tool.poetry.dependencies]
python = ">=3.11,<3.15"

[build-system]
requires = ["poetry-core>=2.0.0"]
build-backend = "poetry.core.masonry.api"
""",
    )

    project = parse_solution_backend(tmp_path)

    assert project.backend is SolutionBackend.POETRY
    assert project.project_name == "ansys-saf-solution"
    assert project.project_version == "0.1.0"
    assert project.requires_python == ">=3.11,<3.15"


def test_parse_poetry_python_dependency_table(tmp_path: Path) -> None:
    """Read the Python requirement from Poetry's structured dependency table."""
    _write_pyproject(
        tmp_path,
        """
[tool.poetry]
name = "ansys-saf-solution"
version = "0.1.0"

[tool.poetry.dependencies.python]
version = ">=3.11,<3.15"
""",
    )

    project = parse_solution_backend(tmp_path)

    assert project.requires_python == ">=3.11,<3.15"


def test_parse_mixed_solution_fails(tmp_path: Path) -> None:
    """Reject a project containing both UV and Poetry metadata or lockfiles."""
    _write_pyproject(
        tmp_path,
        """
[project]
name = "ansys-saf-solution"
version = "0.1.0"

[build-system]
requires = ["poetry-core>=2.0.0"]
build-backend = "poetry.core.masonry.api"
""",
    )
    (tmp_path / "uv.lock").touch()
    (tmp_path / "poetry.lock").touch()

    with pytest.raises(SolutionBackendError, match="Both UV and Poetry"):
        parse_solution_backend(tmp_path)


def test_parse_mixed_solution_without_project_table_fails(tmp_path: Path) -> None:
    """Reject mixed backend configuration even when the UV project table is incomplete."""
    _write_pyproject(
        tmp_path,
        """
[tool.uv]

[tool.poetry]
name = "ansys-saf-solution"
""",
    )

    with pytest.raises(SolutionBackendError, match="Both UV and Poetry"):
        parse_solution_backend(tmp_path)


def test_parse_poetry_project_with_pep621_and_tool_metadata(tmp_path: Path) -> None:
    """Recognize Poetry metadata split between PEP 621 and the Poetry tool table."""
    _write_pyproject(
        tmp_path,
        """
[project]
name = "ansys-saf-solution"
version = "0.1.0"

[tool.poetry]
packages = [{ include = "ansys_saf_solution" }]

[build-system]
requires = ["poetry-core>=2.0.0"]
build-backend = "poetry.core.masonry.api"
""",
    )

    project = parse_solution_backend(tmp_path)

    assert project.backend is SolutionBackend.POETRY
    assert project.project_name == "ansys-saf-solution"
    assert project.project_version == "0.1.0"


def test_parse_solution_without_supported_backend_fails(tmp_path: Path) -> None:
    """Reject a project that does not identify a supported dependency backend."""
    _write_pyproject(
        tmp_path,
        """
[project]
name = "ansys-saf-solution"
version = "0.1.0"
""",
    )

    with pytest.raises(SolutionBackendError, match="Unable to identify"):
        parse_solution_backend(tmp_path)


def test_parse_solution_with_invalid_toml_fails(tmp_path: Path) -> None:
    """Raise a solution project error when pyproject.toml contains invalid TOML."""
    _write_pyproject(tmp_path, "[project\nname = 'invalid'")

    with pytest.raises(SolutionBackendError, match=re.escape(f"Unable to parse '{tmp_path / 'pyproject.toml'}'")):
        parse_solution_backend(tmp_path)


def test_parse_solution_without_pyproject_fails(tmp_path: Path) -> None:
    """Raise an error when the solution does not contain pyproject.toml."""
    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"pyproject.toml not found in solution root directory '{tmp_path}'"),
    ):
        parse_solution_backend(tmp_path)
