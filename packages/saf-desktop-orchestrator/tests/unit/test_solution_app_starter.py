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


import importlib
from pathlib import Path
import re
import subprocess
import sys
import types
from zipfile import ZipFile

from _pytest.monkeypatch import MonkeyPatch
import pytest

from ansys.saf.desktop.orchestrator._scripts import solution_app_starter
from ansys.saf.desktop.orchestrator._scripts.solution_app_starter import (
    _resolve_solution_package,  # pyright: ignore[reportPrivateUsage]
)
from tests.conftest import copy_mock_solution_to_layout


def test_archived_solution_imports_without_repository_tests_package(tmp_path: Path):
    archive_path = Path(__file__).parent.parent / "mocks" / "solution_with_minimal_dash_ui.saf"
    with ZipFile(archive_path) as archive:
        archive.extractall(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import importlib, sys; sys.path.insert(0, sys.argv[1]); "
            "importlib.import_module('saf_desktop_orchestrator_e2e_fixture.solution_with_minimal_dash_ui.main')",
            str(tmp_path / "src"),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "namespace_root",
    [
        "my_namespace",
        "ansys.solutions",
        "synopsys.solutions.platform",
    ],
    ids=[
        "single_level_namespace",
        "legacy_ansys_namespace",
        "three_level_namespace",
    ],
)
def test_resolve_solution_package_supports_namespace_depth_variants(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    namespace_root: str,
):
    src_dir = tmp_path / "src"
    package_dir, expected_namespace_root_parts, expected_solution_name, module_name = copy_mock_solution_to_layout(
        src_dir,
        solution_name="solution_with_minimal_dash_ui",
        namespace_root=namespace_root,
    )

    monkeypatch.setattr(sys, "path", [str(src_dir), *sys.path])

    resolved_namespace_root_parts, resolved_solution_name = _resolve_solution_package(src_dir)

    assert resolved_namespace_root_parts == expected_namespace_root_parts
    assert resolved_solution_name == expected_solution_name

    imported_module = importlib.import_module(
        f"{'.'.join(resolved_namespace_root_parts)}.{resolved_solution_name}.main",
    )
    assert imported_module.__name__ == module_name
    assert Path(str(imported_module.__file__)).resolve() == (package_dir / "main.py").resolve()


def test_resolve_solution_package_raises_when_source_directory_is_missing(tmp_path: Path):
    missing_path = tmp_path / "missing"
    with pytest.raises(
        NotADirectoryError,
        match=re.escape(f"Solution source directory not found at {missing_path}"),
    ):
        _resolve_solution_package(missing_path)


def test_resolve_solution_package_raises_when_no_solution_is_found(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "main.py").write_text("print('not a package entrypoint')")

    expected_error = f"No solution module found under {src_dir}. Expected at least one package entrypoint."
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        _resolve_solution_package(src_dir)


def test_resolve_solution_package_raises_when_multiple_solutions_are_found(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
):
    src_dir = tmp_path / "src"
    (src_dir / "namespace" / "solutions" / "one").mkdir(parents=True)
    (src_dir / "namespace" / "solutions" / "one" / "main.py").write_text("value = 1")
    (src_dir / "other" / "solutions" / "two").mkdir(parents=True)
    (src_dir / "other" / "solutions" / "two" / "main.py").write_text("value = 2")

    monkeypatch.setattr(sys, "path", [str(src_dir), *sys.path])

    one_dir = src_dir / "namespace" / "solutions" / "one"
    two_dir = src_dir / "other" / "solutions" / "two"
    expected_error = (
        "Multiple importable solutions found:\n"
        f"- Found module namespace.solutions.one at {one_dir}\n"
        f"- Found module other.solutions.two at {two_dir}\n"
        "Only one solution is expected in the src directory."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        _resolve_solution_package(src_dir)


def test_resolve_solution_package_raises_when_module_cannot_be_imported(tmp_path: Path, monkeypatch: MonkeyPatch):
    src_dir = tmp_path / "src"
    _, namespace_root_parts, solution_name, _ = copy_mock_solution_to_layout(
        src_dir,
        solution_name="solution_with_minimal_dash_ui",
        namespace_root="testnamespace.solutions",
    )

    def _raise_module_not_found(_module_name: str) -> types.ModuleType:
        raise ModuleNotFoundError("boom")

    monkeypatch.setattr(solution_app_starter.importlib, "import_module", _raise_module_not_found)

    module_name = f"{'.'.join(namespace_root_parts)}.{solution_name}.main"
    expected_error = f"No importable solution module found under {src_dir}. Discovered: {module_name}."
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        _resolve_solution_package(src_dir)


def test_resolve_solution_package_ignores_non_importable_candidates(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
):
    src_dir = tmp_path / "src"
    _, expected_namespace_root_parts, expected_solution_name, _ = copy_mock_solution_to_layout(
        src_dir,
        solution_name="solution_with_minimal_dash_ui",
        namespace_root="valid.solutions",
    )
    invalid_solution_dir = src_dir / "invalid" / "solutions" / "broken"
    invalid_solution_dir.mkdir(parents=True)
    (invalid_solution_dir / "main.py").write_text("import definitely_missing_dependency")

    monkeypatch.setattr(sys, "path", [str(src_dir), *sys.path])

    resolved_namespace_root_parts, resolved_solution_name = _resolve_solution_package(src_dir)

    assert resolved_namespace_root_parts == expected_namespace_root_parts
    assert resolved_solution_name == expected_solution_name


def test_resolve_solution_package_raises_when_imported_module_points_to_different_file(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
):
    src_dir = tmp_path / "src"
    _, namespace_root_parts, solution_name, _ = copy_mock_solution_to_layout(
        src_dir,
        solution_name="solution_with_minimal_dash_ui",
        namespace_root="mismatch.solutions",
    )

    monkeypatch.setattr(sys, "path", [str(src_dir), *sys.path])
    wrong_main_path = tmp_path / "wrong_main.py"
    wrong_main_path.write_text("value = 1")

    def _import_wrong_module(_module_name: str) -> types.SimpleNamespace:
        return types.SimpleNamespace(__file__=str(wrong_main_path))

    monkeypatch.setattr(solution_app_starter.importlib, "import_module", _import_wrong_module)

    module_name = f"{'.'.join(namespace_root_parts)}.{solution_name}.main"
    expected_main_path = src_dir / Path(*module_name.split(".")).with_suffix(".py")
    expected_error = (
        f"Solution module {module_name} does not point to the correct solution file. "
        f"Imported {wrong_main_path.resolve()}, expected {expected_main_path.resolve()}."
    )
    with pytest.raises(ImportError, match=re.escape(expected_error)):
        _resolve_solution_package(src_dir)
