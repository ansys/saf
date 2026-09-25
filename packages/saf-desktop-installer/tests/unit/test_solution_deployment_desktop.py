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

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from unittest.mock import patch
import zipfile

if platform.system() == "Windows":
    import winreg

from click.testing import CliRunner
from plotly.utils import PlotlyJSONEncoder  # pyright: ignore[reportMissingTypeStubs]
import pytest
import pytest_mock
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

import ansys.saf.desktop.installer._common.utils as common_utils
from ansys.saf.desktop.installer._common.utils import has_portal_dependency, simplify_wheel_dependency_constraints
from ansys.saf.desktop.installer._package.manage_dependencies import simplify_wheel_url_dependencies
from ansys.saf.desktop.installer._ui_styles import install_button_style
from ansys.saf.desktop.installer.solution_desktop_deployment import (
    InstallationDirectoryValidator,
    _ensure_third_party_extracted,  # pyright: ignore[reportPrivateUsage]
    build_long_path_section,
    delete_existing_solution_shortcut,
    form_layout,
    get_shortcut_path,
    install_shortcut,
    main,
    modify_solution_wheel_metadata,
)
from ansys.saf.testing.platform_specific import linux_only, windows_only
from ansys.saf.testing.selenium import (
    wait_for_element,
    wait_for_expected_attribute,
    wait_for_expected_property,
    wait_for_partial_text,
)
from tests.conftest import CUSTOM_PACKAGE_FOR_TEST_2_WHEEL_NAMES, check_installer_gui_is_using_local_bootstrap_css
from tests.unit.conftest import InstallerUi
from tests.utils import remove_directory_write_permissions

DEFAULT_INSTALLATION_DIRECTORY = InstallationDirectoryValidator.get_valid_installation_directory()


@pytest.fixture
def mock_start_gui(mocker: pytest_mock.MockerFixture) -> pytest_mock.MockType:
    return mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment._start_installer_gui")


@pytest.fixture
def mock_start_cli(mocker: pytest_mock.MockerFixture) -> pytest_mock.MockType:
    return mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment._start_installer_cli")


@pytest.fixture
def solution_metadata_path(tmp_path: Path) -> Path:
    solution_metadata_path = tmp_path / "solution-metadata.json"
    solution_metadata_path.touch()
    return solution_metadata_path


@pytest.mark.parametrize(
    "exception",
    [
        Exception("fake_exception"),
        FileNotFoundError("fake_exception"),
        subprocess.CalledProcessError(1, "fake_cmd", stderr="fake_exception"),
    ],
    ids=["generic_exception", "file_not_found_error", "subprocess_called_process_error"],
)
def test_solution_desktop_deployment_exception_handling_no_ui(
    tmp_path: Path,
    exception: Exception,
    solution_metadata_path: Path,
) -> None:
    installation_directory = tmp_path / "installation_directory"
    installation_directory.mkdir()
    runner = CliRunner()
    with (
        patch("ansys.saf.desktop.installer.solution_desktop_deployment.start_installer", side_effect=exception),
        patch(
            "ansys.saf.desktop.installer.solution_desktop_deployment.is_webview2_installed",
            return_value=(True, "1.0.0"),
        ),
        patch("ansys.saf.desktop.installer.solution_desktop_deployment.is_long_paths_enabled", return_value=True),
    ):
        result = runner.invoke(
            main,
            ["-m", str(solution_metadata_path), "-i", str(installation_directory), "-p", sys.executable, "--no-ui"],
        )
        assert result.exit_code == 1
        assert "fake_exception" in result.output


def test_modify_solution_wheel_metadata(solution_root_dir: Path) -> None:
    output = subprocess.check_output(["poetry", "build", "--no-interaction"], cwd=solution_root_dir, text=True)
    project_wheel_name = f"{output.split()[1].replace('-', '_')}-0.1.dev0-py3-none-any.whl"
    project_wheel_path = solution_root_dir / "dist" / project_wheel_name
    assert project_wheel_path.is_file()
    destination_dir = solution_root_dir / "dist" / "subdir"
    destination_dir.mkdir()
    destination_path = destination_dir / project_wheel_name
    shutil.copy(project_wheel_path, destination_path)
    modify_solution_wheel_metadata(
        solution_installation_directory=destination_path.parent,
        solution_package_name="ansys-solutions-my-solution-dash",
        solution_version="0.1.dev0",
    )
    current_platform = platform.system()
    expected_wheel_name = CUSTOM_PACKAGE_FOR_TEST_2_WHEEL_NAMES.get(current_platform)
    assert expected_wheel_name is not None, f"Unsupported platform: {current_platform}"
    other_wheel_name = next(
        name for name in CUSTOM_PACKAGE_FOR_TEST_2_WHEEL_NAMES.values() if name != expected_wheel_name
    )
    expected_line = (destination_dir / expected_wheel_name).as_posix()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        with zipfile.ZipFile(destination_path, "r") as zip_in:
            zip_in.extractall(tmpdir_path)
        metadata_path = next(tmpdir_path.glob("*.dist-info/METADATA"))
        assert metadata_path.is_file()
        assert any(expected_line in line for line in metadata_path.read_text().splitlines())
        assert not any(other_wheel_name in line for line in metadata_path.read_text().splitlines())


def test_simplify_wheel_dependency_constraints(tmp_path: Path) -> None:
    metadata_content = """Metadata-Version: 2.1
Name: test-package
Version: 1.0.0
Requires-Dist: some-package @ https://example.com/some-package-1.0.0.whl
Requires-Dist: another-package @ http://example.org/another-package-2.0.0.whl
Requires-Dist: normal-package>=1.0.0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        dist_info = tmpdir_path / "test_package-1.0.0.dist-info"
        dist_info.mkdir()
        metadata_path = dist_info / "METADATA"
        metadata_path.write_text(metadata_content, encoding="utf-8")

        wheel_path = tmp_path / "test_package-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for file_path in tmpdir_path.rglob("*"):
                if file_path.is_file():
                    zip_out.write(file_path, file_path.relative_to(tmpdir_path))

    def mock_get_version(package_name: str) -> str:
        versions = {
            "some-package": "1.0.0",
            "another-package": "2.0.0",
        }
        return versions.get(package_name, "0.0.0")

    with patch(
        "ansys.saf.desktop.installer._common.utils._get_installed_package_version",
        side_effect=mock_get_version,
    ):
        simplify_wheel_dependency_constraints(wheel_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        with zipfile.ZipFile(wheel_path, "r") as zip_in:
            zip_in.extractall(tmpdir_path)
        metadata_path = next(tmpdir_path.glob("*.dist-info/METADATA"))
        content = metadata_path.read_text(encoding="utf-8")

        assert "Requires-Dist: some-package==1.0.0" in content
        assert "Requires-Dist: another-package==2.0.0" in content
        assert "@ https://" not in content
        assert "@ http://" not in content
        assert "Requires-Dist: normal-package>=1.0.0" in content


def _get_expected_version(package_name: str) -> str:
    result = subprocess.run(
        ["pip", "show", package_name],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"Could not determine installed version for package: {package_name}")


def test_get_installed_package_version():
    package_name = "tenacity"
    expected_version = _get_expected_version(package_name)
    version = common_utils._get_installed_package_version(package_name)  # pyright: ignore[reportPrivateUsage]
    assert version == expected_version

    with pytest.raises(RuntimeError, match="Failed to get version for package wrong_package"):
        common_utils._get_installed_package_version("wrong_package")  # pyright: ignore[reportPrivateUsage]


def test_simplify_wheel_url_dependencies(tmp_path: Path) -> None:
    mock_wheel_path = (
        Path(__file__).parent.parent
        / "mocks"
        / "my-solution-dash"
        / "build_assets"
        / "ansys_solutions_custom_package_for_installer_test-0.1.dev0-py3-none-any.whl"
    )
    assert mock_wheel_path.is_file(), f"Mock wheel not found at {mock_wheel_path}"

    wheel_copy = tmp_path / mock_wheel_path.name
    shutil.copy(mock_wheel_path, wheel_copy)

    def mock_get_version(package_name: str) -> str:
        # Return version for scooby which is the wheel URL dependency in the test package
        if package_name == "scooby":
            return "0.11.2"
        return "0.0.0"

    with patch(
        "ansys.saf.desktop.installer._common.utils._get_installed_package_version",
        side_effect=mock_get_version,
    ):
        packages_with_wheel_url_deps = [("ansys-solutions-custom-package-for-installer-test", "0.1.dev0")]
        simplify_wheel_url_dependencies(packages_with_wheel_url_deps, tmp_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        with zipfile.ZipFile(wheel_copy, "r") as zip_in:
            zip_in.extractall(tmpdir_path)
        metadata_path = next(tmpdir_path.glob("*.dist-info/METADATA"))
        content = metadata_path.read_text(encoding="utf-8")

        assert "Requires-Dist: scooby==0.11.2" in content
        assert "@ https://" not in content


def test_simplify_wheel_url_dependencies_wheel_not_found(tmp_path: Path) -> None:
    packages_with_wheel_url_deps = [("nonexistent-package", "1.0.0")]

    with pytest.raises(FileNotFoundError, match="Could not find wheel for package nonexistent-package==1.0.0"):
        simplify_wheel_url_dependencies(packages_with_wheel_url_deps, tmp_path)


@windows_only()
@pytest.mark.parametrize("with_ui", [True, False], ids=["with_ui", "no_ui"])
@pytest.mark.parametrize("webview2_version", [None, "", "0.0.0.0", "1.0.864.35"])
def test_check_webview2_on_windows(
    with_ui: bool,
    webview2_version: str | None,
    mocker: pytest_mock.MockerFixture,
    solution_metadata_path: Path,
    mock_start_gui: pytest_mock.MockType,
    mock_start_cli: pytest_mock.MockType,
) -> None:

    def mock_open_key(*args: Any, **kwargs: Any):
        if webview2_version is None:
            raise FileNotFoundError("fake_exception")
        return mocker.MagicMock()

    def mock_registry_value(hkey: Any, value_name: str):
        return webview2_version, None

    mocker.patch.object(winreg, "OpenKey", side_effect=mock_open_key)  # pyright: ignore[reportPossiblyUnboundVariable]
    mocker.patch.object(winreg, "QueryValueEx", side_effect=mock_registry_value)  # pyright: ignore[reportPossiblyUnboundVariable]
    mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.is_long_paths_enabled", return_value=True)

    runner = CliRunner()
    args = ["-m", str(solution_metadata_path)]
    if not with_ui:
        args.append("--no-ui")

    result = runner.invoke(main, args, input=("\n" if webview2_version != "1.0.864.35" else ""))
    if webview2_version != "1.0.864.35":
        # WebView2 missing always exits regardless of --no-ui; the GUI cannot open without it.
        assert result.exit_code == 1
    else:
        assert result.exit_code == 0

    if webview2_version != "1.0.864.35":
        assert "- Microsoft Edge WebView2 Runtime: Not installed" in result.output
        assert "[ERROR] Microsoft Edge WebView2 Runtime is not installed. Please install it from " in result.output
        assert result.output.endswith("Press any key to exit...")
        mock_start_gui.assert_not_called()
        mock_start_cli.assert_not_called()
    else:
        assert f"- Microsoft Edge WebView2 Runtime: {webview2_version} installed" in result.output
        if with_ui:
            mock_start_gui.assert_called_once()
            mock_start_cli.assert_not_called()
        else:
            mock_start_cli.assert_called_once()
            mock_start_gui.assert_not_called()


@linux_only()
@pytest.mark.parametrize("with_ui", [True, False], ids=["with_ui", "no_ui"])
def test_webview2_check_skipped_on_linux(
    with_ui: bool,
    mocker: pytest_mock.MockerFixture,
    solution_metadata_path: Path,
    mock_start_gui: pytest_mock.MockType,
    mock_start_cli: pytest_mock.MockType,
) -> None:
    m = mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.is_webview2_installed")

    runner = CliRunner()
    args = ["-m", str(solution_metadata_path)]
    if not with_ui:
        args.append("--no-ui")
    result = runner.invoke(main, args)
    assert result.exit_code == 0
    assert "WebView2" not in result.output
    assert not m.called
    if with_ui:
        mock_start_gui.assert_called_once()
        mock_start_cli.assert_not_called()
    else:
        mock_start_cli.assert_called_once()
        mock_start_gui.assert_not_called()


@windows_only()
@pytest.mark.parametrize("with_ui", [True, False], ids=["with_ui", "no_ui"])
@pytest.mark.parametrize("long_paths_enabled", [True, False], ids=["long_paths_enabled", "long_paths_disabled"])
def test_check_long_paths_on_windows(
    with_ui: bool,
    long_paths_enabled: bool,
    mocker: pytest_mock.MockerFixture,
    solution_metadata_path: Path,
    mock_start_gui: pytest_mock.MockType,
    mock_start_cli: pytest_mock.MockType,
) -> None:
    def mock_mkdir(*args: Any, **kwargs: Any):
        if not long_paths_enabled:
            raise FileNotFoundError("path too long")

    mocker.patch("pathlib.Path.mkdir", side_effect=mock_mkdir)
    mocker.patch("shutil.rmtree")
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.is_webview2_installed",
        return_value=(True, "1.0.0"),
    )

    runner = CliRunner()
    args = ["-m", str(solution_metadata_path)]
    if not with_ui:
        args.append("--no-ui")
    result = runner.invoke(main, args, input=("\n" if not long_paths_enabled else ""))
    if not long_paths_enabled and not with_ui:
        assert result.exit_code == 1
    else:
        assert result.exit_code == 0

    if not long_paths_enabled:
        assert "- Windows Long Path enabled: False" in result.output
        assert "[ERROR] Windows Long Paths is not enabled." in result.output

        if with_ui:
            mock_start_gui.assert_called_once()
            mock_start_cli.assert_not_called()
        else:
            assert result.output.endswith("Press any key to exit...")
            mock_start_gui.assert_not_called()
            mock_start_cli.assert_not_called()
    else:
        assert "- Windows Long Path enabled: True" in result.output
        if with_ui:
            mock_start_gui.assert_called_once()
            mock_start_cli.assert_not_called()
        else:
            mock_start_cli.assert_called_once()
            mock_start_gui.assert_not_called()


@linux_only()
@pytest.mark.parametrize("with_ui", [True, False], ids=["with_ui", "no_ui"])
def test_long_paths_check_skipped_on_linux(
    with_ui: bool,
    mocker: pytest_mock.MockerFixture,
    solution_metadata_path: Path,
    mock_start_gui: pytest_mock.MockType,
    mock_start_cli: pytest_mock.MockType,
) -> None:
    m = mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.is_long_paths_enabled")

    runner = CliRunner()
    args = ["-m", str(solution_metadata_path)]
    if not with_ui:
        args.append("--no-ui")
    result = runner.invoke(main, args)
    assert result.exit_code == 0
    assert "Long paths" not in result.output
    assert not m.called
    if with_ui:
        mock_start_gui.assert_called_once()
        mock_start_cli.assert_not_called()
    else:
        mock_start_cli.assert_called_once()
        mock_start_gui.assert_not_called()


@windows_only()
@pytest.mark.parametrize("with_ui", [True, False], ids=["with_ui", "no_ui"])
def test_multiple_prerequisite_errors_on_windows(
    with_ui: bool,
    mocker: pytest_mock.MockerFixture,
    solution_metadata_path: Path,
    mock_start_gui: pytest_mock.MockType,
    mock_start_cli: pytest_mock.MockType,
) -> None:
    # Properly mock registry access
    def mock_open_key(*args: Any, **kwargs: Any):
        raise FileNotFoundError("fake_exception")

    mocker.patch.object(winreg, "OpenKey", side_effect=mock_open_key)  # pyright: ignore[reportPossiblyUnboundVariable]
    mocker.patch.object(winreg, "QueryValueEx", side_effect=FileNotFoundError("fake_exception"))  # pyright: ignore[reportPossiblyUnboundVariable]

    # Mock long-path check failure
    mocker.patch("pathlib.Path.mkdir", side_effect=FileNotFoundError("fake_exception"))
    mocker.patch("shutil.rmtree")

    runner = CliRunner()
    args = ["-m", str(solution_metadata_path)]
    if not with_ui:
        args.append("--no-ui")

    result = runner.invoke(main, args, input="\n")
    # WebView2 is missing → always exit(1) regardless of --no-ui; GUI cannot open without WebView2.
    assert result.exit_code == 1
    assert "- Microsoft Edge WebView2 Runtime: Not installed" in result.output
    assert "- Windows Long Path enabled: False" in result.output
    assert "Microsoft Edge WebView2 Runtime is not installed" in result.output
    assert "Windows Long Paths is not enabled" in result.output
    assert result.output.endswith("Press any key to exit...")
    mock_start_gui.assert_not_called()
    mock_start_cli.assert_not_called()


@pytest.fixture
def directory_is_valid(request: pytest.FixtureRequest, mocker: pytest_mock.MockerFixture) -> bool:
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.InstallationDirectoryValidator.directory_is_valid",
        return_value=request.param,
    )
    return request.param


class TestInstallationDirectoryValidator:
    """Test installation-directory validation and fallback selection."""

    def test_directory_is_valid_when_directory_exists_and_is_writable(self, tmp_path: Path) -> None:
        """Existing writable directories are accepted."""
        assert InstallationDirectoryValidator.directory_is_valid(tmp_path)

    def test_directory_is_invalid_when_directory_exists_but_is_nonwritable(self, tmp_path: Path) -> None:
        """Existing directories are rejected when the target directory itself is not writable."""
        with remove_directory_write_permissions(tmp_path):
            assert not InstallationDirectoryValidator.directory_is_valid(tmp_path)

    def test_directory_is_valid_when_directory_exists_but_parent_is_nonwritable(self, tmp_path: Path) -> None:
        """Existing writable directories stay valid even if their parent directory is not writable."""
        valid_dir = tmp_path / "valid_dir"
        valid_dir.mkdir()
        with remove_directory_write_permissions(tmp_path):
            assert InstallationDirectoryValidator.directory_is_valid(valid_dir)

    def test_directory_is_valid_when_directory_is_nonexistent_but_first_existing_parent_is_writable(
        self,
        tmp_path: Path,
    ) -> None:
        """A missing directory is valid when its first existing parent is writable."""
        assert InstallationDirectoryValidator.directory_is_valid(tmp_path / "non_existent_dir")

    def test_directory_is_invalid_when_directory_is_nonexistent_and_first_existing_parent_is_nonwritable(
        self,
        tmp_path: Path,
    ) -> None:
        """A missing directory is invalid when its first existing parent is not writable."""
        non_creatable_dir = tmp_path / "non_creatable_dir"
        with remove_directory_write_permissions(tmp_path):
            assert not InstallationDirectoryValidator.directory_is_valid(non_creatable_dir)

    def test_directory_is_valid_when_directory_is_nonexistent_first_existing_parent_is_writable_but_not_later_parents(
        self,
        tmp_path: Path,
    ) -> None:
        """Only the first existing parent controls validation for a missing directory path."""
        no_write_parent = tmp_path / "no_write_parent"
        write_parent = no_write_parent / "write_parent"
        write_parent.mkdir(parents=True)
        assert InstallationDirectoryValidator.directory_is_valid(write_parent / "non_existent_dir")

    def test_directory_is_valid_works_with_relative_paths(
        self,
        tmp_path: Path,
    ) -> None:
        """Relative installation paths are resolved against the current working directory."""
        relative_subdir = Path("subdir")
        actual_subdir = tmp_path / "subdir"
        actual_subdir.mkdir()

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            assert InstallationDirectoryValidator.directory_is_valid(relative_subdir)
        finally:
            os.chdir(original_cwd)

    @windows_only()
    def test_directory_is_invalid_when_directory_is_nonexistent_root(self) -> None:
        """A missing root drive path is invalid on Windows."""
        non_existent_root_dir = Path("Z:/") / "subdir"
        assert not InstallationDirectoryValidator.directory_is_valid(non_existent_root_dir)

    @windows_only()
    @pytest.mark.parametrize("directory_is_valid", [True, False], indirect=True)
    def test_get_valid_installation_directory_windows_programw6432_env_var(
        self,
        directory_is_valid: bool,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Test default directory on Windows with PROGRAMW6432 environment variable."""
        mocker.patch.dict(os.environ, {"PROGRAMW6432": "C:\\Program Files"})

        selected_directory = InstallationDirectoryValidator.get_valid_installation_directory()

        if directory_is_valid:
            assert selected_directory == Path("C:\\Program Files") / "ANSYS Inc" / "SAF Solutions"
        else:
            assert selected_directory != Path("C:\\Program Files") / "ANSYS Inc" / "SAF Solutions"

    @windows_only()
    @pytest.mark.parametrize("directory_is_valid", [True, False], indirect=True)
    def test_get_valid_installation_directory_windows_appdata_env_var(
        self,
        directory_is_valid: bool,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Test default directory on Windows without PROGRAMW6432 but with APPDATA environment variable and
        create_directory enabled.
        """
        env_without_programw6432 = {k: v for k, v in os.environ.items() if k != "PROGRAMW6432"}
        env_without_programw6432.update({"APPDATA": "C:\\Fake\\Path\\AppData"})
        mocker.patch.dict(os.environ, env_without_programw6432, clear=True)

        selected_directory = InstallationDirectoryValidator.get_valid_installation_directory()

        if directory_is_valid:
            assert selected_directory == Path("C:\\Fake\\Path\\AppData") / "ANSYS Inc" / "SAF Solutions"
        else:
            assert selected_directory != Path("C:\\Fake\\Path\\AppData") / "ANSYS Inc" / "SAF Solutions"

    @windows_only()
    @pytest.mark.parametrize("directory_is_valid", [True, False], indirect=True)
    def test_get_valid_installation_directory_windows_user_appdata_dir(
        self,
        directory_is_valid: bool,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Windows falls back to the user's AppData/Roaming directory when the env vars are unavailable."""
        env_without_env_vars = {k: v for k, v in os.environ.items() if k not in ["APPDATA", "PROGRAMW6432"]}
        mocker.patch.dict(os.environ, env_without_env_vars, clear=True)

        selected_directory = InstallationDirectoryValidator.get_valid_installation_directory()

        if directory_is_valid:
            assert selected_directory == Path.home() / "AppData" / "Roaming" / "ANSYS Inc" / "SAF Solutions"
        else:
            assert selected_directory != Path.home() / "AppData" / "Roaming" / "ANSYS Inc" / "SAF Solutions"

    @windows_only()
    def test_get_valid_installation_directory_windows_home_ansys(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Windows falls back to ~/ANSYS Inc/SAF Solutions when the AppData candidate is invalid."""
        original_directory_is_valid = InstallationDirectoryValidator.directory_is_valid

        def selective_directory_is_valid(path: Path) -> bool:
            if "AppData" in str(path):
                return False
            return original_directory_is_valid(path)

        mocker.patch(
            "ansys.saf.desktop.installer.solution_desktop_deployment.InstallationDirectoryValidator.directory_is_valid",
            selective_directory_is_valid,
        )
        env_without_env_vars = {k: v for k, v in os.environ.items() if k not in ["APPDATA", "PROGRAMW6432"]}
        mocker.patch.dict(os.environ, env_without_env_vars, clear=True)

        selected_directory = InstallationDirectoryValidator.get_valid_installation_directory()

        assert selected_directory == Path.home() / "ANSYS Inc" / "SAF Solutions"

    @windows_only()
    def test_get_valid_installation_directory_windows_home(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Windows falls back to the home directory when the more specific candidates are invalid."""
        original_directory_is_valid = InstallationDirectoryValidator.directory_is_valid

        def selective_directory_is_valid(path: Path) -> bool:
            if "ANSYS Inc" in str(path):
                return False
            return original_directory_is_valid(path)

        mocker.patch(
            "ansys.saf.desktop.installer.solution_desktop_deployment.InstallationDirectoryValidator.directory_is_valid",
            selective_directory_is_valid,
        )
        env_without_env_vars = {k: v for k, v in os.environ.items() if k not in ["APPDATA", "PROGRAMW6432"]}
        mocker.patch.dict(os.environ, env_without_env_vars, clear=True)

        selected_directory = InstallationDirectoryValidator.get_valid_installation_directory()

        assert selected_directory == Path.home()

    @linux_only()
    @pytest.mark.parametrize("directory_is_valid", [True, False], indirect=True)
    def test_get_valid_installation_directory_linux_as_root(
        self,
        directory_is_valid: bool,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Test default and fallback directory on Linux for a root user."""
        mocker.patch.dict(os.environ, {"SUDO_USER": "test-user"}, clear=True)

        selected_directory = InstallationDirectoryValidator.get_valid_installation_directory()

        if directory_is_valid:
            assert selected_directory == Path("/opt") / "ansys_inc" / "saf_solutions"
        else:
            assert selected_directory == Path("/usr") / "local" / "share" / "ansys_inc" / "saf_solutions"

    @linux_only()
    @pytest.mark.parametrize("directory_is_valid", [True, False], indirect=True)
    def test_get_valid_installation_directory_linux(
        self,
        directory_is_valid: bool,
    ) -> None:
        """Test default and fallback directory on Linux for a non-root user."""
        selected_directory = InstallationDirectoryValidator.get_valid_installation_directory()

        if directory_is_valid:
            assert selected_directory == Path.home() / ".local" / "share" / "ansys_inc" / "saf_solutions"
        else:
            assert selected_directory == Path.home()


@windows_only()
def test_get_shortcut_path_windows(mocker: pytest_mock.MockerFixture) -> None:
    """On Windows, the shortcut is a .lnk placed under %PUBLIC%\\Desktop."""
    mocker.patch.dict(os.environ, {"PUBLIC": r"C:\Users\Public"}, clear=True)

    result = get_shortcut_path("My Test Solution")

    assert result == Path(r"C:\Users\Public") / "Desktop" / "My Test Solution.lnk"


@linux_only()
def test_get_shortcut_path_linux_non_root(tmp_path: Path, mocker: pytest_mock.MockerFixture) -> None:
    """On Linux, a non-root user gets a .desktop entry under ~/Desktop and the directory is created."""
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch.object(Path, "home", return_value=tmp_path)

    result = get_shortcut_path("My Test Solution")

    assert result == tmp_path / "Desktop" / "My Test Solution.desktop"
    assert (tmp_path / "Desktop").is_dir()


@linux_only()
def test_get_shortcut_path_linux_root(mocker: pytest_mock.MockerFixture) -> None:
    """On Linux, when SUDO_USER is set the shortcut is placed under /usr/share/applications."""
    mocker.patch.dict(os.environ, {"SUDO_USER": "test-user"}, clear=True)
    mock_mkdir = mocker.patch.object(Path, "mkdir")

    result = get_shortcut_path("My Test Solution")

    assert result == Path("/usr/share/applications") / "My Test Solution.desktop"
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


def test_delete_existing_solution_shortcut_removes_file_if_present(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """When the resolved shortcut exists, it is removed."""
    shortcut_path = tmp_path / "My Test Solution.shortcut"
    shortcut_path.write_text("dummy")
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.get_shortcut_path",
        return_value=shortcut_path,
    )

    delete_existing_solution_shortcut("My Test Solution")

    assert not shortcut_path.exists()


def test_delete_existing_solution_shortcut_does_nothing_when_missing(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """When the resolved shortcut does not exist, no exception is raised and no unlink occurs."""
    shortcut_path = tmp_path / "does-not-exist.shortcut"
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.get_shortcut_path",
        return_value=shortcut_path,
    )
    mock_unlink = mocker.patch.object(Path, "unlink")

    delete_existing_solution_shortcut("My Test Solution")

    mock_unlink.assert_not_called()


@pytest.mark.parametrize("with_ui", [True, False], ids=["with_ui", "no_ui"])
@pytest.mark.parametrize(
    "use_default_installation_directory",
    [True, False],
    ids=["default_install_dir", "custom_install_dir"],
)
def test_write_permission_check_in_main_success_from_cli(
    with_ui: bool,
    use_default_installation_directory: bool,
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    solution_metadata_path: Path,
    mock_start_gui: pytest_mock.MockType,
    mock_start_cli: pytest_mock.MockType,
) -> None:
    """Test successful write permission checks in main for both default and custom installation directories."""
    installation_directory = DEFAULT_INSTALLATION_DIRECTORY
    args = ["-m", str(solution_metadata_path)]

    if not use_default_installation_directory:
        installation_directory = tmp_path / "install_dir"
        installation_directory.mkdir()
        args.extend(["-i", str(installation_directory)])

    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.is_webview2_installed",
        return_value=(True, "1.0.0"),
    )
    mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.is_long_paths_enabled", return_value=True)
    # Make write checks against the default installation directory (e.g. C:\Program Files\...) succeed
    # regardless of the actual admin state of the test process.
    mocker.patch("pathlib.Path.mkdir")
    mocker.patch("pathlib.Path.open", mocker.mock_open())  # type: ignore
    mocker.patch("pathlib.Path.unlink")

    runner = CliRunner()
    if not with_ui:
        args.append("--no-ui")

    result = runner.invoke(main, args)

    assert result.exit_code == 0

    if with_ui:
        mock_start_gui.assert_called_once()
        mock_start_cli.assert_not_called()
    else:
        mock_start_cli.assert_called_once()
        mock_start_gui.assert_not_called()


@pytest.mark.parametrize("with_ui", [True, False], ids=["with_ui", "no_ui"])
def test_write_permission_check_in_main_failure_fallback_from_cli(
    with_ui: bool,
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    solution_metadata_path: Path,
    mock_start_gui: pytest_mock.MockType,
    mock_start_cli: pytest_mock.MockType,
) -> None:
    """Test write permission failure with fallback directory in main function."""
    installation_directory = tmp_path / "install_dir"
    installation_directory.mkdir()
    fallback_directory = tmp_path / "fallback_dir"
    fallback_directory.mkdir(parents=True)

    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.is_webview2_installed",
        return_value=(True, "1.0.0"),
    )
    mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.is_long_paths_enabled", return_value=True)
    spy_dir_valid = mocker.spy(InstallationDirectoryValidator, "directory_is_valid")
    mock_get_fallback = mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.InstallationDirectoryValidator.get_valid_installation_directory",
        return_value=fallback_directory,
    )
    mocker.patch("pathlib.Path.open", side_effect=PermissionError())

    runner = CliRunner()
    args = ["-m", str(solution_metadata_path), "-i", str(installation_directory)]
    if not with_ui:
        args.append("--no-ui")

    with remove_directory_write_permissions(installation_directory):
        result = runner.invoke(main, args)

    assert result.exit_code == 0 if with_ui else 1

    if with_ui:
        expected_message = (
            f"Warning: The specified installation directory '{installation_directory.as_posix()}' is not writable. "
            "The installer UI will allow you to choose a valid directory."
        )
    else:
        expected_message = (
            f"Error: The specified installation directory '{installation_directory.as_posix()}' is not writable. "
            f"An alternative could be: '{fallback_directory.as_posix()}'"
        )
    assert expected_message in result.output

    spy_dir_valid.assert_called_once_with(installation_directory)

    if with_ui:
        assert mock_get_fallback.call_count == 0
        mock_start_gui.assert_called_once()
        mock_start_cli.assert_not_called()
        called_args = mock_start_gui.call_args[0][0]
        # The UI will show the invalid installation directory in red and suggest the fallback directory
        assert called_args["installation_directory"] == installation_directory
    else:
        assert mock_get_fallback.call_count == 1
        mock_start_cli.assert_not_called()
        mock_start_gui.assert_not_called()


def test_permission_checker_write_and_flush_operations(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """Test that InstallationDirectoryValidator properly writes and flushes the test file."""
    # Mock the Path.open method to return a mock file object
    mock_file = mocker.Mock()
    mock_file.__enter__ = mocker.Mock(return_value=mock_file)
    mock_file.__exit__ = mocker.Mock(return_value=None)

    mock_path_open = mocker.patch("pathlib.Path.open", return_value=mock_file)

    InstallationDirectoryValidator.directory_is_valid(tmp_path)

    # Verify that Path.open was called with write mode
    mock_path_open.assert_called_once_with("w")

    # Verify that write was called with the correct content
    mock_file.write.assert_called_once_with("This should fail if directory is read-only.")


def test_install_shortcut_linux_exec_uses_double_quotes(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir(parents=True)

    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.platform.system",
        return_value="Linux",
    )
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.Path.home",
        return_value=tmp_path,
    )
    # Production install_shortcut resolves "~/.local/share/applications/" via Path.expanduser,
    # which reads HOME/USERPROFILE from os.environ (not Path.home()); provide both so the call
    # succeeds on both POSIX and Windows CI.
    mocker.patch.dict(
        "os.environ",
        {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
        clear=True,
    )
    mock_chmod = mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.Path.chmod",
    )
    mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.shutil.copy2")
    python_path = tmp_path / "python with space" / "bin" / "python"
    icon_path = tmp_path / "assets" / "shortcut.png"
    arguments = '-m test.module --env-file "/tmp/path with spaces/.env"'

    install_shortcut(
        python=python_path,
        installation_icon_path=icon_path,
        arguments=arguments,
        solution_display_name="My Test Solution",
        display_console_window="False",
    )
    shortcut_path = desktop_dir / "My Test Solution.desktop"
    assert shortcut_path.is_file()
    content = shortcut_path.read_text(encoding="utf-8")
    assert f'Exec="{python_path}" {arguments}\n' in content
    assert f"Exec='{python_path}'" not in content
    mock_chmod.assert_called_once_with(0o755)


def test_install_shortcut_linux_uses_applications_dir_when_running_as_root(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """When SUDO_USER is set on Linux, install_shortcut writes to /usr/share/applications
    and skips the per-user copy."""
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.platform.system",
        return_value="Linux",
    )
    mocker.patch.dict(os.environ, {"SUDO_USER": "test-user"}, clear=True)
    mock_mkdir = mocker.patch.object(Path, "mkdir")
    mock_path_open = mocker.patch.object(Path, "open", mocker.mock_open())  # type: ignore
    mock_path_chmod = mocker.patch.object(Path, "chmod")
    mock_copy = mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.shutil.copy2")
    python_path = tmp_path / "python" / "bin" / "python3"
    icon_path = tmp_path / "assets" / "shortcut.png"

    install_shortcut(
        python=python_path,
        installation_icon_path=icon_path,
        arguments="-m test.module",
        solution_display_name="My Test Solution",
        display_console_window="False",
    )

    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_path_open.assert_called_once_with("w")
    written = "".join(call.args[0] for call in mock_path_open.return_value.write.call_args_list)
    assert "[Desktop Entry]" in written
    assert "Name=My Test Solution" in written
    assert f'Exec="{python_path}" -m test.module' in written
    mock_path_chmod.assert_called_once_with(0o755)
    # A SUDO_USER install skips the per-user ~/.local/share/applications copy.
    mock_copy.assert_not_called()


@pytest.mark.parametrize("platform_system", ["Windows", "Linux"], ids=["Windows", "Linux"])
def test_installer_gui_uses_pywebview_on_windows_and_webbrowser_on_linux(
    platform_system: str,
    mocker: pytest_mock.MockerFixture,
    solution_metadata_path: Path,
) -> None:
    """main() with UI dispatches to pywebview on Windows and webbrowser.open on Linux."""
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.platform.system",
        return_value=platform_system,
    )
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.is_webview2_installed",
        return_value=(True, "1.0.0"),
    )
    mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.is_long_paths_enabled", return_value=True)
    mocker.patch("pathlib.Path.mkdir")
    mocker.patch("pathlib.Path.open", mocker.mock_open())  # type: ignore
    mocker.patch("pathlib.Path.unlink")

    mock_webbrowser = mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.webbrowser.open")
    mock_process_class = mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.mp.Process")

    runner = CliRunner()
    result = runner.invoke(main, ["-m", str(solution_metadata_path)])

    assert result.exit_code == 0

    if platform_system == "Windows":
        assert mock_process_class.call_count == 2
        mock_webbrowser.assert_not_called()
    else:
        assert mock_process_class.call_count == 1
        mock_webbrowser.assert_called_once()


@pytest.mark.usefixtures("copy_assets")
class TestInstallationUI:
    """Test that the installation UI behaves as expected."""

    @pytest.mark.parametrize(
        "use_default_installation_directory",
        [True, False],
        ids=["default_install_dir", "custom_install_dir"],
    )
    def test_installation_ui_existing_writable_installation_directory(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
        use_default_installation_directory: bool,
    ) -> None:
        installation_directory: Path | None = None
        expected_installation_directory = DEFAULT_INSTALLATION_DIRECTORY

        if not use_default_installation_directory:
            installation_directory = tmp_path
            expected_installation_directory = tmp_path

        p = installer_ui(solution_metadata_path, installation_directory=installation_directory)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        with pytest.raises(TimeoutException):
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "invalid",
                "false",
                timeout=5,
            )
        wait_for_expected_property(
            selenium_webdriver,
            "input-installation-location",
            "value",
            expected_installation_directory.as_posix(),
        )
        e = wait_for_element(selenium_webdriver, "install-alert")
        assert not e.text

    def test_installation_ui_custom_existing_non_writable_installation_directory(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "non_writable_dir"
        installation_directory.mkdir()
        with remove_directory_write_permissions(installation_directory):
            p = installer_ui(solution_metadata_path, installation_directory=installation_directory)
            selenium_webdriver.get(f"http://localhost:{p.port}")
            wait_for_expected_attribute(selenium_webdriver, "input-installation-location", "invalid", "true")
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "value",
                installation_directory.as_posix(),
            )
            expected_text = (
                f"The installation directory '{installation_directory.as_posix()}' is not writable. "
                f"An alternative could be:"
            )
            wait_for_partial_text(selenium_webdriver, "install-alert", expected_text)

    def test_installation_ui_custom_non_existing_but_creatable_installation_directory(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "non_existing_dir"
        p = installer_ui(solution_metadata_path, installation_directory=installation_directory)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        with pytest.raises(TimeoutException):
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "invalid",
                "false",
                timeout=5,
            )
        wait_for_expected_property(
            selenium_webdriver,
            "input-installation-location",
            "value",
            installation_directory.as_posix(),
        )
        e = wait_for_element(selenium_webdriver, "install-alert")
        assert not e.text

    def test_installation_ui_custom_existing_installation_directory_but_non_writable_parent(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "non_writable_dir" / "subdir"
        installation_directory.mkdir(parents=True)
        with remove_directory_write_permissions(installation_directory.parent):
            p = installer_ui(solution_metadata_path, installation_directory=installation_directory)
            selenium_webdriver.get(f"http://localhost:{p.port}")
            with pytest.raises(TimeoutException):
                wait_for_expected_property(
                    selenium_webdriver,
                    "input-installation-location",
                    "invalid",
                    "false",
                    timeout=5,
                )
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "value",
                installation_directory.as_posix(),
            )
            e = wait_for_element(selenium_webdriver, "install-alert")
            assert not e.text

    def test_installation_ui_custom_non_existing_installation_directory_with_writable_parent(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "install_dir"
        installation_directory.mkdir()
        installation_directory = installation_directory / "non_existent_subdir"
        p = installer_ui(solution_metadata_path, installation_directory=installation_directory)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        with pytest.raises(TimeoutException):
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "invalid",
                "false",
                timeout=5,
            )
        wait_for_expected_property(
            selenium_webdriver,
            "input-installation-location",
            "value",
            installation_directory.as_posix(),
        )
        e = wait_for_element(selenium_webdriver, "install-alert")
        assert not e.text

    def test_installation_ui_custom_non_existing_installation_directory_with_non_writable_parent(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "install_dir"
        installation_directory.mkdir()
        with remove_directory_write_permissions(installation_directory):
            installation_directory = installation_directory / "non_existent_subdir"
            p = installer_ui(solution_metadata_path, installation_directory=installation_directory)
            selenium_webdriver.get(f"http://localhost:{p.port}")
            wait_for_expected_attribute(selenium_webdriver, "input-installation-location", "invalid", "true")
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "value",
                installation_directory.as_posix(),
            )
            expected_text = (
                f"The installation directory '{installation_directory.as_posix()}' is not writable. "
                f"An alternative could be:"
            )
            wait_for_partial_text(selenium_webdriver, "install-alert", expected_text)

    def test_installation_ui_custom_non_existing_installation_directory_with_last_parent_writable_but_not_previous(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "install_dir"
        installation_directory.mkdir()
        installation_directory = installation_directory / "non_existent_subdir"
        with remove_directory_write_permissions(tmp_path):
            p = installer_ui(solution_metadata_path, installation_directory=installation_directory)
            selenium_webdriver.get(f"http://localhost:{p.port}")
            with pytest.raises(TimeoutException):
                wait_for_expected_property(
                    selenium_webdriver,
                    "input-installation-location",
                    "invalid",
                    "false",
                    timeout=5,
                )
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "value",
                installation_directory.as_posix(),
            )
            e = wait_for_element(selenium_webdriver, "install-alert")
            assert not e.text

    def test_installation_ui_set_existing_writable_installation_directory(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "install_dir"
        installation_directory.mkdir()
        p = installer_ui(solution_metadata_path)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
        install_location_input.click()
        install_location_input.clear()
        install_location_input.send_keys(installation_directory.as_posix())
        with pytest.raises(TimeoutException):
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "invalid",
                "false",
                timeout=5,
            )
        wait_for_expected_property(
            selenium_webdriver,
            "input-installation-location",
            "value",
            installation_directory.as_posix(),
        )
        e = wait_for_element(selenium_webdriver, "install-alert")
        assert not e.text

    def test_installation_ui_set_existing_non_writable_installation_directory(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "non_writable_dir"
        installation_directory.mkdir()
        with remove_directory_write_permissions(installation_directory):
            p = installer_ui(solution_metadata_path)
            selenium_webdriver.get(f"http://localhost:{p.port}")
            install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
            install_location_input.click()
            install_location_input.clear()
            install_location_input.send_keys(installation_directory.as_posix())
            wait_for_expected_attribute(selenium_webdriver, "input-installation-location", "invalid", "true")
            install_alert = wait_for_element(selenium_webdriver, "install-alert")
            expected_error_message = (
                f"The installation directory '{installation_directory.as_posix()}' "
                f"is not writable. An alternative could be: "
            )
            assert expected_error_message in install_alert.text

    def test_installation_ui_set_non_existent_installation_directory_with_writable_parent(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        p = installer_ui(solution_metadata_path)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
        install_location_input.click()
        install_location_input.clear()
        install_location_input.send_keys((tmp_path / "non_existent_directory").as_posix())
        with pytest.raises(TimeoutException):
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "invalid",
                "false",
                timeout=5,
            )
        wait_for_expected_property(
            selenium_webdriver,
            "input-installation-location",
            "value",
            (tmp_path / "non_existent_directory").as_posix(),
        )
        e = wait_for_element(selenium_webdriver, "install-alert")
        assert not e.text

    def test_installation_ui_set_non_existent_installation_directory_with_nonwritable_parent(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "install_dir"
        installation_directory.mkdir()
        with remove_directory_write_permissions(installation_directory):
            installation_directory = installation_directory / "non_creatable_subdir"
            p = installer_ui(solution_metadata_path)
            selenium_webdriver.get(f"http://localhost:{p.port}")
            install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
            install_location_input.click()
            install_location_input.clear()
            install_location_input.send_keys(installation_directory.as_posix())
            wait_for_expected_attribute(selenium_webdriver, "input-installation-location", "invalid", "true")
            install_alert = wait_for_element(selenium_webdriver, "install-alert")
            expected_error_message = (
                f"The installation directory '{installation_directory.as_posix()}' "
                f"is not writable. An alternative could be: "
            )
            assert expected_error_message in install_alert.text

    def test_installation_ui_set_non_existent_installation_directory_with_writable_first_parent_but_not_previous(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        non_writable_dir = tmp_path / "non_writable_dir"
        writable_dir = non_writable_dir / "writable_dir"
        writable_dir.mkdir(parents=True)
        installation_directory = writable_dir / "non_existent_subdir"
        with remove_directory_write_permissions(non_writable_dir):
            p = installer_ui(solution_metadata_path)
            selenium_webdriver.get(f"http://localhost:{p.port}")
            install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
            install_location_input.click()
            install_location_input.clear()
            install_location_input.send_keys(installation_directory.as_posix())
            with pytest.raises(TimeoutException):
                wait_for_expected_property(
                    selenium_webdriver,
                    "input-installation-location",
                    "invalid",
                    "false",
                    timeout=5,
                )
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "value",
                installation_directory.as_posix(),
            )
            e = wait_for_element(selenium_webdriver, "install-alert")
            assert not e.text

    def test_installation_ui_set_existing_writable_relative_installation_directory(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        relative_subdir = Path("subdir")
        actual_subdir = tmp_path / "subdir"
        actual_subdir.mkdir()
        p = installer_ui(solution_metadata_path, cwd=tmp_path)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
        install_location_input.click()
        install_location_input.clear()
        install_location_input.send_keys(relative_subdir.as_posix())
        with pytest.raises(TimeoutException):
            wait_for_expected_property(
                selenium_webdriver,
                "input-installation-location",
                "invalid",
                "false",
                timeout=5,
            )
        wait_for_expected_property(
            selenium_webdriver,
            "input-installation-location",
            "value",
            relative_subdir.as_posix(),
        )
        e = wait_for_element(selenium_webdriver, "install-alert")
        assert not e.text

    @windows_only()
    def test_installation_ui_set_non_existing_root_installation_directory(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        non_existent_root_dir = Path("Z:/") / "subdir"
        p = installer_ui(solution_metadata_path)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
        install_location_input.click()
        install_location_input.clear()
        install_location_input.send_keys(non_existent_root_dir.as_posix())
        wait_for_expected_attribute(selenium_webdriver, "input-installation-location", "invalid", "true")
        install_alert = wait_for_element(selenium_webdriver, "install-alert")
        expected_error_message = (
            f"The installation directory '{non_existent_root_dir.as_posix()}' "
            f"is not writable. An alternative could be: "
        )
        assert expected_error_message in install_alert.text

    def test_installation_ui_resets_to_no_error(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        tmp_path: Path,
    ) -> None:
        installation_directory = tmp_path / "non_writable_dir"
        installation_directory.mkdir()
        with remove_directory_write_permissions(installation_directory):
            p = installer_ui(solution_metadata_path)
            selenium_webdriver.get(f"http://localhost:{p.port}")
            install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
            install_location_input.click()
            install_location_input.clear()
            install_location_input.send_keys(installation_directory.as_posix())
            wait_for_expected_attribute(selenium_webdriver, "input-installation-location", "invalid", "true")
            expected_text = (
                f"The installation directory '{installation_directory.as_posix()}' is not writable. "
                f"An alternative could be:"
            )
            wait_for_partial_text(selenium_webdriver, "install-alert", expected_text)
        install_location_input = wait_for_element(selenium_webdriver, "input-installation-location")
        install_location_input.click()
        install_location_input.clear()
        install_location_input.send_keys(installation_directory.as_posix())
        wait_for_expected_attribute(selenium_webdriver, "input-installation-location", "invalid", None)
        install_alert = wait_for_element(selenium_webdriver, "install-alert")
        assert install_alert.text == ""

    @pytest.mark.usefixtures("copy_assets")
    def test_installation_ui_uses_bundled_bootstrap_css(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
    ) -> None:
        p = installer_ui(solution_metadata_path)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        wait_for_expected_property(
            selenium_webdriver,
            "input-installation-location",
            "value",
            DEFAULT_INSTALLATION_DIRECTORY.as_posix(),
        )
        check_installer_gui_is_using_local_bootstrap_css(selenium_webdriver)

    @windows_only()
    @pytest.mark.parametrize(
        ("toggle_checkbox", "expected_checkbox_selected", "expected_warning_visible"),
        [
            (False, True, False),
            (True, False, True),
        ],
        ids=["default_checked_warning_hidden", "unchecked_warning_visible"],
    )
    def test_long_path_checkbox_state_and_warning_visibility(
        self,
        solution_metadata_path: Path,
        installer_ui: InstallerUi,
        selenium_webdriver: WebDriver,
        toggle_checkbox: bool,
        expected_checkbox_selected: bool,
        expected_warning_visible: bool,
    ) -> None:
        """Long-path checkbox state controls warning visibility in the installer UI."""
        p = installer_ui(solution_metadata_path)
        selenium_webdriver.get(f"http://localhost:{p.port}")
        wait_for_expected_property(
            selenium_webdriver,
            "input-installation-location",
            "value",
            DEFAULT_INSTALLATION_DIRECTORY.as_posix(),
        )
        checkbox_container = wait_for_element(selenium_webdriver, "long-path-check-checkbox")
        checkbox_input = checkbox_container.find_element(By.CSS_SELECTOR, "input[type='checkbox']")  # pyright: ignore[reportUnknownMemberType]

        if toggle_checkbox:
            checkbox_input.click()
            # Wait until the warning text is rendered after toggling.
            wait_for_partial_text(selenium_webdriver, "long-path-warning", "short path")

        assert checkbox_input.is_selected() is expected_checkbox_selected
        warning = wait_for_element(selenium_webdriver, "long-path-warning")
        assert warning.is_displayed() is expected_warning_visible


@pytest.mark.parametrize(
    ("platform_name", "expect_long_path_components", "python_interpreter_name"),
    [
        ("Windows", True, "python.exe"),
        ("Linux", False, "python"),
    ],
    ids=["windows_includes_long_path_components", "linux_excludes_long_path_components"],
)
def test_form_layout_long_path_components_visibility_depends_on_platform(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    platform_name: str,
    expect_long_path_components: bool,
    python_interpreter_name: str,
) -> None:
    """form_layout includes long-path controls only for Windows."""
    mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.platform.system", return_value=platform_name)
    fake_root = tmp_path / "root"
    (fake_root / "assets").mkdir(parents=True)
    (fake_root / "assets" / "installer_ui_logo.png").write_bytes(b"\x89PNG\r\n")
    mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.ROOT_DIR", fake_root)

    args = {
        "metadata_file": tmp_path / "metadata.json",
        "installation_directory": tmp_path / "install",
        "python_interpreter": tmp_path / python_interpreter_name,
    }
    layout = form_layout(args)
    layout_json = json.dumps(layout.to_plotly_json(), cls=PlotlyJSONEncoder)

    if expect_long_path_components:
        assert "long-path-check-checkbox" in layout_json
        assert "long-path-warning" in layout_json
        assert "Check Windows Long Paths enabled" in layout_json
    else:
        assert "long-path-check-checkbox" not in layout_json
        assert "long-path-warning" not in layout_json


@pytest.mark.parametrize(
    ("disabled", "expected_background", "expected_border", "expected_pointer_events", "expected_cursor"),
    [
        (False, "#000000", "2px solid #000000", "auto", "pointer"),
        (True, "#d9d9d9", "2px solid #d9d9d9", "none", "not-allowed"),
    ],
    ids=["enabled", "disabled"],
)
def test_install_button_style(
    disabled: bool,
    expected_background: str,
    expected_border: str,
    expected_pointer_events: str,
    expected_cursor: str,
) -> None:
    """Install button style reflects the disabled state."""
    style = install_button_style(disabled=disabled)
    assert style["background-color"] == expected_background
    assert style["border"] == expected_border
    assert style["pointer-events"] == expected_pointer_events
    assert style["cursor"] == expected_cursor
    assert style["color"] == "white"


def test_build_prerequisites_section_returns_empty_when_no_missing() -> None:
    """build_long_path_section returns an empty list when there is no long-path warning to show."""
    assert build_long_path_section({}) == []


def test_build_prerequisites_section() -> None:
    """build_long_path_section renders the warning text and documentation link for a long-path error."""
    long_path_error = {"message": "Windows Long Path is not enabled.", "doc_url": "https://example.com"}
    expected_texts = ["Windows Long Path is not enabled.", "https://example.com", "See instructions."]
    expected_link_count = 1
    result = build_long_path_section(long_path_error)
    assert len(result) == 1
    layout_json = json.dumps(result[0].to_plotly_json(), cls=PlotlyJSONEncoder)

    for text in expected_texts:
        assert text in layout_json

    assert layout_json.count("See instructions.") == expected_link_count


def _write_poetry_lock(root_dir: Path, package_names: list[str]) -> None:
    packages = "\n".join(
        f'[[package]]\nname = "{name}"\nversion = "1.0.0"\ndescription = ""\n' for name in package_names
    )
    (root_dir / "poetry.lock").write_text(packages)


def test_solution_detect_saf_portal_dependency(tmp_path: Path) -> None:
    _write_poetry_lock(tmp_path, ["ansys-saf-portal"])
    assert has_portal_dependency(tmp_path)


def test_solution_detect_saf_desktop_portal_dependency(tmp_path: Path) -> None:
    _write_poetry_lock(tmp_path, ["ansys-saf-desktop-portal"])
    assert has_portal_dependency(tmp_path)


def test_solution_without_portal_doesnt_detect_portal_dependency(tmp_path: Path) -> None:
    _write_poetry_lock(tmp_path, ["some-other-package"])
    assert not has_portal_dependency(tmp_path)


@pytest.mark.parametrize(
    ("platform_system", "setup_zip", "setup_dir", "should_extract"),
    [
        ("Windows", True, False, True),  # Extract when ZIP exists and dir missing
        ("Windows", True, True, False),  # Skip when dir exists (idempotent)
        ("Windows", False, False, False),  # Skip when ZIP missing
        ("Linux", True, False, False),  # No-op on Linux
    ],
    ids=["windows_extract", "windows_skip_dir_exists", "windows_skip_zip_missing", "linux_noop"],
)
def test_ensure_third_party_extracted(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    platform_system: str,
    setup_zip: bool,
    setup_dir: bool,
    should_extract: bool,
) -> None:
    """Test _ensure_third_party_extracted under various platform and file conditions."""
    mocker.patch(
        "ansys.saf.desktop.installer.solution_desktop_deployment.platform.system",
        return_value=platform_system,
    )
    mocker.patch("ansys.saf.desktop.installer.solution_desktop_deployment.ROOT_DIR", tmp_path)

    if setup_zip:
        with zipfile.ZipFile(tmp_path / "third_party.zip", "w") as zf:
            zf.writestr("python/test.dll", b"test content")

    if setup_dir:
        (tmp_path / "third_party").mkdir()
        (tmp_path / "third_party" / "existing.txt").write_text("existing")

    _ensure_third_party_extracted()

    if should_extract:
        assert (tmp_path / "third_party" / "python" / "test.dll").read_bytes() == b"test content"
        assert not (tmp_path / "third_party.zip").is_file()  # ZIP deleted after extraction
    else:
        if setup_dir:
            assert (tmp_path / "third_party" / "existing.txt").read_text() == "existing"
        else:
            assert not (tmp_path / "third_party").exists()
