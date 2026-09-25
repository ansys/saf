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
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid

from packaging.version import parse
from PIL import Image
import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
import toml

from ansys.saf.desktop.installer._package.config import (
    DESKTOP_ORCHESTRATOR_MODULE_NAME,
    DESKTOP_ORCHESTRATOR_PACKAGE_NAME,
)
from ansys.saf.desktop.installer._package.download_python import MINIMUM_REQUIRED_VERSIONS
from ansys.saf.desktop.installer._package.solution import get_solution_package_dir
from ansys.saf.testing.platform_specific import linux_only, windows_only
from ansys.saf.testing.selenium import (
    wait_for_element_and_click,
    wait_for_partial_text,
)
from tests.e2e.conftest import (
    BuildSolution,
    ExecuteSolution,
    InstallSolution,
    SetupSolution,
    _get_solution_module_name,  # pyright: ignore[reportPrivateUsage]
    assert_long_paths_are_checked,
    assert_webview2_is_checked,
    check_built_solution_files,
    check_dependencies,
    check_dependencies_can_be_upgraded,
    check_installed_solution_files,
    check_solution_launched_correctly,
    check_solution_module_preload_is_executed,
    find_msg_in_output,
    get_installed_solution_env_file,
    modify_solution_module_name,
)


@contextmanager
def _block_internet_access():
    """
    Block internet access by setting the HTTP_PROXY and HTTPS_PROXY environment variables to a non-routable address.
    NO_PROXY exempts localhost so that local services are not affected during installation and execution.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HTTP_PROXY", "http://127.0.0.1:1")
        mp.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
        mp.setenv("NO_PROXY", "127.0.0.1,localhost,::1")
        # Verify connectivity is actually blocked using a subprocess to avoid caching side effects
        # (urllib.request caches a global ProxyHandler that leaks into subsequent tests).
        result = subprocess.run(
            [sys.executable, "-c", "from urllib.request import urlopen; urlopen('http://pypi.org', timeout=5)"],
            capture_output=True,
        )
        assert result.returncode != 0
        yield


@pytest.mark.usefixtures("check_gtk_launch_and_xvfb_are_installed")
class TestInstaller:
    @pytest.mark.usefixtures("disable_global_poetry_virtualenvs_creation")
    def test_installer_default(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        session_selenium_webdriver: WebDriver,
        cleanup_shortcut: list[Path],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        Test saf-desktop-installer entry point with the default values. We check:

        - that all the built solution files exist,
        - that the solution documentation has been built and embedded into the solution wheel,
        - that the solution installation executable finalizes correctly,
        - that the right python executable is used in the installed shortcut, and
        - that the solution modules are preloaded,
        - that the solution executes correctly, logging to file by default,
        - that the embedded solution documentation is accessible from the solution UI,
        - that the env vars are loaded from solution's .env,
        - that the installer checks if webview2 is installed when running on Windows,
        - that the installer checks if long paths are enabled when running on Windows,
        - that the .doctrees folder is not included in the solution wheel
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        env_file = solution_root_dir / ".env"
        assert env_file.is_file()
        env_file_content = env_file.read_text()
        # write fake credentials to env file and ensure that file is loaded
        env_file_content += (
            "\nPOETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME=my_user\n"
            "POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD=my_password"
        )
        env_file.write_text(env_file_content)

        output = build_solution([], solution_venv_python_exec, solution_root_dir)
        assert find_msg_in_output(f"Environment variables loaded from {str(env_file.absolute())}", output)
        check_built_solution_files(solution_root_dir)
        check_dependencies_can_be_upgraded(solution_root_dir, solution_venv_python_exec)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        project_ui_url = check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

        # Clicking on the solution documentation button returns expect content of the doc.
        session_selenium_webdriver.get(project_ui_url)
        wait_for_element_and_click(session_selenium_webdriver, "access-solution-doc")
        wait_for_partial_text(session_selenium_webdriver, "solution-doc-content", "My mock documentation.")

    def test_run_solution_without_log_to_files(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        session_selenium_webdriver: WebDriver,
        cleanup_shortcut: list[Path],
    ):
        """
        Test saf-desktop-installer when launching the installed the solution without SAF_DESKTOP_LOG_TO_FILES. Assert
        that the solution executes correctly, the OTLP Dashboard is launched and log files are not generated except
        for the orchestrator.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)
        build_solution([], solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)
        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        env_file = get_installed_solution_env_file(tmp_path, solution_root_dir)
        # ideally, we would replace it with False, but current parsing in orchestrator interprets any value as True
        env_file.write_text(env_file.read_text().replace("SAF_DESKTOP_LOG_TO_FILES=True", ""))
        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
            is_otlp_enabled=True,
        )

    def test_installer_with_no_executable(
        self,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
    ):
        """
        Test saf-desktop-installer entry point with the --no-executable flag activated.
        """
        solution_venv_python_exec, _, _, _ = setup_solution(solution_root_dir)

        args = ["--no-executable"]
        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, with_installer=False)

    @windows_only(reason="Could not find a command to run a shortcut configured with Terminal='true' in Linux.")
    def test_installer_with_display_console_window(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
    ):
        """
        Test saf-desktop-installer entry point with the --display-console-window flag activated.
        """
        solution_venv_python_exec, _, _, _ = setup_solution(solution_root_dir)

        args = ["--display-console-window"]
        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir, pythonw=False)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        process = execute_solution(shortcut_path, solution_root_dir, pythonw=False)

        assert process.api_running()
        assert process.ui_running()
        assert not process.project_running()
        assert process.portal_running()
        assert not process.otel_running()

    def test_installer_with_python_version(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer entry point with the --python-version option.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        python_version = "3.11.10"
        args = ["--python-version", python_version]
        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, python_version=python_version)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir, python_version="3.11")
        check_dependencies(
            tmp_path,
            solution_root_dir,
            python_version=python_version,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    def test_installer_with_excluded_python(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer entry point with the --exclude-python flag activated.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        args = ["--exclude-python"]
        desktop_installer_output = build_solution(args, solution_venv_python_exec, solution_root_dir)
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert find_msg_in_output(
            (
                "Creating a package without embedded Python. The solution might only be installable on a system using "
                f"Python version {python_version}. If the target system uses a different Python version, "
                "use the option --python-version to specify that version."
            ),
            desktop_installer_output,
        )
        check_built_solution_files(solution_root_dir, with_python=False)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir, with_python=False)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    @windows_only(reason="OTEL's Aspire.Dashboard is not executable after obfuscation of wheel files in Linux.")
    def test_installer_with_obfuscation(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer entry point with the --obfuscate flag activated.
        """
        mock_solution_name = solution_root_dir.name
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        args = ["--obfuscate"]
        desktop_installer_output = build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)
        assert find_msg_in_output("Obfuscation complete.", desktop_installer_output)

        installed_solution_path = (
            tmp_path
            / "Ansys Inc"
            / "SAF Solutions"
            / "My Solution Solution"
            / "0.1.dev0"
            / "definitions"
            / mock_solution_name
        )
        mock_solution_name_underscore = mock_solution_name.replace("-", "_")
        solution_src_dir = (
            installed_solution_path
            / ".venv"
            / "Lib"
            / "site-packages"
            / "ansys"
            / "solutions"
            / mock_solution_name_underscore
        )
        assert not list(solution_src_dir.rglob(".py"))

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir, with_obfuscation=True)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["custom-package-for-test-2"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    @pytest.mark.parametrize("python_version", [None, "3.11.8", "3.12.4", "3.12.12", "3.13.0", "3.14.0"])
    def test_installer_with_offline_package_with_different_python_versions(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
        python_version: str | None,
    ):
        """
        Test saf-desktop-installer entry point with the --offline-package flag activated in
        combination with the --python-version flag.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        # Adding an extra dependency that has a package name that is different as a .tar.gz than as a .whl:
        # python-pptx-0.6.19.tar.gz becomes python_pptx-0.6.19-py3-none-any.whl (first dash becomes and underscore)
        poetry_exec_name = "poetry.exe" if platform.system() == "Windows" else "poetry"
        solution_venv_poetry_exec = solution_venv_python_exec.parent / poetry_exec_name
        solution_venv_dir = solution_root_dir / ".venv"
        solution_env = os.environ.copy()
        # For poetry to install dependencies in the right venv
        solution_env["VIRTUAL_ENV"] = solution_venv_dir.as_posix()
        cmd = [solution_venv_poetry_exec, "add", "python-pptx=0.6.19"]
        subprocess.check_output(cmd, env=solution_env, cwd=solution_root_dir)
        # Check that the extra dependency is installed in the solution environment
        result = subprocess.run(
            [solution_venv_python_exec, "-m", "pip", "show", "python-pptx"],
            capture_output=True,
        )
        assert result.returncode == 0

        args = ["--offline-package"] + (["--python-version", python_version] if python_version else [])
        desktop_installer_output = build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, offline_package=True, python_version=python_version)
        python_version = python_version or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        dependencies_msg = find_msg_in_output(
            "Downloading solution's external dependencies with python version",
            desktop_installer_output,
        )
        assert dependencies_msg
        major_minor_key: tuple[int, int] = parse(python_version).release[:2]  # pyright: ignore[reportAssignmentType]
        minimum_python_version = MINIMUM_REQUIRED_VERSIONS[major_minor_key]
        python_version_parsed_from_log = parse(dependencies_msg.split("python version")[-1].strip())
        assert python_version_parsed_from_log >= minimum_python_version

        parsed_python_version = parse(python_version)
        if parsed_python_version < minimum_python_version:
            python_version_warning_msg = find_msg_in_output(
                f"The selected python version: {python_version} is lower",
                desktop_installer_output,
            )
            assert python_version_warning_msg

        # Block internet access to verify offline installation and execution works without network connectivity.
        with _block_internet_access():
            installation_output = install_solution(solution_root_dir, tmp_path)
            assert find_msg_in_output("Preload application", installation_output)
            assert find_msg_in_output("Execution time:", installation_output)
            assert_webview2_is_checked(installation_output)
            assert_long_paths_are_checked(installation_output)
            shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
            cleanup_shortcut.append(shortcut_path)
            check_solution_module_preload_is_executed(tmp_path, solution_root_dir, python_version=python_version)
            check_dependencies(
                tmp_path,
                solution_root_dir,
                python_version=python_version,
                required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby", "python-pptx"],
                excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
            )

            solution_proc = execute_solution(shortcut_path, solution_root_dir)
            check_solution_launched_correctly(
                solution_proc,
                glow_api_port,
                glow_ui_port,
                portal_ui_port,
                session_selenium_webdriver,
            )

    def test_installer_with_offline_package_and_excluded_python(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer entry point with the --offline-package flag in combination with the
        --exclude-python flag.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        args = ["--exclude-python", "--offline-package"]
        desktop_installer_output = build_solution(args, solution_venv_python_exec, solution_root_dir)
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert find_msg_in_output(
            (
                "Creating a package without embedded Python. The solution might only be installable on a system using "
                f"Python version {python_version}. If the target system uses a different Python version, "
                "use the option --python-version to specify that version."
            ),
            desktop_installer_output,
        )
        assert find_msg_in_output(
            f"Downloading solution's external dependencies with python version {python_version}",
            desktop_installer_output,
        )
        check_built_solution_files(
            solution_root_dir,
            offline_package=True,
            with_python=False,
            python_version=python_version,
        )

        # Block internet access to verify offline installation and execution works without network connectivity.
        with _block_internet_access():
            installation_output = install_solution(solution_root_dir, tmp_path)
            assert find_msg_in_output("Preload application", installation_output)
            assert find_msg_in_output("Execution time:", installation_output)
            assert_webview2_is_checked(installation_output)
            assert_long_paths_are_checked(installation_output)
            shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir, with_python=False)
            cleanup_shortcut.append(shortcut_path)
            check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
            check_dependencies(
                tmp_path,
                solution_root_dir,
                required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
                excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
            )

            solution_proc = execute_solution(shortcut_path, solution_root_dir)
            check_solution_launched_correctly(
                solution_proc,
                glow_api_port,
                glow_ui_port,
                portal_ui_port,
                session_selenium_webdriver,
            )

    def test_installer_with_custom_assets(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer entry point with custom installer assets in the solution tree.
        """

        def _files_are_equal(file_1: Path, file_2: Path):
            return Path(file_1).read_bytes() == Path(file_2).read_bytes()

        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        # Create custom assets in ui/assets/installer by rotating the default favicon.
        shortcut_suffix = ".ico" if platform.system() == "Windows" else ".png"
        solution_module_name = _get_solution_module_name(solution_root_dir)
        custom_assets_dir = (
            get_solution_package_dir(solution_root_dir, solution_module_name) / "ui" / "assets" / "installer"
        )
        custom_assets_dir.mkdir(parents=True, exist_ok=True)
        installer_path = Path(__file__).parent.parent.parent / "src" / "ansys" / "saf" / "desktop" / "installer"
        favicon_path = installer_path / "_package" / "assets" / f"favicon{shortcut_suffix}"
        custom_favicon_path = tmp_path / f"custom_favicon{shortcut_suffix}"
        favicon = Image.open(favicon_path)
        favicon = favicon.rotate(90)
        favicon.save(custom_favicon_path)

        shutil.copy(custom_favicon_path, custom_assets_dir / f"favicon{shortcut_suffix}")
        shutil.copy(custom_favicon_path, custom_assets_dir / f"shortcut{shortcut_suffix}")

        source_logo_path = installer_path / "_package" / "assets" / "installer_ui_logo.png"
        custom_logo_path = custom_assets_dir / "installer_ui_logo.png"
        logo = Image.open(source_logo_path)
        logo = logo.rotate(90)
        logo.save(custom_logo_path)

        build_solution([], solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)

        # Check that custom favicon, shortcut and logo are copied.
        favicon_path = solution_root_dir / "dist" / "solution" / "assets" / f"favicon{shortcut_suffix}"
        assert _files_are_equal(custom_favicon_path, favicon_path)
        shortcut_path = solution_root_dir / "dist" / "solution" / "assets" / f"shortcut{shortcut_suffix}"
        assert _files_are_equal(custom_favicon_path, shortcut_path)
        logo_path = solution_root_dir / "dist" / "solution" / "assets" / "installer_ui_logo.png"
        assert _files_are_equal(custom_logo_path, logo_path)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    @pytest.mark.parametrize("python_version", ["3.11.15", "3.12.9"])
    def test_installer_with_force_python_from_source(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
        python_version: str,
    ):
        """
        Test saf-desktop-installer entry point with the --force-python-from-source option.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        args = ["--force-python-from-source", "--python-version", python_version]
        build_output = build_solution(args, solution_venv_python_exec, solution_root_dir)
        log_message = (
            f"The python version {python_version} is available as a NuGet package, but it will be built "
            "from source code because the --force-python-from-source flag was used."
        )
        if python_version == "3.12.9":
            assert find_msg_in_output(log_message, build_output)
        else:
            assert find_msg_in_output(log_message, build_output) is None
        check_built_solution_files(solution_root_dir, python_version=python_version, force_python_from_source=True)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir, force_python_from_source=True)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir, python_version="3.12")
        check_dependencies(
            tmp_path,
            solution_root_dir,
            python_version=python_version,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    @pytest.mark.parametrize("with_key", [True, False])
    def test_installer_with_encrypt(
        self,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        with_key: bool,
    ):
        """
        Test saf-desktop-installer entry point with the encrypt options and with or without encryption key.
        """
        mock_solution_name = solution_root_dir.name
        mock_solution_name_underscore = mock_solution_name.replace("-", "_")
        file_to_encrypt = (
            Path(".\\src") / "ansys" / "solutions" / mock_solution_name_underscore / "method_assets" / "factor.txt"
        )
        obfuscation_file = solution_root_dir / "obfuscation" / "obfuscate.txt"
        obfuscation_file.parent.mkdir()
        obfuscation_file.write_text(str(file_to_encrypt))

        solution_venv_python_exec, _, _, _ = setup_solution(solution_root_dir)

        secret_key: str | None = None
        args = ["--encrypt", "--encryption-file", str(obfuscation_file)]
        if with_key:
            secret_key = str(uuid.uuid4())
            (
                solution_root_dir
                / "src"
                / "ansys"
                / "solutions"
                / mock_solution_name_underscore
                / "method_assets"
                / "glow_assets_metadata.json"
            ).write_text(
                json.dumps(
                    {
                        "translator": secret_key,
                    },
                ),
            )
            args.extend(["--encryption-key", secret_key])

        build_solution(
            args,
            solution_venv_python_exec,
            solution_root_dir,
            expected_error=(
                "The ansys-translation-utilities package is required for encryption and is a private dependency. "
                "To use the --encrypt option, you must request "
                "access to this package from the SAF-SDK maintainers/team."
            ),
        )

    def test_installer_without_documentation(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer with a solution that does not have documentation (also equivalent to failing to
        build the documentation or not generating any output).

        Expected UX:
        - A warning message is shown
        - Build ends OK
        - Wheel package does not contain any documentation in html-doc submodule
        - solution UI fails to open it.
        """
        shutil.rmtree(solution_root_dir / "doc")
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        build_output = build_solution([], solution_venv_python_exec, solution_root_dir)
        assert find_msg_in_output("Failed to build documentation:", build_output)
        doc_src_dir = solution_root_dir / "doc" / "source"
        assert find_msg_in_output(f"Cannot find source directory ({doc_src_dir})", build_output)
        solution_module_name = _get_solution_module_name(solution_root_dir)
        doc_html_dir = get_solution_package_dir(solution_root_dir, solution_module_name) / "html-doc"
        assert find_msg_in_output(f"Fix the errors or manually copy the documentation to {doc_html_dir}.", build_output)
        check_built_solution_files(solution_root_dir, with_documentation=False)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        project_ui_url = check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

        # Clicking on the solution documentation button returns expect message about doc not being available.
        session_selenium_webdriver.get(project_ui_url)
        wait_for_element_and_click(session_selenium_webdriver, "access-solution-doc")
        wait_for_partial_text(
            session_selenium_webdriver,
            "solution-doc-content",
            "Solution documentation is not available.",
        )

    def test_installer_with_modified_solution_module_name(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer entry point with a solution that has a modified solution module name with respect
        to the solution name.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        modify_solution_module_name(solution_root_dir)

        build_solution([], solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    def test_installer_keeps_downloaded_python_for_same_python_version(
        self,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
    ):
        """
        Test that saf-desktop-installer keeps a previously downloaded python if the version is the same
        and removes it otherwise.
        """
        solution_venv_python_exec, _, _, _ = setup_solution(solution_root_dir)

        python_version = "3.11.11"
        args = ["--python-version", python_version, "--no-executable"]
        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, python_version=python_version, with_installer=False)

        new_file = solution_root_dir / "dist" / "solution" / "third_party" / "python" / "new_file.txt"
        new_file.touch()
        assert new_file.is_file()

        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, python_version=python_version, with_installer=False)
        assert new_file.is_file()

        python_version = "3.12.9"
        args = ["--python-version", python_version, "--no-executable"]
        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, python_version=python_version, with_installer=False)
        assert not new_file.is_file()

    def test_installer_with_custom_ui_dependencies(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        session_selenium_webdriver: WebDriver,
        cleanup_shortcut: list[Path],
    ):
        """
        Test saf-desktop-installer entry point with a solution that has arbitrary UI and Desktop dependencies
        defined in the solution's pyproject.toml file.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        build_solution([], solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    def test_installer_with_sdk_dependency_in_multiple_groups(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        session_selenium_webdriver: WebDriver,
        cleanup_shortcut: list[Path],
    ):
        """Build a solution with SAF SDK extras distributed across dependency groups."""
        pyproject_path = solution_root_dir / "pyproject.toml"
        pyproject = toml.load(pyproject_path)
        poetry = pyproject["tool"]["poetry"]
        dependencies = poetry["dependencies"]
        dependencies.pop("ansys-saf-glow-engine")
        dependencies["ansys-saf-sdk"] = "^0.1.0"

        desktop_dependencies = poetry["group"]["desktop"]["dependencies"]
        desktop_dependencies.pop("ansys-saf-desktop-orchestrator")
        desktop_dependencies["ansys-saf-sdk"] = {"version": "^0.1.0", "extras": ["desktop"]}

        with pyproject_path.open("w") as pyproject_file:
            toml.dump(pyproject, pyproject_file)

        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)
        poetry_executable = solution_venv_python_exec.with_name(
            "poetry.exe" if platform.system() == "Windows" else "poetry",
        )
        subprocess.run([poetry_executable, "lock"], cwd=solution_root_dir, check=True)

        build_solution([], solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)

        definitions_pyproject = toml.load(
            solution_root_dir / "dist" / "solution" / "definitions" / "my_solution_dash" / "pyproject.toml",
        )
        sdk_dependency = definitions_pyproject["tool"]["poetry"]["dependencies"]["ansys-saf-sdk"]
        assert sdk_dependency == {"version": "^0.1.0", "extras": ["desktop"]}

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    def test_installer_with_executable_as_dir(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer entry point with the --executable-as-dir option.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        args = ["--executable-as-dir"]
        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, executable_as_dir=True)

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc,
            glow_api_port,
            glow_ui_port,
            portal_ui_port,
            session_selenium_webdriver,
        )

    @pytest.mark.parametrize("solution_root_dir", ["my-solution-dash-old"], indirect=True)
    def test_installer_with_solution_with_installer_duplicated_in_desktop_group(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer when a solution has it in the desktop group and in the build group. This is legacy
        behaviour, SAF-CLI minor than 3.6.0. Modern solutions only have it in the build group.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        args = ["--offline-package"]
        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(
            solution_root_dir,
            with_documentation=False,
            offline_package=True,
            with_method_assets=False,
        )

        # Block internet access to verify offline installation and execution works without network connectivity.
        with _block_internet_access():
            installation_output = install_solution(solution_root_dir, tmp_path)
            assert find_msg_in_output("Preload application", installation_output)
            assert find_msg_in_output("Execution time:", installation_output)
            assert_webview2_is_checked(installation_output)
            assert_long_paths_are_checked(installation_output)
            shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
            cleanup_shortcut.append(shortcut_path)
            check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
            check_dependencies(
                tmp_path,
                solution_root_dir,
                required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
                excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
            )

            solution_proc = execute_solution(shortcut_path, solution_root_dir)
            check_solution_launched_correctly(
                solution_proc,
                glow_api_port,
                glow_ui_port,
                portal_ui_port,
                session_selenium_webdriver,
            )

    def test_installer_with_fallback_pip_based_installation(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer installation using pip fallback (--use-pip).
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        args = ["--offline-package"]
        build_solution(args, solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, offline_package=True)

        # Block internet access to verify offline installation and execution works without network connectivity.
        with _block_internet_access():
            installation_output = install_solution(solution_root_dir, tmp_path, extra_flags=["--use-pip"])
            assert find_msg_in_output("Preload application", installation_output)
            assert find_msg_in_output("Execution time:", installation_output)
            assert_webview2_is_checked(installation_output)
            assert_long_paths_are_checked(installation_output)
            shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
            cleanup_shortcut.append(shortcut_path)
            check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
            check_dependencies(
                tmp_path,
                solution_root_dir,
                required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
                excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
            )

            solution_proc = execute_solution(shortcut_path, solution_root_dir)
            check_solution_launched_correctly(
                solution_proc,
                glow_api_port,
                glow_ui_port,
                portal_ui_port,
                session_selenium_webdriver,
            )

    def test_installer_with_offline_package_and_no_export_plugin(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer installation using --offline-package without poetry-plugin-export.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)

        poetry_venv_python_exec = (
            solution_root_dir
            / ".poetry"
            / ".venv"
            / ("Scripts" if platform.system() == "Windows" else "bin")
            / ("python.exe" if platform.system() == "Windows" else "python")
        )
        assert poetry_venv_python_exec.is_file()
        result = subprocess.run([poetry_venv_python_exec, "-m", "pip", "uninstall", "-y", "poetry-plugin-export"])
        assert result.returncode == 0

        args = ["--offline-package"]
        desktop_installer_output = build_solution(args, solution_venv_python_exec, solution_root_dir)
        assert find_msg_in_output(
            "Installing poetry-plugin-export in the poetry environment to allow build with --offline-package",
            desktop_installer_output,
        )
        result = subprocess.run([poetry_venv_python_exec, "-m", "pip", "show", "poetry-plugin-export"])
        assert result.returncode == 0
        check_built_solution_files(solution_root_dir, offline_package=True)

        # Block internet access to verify offline installation and execution works without network connectivity.
        with _block_internet_access():
            installation_output = install_solution(solution_root_dir, tmp_path, extra_flags=["--use-pip"])
            assert find_msg_in_output("Preload application", installation_output)
            assert find_msg_in_output("Execution time:", installation_output)
            assert_webview2_is_checked(installation_output)
            assert_long_paths_are_checked(installation_output)
            shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
            cleanup_shortcut.append(shortcut_path)
            check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
            check_dependencies(
                tmp_path,
                solution_root_dir,
                required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
                excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
            )

            solution_proc = execute_solution(shortcut_path, solution_root_dir)
            check_solution_launched_correctly(
                solution_proc,
                glow_api_port,
                glow_ui_port,
                portal_ui_port,
                session_selenium_webdriver,
            )

    def test_installer_without_portal(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test saf-desktop-installer entry point with a solution that does not depend on
        the portal and launches without it.
        """
        solution_root_dir = solution_root_dir.rename(solution_root_dir.parent / "my-solution-dash-without-portal")
        solution_venv_python_exec, glow_api_port, glow_ui_port, _ = setup_solution(solution_root_dir)
        # then: solution is built and installed without portal
        build_solution([], solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)
        install_solution(solution_root_dir, tmp_path)
        # and: shortcut is created without --portal
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir, use_portal=False)
        cleanup_shortcut.append(shortcut_path)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            excluded_dependencies=["ansys-saf-desktop-portal", "ansys-saf-portal"],
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc=solution_proc,
            glow_api_port=glow_api_port,
            glow_ui_port=glow_ui_port,
            portal_ui_port="",
            selenium_webdriver=session_selenium_webdriver,
        )

    @linux_only()
    @pytest.mark.usefixtures("check_gtk_launch_and_xvfb_are_installed")
    def test_installer_places_shortcut_in_applications_dir_when_run_as_root(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        cleanup_shortcut: list[Path],
        cleanup_solution_installed_by_root: None,
        session_selenium_webdriver: WebDriver,
    ):
        """
        Test the Linux SUDO_USER install path. We check:

        - that the installer runs to completion when invoked under sudo,
        - that the shortcut lands under the system-wide XDG applications dir (/usr/share/applications),
        as returned by production get_shortcut_path when SUDO_USER is set,
        - that the standard installed-solution files (venv, .env, correct Python) are in place.
        """
        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(solution_root_dir)
        build_solution([], solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir)

        installation_output = install_solution(solution_root_dir, tmp_path, use_sudo=True)
        assert find_msg_in_output("Preload application", installation_output)
        assert find_msg_in_output("Execution time:", installation_output)
        assert_webview2_is_checked(installation_output)
        assert_long_paths_are_checked(installation_output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir, use_sudo=True)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir, use_sudo=True)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
            excluded_dependencies=["ansys-saf-desktop-installer", "pyinstaller"],
            use_sudo=True,
        )

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc=solution_proc,
            glow_api_port=glow_api_port,
            glow_ui_port=glow_ui_port,
            portal_ui_port=portal_ui_port,
            selenium_webdriver=session_selenium_webdriver,
        )


@pytest.mark.parametrize("solution_root_dir", ["synopsys-custom-ns-solution"], indirect=True)
@pytest.mark.usefixtures("check_gtk_launch_and_xvfb_are_installed")
class TestInstallerCustomNamespace:
    """End-to-end tests verifying that the installer works correctly for a solution
    that uses a custom (non-ansys) single-segment namespace root (``synopsys``)."""

    @pytest.mark.parametrize(
        "glow_solution_definition",
        [None, "synopsys.custom_ns_solution.solution.definition"],
        ids=["without_env_var", "with_env_var"],
    )
    @pytest.mark.usefixtures("disable_global_poetry_virtualenvs_creation")
    def test_install_and_launch_with_synopsys_namespace(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        glow_solution_definition: str | None,
        setup_solution: SetupSolution,
        build_solution: BuildSolution,
        install_solution: InstallSolution,
        execute_solution: ExecuteSolution,
        session_selenium_webdriver: WebDriver,
        cleanup_shortcut: list[Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full install + launch cycle works for a solution with a custom synopsys namespace."""

        if glow_solution_definition is None:
            monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)
        else:
            monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", glow_solution_definition)

        solution_venv_python_exec, glow_api_port, glow_ui_port, portal_ui_port = setup_solution(
            solution_root_dir,
        )
        build_solution([], solution_venv_python_exec, solution_root_dir)
        check_built_solution_files(solution_root_dir, with_documentation=False, with_method_assets=False)

        metadata_path = solution_root_dir / "dist" / "solution" / "solution-metadata.json"
        assert metadata_path.is_file(), "solution-metadata.json was not generated"
        metadata = json.loads(metadata_path.read_text())
        assert metadata["glow-package-name"] == DESKTOP_ORCHESTRATOR_PACKAGE_NAME
        assert metadata["glow-entry-point-module"] == DESKTOP_ORCHESTRATOR_MODULE_NAME
        assert metadata["use-glow"] == "True"
        assert metadata["solution-entry-point"] == ""
        assert metadata["solution-name"] == "synopsys-custom-ns-solution"
        assert metadata["solution-module-name"] == "custom_ns_solution"
        assert metadata["solution-version"] == "0.1.dev0"
        assert metadata["solution-display-name"] == "Custom NS Solution"
        assert metadata["solution-package-name"] == "synopsys-custom-ns-solution"
        assert metadata["solution-main-module"] == "synopsys.custom_ns_solution.main"
        assert metadata["display-console-window"] == "False"
        assert metadata["offline-package"] == "False"

        installation_output = install_solution(solution_root_dir, tmp_path)
        assert find_msg_in_output("Preload application", installation_output)

        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)

        solution_proc = execute_solution(shortcut_path, solution_root_dir)
        check_solution_launched_correctly(
            solution_proc=solution_proc,
            glow_api_port=glow_api_port,
            glow_ui_port=glow_ui_port,
            portal_ui_port=portal_ui_port,
            selenium_webdriver=session_selenium_webdriver,
        )
