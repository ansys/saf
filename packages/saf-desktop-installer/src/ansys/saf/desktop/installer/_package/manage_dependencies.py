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

from contextlib import suppress
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename
from packaging.version import Version
import toml

from ansys.saf.desktop.installer._common.utils import (
    modify_solution_wheel_metadata,
    simplify_wheel_dependency_constraints,
)
from ansys.saf.desktop.installer._package.backend_detection import SolutionBackend, detect_solution_backend
from ansys.saf.desktop.installer._package.config import InstallerConfig
from ansys.saf.desktop.installer._package.download_python import PythonManager
from ansys.saf.desktop.installer._package.solution import (
    create_poetry_requirements_txt,
    get_solution_package_name,
    get_solution_version,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


########################################################################################################################
# Variables
########################################################################################################################
# root dir is where this script was executed from using the command line
WHL_CONSTANT = "*.whl"
REQ_FILE = "requirements.txt"
ENCRYPTED_FILE_SUFFIX = ".encrypted"
LOCK_PATH_DEPENDENCY_PATTERN = re.compile(r'(\bpath\s*=\s*)("(?:[^"\\\r\n]|\\.)*")')


########################################################################################################################
# Functions
########################################################################################################################


def _check_poetry_readme_file_from_pyproject(pyproject_location: Path) -> Path:
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


def build_solution_wheel(definitions_folder: Path, solution_root_dir: Path) -> None:
    """Build the solution wheel with its configured backend.

    Args:
        definitions_folder (Path): Path to the definitions folder.
        solution_root_dir (Path): Path to the solution root directory.
    """
    solution_dist_dir = solution_root_dir / "dist"
    backend_info = detect_solution_backend(solution_root_dir)
    if backend_info.backend is SolutionBackend.POETRY:
        _check_poetry_readme_file_from_pyproject(solution_root_dir / "pyproject.toml")
        command = ["poetry", "build", "--no-interaction"]
    else:
        command = ["uv", "build"]

    logger.info(f"Building wheel using {backend_info.backend} in {solution_dist_dir}")
    try:
        subprocess.check_output(
            command,
            cwd=solution_root_dir,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to build wheel using {backend_info.backend}: {e.output}") from e
    project_wheel = next(solution_dist_dir.glob(WHL_CONSTANT), None)
    if not project_wheel or not project_wheel.is_file():
        raise FileNotFoundError(
            f"Wheel file not found in {solution_dist_dir} after building with {backend_info.backend}."
        )
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
    wheels = list(definitions_folder.glob(WHL_CONSTANT))
    wheelhouse = definitions_folder / "wheelhouse"
    if wheelhouse.is_dir():
        wheels.extend(wheelhouse.glob(WHL_CONSTANT))
    for wheel in wheels:
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


def download_pypi_package_with_pip(
    package_name: str,
    package_version: str,
    index_url: str,
    package_directory: Path,
    venv_python_exec: Path,
    certificate: str | None = None,
):
    """Download an exact package version from the configured package index using pip.

    Args:
        package_name (str): Name of the package to download.
        package_version (str): Version of the package to download.
        index_url (str): URL of the package index.
        package_directory (Path): Directory where the downloaded package is saved.
        venv_python_exec (Path): Python executable to run pip from.
        certificate (str | None): Path to the certificate authority file.
    """
    logger.info(f"Downloading {package_name}==={package_version} to {package_directory}.")
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
        package_directory,
        f"{package_name}==={package_version}",  # Using === to force exact version match
    ]
    if certificate:
        command.extend(["--cert", certificate])
    subprocess.check_output(
        command,
        text=True,
    )


def download_build_tool_with_pip(tool: str, definitions_folder: Path, venv_python_exec: Path) -> None:
    logger.info(f"Downloading {tool} build-tool wheels with pip.")
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


def _github_url_with_token(url: str, github_token: str | None, *, required: bool = True) -> str:
    if not github_token:
        if required:
            raise ValueError(
                "Must provide a GitHub token to download dependencies from GitHub."
                " Set the ANSYS_GITHUB_PAT environment variable or"
                " provide the GitHub token as a command line argument --github-token.",
            )
        return url
    if url.startswith("https://"):
        return url.replace("https://", f"https://{quote(github_token, safe='')}@", 1)
    return url


def _download_poetry_git_source(
    package: dict[str, Any],
    package_directory: Path,
    venv_python_exec: Path,
    github_token: str | None = None,
) -> None:
    """Build a locked Git dependency wheel with optional token authentication."""
    source = package["source"]
    url = _github_url_with_token(source["url"], github_token, required=False)
    revision = source.get("resolved_reference") or source["reference"]
    requirement = f"{package['name']} @ git+{url}@{revision}"

    logger.info(f"Downloading Git dependency {package['name']} to {package_directory}.")
    subprocess.check_output(
        [
            venv_python_exec,
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--wheel-dir",
            package_directory,
            requirement,
        ],
        text=True,
    )


def _download_poetry_private_dependency(
    package: dict[str, Any],
    package_directory: Path,
    venv_python_exec: Path,
) -> None:
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

    download_pypi_package_with_pip(
        package["name"],
        package["version"],
        index_url,
        package_directory,
        venv_python_exec,
        certificate=certificate,
    )


def _copy_poetry_file_dependency(package: dict[str, Any], poetry_lock_file: Path, package_directory: Path) -> None:
    """Handle downloading a package from a file source."""
    package_location = Path(package["source"]["url"])
    if not package_location.exists():
        package_location = poetry_lock_file.parent / package["source"]["url"]
    if not package_location.exists():
        raise FileNotFoundError(
            f"Package location {package_location} does not exist."
            " Make sure the package location in the lock file is correct and the file exists.",
        )
    copy_module(package_location, package_directory)


def _has_poetry_wheel_url_dependencies(package: dict[str, Any]) -> bool:
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


def _get_poetry_packages_with_wheel_url_dependencies(poetry_lock_file: Path) -> list[tuple[str, str]]:
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
        if _has_poetry_wheel_url_dependencies(package) and _poetry_package_matches_platform(package):
            packages_with_wheel_url_deps.append((package["name"], package["version"]))

    return packages_with_wheel_url_deps


def _stage_poetry_locked_dependencies(
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
        if package["source"]["type"] == "file" and _poetry_package_matches_platform(package):
            _copy_poetry_file_dependency(package, poetry_lock_file, module_directory)
        elif package["source"]["type"] == "git":
            _download_poetry_git_source(package, module_directory, venv_python_exec, github_token)
        elif "reference" in package["source"]:
            _download_poetry_private_dependency(package, module_directory, venv_python_exec)


def _simplify_poetry_wheel_url_dependencies(
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


def _stage_poetry_internal_dependencies(
    solution_root_dir: Path,
    solution_module_name: str,
    solution_display_name: str,
    pyproject_location: Path,
    venv_python_exec: Path,
    github_token: str | None = None,
) -> None:
    """Stage local, Git, and private dependencies from the solution's Poetry lockfile.

    Args:
        solution_display_name (str): Display name of the solution.
        pyproject_location (Path): Path to the pyproject.toml file.
        github_token (str): Personal Access Token for downloading dependencies from GitHub.
    """
    logger.info(f"Staging Poetry lockfile dependencies for {solution_display_name} solution")
    definitions_folder: Path = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name
    definitions_folder.mkdir(parents=True, exist_ok=True)

    _stage_poetry_locked_dependencies(
        pyproject_location.with_name("poetry.lock"),
        definitions_folder,
        venv_python_exec,
        github_token=github_token,
    )


def export_uv_requirements(solution_root_dir: Path, python_exec: Path, requirements_path: Path) -> Path:
    """Export locked UV dependencies for installation, retaining source paths for later staging."""
    project_file = solution_root_dir / "pyproject.toml"
    lock_file = solution_root_dir / "uv.lock"
    if not lock_file.is_file():
        raise FileNotFoundError(f"UV lockfile not found: {lock_file}")

    with project_file.open("rb") as project:
        configuration = tomllib.load(project)
    groups = configuration.get("dependency-groups", {})
    if not isinstance(groups, dict):
        raise ValueError(f"'dependency-groups' must be a table in '{project_file}'.")

    command = [
        "uv",
        "export",
        "--locked",
        "--no-default-groups",
        "--no-emit-project",
        "--python",
        str(python_exec),
    ]
    for group in ("desktop", "ui", "doc"):
        if group in groups:
            command.extend(["--group", group])

    try:
        result = subprocess.run(command, cwd=solution_root_dir, capture_output=True, check=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"UV dependency export failed: {e.stderr}") from e
    requirements_path.write_text(result.stdout, encoding="utf-8")
    return requirements_path


def _selected_uv_lock_packages(solution_root_dir: Path, requirements_path: Path) -> list[dict[str, Any]]:
    """Select native UV lock entries represented in UV's target-specific requirements export."""
    lock_file = solution_root_dir / "uv.lock"
    with lock_file.open("rb") as source_file:
        lock = tomllib.load(source_file)
    if lock.get("version") != 1:
        raise ValueError(f"Unsupported UV lockfile version in {lock_file}: {lock.get('version')!r}")
    packages = lock.get("package", [])
    if not isinstance(packages, list) or not all(
        isinstance(package, dict) and isinstance(package.get("name"), str) for package in packages
    ):
        raise ValueError(f"Invalid package list in {lock_file}.")

    selected = _selected_uv_requirements(requirements_path)
    return [
        package
        for package in packages
        if (versions := selected.get(canonicalize_name(package["name"]))) is not None
        and (None in versions or package.get("version") in versions)
    ]


def _selected_uv_requirements(requirements_path: Path) -> dict[str, set[str | None]]:
    """Parse names and exact versions from UV's requirements export."""
    selected: dict[str, set[str | None]] = {}
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement_line = line.strip().removesuffix("\\").rstrip()
        if not requirement_line or requirement_line.startswith(("#", "-")):
            continue
        try:
            requirement = Requirement(requirement_line)
        except InvalidRequirement:
            file_package = _uv_file_requirement_package(requirement_line)
            if file_package is None:
                continue
            name, version = file_package
            selected.setdefault(canonicalize_name(name), set()).add(version)
            continue

        exact_versions = {
            specifier.version
            for specifier in requirement.specifier
            if specifier.operator in {"==", "==="} and "*" not in specifier.version
        }
        versions = exact_versions or {None}
        selected.setdefault(canonicalize_name(requirement.name), set()).update(versions)
    return selected


def _uv_file_requirement_package(requirement: str) -> tuple[str, str] | None:
    parsed_url = urlsplit(requirement)
    if parsed_url.scheme != "file":
        return None
    filename = Path(unquote(parsed_url.path)).name
    try:
        name, version, _, _ = parse_wheel_filename(filename)
    except ValueError:
        try:
            name, version = parse_sdist_filename(filename)
        except ValueError:
            return None
    return name, str(version)


def stage_uv_selected_local_dependencies(
    solution_root_dir: Path,
    lock_packages: list[dict[str, Any]],
    wheelhouse: Path,
    python_exec: Path,
    github_token: str | None = None,
) -> None:
    """Build wheels for local and Git UV dependencies, letting pip evaluate target markers."""
    requirements = [
        requirement
        for package in lock_packages
        if (requirement := _uv_staged_requirement(package, solution_root_dir, github_token)) is not None
    ]

    if not requirements:
        return

    wheelhouse.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary_directory:
        requirements_path = Path(temporary_directory) / "local-requirements.txt"
        requirements_path.write_text("\n".join(requirements), encoding="utf-8")
        command = [
            str(python_exec),
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--wheel-dir",
            str(wheelhouse),
            "-r",
            str(requirements_path),
        ]
        try:
            subprocess.run(command, cwd=solution_root_dir, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            message = e.stderr or e.stdout or str(e)
            for secret in (github_token, quote(github_token, safe="") if github_token else None):
                if secret:
                    message = message.replace(secret, "***")
            raise RuntimeError(f"Failed to stage local or Git UV dependencies: {message}") from e


def _uv_staged_requirement(
    package: Any,
    solution_root_dir: Path,
    github_token: str | None,
) -> str | None:
    for requirement in (
        _uv_local_requirement(package, solution_root_dir),
        _uv_archive_requirement(package),
        _uv_git_requirement(package, github_token),
    ):
        if requirement is not None:
            return requirement
    return None


def _uv_archive_requirement(package: Any) -> str | None:
    if not isinstance(package, dict):
        raise ValueError("Invalid package entry in uv.lock.")
    source = package.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("url"), str):
        return None
    name = package.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("Invalid URL package in uv.lock.")
    return _with_uv_marker(f"{name} @ {source['url']}", package)


def _uv_git_requirement(package: Any, github_token: str | None) -> str | None:
    if not isinstance(package, dict):
        raise ValueError("Invalid package entry in uv.lock.")
    source = package.get("source")
    if not isinstance(source, dict) or "git" not in source:
        return None
    name = package.get("name")
    git_source = source["git"]
    if not isinstance(name, str) or not isinstance(git_source, str):
        raise ValueError("Invalid Git dependency in uv.lock.")
    parsed_source = urlsplit(git_source)
    revision, *fragments = parsed_source.fragment.split("&")
    if not revision:
        raise ValueError("Missing locked Git revision in uv.lock.")
    query = parse_qsl(parsed_source.query, keep_blank_values=True)
    fragments.extend(f"subdirectory={quote(value, safe='/')}" for key, value in query if key == "subdirectory")
    repository_query = [(key, value) for key, value in query if key not in {"rev", "tag", "branch", "subdirectory"}]
    url = urlunsplit(
        (parsed_source.scheme, parsed_source.netloc, parsed_source.path, urlencode(repository_query), ""),
    )
    url = _github_url_with_token(url, github_token, required=False)
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in {"https", "file"}:
        raise ValueError(f"Unsupported Git dependency URL in uv.lock: {url!r}")
    git_url = urlunsplit(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            f"{parsed_url.path}@{revision}",
            parsed_url.query,
            "",
        ),
    )
    git_url = f"git+{git_url}"
    for fragment in fragments:
        if fragment.startswith("subdirectory="):
            git_url += f"#{fragment}"
            break
    return _with_uv_marker(f"{name} @ {git_url}", package)


def _with_uv_marker(requirement: str, package: dict[str, Any]) -> str:
    markers = package.get("resolution-markers")
    if markers is None:
        return requirement
    if not isinstance(markers, list) or not all(isinstance(marker, str) for marker in markers):
        raise ValueError("Invalid resolution markers in uv.lock.")
    if not markers:
        return requirement
    marker = " or ".join(f"({value})" for value in markers)
    return f"{requirement} ; {marker}"


def _use_built_uv_solution_version(project: dict[str, Any], definitions_folder: Path) -> None:
    """Replace a dynamic project version with the built solution wheel version so UV can lock without building."""
    metadata = project.get("project")
    if not isinstance(metadata, dict):
        return
    dynamic_fields = metadata.get("dynamic")
    if not isinstance(dynamic_fields, list) or "version" not in dynamic_fields:
        return
    package_name = canonicalize_name(metadata["name"])
    versions = [
        version
        for name, version, *_ in (parse_wheel_filename(wheel.name) for wheel in definitions_folder.glob("*.whl"))
        if name == package_name
    ]
    if len(versions) != 1:
        raise RuntimeError(
            f"Expected one built {package_name} wheel in {definitions_folder} to read its version, "
            f"found {len(versions)}."
        )
    metadata["version"] = str(versions[0])
    remaining_dynamic_fields = [field for field in dynamic_fields if field != "version"]
    if remaining_dynamic_fields:
        metadata["dynamic"] = remaining_dynamic_fields
    else:
        del metadata["dynamic"]


def create_uv_installation_project(
    solution_root_dir: Path,
    definitions_folder: Path,
    python_exec: Path,
    github_token: str | None = None,
    offline_package: bool = False,
) -> None:
    """Create a portable UV project and stage the locked local dependencies."""
    project_file = solution_root_dir / "pyproject.toml"
    lock_file = solution_root_dir / "uv.lock"
    groups = ["desktop", "ui", "doc"]
    with project_file.open("rb") as source_file:
        project = tomllib.load(source_file)
    dependency_groups = project.get("dependency-groups", {})
    if not isinstance(dependency_groups, dict):
        raise ValueError(f"'dependency-groups' must be a table in '{project_file}'.")

    selected_groups = [group for group in groups if group in dependency_groups]
    project["dependency-groups"] = {group: dependency_groups[group] for group in selected_groups}
    _use_built_uv_solution_version(project, definitions_folder)
    if offline_package:
        target_environment = subprocess.check_output(
            [
                str(python_exec),
                "-c",
                "import sys; print(f\"sys_platform == '{sys.platform}' and "
                "python_version == '{sys.version_info.major}.{sys.version_info.minor}'\")",
            ],
            text=True,
        ).strip()
        uv_settings = project.setdefault("tool", {}).setdefault("uv", {})
        uv_settings["environments"] = [target_environment]
        uv_settings["no-index"] = True
        uv_settings["find-links"] = ["wheelhouse"]
    definitions_folder.mkdir(parents=True, exist_ok=True)
    wheelhouse = definitions_folder / "wheelhouse"

    with tempfile.TemporaryDirectory() as temporary_directory:
        requirements_path = Path(temporary_directory) / "requirements.txt"
        export_uv_requirements(solution_root_dir, python_exec, requirements_path)
        lock_packages = _selected_uv_lock_packages(solution_root_dir, requirements_path)
        stage_uv_selected_local_dependencies(solution_root_dir, lock_packages, wheelhouse, python_exec, github_token)
        _stage_uv_private_dependencies(solution_root_dir, lock_packages, wheelhouse, python_exec)
        if offline_package:
            stage_uv_external_dependencies(solution_root_dir, definitions_folder, python_exec, lock_packages)
        _rewrite_uv_local_sources(
            project,
            solution_root_dir,
            lock_packages,
            wheelhouse,
            include_public_registry_packages=offline_package,
        )

    project_path = definitions_folder / "pyproject.toml"
    project_path.write_text(toml.dumps(project), encoding="utf-8")
    shutil.copy2(lock_file, definitions_folder / "uv.lock")
    (definitions_folder / "uv-groups.txt").write_text("\n".join(selected_groups), encoding="utf-8")

    uv_executable = shutil.which("uv")
    if uv_executable is None:
        raise FileNotFoundError("The UV executable could not be found to bundle with the solution.")

    try:
        subprocess.run(
            _uv_lock_command(uv_executable, python_exec, offline_package),
            cwd=definitions_folder,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create portable UV lockfile: {e.stderr}") from e
    _export_uv_pip_requirements(uv_executable, definitions_folder, python_exec, selected_groups)

    tools_directory = definitions_folder / "tools"
    tools_directory.mkdir(parents=True, exist_ok=True)
    executable_name = "uv.exe" if platform.system() == "Windows" else "uv"
    shutil.copy2(uv_executable, tools_directory / executable_name)


def _export_uv_pip_requirements(
    uv_executable: str,
    definitions_folder: Path,
    python_exec: Path,
    groups: list[str],
) -> None:
    command = [
        uv_executable,
        "export",
        "--locked",
        "--no-default-groups",
        "--no-emit-project",
        "--no-hashes",
        "--python",
        str(python_exec),
    ]
    for group in groups:
        command.extend(["--group", group])
    try:
        result = subprocess.run(
            command,
            cwd=definitions_folder,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to export portable UV requirements: {e.stderr}") from e
    (definitions_folder / "uv-requirements.txt").write_text(result.stdout, encoding="utf-8")


def _uv_lock_command(uv_executable: str | Path, python_exec: Path, offline_package: bool) -> list[str]:
    """Lock the portable project; online packages may fetch registry metadata missing from the local UV cache."""
    command = [str(uv_executable), "lock", "--python", str(python_exec)]
    if offline_package:
        command.insert(2, "--offline")
    return command


def refresh_uv_project_lock(definitions_folder: Path, python_exec: Path, offline_package: bool = False) -> None:
    """Recalculate local wheel hashes after obfuscation."""
    executable_name = "uv.exe" if platform.system() == "Windows" else "uv"
    uv_executable = definitions_folder / "tools" / executable_name
    try:
        subprocess.run(
            _uv_lock_command(uv_executable, python_exec, offline_package),
            cwd=definitions_folder,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to refresh portable UV lockfile: {e.stderr}") from e


def _rewrite_uv_local_sources(
    project: dict[str, Any],
    solution_root_dir: Path,
    lock_packages: list[dict[str, Any]],
    wheelhouse: Path,
    include_public_registry_packages: bool = False,
) -> None:
    """Point each locked local dependency at its staged wheel."""
    wheels_by_package: dict[str, list[tuple[str, Path]]] = {}
    for wheel in wheelhouse.glob(WHL_CONSTANT):
        name, version, _, _ = parse_wheel_filename(wheel.name)
        wheels_by_package.setdefault(canonicalize_name(name), []).append((str(version), wheel))
    local_sources: dict[str, list[dict[str, str]]] = {}
    public_registry_names: set[str] = set()
    for package in lock_packages:
        if include_public_registry_packages and _is_public_uv_package(package):
            public_registry_names.add(canonicalize_name(package["name"]))
        elif _is_uv_staged_package(package, solution_root_dir):
            name, source = _uv_wheel_source(package, wheels_by_package)
            if source is not None:
                local_sources.setdefault(name, []).append(source)

    if not local_sources and not public_registry_names:
        return
    tool = project.setdefault("tool", {})
    uv = tool.setdefault("uv", {})
    sources = uv.setdefault("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("The [tool.uv.sources] section must be a table.")
    sources = {name: source for name, source in sources.items() if canonicalize_name(name) not in public_registry_names}
    uv["sources"] = sources
    sources.update({name: values[0] if len(values) == 1 else values for name, values in local_sources.items()})
    project_metadata = project.setdefault("project", {})
    dependencies = project_metadata.setdefault("dependencies", [])
    direct_names = {canonicalize_name(Requirement(dependency).name) for dependency in dependencies}
    for name, values in local_sources.items():
        if canonicalize_name(name) not in direct_names:
            markers = [value["marker"] for value in values if "marker" in value]
            marker = " or ".join(f"({value})" for value in markers) if len(markers) == len(values) else ""
            dependencies.append(f"{name} ; {marker}" if marker else name)


def _is_uv_staged_package(package: dict[str, Any], solution_root_dir: Path) -> bool:
    source = package.get("source")
    if not isinstance(source, dict):
        raise ValueError("Invalid package source in uv.lock.")
    if (
        _uv_local_source(package, solution_root_dir) is not None
        or isinstance(source.get("git"), str)
        or isinstance(source.get("url"), str)
    ):
        return True
    index_url = source.get("registry")
    return isinstance(index_url, str) and not _is_public_uv_index(index_url)


def _uv_wheel_source(
    package: dict[str, Any],
    wheels_by_package: dict[str, list[tuple[str, Path]]],
) -> tuple[str, dict[str, str] | None]:
    name = package.get("name")
    version = package.get("version")
    if not isinstance(name, str):
        raise ValueError("Invalid staged package entry in uv.lock.")
    candidates = wheels_by_package.get(canonicalize_name(name), [])
    matching_wheels = (
        [wheel for wheel_version, wheel in candidates if wheel_version == version]
        if isinstance(version, str)
        else [wheel for _, wheel in candidates]
    )
    if not matching_wheels:
        return name, None
    if len(matching_wheels) > 1:
        raise ValueError(f"Multiple staged wheels match package '{name}' in uv.lock.")
    source = {"path": f"wheelhouse/{matching_wheels[0].name}"}
    markers = package.get("resolution-markers")
    if markers is not None:
        if not isinstance(markers, list) or not all(isinstance(marker, str) for marker in markers):
            raise ValueError("Invalid resolution markers in uv.lock.")
        if markers:
            source["marker"] = " or ".join(f"({value})" for value in markers)
    return name, source


def _stage_uv_private_dependencies(
    solution_root_dir: Path,
    lock_packages: list[dict[str, Any]],
    wheelhouse: Path,
    python_exec: Path,
) -> None:
    """Build wheels for packages locked to non-PyPI registries."""
    private_packages = _get_private_uv_packages(lock_packages)
    if not private_packages:
        return

    with (solution_root_dir / "pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)
    indexes = project.get("tool", {}).get("uv", {}).get("index", [])
    if not isinstance(indexes, list):
        indexes = []

    for index_url, index_packages in private_packages.items():
        requirements = [_private_uv_requirement(package) for package in index_packages]
        _build_private_uv_wheels(solution_root_dir, wheelhouse, python_exec, index_url, indexes, requirements)


def _get_private_uv_packages(packages: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    private_packages: dict[str, list[dict[str, Any]]] = {}
    for package in packages:
        source = package.get("source")
        if not isinstance(source, dict):
            raise ValueError("Invalid package source in uv.lock.")
        index_url = source.get("registry")
        if isinstance(index_url, str) and not _is_public_uv_index(index_url):
            private_packages.setdefault(index_url, []).append(package)
    return private_packages


def _private_uv_requirement(package: dict[str, Any]) -> str:
    name, version = package.get("name"), package.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ValueError("Invalid private package entry in uv.lock.")
    return _with_uv_marker(f"{name}=={version}", package)


def _build_private_uv_wheels(
    solution_root_dir: Path,
    wheelhouse: Path,
    python_exec: Path,
    index_url: str,
    indexes: list[Any],
    requirements: list[str],
) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        requirements_path = Path(temporary_directory) / "private-requirements.txt"
        requirements_path.write_text("\n".join(requirements), encoding="utf-8")
        credentials_url, secrets = _uv_index_credentials(index_url, indexes)
        environment = os.environ.copy()
        environment["PIP_INDEX_URL"] = credentials_url
        command = [
            str(python_exec),
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--extra-index-url",
            "https://pypi.org/simple",
            "--wheel-dir",
            str(wheelhouse),
            "-r",
            str(requirements_path),
        ]
        try:
            subprocess.run(
                command,
                cwd=solution_root_dir,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            message = (e.stderr or e.stdout or str(e)).replace(credentials_url, index_url)
            for secret in secrets:
                message = message.replace(secret, "***")
            raise RuntimeError(f"Failed to stage private UV dependencies: {message}") from e


def _is_public_uv_index(index_url: str) -> bool:
    return urlsplit(index_url).hostname == "pypi.org"


def _is_public_uv_package(package: dict[str, Any]) -> bool:
    source = package.get("source")
    index_url = source.get("registry") if isinstance(source, dict) else None
    return isinstance(index_url, str) and _is_public_uv_index(index_url)


def _uv_index_credentials(index_url: str, indexes: list[Any]) -> tuple[str, list[str]]:
    for index in indexes:
        if not isinstance(index, dict) or index.get("url") != index_url or not isinstance(index.get("name"), str):
            continue
        index_name = re.sub(r"[^A-Za-z0-9]", "_", index["name"]).upper()
        username = os.environ.get(f"UV_INDEX_{index_name}_USERNAME", "")
        password = os.environ.get(f"UV_INDEX_{index_name}_PASSWORD", "")
        if not username and not password:
            return index_url, []
        parsed_url = urlsplit(index_url)
        userinfo = quote(username, safe="")
        if password:
            userinfo += f":{quote(password, safe='')}"
        credentialed_url = urlunsplit(
            (
                parsed_url.scheme,
                f"{userinfo}@{parsed_url.netloc}",
                parsed_url.path,
                parsed_url.query,
                parsed_url.fragment,
            ),
        )
        return credentialed_url, [secret for secret in (username, password) if secret]
    return index_url, []


def stage_uv_external_dependencies(
    solution_root_dir: Path,
    definitions_folder: Path,
    python_exec: Path,
    lock_packages: list[dict[str, Any]],
) -> None:
    """Build wheels for locked non-local UV dependencies for an offline installer."""
    wheelhouse = definitions_folder / "wheelhouse"
    wheelhouse.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary_directory:
        requirements_path = Path(temporary_directory) / "requirements.txt"
        command = [
            "uv",
            "export",
            "--locked",
            "--no-default-groups",
            "--no-emit-project",
            "--no-emit-local",
            "--no-hashes",
            "--python",
            str(python_exec),
        ]
        with (solution_root_dir / "pyproject.toml").open("rb") as project_file:
            project = tomllib.load(project_file)
        groups = project.get("dependency-groups", {})
        if not isinstance(groups, dict):
            raise ValueError("The 'dependency-groups' section must be a table.")
        for group in ("desktop", "ui", "doc"):
            if group in groups:
                command.extend(["--group", group])
        try:
            result = subprocess.run(
                command,
                cwd=solution_root_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"UV dependency export failed: {e.stderr}") from e
        requirements_path.write_text(
            _exclude_uv_staged_requirements(result.stdout, lock_packages, solution_root_dir),
            encoding="utf-8",
        )
        try:
            subprocess.run(
                [
                    str(python_exec),
                    "-m",
                    "pip",
                    "wheel",
                    "--disable-pip-version-check",
                    "--no-deps",
                    "--index-url",
                    "https://pypi.org/simple",
                    "--find-links",
                    str(wheelhouse),
                    "--wheel-dir",
                    str(wheelhouse),
                    "-r",
                    str(requirements_path),
                ],
                cwd=solution_root_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to stage external UV dependencies: {e.stderr}") from e


def _exclude_uv_staged_requirements(
    requirements: str,
    lock_packages: list[dict[str, Any]],
    solution_root_dir: Path,
) -> str:
    """Omit requirements already built into wheelhouse wheels."""
    staged_names = {
        canonicalize_name(package["name"])
        for package in lock_packages
        if isinstance(package.get("name"), str) and _is_uv_staged_package(package, solution_root_dir)
    }

    filtered_lines: list[str] = []
    skip_continuation = False
    for line in requirements.splitlines():
        if line.startswith((" ", "\t")):
            if not skip_continuation:
                filtered_lines.append(line)
            continue
        skip_continuation = False
        if line and not line.startswith(("#", "-")):
            with suppress(InvalidRequirement):
                skip_continuation = canonicalize_name(Requirement(line).name) in staged_names
        if not skip_continuation:
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def _uv_local_requirement(package: Any, solution_root_dir: Path) -> str | None:
    if not isinstance(package, dict):
        raise ValueError("Invalid package entry in uv.lock.")
    source = _uv_local_source(package, solution_root_dir)
    if source is None:
        return None
    package_name = package.get("name")
    if not isinstance(package_name, str) or not package_name:
        raise ValueError("Invalid package name in uv.lock.")
    return _with_uv_marker(f"{package_name} @ {source.as_uri()}", package)


def _uv_local_source(package: dict[str, Any], solution_root_dir: Path) -> Path | None:
    source_info = package.get("source")
    if not isinstance(source_info, dict):
        raise ValueError("Invalid package source in uv.lock.")
    path = source_info.get("path")
    if path is None:
        return None
    if not isinstance(path, str):
        raise ValueError("Invalid local path in uv.lock.")
    source = Path(path)
    if not source.is_absolute():
        source = solution_root_dir / source
    wheels = package.get("wheels", [])
    expected_hash = next(
        (
            entry["hash"].removeprefix("sha256:")
            for entry in wheels
            if isinstance(entry, dict)
            and entry.get("filename") == source.name
            and isinstance(entry.get("hash"), str)
            and entry["hash"].startswith("sha256:")
        ),
        None,
    )
    if source.suffix == ".whl" and expected_hash is None:
        raise ValueError(f"Missing SHA-256 hash for local archive {source}.")
    if source.is_file():
        with source.open("rb") as archive_file:
            digest = hashlib.file_digest(archive_file, "sha256").hexdigest()
        if expected_hash is not None and digest != expected_hash:
            raise ValueError(f"SHA-256 hash mismatch for local archive {source}.")
    return source.resolve()


def _download_poetry_external_dependencies(
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
    download_build_tool_with_pip("pip", definitions_folder, venv_python_exec)
    download_build_tool_with_pip("poetry", definitions_folder, venv_python_exec)
    temporary_requirements = create_poetry_requirements_txt(pyproject_location, definitions_folder)
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


def _poetry_package_matches_platform(package: dict[str, Any]) -> bool:
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


def build_and_stage_solution_packages(
    definitions_folder: Path,
    venv_python_exec: Path,
    solution_root_dir: Path,
    solution_module_name: str,
    solution_display_name: str,
    installer_config: InstallerConfig,
    python_version: str,
    backend: SolutionBackend | None = None,
) -> None:
    logger.info("Building and staging solution packages, optionally obfuscating them.")
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
                build_solution_wheel(definitions_folder, solution_root_dir)
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
        build_solution_wheel(definitions_folder, solution_root_dir)
    backend = backend or detect_solution_backend(solution_root_dir).backend
    poetry_packages_with_wheel_url_dependencies: list[tuple[str, str]] = []
    if backend is SolutionBackend.POETRY:
        poetry_packages_with_wheel_url_dependencies = _get_poetry_packages_with_wheel_url_dependencies(
            installer_config.pyproject_location.with_name("poetry.lock"),
        )
        _stage_poetry_internal_dependencies(
            solution_root_dir,
            solution_module_name,
            solution_display_name,
            installer_config.pyproject_location,
            venv_python_exec,
            github_token=installer_config.github_token,
        )
        modify_solution_wheel_metadata(
            definitions_folder,
            get_solution_package_name(solution_root_dir),
            get_solution_version(solution_root_dir),
        )
    else:
        create_uv_installation_project(
            solution_root_dir,
            definitions_folder,
            venv_python_exec,
            installer_config.github_token,
            installer_config.offline_package,
        )
    if installer_config.obfuscate:
        obfuscate_solution(definitions_folder, venv_python_exec)
        if backend is SolutionBackend.UV:
            refresh_uv_project_lock(definitions_folder, venv_python_exec, installer_config.offline_package)
    if installer_config.offline_package and backend is SolutionBackend.POETRY:
        _download_poetry_external_dependencies(
            definitions_folder,
            installer_config.pyproject_location,
            venv_python_exec,
            python_version,
        )
        _convert_poetry_archives_to_wheels(definitions_folder, venv_python_exec)
        _simplify_poetry_wheel_url_dependencies(
            poetry_packages_with_wheel_url_dependencies,
            definitions_folder,
        )


def _convert_poetry_archives_to_wheels(definitions_folder: Path, venv_python_exec: Path) -> None:
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


def _merge_poetry_group_dependencies(
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


def create_poetry_installation_project(
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

    _merge_poetry_group_dependencies(["desktop", "ui", "doc"], poetry, dependencies)

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
    relativize_poetry_lock_path_dependencies(definitions_folder)


def relativize_poetry_lock_path_dependencies(definitions_folder: Path) -> None:
    """Make absolute path dependencies in ``poetry.lock`` relative to the lock folder.

    Poetry writes path dependencies read from wheel METADATA verbatim, which leaks build-machine paths.
    On Python < 3.14, ``Path.exists()`` raises ``PermissionError`` when such a path exists but is unreadable,
    which breaks the installation.
    """
    poetry_lock_path = definitions_folder / "poetry.lock"
    lock_dir = definitions_folder.resolve()

    def _relativize(match: re.Match[str]) -> str:
        dependency_path = Path(tomllib.loads(f"v = {match.group(2)}")["v"])
        if not dependency_path.is_absolute():
            return match.group(0)
        try:
            relative_path = dependency_path.resolve().relative_to(lock_dir)
        except ValueError:
            logger.warning(f"Absolute path dependency outside {lock_dir} left unchanged: {dependency_path}")
            return match.group(0)
        # JSON string escapes are valid TOML basic string escapes, except DEL which TOML requires escaped.
        encoded_path = json.dumps(relative_path.as_posix(), ensure_ascii=False).replace("\x7f", "\\u007F")
        return f"{match.group(1)}{encoded_path}"

    content = poetry_lock_path.read_text(encoding="utf-8")
    poetry_lock_path.write_text(LOCK_PATH_DEPENDENCY_PATTERN.sub(_relativize, content), encoding="utf-8")


def write_backend_tool_requirements(
    solution_root_dir: Path,
    solution_module_name: str,
    venv_python_exec: Path,
    backend: SolutionBackend,
) -> None:
    definitions_folder = get_definitions_folder(solution_root_dir, solution_module_name)
    project_file_path = solution_root_dir / "pyproject.toml"
    project = toml.load(project_file_path)

    tools_directory = definitions_folder / "tools"
    tools_directory.mkdir(parents=True, exist_ok=True)
    logger.info(f"Adding tool requirements files to {tools_directory}")

    pip_version_information = subprocess.check_output(
        [venv_python_exec, "-m", "pip", "--disable-pip-version-check", "--version"],
        text=True,
    )
    pip_version = pip_version_information.split()[1]

    poetry_reqs = None
    if backend is SolutionBackend.POETRY:
        if "build-system-requirements" not in project:
            raise KeyError(f"build-system-requirements key not found in {project_file_path}.")

        build_system_requirements = project["build-system-requirements"]

        if "build-system-version" not in build_system_requirements:
            raise KeyError(
                f"build-system-version key not found in build-system-requirements section in {project_file_path}.",
            )

        poetry_version = build_system_requirements["build-system-version"]
        poetry_reqs = f"poetry=={poetry_version}"
        if Version(poetry_version) >= Version("2.0.0"):
            poetry_reqs += "\npoetry-plugin-export>=1.8"

    (tools_directory / "pip_requirements.txt").write_text(f"pip=={pip_version}")
    if poetry_reqs is not None:
        (tools_directory / "poetry_requirements.txt").write_text(poetry_reqs)


def download_embeddable_python(solution_folder: Path, installer_config: InstallerConfig) -> tuple[Path, str]:
    # The selected Python is used to stage dependencies for either supported backend.
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


def create_venv_in_definitions_folder(
    definitions_folder: Path,
    downloaded_python_exec: Path,
    backend: SolutionBackend,
) -> tuple[Path, Path]:
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
        packages = ["wheel"]
        if backend is SolutionBackend.POETRY:
            packages.append("poetry")
        packages.extend(["setuptools", "pyc-wheel"])
        subprocess.check_output(
            [str(venv_python_exec), "-m", "pip", "install", *packages],
            text=True,
            stderr=subprocess.STDOUT,
        )
        return definitions_venv, venv_python_exec
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to create virtual environment to download external dependencies: {e.output}",
        ) from e
