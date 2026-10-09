# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#

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



from pathlib import Path
import shutil

SOLUTION_UI_PATH = Path.cwd() / "src" / "{{ cookiecutter.__solution_namespace_path }}" / "{{ cookiecutter.__solution_module_name }}" / "ui"  # noqa: E501
SOLUTION_UI_TESTS_PATH = Path.cwd() / "tests" / "unit" / "test_solution_ui.py"


def _remove_ui_files() -> None:
    if "{{ cookiecutter.__ui_framework }}" != "dash":  # pyright: ignore[reportUnnecessaryComparison]
        shutil.rmtree(SOLUTION_UI_PATH)


def _remove_ui_tests() -> None:
    if "{{ cookiecutter.__ui_framework }}" != "dash":  # pyright: ignore[reportUnnecessaryComparison]
        SOLUTION_UI_TESTS_PATH.unlink()


def _copy_poetry_lock():
    if "{{ cookiecutter.__ui_framework }}" == "dash":  # pyright: ignore[reportUnnecessaryComparison]
        shutil.copy(Path("lock_files") / "dash" / "poetry.lock", ".")
    else:
        shutil.copy(Path("lock_files") / "no_ui" / "poetry.lock", ".")
    shutil.rmtree("lock_files")


def main():
    _remove_ui_files()
    _copy_poetry_lock()
    _remove_ui_tests()


if __name__ == "__main__":
    main()
