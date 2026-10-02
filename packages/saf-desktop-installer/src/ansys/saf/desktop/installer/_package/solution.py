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
Common functions for solution package utility.

"""

########################################################################################################################
# Imports
########################################################################################################################
import datetime
import importlib
import inspect
import json
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

import toml

from ansys.saf.desktop.installer._package.config import (
    DESKTOP_ORCHESTRATOR_MODULE_NAME,
    DESKTOP_ORCHESTRATOR_PACKAGE_NAME,
    InstallerConfig,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

########################################################################################################################
# Variables
########################################################################################################################
# root dir is where this script was executed from using the command line
WHL_CONSTANT = "*.whl"
REQ_FILE = "requirements.txt"
GLOW_SOLUTION_DEFINITION_ENV = "GLOW_SOLUTION_DEFINITION"


########################################################################################################################
# Functions
########################################################################################################################


class SolutionInfo:
    def __init__(self, solution_root_dir: Path):
        self.solution_root_dir = solution_root_dir

        self._solution_module_name: str | None = None
        self._solution_module_dotted_path: str | None = None
        self._solution_display_name: str | None = None
        self._solution_package_name: str | None = None
        self._solution_version: str | None = None

    @property
    def solution_module_name(self) -> str:
        if self._solution_module_name is None:
            self._solution_module_name = get_solution_module_name(self.solution_root_dir)
        return self._solution_module_name

    @property
    def solution_module_dotted_path(self) -> str:
        if self._solution_module_dotted_path is None:
            self._solution_module_dotted_path = get_solution_module_dotted_path(
                self.solution_root_dir,
                self.solution_module_name,
            )
        return self._solution_module_dotted_path

    @property
    def solution_display_name(self) -> str:
        if self._solution_display_name is None:
            self._solution_display_name = get_solution_display_name(self.solution_module_dotted_path)
        return self._solution_display_name

    @property
    def solution_package_name(self) -> str:
        if self._solution_package_name is None:
            self._solution_package_name = get_solution_package_name(self.solution_root_dir)
        return self._solution_package_name

    @property
    def solution_version(self) -> str:
        if self._solution_version is None:
            self._solution_version = get_solution_version()
        return self._solution_version


def get_solution_module_name(solution_root_dir: Path) -> str:
    """Get solution module name.

    Args:
        solution_root_dir (Path): Path to the solution's root directory

    Returns:
        str: Solution module name."""
    _, solution_module_name = get_solution_namespace_info(solution_root_dir)
    return solution_module_name


def get_solution_namespace_info(solution_root_dir: Path) -> tuple[tuple[str, ...], str]:
    """Get the solution namespace root and module name.

    Args:
        solution_root_dir (Path): Path to the solution's root directory.

    Returns:
        tuple[tuple[str, ...], str]: Namespace root parts and solution module name.
    """
    solution_definition = os.getenv(GLOW_SOLUTION_DEFINITION_ENV)
    if solution_definition:
        match = re.fullmatch(
            r"(?P<namespace_root>.+)\.(?P<module>[^.]+)\.solution\.definition",
            solution_definition,
        )
        if match:
            return tuple(match.group("namespace_root").split(".")), match.group("module")
        raise ValueError(
            f"Invalid {GLOW_SOLUTION_DEFINITION_ENV} value: {solution_definition!r}. "
            "Expected format: '<namespace_root>.<module>.solution.definition'.",
        )

    src_dir = solution_root_dir / "src"
    discovered_packages: list[tuple[tuple[str, ...], str]] = []
    for definition_file in src_dir.rglob("definition.py"):
        if definition_file.parent.name != "solution":
            continue

        # Expected package layout is src/<namespace_root>/<solution_module>/solution/definition.py.
        solution_package_dir = definition_file.parent.parent
        if not solution_package_dir.is_dir():
            continue

        package_relative_parts = solution_package_dir.relative_to(src_dir).parts
        if len(package_relative_parts) < 2:
            continue

        namespace_root_parts = package_relative_parts[:-1]
        solution_module_name = package_relative_parts[-1]
        discovered_packages.append((namespace_root_parts, solution_module_name))

    if len(discovered_packages) > 1:
        discovered_module_paths = sorted(
            ".".join([*namespace_root_parts, solution_module_name])
            for namespace_root_parts, solution_module_name in discovered_packages
        )
        raise ValueError(
            "Multiple solution packages were found under "
            f"{src_dir}: {discovered_module_paths}. "
            f"Set {GLOW_SOLUTION_DEFINITION_ENV} to the target solution.",
        )

    if len(discovered_packages) == 1:
        return discovered_packages[0]

    raise FileNotFoundError(f"Could not find solution module under {src_dir}.")


def get_solution_package_name(solution_root_dir: Path) -> str:
    """Get solution package name.

    Args:
        solution_root_dir (Path): Path to the solution's root directory

    Returns:
        str: Solution package name."""
    pyproject_data = toml.load(solution_root_dir / "pyproject.toml")
    return pyproject_data["tool"]["poetry"]["name"]


def get_solution_module_dotted_path(solution_root_dir: Path, solution_module_name: str) -> str:
    """Get solution module dotted path as a string.

    Args:
        solution_root_dir (Path): Path to the solution's root directory.
        solution_module_name (str): The name of the solution module.

    Returns:
        str: Solution module dotted path."""
    namespace_root_parts, resolved_solution_module_name = get_solution_namespace_info(solution_root_dir)
    if resolved_solution_module_name != solution_module_name:
        raise ValueError(
            f"Resolved solution module name {resolved_solution_module_name} does not match {solution_module_name}.",
        )
    return f"{'.'.join(namespace_root_parts)}.{solution_module_name}"


def get_solution_package_dir(solution_root_dir: Path, solution_module_name: str) -> Path:
    """Get the solution package directory under ``src``.

    The namespace root can come from the ``GLOW_SOLUTION_DEFINITION`` environment
    variable or be inferred from the solution source tree.

    Args:
        solution_root_dir (Path): Path to the solution's root directory.
        solution_module_name (str): The name of the solution module.

    Returns:
        Path: Path to the solution package directory.
    """
    namespace_root_parts, resolved_solution_module_name = get_solution_namespace_info(solution_root_dir)
    if resolved_solution_module_name != solution_module_name:
        raise ValueError(
            f"Resolved solution module name {resolved_solution_module_name} does not match {solution_module_name}.",
        )
    solution_package_dir = solution_root_dir / "src" / Path(*namespace_root_parts) / solution_module_name
    if not solution_package_dir.is_dir():
        raise FileNotFoundError(f"Solution package directory does not exist: {solution_package_dir}")
    return solution_package_dir


def get_solution_display_name(solution_module_dotted_path: str) -> str:
    """Get solution display name.

    Args:
        solution_module_dotted_path (str): The dotted path of the solution module.

    Returns:
        str: Solution display name."""
    solution_definition_module_dotted_path = ".".join([solution_module_dotted_path, "solution", "definition"])
    solution_definition_module = importlib.import_module(solution_definition_module_dotted_path)
    solution_display_name: str | None = None
    for name, obj in inspect.getmembers(solution_definition_module, inspect.isclass):
        if obj.__bases__[0].__name__ == "Solution":
            solution_display_name = obj.model_fields.get("display_name").default
            if solution_display_name is None:
                raise ValueError(f"Class {name} has no display name.")
            else:
                return solution_display_name

    raise ValueError("The solution definition does not contain a Solution subclass.")


def get_solution_version() -> str:
    """Get solution version.

    Args:
        None

    Returns:
        str: Solution version."""
    try:
        solution_version = (
            subprocess.run(["poetry", "version", "--no-interaction"], capture_output=True, check=True, text=True)  # noqa: S607
            .stdout.strip()
            .split()[1]
        )
        if solution_version == "":
            raise ValueError("Solution version is empty.")
        if solution_version == "unknown":
            raise ValueError("Solution version is unknown.")
        return solution_version
    except IndexError:
        raise ValueError("Failed to get solution version.") from None


def copy_configuration_files(solution_root_dir: Path, solution_module_name: str) -> None:
    """Copy configuration files for solution.

    Args:
        solution_root_dir (Path): Path to the solution root directory.
        solution_display_name (str): Solution display name.
    """

    allowed_config_files = [".yaml", ".yml", ".config", ".ini"]

    for file in solution_root_dir.glob(".*"):
        if file.name in ["tox.ini"]:
            continue
        if file.is_file() and file.name in allowed_config_files:
            shutil.copy(
                file,
                solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name,
            )


def create_solution_metadata(
    solution_info: SolutionInfo,
    installer_config: InstallerConfig,
) -> None:
    """Create solution metadata file.

    Args:
        solution_root_dir (Path): Path to the solution root directory.
        args (Dict[str, Union[str, bool, Path]]): List of arguments passed to the script.
    """
    metadata_file = solution_info.solution_root_dir / "dist" / "solution" / "solution-metadata.json"
    logger.info(f"Creating solution metadata file: {metadata_file}")
    solution_metadata = {
        "glow-package-name": DESKTOP_ORCHESTRATOR_PACKAGE_NAME,
        "glow-entry-point-module": DESKTOP_ORCHESTRATOR_MODULE_NAME,
        "use-glow": (
            "True" if installer_config.solution_ui_framework == "dash" and installer_config.use_glow else "False"
        ),
        "solution-entry-point": (
            ""
            if installer_config.solution_ui_framework == "dash" and installer_config.use_glow
            else installer_config.solution_entry_point
        ),
        "solution-name": solution_info.solution_root_dir.name,
        "solution-module-name": solution_info.solution_module_name,
        "solution-version": solution_info.solution_version,
        "solution-display-name": solution_info.solution_display_name,
        "solution-package-name": solution_info.solution_package_name,
        "solution-main-module": f"{solution_info.solution_module_dotted_path}.main",
        "display-console-window": "True" if installer_config.display_console_window else "False",
        "offline-package": "True" if installer_config.offline_package else "False",
        "python-version": installer_config.python_version,
    }

    logger.info(f"Solution Metadata: {solution_metadata}")
    metadata_file.write_text(json.dumps(solution_metadata, indent=4))


def create_requirements_txt(pyproject_location: Path, definitions_folder: Path) -> Path:
    """Create requirements.txt file using poetry.

    Args:
        pyproject_location (Path): Path to the pyproject.toml file.
        definitions_folder (Path): Path to the definitions folder.
    """
    requirements_txt = definitions_folder / REQ_FILE
    logger.info(f"Creating requirements.txt file to {requirements_txt} using poetry from {pyproject_location.parent}")
    output = subprocess.run(
        ["poetry", "export", "--with", "desktop,ui,doc", "--without-hashes", "--format", REQ_FILE],  # noqa: S607
        cwd=pyproject_location.parent,
        capture_output=True,
    )
    if output.returncode != 0:
        logger.error(f"Failed to create requirements.txt file using poetry: {output.stderr}")
        sys.exit(1)
    output = output.stdout.decode("utf-8")
    output = "\n".join([line for line in output.split("\n") if "extra-index-url" not in line])
    output = re.sub(".*@.*", "", output)  # ignore direct links to wheels. helps development

    wheels = "\n".join(str(wheel.absolute()) for wheel in definitions_folder.glob(WHL_CONSTANT))
    output = f"{wheels}\n{output}"
    requirements_txt.write_text(output)
    return requirements_txt


def get_appdata_directory() -> str:
    if platform.system() == "Windows":
        return Path(os.environ["APPDATA"]).as_posix()
    else:
        return str(Path(os.getenv("XDG_DATA_HOME", "~/.local/share")).expanduser())


def create_env_file(solution_root_dir: Path, solution_module_name: str) -> None:
    """Create env file for solution.

    Args:
        solution_root_dir (Path): Path to the solution root directory.
        solution_display_name (str): Display name of the solution.
    """
    env_file = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name / ".env"

    env_content = ""
    if (solution_root_dir / ".env").is_file():
        logger.info(f"Copying env file from Solution's root directory into {env_file}")
        env_content = (solution_root_dir / ".env").read_text()
    else:
        logger.info(f"Creating env file: {env_file}")
        env_content = "PORTAL_DATABASE_TYPE=sqlite\n"
        env_content += f"DATABASE_LOCATION={get_appdata_directory()}/ansys/portal\n"
        env_content += "PORTAL_PROJECT_DATABASE_LOCATION=${DATABASE_LOCATION}/project.db\n"

    if all(not line.startswith("SAF_DESKTOP_LOG_TO_FILES=") for line in env_content.splitlines()):
        env_content += "\nSAF_DESKTOP_LOG_TO_FILES=True\n"

    env_file.write_text(env_content)


def create_version_file(solution_root_dir: Path, solution_display_name: str, solution_version: str) -> None:
    """Create version.txt file.

    Args:
        solution_root_dir (Path): Path to the solution root directory.
        solution_display_name (str): Display name of the solution.
    """
    version_file = solution_root_dir / "dist" / "solution" / "version.txt"
    logger.info(f"Creating version file: {version_file}")
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    try:
        github_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()  # noqa: S607
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning(
            "Could not get the git SHA to populate the version file. Check if git is installed and initialized in the "
            "current project. Setting git SHA to Unknown.",
        )
        github_sha = "Unknown"
    content = f"build.date = {current_time}\n"
    content += f"github.sha = {github_sha}\n"
    content += f"ReleaseVersion = {solution_display_name} Solution {solution_version}\n"
    content += f"ProductName = {solution_display_name} Solution\n"
    content += f"Report_Release = {solution_version}"

    logger.info(f"Version File Content:\n{content}")
    version_file.write_text(content)


def build_and_embed_documentation(solution_root_dir: Path, solution_module_name: str) -> None:
    """Build solution documentation and embed it into the solution package html-doc directory.

    Args:
        solution_root_dir (Path): Path to the solution root directory.
        solution_module_name (str): Name of the solution module.
    """
    dest_doc_html_dir = get_solution_package_dir(solution_root_dir, solution_module_name) / "html-doc"

    sphinx_cmd = ["sphinx-build", "doc/source", "doc/build/html", "--color", "-vW", "-bhtml"]
    logger.info("Building HTML documentation from doc/source with Sphinx.")
    try:
        subprocess.check_output(sphinx_cmd, stderr=subprocess.STDOUT, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # CalledProcessError doesn't cover the case where sphinx-build is not available as executable
        error_msg = e.output if isinstance(e, subprocess.CalledProcessError) else str(e)
        logger.warning(
            f"Failed to build documentation: {error_msg}\n"
            f"Fix the errors or manually copy the documentation to {dest_doc_html_dir}.",
        )
        return

    doc_html_dir = solution_root_dir / "doc" / "build" / "html"
    if not doc_html_dir.is_dir():
        logger.warning(f"Documentation built directory {doc_html_dir} does not exist. Skipping...")
        return

    logger.info(f"Copying documentation to: {dest_doc_html_dir}")
    shutil.rmtree(dest_doc_html_dir, ignore_errors=True)
    shutil.copytree(doc_html_dir, dest_doc_html_dir, ignore=shutil.ignore_patterns(".doctrees"))


def move_assets_and_deployment_script(
    solution_folder: Path,
    solution_root_dir: Path,
    solution_module_name: str,
) -> None:
    # move assets and deployment script to solution folder
    scripts_folder = Path(__file__).parent
    assets_folder = scripts_folder / "assets"
    deployment_script = scripts_folder.parent / "solution_desktop_deployment.py"

    logger.info(f"Copying assets and deployment script to {solution_folder}")
    shutil.copytree(assets_folder, solution_folder / "assets")
    shutil.copy(deployment_script, solution_folder)

    custom_assets_dir = (
        get_solution_package_dir(solution_root_dir, solution_module_name) / "ui" / "assets" / "installer"
    )
    platform_suffix = ".ico" if platform.system() == "Windows" else ".png"

    installer_ui_logo_file = custom_assets_dir / "installer_ui_logo.png"
    if installer_ui_logo_file.is_file():
        shutil.copy(installer_ui_logo_file, solution_folder / "assets" / "installer_ui_logo.png")

    platform_favicon = custom_assets_dir / f"favicon{platform_suffix}"
    other_favicon = custom_assets_dir / ("favicon.png" if platform_suffix == ".ico" else "favicon.ico")
    if platform_favicon.is_file():
        shutil.copy(platform_favicon, solution_folder / "assets" / f"favicon{platform_suffix}")
    elif other_favicon.is_file():
        logger.warning(
            f"Ignoring {other_favicon.name} in {custom_assets_dir}. "
            f"Expected favicon{platform_suffix} for {platform.system()}. Using default favicon{platform_suffix}.",
        )

    platform_shortcut = custom_assets_dir / f"shortcut{platform_suffix}"
    if platform_shortcut.is_file():
        shutil.copy(platform_shortcut, solution_folder / "assets" / f"shortcut{platform_suffix}")
    else:
        shutil.copy(
            solution_folder / "assets" / f"favicon{platform_suffix}",
            solution_folder / "assets" / f"shortcut{platform_suffix}",
        )
