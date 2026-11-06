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

"""Test solution backend detection and invalid project handling."""

from pathlib import Path

import pytest

from ansys.saf.desktop.installer._package.backend_detection import (
    SolutionBackend,
    SolutionBackendError,
    detect_solution_backend,
)


def _write_pyproject(solution_root_dir: Path, content: str) -> None:
    """Write project metadata for a backend detection test."""
    (solution_root_dir / "pyproject.toml").write_text(content, encoding="utf-8")


def test_detect_uv_from_tool_table_and_returns_expected_lockfile(tmp_path: Path) -> None:
    """Recognize an empty tool.uv table even when uv.lock does not exist."""
    _write_pyproject(tmp_path, "[project]\nname = 'solution'\n\n[tool.uv]\n")

    result = detect_solution_backend(tmp_path)

    assert result.backend is SolutionBackend.UV
    assert result.lockfile_path == tmp_path / "uv.lock"


def test_detect_uv_from_lockfile(tmp_path: Path) -> None:
    """Recognize UV from its lockfile without a tool.uv table."""
    _write_pyproject(tmp_path, "[project]\nname = 'solution'\n")
    (tmp_path / "uv.lock").touch()

    result = detect_solution_backend(tmp_path)

    assert result.backend is SolutionBackend.UV
    assert result.lockfile_path == tmp_path / "uv.lock"


@pytest.mark.parametrize(
    "pyproject",
    [
        "[tool.poetry]\nname = 'solution'\n",
        "[project]\nname = 'solution'\n\n[build-system]\n"
        "requires = ['poetry-core']\nbuild-backend = 'poetry.core.masonry.api'\n",
    ],
)
def test_detect_poetry(tmp_path: Path, pyproject: str) -> None:
    """Recognize legacy Poetry metadata or a PEP 621 project using Poetry's build backend."""
    _write_pyproject(tmp_path, pyproject)

    result = detect_solution_backend(tmp_path)

    assert result.backend is SolutionBackend.POETRY
    assert result.lockfile_path == tmp_path / "poetry.lock"


def test_detect_poetry_from_lockfile(tmp_path: Path) -> None:
    """Recognize Poetry from its lockfile without Poetry-specific project metadata."""
    _write_pyproject(tmp_path, "[project]\nname = 'solution'\n")
    (tmp_path / "poetry.lock").touch()

    result = detect_solution_backend(tmp_path)

    assert result.backend is SolutionBackend.POETRY
    assert result.lockfile_path == tmp_path / "poetry.lock"


def test_detect_backend_rejects_mixed_metadata(tmp_path: Path) -> None:
    """Reject a project declaring both backends instead of choosing one silently."""
    _write_pyproject(tmp_path, "[tool.poetry]\nname = 'solution'\n\n[tool.uv]\n")

    with pytest.raises(SolutionBackendError, match="Both UV and Poetry"):
        detect_solution_backend(tmp_path)


def test_detect_backend_rejects_unknown_metadata(tmp_path: Path) -> None:
    """Reject a PEP 621 project without evidence of either supported backend."""
    _write_pyproject(tmp_path, "[project]\nname = 'solution'\n")

    with pytest.raises(SolutionBackendError, match="Unable to identify"):
        detect_solution_backend(tmp_path)


def test_detect_backend_requires_pyproject(tmp_path: Path) -> None:
    """Report a missing pyproject.toml before attempting backend detection."""
    with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
        detect_solution_backend(tmp_path)


def test_detect_backend_reports_invalid_toml(tmp_path: Path) -> None:
    """Report malformed TOML as a solution backend error."""
    _write_pyproject(tmp_path, "[project\n")

    with pytest.raises(SolutionBackendError, match="Unable to parse"):
        detect_solution_backend(tmp_path)
