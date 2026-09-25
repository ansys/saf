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

from collections.abc import Callable
import hashlib
from pathlib import Path
import platform
import re
import subprocess
import tarfile
import tempfile
import zipfile

from packaging.markers import Marker
from packaging.version import Version
import toml


def matches_current_platform(markers: str) -> bool:
    """Check if the markers string matches the current platform."""
    try:
        return Marker(markers).evaluate()
    except Exception:
        return False


def filter_metadata_platform_specific_dependencies(metadata_path: Path) -> str:
    """Filter out platform-specific dependencies from METADATA content."""
    filtered_lines: list[str] = []
    metadata_content = metadata_path.read_text(encoding="utf-8")
    for line in metadata_content.splitlines():
        if line.startswith("Requires-Dist:"):
            if ";" in line:
                marker_part = line.split(";")[1].strip()
                if "extra ==" not in marker_part and not matches_current_platform(
                    marker_part,
                ):
                    continue
            filtered_lines.append(line)
        else:
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def _modify_wheel_metadata(
    wheel_path: Path,
    metadata_transform: Callable[[str], str],
) -> None:
    """Common logic to modify a wheel's METADATA file.

    Args:
        wheel_path: Path to the wheel file to modify
        metadata_transform: Function that transforms the metadata content
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Extract the wheel
        with zipfile.ZipFile(wheel_path, "r") as zip_in:
            safe_extract(zip_in, tmpdir_path)

        # Read and modify the METADATA file
        metadata_path = next(tmpdir_path.glob("*.dist-info/METADATA"), None)
        if metadata_path is None:
            raise FileNotFoundError(f"Missing METADATA file in: {tmpdir_path}")

        metadata_content = filter_metadata_platform_specific_dependencies(metadata_path)

        # Apply the transformation
        new_metadata_content = metadata_transform(metadata_content)

        metadata_path.write_text(new_metadata_content, encoding="utf-8")

        # Re-create the wheel
        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for file_path in tmpdir_path.rglob("*"):
                if file_path.is_file():
                    zip_out.write(file_path, file_path.relative_to(tmpdir_path))


def modify_solution_wheel_metadata(
    solution_installation_directory: Path,
    solution_package_name: str,
    solution_version: str,
) -> None:
    """Modify solution wheel metadata to fix local wheel dependency paths."""
    solution_wheel_package_name = solution_package_name.replace("-", "_")
    solution_wheel = (
        solution_installation_directory / f"{solution_wheel_package_name}-{solution_version}-py3-none-any.whl"
    )
    if not solution_wheel.is_file():
        raise FileNotFoundError(f"Missing solution wheel at: {solution_wheel}")

    def transform_metadata(metadata_content: str) -> str:
        """Transform metadata to point to the new installation directory."""
        pattern = re.compile(
            r"^(Requires-Dist:\s*[^@]+@)\s*file:///.+?([^/\\]+\.whl)(.*)$",
            re.MULTILINE,
        )
        solution_installation_directory_str = solution_installation_directory.as_posix().replace(" ", "%20")
        if platform.system() == "Windows":
            sub_str = rf"\1 file:///{solution_installation_directory_str}/\2\3"
        elif platform.system() == "Linux":
            sub_str = rf"\1 file://{solution_installation_directory_str}/\2\3"
        else:
            raise RuntimeError("Unsupported operating system.")
        return pattern.sub(sub_str, metadata_content)

    _modify_wheel_metadata(solution_wheel, transform_metadata)

    # If poetry.lock exists, update it with the new hash of the modified wheel
    poetry_lock_path = solution_installation_directory / "poetry.lock"
    if poetry_lock_path.is_file():
        new_sha = f"sha256:{hashlib.sha256(solution_wheel.read_bytes()).hexdigest()}"
        poetry_lock_content = poetry_lock_path.read_text(encoding="utf-8")
        pattern = re.compile(
            rf'(\{{\s*file\s*=\s*"{re.escape(solution_wheel.name)}",\s*hash\s*=\s*")sha256:[0-9a-f]+"\s*\}}',
        )
        new_poetry_lock_content = pattern.sub(rf'\1{new_sha}" }}', poetry_lock_content)
        poetry_lock_path.write_text(new_poetry_lock_content, encoding="utf-8")


def _get_installed_package_version(package_name: str) -> str:
    """Get the installed version of a package using pip show."""
    try:
        # Need to use solution's Python as the package is not available yet
        # in the definitions environment
        result = subprocess.run(
            ["pip", "show", package_name],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to get version for package {package_name}: {e}",
        ) from e
    raise ValueError(
        f"Could not determine installed version for package: {package_name}",
    )


def simplify_wheel_dependency_constraints(wheel_path: Path) -> None:
    """Simplify wheel metadata by removing version constraints and URLs from dependencies.

    This is useful for packages that have dependencies with wheel URL sources,
    preventing Poetry solver conflicts. Only modifies dependencies that have HTTP(S) wheel URLs.

    Args:
        wheel_path: Path to the wheel file to modify
    """
    if not wheel_path.is_file():
        return

    def transform_metadata(metadata_content: str) -> str:
        """Simplify Requires-Dist lines that have wheel URL dependencies."""
        pattern = re.compile(
            r"^Requires-Dist:\s*([^\s@]+)\s*@\s*https?://[^\s]+\.whl",
            re.MULTILINE,
        )

        def replace_func(match: re.Match[str]) -> str:
            package_name = match.group(1)
            package_version = _get_installed_package_version(package_name)
            return f"Requires-Dist: {package_name}=={package_version}"

        return pattern.sub(replace_func, metadata_content)

    _modify_wheel_metadata(wheel_path, transform_metadata)


def _get_poetry_version() -> Version:
    """Get the Poetry version installed in the solution."""
    try:
        poetry_version_str = subprocess.check_output(["poetry", "--version"], text=True)  # noqa: S607
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get Poetry version: {e}") from e
    match = re.search(r"\d+\.\d+\.\d+", poetry_version_str)
    if not match:
        raise RuntimeError(
            f"Could not parse Poetry version from output: {poetry_version_str}",
        )
    poetry_version = match.group()
    return Version(poetry_version)


def _check_poetry_version_is_2_or_higher() -> bool:
    """Check if the installed Poetry version is 2.0.0 or higher."""
    return _get_poetry_version() >= Version("2.0.0")


def check_poetry_plugin_export_is_required(offline_package: bool) -> bool:
    if offline_package and _check_poetry_version_is_2_or_higher():
        return subprocess.run(["poetry", "export"], capture_output=True, text=True).returncode != 0  # noqa: S607
    return False


def safe_extract(file: zipfile.ZipFile | tarfile.TarFile, target_dir: Path) -> None:
    """Safely extract an archive file, validating all members to prevent path traversal attacks."""
    target_dir = target_dir.resolve()
    members = file.namelist() if isinstance(file, zipfile.ZipFile) else file.getmembers()
    for member in members:
        member_name = member if isinstance(member, str) else member.name
        member_path = (target_dir / member_name).resolve()
        # Ensure the member path is within the target directory
        if not member_path.is_relative_to(target_dir):
            raise ValueError(f"Attempted path traversal in archive file: {member_name}")
        file.extract(member, target_dir)  # pyright: ignore[reportArgumentType]


def has_portal_dependency(solution_root_dir: Path) -> bool:
    """Check if the solution uses the SAF Portal by looking for
    ansys-saf-desktop-portal or ansys-saf-portal in the poetry.lock"""
    poetry_lock_data = toml.load(solution_root_dir / "poetry.lock")
    for package in poetry_lock_data["package"]:
        if package["name"] in ["ansys-saf-desktop-portal", "ansys-saf-portal"]:
            return True
    return False
