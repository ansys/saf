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

from pathlib import Path
import shutil
import sys

import pytest
from selenium.webdriver.chrome.webdriver import WebDriver

from ansys.saf.cli._config.const import (
    DEFAULT_SOLUTION_DISPLAY_NAME,
    DEFAULT_SOLUTION_NAME,
    DEFAULT_SOLUTION_NAMESPACE,
    DEFAULT_UI_FRAMEWORK,
    UI_FRAMEWORKS,
)
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._utilities.conversion import namespace_to_path, to_module_name
from ansys.saf.testing.selenium import wait_for_element_and_click, wait_for_text
from tests.e2e.conftest import (
    ExecuteCommand,
    ListSolutions,
    NewSolution,
    RunSolution,
    is_lint_dot_github_workflow_folder_successful,
    is_solution_registered,
    lint_scaffolded_solution,
    verify_generated_solution,
)
from tests.outcome_checks import check_scaffolded_solution_files, check_scaffolded_solution_structure


def _extract_solution_module_name(solution_dir: Path, namespace: str) -> str:
    """Extract solution module name from the solution directory structure."""
    namespace_path = namespace_to_path(namespace)
    src_module_path = solution_dir / "src" / namespace_path
    if src_module_path.exists():
        for item in src_module_path.iterdir():
            if item.is_dir() and (item / "solution").exists():
                return item.name
    return ""


def test_saf_new_solution_default(
    tmp_path: Path,
    new_solution: NewSolution,
    list_solutions: ListSolutions,
):
    """
    Test ``saf new`` accepting the default values to all prompts.
    Assert the prompt messages and its default values.
    Assert that the expected files are created, the solution generated is valid and the solution is registered in the
    CLI's database.
    """
    expected_solution_path = tmp_path / DEFAULT_SOLUTION_NAME
    assert not is_solution_registered(list_solutions(), expected_solution_path)
    assert not expected_solution_path.is_dir()

    # Create solution without parameters, accepting default values of prompts
    p = new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    output = "\n".join(p.output)
    assert (
        "\n".join(
            [
                "What is the solution name? [my_solution]: What is the solution display name? [My Solution]: What is the UI framework of the Solution?",  # noqa: E501
                "- dash",
                "- none",
                "Choose UI framework [dash]:",
            ],
        )
        in output
    )
    assert "What is the solution namespace? (e.g. myorg.apps) [saf.solutions]:" in output

    verify_generated_solution(
        list_solutions(),
        tmp_path,
        DEFAULT_SOLUTION_NAME,
        to_module_name(DEFAULT_SOLUTION_NAME),
        DEFAULT_SOLUTION_DISPLAY_NAME,
        DEFAULT_UI_FRAMEWORK,
        DEFAULT_SOLUTION_NAMESPACE,
    )


@pytest.mark.parametrize("ui_framework", UI_FRAMEWORKS)
def test_saf_new_solution_has_expected_structure(
    tmp_path: Path,
    new_solution: NewSolution,
    ui_framework: str,
    session_solution_namespace: str,
):
    """
    Test that ``saf new`` generates a solution with the expected file structure.

    Unlike the dynamic template scan in ``verify_generated_solution``, this test compares
    the generated solution against a hardcoded expected structure. This catches cases where
    an item is accidentally removed from the solution template.
    """
    solution_name = "my_test_solution"
    solution_module_name = "my_test_solution"
    new_solution(
        [
            "--solution-name",
            solution_name,
            "--solution-display-name",
            "My Test Solution",
            "--ui-framework",
            ui_framework,
            "--namespace",
            session_solution_namespace,
        ],
        cwd=tmp_path,
        input_str="\n",
    )
    # Uses default namespace
    check_scaffolded_solution_structure(
        tmp_path,
        solution_name,
        solution_module_name,
        ui_framework,
        session_solution_namespace,
    )


@pytest.mark.parametrize(
    ("solution_name", "namespace", "ui_framework"),
    [
        ("test_ansys_ns", "ansys.solutions", "dash"),  # backward compatibility: old namespace
        ("test_default_ns", "saf.solutions", "dash"),  # default namespace, accepts prompt default
        ("test_custom_ns", "mycompany.solutions", "dash"),  # custom 2-part namespace
        ("test_nested_ns", "org.dept.team.solutions", "none"),  # deeply nested namespace
    ],
)
def test_saf_new_solution_with_namespace(
    tmp_path: Path,
    new_solution: NewSolution,
    solution_name: str,
    namespace: str,
    ui_framework: str,
):
    """Test creating a solution with various namespaces (default, custom, nested)."""
    p = new_solution(
        args=["--solution-name", solution_name, "--namespace", namespace, "--ui-framework", ui_framework],
        cwd=tmp_path,
        input_str="\n",
        expected_return_code=0,
    )

    assert p.return_code == 0, f"saf new failed: {p.output}"

    solution_dir = tmp_path / solution_name
    assert solution_dir.is_dir(), f"Solution directory {solution_dir} was not created"

    module_name = _extract_solution_module_name(solution_dir, namespace)
    assert module_name, f"Could not find solution module under namespace {namespace}"

    # Verify the full scaffolded structure matches expected files for the namespace
    check_scaffolded_solution_structure(tmp_path, solution_name, module_name, ui_framework, namespace=namespace)

    check_scaffolded_solution_files(tmp_path, solution_name, module_name, ui_framework, namespace=namespace)

    namespace_path = namespace_to_path(namespace)
    expected_module_path = solution_dir / "src" / namespace_path / module_name
    assert expected_module_path.exists(), f"Expected module path {expected_module_path} does not exist"


def test_saf_new_solution_lint_github_workflow(
    tmp_path: Path,
    new_solution: NewSolution,
):
    """
    Test ``saf new`` accepting the default values to all prompts.
    Lint the .github/workflows directory of the solution.
    """
    is_actionlint_available = shutil.which("actionlint") is not None

    if not is_actionlint_available:
        pytest.skip("actionlint not available to run the test.")

    new_solution(input_str="\n\n\n\n", cwd=tmp_path)

    assert is_lint_dot_github_workflow_folder_successful(tmp_path, DEFAULT_SOLUTION_NAME)


def test_saf_new_solution_answering_prompts(tmp_path: Path, new_solution: NewSolution, list_solutions: ListSolutions):
    """
    Test ``saf new`` passing values to the prompts different than defaults.
    Assert that the expected files are created, the solution generated is valid and the solution is registered in the
    CLI's database.
    """
    solution_name = "my_test_solution"
    expected_solution_module_name = "my_test_solution"
    solution_display_name = "My Test Solution"
    solution_namespace = "myorg.apps"
    ui_framework = "none"
    assert solution_name != DEFAULT_SOLUTION_NAME
    assert solution_display_name != DEFAULT_SOLUTION_DISPLAY_NAME
    assert ui_framework != DEFAULT_UI_FRAMEWORK
    assert solution_namespace != DEFAULT_SOLUTION_NAMESPACE

    expected_solution_path = tmp_path / solution_name
    assert not is_solution_registered(list_solutions(), expected_solution_path)
    assert not expected_solution_path.is_dir()

    # Create solution providing custom parameters.
    new_solution(
        input_str=f"{solution_name}\n{solution_display_name}\n{ui_framework}\n{solution_namespace}\n",
        cwd=tmp_path,
    )

    verify_generated_solution(
        list_solutions(),
        tmp_path,
        solution_name,
        expected_solution_module_name,
        solution_display_name,
        ui_framework,
        namespace=solution_namespace,
    )


def test_saf_new_solution_with_partial_parameters(
    tmp_path: Path,
    new_solution: NewSolution,
    list_solutions: ListSolutions,
    session_solution_namespace: str,
):
    """
    Test ``saf new`` passing some parameters and answering the prompt for the rest.
    Assert that only the skipped parameters are prompted.
    Assert that the expected files are created, the solution generated is valid and the solution is registered in the
    CLI's database.
    """
    solution_name = "my_test_solution"
    expected_solution_module_name = "my_test_solution"
    ui_framework = "none"
    assert solution_name != DEFAULT_SOLUTION_NAME
    assert ui_framework != DEFAULT_UI_FRAMEWORK

    expected_solution_path = tmp_path / solution_name
    assert not is_solution_registered(list_solutions(), expected_solution_path)
    assert not expected_solution_path.is_dir()

    # Create solution without parameters, accepting default values of prompts
    p = new_solution(
        ["--solution-name", solution_name, "--ui-framework", ui_framework, "--namespace", session_solution_namespace],
        input_str="\n",
        cwd=tmp_path,
    )
    assert "\n".join(["What is the solution display name? [My Solution]:"]) in "\n".join(p.output)

    verify_generated_solution(
        list_solutions(),
        tmp_path,
        solution_name,
        expected_solution_module_name,
        DEFAULT_SOLUTION_DISPLAY_NAME,
        ui_framework,
        namespace=session_solution_namespace,
    )


@pytest.mark.parametrize("ui_framework", ["none", "dash"])
def test_saf_new_solution_with_only_parameters(
    tmp_path: Path,
    new_solution: NewSolution,
    list_solutions: ListSolutions,
    ui_framework: str,
    session_solution_namespace: str,
):
    """
    Test ``saf new`` with parameters solution-name, solution-display-name and ui-framework.
    For every execution, assert that the expected files are created, the solution generated is valid
    and the solution is registered in the CLI's database.
    """
    solution_name = "my_test_solution"
    expected_solution_module_name = "my_test_solution"
    solution_display_name = "My Test Solution"
    assert solution_name != DEFAULT_SOLUTION_NAME
    assert solution_display_name != DEFAULT_SOLUTION_DISPLAY_NAME

    expected_solution_path = tmp_path / solution_name
    assert not is_solution_registered(list_solutions(), expected_solution_path)
    assert not expected_solution_path.is_dir()

    # Create solution
    new_solution(
        [
            "--solution-name",
            solution_name,
            "--solution-display-name",
            solution_display_name,
            "--namespace",
            session_solution_namespace,
            "--ui-framework",
            ui_framework,
        ],
        cwd=tmp_path,
        input_str="\n",
    )

    verify_generated_solution(
        list_solutions(),
        tmp_path,
        solution_name,
        expected_solution_module_name,
        solution_display_name,
        ui_framework,
        namespace=session_solution_namespace,
    )


@pytest.mark.skip(
    reason="There is a mismatch between the black dependency and pre-commit's black, making this test to fail.",
)
@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", UI_FRAMEWORKS, indirect=True)
def test_saf_new_solution_is_properly_linted(
    session_solution: SolutionRegistry,
    session_solution_ui_framework: str,
    session_solution_namespace: str,
):
    """
    Test ``saf new`` for every UI framework and assert that the solution files are properly linted.
    """
    if session_solution_ui_framework == "none":
        # FIXME: No UI framework generates a few empty lines
        with pytest.raises(AssertionError):
            lint_scaffolded_solution(session_solution.root_dir, session_solution.name, session_solution_namespace)
    else:
        lint_scaffolded_solution(session_solution.root_dir, session_solution.name, session_solution_namespace)


def test_saf_new_solution_into_existing_dir_raises_error(tmp_path: Path, new_solution: NewSolution):
    """
    Test that creating a solution that would overwrite an existing solution raises an exception and doesn't overwrite
    the existing dir.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    solution_path = tmp_path / DEFAULT_SOLUTION_NAME
    (solution_path / "dummy_file").touch()
    p = new_solution(input_str="\n\n\n\n", cwd=tmp_path, expected_return_code=1)
    assert f"FileExistsError: A file or directory already exists at {solution_path}" in p.output
    assert (solution_path / "dummy_file").is_file()


def test_saf_new_solution_into_solution_present_in_db_but_removed_dir(
    tmp_path: Path,
    new_solution: NewSolution,
    list_solutions: ListSolutions,
):
    """
    Test that when a solution is present in the database but its directory has been removed,
    recreating it keeps the registry consistent.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    verify_generated_solution(
        list_solutions(),
        tmp_path,
        DEFAULT_SOLUTION_NAME,
        to_module_name(DEFAULT_SOLUTION_NAME),
        DEFAULT_SOLUTION_DISPLAY_NAME,
        DEFAULT_UI_FRAMEWORK,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    solution_path = tmp_path / DEFAULT_SOLUTION_NAME
    shutil.rmtree(solution_path)
    assert not solution_path.exists()
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    verify_generated_solution(
        list_solutions(),
        tmp_path,
        DEFAULT_SOLUTION_NAME,
        to_module_name(DEFAULT_SOLUTION_NAME),
        DEFAULT_SOLUTION_DISPLAY_NAME,
        DEFAULT_UI_FRAMEWORK,
        DEFAULT_SOLUTION_NAMESPACE,
    )


def test_saf_new_solution_into_solution_present_in_db_but_removed_dir_with_different_display_name(
    tmp_path: Path,
    new_solution: NewSolution,
    list_solutions: ListSolutions,
):
    """
    Test that a solution whose directory has been removed but is still present in the database can be recreated
    with the same name but a different display name.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    verify_generated_solution(
        list_solutions(),
        tmp_path,
        DEFAULT_SOLUTION_NAME,
        to_module_name(DEFAULT_SOLUTION_NAME),
        DEFAULT_SOLUTION_DISPLAY_NAME,
        DEFAULT_UI_FRAMEWORK,
        DEFAULT_SOLUTION_NAMESPACE,
    )
    solution_path = tmp_path / DEFAULT_SOLUTION_NAME
    shutil.rmtree(solution_path)
    assert not solution_path.exists()
    expected_solution_display_name = "Different Display Name"
    new_solution(["--solution-display-name", expected_solution_display_name], input_str="\n\n\n", cwd=tmp_path)
    verify_generated_solution(
        list_solutions(),
        tmp_path,
        DEFAULT_SOLUTION_NAME,
        to_module_name(DEFAULT_SOLUTION_NAME),
        expected_solution_display_name,
        DEFAULT_UI_FRAMEWORK,
        DEFAULT_SOLUTION_NAMESPACE,
    )


def test_saf_new_solution_invalid_name_raises_error(tmp_path: Path, new_solution: NewSolution):
    """
    Test that creating a solution with an invalid name raises an exception and nothing is created
    """
    invalid_name = "hell/o"
    p = new_solution(["--solution-name", invalid_name], cwd=tmp_path, input_str="\n\n\n", expected_return_code=1)
    assert "Value error, Solution name contains invalid characters:" in "\n".join(p.output)
    assert not (tmp_path / invalid_name).exists()


def test_saf_new_solution_extra_argument_raises_error(tmp_path: Path, new_solution: NewSolution):
    """
    Test that creating a solution with an extra argument raises an exception before prompting.
    """
    p = new_solution(["extra_argument"], cwd=tmp_path, expected_return_code=2)
    saf_executable = f"saf{'.EXE' if sys.platform == 'win32' else ''}"
    expected_output = (
        f"Usage: {saf_executable} new [OPTIONS]\nTry '{saf_executable} new --help' for help.\n\n"
        "Error: Got unexpected extra argument (extra_argument)"
    )
    assert "\n".join(p.output) == expected_output
    assert not (tmp_path / DEFAULT_SOLUTION_NAME).exists()

    # even if other valid options are provided, the extra argument should still early raise the error
    p = new_solution(["--solution-name", "my_solution", "extra_argument"], cwd=tmp_path, expected_return_code=2)
    expected_output = (
        f"Usage: {saf_executable} new [OPTIONS]\nTry '{saf_executable} new --help' for help.\n\n"
        "Error: Got unexpected extra argument (extra_argument)"
    )
    assert "\n".join(p.output) == expected_output
    assert not (tmp_path / "my_solution").exists()


def test_saf_new_solution_invalid_option_raises_error(tmp_path: Path, new_solution: NewSolution):
    """
    Test that creating a solution with an invalid option raises an exception before prompting.
    """
    p = new_solution(["--wrong-option"], cwd=tmp_path, expected_return_code=2)

    saf_executable = f"saf{'.EXE' if sys.platform == 'win32' else ''}"
    expected_output = (
        f"Usage: {saf_executable} new [OPTIONS]\nTry "
        f"'{saf_executable} new --help' for help.\n\nError: No such option '--wrong-option'."
    )

    assert "\n".join(p.output) == expected_output
    assert not (tmp_path / DEFAULT_SOLUTION_NAME).exists()

    # even if other valid options are provided, the wrong option should still early raise the error
    p = new_solution(["--solution-name", "my_solution", "--wrong-option"], cwd=tmp_path, expected_return_code=2)
    expected_output = (
        f"Usage: {saf_executable} new [OPTIONS]\nTry "
        f"'{saf_executable} new --help' for help.\n\nError: No such option '--wrong-option'."
    )
    assert "\n".join(p.output) == expected_output
    assert not (tmp_path / "my_solution").exists()


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_built_documentation")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.parametrize("mode", ["prod", "dev", "no-doc"])
def test_saf_new_solution_includes_button_to_open_solution_documentation(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    execute_command: ExecuteCommand,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
    mode: str,
):
    """
    Test that the solution scaffolded with ``saf new`` includes a button in the UI to open the solution documentation.

    The button works for both scenarios: production, where the documentation is embedded in the solution's python
    module; development, where the documentation is generated at $cwd/doc/build/html.
    If the documentation is not available, it shows a warning message to the user.
    """
    expected_doc_file: Path | None = None
    if mode != "no-doc":
        command = "sphinx-build doc/source doc/build/html --color -vW -bhtml"
        execute_command([session_solution.name, command])
        expected_doc_file = session_solution.root_dir / "doc" / "build" / "html" / "index.html"
        if mode == "prod":
            # it should not be available at $cwd/doc/build/html, otherwise it would fallback to this location.
            namespace_path = namespace_to_path(session_solution_namespace)
            dest_dir = (
                session_solution.root_dir
                / "src"
                / namespace_path
                / session_solution.name.replace("-", "_")
                / "html-doc"
            )
            shutil.move(expected_doc_file.parent, dest_dir)
            expected_doc_file = dest_dir / "index.html"

    p = run_solution([session_solution.name])

    project_ui_url = p.get_solution_ui_url()
    session_selenium_webdriver.get(project_ui_url)
    wait_for_element_and_click(session_selenium_webdriver, "access-solution-doc")
    if mode != "no-doc":
        # TODO: assert logger.info(f"Opening documentation at {doc_index_path}") done by the UI server.
        assert 1
    else:
        wait_for_text(
            session_selenium_webdriver,
            "alerts-container",
            "WARNING\nSolution documentation is not available.",
        )
