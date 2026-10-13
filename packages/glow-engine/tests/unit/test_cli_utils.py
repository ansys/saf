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
import os
from pathlib import Path
import py_compile
import re
import shutil
import sys
from unittest import mock
from unittest.mock import patch
import uuid

import pytest

from ansys.saf.glow._utilities.solution_modules import (
    _AUTODISCOVERY_ENV_VARS_ERROR,  # pyright: ignore[reportPrivateUsage]
    _convert_module_path_to_module_str,  # pyright: ignore[reportPrivateUsage]
    _get_import_from_main_module,  # pyright: ignore[reportPrivateUsage]
    _verify_main_module,  # pyright: ignore[reportPrivateUsage]
    find_solution_name,
    get_autodiscovery_definition_module_str,
    get_autodiscovery_ui_module_str,
    get_main_module,
)
from ansys.saf.testing.platform_specific import windows_only
from tests.conftest import IGNORE_PYC_FILES, MOCKS_DIR, SOLUTIONS_MOCKS_DIR


@pytest.fixture(autouse=True)
def clean_env():
    # Tested functions internally import modules, modify the sys.path/sys.modules and environment variables
    # such as GLOW_SOLUTION_NAME, _URL, _HOST, _PORT... Clean it up between tests
    old_paths = sys.path.copy()
    old_modules = sys.modules.copy()
    with (
        mock.patch.dict(os.environ, os.environ.copy()),
        patch("ansys.saf.glow.cli._cli_entry_point.run_ui"),
        patch(
            "ansys.saf.glow.cli._cli_entry_point.run_api",
        ),
    ):
        yield
    sys.path = old_paths
    sys.modules = old_modules


def write_python_module(tmp_path: Path, file_content: str, compiled: bool = False) -> tuple[str, Path]:
    module_path = tmp_path / "ansys" / "solutions" / str(uuid.uuid4()) / "my_file.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(file_content)
    if compiled:
        module_path_compiled = module_path.with_name("my_file_compiled.pyc")
        py_compile.compile(str(module_path), str(module_path_compiled))
        return _convert_module_path_to_module_str(str(module_path_compiled)), module_path_compiled
    else:
        return _convert_module_path_to_module_str(str(module_path)), module_path


def copy_solution(orig_dir: Path, dest_dir: Path):
    shutil.copytree(orig_dir, dest_dir, dirs_exist_ok=True, ignore=IGNORE_PYC_FILES)


def test_get_import_module_regular_import(tmp_path: Path):
    module_str, module_path = write_python_module(tmp_path, "import my_solution.definition")
    with pytest.raises(ModuleNotFoundError, match="No module named 'my_solution'"):
        # importlib-based solutions require modules to be available,
        # in comparison, cli.utils do not execute the code.
        importlib.import_module(module_str)
    assert _get_import_from_main_module(module_str, "definition", module_path) == "my_solution.definition"


def test_get_import_module_regular_import_as_import(tmp_path: Path):
    module_str, module_path = write_python_module(tmp_path, "import my_solution.custom_definition as definition")
    assert _get_import_from_main_module(module_str, "definition", module_path) == "my_solution.custom_definition"


def test_get_import_module_from_import(tmp_path: Path):
    module_str, module_path = write_python_module(tmp_path, "from my_solution import definition")
    assert _get_import_from_main_module(module_str, "definition", module_path) == "my_solution.definition"


def test_get_import_module_from_import_as_import(tmp_path: Path):
    module_str, module_path = write_python_module(tmp_path, "from my_solution import custom_definition as definition")
    assert _get_import_from_main_module(module_str, "definition", module_path) == "my_solution.custom_definition"


@pytest.mark.parametrize("compiled", [False, True])
@pytest.mark.parametrize("validate", [False, True])
@pytest.mark.parametrize("provide_path", [False, True])
def test_verify_glow_main_import(tmp_path: Path, compiled: bool, validate: bool, provide_path: bool):
    module_str, module_path = write_python_module(
        tmp_path,
        """
from ansys.saf.glow.runtime import glow_main
    """,
        compiled,
    )
    try:
        _verify_main_module(module_str, module_path if provide_path else None, validate)
    except Exception as e:
        pytest.fail(f"{e}")


@pytest.mark.parametrize("compiled", [False, True])
@pytest.mark.parametrize("validate", [False, True])
@pytest.mark.parametrize("provide_path", [False, True])
def test_verify_glow_main_import_with_other_imports(tmp_path: Path, compiled: bool, validate: bool, provide_path: bool):
    module_str, module_path = write_python_module(
        tmp_path,
        """
from ansys.saf.glow.runtime import glow_main
import junk
    """,
        compiled,
    )
    if validate:
        with pytest.raises(RuntimeError, match="ModuleNotFoundError: No module named 'junk'"):
            _verify_main_module(module_str, module_path if provide_path else None, validate)
    else:
        try:
            _verify_main_module(module_str, module_path if provide_path else None, validate)
        except Exception as e:
            pytest.fail(f"{e}")


def test_solution_classname():
    solution_name = find_solution_name("tests.mocks.solutions.exceptions")
    assert solution_name == "ExceptionsSolution"


def test_solution_classname_compiled():
    orig_file = SOLUTIONS_MOCKS_DIR / "exceptions.py"
    assert orig_file.is_file()
    dest_file = orig_file.with_name("exceptions_compiled.pyc")
    assert not dest_file.exists()
    py_compile.compile(str(orig_file), str(dest_file))

    solution_name = find_solution_name("tests.mocks.solutions.exceptions_compiled")
    assert solution_name == "ExceptionsSolution"
    dest_file.unlink()


def test_convert_path_to_module_py():
    module = _convert_module_path_to_module_str("my_project/ansys/solutions/my_solution/my_file.py")
    assert module == "ansys.solutions.my_solution.my_file"


@windows_only()
def test_convert_path_to_module_py_windows():
    module = _convert_module_path_to_module_str(r"C:\\my_project\ansys\solutions\my_solution\my_file.py")
    assert module == "ansys.solutions.my_solution.my_file"


def test_convert_path_to_module_pyc():
    module = _convert_module_path_to_module_str("my_project/ansys/solutions/my_solution/my_file.pyc")
    assert module == "ansys.solutions.my_solution.my_file"


def test_convert_path_to_module_without_ansys_dir():
    with pytest.raises(RuntimeError, match=re.escape(_AUTODISCOVERY_ENV_VARS_ERROR)):
        _convert_module_path_to_module_str("my_project/ansys/my_solution/my_file.pyc")


def test_get_definition_module_str(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src_dir = tmp_path / str(uuid.uuid4())
    solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_without_ui_in_ansys"
    copy_solution(MOCKS_DIR / "solution_without_ui_in_ansys", solution_dir)
    monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
    definition_module_path = get_autodiscovery_definition_module_str()
    assert definition_module_path == "ansys.solutions.solution_without_ui_in_ansys.solution.definition"


def test_get_definition_module_str_rare_structure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src_dir = tmp_path / str(uuid.uuid4())
    solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_rare_structure_in_ansys"
    copy_solution(MOCKS_DIR / "solution_rare_structure_in_ansys", solution_dir)
    monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
    with pytest.raises(RuntimeError) as e:
        get_autodiscovery_definition_module_str()
    assert e.match(
        "Failed to find a viable solution entry point.\nNone of the following directories contain main.py or "
        "main.pyc files:",
    )
    assert e.match("Correct the above errors or use the '--solution' option to specify a solution entry point module.")


def test_get_definition_module_str_compiled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src_dir = tmp_path / str(uuid.uuid4())
    solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_without_ui_in_ansys"
    copy_solution(MOCKS_DIR / "solution_without_ui_in_ansys", solution_dir)
    monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
    for file in solution_dir.rglob("*"):
        if file.is_file() and file.suffix == ".py":
            py_compile.compile(str(file), str(file.with_suffix(".pyc")))
            file.unlink()
    with pytest.raises(RuntimeError, match="The solution definition module cannot be found."):
        get_autodiscovery_definition_module_str()


def test_get_autodiscovery_definition_module_str_without_ansys_solutions():
    with patch("importlib.util.find_spec", return_value=None):  # noqa: SIM117
        with pytest.raises(
            RuntimeError,
            match=re.escape(_AUTODISCOVERY_ENV_VARS_ERROR),
        ):
            get_autodiscovery_definition_module_str()


def test_get_autodiscovery_ui_module_str(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src_dir = tmp_path / str(uuid.uuid4())
    solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_without_ui_in_ansys"
    copy_solution(MOCKS_DIR / "solution_without_ui_in_ansys", solution_dir)
    monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]

    assert get_autodiscovery_ui_module_str() == "ansys.solutions.solution_without_ui_in_ansys.ui.app"


def test_get_autodiscovery_ui_module_str_without_ansys_solutions():
    with patch("importlib.util.find_spec", return_value=None):
        assert get_autodiscovery_ui_module_str() is None


@pytest.mark.parametrize("validate", [True, False])
class TestGetMainModule:
    def test_get_main_module_with_solution_module(self, validate: bool):
        assert get_main_module("tests.mocks.solution_with_ui.main", validate) == "tests.mocks.solution_with_ui.main"

    def test_get_main_module_with_solution_compiled_module(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "compiled_mocks" / "solution_with_ui"
        copy_solution(MOCKS_DIR / "solution_with_ui", solution_dir)
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        for file in solution_dir.rglob("*"):
            if file.is_file() and file.suffix == ".py":
                py_compile.compile(str(file), str(file.with_suffix(".pyc")))
                file.unlink()
        assert (
            get_main_module("compiled_mocks.solution_with_ui.main", validate) == "compiled_mocks.solution_with_ui.main"
        )

    def test_get_main_module_with_solution_path(self, validate: bool, tmp_path: Path):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_with_ui_in_ansys"
        copy_solution(MOCKS_DIR / "solution_with_ui_in_ansys", solution_dir)
        assert (
            get_main_module(str(solution_dir / "main.py"), validate) == "ansys.solutions.solution_with_ui_in_ansys.main"
        )

    def test_get_main_module_with_solution_compiled_path(self, validate: bool, tmp_path: Path):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_with_ui_in_ansys"
        copy_solution(MOCKS_DIR / "solution_with_ui_in_ansys", solution_dir)
        for file in solution_dir.rglob("*"):
            if file.is_file() and file.suffix == ".py":
                py_compile.compile(str(file), str(file.with_suffix(".pyc")))
                file.unlink()
        assert (
            get_main_module(str(solution_dir / "main.pyc"), validate)
            == "ansys.solutions.solution_with_ui_in_ansys.main"
        )

    def test_get_main_module_with_autodiscovery(self, validate: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_with_ui_in_ansys"
        copy_solution(MOCKS_DIR / "solution_with_ui_in_ansys", solution_dir)
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        assert get_main_module(validate_module=validate) == "ansys.solutions.solution_with_ui_in_ansys.main"

    def test_get_main_module_with_autodiscovery_compiled(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_with_ui_in_ansys"
        copy_solution(MOCKS_DIR / "solution_with_ui_in_ansys", solution_dir)
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        for file in solution_dir.rglob("*"):
            if file.is_file() and file.suffix == ".py":
                py_compile.compile(str(file), str(file.with_suffix(".pyc")))
                file.unlink()
        assert get_main_module(validate_module=validate) == "ansys.solutions.solution_with_ui_in_ansys.main"

    def test_get_main_module_with_autodiscovery_no_ansys_solutions(self, validate: bool):
        # Mock it because we may have dependencies in the tests group that are in the ansys.solutions namespace
        with patch("importlib.util.find_spec", return_value=None):  # noqa: SIM117
            with pytest.raises(RuntimeError, match="The package 'ansys.solutions' was not found."):
                get_main_module(validate_module=validate)

    def test_get_main_module_with_autodiscovery_empty_ansys_solutions(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions"
        solution_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]

        # Mocking the find_spec() result because we may have dependencies in the tests group that are in th
        # ansys.solutions namespace
        class MockSpec:
            submodule_search_locations = [str(solution_dir)]

        with patch("importlib.util.find_spec", return_value=MockSpec), pytest.raises(RuntimeError) as e:
            get_main_module(validate_module=validate)
        assert e.match(
            "Failed to find a viable solution entry point.\nThere are no solutions defined within ansys.solutions.\n"
            "Create a 'main' module in a package within 'ansys.solutions'.",
        )
        assert e.match(
            "Correct the above errors or use the '--solution' option to specify a solution entry point module.",
        )

    def test_get_main_module_with_autodiscovery_ansys_solutions_without_main(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_with_ui_in_ansys"
        copy_solution(MOCKS_DIR / "solution_with_ui_in_ansys", solution_dir)
        (solution_dir / "main.py").unlink()
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        with pytest.raises(RuntimeError) as e:
            get_main_module(validate_module=validate)
        assert e.match(
            "Failed to find a viable solution entry point.\nNone of the following directories contain main.py or "
            "main.pyc files:",
        )
        assert e.match(
            "Correct the above errors or use the '--solution' option to specify a solution entry point module.",
        )

    def test_get_main_module_with_autodiscovery_wrong_main(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "my_solution" / "main.py"
        solution_dir.parent.mkdir(parents=True, exist_ok=True)
        solution_dir.write_text("import pathlib")
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        with pytest.raises(RuntimeError) as e:
            get_main_module(validate_module=validate)
        assert e.match(
            "Failed to find a viable solution entry point.\nansys.solutions.my_solution.main does not contain a "
            "definition of glow_main which is callable.",
        )
        assert e.match(
            "Correct the above errors or use the '--solution' option to specify a solution entry point module.",
        )

    def test_get_main_module_with_autodiscovery_wrong_compiled_main(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "my_solution" / "main.py"
        solution_dir.parent.mkdir(parents=True, exist_ok=True)
        solution_dir.write_text("import pathlib")
        py_compile.compile(str(solution_dir), str(solution_dir.with_suffix(".pyc")))
        solution_dir.unlink()
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        if validate:
            with pytest.raises(RuntimeError) as e:
                get_main_module(validate_module=validate)
            assert e.match(
                "Failed to find a viable solution entry point.\nansys.solutions.my_solution.main does not contain a "
                "definition of glow_main which is callable.",
            )
            assert e.match(
                "Correct the above errors or use the '--solution' option to specify a solution entry point module.",
            )
        else:
            assert get_main_module(validate_module=validate) == "ansys.solutions.my_solution.main"

    def test_get_main_module_with_autodiscovery_multiple_solutions(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_without_ui_in_ansys"
        copy_solution(MOCKS_DIR / "solution_without_ui_in_ansys", solution_dir)
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "solution_with_ui_in_ansys"
        copy_solution(MOCKS_DIR / "solution_with_ui_in_ansys", solution_dir)
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        expected_error = (
            "Detected multiple solution entry points in ansys.solutions module. "
            "Use the '--solution' option to specify the solution entry point module that "
            "should be utilized."
        )
        with pytest.raises(RuntimeError, match=expected_error):
            get_main_module(validate_module=validate)

    def test_get_main_module_with_autodiscovery_unloadable_main(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "my_solution" / "main.py"
        orig_main = MOCKS_DIR / "solution_without_ui_in_ansys" / "main.py"
        solution_dir.parent.mkdir(parents=True, exist_ok=True)
        solution_dir.write_text(f"junk\n{orig_main.read_text()}")
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        if validate:
            with pytest.raises(RuntimeError) as e:
                get_main_module(validate_module=validate)
            assert e.match(
                "Failed to find a viable solution entry point.\nansys.solutions.my_solution.main could not be loaded.",
            )
            assert e.match('main.py", line 1, in <module>')
            assert e.match("NameError: name 'junk' is not defined")
            assert e.match(
                "Correct the above errors or use the '--solution' option to specify a solution entry point module.",
            )
        else:
            assert get_main_module(validate_module=validate) == "ansys.solutions.my_solution.main"

    def test_get_main_module_with_autodiscovery_missing_import(
        self,
        validate: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        src_dir = tmp_path / str(uuid.uuid4())
        solution_dir = src_dir / "src" / "ansys" / "solutions" / "my_solution" / "main.py"
        orig_main = MOCKS_DIR / "solution_without_ui_in_ansys" / "main.py"
        solution_dir.parent.mkdir(parents=True, exist_ok=True)
        solution_dir.write_text(f"import junk\n{orig_main.read_text()}")
        monkeypatch.syspath_prepend(str(src_dir / "src"))  # pyright: ignore[reportUnknownMemberType]
        if validate:
            with pytest.raises(RuntimeError) as e:
                get_main_module(validate_module=validate)
            assert e.match(
                "Failed to find a viable solution entry point.\nansys.solutions.my_solution.main could not be loaded.",
            )
            assert e.match("line 1, in <module>")
            assert e.match("import junk")
            assert e.match("ModuleNotFoundError: No module named 'junk'")
            assert e.match(
                "Correct the above errors or use the '--solution' option to specify a solution entry point module.",
            )
        else:
            assert get_main_module(validate_module=validate) == "ansys.solutions.my_solution.main"
