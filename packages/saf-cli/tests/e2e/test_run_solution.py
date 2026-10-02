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

import os
from pathlib import Path
import platform
import re
import shutil

from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_element_and_click,
    wait_for_element_and_send_text,
    wait_for_expected_attribute,
    wait_for_expected_property,
)
import httpx2
import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_NAME, SAF_DESKTOP_LOG_TO_FILES
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._utilities.conversion import namespace_to_path
from tests.e2e.conftest import (
    ListSolutions,
    NewSolution,
    RunSolution,
    check_api_is_functional,
    check_expected_messages,
    check_orchestrator_process,
    check_ui_is_functional,
    is_solution_registered,
)

_STEP_ROUTES_AND_CONTENT = [
    ("First Step", "/first-step", "Compute the sum of two numbers."),
    ("Second Step", "/second-step", "This page is empty for now."),
    ("About", "", "Add a short sentence to describe the goal of the solution"),
]


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.parametrize("solution_param_type", [None, "relative", "absolute", "solution_name"])
def test_saf_run(
    session_database_path: Path,
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    list_solutions: ListSolutions,
    run_solution: RunSolution,
    solution_param_type: str | None,
    session_selenium_webdriver: WebDriver,
    mock_session_appdata: Path,
):
    """
    Test ``saf run`` with the default option values and all the possible solution argument types: an empty string,
    a relative path, an absolute path, and a solution name.
    """
    if solution_param_type != "solution_name":
        session_database_path.unlink()
        assert not is_solution_registered(
            list_solutions(),
            session_solution.root_dir,
            session_solution.name,
            session_solution.display_name,
        )

    if solution_param_type == "solution_name":
        p = run_solution([session_solution.name])
    elif solution_param_type == "relative":
        p = run_solution([f"./{session_solution.name}"], cwd=session_solution.root_dir.parent)
    elif solution_param_type == "absolute":
        p = run_solution([session_solution.root_dir.absolute().as_posix()])
    elif not solution_param_type:
        p = run_solution([""], cwd=session_solution.root_dir)
    else:
        raise ValueError(f"Invalid solution_param_type: {solution_param_type}")

    # .env of solution is loaded
    assert (session_solution.root_dir / ".env").is_file()
    assert p.find_msg_in_output(f"Environment variables loaded from {session_solution.root_dir.resolve() / '.env'}")

    check_expected_messages(p, session_solution.display_name)

    # Orchestrator log contains expected message
    solution_dirname = f"{session_solution.name}_solution".title().replace("_", "")
    orchestrator_log = mock_session_appdata / "ansys" / "glow" / solution_dirname / "orchestrator.log"
    assert "OTEL Dashboard:" in orchestrator_log.read_text()

    check_orchestrator_process(p, session_solution, session_solution_namespace)

    check_api_is_functional(p)

    check_ui_is_functional(session_selenium_webdriver, p)

    assert is_solution_registered(
        list_solutions(),
        session_solution.root_dir,
        session_solution.name,
        session_solution.display_name,
    )


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_use_media_from_assets(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
):
    """Test ``saf run`` uses images and css from the solution assets folder in the UI."""
    p = run_solution([session_solution.name])
    session_selenium_webdriver.get(p.get_solution_ui_url())
    wait_for_element(
        session_selenium_webdriver,
        "//img[@src='/assets/images/workflow-placeholder.png']",
        element_type=By.XPATH,
        timeout=60,
    )
    page_source = session_selenium_webdriver.page_source
    media_paths = set(re.findall(r"/assets/[^\"'&]+\.(?:svg|png)", page_source))
    ui_url = p.get_solution_ui_url().rsplit("/projects")[0]
    expected_media_paths = {
        f"{ui_url}/assets/logos/light/placeholder_logo.png",
        f"{ui_url}/assets/icons/light/radix-icons--sun.svg",
        f"{ui_url}/assets/icons/light/teenyicons--doc-solid.svg",
        f"{ui_url}/assets/icons/light/material-symbols--home.svg",
        f"{ui_url}/assets/icons/light/game-icons--crossed-air-flows.svg",
        f"{ui_url}/assets/icons/light/carbon--ibm-engineering-workflow-mgmt.svg",
    }
    assert expected_media_paths <= {f"{ui_url}{path}" for path in media_paths}
    assert '<link rel="stylesheet" href="/assets/css/all.css' in page_source
    assert '<link rel="stylesheet" href="/assets/css/bootstrap.min.css' in page_source


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_with_portal(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
):
    """
    Test ``saf run`` with the --portal flag.
    """
    p = run_solution([session_solution.name, "--portal"])

    # .env of solution is loaded
    assert (session_solution.root_dir / ".env").is_file()
    assert p.find_msg_in_output(f"Environment variables loaded from {session_solution.root_dir.resolve() / '.env'}")

    check_expected_messages(p, session_solution.display_name, with_portal=True)

    check_orchestrator_process(p, session_solution, session_solution_namespace, with_portal=True)

    check_api_is_functional(p, with_portal=True)

    check_ui_is_functional(session_selenium_webdriver, p, with_portal=True)


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_with_portal_opens_projects_dashboard(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
):
    """
    Test ``saf run --portal`` opens the projects dashboard of the solution UI instead of starting a portal.
    """
    p = run_solution([session_solution.name, "--portal"])

    projects_dashboard_url = p.get_projects_dashboard_url()
    assert projects_dashboard_url == f"{p.get_solution_ui_url(no_project=True)}/projects"
    assert p.find_msg_in_output("SAF Portal: not launched")

    session_selenium_webdriver.get(projects_dashboard_url)
    wait_for_element(session_selenium_webdriver, "projects-dashboard", element_type=By.ID)


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_with_env_file(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
):
    """
    Test ``saf run`` with --env-file overrides the .env file from the solution root directory.
    """
    my_env_file = session_solution.root_dir.parent / "my_env_file.env"
    my_env_file.write_text("MY_ENV_VAR=123\n")
    p = run_solution([session_solution.name, "--env-file", str(my_env_file)])

    # custom env file is loaded
    assert (session_solution.root_dir / ".env").is_file()
    assert p.find_msg_in_output(f"Environment variables loaded from {my_env_file.resolve()}")
    assert not p.find_msg_in_output(f"Environment variables loaded from {session_solution.root_dir / '.env'}")


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("restore_glow_env_vars")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_without_glow_vars_in_env(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
):
    """
    Test ``saf run`` works correctly when .env file does not contain GLOW_SOLUTION_DEFINITION and GLOW_UI_MODULE.
    This verifies backward compatibility and the fallback logic that derives these values from the main module.
    """
    p = run_solution([session_solution.name])
    check_expected_messages(p, session_solution.display_name)
    check_api_is_functional(p)
    check_ui_is_functional(session_selenium_webdriver, p)


def test_run_invalid_solution(tmp_path: Path, new_solution: NewSolution, run_solution: RunSolution):
    """
    Test running an existing solution that is invalid raises an error.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    shutil.rmtree(tmp_path / DEFAULT_SOLUTION_NAME)

    p = run_solution([DEFAULT_SOLUTION_NAME], cwd=tmp_path, wait_for_healthy=False)
    assert p.return_code == 1
    assert p.find_msg_in_output(f"NotADirectoryError: Solution not found at {str(tmp_path / DEFAULT_SOLUTION_NAME)}")


def test_run_multiple_solutions_same_name_invalid_solution(
    tmp_path: Path,
    new_solution: NewSolution,
    run_solution: RunSolution,
):
    """
    Test running an existing solution that has the same name as other that is invalid.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    (tmp_path / "another_solution").mkdir()
    new_solution(input_str="\n\n\n\n", cwd=(tmp_path / "another_solution"))
    shutil.rmtree(tmp_path / "another_solution")

    p = run_solution([DEFAULT_SOLUTION_NAME], wait_for_healthy=False)
    # fails to launch because we didn't install the env, but the solution was correctly selected
    assert p.find_msg_in_output(
        f"FileNotFoundError: Executable not found at {str(tmp_path / DEFAULT_SOLUTION_NAME)}",
    )


def test_run_multiple_solutions_same_name(
    tmp_path: Path,
    new_solution: NewSolution,
    run_solution: RunSolution,
):
    """
    Test running an existing solution that has the same name as other raises an error.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    (tmp_path / "another_solution").mkdir()
    new_solution(input_str="\n\n\n\n", cwd=(tmp_path / "another_solution"))

    p = run_solution([DEFAULT_SOLUTION_NAME], wait_for_healthy=False)

    assert p.return_code == 1
    assert p.find_msg_in_output(f"ValueError: Multiple solutions found with the name {DEFAULT_SOLUTION_NAME}.")
    assert p.find_msg_in_output(str(tmp_path / DEFAULT_SOLUTION_NAME))
    assert p.find_msg_in_output(str(tmp_path / "another_solution" / DEFAULT_SOLUTION_NAME))
    assert p.find_msg_in_output("Hint: You can specify the correct one by using the full path")


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_debug_no_error(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
):
    """
    Test that there is no error shown when running ``saf run --debug`` with the default solution.
    """
    p = run_solution(
        [
            session_solution.name,
            "--debug",
        ],
        wait_for_healthy=True,
    )
    project_ui_url = p.get_solution_ui_url()
    session_selenium_webdriver.get(project_ui_url)
    with pytest.raises(TimeoutException):
        wait_for_element(session_selenium_webdriver, "test-devtools-error-count", element_type=By.CLASS_NAME)


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["none"], indirect=True)
@pytest.mark.parametrize("automatic_project_migration", [True, False], ids=["enable", "disable"])
def test_saf_run_project_migration(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    automatic_project_migration: bool,
    session_solution_namespace: str,
):
    """
    Test ``saf run`` with and without --no-automatic-project-migration, and check if an old project can be upgraded
    to a newer solution schema.
    """
    # GIVEN: Project of a given solution
    p = run_solution(
        [session_solution.name] + (["--no-automatic-project-migration"] if not automatic_project_migration else []),
    )
    first_project_name = p.get_project_name()
    r = httpx2.get(p.get_project_api_url())
    assert r.status_code == 200

    # WHEN: Modifying the solution schema by adding a new field to the first step and relaunching the solution
    first_step_file = (
        session_solution.root_dir
        / "src"
        / namespace_to_path(session_solution_namespace)
        / session_solution.name.replace("-", "_")
        / "solution"
        / "first_step.py"
    )
    assert first_step_file.is_file()
    first_step_file.write_text(
        first_step_file.read_text().replace(
            "result: float = 0",
            "result: float = 0\n    new_step_field: int = 0",
        ),
    )
    p.restart(clear_output=True)

    # THEN: Trying to retrieve the old project raises an error.
    first_project_api_url = p.get_api_docs_url().replace("docs", first_project_name)
    r = httpx2.get(first_project_api_url)
    assert r.status_code == 422
    assert "extra step fields are not allowed without upgrading the solution." in r.json()["detail"]

    # WHEN: Upgrading the project to the new solution schema, fails if automatic solution upgrades are disabled.
    r = httpx2.post(f"{first_project_api_url}:upgrade")
    if not automatic_project_migration:
        assert r.status_code == 422
        assert "Step 'first_step' is missing fields ['new_step_field']" in r.json()["detail"]
    else:
        assert r.status_code == 200

    # THEN: The project is now accessible again if automatic solution upgrades are enabled.
    #       Otherwise, remains inaccessible.
    r = httpx2.get(first_project_api_url)
    if not automatic_project_migration:
        assert r.status_code == 422
        assert "extra step fields are not allowed without upgrading the solution." in r.json()["detail"]
    else:
        assert r.status_code == 200


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.parametrize("log_to_files", ["cli", "env", "dotenv"])
def test_saf_run_with_log_to_files(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    log_to_files: str,
    mock_session_appdata: Path,
):
    """
    Test that it is possible to log to files instead of aspire by using one of the following option:

    - saf run --log-to-files
    - setting 'SAF_DESKTOP_LOG_TO_FILES' env var
    - adding SAF_DESKTOP_LOG_TO_FILES=True in .env
    """
    match log_to_files:
        case "cli":
            p = run_solution([session_solution.name, "--log-to-files"])
        case "env":
            env = os.environ.copy()
            env["SAF_DESKTOP_LOG_TO_FILES"] = "True"
            p = run_solution([session_solution.name], env=env)
        case "dotenv":
            dotenv = session_solution.root_dir / ".env"
            dotenv.write_text(f"{SAF_DESKTOP_LOG_TO_FILES}=True\n")
            p = run_solution([session_solution.name])
        case _:
            raise ValueError("Invalid parameter")

    solution_dirname = f"{session_solution.name}_solution".title().replace("_", "")
    logdir = mock_session_appdata / "ansys" / "glow" / solution_dirname / "logs"
    assert logdir.is_dir()
    api_logdir = logdir / "api_server"
    assert api_logdir.is_dir()
    ui_logdir = logdir / "ui_server"
    assert ui_logdir.is_dir()
    assert p.find_msg_in_output("INFO - OTEL Dashboard: not launched")


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_subprocess_fails(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    session_solution_namespace: str,
):
    """
    Test ``saf run`` propagates subprocess failure by returning non-zero exit code and printing the exception.
    """
    # add wrong import to solution src to make run fail
    first_step_file = (
        session_solution.root_dir
        / "src"
        / namespace_to_path(session_solution_namespace)
        / session_solution.name.replace("-", "_")
        / "solution"
        / "first_step.py"
    )
    assert first_step_file.is_file()
    first_step_file.write_text("import fake_module\n" + first_step_file.read_text())

    p = run_solution([session_solution.name], wait_for_healthy=False)
    assert p.return_code == 1
    assert p.find_msg_in_output("subprocess.CalledProcessError")
    assert p.find_msg_in_output("returned non-zero exit status 1.")


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_navigate_using_nav_tree(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
):
    """Test navigation through the tree menu updates page content, active nav item and URL."""
    active_tree_item_xpath = (
        "//a[@data-active='true' and .//span[contains(@class, 'mantine-NavLink-label') "
        "and contains(normalize-space(.), '{label}')]]"
    )

    p = run_solution([session_solution.name])
    session_selenium_webdriver.get(p.get_solution_ui_url())

    # Default page is About page.
    wait_for_element(
        session_selenium_webdriver,
        "//*[contains(text(), 'Add a short sentence to describe the goal of the solution')]",
        element_type=By.XPATH,
    )
    wait_for_element(
        session_selenium_webdriver,
        active_tree_item_xpath.format(label="About"),
        element_type=By.XPATH,
    )

    # Go through all pages and back to default
    for step_label, route_suffix, expected_content in _STEP_ROUTES_AND_CONTENT:
        wait_for_element_and_click(
            session_selenium_webdriver,
            f"//*[contains(text(), '{step_label}')]",
            element_type=By.XPATH,
        )
        wait_for_element(
            session_selenium_webdriver,
            f"//*[contains(text(), '{expected_content}')]",
            element_type=By.XPATH,
        )
        wait_for_element(
            session_selenium_webdriver,
            active_tree_item_xpath.format(label=step_label),
            element_type=By.XPATH,
        )
        assert session_selenium_webdriver.current_url == f"{p.get_solution_ui_url()}{route_suffix}"


@pytest.mark.xfail(reason="Fails often, both in CI and locally.")
@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_navigate_using_urls(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
):
    """Test navigation through URLs updates both page content and active nav item.

    Also check that going back and forward in the browser history works as expected."""
    active_tree_item_xpath = (
        "//a[@data-active='true' and .//span[contains(@class, 'mantine-NavLink-label') "
        "and contains(normalize-space(.), '{label}')]]"
    )

    p = run_solution([session_solution.name])
    session_selenium_webdriver.get(p.get_solution_ui_url())

    # Default page is About page.
    wait_for_element(
        session_selenium_webdriver,
        "//*[contains(text(), 'Add a short sentence to describe the goal of the solution')]",
        element_type=By.XPATH,
    )
    wait_for_element(
        session_selenium_webdriver,
        active_tree_item_xpath.format(label="About"),
        element_type=By.XPATH,
    )

    # Navigate directly using page URLs and assert active tree item and content.
    for step_label, route_suffix, expected_content in _STEP_ROUTES_AND_CONTENT:
        session_selenium_webdriver.get(f"{p.get_solution_ui_url()}{route_suffix}")
        wait_for_element(
            session_selenium_webdriver,
            f"//*[contains(text(), '{expected_content}')]",
            element_type=By.XPATH,
            timeout=120,
        )
        wait_for_element(
            session_selenium_webdriver,
            active_tree_item_xpath.format(label=step_label),
            element_type=By.XPATH,
        )

    # Go back to Second Step
    session_selenium_webdriver.back()
    wait_for_element(
        session_selenium_webdriver,
        f"//*[contains(text(), '{_STEP_ROUTES_AND_CONTENT[-2][2]}')]",
        element_type=By.XPATH,
    )
    wait_for_element(
        session_selenium_webdriver,
        active_tree_item_xpath.format(label=_STEP_ROUTES_AND_CONTENT[-2][0]),
        element_type=By.XPATH,
    )

    # Go forward to About
    session_selenium_webdriver.forward()
    wait_for_element(
        session_selenium_webdriver,
        f"//*[contains(text(), '{_STEP_ROUTES_AND_CONTENT[-1][2]}')]",
        element_type=By.XPATH,
    )
    wait_for_element(
        session_selenium_webdriver,
        active_tree_item_xpath.format(label=_STEP_ROUTES_AND_CONTENT[-1][0]),
        element_type=By.XPATH,
    )


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
@pytest.mark.parametrize("custom_404_page", [False, True], ids=["default_404", "custom_404"])
def test_404_page_on_invalid_urls(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
    custom_404_page: bool,
):
    """Test 404 page content is shown for invalid routes in the solution UI."""
    expected_404_content = "404 - Page not found"
    if custom_404_page:
        expected_404_content = "This is our custom 404 content"
        solution_module_name = session_solution.name.replace("-", "_")
        not_found_page_file = (
            session_solution.root_dir
            / "src"
            / namespace_to_path(session_solution_namespace)
            / solution_module_name
            / "ui"
            / "pages"
            / "not_found_404.py"
        )
        not_found_page_file.write_text(
            "import dash\n"
            "from dash import html\n\n"
            "dash.register_page(__name__)\n\n"
            'layout = html.H1("This is our custom 404 content")\n',
        )

    p = run_solution([session_solution.name])
    solution_ui_url = p.get_solution_ui_url()
    solution_ui_url_no_project = solution_ui_url.rsplit("/projects", 1)[0]

    invalid_urls = [
        f"{solution_ui_url}/invalid-step",  # valid project, invalid step
        f"{solution_ui_url_no_project}/invalid-route",  # invalid route
        f"{solution_ui_url_no_project}/projects/invalid-project",  # invalid project
    ]

    for invalid_url in invalid_urls:
        session_selenium_webdriver.get(invalid_url)
        wait_for_element(
            session_selenium_webdriver,
            f"//*[contains(text(), '{expected_404_content}')]",
            element_type=By.XPATH,
        )


def _change_theme(session_selenium_webdriver: WebDriver, to_theme: str):
    from_theme = "light" if to_theme == "dark" else "dark"
    switch_input = wait_for_element(
        session_selenium_webdriver,
        "color-scheme-switch",
        element_type=By.ID,
    )
    assert not switch_input.is_selected()
    wait_for_expected_attribute(
        session_selenium_webdriver,
        "html",
        "data-mantine-color-scheme",
        from_theme,
        element_type=By.TAG_NAME,
    )
    # For some reason, using wait_for_element_and_click or switch_input.click() does not work to click the switch,
    # so we use execute_script as a workaround.
    session_selenium_webdriver.execute_script(  # pyright: ignore[reportUnknownMemberType]
        "arguments[0].click();",
        switch_input,
    )
    assert switch_input.is_selected()
    wait_for_expected_attribute(
        session_selenium_webdriver,
        "html",
        "data-mantine-color-scheme",
        to_theme,
        element_type=By.TAG_NAME,
    )


@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_dark_light_theme_switch(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    selenium_webdriver: WebDriver,
):
    """
    Test that the dark/light theme switch works correctly in the solution UI.
    """
    p = run_solution([session_solution.name])
    selenium_webdriver.get(p.get_solution_ui_url())
    solution_ui_url = p.get_solution_ui_url()
    solution_ui_url_no_project = p.get_solution_ui_url().rsplit("/projects", 1)[0]

    # default theme is light
    _check_header_components_theme(selenium_webdriver, solution_ui_url_no_project, "light")

    # Assert that the update of the navigation bar icons does not affect the loading of the About page.
    wait_for_element(
        selenium_webdriver,
        "//img[@src='/assets/images/workflow-placeholder.png']",
        element_type=By.XPATH,
        timeout=60,
    )
    # Change the value of the first-arg input to make sure switching the theme does not affect the state of the page.
    wait_for_element_and_click(
        selenium_webdriver,
        "//*[contains(text(), 'First Step')]",
        element_type=By.XPATH,
    )
    _check_header_components_theme(selenium_webdriver, solution_ui_url_no_project, "light")
    wait_for_element_and_send_text(selenium_webdriver, "first-arg", "4")
    wait_for_expected_property(selenium_webdriver, "first-arg", "value", "04")
    _change_theme(selenium_webdriver, "dark")
    _check_header_components_theme(selenium_webdriver, solution_ui_url_no_project, "dark")
    wait_for_expected_property(selenium_webdriver, "first-arg", "value", "04")

    # Change page using navigation tree and ensure the theme is preserved
    wait_for_element_and_click(
        selenium_webdriver,
        "//*[contains(text(), 'Second Step')]",
        element_type=By.XPATH,
    )
    wait_for_element(
        selenium_webdriver,
        "//*[contains(text(), 'This page is empty for now.')]",
        element_type=By.XPATH,
    )
    _check_header_components_theme(selenium_webdriver, solution_ui_url_no_project, "dark")

    # Change page using URL and ensure the theme is preserved
    selenium_webdriver.get(f"{solution_ui_url}/first-step")
    wait_for_element(
        selenium_webdriver,
        "//*[contains(text(), 'Compute the sum of two numbers.')]",
        element_type=By.XPATH,
    )
    _check_header_components_theme(selenium_webdriver, solution_ui_url_no_project, "dark")


def _check_header_components_theme(
    selenium_webdriver: WebDriver,
    solution_ui_url_no_project: str,
    theme: str,
    with_portal: bool = False,
):
    wait_for_expected_attribute(
        selenium_webdriver,
        "logo-image",
        "src",
        f"{solution_ui_url_no_project}/assets/logos/{theme}/placeholder_logo.png",
    )
    wait_for_expected_attribute(
        selenium_webdriver,
        "#access-solution-doc img",
        "src",
        f"{solution_ui_url_no_project}/assets/icons/{theme}/teenyicons--doc-solid.svg",
        element_type=By.CSS_SELECTOR,
    )
    if with_portal:
        wait_for_expected_attribute(
            selenium_webdriver,
            "#back-to-projects-icon img",
            "src",
            f"{solution_ui_url_no_project}/assets/icons/{theme}/carbon--return.svg",
            element_type=By.CSS_SELECTOR,
        )


@pytest.mark.xfail(reason="Fails often, both in CI and locally.")
@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_theme_is_preserved_on_return_to_portal(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    selenium_webdriver: WebDriver,
):
    """
    Test that the dark/light theme switch is preserved when returning to the portal and coming back to the project.
    """
    # Create a project so that we can access a project when running with --portal below
    p_create_project = run_solution([session_solution.name])
    project_name = p_create_project.get_project_name().split("/")[-1]
    p_create_project.stop()

    p_portal = run_solution([session_solution.name, "--portal"])
    selenium_webdriver.get(p_portal.get_portal_url())

    # Click on the project card using the project item ID
    wait_for_element_and_click(
        selenium_webdriver,
        "project-item-0",
        element_type=By.ID,
    )

    solution_ui_url = p_portal.get_solution_ui_url(no_project=True) + f"/projects/{project_name}"
    selenium_webdriver.get(solution_ui_url)

    _change_theme(selenium_webdriver, "dark")

    solution_ui_url_no_project = solution_ui_url.rsplit("/projects")[0]

    _check_header_components_theme(selenium_webdriver, solution_ui_url_no_project, "dark", with_portal=True)

    # Click on the "Back to Projects" button
    wait_for_element_and_click(selenium_webdriver, "back-to-projects-icon")

    selenium_webdriver.get(p_portal.get_portal_url())

    # Click the project card again to return to the solution UI page
    wait_for_element_and_click(
        selenium_webdriver,
        "project-item-0",
        element_type=By.ID,
    )

    selenium_webdriver.get(solution_ui_url)

    _check_header_components_theme(selenium_webdriver, solution_ui_url_no_project, "dark", with_portal=True)


@pytest.mark.use_session_solution
@pytest.mark.usefixtures("cleanup_solution_src")
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_with_custom_pywebview_icon(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    mock_session_appdata: Path,
    session_solution_namespace: str,
):
    """
    Test that it is possible to set a custom icon for the pywebview window by placing a favicon.ico
    file in the solution UI assets directory.
    """

    @retry(stop=stop_after_attempt(20), wait=wait_fixed(0.25))
    def find_custom_icon_loaded(orchestrator_log: Path, custom_icon_file: Path):
        if f"DEBUG - Set custom icon for pywebview from {custom_icon_file}" not in orchestrator_log.read_text():
            raise TryAgain

    custom_icon_file = Path(__file__).parent.parent / "mocks" / "favicon.ico"
    assert custom_icon_file.is_file()
    dest_custom_icon_file = (
        session_solution.root_dir
        / "src"
        / namespace_to_path(session_solution_namespace)
        / session_solution.name.replace("-", "_")
        / "ui"
        / "assets"
        / "pywebview"
        / "favicon.ico"
    )
    shutil.copy(custom_icon_file, dest_custom_icon_file)

    run_solution([session_solution.name])

    # Orchestrator log contains expected "custom icon set" message
    solution_dirname = f"{session_solution.name}_solution".title().replace("_", "")
    orchestrator_log = mock_session_appdata / "ansys" / "glow" / solution_dirname / "orchestrator.log"
    if platform.system() == "Windows":
        find_custom_icon_loaded(orchestrator_log, dest_custom_icon_file)
    else:
        assert "DEBUG - Set custom icon for pywebview from" not in orchestrator_log.read_text()
