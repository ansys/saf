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

import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from typing import Any
from unittest.mock import patch

from packaging.markers import default_environment
from packaging.version import Version
import pytest
import pytest_mock
import toml

from ansys.saf.desktop.installer._package import manage_dependencies
from ansys.saf.desktop.installer._package.backend_detection import SolutionBackend
from ansys.saf.desktop.installer._package.config import InstallerConfig
from ansys.saf.desktop.installer._package.manage_dependencies import (
    build_and_stage_solution_packages,
    copy_files,
    delete_encrypted_files,
)
from ansys.saf.desktop.installer._package.solution import (
    SolutionInfo,
    create_solution_metadata,
    get_solution_module_dotted_path,
    get_solution_module_name,
    get_solution_namespace_info,
    get_solution_package_dir,
)
from ansys.saf.desktop.installer._package.solution_package import (
    _restore_third_party,  # pyright: ignore[reportPrivateUsage]
    _zip_third_party,  # pyright: ignore[reportPrivateUsage]
    build_executable_installer,
    setup_solution_folder,
)
from tests.conftest import CUSTOM_PACKAGE_FOR_TEST_2_WHEEL_NAMES, use_poetry_mock_solution


@pytest.mark.parametrize(
    ("groups", "selected_groups"),
    [
        ("", []),
        ("desktop = []\ndoc = []\ndev = []\n", ["desktop", "doc"]),
        ("desktop = []\nui = []\ndoc = []\n", ["desktop", "ui", "doc"]),
    ],
)
def test_export_uv_requirements_selects_existing_groups(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    groups: str,
    selected_groups: list[str],
) -> None:
    """Export locked main dependencies and only the requested groups that exist."""
    project = tmp_path / "solution"
    project.mkdir()
    (project / "pyproject.toml").write_text(f"[dependency-groups]\n{groups}", encoding="utf-8")
    (project / "uv.lock").touch()
    output = tmp_path / "requirements.txt"
    python = tmp_path / "python"
    command = ["uv", "export", "--locked", "--no-default-groups", "--no-emit-project", "--python", str(python)]
    for group in selected_groups:
        command.extend(["--group", group])
    run = mocker.patch.object(
        manage_dependencies.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(command, 0, "package==1.0\n", ""),
    )

    result = manage_dependencies.export_uv_requirements(project, python, output)

    assert result == output
    assert output.read_text(encoding="utf-8") == "package==1.0\n"
    run.assert_called_once_with(command, cwd=project, capture_output=True, check=True, text=True)


def test_export_uv_requirements_requires_lock(tmp_path: Path, mocker: pytest_mock.MockerFixture) -> None:
    """Reject missing UV locks before trying to export dependencies."""
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n", encoding="utf-8")
    run = mocker.patch.object(manage_dependencies.subprocess, "run")

    with pytest.raises(FileNotFoundError, match="uv.lock"):
        manage_dependencies.export_uv_requirements(tmp_path, tmp_path / "python", tmp_path / "requirements.txt")

    run.assert_not_called()


def test_export_uv_requirements_reports_export_failure(tmp_path: Path, mocker: pytest_mock.MockerFixture) -> None:
    """Report a UV export failure, including a stale lock, without writing requirements."""
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n", encoding="utf-8")
    (tmp_path / "uv.lock").touch()
    output = tmp_path / "requirements.txt"
    error = subprocess.CalledProcessError(1, ["uv", "export"], stderr="The lockfile needs to be updated")
    mocker.patch.object(manage_dependencies.subprocess, "run", side_effect=error)

    with pytest.raises(RuntimeError, match="UV dependency export failed.*lockfile needs to be updated"):
        manage_dependencies.export_uv_requirements(tmp_path, tmp_path / "python", output)

    assert not output.exists()


def test_select_uv_lock_packages_from_selected_requirements(tmp_path: Path) -> None:
    """Use UV's selected requirements to filter native lock entries by package/version."""
    wheel = tmp_path / "example-1.0-py3-none-any.whl"
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "version = 1\n"
        '[[package]]\nname = "example"\nversion = "1.0"\nsource = { path = "example-1.0-py3-none-any.whl" }\n'
        '[[package]]\nname = "idna"\nversion = "3.10"\nsource = { registry = "https://pypi.org/simple" }\n'
        '[[package]]\nname = "dev-only"\nversion = "1.0"\nsource = { registry = "https://pypi.org/simple" }\n',
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        f"{wheel.as_uri()} \\\n    --hash=sha256:example\nidna==3.10 \\\n    --hash=sha256:example\n",
        encoding="utf-8",
    )

    selected = manage_dependencies._selected_uv_lock_packages(tmp_path, requirements)  # pyright: ignore[reportPrivateUsage]

    assert [(package["name"], package["version"]) for package in selected] == [("example", "1.0"), ("idna", "3.10")]


def test_select_uv_lock_packages_from_relative_per_platform_wheel_paths(tmp_path: Path) -> None:
    """Select only the target's wheel when UV exports [tool.uv.sources] wheels as relative paths with markers."""
    windows_wheel = "build_assets/example-1.0-py3-none-win_amd64.whl"
    linux_wheel = "build_assets/example-1.0-py3-none-manylinux_2_28_x86_64.whl"
    (tmp_path / "uv.lock").write_text(
        "version = 1\n"
        f'[[package]]\nname = "example"\nversion = "1.0"\nsource = {{ path = "{windows_wheel}" }}\n'
        f'[[package]]\nname = "example"\nversion = "1.0"\nsource = {{ path = "{linux_wheel}" }}\n',
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        f"./{windows_wheel} ; sys_platform == 'win32'\n./{linux_wheel} ; sys_platform == 'linux'\n",
        encoding="utf-8",
    )

    selected = manage_dependencies._selected_uv_lock_packages(  # pyright: ignore[reportPrivateUsage]
        tmp_path, requirements, Path(sys.executable)
    )

    expected_wheel = windows_wheel if sys.platform == "win32" else linux_wheel
    assert [package["source"]["path"] for package in selected] == [expected_wheel]


def test_pin_staged_wheel_url_dependencies(tmp_path: Path) -> None:
    """Pin URL requirements of staged wheels to staged copies and leave other URL requirements untouched."""
    import zipfile

    with zipfile.ZipFile(tmp_path / "scooby-0.11.2-py3-none-any.whl", "w") as wheel:
        wheel.writestr("scooby-0.11.2.dist-info/METADATA", "Metadata-Version: 2.1\nName: scooby\nVersion: 0.11.2\n")
    parent = tmp_path / "parent-1.0-py3-none-any.whl"
    with zipfile.ZipFile(parent, "w") as wheel:
        wheel.writestr(
            "parent-1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: parent\nVersion: 1.0\n"
            "Requires-Dist: scooby[cpu] @ https://example.com/scooby-0.11.2-py3-none-any.whl"
            " ; sys_platform == 'win32'\n"
            "Requires-Dist: other @ https://example.com/other-1.0-py3-none-any.whl\n",
        )
        wheel.writestr("parent/__init__.py", "")

    manage_dependencies._pin_staged_wheel_url_dependencies(tmp_path)  # pyright: ignore[reportPrivateUsage]

    with zipfile.ZipFile(parent) as wheel:
        metadata = wheel.read("parent-1.0.dist-info/METADATA").decode()
        assert "parent/__init__.py" in wheel.namelist()
    assert 'Requires-Dist: scooby[cpu]==0.11.2 ; sys_platform == "win32"\n' in metadata
    assert "Requires-Dist: other @ https://example.com/other-1.0-py3-none-any.whl\n" in metadata


def test_stage_uv_selected_local_dependencies(tmp_path: Path, mocker: pytest_mock.MockerFixture) -> None:
    """Build wheels for native UV local, Git, and URL lock sources."""
    wheel = tmp_path / "example-1.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    project = tmp_path / "local-project"
    project.mkdir()
    packages = [
        {
            "name": "local",
            "source": {"path": "local-project"},
            "resolution-markers": ["python_full_version < '3.13'"],
        },
        {
            "name": "example",
            "source": {"path": wheel.name},
            "wheels": [{"filename": wheel.name, "hash": f"sha256:{digest}"}],
        },
        {"name": "git", "source": {"git": "https://github.com/org/repo.git#abcdef"}},
        {"name": "remote", "source": {"url": "https://example.invalid/a.whl"}},
    ]
    python = tmp_path / "python"
    wheelhouse = tmp_path / "wheelhouse"

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        requirements = Path(command[-1]).read_text(encoding="utf-8").splitlines()
        assert requirements == [
            f"local @ {project.resolve().as_uri()} ; (python_full_version < '3.13')",
            f"example @ {wheel.resolve().as_uri()}",
            "git @ git+https://github.com/org/repo.git@abcdef",
            "remote @ https://example.invalid/a.whl",
        ]
        assert command == [
            str(python),
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--wheel-dir",
            str(wheelhouse),
            "-r",
            command[-1],
        ]
        assert kwargs == {"cwd": tmp_path, "check": True, "capture_output": True, "text": True}
        return subprocess.CompletedProcess(command, 0, "", "")

    mocker.patch.object(manage_dependencies.subprocess, "run", side_effect=run)
    assert manage_dependencies.stage_uv_selected_local_dependencies(tmp_path, packages, wheelhouse, python) is None


def test_stage_uv_selected_local_wheel_checks_hash(tmp_path: Path, mocker: pytest_mock.MockerFixture) -> None:
    """Reject a changed local wheel before staging it."""
    wheel = tmp_path / "local.whl"
    wheel.write_bytes(b"modified")
    packages = [
        {
            "name": "local",
            "source": {"path": "local.whl"},
            "wheels": [{"filename": "local.whl", "hash": "sha256:wrong"}],
        },
    ]
    with pytest.raises(ValueError, match="SHA-256 hash mismatch"):
        manage_dependencies.stage_uv_selected_local_dependencies(
            tmp_path,
            packages,
            tmp_path / "wheelhouse",
            tmp_path,
        )


@pytest.mark.parametrize("offline_package", [False, True])
def test_refresh_uv_project_lock_uses_network_only_for_online_packages(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    offline_package: bool,
) -> None:
    """Online packages may need registry metadata that is not in the local UV cache."""
    run = mocker.patch.object(manage_dependencies.subprocess, "run")

    manage_dependencies.refresh_uv_project_lock(tmp_path, tmp_path / "python.exe", offline_package)

    assert ("--offline" in run.call_args.args[0]) is offline_package


def test_uv_installation_project_uses_built_dynamic_version(tmp_path: Path) -> None:
    """Give the portable UV project a static version so `uv lock` does not call the build backend."""
    (tmp_path / "my_solution-2.1.0b0-py3-none-any.whl").touch()
    (tmp_path / "other_package-9.0-py3-none-any.whl").touch()
    project: dict[str, Any] = {"project": {"name": "My.Solution", "dynamic": ["version", "readme"]}}

    manage_dependencies._use_built_uv_solution_version(project, tmp_path)  # pyright: ignore[reportPrivateUsage]

    assert project["project"] == {"name": "My.Solution", "version": "2.1.0b0", "dynamic": ["readme"]}


def test_uv_installation_project_keeps_static_version(tmp_path: Path) -> None:
    """Leave static UV project versions untouched."""
    project: dict[str, Any] = {"project": {"name": "my-solution", "version": "1.0"}}

    manage_dependencies._use_built_uv_solution_version(project, tmp_path)  # pyright: ignore[reportPrivateUsage]

    assert project["project"] == {"name": "my-solution", "version": "1.0"}


def test_rewrite_uv_local_sources_points_at_staged_wheels(tmp_path: Path) -> None:
    """Rewrite local project sources to portable wheelhouse paths."""
    project_root = tmp_path / "source"
    local_source = project_root / "local-dependency"
    local_source.mkdir(parents=True)
    packages = [
        {
            "name": "local-dependency",
            "version": "1.0",
            "source": {"path": "local-dependency"},
            "resolution-markers": ["sys_platform == 'win32'"],
        },
        {
            "name": "private-package",
            "version": "2.0",
            "source": {"registry": "https://packages.example/simple"},
        },
        {"name": "idna", "version": "3.10", "source": {"registry": "https://pypi.org/simple"}},
    ]
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "local_dependency-1.0-py3-none-any.whl"
    wheel.touch()
    private_wheel = wheelhouse / "private_package-2.0-py3-none-any.whl"
    private_wheel.touch()
    public_wheel = wheelhouse / "idna-3.10-py3-none-any.whl"
    public_wheel.touch()
    project: dict[str, Any] = {"tool": {"uv": {"sources": {}}}}

    manage_dependencies._rewrite_uv_local_sources(  # pyright: ignore[reportPrivateUsage]
        project,
        project_root,
        packages,
        wheelhouse,
        include_public_registry_packages=True,
    )

    assert project["tool"]["uv"]["sources"]["local-dependency"] == {
        "path": f"wheelhouse/{wheel.name}",
        "marker": "(sys_platform == 'win32')",
    }
    assert project["tool"]["uv"]["sources"]["private-package"] == {"path": f"wheelhouse/{private_wheel.name}"}
    assert "idna" not in project["tool"]["uv"]["sources"]
    assert project["project"]["dependencies"] == [
        "local-dependency ; ((sys_platform == 'win32'))",
        "private-package",
    ]


def test_stage_uv_private_dependencies_uses_uv_index_credentials(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "source"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[tool.uv]\n[[tool.uv.index]]\nname = "company"\nurl = "https://packages.example/simple"\n',
        encoding="utf-8",
    )
    packages = [
        {
            "name": "internal-package",
            "version": "1.0",
            "source": {"registry": "https://packages.example/simple"},
        },
    ]
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    monkeypatch.setenv("UV_INDEX_COMPANY_USERNAME", "build-user")
    monkeypatch.setenv("UV_INDEX_COMPANY_PASSWORD", "build-token")

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs["env"]["PIP_INDEX_URL"] == "https://build-user:build-token@packages.example/simple"
        assert Path(command[command.index("-r") + 1]).read_text(encoding="utf-8") == "internal-package==1.0"
        return subprocess.CompletedProcess(command, 0, "", "")

    mocker.patch.object(manage_dependencies.subprocess, "run", side_effect=run)

    manage_dependencies._stage_uv_private_dependencies(  # pyright: ignore[reportPrivateUsage]
        project,
        packages,
        wheelhouse,
        tmp_path / "python",
    )


def test_uv_git_requirement_uses_locked_revision_and_subdirectory() -> None:
    package = {
        "name": "git-package",
        "source": {"git": "https://github.com/org/repo.git#abcdef&subdirectory=python%20package"},
    }

    requirement = manage_dependencies._uv_git_requirement(  # pyright: ignore[reportPrivateUsage]
        package,
        "ghp+test",
    )

    assert requirement == (
        "git-package @ git+https://ghp%2Btest@github.com/org/repo.git@abcdef#subdirectory=python%20package"
    )


@pytest.mark.parametrize("query", ["", "?rev=main", "?tag=v1.0", "?branch=main"])
def test_uv_public_git_requirement_does_not_require_token(query: str) -> None:
    package = {
        "name": "public-git-package",
        "source": {"git": f"https://github.com/org/repo.git{query}#abcdef"},
    }

    requirement = manage_dependencies._uv_git_requirement(  # pyright: ignore[reportPrivateUsage]
        package,
        None,
    )

    assert requirement == "public-git-package @ git+https://github.com/org/repo.git@abcdef"


def test_uv_git_requirement_moves_query_subdirectory_to_pip_fragment() -> None:
    package = {
        "name": "git-package",
        "source": {"git": "https://github.com/org/repo.git?rev=main&subdirectory=python%20package#abcdef"},
    }

    requirement = manage_dependencies._uv_git_requirement(  # pyright: ignore[reportPrivateUsage]
        package,
        None,
    )

    assert requirement == "git-package @ git+https://github.com/org/repo.git@abcdef#subdirectory=python%20package"


def test_obfuscate_solution_includes_uv_wheelhouse_dependencies(
    tmp_path: Path, mocker: pytest_mock.MockerFixture
) -> None:
    root_wheel = tmp_path / "solution-1.0-py3-none-any.whl"
    root_wheel.touch()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    private_wheel = wheelhouse / "private-1.0-py3-none-any.whl"
    private_wheel.touch()
    check_output = mocker.patch.object(manage_dependencies.subprocess, "check_output")
    python = tmp_path / "python"

    manage_dependencies.obfuscate_solution(tmp_path, python)

    assert {call.args[0][-1] for call in check_output.call_args_list} == {str(root_wheel), str(private_wheel)}


def test_stage_uv_selected_local_dependencies_reports_pip_failure(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """Surface local source build failures from the target Python's pip."""
    project = tmp_path / "project"
    project.mkdir()
    packages = [{"name": "local", "source": {"path": "project"}}]
    error = subprocess.CalledProcessError(1, ["python", "-m", "pip", "wheel"], stderr="wheel build failed")
    mocker.patch.object(manage_dependencies.subprocess, "run", side_effect=error)

    with pytest.raises(RuntimeError, match="Failed to stage local or Git UV dependencies.*wheel build failed"):
        manage_dependencies.stage_uv_selected_local_dependencies(
            tmp_path,
            packages,
            tmp_path / "wheelhouse",
            tmp_path / "python",
        )


@pytest.mark.parametrize(
    ("backend", "packages"),
    [
        (SolutionBackend.POETRY, ["wheel", "poetry", "setuptools", "pyc-wheel"]),
        (SolutionBackend.UV, ["wheel", "setuptools", "pyc-wheel"]),
    ],
)
def test_create_definitions_venv_installs_backend_tools(
    tmp_path: Path,
    backend: SolutionBackend,
    packages: list[str],
) -> None:
    """Create the build environment and install only the tools needed by its backend."""
    definitions = tmp_path / "definitions"
    python = tmp_path / "python"
    venv = definitions / ".venv"
    venv_python = venv / "Scripts" / "python.exe" if platform.system() == "Windows" else venv / "bin" / "python"

    with patch("ansys.saf.desktop.installer._package.manage_dependencies.subprocess.check_output") as run:
        result = manage_dependencies.create_venv_in_definitions_folder(definitions, python, backend)

    assert result == (venv, venv_python)
    assert run.call_count == 2
    assert run.call_args_list[0].args[0] == [str(python), "-m", "venv", str(venv)]
    assert run.call_args_list[1].args[0] == [str(venv_python), "-m", "pip", "install", *packages]


@pytest.mark.parametrize("failure_call", [0, 1], ids=["create-venv", "install-tools"])
def test_create_definitions_venv_reports_failures(
    tmp_path: Path,
    failure_call: int,
) -> None:
    """Report errors from environment creation or tool installation."""
    error = subprocess.CalledProcessError(1, ["python"], output="test failure")
    outputs: list[bytes | subprocess.CalledProcessError] = [b"", b""]
    outputs[failure_call] = error
    with (
        patch(
            "ansys.saf.desktop.installer._package.manage_dependencies.subprocess.check_output",
            side_effect=outputs,
        ),
        pytest.raises(RuntimeError, match="Failed to create virtual environment.*test failure"),
    ):
        manage_dependencies.create_venv_in_definitions_folder(tmp_path, tmp_path / "python", SolutionBackend.POETRY)


@pytest.mark.parametrize(
    ("section", "backend"),
    [("tool.poetry", SolutionBackend.POETRY), ("tool.uv", SolutionBackend.UV)],
)
def test_setup_solution_folder_passes_detected_backend(
    tmp_path: Path,
    mock_installer_config: InstallerConfig,
    mocker: pytest_mock.MockerFixture,
    section: str,
    backend: SolutionBackend,
) -> None:
    """Pass the solution's detected backend to environment and tool preparation."""
    (tmp_path / "pyproject.toml").write_text(f"[{section}]\n")
    solution_info = mocker.Mock(spec=SolutionInfo)
    solution_info.solution_root_dir = tmp_path
    solution_info.solution_module_name = "example"
    solution_info.solution_display_name = "Example"
    solution_info.solution_version = "1.0"
    module = "ansys.saf.desktop.installer._package.solution_package"
    for name in (
        "build_and_embed_documentation",
        "create_solution_metadata",
        "create_version_file",
        "move_assets_and_deployment_script",
    ):
        mocker.patch(f"{module}.{name}")
    definitions = tmp_path / "definitions"
    python = tmp_path / "python"
    mocker.patch(f"{module}.get_definitions_folder", return_value=definitions)
    mocker.patch(f"{module}.download_embeddable_python", return_value=(python, "3.11"))
    venv = definitions / ".venv"
    venv_python = venv / "python"
    create_venv = mocker.patch(f"{module}.create_venv_in_definitions_folder", return_value=(venv, venv_python))
    write_tool_requirements = mocker.patch(
        f"{module}.write_backend_tool_requirements",
        side_effect=RuntimeError("stop"),
    )

    with pytest.raises(RuntimeError, match="stop"):
        setup_solution_folder(solution_info, mock_installer_config)

    create_venv.assert_called_once_with(definitions, python, backend)
    write_tool_requirements.assert_called_once_with(tmp_path, "example", venv_python, backend)


def test_setup_uv_solution_skips_poetry_project_generation(
    tmp_path: Path,
    mock_installer_config: InstallerConfig,
    mocker: pytest_mock.MockerFixture,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "1.0"\n[tool.uv]\n',
        encoding="utf-8",
    )
    mock_installer_config.pyproject_location = tmp_path / "pyproject.toml"
    solution_info = mocker.Mock(spec=SolutionInfo)
    solution_info.solution_root_dir = tmp_path
    solution_info.solution_module_name = "example"
    solution_info.solution_display_name = "Example"
    solution_info.solution_version = "1.0"
    module = "ansys.saf.desktop.installer._package.solution_package"
    for name in (
        "build_and_embed_documentation",
        "create_solution_metadata",
        "create_version_file",
        "move_assets_and_deployment_script",
        "write_backend_tool_requirements",
        "create_env_file",
        "copy_configuration_files",
    ):
        mocker.patch(f"{module}.{name}")
    definitions = tmp_path / "definitions"
    python = tmp_path / "python"
    mocker.patch(f"{module}.get_definitions_folder", return_value=definitions)
    mocker.patch(f"{module}.download_embeddable_python", return_value=(python, "3.11"))
    mocker.patch(
        f"{module}.create_venv_in_definitions_folder",
        return_value=(definitions / ".venv", definitions / ".venv" / "python"),
    )
    build_and_stage = mocker.patch(f"{module}.build_and_stage_solution_packages")
    create_poetry_project = mocker.patch(f"{module}.create_poetry_installation_project")

    setup_solution_folder(solution_info, mock_installer_config)

    assert build_and_stage.call_args.args[-1] is SolutionBackend.UV
    create_poetry_project.assert_not_called()


@pytest.mark.parametrize(
    ("backend", "configuration", "poetry_requirements"),
    [
        (SolutionBackend.POETRY, '[build-system-requirements]\nbuild-system-version = "1.8.4"\n', "poetry==1.8.4"),
        (
            SolutionBackend.POETRY,
            '[build-system-requirements]\nbuild-system-version = "2.5.1"\n',
            "poetry==2.5.1\npoetry-plugin-export>=1.8",
        ),
        (SolutionBackend.UV, "[tool.uv]\n", None),
    ],
)
def test_write_backend_tool_requirements(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    backend: SolutionBackend,
    configuration: str,
    poetry_requirements: str | None,
) -> None:
    """Write pip requirements and only the selected backend's tool requirements."""
    (tmp_path / "pyproject.toml").write_text(configuration)
    python = tmp_path / "python"
    check_output = mocker.patch.object(manage_dependencies.subprocess, "check_output", return_value="pip 24.0 from x")

    manage_dependencies.write_backend_tool_requirements(tmp_path, "example", python, backend)

    tools = tmp_path / "dist" / "solution" / "definitions" / "example" / "tools"
    assert (tools / "pip_requirements.txt").read_text() == "pip==24.0"
    poetry_file = tools / "poetry_requirements.txt"
    if poetry_requirements is None:
        assert not poetry_file.exists()
    else:
        assert poetry_file.read_text() == poetry_requirements
    check_output.assert_called_once_with([python, "-m", "pip", "--disable-pip-version-check", "--version"], text=True)


@pytest.mark.parametrize(
    ("configuration", "missing_key"),
    [
        ("[tool.poetry]\n", "build-system-requirements"),
        ("[build-system-requirements]\n", "build-system-version"),
    ],
)
def test_write_backend_tool_requirements_requires_poetry_version(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    configuration: str,
    missing_key: str,
) -> None:
    """Keep the existing errors for missing Poetry version configuration."""
    (tmp_path / "pyproject.toml").write_text(configuration)
    mocker.patch.object(manage_dependencies.subprocess, "check_output", return_value="pip 24.0 from x")

    with pytest.raises(KeyError, match=missing_key):
        manage_dependencies.write_backend_tool_requirements(
            tmp_path,
            "example",
            tmp_path / "python",
            SolutionBackend.POETRY,
        )


def test_merge_poetry_group_dependencies_adds_extras_to_main_dependency():
    dependencies: dict[str, Any] = {
        "example-package": {"version": "^1.0", "extras": ["main-extra"], "python": ">=3.11"},
    }
    poetry: dict[str, Any] = {
        "group": {
            "desktop": {"dependencies": {"example_package": {"version": "^2.0", "extras": ["desktop-extra"]}}},
            "ui": {"dependencies": {"example-package": {"extras": ["ui-extra", "main-extra"]}}},
            "doc": {"dependencies": {"example-package": {"extras": ["doc-extra"]}}},
        },
    }

    manage_dependencies._merge_poetry_group_dependencies(  # pyright: ignore[reportPrivateUsage]
        ["desktop", "ui", "doc"],
        poetry,
        dependencies,
    )

    assert dependencies == {
        "example-package": {
            "version": "^1.0",
            "extras": ["main-extra", "desktop-extra", "ui-extra", "doc-extra"],
            "python": ">=3.11",
        },
    }


def test_merge_poetry_group_dependencies_adds_extras_to_string_main_dependency():
    dependencies: dict[str, Any] = {"example-package": "^1.0"}
    poetry: dict[str, Any] = {
        "group": {"desktop": {"dependencies": {"example_package": {"extras": ["desktop-extra"]}}}},
    }

    manage_dependencies._merge_poetry_group_dependencies(  # pyright: ignore[reportPrivateUsage]
        ["desktop"],
        poetry,
        dependencies,
    )

    assert dependencies == {"example-package": {"version": "^1.0", "extras": ["desktop-extra"]}}


def test_relativize_poetry_lock_path_dependencies(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    definitions_folder = tmp_path / "definitions" / "my_solution"
    definitions_folder.mkdir(parents=True)
    inside = (definitions_folder / "dep-1.0.0-py3-none-any.whl").as_posix()
    nested = (definitions_folder / "sub" / "nested-1.0.0-py3-none-any.whl").as_posix()
    outside = (tmp_path / "elsewhere" / "other-1.0.0-py3-none-any.whl").as_posix()
    multi_a = (definitions_folder / "multi-1.0.0-cp312-cp312-win_amd64.whl").as_posix()
    multi_b = (definitions_folder / "multi-1.0.0-cp312-cp312-manylinux_2_17_x86_64.whl").as_posix()
    lock_content = f"""[[package]]
name = "my-solution"
version = "0.1.0"

[package.dependencies]
dep = {{path = "{inside}"}}
nested = {{path = "{nested}"}}
other = {{path = "{outside}"}}
relative = {{path = "relative-1.0.0-py3-none-any.whl"}}
multi = [
    {{path = "{multi_a}", markers = "sys_platform == \\"win32\\""}},
    {{path = "{multi_b}", markers = "sys_platform == \\"linux\\""}},
]

[package.source]
type = "file"
url = "my_solution-0.1.0-py3-none-any.whl"
"""
    poetry_lock = definitions_folder / "poetry.lock"
    poetry_lock.write_text(lock_content, encoding="utf-8")

    manage_dependencies.relativize_poetry_lock_path_dependencies(definitions_folder)

    dependencies = toml.loads(poetry_lock.read_text(encoding="utf-8"))["package"][0]["dependencies"]
    assert dependencies["dep"] == {"path": "dep-1.0.0-py3-none-any.whl"}
    assert dependencies["nested"] == {"path": "sub/nested-1.0.0-py3-none-any.whl"}
    assert dependencies["other"] == {"path": outside}
    assert dependencies["relative"] == {"path": "relative-1.0.0-py3-none-any.whl"}
    assert [constraint["path"] for constraint in dependencies["multi"]] == [
        "multi-1.0.0-cp312-cp312-win_amd64.whl",
        "multi-1.0.0-cp312-cp312-manylinux_2_17_x86_64.whl",
    ]
    assert 'url = "my_solution-0.1.0-py3-none-any.whl"' in poetry_lock.read_text(encoding="utf-8")
    assert "other-1.0.0-py3-none-any.whl" in caplog.text


@pytest.mark.parametrize(
    "build_dir_name",
    [
        pytest.param(
            'build"quoted',
            marks=pytest.mark.skipif(platform.system() == "Windows", reason="Invalid Windows directory name."),
        ),
        "build\\back",
    ],
)
def test_relativize_poetry_lock_path_dependencies_with_escaped_characters(
    tmp_path: Path,
    build_dir_name: str,
) -> None:
    definitions_folder = tmp_path / build_dir_name / "definitions"
    definitions_folder.mkdir(parents=True)
    wheel_path = str(definitions_folder / "dep-1.0.0-py3-none-any.whl")
    poetry_lock = definitions_folder / "poetry.lock"
    poetry_lock.write_text(
        f'[[package]]\nname = "my-solution"\n\n[package.dependencies]\ndep = {{path = {json.dumps(wheel_path)}}}\n',
        encoding="utf-8",
    )

    manage_dependencies.relativize_poetry_lock_path_dependencies(definitions_folder)

    dependencies = tomllib.loads(poetry_lock.read_text(encoding="utf-8"))["package"][0]["dependencies"]
    assert dependencies["dep"] == {"path": "dep-1.0.0-py3-none-any.whl"}


def test_create_poetry_installation_project_relativizes_lock_path_dependencies(tmp_path: Path) -> None:
    solution_root_dir = tmp_path / "solution"
    solution_root_dir.mkdir()
    pyproject = solution_root_dir / "pyproject.toml"
    pyproject.write_text(
        '[tool.poetry]\nname = "my-solution"\n\n[tool.poetry.dependencies]\npython = ">=3.11,<3.13"\n',
        encoding="utf-8",
    )
    definitions_folder = tmp_path / "definitions"
    definitions_folder.mkdir()
    with (
        patch("ansys.saf.desktop.installer._package.manage_dependencies.subprocess.check_output"),
        patch(
            "ansys.saf.desktop.installer._package.manage_dependencies.relativize_poetry_lock_path_dependencies",
        ) as mock_relativize,
    ):
        manage_dependencies.create_poetry_installation_project(
            Path("python"),
            pyproject,
            definitions_folder,
            "3.12",
        )
    mock_relativize.assert_called_once_with(definitions_folder)


@pytest.mark.parametrize(
    ("backend", "pyproject", "command"),
    [
        (
            "poetry",
            '[tool.poetry]\nname = "ansys-solution"\nversion = "1.2.3"\nreadme = "README.md"\n',
            ["poetry", "build", "--no-interaction"],
        ),
        (
            "uv",
            '[project]\nname = "ansys-solution"\nversion = "1.2.3"\nreadme = "README.md"\n\n[tool.uv]\n',
            ["uv", "build"],
        ),
    ],
)
def test_build_solution_wheel_uses_detected_backend(
    tmp_path: Path,
    backend: str,
    pyproject: str,
    command: list[str],
) -> None:
    """Select the backend's build command, copy its wheel, and request metadata adjustment."""
    solution_root_dir = tmp_path / "solution"
    solution_root_dir.mkdir()
    (solution_root_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (solution_root_dir / "README.md").touch()
    definitions_folder = tmp_path / "definitions"
    definitions_folder.mkdir()
    wheel_name = "ansys_solution-1.2.3-py3-none-any.whl"

    def build_wheel(args: list[str], **kwargs: Any) -> bytes:
        assert args == command
        assert kwargs["cwd"] == solution_root_dir
        dist_folder = solution_root_dir / "dist"
        dist_folder.mkdir()
        (dist_folder / wheel_name).touch()
        return b""

    with (
        patch(
            "ansys.saf.desktop.installer._package.manage_dependencies.subprocess.check_output",
            side_effect=build_wheel,
        ) as mock_build,
        patch(
            "ansys.saf.desktop.installer._package.manage_dependencies.modify_solution_wheel_metadata",
        ) as mock_modify_metadata,
    ):
        manage_dependencies.build_solution_wheel(definitions_folder, solution_root_dir)

    mock_build.assert_called_once()
    assert (definitions_folder / wheel_name).is_file()
    mock_modify_metadata.assert_called_once_with(definitions_folder, "ansys_solution", "1.2.3")


@pytest.fixture
def mock_installer_config(solution_root_dir: Path) -> InstallerConfig:
    return InstallerConfig(
        encryption_file=solution_root_dir / "obfuscate.txt",
        pyproject_location=solution_root_dir / "pyproject.toml",
        python_version="3.11.10",
    )


@pytest.fixture
def mock_subprocess_calls(  # noqa: C901
    mocker: pytest_mock.MockFixture,
    solution_root_dir: Path,
) -> pytest_mock.MockType:
    expected_doc_html = solution_root_dir / "doc" / "build" / "html" / "index.html"
    expected_exec = (
        solution_root_dir / "dist" / ("test-installer.exe" if platform.system() == "Windows" else "test-installer")
    )
    python_dir = solution_root_dir / "dist" / "solution" / "third_party" / "python"
    linux_expected_python_exec = python_dir / "bin" / "python3"
    windows_source_expected_python_exec = python_dir / "python.exe"
    windows_nuget_expected_python_exec = python_dir / "tools" / "python.exe"

    def _project_name_and_version(project_dir: Path) -> tuple[str, str]:
        pyproject = toml.load(project_dir / "pyproject.toml")
        metadata = pyproject.get("project") or pyproject["tool"]["poetry"]
        return metadata["name"], metadata["version"]

    def _build_mock_wheel(args: list[str], project_dir: Path) -> subprocess.CompletedProcess[str]:
        name, version = _project_name_and_version(project_dir)
        wheel = project_dir / "dist" / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
        wheel.parent.mkdir(parents=True, exist_ok=True)
        wheel.touch()
        return subprocess.CompletedProcess(args, 0, f"Built {wheel.name}", "")

    def _mock_subprocess_run(args: list[str], **kwargs: dict[str, Any]):  # type: ignore  # noqa: C901
        if args == ["sphinx-build", "doc/source", "doc/build/html", "--color", "-vW", "-bhtml"]:
            if not (solution_root_dir / "doc").is_dir():
                raise subprocess.CalledProcessError(1, args, "mock error when building doc", "")
            if any((solution_root_dir / "doc").iterdir()):
                expected_doc_html.parent.mkdir(parents=True, exist_ok=True)
                expected_doc_html.write_text("mock_documentation")
        elif args == ["poetry", "version", "--no-interaction"]:
            name, version = _project_name_and_version(Path(kwargs["cwd"]))  # type: ignore
            return subprocess.CompletedProcess(args, 0, f"{name} {version}", "")
        elif args[-4:] == ["-m", "pip", "--disable-pip-version-check", "--version"]:
            return subprocess.CompletedProcess(args, 0, "pip 22.3.1 from mock_directory", "")
        elif args in (["poetry", "build", "--no-interaction"], ["uv", "build"]):
            return _build_mock_wheel(args, Path(kwargs["cwd"]))  # type: ignore
        elif len(args) == 3 and args[1] == "-c" and "sys_platform" in args[2]:
            return subprocess.CompletedProcess(args, 0, json.dumps(default_environment()), "")
        elif "pyinstaller" in str(args[0]):
            expected_exec.parent.mkdir(parents=True, exist_ok=True)
            expected_exec.touch()
        elif args == ["make", "install"]:
            linux_expected_python_exec.parent.mkdir(parents=True)
            linux_expected_python_exec.touch()
        elif args == ["cmd", "/c", "PCBuild\\build.bat", "-e"]:
            windows_source_expected_python_exec.touch()
            windows_nuget_expected_python_exec.parent.mkdir(parents=True)
            windows_nuget_expected_python_exec.touch()

        empty_output = "" if kwargs.get("text") else b""
        return subprocess.CompletedProcess(args, 0, empty_output, empty_output)  # type: ignore

    subprocess_run_mock = mocker.patch("subprocess.run")
    subprocess_run_mock.side_effect = _mock_subprocess_run

    return subprocess_run_mock


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_missing_obfuscate_txt(solution_root_dir: Path, mock_installer_config: InstallerConfig):
    assert not (solution_root_dir / "obfuscate.txt").is_file()
    mock_installer_config.encrypt = True
    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"Could not find file {solution_root_dir / 'obfuscate.txt'}. Make sure the file exists."),
    ):
        setup_solution_folder(SolutionInfo(solution_root_dir), mock_installer_config)


@pytest.fixture
def mock_encrypted_files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source_file1 = tmp_path / "src" / "ansys" / "solutions" / "my_solution" / "factor.txt"
    source_file2 = tmp_path / "src" / "ansys" / "solutions" / "my_solution" / "data.json"
    encrypted_file1 = tmp_path / "src" / "ansys" / "solutions" / "my_solution" / "factor.txt.encrypted"
    encrypted_file2 = tmp_path / "src" / "ansys" / "solutions" / "my_solution" / "data.json.encrypted"

    source_file1.parent.mkdir(parents=True, exist_ok=True)
    source_file1.write_text("original content 1")
    source_file2.write_text("original content 2")
    encrypted_file1.write_text("encrypted content 1")
    encrypted_file2.write_text("encrypted content 2")

    return source_file1, source_file2, encrypted_file1, encrypted_file2


def test_delete_encrypted_files_removes_encrypted_artifacts(
    tmp_path: Path,
    mock_encrypted_files: tuple[Path, Path, Path, Path],
):
    """Verify that delete_encrypted_files removes .encrypted counterparts from solution root."""
    source_file1, source_file2, encrypted_file1, encrypted_file2 = mock_encrypted_files

    encryption_manifest = tmp_path / "encrypt_manifest.txt"
    encryption_manifest.write_text(
        "src/ansys/solutions/my_solution/factor.txt\nsrc/ansys/solutions/my_solution/data.json\n",
    )

    assert encrypted_file1.read_text() == "encrypted content 1"
    assert encrypted_file2.read_text() == "encrypted content 2"

    delete_encrypted_files(tmp_path, encryption_manifest)

    assert not encrypted_file1.exists()
    assert not encrypted_file2.exists()
    assert source_file1.read_text() == "original content 1"
    assert source_file2.read_text() == "original content 2"


def test_delete_encrypted_files_is_idempotent(tmp_path: Path, mock_encrypted_files: tuple[Path, Path, Path, Path]):
    """Verify that delete_encrypted_files safely handles missing encrypted files."""
    source_file, _, encrypted_file, _ = mock_encrypted_files

    encryption_manifest = tmp_path / "encrypt_manifest.txt"
    encryption_manifest.write_text("src/ansys/solutions/my_solution/factor.txt")

    delete_encrypted_files(tmp_path, encryption_manifest)

    assert not encrypted_file.exists()
    assert source_file.read_text() == "original content 1"

    # No encrypted file exists, but cleanup should not fail
    delete_encrypted_files(tmp_path, encryption_manifest)

    # Original file should remain untouched
    assert not encrypted_file.exists()
    assert source_file.read_text() == "original content 1"


def test_delete_encrypted_files_raises_error_on_missing_manifest(tmp_path: Path):
    """Verify that delete_encrypted_files raises exception when manifest file is missing."""
    nonexistent_file = tmp_path / "nonexistent_manifest.txt"
    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"Could not find file {nonexistent_file}. Make sure the file exists."),
    ):
        delete_encrypted_files(tmp_path, nonexistent_file)


@pytest.mark.parametrize(
    "files_file_content",
    [
        "%s\n%s\n",
        "  %s  \n  %s  \n",
        "\n%s\n\n%s\n\n",
        "   \n%s\n\t\n%s\n  \t  \n",
    ],
    ids=["basic", "leading_trailing_spaces", "empty_lines", "whitespace_only_lines"],
)
def test_delete_encrypted_files_ignores_empty_lines(
    tmp_path: Path,
    files_file_content: str,
    mock_encrypted_files: tuple[Path, Path, Path, Path],
):
    """Verify that delete_encrypted_files skips empty lines in the manifest."""
    source_file1, source_file2, encrypted_file1, encrypted_file2 = mock_encrypted_files

    encryption_manifest = tmp_path / "encrypt_manifest.txt"
    encryption_manifest.write_text(
        files_file_content
        % ("src/ansys/solutions/my_solution/factor.txt", "src/ansys/solutions/my_solution/data.json"),
    )

    delete_encrypted_files(tmp_path, encryption_manifest)

    assert not encrypted_file1.exists()
    assert not encrypted_file2.exists()
    assert source_file1.read_text() == "original content 1"
    assert source_file2.read_text() == "original content 2"


def test_delete_encrypted_files_handles_backslash_paths(
    tmp_path: Path,
    mock_encrypted_files: tuple[Path, Path, Path, Path],
):
    """Verify that delete_encrypted_files handles manifest entries with backslashes."""
    source_file, _, encrypted_file, _ = mock_encrypted_files

    encryption_manifest = tmp_path / "encrypt_manifest.txt"
    encryption_manifest.write_text(".\\src\\ansys\\solutions\\my_solution\\factor.txt\n")

    assert encrypted_file.read_text() == "encrypted content 1"

    delete_encrypted_files(tmp_path, encryption_manifest)

    assert not encrypted_file.exists()
    assert source_file.read_text() == "original content 1"


def test_get_solution_package_dir_from_glow_solution_definition(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.platform.solutions.my_solution_dash.solution.definition",
    )

    expected_solution_package_dir = (
        solution_root_dir / "src" / "synopsys" / "platform" / "solutions" / "my_solution_dash"
    )
    expected_solution_package_dir.mkdir(parents=True, exist_ok=True)

    solution_package_dir = get_solution_package_dir(solution_root_dir, "my_solution_dash")

    assert solution_package_dir == expected_solution_package_dir


@pytest.mark.parametrize(
    ("solution_root_dir", "module_name", "expected_namespace_path"),
    [
        ("my-solution-dash", "my_solution_dash", "ansys/solutions"),
        ("synopsys-custom-ns-solution", "custom_ns_solution", "synopsys"),
    ],
    indirect=["solution_root_dir"],
)
def test_get_solution_package_dir_falls_back_to_org_directory_under_src(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
    module_name: str,
    expected_namespace_path: str,
):
    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    solution_package_dir = get_solution_package_dir(solution_root_dir, module_name)

    assert solution_package_dir == solution_root_dir / "src" / expected_namespace_path / module_name


def test_get_solution_module_name_from_glow_solution_definition(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.solutions.my_solution_dash.solution.definition",
    )

    solution_module_name = get_solution_module_name(solution_root_dir)

    assert solution_module_name == "my_solution_dash"


def test_get_solution_module_name_falls_back_to_org_directory_under_src(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    solution_module_name = get_solution_module_name(solution_root_dir)

    assert solution_module_name == "my_solution_dash"


def test_get_solution_module_dotted_path_from_glow_solution_definition(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.platform.solutions.my_solution_dash.solution.definition",
    )

    solution_module_dotted_path = get_solution_module_dotted_path(solution_root_dir, "my_solution_dash")

    assert solution_module_dotted_path == "synopsys.platform.solutions.my_solution_dash"


def test_get_solution_module_dotted_path_falls_back_to_org_directory_under_src(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    solution_module_dotted_path = get_solution_module_dotted_path(solution_root_dir, "my_solution_dash")

    assert solution_module_dotted_path == "ansys.solutions.my_solution_dash"


def test_get_solution_module_name_from_synopsys_namespace(tmp_path: Path) -> None:
    """Namespace resolution via filesystem scan returns the correct module for a single-segment custom namespace."""
    solution_root_dir = tmp_path / "synopsys-custom-ns-solution"
    pkg_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution" / "solution"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "definition.py").write_text("# stub")

    module_name = get_solution_module_name(solution_root_dir)

    assert module_name == "custom_ns_solution"


def test_get_solution_module_dotted_path_from_synopsys_namespace(tmp_path: Path) -> None:
    """Dotted path is built from the single-segment synopsys namespace root."""
    solution_root_dir = tmp_path / "synopsys-custom-ns-solution"
    pkg_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution" / "solution"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "definition.py").write_text("# stub")

    dotted_path = get_solution_module_dotted_path(solution_root_dir, "custom_ns_solution")

    assert dotted_path == "synopsys.custom_ns_solution"


def test_get_solution_package_dir_from_synopsys_namespace(tmp_path: Path) -> None:
    """Package dir resolves to src/synopsys/custom_ns_solution for the custom namespace mock."""
    solution_root_dir = tmp_path / "synopsys-custom-ns-solution"
    expected_pkg_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution"
    (expected_pkg_dir / "solution").mkdir(parents=True)
    (expected_pkg_dir / "solution" / "definition.py").write_text("# stub")

    package_dir = get_solution_package_dir(solution_root_dir, "custom_ns_solution")

    assert package_dir == expected_pkg_dir


def test_get_solution_module_name_from_glow_solution_definition_synopsys(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    """GLOW_SOLUTION_DEFINITION with synopsys single-segment namespace yields correct module name."""
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.custom_ns_solution.solution.definition",
    )

    module_name = get_solution_module_name(solution_root_dir)

    assert module_name == "custom_ns_solution"


def test_get_solution_module_dotted_path_from_glow_solution_definition_synopsys(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    """GLOW_SOLUTION_DEFINITION with synopsys single-segment namespace yields correct dotted path."""
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.custom_ns_solution.solution.definition",
    )

    dotted_path = get_solution_module_dotted_path(solution_root_dir, "custom_ns_solution")

    assert dotted_path == "synopsys.custom_ns_solution"


def test_get_solution_package_dir_from_glow_solution_definition_synopsys(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    """GLOW_SOLUTION_DEFINITION with synopsys single-segment namespace yields correct package dir."""
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.custom_ns_solution.solution.definition",
    )

    expected_package_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution"
    expected_package_dir.mkdir(parents=True, exist_ok=True)

    package_dir = get_solution_package_dir(solution_root_dir, "custom_ns_solution")

    assert package_dir == expected_package_dir


def test_get_solution_package_dir_raises_if_env_resolved_path_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.custom_ns_solution.solution.definition",
    )

    expected_package_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution"

    with pytest.raises(
        FileNotFoundError,
        match=re.escape(
            f"Solution package directory does not exist: {expected_package_dir}",
        ),
    ):
        get_solution_package_dir(solution_root_dir, "custom_ns_solution")


def test_get_solution_namespace_info_raises_on_invalid_glow_solution_definition(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    """get_solution_namespace_info raises ValueError when GLOW_SOLUTION_DEFINITION has invalid format."""

    # Missing ".solution.definition" suffix
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "synopsys.custom_ns_solution")

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Invalid GLOW_SOLUTION_DEFINITION value: 'synopsys.custom_ns_solution'. "
            "Expected format: '<namespace_root>.<module>.solution.definition'.",
        ),
    ):
        get_solution_namespace_info(solution_root_dir)


def test_get_solution_namespace_info_raises_when_no_solution_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """get_solution_namespace_info raises FileNotFoundError when no solution/definition.py exists."""

    solution_root_dir = tmp_path / "empty-solution"
    solution_root_dir.mkdir()
    (solution_root_dir / "src").mkdir()

    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"Could not find solution module under {solution_root_dir / 'src'}."),
    ):
        get_solution_namespace_info(solution_root_dir)


def test_get_solution_namespace_info_raises_when_multiple_solutions_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """get_solution_namespace_info raises ValueError when autodiscovery finds multiple solutions."""

    solution_root_dir = tmp_path / "multi-solution"
    first_solution_dir = solution_root_dir / "src" / "ansys" / "solutions" / "first_solution" / "solution"
    second_solution_dir = solution_root_dir / "src" / "synopsys" / "second_solution" / "solution"
    first_solution_dir.mkdir(parents=True)
    second_solution_dir.mkdir(parents=True)
    (first_solution_dir / "definition.py").write_text("# test")
    (second_solution_dir / "definition.py").write_text("# test")

    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Multiple solution packages were found under "
            f"{solution_root_dir / 'src'}: ['ansys.solutions.first_solution', 'synopsys.second_solution']. "
            "Set GLOW_SOLUTION_DEFINITION to the target solution.",
        ),
    ):
        get_solution_namespace_info(solution_root_dir)


@pytest.mark.parametrize("solution_root_dir", ["synopsys-custom-ns-solution"], indirect=True)
def test_create_solution_metadata_with_synopsys_namespace(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
) -> None:
    """create_solution_metadata writes synopsys namespace fields to solution-metadata.json."""

    (solution_root_dir / "dist" / "solution").mkdir(parents=True, exist_ok=True)
    solution_info = SolutionInfo(solution_root_dir)

    with patch(
        "ansys.saf.desktop.installer._package.solution.get_solution_display_name",
        return_value="Custom NS Solution",
    ):
        create_solution_metadata(solution_info, mock_installer_config)

    metadata_path = solution_root_dir / "dist" / "solution" / "solution-metadata.json"
    assert metadata_path.is_file()
    metadata = json.loads(metadata_path.read_text())
    assert metadata["solution-module-name"] == "custom_ns_solution"
    assert metadata["solution-main-module"] == "synopsys.custom_ns_solution.main"
    assert metadata["solution-name"] == "synopsys-custom-ns-solution"
    assert metadata["solution-display-name"] == "Custom NS Solution"
    assert metadata["solution-version"] == "0.1.dev0"
    assert metadata["solution-backend"] == "uv"


def test_create_solution_metadata_marks_uv_backend(
    tmp_path: Path,
    mock_installer_config: InstallerConfig,
    mocker: pytest_mock.MockerFixture,
) -> None:
    (tmp_path / "dist" / "solution").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "1.0"\n[tool.uv]\n',
        encoding="utf-8",
    )
    mock_installer_config.pyproject_location = tmp_path / "pyproject.toml"
    solution_info = mocker.Mock()
    solution_info.solution_root_dir = tmp_path
    solution_info.solution_module_name = "example"
    solution_info.solution_version = "1.0"
    solution_info.solution_display_name = "Example"
    solution_info.solution_package_name = "example"
    solution_info.solution_module_dotted_path = "ansys.solutions.example"

    create_solution_metadata(solution_info, mock_installer_config)

    metadata = json.loads((tmp_path / "dist" / "solution" / "solution-metadata.json").read_text())
    assert metadata["solution-backend"] == "uv"


@use_poetry_mock_solution
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_no_readme_key_in_pyproject(solution_root_dir: Path, mock_installer_config: InstallerConfig):
    solution_info = SolutionInfo(solution_root_dir)

    pyproject_content = toml.load(mock_installer_config.pyproject_location)
    pyproject_content.setdefault("tool", {}).setdefault("poetry", {}).pop("readme", None)
    with Path.open(mock_installer_config.pyproject_location, "w") as f:
        toml.dump(pyproject_content, f)

    with pytest.raises(
        ValueError,
        match=re.escape(f"No readme file specified in {mock_installer_config.pyproject_location}."),
    ):
        setup_solution_folder(solution_info, mock_installer_config)


@pytest.mark.parametrize(
    "readme_value",
    [["README.md", "README.str"], {"file": "README.md", "content-type": "text/markdown"}],
)
@use_poetry_mock_solution
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_readme_key_is_not_str(
    readme_value: dict[str, str] | list[str],
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
):
    solution_info = SolutionInfo(solution_root_dir)

    pyproject_content = toml.load(mock_installer_config.pyproject_location)
    pyproject_content.setdefault("tool", {}).setdefault("poetry", {})["readme"] = readme_value

    with Path.open(mock_installer_config.pyproject_location, "w") as f:
        toml.dump(pyproject_content, f)

    expected_warning_msg = f"The readme field in {mock_installer_config.pyproject_location} is not a string."
    with pytest.raises(
        TypeError,
        match=re.escape(expected_warning_msg),
    ):
        setup_solution_folder(solution_info, mock_installer_config)


@use_poetry_mock_solution
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_missing_readme_file(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
):
    solution_info = SolutionInfo(solution_root_dir)

    pyproject_content = toml.load(mock_installer_config.pyproject_location)
    readme_value = "README.md"
    pyproject_content.setdefault("tool", {}).setdefault("poetry", {})["readme"] = readme_value

    with Path.open(mock_installer_config.pyproject_location, "w") as f:
        toml.dump(pyproject_content, f)

    # Remove the README.md file to simulate the missing file scenario
    readme_path = solution_root_dir / readme_value
    readme_path.unlink(missing_ok=True)
    with pytest.raises(
        FileNotFoundError,
        match=re.escape(
            f"The readme file {readme_path} does not exist.",
        ),
    ):
        setup_solution_folder(solution_info, mock_installer_config)


@use_poetry_mock_solution
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_readme_random_format(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
):
    solution_info = SolutionInfo(solution_root_dir)

    pyproject_content = toml.load(mock_installer_config.pyproject_location)
    readme_value = "READMEfast.py"
    pyproject_content.setdefault("tool", {}).setdefault("poetry", {})["readme"] = readme_value

    with Path.open(mock_installer_config.pyproject_location, "w") as f:
        toml.dump(pyproject_content, f)

    # Create a README.md file with random content
    (solution_root_dir / readme_value).touch(exist_ok=True)

    with patch("ansys.saf.desktop.installer._package.manage_dependencies.modify_solution_wheel_metadata"):
        setup_solution_folder(solution_info, mock_installer_config)


@use_poetry_mock_solution
@pytest.mark.parametrize("poetry_version", ["1.8.4", "2.5.1"], ids=["poetry_below_2", "poetry_2_or_higher"])
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_mock_solution(
    mock_installer_config: InstallerConfig,
    solution_root_dir: Path,
    poetry_version: str,
):
    solution_info = SolutionInfo(solution_root_dir)
    pyproject_path = solution_root_dir / "pyproject.toml"
    pyproject = toml.load(pyproject_path)
    pyproject["build-system-requirements"]["build-system-version"] = poetry_version
    pyproject_path.write_text(toml.dumps(pyproject))
    with patch("ansys.saf.desktop.installer._package.manage_dependencies.modify_solution_wheel_metadata"):
        setup_solution_folder(solution_info, mock_installer_config)
    build_executable_installer(
        solution_folder=solution_info.solution_root_dir / "dist" / "solution",
        output_folder=solution_info.solution_root_dir / "dist",
        solution_display_name=solution_info.solution_display_name,
    )

    # documentation is built
    expected_doc_html = solution_root_dir / "doc" / "build" / "html" / "index.html"
    assert expected_doc_html.is_file()

    # documentation is copied to src/
    assert (
        solution_root_dir / "src" / "ansys" / "solutions" / "my_solution_dash_old" / "html-doc" / "index.html"
    ).read_text() == "mock_documentation"

    # solution wheel is generated
    expected_wheel = solution_root_dir / "dist" / "ansys_solutions_my_solution_dash_old-0.1.dev0-py3-none-any.whl"
    assert expected_wheel.is_file()

    # pyinstaller-based executable is generated
    expected_exec = (
        solution_root_dir / "dist" / ("test-installer.exe" if platform.system() == "Windows" else "test-installer")
    )
    assert expected_exec.is_file()

    # metadata, version and desktop_deployment scripts are generated
    solution_location = solution_root_dir / "dist" / "solution"
    assert (solution_location / "solution-metadata.json").is_file()
    assert (solution_location / "version.txt").is_file()
    assert (solution_location / "solution_desktop_deployment.py").is_file()

    # python binary is downloaded
    python_dir = solution_location / "third_party" / "python"
    assert next(python_dir.glob(f"**/{'python.exe' if platform.system() == 'Windows' else 'python3'}")).is_file()

    # local pyproject.toml wheels are copied to the definitions directory
    expected_wheel_dir = solution_root_dir / "dist" / "solution" / "definitions" / "my_solution_dash_old"
    current_platform = platform.system()
    expected_wheel_name = CUSTOM_PACKAGE_FOR_TEST_2_WHEEL_NAMES.get(current_platform)
    assert expected_wheel_name is not None, f"Unsupported platform: {current_platform}"
    assert (expected_wheel_dir / expected_wheel_name).is_file()
    dist_pyproject = expected_wheel_dir / "pyproject.toml"
    # And wheel paths are updated in the dist pyproject.toml
    assert "build_assets" not in dist_pyproject.read_text()

    # pip and poetry requirement files are generated with the correct content
    expected_tools_dir = solution_root_dir / "dist" / "solution" / "definitions" / "my_solution_dash_old" / "tools"
    pip_requirements = expected_tools_dir / "pip_requirements.txt"
    poetry_requirements = expected_tools_dir / "poetry_requirements.txt"
    assert pip_requirements.is_file()
    assert "pip==" in pip_requirements.read_text()
    assert poetry_requirements.is_file()
    pyproject = toml.load(solution_root_dir / "pyproject.toml")
    assert pyproject["build-system-requirements"]["build-system-version"] == poetry_version
    poetry_requirements_content = poetry_requirements.read_text()
    assert f"poetry=={poetry_version}" in poetry_requirements_content
    if Version(poetry_version) >= Version("2.0.0"):
        assert "poetry-plugin-export>=1.8" in poetry_requirements_content
    else:
        assert "poetry-plugin-export" not in poetry_requirements_content


@pytest.mark.parametrize("error_type", ["failure_to_build", "no_output"])
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_without_documentation(
    error_type: str,
    mock_installer_config: InstallerConfig,
    solution_root_dir: Path,
    mocker: pytest_mock.MockerFixture,
):
    solution_info = SolutionInfo(solution_root_dir)

    expected_doc_html = solution_root_dir / "doc" / "build" / "html"
    solution_html_doc = solution_root_dir / "src" / "ansys" / "solutions" / "my_solution_dash" / "html-doc"

    if error_type == "failure_to_build":
        shutil.rmtree(solution_root_dir / "doc")
        expected_warning_msg = (
            "Failed to build documentation: mock error when building doc\n"
            f"Fix the errors or manually copy the documentation to {solution_html_doc}."
        )
    elif error_type == "no_output":
        shutil.rmtree(solution_root_dir / "doc" / "source")
        expected_warning_msg = f"Documentation built directory {expected_doc_html} does not exist. Skipping..."
    else:
        pytest.fail(f"Invalid parameter value {error_type=}")

    mock_log_warning = mocker.patch("logging.Logger.warning")

    solution_display_name = "Fake Solution Display Name"
    with patch("ansys.saf.desktop.installer._package.manage_dependencies.modify_solution_wheel_metadata"):
        setup_solution_folder(solution_info, mock_installer_config)
    build_executable_installer(
        solution_folder=solution_root_dir / "dist" / "solution",
        output_folder=solution_root_dir / "dist",
        solution_display_name=solution_display_name,
    )

    # documentation build proc didn't generate any html output
    assert not expected_doc_html.is_dir()

    # documentation is not copied to src/
    assert not solution_html_doc.is_dir()

    # Expected msg is shown to user
    assert mock_log_warning.call_count == 2
    assert mock_log_warning.call_args_list[0][0][0] == expected_warning_msg

    # Rest of files are successfully generated
    solution_dist_dir = solution_root_dir / "dist"
    assert (solution_dist_dir / "ansys_solutions_my_solution_dash-0.1.dev0-py3-none-any.whl").is_file()
    assert (
        solution_dist_dir / ("test-installer.exe" if platform.system() == "Windows" else "test-installer")
    ).is_file()
    assert (solution_dist_dir / "solution" / "solution-metadata.json").is_file()
    assert (solution_dist_dir / "solution" / "version.txt").is_file()
    assert (solution_dist_dir / "solution" / "solution_desktop_deployment.py").is_file()
    python_dir = solution_dist_dir / "solution" / "third_party" / "python"
    assert next(python_dir.glob(f"**/{'python.exe' if platform.system() == 'Windows' else 'python3'}")).is_file()


@pytest.fixture
def mock_encrypt_solution(mocker: pytest_mock.MockerFixture) -> None:
    # Mock encrypt_solution to simulate the encryption process without requiring translation-utilities:
    # delete original files and create encrypted versions

    def _mock_encrypt_solution(encryption_file: Path, root: Path, encryption_key: str | None = None):
        for line in encryption_file.read_text().splitlines():
            file_path_str = line.strip().replace("\\", "/")
            if not file_path_str:
                continue
            original = root / file_path_str
            if original.is_file():
                encrypted = original.with_suffix(original.suffix + ".encrypted")
                encrypted.write_text(original.read_text() + " [encrypted]")
                original.unlink()

    mocker.patch(
        "ansys.saf.desktop.installer._package.manage_dependencies.encrypt_solution",
        side_effect=_mock_encrypt_solution,
    )


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name", "mock_encrypt_solution")
def test_encryption_workflow_when_building_and_staging_solution_packages(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
    mocker: pytest_mock.MockerFixture,
):
    """Verify that encrypted files are cleaned from solution root after encryption build."""
    # Mock the build_wheel and download functions to avoid wheel file processing
    mocker.patch.object(manage_dependencies, "build_solution_wheel")
    mocker.patch.object(manage_dependencies, "_get_poetry_packages_with_wheel_url_dependencies", return_value=[])
    mocker.patch.object(manage_dependencies, "_stage_poetry_internal_dependencies")
    mocker.patch.object(manage_dependencies, "modify_solution_wheel_metadata")
    copy_files_spy = mocker.spy(manage_dependencies, "copy_files")
    delete_encrypted_files_spy = mocker.spy(manage_dependencies, "delete_encrypted_files")

    # Setup: Create encryption manifest with a file to encrypt
    solution_module_name = "my_solution_dash"
    file_to_encrypt = (
        solution_root_dir / "src" / "ansys" / "solutions" / solution_module_name / "method_assets" / "factor.txt"
    )
    file_to_encrypt.parent.mkdir(parents=True, exist_ok=True)
    file_to_encrypt.write_text("original content")
    encryption_manifest = solution_root_dir / "encrypt_manifest.txt"
    encryption_manifest.write_text(f"src/ansys/solutions/{solution_module_name}/method_assets/factor.txt\n")

    # Execute: build and stage solution packages with encryption enabled
    mock_installer_config.encrypt = True
    mock_installer_config.encryption_file = encryption_manifest

    definitions_folder = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name
    definitions_folder.mkdir(parents=True, exist_ok=True)

    venv_python_exec = solution_root_dir / ".venv" / "Scripts" / "python.exe"
    venv_python_exec.parent.mkdir(parents=True, exist_ok=True)
    venv_python_exec.touch()

    build_and_stage_solution_packages(
        definitions_folder,
        venv_python_exec,
        solution_root_dir,
        solution_module_name,
        "Test Solution",
        mock_installer_config,
        "3.11.14",
    )

    # Assert: Original file is restored, encrypted file is cleaned up
    encrypted_file = file_to_encrypt.with_suffix(".txt.encrypted")
    assert not encrypted_file.exists()
    assert file_to_encrypt.read_text() == "original content"
    assert copy_files_spy.call_count == 2
    assert delete_encrypted_files_spy.call_count == 1


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name", "mock_encrypt_solution")
def test_encryption_workflow_when_solution_package_build_fails_after_encryption(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
    mocker: pytest_mock.MockerFixture,
):
    """Verify finally restores and cleans files when wheel build fails after encryption."""
    mocker.patch.object(
        manage_dependencies,
        "build_solution_wheel",
        side_effect=RuntimeError("mock wheel build failure"),
    )
    copy_files_spy = mocker.spy(manage_dependencies, "copy_files")
    delete_encrypted_files_spy = mocker.spy(manage_dependencies, "delete_encrypted_files")

    # Setup: Create encryption manifest with a file to encrypt
    solution_module_name = "my_solution_dash"
    file_to_encrypt = (
        solution_root_dir / "src" / "ansys" / "solutions" / solution_module_name / "method_assets" / "factor.txt"
    )

    file_to_encrypt.parent.mkdir(parents=True, exist_ok=True)
    file_to_encrypt.write_text("original content")
    encryption_manifest = solution_root_dir / "encrypt_manifest.txt"
    encryption_manifest.write_text(f"src/ansys/solutions/{solution_module_name}/method_assets/factor.txt\n")

    # Execute: build and stage solution packages with encryption enabled
    mock_installer_config.encrypt = True
    mock_installer_config.encryption_file = encryption_manifest

    definitions_folder = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name
    definitions_folder.mkdir(parents=True, exist_ok=True)

    venv_python_exec = solution_root_dir / ".venv" / "Scripts" / "python.exe"
    venv_python_exec.parent.mkdir(parents=True, exist_ok=True)
    venv_python_exec.touch()

    with pytest.raises(RuntimeError, match="mock wheel build failure"):
        build_and_stage_solution_packages(
            definitions_folder,
            venv_python_exec,
            solution_root_dir,
            solution_module_name,
            "Test Solution",
            mock_installer_config,
            "3.11.14",
        )

    # Assert: Original file is restored, encrypted file is cleaned up
    encrypted_file = file_to_encrypt.with_suffix(".txt.encrypted")
    assert not encrypted_file.exists()
    assert file_to_encrypt.read_text() == "original content"
    assert copy_files_spy.call_count == 2
    assert delete_encrypted_files_spy.call_count == 1


@pytest.fixture
def copy_files_setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create source files and directories for copy_files tests."""
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    files_file_path = tmp_path / "files_to_encrypt.txt"
    source_dir.mkdir()
    target_dir.mkdir()
    (source_dir / "file1.txt").write_text("content1")
    (source_dir / "sub").mkdir()
    (source_dir / "sub" / "file2.txt").write_text("content2")
    return source_dir, target_dir, files_file_path


@pytest.mark.parametrize(
    "files_file_content",
    [
        "file1.txt\nsub/file2.txt\n",
        "  file1.txt  \n  sub/file2.txt  \n",
        "\nfile1.txt\n\nsub/file2.txt\n\n",
        "   \nfile1.txt\n\t\nsub/file2.txt\n  \t  \n",
        "file1.txt\nsub\\file2.txt\n",
    ],
    ids=["basic", "leading_trailing_spaces", "empty_lines", "whitespace_only_lines", "backslash_paths"],
)
def test_copy_files(copy_files_setup: tuple[Path, Path, Path], files_file_content: str):
    source_dir, target_dir, files_file_path = copy_files_setup
    files_file_path.write_text(files_file_content)

    copy_files(source_dir, target_dir, files_file_path)

    # Act: files are copied to target directory with same relative paths,
    # and original content is preserved
    assert (target_dir / "file1.txt").read_text() == "content1"
    assert (target_dir / "sub" / "file2.txt").read_text() == "content2"
    assert (source_dir / "file1.txt").read_text() == "content1"
    assert (source_dir / "sub" / "file2.txt").read_text() == "content2"


def test_copy_files_missing_manifest(copy_files_setup: tuple[Path, Path, Path]):
    source_dir, target_dir, files_file_path = copy_files_setup
    with pytest.raises(FileNotFoundError, match="Could not find file"):
        copy_files(source_dir, target_dir, files_file_path)


def test_copy_files_missing_source_file(copy_files_setup: tuple[Path, Path, Path]):
    source_dir, target_dir, files_file_path = copy_files_setup
    files_file_path.write_text("nonexistent.txt\n")
    with pytest.raises(FileNotFoundError, match="source File"):
        copy_files(source_dir, target_dir, files_file_path)


@pytest.fixture
def third_party_folder(tmp_path: Path) -> Path:
    tp = tmp_path / "third_party"
    (tp / "python").mkdir(parents=True)
    (tp / "python" / "libssl-3.dll").write_bytes(b"\x4d\x5a" + b"\x00" * 10)
    (tp / "python" / "python.exe").write_bytes(b"\x4d\x5a" + b"\x00" * 10)
    (tp / "data.txt").write_text("payload")
    return tmp_path


@pytest.mark.parametrize(
    ("platform_system", "has_third_party", "should_zip"),
    [
        ("Windows", True, True),
        ("Windows", False, False),
        ("Linux", True, False),
    ],
    ids=["windows_zips", "windows_missing_dir", "linux_noop"],
)
def test_zip_third_party(
    third_party_folder: Path,
    mocker: pytest_mock.MockerFixture,
    platform_system: str,
    has_third_party: bool,
    should_zip: bool,
) -> None:
    """Test _zip_third_party across platforms and file existence scenarios."""
    mocker.patch("ansys.saf.desktop.installer._package.solution_package.platform.system", return_value=platform_system)

    if not has_third_party:
        import shutil as _shutil

        _shutil.rmtree(third_party_folder / "third_party")

    result = _zip_third_party(third_party_folder)

    if should_zip:
        assert result is not None
        assert result == third_party_folder / "third_party.zip"
        assert result.is_file()
        assert not (third_party_folder / "third_party").exists()
        # Verify ZIP contains all files
        import zipfile as _zipfile

        with _zipfile.ZipFile(result) as zf:
            names = set(zf.namelist())
            assert {"python/libssl-3.dll", "python/python.exe", "data.txt"}.issubset(names)
            # Verify no third_party/ prefix in entries
            for name in names:
                assert not name.startswith("third_party/"), f"ZIP entry has unexpected prefix: {name}"
    else:
        assert result is None
        if has_third_party:
            assert (third_party_folder / "third_party").is_dir()


@pytest.mark.parametrize(
    "zip_exists",
    [
        True,
        False,
        None,
    ],
    ids=["valid_zip", "missing_zip", "none_zip_path"],
)
def test_restore_third_party(
    third_party_folder: Path,
    zip_exists: bool | None,
) -> None:
    """Test _restore_third_party with various ZIP existence scenarios."""
    expected_extracted = bool(zip_exists) and platform.system() == "Windows"

    if zip_exists is True:
        zip_path = _zip_third_party(third_party_folder)
        if platform.system() == "Windows":
            assert zip_path is not None
    elif zip_exists is False:
        zip_path = third_party_folder / "third_party.zip"
    else:  # None
        zip_path = None

    _restore_third_party(third_party_folder, zip_path)

    third_party = third_party_folder / "third_party"
    if expected_extracted:
        assert (third_party / "python" / "libssl-3.dll").is_file()
        assert (third_party / "python" / "python.exe").is_file()
        assert (third_party / "data.txt").read_text() == "payload"
        assert not (third_party_folder / "third_party.zip").is_file()
    else:
        # no-op: pre-existing third_party directory is unchanged
        assert (third_party / "data.txt").read_text() == "payload"
        assert not (third_party_folder / "third_party.zip").is_file()
