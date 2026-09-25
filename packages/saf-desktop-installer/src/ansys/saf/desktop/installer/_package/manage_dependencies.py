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
A Python script to download dependencies from a pyproject.toml.
Platform      : OS independent
"""

import logging
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from packaging.version import Version
import toml

from ansys.saf.desktop.installer._common.utils import (
    modify_solution_wheel_metadata,
    simplify_wheel_dependency_constraints,
)
from ansys.saf.desktop.installer._package.config import InstallerConfig
from ansys.saf.desktop.installer._package.download_python import PythonManager
from ansys.saf.desktop.installer._package.solution import create_requirements_txt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

########################################################################################################################
# Variables
########################################################################################################################
# root dir is where this script was executed from using the command line
WHL_CONSTANT = "*.whl"
REQ_FILE = "requirements.txt"
ENCRYPTED_FILE_SUFFIX = ".encrypted"


########################################################################################################################
# Functions
########################################################################################################################


def _check_readme_file_from_pyproject(pyproject_location: Path) -> Path:
    """Get the readme file dynamically from the pyproject.toml file.

    Args:
        pyproject_location (Path): Path to the pyproject.toml file.
    """
    pyproject_toml_content = toml.load(pyproject_location)
    pyproject_readme_value = pyproject_toml_content.get("tool", {}).get("poetry", {}).get("readme")

    if not pyproject_readme_value:
        raise ValueError(f"No readme file specified in {pyproject_location}.")

    if not isinstance(pyproject_readme_value, str):
        raise TypeError(f"The readme field in {pyproject_location} is not a string.")

    readme_file = Path(pyproject_location.parent / pyproject_readme_value)
    if not readme_file.is_file():
        raise FileNotFoundError(f"The readme file {readme_file} does not exist.")

    return readme_file


def build_wheel_using_poetry(definitions_folder: Path, solution_root_dir: Path) -> None:
    """Build wheel using poetry.

    Args:
        definitions_folder (Path): Path to the definitions folder.
        solution_root_dir (Path): Path to the solution root directory.
    """
    solution_dist_dir = solution_root_dir / "dist"
    logger.info(f"Building wheel using poetry in {solution_dist_dir}")
    _check_readme_file_from_pyproject(solution_root_dir / "pyproject.toml")
    try:
        subprocess.check_output(
            ["poetry", "build", "--no-interaction"],  # noqa: S607
            cwd=solution_root_dir,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to build wheel using poetry: {e.output}") from e
    project_wheel = next(solution_dist_dir.glob(WHL_CONSTANT), None)
    if not project_wheel or not project_wheel.is_file():
        raise FileNotFoundError(f"Wheel file not found in {solution_dist_dir} after building with poetry.")
    logger.info(f"Wheel built successfully: {project_wheel.name}")
    logger.info(f"Copying {project_wheel.name} to {definitions_folder}")
    shutil.copy(project_wheel, definitions_folder / project_wheel.name)
    solution_package_name, solution_version = str(project_wheel.name).split("-")[:2]
    modify_solution_wheel_metadata(definitions_folder, solution_package_name, solution_version)


def obfuscate_solution(definitions_folder: Path, venv_python_exec: Path) -> None:
    """Obfuscate solution and internal dependencies.

    Args:
        definitions_folder (Path): Path to the definitions folder
    """
    logger.info(f"Obfuscating solution and internal dependencies in {definitions_folder}")
    for wheel in definitions_folder.glob(WHL_CONSTANT):
        logger.info(f"Obfuscating {wheel}")
        try:
            subprocess.check_output(
                [venv_python_exec, "-m", "pyc_wheel", str(wheel)],
                text=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to obfuscate wheel {wheel}: {e.output}") from e
    logger.info("Obfuscation complete.")


def encrypt_solution(encryption_file: Path, root: Path, encryption_key: str | None = None) -> None:
    """Encrypt solution and internal dependencies.

    Args:
        encryption_file (Path): File containing paths to encrypt.
        root (Path): Root directory for the paths in the encryption file.
        encryption_key (str or None): Key to encrypt the solution and internal dependencies. If None, keyless mode
                                      is used.
    """
    logger.info(f"Encrypting solution and internal dependencies (keyless mode: {encryption_key is None})")
    if encryption_file.as_posix() == "":
        raise ValueError("Must provide a file containing paths to encrypt.")
    if not encryption_file.exists():
        raise FileNotFoundError(f"Could not find file {encryption_file}. Make sure the file exists.")
    from ansys.translation_utilities.translator import c  # type: ignore

    c(encryption_file, key=encryption_key, root=root)


def download_module(
    module_name: str,
    module_version: str,
    index_url: str,
    module_directory: Path,
    venv_python_exec: Path,
    certificate: str | None = None,
):
    """Download a module from the ANSYS internal PyPI server.

    Args:
        module_name (str): Name of the module to download.
        module_version (str): Version of the module to download.
        index_url (str): URL of the ANSYS internal PyPI server.
        module_directory (Path): Directory to download
        certificate (str): path to the certificate authority file.
    """
    logger.info(f"Downloading {module_name}==={module_version} from {index_url} to {module_directory}.")
    command = [
        venv_python_exec,
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--no-deps",
        "--index-url",
        index_url,
        "--dest",
        module_directory,
        f"{module_name}==={module_version}",  # Using === to force exact version match
    ]
    if certificate:
        command.extend(["--cert", certificate])
    subprocess.check_output(
        command,
        text=True,
    )


def download_tool(tool: str, definitions_folder: Path, venv_python_exec: Path) -> None:
    logger.info(f"downloading {tool}")
    tools_directory = definitions_folder / "tools"
    tool_directory = tools_directory / tool
    tool_directory.mkdir(parents=True, exist_ok=True)
    requirements_file_path = tools_directory / f"{tool}_requirements.txt"

    if not requirements_file_path.is_file():
        raise RuntimeError(f"unable to find requirements file for {tool} at {requirements_file_path}")

    subprocess.run(
        [venv_python_exec, "-m", "pip", "download", "--disable-pip-version-check", "-r", requirements_file_path],
        cwd=tool_directory,
        check=True,
    )
    requirements = "\n".join(f"./{tool}/{wheel.name}" for wheel in tool_directory.glob(WHL_CONSTANT))
    requirements_file_path.write_text(requirements)


def copy_module(module_location: Path, module_directory: Path):
    """Copy a module from a location to a directory.

    Args:
        module_location (Path): Location of the module to copy.
        module_directory (Path): Directory to copy the module to.
    """
    print(f"Copying {module_location} to {module_directory}.")
    shutil.copy(module_location, module_directory)


def download_git_source(
    package: dict[str, Any],
    module_directory: Path,
    venv_python_exec: Path,
    github_token: str | None = None,
) -> None:
    """Download a git source package."""
    if not github_token:
        raise ValueError(
            "Must provide a GitHub token to download dependencies from GitHub."
            " Set the ANSYS_GITHUB_PAT environment variable or"
            " provide the GitHub token as a command line argument --github-token.",
        )

    index_url = package["source"]["url"]
    source = package["source"]["reference"]

    index_url = index_url.replace("https://", f"https://{github_token}@")
    index_url = f"git+{index_url}@{source}"

    download_module(
        package["name"],
        package["version"],
        index_url,
        module_directory,
        venv_python_exec,
    )


def download_private_package(package: dict[str, Any], module_directory: Path, venv_python_exec: Path) -> None:
    """Download a private package."""
    index_url = package["source"]["url"]
    source = package["source"]["reference"]

    source_name_slug = source.upper().replace("-", "_")
    username = os.environ.get(f"POETRY_HTTP_BASIC_{source_name_slug}_USERNAME", "")
    password = os.environ.get(f"POETRY_HTTP_BASIC_{source_name_slug}_PASSWORD", "")
    certificate = os.environ.get(f"POETRY_CERTIFICATES_{source_name_slug}_CERT", "")
    if not password:
        raise ValueError(f"No token found for private source {source}.")

    prefix = f"{username}:{password}" if username else f"{password}"
    index_url = index_url.replace("https://", f"https://{prefix}@")

    download_module(
        package["name"],
        package["version"],
        index_url,
        module_directory,
        venv_python_exec,
        certificate=certificate,
    )


def handle_file_source(package: dict[str, Any], poetry_lock_file: Path, module_directory: Path) -> None:
    """Handle downloading a package from a file source."""
    package_location = Path(package["source"]["url"])
    if not package_location.exists():
        package_location = poetry_lock_file.parent / package["source"]["url"]
    if not package_location.exists():
        raise FileNotFoundError(
            f"Package location {package_location} does not exist."
            " Make sure the package location in the lock file is correct and the file exists.",
        )
    copy_module(package_location, module_directory)


def has_dependencies_with_wheel_url(package: dict[str, Any]) -> bool:
    """Check if the package has dependencies with wheel URL."""
    dependencies = package.get("dependencies", {})
    for _, dep_info in dependencies.items():
        if (
            isinstance(dep_info, dict)
            and "url" in dep_info
            and isinstance(dep_info["url"], str)
            and dep_info["url"].startswith("http")
            and dep_info["url"].endswith(".whl")
        ):
            return True
    return False


def get_packages_with_wheel_url_deps(poetry_lock_file: Path) -> list[tuple[str, str]]:
    """Get packages with wheel URL dependencies from a poetry.lock file.

    Args:
        poetry_lock_file (Path): Path to the poetry.lock file.

    Returns:
        list[tuple[str, str]]: List of packages with wheel URL dependencies.
            Format: (package_name, package_version).
    """
    lock_file_content = toml.load(poetry_lock_file)
    packages_with_wheel_url_deps: list[tuple[str, str]] = []
    for package in lock_file_content["package"]:
        if has_dependencies_with_wheel_url(package) and package_matches_platform(package):
            packages_with_wheel_url_deps.append((package["name"], package["version"]))

    return packages_with_wheel_url_deps


def download_dependencies(
    poetry_lock_file: Path,
    module_directory: Path,
    venv_python_exec: Path,
    github_token: str | None = None,
) -> None:
    """Download the dependencies listed in a poetry.lock file.

    Args:
        poetry_lock_file (Path): Path to the poetry.lock file.
        module_directory (Path): Directory to download
        venv_python_exec (Path): Path to the Python executable in the virtual environment.
        github_token (str or None): Personal Access Token for downloading dependencies from GitHub.

    Returns:
        list[tuple[str, str]]: List of packages with wheel URL dependencies.
            Format: (package_name, package_version).
    """
    logger.info(f"Downloading dependencies from {poetry_lock_file} to {module_directory}.")
    lock_file_content = toml.load(poetry_lock_file)
    for package in lock_file_content["package"]:
        if (
            package["name"] in ["python"]
            or "source" not in package
            or (
                "groups" in package
                and not any(group in ["desktop", "ui", "doc", "main"] for group in package["groups"])
            )
        ):
            continue
        if package["source"]["type"] == "file" and package_matches_platform(package):
            handle_file_source(package, poetry_lock_file, module_directory)
        # TODO: This may have issues with public .git dependencies
        elif package["source"]["url"].endswith(".git"):
            download_git_source(package, module_directory, venv_python_exec, github_token)
        elif "reference" in package["source"]:
            download_private_package(package, module_directory, venv_python_exec)


def simplify_wheel_url_dependencies(
    packages_with_wheel_url_deps: list[tuple[str, str]],
    module_directory: Path,
) -> None:
    for package_name, package_version in packages_with_wheel_url_deps:
        normalized_name = package_name.replace("-", "_")

        pattern = re.compile(
            rf"^{re.escape(normalized_name)}.*{re.escape(package_version)}.*\.whl$",
            re.IGNORECASE,
        )

        matching_wheels = [wheel for wheel in module_directory.glob(WHL_CONSTANT) if pattern.match(wheel.name)]

        if not matching_wheels:
            raise FileNotFoundError(
                f"Could not find wheel for package {package_name}=={package_version} "
                "with wheel URL dependencies in the downloaded modules.",
            )
        if len(matching_wheels) > 1:
            raise RuntimeError(f"Multiple wheels found for package {package_name}=={package_version} ")
        wheel_path = matching_wheels[0]
        simplify_wheel_dependency_constraints(wheel_path)


def download_internal_dependencies(
    solution_root_dir: Path,
    solution_module_name: str,
    solution_display_name: str,
    pyproject_location: Path,
    venv_python_exec: Path,
    github_token: str | None = None,
) -> None:
    """Download internal dependencies from Solutions PyPI repository.

    Args:
        solution_display_name (str): Display name of the solution.
        pyproject_location (Path): Path to the pyproject.toml file.
        github_token (str): Personal Access Token for downloading dependencies from GitHub.
    """
    logger.info(f"Downloading internal dependencies from Solutions PyPI for {solution_display_name} solution")
    definitions_folder: Path = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name
    definitions_folder.mkdir(parents=True, exist_ok=True)

    download_dependencies(
        pyproject_location.with_name("poetry.lock"),
        definitions_folder,
        venv_python_exec,
        github_token=github_token,
    )


def download_external_dependencies(
    definitions_folder: Path,
    pyproject_location: Path,
    venv_python_exec: Path,
    python_version: str,
) -> None:
    """Download external dependencies from PyPI repository.

    Args:
        definitions_folder (Path): Path to the definitions folder.
        pyproject_location (Path): Path to the pyproject.toml file.
    """
    download_tool("pip", definitions_folder, venv_python_exec)
    download_tool("poetry", definitions_folder, venv_python_exec)
    temporary_requirements = create_requirements_txt(pyproject_location, definitions_folder)
    logger.info(f"Downloading solution's external dependencies with python version {python_version}")
    try:
        subprocess.check_output(
            [
                venv_python_exec,
                "-m",
                "pip",
                "download",
                "--disable-pip-version-check",
                "-r",
                str(temporary_requirements.absolute()),
            ],
            cwd=definitions_folder,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to download external dependencies: {e.output}") from e
    temporary_requirements.unlink()


def package_matches_platform(package: dict[str, Any]) -> bool:
    """Check if the package matches the current platform."""
    if "source" not in package:
        return True
    package_platform = package["source"]["url"].split("-")[-1]
    return (
        sys.platform.startswith("win")
        and "win" in package_platform
        or sys.platform.startswith("linux")
        and "linux" in package_platform
        or "win" not in package_platform
        and "linux" not in package_platform
    )


def get_definitions_folder(solution_root_dir: Path, solution_module_name: str) -> Path:
    definitions_folder = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name
    definitions_folder.mkdir(parents=True, exist_ok=True)
    return definitions_folder


def _parse_files_file_path(files_file_path: Path) -> list[str]:
    if not files_file_path.is_file():
        raise FileNotFoundError(f"Could not find file {files_file_path}. Make sure the file exists.")
    file_paths: list[str] = []
    for file in files_file_path.read_text().splitlines():
        file_str = file.strip().replace("\\", "/")
        if not file_str:
            continue
        file_paths.append(file_str)
    return file_paths


def delete_encrypted_files(source_dir: Path, files_file_path: Path) -> None:
    for file_str in _parse_files_file_path(files_file_path):
        source_file = (source_dir / file_str).resolve()
        encrypted_file = source_file.with_suffix(source_file.suffix + ENCRYPTED_FILE_SUFFIX)
        if encrypted_file.is_file():
            encrypted_file.unlink()


def copy_files(source_dir: Path, target_dir: Path, files_file_path: Path):
    for file_str in _parse_files_file_path(files_file_path):
        source_file = (source_dir / file_str).resolve()
        if not source_file.exists():
            raise FileNotFoundError(f"When making temporary copy source File {source_file} does not exist.")
        target_file = (target_dir / file_str).resolve()
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_file, target_file)


def add_wheels(
    definitions_folder: Path,
    venv_python_exec: Path,
    solution_root_dir: Path,
    solution_module_name: str,
    solution_display_name: str,
    installer_config: InstallerConfig,
    python_version: str,
) -> None:
    logger.info("Adding dependencies to solution folder and optionally obfuscating them.")
    if installer_config.encrypt:
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp_dir_path = Path(tmpdirname)
            try:
                logger.info(f"Copying decrypt files to temporary directory: {tmpdirname}")
                copy_files(solution_root_dir, tmp_dir_path, installer_config.encryption_file)
                logger.info("encrypting files in copy of solution")
                # c() within encrypt_solution() has the side effect of deleting the original files after
                # encryption, hence the temporary storage. Note that we are not encrypting the copied files in the
                # temporary directory, we are encrypting the original files in solution_root_dir. That's why we copy
                # them back afterwards.
                encrypt_solution(installer_config.encryption_file, solution_root_dir, installer_config.encryption_key)
                logger.info("building solution wheel")
                build_wheel_using_poetry(definitions_folder, solution_root_dir)
            finally:
                # Copy back the original files to solution_root_dir so future builds are not affected by the encryption
                # of the current build.
                logger.info(f"Copying decrypt files back to source tree: {solution_root_dir}")
                copy_files(tmp_dir_path, solution_root_dir, installer_config.encryption_file)
                # Clean up the encrypted files created during encryption to avoid source tree pollution
                logger.info("Removing encrypted files created during encryption")
                delete_encrypted_files(solution_root_dir, installer_config.encryption_file)
    else:
        logger.info("building solution wheel")
        build_wheel_using_poetry(definitions_folder, solution_root_dir)
    packages_with_wheel_url_deps = get_packages_with_wheel_url_deps(
        installer_config.pyproject_location.with_name("poetry.lock"),
    )
    download_internal_dependencies(
        solution_root_dir,
        solution_module_name,
        solution_display_name,
        installer_config.pyproject_location,
        venv_python_exec,
        github_token=installer_config.github_token,
    )
    if installer_config.obfuscate:
        obfuscate_solution(definitions_folder, venv_python_exec)
    if installer_config.offline_package:
        download_external_dependencies(
            definitions_folder,
            installer_config.pyproject_location,
            venv_python_exec,
            python_version,
        )
        convert_tar_gz_files_to_wheels(definitions_folder, venv_python_exec)
        simplify_wheel_url_dependencies(packages_with_wheel_url_deps, definitions_folder)


def convert_tar_gz_files_to_wheels(definitions_folder: Path, venv_python_exec: Path) -> None:
    # pip download gets .tar.gz files instead of wheels for some packages. Since a subset of these
    # are not installable offline so we convert them to wheels here. Use a temporary directory here
    # because the wheel command downloads wheels as a side effect
    temp_dir = definitions_folder / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    for tar in definitions_folder.glob("*.tar.gz"):
        logger.info(f"converting {tar} into wheel")
        try:
            subprocess.check_output(
                [
                    venv_python_exec,
                    "-m",
                    "pip",
                    "wheel",
                    "--disable-pip-version-check",
                    tar,
                ],
                cwd=temp_dir,
                text=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to convert {tar} into wheel: {e.output}") from e
        # package name sometimes is not the same in .tar.gz and .whl files. Dashes might be replaced by underscores
        # or vice versa.
        package_and_version = tar.name[: -(len(".tar.gz"))]
        pattern = re.compile(rf"^{package_and_version.replace('-', '[-_]')}-.*\.whl$")
        matches = [wf for wf in temp_dir.glob("*.whl") if pattern.match(wf.name)]
        wheel = matches[0]
        if not wheel.is_file():
            raise FileNotFoundError(f"expected wheel file {wheel} not found")
        shutil.move(wheel, definitions_folder)
        # remove the tar files so we don't redundantly add them to the installer
        logger.info(f"converted {tar} into wheel")
        logger.info(f"removing {tar}")
        tar.unlink()
    shutil.rmtree(temp_dir)


def merge_group_dependencies(
    groups: list[str],
    poetry: dict[str, Any],
    dependencies: dict[str, Any],
) -> None:
    """Merge group dependencies into the main dependencies dictionary."""
    for group in groups:
        group_dependencies: dict[str, Any] = poetry.get("group", {}).get(group, {}).get("dependencies", {})
        for package, info in group_dependencies.items():
            package = package.replace("_", "-")
            if package not in dependencies:
                dependencies[package] = info
            elif isinstance(info, dict) and info.get("extras"):  # type: ignore[reportUnknownMemberType]
                if isinstance(dependencies[package], str):
                    dependencies[package] = {"version": dependencies[package]}
                if isinstance(dependencies[package], dict):
                    extras = dependencies[package].setdefault("extras", [])
                    extras.extend(extra for extra in info["extras"] if extra not in extras)  # type: ignore[reportUnknownVariableType]


def add_poetry_project(
    venv_python_exec: Path,
    pyproject_location: Path,
    definitions_folder: Path,
    python_version: str,
) -> None:

    logger.info("creating poetry project for install")
    project_file = definitions_folder / "pyproject.toml"
    shutil.copy(pyproject_location, project_file)
    project = toml.load(project_file)
    poetry = project["tool"]["poetry"]
    poetry["name"] = "project"
    dependencies: dict[str, Any] = poetry["dependencies"]

    for wheel in definitions_folder.glob(WHL_CONSTANT):
        package = wheel.stem.split("-")[0].replace("_", "-")
        dependencies[package] = {"path": f"./{wheel.name}"}

    merge_group_dependencies(["desktop", "ui", "doc"], poetry, dependencies)

    # In already existing solutions, ansys-saf-desktop-installer might still be included among the "desktop"
    # dependencies. If that is the case, we exclude it from the pyproject along with pyinstaller, which is
    # also included in the dependencies dictionary when using the offline package option.
    dependencies.pop("ansys-saf-desktop-installer", None)
    dependencies.pop("pyinstaller", None)

    if "group" in poetry:
        del poetry["group"]

    # Replace lowest python version with the one passed with --python-version option.
    # This is necessary to avoid errors during the poetry lock below, as some of the
    # downloaded external dependencies might not support the minimum python version limit.
    dependencies["python"] = dependencies["python"].replace("3.11", python_version)

    with project_file.open("w") as f:
        toml.dump(project, f)

    lock_location = pyproject_location.with_name("poetry.lock")
    if lock_location.is_file():
        shutil.copy(lock_location, definitions_folder / "poetry.lock")
    try:
        subprocess.check_output(
            [str(venv_python_exec), "-m", "poetry", "lock"],
            cwd=definitions_folder,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "VIRTUAL_ENV": venv_python_exec.parent.parent.as_posix()},
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to lock poetry project: {e.stderr}") from e


def add_tools_requirements(solution_root_dir: Path, solution_module_name: str, venv_python_exec: Path) -> None:
    definitions_folder = get_definitions_folder(solution_root_dir, solution_module_name)
    project_file_path = solution_root_dir / "pyproject.toml"
    project = toml.load(project_file_path)

    tools_directory = definitions_folder / "tools"
    tools_directory.mkdir(parents=True, exist_ok=True)
    logger.info(f"Adding requirements files for pip and poetry to {tools_directory}")

    pip_version_information = subprocess.check_output(
        [venv_python_exec, "-m", "pip", "--disable-pip-version-check", "--version"],
        text=True,
    )
    pip_version = pip_version_information.split()[1]

    if "build-system-requirements" not in project:
        raise KeyError(f"build-system-requirements key not found in {project_file_path}.")

    build_system_requirements = project["build-system-requirements"]

    if "build-system-version" not in build_system_requirements:
        raise KeyError(
            f"build-system-version key not found in build-system-requirements section in {project_file_path}.",
        )

    poetry_version = build_system_requirements["build-system-version"]

    (tools_directory / "pip_requirements.txt").write_text(f"pip=={pip_version}")
    poetry_reqs = f"poetry=={poetry_version}"
    if Version(poetry_version) >= Version("2.0.0"):
        poetry_reqs += "\npoetry-plugin-export>=1.8"
    (tools_directory / "poetry_requirements.txt").write_text(poetry_reqs)


def download_embeddable_python(solution_folder: Path, installer_config: InstallerConfig) -> tuple[Path, str]:
    # We always download python because we need it at least for the poetry lock command in the definitions folder
    python_manager = PythonManager(
        solution_folder,
        installer_config.python_version,
        installer_config.exclude_python,
        installer_config.force_python_from_source,
    )
    downloaded_python_exec, python_version = python_manager.setup_python_interpreter()
    return downloaded_python_exec, python_version


def _get_venv_python_exec(venv_folder: Path) -> Path:
    if platform.system() == "Windows":
        return venv_folder / "Scripts" / "python.exe"
    elif platform.system() == "Linux":
        return venv_folder / "bin" / "python"
    else:
        raise RuntimeError("Unsupported operating system")


def create_venv_in_definitions_folder(definitions_folder: Path, downloaded_python_exec: Path) -> tuple[Path, Path]:
    definitions_venv = definitions_folder / ".venv"
    logger.info(f"Creating virtual environment in {definitions_venv} using Python executable {downloaded_python_exec}")
    try:
        subprocess.check_output(
            [
                str(downloaded_python_exec),
                "-m",
                "venv",
                str(definitions_venv),
            ],
            text=True,
            stderr=subprocess.STDOUT,
        )
        venv_python_exec = _get_venv_python_exec(definitions_venv)
        subprocess.check_output(
            [str(venv_python_exec), "-m", "pip", "install", "wheel", "poetry", "setuptools", "pyc-wheel"],
            text=True,
            stderr=subprocess.STDOUT,
        )
        return definitions_venv, venv_python_exec
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to create virtual environment to download external dependencies: {e.output}",
        ) from e
