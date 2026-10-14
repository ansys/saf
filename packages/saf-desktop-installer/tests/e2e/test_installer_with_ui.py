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

import logging
from pathlib import Path
import platform

import pytest
from selenium.webdriver.chrome.webdriver import WebDriver

from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_element_and_click,
    wait_for_expected_attribute,
    wait_for_expected_property,
    wait_for_partial_text,
)
from tests.conftest import check_installer_gui_is_using_local_bootstrap_css
from tests.e2e.conftest import (
    InstallSolutionGUI,
    check_dependencies,
    check_installed_solution_files,
    check_solution_module_preload_is_executed,
)
from tests.utils import remove_directory_write_permissions

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def _launch_installation(session_selenium_webdriver: WebDriver) -> None:
    wait_for_expected_property(session_selenium_webdriver, "install-button", "disabled", False)  # type: ignore
    e = wait_for_element(session_selenium_webdriver, "install-alert")
    assert e.text == ""

    # Start installation and wait for final message
    wait_for_element_and_click(session_selenium_webdriver, "install-button")


def _verify_installation(
    session_selenium_webdriver: WebDriver,
    cleanup_shortcut: list[Path],
    tmp_path: Path,
    solution_root_dir: Path,
) -> None:
    # During installation, all inputs are disabled
    wait_for_expected_property(
        session_selenium_webdriver,
        "input-metadata-file-location",
        "disabled",
        True,  # type: ignore
    )
    wait_for_expected_property(
        session_selenium_webdriver,
        "input-installation-location",
        "disabled",
        True,  # type: ignore
    )
    wait_for_expected_property(
        session_selenium_webdriver,
        "input-python-interpreter-location",
        "disabled",
        True,  # type: ignore
    )
    wait_for_expected_property(
        session_selenium_webdriver,
        "install-button",
        "disabled",
        True,  # type: ignore
    )
    wait_for_partial_text(
        session_selenium_webdriver,
        "install-alert",
        "Installation completed in",
        timeout=1200,
    )

    shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
    cleanup_shortcut.append(shortcut_path)
    check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
    check_dependencies(
        tmp_path,
        solution_root_dir,
        required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
    )


@pytest.mark.usefixtures("check_gtk_launch_and_xvfb_are_installed")
class TestInstallerWithUI:
    def test_installer_gui_default(
        self,
        tmp_path: Path,
        solution_root_dir: Path,
        session_built_solution: tuple[Path, Path, str, str, str],
        install_solution_via_gui: InstallSolutionGUI,
        session_selenium_webdriver: WebDriver,
        cleanup_shortcut: list[Path],
    ):
        """
        Test the default installer UI flow and complete the installation successfully. We check:

        - that the GUI has the expected elements and values,
        - that the installer UI loads the bundled Bootstrap CSS,
        - that clicking on Install, disables all inputs,
        - that the solution installation finalizes correctly when installed via the GUI,
        - that the right python executable is used in the installed shortcut, and
        - that the solution modules are preloaded,
        """
        solution_root_dir, _, _, _, _ = session_built_solution

        installation_proc = install_solution_via_gui(solution_root_dir, tmp_path)

        session_selenium_webdriver.get(installation_proc.installer_ui_url)

        e = wait_for_element(session_selenium_webdriver, "input-metadata-file-location")
        assert e.get_property("value").endswith("solution-metadata.json")  # type: ignore
        e = wait_for_element(session_selenium_webdriver, "input-installation-location")
        assert e.get_property("value") == tmp_path.as_posix()  # type: ignore
        e = wait_for_element(session_selenium_webdriver, "input-python-interpreter-location")
        assert e.get_property("value").endswith(  # type: ignore
            "/python.exe" if platform.system() == "Windows" else "/python3",
        )

        check_installer_gui_is_using_local_bootstrap_css(session_selenium_webdriver)

        # start installation and wait for final message
        wait_for_element_and_click(session_selenium_webdriver, "install-button")
        # during installation, all inputs are disabled
        wait_for_expected_property(session_selenium_webdriver, "input-metadata-file-location", "disabled", True)  # type: ignore
        wait_for_expected_property(session_selenium_webdriver, "input-installation-location", "disabled", True)  # type: ignore
        wait_for_expected_property(session_selenium_webdriver, "input-python-interpreter-location", "disabled", True)  # type: ignore
        wait_for_expected_property(session_selenium_webdriver, "install-button", "disabled", True)  # type: ignore
        wait_for_partial_text(session_selenium_webdriver, "install-alert", "Installation completed in", timeout=1200)

        # Process class is not capable of getting this output as it's printed too fast to the console, before the
        # parsing thread is started.
        # assert_webview2_is_checked(installation_proc.output)
        # assert_long_paths_are_checked(installation_proc.output)
        shortcut_path = check_installed_solution_files(tmp_path, solution_root_dir)
        cleanup_shortcut.append(shortcut_path)
        check_solution_module_preload_is_executed(tmp_path, solution_root_dir)
        check_dependencies(
            tmp_path,
            solution_root_dir,
            required_dependencies=["tqdm", "pooch", "custom-package-for-test-2", "scooby"],
        )

    def test_installer_gui_installation_directory_without_write_permissions(
        self,
        tmp_path: Path,
        session_built_solution: tuple[Path, Path, str, str, str],
        install_solution_via_gui: InstallSolutionGUI,
        session_selenium_webdriver: WebDriver,
        cleanup_shortcut: list[Path],
    ):
        """
        Test recovery from an invalid installation directory in the installer UI. We check:

        - that an error message is shown when trying to use a non-writable installation directory,
        - that the install button is disabled while the directory is invalid,
        - that the installation location input is marked as invalid, and
        - that switching to a non-existent but creatable directory allows the installation to complete.
        """
        solution_root_dir, _, _, _, _ = session_built_solution

        installation_proc = install_solution_via_gui(solution_root_dir, tmp_path)
        session_selenium_webdriver.get(installation_proc.installer_ui_url)

        # Create a no-write access directory for testing
        directory_without_write_permissions = tmp_path / "no_write_access"
        directory_without_write_permissions.mkdir(parents=True, exist_ok=True)

        # Start the installer GUI with a writable directory first
        installation_proc = install_solution_via_gui(solution_root_dir, tmp_path)
        session_selenium_webdriver.get(installation_proc.installer_ui_url)

        # 1st attempt: set no-write access directory and try to install -----------------------------------------------

        wait_for_element(session_selenium_webdriver, "input-installation-location")

        with remove_directory_write_permissions(directory_without_write_permissions):
            # Test if the directory is actually no-write access by trying to create a file
            test_file = directory_without_write_permissions / "test_write.txt"
            with pytest.raises(PermissionError):
                test_file.write_text("test")

            # Change the installation directory to the no-write access one
            install_location_input = wait_for_element(session_selenium_webdriver, "input-installation-location")
            install_location_input.click()
            install_location_input.clear()
            install_location_input.send_keys(str(directory_without_write_permissions.as_posix()))

            e = wait_for_element(session_selenium_webdriver, "input-metadata-file-location")
            assert e.get_property("value").endswith("solution-metadata.json")  # type: ignore
            e = wait_for_element(session_selenium_webdriver, "input-python-interpreter-location")
            assert e.get_property("value").endswith(  # type: ignore
                "/python.exe" if platform.system() == "Windows" else "/python3",
            )
            wait_for_expected_property(session_selenium_webdriver, "install-button", "disabled", True)  # type: ignore
            wait_for_expected_attribute(session_selenium_webdriver, "input-installation-location", "invalid", "true")
            e = wait_for_element(session_selenium_webdriver, "install-alert")
            expected_text = (
                f"The installation directory '{directory_without_write_permissions.as_posix()}' is not writable. "
                f"An alternative could be:"
            )
            assert expected_text in e.text  # type: ignore

        # 2nd attempt: set non-existent but creatable directory -------------------------------------------------------

        # Change the installation directory to a non-existent but creatable one
        non_existent_directory = tmp_path / "non_existent_directory"
        install_location_input = wait_for_element(session_selenium_webdriver, "input-installation-location")
        install_location_input.click()
        install_location_input.clear()
        install_location_input.send_keys(str(non_existent_directory.as_posix()))

        _launch_installation(session_selenium_webdriver)
        _verify_installation(
            session_selenium_webdriver,
            cleanup_shortcut,
            tmp_path / "non_existent_directory",
            solution_root_dir,
        )
