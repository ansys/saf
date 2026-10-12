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

from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess

import httpx2
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import tomlkit

from ansys.saf.cli._config.const import (
    DEFAULT_SOLUTION_NAME,
    DEFAULT_SOLUTION_NAMESPACE,
    DEFAULT_STEP_NAME,
    DEFAULT_TEMPLATE_NAME,
    DEFAULT_UI_FRAMEWORK,
    UI_FRAMEWORKS,
)
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._utilities.conversion import namespace_to_path
from ansys.saf.testing.common import find_exec_in_venv
from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_element_and_click,
    wait_for_element_and_send_text,
    wait_for_expected_property,
)
from tests.e2e.conftest import (
    AddStep,
    ExecuteCommand,
    ListSolutions,
    NewSolution,
    RunSolution,
    is_solution_registered,
)
from tests.e2e.saf_process import SAFProcess


def _check_step_available_on_api(step_name: str, solution_proc: SAFProcess) -> None:
    solution_api_url = solution_proc.find_msg_in_output(r"Solution API: http://127\.0\.0\.1:\d+/docs", regex=True)
    assert solution_api_url
    solution_api_url = solution_api_url.removeprefix("INFO - Solution API: ")

    project_name = solution_proc.find_msg_in_output(r"- name: projects/[0-9a-f]+", regex=True)
    assert project_name

    project_api_url = solution_api_url.replace("/docs", f"/{project_name.removeprefix('- name: ')}")
    new_step_url = f"{project_api_url}/steps/{step_name.replace('_', '-')}"
    assert httpx2.get(new_step_url).status_code == 200


def _verify_step_added(
    solution_proc: SAFProcess,
    selenium_webdriver: WebDriver,
    solution_module_dir: Path,
    step_name: str,
    ui_framework: str,
):
    # Files exist at expected location
    assert (solution_module_dir / "solution" / f"{step_name}.py").is_file()
    ui_page_path = solution_module_dir / "ui" / "pages" / f"{step_name.replace('step', 'page')}.py"
    if ui_framework == "none":
        assert not ui_page_path.is_file()
    else:
        assert ui_page_path.is_file()

    # Step is available at the Solution API
    _check_step_available_on_api(step_name, solution_proc)

    # Step appears in the UI and it is functional
    if ui_framework != "none":
        project_ui_url = solution_proc.get_solution_ui_url()
        selenium_webdriver.get(project_ui_url)
        wait_for_element(selenium_webdriver, "page-content")
        step_display_name = step_name.replace("_", " ").title()
        wait_for_element_and_click(
            selenium_webdriver,
            f"//*[contains(text(), '{step_display_name}')]",
            element_type=By.XPATH,
        )
        wait_for_expected_property(selenium_webdriver, f"{step_name}-result", "value", "0", timeout=120)
        wait_for_element_and_send_text(selenium_webdriver, f"{step_name}-first-arg", "1")
        wait_for_element_and_send_text(selenium_webdriver, f"{step_name}-second-arg", "2")
        wait_for_element_and_click(selenium_webdriver, f"{step_name}-calculate")
        wait_for_expected_property(selenium_webdriver, f"{step_name}-result", "value", "3", timeout=120)

        # can also be navigated using URL
        selenium_webdriver.get(f"{project_ui_url}/{step_name.replace('_', '-')}")
        wait_for_element_and_click(
            selenium_webdriver,
            f"//*[contains(text(), '{step_display_name}')]",
            element_type=By.XPATH,
        )
        wait_for_expected_property(selenium_webdriver, f"{step_name}-result", "value", "3", timeout=120)


def _verify_step_not_added(solution_module_dir: Path, step_name: str):
    # Files don't exist at expected location
    assert not (solution_module_dir / "solution" / f"{step_name}.py").is_file()
    assert not (solution_module_dir / "ui" / "pages" / f"{step_name.replace('step', 'page')}.py").is_file()


@pytest.mark.parametrize("solution_param_type", [None, "relative", "absolute"])
@pytest.mark.parametrize("namespace", [None, "ansys.solutions", "myorg.apps"])
def test_add_step_non_registered_solutions(
    tmp_path: Path,
    database_path: Path,
    solution_param_type: str | None,
    namespace: str | None,
    new_solution: NewSolution,
    list_solutions: ListSolutions,
    add_step: AddStep,
):
    """
    Test that is possible to add a step to a solution that is not registered in the CLI's database. The solution should
    be added to DB and the process should work as expected.
    """
    # Pass namespace only if not None (to test default namespace behavior)
    new_solution_args = ["--namespace", namespace] if namespace else []
    new_solution_input = "\n\n\n\n" if namespace is None else "\n\n\n"
    new_solution(args=new_solution_args, input_str=new_solution_input, cwd=tmp_path)
    database_path.unlink()
    solution_path = tmp_path / DEFAULT_SOLUTION_NAME
    assert not is_solution_registered(list_solutions(), solution_path)

    if solution_param_type == "relative":
        add_step([f"./{solution_path.name}"], cwd=tmp_path, input_str="\n\n\n")
    elif solution_param_type == "absolute":
        add_step([solution_path.absolute().as_posix()], cwd=None, input_str="\n\n\n")
    elif not solution_param_type:
        add_step([""], cwd=solution_path, input_str="\n\n\n")
    else:
        raise ValueError(f"Invalid solution_param_type: {solution_param_type}")

    assert is_solution_registered(list_solutions(), solution_path, solution_name=solution_path.name)
    solution_module_name = DEFAULT_SOLUTION_NAME.replace("-", "_")
    # Use provided namespace or DEFAULT_SOLUTION_NAMESPACE if None
    effective_namespace = namespace or DEFAULT_SOLUTION_NAMESPACE
    namespace_path = Path(*effective_namespace.split("."))
    solution_module_dir = solution_path / "src" / namespace_path / solution_module_name
    assert (solution_module_dir / "solution" / f"{DEFAULT_STEP_NAME}.py").is_file()
    assert (solution_module_dir / "ui" / "pages" / f"{DEFAULT_STEP_NAME.replace('step', 'page')}.py").is_file()


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.parametrize("session_solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
def test_add_step_with_various_namespaces(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """
    Test adding a step to a solution with both default and custom namespaces.
    Verifies that steps are properly added, available in the API, and functional in the UI.
    """
    p = add_step([session_solution.name], input_str="\n\n\n")
    assert "\n".join(
        [
            "What is the Step name? [my_new_step]: What is the UI framework of the Solution?",
            "- dash",
            "- none",
            "Choose UI framework [dash]: What is the Step template name? [calculator-step]:",
        ],
    ) in "\n".join(p.output)
    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )
    # FIXME: imports added to definition.py and page.py are not sorted... probably better to skip them than trying to
    # fix them in the generation
    # lint_scaffolded_solution(tmp_path, DEFAULT_SOLUTION_NAME)


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_in_solution_with_package_name_different_from_solution_name(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """
    Test adding a step to an existing solution that has a package name different from the solution name.
    """
    solution_package_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    assert solution_package_dir.is_dir()
    new_solution_package_dir = solution_package_dir.parent / "different_package_name"
    shutil.move(solution_package_dir, new_solution_package_dir)
    for py_file in new_solution_package_dir.rglob("*.py"):
        content = py_file.read_text()
        if solution_package_dir.name in content:
            py_file.write_text(content.replace(solution_package_dir.name, new_solution_package_dir.name))
    p = add_step([session_solution.name], input_str="\n\n\n")
    assert "\n".join(
        [
            "What is the Step name? [my_new_step]: What is the UI framework of the Solution?",
            "- dash",
            "- none",
            "Choose UI framework [dash]: What is the Step template name? [calculator-step]:",
        ],
    ) in "\n".join(p.output)

    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        new_solution_package_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "cleanup_solution_poetry_lock",
    "cleanup_solution_venv",
    "install_custom_template_plugin",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_with_custom_step_with_several_dependencies(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """
    Test adding a step that contains main dependencies to an existing solution that contains no such dependencies
    adds these dependencies to the solution's pyproject.toml and installs them in the solution's virtual environment.
    """
    p = add_step([session_solution.name], input_str="\n\nseveral-deps-step\n")
    assert "\n".join(
        [
            "What is the Step name? [my_new_step]: What is the UI framework of the Solution?",
            "- dash",
            "- none",
            "Choose UI framework [dash]: What is the Step template name? [calculator-step]:",
        ],
    ) in "\n".join(p.output)

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )

    expected_dependencies = ["humanize", "msgpack"]
    solution_pyproject_path = session_solution.root_dir / "pyproject.toml"
    solution_pyproject_content = tomlkit.loads(solution_pyproject_path.read_bytes()).unwrap()
    solution_venv_python_exec = find_exec_in_venv(session_solution.root_dir, "python")
    for dependency in expected_dependencies:
        assert dependency in solution_pyproject_content["tool"]["poetry"]["dependencies"]
        assert subprocess.run([solution_venv_python_exec.as_posix(), "-m", "pip", "show", dependency]).returncode == 0
    expected_dependencies_text = (
        'humanize = "^4.15.0"\nmsgpack = {version = "^1.0.0", allow-prereleases = true}\n\n[tool.poetry.group.desktop]'
    )
    solution_pyproject_content_text = solution_pyproject_path.read_text()
    assert expected_dependencies_text in solution_pyproject_content_text


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "cleanup_solution_poetry_lock",
    "cleanup_solution_venv",
    "install_custom_template_plugin_with_glow_and_ui_deps",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_with_custom_step_with_several_dependencies_one_conflicting_one_new(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    execute_command: ExecuteCommand,
    session_selenium_webdriver: WebDriver,
):
    """
    Test adding a step that contains main and ui dependencies to an existing solution that already contains some of
    these dependencies adds the dependencies that are not in common, shows a warning with the dependencies in common
    and does not install anything in the solution's environment.
    """
    p = add_step([session_solution.name], input_str="\n\nsecond-step\n")
    assert "\n".join(
        [
            "What is the Step name? [my_new_step]: What is the UI framework of the Solution?",
            "- dash",
            "- none",
            "Choose UI framework [dash]: What is the Step template name? [calculator-step]:",
        ],
    ) in "\n".join(p.output)
    assert "Updating solution dependencies. Do not modify solution files until completion." in "\n".join(p.output)
    dependency_warning_content = (
        f"WARNING: the step template 'second-step' has some dependencies in common with the "
        f"solution's pyproject.toml at {session_solution.root_dir / 'pyproject.toml'}. Review the solution's "
        f"pyproject.toml and manually update it if necessary, to ensure that it is compatible with the step "
        f"template's dependencies.\n\n"
        f"Step specification of the common dependencies:\n"
        "  - ansys-saf-sdk (main): {'version': '^0.2.0', 'allow-prereleases': True, 'extras': ['core-hps']}\n\n"
        f"After reviewing the dependencies, please run:\n"
        f'  - saf execute {session_solution.name} "poetry lock"\n'
        f'  - saf execute {session_solution.name} "poetry install --with ui"'
    )
    assert dependency_warning_content in "\n".join(p.output)

    solution_venv_python_exec = find_exec_in_venv(session_solution.root_dir, "python")

    assert subprocess.run([solution_venv_python_exec.as_posix(), "-m", "pip", "show", "streamlit"]).returncode == 1

    pyproject_content = tomlkit.loads((session_solution.root_dir / "pyproject.toml").read_bytes()).unwrap()
    ui_deps = pyproject_content["tool"]["poetry"]["group"]["ui"]["dependencies"]
    assert "streamlit" in ui_deps
    assert ui_deps["streamlit"] == "^1.58.0"

    execute_command([session_solution.name, "poetry lock"])
    execute_command([session_solution.name, "poetry install --with ui"])

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )

    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )

    assert subprocess.run([solution_venv_python_exec.as_posix(), "-m", "pip", "show", "streamlit"]).returncode == 0


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "cleanup_solution_poetry_lock",
    "cleanup_solution_venv",
    "install_custom_template_plugin_with_new_dep_group",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_with_custom_step_with_new_dependency_group(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """
    Test adding a step that contains a new dependency group to an existing solution creates the new group in the
    solution's pyproject.toml and installs it given that it is not present in the solution's pyproject.toml.
    """
    p = add_step([session_solution.name], input_str="\n\nsecond-step\n")
    assert "\n".join(
        [
            "What is the Step name? [my_new_step]: What is the UI framework of the Solution?",
            "- dash",
            "- none",
            "Choose UI framework [dash]: What is the Step template name? [calculator-step]:",
        ],
    ) in "\n".join(p.output)
    assert "Updating solution dependencies. Do not modify solution files until completion." in "\n".join(p.output)

    pyproject_content = tomlkit.loads((session_solution.root_dir / "pyproject.toml").read_bytes()).unwrap()
    new_group_deps = pyproject_content["tool"]["poetry"]["group"]["new_group"]["dependencies"]
    assert "humanize" in new_group_deps
    assert new_group_deps["humanize"] == "^4.15.0"

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )

    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )

    solution_venv_python_exec = find_exec_in_venv(session_solution.root_dir, "python")

    assert subprocess.run([solution_venv_python_exec.as_posix(), "-m", "pip", "show", "humanize"]).returncode == 0


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "cleanup_solution_poetry_lock",
    "cleanup_solution_venv",
    "install_custom_template_plugin_with_glow_in_different_group",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_with_custom_step_with_several_dependencies_one_conflicting_in_different_groups(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    execute_command: ExecuteCommand,
    session_selenium_webdriver: WebDriver,
):
    """
    Test adding a step that contains main and ui dependencies to an existing solution that already contains some of
    these dependencies adds the dependencies that are not in common, shows a warning with the dependencies in common
    and does not install anything in the solution's environment.
    """
    p = add_step([session_solution.name], input_str="\n\nsecond-step\n")
    assert "\n".join(
        [
            "What is the Step name? [my_new_step]: What is the UI framework of the Solution?",
            "- dash",
            "- none",
            "Choose UI framework [dash]: What is the Step template name? [calculator-step]:",
        ],
    ) in "\n".join(p.output)
    assert "Updating solution dependencies. Do not modify solution files until completion." in "\n".join(p.output)
    dependency_warning_content = (
        f"WARNING: the step template 'second-step' has some dependencies in common with the "
        f"solution's pyproject.toml at {session_solution.root_dir / 'pyproject.toml'}. Review the solution's "
        f"pyproject.toml and manually update it if necessary, to ensure that it is compatible with the step "
        f"template's dependencies.\n\n"
        f"Step specification of the common dependencies:\n"
        "  - ansys-saf-sdk (another_group group): {'version': '^0.2.0', 'allow-prereleases': True, "
        "'extras': ['core-hps']}\n\n"
        f"After reviewing the dependencies, please run:\n"
        f'  - saf execute {session_solution.name} "poetry lock"\n'
        f'  - saf execute {session_solution.name} "poetry install --with another_group,ui"'
    )
    assert dependency_warning_content in "\n".join(p.output)

    solution_venv_python_exec = find_exec_in_venv(session_solution.root_dir, "python")

    assert subprocess.run([solution_venv_python_exec.as_posix(), "-m", "pip", "show", "streamlit"]).returncode == 1

    pyproject_content = tomlkit.loads((session_solution.root_dir / "pyproject.toml").read_bytes()).unwrap()
    assert "another_group" in pyproject_content["tool"]["poetry"]["group"]
    assert not pyproject_content["tool"]["poetry"]["group"]["another_group"]["dependencies"]
    ui_deps = pyproject_content["tool"]["poetry"]["group"]["ui"]["dependencies"]
    assert "streamlit" in ui_deps
    assert ui_deps["streamlit"] == "^1.58.0"

    execute_command([session_solution.name, "poetry lock"])
    execute_command([session_solution.name, "poetry install --with another_group,ui"])

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )

    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )

    assert subprocess.run([solution_venv_python_exec.as_posix(), "-m", "pip", "show", "streamlit"]).returncode == 0


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures("cleanup_solution_src", "install_custom_template_plugin_invalid_template")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_with_invalid_template(session_solution: SolutionRegistry, add_step: AddStep):
    expected_error_message = (
        "Template 'second-step' in plugin module 'ansys.saf.test_custom_templates_invalid_template' is invalid."
    )
    p = add_step([session_solution.name], input_str="\n\nsecond-step\n", expected_return_code=1)
    assert p.find_msg_in_output(expected_error_message)


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_with_non_existing_template(session_solution: SolutionRegistry, add_step: AddStep):
    expected_error_message = (
        "Could not find a valid template for template name 'non-existing-template'.\n"
        " - Run `saf templates` to list the available templates.\n"
        " - Run `saf templates --verbose` to include more details on plugin and template errors."
    )
    p = add_step([session_solution.name], input_str="\n\nnon-existing-template\n", expected_return_code=1)
    assert expected_error_message in "\n".join(p.output)


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", UI_FRAMEWORKS, indirect=True)
def test_add_multiple_steps_using_parameters(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
    session_solution_ui_framework: str,
):
    """
    Test adding a step to an existing solution passing information by parameters. Covers all possible options and
    UI frameworks and also adding multiple steps into the same solution.
    Assert that the steps are available in the solution UI / API.
    """
    step_name = "my_test_new_step"
    assert step_name != DEFAULT_STEP_NAME
    add_step(
        [
            session_solution.name,
            "--step-name",
            step_name,
            "--ui-framework",
            session_solution_ui_framework,
            "--template",
            DEFAULT_TEMPLATE_NAME,
        ],
    )

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        step_name,
        session_solution_ui_framework,
    )
    solution_proc.stop()

    # Add a second step
    another_step = "another_step"
    assert another_step != step_name
    assert another_step != DEFAULT_STEP_NAME
    add_step(
        [
            session_solution.name,
            "--step-name",
            another_step,
            "--ui-framework",
            session_solution_ui_framework,
            "--template",
            DEFAULT_TEMPLATE_NAME,
        ],
    )

    solution_proc = run_solution([session_solution.name])
    # TODO: merge with _verify_step_added, so transactions and navigations is tested always
    _check_step_available_on_api(another_step, solution_proc)
    if session_solution_ui_framework != "none":
        # Check that the new step is available in the UI and navigation works
        project_ui_url = solution_proc.get_solution_ui_url()

        session_selenium_webdriver.get(project_ui_url)
        wait_for_element(session_selenium_webdriver, "page-content")

        expected_result = "0"
        another_step_display_name = another_step.replace("_", " ").title()
        another_page_element = wait_for_element(
            session_selenium_webdriver,
            f"//*[contains(text(), '{another_step_display_name}')]",
            element_type=By.XPATH,
        )

        another_page_element.click()

        wait_for_expected_property(session_selenium_webdriver, "another_step-result", "value", expected_result)

        step_display_name = step_name.replace("_", " ").title()
        new_page_element = wait_for_element(
            session_selenium_webdriver,
            f"//*[contains(text(), '{step_display_name}')]",
            element_type=By.XPATH,
        )

        new_page_element.click()
        another_page_element.click()


def test_add_step_invalid_solution(tmp_path: Path, new_solution: NewSolution, add_step: AddStep):
    """
    Test adding a step to an existing solution that is invalid raises an error.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    shutil.rmtree(tmp_path / DEFAULT_SOLUTION_NAME)

    p = add_step([DEFAULT_SOLUTION_NAME], input_str="\n\n\n", cwd=tmp_path, expected_return_code=1)
    assert p.find_msg_in_output(f"NotADirectoryError: Solution not found at {str(tmp_path / DEFAULT_SOLUTION_NAME)}")


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_without_ui_to_solution_with_ui(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """
    Test adding a step with different framework than the existing solution does not create
    any files in the solution and does not modify any file, except when adding a no-ui step to a UI solution.
    """
    add_step([session_solution.name], input_str=f"{DEFAULT_STEP_NAME}\nnone\n\n")

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        "none",
    )


def test_add_step_with_ui_to_solution_without_ui(tmp_path: Path, new_solution: NewSolution, add_step: AddStep):
    """
    Test adding a step with different framework than the existing solution does not create
    any files in the solution and does not modify any file, except when adding a no-ui step to a UI solution.
    """
    new_solution(input_str="\n\nnone\n\n", cwd=tmp_path)
    p = add_step([DEFAULT_SOLUTION_NAME], input_str=f"{DEFAULT_STEP_NAME}\ndash\n\n", expected_return_code=1)
    assert p.find_msg_in_output(
        "RuntimeError: The step you are creating is using a different framework than the one "
        "you used to create the solution with.",
    )
    solution_module_dir = (
        tmp_path
        / DEFAULT_SOLUTION_NAME
        / "src"
        / namespace_to_path(DEFAULT_SOLUTION_NAMESPACE)
        / DEFAULT_SOLUTION_NAME.replace("-", "_")
    )
    assert solution_module_dir.is_dir()
    _verify_step_not_added(solution_module_dir, DEFAULT_STEP_NAME)


def test_add_step_multiple_solutions_same_name_invalid_solution(
    tmp_path: Path,
    new_solution: NewSolution,
    add_step: AddStep,
):
    """
    Test adding a step to an existing solution that has the same name as other that is invalid.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    (tmp_path / "another_solution").mkdir()
    new_solution(input_str="\n\n\n\n", cwd=(tmp_path / "another_solution"))
    shutil.rmtree(tmp_path / "another_solution")

    p = add_step([DEFAULT_SOLUTION_NAME], input_str="\n\n\n")
    assert "\n".join(
        [
            "What is the Step name? [my_new_step]: What is the UI framework of the Solution?",
            "- dash",
            "- none",
            "Choose UI framework [dash]:",
        ],
    ) in "\n".join(p.output)


def test_add_step_multiple_solutions_same_name(tmp_path: Path, new_solution: NewSolution, add_step: AddStep):
    """
    Test adding a step to an existing solution that has the same name as other raises an error.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    (tmp_path / "another_solution").mkdir()
    new_solution(input_str="\n\n\n\n", cwd=(tmp_path / "another_solution"))

    p = add_step([DEFAULT_SOLUTION_NAME], input_str="\n\n\n", expected_return_code=1)

    assert p.find_msg_in_output(f"ValueError: Multiple solutions found with the name {DEFAULT_SOLUTION_NAME}.")
    assert p.find_msg_in_output(str(tmp_path / DEFAULT_SOLUTION_NAME))
    assert p.find_msg_in_output(str(tmp_path / "another_solution" / DEFAULT_SOLUTION_NAME))
    assert p.find_msg_in_output("Hint: You can specify the correct one by using the full path")


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_duplicate_step_name_prompts_again_if_prompt_used(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test that using a duplicate step name via prompt re-asks for a different name."""
    add_step([session_solution.name], input_str="\n\n\n")
    p = add_step([session_solution.name], input_str="\n\n\nmy_second_step\n")
    output = "\n".join(p.output)
    assert f"A step with name 'my_new_step' already exists in solution '{session_solution.name}'." in output
    assert "Please enter a different Step name [my_new_step]:" in output

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        "my_second_step",
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_duplicate_step_name_raises_error_if_flag_used(session_solution: SolutionRegistry, add_step: AddStep):
    """Test that using a duplicate step name via --step-name flag raises an error."""
    add_step([session_solution.name], input_str="\n\n\n")
    p = add_step([session_solution.name, "--step-name", DEFAULT_STEP_NAME], input_str="\n\n", expected_return_code=1)
    output = "\n".join(p.output)
    assert f"Error: Step name '{DEFAULT_STEP_NAME}' is already taken in solution '{session_solution.name}'." in output


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures("cleanup_solution_src", "cleanup_solution_pyproject", "install_custom_template_plugin")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_solution_no_pyproject_no_template_saf_cli_compat_range(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test adding a step when pyproject.toml is missing and template has no CLI compat range."""
    pyproject_path = session_solution.root_dir / "pyproject.toml"
    pyproject_path.unlink()

    template_name = "second-step"
    p = add_step(
        [session_solution.name],
        input_str=f"\n\n{template_name}\n",
    )
    output = "\n".join(p.output)
    assert "Warning" not in output

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "install_custom_template_plugin_with_compatible_cli_constraint",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_solution_no_pyproject_with_template_saf_cli_compat_range(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test adding a step when pyproject.toml is missing and template declares a CLI compat range."""
    pyproject_path = session_solution.root_dir / "pyproject.toml"
    pyproject_path.unlink()

    template_name = "second-step"
    p = add_step(
        [session_solution.name],
        input_str=f"\n\n{template_name}\n",
    )
    output = "\n".join(p.output)
    expected_warning = (
        f"Warning: Template '{template_name}' declares the saf-cli compatibility constraint "
        f"'>=1.0.0', but the solution does not declare a valid "
        f"saf-cli version in pyproject.toml. The step might not work as expected."
    )
    assert expected_warning in output

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures("cleanup_solution_src", "cleanup_solution_pyproject", "install_custom_template_plugin")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_template_no_cli_version_no_template_saf_cli_compat_range(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test adding a step when solution has no saf-cli-version and template has no CLI compat range."""
    pyproject_path = session_solution.root_dir / "pyproject.toml"
    pyproject_content = tomlkit.loads(pyproject_path.read_bytes())
    pyproject_content.pop("saf-cli-version", None)  # type: ignore
    pyproject_path.write_text(tomlkit.dumps(pyproject_content))  # type: ignore

    template_name = "second-step"
    p = add_step(
        [session_solution.name],
        input_str=f"\n\n{template_name}\n",
    )
    output = "\n".join(p.output)
    assert "Warning" not in output

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "install_custom_template_plugin_with_compatible_cli_constraint",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_template_no_cli_version_with_template_saf_cli_compat_range(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test adding a step when solution has no saf-cli-version but template declares a CLI compat range."""
    pyproject_path = session_solution.root_dir / "pyproject.toml"
    pyproject_content = tomlkit.loads(pyproject_path.read_bytes())
    pyproject_content.pop("saf-cli-version", None)  # type: ignore
    pyproject_path.write_text(tomlkit.dumps(pyproject_content))  # type: ignore

    template_name = "second-step"
    p = add_step(
        [session_solution.name],
        input_str=f"\n\n{template_name}\n",
    )
    output = "\n".join(p.output)
    assert (
        f"Warning: Template '{template_name}' declares the saf-cli compatibility constraint "
        f"'>=1.0.0', but the solution does not declare a valid saf-cli "
        f"version in pyproject.toml. The step might not work as expected."
    ) in output

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures("cleanup_solution_src", "cleanup_solution_pyproject", "install_custom_template_plugin")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_template_invalid_cli_version_no_template_saf_cli_compat_range(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test adding a step when solution has an invalid saf-cli-version and template has no CLI compat range."""
    pyproject_path = session_solution.root_dir / "pyproject.toml"
    pyproject_content = tomlkit.loads(pyproject_path.read_bytes())
    pyproject_content["saf-cli-version"]["saf-cli-version"] = "invalid"  # type: ignore
    pyproject_path.write_text(tomlkit.dumps(pyproject_content))  # type: ignore

    template_name = "second-step"
    p = add_step(
        [session_solution.name],
        input_str=f"\n\n{template_name}\n",
    )
    output = "\n".join(p.output)
    assert "Warning" not in output

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "install_custom_template_plugin_with_compatible_cli_constraint",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_template_invalid_cli_version_with_template_saf_cli_compat_range(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test adding a step when solution has an invalid saf-cli-version but template declares a CLI compat range."""
    pyproject_path = session_solution.root_dir / "pyproject.toml"
    pyproject_content = tomlkit.loads(pyproject_path.read_bytes())
    pyproject_content["saf-cli-version"]["saf-cli-version"] = "invalid"  # type: ignore
    pyproject_path.write_text(tomlkit.dumps(pyproject_content))  # type: ignore

    template_name = "second-step"
    p = add_step(
        [session_solution.name],
        input_str=f"\n\n{template_name}\n",
    )
    output = "\n".join(p.output)
    assert (
        f"Warning: Template '{template_name}' declares the saf-cli compatibility constraint "
        f"'>=1.0.0', but the solution does not declare a valid saf-cli "
        f"version in pyproject.toml. The step might not work as expected."
    ) in output

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_template_cli_version_but_no_template_saf_cli_compat_range(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test adding a step when solution has a valid saf-cli-version but template has no CLI compat range."""
    p = add_step(
        [session_solution.name],
        input_str="\n\n\n",
    )
    output = "\n".join(p.output)
    assert "Warning" not in output

    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])
    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures("cleanup_solution_src", "install_custom_template_plugin_with_incompatible_cli_constraint")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_incompatible_saf_cli_version_fails(
    session_solution: SolutionRegistry,
    add_step: AddStep,
):
    """Test that adding a step fails when the solution's saf-cli version is outside the template's compat range."""
    pyproject_path = session_solution.root_dir / "pyproject.toml"
    pyproject_content = tomlkit.loads(pyproject_path.read_bytes())
    saf_cli_version = pyproject_content.get("saf-cli-version", {}).get("saf-cli-version")  # type: ignore

    template_name = "second-step"
    p = add_step(
        [session_solution.name],
        input_str=f"\n\n{template_name}\n",
        expected_return_code=1,
    )
    output = "\n".join(p.output)
    assert (
        f"Template '{template_name}' requires a saf-cli version in the range "
        f"'<1.0.0', but the solution's saf-cli version is {saf_cli_version}."
    ) in output


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures("cleanup_solution_src", "install_custom_template_plugin_with_compatible_cli_constraint")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_compatible_saf_cli_version_succeeds(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    add_step: AddStep,
    session_selenium_webdriver: WebDriver,
):
    """Test that adding a step succeeds when the solution's saf-cli version is within the template's compat range."""
    add_step(
        [session_solution.name],
        input_str="\n\nsecond-step\n",
    )
    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_proc = run_solution([session_solution.name])

    _verify_step_added(
        solution_proc,
        session_selenium_webdriver,
        solution_module_dir,
        DEFAULT_STEP_NAME,
        DEFAULT_UI_FRAMEWORK,
    )


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_no_definition_file(
    session_solution: SolutionRegistry,
    add_step: AddStep,
    session_solution_namespace: str,
):
    """Test that adding a step fails when the solution definition file is missing."""
    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )
    solution_definition_path = solution_module_dir / "solution" / "definition.py"
    solution_definition_path.unlink()
    p = add_step([session_solution.name], input_str="\n\n\n", expected_return_code=1)
    assert f"Solution definition not found in expected location: {solution_definition_path}" in "\n".join(p.output)


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures("cleanup_solution_src", "install_custom_template_plugin_with_invalid_cli_constraint")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_add_step_template_has_invalid_compatibility_range(session_solution: SolutionRegistry, add_step: AddStep):
    """Test that adding a step fails when the template declares an invalid CLI compatibility range."""
    expected_error = (
        "Invalid saf-cli version compatibility range: 'invalid'. "
        "Make sure you define a range of versions using standard packaging specifier format, "
        "e.g. '>=0.1.0,<1.0.0' or '==0.2.5'."
    )
    p = add_step([session_solution.name], input_str="\n\nsecond-step\n", expected_return_code=1)
    assert expected_error in "\n".join(p.output)


@contextmanager
def _verify_successful_rollback(
    solution_root_dir: Path,
    solution_module_dir: Path,
    poetry_lock_exists_before_failure: bool,
):
    main_page = solution_module_dir / "ui" / "pages" / "page.py"
    definition = solution_module_dir / "solution" / "definition.py"

    pyproject_path = solution_root_dir / "pyproject.toml"
    poetry_lock_path = solution_root_dir / "poetry.lock"

    if not poetry_lock_exists_before_failure and poetry_lock_path.is_file():
        poetry_lock_path.unlink()

    snapshot_before = set(solution_module_dir.rglob("*"))

    original_main_page = main_page.read_bytes()
    original_definition = definition.read_bytes()
    original_pyproject = pyproject_path.read_bytes()
    original_lock = poetry_lock_path.read_bytes() if poetry_lock_path.exists() else None
    yield
    assert set(solution_module_dir.rglob("*")) == snapshot_before
    assert main_page.read_bytes() == original_main_page
    assert definition.read_bytes() == original_definition
    assert pyproject_path.read_bytes() == original_pyproject

    if original_lock is not None:
        assert poetry_lock_path.read_bytes() == original_lock
    else:
        assert not poetry_lock_path.exists()

    _verify_step_not_added(solution_module_dir, DEFAULT_STEP_NAME)


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "cleanup_solution_poetry_lock",
    "install_custom_template_plugin_fails_on_post_hook",
    "install_custom_template_plugin_with_invalid_dependency",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.parametrize("poetry_lock_exists_before_failure", [True, False])
def test_add_step_rollback_on_failure(
    session_solution: SolutionRegistry,
    add_step: AddStep,
    poetry_lock_exists_before_failure: bool,
    session_solution_namespace: str,
):
    """
    Validate full rollback across BackupManager stages.
    """
    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )

    with _verify_successful_rollback(
        session_solution.root_dir,
        solution_module_dir,
        poetry_lock_exists_before_failure,
    ):
        p = add_step(
            [session_solution.name],
            input_str="\n\nseveral-deps-step\n",
            expected_return_code=1,
        )

    assert "simulated hook failure" in "\n".join(p.output)

    with _verify_successful_rollback(
        session_solution.root_dir,
        solution_module_dir,
        poetry_lock_exists_before_failure,
    ):
        p = add_step(
            [session_solution.name],
            input_str="\n\nthird-step\n",
            expected_return_code=1,
        )

    assert "Could not parse version constraint: ^0.-5.abc" in "\n".join(p.output)

    # The same solution should remain healthy after rollback and allow subsequent add-step.
    next_step_name = f"rollback_success_{str(poetry_lock_exists_before_failure).lower()}_step"
    p = add_step(
        [
            session_solution.name,
            "--step-name",
            next_step_name,
            "--ui-framework",
            "dash",
            "--template",
            DEFAULT_TEMPLATE_NAME,
        ],
    )

    assert (solution_module_dir / "solution" / f"{next_step_name}.py").is_file()
    assert (solution_module_dir / "ui" / "pages" / f"{next_step_name.replace('step', 'page')}.py").is_file()


@pytest.mark.use_session_solution
@pytest.mark.use_custom_plugins
@pytest.mark.usefixtures(
    "cleanup_solution_src",
    "cleanup_solution_pyproject",
    "cleanup_solution_poetry_lock",
    "install_custom_template_plugin_fails_on_post_hook",
)
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.parametrize("poetry_lock_exists_before_failure", [True, False])
def test_add_step_rollback_on_dependency_update_failure(
    session_solution: SolutionRegistry,
    add_step: AddStep,
    poetry_lock_exists_before_failure: bool,
    session_solution_namespace: str,
):
    """
    Validate full rollback across BackupManager stages.
    """
    solution_module_dir = (
        session_solution.root_dir / "src" / namespace_to_path(session_solution_namespace) / session_solution.name
    )

    main_page = solution_module_dir / "ui" / "pages" / "page.py"
    definition = solution_module_dir / "solution" / "definition.py"

    pyproject_path = session_solution.root_dir / "pyproject.toml"
    poetry_lock_path = session_solution.root_dir / "poetry.lock"

    if not poetry_lock_exists_before_failure:
        poetry_lock_path.unlink()

    snapshot_before = set(solution_module_dir.rglob("*"))

    original_main_page = main_page.read_bytes()
    original_definition = definition.read_bytes()
    original_pyproject = pyproject_path.read_bytes()
    original_lock = poetry_lock_path.read_bytes() if poetry_lock_path.exists() else None
    p = add_step(
        [session_solution.name],
        input_str="\n\nseveral-deps-step\n",
        expected_return_code=1,
    )

    assert "simulated hook failure" in "\n".join(p.output)
    assert set(solution_module_dir.rglob("*")) == snapshot_before
    assert main_page.read_bytes() == original_main_page
    assert definition.read_bytes() == original_definition
    assert pyproject_path.read_bytes() == original_pyproject

    if original_lock is not None:
        assert poetry_lock_path.read_bytes() == original_lock
    else:
        assert not poetry_lock_path.exists()

    _verify_step_not_added(solution_module_dir, DEFAULT_STEP_NAME)

    # The same solution should remain healthy after rollback and allow subsequent add-step.
    next_step_name = f"dep_rollback_success_{str(poetry_lock_exists_before_failure).lower()}_step"
    p = add_step(
        [
            session_solution.name,
            "--step-name",
            next_step_name,
            "--ui-framework",
            "dash",
            "--template",
            DEFAULT_TEMPLATE_NAME,
        ],
    )

    assert (solution_module_dir / "solution" / f"{next_step_name}.py").is_file()
    assert (solution_module_dir / "ui" / "pages" / f"{next_step_name.replace('step', 'page')}.py").is_file()
