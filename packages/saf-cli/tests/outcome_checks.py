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

import ast
import json
from pathlib import Path
import platform
import subprocess
import sys

import httpx2
import tomlkit

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_NAME, DEFAULT_SOLUTION_NAMESPACE, SOLUTION_TEMPLATE_PATH
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._utilities.conversion import namespace_to_path
from ansys.saf.testing.common import find_exec_in_venv

################################################# Solution Scaffolding #################################################


def _get_expected_scaffolded_solution_files(
    solution_module_name: str,
    ui_framework: str,
    namespace: str = DEFAULT_SOLUTION_NAMESPACE,
) -> list[str]:
    solution_template_dir = SOLUTION_TEMPLATE_PATH / "{{cookiecutter.__solution_name}}"
    namespace_path = namespace_to_path(namespace)
    expected_scaffolded_files: list[str] = []
    for x in list(solution_template_dir.rglob("*")):
        if x.is_file():
            expected_scaffolded_files.append(x.relative_to(solution_template_dir).as_posix())

    # replace lock_files with a single one
    expected_scaffolded_files = [
        file_str for file_str in expected_scaffolded_files if not file_str.startswith("lock_files")
    ]
    expected_scaffolded_files.append("poetry.lock")

    # filter ui files if needed
    if ui_framework == "none":
        expected_scaffolded_files = [
            file_str
            for file_str in expected_scaffolded_files
            if not file_str.startswith(
                "src/{{ cookiecutter.__solution_namespace_path }}/{{cookiecutter.__solution_module_name}}/ui",
            )
        ]

    # remove solution ui test file is needed
    if ui_framework == "none":
        expected_scaffolded_files = [
            file_str for file_str in expected_scaffolded_files if file_str != "tests/unit/test_solution_ui.py"
        ]

    # replace all placeholders
    expected_scaffolded_files = [
        file_str.replace("{{ cookiecutter.__solution_namespace_path }}", namespace_path).replace(
            "{{cookiecutter.__solution_module_name}}",
            solution_module_name,
        )
        for file_str in expected_scaffolded_files
    ]

    return expected_scaffolded_files


def check_scaffolded_solution_files(
    root_dir: Path,
    solution_name: str,
    solution_module_name: str,
    ui_framework: str,
    namespace: str = DEFAULT_SOLUTION_NAMESPACE,
):
    scaffolded_solution_dir = root_dir / solution_name
    assert scaffolded_solution_dir.is_dir()
    expected_scaffolded_files = _get_expected_scaffolded_solution_files(
        solution_module_name,
        ui_framework,
        namespace=namespace,
    )
    scaffolded_files = [
        file.relative_to(scaffolded_solution_dir).as_posix()
        for file in scaffolded_solution_dir.rglob("*")
        if file.is_file()
    ]
    assert sorted(expected_scaffolded_files) == sorted(scaffolded_files)


_MODULE_PLACEHOLDER = "__SOLUTION_MODULE_NAME__"
_NAMESPACE_PLACEHOLDER = "__NAMESPACE_PATH__"

# Complete expected file structure of a scaffolded solution with the dash UI framework.
# For the "none" UI framework, entries under the UI path prefix and tests/unit/test_solution_ui.py are excluded.
# This list must be kept in sync with the solution template at:
#   src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/
# NOTE: Use __NAMESPACE_PATH__ placeholder for namespace-dependent paths.
# It will be replaced with the actual namespace path.
EXPECTED_SOLUTION_TEMPLATE_STRUCTURE = [
    # Root files
    ".devcontainer/devcontainer.json",
    ".codespell.ignore",
    ".env",
    ".flake8",
    ".gitignore",
    ".pre-commit-config.yaml",
    "AGENTS.md",
    "CHANGELOG.md",
    "poetry.lock",
    "pyproject.toml",
    "README.md",
    # .github
    ".github/labeler.yml",
    ".github/labels.yml",
    ".github/workflows/build-image.yml",
    ".github/workflows/build-release.yml",
    ".github/workflows/label.yml",
    # .vscode
    ".vscode/extensions.json",
    ".vscode/launch.json",
    # deployments
    "deployments/Dockerfile",
    "deployments/README.md",
    "deployments/distributed-deployment-template/.env",
    "deployments/distributed-deployment-template/compose.yaml",
    "deployments/external/.env",
    "deployments/external/compose.yaml",
    "deployments/standalone/.env",
    "deployments/standalone/compose.yaml",
    "deployments/standalone-with-hps/.env",
    "deployments/standalone-with-hps/compose.yaml",
    # doc
    "doc/source/_static/css/custom.css",
    "doc/source/conf.py",
    "doc/source/index.rst",
    "doc/.vale.ini",
    "doc/make.bat",
    "doc/Makefile",
    # src - solution module (common)
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/main.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/__init__.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/portal_assets/application.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/portal_assets/description.json",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/portal_assets/project.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/solution/definition.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/solution/first_step.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/solution/second_step.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/solution/method_assets/README.md",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/solution/scripts/README.md",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/solution/scripts/assets/README.md",
    # src - solution module (UI - dash only)
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/app.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/css/all.css",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/css/bootstrap.min.css",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/css/style.css",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/dark/carbon--ibm-engineering-workflow-mgmt.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/dark/carbon--return.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/dark/game-icons--crossed-air-flows.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/dark/material-symbols--home.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/dark/radix-icons--moon.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/dark/radix-icons--sun.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/dark/streamline--startup-solid.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/dark/teenyicons--doc-solid.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/light/carbon--ibm-engineering-workflow-mgmt.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/light/carbon--return.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/light/game-icons--crossed-air-flows.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/light/material-symbols--home.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/light/radix-icons--moon.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/light/radix-icons--sun.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/light/streamline--startup-solid.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/icons/light/teenyicons--doc-solid.svg",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/images/README.md",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/images/workflow-placeholder.png",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/installer/README.md",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/installer/favicon.ico",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/installer/installer_ui_logo.png",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/installer/shortcut.ico",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/logos/dark/placeholder_logo.png",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/logos/light/placeholder_logo.png",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/pywebview/README.md",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/scripts/README.md",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/orchestrator/README.md",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/orchestrator/splash.png",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/assets/pywebview/favicon.ico",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/pages/about_page.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/pages/first_page.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/pages/page.py",
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/pages/second_page.py",
    # tests
    "tests/conftest.py",
    "tests/unit/test_solution_api.py",
    # tests (UI - dash only)
    "tests/unit/test_solution_ui.py",
]


def _get_expected_solution_structure(
    solution_module_name: str,
    ui_framework: str,
    namespace: str = DEFAULT_SOLUTION_NAMESPACE,
) -> list[str]:
    """Build expected file list applying module, namespace, and UI filtering."""
    # Replace both module name placeholder and namespace placeholder
    namespace_path = namespace_to_path(namespace)
    expected_files = [
        path.replace(_MODULE_PLACEHOLDER, solution_module_name).replace(_NAMESPACE_PLACEHOLDER, namespace_path)
        for path in EXPECTED_SOLUTION_TEMPLATE_STRUCTURE
    ]

    if ui_framework != "dash":
        ui_path_prefix = f"src/{namespace_path}/{solution_module_name}/ui"
        expected_files = [
            path
            for path in expected_files
            if not path.startswith(ui_path_prefix) and path != "tests/unit/test_solution_ui.py"
        ]

    return expected_files


def check_scaffolded_solution_structure(
    root_dir: Path,
    solution_name: str,
    solution_module_name: str,
    ui_framework: str,
    namespace: str,
) -> None:
    """Verify the generated solution file structure matches the hardcoded expected structure.

    Unlike ``check_scaffolded_solution_files`` which dynamically scans the solution template directory,
    this function compares against a hardcoded list. This catches cases where an item is accidentally
    removed from the solution template.
    """
    scaffolded_solution_dir = root_dir / solution_name
    assert scaffolded_solution_dir.is_dir()
    expected_files = set(_get_expected_solution_structure(solution_module_name, ui_framework, namespace=namespace))
    actual_files = {
        file.relative_to(scaffolded_solution_dir).as_posix()
        for file in scaffolded_solution_dir.rglob("*")
        if file.is_file()
    }
    assert expected_files == actual_files


def check_agents_file(
    root_dir: Path,
    solution_name: str,
    solution_module_name: str,
    solution_display_name: str,
    solution_definition_class_name: str,
    ui_framework: str,
) -> None:
    """Assert that the rendered AGENTS.md contains the expected values and no unreplaced cookiecutter variables."""
    agents_md_file = root_dir / solution_name / "AGENTS.md"
    assert agents_md_file.is_file()
    content = agents_md_file.read_text()

    assert "cookiecutter" not in content

    assert solution_name in content
    assert solution_module_name in content
    assert solution_display_name in content
    assert solution_definition_class_name in content

    is_dash = ui_framework == "dash"
    assert ("--ui-framework dash" in content) == is_dash
    assert ("Dash" in content) == is_dash
    assert ("without a bundled UI framework" in content) != is_dash


################################################ Solution Installation ################################################


def _normalize_package_name(string: str) -> str:
    return string.replace("_", "-").lower()


def _get_expected_packages(solution_path: Path, dependency_groups: list[str]) -> dict[str, list[dict[str, str]]]:
    pyproject_data = tomlkit.loads((solution_path / "pyproject.toml").read_bytes()).unwrap()
    lock_data = tomlkit.loads((solution_path / "poetry.lock").read_bytes()).unwrap()

    dependencies = [
        dep
        for dep, value in dict(pyproject_data["tool"]["poetry"]["dependencies"]).items()
        if dep != "python" and (not isinstance(value, dict) or not value.get("optional", False))  # type: ignore[reportUnknownMemberType]
    ]

    for dependency_group in dependency_groups:
        dependencies += list(pyproject_data["tool"]["poetry"]["group"][dependency_group]["dependencies"])

    expected_installed_packages: dict[str, list[dict[str, str]]] = {}
    for dependency in dependencies:
        # there can be more than 1 version of a package in the lock file, so we need to check all of them
        for package in lock_data["package"]:
            if _normalize_package_name(package["name"]) == _normalize_package_name(dependency):
                expected_installed_packages.setdefault(dependency, []).append(
                    {"name": _normalize_package_name(package["name"]), "version": package["version"]},
                )

    return expected_installed_packages


def _check_solution_executables(solution_path: Path) -> None:
    find_exec_in_venv(solution_path, "python")
    find_exec_in_venv(solution_path, "poetry")


def _check_poetry_structure(solution_path: Path, check_poetry_cache: bool = False) -> None:
    poetry_venv = solution_path / ".poetry" / ".venv"
    poetry_cache_dir = solution_path / ".poetry" / ".cache"
    poetry_lock_file = solution_path / "poetry.lock"
    poetry_toml_file = solution_path / "poetry.toml"
    expected_config_cache_dir = solution_path / ".poetry" / ".cache"
    poetry_local_config = tomlkit.loads(poetry_toml_file.read_bytes()).unwrap()
    config_cache_dir = Path(poetry_local_config["cache-dir"])
    assert poetry_venv.is_dir()
    assert poetry_cache_dir.is_dir() if check_poetry_cache else True
    assert poetry_lock_file.is_file()
    assert config_cache_dir == expected_config_cache_dir


def _check_solution_installed_packages(
    solution_path: Path,
    installed_groups: list[str],
    not_installed_groups: list[str] | None = None,
) -> None:
    pip_executable_path = find_exec_in_venv(solution_path, "pip")
    cmd = [pip_executable_path, "list", "--format", "json"]
    installed_packages = subprocess.check_output(cmd, text=True)
    installed_packages = json.loads(_normalize_package_name(installed_packages.replace("\\", "\\\\")))
    expected_installed_packages = _get_expected_packages(solution_path, installed_groups)
    for package_name, expected_versions in expected_installed_packages.items():
        if not any(package in expected_versions for package in installed_packages):
            raise AssertionError(
                f"Expected '{package_name}' with versions {expected_versions} "
                f"not found in installation: {installed_packages}",
            )
    if not_installed_groups:
        expected_not_installed_packages = _get_expected_packages(solution_path, not_installed_groups)
        all_installed = True
        assert not all(package in installed_packages for package in expected_not_installed_packages)
        for expected_versions in expected_not_installed_packages.values():
            if not any(package in expected_versions for package in installed_packages):
                all_installed = False
                break
        assert not all_installed


def _check_poetry_version(solution_path: Path) -> None:
    poetry_executable_path = find_exec_in_venv(solution_path, "poetry")
    cmd = [poetry_executable_path, "--version"]
    installed_build_system_version = subprocess.check_output(cmd, text=True).strip()
    installed_build_system_version = installed_build_system_version.split("version ")[-1][:-1]
    pyproject_data = tomlkit.loads((solution_path / "pyproject.toml").read_bytes()).unwrap()
    pyproject_build_system_version = pyproject_data["build-system-requirements"]["build-system-version"]
    assert installed_build_system_version == pyproject_build_system_version


def _check_saf_cli_version(solution_path: Path) -> None:
    saf_executable_path = Path(sys.executable).parent / ("saf.exe" if platform.system() == "Windows" else "saf")
    cmd = [saf_executable_path, "--version"]
    saf_cli_version = subprocess.check_output(cmd, text=True).strip()
    pyproject_data = tomlkit.loads((solution_path / "pyproject.toml").read_bytes()).unwrap()
    pyproject_saf_cli_version = pyproject_data["saf-cli-version"]["saf-cli-version"]
    assert saf_cli_version == pyproject_saf_cli_version


def _check_solution_module_preload_is_executed(
    solution_path: Path,
    solution_namespace: str = DEFAULT_SOLUTION_NAMESPACE,
    solution_name: str | None = None,
) -> None:
    solution_venv_python_exec = find_exec_in_venv(solution_path, "python")
    output = subprocess.check_output(
        [solution_venv_python_exec.absolute().as_posix(), "-c", "import sys; print(sys.path)"],
        text=True,
    ).strip()
    sys_paths: list[str] = ast.literal_eval(output)
    src_path = (solution_path / "src").resolve()
    assert str(src_path) in sys_paths
    namespace_path = namespace_to_path(solution_namespace)
    solution_package = src_path / namespace_path / (solution_name or DEFAULT_SOLUTION_NAME)
    assert (solution_package / "__pycache__").is_dir()
    assert (solution_package / "solution" / "__pycache__").is_dir()
    assert (solution_package / "ui" / "__pycache__").is_dir()
    assert (solution_package / "ui" / "pages" / "__pycache__").is_dir()


def _check_poetry_plugin_export_is_installed(solution_path: Path) -> None:
    poetry_venv_python_exec = find_exec_in_venv(solution_path / ".poetry", "python")
    cmd = [poetry_venv_python_exec.absolute().as_posix(), "-m", "pip", "show", "poetry-plugin-export"]
    output = subprocess.check_output(cmd, text=True).strip()
    assert "Name: poetry-plugin-export" in output


def verify_installation(
    solution_path: Path,
    solution_namespace: str = DEFAULT_SOLUTION_NAMESPACE,
    installed_groups: list[str] | None = None,
    not_installed_groups: list[str] | None = None,
    check_poetry_cache: bool = False,
    skip_preload: bool = False,
    solution_name: str | None = None,
) -> None:
    _check_solution_executables(solution_path)
    _check_poetry_structure(solution_path, check_poetry_cache)
    _check_poetry_version(solution_path)
    _check_saf_cli_version(solution_path)
    _check_solution_installed_packages(
        solution_path,
        installed_groups=installed_groups or ["desktop", "ui", "doc", "build"],
        not_installed_groups=not_installed_groups,
    )
    _check_poetry_plugin_export_is_installed(solution_path)
    if not skip_preload:
        _check_solution_module_preload_is_executed(solution_path, solution_namespace, solution_name)


################################################ Solution Build ################################################


def _get_common_built_solution_files(solution_module_name: str, solution_package_name: str) -> list[Path]:
    dist_dir = Path("dist")
    platform_suffix = ".ico" if platform.system() == "Windows" else ".png"
    expected_solution_files = [
        dist_dir / f"{solution_package_name}-0.0.0-py3-none-any.whl",
        dist_dir / f"{solution_package_name}-0.0.0.tar.gz",
        dist_dir / "solution" / "solution-metadata.json",
        dist_dir / "solution" / "solution_desktop_deployment.py",
        dist_dir / "solution" / "version.txt",
        dist_dir / "solution" / "assets" / f"favicon{platform_suffix}",
        dist_dir / "solution" / "assets" / f"shortcut{platform_suffix}",
        dist_dir / "solution" / "assets" / "installer_ui_logo.png",
        dist_dir / "solution" / "definitions" / solution_module_name / ".env",
        dist_dir / "solution" / "definitions" / solution_module_name / "poetry.lock",
        dist_dir / "solution" / "definitions" / solution_module_name / "pyproject.toml",
        dist_dir / "solution" / "definitions" / solution_module_name / "tools" / "pip_requirements.txt",
        dist_dir / "solution" / "definitions" / solution_module_name / "tools" / "poetry_requirements.txt",
    ]
    return expected_solution_files


def _get_available_python_versions_on_nuget() -> list[str]:
    versions_url = "https://api.nuget.org/v3-flatcontainer/python/index.json"
    response = httpx2.get(versions_url)
    response.raise_for_status()

    versions: list[str] = response.json()["versions"]
    available_versions: list[str] = []
    for version in versions:
        if version.startswith(("3.11", "3.12", "3.13", "3.14")):
            available_versions.append(version)

    return available_versions


def _get_expected_python_path_on_windows(third_party_dir: Path, current_python_version: str) -> Path:
    # Minimum Nuget Python 3.11 patch version contains vulnerabilities and we use the official
    # Python URL to download it, which leads to a different python path.
    if (
        current_python_version.startswith(("3.12", "3.13", "3.14"))
        and current_python_version in _get_available_python_versions_on_nuget()
    ):
        return third_party_dir / "python" / "tools" / "python.exe"
    else:
        return third_party_dir / "python" / "python.exe"


def check_built_solution_files(
    solution: SolutionRegistry,
    solution_namespace: str,
    expect_private_wheels: bool = False,
) -> None:
    normalized_solution_display_name = solution.display_name.lower().replace(" ", "-")
    namespace_path = namespace_to_path(solution_namespace)
    solution_module_path = next(directory for directory in (solution.root_dir / "src" / namespace_path).iterdir())
    solution_module_name = solution_module_path.name

    pyproject_data = tomlkit.loads((solution.root_dir / "pyproject.toml").read_bytes()).unwrap()
    solution_package_name = pyproject_data["tool"]["poetry"]["name"].replace("-", "_")

    expected_files = _get_common_built_solution_files(solution_module_name, solution_package_name)
    assert all((solution.root_dir / path).is_file() for path in expected_files)
    wheels_dir = solution.root_dir / "dist" / "solution" / "definitions" / solution_module_name
    private_wheels = list(wheels_dir.glob("ansys_*.whl"))
    assert bool(private_wheels) == expect_private_wheels
    third_party_dir = solution.root_dir / "dist" / "solution" / "third_party"
    current_python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if platform.system() == "Windows":
        assert (solution.root_dir / "dist" / f"{normalized_solution_display_name}-installer.exe").is_file()
        # The .zip file has been successfully extracted; no zip files should remain.
        python_zip = list(third_party_dir.glob("python-*.zip"))
        assert not python_zip
        # Verify that python.exe exists in the expected directory.
        expected_python_path = _get_expected_python_path_on_windows(third_party_dir, current_python_version)
        assert expected_python_path.is_file()

    elif platform.system() == "Linux":
        assert (solution.root_dir / "dist" / f"{normalized_solution_display_name}-installer").is_file()
        # The .tgz file has been successfully extracted; no tgz files should remain.
        python_tgz = list(third_party_dir.glob("python-*.tgz"))
        assert not python_tgz
        # Verify that python3 exists in the expected directory.
        assert (third_party_dir / "python" / "bin" / "python3").is_file()
    else:
        raise ValueError("Unsupported operating system")
