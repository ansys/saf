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

Solution Package Utility.

"""

########################################################################################################################
# Imports
########################################################################################################################
import logging
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

from ansys.saf.desktop.installer._package.backend_detection import SolutionBackend, detect_solution_backend
from ansys.saf.desktop.installer._package.config import InstallerConfig
from ansys.saf.desktop.installer._package.manage_dependencies import (
    build_and_stage_solution_packages,
    create_poetry_installation_project,
    create_venv_in_definitions_folder,
    download_embeddable_python,
    get_definitions_folder,
    write_backend_tool_requirements,
)
from ansys.saf.desktop.installer._package.solution import (
    SolutionInfo,
    build_and_embed_documentation,
    copy_configuration_files,
    create_env_file,
    create_solution_metadata,
    create_version_file,
    move_assets_and_deployment_script,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

########################################################################################################################
# Variables
########################################################################################################################
WHL_CONSTANT = "*.whl"
REQ_FILE = "requirements.txt"

########################################################################################################################
# Functions
########################################################################################################################


def initial_cleanup(solution_root_dir: Path) -> None:
    """Delete dist folder.

    Args:
        solution_root_dir (Path): Path to the solution root directory.
    """
    dist_folder = solution_root_dir / "dist"
    if not dist_folder.exists():
        return
    logger.info("Cleaning dist folder")
    for path in sorted(dist_folder.rglob("*"), reverse=True):
        if "third_party" in str(path):
            continue
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.resolve() != dist_folder / "solution":
            shutil.rmtree(path)


def setup_solution_folder(
    solution_info: SolutionInfo,
    installer_config: InstallerConfig,
) -> None:
    logger.info("Setting up solution folder containing all necessary files for packaging and distribution.")

    solution_folder = solution_info.solution_root_dir / "dist" / "solution"
    if not solution_folder.exists():
        solution_folder.mkdir(parents=True)

    third_party_folder = solution_folder / "third_party"
    if not third_party_folder.exists():
        third_party_folder.mkdir(parents=True)

    build_and_embed_documentation(solution_info.solution_root_dir, solution_info.solution_module_name)

    create_solution_metadata(solution_info, installer_config)

    create_version_file(
        solution_info.solution_root_dir,
        solution_info.solution_display_name,
        solution_info.solution_version,
    )

    move_assets_and_deployment_script(
        solution_folder,
        solution_info.solution_root_dir,
        solution_info.solution_module_name,
    )

    definitions_folder = get_definitions_folder(
        solution_info.solution_root_dir,
        solution_info.solution_module_name,
    )

    downloaded_python_exec, python_version = download_embeddable_python(solution_folder, installer_config)

    # We create a virtual environment with the selected python version to download the appropriate
    # version of the dependencies. This is particularly important when using the offline packaging option,
    # but can also be necessary even if this option is not used, as the internal dependencies, which are always
    # downloaded, have different versions for different Python versions.
    backend = detect_solution_backend(solution_info.solution_root_dir).backend
    definitions_venv, venv_python_exec = create_venv_in_definitions_folder(
        definitions_folder,
        downloaded_python_exec,
        backend,
    )

    write_backend_tool_requirements(
        solution_info.solution_root_dir,
        solution_info.solution_module_name,
        venv_python_exec,
        backend,
    )

    build_and_stage_solution_packages(
        definitions_folder,
        venv_python_exec,
        solution_info.solution_root_dir,
        solution_info.solution_module_name,
        solution_info.solution_display_name,
        installer_config,
        python_version,
        backend,
    )

    if backend is SolutionBackend.POETRY:
        create_poetry_installation_project(
            venv_python_exec,
            installer_config.pyproject_location,
            definitions_folder,
            python_version,
        )

    create_env_file(solution_info.solution_root_dir, solution_info.solution_module_name)

    copy_configuration_files(solution_info.solution_root_dir, solution_info.solution_module_name)

    if definitions_venv.is_dir():
        shutil.rmtree(definitions_venv)

    if installer_config.exclude_python and (python_directory := third_party_folder / "python").is_dir():
        shutil.rmtree(python_directory)


def run_pyinstaller(pyinstaller_args: list[str], solution_folder: Path) -> subprocess.CompletedProcess[bytes]:
    """Run pyinstaller command.

    Args:
        pyinstaller_args (List[str]): Pyinstaller arguments.
        solution_folder (Path): Solution folder.

    Returns:
        subprocess.CompletedProcess[bytes]: Output.
    """
    if platform.system() == "Windows":
        output = subprocess.run(
            pyinstaller_args,
            cwd=solution_folder,
            capture_output=True,
        )
    else:
        for i, arg in enumerate(pyinstaller_args):
            if "\\" in arg or "\\\\" in arg:
                arg = arg.replace("\\", "/")
                pyinstaller_args[i] = arg
            if ";" in arg:
                arg = arg.replace(";", ":")
                pyinstaller_args[i] = arg
        output = subprocess.run(
            pyinstaller_args,
            cwd=solution_folder,
            capture_output=True,
        )
    return output


def _get_pyinstaller_exec_path() -> Path:
    # To generate a working solution installer, pyinstaller needs access to the dependencies of the solution.
    # This requires pyinstaller to be installed in the same environment as these dependencies. That's why we
    # prioritize the pyinstaller executable that is installed in the solution's environment over a possible
    # pyinstaller executable in the active environment.
    pyinstaller_path = Path(sys.executable).parent / "pyinstaller"
    if pyinstaller_path.is_file():
        return pyinstaller_path
    elif pyinstaller_path.with_suffix(".exe").is_file():
        return pyinstaller_path.with_suffix(".exe")
    elif pyinstaller_path.with_suffix(".cmd").is_file():
        return pyinstaller_path.with_suffix(".cmd")

    pyinstaller_path = shutil.which("pyinstaller")
    if pyinstaller_path:
        return Path(pyinstaller_path)

    raise RuntimeError("Pyinstaller not found.")


def _zip_third_party(solution_folder: Path) -> Path | None:
    """Compress the entire ``third_party/`` directory into a ZIP archive before running PyInstaller.

    PyInstaller 6.x on Windows scans DLL files found in ``--add-data`` source paths and
    promotes them to the ``_MEIPASS`` root.  Any DLL inside ``third_party/`` that shares a
    filename with a DLL needed by the frozen application (e.g. ``libssl-3.dll``,
    ``libcrypto-3.dll``) will overwrite the correct build-environment version, causing
    ``ImportError: DLL load failed while importing _ssl`` at startup.

    Compressing the entire ``third_party/`` directory into a single ZIP makes it completely
    opaque to PyInstaller's binary scanner: ZIP archives have no PE header and are never
    analysed for DLL dependencies, so no promotion can occur regardless of what is added to
    ``third_party/`` in the future.  The directory is restored by
    :func:`_restore_third_party` after PyInstaller finishes.

    Only applicable on Windows where DLL filename collisions can occur.  Returns ``None``
    on other platforms or when ``third_party/`` does not exist.
    """
    if platform.system() != "Windows":
        return None
    third_party_dir = solution_folder / "third_party"
    if not third_party_dir.is_dir():
        return None
    third_party_zip = solution_folder / "third_party.zip"
    logger.info(
        f"Compressing {third_party_dir} into {third_party_zip} to prevent DLL conflicts in PyInstaller bundle.",
    )
    with zipfile.ZipFile(third_party_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(third_party_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(third_party_dir))
    shutil.rmtree(third_party_dir)
    logger.info("third_party/ compressed and removed before PyInstaller analysis.")
    return third_party_zip


def _restore_third_party(solution_folder: Path, third_party_zip: Path | None) -> None:
    """Restore the ``third_party/`` directory from its ZIP after PyInstaller has finished.

    Pairs with :func:`_zip_third_party`.  Always called from a ``finally`` block so the
    directory is restored even when PyInstaller exits with a non-zero code.
    """
    if third_party_zip is None or not third_party_zip.is_file():
        return
    third_party_dir = solution_folder / "third_party"
    logger.info(f"Restoring {third_party_dir} from {third_party_zip}.")
    third_party_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(third_party_zip, "r") as zf:
        zf.extractall(third_party_dir)
    third_party_zip.unlink()
    logger.info("third_party/ directory restored and third_party.zip deleted.")


def build_executable_installer(
    solution_folder: Path,
    output_folder: Path,
    solution_display_name: str,
    executable_as_dir: bool = False,
) -> None:
    """Build executable installer.

    Args:
        solution_folder (Path): Path to the solution folder.
        output_folder (Path): Path to the output folder.
        solution_display_name (str): Display name of the solution.
    """
    exe_name = solution_display_name.lower().replace(" ", "-") + "-installer"
    logger.info(f"Building executable installer from {solution_folder}")
    pyinstaller_exec = _get_pyinstaller_exec_path()
    # TODO: this list seems to be very arbitrary. We need to investigate further.
    exclude_modules = [
        "scipy",
        "sphinx",
        "numpy",
        "matplotlib",
        "pandas",
        "ansys-saf-desktop-installer",
        "ansys-saf-desktop-orchestrator",
        "ansys-saf-glow-engine",
        "ansys-saf-portal",
        "ansys-saf-desktop-portal",
        "ansys-sphinx-theme",
        "ansys-translation-utilities",
        "pytest",
    ]

    pyinstaller_args = [
        pyinstaller_exec.as_posix(),
        "--onedir" if executable_as_dir else "--onefile",
        "--noconfirm",
        "--clean",
        ".\\solution_desktop_deployment.py",
        "--name",
        exe_name,
        "--icon",
        f".\\assets\\favicon{'.ico' if platform.system() == 'Windows' else '.png'}",
        "--hidden-import",
        "_struct",
        "--copy-metadata",
        "typing_extensions",
        "--add-data",
        ".\\assets\\;.\\assets\\",
        "--add-data",
        ".\\definitions\\;.\\definitions\\",
        # On Windows third_party/ is compressed into third_party.zip before PyInstaller runs
        # (see _zip_third_party) so no DLL inside it can be promoted to _MEIPASS root.
        # On Linux the directory is passed directly as usual.
        "--add-data",
        ".\\third_party.zip;." if platform.system() == "Windows" else ".\\third_party\\;.\\third_party\\",
        "--add-data",
        ".\\solution-metadata.json;.",
        "--add-data",
        ".\\version.txt;.",
        "--distpath",
        str(output_folder),
    ]
    for module in exclude_modules:
        pyinstaller_args.extend(["--exclude-module", module])
    # Compress the entire third_party/ directory so PyInstaller's binary scanner cannot
    # see any DLL inside it. Without this, DLLs from the embedded Python NuGet package
    # (e.g. libssl-3.dll, libcrypto-3.dll) share filenames with the build-environment
    # Python's DLLs but carry a different OpenSSL version; PyInstaller promotes them to
    # _MEIPASS root and overwrites the correct versions, causing _ssl import failure.
    third_party_zip = _zip_third_party(solution_folder)
    try:
        output = run_pyinstaller(pyinstaller_args, solution_folder)
    finally:
        _restore_third_party(solution_folder, third_party_zip)
    # remove the spec file
    spec_file = solution_folder / f"{exe_name}.spec"
    if spec_file.exists():
        spec_file.unlink()
    if output.returncode != 0:
        logger.error(f"Failed to build executable installer: {output.stderr}")
        sys.exit(1)
    logger.info("Executable installer built successfully")
    # remove the build folder
    build_folder = solution_folder / "build"
    if build_folder.exists():
        shutil.rmtree(build_folder)
    exe_path = output_folder / exe_name / exe_name if executable_as_dir else output_folder / exe_name
    print(f"Executable installer located in {exe_path.with_suffix('.exe' if platform.system() == 'Windows' else '')}")
