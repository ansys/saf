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

from collections.abc import Generator
import logging
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import tempfile
from typing import Protocol
import uuid

from ansys.saf.testing.common import YieldFixture, find_exec_in_venv
from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_element_and_click,
    wait_for_element_and_send_text,
    wait_for_expected_property,
)
import httpx2
import psutil
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed
import tomlkit

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_DISPLAY_NAME, DEFAULT_SOLUTION_NAME, DEFAULT_SOLUTION_NAMESPACE
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._utilities.conversion import namespace_to_path
from tests.e2e.app_starter_process import SolutionAppStarter
from tests.e2e.saf_process import SAFProcess
from tests.e2e.solution_process import (
    SolutionShortcutPythonwProcess,
)
from tests.outcome_checks import check_scaffolded_solution_files

logger = logging.getLogger(__name__)


#################################################### PREREQUISITES ####################################################


@pytest.fixture
def check_gtk_launch_and_xvfb_are_installed():
    if platform.system() == "Linux" and (not shutil.which("gtk-launch") or not shutil.which("xvfb-run")):
        raise RuntimeError(
            "gtk-launch and xvfb need to be installed to execute these tests. Run:\n"
            "sudo apt update\nsudo apt install libgtk-3-bin xvfb",
        )


##################################################### GET VERSION #####################################################


class GetSAFVersion(Protocol):
    def __call__(self, expected_return_code: int = 0) -> SAFProcess: ...


@pytest.fixture
def get_saf_version() -> GetSAFVersion:
    def _get_saf_version(expected_return_code: int = 0) -> SAFProcess:
        p = SAFProcess.run(["--version"], expected_return_code=expected_return_code)
        return p

    return _get_saf_version


################################################## CREATE SOLUTIONS ###################################################


class NewSolution(Protocol):
    def __call__(
        self,
        args: list[str] | None = None,
        cwd: Path | None = None,
        input_str: str = "",
        expected_return_code: int = 0,
    ) -> SAFProcess: ...


def _new_solution(
    args: list[str] | None = None,
    cwd: Path | None = None,
    input_str: str = "",
    expected_return_code: int = 0,
) -> SAFProcess:
    # Avoid using cwd=None to not pollute the CWD (typically, saf-cli's rootdir) with test solutions
    cwd = cwd or Path(tempfile.mkdtemp(prefix="saf-cli-test-"))
    p = SAFProcess.run(
        ["new"] + (args if args is not None else []),
        cwd=cwd,
        input_str=input_str,
        expected_return_code=expected_return_code,
    )
    return p


# set a different mock_appdata for each test function that uses new_solution to avoid collisions
# between solutions with the same root directory.
@pytest.fixture
def new_solution(mock_appdata: Path, database_path: Path) -> NewSolution:
    return _new_solution


def verify_generated_solution(
    solutions_output: list[str],
    root_path: Path,
    solution_name: str,
    solution_module_name: str,
    solution_display_name: str,
    ui_framework: str,
    namespace: str,
):
    expected_solution_root_dir = root_path / solution_name

    # Solution is registered in the DB
    assert is_solution_registered(
        solutions_output,
        expected_solution_root_dir,
        solution_name=solution_name,
        solution_display_name=solution_display_name,
    )

    # Directory is created with the expected files
    check_scaffolded_solution_files(root_path, solution_name, solution_module_name, ui_framework, namespace=namespace)


################################################## INSTALL SOLUTIONS ##################################################


class InstallSolution(Protocol):
    def __call__(
        self,
        args: list[str] | None = None,
        cwd: Path | None = None,
        expected_return_code: int = 0,
    ) -> SAFProcess: ...


def _install_solution(
    args: list[str] | None = None,
    cwd: Path | None = None,
    expected_return_code: int = 0,
) -> SAFProcess:
    p = SAFProcess.run(
        ["install"] + (args if args is not None else []),
        cwd=cwd,
        expected_return_code=expected_return_code,
    )
    return p


@pytest.fixture
def install_solution() -> InstallSolution:
    return _install_solution


def _stage_extra_packages_in_solution_dir(solution_dir: Path) -> list[Path]:
    """Copy extra wheel files into the solution directory and return the staged wheel paths."""
    extra_packages_dir = os.getenv("SAF_EXTRA_PACKAGES_DIR", None)
    if not extra_packages_dir:
        return []

    staged_dir = solution_dir / ".saf-extra-packages"
    staged_dir.mkdir(exist_ok=True)

    staged_wheel_files: list[Path] = []
    for whl_file in Path(extra_packages_dir).resolve().glob("*.whl"):
        staged_whl_file = staged_dir / whl_file.name
        shutil.copy2(whl_file, staged_whl_file)
        staged_wheel_files.append(staged_whl_file)

    return staged_wheel_files


def add_extra_packages_to_solution(solution_name: str, solution_dir: Path) -> None:
    """Add staged extra wheel files to an installed local solution."""
    for staged_whl_file in _stage_extra_packages_in_solution_dir(solution_dir):
        _execute_command([solution_name, f"poetry add {staged_whl_file.as_posix()}"])


def configure_docker_extra_packages(solution_dir: Path) -> None:
    """Patch the generated Dockerfile to install staged extra wheel files during image builds."""
    staged_wheel_files = _stage_extra_packages_in_solution_dir(solution_dir)
    if not staged_wheel_files:
        return

    dockerfile_path = solution_dir / "deployments" / "Dockerfile"
    dockerfile_content = dockerfile_path.read_text()
    dockerfile_snippet = "RUN poetry install\n"
    extra_packages_install_lines = "".join(
        f"RUN poetry add /tmp/saf-extra-packages/{staged_whl_file.name}\n" for staged_whl_file in staged_wheel_files
    )
    dockerfile_content = dockerfile_content.replace(
        dockerfile_snippet,
        f"COPY .saf-extra-packages /tmp/saf-extra-packages\n{extra_packages_install_lines}{dockerfile_snippet}",
    )
    dockerfile_path.write_text(dockerfile_content)


################################################### LIST SOLUTIONS ####################################################


class ListSolutions(Protocol):
    def __call__(self, expected_return_code: int = 0) -> list[str]: ...


def _list_solutions(expected_return_code: int = 0) -> list[str]:
    p = SAFProcess.run(["solutions"], expected_return_code=expected_return_code)
    return p.output


@pytest.fixture
def list_solutions() -> ListSolutions:
    return _list_solutions


def is_solution_registered(
    solutions_output: list[str],
    solution_root_dir: Path,
    solution_name: str | None = None,
    solution_display_name: str | None = None,
) -> bool:
    solution_name = solution_name or DEFAULT_SOLUTION_NAME
    solution_display_name = solution_display_name or DEFAULT_SOLUTION_DISPLAY_NAME
    solution_str = (
        f"{solution_name}\n    Root directory: {solution_root_dir.resolve()}\n    Display Name: {solution_display_name}"
    )
    return solution_str in "\n".join(solutions_output)


################################################## EXPORT SOLUTIONS ###################################################


class ArchiveSolution(Protocol):
    def __call__(
        self,
        args: list[str] | None = None,
        cwd: Path | None = None,
        expected_return_code: int = 0,
    ) -> SAFProcess: ...


@pytest.fixture
def archive_solution() -> ArchiveSolution:
    def _archive_solution(
        args: list[str] | None = None,
        cwd: Path | None = None,
        expected_return_code: int = 0,
    ) -> SAFProcess:
        p = SAFProcess.run(
            ["archive"] + (args if args is not None else []),
            cwd=cwd,
            expected_return_code=expected_return_code,
        )
        return p

    return _archive_solution


#################################################### RUN SOLUTIONS ####################################################


def check_expected_messages(
    p: SAFProcess,
    solution_display_name: str,
    with_portal: bool = False,
) -> None:
    assert p.find_msg_in_output(f"Solution: {solution_display_name}")
    if with_portal:
        assert p.find_msg_in_output("Project: no project created or selected")
    else:
        project_display_name = p.get_project_display_name()
        assert project_display_name
        project_name = p.get_project_name()
        assert project_name
    solution_api_url = p.get_api_docs_url()
    assert p.find_msg_in_output(f"Solution API: {solution_api_url}")
    solution_ui_url = p.get_solution_ui_url(no_project=with_portal)
    assert p.find_msg_in_output(f"Solution UI: {solution_ui_url}")
    otel_dashboard_url = p.get_otel_dashboard_url()
    assert p.find_msg_in_output(f"OTEL Dashboard: {otel_dashboard_url}")
    # With --portal, the orchestrator uses the projects dashboard if installed, instead of starting a portal.
    uses_projects_dashboard = with_portal and p.get_projects_dashboard_url() is not None
    portal_url = p.get_portal_url() if with_portal and not uses_projects_dashboard else "not launched"
    assert p.find_msg_in_output(f"SAF Portal: {portal_url}")
    # TODO if PIM and additional services get tested, check URL as done for portal
    assert p.find_msg_in_output("PIM Light Server: not launched")
    assert p.find_msg_in_output("Additional services: not launched")


def check_api_is_functional(p: SAFProcess, with_portal: bool = False) -> None:
    api_url = p.get_api_docs_url() if with_portal else p.get_project_api_url()
    response = httpx2.get(api_url)
    assert response.status_code == 200
    if not with_portal:
        assert response.json()["display_name"] == p.get_project_display_name()


def check_ui_is_functional(
    selenium_webdriver: WebDriver,
    p: SAFProcess | None = None,
    project_ui_url: str | None = None,
    with_portal: bool = False,
    timeout: int = 60,
    ui_path_prefix: str = "",
) -> None:
    """
    Check UI is functional. Accepts either a running SAFProcess (p) or a direct project_ui_url.
    If p is provided, uses it to get the solution UI URL. Otherwise, uses project_ui_url directly.
    """
    solution_ui_url = p.get_solution_ui_url(no_project=with_portal) if p is not None else project_ui_url
    if not solution_ui_url:
        raise ValueError("Either p (SAFProcess) or project_ui_url must be provided.")

    if with_portal:
        assert httpx2.get(solution_ui_url).status_code == 200
    else:
        selenium_webdriver.get(solution_ui_url)
        # Assert initial page is About page, showing main image and tree-like menu with the different steps
        wait_for_element(
            selenium_webdriver,
            f"//img[@src='{ui_path_prefix.rstrip('/')}/assets/images/workflow-placeholder.png']",
            element_type=By.XPATH,
            timeout=60,
        )
        wait_for_element_and_click(selenium_webdriver, "//*[contains(text(), 'First Step')]", element_type=By.XPATH)
        # Assert first page is loaded and fields can be entered
        wait_for_expected_property(selenium_webdriver, "result", "value", "0")
        wait_for_element_and_send_text(selenium_webdriver, "first-arg", "4")
        wait_for_element_and_send_text(selenium_webdriver, "second-arg", "3")
        # Assert callback works and updates the result
        wait_for_element_and_click(selenium_webdriver, "calculate")
        wait_for_expected_property(selenium_webdriver, "result", "value", "7", timeout)


def check_orchestrator_process(
    p: SAFProcess,
    solution: SolutionRegistry,
    solution_namespace: str,
    solution_name: str | None = None,
    with_portal: bool = False,
) -> None:
    assert p.process  # just for type checking
    children_cmds: list[list[str]] = []
    for child in psutil.Process(p.process.pid).children(recursive=True):
        try:
            children_cmds.append(child.cmdline())
        except psutil.ZombieProcess:
            continue
        except psutil.Error:
            continue
    expected_python_exec = Path("Scripts") / "python.exe" if platform.system() == "Windows" else Path("bin") / "python"
    expected_orchestrator_proc = [
        (solution.root_dir.resolve() / ".venv" / expected_python_exec).as_posix(),
        "-m",
        "ansys.saf.desktop.orchestrator",
        "--solution-main-module-name",
        f"{solution_namespace}.{solution.name}.main",
    ]
    # TODO extend with other options when tested
    expected_orchestrator_proc += ["--portal"] if with_portal else []
    default_env_file = solution.root_dir.resolve() / ".env"
    if default_env_file.is_file():
        expected_orchestrator_proc += ["--env-file", default_env_file.as_posix()]
    assert expected_orchestrator_proc in children_cmds


class RunSolution(Protocol):
    def __call__(
        self,
        args: list[str] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        wait_for_healthy: bool = True,
    ) -> SAFProcess: ...


@pytest.fixture
def run_solution() -> YieldFixture[RunSolution]:
    procs: list[SAFProcess] = []

    def _run_solution(
        args: list[str] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        wait_for_healthy: bool = True,
    ) -> SAFProcess:
        @retry(stop=stop_after_attempt(720), wait=wait_fixed(0.5))
        def find_final_orchestrator_startup_message(p: SAFProcess):
            if not p.find_msg_in_output("Additional services: "):
                raise TryAgain

        p = SAFProcess.run(
            ["run"] + (args if args is not None else []),
            cwd=cwd,
            bg=wait_for_healthy,
            env=env,
            health_check=find_final_orchestrator_startup_message if wait_for_healthy else None,
        )
        procs.append(p)
        return p

    yield _run_solution

    for p in procs:
        p.stop()


class RunArchivedSolution(Protocol):
    def __call__(self, solution_root_dir: Path, archived_solution: Path) -> SolutionAppStarter: ...


@pytest.fixture
def run_solution_app_starter() -> YieldFixture[RunArchivedSolution]:
    procs: list[SolutionAppStarter] = []

    def _run_solution_app_starter(solution_root_dir: Path, archived_solution: Path) -> SolutionAppStarter:
        p = SolutionAppStarter.run(solution_root_dir, archived_solution)
        procs.append(p)
        return p

    yield _run_solution_app_starter

    for p in procs:
        p.stop()


############################################# EXECUTE COMMANDS IN SOLUTION ############################################


class ExecuteCommand(Protocol):
    def __call__(self, args: list[str], cwd: Path | None = None, expected_return_code: int = 0) -> list[str]: ...


def _execute_command(args: list[str], cwd: Path | None = None, expected_return_code: int = 0) -> list[str]:
    p = SAFProcess.run(["execute"] + args, cwd=cwd, expected_return_code=expected_return_code)
    return p.output


@pytest.fixture
def execute_command() -> ExecuteCommand:
    return _execute_command


################################################### BUILD SOLUTIONS ###################################################


class BuildSolution(Protocol):
    def __call__(
        self,
        args: list[str] | None = None,
        cwd: Path | None = None,
        expected_return_code: int = 0,
    ) -> SAFProcess: ...


@pytest.fixture
def build_solution() -> BuildSolution:
    def _build_solution(
        args: list[str] | None = None,
        cwd: Path | None = None,
        expected_return_code: int = 0,
    ) -> SAFProcess:
        args = args or []
        p = SAFProcess.run(["build"] + (args or []), cwd=cwd, expected_return_code=expected_return_code)
        return p

    return _build_solution


############################################ INSTALL SOLUTION EXECUTABLE #############################################


def get_solution_installer_path(solution_root_dir: Path, display_name: str) -> Path:
    display_name_installer = display_name.lower().replace(" ", "-")
    if platform.system() == "Windows":
        installer = solution_root_dir / "dist" / f"{display_name_installer}-installer.exe"
    elif platform.system() == "Linux":
        installer = solution_root_dir / "dist" / f"{display_name_installer}-installer"
    else:
        raise ValueError("Unsupported operating system")
    return installer


class InstallSolutionExecutable(Protocol):
    def __call__(self, solution_root_dir: Path, tmp_path: Path, display_name: str) -> list[str]: ...


@pytest.fixture
def install_solution_executable() -> InstallSolutionExecutable:
    def _install_solution_executable(solution_root_dir: Path, tmp_path: Path, display_name: str) -> list[str]:
        installer_path = get_solution_installer_path(solution_root_dir, display_name)
        cmd = [str(installer_path), "--no-ui", "--installation-directory", str(tmp_path)]
        p = subprocess.run(cmd, text=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        assert p.returncode == 0, f"Installation failed with error: {p.stdout}"
        return p.stdout.splitlines()

    return _install_solution_executable


def get_shortcut_path(display_name: str) -> Path:
    if platform.system() == "Windows":
        shortcut_path = Path(os.environ["PUBLIC"]) / "Desktop" / f"{display_name}.lnk"
    else:
        shortcut_path = Path(os.environ["HOME"]) / "Desktop" / f"{display_name}.desktop"
    return shortcut_path


############################################ EXECUTE INSTALLED SOLUTION #############################################


@retry(stop=stop_after_attempt(300), wait=wait_fixed(1))
def _get_a_project_identifier(glow_api_port: str) -> str:
    try:
        new_project_json = httpx2.post(
            f"http://127.0.0.1:{glow_api_port}/projects",
            json={"display_name": "test"},
        ).json()
        if not new_project_json:
            raise TryAgain
    except Exception:
        raise
    project_identifier: str = new_project_json["name"].removeprefix("projects/")
    return project_identifier


@retry(stop=stop_after_attempt(300), wait=wait_fixed(1))
def _check_service_health(url: str):
    try:
        response = httpx2.get(url)
        if not response.status_code == 200:
            raise TryAgain
    except Exception:
        raise


def check_solution_launched_correctly(
    glow_api_port: str,
    glow_ui_port: str,
    portal_ui_port: str | None = None,
    ui_path_prefix: str = "",
) -> str:
    if portal_ui_port:
        portal_url = f"http://127.0.0.1:{portal_ui_port}"
        _check_service_health(portal_url)

    api_url = f"http://127.0.0.1:{glow_api_port}/docs"
    _check_service_health(api_url)

    project_identifier = _get_a_project_identifier(glow_api_port)

    ui_url = f"http://127.0.0.1:{glow_ui_port}{ui_path_prefix.rstrip('/')}/projects/{project_identifier}"
    _check_service_health(ui_url)

    return ui_url


class RunInstalledSolution(Protocol):
    def __call__(self, shortcut_path: Path) -> SolutionShortcutPythonwProcess: ...


@pytest.fixture
def run_installed_solution() -> YieldFixture[RunInstalledSolution]:
    procs: list[SolutionShortcutPythonwProcess] = []

    def _run_installed_solution(shortcut_path: Path) -> SolutionShortcutPythonwProcess:
        p = SolutionShortcutPythonwProcess.run(shortcut_path)
        procs.append(p)
        return p

    yield _run_installed_solution

    for p in procs:
        p.stop()


################################################### STEP MANAGEMENT ###################################################


class AddStep(Protocol):
    def __call__(
        self,
        args: list[str] | None = None,
        cwd: Path | None = None,
        input_str: str = "",
        expected_return_code: int = 0,
    ) -> SAFProcess: ...


@pytest.fixture
def add_step() -> AddStep:
    def _add_step(
        args: list[str] | None = None,
        cwd: Path | None = None,
        input_str: str = "",
        expected_return_code: int = 0,
    ) -> SAFProcess:
        p = SAFProcess.run(
            ["add-step"] + (args if args is not None else []),
            cwd=cwd,
            input_str=input_str,
            expected_return_code=expected_return_code,
        )
        return p

    return _add_step


################################################## LINTING TEMPLATES ##################################################


def lint_scaffolded_solution(solution_root_dir: Path, solution_name: str, solution_namespace: str) -> None:
    # can't use `pre-commit run --all-files` because the scaffolded solution is not in a git repo

    def _run_linting_tool(solution_root_dir: Path, tool: str, args: list[str]) -> str:
        tool_exec = find_exec_in_venv(solution_root_dir, tool)
        return subprocess.check_output(
            [tool_exec] + args,
            cwd=solution_root_dir,
            stderr=subprocess.STDOUT,
            text=True,
        )

    solution_main_file = solution_root_dir / "src" / namespace_to_path(solution_namespace) / solution_name / "main.py"
    assert solution_main_file.is_file()
    pyproject_file = solution_root_dir / "pyproject.toml"
    assert pyproject_file.is_file()

    out = _run_linting_tool(solution_root_dir, "black", ["."])
    assert "reformatted" not in out.strip().splitlines()[-1]
    # introduce an error on purpose to verify that the process works (error is automatically fixed)
    solution_main_file.write_text(
        solution_main_file.read_text().replace("glow_main(definition, app)", "glow_main(definition,\napp)"),
    )
    out = _run_linting_tool(solution_root_dir, "black", ["."])
    assert out.strip().splitlines()[0] == f"reformatted {solution_main_file}"
    assert "1 file reformatted" in out.strip().splitlines()[-1]

    out = _run_linting_tool(solution_root_dir, "isort", ["."])
    assert out.strip() == "Skipped 2 files"
    # introduce an error on purpose to verify that the process works
    solution_main_file.write_text(
        solution_main_file.read_text().replace(
            "from ansys.saf.glow.runtime import glow_main\n",
            "from ansys.saf.glow.runtime import glow_main\nimport re\n",
        ),
    )
    out = _run_linting_tool(solution_root_dir, "isort", ["."])
    assert out.strip() == f"Fixing {solution_main_file}\nSkipped 2 files"
    solution_main_file.write_text(solution_main_file.read_text().replace("import re\n", ""))

    out = _run_linting_tool(solution_root_dir, "flake8", ["."])
    assert out.strip() == "0"
    # introduce an error on purpose to verify that the process works
    solution_main_file.write_text(
        solution_main_file.read_text().replace(
            "from ansys.saf.glow.runtime import glow_main\n",
            "from ansys.saf.glow.runtime import glow_main\nimport re\n",
        ),
    )
    with pytest.raises(subprocess.CalledProcessError):
        _run_linting_tool(solution_root_dir, "flake8", ["."])
    solution_main_file.write_text(solution_main_file.read_text().replace("import re\n", ""))

    out = _run_linting_tool(
        solution_root_dir,
        "codespell",
        ["--skip", ".venv,.poetry,doc/styles/*,*.js,*.tmp,*.lock", "--ignore-words", ".codespell.ignore"],
    )
    assert out.strip() == "0"
    # introduce an error on purpose to verify that the process works
    solution_main_file.write_text(
        solution_main_file.read_text().replace('"""Entry point."""', '"""Entry piont."""'),  # codespell:ignore piont
    )
    with pytest.raises(subprocess.CalledProcessError):
        _run_linting_tool(
            solution_root_dir,
            "codespell",
            ["--skip", ".venv,.poetry,doc/styles/*,*.js,*.tmp,*.lock", "--ignore-words", ".codespell.ignore"],
        )
    solution_main_file.write_text(
        solution_main_file.read_text().replace('"""Entry piont."""', '"""Entry point."""'),  # codespell:ignore piont
    )

    _run_linting_tool(solution_root_dir, "pydocstyle", ["./src"])
    # introduce an error on purpose to verify that the process works
    solution_main_file.write_text(
        solution_main_file.read_text().replace('def main():\n    """Entry point."""\n', "def main():\n"),
    )
    with pytest.raises(subprocess.CalledProcessError):
        _run_linting_tool(solution_root_dir, "pydocstyle", ["./src"])
    solution_main_file.write_text(
        solution_main_file.read_text().replace("def main():\n", 'def main():\n    """Entry point."""\n'),
    )

    out = _run_linting_tool(solution_root_dir, "poetry", ["check"])
    assert out.strip() == "All set!"
    # introduce an error on purpose to verify that the process works
    # NOTE: with the current saf install implementation, if there is an issue in poetry.lock,
    # it will fail in the saf install and this will not be reached. Leaving it for future-proof.
    original = pyproject_file.read_text()
    pyproject_file.write_text(original.replace('python = ">=3.11,<3.15"', 'python = "test"'))
    with pytest.raises(subprocess.CalledProcessError):
        _run_linting_tool(solution_root_dir, "poetry", ["check"])
    pyproject_file.write_text(original)


def is_lint_dot_github_workflow_folder_successful(root_path: Path, solution_name: str) -> bool:
    solution_root_dir = root_path / solution_name
    github_workflows_directory = solution_root_dir / ".github" / "workflows"

    for item in github_workflows_directory.iterdir():
        result = subprocess.run(
            ["actionlint", str(item)],
            capture_output=True,
            text=True,
        )

        if result.stdout != "":
            return False

    return True


################################################### SESSION SOLUTIONS ##################################################
# Use these session solutions when the test requires a solution with its environment created and its dependencies
# installed. Make sure to revert any change to the solution to avoid leakage to future tests.
# TODO: extend to doing it once and then copying it to every worker. However, it should be done only for the UI
# frameworks that are parametrized in one of the selected tests. We could optimize it further by selectively copying to
# the workers based on the parameters of their selected tests.

SESSION_SOLUTIONS: dict[tuple[str, str], SolutionRegistry] = {}


@pytest.fixture(scope="session")
def session_solution_ui_framework(request: pytest.FixtureRequest) -> str:
    # We don't provide a default to avoid tests thinking that they are getting the default UI framework when they are
    # instead getting the last state left by a previous test.
    return request.param


@pytest.fixture(scope="session")
def session_solution_namespace(request: pytest.FixtureRequest) -> str:
    # Return the parametrized namespace or the default if not parametrized.
    # This allows tests to reuse solutions across different namespaces.
    param = getattr(request, "param", DEFAULT_SOLUTION_NAMESPACE)
    return param if param is not None else DEFAULT_SOLUTION_NAMESPACE


@pytest.fixture(scope="session")
def session_solution(
    mock_session_appdata: Path,
    session_solution_ui_framework: str,
    session_solution_namespace: str,
) -> SolutionRegistry:
    session_solutions_dir = mock_session_appdata / "solutions"
    session_solutions_dir.mkdir(exist_ok=True)

    session_key = (session_solution_ui_framework, session_solution_namespace)
    if session_key not in SESSION_SOLUTIONS:
        random_id = str(random.randint(0, 10000)).zfill(5)
        solution_name = f"test_solution_{random_id}"
        solution_display_name = f"Test Solution {random_id}"

        _new_solution(
            args=[
                "--namespace",
                session_solution_namespace,
            ],
            cwd=session_solutions_dir,
            input_str=f"{solution_name}\n{solution_display_name}\n{session_solution_ui_framework}\n\n",
        )
        assert is_solution_registered(
            _list_solutions(),
            session_solutions_dir / solution_name,
            solution_name=solution_name,
            solution_display_name=solution_display_name,
        )

        # Letting each test install the dependency groups that it needs leads to an inconsistent order of
        # installation because they are not always executed in the same order. That is why we install all
        # dependency groups here. Also, this way we avoid having to call install_solution in many tests.
        _install_solution([solution_name, "-d", "all"])

        # Adding private dependencies to solution
        add_extra_packages_to_solution(solution_name, session_solutions_dir / solution_name)

        SESSION_SOLUTIONS[session_key] = SolutionRegistry(
            name=solution_name,
            root_dir=session_solutions_dir / solution_name,
            display_name=solution_display_name,
        )

    return SESSION_SOLUTIONS[session_key]


@pytest.fixture
def temporary_python_script(session_solution: SolutionRegistry) -> YieldFixture[Path]:
    script_path = session_solution.root_dir / "my_scripts" / "script.py"
    script_path.parent.mkdir()
    yield script_path
    shutil.rmtree(script_path.parent)


@pytest.fixture
def cleanup_built_documentation(
    session_solution: SolutionRegistry,
    session_solution_namespace: str,
) -> YieldFixture[None]:
    yield
    doc_dev_dir = session_solution.root_dir / "doc" / "build"
    if doc_dev_dir.is_dir():
        shutil.rmtree(doc_dev_dir)
    doc_prod_dir = (
        session_solution.root_dir
        / "src"
        / namespace_to_path(session_solution_namespace)
        / session_solution.name.replace("-", "_")
        / "html-doc"
    )
    if doc_prod_dir.is_dir():
        shutil.rmtree(doc_prod_dir)


@pytest.fixture
def env_file_with_mock_value(session_solution: SolutionRegistry) -> YieldFixture[tuple[str, str]]:
    solution_env_file = session_solution.root_dir / ".env"
    backup_env_file = session_solution.root_dir / ".env.backup"
    shutil.copyfile(solution_env_file, backup_env_file)
    random_name = f"MY_CUSTOM_ENV_VAR_{str(random.randint(0, 1000)).zfill(4)}"
    random_value = str(uuid.uuid4())
    solution_env_file.write_text(f"{random_name}={random_value}")
    yield (random_name, random_value)
    shutil.copyfile(backup_env_file, solution_env_file)
    backup_env_file.unlink()


@pytest.fixture
def cleanup_solution_src(tmp_path: Path, session_solution: SolutionRegistry) -> YieldFixture[None]:
    solution_src_dir = session_solution.root_dir / "src"
    backup_src_dir = tmp_path / "solution_src_backup"
    shutil.copytree(solution_src_dir, backup_src_dir)
    yield
    shutil.rmtree(solution_src_dir)
    shutil.copytree(backup_src_dir, solution_src_dir)


@pytest.fixture
def cleanup_solution_pyproject(tmp_path: Path, session_solution: SolutionRegistry) -> YieldFixture[None]:
    solution_pyproject_file = session_solution.root_dir / "pyproject.toml"
    backup_pyproject_file = tmp_path / "pyproject_backup.toml"
    shutil.copyfile(solution_pyproject_file, backup_pyproject_file)
    yield
    solution_pyproject_file.unlink(missing_ok=True)
    shutil.copyfile(backup_pyproject_file, solution_pyproject_file)


@pytest.fixture
def cleanup_solution_poetry_lock(tmp_path: Path, session_solution: SolutionRegistry) -> YieldFixture[None]:
    solution_poetry_lock_file = session_solution.root_dir / "poetry.lock"
    backup_poetry_lock_file = tmp_path / "poetry_lock_backup.lock"
    shutil.copyfile(solution_poetry_lock_file, backup_poetry_lock_file)
    yield
    solution_poetry_lock_file.unlink(missing_ok=True)
    shutil.copyfile(backup_poetry_lock_file, solution_poetry_lock_file)


@pytest.fixture
def cleanup_solution_venv(tmp_path: Path, session_solution: SolutionRegistry) -> YieldFixture[None]:
    @retry(stop=stop_after_attempt(12), wait=wait_fixed(5))
    def _remove_tree_with_retry(solution_venv_dir: Path) -> None:
        try:
            shutil.rmtree(solution_venv_dir)
        except Exception:
            raise TryAgain from None

    solution_venv_dir = session_solution.root_dir / ".venv"
    backup_venv_dir = tmp_path / "venv_backup"
    shutil.copytree(solution_venv_dir, backup_venv_dir)
    yield
    _remove_tree_with_retry(solution_venv_dir)
    shutil.copytree(backup_venv_dir, solution_venv_dir)


@pytest.fixture
def cleanup_solution_dist(session_solution: SolutionRegistry) -> YieldFixture[None]:
    yield
    solution_dist_dir = session_solution.root_dir / "dist"
    shutil.rmtree(solution_dist_dir)


@pytest.fixture
def cleanup_solution_wheels_dir(session_solution: SolutionRegistry) -> YieldFixture[None]:
    yield
    solution_wheels_dir = session_solution.root_dir / "wheels"
    shutil.rmtree(solution_wheels_dir)


@pytest.fixture
def restore_glow_env_vars(session_solution: SolutionRegistry) -> Generator[None, None, None]:
    env_file = session_solution.root_dir / ".env"

    original_content = env_file.read_text() if env_file.is_file() else None

    if original_content is not None:
        excluded_prefixes = (
            "GLOW_SOLUTION_DEFINITION=",
            "GLOW_UI_MODULE=",
        )

        env_file.write_text(
            "\n".join(line for line in original_content.splitlines() if not line.startswith(excluded_prefixes)),
        )

    yield

    # Restore original state
    if original_content is not None:
        env_file.write_text(original_content)
    else:
        env_file.unlink(missing_ok=True)


################################################### UPDATE SOLUTIONS ##################################################


def _add_saf_sdk_extra_to_main_group(solution_dir: Path, extra: str) -> None:
    """Add an extra to the ansys-saf-sdk dependency of the main poetry group, whether it's a string or a table."""
    pyproject_file = solution_dir / "pyproject.toml"
    pyproject = tomlkit.parse(pyproject_file.read_text())
    saf_sdk_dependency = pyproject["tool"]["poetry"]["dependencies"]["ansys-saf-sdk"]  # type: ignore[index]
    if isinstance(saf_sdk_dependency, str):
        pyproject["tool"]["poetry"]["dependencies"]["ansys-saf-sdk"] = {  # type: ignore[index]
            "version": saf_sdk_dependency,
            "extras": [extra],
        }
    else:
        extras = saf_sdk_dependency.setdefault("extras", [])  # type: ignore
        if extra not in extras:
            extras.append(extra)  # type: ignore[reportUnknownMemberType]
    pyproject_file.write_text(tomlkit.dumps(pyproject))  # type: ignore[reportUnknownMemberType]


def add_hps_extra_to_solution(solution_dir: Path, solution_name: str) -> None:
    _add_saf_sdk_extra_to_main_group(solution_dir, "core-hps")
    _execute_command([solution_name, "poetry lock"])


def configure_hps_solution(solution_dir: Path, solution_name: str, solution_namespace: str) -> None:
    """
    Configures the solution to use HPS by updating steps/pages.
    """
    # add core-hps extra to the main saf-sdk dependency
    add_hps_extra_to_solution(solution_dir, solution_name)

    # update first step and first page to use HPS
    first_step_path = (
        solution_dir / "src" / namespace_to_path(solution_namespace) / solution_name / "solution" / "first_step.py"
    )
    first_step_with_hps_path = Path(__file__).parent.parent / "mocks" / "steps" / "first_step_with_hps.py"
    first_step_path.write_text(first_step_with_hps_path.read_text())
    first_page_path = (
        solution_dir / "src" / namespace_to_path(solution_namespace) / solution_name / "ui" / "pages" / "first_page.py"
    )
    first_page_with_hps_path = Path(__file__).parent.parent / "mocks" / "pages" / "first_page_with_hps.py"
    first_page_path.write_text(first_page_with_hps_path.read_text())

    # Add script used by hps job
    scripts_dir = solution_dir / "src" / namespace_to_path(solution_namespace) / solution_name / "solution" / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    simple_add_source_path = Path(__file__).parent.parent / "mocks" / "scripts" / "simple_add.py"
    (scripts_dir / "simple_add.py").write_text(simple_add_source_path.read_text())


def configure_solution_to_store_result_in_file(
    solution_dir: Path,
    solution_name: str,
    solution_namespace: str,
) -> None:
    """
    Configures the solution to store the result in a file and display it from there.
    """
    first_step_path = (
        solution_dir / "src" / namespace_to_path(solution_namespace) / solution_name / "solution" / "first_step.py"
    )
    first_step_with_file_output_path = (
        Path(__file__).parent.parent / "mocks" / "steps" / "first_step_with_file_output.py"
    )
    first_step_path.write_text(first_step_with_file_output_path.read_text())

    first_page_path = (
        solution_dir / "src" / namespace_to_path(solution_namespace) / solution_name / "ui" / "pages" / "first_page.py"
    )
    first_page_with_file_output_path = (
        Path(__file__).parent.parent / "mocks" / "pages" / "first_page_with_file_output.py"
    )
    first_page_path.write_text(first_page_with_file_output_path.read_text())


################################################### LIST TEMPLATES ####################################################


class ListTemplates(Protocol):
    def __call__(self, args: list[str] | None = None) -> list[str]: ...


def _list_templates(args: list[str] | None = None) -> list[str]:
    p = SAFProcess.run(["templates"] + (args if args else []))
    return p.output


@pytest.fixture
def list_templates() -> ListTemplates:
    return _list_templates
