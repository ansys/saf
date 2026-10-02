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
import platform
import re
import subprocess
from unittest.mock import MagicMock, call

from packaging.version import Version
import pytest
import pytest_mock
import requests

from ansys.saf.desktop.installer._package.download_python import (
    NUGET_VERSIONS_URL,
    OFFICIAL_VERSIONS_URLS,
    PythonIndexHTMLParser,
    PythonManager,
)
from ansys.saf.testing.platform_specific import windows_only


def _get_latest_python_versions() -> dict[str, str]:
    response = requests.get(OFFICIAL_VERSIONS_URLS[0])
    latest_python_versions: dict[str, str] = {}
    for major_minor in ["3.11", "3.12", "3.13", "3.14"]:
        versions: list[str] = [version["name"].split(" ")[-1] for version in response.json()]
        versions = [version for version in versions if version.startswith(major_minor) and len(version.split(".")) == 3]
        sorted_versions = sorted(versions, key=Version)
        latest_python_versions[major_minor] = sorted_versions[-1]
    return latest_python_versions


LATEST_PYTHON_VERSIONS = _get_latest_python_versions()
LATEST_3_11 = LATEST_PYTHON_VERSIONS["3.11"]
LATEST_3_12 = LATEST_PYTHON_VERSIONS["3.12"]
LATEST_3_13 = LATEST_PYTHON_VERSIONS["3.13"]
LATEST_3_14 = LATEST_PYTHON_VERSIONS["3.14"]


class TestPythonIndexHTMLParser:
    def test_parse_valid_python_versions_from_html(self):
        """Test parsing valid Python version links from HTML."""
        parser = PythonIndexHTMLParser()
        html_content = """
        <html>
        <body>
        <a href="3.11.9/">3.11.9</a>
        <a href="3.12.0/">3.12.0</a>
        <a href="3.13.0/">3.13.0</a>
        <a href="3.14.0/">3.14.0</a>
        </body>
        </html>
        """
        parser.feed(html_content)

        assert "3.11.9" in parser.versions
        assert "3.12.0" in parser.versions
        assert "3.13.0" in parser.versions
        assert "3.14.0" in parser.versions

    def test_ignores_non_version_links(self):
        """Test that non-version links are ignored."""
        parser = PythonIndexHTMLParser()
        html_content = """
        <html>
        <body>
        <a href="../">Parent</a>
        <a href="docs/">Docs</a>
        <a href="3.11.11/">3.11.11</a>
        <a href="README.txt">README</a>
        </body>
        </html>
        """
        parser.feed(html_content)

        assert parser.versions == ["3.11.11"]

    def test_ignores_links_without_trailing_slash(self):
        """Test that links without trailing slash are ignored."""
        parser = PythonIndexHTMLParser()
        html_content = """
        <html>
        <body>
        <a href="3.11.9">3.11.9</a>
        <a href="3.11.11/">3.11.11</a>
        </body>
        </html>
        """
        parser.feed(html_content)

        assert parser.versions == ["3.11.11"]

    def test_ignores_short_links(self):
        """Test that short links (less than 5 chars) are ignored."""
        parser = PythonIndexHTMLParser()
        html_content = """
        <html>
        <body>
        <a href="3.1/">3.1</a>
        <a href="3.11.11/">3.11.11</a>
        </body>
        </html>
        """
        parser.feed(html_content)

        assert parser.versions == ["3.11.11"]

    def test_empty_html(self):
        """Test parsing empty HTML returns empty versions list."""
        parser = PythonIndexHTMLParser()
        parser.feed("<html><body></body></html>")

        assert parser.versions == []

    def test_links_without_href_are_ignored(self):
        """Test that anchor tags without href attribute are ignored."""
        parser = PythonIndexHTMLParser()
        html_content = """
        <html>
        <body>
        <a name="3.11.9">3.11.9</a>
        <a href="3.11.11/">3.11.11</a>
        </body>
        </html>
        """
        parser.feed(html_content)

        assert parser.versions == ["3.11.11"]


class TestGetAvailablePythonVersionsMultipleUrls:
    def test_first_url_success_does_not_call_second(self, tmp_path: Path, mocker: pytest_mock.MockFixture):
        """Test that if first URL succeeds, second URL is not called."""
        mock_get = mocker.patch("requests.get")
        first_response = MagicMock()
        first_response.status_code = 200
        first_response.json.return_value = [
            {"name": "Python 3.11.14"},
            {"name": "Python 3.12.12"},
            {"name": "Python 3.13.0"},
            {"name": "Python 3.14.0"},
        ]
        mock_get.return_value = first_response

        mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=True)
        mock_get_python_exec = mocker.patch.object(
            PythonManager,
            "_get_downloaded_python_exec",
            return_value=Path("fake_path"),
        )
        python_manager = PythonManager(tmp_path, "3.11.14", False, False)
        python_manager.setup_python_interpreter()

        mock_get.assert_called_once_with(OFFICIAL_VERSIONS_URLS[0])
        mock_check.assert_called_once()
        mock_get_python_exec.assert_called_once()

    def test_fallback_to_second_url_when_first_fails(self, tmp_path: Path, mocker: pytest_mock.MockFixture):
        """Test fallback to second URL when first returns non-200 status."""
        mock_get = mocker.patch("requests.get")
        first_response = MagicMock()
        first_response.status_code = 500
        first_response.content = b"Internal Server Error"
        second_response = MagicMock()
        second_response.status_code = 200
        second_response.text = """
        <html>
        <body>
        <a href="3.11.14/">3.11.14</a>
        <a href="3.12.12/">3.12.12</a>
        <a href="3.13.0/">3.13.0</a>
        <a href="3.14.0/">3.14.0</a>
        </body>
        </html>
        """
        mock_get.side_effect = [first_response, second_response]

        mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=True)
        mock_get_python_exec = mocker.patch.object(
            PythonManager,
            "_get_downloaded_python_exec",
            return_value=Path("fake_path"),
        )
        python_manager = PythonManager(tmp_path, "3.11.14", False, False)
        python_manager.setup_python_interpreter()

        assert mock_get.call_args_list == [call(OFFICIAL_VERSIONS_URLS[0]), call(OFFICIAL_VERSIONS_URLS[1])]
        mock_check.assert_called_once()
        mock_get_python_exec.assert_called_once()

    def test_raises_error_when_all_urls_fail(self, tmp_path: Path, mocker: pytest_mock.MockFixture):
        """Test RuntimeError is raised when all URLs fail."""
        mock_get = mocker.patch("requests.get")

        first_response = MagicMock()
        first_response.status_code = 500
        first_response.content = b"Internal Server Error"

        second_response = MagicMock()
        second_response.status_code = 404
        second_response.content = b"Not Found"

        mock_get.side_effect = [first_response, second_response]

        expected_error = (
            "Failed to retrieve Python versions: "
            "https://www.python.org/api/v2/downloads/release/: 500 b'Internal Server Error', "
            "https://www.python.org/ftp/python: 404 b'Not Found'"
        )
        with pytest.raises(RuntimeError, match=expected_error):
            PythonManager(tmp_path, "3.11.14", False, False)

        assert mock_get.call_args_list == [call(OFFICIAL_VERSIONS_URLS[0]), call(OFFICIAL_VERSIONS_URLS[1])]

    def test_real_request_to_first_url(self, tmp_path: Path, mocker: pytest_mock.MockFixture):
        """Test real HTTP request to the first URL."""
        mock_get = mocker.spy(requests, "get")
        mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=True)
        mock_get_python_exec = mocker.patch.object(
            PythonManager,
            "_get_downloaded_python_exec",
            return_value=Path("fake_path"),
        )
        python_manager = PythonManager(tmp_path, "3.11.14", False, False)
        python_manager.setup_python_interpreter()

        mock_get.assert_called_once_with(OFFICIAL_VERSIONS_URLS[0])
        mock_check.assert_called_once()
        mock_get_python_exec.assert_called_once()

    def test_real_request_fallback_to_second_url(self, tmp_path: Path, mocker: pytest_mock.MockFixture):
        """Test real HTTP request fallback to second URL when first fails."""
        # Pre-fetch the real response from the second URL before mocking
        second_real_response = requests.get(OFFICIAL_VERSIONS_URLS[1])
        assert second_real_response.status_code == 200

        # Now set up the mock to fail the first URL and return real data for second
        mock_get = mocker.patch("requests.get")

        first_mock_response = MagicMock()
        first_mock_response.status_code = 500
        first_mock_response.content = b"Internal Server Error"

        second_mock_response = MagicMock()
        second_mock_response.status_code = 200
        second_mock_response.text = second_real_response.text

        mock_get.side_effect = [first_mock_response, second_mock_response]

        mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=True)
        mock_get_python_exec = mocker.patch.object(
            PythonManager,
            "_get_downloaded_python_exec",
            return_value=Path("fake_path"),
        )
        python_manager = PythonManager(tmp_path, "3.11.14", False, False)
        python_manager.setup_python_interpreter()

        assert mock_get.call_args_list == [call(OFFICIAL_VERSIONS_URLS[0]), call(OFFICIAL_VERSIONS_URLS[1])]
        mock_check.assert_called_once()
        mock_get_python_exec.assert_called_once()


def test_python_is_not_downloaded_nor_installed_if_already_exists(tmp_path: Path, mocker: pytest_mock.MockFixture):
    mock_subprocess = mocker.patch("subprocess.check_output")

    mock_download = mocker.patch.object(PythonManager, "_download_python_interpreter")
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")

    python_manager = PythonManager(tmp_path, "3.11.14", False, False)

    mock_subprocess.return_value = f"Python {python_manager._python_version}"  # pyright: ignore[reportPrivateUsage]

    if platform.system() == "Windows":
        tools_folder = python_manager._python_dir / "tools"  # pyright: ignore[reportPrivateUsage]
        tools_folder.mkdir(parents=True)
        python_exec = python_manager._python_dir / "tools" / "python.exe"  # pyright: ignore[reportPrivateUsage]
        python_exec.touch()
        pythonw_exec = python_manager._python_dir / "tools" / "pythonw.exe"  # pyright: ignore[reportPrivateUsage]
        pythonw_exec.touch()
    elif platform.system() == "Linux":
        bin_folder = python_manager._python_dir / "bin"  # pyright: ignore[reportPrivateUsage]
        bin_folder.mkdir(parents=True)
        python_exec = python_manager._python_dir / "bin" / "python3"  # pyright: ignore[reportPrivateUsage]
        python_exec.touch()
    else:
        raise ValueError("Unsupported operating system.")

    python_manager.setup_python_interpreter()

    mock_download.assert_not_called()
    mock_install.assert_not_called()


def test_python_is_downloaded_and_installed_if_python_exec_is_missing(tmp_path: Path, mocker: pytest_mock.MockFixture):
    mock_download = mocker.patch.object(PythonManager, "_download_python_interpreter", return_value=Path("fake_path"))
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")
    mock_get_python_exec = mocker.patch.object(
        PythonManager,
        "_get_downloaded_python_exec",
        return_value=Path("fake_path"),
    )

    python_manager = PythonManager(tmp_path, "3.11.14", False, False)

    if platform.system() == "Windows":
        tools_folder = python_manager._python_dir / "tools"  # pyright: ignore[reportPrivateUsage]
        tools_folder.mkdir(parents=True)
        pythonw_exec = python_manager._python_dir / "tools" / "pythonw.exe"  # pyright: ignore[reportPrivateUsage]
        pythonw_exec.touch()

    python_manager.setup_python_interpreter()

    mock_download.assert_called_once()
    mock_install.assert_called_once_with(Path("fake_path"))
    assert mock_get_python_exec.call_count == 2


def test_python_is_downloaded_and_installed_if_pythonw_exec_is_missing(tmp_path: Path, mocker: pytest_mock.MockFixture):
    mock_download = mocker.patch.object(PythonManager, "_download_python_interpreter", return_value=Path("fake_path"))
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")

    python_manager = PythonManager(tmp_path, "3.11.14", False, False)

    if platform.system() == "Windows":
        tools_folder = python_manager._python_dir / "tools"  # pyright: ignore[reportPrivateUsage]
        tools_folder.mkdir(parents=True)
        python_exec = python_manager._python_dir / "tools" / "python.exe"  # pyright: ignore[reportPrivateUsage]
        python_exec.touch()
    elif platform.system() == "Linux":
        bin_folder = python_manager._python_dir / "bin"  # pyright: ignore[reportPrivateUsage]
        bin_folder.mkdir(parents=True)
        python_exec = python_manager._python_dir / "bin" / "python3"  # pyright: ignore[reportPrivateUsage]
        python_exec.touch()
    else:
        raise ValueError("Unsupported operating system.")

    python_manager.setup_python_interpreter()

    mock_download.assert_called_once()
    mock_install.assert_called_once_with(Path("fake_path"))


def test_python_is_downloaded_and_installed_if_python_is_installed_with_different_version(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
):
    mock_subprocess = mocker.patch("subprocess.check_output")

    mock_download = mocker.patch.object(PythonManager, "_download_python_interpreter", return_value=Path("fake_path"))
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")

    python_manager = PythonManager(tmp_path, "3.11.14", False, False)

    mock_subprocess.return_value = "Python 3.12.9"  # pyright: ignore[reportPrivateUsage]

    if platform.system() == "Windows":
        tools_folder = python_manager._python_dir / "tools"  # pyright: ignore[reportPrivateUsage]
        tools_folder.mkdir(parents=True)
        python_exec = python_manager._python_dir / "tools" / "python.exe"  # pyright: ignore[reportPrivateUsage]
        python_exec.touch()
    elif platform.system() == "Linux":
        bin_folder = python_manager._python_dir / "bin"  # pyright: ignore[reportPrivateUsage]
        bin_folder.mkdir(parents=True)
        python_exec = python_manager._python_dir / "bin" / "python3"  # pyright: ignore[reportPrivateUsage]
        python_exec.touch()
    else:
        raise ValueError("Unsupported operating system.")

    python_manager.setup_python_interpreter()

    mock_download.assert_called_once()
    mock_install.assert_called_once_with(Path("fake_path"))


@pytest.mark.parametrize(
    ("selected_version", "used_version"),
    [
        ("3.11.9", LATEST_3_11),
        ("3.12.9", "3.12.9"),
        ("3.12.12", "3.12.12"),
        ("3.13.0", "3.13.0"),
        ("3.14.0", "3.14.0"),
    ],
)
def test_download_python_interpreter_with_vulnerable_complete_version(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
    selected_version: str,
    used_version: str,
):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=False)
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")
    mock_get_python_exec = mocker.patch.object(
        PythonManager,
        "_get_downloaded_python_exec",
        return_value=Path("fake_path"),
    )

    python_manager = PythonManager(tmp_path, selected_version, False, False)
    python_manager.setup_python_interpreter()

    nuget_versions = PythonManager._get_available_python_versions([NUGET_VERSIONS_URL])  # pyright: ignore[reportPrivateUsage]
    if platform.system() == "Windows" and used_version in nuget_versions:
        python_file = tmp_path / "third_party" / f"python-{used_version}.zip"
    else:
        python_file = tmp_path / "third_party" / f"python-{used_version}.tgz"
    assert python_file.is_file()

    mock_check.assert_called_once()
    mock_install.assert_called_once_with(python_file)
    mock_get_python_exec.assert_called_once()


@pytest.mark.parametrize(
    ("selected_version", "used_version"),
    [
        ("3", LATEST_3_14),
        ("3.11", LATEST_3_11),
        ("3.12", LATEST_3_12),
        ("3.13", LATEST_3_13),
        ("3.14", LATEST_3_14),
    ],
)
def test_download_python_interpreter_with_vulnerable_incomplete_version(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
    selected_version: str,
    used_version: str,
):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=False)
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")
    mock_get_python_exec = mocker.patch.object(
        PythonManager,
        "_get_downloaded_python_exec",
        return_value=Path("fake_path"),
    )

    python_manager = PythonManager(tmp_path, selected_version, False, False)
    python_manager.setup_python_interpreter()

    nuget_versions = PythonManager._get_available_python_versions([NUGET_VERSIONS_URL])  # pyright: ignore[reportPrivateUsage]
    if platform.system() == "Windows" and used_version in nuget_versions:
        python_file = tmp_path / "third_party" / f"python-{used_version}.zip"
    else:
        python_file = tmp_path / "third_party" / f"python-{used_version}.tgz"
    assert python_file.is_file()

    mock_check.assert_called_once()
    mock_install.assert_called_once_with(python_file)
    mock_get_python_exec.assert_called_once()


@pytest.mark.parametrize(
    ("selected_version", "used_version"),
    [
        ("3.11.14", "3.11.14"),
        ("3.12.9", "3.12.9"),
        ("3.13.0", "3.13.0"),
        ("3.14.0", "3.14.0"),
    ],
)
def test_download_python_interpreter_with_safe_versions(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
    selected_version: str,
    used_version: str,
):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=False)
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")
    mock_get_python_exec = mocker.patch.object(
        PythonManager,
        "_get_downloaded_python_exec",
        return_value=Path("fake_path"),
    )

    python_manager = PythonManager(tmp_path, selected_version, False, False)
    python_manager.setup_python_interpreter()

    # some versions are available in nuget and others are not, so the extension changes between .zip and .tgz
    nuget_versions = PythonManager._get_available_python_versions([NUGET_VERSIONS_URL])  # pyright: ignore[reportPrivateUsage]
    if platform.system() == "Windows" and used_version in nuget_versions:
        python_file = tmp_path / "third_party" / f"python-{used_version}.zip"
    else:
        python_file = tmp_path / "third_party" / f"python-{used_version}.tgz"
    assert python_file.is_file()

    mock_check.assert_called_once()
    mock_install.assert_called_once_with(python_file)
    mock_get_python_exec.assert_called_once()


@pytest.mark.parametrize(
    ("selected_version", "used_version"),
    [
        ("3", LATEST_3_14),
        ("3.11", LATEST_3_11),
        ("3.12", LATEST_3_12),
        ("3.13", LATEST_3_13),
        ("3.14", LATEST_3_14),
        ("3.11.9", "3.11.9"),
        ("3.11.14", "3.11.14"),
        ("3.12.0", "3.12.0"),
        ("3.12.4", "3.12.4"),
        ("3.12.11", "3.12.11"),
        ("3.13.0", "3.13.0"),
        ("3.14.0", "3.14.0"),
    ],
)
def test_download_python_interpreter_with_ignore_minimum_version(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
    selected_version: str,
    used_version: str,
):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=False)
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")
    mock_get_python_exec = mocker.patch.object(
        PythonManager,
        "_get_downloaded_python_exec",
        return_value=Path("fake_path"),
    )

    python_manager = PythonManager(tmp_path, selected_version, True, False)
    python_manager.setup_python_interpreter()

    # some versions are available in nuget and others are not, so the extension changes between .zip and .tgz
    nuget_versions = PythonManager._get_available_python_versions([NUGET_VERSIONS_URL])  # pyright: ignore[reportPrivateUsage]
    if platform.system() == "Windows" and used_version in nuget_versions:
        python_file = tmp_path / "third_party" / f"python-{used_version}.zip"
    else:
        python_file = tmp_path / "third_party" / f"python-{used_version}.tgz"
    assert python_file.is_file()

    mock_check.assert_called_once()
    mock_install.assert_called_once_with(python_file)
    mock_get_python_exec.assert_called_once()


def test_python_download_url_response_not_ok(tmp_path: Path, mocker: pytest_mock.MockFixture):
    mock_get = mocker.patch("requests.get")
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=False)
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")

    available_versions = ["3.11.14"]

    mocker.patch.object(
        PythonManager,
        "_get_available_python_versions",
        return_value=available_versions,
    )

    python_manager = PythonManager(tmp_path, "3.11.14", False, False)

    mock_get.return_value.ok = False
    mock_get.status_code = 400
    error_message = (
        "Could not downloaded python version: "
        f"{python_manager._python_version}."  # pyright: ignore[reportPrivateUsage]
    )
    with pytest.raises(RuntimeError, match=error_message):
        python_manager.setup_python_interpreter()

    mock_check.assert_called_once()
    mock_install.assert_not_called()


def test_download_python_interpreter_version_longer_than_patch(tmp_path: Path, mocker: pytest_mock.MockFixture):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed")
    mock_download = mocker.patch.object(PythonManager, "_download_python_interpreter")
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")

    with pytest.raises(
        ValueError,
        match=(
            "Unexpected python version: 3.11.14.4. Accepted python version can have values up to the patch version."
        ),
    ):
        PythonManager(tmp_path, "3.11.14.4", False, False)

    mock_check.assert_not_called()
    mock_download.assert_not_called()
    mock_install.assert_not_called()


def test_download_python_interpreter_version_not_available(tmp_path: Path, mocker: pytest_mock.MockFixture):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed")
    mock_download = mocker.patch.object(PythonManager, "_download_python_interpreter")
    mock_install = mocker.patch.object(PythonManager, "_install_python_interpreter")

    available_versions = ["3.11.14", "3.12.9", "3.13.0", "3.14.0"]

    mocker.patch.object(
        PythonManager,
        "_get_available_python_versions",
        return_value=available_versions,
    )

    with pytest.raises(
        ValueError,
        match=re.escape(
            f"The selected python version: 3.11.25, is not among the available python versions: {available_versions}.",
        ),
    ):
        PythonManager(tmp_path, "3.11.25", False, False)

    mock_check.assert_not_called()
    mock_download.assert_not_called()
    mock_install.assert_not_called()


@pytest.mark.parametrize(
    ("selected_version", "used_version"),
    [
        ("3.11.4", LATEST_3_11),
        ("3.12.9", "3.12.9"),
        ("3.13.0", "3.13.0"),
        ("3.14.0", "3.14.0"),
    ],
)
def test_python_is_installed(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
    selected_version: str,
    used_version: str,
):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=False)

    python_manager = PythonManager(tmp_path, selected_version, False, False)

    python_manager.setup_python_interpreter()

    if platform.system() == "Windows":
        nuget_versions = PythonManager._get_available_python_versions([NUGET_VERSIONS_URL])  # pyright: ignore[reportPrivateUsage]
        if used_version in nuget_versions:
            python_file = tmp_path / "third_party" / "python" / "tools" / "python.exe"
            pythonw_file = tmp_path / "third_party" / "python" / "tools" / "pythonw.exe"
        else:
            python_file = tmp_path / "third_party" / "python" / "python.exe"
            pythonw_file = tmp_path / "third_party" / "python" / "pythonw.exe"
        assert pythonw_file.is_file()
    elif platform.system() == "Linux":
        python_file = tmp_path / "third_party" / "python" / "bin" / "python3"
    else:
        raise ValueError("Unsupported operating system.")
    assert python_file.is_file()

    cmd = [python_file, "--version"]
    output = subprocess.check_output(cmd, text=True).strip()
    version = output.split(" ")[-1]
    assert version == used_version

    third_party_dir_content = list((tmp_path / "third_party").glob("*"))
    assert third_party_dir_content == [tmp_path / "third_party" / "python"]

    mock_check.assert_called_once()


@windows_only()
def test_python_is_installed_from_source_with_force_python_from_source(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=False)
    mock_download = mocker.patch.object(PythonManager, "_download_python_interpreter")
    mock_install_from_source = mocker.patch.object(
        PythonManager,
        f"_install_python_interpreter_from_source_code_on_{platform.system().lower()}",
    )
    mocker.patch("tarfile.open")
    mocker.patch("pathlib.Path.mkdir")
    mock_get_python_exec = mocker.patch.object(
        PythonManager,
        "_get_downloaded_python_exec",
        return_value=Path("fake_path"),
    )

    # Python version 3.12.9 is available in nuget, but we force the download from python.org as source code
    python_manager = PythonManager(tmp_path, "3.12.9", False, True)

    python_manager.setup_python_interpreter()

    mock_check.assert_called_once()
    mock_download.assert_called_once()
    mock_install_from_source.assert_called_once()
    mock_get_python_exec.assert_called_once()


@pytest.mark.parametrize("python_version", [LATEST_3_11, LATEST_3_12, LATEST_3_13, LATEST_3_14])
def test_download_python_built_from_source_can_import_and_use_tkinter(
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
    python_version: str,
):
    mock_check = mocker.patch.object(PythonManager, "_check_if_python_is_installed", return_value=False)

    python_manager = PythonManager(tmp_path, python_version, False, True)

    python_manager.setup_python_interpreter()

    python_file = (
        tmp_path / "third_party" / "python" / "python.exe"
        if platform.system() == "Windows"
        else tmp_path / "third_party" / "python" / "bin" / "python3"
    )
    assert python_file.is_file()

    cmd = [python_file, "--version"]
    output = subprocess.check_output(cmd, text=True).strip()
    version = output.split(" ")[-1]
    assert version == python_version

    third_party_dir_content = list((tmp_path / "third_party").glob("*"))
    assert third_party_dir_content == [tmp_path / "third_party" / "python"]

    cmd: list[str | Path] = []
    if platform.system() == "Linux":
        cmd += ["xvfb-run", "-a"]
    cmd += [python_file, "-c", "import tkinter; root = tkinter.Tk(); root.destroy()"]
    subprocess.run(cmd, check=True)

    mock_check.assert_called_once()
