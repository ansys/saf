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
Desktop deployment on Windows platform of a solution application build with the Guided Low Code Workflow (GLOW).

Parameters
----------

metadata-file: file (optional)
    json file containing the solution metadata.

installation-directory: Path (optional)
    Installation directory.

Usage
-----

To run the script:
``python solution_desktop_deployment.py -m solution.json``

The structure of the input json file must be as follows:
{
    "glow-package-name": "GLOW_PACKAGE_NAME",
    "glow-entry-point-module": "GLOW_ENTRY_POINT_MODULE",
    "use-glow": "True"/"False",
    "solution-name": "SOLUTION_NAME",
    "solution-module-name": "SOLUTION_MODULE_NAME",
    "solution-display-name": "SOLUTION_DISPLAY_NAME",
    "solution-package-name": "SOLUTION_PACKAGE_NAME",
    "solution-main-module": "SOLUTION_MAIN_MODULE",
    "display-console-window": "True"/"False",
}
"""

# ==================================================== [Imports] ==================================================== #

import base64
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import random
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, NamedTuple
import uuid
import webbrowser
import zipfile

import click
from dash import Dash, Input, Output, State, dcc, html, no_update  # pyright: ignore[reportMissingTypeStubs]
import dash_bootstrap_components as dbc  # pyright: ignore[reportMissingTypeStubs]
import webview as pywebview  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.desktop.installer._common.utils import has_portal_dependency, modify_solution_wheel_metadata
from ansys.saf.desktop.installer._installer.prerequisites import (
    LONG_PATHS_ERROR_MSG,
    WEBVIEW2_ERROR_MSG,
    is_long_paths_enabled,
    is_webview2_installed,
)
from ansys.saf.desktop.installer._ui_styles import (
    LONG_PATH_WARNING_HIDDEN_STYLE,
    LONG_PATH_WARNING_SHOWN_STYLE,
    PREREQUISITES_NOT_FULFILLED_MSG_STYLE_BASE,
    install_button_style,
)

# =================================================== [constants] =================================================== #

VIRTUAL_ENVIRONMENT_NAME = ".venv"  # this is the name that poetry gives the virtual environment it creates
ROOT_DIR = Path(sys._MEIPASS).absolute() if hasattr(sys, "_MEIPASS") else Path(__file__).parent.absolute()  # type: ignore
PYTHON_NOT_FOUND = "Python not found"
INSTALLER_HEADING = "Solution Installer"
VERSION_FILE = "version.txt"
TARGET_SOLUTIONS_DIRECTORY_NAME = "SAF Solutions" if platform.system() == "Windows" else "saf_solutions"

# =================================================== [Functions] =================================================== #


def get_shortcut_path(solution_display_name: str) -> Path:
    """Return the path to the shortcut to create."""
    if platform.system() == "Windows":
        return Path(os.environ["PUBLIC"]) / "Desktop" / f"{solution_display_name}.lnk"
    shortcut_directory = Path("/usr/share/applications") if os.environ.get("SUDO_USER") else Path.home() / "Desktop"
    shortcut_directory.mkdir(parents=True, exist_ok=True)
    return shortcut_directory / f"{solution_display_name}.desktop"


def get_system_python_interpreter() -> Path | None:
    for name in ("python", "python3", "python3.14", "python3.13", "python3.12", "python3.11"):
        if python_exec := shutil.which(name):
            return Path(python_exec).resolve()

    if platform.system() == "Windows":
        possible_dirs = [
            Path(r"C:\Python314"),
            Path(r"C:\Python313"),
            Path(r"C:\Python312"),
            Path(r"C:\Python311"),
            Path(r"C:\Program Files\Python314"),
            Path(r"C:\Program Files\Python313"),
            Path(r"C:\Program Files\Python312"),
            Path(r"C:\Program Files\Python311"),
            Path(r"C:\Program Files (x86)\Python314"),
            Path(r"C:\Program Files (x86)\Python313"),
            Path(r"C:\Program Files (x86)\Python312"),
            Path(r"C:\Program Files (x86)\Python311"),
            Path.home() / r"AppData\Local\Programs\Python\Python314",
            Path.home() / r"AppData\Local\Programs\Python\Python313",
            Path.home() / r"AppData\Local\Programs\Python\Python312",
            Path.home() / r"AppData\Local\Programs\Python\Python311",
        ]
        for base in possible_dirs:
            python_exec = base / "python.exe"
            if python_exec.is_file():
                return python_exec.resolve()
    elif platform.system() == "Linux":
        for path in (
            "/usr/bin/python3.14",
            "/usr/bin/python3.13",
            "/usr/bin/python3.12",
            "/usr/bin/python3.11",
            "/usr/local/bin/python3.14",
            "/usr/local/bin/python3.13",
            "/usr/local/bin/python3.12",
            "/usr/local/bin/python3.11",
            "/usr/bin/python3",
            "/usr/bin/python",
        ):
            python_exec = Path(path)
            if python_exec.is_file():
                return python_exec
    else:
        raise RuntimeError("Unsupported operating system.")

    return None


def get_python_interpreter(python_dir: Path) -> Path | None:
    """Get Python interpreter"""
    if platform.system() == "Windows":
        if (python_interpreter := python_dir / "python.exe").is_file():
            return python_interpreter
        if (python_interpreter := python_dir / "tools" / "python.exe").is_file():
            return python_interpreter
    elif platform.system() == "Linux":
        if (python_interpreter := python_dir / "bin" / "python3").is_file():
            return python_interpreter
    else:
        raise RuntimeError("Unsupported operating system.")

    return get_system_python_interpreter()


def get_python_interpreter_in_venv(venv_path: Path) -> Path:
    """Get Python interpreter in virtual environment"""
    python_exec = (
        venv_path / "Scripts" / "python.exe" if platform.system() == "Windows" else venv_path / "bin" / "python3"
    )
    if not python_exec.is_file():
        raise RuntimeError(f"Unable to find a python interpreter in virtual environment {venv_path}")
    return python_exec


def _ensure_third_party_extracted() -> None:
    """Extract the ``third_party.zip`` bundle to its expected directory if not already present.

    At build time, :func:`~ansys.saf.desktop.installer._package.solution_package._zip_third_party`
    compresses the entire ``third_party/`` directory into ``third_party.zip`` so that
    PyInstaller's binary scanner cannot see any DLL inside it.  This function reverses that
    step at runtime on Windows, restoring the full ``third_party/`` tree before the installer
    logic accesses the embedded Python interpreter or any other file inside it.

    The extraction is skipped when ``third_party/`` already exists (idempotent; handles
    ``--onedir`` mode where extracted files persist across runs).
    """
    if platform.system() != "Windows":
        return
    third_party_zip = ROOT_DIR / "third_party.zip"
    third_party_dir = ROOT_DIR / "third_party"
    if third_party_zip.is_file() and not third_party_dir.exists():
        third_party_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(third_party_zip, "r") as zf:
            zf.extractall(third_party_dir)
        third_party_zip.unlink()


def get_python_version(python_exe: Path) -> str:
    """Get Python version"""
    return subprocess.check_output(
        [str(python_exe), "--version"],
        stderr=subprocess.PIPE,
        text=True,
    ).strip()


def get_wheel(package_name: str, wheel_directory: Path) -> Path:
    """Get the wheel of a given package."""

    # Replace dashes by underscores in package name
    package_name = package_name.replace("-", "_")
    # Get all wheels in directory
    wheels = list(wheel_directory.glob(f"{package_name}-*-py3-none-any.whl"))
    # Check if directory contains wheels
    if not wheels:
        sys.exit(f"No wheels matching package {package_name} in {wheel_directory}")
    # Check if one single wheel matches package name
    if len(wheels) != 1:
        sys.exit(f"More than one path matching {package_name}-*-py3-none-any.whl in {wheel_directory}")
    return wheels[0]


def check_deployment_directory(
    deployment_directory: Path,
    solution_module_name: str,
    solution_package_name: str,
) -> None:
    """Check if the deployment directory contains the necessary files for the solution deployment."""
    # Check if solution directory is available in definitions directory
    solution_deployment_directory = deployment_directory / "definitions" / solution_module_name
    if not solution_deployment_directory.is_dir():
        sys.exit(f"No solution directory in: {solution_deployment_directory}")
    # Check if solution directory contains wheels
    if len(list(solution_deployment_directory.glob("*.whl"))) == 0:
        sys.exit(f"No wheels in solution directory: {solution_deployment_directory}")
    # Check if solution directory contains solution wheel
    if not get_wheel(solution_package_name, solution_deployment_directory).is_file():
        sys.exit(f"No {solution_package_name} in {solution_deployment_directory}.")
    # Check if version.txt is available
    version_file = deployment_directory / VERSION_FILE
    if not version_file.is_file():
        sys.exit(f"Missing version file at: {version_file}")


def get_installation_directory_path(
    installation_directory: Path,
    solution_display_name: str,
    solution_version: str,
) -> Path:
    """returns the path to the solution installation directory."""
    solution_name_reworked = solution_display_name + " Solution"
    return installation_directory / solution_name_reworked / solution_version


def delete_existing_solution_directory(installation_directory: Path) -> None:
    """Delete existing solution directory."""
    if installation_directory.is_dir():
        print(f"Remove existing installation: {installation_directory}")
        shutil.rmtree(str(installation_directory))
    elif installation_directory.is_file():
        print(f"Remove existing file: {installation_directory}")
        installation_directory.unlink()


def delete_existing_solution_shortcut(solution_display_name: str) -> None:
    """Delete existing solution shortcut."""
    shortcut_path = get_shortcut_path(solution_display_name)
    if shortcut_path.is_file():
        print(f"Remove existing shortcut: {shortcut_path}")
        shortcut_path.unlink()


def cleanup_workspace(installation_directory: Path, solution_display_name: str) -> None:
    """Check if solution already exists and delete it"""
    # Remove existing install directory
    delete_existing_solution_directory(installation_directory)
    # Remove shortcut
    delete_existing_solution_shortcut(solution_display_name)


def deploy_materials_for_installation(
    deployment_directory: Path,
    installation_directory: Path,
    solution_module_name: str,
    solution_package_name: str,
    solution_version: str,
    python_interpreter: Path,
) -> None:
    """Deploy materials for installation"""
    python_deployment_directory = deployment_directory / "third_party" / "python"
    try:
        # Check if the python interpreter is inside the deployment directory. If so, copy it to the installation
        # directory. Otherwise, we are using the system python interpreter and we do not need to copy anything.
        python_interpreter.relative_to(python_deployment_directory)
        python_installation_directory = installation_directory / "python"
        print("Copying Python interpreter to installation directory")
        shutil.copytree(python_deployment_directory, python_installation_directory)
    except ValueError:
        pass

    # Set paths
    solution_deployment_directory = deployment_directory / "definitions" / solution_module_name
    solution_installation_directory = installation_directory / "definitions" / solution_module_name
    # Copy solution directory
    print("Copying Solution directory in installation directory")
    shutil.copytree(solution_deployment_directory, str(solution_installation_directory))

    # Modify solution wheel METADATA file to fix local wheel dependency paths
    modify_solution_wheel_metadata(
        solution_installation_directory,
        solution_package_name,
        solution_version,
    )

    # Set paths
    version_deployment_file = deployment_directory / VERSION_FILE
    version_installation_file = installation_directory / VERSION_FILE
    # Copy solution directory
    print("Copying Version file in installation directory")
    shutil.copyfile(version_deployment_file, str(version_installation_file))

    # Copy shortcut
    shortcut_suffix = ".ico" if platform.system() == "Windows" else ".png"
    icon_deployment_file = deployment_directory / "assets" / f"shortcut{shortcut_suffix}"
    icon_installation_file = installation_directory / "assets" / f"shortcut{shortcut_suffix}"
    print("Copying Shortcut icon in installation directory")
    (installation_directory / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(icon_deployment_file, str(icon_installation_file))


def compute_solution_commandline(
    installation_directory: Path,
    glow_entry_point_module: str,
    solution_main_module: str,
    use_glow: str,
    solution_entry_point: str,
    display_console_window: str = "False",
    solution_use_portal: bool = False,
) -> tuple[Path, list[str]]:
    if platform.system() == "Windows":
        python = installation_directory / VIRTUAL_ENVIRONMENT_NAME / "Scripts"
        python = python / "python.exe" if display_console_window == "True" else python / "pythonw.exe"
    else:
        python = installation_directory / VIRTUAL_ENVIRONMENT_NAME / "bin" / "python"

    if not python.is_file():
        raise RuntimeError(f"Unable to find {python.stem} in solution virtual environment at {python}")

    env_file = installation_directory / ".env"
    if not env_file.is_file():
        raise RuntimeError(f"Unable to find .env file in solution installation directory at {env_file}")

    if use_glow == "True":
        arguments = [
            "-m",
            glow_entry_point_module,
            "--solution-main-module-name",
            solution_main_module,
        ]
        if solution_use_portal:
            arguments.append("--portal")
        arguments.extend(
            [
                "--env-file",
                f'"{env_file.as_posix()}"',
            ],
        )
    else:
        arguments = ["-m", solution_entry_point]

    return python, arguments


def install_shortcut(
    python: Path,
    installation_icon_path: Path,
    arguments: str,
    solution_display_name: str,
    display_console_window: str = "False",
) -> None:
    """Install shortcut"""
    shortcut_path = get_shortcut_path(solution_display_name)
    python_path = str(python)

    if platform.system() == "Windows":
        shell_cmd = "$WshShell = New-Object -ComObject WScript.Shell; "
        shell_cmd += f"$Shortcut = $WshShell.CreateShortcut('{str(shortcut_path)}'); "
        shell_cmd += f"$Shortcut.TargetPath = '{python_path}'; "
        shell_cmd += f"$Shortcut.Arguments = '{arguments}'; "
        shell_cmd += f"$Shortcut.Description = '{solution_display_name} Application'; "
        shell_cmd += f"$Shortcut.IconLocation = '{installation_icon_path}'; "
        shell_cmd += "$Shortcut.Save()"
        subprocess.check_output(["powershell.exe", "-Command", shell_cmd], stderr=subprocess.PIPE, text=True)  # noqa: S607
    else:
        with shortcut_path.open("w") as file:
            file.write("[Desktop Entry]\n")
            file.write(f"Name={solution_display_name}\n")
            file.write(f'Exec="{python_path}" {arguments}\n')
            file.write("Type=Application\n")
            file.write(f"Terminal={'true' if display_console_window == 'True' else 'false'}\n")
            file.write("Categories=Development;\n")
            file.write(f"Icon={installation_icon_path}\n")
        shortcut_path.chmod(0o755)
        if not os.environ.get("SUDO_USER"):
            user_apps_path = Path("~/.local/share/applications/").expanduser()
            user_apps_path.mkdir(parents=True, exist_ok=True)
            shutil.copy2(shortcut_path, user_apps_path)


def install_tool(
    tool: str,
    virtual_tools_python_exe: Path,
    installation_directory: Path,
    package_metadata: dict[str, Any],
    pip_cache_dir: Path,
    force_reinstall: bool = False,
) -> None:
    tools_directory = installation_directory / "definitions" / package_metadata["solution-module-name"] / "tools"
    requirements_path = tools_directory / f"{tool}_requirements.txt"

    if not requirements_path.is_file():
        raise RuntimeError(f"tools requirements file {requirements_path} does not exist.")

    args = [
        str(virtual_tools_python_exe),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(requirements_path),
    ]

    if force_reinstall:
        args.append("--force-reinstall")

    env = os.environ.copy()
    env["PIP_CACHE_DIR"] = str(pip_cache_dir)

    print(f"installing {tool} into virtual environment")
    subprocess.check_output(args, cwd=tools_directory, env=env, stderr=subprocess.PIPE, text=True)
    print(f"{tool} installed into virtual environment")


def delete_cache(cache: Path) -> None:
    if cache.is_dir():
        print(f"deleting {cache}")
        shutil.rmtree(cache)
    else:
        print(f"no cache directory {cache} to delete")


def delete_entity(f: Path) -> None:
    print(f"deleting {f}")
    if f.is_dir():
        shutil.rmtree(f)
    else:
        f.unlink()


class SolutionInfo(NamedTuple):
    solution_installation_directory: Path
    use_portal: bool


def installation(
    installation_directory: Path,
    package_metadata: dict[str, Any],
    python_interpreter: Path,
    use_pip: bool = False,
) -> SolutionInfo:
    solution_installation_directory: Path = (
        installation_directory / "definitions" / package_metadata["solution-module-name"]
    )
    print("Python interpreter: ", python_interpreter)

    # we create a temporary virtual environment for poetry
    install_tools_venv = "install_tools_venv"
    subprocess.check_output(
        [str(python_interpreter.resolve()), "-m", "venv", install_tools_venv],
        cwd=installation_directory,
        stderr=subprocess.PIPE,
        text=True,
    )
    virtual_tools_directory = installation_directory / install_tools_venv
    virtual_tools_python_exe = get_python_interpreter_in_venv(virtual_tools_directory)
    pip_cache_dir = installation_directory / "pip_cache"
    install_tool(
        "pip",
        virtual_tools_python_exe,
        installation_directory,
        package_metadata,
        pip_cache_dir,
        force_reinstall=True,
    )

    # we always install poetry because we use it to generate a requirements.txt for pip if we use pip
    install_tool("poetry", virtual_tools_python_exe, installation_directory, package_metadata, pip_cache_dir)

    # install the application into a virtual environment in the project directory
    # Prepend the bundled Python's directory to PATH so that Poetry's internal subprocesses
    # (e.g. `python -EsSc 'import sys; print(sys.executable)'`) resolve to the bundled Python
    # rather than a Windows Store app-execution alias.
    poetry_env = os.environ.copy()
    python_interpreter_dir = str(python_interpreter.resolve().parent)
    poetry_env["PATH"] = python_interpreter_dir + os.pathsep + poetry_env.get("PATH", "")

    subprocess.check_output(
        [virtual_tools_python_exe, "-m", "poetry", "config", "--local", "virtualenvs.create", "true"],
        cwd=solution_installation_directory,
        env=poetry_env,
        stderr=subprocess.PIPE,
        text=True,
    )
    subprocess.check_output(
        [virtual_tools_python_exe, "-m", "poetry", "config", "--local", "virtualenvs.in-project", "true"],
        cwd=solution_installation_directory,
        env=poetry_env,
        stderr=subprocess.PIPE,
        text=True,
    )
    poetry_cache_dir = installation_directory / "poetry_cache"
    subprocess.check_output(
        [virtual_tools_python_exe, "-m", "poetry", "config", "--local", "cache-dir", str(poetry_cache_dir)],
        cwd=solution_installation_directory,
        env=poetry_env,
        stderr=subprocess.PIPE,
        text=True,
    )
    # This is necessary to set the python to be used by the application. Otherwise, poetry might default to using
    # the python installed in the system.
    subprocess.check_output(
        [virtual_tools_python_exe, "-m", "poetry", "env", "use", str(python_interpreter.resolve())],
        cwd=solution_installation_directory,
        env=poetry_env,
        stderr=subprocess.PIPE,
        text=True,
    )

    solution_virtual_environment = solution_installation_directory / VIRTUAL_ENVIRONMENT_NAME
    print(f"creating virtual environment containing the solution in {solution_virtual_environment}")
    # poetry install occasionally fails so we run it several times before giving up
    return_code = 1
    remaining_attempts = 0 if use_pip else 5
    while (return_code != 0) and (remaining_attempts != 0):
        return_code = subprocess.run(
            [virtual_tools_python_exe, "-m", "poetry", "install", "--no-root"],
            cwd=solution_installation_directory,
            env=poetry_env,
            stderr=subprocess.PIPE,
            check=False,
        ).returncode
        remaining_attempts -= 1
    if return_code != 0:
        print("installing using pip")

        # poetry install is not so unreliable that it won't install the solution after 5 attempts
        # so it is very unlikely that the following code will be executed
        # but just in case we will extract the requirements using poetry and install them using pip

        install_using_pip(
            installation_directory,
            package_metadata,
            solution_installation_directory,
            virtual_tools_python_exe,
            pip_cache_dir,
            solution_virtual_environment,
        )

    print("created virtual environment containing the solution")
    solution_use_portal = has_portal_dependency(solution_installation_directory)
    print(f"solution uses portal: {solution_use_portal}")
    # the following seems to be OK, the venv in project dir seems to end up independent of the poetry venv
    print(f"deleting {virtual_tools_directory}")
    shutil.rmtree(virtual_tools_directory)

    for wheel in solution_installation_directory.glob("*.whl"):
        delete_entity(wheel)

    delete_cache(pip_cache_dir)
    delete_cache(poetry_cache_dir)

    delete_entity(solution_installation_directory / "pyproject.toml")
    delete_entity(solution_installation_directory / "poetry.lock")
    delete_entity(solution_installation_directory / "poetry.toml")
    requirements_txt = solution_installation_directory / "requirements.txt"
    if requirements_txt.is_file():
        delete_entity(requirements_txt)
    dot_poetry = solution_installation_directory / ".poetry"
    if dot_poetry.exists():
        delete_entity(dot_poetry)
    delete_entity(solution_installation_directory / "tools")

    return SolutionInfo(solution_installation_directory, solution_use_portal)


def install_using_pip(
    installation_directory: Path,
    package_metadata: dict[str, Any],
    solution_installation_directory: Path,
    virtual_tools_python_exe: Path,
    pip_cache_dir: Path,
    solution_virtual_environment: Path,
) -> None:
    if solution_virtual_environment.exists():
        delete_entity(solution_virtual_environment)

    requirements_file_path = solution_installation_directory / "requirements.txt"

    print(f"using poetry to write requirements file {requirements_file_path}")
    # Do not use resolve() on virtual_tools_python_exe, because it returns the path to the embedded python
    # that was used to create virtual_tools_python_exe's virtual environment.
    requirements = subprocess.check_output(
        [
            str(virtual_tools_python_exe),
            "-m",
            "poetry",
            "export",
            "--without-hashes",
            "--format",
            "requirements.txt",
        ],
        cwd=solution_installation_directory,
        stderr=subprocess.PIPE,
        text=True,
    )
    requirements_file_path.write_text(requirements)

    print(f"create virtual environment {solution_virtual_environment} which will contain solution")
    subprocess.check_output(
        [str(virtual_tools_python_exe), "-m", "venv", VIRTUAL_ENVIRONMENT_NAME],
        cwd=solution_installation_directory,
        stderr=subprocess.PIPE,
        text=True,
    )

    installed_python_exe = get_python_interpreter_in_venv(solution_virtual_environment)
    install_tool(
        "pip",
        installed_python_exe,
        installation_directory,
        package_metadata,
        pip_cache_dir,
        force_reinstall=True,
    )

    print(f"using pip install requirements from {requirements_file_path} into {solution_virtual_environment}")
    subprocess.check_output(
        [
            installed_python_exe,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "-r",
            requirements_file_path,
        ],
        cwd=solution_installation_directory,
        stderr=subprocess.PIPE,
        text=True,
    )


def start_installer(args: dict[str, Any]) -> float:
    """Orchestrate the solution deployment."""
    python_interpreter: Path = args["python_interpreter"]
    if not python_interpreter.is_file():
        raise FileNotFoundError(f"Python interpreter not found: {python_interpreter}")

    # Start timer
    time_on = time.time()

    # Load JSON
    with Path.open(args["metadata_file"]) as file:
        package_metadata = json.load(file)

    # Display header
    print("=============================================================================================")
    print(INSTALLER_HEADING)
    print("=============================================================================================")
    print("")
    print("Python interpreter: ", args["python_interpreter"])

    # Setup solution deployment directory
    deployment_directory = ROOT_DIR

    # Check deployment directory
    check_deployment_directory(
        deployment_directory,
        package_metadata["solution-module-name"],
        package_metadata["solution-package-name"],
    )

    # Setup solution installation directory
    installation_directory = get_installation_directory_path(
        args["installation_directory"],
        package_metadata["solution-display-name"],
        package_metadata["solution-version"],
    )

    # Recap parameters
    print("Deployment parameters ---------------------------------------------------------------------")
    print(f"OS                       : {platform.system()}")
    print(f"Python version           : {get_python_version(args['python_interpreter'])}")
    print(f"Deployment directory     : {deployment_directory}")
    print(f"Installation directory   : {installation_directory}")
    print("GLOW package name        : {}".format(package_metadata["glow-package-name"]))
    print("GLOW entry point module  : {}".format(package_metadata["glow-entry-point-module"]))
    print("Solution name            : {}".format(package_metadata["solution-name"]))
    print("Solution module name     : {}".format(package_metadata["solution-module-name"]))
    print("Solution display name    : {}".format(package_metadata["solution-display-name"]))
    print("Solution package name    : {}".format(package_metadata["solution-package-name"]))
    print("Solution main module     : {}".format(package_metadata["solution-main-module"]))
    print("")

    print("Workspace clean-up parameters -------------------------------------------------------------")

    # Check if solution already exists and delete it
    cleanup_workspace(installation_directory, package_metadata["solution-display-name"])
    print("")

    print("Deployment --------------------------------------------------------------------------------")

    # Create installation directory
    print("Create solution installation directory")
    installation_directory.mkdir(parents=True, exist_ok=True)

    # Transfer materials from deployment to installation directory
    print("Deploy material to solution installation directory")
    deploy_materials_for_installation(
        deployment_directory,
        installation_directory,
        package_metadata["solution-module-name"],
        package_metadata["solution-package-name"],
        package_metadata["solution-version"],
        args["python_interpreter"],
    )
    print("")

    print("Installation ------------------------------------------------------------------------------")

    # Move to solution installation folder
    python_dir = installation_directory / "python"
    installation_python_interpreter = get_python_interpreter(python_dir)
    if not installation_python_interpreter:
        raise RuntimeError("Could not find a valid Python interpreter in the installation directory.")
    solution_info = installation(
        installation_directory=installation_directory,
        package_metadata=package_metadata,
        python_interpreter=installation_python_interpreter,
        use_pip=args["use_pip"],
    )

    solution_python_exe, arguments = compute_solution_commandline(
        solution_info.solution_installation_directory,
        package_metadata["glow-entry-point-module"],
        package_metadata["solution-main-module"],
        package_metadata["use-glow"],
        package_metadata["solution-entry-point"],
        display_console_window=package_metadata["display-console-window"],
        solution_use_portal=solution_info.use_portal,
    )

    # Preload application so that the first execution is faster.
    print("Preload application")
    preload_start = time.time()
    preload_python_exe = solution_python_exe.absolute()
    if preload_python_exe.name == "pythonw.exe":
        preload_python_exe = preload_python_exe.parent / "python.exe"
    command_line = [preload_python_exe.as_posix()]
    command_line.extend(arguments)
    command_line.append("--pre-load")
    kwargs: dict[str, Any] = {}
    kwargs["stdout"] = subprocess.PIPE
    kwargs["stderr"] = subprocess.STDOUT

    print(f"Executing: {command_line}")
    print("-" * 90)
    with subprocess.Popen(command_line, **kwargs) as proc:
        if proc.stdout is not None:
            for line in proc.stdout:
                msg = line.decode("utf-8").rstrip()  # type: ignore
                print(msg)  # type: ignore
    print("-" * 90)

    if proc.returncode == 0:
        print("The application completed successfully.")
    else:
        print(f"The application exited with code {proc.returncode}.")
        raise RuntimeError(f"The application exited with code {proc.returncode}")
    print("preload time:", time.time() - preload_start)

    print("Solution Python interpreter: ", solution_python_exe)
    arguments_string = " ".join(arguments)
    print("Solution arguments: ", arguments_string)

    # Install shortcut
    print("Install shortcut")
    shortcut_suffix = ".ico" if platform.system() == "Windows" else ".png"
    installation_icon_path = installation_directory / "assets" / f"shortcut{shortcut_suffix}"
    install_shortcut(
        solution_python_exe,
        installation_icon_path,
        arguments_string,
        package_metadata["solution-display-name"],
        display_console_window=package_metadata["display-console-window"],
    )

    # Compute execution time
    elapsed_time = (time.time() - time_on) / 60  # in minutes
    print(f"Execution time: {elapsed_time:.1f} minutes.")
    print("")
    return elapsed_time


def build_long_path_section(long_path_error: dict[str, str]) -> list[Any]:
    """Build the Dash HTML section listing unmet prerequisites, or return an empty list if all are met."""
    if not long_path_error:
        return []

    return [
        html.Div(
            [
                html.Div(
                    "Prerequisites",
                    style={
                        "font-weight": "600",
                        "margin-bottom": "8px",
                        "font-size": "16px",
                        "font-style": "italic",
                    },
                ),
                html.Li(
                    [
                        html.Img(
                            src="/assets/exclamation-circle-fill.svg",
                            style={
                                "width": "14px",
                                "height": "14px",
                                "margin-right": "6px",
                                "flex-shrink": "0",
                            },
                        ),
                        html.Span(
                            [
                                long_path_error["message"],
                                *(
                                    [
                                        " ",
                                        html.A(
                                            "See instructions.",
                                            href=long_path_error["doc_url"],
                                            target="_blank",
                                            style={
                                                "color": "#007bff",
                                                "text-decoration": "none",
                                                "white-space": "nowrap",
                                            },
                                        ),
                                    ]
                                ),
                            ],
                            style={"line-height": "1.4"},
                        ),
                    ],
                    style={
                        "margin-bottom": "6px",
                        "list-style-type": "none",
                        "display": "flex",
                        "align-items": "flex-start",
                        "font-style": "italic",
                    },
                ),
            ],
            style={
                "border": "1px solid #e0e0e0",
                "border-radius": "6px",
                "padding": "12px",
                "background-color": "#ffffff",
                "width": "100%",
                "margin-bottom": "10px",
            },
        ),
    ]


def form_layout(args: dict[str, Any]) -> html.Div:
    return html.Div(
        id="main",
        style={
            "padding": "10px",
            "width": "75vw" if platform.system() == "Windows" else "50vw",
            "display": "flex",
            "justify-content": "center",
            "flex-direction": "column",
            "align-items": "center",
            "margin": "0 auto",
        },
        children=[
            dbc.Table(
                style={"padding": "10px"},
                children=[
                    html.Tr(
                        html.Img(
                            src="data:image/png;base64,{}".format(
                                base64.b64encode(
                                    (ROOT_DIR / "assets" / "installer_ui_logo.png").open("rb").read(),
                                ).decode(),
                            ),
                            style={
                                "display": "block",
                                "margin": "0 auto",
                                "width": "50%",
                                "margin-bottom": "20px",
                            },
                        ),
                    ),
                    html.Tr(
                        html.Td(
                            html.Div(
                                id="prerequisites-section",
                                style={"padding": "0px"},
                            ),
                            colSpan=1,
                        ),
                    ),
                    html.Tr("Metadata File Location"),
                    html.Tr(
                        dbc.Input(
                            id="input-metadata-file-location",
                            type="text",
                            placeholder="Enter metadata file location",
                            value=args["metadata_file"].as_posix(),
                            style={"width": "100%", "margin-bottom": "10px"},
                        ),
                    ),
                    html.Tr("Installation Location"),
                    html.Tr(
                        dbc.Input(
                            id="input-installation-location",
                            type="text",
                            value=args["installation_directory"].as_posix(),
                            placeholder="Enter location to install the solution",
                            style={"width": "100%", "margin-bottom": "10px"},
                        ),
                    ),
                    html.Tr("Python Interpreter Location"),
                    html.Tr(
                        dbc.Input(
                            id="input-python-interpreter-location",
                            type="text",
                            value=args["python_interpreter"].as_posix(),
                            placeholder="Enter python interpreter or directory containing the python interpreter",
                            style={"width": "100%", "margin-bottom": "10px"},
                        ),
                    ),
                    *(
                        [
                            html.Tr(
                                html.Td(
                                    dbc.Checklist(
                                        id="long-path-check-checkbox",
                                        options=[{"label": "Check Windows Long Paths enabled", "value": "check"}],
                                        value=["check"],
                                        style={"margin": "0", "padding-left": "0"},
                                        inputStyle={"margin-right": "6px"},
                                        labelStyle={"margin-bottom": "0"},
                                    ),
                                    colSpan=1,
                                    style={"padding-top": "2px", "padding-bottom": "8px"},
                                ),
                            ),
                            html.Tr(
                                html.Td(
                                    html.Div(
                                        [
                                            html.Img(
                                                src="/assets/exclamation-circle-fill.svg",
                                                style={
                                                    "width": "14px",
                                                    "height": "14px",
                                                    "margin-right": "6px",
                                                    "flex-shrink": "0",
                                                },
                                            ),
                                            html.Span(
                                                "Windows Long Path check is disabled. "
                                                "We recommend installing the solution at a short path "
                                                "(for example, a disk root such as C:\\) "
                                                "to avoid potential file path issues.",
                                            ),
                                        ],
                                        id="long-path-warning",
                                        style=LONG_PATH_WARNING_HIDDEN_STYLE,
                                    ),
                                    colSpan=1,
                                    style={"padding-top": "0", "padding-bottom": "8px"},
                                ),
                            ),
                        ]
                        if platform.system() == "Windows"
                        else []
                    ),
                    html.Tr(
                        dbc.Button(
                            "Install",
                            id="install-button",
                            color="primary",
                            disabled=False,
                            style=install_button_style(disabled=False),
                        ),
                    ),
                    html.Tr(
                        html.Td(
                            "Prerequisites are not fulfilled. "
                            "Please fix the listed items, then close and relaunch the installer.",
                            id="prerequisites-not-fulfilled-msg",
                            style={"display": "none"},
                        ),
                    ),
                ],
            ),
            html.Div(
                dcc.Loading(
                    id="loading",
                    type="circle",
                    color="#FFBA00",
                    children=[dbc.Alert(id="install-alert", color="success", style={"display": "none"})],
                ),
                style={"width": "100%"},
            ),
        ],
    )


def register_callbacks(app: Dash, args: dict[str, Any]) -> None:
    """Register all callbacks for the Dash app."""

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        [
            Output("input-installation-location", "invalid"),
            Output("install-button", "disabled", allow_duplicate=True),
            Output("install-alert", "children", allow_duplicate=True),
            Output("install-alert", "style", allow_duplicate=True),
            Output("install-alert", "color", allow_duplicate=True),
        ],
        [Input("input-installation-location", "value")],
        prevent_initial_call="initial_duplicate",
    )
    def check_installation_directory(  # pyright: ignore[reportUnusedFunction]
        installation_directory: str,
    ) -> tuple[bool, bool, Any, dict[str, Any], Any]:
        if InstallationDirectoryValidator.directory_is_valid(Path(installation_directory)):
            return (
                False,
                False,
                no_update,
                {"display": "none"},
                no_update,
            )
        else:
            return (
                True,
                True,
                f"The installation directory '{installation_directory}' is not writable. An alternative could be: "
                f"{InstallationDirectoryValidator.get_valid_installation_directory().as_posix()}",
                {"display": "block", "user-select": "text", "cursor": "text"},
                "danger",
            )

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        [
            Output("input-metadata-file-location", "disabled"),
            Output("input-installation-location", "disabled"),
            Output("input-python-interpreter-location", "disabled"),
            Output("install-button", "disabled"),
        ],
        [Input("install-button", "n_clicks")],
        prevent_initial_call=True,
    )
    def disable_inputs(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int,
    ) -> tuple[bool, bool, bool, bool]:
        disabled = bool(n_clicks)
        return disabled, disabled, disabled, disabled

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        [
            Output("install-alert", "children"),
            Output("install-alert", "style"),
            Output("install-alert", "color"),
        ],
        [Input("install-button", "n_clicks")],
        [
            State("input-metadata-file-location", "value"),
            State("input-installation-location", "value"),
            State("input-python-interpreter-location", "value"),
        ],
        prevent_initial_call=True,
    )
    def run_installer(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int,
        input1_value: str,
        input2_value: str,
        input3_value: str,
    ) -> tuple[str, dict[str, str], Any]:
        if n_clicks:
            print("Running installer")
            execution_time: float | None = None
            error: str | None = None
            new_args = {
                "metadata_file": Path(input1_value),
                "installation_directory": Path(input2_value),
                "python_interpreter": Path(input3_value),
                "use_pip": args["use_pip"],
            }
            try:
                execution_time = round(start_installer(new_args), 2)
            except subprocess.CalledProcessError as e:
                error = f"Command {e.cmd} failed with the following error: {e.stderr}"
            except Exception as e:
                error = f"The following error occurred: {e}"

            if error:
                return error, {"display": "block", "user-select": "text", "cursor": "text"}, "danger"
            else:
                return f"Installation completed in {execution_time} minutes.", {"display": "block"}, "success"

        return "", {"display": "none"}, no_update

    if platform.system() == "Windows":
        _register_toggle_long_path_check_callback(app)


def _register_toggle_long_path_check_callback(app: Dash) -> None:
    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        [
            Output("prerequisites-section", "children"),
            Output("prerequisites-not-fulfilled-msg", "style"),
            Output("install-button", "disabled", allow_duplicate=True),
            Output("install-button", "style", allow_duplicate=True),
            Output("long-path-warning", "style"),
        ],
        [Input("long-path-check-checkbox", "value")],
        prevent_initial_call="initial_duplicate",
    )
    def toggle_long_path_check(  # pyright: ignore[reportUnusedFunction]
        checkbox_value: list[str],
    ) -> tuple[list[Any], dict[str, Any], bool, dict[str, Any], dict[str, Any]]:
        check_long_paths = bool(checkbox_value)
        long_path_error: dict[str, str] = {}
        if platform.system() == "Windows" and check_long_paths and not is_long_paths_enabled():
            long_path_error = {
                "message": "Windows Long Paths is not enabled.",
                "doc_url": "https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation",
            }
        install_button_disabled = bool(long_path_error)
        return (
            build_long_path_section(long_path_error),
            {**PREREQUISITES_NOT_FULFILLED_MSG_STYLE_BASE, "display": "none" if not long_path_error else "block"},
            install_button_disabled,
            install_button_style(disabled=install_button_disabled),
            LONG_PATH_WARNING_HIDDEN_STYLE if check_long_paths else LONG_PATH_WARNING_SHOWN_STYLE,
        )


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return True
        except OSError:
            return False


def get_random_port() -> int:
    while True:
        port = random.randint(40000, 65000)  # noqa: S311
        if is_port_free(port):
            return port


def start_webview(port: int) -> None:
    pywebview.create_window(INSTALLER_HEADING, f"http://localhost:{port}", width=800, height=520, resizable=False)  # pyright: ignore[reportUnknownMemberType]
    pywebview.start()


def start_dash(args: dict[str, Any], port: int) -> None:
    app = Dash(
        INSTALLER_HEADING,
        assets_folder=str(ROOT_DIR / "assets"),
        meta_tags=[
            {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        ],
        title=INSTALLER_HEADING,
    )

    app.layout = form_layout(args)

    register_callbacks(app, args)

    app.run(  # pyright: ignore[reportUnknownMemberType]
        port=str(port),
        debug=False,
        dev_tools_silence_routes_logging=True,
        dev_tools_hot_reload=False,
    )


def _start_installer_gui(args: dict[str, Any], port: int) -> None:
    dash_process = mp.Process(target=start_dash, args=(args, port))
    dash_process.start()
    try:
        if platform.system() == "Windows":
            webview_process = mp.Process(target=start_webview, args=(port,))
            webview_process.start()
            webview_process.join()
        else:
            ui_url = f"http://localhost:{port}"
            print(f"Starting installer UI at {ui_url}")
            print("Press Ctrl+C to exit...")
            webbrowser.open(ui_url)
            dash_process.join()
    except KeyboardInterrupt:
        pass
    finally:
        if dash_process.is_alive():
            dash_process.terminate()
            dash_process.join(timeout=5)


def _start_installer_cli(args: dict[str, Any]) -> None:
    execution_time: float | None = None
    error: str | None = None
    try:
        execution_time = start_installer(args)
    except subprocess.CalledProcessError as e:
        error = f"Command {e.cmd} failed with the following error: {e.stderr}"
    except Exception as e:
        error = f"The following error occurred: {e}"
    if error:
        print(error)
        sys.exit(1)
    else:
        print(f"Installation completed in {execution_time} minutes.")


class InstallationDirectoryValidator:
    """Cross-platform installation directory validator."""

    @staticmethod
    def directory_is_valid(path: Path) -> bool:
        if path.exists() and not path.is_dir():
            return False
        parent = path
        while not parent.is_dir():
            if parent == parent.parent:
                return False
            parent = parent.parent
        test_file = parent / f"test_write_{uuid.uuid4().hex}.txt"
        try:
            with test_file.open("w") as f:
                f.write("This should fail if directory is read-only.")
            return True
        except Exception:
            return False
        finally:
            test_file.unlink(missing_ok=True)

    @classmethod
    def _get_valid_windows_installation_directory(cls) -> Path:
        installation_dir_candidates: list[Path] = []
        if os.environ.get("PROGRAMW6432"):
            installation_dir = Path(os.environ["PROGRAMW6432"]) / "ANSYS Inc" / TARGET_SOLUTIONS_DIRECTORY_NAME
            installation_dir_candidates.append(installation_dir)
        if installation_dir := os.environ.get("APPDATA"):
            installation_dir = Path(installation_dir) / "ANSYS Inc" / TARGET_SOLUTIONS_DIRECTORY_NAME
            installation_dir_candidates.append(installation_dir)
        installation_dir_candidates.append(
            Path.home() / "AppData" / "Roaming" / "ANSYS Inc" / TARGET_SOLUTIONS_DIRECTORY_NAME,
        )
        installation_dir_candidates.append(
            Path.home() / "ANSYS Inc" / TARGET_SOLUTIONS_DIRECTORY_NAME,
        )

        for installation_dir in installation_dir_candidates:
            if cls.directory_is_valid(installation_dir):
                return installation_dir
        return Path.home()

    @classmethod
    def _get_valid_linux_installation_directory(cls) -> Path:
        if os.environ.get("SUDO_USER"):
            installation_dir = Path("/opt") / "ansys_inc" / TARGET_SOLUTIONS_DIRECTORY_NAME
            if cls.directory_is_valid(installation_dir):
                return installation_dir
            return Path("/usr") / "local" / "share" / "ansys_inc" / TARGET_SOLUTIONS_DIRECTORY_NAME
        else:
            installation_dir = Path.home() / ".local" / "share" / "ansys_inc" / TARGET_SOLUTIONS_DIRECTORY_NAME
            if cls.directory_is_valid(installation_dir):
                return installation_dir
            return Path.home()

    @classmethod
    def get_valid_installation_directory(cls) -> Path:
        if platform.system() == "Windows":
            return cls._get_valid_windows_installation_directory()
        else:
            return cls._get_valid_linux_installation_directory()

    @classmethod
    def validate_cli_installation_directory(cls, installation_directory: Path, no_ui: bool) -> Path:
        install_dir_is_valid = cls.directory_is_valid(installation_directory)
        if not install_dir_is_valid and no_ui:
            print(
                f"Error: The specified installation directory '{installation_directory.as_posix()}' "
                "is not writable. An alternative could be: "
                f"'{cls.get_valid_installation_directory().as_posix()}'",
            )
            sys.exit(1)
        elif not install_dir_is_valid:
            print(
                f"Warning: The specified installation directory '{installation_directory.as_posix()}' "
                f"is not writable. The installer UI will allow you to choose a valid directory.",
            )

        return installation_directory


@click.command()
@click.option("-n", "--no-ui", is_flag=True, help="Do not start the UI", default=False, required=False)
@click.option(
    "-m",
    "--metadata-file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True, path_type=Path),
    help="JSON file with the Solution metadata.",
    default=ROOT_DIR / "solution-metadata.json",
    required=False,
)
@click.option(
    "-i",
    "--installation-directory",
    type=click.Path(resolve_path=True, path_type=Path),
    help="Installation directory",
    default=InstallationDirectoryValidator.get_valid_installation_directory,
    required=False,
)
@click.option(
    "-p",
    "--python-interpreter",
    type=click.Path(file_okay=True, resolve_path=True, path_type=Path),
    help="Python interpreter to be used for the installation of the solution.",
    required=False,
)
@click.option(
    "-x",
    "--use-pip",
    "--use_pip",
    is_flag=True,
    help="Use pip to perform the installation",
    default=False,
    required=False,
)
@click.option(
    "-P",
    "--port",
    type=int,
    help="Port to use for the installation",
    default=get_random_port(),
    required=False,
)
@click.pass_context
def main(  # noqa: C901
    ctx: click.Context,
    metadata_file: Path,
    installation_directory: Path,
    python_interpreter: Path | None,
    no_ui: bool,
    use_pip: bool,
    port: int,
):
    print("Checking prerequisites...")
    # Errors that can be shown in the installer UI (pywebview is still functional).
    if platform.system() == "Windows":
        errors: list[str] = []
        # Pywebview, which is used for this installer GUI and also for the Solution UI, requires WebView2
        # runtime to be installed on Windows.  Without it the GUI cannot open at all.
        webview2_installed, webview2_version = is_webview2_installed()
        print(f"- Microsoft Edge WebView2 Runtime: {webview2_version if webview2_installed else 'Not'} installed")
        if not webview2_installed:
            errors.append(WEBVIEW2_ERROR_MSG)

        # Installation paths typically exceed 260 characters on Windows.
        long_paths_enabled = is_long_paths_enabled()
        print(f"- Windows Long Path enabled: {long_paths_enabled}")
        if not long_paths_enabled:
            errors.append(LONG_PATHS_ERROR_MSG)

        for error in errors:
            print(error)

        if not webview2_installed:
            # The installer GUI (pywebview) cannot start without WebView2 — and neither can the Solution UI.
            # Exit unconditionally regardless of whether --no-ui was specified.
            input("Press any key to exit...")
            sys.exit(1)

        if not long_paths_enabled:
            if no_ui:
                print(
                    "Use the installer UI to bypass the Windows Long Paths check. "
                    "The solution might not work properly if Windows Long Paths is not enabled.",
                )
                input("Press any key to exit...")
                sys.exit(1)
            print("Launching installer UI with Windows Long Paths prerequisite not satisfied.")

    if ctx.get_parameter_source("installation_directory") == click.core.ParameterSource.COMMANDLINE:
        installation_directory = InstallationDirectoryValidator.validate_cli_installation_directory(
            installation_directory,
            no_ui,
        )

    args: dict[str, Any] = {
        "metadata_file": metadata_file,
        "installation_directory": installation_directory,
        "use_pip": use_pip,
    }

    if python_interpreter and python_interpreter.is_file():
        args["python_interpreter"] = python_interpreter
    else:
        if python_interpreter:
            print(f"Warning: Specified Python interpreter {python_interpreter} is not a valid file.")
        _ensure_third_party_extracted()
        python_dir = ROOT_DIR / "third_party" / "python"
        python_interpreter = get_python_interpreter(python_dir)
        if python_interpreter:
            args["python_interpreter"] = python_interpreter
        elif not no_ui:
            args["python_interpreter"] = PYTHON_NOT_FOUND
        else:
            raise RuntimeError("Could not find a valid Python interpreter in the deployment directory.")

    if not no_ui:
        _start_installer_gui(args, port)
    else:
        _start_installer_cli(args)


if __name__ == "__main__":
    mp.freeze_support()
    main()
