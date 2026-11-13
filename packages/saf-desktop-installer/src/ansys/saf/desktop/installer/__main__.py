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
import os
from pathlib import Path
import platform
import subprocess
import sys

from dotenv import dotenv_values

from ansys.saf.desktop.installer._common.utils import check_poetry_plugin_export_is_required
from ansys.saf.desktop.installer._package.backend_detection import SolutionBackend, detect_solution_backend
from ansys.saf.desktop.installer._package.config import (
    DEFAULT_ENCRIPTION_FILE,
    DEFAULT_PYTHON_VERSION,
    DEFAULT_UI_FRAMEWORK,
    InstallerConfig,
    validate_config,
)
from ansys.saf.desktop.installer._package.solution import SolutionInfo
from ansys.saf.desktop.installer._package.solution_package import (
    build_executable_installer,
    initial_cleanup,
    setup_solution_folder,
)

logger = logging.getLogger(__name__)


def _load_filtered_dotenv(dotenv_file: Path, env: dict[str, str] | None = None) -> None:
    if env is None:
        env = os.environ  # pyright: ignore[reportAssignmentType]

    # We don't use load_dotenv from dotenv library for security reasons. This way, we only load the env vars
    # that match what we are looking for.
    env_vars = dotenv_values(dotenv_file)

    allowed_prefixes = ("POETRY_HTTP_BASIC_", "POETRY_CERTIFICATES_", "UV_INDEX_", "UV_DEFAULT_INDEX")
    filtered_env_vars = {key: value for key, value in env_vars.items() if key.startswith(allowed_prefixes)}

    for key, value in filtered_env_vars.items():
        # to have the same default behaviour as load_dotenv, we only set the env var if it is not already set.
        # https://saurabh-kumar.com/python-dotenv/#getting-started
        if value and not env.get(key):  # pyright: ignore[reportOptionalMemberAccess]
            env[key] = value  # pyright: ignore[reportOptionalSubscript]


def _get_poetry_venv_python_exec() -> Path:
    poetry_venv_path = Path(sys.prefix).parent / ".poetry" / ".venv"
    if not poetry_venv_path.is_dir():
        raise RuntimeError(
            f"Could not find a Poetry virtual environment at the expected location: {poetry_venv_path}. "
            "Make sure Poetry is installed in its own virtual environment at this location.",
        )
    return (
        poetry_venv_path
        / ("Scripts" if platform.system() == "Windows" else "bin")
        / ("python.exe" if platform.system() == "Windows" else "python")
    )


def _prepare_poetry_backend(offline_package: bool) -> None:
    logger.warning("Poetry-based solutions are deprecated. Packaging will continue using Poetry.")
    if not offline_package or not check_poetry_plugin_export_is_required(offline_package):
        return

    logger.info(
        "Installing poetry-plugin-export in the poetry environment to allow build with --offline-package",
    )
    poetry_venv_python_exec = _get_poetry_venv_python_exec()
    try:
        subprocess.check_output([poetry_venv_python_exec, "-m", "pip", "install", "poetry-plugin-export>=1.8"])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "Failed to install poetry-plugin-export, which is required to build with --offline-package for Poetry >=2",
        ) from e


def package_solution(solution_info: SolutionInfo, installer_config: InstallerConfig) -> None:
    backend = detect_solution_backend(solution_info.solution_root_dir).backend
    if backend is SolutionBackend.POETRY:
        _prepare_poetry_backend(installer_config.offline_package)

    env_file = installer_config.env_file or (solution_info.solution_root_dir / ".env")
    if env_file.is_file():
        logger.info(f"Environment variables loaded from {env_file.resolve()}")
        _load_filtered_dotenv(env_file.resolve())

    initial_cleanup(solution_info.solution_root_dir)

    setup_solution_folder(solution_info, installer_config)

    if installer_config.no_executable:
        return

    build_executable_installer(
        solution_folder=solution_info.solution_root_dir / "dist" / "solution",
        output_folder=solution_info.solution_root_dir / "dist",
        solution_display_name=solution_info.solution_display_name,
        executable_as_dir=installer_config.executable_as_dir,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CLI for packaging a solution into a standalone desktop installer.")
    parser.add_argument(
        "--display-console-window",
        action="store_true",
        default=False,
        help="Display the console window when running the solution.",
    )
    parser.add_argument(
        "--encrypt",
        action="store_true",
        default=False,
        help="Encrypt the solution code before packaging.",
    )
    parser.add_argument(
        "--encryption-file",
        help="The file containing the list of files to encrypt.",
        default=DEFAULT_ENCRIPTION_FILE,
    )
    parser.add_argument(
        "--encryption-key",
        help="The key to use for encryption. If none, keyless mode is used.",
        default=None,
    )
    parser.add_argument(
        "--no-executable",
        action="store_true",
        default=False,
        help="Do not create an executable installer for the solution.",
    )
    parser.add_argument(
        "--obfuscate",
        action="store_true",
        default=False,
        help="Obfuscate the solution code before packaging.",
    )
    parser.add_argument(
        "--offline-package",
        action="store_true",
        default=False,
        help="Create a package that installs without internet access.",
    )
    parser.add_argument(
        "--exclude-python",
        action="store_true",
        default=False,
        help="Do not ship the Python interpreter with the packaged solution.",
    )
    parser.add_argument(
        "--python-version",
        help="The version of Python to use for the solution.",
        default=DEFAULT_PYTHON_VERSION,
    )
    parser.add_argument(
        "--force-python-from-source",
        action="store_true",
        help="Force building Python from source instead of downloading it from NuGet packages (Windows only).",
        default=False,
    )
    parser.add_argument(
        "--solution-entry-point",
        help=(
            "The main solution entry point to start the solution. "
            "Module should be a dotted import ('ansys.solutions.mysoln.main'). "
            "If not provided, the solution will be run with the default entry point."
        ),
        default="",
    )
    parser.add_argument(
        "--github-token",
        help="Personal Access Token for downloading dependencies from GitHub.",
        default="",
    )
    parser.add_argument(
        "--solution-ui-framework",
        help="The UI framework used in the solution.",
        default=DEFAULT_UI_FRAMEWORK,
    )
    parser.add_argument(
        "--no-glow",
        action="store_true",
        default=False,
        help="Add this flag if the solution does not use SAF/GLOW.",
    )
    parser.add_argument(
        "--env-file",
        help=("Load environment variables from this file. [default: .env]."),
        default="",
    )
    parser.add_argument(
        "--executable-as-dir",
        action="store_true",
        help=(
            "Bundle the executable in a directory containing all the supporting files. "
            "This is mandatory if the executable file size would exceed the pyinstaller limit of 4GB."
        ),
        default=False,
    )
    args = parser.parse_args()

    # If excluding python and packaging for an offline installation, the external dependencies are downloaded using
    # the Python version specified in the python_version option. These dependencies might only work with that Python
    # minor version.
    if args.exclude_python:
        logger.warning(
            "Creating a package without embedded Python. The solution might only be installable on a system using "
            f"Python version {args.python_version}. If the target system uses a different Python version, "
            "use the option --python-version to specify that version.",
        )

    # We assume this script is executed in the root dir of the solution to be packaged
    solution_info = SolutionInfo(solution_root_dir=Path.cwd())

    config = InstallerConfig(
        display_console_window=args.display_console_window,
        encrypt=args.encrypt,
        encryption_file=Path(args.encryption_file),
        obfuscate=args.obfuscate,
        offline_package=args.offline_package,
        exclude_python=args.exclude_python,
        python_version=args.python_version,
        force_python_from_source=args.force_python_from_source,
        solution_entry_point=args.solution_entry_point,
        solution_ui_framework=args.solution_ui_framework,
        use_glow=not args.no_glow,
        no_executable=args.no_executable,
        github_token=args.github_token if args.github_token else os.environ.get("ANSYS_GITHUB_PAT", None),
        encryption_key=args.encryption_key,
        env_file=Path(args.env_file) if args.env_file else None,
        executable_as_dir=args.executable_as_dir,
    )

    validate_config(config)
    package_solution(solution_info, config)
