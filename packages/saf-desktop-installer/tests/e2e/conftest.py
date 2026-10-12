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

import ast
from collections.abc import Callable, Generator
import configparser
import getpass
import json
import logging
import os
from pathlib import Path
import platform
import random
import shlex
import shutil
import subprocess
import sys
from typing import Any, Protocol
import venv
import zipfile

from dotenv import set_key
import httpx2
from packaging.markers import Marker
from packaging.version import parse as parse_version
from pylnk3 import Lnk, parse  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed
import toml

from ansys.saf.desktop.installer.__main__ import _load_filtered_dotenv  # pyright: ignore[reportPrivateUsage]
from ansys.saf.desktop.installer._package.download_python import MINIMUM_REQUIRED_VERSIONS
from ansys.saf.desktop.installer._package.solution import get_solution_namespace_info
from ansys.saf.desktop.installer.solution_desktop_deployment import TARGET_SOLUTIONS_DIRECTORY_NAME
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.network import get_random_free_port
from ansys.saf.testing.platform_specific import is_ci_run
from ansys.saf.testing.selenium import (
    wait_for_element_and_click,
    wait_for_element_and_send_text,
    wait_for_text,
)
from tests.e2e.installer_process import SolutionInstallerProcess
from tests.e2e.solution_process import SolutionShortcutProcess
from tests.utils import get_appdata_directory

SOLUTION_DISPLAY_NAME = {
    "my-solution-dash": "My Solution Dash",
    "my-solution-dash-without-portal": "My Solution Dash",
    "my-solution-dash-old": "My Solution Dash Old",
    "synopsys-custom-ns-solution": "Custom NS Solution",
}
SOLUTION_CLASS_NAME = {
    "my-solution-dash": "MySolutionDashSolution",
    "my-solution-dash-without-portal": "MySolutionDashSolution",
    "my-solution-dash-old": "MySolutionDashOldSolution",
    "synopsys-custom-ns-solution": "MyCustomNSSolution",
}
SOLUTION_EXTRA_PACKAGES = {
    "my-solution-dash": {"ansys_saf_desktop_portal": "desktop", "ansys_saf_aspire": "desktop"},
    "my-solution-dash-without-portal": {"ansys_saf_aspire": "desktop"},
    "my-solution-dash-old": {"ansys_saf_desktop_portal": "desktop", "ansys_saf_aspire": "desktop"},
    "synopsys-custom-ns-solution": {"ansys_saf_desktop_portal": "desktop", "ansys_saf_aspire": "desktop"},
}
logger = logging.getLogger(__name__)
# Cache for session solutions
_session_solutions_cache: dict[str, tuple[Path, Path, str, str, str]] = {}


#################################################### PREREQUISITES ####################################################


@pytest.fixture(scope="class")
def check_gtk_launch_and_xvfb_are_installed():
    if platform.system() == "Linux" and (not shutil.which("gtk-launch") or not shutil.which("xvfb-run")):
        raise RuntimeError(
            "gtk-launch and xvfb need to be installed to execute these tests. Run:\n"
            "sudo apt update\nsudo apt install libgtk-3-bin xvfb",
        )


def only_for_ci(reason: str = "Only run on the CI."):
    return pytest.mark.skipif(not is_ci_run(), reason=reason)


###################################################### UTILITIES ######################################################


def find_msg_in_output(msg: str, output: list[str]) -> str | None:
    for line in output:
        if msg in line:
            return line


@pytest.fixture
def copy_assets() -> Generator[None, None, None]:
    """Copy installer UI assets required when launching InstallerUIProcess from source."""
    installer_path = Path(__file__).parent.parent.parent / "src" / "ansys" / "saf" / "desktop" / "installer"
    source_logo_path = installer_path / "_package" / "assets" / "installer_ui_logo.png"
    bootstrap_css_path = installer_path / "_package" / "assets" / "bootstrap.min.css"
    assert source_logo_path.is_file(), f"Source logo not found at {source_logo_path}"
    assert bootstrap_css_path.is_file(), f"Bootstrap css not found at {bootstrap_css_path}"

    destination_dir = installer_path / "assets"
    destination_dir.mkdir(exist_ok=True)
    shutil.copy(source_logo_path, destination_dir / "installer_ui_logo.png")
    shutil.copy(bootstrap_css_path, destination_dir / "bootstrap.min.css")

    yield

    if destination_dir.is_dir():
        shutil.rmtree(destination_dir)


@pytest.fixture
def cleanup_shortcut() -> Generator[list[Path], None, None]:
    """Fixture to track and remove the shortcut file created during the test."""
    shortcuts: list[Path] = []

    yield shortcuts

    for shortcut in shortcuts:
        shortcut.unlink(missing_ok=True)
        # For Linux we need to copy the shortcut to ~/.local/share/applications so that it can be launched
        # using gtk-launch. Here we remove this copy.
        if platform.system() == "Linux":
            apps_path = Path(os.environ.get("HOME", "")) / ".local" / "share" / "applications"
            (apps_path / shortcut.name).unlink(missing_ok=True)


@pytest.fixture
def cleanup_solution_installed_by_root(solution_root_dir: Path) -> Generator[None, None, None]:
    """Fixture to track and remove the solution installed by root during the test."""
    yield
    solution_root_dir = (
        Path("/opt") / "ansys_inc" / TARGET_SOLUTIONS_DIRECTORY_NAME / SOLUTION_CLASS_NAME[solution_root_dir.name]
    )
    if solution_root_dir.is_dir():
        shutil.rmtree(solution_root_dir)


def modify_solution_module_name(solution_root_dir: Path) -> None:
    # Change the solution module name (only applicable to the legacy ansys.solutions mock)
    namespace_root_parts, old_module_name = get_solution_namespace_info(solution_root_dir)
    old_module_path = solution_root_dir / "src" / Path(*namespace_root_parts) / old_module_name
    new_module_name = old_module_name.replace("_", "")
    new_module_path = old_module_path.parent / new_module_name
    shutil.move(old_module_path, new_module_path)
    old_dotted = ".".join([*namespace_root_parts, old_module_name])
    new_dotted = ".".join([*namespace_root_parts, new_module_name])
    # Update the imports in the solution's code
    for path in solution_root_dir.rglob("src/**/*.py"):
        file_path = solution_root_dir / path
        file_path.write_text(file_path.read_text().replace(old_dotted, new_dotted))


################################################### SOLUTION SETUP ####################################################


def _create_virtual_environment(solution_venv_dir: Path) -> None:
    if solution_venv_dir.is_dir():
        shutil.rmtree(solution_venv_dir)
    solution_venv_dir.mkdir(parents=True)
    venv.EnvBuilder(with_pip=True).create(solution_venv_dir)


def _get_virtual_environment_executable_path(venv_dir: Path, executable_name: str) -> Path:
    if platform.system() == "Windows":
        venv_dir_exec = venv_dir / "Scripts" / f"{executable_name}.exe"
    elif platform.system() == "Linux":
        venv_dir_exec = venv_dir / "bin" / f"{executable_name}"
    else:
        raise ValueError("Unsupported operating system")
    return venv_dir_exec


def _get_poetry_link_command(poetry_env_poetry_exec: Path, solution_env_poetry_exec: Path):
    if platform.system() == "Windows":
        cmd = [
            "powershell",
            "-Command",
            "New-Item",
            "-ItemType",
            "HardLink",
            "-Path",
            solution_env_poetry_exec.as_posix(),
            "-Target",
            poetry_env_poetry_exec.as_posix(),
        ]
    elif platform.system() == "Linux":
        cmd = [
            "ln",
            poetry_env_poetry_exec.as_posix(),
            solution_env_poetry_exec.as_posix(),
        ]
    else:
        raise ValueError("Unsupported operating system")
    return cmd


class SetupSolution(Protocol):
    def __call__(self, solution_root_dir: Path) -> tuple[Path, str, str, str]: ...


def _setup_solution(solution_root_dir: Path) -> tuple[Path, str, str, str]:
    # setup a working venv for the solution like what saf install would do in a real setup.
    solution_pyproject_data = toml.load(solution_root_dir / "pyproject.toml")
    solution_env = os.environ.copy()
    _load_filtered_dotenv(solution_root_dir / ".env", solution_env)

    solution_venv_dir = solution_root_dir / ".venv"
    _create_virtual_environment(solution_venv_dir)
    assert solution_venv_dir.is_dir()
    solution_env["VIRTUAL_ENV"] = solution_venv_dir.as_posix()  # for poetry to install dependencies in the right venv

    poetry_venv_dir = solution_root_dir / ".poetry" / ".venv"
    _create_virtual_environment(poetry_venv_dir)
    assert poetry_venv_dir.is_dir()

    poetry_venv_pip_exec = _get_virtual_environment_executable_path(poetry_venv_dir, "pip")
    poetry_version: str = solution_pyproject_data["build-system-requirements"]["build-system-version"]
    cmd = [poetry_venv_pip_exec, "install", f"poetry=={poetry_version}"]
    subprocess.run(cmd)
    # Install poetry-plugin-export if poetry >= 2.0.0 as it is not longer included by default.
    if poetry_version.startswith("2."):
        cmd = [poetry_venv_pip_exec, "install", "poetry-plugin-export>=1.8"]
        subprocess.run(cmd)

    # virtualenv 20.31.0 incompatible with poetry < 2
    if poetry_version.startswith("1."):
        subprocess.run([poetry_venv_pip_exec, "install", "virtualenv==20.30.0"])

    # It is necessary to create the poetry.exe file in the solution environment because it is called
    # in _package/solution.py
    poetry_venv_poetry_exec = _get_virtual_environment_executable_path(poetry_venv_dir, "poetry")
    assert poetry_venv_poetry_exec.is_file()
    solution_venv_poetry_exec = _get_virtual_environment_executable_path(solution_venv_dir, "poetry")
    assert not solution_venv_poetry_exec.is_file()
    cmd = _get_poetry_link_command(poetry_venv_poetry_exec, solution_venv_poetry_exec)
    subprocess.run(cmd)
    assert solution_venv_poetry_exec.is_file()

    # we copy the installer code to a new folder on the same mount as the solution
    # otherwise the poetry add that follows will fail
    installer_src_dir = Path(__file__).parent.parent.parent
    installer_lib_dest_dir = solution_root_dir.parent / "saf-desktop-installer"
    installer_lib_dest_dir.mkdir()
    shutil.copytree(
        installer_src_dir,
        installer_lib_dest_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "doc",
            ".poetry",
            ".github",
            ".ruff_cache",
            ".venv",
            "tests",
            "*.pyc",
            "__pycache__",
        ),
    )

    # add private packages to the solution
    _add_extra_packages_to_solution(
        solution_root_dir,
        solution_venv_poetry_exec,
        solution_env,
        SOLUTION_EXTRA_PACKAGES[solution_root_dir.name],
    )

    # create a dependency on the src installer in the build group via poetry add
    if solution_root_dir.name == "my-solution-dash-old":
        cmd = [solution_venv_poetry_exec, "add", "--group", "desktop", installer_lib_dest_dir.as_posix()]
        subprocess.run(cmd, cwd=solution_root_dir, env=solution_env, check=True)
    cmd = [solution_venv_poetry_exec, "add", "--group", "build", installer_lib_dest_dir.as_posix()]
    subprocess.run(cmd, cwd=solution_root_dir, env=solution_env, check=True)

    # install the solution dependencies
    cmd = [solution_venv_poetry_exec, "install", "--all-groups"]
    subprocess.run(cmd, cwd=solution_root_dir, env=solution_env, check=True)

    env_path = solution_root_dir / ".env"
    # Replace APPDATA_PLACEHOLDER in the solution's .env file with the appropriate value according to the OS.
    appdata_directory = get_appdata_directory()
    env_content = env_path.read_text() if env_path.is_file() else ""
    env_path.write_text(env_content.replace("APPDATA_PLACEHOLDER", appdata_directory))
    glow_api_port = str(get_random_free_port())
    glow_ui_port = str(get_random_free_port())
    portal_ui_port = str(get_random_free_port())
    set_key(env_path, "GLOW_API_PORT", glow_api_port)
    set_key(env_path, "GLOW_UI_PORT", glow_ui_port)
    set_key(env_path, "PORTAL_UI_PORT", portal_ui_port)

    solution_venv_python_exec = _get_virtual_environment_executable_path(solution_venv_dir, "python")
    assert solution_venv_python_exec.is_file()

    return solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port


@pytest.fixture
def setup_solution() -> SetupSolution:
    """Fixture to set up a solution in a temporary directory."""
    return _setup_solution


@pytest.fixture(scope="session")
def session_solution_factory(
    tmp_path_factory: pytest.TempPathFactory,
) -> Callable[[str], tuple[Path, Path, str, str, str]]:
    """Factory to create session solutions with different parameters."""

    def _get_or_create_solution(solution_name: str = "my-solution-dash") -> tuple[Path, Path, str, str, str]:
        if solution_name in _session_solutions_cache:
            logger.info(f"Using cached session solution: {solution_name}")
            return _session_solutions_cache[solution_name]

        logger.info(f"Creating new session solution: {solution_name}")

        # Create a session-level temp directory
        session_tmp = tmp_path_factory.mktemp(f"session_solution_{solution_name}")

        # Copy the solution template to session directory
        test_assets_dir = Path(__file__).parent.parent / "mocks"
        template_dir = test_assets_dir / solution_name

        if not template_dir.exists():
            raise ValueError(f"Solution template not found: {template_dir}")

        solution_root_dir = session_tmp / solution_name
        shutil.copytree(template_dir, solution_root_dir)

        # Use the extracted _setup_solution function directly
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = _setup_solution(solution_root_dir)

        result = (solution_root_dir, solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port)
        _session_solutions_cache[solution_name] = result
        logger.info(f"Cached session solution: {solution_name}")
        return result

    return _get_or_create_solution


@pytest.fixture(scope="session")
def session_solution_setup(
    session_solution_factory: Callable[[str], tuple[Path, Path, str, str, str]],
) -> tuple[Path, Path, str, str, str]:
    """Default session solution setup for my-solution-dash."""
    return session_solution_factory("my-solution-dash")


def _add_extra_packages_to_solution(
    solution_root_dir: Path,
    solution_venv_poetry_exec: Path,
    solution_env: dict[str, str],
    packages_to_add: dict[str, str],
) -> None:
    """Copy extra wheel files into the solution directory and add them to the solution."""
    extra_packages_dir = os.getenv("SAF_EXTRA_PACKAGES_DIR", None)
    if not extra_packages_dir:
        return None

    staged_dir = solution_root_dir / ".saf-extra-packages"
    staged_dir.mkdir(exist_ok=True)

    for whl_file in Path(extra_packages_dir).resolve().glob("*.whl"):
        for package_name, group_to_add in packages_to_add.items():
            if not whl_file.name.startswith(package_name):
                continue
            staged_whl_file = staged_dir / whl_file.name
            shutil.copy2(whl_file, staged_whl_file)
            subprocess.run(
                [solution_venv_poetry_exec, "add", "--group", group_to_add, staged_whl_file.as_posix()],
                cwd=solution_root_dir,
                env=solution_env,
                check=True,
            )


################################################### SOLUTION BUILD ####################################################


def _get_solution_module_name(solution_root_dir: Path) -> str:
    _, solution_module_name = get_solution_namespace_info(solution_root_dir)
    return solution_module_name


def _get_built_solution_embeddable_python_executable(
    solution_root_dir: Path,
    force_python_from_source: bool,
) -> Path | None:
    python_dir = solution_root_dir / "dist" / "solution" / "third_party" / "python"
    if platform.system() == "Windows":
        if force_python_from_source:
            python_file_path = python_dir / "python.exe"
        else:
            python_file_path = next(python_dir.glob("**/python.exe"), None)
    elif platform.system() == "Linux":
        python_file_path = python_dir / "bin" / "python3"
    else:
        raise ValueError("Unsupported operating system")
    return python_file_path


def _get_expected_build_packages(build_packages_directory: Path, solution_root_dir: Path) -> list[Path]:
    pyproject_content = toml.load(solution_root_dir / build_packages_directory / "pyproject.toml")
    expected_build_packages: list[Path] = []
    dependencies = pyproject_content["tool"]["poetry"]["dependencies"]
    for dep in dependencies:
        if (
            dep not in ["python", "ansys-saf-desktop-installer"]
            and isinstance(dependencies[dep], dict)
            and "path" in dependencies[dep]
        ):
            expected_build_packages.append(build_packages_directory / dependencies[dep]["path"])
    return expected_build_packages


def _get_common_built_solution_files(
    solution_module_name: str,
    solution_package_name: str,
    solution_root_dir: Path,
) -> list[Path]:
    dist_dir = Path("dist")
    shortcut_suffix = ".ico" if platform.system() == "Windows" else ".png"
    expected_solution_files = [
        dist_dir / f"{solution_package_name}-0.1.dev0-py3-none-any.whl",
        dist_dir / f"{solution_package_name}-0.1.dev0.tar.gz",
        dist_dir / "solution" / "solution-metadata.json",
        dist_dir / "solution" / "solution_desktop_deployment.py",
        dist_dir / "solution" / "version.txt",
        dist_dir / "solution" / "assets" / "favicon.ico",
        dist_dir / "solution" / "assets" / "favicon.png",
        dist_dir / "solution" / "assets" / f"shortcut{shortcut_suffix}",
        dist_dir / "solution" / "assets" / "installer_ui_logo.png",
        dist_dir / "solution" / "definitions" / solution_module_name / ".env",
        dist_dir / "solution" / "definitions" / solution_module_name / "pyproject.toml",
        dist_dir / "solution" / "definitions" / solution_module_name / "poetry.lock",
        dist_dir / "solution" / "definitions" / solution_module_name / "tools" / "pip_requirements.txt",
        dist_dir / "solution" / "definitions" / solution_module_name / "tools" / "poetry_requirements.txt",
    ]
    expected_build_packages = _get_expected_build_packages(
        dist_dir / "solution" / "definitions" / solution_module_name,
        solution_root_dir,
    )
    return expected_solution_files + expected_build_packages


def _get_solution_installer_path(solution_root_dir: Path) -> Path:
    dist_dir = solution_root_dir / "dist"
    if platform.system() == "Windows":
        installer_files = sorted(dist_dir.glob("*-installer.exe"))
    elif platform.system() == "Linux":
        installer_files = sorted(path for path in dist_dir.glob("*-installer") if path.is_file())
    else:
        raise ValueError("Unsupported operating system")

    if installer_files:
        return installer_files[0]

    installer_path = dist_dir / f"{solution_root_dir.name}-installer"
    installer_path = installer_path / installer_path.name if installer_path.is_dir() else installer_path
    return installer_path.with_suffix(".exe") if platform.system() == "Windows" else installer_path


def check_built_solution_files(
    solution_root_dir: Path,
    with_installer: bool = True,
    with_pyproject: bool = True,
    with_python: bool = True,
    offline_package: bool = False,
    with_documentation: bool = True,
    with_method_assets: bool = True,
    with_encrypted_assets: bool = False,
    python_version: str | None = None,
    force_python_from_source: bool = False,
    executable_as_dir: bool = False,
):
    solution_module_name = _get_solution_module_name(solution_root_dir)

    pyproject_data = toml.load(solution_root_dir / "pyproject.toml")
    solution_package_name = pyproject_data["tool"]["poetry"]["name"].replace("-", "_")

    assert all(
        (solution_root_dir / path).is_file()
        for path in _get_common_built_solution_files(
            solution_module_name,
            solution_package_name,
            solution_root_dir,
        )
    )

    solution_wheel = solution_root_dir / "dist" / f"{solution_package_name}-0.1.dev0-py3-none-any.whl"
    with zipfile.ZipFile(solution_wheel) as wheel_zip:
        files_in_wheel = wheel_zip.namelist()
        namespace_root_parts, _module = get_solution_namespace_info(solution_root_dir)
        namespace_prefix = "/".join(namespace_root_parts)
        asset_file = f"{namespace_prefix}/{solution_module_name}/method_assets/factor.txt"
        doctrees_folder = f"{namespace_prefix}/{solution_module_name}/html-doc/.doctrees/"
        index_doc_file = f"{namespace_prefix}/{solution_module_name}/html-doc/index.html"
        if with_documentation:
            assert index_doc_file in files_in_wheel
            assert "My mock documentation." in wheel_zip.read(index_doc_file).decode("utf-8")
            assert not any(file_name.startswith(doctrees_folder.rstrip("/")) for file_name in files_in_wheel)
        else:
            assert all(
                not file_name.startswith(f"{namespace_prefix}/{solution_module_name}/html-doc")
                for file_name in files_in_wheel
            )
        if with_encrypted_assets:
            assert f"{asset_file}.encrypted" in files_in_wheel
            assert asset_file not in files_in_wheel
        elif with_method_assets:
            assert f"{asset_file}.encrypted" not in files_in_wheel
            assert asset_file in files_in_wheel
        else:
            assert f"{asset_file}.encrypted" not in files_in_wheel
            assert asset_file not in files_in_wheel

    if with_pyproject:
        assert (
            solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name / "pyproject.toml"
        ).is_file()

    wheels_dir = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name
    assert list(wheels_dir.glob("ansys_*.whl"))
    if offline_package:
        assert any(f.name.startswith("aiofiles-") and f.suffix == ".whl" for f in list(wheels_dir.glob("*.whl")))
        assert len(list(wheels_dir.glob("*.whl"))) > len(list(wheels_dir.glob("ansys_*.whl"))) + 10
    else:
        # There is only one non ansys_*.whl file, which is the custom-package-for-test-2 local wheel package
        assert len(list(wheels_dir.glob("*.whl"))) == len(list(wheels_dir.glob("ansys_*.whl"))) + 1

    installer_path = _get_solution_installer_path(solution_root_dir)
    assert installer_path.is_file() if with_installer else not installer_path.exists()
    if executable_as_dir:
        assert (installer_path.parent / "_internal").is_dir()

    current_python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    python_version = python_version or current_python_version
    embeddable_python_exec = _get_built_solution_embeddable_python_executable(
        solution_root_dir,
        force_python_from_source,
    )
    if with_python:
        assert embeddable_python_exec
        assert embeddable_python_exec.is_file()
        major_minor_key: tuple[int, int] = parse_version(python_version).release[:2]  # pyright: ignore[reportAssignmentType]
        output = subprocess.check_output([embeddable_python_exec, "--version"], text=True).strip()
        parsed_python_version = parse_version(output.split(" ")[-1])
        minimum_python_version = MINIMUM_REQUIRED_VERSIONS[major_minor_key]
        assert parsed_python_version >= minimum_python_version
    else:
        assert embeddable_python_exec is None or not embeddable_python_exec.is_file()

    # Check no virtual environment was created inside dist/ when creating the poetry.lock file
    assert not (solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name / ".venv").is_dir()


def check_dependencies_can_be_upgraded(solution_root_dir: Path, solution_venv_python_exec: Path):
    poetry_lock_path = solution_root_dir / "poetry.lock"
    original_poetry_lock_data = toml.load(poetry_lock_path)
    shutil.move(poetry_lock_path, poetry_lock_path.with_suffix(".lock.bak"))

    solution_venv_poetry_exec = solution_venv_python_exec.parent / (
        "poetry.exe" if platform.system() == "Windows" else "poetry"
    )
    cmd = [solution_venv_poetry_exec, "lock"]
    subprocess.run(cmd, cwd=solution_root_dir)

    new_poetry_lock_data = toml.load(poetry_lock_path)

    original_packages = {package["name"]: package["version"] for package in original_poetry_lock_data["package"]}
    assert any(
        parse_version(new_package["version"]) > parse_version(original_version)
        for new_package in new_poetry_lock_data["package"]
        if (original_version := original_packages.get(new_package["name"]))
    )

    shutil.move(poetry_lock_path.with_suffix(".lock.bak"), poetry_lock_path)


class BuildSolution(Protocol):
    def __call__(
        self,
        args: list[str],
        python_exec: Path,
        solution_root_dir: Path,
        expected_error: str | None = None,
    ) -> list[str]: ...


def _build_solution(
    args: list[str],
    python_exec: Path,
    solution_root_dir: Path,
    expected_error: str | None = None,
) -> list[str]:
    solution_env = os.environ.copy()
    solution_venv_bin_dir = (
        solution_root_dir / ".venv" / "Scripts"
        if platform.system() == "Windows"
        else solution_root_dir / ".venv" / "bin"
    )
    solution_env["VIRTUAL_ENV"] = str(solution_venv_bin_dir.parent)
    solution_env["PATH"] = os.pathsep.join([str(solution_venv_bin_dir), solution_env.get("PATH", "")])
    cmd = [
        python_exec,
        "-m",
        "ansys.saf.desktop.installer",
    ] + args

    def run_installer() -> str:
        return subprocess.check_output(
            cmd,
            env=solution_env,
            cwd=solution_root_dir,
            text=True,
            stderr=subprocess.STDOUT,
        )

    if expected_error:
        with pytest.raises(subprocess.CalledProcessError) as e:
            run_installer()
        assert expected_error in e.value.output
        return []

    try:
        desktop_installer_output = run_installer()
    except subprocess.CalledProcessError as e:
        logger.error("Build solution failed with error:\n%s", e.output)
        raise
    return desktop_installer_output.splitlines()


@pytest.fixture
def build_solution() -> BuildSolution:
    """Fixture to build the solution with different parameters."""
    return _build_solution


@pytest.fixture(scope="session")
def session_built_solution(
    session_solution_setup: tuple[Path, Path, str, str, str],
) -> tuple[Path, Path, str, str, str]:
    """
    Session-scoped fixture that builds the solution once and reuses it across all tests.
    """
    solution_root_dir, solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = session_solution_setup

    # Use the extracted _build_solution function directly
    logger.info(f"Building session solution: {solution_root_dir.name}")
    _build_solution([], solution_venv_python_exec, solution_root_dir)
    check_built_solution_files(solution_root_dir)
    logger.info(f"Session solution built successfully: {solution_root_dir.name}")

    return solution_root_dir, solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port


################################################## SOLUTION INSTALL ###################################################


def assert_webview2_is_checked(install_output: list[str]):
    """Assert the check for WebView2 is in the installation output log."""
    if platform.system() == "Windows":
        assert find_msg_in_output("- Microsoft Edge WebView2 Runtime: ", install_output)
    else:
        assert not find_msg_in_output("WebView2", install_output)


def assert_long_paths_are_checked(install_output: list[str]):
    """Assert the check for long paths is in the installation output log."""
    if platform.system() == "Windows":
        assert find_msg_in_output("- Windows Long Path enabled: ", install_output)
    else:
        assert not find_msg_in_output("Long paths", install_output)


def _get_installed_solution_root_dir_name(solution_root_dir: Path) -> str:
    return f"{SOLUTION_DISPLAY_NAME[solution_root_dir.name]} Solution"


def _get_installed_solution_version_dir(installation_path: Path, solution_root_dir: Path) -> Path:
    installed_solution_root_dir_name = _get_installed_solution_root_dir_name(solution_root_dir)
    installed_solution_version_dir = installation_path / installed_solution_root_dir_name / "0.1.dev0"
    return installed_solution_version_dir


def _get_installed_solution_venv_python_executable(installation_path: Path, solution_root_dir: Path) -> Path:
    installed_solution_version_dir = _get_installed_solution_version_dir(installation_path, solution_root_dir)
    solution_module_name = _get_solution_module_name(solution_root_dir)
    installed_solution_venv_dir = installed_solution_version_dir / "definitions" / solution_module_name / ".venv"
    if platform.system() == "Windows":
        return installed_solution_venv_dir / "Scripts" / "python.exe"
    elif platform.system() == "Linux":
        return installed_solution_venv_dir / "bin" / "python"
    else:
        raise ValueError("Unsupported operating system")


def _get_installed_solution_venv_packages_dir(
    installation_path: Path,
    solution_root_dir: Path,
    python_version: str | None = None,
) -> Path:
    installed_solution_version_dir = _get_installed_solution_version_dir(installation_path, solution_root_dir)
    solution_module_name = _get_solution_module_name(solution_root_dir)
    python_version = (
        ".".join(python_version.split(".")[:2])
        if python_version
        else f"{sys.version_info.major}.{sys.version_info.minor}"
    )
    installed_solution_venv_packages_dir = (
        installed_solution_version_dir
        / "definitions"
        / solution_module_name
        / ".venv"
        / ("Lib" if platform.system() == "Windows" else "lib")
        / ("site-packages" if platform.system() == "Windows" else f"python{python_version}/site-packages")
    )
    return installed_solution_venv_packages_dir


def _get_installed_solution_package_dir(installed_solution_venv_packages_dir: Path, solution_root_dir: Path) -> Path:
    solution_module_name = _get_solution_module_name(solution_root_dir)
    installed_solution_package_dir = installed_solution_venv_packages_dir / "ansys" / "solutions" / solution_module_name
    return installed_solution_package_dir


def check_solution_module_preload_is_executed(
    tmp_path: Path,
    solution_root_dir: Path,
    with_obfuscation: bool = False,
    python_version: str | None = None,
    use_sudo: bool = False,
) -> None:
    installation_path = tmp_path if not use_sudo else Path("/opt") / "ansys_inc" / TARGET_SOLUTIONS_DIRECTORY_NAME
    installed_solution_venv_python_exec = _get_installed_solution_venv_python_executable(
        installation_path,
        solution_root_dir,
    )
    output = subprocess.check_output(
        [installed_solution_venv_python_exec.absolute().as_posix(), "-c", "import sys; print(sys.path)"],
        text=True,
    ).strip()
    sys_paths: list[Path] = [Path(sys_path) for sys_path in ast.literal_eval(output)]
    installed_solution_venv_packages_dir = _get_installed_solution_venv_packages_dir(
        installation_path,
        solution_root_dir,
        python_version,
    )
    assert installed_solution_venv_packages_dir in sys_paths
    if not with_obfuscation:
        installed_solution_package_dir = _get_installed_solution_package_dir(
            installed_solution_venv_packages_dir,
            solution_root_dir,
        )
        assert (installed_solution_package_dir / "__pycache__").is_dir()
        assert (installed_solution_package_dir / "solution" / "__pycache__").is_dir()
        assert (installed_solution_package_dir / "ui" / "__pycache__").is_dir()


def _get_embedded_python_executable(
    tmp_path: Path,
    solution_root_dir: Path,
    force_python_from_source: bool,
) -> Path:
    installed_solution_version_dir = _get_installed_solution_version_dir(tmp_path, solution_root_dir)
    python_dir = installed_solution_version_dir / "python"
    if platform.system() == "Windows":
        if force_python_from_source:
            return python_dir / "python.exe"
        return next(python_dir.glob("**/python.exe"))
    elif platform.system() == "Linux":
        return python_dir / "bin" / "python3"
    else:
        raise ValueError("Unsupported operating system")


def _check_solution_environment_uses_downloaded_python(
    tmp_path: Path,
    solution_root_dir: Path,
    force_python_from_source: bool,
) -> None:
    embedded_python_exec = _get_embedded_python_executable(tmp_path, solution_root_dir, force_python_from_source)
    assert embedded_python_exec.is_file()
    installed_solution_venv_python_exec = _get_installed_solution_venv_python_executable(tmp_path, solution_root_dir)
    assert installed_solution_venv_python_exec.is_file()
    cmd = [installed_solution_venv_python_exec, "-c", "import sys; print(sys.base_prefix)"]
    installed_solution_venv_python_base_prefix = Path(subprocess.check_output(cmd, text=True).strip())
    if platform.system() == "Windows":
        if "PCbuild" in str(embedded_python_exec):
            base_prefix_dir = embedded_python_exec.parent.parent.parent
            assert installed_solution_venv_python_base_prefix.as_posix() == base_prefix_dir.as_posix()
        else:
            assert installed_solution_venv_python_base_prefix.as_posix() == embedded_python_exec.parent.as_posix()
    elif platform.system() == "Linux":
        assert installed_solution_venv_python_base_prefix.as_posix() == embedded_python_exec.parent.parent.as_posix()
    else:
        raise ValueError("Unsupported operating system")


def _check_markers(markers: Any, python_version: str) -> bool:
    if not markers:
        return True
    marker_list: list[Marker] = []
    if isinstance(markers, str):
        marker_list.append(Marker(markers))
    else:
        marker_list += [Marker(markers[group]) for group in markers if group in ["main", "desktop", "ui", "doc"]]

    return all(
        marker.evaluate(
            {
                "python_version": ".".join(python_version.split(".")[:2]),
                "python_full_version": python_version,
            },
        )
        for marker in marker_list
    )


def check_dependencies(
    tmp_path: Path,
    solution_root_dir: Path,
    python_version: str | None = None,
    excluded_dependencies: list[str] | None = None,
    required_dependencies: list[str] | None = None,
    use_sudo: bool = False,
) -> None:
    """
    Check that the specified dependencies are installed or not installed in the solution's virtual environment.

    Args:
        tmp_path: Temporary path where the solution is installed
        solution_root_dir: Root directory of the solution
        python_version: Python version to evaluate markers against (defaults to current Python version if None)
        excluded_dependencies: List of dependencies that must NOT be installed
        required_dependencies: List of dependencies that must be installed
    """
    python_version = python_version or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    poetry_lock_data = toml.load(solution_root_dir / "poetry.lock")
    expected_package_versions: dict[str, str] = {}
    for package in poetry_lock_data["package"]:
        if not any(group in package.get("groups", []) for group in ["main", "desktop", "ui", "doc"]) or package[
            "name"
        ] in ["ansys-saf-desktop-installer", "pyinstaller"]:
            continue
        if _check_markers(package.get("markers", ""), python_version):
            expected_package_versions[package["name"].replace("_", "-").lower()] = package["version"]

    assert expected_package_versions

    installation_path = tmp_path if not use_sudo else Path("/opt") / "ansys_inc" / TARGET_SOLUTIONS_DIRECTORY_NAME
    installed_solution_venv_python_exec = _get_installed_solution_venv_python_executable(
        installation_path,
        solution_root_dir,
    )
    assert installed_solution_venv_python_exec.is_file()

    cmd = [installed_solution_venv_python_exec, "-m", "pip", "list", "--format", "json"]
    installed_package_versions = {
        pkg["name"].replace("_", "-").lower(): pkg["version"]
        for pkg in json.loads(subprocess.check_output(cmd, text=True))
    }

    # The installed packages include the expected packages plus pip and the solution itself
    assert len(expected_package_versions) == len(installed_package_versions) - 2
    assert all(installed_package_versions[package] == version for package, version in expected_package_versions.items())

    for package in excluded_dependencies or []:
        cmd = [installed_solution_venv_python_exec, "-m", "pip", "show", package]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.error("Dependency %s should NOT be installed but was found in the solution", package)
            raise ValueError(f"Dependency {package} should NOT be installed but was found in the solution.")

    for package in required_dependencies or []:
        cmd = [installed_solution_venv_python_exec, "-m", "pip", "show", package]
        try:
            subprocess.check_output(cmd, text=True)
        except subprocess.CalledProcessError as e:
            logger.error("Required dependency %s not found in the installed solution: %s", package, str(e))
            raise ValueError(f"Required dependency {package} not found in the installed solution.") from e


def _check_shortcut_uses_correct_python(shortcut_path: Path, tmp_path: Path, solution_root_dir: Path, pythonw: bool):
    installed_solution_venv_python_exec = _get_installed_solution_venv_python_executable(tmp_path, solution_root_dir)
    assert installed_solution_venv_python_exec.is_file()
    if platform.system() == "Windows":
        lnk: Lnk = parse(str(shortcut_path))
        assert Path(lnk.path).parent.as_posix() == installed_solution_venv_python_exec.parent.as_posix()  # type: ignore
        python_name = Path(lnk.path).name  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
        assert python_name == "pythonw.exe" if pythonw else python_name == "python.exe"
    elif platform.system() == "Linux":
        config = configparser.ConfigParser()
        config.read(shortcut_path)
        entry = config["Desktop Entry"]
        cmd = entry.get("Exec", "")
        python_path = Path(shlex.split(cmd)[0])
        assert python_path.as_posix() == installed_solution_venv_python_exec.as_posix()
        # No pythonw for Linux
    else:
        raise ValueError("Unsupported operating system")


def _shortcut_uses_portal(shortcut_path: Path, tmp_path: Path, solution_root_dir: Path) -> bool:
    installed_solution_venv_python_exec = _get_installed_solution_venv_python_executable(tmp_path, solution_root_dir)
    assert installed_solution_venv_python_exec.is_file()
    if platform.system() == "Windows":
        lnk: Lnk = parse(str(shortcut_path))
        arguments = getattr(lnk, "arguments", "")  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
        return "--portal" in str(arguments)
    elif platform.system() == "Linux":
        config = configparser.ConfigParser()
        config.read(shortcut_path)
        entry = config["Desktop Entry"]
        cmd = entry.get("Exec", "")
        return "--portal" in cmd
    else:
        raise ValueError("Unsupported operating system")


def _get_shortcut_path(solution_root_dir: Path, use_sudo: bool = False) -> Path:
    if platform.system() == "Windows":
        shortcut_path = Path(os.environ["PUBLIC"]) / "Desktop" / f"{SOLUTION_DISPLAY_NAME[solution_root_dir.name]}.lnk"
    elif platform.system() == "Linux":
        shortcut_dir = Path("/usr/share/applications") if use_sudo else Path(os.environ["HOME"]) / "Desktop"
        shortcut_path = shortcut_dir / f"{SOLUTION_DISPLAY_NAME[solution_root_dir.name]}.desktop"
    else:
        raise ValueError("Unsupported operating system")
    return shortcut_path


def _get_solution_linux_application_path(shortcut_path: Path) -> Path:
    return Path("~/.local/share/applications").expanduser() / shortcut_path.name


def check_installed_solution_files(
    tmp_path: Path,
    solution_root_dir: Path,
    with_python: bool = True,
    pythonw: bool = True,
    force_python_from_source: bool = False,
    use_portal: bool = True,
    use_sudo: bool = False,
) -> Path:
    installation_path = tmp_path if not use_sudo else Path("/opt") / "ansys_inc" / TARGET_SOLUTIONS_DIRECTORY_NAME
    installed_solution_version_dir = _get_installed_solution_version_dir(installation_path, solution_root_dir)
    asset_image_suffix = ".ico" if platform.system() == "Windows" else ".png"
    assert (installed_solution_version_dir / "assets" / f"shortcut{asset_image_suffix}").is_file()
    assert (installed_solution_version_dir / "version.txt").is_file()
    solution_module_name = _get_solution_module_name(solution_root_dir)
    installed_solution_module_name_dir = installed_solution_version_dir / "definitions" / solution_module_name
    assert (installed_solution_module_name_dir / ".venv").is_dir()
    assert (installed_solution_module_name_dir / ".env").is_file()
    if with_python:
        _check_solution_environment_uses_downloaded_python(
            installation_path,
            solution_root_dir,
            force_python_from_source,
        )
    shortcut_path = _get_shortcut_path(solution_root_dir, use_sudo)
    assert shortcut_path.is_file()
    if platform.system() == "Linux" and not use_sudo:
        application_path = _get_solution_linux_application_path(shortcut_path)
        assert application_path.is_file()
    _check_shortcut_uses_correct_python(shortcut_path, installation_path, solution_root_dir, pythonw)
    assert _shortcut_uses_portal(shortcut_path, installation_path, solution_root_dir) == use_portal

    return shortcut_path


class InstallSolution(Protocol):
    def __call__(
        self,
        solution_root_dir: Path,
        tmp_path: Path,
        expected_return_code: int = 0,
        extra_flags: list[str] | None = None,
        use_sudo: bool = False,
    ) -> list[str]: ...


@pytest.fixture
def install_solution() -> InstallSolution:

    def _install_solution(
        solution_root_dir: Path,
        tmp_path: Path,
        expected_return_code: int = 0,
        extra_flags: list[str] | None = None,
        use_sudo: bool = False,
    ) -> list[str]:
        installer_path = _get_solution_installer_path(solution_root_dir)
        shortcut_path = _get_shortcut_path(solution_root_dir, use_sudo)
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [installer_path.as_posix(), "--no-ui"]
        cmd += ["--installation-directory", tmp_path.as_posix()] if not use_sudo else []
        if extra_flags:
            cmd.extend(extra_flags)
        installation_env = os.environ.copy()
        if use_sudo:
            # Production get_shortcut_path only checks whether SUDO_USER is truthy. When the test
            # itself was launched under sudo we propagate the real value; otherwise we fall back to
            # the current invoking user so the installer subprocess still takes the root branch.
            installation_env["SUDO_USER"] = os.environ.get("SUDO_USER") or getpass.getuser()
        p = subprocess.run(cmd, capture_output=True, text=True, env=installation_env)
        assert p.returncode == expected_return_code, p.stderr
        return p.stdout.splitlines()

    return _install_solution


class InstallSolutionGUI(Protocol):
    def __call__(
        self,
        solution_root_dir: Path,
        tmp_path: Path,
        use_sudo: bool = False,
    ) -> SolutionInstallerProcess: ...


@pytest.fixture
def install_solution_via_gui() -> YieldFixture[InstallSolutionGUI]:

    procs: list[SolutionInstallerProcess] = []

    def _install_solution(
        solution_root_dir: Path,
        tmp_path: Path,
        use_sudo: bool = False,
    ) -> SolutionInstallerProcess:
        installer_path = _get_solution_installer_path(solution_root_dir)
        shortcut_path = _get_shortcut_path(solution_root_dir, use_sudo)
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [installer_path.as_posix()]
        cmd += ["--installation-directory", tmp_path.as_posix()] if not use_sudo else []
        p = SolutionInstallerProcess.run(cmd)
        procs.append(p)
        return p

    yield _install_solution

    for proc in procs:
        proc.stop()


def _get_global_poetry_config_path() -> Path | None:
    cmd = ["poetry", "config", "--list", "-vvv"]
    output = subprocess.check_output(cmd, text=True).splitlines()
    poetry_global_config_line = next((line for line in output if "config.toml" in line), None)

    if poetry_global_config_line:
        poetry_global_config_path = Path(poetry_global_config_line.split(" ")[-1])
        return poetry_global_config_path
    return None


@pytest.fixture
def disable_global_poetry_virtualenvs_creation(tmp_path: Path) -> Generator[None, None, None]:
    poetry_global_config_path = _get_global_poetry_config_path()
    poetry_global_config_backup_path: Path | None = None
    if poetry_global_config_path:
        poetry_global_config_backup_path = tmp_path / "config.toml.bak"
        shutil.copy(poetry_global_config_path, poetry_global_config_backup_path)

    cmd = ["poetry", "config", "virtualenvs.create", "false"]
    subprocess.run(cmd)
    poetry_global_config_path = _get_global_poetry_config_path()
    assert poetry_global_config_path
    assert poetry_global_config_path.is_file()
    poetry_global_config = toml.load(poetry_global_config_path)
    assert not poetry_global_config["virtualenvs"]["create"]

    yield

    if poetry_global_config_backup_path and poetry_global_config_backup_path.is_file():
        shutil.move(poetry_global_config_backup_path, poetry_global_config_path)
    elif poetry_global_config_backup_path is None:
        poetry_global_config_path.unlink(missing_ok=True)
    else:
        raise FileNotFoundError(
            "Could not revert the changes in the global poetry configuration. "
            f"Check the current configuration: {poetry_global_config_path}",
        )


################################################## EXECUTE SOLUTION ###################################################


def get_installed_solution_env_file(tmp_path: Path, solution_root_dir: Path) -> Path:
    installed_solution_version_dir = _get_installed_solution_version_dir(tmp_path, solution_root_dir)
    solution_module_name = _get_solution_module_name(solution_root_dir)
    return installed_solution_version_dir / "definitions" / solution_module_name / ".env"


@retry(stop=stop_after_attempt(300), wait=wait_fixed(1))
def _check_service_health(url: str):
    try:
        if not httpx2.get(url).status_code == 200:
            raise TryAgain
    except Exception:
        raise


@retry(stop=stop_after_attempt(300), wait=wait_fixed(1))
def _get_a_project_identifier(glow_api_port: str) -> str | None:
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
def _check_message_in_logs(solution_proc: SolutionShortcutProcess, message: str, service: str) -> bool:
    try:
        logs = {
            "orchestrator": solution_proc.orchestrator_logs(),
            "api": solution_proc.api_logs(),
            "ui": solution_proc.ui_logs(),
        }[service]
        if not find_msg_in_output(message, logs):
            raise TryAgain
    except Exception:
        raise
    return True


def check_solution_launched_correctly(
    solution_proc: SolutionShortcutProcess,
    glow_api_port: str,
    glow_ui_port: str,
    portal_ui_port: str,
    selenium_webdriver: WebDriver,
    is_otlp_enabled: bool = False,
) -> str:
    # We need services to be healthy before checking logs or trying to use the solution
    if portal_ui_port != "":
        portal_url = f"http://127.0.0.1:{portal_ui_port}"
        _check_service_health(portal_url)

    api_url = f"http://127.0.0.1:{glow_api_port}/docs"
    _check_service_health(api_url)

    project_identifier = _get_a_project_identifier(glow_api_port)

    project_ui_url = f"http://127.0.0.1:{glow_ui_port}/projects/{project_identifier}"
    _check_service_health(project_ui_url)

    # By default, OTEL is disabled and all logging goes to local files
    if not is_otlp_enabled:
        _check_message_in_logs(solution_proc, "INFO - OTEL Dashboard: not launched", "orchestrator")
        _check_message_in_logs(solution_proc, f"Running GLOW API server on http://127.0.0.1:{glow_api_port}", "api")
        _check_message_in_logs(solution_proc, f"Running GLOW UI server on http://127.0.0.1:{glow_ui_port}", "ui")
    else:
        _check_message_in_logs(solution_proc, "INFO - OTEL Dashboard: http://127.0.0.1:", "orchestrator")
        assert not solution_proc.api_logs()
        assert not solution_proc.ui_logs()

    # Solution is operable
    selenium_webdriver.get(project_ui_url)
    wait_for_element_and_click(selenium_webdriver, "//*[contains(text(), 'First Step')]", element_type=By.XPATH)
    wait_for_text(selenium_webdriver, "result", "")
    first_arg = random.randint(0, 100)
    wait_for_element_and_send_text(selenium_webdriver, "first-arg", str(first_arg))
    second_arg = random.randint(0, 100)
    wait_for_element_and_send_text(selenium_webdriver, "second-arg", str(second_arg))
    wait_for_element_and_click(selenium_webdriver, "calculate")
    wait_for_text(selenium_webdriver, "result", str(first_arg + second_arg))

    return project_ui_url


class ExecuteSolution(Protocol):
    def __call__(
        self,
        shortcut_path: Path,
        solution_root_dir: Path,
        pythonw: bool = True,
    ) -> SolutionShortcutProcess: ...


@pytest.fixture
def execute_solution() -> YieldFixture[ExecuteSolution]:

    procs: list[SolutionShortcutProcess] = []

    def _execute_solution(
        shortcut_path: Path,
        solution_root_dir: Path,
        pythonw: bool = True,
    ) -> SolutionShortcutProcess:
        p = SolutionShortcutProcess.run(
            SOLUTION_CLASS_NAME[solution_root_dir.name],
            shortcut_path,
            use_pythonw=(pythonw and platform.system() == "Windows"),
        )
        procs.append(p)
        return p

    yield _execute_solution

    for p in procs:
        p.stop()
