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

"""
A Python script to download Python interpreter for the solution.
Platform      : Windows, Linux
"""

########################################################################################################################
# Imports
########################################################################################################################
from html.parser import HTMLParser
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import zipfile

from packaging.version import Version, parse
import requests

from ansys.saf.desktop.installer._common.utils import safe_extract

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ANSI styling for terminal output (bold yellow for warnings)
ANSI_BOLD_YELLOW = "\033[1;33m"
ANSI_RESET = "\033[0m"

NUGET_VERSIONS_URL = "https://api.nuget.org/v3-flatcontainer/python/index.json"
PYTHON_VERSION_INDEX = "https://www.python.org/ftp/python"
OFFICIAL_VERSIONS_URLS = ["https://www.python.org/api/v2/downloads/release/", PYTHON_VERSION_INDEX]
# The following minimum required versions were added to avoid shipping python interpreters with the following
# known setuptools vulnerabilities:
# https://github.com/advisories/GHSA-cx63-2mw6-8hw5
# https://github.com/advisories/GHSA-5rjg-fvgr-3xxf
# It is not planned to keep up to date following all python vulnerabilities.
MINIMUM_REQUIRED_VERSIONS = {
    (3, 11): parse("3.11.14"),
    (3, 12): parse("3.12.0"),
    (3, 13): parse("3.13.0"),
    (3, 14): parse("3.14.0"),
}


class PythonIndexHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._versions: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attrs_dict = dict(attrs)
        if tag == "a" and "href" in attrs_dict:
            href = attrs_dict["href"]
            if href is not None and href.endswith("/") and href.count(".") == 2 and len(href) > 5:
                self._versions.append(href[:-1])

    @property
    def versions(self) -> list[str]:
        return self._versions


class PythonManager:
    """Python interpreter download class."""

    def __init__(
        self,
        solution_folder: Path,
        python_version: str,
        ignore_minimum_version: bool,
        force_python_from_source: bool,
    ) -> None:
        """Initialize PythonInterpreter class."""
        self._python_version = self._resolve_python_version(python_version, ignore_minimum_version)
        self._third_party_folder = solution_folder / "third_party"
        self._python_dir = self._third_party_folder / "python"
        self._force_python_from_source = force_python_from_source

    @classmethod
    def _get_available_python_versions(cls, versions_urls: list[str]) -> list[str]:

        response_errors: list[str] = []

        for versions_url in versions_urls:
            response = requests.get(versions_url)  # noqa: S113

            if response.status_code == 200:
                if versions_url == PYTHON_VERSION_INDEX:
                    parser = PythonIndexHTMLParser()
                    parser.feed(response.text)
                    versions = parser.versions
                else:
                    version_metadata = response.json()
                    if isinstance(version_metadata, dict):
                        # Nuget returns a dictionary containing the list of versions
                        versions: list[str] = response.json()["versions"]
                    elif isinstance(version_metadata, list):
                        # The official python API returns a list of dictionaries corresponding to the different versions
                        versions: list[str] = [version["name"].split(" ")[-1] for version in response.json()]
                    else:
                        raise RuntimeError(f"Unexpected version metadata: {version_metadata}")

                available_versions: list[str] = []
                for version in versions:
                    if version.startswith(("3.11", "3.12", "3.13", "3.14")):
                        available_versions.append(version)

                return available_versions
            else:
                response_errors.append(f"{versions_url}: {response.status_code} {response.content}")
        raise RuntimeError("Failed to retrieve Python versions: " + ", ".join(response_errors))

    def _is_strict_three_part_version(self, version: str) -> bool:
        parts = version.split(".")
        if len(parts) != 3:
            return False
        return all(part.isdigit() for part in parts)

    def _resolve_python_version(self, python_version: str, ignore_minimum_version: bool) -> str:
        """
        Find the best suitable python version.
        :return: Python version string.
        :rtype: str
        """
        selected_version: Version = parse(python_version)
        official_available_versions = self._get_available_python_versions(OFFICIAL_VERSIONS_URLS)

        if len(selected_version.release) > 3:
            raise ValueError(
                f"Unexpected python version: {selected_version}. "
                "Accepted python version can have values up to the patch version.",
            )

        if len(selected_version.release) == 3:
            major_minor_key = selected_version.release[:2]
            minimum_required_version = MINIMUM_REQUIRED_VERSIONS[major_minor_key]
            if python_version not in official_available_versions:
                raise ValueError(
                    f"The selected python version: {selected_version}, "
                    f"is not among the available python versions: {official_available_versions}.",
                )
            elif selected_version < minimum_required_version and not ignore_minimum_version:
                logger.warning(
                    f"{ANSI_BOLD_YELLOW}"
                    f"The selected python version: {selected_version} is lower than the minimum required "
                    f"python version: {minimum_required_version} for the major.minor version: {major_minor_key}. "
                    "Proceeding to find the highest available patch version."
                    f"{ANSI_RESET}",
                )
                selected_version = parse(".".join(map(str, major_minor_key)))
            else:
                return python_version

        # If the version contains only a major value, only major and minor values, or is lower than the minimum
        # required version, find the highest patch version available.
        length_selected_version = len(selected_version.release)
        parsed_available_versions = [parse(v) for v in official_available_versions]
        try:
            highest_version = max(
                [
                    v
                    for v in parsed_available_versions
                    if selected_version.release[:length_selected_version] == v.release[:length_selected_version]
                    and self._is_strict_three_part_version(str(v))
                ],
            )
        except ValueError as e:
            raise ValueError(f"No available python version for python {selected_version}") from e

        logger.info(
            f"Selected python version {highest_version} among the available versions for python {selected_version}.",
        )
        return str(highest_version)

    def _extract_python_interpreter(self, downloaded_python_path: Path) -> None:
        """Extract python interpreter."""
        logger.info(f"Extracting python source code to {self._python_dir}")
        self._python_dir.mkdir()
        with zipfile.ZipFile(downloaded_python_path, "r") as python_zip:
            safe_extract(python_zip, self._python_dir)
        downloaded_python_path.unlink()

    def _check_if_python_is_installed(self) -> bool:
        """Check if a python interpreter is already installed."""
        python_exec = self._get_downloaded_python_exec()

        if not python_exec:
            return False

        if platform.system() == "Windows":
            pythonw_exec = python_exec.parent / "pythonw.exe"
            if not pythonw_exec.is_file():
                return False

        if python_exec.is_file():
            cmd = [python_exec, "--version"]
            try:
                output = subprocess.check_output(cmd, text=True).strip()
            except Exception:
                return False
            if self._python_version != output.split(" ")[-1]:
                return False
        else:
            return False

        return True

    def _download_python_interpreter(self) -> Path:
        """Download python interpreter to solution folder."""
        self._third_party_folder.mkdir(parents=True, exist_ok=True)
        nuget_available_versions = self._get_available_python_versions([NUGET_VERSIONS_URL])
        if (
            platform.system() == "Windows"
            and self._python_version in nuget_available_versions
            and not self._force_python_from_source
        ):
            url = f"https://www.nuget.org/api/v2/package/python/{self._python_version}"
            downloaded_python_path = self._third_party_folder / f"python-{self._python_version}.zip"
        else:
            if self._python_version in nuget_available_versions and self._force_python_from_source:
                logger.info(
                    f"The python version {self._python_version} is available as a NuGet package, but it will be built "
                    "from source code because the --force-python-from-source flag was used.",
                )
            url = f"https://www.python.org/ftp/python/{self._python_version}/Python-{self._python_version}.tgz"
            downloaded_python_path = self._third_party_folder / f"python-{self._python_version}.tgz"

        logger.info(f"Downloading python {self._python_version} from {url}")
        response: requests.Response = requests.get(url)  # noqa: S113
        if not response.ok:
            raise RuntimeError(
                f"Could not downloaded python version: {self._python_version}. "
                f"Response: {response.status_code} {response.text}",
            )

        logger.info(f"Writing python interpreter to {self._third_party_folder}")
        with downloaded_python_path.open("wb") as file:
            file.write(response.content)
        return downloaded_python_path

    def _install_python_interpreter_from_source_code_on_linux(self, source_code_dir_path: Path):
        logger.info("Installing necessary dependencies to build python from source code")
        cmd = ["sudo", "apt", "update"]
        subprocess.run(cmd, check=True)
        dependencies = [
            "build-essential",
            "checkinstall",
            "zlib1g-dev",
            "libssl-dev",
            "libreadline-dev",
            "libbz2-dev",
            "libsqlite3-dev",
            "libncursesw5-dev",
            "libffi-dev",
            "liblzma-dev",
            "tk-dev",
            "tcl-dev",
        ]
        cmd = ["sudo", "apt", "install", "-y"] + dependencies
        subprocess.run(cmd, check=True)

        logger.info("Configure python build and install")
        cmd = ["./configure", "--prefix", str(self._python_dir), "--enable-optimizations"]
        subprocess.run(cmd, cwd=source_code_dir_path, check=True)
        nproc = os.cpu_count() or 1
        cmd = ["make", f"-j{nproc}"]
        subprocess.run(cmd, cwd=source_code_dir_path, check=True)
        cmd = ["make", "install"]
        subprocess.run(cmd, cwd=source_code_dir_path, check=True)

    def _install_python_interpreter_from_source_code_on_windows(self, source_code_dir_path: Path):
        logger.info("Building python from source")
        try:
            # Set the NUGET_URL environment variable to download nuget.exe during the build process
            # This is necessary because the default URL for nuget.exe may not be accessible in some environments.
            build_env = os.environ.copy()
            build_env["NUGET_URL"] = "https://dist.nuget.org/win-x86-commandline/latest/nuget.exe"
            cmd = ["cmd", "/c", "PCBuild\\build.bat", "-e"]
            subprocess.run(cmd, cwd=source_code_dir_path, capture_output=True, check=True, text=True, env=build_env)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Building Python from source code failed. "
                f"Make sure Visual Studio Build Tools are installed:\n{e.stdout}",
            ) from e
        cmd = ["cmd", "/c", "python.bat", "PC\\layout", "--preset-default", "--copy", str(self._python_dir)]
        subprocess.run(cmd, cwd=source_code_dir_path, capture_output=True, check=True, text=True)

    def _install_python_interpreter_from_source_code(self, downloaded_python_path: Path):
        source_code_dir_name = downloaded_python_path.name.replace(".tgz", "").capitalize()
        source_code_dir_path = downloaded_python_path.parent / source_code_dir_name

        logger.info(f"Extracting python source code to {source_code_dir_path}")
        with tarfile.open(downloaded_python_path, "r") as python_tar:
            safe_extract(python_tar, source_code_dir_path.parent)

        self._python_dir.mkdir()
        if platform.system() == "Windows":
            self._install_python_interpreter_from_source_code_on_windows(source_code_dir_path)
        elif platform.system() == "Linux":
            self._install_python_interpreter_from_source_code_on_linux(source_code_dir_path)
        else:
            raise ValueError("Unsupported operating system.")

        downloaded_python_path.unlink(missing_ok=True)
        if source_code_dir_path.is_dir():
            try:
                shutil.rmtree(source_code_dir_path)
            except Exception as e:
                logger.warning(f"Could not remove python source code directory {source_code_dir_path}: {e}")

    def _install_python_interpreter(self, downloaded_python_path: Path):
        if self._python_dir.is_dir():
            logger.info(f"Cleaning python directory {self._python_dir}")
            shutil.rmtree(self._python_dir)

        if platform.system() == "Windows" and downloaded_python_path.suffix == ".zip":
            self._extract_python_interpreter(downloaded_python_path)
        else:
            self._install_python_interpreter_from_source_code(downloaded_python_path)

    def _get_downloaded_python_exec(self) -> Path | None:
        if platform.system() == "Windows":
            # python built from source code
            if (python_exec := self._python_dir / "python.exe").is_file():
                return python_exec
            # python extracted from nuget package
            if (python_exec := self._python_dir / "tools" / "python.exe").is_file():
                return python_exec
            return None
        elif platform.system() == "Linux":
            python_exec = self._python_dir / "bin" / "python3"
            return python_exec if python_exec.is_file() else None
        else:
            raise RuntimeError("Unsupported operating system")

    def setup_python_interpreter(self) -> tuple[Path, str]:
        if not self._check_if_python_is_installed():
            logger.info(f"Setting up python version {self._python_version}.")
            downloaded_python_path = self._download_python_interpreter()
            self._install_python_interpreter(downloaded_python_path)
        else:
            logger.info(f"Python version {self._python_version} found under {self._python_dir}. Skipping download.")
        if python_exec := self._get_downloaded_python_exec():
            return python_exec, self._python_version
        else:
            raise RuntimeError("Could not find the downloaded Python executable.")
